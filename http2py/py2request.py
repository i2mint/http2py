"""
Won't show the details here, but if you are used to it's not that hard,
you just need to find the definition of the API, read it, figure out what part
of the request you need in the URL and what you need to put in the "payload",
figure out how those _inputs_ of the request need to be formated,
construct the URL and the payload according to your newly acquired knowledge of this specific API,
make a web request (say with `urllib.request` or `requests`),
extract the information you need from the response object (often in `.contents` or `.json()`),
and often process the data further to get it in the format you can use it directly
(say a list, a dict, a dataframe, a numpy array, etc.).

And if you're experienced, and have felt the pain of needing to reuse or adapt your code,
you'll clean things up as soon as you figure this puzzle out.
You'll divide your code into separate concerns, encapsulate these concerns in functions and classes,
and offer a simple, intuitive, python-like interface that reflects the simplicity
of what you're actually doing: Just getting some data. Something like:

```
nice_python_obj_I_can_use_directly = get_that_darn_data(query, using, my, words, values, and, defaults='here')
```

The details being hidden away, as they should.

And that's fine. You've done well. Congratulate yourself, you deserve it.

Now do that again and again and again, and sometimes under the pressure of a deadline that depends on this data being acquired.

Are you enjoying yourself?

There must be a better way...
"""
from functools import wraps
from inspect import signature, Parameter
from glom import glom
from requests import request
import string
# import io
import re
from typing import Any, Union

from http2py.util import I2mintModuleNotFoundErrorNiceMessage, is_jsonable
from http2py.default_configs import default_json_output_trans, default_text_output_trans, default_content_output_trans

with I2mintModuleNotFoundErrorNiceMessage():
    from i2.util import inject_method, imdict
    from i2.signatures import set_signature_of_func, KO

DFLT_PORT = 5000
DFLT_BASE_URL = 'http://localhost:{port}'.format(port=DFLT_PORT)
DFLT_REQUEST_METHOD = 'GET'
DFLT_REQUEST_KWARGS = imdict({'method': DFLT_REQUEST_METHOD, 'url': ''})

pytype_for_oatype = {
    'string': str, 'number': Union[float, int], 'integer': int, 'array': list, 'object': dict, 'boolean': bool, '{}': Any
}

def identity_func(x):
    return x


class DebugOptions:
    print_request_kwargs = 'print_request_kwargs'
    return_request_kwargs = 'return_request_kwargs'


def mk_default_completion_validator(dflt_kwargs=DFLT_REQUEST_KWARGS):
    def default_completion_validator(kwargs):
        return dict(dflt_kwargs, **kwargs)

    return default_completion_validator


def all_necessary_fields_validator(kwargs):
    assert 'method' in kwargs and 'url' in kwargs, "Need both a method and a url field!"
    return kwargs


def _ensure_list(x):
    if isinstance(x, str):
        return [x]
    return x


def mk_param_spec_from_arg_schema(arg, required=False):
    spec_dict = {
        'name': arg['name'],
    }
    if 'default' in arg:
        spec_dict['default'] = (arg['default'])
    elif not arg.get('required', required):
        spec_dict['default'] = None
    else:
        spec_dict['default'] =Parameter.empty
    if 'type' in arg:
        spec_dict['annotation'] = arg['type']
    if 'kind' in arg:
        spec_dict['kind'] = arg['kind']
    else:
        spec_dict['kind'] = KO
    return spec_dict


