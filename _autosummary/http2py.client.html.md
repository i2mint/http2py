# http2py.client

The main entry point: a python object facading an http service.

[`HttpClient`](#http2py.client.HttpClient) takes an OpenAPI specification (a dict, or the URL of one)
and exposes each declared route as a normal python method.

### Classes

| [`HttpClient`](#http2py.client.HttpClient)([openapi_spec, url, ...])   | A client class meant as an interface to an HTTP service with one or more routes defined with an OpenAPI spec.   |
|-----------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------|

### *class* http2py.client.HttpClient(openapi_spec=None, url=None, session_state=None, base_url=None, verify_cert=True, \*, binary_loads=None, binary_dumps=<built-in function dumps>, \*\*auth_kwargs)

Bases: [`object`](https://docs.python.org/3/builtins/functions.html#object)

A client class meant as an interface to an HTTP service with one or more routes
defined with an OpenAPI spec.

Every route is in `client.routes` (a `{name: method}` dict), and is also an
attribute of the client (`client.<name>`) as long as its name neither starts
with `_` nor is already an attribute the client works with: a spec, possibly
served by a remote, must not be able to replace the client’s own attributes (such
as `session` or `handle_request`). A route that cannot be an attribute is
still reachable as `client.routes[name]`, and a warning says so. The purely
informational attributes (`title`, `version`, `base_url`), which the client
never reads after `__init__`, can be taken by a route.
