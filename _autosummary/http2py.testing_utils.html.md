# http2py.testing_utils

Helpers for testing code that talks to an http service.

[`MockHttpClient`](#http2py.testing_utils.MockHttpClient) answers without touching the network, and
`mk_unit_tests()` generates test stubs from a client’s bound methods.

### Functions

| `mk_unit_tests`(client)   |    |
|---------------------------|----|

### Classes

| [`MockHttpClient`](#http2py.testing_utils.MockHttpClient)([openapi_spec, ...])   |    |
|----------------------------------------------------------------------------------------|----|

### *class* http2py.testing_utils.MockHttpClient(openapi_spec=None, session_state=None, url=None, \*\*auth_kwargs)

Bases: [`HttpClient`](http2py.client.html.md#http2py.client.HttpClient)
