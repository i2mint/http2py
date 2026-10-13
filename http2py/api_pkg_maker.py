"""Generate an installable python package from an OpenAPI specification.

Given a spec (or the URL of one), :func:`mk_api_pkg` writes a small source
distribution whose functions are bound to the service's routes.

The sdist is built by running ``setup.py sdist`` in a subprocess. This module
used to call ``setuptools.sandbox.run_setup``, which modern setuptools no longer
ships -- so merely *importing* it raised ``ImportError`` and the
``api-pkg-maker`` console script could not start at all (i2mint/http2py#14).
The subprocess is also better behaved: ``sandbox.run_setup`` needed the process
to ``os.chdir`` into the build directory and never came back.

``setuptools`` is still needed to *run* :func:`mk_api_pkg`, but it is
deliberately NOT a declared dependency of http2py: it is needed by this one
function, not by ``import http2py``, and a virtualenv created by ``uv`` does not
ship it. :func:`_check_build_backend` turns its absence into an actionable
message instead of a subprocess exit code.

Nothing taken from the spec is pasted into generated source as code: the spec
is written as a JSON data file the package loads at import, and every route
name must be a plain Python identifier (i2mint/http2py#21). A spec fetched from
a server therefore cannot inject code into the package built from it.
"""

import json
import keyword
import os
import re
import shutil
import subprocess
import sys
import tempfile
import warnings
from collections.abc import Callable
from importlib import import_module
from typing import Optional, Union
from http2py.client import HttpClient
from datetime import datetime, timezone

#: Where built packages are written. ``expanduser`` rather than
#: ``os.environ["HOME"]``: the latter is a module-import-time ``KeyError`` on
#: Windows, which would take the whole package down with it.
OUTPUT_DIR = os.path.join(os.path.expanduser("~"), "http2py", "api_pkgs")

INIT_FILE_TPL = """from .funcs import {funcs}
"""

SPEC_FILENAME = "openapi_spec.json"

# Every name the generated module defines besides the routes starts with "_",
# except ``api``; route names may not start with "_" nor be "api" (_route_names).
FUNCS_FILE_TPL = """import json as _json
from importlib import import_module as _import_module
from pathlib import Path as _Path

from i2 import Sig as _Sig
from http2py.client import HttpClient as _HttpClient


def _import_object(ref):
    module_name, _, name = ref.rpartition(".")
    return getattr(_import_module(module_name), name)


_SPEC = _json.loads(
    (_Path(__file__).parent / {spec_filename!r}).read_text(encoding="utf-8")
)
api = _HttpClient(openapi_spec=_SPEC, binary_loads={binary_loads})


def _apply_sig(meth):
    def wrapper(func):
        sig = _Sig(meth) - 'self'
        return sig(func)
    return wrapper
{funcs}"""

_RESERVED_ROUTE_NAMES = {"api", "funcs"}  # funcs: the module's own name

FUNC_TPL = """

@_apply_sig(api.routes[{func_name!r}])
def {func_name}(*args, **kwargs):
    return api.routes[{func_name!r}](*args, **kwargs)
"""

# The first http2py release with ``HttpClient.routes``, which generated packages call.
MIN_HTTP2PY_VERSION = "0.1.37"

SETUP_PY = """from setuptools import setup

setup()
"""

SETUP_CFG_TPL = """[metadata]
name = {name}
version = {version}
platforms = any
description = {description}
author = {author}
license = {license}

[options]
packages = find:
include_package_data = True
zip_safe = False
install_requires =
    i2
    http2py>={min_http2py}

[options.package_data]
* = {spec_filename}
"""

_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"  # ASCII: Python normalizes other letters
_DOTTED_PATH = re.compile(rf"{_IDENTIFIER}(\.{_IDENTIFIER})+")


def _is_plain_identifier(name: str) -> bool:
    return re.fullmatch(_IDENTIFIER, name) is not None and not keyword.iskeyword(name)


