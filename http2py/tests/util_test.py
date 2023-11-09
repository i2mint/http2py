"""Test the util module."""

import yaml
import pytest
from http2py.util import files, get_routes, Routes

test_data_path = files / 'tests' / 'test_data'
simple_openapi_spec_path = test_data_path / 'simple_openapi_spec.yaml'


def _openapi_spec():
    return yaml.safe_load(simple_openapi_spec_path.read_text())


@pytest.fixture
def openapi_spec():
    return _openapi_spec()


def test_get_routes(openapi_spec):
    result = list(get_routes(openapi_spec))
    assert result == [('get', '/items'), ('post', '/items')]

    result = list(get_routes(openapi_spec, include_methods='get'))
    assert result == [('get', '/items')]

    result = list(get_routes(openapi_spec, include_methods='post'))
    assert result == [('post', '/items')]

    result = list(get_routes(openapi_spec, include_methods='put'))
    assert result == []


def test_routes(openapi_spec):
    routes = Routes(openapi_spec)
    assert list(routes) == [('get', '/items'), ('post', '/items')]

    get_route = routes['get', '/items']

    assert get_route.input_specs == {
        'parameters': [
            {
                'in': 'query',
                'name': 'type',
                'schema': {'type': 'string'},
                'required': True,
                'description': 'Type of items to list',
            },
            {
                'in': 'query',
                'name': 'limit',
                'schema': {'type': 'integer', 'default': 10},
                'required': False,
                'description': 'Maximum number of items to return',
            },
        ],
        'requestBody': {},
    }

    assert get_route.output_specs == {
        '200': {
            'description': 'An array of items',
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'active': {'type': 'boolean'},
                            },
                        },
                    }
                }
            },
        }
    }

    assert get_route.parameters == [
        {
            'in': 'query',
            'name': 'type',
            'schema': {'type': 'string'},
            'required': True,
            'description': 'Type of items to list',
        },
        {
            'in': 'query',
            'name': 'limit',
            'schema': {'type': 'integer', 'default': 10},
            'required': False,
            'description': 'Maximum number of items to return',
        },
    ]

    post_route = routes['post', '/items']

    assert post_route.input_specs == {
        'parameters': [],
        'requestBody': {
            'required': True,
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'age': {'type': 'integer', 'default': 42},
                        },
                    }
                }
            },
        },
    }

    assert post_route.output_specs == {
        '201': {
            'description': 'Item created',
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'id': {
                                'type': 'integer',
                                'description': 'Unique identifier of the created item',
                            }
                        },
                    }
                }
            },
        }
    }

    assert post_route.parameters == [
        {'in': 'body', 'name': 'name', 'schema': {'type': 'string'}},
        {'in': 'body', 'name': 'age', 'schema': {'type': 'integer', 'default': 42}},
    ]
