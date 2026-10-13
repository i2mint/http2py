"""The main entry point: a python object facading an http service.

:class:`HttpClient` takes an OpenAPI specification (a dict, or the URL of one)
and exposes each declared route as a normal python method.
"""

import warnings

from glom import glom
from requests import request, get, Session
from i2.errors import AuthorizationError

from http2py.authentication import mk_auth, DFLT_CONFIG_FILENAME
from http2py.py2request import (
    DFLT_BINARY_DUMPS,
    mk_method_spec_from_openapi_method_spec,
    mk_request_function,
)
from http2py.decorators import check_loads
from http2py.global_state import get_global_state


class HttpClient:
    """
    A client class meant as an interface to an HTTP service with one or more routes
    defined with an OpenAPI spec.

    Every route is in ``client.routes`` (a ``{name: method}`` dict), and is also an
    attribute of the client (``client.<name>``) as long as its name neither starts
    with ``_`` nor is already an attribute of the client: a spec, possibly served by
    a remote, must not be able to replace the client's own attributes (such as
    ``session`` or ``handle_request``). A route that cannot be an attribute is still
    reachable as ``client.routes[name]``, and a warning says so.
    """

    auth_type = ""
    login_input_keys = []
    login_url = ""
    openapi_spec = {}
    refresh_url = ""
    refresh_input_keys = []
    session = None
    login_args = None  # set by init_security; declared so no route can take the name

    def __init__(
        self,
        openapi_spec=None,
        url=None,
        session_state=None,
        base_url=None,
        verify_cert=True,
        *,
        binary_loads=None,
        binary_dumps=DFLT_BINARY_DUMPS,
        **auth_kwargs,
    ):
        """
        Initialize the client with an OpenAPI spec and optional authentication inputs

        :param openapi_spec: A server specification in OpenAPI format
        :param url: The url to fetch the OpenAPI specification. It will overwrite `openapi_spec` if provided.
        :param session: A session for HTTP requests
        :param base_url: A base url to enforce if you don't want to take the base url from the OpenAPI spec
        :param verify_cert: If True, it verifies the SSL certificate validity for each https request.
        :param binary_loads: How to decode binary (octet-stream) responses. By
            default they are NOT unpickled (that would let the server run code on
            this client) and raise ``BinaryResponseNotDecoded``; pass ``bytes``,
            a decoder of your own, or ``http2py.decorators.unsafe_pickle_loads``
            if the server is fully trusted.
        :param binary_dumps: How to encode binary request bodies (default
            ``pickle.dumps``).

        :Keyword Arguments:
            * *api_key*
              The API key, if using API key auth
            * account, email, password, etc. *
              Input values to be passed to the login url, if using bearer auth

        """
        self.verify_cert = verify_cert
        check_loads(binary_loads)
        self.binary_loads = binary_loads
        self.binary_dumps = binary_dumps
        if url and not openapi_spec:
            openapi_spec = get(url, verify=self.verify_cert).json()
        self.openapi_spec = openapi_spec
        server_info = openapi_spec["info"]
        self.title = server_info["title"]
        self.version = server_info["version"]
        if base_url:
            self.base_url = base_url
        else:
            self.base_url = glom(openapi_spec, "servers.0.url")
        security = openapi_spec.get("security", None)
        self.session = Session()
        if security:
            self.init_security(openapi_spec, **auth_kwargs)
        if not session_state:
            session_state = get_global_state(
                "session_state",
                {"session": self.session, "refresh_inputs": {}},
            )
        self.session = session_state.get("session")
        if not self.session:
            raise ValueError("No session provided when instantiating HttpClient")
        self.refresh_inputs = session_state.get("refresh_inputs")
        if self.refresh_inputs is None:
            raise ValueError("No refresh inputs provided when instantiating HttpClient")
        self.routes = {}
        for pathname, path_spec in openapi_spec["paths"].items():
            url_template = self.base_url + pathname
            for http_method, openapi_method_spec in path_spec.items():
                self.register_method(url_template, http_method, openapi_method_spec)

    def init_security(self, openapi_spec, **auth_kwargs):
        security = openapi_spec["security"]
        auth_type = list(security.keys())[0]
        if auth_type == "apiKey":
            self.auth_type = "api_key"
            api_key = auth_kwargs.get("api_key", None)
            self.set_header({"Authorization": api_key})
        elif auth_type == "bearerAuth":
            self.auth_type = "login"
            login_details = glom(
                openapi_spec,
                "components.securitySchemes.bearerAuth.x-login",
                default={},
            )
            self.login_url = login_details.get("login_url", None)
            self.login_input_keys = login_details.get("login_inputs", [])
            self.login_args = {}
            for key in auth_kwargs:
                if key in self.login_input_keys:
                    self.login_args[key] = auth_kwargs[key] or False
            self.refresh_input_keys = login_details.get("refresh_inputs", [])
            self.login_response_keys = login_details.get("outputs", [])
            jwt = auth_kwargs.get("jwt", None)
            if jwt:
                self.set_header({"Authorization": f"Bearer {jwt}"})

    def register_method(self, url_template, http_method, openapi_method_spec):
        content_type = None
        if "requestBody" in openapi_method_spec:
            content_type = next(
                iter(glom(openapi_method_spec, "requestBody.content").keys())
            )
        method_spec = mk_method_spec_from_openapi_method_spec(
            openapi_method_spec,
            method=http_method,
            url_template=url_template,
            content_type=content_type,
        )
        func = mk_request_function(
            method_spec,
            dispatch=self.handle_request,
            verify_cert=self.verify_cert,
            binary_loads=self.binary_loads,
            binary_dumps=self.binary_dumps,
        )
        func.method_spec = method_spec
        func.content_type = content_type
        funcname = func.__name__
        method = func.__get__(self)
        can_be_attribute = self._can_be_route_attribute(funcname)
        self.routes[funcname] = method
        if can_be_attribute:
            setattr(self, funcname, method)
        else:
            warnings.warn(
                f"Route {funcname!r} is not set as an attribute of the client: the name "
                f"starts with '_' or is already an attribute of {type(self).__name__}. "
                f"Call it as client.routes[{funcname!r}](...).",
                stacklevel=2,
            )

    def _can_be_route_attribute(self, name):
        """Whether a route called ``name`` may be set as an attribute of the client:
        the name is public, and is not an attribute already (unless that attribute is
        an earlier route of the same name, which a later route replaces)."""
        if name.startswith("_"):
            return False
        if name in self.routes:
            return vars(self).get(name) is self.routes[name]
        return not hasattr(self, name)

    def handle_request(self, method, url, **_request_kwargs):
        self.ensure_login()
        return self.session.request(method, url, **_request_kwargs)

    def set_header(self, header):
        self.session.headers.update(header)

    def ensure_login(self):
        if self.auth_type != "login":
            return True
        if not self.session.headers.get("Authorization", None):
            return self._login()
        return True

    def _login(self):
        if not self.login_url:
            raise ValueError(
                "Login was called without a login url. "
                "Check your initialization arguments for HttpClient."
            )
        if not self.login_args:
            raise ValueError(
                "Login was called without any login inputs. "
                "Check your initialization arguments for HttpClient."
            )
        login_result = request("post", self.login_url, json=self.login_args).json()
        return self.receive_login(login_result)

    def refresh_login(self):
        if not self.refresh_url or not self.refresh_inputs:
            return self._login()
        refresh_result = request(
            "post", self.refresh_url, json=self.refresh_inputs
        ).json()
        return self.receive_login(refresh_result)

    def receive_login(self, login_result):
        error = login_result.get("error", None)
        if error:
            raise AuthorizationError(error)
        for key in self.login_response_keys:
            value = login_result.get(key, None)
            if key == "jwt":
                auth_header = {"Authorization": f"Bearer {value}"}
                self.set_header(auth_header)
            elif key in self.refresh_input_keys:
                self.refresh_inputs[key] = value

    def set_profile(self, profile: str, config: str = DFLT_CONFIG_FILENAME):
        new_auth = mk_auth({}, self.login_input_keys, config, profile)
        if not new_auth:
            raise KeyError(
                f"Could not find authentication credentials for profile {profile} in file {config}"
            )
        for key in new_auth:
            if key in self.login_input_keys:
                self.login_args[key] = new_auth[key] or False
            self._login()

    def is_request_method(self, methodname):
        method = self.routes.get(methodname) or getattr(self, methodname)
        return method and hasattr(method, "method_spec")
