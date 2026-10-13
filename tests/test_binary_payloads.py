"""Binary (octet-stream) responses are never unpickled unless explicitly asked."""

import pickle

import pytest

from http2py import HttpClient, mk_request_function
from http2py.constants import BINARY_CONTENT_TYPE, JSON_CONTENT_TYPE
from http2py.decorators import (
    BinaryResponseNotDecoded,
    handle_binary_resp,
    unsafe_pickle_loads,
)

_calls = []


def _record(*args):
    _calls.append(args)
    return "ran"


class _RunsCodeWhenUnpickled:
    """Unpickling this calls ``_record``: a harmless stand-in for a payload."""

    def __reduce__(self):
        return (_record, ("unpickled",))


EVIL = pickle.dumps(_RunsCodeWhenUnpickled())


class _Resp:
    status_code = 200

    def __init__(self, content):
        self.content = content


def _binary_spec(**extra):
    return dict(
        method="post",
        url="http://test.invalid/f",
        content_type=BINARY_CONTENT_TYPE,
        response_type=BINARY_CONTENT_TYPE,
        body_arg_names=["x"],
        **extra,
    )


def _fake_dispatch(content, sent):
    def dispatch(method, url, **request_kwargs):
        sent.append(request_kwargs)
        return _Resp(content)

    return dispatch


def test_binary_response_is_not_unpickled_by_default():
    _calls.clear()
    f = mk_request_function(
        _binary_spec(), function_kind="function", dispatch=_fake_dispatch(EVIL, [])
    )
    with pytest.raises(BinaryResponseNotDecoded, match="unsafe_pickle_loads"):
        f(x=1)
    assert _calls == []


def test_binary_loads_choices():
    _calls.clear()
    raw = mk_request_function(
        _binary_spec(),
        function_kind="function",
        dispatch=_fake_dispatch(EVIL, []),
        binary_loads=bytes,
    )
    assert raw(x=1) == EVIL and _calls == []

    trusted = mk_request_function(
        _binary_spec(),
        function_kind="function",
        dispatch=_fake_dispatch(pickle.dumps({"a": 1}), []),
        binary_loads=unsafe_pickle_loads,
    )
    assert trusted(x=1) == {"a": 1}


def test_bare_pickle_loads_warns_and_non_callable_is_rejected():
    with pytest.warns(UserWarning, match="unsafe_pickle_loads"):
        handle_binary_resp(lambda x: x, loads=pickle.loads)
    with pytest.raises(TypeError):
        handle_binary_resp(lambda x: x, loads="pickle")


def test_binary_dumps_encodes_request_body():
    sent = []
    f = mk_request_function(
        _binary_spec(),
        function_kind="function",
        dispatch=_fake_dispatch(b"ok", sent),
        binary_loads=bytes,
        binary_dumps=lambda kwargs: repr(sorted(kwargs.items())).encode(),
    )
    f(x=1)
    assert sent[-1]["data"] == b"[('x', 1)]"

    sent.clear()
    mk_request_function(
        _binary_spec(),
        function_kind="function",
        dispatch=_fake_dispatch(b"ok", sent),
        binary_loads=bytes,
    )(x=1)
    assert pickle.loads(sent[-1]["data"]) == {"x": 1}  # default stays pickle


def test_http_client_passes_binary_loads_through():
    spec = {
        "openapi": "3.0.3",
        "info": {"title": "t", "version": "1"},
        "servers": [{"url": "http://test.invalid"}],
        "paths": {
            "/f": {
                "post": {
                    "x-method_name": "f",
                    "requestBody": {
                        "content": {
                            JSON_CONTENT_TYPE: {
                                "schema": {
                                    "type": "object",
                                    "properties": {"x": {"type": "integer"}},
                                }
                            }
                        }
                    },
                    "responses": {"200": {"content": {BINARY_CONTENT_TYPE: {}}}},
                }
            }
        },
    }

    def client(**kwargs):
        c = HttpClient(
            spec, session_state={"session": object(), "refresh_inputs": {}}, **kwargs
        )
        c.handle_request = _fake_dispatch(EVIL, [])
        c.register_method("http://test.invalid/f", "post", spec["paths"]["/f"]["post"])
        return c

    _calls.clear()
    with pytest.raises(BinaryResponseNotDecoded):
        client().f(x=1)
    assert client(binary_loads=bytes).f(x=1) == EVIL
    assert _calls == []
