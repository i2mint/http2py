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
