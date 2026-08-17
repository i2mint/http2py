"""Tripwires for dependencies http2py declares but does not itself use.

Right now there is exactly one: ``dill``. ``ju/oas.py`` imports it at module
level while ``ju`` does not declare it, and ``ju/__init__.py`` imports ``ju.oas``
eagerly -- so a cold ``pip install http2py`` dies on ``import ju`` with
``ModuleNotFoundError: No module named 'dill'``. Declaring ``dill`` here is a
workaround, tracked upstream as i2mint/ju#6.

A workaround with no expiry becomes permanent, so the test below fails the
moment upstream is fixed (either the import goes away or ``dill`` becomes a
declared requirement of ``ju``). When it fails, drop ``dill`` from
``[project].dependencies`` and delete this module.

The check is deliberately static -- it reads ``ju``'s source and metadata rather
than re-importing ``ju`` with ``dill`` hidden, so it cannot leave a half-imported
package behind for the rest of the session.
"""

import ast
import re
import sys
from importlib.metadata import PackageNotFoundError, requires
from pathlib import Path

import pytest


def _ju_oas_source():
    import ju.oas

    return Path(ju.oas.__file__).read_text()


def _module_level_imports(source):
    """Top-level (non-nested) imported top-level module names."""
    names = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def _declared_requirement_names(distribution):
    try:
        reqs = requires(distribution) or []
    except PackageNotFoundError:  # pragma: no cover - ju is a hard dependency
        pytest.skip(f"{distribution} is not installed as a distribution")
    return {re.split(r"[\s\[<>=!;(]", req, maxsplit=1)[0].lower() for req in reqs}


def test_dill_workaround_is_still_needed():
    """Fails once i2mint/ju#6 is released -- then remove the `dill` dependency."""
    imports_dill = "dill" in _module_level_imports(_ju_oas_source())
    ju_declares_dill = "dill" in _declared_requirement_names("ju")

    assert imports_dill and not ju_declares_dill, (
        "ju no longer needs http2py to carry `dill` for it "
        f"(module-level import: {imports_dill}, declared by ju: {ju_declares_dill}). "
        "Remove `dill` from [project].dependencies in pyproject.toml and delete "
        "this module. See i2mint/ju#6."
    )


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib needs Python 3.11+")
def test_dill_is_declared_while_the_workaround_stands():
    """The workaround only works if the dependency is actually declared.

    Read from pyproject.toml rather than installed metadata: an editable install
    freezes its .dist-info at install time, so the metadata of a dev checkout
    lags the file that CI actually builds from.
    """
    import tomllib

    repo_root = Path(__file__).resolve().parent.parent
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())
    declared = {
        re.split(r"[\s\[<>=!;(]", dep, maxsplit=1)[0].lower()
        for dep in pyproject["project"]["dependencies"]
    }
    assert "dill" in declared, (
        "http2py must declare `dill` while i2mint/ju#6 is open, otherwise a cold "
        "`pip install http2py` fails at `import ju`."
    )
