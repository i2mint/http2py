import argh
from functools import wraps
from glom import glom
from inspect import signature
import json
import os
from pathlib import Path
import requests
from typing import Callable, Iterable
import yaml

from i2.io_trans import JSONAnnotAndDfltIoTrans
from i2.signatures import set_signature_of_func, Sig, KO
from http2py import HttpClient
from http2py.authentication import mk_auth, DFLT_CONFIG_FILENAME

def mk_sig_argparse_friendly(sig):
    """Modifies a signature to change all leading underscores in param names
    to trailing underscores, to ensure compatibility with argparse"""
    for argname, argspec in sig.parameters.items():
        if argname.startswith('_'):
            argname = argname[1:] + '_'
            argspec = argspec.replace(name=argname)
            assert argname not in sig.names, f"{argname} was already in {sig.names}"
        yield argname, argspec


def mk_argparse_friendly(func):
    """Wraps a function to expose a signature that is compatible with argparse by stripping leading
    underscores from all keyword arguments, but does not mutate the signature of the original function"""
    orig_sig = Sig(func)
    new_params = dict(mk_sig_argparse_friendly(orig_sig))
    new_sig = orig_sig.replace(parameters=new_params, return_annotation=orig_sig.return_annotation)
    @wraps(func)
    def _func(*args, **kwargs):
        mapped_kwargs = {}
        for argname, argvalue in kwargs.items():
            if argname not in [param.name for param in orig_sig.params]:
                mapped_argname = '_' + argname[:-1]
            else:
                mapped_argname = argname
            mapped_kwargs[mapped_argname] = argvalue
        # convert strings into correct JSON types
        io_trans = JSONAnnotAndDfltIoTrans()
        return io_trans(func)(*args, **mapped_kwargs)
    return new_sig(_func)



def mk_cli(openapi_spec: dict = '',
           url: str = '',
           filename: str = '',
           parse_yaml: bool = False,
           config_filename: str = DFLT_CONFIG_FILENAME,
           profile: str = ''):
    """Creates a CLI parser that exposes all of the methods of an HTTP client defined by an OpenAPI spec.
    Accepts either an OpenAPI spec dict, a url, or path to a local file.

    :param openapi_spec: An OpenAPI service specification
    :param url: A URL for an OpenAPI spec that can be accessed with an HTTP GET request
    :param filename: The path to a local file that contains an OpenAPI spec
    :param parse_yaml: A flag to indicate that the provided OpenAPI spec is in YAML format rather than JSON (default: False)
    :param config_filename: The path to a local config file that contains authentication details for the HTTP service
        in JSON format (default: ~/.http2cli/credentials.json
    """
    if not openapi_spec:
        if url:
            raw_spec = requests.get(url).text
        elif filename:
            with open(filename) as fp:
                raw_spec = fp.read()
        else:
            raise ValueError('You must provide an OpenAPI spec dict, url, or filename.')
        if raw_spec:
            if parse_yaml:
                openapi_spec = yaml.safe_load(raw_spec)
            else:
                openapi_spec = json.loads(raw_spec)
        else:
            raise ValueError('No valid OpenAPI spec found.')
    security = openapi_spec.get('security', None)
    expected_auth_kwargs = []
    if security:
        auth_type = list(security.keys())[0]
        if auth_type == 'apiKey':
            expected_auth_kwargs = ['api_key']
        elif auth_type == 'bearerAuth':
            login_details = glom(openapi_spec, 'components.securitySchemes.bearerAuth.x-login', default={})
            expected_auth_kwargs = login_details.get('login_inputs', [])
    client_details = HttpClient(openapi_spec)
    cli_methods = [register_cli_method(openapi_spec, method, expected_auth_kwargs)
                   for methodname, method in client_details.__dict__.items() if getattr(method, 'method_spec', None)]
    parser = argh.ArghParser()
    parser.add_commands(cli_methods)
    return parser


def dispatch_cli(*args, **kwargs):
    """Makes a CLI parser with mk_cli and then dispatches it (see documentation of mk_cli)"""
    parser = mk_cli(*args, **kwargs)
    parser.dispatch()

set_signature_of_func(dispatch_cli, signature(mk_cli))

def register_cli_method(
        openapi_spec: dict,
        client_method: Callable,
        expected_auth_kwargs: Iterable[str] = None,
        config_filename: str = DFLT_CONFIG_FILENAME,
        profile: str = ''):
    """Creates a CLI-friendly function to instantiate an HttpClient with appropriate authentication
    arguments and call a particular method of the client instance

    :param openapi_spec: The OpenAPI spec used to make the client
    :param client_method: The instance method to wrap
    :param expected_auth_kwargs: A list of authentication kwargs that the CLI should ask for
        (defaults to empty list)
    :param config_filename: The path to a JSON file to read for authentication kwargs
        (defaults to ~/.http2py/credentials.json)
    """
    methodname = client_method.__name__
    method_sig = Sig(client_method)
    if not expected_auth_kwargs:
        expected_auth_kwargs = []
    method_sig = method_sig.merge_with_sig([
        *[{'name': kwarg, 'kind': KO, 'default': ''} for kwarg in expected_auth_kwargs],
          {'name': 'config', 'kind': KO, 'default': config_filename}])
    def cli_method(*args, **kwargs):
        config_filename = kwargs.pop('config')
        auth_kwargs = {key: kwargs.pop(key) for key in expected_auth_kwargs}
        auth_kwargs = mk_auth(auth_kwargs, expected_auth_kwargs, config_filename, profile)
        http_client = HttpClient(openapi_spec, **auth_kwargs)
        return getattr(http_client, methodname)(**kwargs)
    method_sig.wrap(cli_method)
    cli_method.__name__ = methodname
    return mk_argparse_friendly(cli_method)
