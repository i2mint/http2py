import pytest
from plunk.tw.py2py_front_example.simple_pycode import foo, bar, confuser
from py2http import run_app
from py2http.util import run_process


@pytest.fixture(scope='session', autouse=True)
def ws_app():
    with run_process(
        func=run_app,
        func_kwargs=dict(
            app_obj=[foo, bar, confuser],
            publish_openapi=True
        ),
        is_ready=3
    ) as proc:
        yield proc
