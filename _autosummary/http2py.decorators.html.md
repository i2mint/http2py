# http2py.decorators

Response handling: map http status codes to exceptions, decode the payload.

`handle_json_resp` / `handle_binary_resp` / `handle_raw_resp` wrap an
output transformation so it only ever sees a successful response of the
expected content type.

Binary (`application/octet-stream`) responses are never unpickled unless asked:
unpickling runs code chosen by whoever produced the bytes, so a spoofed or
compromised server could run code on the client. Pass `loads=` to
`handle_binary_resp` (or `binary_loads=` to `mk_request_function` /
`HttpClient`): `bytes` for the raw content, a decoder of your own, or
`unsafe_pickle_loads` if (and only if) the server is fully trusted.

```pycon
>>> class Resp:
...     status_code, content = 200, b'raw bytes'
>>> handle_binary_resp(lambda x: x, loads=bytes)(Resp())
b'raw bytes'
>>> handle_binary_resp(lambda x: x)(Resp())
Traceback (most recent call last):
  ...
http2py.decorators.BinaryResponseNotDecoded: Got a binary response but no loads=... to decode it. ...
```

### Functions

| [`check_loads`](#http2py.decorators.check_loads)(loads)        | Validate a `loads=` / `binary_loads=` argument: `None` or a callable.   |
|----------------------------------------------------------------------------|-------------------------------------------------------------------------|
| [`unsafe_pickle_loads`](#http2py.decorators.unsafe_pickle_loads)(data) | Unpickle `data`.                                                        |

### Exceptions

| [`BinaryResponseNotDecoded`](#http2py.decorators.BinaryResponseNotDecoded)   | A binary response arrived, but no `loads` was given to decode it.   |
|-----------------------------------------------------------------------------|---------------------------------------------------------------------|

### *exception* http2py.decorators.BinaryResponseNotDecoded

Bases: [`ValueError`](https://docs.python.org/3/builtins/exceptions.html#ValueError)

A binary response arrived, but no `loads` was given to decode it.

### http2py.decorators.check_loads(loads)

Validate a `loads=` / `binary_loads=` argument: `None` or a callable.

`pickle.loads` itself gets a warning suggesting `unsafe_pickle_loads`.
That is advice, not a guard: any other callable (a `partial` of
`pickle.loads`, `dill.loads`, …) is trusted as given.

* **Return type:**
  [`None`](https://docs.python.org/3/builtins/constants.html#None)

### http2py.decorators.unsafe_pickle_loads(data)

Unpickle `data`. UNSAFE on anything an untrusted server can send.

Unpickling runs code chosen by whoever produced the bytes, so use this only
when the server (and the network path to it) is fully trusted. It exists so
that opting into pickled responses is explicit and visible at the call site:

```default
HttpClient(spec, binary_loads=unsafe_pickle_loads)
```

* **Return type:**
  [`Any`](https://docs.python.org/3/library/typing.html#typing.Any)
