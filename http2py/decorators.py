"""Response handling: map http status codes to exceptions, decode the payload.

``handle_json_resp`` / ``handle_binary_resp`` / ``handle_raw_resp`` wrap an
output transformation so it only ever sees a successful response of the
expected content type.

Binary (``application/octet-stream``) responses are never unpickled unless asked:
unpickling runs code chosen by whoever produced the bytes, so a spoofed or
compromised server could run code on the client. Pass ``loads=`` to
``handle_binary_resp`` (or ``binary_loads=`` to ``mk_request_function`` /
``HttpClient``): ``bytes`` for the raw content, a decoder of your own, or
``unsafe_pickle_loads`` if (and only if) the server is fully trusted.

>>> class Resp:
...     status_code, content = 200, b'raw bytes'
>>> handle_binary_resp(lambda x: x, loads=bytes)(Resp())
b'raw bytes'
>>> handle_binary_resp(lambda x: x)(Resp())  # doctest: +ELLIPSIS
Traceback (most recent call last):
  ...
http2py.decorators.BinaryResponseNotDecoded: Got a binary response but no loads=... to decode it. ...
"""

import pickle
import warnings
from collections.abc import Callable
from functools import partial
from typing import Any, Optional

from i2.errors import (
    AuthorizationError,
    ForbiddenError,
    InputError,
    NotFoundError,
    DuplicateRecordError,
)

from http2py.constants import BINARY_CONTENT_TYPE, JSON_CONTENT_TYPE, RAW_CONTENT_TYPE


def _handle_error(resp):
    if resp.status_code == 400:
        if resp.reason == "AuthorizationError":
            raise AuthorizationError(resp.text)
        if resp.reason == "InputError":
            raise InputError(resp.text)
        if resp.reason == "DuplicateRecordError":
            raise DuplicateRecordError(resp.text)
    if resp.status_code == 403:
        raise ForbiddenError(resp.text)
    if resp.status_code == 404:
        raise NotFoundError(resp.text)
    raise RuntimeError(resp.text)


class BinaryResponseNotDecoded(ValueError):
    """A binary response arrived, but no ``loads`` was given to decode it."""


def unsafe_pickle_loads(data: bytes) -> Any:
    """Unpickle ``data``. UNSAFE on anything an untrusted server can send.

    Unpickling runs code chosen by whoever produced the bytes, so use this only
    when the server (and the network path to it) is fully trusted. It exists so
    that opting into pickled responses is explicit and visible at the call site::

        HttpClient(spec, binary_loads=unsafe_pickle_loads)
    """
    return pickle.loads(data)


def _check_loads(loads):
    if loads is None:
        return
    if not callable(loads):
        raise TypeError(f"loads must be callable, got {loads!r}")
    if loads is pickle.loads:
        warnings.warn(
            "loads=pickle.loads unpickles server data, which lets a spoofed or "
            "compromised server run code on this client. Use "
            "loads=unsafe_pickle_loads to make that choice explicit, and only if "
            "the server is fully trusted.",
            stacklevel=3,
        )


def _handle_resp(func, content_type, *, loads: Optional[Callable[[bytes], Any]] = None):
    _check_loads(loads)

    def output_trans(resp):
        if resp.status_code == 200:
            if content_type == JSON_CONTENT_TYPE:
                output = resp.json()
            elif content_type == BINARY_CONTENT_TYPE:
                if loads is None:
                    raise BinaryResponseNotDecoded(
                        "Got a binary response but no loads=... to decode it. "
                        "Binary responses are no longer unpickled by default, "
                        "since unpickling lets the server run code on this "
                        "client. Pass binary_loads=bytes for the raw content, a "
                        "decoder of your own, or binary_loads=unsafe_pickle_loads "
                        "(from http2py.decorators) if the server is fully trusted."
                    )
                output = loads(resp.content)
            elif content_type == RAW_CONTENT_TYPE:
                output = resp.text
            else:
                raise NotImplementedError(
                    f"Response of type {content_type} is not supported yet."
                )
            return func(output)
        else:
            _handle_error(resp)

    output_trans.content_type = content_type
    return output_trans


handle_json_resp = partial(_handle_resp, content_type=JSON_CONTENT_TYPE)
handle_binary_resp = partial(_handle_resp, content_type=BINARY_CONTENT_TYPE)
handle_raw_resp = partial(_handle_resp, content_type=RAW_CONTENT_TYPE)
