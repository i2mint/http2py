# http2py.py2request

Won’t show the details here, but if you are used to it’s not that hard,
you just need to find the definition of the API, read it, figure out what part
of the request you need in the URL and what you need to put in the “payload”,
figure out how those \_inputs_ of the request need to be formated,
construct the URL and the payload according to your newly acquired knowledge of this specific API,
make a web request (say with `urllib.request` or `requests`),
extract the information you need from the response object (often in `.contents` or `.json()`),
and often process the data further to get it in the format you can use it directly
(say a list, a dict, a dataframe, a numpy array, etc.).

And if you’re experienced, and have felt the pain of needing to reuse or adapt your code,
you’ll clean things up as soon as you figure this puzzle out.
You’ll divide your code into separate concerns, encapsulate these concerns in functions and classes,
and offer a simple, intuitive, python-like interface that reflects the simplicity
of what you’re actually doing: Just getting some data. Something like:

```text
nice_python_obj_I_can_use_directly = get_that_darn_data(query, using, my, words, values, and, defaults='here')
```

The details being hidden away, as they should.

And that’s fine. You’ve done well. Congratulate yourself, you deserve it.

Now do that again and again and again, and sometimes under the pressure of a deadline that depends on this data being acquired.

Are you enjoying yourself?

There must be a better way…

### Functions

