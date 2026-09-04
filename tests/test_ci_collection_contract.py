"""Guards on what CI is allowed to collect -- the thing that was actually broken.

Under ``pytest --doctest-modules`` (what the CI test action runs) an unimportable
module is not one red test, it is a collection abort that takes the whole session
down.

``http2py/api_pkg_maker.py`` used to be in that state -- it imported
``setuptools.sandbox``, removed from modern setuptools. It now builds the sdist
in a subprocess instead, imports cleanly, and is collected again. What remains
excluded is ``http2py/tests``, whose fixtures stand up a real ``py2http`` web
service: ``py2http`` is a test-only requirement that CI does not install.

The exclusion lives in two places that must agree:
``[tool.wads.ci.testing].exclude_paths`` in pyproject.toml, and
``collect_ignore`` in the repo-root conftest.py.

There is a third, subtler trap that these tests pin down: pytest eagerly imports
``conftest.py`` from any ``test*`` sub-directory of a collection root *before*
``--ignore`` is consulted. ``http2py/tests/conftest.py`` therefore gets imported
even though the directory is excluded -- so it must not need anything outside
this package's declared dependencies at import time.
"""

import importlib
import importlib.util
import pkgutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# Modules that are known-unimportable and therefore excluded from collection.
# Empty, and it should stay that way: an unimportable module aborts the whole
# CI session rather than failing one test.
KNOWN_UNIMPORTABLE: set = set()

EXPECTED_EXCLUDED_PATHS = {"http2py/tests"}


def _package_modules():
    """Dotted names of every module under the http2py package."""
    import http2py

    return sorted(
        name
        for _, name, _ in pkgutil.walk_packages(
            http2py.__path__, prefix="http2py."
        )
    )


def test_every_package_module_imports_except_the_known_broken_one():
    """A new unimportable module would abort CI collection -- fail here instead."""
    failures = {}
    for name in _package_modules():
        if name in KNOWN_UNIMPORTABLE or name.startswith("http2py.tests"):
            continue
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 -- reporting, not handling
            failures[name] = f"{type(exc).__name__}: {exc}"
    assert not failures, f"modules that would abort collection: {failures}"


def test_api_pkg_maker_imports_and_the_console_script_can_start():
    """The former tripwire for issue #14, inverted now that the module is fixed.

    ``api-pkg-maker`` is this package's only console script, and it could not
    start at all: ``from setuptools import sandbox`` raised ``ImportError`` at
    import time, before ``main()`` was ever entered. Both halves are asserted --
    the module imports, and the entry point the console script calls is there.
    """
    module = importlib.import_module("http2py.api_pkg_maker")
    assert callable(module.main)
    assert callable(module.mk_api_pkg)


def test_no_module_is_excluded_for_being_unimportable():
    """Guard the invariant, not the past exception.

    ``KNOWN_UNIMPORTABLE`` is empty. If a future change adds a module that
    cannot be imported, the honest fix is to fix the module -- not to grow this
    set -- because an unimportable module aborts collection for everything.
    """
    assert KNOWN_UNIMPORTABLE == set()


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib needs Python 3.11+")
def test_pyproject_and_conftest_exclusions_agree():
    """The two exclusion lists are separate mechanisms; they must not drift."""
    import tomllib

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    ci_excluded = set(pyproject["tool"]["wads"]["ci"]["testing"]["exclude_paths"])

    spec = importlib.util.spec_from_file_location(
        "_http2py_root_conftest", REPO_ROOT / "conftest.py"
    )
    root_conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_conftest)
    conftest_excluded = set(root_conftest.collect_ignore)

    assert ci_excluded == EXPECTED_EXCLUDED_PATHS
    assert conftest_excluded == EXPECTED_EXCLUDED_PATHS


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib needs Python 3.11+")
def test_docs_builder_is_disabled():
    """docs/ and docsrc/ are gone from this repo; re-enabling docs would re-break
    the Publish job the same way the legacy `epythet make . github` call did."""
    import tomllib

    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())
    assert pyproject["tool"]["wads"]["ci"]["docs"]["enabled"] is False


def test_excluded_test_dir_conftest_imports_without_undeclared_deps():
    """``http2py/tests/conftest.py`` is imported by pytest before --ignore applies.

    It must therefore not import anything outside http2py's declared
    dependencies at module level. ``py2http`` is a test-only dependency that CI
    does not install, so importing it eagerly aborted the session with
    "ImportError while loading conftest" before any test ran.
    """
    conftest_path = REPO_ROOT / "http2py" / "tests" / "conftest.py"

    class _BlockPy2http:
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "py2http" or fullname.startswith("py2http."):
                raise ImportError(f"{fullname} is blocked for this test")
            return None

    blocker = _BlockPy2http()
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] == "py2http"}
    for key in saved:
        del sys.modules[key]
    sys.meta_path.insert(0, blocker)
    try:
        spec = importlib.util.spec_from_file_location(
            "_http2py_tests_conftest", conftest_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.update(saved)
        sys.modules.pop("_http2py_tests_conftest", None)

    assert hasattr(module, "ws_app")


def test_mk_api_pkg_builds_a_source_distribution(tmp_path, monkeypatch):
    """End-to-end proof that the ``setuptools.sandbox`` fix actually works.

    Builds a real sdist from a spec dict -- no network, no live service -- and
    checks the archive is where ``mk_api_pkg`` says it is. Also asserts the
    working directory survives: the old implementation did a bare
    ``os.chdir(tempdir)`` and never came back, which quietly broke any caller
    that used relative paths afterwards.
    """
    import tarfile

    from http2py import api_pkg_maker

    monkeypatch.setattr(api_pkg_maker, "OUTPUT_DIR", str(tmp_path))
    cwd_before = Path.cwd()

    spec = {
        "openapi": "3.0.2",
        "info": {"title": "d", "version": "0.1"},
        "servers": [{"url": "http://localhost:3030"}],
        "paths": {
            "/foo": {
                "post": {
                    "x-method_name": "foo",
                    "description": "foo.",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"a": {"type": "integer"}},
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "",
                            "content": {"application/json": {"schema": {}}},
                        }
                    },
                }
            }
        },
    }

    built = api_pkg_maker.mk_api_pkg(spec, pkg_name="probepkg", pkg_version="1.2.3")

    assert Path(built).is_file()
    assert Path(built).name == "probepkg-1.2.3.tar.gz"
    assert Path(built).parent == tmp_path
    assert Path.cwd() == cwd_before, "mk_api_pkg left the process in another directory"
    with tarfile.open(built) as archive:
        names = {n.split("/", 1)[-1] for n in archive.getnames()}
    assert "probepkg/funcs.py" in names