def object_ref(obj: Union[str, Callable]) -> str:
    """The dotted import path (``"module.name"``) a generated package uses to
    import ``obj``: ``obj`` itself when it is a string (checked to name a callable,
    unless its module is not installed here: then a warning), else the path of an
    importable callable, checked to import back to that very object.

    >>> object_ref(bytes)
    'builtins.bytes'
    >>> object_ref("http2py.decorators.unsafe_pickle_loads")
    'http2py.decorators.unsafe_pickle_loads'
    >>> object_ref(lambda b: b)  # doctest: +ELLIPSIS
    Traceback (most recent call last):
      ...
    ValueError: Not an importable module.name path: '...<lambda>'
    """
    if isinstance(obj, str):
        ref = obj
    else:
        ref = f"{getattr(obj, '__module__', '')}.{getattr(obj, '__qualname__', '')}"
    if not _DOTTED_PATH.fullmatch(ref):
        raise ValueError(f"Not an importable module.name path: {ref[:80]!r}")
    module_name, _, name = ref.rpartition(".")
    try:
        imported = getattr(import_module(module_name), name)
    except ModuleNotFoundError as error:
        if isinstance(obj, str):  # may be installed only where the package runs
            warnings.warn(f"{ref!r} cannot be imported here ({error}); kept as given")
            return ref
        raise ValueError(f"{ref!r} does not import: {error}") from None
    except Exception as error:
        raise ValueError(f"{ref!r} does not import: {error!r}") from None
    if not callable(imported):
        raise ValueError(f"{ref!r} is not callable")
    if not isinstance(obj, str) and imported is not obj:
        raise ValueError(f"{ref!r} does not import back to {obj!r}")
    return ref


def _route_names(api: HttpClient) -> list:
    """The method names ``api`` registered, each a plain identifier, since each is
    written into generated source."""
    names = list(api.routes)
    for name in names:
        if not _is_plain_identifier(name):
            raise ValueError(
                f"Route name {name[:60]!r} is not an ASCII Python identifier: cannot "
                "generate a function for it."
            )
        if name.startswith("_") or name in _RESERVED_ROUTE_NAMES:
            raise ValueError(
                f"Route name {name!r} is reserved (it starts with '_' or is 'api')."
            )
    if not names:
        raise RuntimeError("The API is empty")
    return names


def _cfg_value(text: str) -> str:
    """``text`` as a setup.cfg value: one line, ``%`` escaped from interpolation."""
    return " ".join(str(text).split()).replace("%", "%%")


def api_pkg_files(
    openapi_spec: dict = None,
    openapi_url: str = None,
    pkg_name: str = None,
    pkg_version: str = None,
    pkg_description: str = None,
    pkg_author: str = None,
    pkg_license: str = None,
    *,
    binary_loads: Optional[Union[str, Callable]] = None,
) -> dict:
    """The source files of the package :func:`mk_api_pkg` builds, as
    ``{relative path: text}`` (see :func:`mk_api_pkg` for the arguments)."""
    if isinstance(openapi_spec, str):  # e.g. given as JSON text on the command line
        openapi_spec = json.loads(openapi_spec)
    api = HttpClient(openapi_spec=openapi_spec, url=openapi_url)
    func_names = _route_names(api)
    loads_code = (
        "None"
        if binary_loads is None
        else (f"_import_object({object_ref(binary_loads)!r})")
    )
    pkg_name = pkg_name or _mk_pkg_name()
    if not _is_plain_identifier(pkg_name):
        raise ValueError(f"pkg_name must be an ASCII Python identifier: {pkg_name!r}")
    server_url = api.openapi_spec["servers"][0]["url"]
    setup_cfg = SETUP_CFG_TPL.format(
        name=pkg_name,
        version=_cfg_value(pkg_version or "1.0.0"),
        description=_cfg_value(
            pkg_description
            or f"A client API to consume the webservices exposed at {server_url}"
        ),
        author=_cfg_value(pkg_author or "API Package Maker"),
        license=_cfg_value(pkg_license or "Apache"),
        spec_filename=SPEC_FILENAME,
        min_http2py=MIN_HTTP2PY_VERSION,
    )
    funcs_code = FUNCS_FILE_TPL.format(
        spec_filename=SPEC_FILENAME,
        binary_loads=loads_code,
        funcs="".join(FUNC_TPL.format(func_name=name) for name in func_names),
    )
    return {
        "setup.py": SETUP_PY,
        "setup.cfg": setup_cfg,
        f"{pkg_name}/__init__.py": INIT_FILE_TPL.format(funcs=", ".join(func_names)),
        f"{pkg_name}/funcs.py": funcs_code,
        f"{pkg_name}/{SPEC_FILENAME}": json.dumps(api.openapi_spec, indent=1),
    }


