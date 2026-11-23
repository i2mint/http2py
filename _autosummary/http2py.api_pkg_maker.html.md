# http2py.api_pkg_maker

Generate an installable python package from an OpenAPI specification.

Given a spec (or the URL of one), [`mk_api_pkg()`](#http2py.api_pkg_maker.mk_api_pkg) writes a small source
distribution whose functions are bound to the service’s routes.

The sdist is built by running `setup.py sdist` in a subprocess. This module
used to call `setuptools.sandbox.run_setup`, which modern setuptools no longer
ships – so merely *importing* it raised `ImportError` and the
`api-pkg-maker` console script could not start at all (i2mint/http2py#14).
The subprocess is also better behaved: `sandbox.run_setup` needed the process
to `os.chdir` into the build directory and never came back.

`setuptools` is still needed to *run* [`mk_api_pkg()`](#http2py.api_pkg_maker.mk_api_pkg), but it is
deliberately NOT a declared dependency of http2py: it is needed by this one
function, not by `import http2py`, and a virtualenv created by `uv` does not
ship it. `_check_build_backend()` turns its absence into an actionable
message instead of a subprocess exit code.

Nothing taken from the spec is pasted into generated source as code: the spec
is written as a JSON data file the package loads at import, and every route
name must be a plain Python identifier (i2mint/http2py#21). A spec fetched from
a server therefore cannot inject code into the package built from it.

### Module Attributes

| [`OUTPUT_DIR`](#http2py.api_pkg_maker.OUTPUT_DIR)   | Where built packages are written.   |
|---------------------------------------------------------------|-------------------------------------|

### Functions

| [`api_pkg_files`](#http2py.api_pkg_maker.api_pkg_files)([openapi_spec, openapi_url, ...])   | The source files of the package [`mk_api_pkg()`](#http2py.api_pkg_maker.mk_api_pkg) builds, as `{relative path: text}` (see [`mk_api_pkg()`](#http2py.api_pkg_maker.mk_api_pkg) for the arguments).                                                                         |
|----------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| [`main`](#http2py.api_pkg_maker.main)()                                            | Entry point for the `api-pkg-maker` console script; returns the exit code.                                                                                                                                                                                                                      |
| [`mk_api_pkg`](#http2py.api_pkg_maker.mk_api_pkg)([openapi_spec, openapi_url, ...])      | Build a pip installable package containing the functions to consume a running webservice application executed with py2http.                                                                                                                                                                     |
| [`object_ref`](#http2py.api_pkg_maker.object_ref)(obj)                                   | The dotted import path (`"module.name"`) a generated package uses to import `obj`: `obj` itself when it is a string (checked to name a callable, unless its module is not installed here: then a warning), else the path of an importable callable, checked to import back to that very object. |

### http2py.api_pkg_maker.OUTPUT_DIR *= '/home/runner/http2py/api_pkgs'*

Where built packages are written. `expanduser` rather than
`os.environ["HOME"]`: the latter is a module-import-time `KeyError` on
Windows, which would take the whole package down with it.

### http2py.api_pkg_maker.api_pkg_files(openapi_spec=None, openapi_url=None, pkg_name=None, pkg_version=None, pkg_description=None, pkg_author=None, pkg_license=None, , binary_loads=None)

The source files of the package [`mk_api_pkg()`](#http2py.api_pkg_maker.mk_api_pkg) builds, as
`{relative path: text}` (see [`mk_api_pkg()`](#http2py.api_pkg_maker.mk_api_pkg) for the arguments).

* **Return type:**
  [`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)

### http2py.api_pkg_maker.main()

Entry point for the `api-pkg-maker` console script; returns the exit code.

`cw.dispatch` returns the code rather than exiting, and
`[project.scripts]` wraps this in `sys.exit(main())`.

### http2py.api_pkg_maker.mk_api_pkg(openapi_spec=None, openapi_url=None, pkg_name=None, pkg_version=None, pkg_description=None, pkg_author=None, pkg_license=None, , binary_loads=None, output_dir=None)

Build a pip installable package containing the functions to consume a running
webservice application executed with py2http.

The package holds the spec as it was when built (fetched from `openapi_url`
if no `openapi_spec` is given), as a JSON file it loads at import.

* **Parameters:**
  * **openapi_spec** ([`dict`](https://docs.python.org/3/builtins/stdtypes.html#dict)) – The openapi specification for the webservice.
  * **openapi_url** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The url to fetch the openapi specification for the webservice.
  * **pkg_name** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The name of the package. If no name is provided, default to
    ‘apipkg{timestamp}’
  * **pkg_version** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The version number of the package. If no version is provided,
    default to 1.0.0
  * **pkg_description** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The description of the package.
  * **pkg_author** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The author of the package. If no author provided, default to
    ‘API Package Maker’
  * **pkg_license** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – The license for the package. If no license provided, default
    to ‘Apache’
  * **binary_loads** ([`Union`](https://docs.python.org/3/library/typing.html#typing.Union)[[`str`](https://docs.python.org/3/builtins/stdtypes.html#str), [`Callable`](https://docs.python.org/3/library/collections.abc.html#collections.abc.Callable), [`None`](https://docs.python.org/3/builtins/constants.html#None)]) – How the package decodes binary (octet-stream) responses:
    an importable callable or its dotted path (`"builtins.bytes"` for the raw
    content, `"http2py.decorators.unsafe_pickle_loads"` for a fully trusted
    server). By default they raise `BinaryResponseNotDecoded`.
  * **output_dir** ([`str`](https://docs.python.org/3/builtins/stdtypes.html#str)) – Where the built `.tar.gz` is written (default `OUTPUT_DIR`).

### http2py.api_pkg_maker.object_ref(obj)

The dotted import path (`"module.name"`) a generated package uses to
import `obj`: `obj` itself when it is a string (checked to name a callable,
unless its module is not installed here: then a warning), else the path of an
importable callable, checked to import back to that very object.

```pycon
>>> object_ref(bytes)
'builtins.bytes'
>>> object_ref("http2py.decorators.unsafe_pickle_loads")
'http2py.decorators.unsafe_pickle_loads'
>>> object_ref(lambda b: b)
Traceback (most recent call last):
  ...
ValueError: Not an importable module.name path: '...<lambda>'
```

* **Return type:**
  [`str`](https://docs.python.org/3/builtins/stdtypes.html#str)
