"""Smoke tests: the package imports and its advertised public surface works.

http2py is in maintenance mode (its README points users at ``ho``), so these
tests deliberately stay at the level of "a `pip install http2py` is usable":
the top-level import succeeds, the names re-exported from ``__init__`` exist,
and the central factory still builds a callable with the right signature. No
network is touched.
"""

import pytest


def test_import():
    import http2py  # noqa: F401


@pytest.mark.parametrize(
    "name", ["HttpClient", "mk_cli", "dispatch_cli", "mk_request_function"]
)
def test_public_names_are_exported(name):
    import http2py

    assert hasattr(http2py, name), f"http2py.{name} is missing from the public API"


def test_mk_request_function_formats_the_url_template_from_path_args():
    """The core factory: spec in, callable out, url_template filled from args.

    ``dispatch`` is injected so nothing leaves the machine -- that seam is the
    reason this can be a real behavioural test rather than a mock-heavy one.
    """
    from http2py import mk_request_function

    calls = []

    class _Response:
        status_code = 200
        text = "pong"

    def fake_dispatch(method, url, **request_kwargs):
        calls.append((method, url))
        return _Response()

    func = mk_request_function(
        {
            "method_name": "ping",
            "url_template": "https://example.com/ping/{who}",
            "path_arg_names": ["who"],
            "method": "GET",
        },
        function_kind="function",
        dispatch=fake_dispatch,
    )

    assert callable(func)
    assert func.func_args == ["who"]
    assert func(who="bob") == "pong"
    assert calls == [("GET", "https://example.com/ping/bob")]


def test_http_client_from_openapi_spec_binds_declared_methods():
    from http2py import HttpClient

    spec = {
        "openapi": "3.0.2",
        "info": {"title": "example", "version": "0.1"},
        "servers": [{"url": "https://example.com"}],
        "paths": {
            "/ping": {
                "get": {
                    "x-method_name": "ping",
                    "description": "Answers with a pong.",
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
    client = HttpClient(openapi_spec=spec)
    assert callable(getattr(client, "ping", None))
