import argh
import os
import shutil
import tempfile
from http2py.client import HttpClient
from datetime import datetime, timezone
from setuptools import sandbox

OUTPUT_DIR = os.path.join(os.environ['HOME'], 'http2py', 'api_pkgs')

INIT_FILE_TPL = '''from .funcs import {funcs}
'''

FUNCS_FILE_TPL = '''from i2 import Sig
from http2py.client import HttpClient

api = HttpClient(openapi_spec={openapi_spec}, url={openapi_url})


def apply_sig(meth):
    def wrapper(func):
        sig = Sig(meth) - 'self'
        return sig(func)
    return wrapper
{funcs}'''

FUNC_TPL = '''

@apply_sig(api.{func_name})
def {func_name}(*args, **kwargs):
    return api.{func_name}(*args, **kwargs)
'''

SETUP_PY = '''from setuptools import setup

setup()
'''

SETUP_CFG_TPL = '''[metadata]
name = {name}
version = {version}
platforms = any
description = {description}
author = {author}
license = {license}

[options]
packages = find:
include_package_data = True
zip_safe = False
install_requires =
    i2
    http2py
'''


def mk_api_pkg(
    openapi_spec: dict = None,
    openapi_url: str = None,
    pkg_name: str = None,
    pkg_version: str = None,
    pkg_description: str = None,
    pkg_author: str = None,
    pkg_license: str = None,
):
    """
    Build a pip installable package containing the functions to consume a running
    webservice application executed with py2http.

    :param openapi_spec: The openapi specification for the webservice.
    :type openapi_spec: dict, optional
    :param openapi_url: The url to fetch the openapi specification for the webservice.
    :type openapi_url: str, optional
    :param pkg_name: The name of the package. If no name is provided, default to
    'apipkg{timestamp}'
    :type pkg_name: str, optional
    :param pkg_version: The version number of the package. If no version is provided,
    default to 1.0.0
    :type pkg_version: str, optional
    :param pkg_description: The description of the package.
    :type pkg_description: str, optional
    :param pkg_author: The author of the package. If no author provided, default to
    'API Package Maker'
    :type pkg_author: str, optional
    :param pkg_license: The license for the package. If no license provided, default
    to 'Apache'
    :type pkg_license: str, optional
    """

    def mk_str_element(value: str):
        return value if value is None else f"'{value}'"

    def mk_pkg_name():
        dt = datetime.now(timezone.utc)
        utc_time = dt.replace(tzinfo=timezone.utc)
        utc_timestamp = int(utc_time.timestamp())
        return f'apipkg{utc_timestamp}'

    def create_file(filepath, content):
        with open(filepath, 'w') as file:
            print(content, file=file)

    tempdir = tempfile.mkdtemp()
    try:
        api = HttpClient(openapi_spec=openapi_spec, url=openapi_url)
        paths_spec = api.openapi_spec.get('paths')
        if not paths_spec:
            raise RuntimeError('The API is empty')
        func_names = [path[1:] for path in paths_spec]
        funcs_code = [FUNC_TPL.format(func_name=func_name) for func_name in func_names]
        funcs_file_code = FUNCS_FILE_TPL.format(
            openapi_spec=mk_str_element(openapi_spec),
            openapi_url=mk_str_element(openapi_url),
            funcs=''.join(funcs_code),
        )
        init_file_code = INIT_FILE_TPL.format(funcs=', '.join(func_names))
        pkg_name = pkg_name or mk_pkg_name()
        module_dir = os.path.join(tempdir, pkg_name)
        os.makedirs(module_dir)
        create_file(
            filepath=os.path.join(module_dir, f'__init__.py'), content=init_file_code
        )
        create_file(
            filepath=os.path.join(module_dir, f'funcs.py'), content=funcs_file_code
        )
        server_url = api.openapi_spec['servers'][0]['url']
        pkg_version = pkg_version or '1.0.0'
        setup_cfg_content = SETUP_CFG_TPL.format(
            name=pkg_name,
            version=pkg_version,
            description=pkg_description
            or f'A client API to consume the webservices exposed at {server_url}',
            author=pkg_author or 'API Package Maker',
            license=pkg_license or 'Apache',
        )
        create_file(
            filepath=os.path.join(tempdir, f'setup.cfg'), content=setup_cfg_content
        )
        create_file(filepath=os.path.join(tempdir, f'setup.py'), content=SETUP_PY)
        os.chdir(tempdir)
        sandbox.run_setup('setup.py', ['sdist'])
        pkg_filename = f'{pkg_name}-{pkg_version}.tar.gz'
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        shutil.copy(src=os.path.join(tempdir, 'dist', pkg_filename), dst=OUTPUT_DIR)

        return os.path.join(OUTPUT_DIR, pkg_filename)

    finally:
        shutil.rmtree(tempdir)


def main():
    argh.dispatch_command(mk_api_pkg)


if __name__ == '__main__':
    main()
