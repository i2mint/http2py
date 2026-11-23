# http2py.cli_maker

Turn an http-bound python object into a command line interface.

Signatures are first made argparse-friendly ([`mk_argparse_friendly()`](#http2py.cli_maker.mk_argparse_friendly)),
then turned into a parser by [`mk_cli()`](#http2py.cli_maker.mk_cli) and run by [`dispatch_cli()`](#http2py.cli_maker.dispatch_cli).

The parser is built by `cw`. Its `BY_NAME_IF_KWONLY` naming is what
reproduces the grammar this module has always produced – see
[`CLI_CONVENTION`](#http2py.cli_maker.CLI_CONVENTION).

### Module Attributes

| [`CLI_CONVENTION`](#http2py.cli_maker.CLI_CONVENTION)   | How the command line is derived from a signature.   |
|-------------------------------------------------------------------|-----------------------------------------------------|

### Functions

| [`dispatch_cli`](#http2py.cli_maker.dispatch_cli)([openapi_spec, url, filename, ...])   | Makes a CLI parser with mk_cli and then runs it (see documentation of mk_cli)                                                                                                                   |
|-----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`mk_argparse_friendly`](#http2py.cli_maker.mk_argparse_friendly)(func)                         | Wraps a function to expose a signature that is compatible with argparse by stripping leading underscores from all keyword arguments, but does not mutate the signature of the original function |
| [`mk_cli`](#http2py.cli_maker.mk_cli)([openapi_spec, url, filename, ...])         | Creates a CLI parser that exposes all of the methods of an HTTP client defined by an OpenAPI spec.                                                                                              |
| [`mk_sig_argparse_friendly`](#http2py.cli_maker.mk_sig_argparse_friendly)(sig)                      | Modifies a signature to change all leading underscores in param names to trailing underscores, to ensure compatibility with argparse                                                            |
| [`register_cli_method`](#http2py.cli_maker.register_cli_method)(openapi_spec, client_method)   | Creates a CLI-friendly function to instantiate an HttpClient with appropriate authentication arguments and call a particular method of the client instance                                      |

### http2py.cli_maker.CLI_CONVENTION *= Convention(naming='by_name_if_kwonly', short_flags=True, hyphenate_commands=True, hyphenate_groups=False, default_in_help=True, hints_when_declared=False, resolve_hints=False, decode=<function argh_decode>, egress=<function argh_egress>)*

How the command line is derived from a signature.

Every function [`register_cli_method()`](#http2py.cli_maker.register_cli_method) builds has KEYWORD-ONLY parameters
only (plus `*args`/`**kwargs` on a no-argument route), because
`Sig.merge_with_sig()` is called with `kind=KO`. For that shape,
`BY_NAME_IF_KWONLY` is what reproduces the grammar this module produced
under argh: every parameter is an option, required exactly when it has no
default – `get-thing -u UID -p PID [-l LIMIT]`.

cw’s `ARGH` default (`BY_NAME_IF_HAS_DEFAULT`) would NOT: it turns a
keyword-only parameter with no default into a *positional*, so every required
API argument would silently change spelling. That is not a cw bug – it
faithfully reproduces argh’s *explicit* `BY_NAME_IF_HAS_DEFAULT` policy.
This module never selected a policy, and argh’s no-policy legacy mode is the
one that matches `BY_NAME_IF_KWONLY` here.

### http2py.cli_maker.dispatch_cli(openapi_spec='', url='', filename='', parse_yaml=False, config_filename='/home/runner/.http2py/credentials.json', , binary_loads=None)

Makes a CLI parser with mk_cli and then runs it (see documentation of mk_cli)

Returns `None` when the command ran, and raises `SystemExit(2)` on a
command-line error – the same two outcomes the previous argh-based
implementation produced. `cw.run` *returns* the exit code rather than
exiting, so the non-zero case is re-raised here.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### http2py.cli_maker.mk_argparse_friendly(func)

Wraps a function to expose a signature that is compatible with argparse by stripping leading
underscores from all keyword arguments, but does not mutate the signature of the original function

### http2py.cli_maker.mk_cli(openapi_spec='', url='', filename='', parse_yaml=False, config_filename='/home/runner/.http2py/credentials.json', , binary_loads=None)

Creates a CLI parser that exposes all of the methods of an HTTP client defined by an OpenAPI spec.
Accepts either an OpenAPI spec dict, a url, or path to a local file.

* **Parameters:**
  * **openapi_spec** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – An OpenAPI service specification
  * **url** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – A URL for an OpenAPI spec that can be accessed with an HTTP GET request
  * **filename** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The path to a local file that contains an OpenAPI spec
  * **parse_yaml** ([`bool`](https://docs.python.org/3/builtins/functions.html#bool)) – A flag to indicate that the provided OpenAPI spec is in YAML format rather than JSON (default: False)
  * **config_filename** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The path to a local config file that contains authentication details for the HTTP service
    in JSON format (default: ~/.http2cli/credentials.json
  * **binary_loads** ([`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)) – How commands decode binary (octet-stream) responses, passed to
    `HttpClient`: `bytes` for the raw content, a decoder of your own, or
    `http2py.decorators.unsafe_pickle_loads` for a fully trusted server. By
    default such a response raises `BinaryResponseNotDecoded`.

### http2py.cli_maker.mk_sig_argparse_friendly(sig)

Modifies a signature to change all leading underscores in param names
to trailing underscores, to ensure compatibility with argparse

### http2py.cli_maker.register_cli_method(openapi_spec, client_method, expected_auth_kwargs=None, config_filename='/home/runner/.http2py/credentials.json', profile='', , binary_loads=None)

Creates a CLI-friendly function to instantiate an HttpClient with appropriate authentication
arguments and call a particular method of the client instance

* **Parameters:**
  * **openapi_spec** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – The OpenAPI spec used to make the client
  * **client_method** ([`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)) – The instance method to wrap
  * **expected_auth_kwargs** ([`Iterable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Iterable)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str)]) – A list of authentication kwargs that the CLI should ask for
    (defaults to empty list)
  * **config_filename** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The path to a JSON file to read for authentication kwargs
    (defaults to ~/.http2py/credentials.json)
  * **profile** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The named profile to find in the config file
  * **binary_loads** ([`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable)) – How binary (octet-stream) responses are decoded (see
    [`mk_cli()`](#http2py.cli_maker.mk_cli))
