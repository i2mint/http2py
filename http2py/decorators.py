from functools import partial
from i2.errors import (
    AuthorizationError,
    ForbiddenError,
    InputError,
    NotFoundError,
    DuplicateRecordError,
)
import pickle

from http2py.constants import BINARY_CONTENT_TYPE, JSON_CONTENT_TYPE, RAW_CONTENT_TYPE


def _handle_error(resp):
    if resp.status_code == 400:
        if resp.reason == 'AuthorizationError':
            raise AuthorizationError(resp.text)
        if resp.reason == 'InputError':
            raise InputError(resp.text)
        if resp.reason == 'DuplicateRecordError':
            raise DuplicateRecordError(resp.text)
    if resp.status_code == 403:
        raise ForbiddenError(resp.text)
    if resp.status_code == 404:
        raise NotFoundError(resp.text)
    raise RuntimeError(resp.text)


def _handle_resp(func, content_type):
    def output_trans(resp):
        if resp.status_code == 200:
            if content_type == JSON_CONTENT_TYPE:
                output = resp.json()
            elif content_type == BINARY_CONTENT_TYPE:
                output = pickle.loads(resp.content)
            elif content_type == RAW_CONTENT_TYPE:
                output = resp.text
            else:
                raise NotImplementedError(
                    f'Response of type {content_type} is not supported yet.'
                )
            return func(output)
        else:
            _handle_error(resp)

    output_trans.content_type = content_type
    return output_trans


handle_json_resp = partial(_handle_resp, content_type=JSON_CONTENT_TYPE)
handle_binary_resp = partial(_handle_resp, content_type=BINARY_CONTENT_TYPE)
handle_raw_resp = partial(_handle_resp, content_type=RAW_CONTENT_TYPE)