def mk_request_function(method_spec, *, function_kind='method', dispatch=request):
    """
    Makes function that will make http requests for you, on your own terms.

    Specify what API you want to talk to, and how you want to talk to it (and it talk back to you), and
    get a function that does exactly that.

    Essentially, this factory function allows you to take an API specification, specify how you want it to
    relate to python objects (how to convert input arguments to API elements, and how to convert the response of
    the request, for instance), and get a method that is ready to be used.

    What does a method_spec contain?
    Well... consider first this. The core of this code is this:
    ```
        request_kwargs = dict(**method_spec['request_kwargs'])  # to make a copy
        ...  # a bunch more code that updates request_kwargs according to other keys of method_spec
        ...  # ... and some other debugging hooks
        r = request(**request_kwargs)  # call the request
        if 'output_trans' in method_spec:  # see if there's an output_trans function
            r = method_spec['output_trans'](r)  # ... if so, use it to extract what you want from the response
        return r
    ```
    So you can do almost everything you need with one single key: `'request_kwargs'` and `'output_trans'` alone.
    But there wouldn't be as much advantage over just calling requests if that's all there was to it,
    so we offer some other special keys to cover some of the common patterns.
        - 'method':
        - 'url_template': Specify the url, but with named placeholders: Example `'http://base.com/{user}/{action}'`.
        - 'json_arg_names': Specify the names of arguments of the function that should be put in the json load
        - 'debug': 'print_request_kwargs' or 'return_request_kwargs'
        - 'input_trans': Function applied to
        - 'output_trans': A function applied to response object to extract what we want to return.
        - 'wraps': A function whose signature we should use as the output's function's signature

    :param method_spec: Specification of how to convert arguments of the function that is being made to an http request.
    :return: A function.
        Note: I say "function", but the function is meant to be a method, so the function has a self as first argument.
        That argument is ignored.

    """
    original_spec = method_spec
    method_spec = method_spec.copy()  # make a copy
    method_spec['input_trans'] = method_spec.get('input_trans', None) or {}

    request_kwargs = method_spec.get('request_kwargs', {}).copy()
    method = method_spec.pop('method',
                             request_kwargs.pop('method',
                                                DFLT_REQUEST_METHOD))
    path_arg_names = _ensure_list(method_spec.get('path_arg_names', []))
    query_arg_names = _ensure_list(method_spec.get('query_arg_names', []))
    body_arg_names = _ensure_list(method_spec.get('body_arg_names', []))
    arg_specs = method_spec.get('arg_specs', [])
    formatted_arg_specs = [mk_param_spec_from_arg_schema(arg) for arg in arg_specs]
    func_args = path_arg_names + query_arg_names + body_arg_names

    debug = method_spec.pop('debug', None)
    if 'debug' in method_spec:
        debug = method_spec['debug']

    output_trans = method_spec.pop('output_trans', None)
    if output_trans is None:
        response_type = method_spec.get('response_type', 'text/plain')
        if response_type == 'text/plain':
            output_trans = default_text_output_trans
        if response_type == 'application/json':
            output_trans = default_json_output_trans
        else:
            output_trans = default_content_output_trans

    wraps_func = method_spec.pop('wraps', None)

    # TODO: inject a signature, and possibly a __doc__ in this function
    def request_func(*args, **kwargs):

        def get_req_param_key():
            content_type = method_spec.get('content_type', 'text/plain')
            if content_type == 'text/plain':
                return 'data'
            if content_type == 'multipart/form-data':
                return 'files'
            if content_type == 'application/octet-stream':
                return 'stream'

        kwargs = dict(kwargs, **{argname: argval for argname, argval in zip(func_args, args)})

        # convert argument types TODO: Not efficient. Might could be revised.
        for arg_name, converter in method_spec.get('input_trans', {}).items():
            if arg_name in kwargs:
                kwargs[arg_name] = converter(kwargs[arg_name])

        # making the request_kwargs ####################################################################################
        _request_kwargs = dict(**request_kwargs)  # to make a copy
        url = None
        if 'url_template' in method_spec:
            url_template = method_spec['url_template']
            # Check if the url template already have parameters, add them otherwise
            if query_arg_names and not re.search("^.*\?((.*=.*)(&?))+$", url_template):
                url_arg_parts = [f'{x}={{{x}}}' for x in query_arg_names if x in kwargs]
                url_args = '&'.join(url_arg_parts)
                url_template += f'?{url_args}'
            url = url_template.format(**kwargs)
        elif 'url' in method_spec:
            url = method_spec['url']

        json = {k: v for k, v in kwargs.items() if is_jsonable(v)}
        _request_kwargs['json'] = json
        remaining_kwargs = {k: v for k, v in kwargs.items() if k not in json}
        if remaining_kwargs:
            req_param_key = get_req_param_key()
            _request_kwargs[req_param_key] = {k: v for k, v in remaining_kwargs.items() if k in body_arg_names}

        if debug is not None:
            if debug == 'print_request_kwargs':
                print(_request_kwargs)
            elif debug == 'return_request_kwargs':
                return _request_kwargs

        r = dispatch(method, url, **_request_kwargs)
        if callable(output_trans):
            return output_trans(r)
        return r

    if function_kind == 'method':
        _request_func = request_func

        def request_func(self, *args, **kwargs):
            return _request_func(*args, **kwargs)

    if wraps_func:
        return wraps(wraps_func)(request_func)
    else:
        if formatted_arg_specs:
            if function_kind == 'method':
                set_signature_of_func(request_func, ['self'] + formatted_arg_specs)
            elif function_kind == 'function':
                set_signature_of_func(request_func, formatted_arg_specs)

    request_func.original_spec = original_spec
    request_func.func_args = func_args
    request_func.debug = debug
    request_func.method_spec = method_spec
    funcname = method_spec.get('method_name', None)
    if funcname:
        request_func.__name__ = funcname
    docstring = method_spec.get('docstring', None)
    if docstring:
        request_func.__doc__ = docstring

    assert callable(output_trans), f'output_trans {output_trans} is not callable, try again'
    return request_func


