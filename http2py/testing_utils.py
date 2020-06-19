TEST_NUMBER = 100
TEST_STRING = 'test'


# TODO: fill this out. Needs type annotations on the methods
# (types should be extracted in mk_method_spec_from_openapi_method_spec and then
# used to make annotations in mk_request_function)
def mk_unit_tests(client):
    for method_name in dir(client):
        method = getattr(client, method_name)
        method_spec = getattr(method, 'method_spec')
        if not method_spec:
            continue
