"""Offline tests of http2py's error mapping, loads validation, util helpers and ``mk_auth``."""

import json
import pickle
import warnings

import pytest
from i2.errors import (
    AuthorizationError,
    DuplicateRecordError,
    ForbiddenError,
    InputError,
    NotFoundError,
)

from http2py.authentication import mk_auth
from http2py.decorators import (
    _handle_error,
    _handle_resp,
    check_loads,
    unsafe_pickle_loads,
)
from http2py.constants import JSON_CONTENT_TYPE, RAW_CONTENT_TYPE
from http2py.util import (
    I2mintModuleNotFoundErrorNiceMessage,
    ModuleNotFoundErrorNiceMessage,
    add_defaults,
    is_jsonable,
)


class Resp:
    def __init__(self, status_code=200, reason="", text="msg", content=b"", payload=None):
        self.status_code, self.reason, self.text = status_code, reason, text
        self.content, self._payload = content, payload

    def json(self):
        return self._payload


@pytest.mark.parametrize(
    "status, reason, exc",
    [
        (400, "AuthorizationError", AuthorizationError),
        (400, "InputError", InputError),
        (400, "DuplicateRecordError", DuplicateRecordError),
        (401, "", AuthorizationError),
        (403, "", ForbiddenError),
        (404, "", NotFoundError),
        (400, "Other", RuntimeError),
        (500, "", RuntimeError),
    ],
)
def test_handle_error_maps_status_to_exception(status, reason, exc):
    with pytest.raises(exc):
        _handle_error(Resp(status, reason))


def test_handle_resp_json_raw_and_unsupported_types():
    assert _handle_resp(lambda x: x, JSON_CONTENT_TYPE)(Resp(payload={"a": 1})) == {"a": 1}
    assert _handle_resp(lambda x: x, RAW_CONTENT_TYPE)(Resp(text="hi")) == "hi"
    with pytest.raises(NotImplementedError):
        _handle_resp(lambda x: x, "text/weird")(Resp())
    with pytest.raises(NotFoundError):
        _handle_resp(lambda x: x, RAW_CONTENT_TYPE)(Resp(404))


def test_check_loads_validation_and_pickle_warning():
    check_loads(None)
    check_loads(bytes)
    with pytest.raises(TypeError):
        check_loads("not callable")
    with pytest.warns(UserWarning, match="unsafe_pickle_loads"):
        check_loads(pickle.loads)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        check_loads(unsafe_pickle_loads)
    assert unsafe_pickle_loads(pickle.dumps([1, 2])) == [1, 2]


def test_add_defaults_fills_only_missing_keys():
    d = {"a": {"x": 1}, "b": {}}
    assert add_defaults(d, {"x": 0, "y": 2}) == {"a": {"x": 1, "y": 2}, "b": {"x": 0, "y": 2}}


def test_is_jsonable():
    assert is_jsonable({"a": [1, 2]}) and not is_jsonable(object())


@pytest.mark.parametrize(
    "cm, hint", [(ModuleNotFoundErrorNiceMessage, "pip install nopkg"), (I2mintModuleNotFoundErrorNiceMessage, "git clone")]
)
def test_nice_module_not_found_messages(cm, hint):
    with pytest.raises(ModuleNotFoundError, match=hint):
        with cm():
            import nopkg_does_not_exist  # noqa: F401

    with pytest.raises(ModuleNotFoundError) as e:
        with cm():
            raise ModuleNotFoundError(name="nopkg")
    assert "nopkg" in str(e.value)
    with cm():  # other outcomes pass through
        pass


def test_mk_auth_fills_missing_values_from_the_credentials_file(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"default": {"key": "d"}, "work": {"key": "w", "secret": "s"}}))
    assert mk_auth({"key": "given"}, ["key"], cfg) == {"key": "given"}
    assert mk_auth({}, ["key"], cfg) == {"key": "d"}
    assert mk_auth({}, ["key", "secret"], cfg, profile="work") == {"key": "w", "secret": "s"}
    assert mk_auth({}, ["key"], cfg, profile="missing") == {"key": "d"}
    flat = tmp_path / "f.json"
    flat.write_text(json.dumps({"key": "flat"}))
    assert mk_auth({}, ["key", "other"], flat) == {"key": "flat", "other": ""}
