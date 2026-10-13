"""``mk_cli`` and ``api_pkg_maker`` pass ``binary_loads`` through, and a package
generated from a spec compiles and cannot be made to run code by that spec
(i2mint/http2py#21)."""

from __future__ import annotations

import copy
import importlib
import json
import sys
import tarfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from spec_fixture import SPEC  # noqa: E402

from http2py.api_pkg_maker import api_pkg_files, mk_api_pkg, object_ref  # noqa: E402


def _write(files: dict, root: Path) -> None:
    for relpath, content in files.items():
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


@pytest.fixture
def import_generated(tmp_path, monkeypatch):
    """Write a generated package under tmp_path and import it."""

    def _import(files):
        _write(files, tmp_path)
        monkeypatch.syspath_prepend(str(tmp_path))
        pkg_name = next(path.split("/")[0] for path in files if "/" in path)
        importlib.invalidate_caches()
        module = importlib.import_module(f"{pkg_name}.funcs")
        monkeypatch.delitem(sys.modules, pkg_name)
        monkeypatch.delitem(sys.modules, f"{pkg_name}.funcs")
        return module

    return _import


def test_generated_package_compiles_and_exposes_every_route(import_generated):
    files = api_pkg_files(SPEC, pkg_name="genpkg_routes")
    for relpath, content in files.items():
        if relpath.endswith(".py"):
            compile(content, relpath, "exec")
    funcs = import_generated(files)
    assert {"get_thing", "make", "plain"} <= set(vars(funcs))
    assert funcs.api.binary_loads is None


def test_spec_is_data_not_source():
    spec = copy.deepcopy(SPEC)
    spec["info"]["title"] = "'''\"\"\"); import os; os.system('x') #"
    files = api_pkg_files(spec, pkg_name="genpkg_data")
    assert "os.system" not in files["genpkg_data/funcs.py"]
    assert json.loads(files["genpkg_data/openapi_spec.json"]) == spec


@pytest.mark.parametrize(
    "bad_name",
    [
        "x():\n    import os\n    os.system('x')\ndef y",
        "class",
        "a-b",
        "\uff41\uff50\uff49",  # full-width "api": an identifier Python normalizes to api
        "api",
        "_apply_sig",
        "funcs",
    ],
)
def test_route_name_that_is_not_an_identifier_is_refused(bad_name):
    spec = copy.deepcopy(SPEC)
    spec["paths"]["/plain"]["get"]["x-method_name"] = bad_name
    with pytest.raises(ValueError, match="not an ASCII Python identifier|reserved"):
        api_pkg_files(spec, pkg_name="genpkg_bad")


def test_setup_cfg_fields_stay_on_one_line():
    files = api_pkg_files(
        SPEC, pkg_name="genpkg_cfg", pkg_description="one\n[options]\nscripts = x"
    )
    assert "\n[options]\nscripts" not in files["setup.cfg"]


def test_binary_loads_reaches_the_generated_client(import_generated):
    files = api_pkg_files(SPEC, pkg_name="genpkg_loads", binary_loads=bytes)
    assert import_generated(files).api.binary_loads is bytes


@pytest.mark.parametrize(
    "ref",
    [
        lambda b: b,
        "bytes",
        "os.system('x') or bytes",
        "a.b; import os",
        "json.no_such_loads",
        "json.decoder",  # a module, not a callable
    ],
)
def test_binary_loads_must_be_an_importable_path(ref):
    with pytest.raises(ValueError):
        object_ref(ref)


def test_mk_api_pkg_ships_the_spec(tmp_path):
    pytest.importorskip("setuptools")
    sdist = mk_api_pkg(SPEC, pkg_name="genpkg_sdist", output_dir=str(tmp_path))
    with tarfile.open(sdist) as tar:
        names = tar.getnames()
    assert "genpkg_sdist-1.0.0/genpkg_sdist/openapi_spec.json" in names


def test_dispatch_cli_passes_binary_loads_to_the_client(monkeypatch, tmp_path):
    from http2py import cli_maker

    seen = {}

    class FakeClient:
        def __init__(self, openapi_spec, **kwargs):
            seen.update(kwargs)

        def plain(self, **kwargs):
            return "ran"

    real_mk_cli = cli_maker.mk_cli

    def mk_cli_then_fake_client(*args, **kwargs):
        parser = real_mk_cli(*args, **kwargs)  # built from the real client
        monkeypatch.setattr(cli_maker, "HttpClient", FakeClient)  # run with the fake
        return parser

    monkeypatch.setattr(cli_maker, "mk_cli", mk_cli_then_fake_client)
    monkeypatch.setattr(sys, "argv", ["PROG", "plain", "--api-key", "k"])
    config = tmp_path / "credentials.json"
    config.write_text("{}")
    cli_maker.dispatch_cli(
        openapi_spec=SPEC, config_filename=str(config), binary_loads=bytes
    )
    assert seen["binary_loads"] is bytes


def test_mk_cli_refuses_a_non_callable_binary_loads():
    from http2py.cli_maker import mk_cli

    with pytest.raises(TypeError):
        mk_cli(openapi_spec=SPEC, binary_loads="bytes")


def test_spec_without_routes_is_refused():
    spec = copy.deepcopy(SPEC)
    spec["paths"] = {"/x": {}}
    with pytest.raises(RuntimeError, match="empty"):
        api_pkg_files(spec, pkg_name="genpkg_empty")


def test_spec_may_be_given_as_json_text(import_generated):
    files = api_pkg_files(json.dumps(SPEC), pkg_name="genpkg_text")
    assert "plain" in vars(import_generated(files))


def test_awkward_names_and_values_still_build(tmp_path):
    pytest.importorskip("setuptools")
    spec = copy.deepcopy(SPEC)
    spec["servers"] = [{"url": "https://h/a%20b"}]
    sdist = mk_api_pkg(
        spec,
        pkg_name="MyPkg",
        pkg_version="v1.0",
        pkg_author="100% me",
        output_dir=str(tmp_path),
    )
    assert Path(sdist).is_file()


def test_binary_loads_ref_to_a_module_not_installed_here_is_kept():
    with pytest.warns(UserWarning, match="cannot be imported here"):
        assert object_ref("no_such_module.loads") == "no_such_module.loads"
