"""Server errors come back as the i2 error the server raised."""

from types import SimpleNamespace

import pytest
from i2.errors import AuthorizationError, ForbiddenError, InputError, NotFoundError

from http2py.decorators import _handle_error


@pytest.mark.parametrize(
    "status, reason, error",
    [
        (401, "Unauthorized", AuthorizationError),  # py2http since i2mint/py2http#31
        (400, "AuthorizationError", AuthorizationError),  # older py2http
        (400, "InputError", InputError),
        (403, "Forbidden", ForbiddenError),
        (404, "Not Found", NotFoundError),
        (500, "Internal Server Error", RuntimeError),
    ],
)
def test_status_maps_to_error(status, reason, error):
    resp = SimpleNamespace(status_code=status, reason=reason, text="msg")
    with pytest.raises(error):
        _handle_error(resp)