DFLT_METHOD_FUNC_FROM_METHOD_SPEC = mk_request_function

str_formatter = string.Formatter()


class Py2Request(object):
    """ Make a class that has methods that offer a python interface to web requests """

    def __init__(self, method_specs=None,
                 method_func_from_method_spec=DFLT_METHOD_FUNC_FROM_METHOD_SPEC, **kwargs):
        """
        Initialize the object with web request calling methods.
        You can also just make an empty Py2Request object, and inject methods later on, one by one.


        :param method_specs:  A {method_name: method_spec,...} dict that specifies
            what methods to create (the method_name part) and what that method should do (the method_spec part).
            Notice that there's no restriction on method_specs, but by default (becauise
        :param method_func_from_method_spec: The function that makes an actual method (function, which will be bounded)
            from the method_specs

        Notice that there's no restriction on the method_spec (singular) values of the method_specs dict.
        Indeed, it could be any object that is understood by the method_func_from_method_spec function, that
        would result in a function that can be "injected" as a method of Py2Request.

        In a sense, `method_func_from_method_spec` is your compiler, and the values of `method_specs` are the
        data/code you give to that compiler make produce a function for you.

        See `mk_request_function` function. Either to see what should be in the `method_specs` dict,
        or to find inspiration on how you could write your own `method_func_from_method_spec`.

        >>> import re
        >>> from collections import Counter
        >>> from functools import lru_cache
        >>> # Defining the functions we'll use
        >>> def print_content(r):
        ...     print(r.text)
        >>> def dict_of_json(r):
        ...     return json.loads(r.content)
        >>> tokenizer = re.compile('\w+').findall
        >>> # Defining the specs
        >>> method_specs = {
        ...     'google_google': {
        ...         'request_kwargs': {
        ...             'url': 'https://www.google.com/search?q=google'
        ...         }
        ...     },
        ...     'search_google': {
        ...         'url_template': 'https://www.google.com/search?q={search_term}',
        ...         'query_arg_names': ['search_term'],  # only needed if you want to use unnamed arguments in your method
        ...         'output_trans': lambda r: r.text,
        ...     },
        ...     'search_google_and_count_tokens': {
        ...         'url_template': 'https://www.google.com/search?q={search_term}',
        ...         'output_trans': lambda r: Counter(tokenizer(r.text)).most_common()
        ...     },
        ...     'my_ip': {
        ...         'url_template': 'https://api.ipify.org?format=json',
        ...         'output_trans': dict_of_json,
        ...         'method_wrap': lru_cache()
        ...     },
        ...     'print_ip_location': {
        ...         'url_template': 'http://ip-api.com/#{ip_address}',
        ...         'output_trans': print_content
        ...     },
        ... }
        >>> pr = Py2Request(method_specs=method_specs)
        >>> html = pr.search_google('convention over configuration')
        >>> html[:14].lower()
        '<!doctype html'
        >>> # And I'll let the reader try the other requests, whose results are not stable enough to test like this

        """
        self._method_specs = dict(method_specs or {}, **kwargs)
        self._dflt_method_func_from_method_spec = method_func_from_method_spec
        self._process_method_specs()

        for method_name, method_spec in self._method_specs.items():
            self._inject_method(method_name, method_spec, method_func_from_method_spec)

    def _process_method_specs(self):
        if self._dflt_method_func_from_method_spec == mk_request_function:
            for method_name, method_spec in self._method_specs.items():
                if 'args' not in method_spec and 'url_template' in method_spec:
                    method_spec['args'] = list(filter(bool,
                                                      (x[1] for x in str_formatter.parse(method_spec['url_template']))))

    def _inject_method(self, method_name, method_spec, method_func_from_method_spec=None):
        method_wrap = None
        if not callable(method_spec):
            method_spec = dict(**method_spec)
            args = []
            if isinstance(method_spec, dict):
                args = method_spec.get('args', [])
            method_wrap = method_spec.pop('method_wrap', None)
            if method_func_from_method_spec is None:
                method_func_from_method_spec = self._dflt_method_func_from_method_spec
            method_spec = method_func_from_method_spec(method_spec)
        inject_method(self, method_spec, method_name)

        if method_wrap is not None:
            setattr(self, method_name, method_wrap(getattr(self, method_name)))


