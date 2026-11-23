# http2py.authentication

Resolve credentials and build the auth callables that requests will use.

`mk_auth()` turns an auth specification – inline values, environment
variables, or a JSON credentials file – into something the request layer can
attach to outgoing calls.

### Functions

| `mk_auth`(auth_kwargs, expected_auth_kwargs[, ...])   |    |
|-------------------------------------------------------|----|
