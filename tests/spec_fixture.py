"""One OpenAPI spec exercising every argument shape ``mk_cli`` has to handle.

Path parameters (required, and typed), query parameters (optional, with and
without a schema default), a JSON request body with a ``required`` list, an
``apiKey`` security scheme (which adds an ``api_key`` CLI argument), and a route
with no arguments at all (which yields a ``*args``/``**kwargs`` signature).

Kept as a module rather than inline so the golden recorder and the tests are
provably looking at the same spec.
"""

CONTENT = "application/json"

SPEC = {
    "openapi": "3.0.2",
    "info": {"title": "example", "version": "0.1"},
    "servers": [{"url": "https://example.com"}],
    "security": {"apiKey": {}},
    "paths": {
        "/u/{uid}/p/{pid}": {
            "get": {
                "x-method_name": "get_thing",
                "description": "Two path args and two query args.",
                "parameters": [
                    {
                        "name": "uid",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "pid",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "integer"},
                    },
                    {
                        "name": "verbose",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "boolean"},
                    },
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer", "default": 10},
                    },
                ],
                "responses": {
                    "200": {"description": "", "content": {CONTENT: {"schema": {}}}}
                },
            }
        },
        "/make": {
            "post": {
                "x-method_name": "make",
                "description": "A request body with one required property.",
                "requestBody": {
                    "content": {
                        CONTENT: {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "count": {"type": "integer"},
                                    "flag": {"type": "boolean"},
                                },
                                "required": ["name"],
                            }
                        }
                    }
                },
                "responses": {
                    "200": {"description": "", "content": {CONTENT: {"schema": {}}}}
                },
            }
        },
        "/plain": {
            "get": {
                "x-method_name": "plain",
                "description": "No arguments at all.",
                "responses": {
                    "200": {"description": "", "content": {CONTENT: {"schema": {}}}}
                },
            }
        },
    },
}
