"""Fixtures for the live-service tests in this directory.

These tests stand up a real ``py2http`` web service and talk to it, so
``py2http`` is a test-only requirement (see ``test_requirements.txt``) and is
*not* one of http2py's declared dependencies.

It is imported inside the fixture rather than at module level on purpose:
pytest eagerly imports the ``conftest.py`` of any ``test*`` sub-directory of a
collection root, and it does so *before* ``--ignore`` is applied. A module-level
``from py2http import run_app`` therefore aborted the entire session with
"ImportError while loading conftest" on any machine (CI included) that has no
py2http installed -- even though this directory is excluded from collection.
"""

import pytest


def foo(a: int = 0, b: int = 0, c=0):
    """This is foo. It computes something"""
    return (a * b) + c


def bar(x, greeting="hello"):
    """bar greets its input"""
    return f"{greeting} {x}"


def confuser(a: int = 0, x: float = 3.14):
    return (a**2) * x


@pytest.fixture(scope="session", autouse=True)
def ws_app():
    from py2http import run_app
    from py2http.util import run_process

    with run_process(
        func=run_app,
        func_kwargs=dict(
            app_obj=[foo, bar, confuser], publish_openapi=True, server="wsgiref"
        ),
        is_ready=3,
    ) as proc:
        yield proc