class UrlMethodSpecsMaker:
    """
    Utility to help in making templated method_specs dicts to be used to define a Py2Request object.
    """

    def __init__(self, url_root, constant_url_query=None, **constant_items):
        r"""
        Make a method_spec factory.

        Args:
            url_root: The absolute prefix of all 'url_template' keys
            constant_url_query: The dict specifying the query part of the url_template that should appear in
                all url_templates (used for example, to specify api keys)
            **constant_items: Other dict entries that should be systematically created

        Intention pasted below, but commenting out because some errors:

        # >>> mk_specs = UrlMethodSpecsMaker(
        # ...     url_root='http://myapi.com',
        # ...     constant_url_query={'apikey': 'SECRET', 'fav': 42},
        # ...     output_trans=lambda response: response.json())
        # >>>
        # >>> s = mk_specs(route='/search', url_queries={'q': 'search_term', 'limit': 'n'})
        # >>> assert list(s.keys()) == ['url_template', 'args', 'output_trans']
        # >>> s['url_template']
        # 'http://myapi.com/search?apikey=SECRET&fav=42&q={search_term}&limit={n}'
        # >>> s['args']
        # ['search_term', 'n']
        # >>>
        # >>> s = mk_specs(route='/actions/poke', url_queries='user')
        # >>> s['url_template']
        # 'http://myapi.com/actions/poke?apikey=SECRET&fav=42&user={user}'
        # >>> s['args']
        # ['user']
        # >>>
        # >>> s = mk_specs('/actions/msg', ['user', 'msg'])
        # >>> s['url_template']
        # 'http://myapi.com/actions/msg?apikey=SECRET&fav=42&user={user}&msg={msg}'
        # >>> s['args']
        # ['user', 'msg']
        """
        self.url_root = url_root
        self.constant_url_query = constant_url_query or {}
        # if constant_url_query is None:
        #     self.constant_url_suffix = ''
        # else:
        #     self.constant_url_suffix = '?' + '&'.join(
        #         map(lambda kv: f'{kv[0]}={kv[1]}', constant_url_query.items()))
        self.constant_items = constant_items

    def __call__(self, route='', url_queries=None, **more_url_queries):
        d = {}
        url_template = self.url_root + route
        if url_queries is None:
            d = {'url_template': url_template}
        else:
            if isinstance(url_queries, str):
                url_queries = {url_queries: url_queries}
            elif isinstance(url_queries, (list, tuple, set)):
                url_queries = {name: name for name in url_queries}
            # assert the general case where url query (key) and arg (val) names are different
            assert isinstance(url_queries, dict), "url_queries should be a dict"
            url_queries = dict(self.constant_url_query, **dict(url_queries, **more_url_queries))
            url_template += '?' + '&'.join(
                map(lambda kv: f'{kv[0]}={{{kv[1]}}}', url_queries.items()))
            d = {'url_template': url_template, 'args': list(url_queries.values())}
        return dict(d, **self.constant_items)


def raw_response_on_error(func):
    """A useful output trans decorator that will return the raw response if the output_trans raises
    an error.
    The response object will also contain the error that was raised,
    in the response.output_trans_error attribute."""

    @wraps(func)
    def _func(response):
        try:
            return func(response)
        except BaseException as e:
            response.output_trans_error = e
            return response

    return _func


