import pytest
from py2http import run_app
from py2http.util import run_process


def foo(a: int = 0, b: int = 0, c=0):
    """This is foo. It computes something"""
    return (a * b) + c


def bar(x, greeting='hello'):
    """bar greets its input"""
    return f'{greeting} {x}'


def confuser(a: int = 0, x: float = 3.14):
    return (a ** 2) * x


@pytest.fixture(scope='session', autouse=True)
def ws_app():

    with run_process(
        func=run_app,
        func_kwargs=dict(app_obj=[foo, bar, confuser], publish_openapi=True),
        is_ready=3,
    ) as proc:
        yield proc
