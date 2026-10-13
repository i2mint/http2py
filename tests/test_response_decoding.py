"""How responses are decoded (``http2py.decorators``) and how a client's requests are
built from a spec it may have fetched from a server (``mk_request_function``)."""

import pickle
import warnings

import pytest

from http2py.decorators import (
    BinaryResponseNotDecoded,
    check_loads,
    handle_binary_resp,
    unsafe_pickle_loads,
)
from http2py.py2request import mk_request_function


class Resp:
    def __init__(self, content=b"", *, status_code=200, text="", reason="OK"):
        self.content, self.status_code, self.text, self.reason = (
            content,
            status_code,
            text,
            reason,
        )


def _identity(x):
    return x


def test_binary_response_needs_an_explicit_decoder():
    with pytest.raises(BinaryResponseNotDecoded):
        handle_binary_resp(_identity)(Resp(pickle.dumps(1)))
    assert handle_binary_resp(_identity, loads=bytes)(Resp(b"raw")) == b"raw"
    trusted = handle_binary_resp(_identity, loads=unsafe_pickle_loads)
    assert trusted(Resp(pickle.dumps({"a": 1}))) == {"a": 1}


def test_check_loads():
    check_loads(None)
    check_loads(bytes)
    with pytest.raises(TypeError):
        check_loads("pickle.loads")
    with pytest.warns(UserWarning, match="unsafe_pickle_loads"):
        check_loads(pickle.loads)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        check_loads(unsafe_pickle_loads)  # the explicit opt-in does not warn


def test_non_200_binary_response_raises_the_mapped_error():
    from i2.errors import NotFoundError

    with pytest.raises(NotFoundError):
        handle_binary_resp(_identity, loads=bytes)(Resp(status_code=404, text="no"))


def _captured_request(method_spec, **call_kwargs):
    """The (method, url, request kwargs) a request function would dispatch."""
    calls = []

    def dispatch(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return Resp(b"{}")

    func = mk_request_function(method_spec, dispatch=dispatch)
    func(None, **call_kwargs)
    return calls[0]


def test_binary_request_bodies_use_binary_dumps():
    spec = {
        "method": "POST",
        "url_template": "http://h/f",
        "body_arg_names": ["x"],
        "content_type": "application/octet-stream",
        "output_trans": _identity,
    }
    _, _, kwargs = _captured_request(spec, x=1)
    assert pickle.loads(kwargs["data"]) == {"x": 1}
    calls = []
    func = mk_request_function(
        spec,
        dispatch=lambda m, u, **kw: calls.append(kw) or Resp(),
        binary_dumps=lambda d: b"custom",
    )
    func(None, x=1)
    assert calls[0]["data"] == b"custom"


def test_path_args_are_url_encoded():
    spec = {
        "method": "GET",
        "url_template": "http://h/u/{uid}",
        "path_arg_names": ["uid"],
        "output_trans": _identity,
    }
    _, url, _ = _captured_request(spec, uid="a/b c")
    assert url == "http://h/u/a%2Fb%20c"


@pytest.mark.parametrize(
    "template",
    [
        "http://h/{x.__class__}",
        "http://h/{x[0]}",
        "http://h/{x:{x.__class__}}",
        "http://h/{0}",
    ],
)
def test_url_templates_may_only_name_arguments(template):
    """A spec served by a remote must not read attributes of the caller's
    arguments into the URL."""
    spec = {"method": "GET", "url_template": template, "path_arg_names": ["x"]}
    with pytest.raises(ValueError, match="not a plain name"):
        mk_request_function(spec)


def test_spec_with_attribute_placeholder_is_refused_by_the_client():
    import copy
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from spec_fixture import SPEC

    from http2py import HttpClient

    spec = copy.deepcopy(SPEC)
    spec["paths"]["/x/{uid.__class__.__mro__}"] = spec["paths"].pop("/u/{uid}/p/{pid}")
    with pytest.raises(ValueError, match="not a plain name"):
        HttpClient(spec, session_state={"session": object(), "refresh_inputs": {}})