def mk_method_spec_from_openapi_method_spec(openapi_method_spec,
                                            method='post',
                                            url_template='',
                                            content_type='application/json',
                                            input_trans=None,
                                            output_trans=None):
    path_arg_names = []
    query_arg_names = []
    body_arg_names = []
    arg_specs = []
    if 'parameters' in openapi_method_spec:
        params = openapi_method_spec['parameters']
        for param in params:
            argname = param['name']
            argtype = param['type']
            arg_spec = {'name': argname, 'type': pytype_for_oatype[argtype]}
            if param.get('in', 'path') == 'path':
                arg_spec['required'] = True
                path_arg_names.append(argname)
            else:
                if param.get('required'):
                    arg_spec['required']   = True
                elif 'default' in param:
                    arg_spec['default'] = param['default']
                query_arg_names.append(argname)
            arg_specs.append(arg_spec)
    if 'requestBody' in openapi_method_spec:
        body_properties = glom(openapi_method_spec, f'requestBody.content.{content_type}.schema.properties', default={})
        required_properties = glom(openapi_method_spec, f'requestBody.content.{content_type}.schema.required', default=[])
        for argname, details in body_properties.items():
            body_arg_names.append(argname)
            argtype = details['type']
            # TODO: fully support typed dict and typed iterable types
            arg_spec = {'name': argname, 'type': pytype_for_oatype[argtype]}
            if 'default' in details:
                arg_spec['default'] = details['default']
            if argname in required_properties:
                arg_spec['required'] = True
            arg_specs.append(arg_spec)


    method_spec = dict(
        method=method, url_template=url_template, input_trans=input_trans, output_trans=output_trans,
        path_arg_names=path_arg_names, query_arg_names=query_arg_names, body_arg_names=body_arg_names, 
        method_name=openapi_method_spec.get('x-method_name', ''),
        docstring=openapi_method_spec.get('description', ''), content_type=content_type, 
        response_type=next(iter(glom(openapi_method_spec, f'responses.200.content'))),
        arg_specs=arg_specs
    )
    return method_spec


##### Open api stuff TODO: To move ###########################################
from inspect import Parameter, Signature
from typing import Union, Callable, Iterable
from typing import Mapping as MappingType

PK = Parameter.POSITIONAL_OR_KEYWORD

ParamsType = Iterable[Parameter]
ParamsAble = Union[ParamsType, MappingType[str, Parameter], Callable]


def _params_from_props(openapi_props):
    for name, p in openapi_props.items():
        yield Parameter(name=name, kind=PK,
                        default=p.get('default', Parameter.empty),
                        annotation=p.get('type', Parameter.empty))


def add_annots_from_openapi_props(func, openapi_props):
    func.__signature__ = Signature(_params_from_props(openapi_props))
    return func


# def get_props_for_func(func, openapi_spec):
#     path = func_to_path(func)
#     t = openapi_spec["paths"][func_to_path(func)]
#     t = t.get('post', t.get('get', None))  # make more robust
#     assert t is not None
#     # TODO: glommify
#     return t['requestBody']['content']['application/json']['schema']['properties']


def _get_path_spec(path, openapi_spec):
    return openapi_spec['paths'][path]


def mk_request_func_from_openapi_spec(path, openapi_spec, method='post', content_type='application/json',
                                      input_trans=None, output_trans=None):
    base_url = openapi_spec['servers'][0]['url']
    if base_url.endswith('/'):
        base_url = base_url[:-1]  # TODO: need a urljoin instead of this hack!
    path_spec = _get_path_spec(path, openapi_spec)
    url = base_url + path  # TODO: url join
    method = method or next(iter(path_spec))
    spec = path_spec[method]
    method_spec = mk_method_spec_from_openapi_method_spec(spec, method=method, url_template=url,
                                                          content_type=content_type,
                                                          input_trans=input_trans,
                                                          output_trans=output_trans)

    func = mk_request_function(method_spec, function_kind='function')
    openapi_props = glom(spec, f'requestBody.content.{content_type}.schema.properties')
    try:
        _, func_name = path.split('/')  # fragile way of getting the name
    except Exception:
        func_name = 'request_func'

    if 'x-func' in spec:
        original_func = spec['x-func']
        func.__signature__ = signature(original_func)
    else:
        func = add_annots_from_openapi_props(func, openapi_props)
    func.path = path
    func.method = method
    func.content_type = content_type
    func.__name__ = func_name
    func.__qualname__ = func_name
    return func


mk_request_function.from_openapi_spec = mk_request_func_from_openapi_spec

