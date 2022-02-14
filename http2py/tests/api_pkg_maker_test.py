import os
import re
import pytest
from http2py.api_pkg_maker import OUTPUT_DIR, mk_api_pkg


@pytest.mark.parametrize(
    'openapi_spec, openapi_url, pkg_name, pkg_version, pkg_description, pkg_author, pkg_license',
    [
        (
            {
                'openapi': '3.0.2',
                'info': {'title': 'default', 'version': '0.1'},
                'servers': [{'url': 'http://localhost:3030'}],
                'paths': {
                    '/foo': {
                        'post': {
                            'x-method_name': 'foo',
                            'description': 'This is foo. It computes something',
                            'requestBody': {
                                'required': True,
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'properties': {
                                                'a': {'type': 'integer', 'default': 0},
                                                'b': {'type': 'integer', 'default': 0},
                                                'c': {'type': 'integer', 'default': 0},
                                            },
                                        }
                                    }
                                },
                            },
                            'responses': {
                                '200': {
                                    'description': '',
                                    'content': {'application/json': {'schema': {}}},
                                }
                            },
                        }
                    },
                    '/bar': {
                        'post': {
                            'x-method_name': 'bar',
                            'description': 'bar greets its input',
                            'requestBody': {
                                'required': True,
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'properties': {
                                                'x': {'type': '{}'},
                                                'greeting': {
                                                    'type': 'string',
                                                    'default': 'hello',
                                                },
                                            },
                                            'required': ['x'],
                                        }
                                    }
                                },
                            },
                            'responses': {
                                '200': {
                                    'description': '',
                                    'content': {'application/json': {'schema': {}}},
                                }
                            },
                        }
                    },
                    '/confuser': {
                        'post': {
                            'x-method_name': 'confuser',
                            'description': '',
                            'requestBody': {
                                'required': True,
                                'content': {
                                    'application/json': {
                                        'schema': {
                                            'type': 'object',
                                            'properties': {
                                                'a': {'type': 'integer', 'default': 0},
                                                'x': {
                                                    'type': 'number',
                                                    'format': 'float',
                                                    'default': 3.14,
                                                },
                                            },
                                        }
                                    }
                                },
                            },
                            'responses': {
                                '200': {
                                    'description': '',
                                    'content': {'application/json': {'schema': {}}},
                                }
                            },
                        }
                    },
                },
            },
            None,
            None,
            None,
            None,
            None,
            None,
        ),
        (None, 'http://127.0.0.1:3030/openapi', None, None, None, None, None,),
        (
            None,
            'http://127.0.0.1:3030/openapi',
            'myapi',
            '1.2.3',
            'Some packages description.',
            'John Doe',
            'MIT',
        ),
    ],
)
def test_mk_api_pkg(
    openapi_spec,
    openapi_url,
    pkg_name,
    pkg_version,
    pkg_description,
    pkg_author,
    pkg_license,
):
    output_pkg_filepath = mk_api_pkg(
        openapi_spec,
        openapi_url,
        pkg_name,
        pkg_version,
        pkg_description,
        pkg_author,
        pkg_license,
    )
    output_pkg_dirpath = os.path.dirname(output_pkg_filepath)
    assert output_pkg_dirpath == OUTPUT_DIR
    output_pkg_filename = os.path.basename(output_pkg_filepath)
    output_pkg_name = re.search(r'(.+?)-', output_pkg_filename).group(1)
    if pkg_name:
        assert output_pkg_name == pkg_name
    else:
        assert bool(re.compile(r'apipkg[0-9]*').match(output_pkg_name))
    output_pkg_version = re.search(r'.*-(.+?)\.tar\.gz', output_pkg_filename).group(1)
    assert output_pkg_version == (pkg_version or '1.0.0')
    os.remove(output_pkg_filepath)
