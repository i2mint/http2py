from glom import glom
from requests import request, Session
from i2.errors import AuthorizationError

from http2py.authentication import mk_auth, DFLT_CONFIG_FILENAME
from http2py.py2request import mk_method_spec_from_openapi_method_spec, mk_request_function
from http2py.global_state import get_global_state


class HttpClient:
    """
    A client class meant as an interface to an HTTP service with one or more routes
    defined with an OpenAPI spec.
    """
    auth_type = ''
    login_input_keys = []
    login_url = ''
    openapi_spec = {}
    refresh_url = ''
    refresh_input_keys = []
    session = None

    def __init__(self, openapi_spec, session_state=None, **auth_kwargs):
        """
        Initialize the client with an OpenAPI spec and optional authentication inputs

        :param openapi_spec: A server specification in OpenAPI format
        :param session: A session for HTTP requests

        :Keyword Arguments:
            * *api_key*
              The API key, if using API key auth
            * account, email, password, etc. *
              Input values to be passed to the login url, if using bearer auth

        """
        self.openapi_spec = openapi_spec
        server_info = openapi_spec['info']
        self.title = server_info['title']
        self.version = server_info['version']
        self.base_url = glom(openapi_spec, 'servers.0.url')
        security = openapi_spec.get('security', None)
        self.session = Session()
        if security:
            self.init_security(openapi_spec, **auth_kwargs)
        if not session_state:
            session_state = get_global_state(
                'session_state',
                {'session': self.session, 'refresh_inputs': {}}
            )
        self.session = session_state.get('session')
        if not self.session:
            raise ValueError('No session provided when instantiating HttpClient')
        self.refresh_inputs = session_state.get('refresh_inputs')
        if self.refresh_inputs is None:
            raise ValueError('No refresh inputs provided when instantiating HttpClient')
        for pathname, path_spec in openapi_spec['paths'].items():
            url_template = self.base_url + pathname
            for http_method, openapi_method_spec in path_spec.items():
                self.register_method(url_template, http_method, openapi_method_spec)

    def init_security(self, openapi_spec, **auth_kwargs):
        security = openapi_spec['security']
        auth_type = list(security.keys())[0]
        if auth_type == 'apiKey':
            self.auth_type = 'api_key'
            self.api_key = auth_kwargs.get('api_key', None)
            self.set_header({'Authorization': self.api_key})
        elif auth_type == 'bearerAuth':
            self.auth_type = 'login'
            login_details = glom(openapi_spec, 'components.securitySchemes.bearerAuth.x-login', default={})
            self.login_url = login_details.get('login_url', None)
            self.login_input_keys = login_details.get('login_inputs', [])
            self.login_args = {}
            for key in auth_kwargs:
                if key in self.login_input_keys:
                    self.login_args[key] = auth_kwargs[key] or False
            self.refresh_input_keys = login_details.get('refresh_inputs', [])
            self.login_response_keys = login_details.get('outputs', [])

    def register_method(self, url_template, http_method, openapi_method_spec):
        content_type = None
        if 'requestBody' in openapi_method_spec:
            content_type = next(iter(glom(openapi_method_spec, 'requestBody.content').keys()))
        method_spec = mk_method_spec_from_openapi_method_spec(openapi_method_spec,
                                                              method=http_method,
                                                              url_template=url_template,
                                                              content_type=content_type)
        func = mk_request_function(method_spec, dispatch=self.handle_request)
        func.method_spec = method_spec
        func.content_type = content_type
        funcname = func.__name__
        setattr(self, funcname, func.__get__(self))

    def handle_request(self, method, url, **_request_kwargs):
        self.ensure_login()
        return self.session.request(method, url, **_request_kwargs)

    def set_header(self, header):
        self.session.headers.update(header)


    def ensure_login(self):
        if self.auth_type != 'login':
            return True
        if not self.session.headers.get('Authorization', None):
            return self.login()
        return True

    def login(self):
        if not self.login_url:
            raise ValueError('Login was called without a login url. '
                             'Check your initialization arguments for HttpClient.')
        if not self.login_args:
            raise ValueError('Login was called without any login inputs. '
                             'Check your initialization arguments for HttpClient.')
        login_result = request('post', self.login_url, json=self.login_args).json()
        return self.receive_login(login_result)

    def refresh_login(self):
        if not self.refresh_url or not self.refresh_inputs:
            return self.login()
        refresh_result = request('post', self.refresh_url, json=self.refresh_inputs).json()
        return self.receive_login(refresh_result)

    def receive_login(self, login_result):
        error = login_result.get('error', None)
        if error:
            raise AuthorizationError(error)
        for key in self.login_response_keys:
            value = login_result.get(key, None)
            if key == 'jwt':
                auth_header = {'Authorization': f'Bearer {value}'}
                self.set_header(auth_header)
            elif key in self.refresh_input_keys:
                self.refresh_inputs[key] = value

    def set_profile(self, profile: str, config: str = DFLT_CONFIG_FILENAME):
        new_auth = mk_auth({}, self.login_input_keys, config, profile)
        if not new_auth:
            raise KeyError(f'Could not find authentication credentials for profile {profile} in file {config}')
        for key in new_auth:
            if key in self.login_input_keys:
                self.login_args[key] = new_auth[key] or False
            self.login()