| [`DFLT_METHOD_FUNC_FROM_METHOD_SPEC`](#http2py.py2request.DFLT_METHOD_FUNC_FROM_METHOD_SPEC)(method_spec, \*)   | Makes function that will make http requests for you, on your own terms.                                                                            |
|-------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------|
| `add_annots_from_openapi_props`(func, ...)                                                            |                                                                                                                                                    |
| `all_necessary_fields_validator`(kwargs)                                                              |                                                                                                                                                    |
| [`check_url_template`](#http2py.py2request.check_url_template)(url_template, \*[, ...])          | Return `url_template` if no placeholder in it, nor any of the `query_arg_names` (appended as `?name={name}` when calling), reads into an argument. |
| `default_path_to_func_name`(method, uri)                                                              |                                                                                                                                                    |
| [`extract_format_names`](#http2py.py2request.extract_format_names)(string_template)                | Extracts the names of the fields in a string template, returning a list of strings.                                                                |
| `identity_func`(x)                                                                                    |                                                                                                                                                    |
| `mk_default_completion_validator`([dflt_kwargs])                                                      |                                                                                                                                                    |
| `mk_method_spec_from_openapi_method_spec`(...)                                                        |                                                                                                                                                    |
| `mk_param_spec_from_arg_schema`(arg[, required])                                                      |                                                                                                                                                    |
| `mk_request_func_from_openapi_spec`(path, ...)                                                        |                                                                                                                                                    |
| [`mk_request_function`](#http2py.py2request.mk_request_function)(method_spec, \*[, ...])          | Makes function that will make http requests for you, on your own terms.                                                                            |
| [`openapi_to_py`](#http2py.py2request.openapi_to_py)(openapi_spec[, paths, ...])            | Given an OpenAPI spec dict, returns a dict mapping function names to request functions.                                                            |
| [`raw_response_on_error`](#http2py.py2request.raw_response_on_error)(func)                          | A useful output trans decorator that will return the raw response if the output_trans raises an error.                                             |

### Classes

| `DebugOptions`()                                                                      |                                                                                                  |
|---------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| [`Py2Request`](#http2py.py2request.Py2Request)([method_specs, ...])      | Make a class that has methods that offer a python interface to web requests                      |
| [`UrlMethodSpecsMaker`](#http2py.py2request.UrlMethodSpecsMaker)(url_root[, ...]) | Utility to help in making templated method_specs dicts to be used to define a Py2Request object. |

### http2py.py2request.DFLT_METHOD_FUNC_FROM_METHOD_SPEC(method_spec, \*, function_kind='method', dispatch=<function request>, verify_cert=True, binary_loads=None, binary_dumps=<built-in function dumps>)

Makes function that will make http requests for you, on your own terms.

Specify what API you want to talk to, and how you want to talk to it (and it talk back to you), and
get a function that does exactly that.

Essentially, this factory function allows you to take an API specification, specify how you want it to
relate to python objects (how to convert input arguments to API elements, and how to convert the response of
the request, for instance), and get a method that is ready to be used.

What does a method_spec contain?
Well… consider first this. The core of this code is this:

```text
request_kwargs = dict(**method_spec['request_kwargs'])  # to make a copy
...  # a bunch more code that updates request_kwargs according to other keys of method_spec
...  # ... and some other debugging hooks
r = request(**request_kwargs)  # call the request
if 'output_trans' in method_spec:  # see if there's an output_trans function
    r = method_spec['output_trans'](r)  # ... if so, use it to extract what you want from the response
return r
```

So you can do almost everything you need with one single key: `'request_kwargs'` and `'output_trans'` alone.
But there wouldn’t be as much advantage over just calling requests if that’s all there was to it,
so we offer some other special keys to cover some of the common patterns.

> - ‘method’:
> - ‘url_template’: Specify the url, but with named placeholders: Example `'http://base.com/{user}/{action}'`.
> - ‘json_arg_names’: Specify the names of arguments of the function that should be put in the json load
> - ‘debug’: ‘print_request_kwargs’ or ‘return_request_kwargs’
> - ‘input_trans’: Function applied to
> - ‘output_trans’: A function applied to response object to extract what we want to return.
> - ‘wraps’: A function whose signature we should use as the output’s function’s signature
* **Parameters:**
  * **method_spec** – Specification of how to convert arguments of the function that is being made to an http request.
  * **binary_loads** – How to decode a binary (octet-stream) response, when
    `method_spec` has no `output_trans`. `None` (the default) raises
    `BinaryResponseNotDecoded` on such a response rather than unpickling
    it; pass `bytes` for the raw content, a decoder of your own, or
    `http2py.decorators.unsafe_pickle_loads` if the server is fully trusted.
  * **binary_dumps** – How to encode the arguments of a binary request body
    (default `pickle.dumps`; see `DFLT_BINARY_DUMPS`).
* **Returns:**
  A function.

  Note:
  : I say “function”, but the function is meant to be a method, so the function has a self as first argument.
    That argument is ignored.

### *class* http2py.py2request.Py2Request(method_specs=None, method_func_from_method_spec=<function mk_request_function>, \*\*kwargs)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Make a class that has methods that offer a python interface to web requests

### *class* http2py.py2request.UrlMethodSpecsMaker(url_root, constant_url_query=None, \*\*constant_items)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

Utility to help in making templated method_specs dicts to be used to define a Py2Request object.

### http2py.py2request.check_url_template(url_template, , query_arg_names=())

Return `url_template` if no placeholder in it, nor any of the
`query_arg_names` (appended as `?name={name}` when calling), reads into an
argument.

A template is filled with `str.format(**arguments)`, and it may come from a spec
fetched from a server. `{a.__class__}` or `{a[0]}` would read attributes or
items of the caller’s arguments into the URL, so they are refused. Other names,
such as OpenAPI’s hyphenated `{user-id}`, are fine.

```pycon
>>> check_url_template('http://h/u/{user-id}?q={q}')
'http://h/u/{user-id}?q={q}'
>>> check_url_template('http://h/{a.__init__.__globals__}')
Traceback (most recent call last):
  ...
ValueError: URL template placeholder '{a.__init__.__globals__}' reads into an argument
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)

### http2py.py2request.extract_format_names(string_template)

Extracts the names of the fields in a string template, returning a list of
strings.

```pycon
>>> string_template = "Hello, {name}! You are {age} years old."
>>> extract_format_names(string_template)
('name', 'age')
```

### http2py.py2request.mk_request_function(method_spec, \*, function_kind='method', dispatch=<function request>, verify_cert=True, binary_loads=None, binary_dumps=<built-in function dumps>)

Makes function that will make http requests for you, on your own terms.

Specify what API you want to talk to, and how you want to talk to it (and it talk back to you), and
get a function that does exactly that.

Essentially, this factory function allows you to take an API specification, specify how you want it to
relate to python objects (how to convert input arguments to API elements, and how to convert the response of
the request, for instance), and get a method that is ready to be used.

What does a method_spec contain?
Well… consider first this. The core of this code is this:

```text
request_kwargs = dict(**method_spec['request_kwargs'])  # to make a copy
...  # a bunch more code that updates request_kwargs according to other keys of method_spec
...  # ... and some other debugging hooks
r = request(**request_kwargs)  # call the request
if 'output_trans' in method_spec:  # see if there's an output_trans function
    r = method_spec['output_trans'](r)  # ... if so, use it to extract what you want from the response
return r
```

So you can do almost everything you need with one single key: `'request_kwargs'` and `'output_trans'` alone.
But there wouldn’t be as much advantage over just calling requests if that’s all there was to it,
so we offer some other special keys to cover some of the common patterns.

> - ‘method’:
> - ‘url_template’: Specify the url, but with named placeholders: Example `'http://base.com/{user}/{action}'`.
> - ‘json_arg_names’: Specify the names of arguments of the function that should be put in the json load
> - ‘debug’: ‘print_request_kwargs’ or ‘return_request_kwargs’
> - ‘input_trans’: Function applied to
> - ‘output_trans’: A function applied to response object to extract what we want to return.
> - ‘wraps’: A function whose signature we should use as the output’s function’s signature
* **Parameters:**
  * **method_spec** – Specification of how to convert arguments of the function that is being made to an http request.
  * **binary_loads** – How to decode a binary (octet-stream) response, when
    `method_spec` has no `output_trans`. `None` (the default) raises
    `BinaryResponseNotDecoded` on such a response rather than unpickling
    it; pass `bytes` for the raw content, a decoder of your own, or
    `http2py.decorators.unsafe_pickle_loads` if the server is fully trusted.
  * **binary_dumps** – How to encode the arguments of a binary request body
    (default `pickle.dumps`; see `DFLT_BINARY_DUMPS`).
* **Returns:**
  A function.

  Note:
  : I say “function”, but the function is meant to be a method, so the function has a self as first argument.
    That argument is ignored.

### http2py.py2request.openapi_to_py(openapi_spec, paths=None, \*, path_to_func_name=<function default_path_to_func_name>, servers=None, default_server_url='http://localhost:8000', binary_loads=None, binary_dumps=<built-in function dumps>)

Given an OpenAPI spec dict, returns a dict mapping function names to request functions.
The `servers` argument overrides or provides a default for the OpenAPI servers field.
`binary_loads` / `binary_dumps` are passed to `mk_request_function`.

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)]

### http2py.py2request.raw_response_on_error(func)

A useful output trans decorator that will return the raw response if the output_trans raises
an error.
The response object will also contain the error that was raised,
in the response.output_trans_error attribute.
