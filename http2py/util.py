import json

try:
    import importlib.resources

    _files = importlib.resources.files  # only valid in 3.9+
except AttributeError:
    import importlib_resources  # needs pip install

    _files = importlib_resources.files

files = _files("http2py")


def add_defaults(d, dflts):
    """Adds defaults to every (mapping) value of every item of d"""
    dflt_keys = set(dflts)
    for k, v in d.items():
        d[k].update({dflt_key: dflts[dflt_key] for dflt_key in dflt_keys.difference(v)})
    return d


class ModuleNotFoundErrorNiceMessage:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is ModuleNotFoundError:
            raise ModuleNotFoundError(
                f'''
It seems you don't have requred `{exc_val.name}` package.
Try installing it by running:

    pip install {exc_val.name}

in your terminal.
For more information: https://pypi.org/project/{exc_val.name}
            '''
            )


class I2mintModuleNotFoundErrorNiceMessage:
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is ModuleNotFoundError:
            raise ModuleNotFoundError(
                f'''
It seems you don't have requred `{exc_val.name}` package. Not sure if this is the problem, but you could try:
    git clone https://github.com/i2mint/{exc_val.name}
in a place that your python path (i.e. PYTHONPATH environment variable).  
            '''
            )


def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except (TypeError, OverflowError):
        return False


# -------------------------------------------------------------------------------------
# OpenAPI specs parser
# Note: Perhaps a better way to do this is to use a "parsing" class with cache_property

from typing import Any, Dict, Iterable, Iterator
from functools import cached_property, partial
from dol import KvReader, cached_keys
from dataclasses import dataclass, field

http_methods = {'get', 'post', 'put', 'delete', 'patch', 'options', 'head'}


def get_routes(d: Dict[str, Any], include_methods=tuple(http_methods)) -> Iterable[str]:
    """
    Takes OpenAPI specification dict 'd' and returns the key-paths to all the endpoints.
    """
    if isinstance(include_methods, str):
        include_methods = {include_methods}
    for endpoint in (paths := d.get('paths', {})):
        for method in paths[endpoint]:
            if method in include_methods:
                yield method, endpoint


dflt_type_mapping = tuple(
    {
        "array": list,
        "integer": int,
        "object": dict,
        "string": str,
        "boolean": bool,
        "number": float,
    }.items()
)


@cached_keys
class Routes(KvReader):
    def __init__(self, spec: dict, *, type_mapping: dict = dflt_type_mapping) -> None:
        self.spec = spec
        self._mk_route = partial(Route, spec=spec, type_mapping=type_mapping)
        self._title = spec.get('info', {}).get('title', 'OpenAPI spec')

    @classmethod
    def from_yaml(cls, yaml_str: str):
        import yaml

        return cls(yaml.safe_load(yaml_str))

    @property
    def _paths(self):
        self.spec['paths']

    def __iter__(self):
        return get_routes(self.spec)

    def __getitem__(self, k):
        return self._mk_route(*k)

    def __repr__(self) -> str:
        return f"{type(self).__name__}('{self._title}')"


@dataclass
class Route:
    method: str
    endpoint: str
    spec: dict = field(repr=False)
    # TODO: When moving to 3.9+, make below keyword-only
    type_mapping: dict = field(default=dflt_type_mapping, repr=False)

    def __post_init__(self):
        self.type_mapping = dict(self.type_mapping)

    @cached_property
    def method_data(self):
        method, endpoint = self.method, self.endpoint
        method_data = self.spec.get('paths', {}).get(endpoint, {}).get(method, None)
        if method_data is None:
            raise KeyError(f"Endpoint '{endpoint}' has no method '{method}'")
        return method_data

    @cached_property
    def input_specs(self):
        return {
            'parameters': self.method_data.get('parameters', []),
            'requestBody': self.method_data.get('requestBody', {}),
        }

    @cached_property
    def output_specs(self):
        return self.method_data.get('responses', {})

    @cached_property
    def parameters(self):
        # Start with the parameters defined in the 'parameters' section
        params = self.method_data.get('parameters', [])

        # Check if requestBody is defined and has content with a JSON content type
        request_body = self.method_data.get('requestBody', {})
        content = request_body.get('content', {}).get('application/json', {})

        # If there's a schema, we extract its properties and merge with the parameters
        if 'schema' in content:
            schema_props = content['schema'].get('properties', {})
            for name, details in schema_props.items():
                params.append(
                    {
                        'in': 'body',  # or 'in': 'requestBody', if that makes more sense in your context
                        'name': name,
                        'schema': details,
                    }
                )

        return params