def _mk_pkg_name():
    return f"apipkg{int(datetime.now(timezone.utc).timestamp())}"


def mk_api_pkg(
    openapi_spec: dict = None,
    openapi_url: str = None,
    pkg_name: str = None,
    pkg_version: str = None,
    pkg_description: str = None,
    pkg_author: str = None,
    pkg_license: str = None,
    *,
    binary_loads: Optional[Union[str, Callable]] = None,
    output_dir: str = None,
):
    """
    Build a pip installable package containing the functions to consume a running
    webservice application executed with py2http.

    The package holds the spec as it was when built (fetched from ``openapi_url``
    if no ``openapi_spec`` is given), as a JSON file it loads at import.

    :param openapi_spec: The openapi specification for the webservice.
    :type openapi_spec: dict, optional
    :param openapi_url: The url to fetch the openapi specification for the webservice.
    :type openapi_url: str, optional
    :param pkg_name: The name of the package. If no name is provided, default to
    'apipkg{timestamp}'
    :type pkg_name: str, optional
    :param pkg_version: The version number of the package. If no version is provided,
    default to 1.0.0
    :type pkg_version: str, optional
    :param pkg_description: The description of the package.
    :type pkg_description: str, optional
    :param pkg_author: The author of the package. If no author provided, default to
    'API Package Maker'
    :type pkg_author: str, optional
    :param pkg_license: The license for the package. If no license provided, default
    to 'Apache'
    :type pkg_license: str, optional
    :param binary_loads: How the package decodes binary (octet-stream) responses:
        an importable callable or its dotted path (``"builtins.bytes"`` for the raw
        content, ``"http2py.decorators.unsafe_pickle_loads"`` for a fully trusted
        server). By default they raise ``BinaryResponseNotDecoded``.
    :param output_dir: Where the built ``.tar.gz`` is written (default ``OUTPUT_DIR``).
    """
    _check_build_backend()
    output_dir = OUTPUT_DIR if output_dir is None else output_dir
    files = api_pkg_files(
        openapi_spec,
        openapi_url,
        pkg_name,
        pkg_version,
        pkg_description,
        pkg_author,
        pkg_license,
        binary_loads=binary_loads,
    )
    pkg_name = next(path.split("/")[0] for path in files if "/" in path)

    tempdir = tempfile.mkdtemp()
    try:
        for relpath, content in files.items():
            filepath = os.path.join(tempdir, *relpath.split("/"))
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as file:
                file.write(content)
        build = subprocess.run(
            [sys.executable, "setup.py", "sdist"],
            cwd=tempdir,
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            # check=True would raise a CalledProcessError carrying only the exit
            # status, discarding the captured output that says what went wrong.
            raise RuntimeError(
                f"`setup.py sdist` failed (exit {build.returncode}) while building "
                f"{pkg_name!r}.\n--- stdout ---\n{build.stdout}"
                f"\n--- stderr ---\n{build.stderr}"
            )
        # setuptools normalizes the name and version in the file name it writes
        (pkg_filename,) = os.listdir(os.path.join(tempdir, "dist"))
        os.makedirs(output_dir, exist_ok=True)
        shutil.copy(src=os.path.join(tempdir, "dist", pkg_filename), dst=output_dir)

        return os.path.join(output_dir, pkg_filename)

    finally:
        shutil.rmtree(tempdir)


def _check_build_backend():
    """Fail early and legibly when the interpreter cannot build an sdist.

    ``setup.py sdist`` needs setuptools in the *subprocess's* interpreter, which
    is this one. Environments created by ``uv`` (and ``python -m venv
    --without-pip``) do not have it. Without this check the user sees a bare
    ``CalledProcessError`` with an exit status and no cause.
    """
    import importlib.util

    if importlib.util.find_spec("setuptools") is None:
        raise RuntimeError(
            "mk_api_pkg builds a source distribution with `setup.py sdist`, "
            f"which needs setuptools in {sys.executable}. Install it with: "
            f"{sys.executable} -m pip install setuptools"
        )


def main():
    """Entry point for the ``api-pkg-maker`` console script; returns the exit code.

    ``cw.dispatch`` returns the code rather than exiting, and
    ``[project.scripts]`` wraps this in ``sys.exit(main())``.
    """
    import cw

    return cw.dispatch(mk_api_pkg)


if __name__ == "__main__":
    raise SystemExit(main())
