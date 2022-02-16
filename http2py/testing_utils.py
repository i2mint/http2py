from http2py.client import HttpClient

TEST_NUMBER = 100
TEST_STRING = 'test'


class MockHttpClient(HttpClient):
    def __init__(self, openapi_spec=None, session_state=None, url=None, **auth_kwargs):
        self.ping.method_spec = {}

    def add_mock_methods(self, methods):
        for method_def in methods:

            def _method(*args, **kwargs):
                pass

            new_method = _method
            if isinstance(method_def, str):
                methodname = method_def
            elif isinstance(method_def, dict):
                methodname = method_def['name']
                sig = method_def.get('sig')
                doc = method_def.get('doc')
                if sig:
                    _method.__signature__ = sig
                if doc:
                    _method.__doc__ = doc
            else:
                methodname = method_def.__name__
                new_method = method_def
            new_method.__name__ = methodname
            new_method.method_spec = {}
            setattr(self, methodname, new_method)

    def ping(self):
        return {'ping': 'pong'}


# TODO: fill this out. Needs type annotations on the methods
# (types should be extracted in mk_method_spec_from_openapi_method_spec and then
# used to make annotations in mk_request_function)
def mk_unit_tests(client):
    for method_name in dir(client):
        method = getattr(client, method_name)
        method_spec = getattr(method, 'method_spec')
        if not method_spec:
            continue