# def mk_request_method(method_spec):
#     """
#     Makes function that will make http requests for you, on your own terms.
#
#     Specify what API you want to talk to, and how you want to talk to it (and it talk back to you), and
#     get a function that does exactly that.
#
#     Essentially, this factory function allows you to take an API specification, specify how you want it to
#     relate to python objects (how to convert input arguments to API elements, and how to convert the response of
#     the request, for instance), and get a method that is ready to be used.
#
#     :param method_spec: Specification of how to convert arguments of the function that is being made to an http request.
#     :return: A function.
#         Note: I say "function", but the function is meant to be a method, so the function has a self as first argument.
#         That argument is ignored.
#
#     """
#     # defaults
#     method_spec = method_spec.copy()
#     method_spec['request_kwargs'] = method_spec.get('request_kwargs', {})
#     method_spec['request_kwargs']['method'] = method_spec['request_kwargs'].get('method', 'GET')
#     arg_order = _ensure_list(method_spec.get('args', []))
#
#     # TODO: inject a signature, and possibly a __doc__ in this function
#     def request_method(self, *args, **kwargs):
#
#         # absorb args in kwargs
#         if len(args) > len(arg_order):
#             raise ValueError(
#                 f"The number ({len(args)}) of unnamed arguments was greater than "
#                 f"the number ({len(arg_order)}) of specified arguments in arg_order")
#
#         kwargs = dict(kwargs, **{argname: argval for argname, argval in zip(arg_order, args)})
#
#         # convert argument types TODO: Not efficient. Might could be revised.
#         for arg_name, converter in method_spec.get('input_trans', {}).items():
#             if arg_name in kwargs:
#                 kwargs[arg_name] = converter(kwargs[arg_name])
#
#         json_data = {}
#         for arg_name in method_spec.get('json_arg_names', []):
#             if arg_name in kwargs:
#                 json_data[arg_name] = kwargs.pop(arg_name)
#
#         # making the request_kwargs ####################################################################################
#         request_kwargs = method_spec['request_kwargs']
#         if 'url_template' in method_spec:
#             request_kwargs['url'] = method_spec['url_template'].format(**kwargs)
#         elif 'url' in method_spec:
#             request_kwargs['url'] = method_spec['url']
#
#         if json_data:
#             request_kwargs['json'] = json_data
#
#         if 'debug' in method_spec:
#             debug = method_spec['debug']
#             if debug == 'print_request_kwargs':
#                 print(request_kwargs)
#             elif debug == 'return_request_kwargs':
#                 return request_kwargs
#
#         r = request(**request_kwargs)
#         if 'output_trans' in method_spec:
#             r = method_spec['output_trans'](r)
#         return r
#
#     if 'wraps' in method_spec:
#         wraps(method_spec['wraps'])(request_method)
#     else:
#         all_args = method_spec.get('args', []) + method_spec.get('json_arg_names', [])
#         if all_args:
#             set_signature_of_func(request_method, ['self'] + all_args)
#
#     return request_method


# def mk_python_binder(method_specs,
#                      method_func_from_method_spec=DFLT_METHOD_FUNC_FROM_METHOD_SPEC,
#                      obj_kwargs=None
#                      ):
#     if obj_kwargs is None:
#         obj_kwargs = {}
#     binder = Py2Req(**obj_kwargs)
#
#     for method_name, method_spec in method_specs.iteritems():
#         if not callable(method_spec):
#             if method_func_from_method_spec is None:
#                 raise ValueError("You need a method_func_from_method_spec")
#             method_spec = method_func_from_method_spec(method_spec)
#         inject_method(binder, method_spec, method_name)
#
#     return binder

# def mk_request_kwargs(base_url, input_trans=None):
#
#     if input_trans is None:
#         input_trans = lambda x: x

# def mk_request_function(base_url, input_trans=None, kwargs_validator=None, output_trans=None):
#     if kwargs_validator is None:
#         kwargs_validator = mk_default_completion_validator()
#
#     def request_func(self, **kwargs):
#         kwargs = input_trans(kwargs)
#         kwargs = kwargs_validator(kwargs)
#         kwargs['url'] = base_url + kwargs['url']  # prepend url with base_url TODO: Consider other name (suff_url?)
#         return request(**kwargs)
#
#     return request_func

# class Py2Request(object):
#     def __init__(self, base_url=DFLT_BASE_URL, kwargs_validator=None):
#         self.base_url = base_url
#         if kwargs_validator is None:
#             kwargs_validator = mk_default_completion_validator()
#         self.kwargs_validator = kwargs_validator
#
#     def request(self, **kwargs):  # TODO: How to get kwargs spec directly from request (using inspect)?
#         kwargs = self.kwargs_validator(kwargs)
#         kwargs['url'] = self.base_url + kwargs['url']  # prepend url with base_url
#         return request(**kwargs)
