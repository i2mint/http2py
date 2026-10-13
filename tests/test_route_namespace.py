"""A route's name cannot replace an attribute of ``HttpClient`` (i2mint/http2py#23):
every route is in ``client.routes``, and only names that collide with nothing are
also set as attributes."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from spec_fixture import SPEC  # noqa: E402

from http2py import HttpClient  # noqa: E402
from http2py.api_pkg_maker import api_pkg_files  # noqa: E402


def _spec_naming_plain(name):
    spec = copy.deepcopy(SPEC)
    spec["paths"]["/plain"]["get"]["x-method_name"] = name
    return spec


def _client(spec):
    return HttpClient(spec, session_state={"session": object(), "refresh_inputs": {}})


@pytest.mark.parametrize(
    "name",
    ["openapi_spec", "session", "handle_request", "ensure_login", "binary_loads"]
    + ["routes", "login_args", "login_response_keys", "verify_cert", "_private"],
)
def test_colliding_route_name_keeps_the_client_attribute(name):
    spec = _spec_naming_plain(name)
    with pytest.warns(UserWarning, match=f"client.routes\\[{name!r}\\]"):
        client = _client(spec)
    route = client.routes[name]
    assert getattr(route, "method_spec", None)
    assert getattr(client, name, None) is not route
    assert client.openapi_spec is spec
    assert callable(client.handle_request) and callable(client.ensure_login)


def test_non_colliding_routes_are_attributes_too():
    client = _client(SPEC)
    assert set(client.routes) == {"get_thing", "make", "plain"}
    for name, route in client.routes.items():
        assert getattr(client, name) is route
        assert client.is_request_method(name)


def test_api_pkg_for_a_route_named_like_a_client_attribute():
    # used to crash with "'function' object has no attribute 'get'"
    with pytest.warns(UserWarning):
        files = api_pkg_files(_spec_naming_plain("openapi_spec"), pkg_name="genpkg_c")
    funcs = files["genpkg_c/funcs.py"]
    assert "def openapi_spec(" in funcs
    assert "api.routes['openapi_spec']" in funcs


@pytest.mark.parametrize("name", ["title", "version", "base_url"])
def test_informational_attributes_can_be_route_names(name):
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client = _client(_spec_naming_plain(name))
    assert getattr(client, name) is client.routes[name]


def test_duplicate_route_names_warn():
    with pytest.warns(UserWarning, match="Two routes are named 'get_thing'"):
        client = _client(_spec_naming_plain("get_thing"))
    assert set(client.routes) == {"get_thing", "make"}


def test_cli_calls_the_route_not_the_client_attribute(monkeypatch):
    from http2py import cli_maker

    spec = _spec_naming_plain("ensure_login")
    with pytest.warns(UserWarning):
        route = _client(spec).routes["ensure_login"]

    class Sent(Exception):
        pass

    def handle_request(self, method, url, **kw):
        raise Sent(url)

    monkeypatch.setattr(HttpClient, "handle_request", handle_request)
    with pytest.warns(UserWarning), pytest.raises(Sent, match="/plain$"):
        cli_method = cli_maker.register_cli_method(spec, route, [])
        cli_method(config="no-such-config", api_key="k")


def test_subclass_skipping_init_can_register_routes():
    class Bare(HttpClient):
        def __init__(self):
            self.verify_cert, self.binary_loads, self.binary_dumps = True, None, None

    bare = Bare()
    spec = SPEC["paths"]["/plain"]["get"]
    bare.register_method("https://example.com/plain", "get", spec)
    assert bare.routes["plain"] is bare.plain


def _spec_without_names():
    """A spec whose routes have no ``x-method_name`` (i2mint/http2py#26)."""
    spec = copy.deepcopy(SPEC)
    for path_item in spec["paths"].values():
        for op in path_item.values():
            op.pop("x-method_name", None)
    return spec


def test_routes_without_x_method_name_get_distinct_names_from_method_and_path():
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        client = _client(_spec_without_names())
    assert len(client.routes) == len(SPEC["paths"]) == 3
    assert "get_plain" in client.routes
    for name, route in client.routes.items():
        assert route.__name__ == name != "request_func"


def test_operation_id_names_a_route_without_x_method_name():
    spec = _spec_without_names()
    spec["paths"]["/plain"]["get"]["operationId"] = "list-plain.things"
    assert "list_plain_things" in _client(spec).routes


def test_x_method_name_wins_over_operation_id():
    spec = _spec_naming_plain("mine")
    spec["paths"]["/plain"]["get"]["operationId"] = "theirs"
    assert "mine" in _client(spec).routes


def test_api_pkg_for_a_spec_without_x_method_names():
    files = api_pkg_files(_spec_without_names(), pkg_name="genpkg_d")
    assert "def get_plain(" in files["genpkg_d/funcs.py"]


def test_generated_package_pins_the_http2py_that_has_client_routes():
    from http2py.api_pkg_maker import MIN_HTTP2PY_VERSION

    files = api_pkg_files(SPEC, pkg_name="genpkg_e")
    assert f"http2py>={MIN_HTTP2PY_VERSION}" in files["setup.cfg"]


def test_derived_names_do_not_depend_on_the_server_url():
    spec = _spec_without_names()
    spec["servers"] = [{"url": "https://example.com/v1/api"}]
    assert set(_client(spec).routes) == set(_client(_spec_without_names()).routes)


@pytest.mark.parametrize("operation_id", ["-", "___", "日本"])
def test_unusable_operation_id_falls_back_to_method_and_path(operation_id):
    spec = _spec_without_names()
    spec["paths"]["/plain"]["get"]["operationId"] = operation_id
    assert "get_plain" in _client(spec).routes


def test_a_second_route_of_the_same_name_replaces_the_first_with_a_warning():
    spec = copy.deepcopy(SPEC)
    other = copy.deepcopy(spec["paths"]["/plain"])
    spec["paths"]["/plain2"] = other
    with pytest.warns(UserWarning, match="Two routes are named"):
        client = _client(spec)
    name = other["get"]["x-method_name"]
    assert client.routes[name].method_spec["url_template"].endswith("/plain2")
    assert getattr(client, name) is client.routes[name]
