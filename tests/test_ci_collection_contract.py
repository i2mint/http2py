"""Guards on what CI is allowed to collect -- the thing that was actually broken.

Under ``pytest --doctest-modules`` (what the CI test action runs) an unimportable
module is not one red test, it is a collection abort that takes the whole session
down. Two modules in this repo are in that state:

* ``http2py/api_pkg_maker.py`` imports ``setuptools.sandbox``, removed from
  modern setuptools;
* ``http2py/tests/api_pkg_maker_test.py`` imports that module.

Both are left in place on purpose (rewriting vs. deleting ``api_pkg_maker`` is
still open on issue #14) and excluded from collection in two places that must
agree: ``[tool.wads.ci.testing].exclude_paths`` in pyproject.toml, and
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
# Keep this in step with pyproject's exclude_paths and conftest's collect_ignore.
KNOWN_UNIMPORTABLE = {"http2py.api_pkg_maker"}

EXPECTED_EXCLUDED_PATHS = {"http2py/api_pkg_maker.py", "http2py/tests"}


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


def test_known_broken_module_is_still_broken():
    """Tripwire for issue #14.

    If ``api_pkg_maker`` starts importing again (someone rewrote it, or removed
    it), the exclusions below are dead weight and the #14 (a)/(b) question is
    answered -- so this deliberately fails to force that cleanup rather than
    letting a stale exclusion sit there forever.
    """
    for name in KNOWN_UNIMPORTABLE:
        with pytest.raises(ImportError):
            importlib.import_module(name)


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
