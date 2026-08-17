"""Pytest configuration for the http2py repository.

``http2py.api_pkg_maker`` imports ``setuptools.sandbox``, which modern
setuptools no longer ships, so merely *importing* the module raises
``ImportError``. Under ``--doctest-modules`` that is not a single failing test:
it aborts collection for the whole session. The module is deliberately left in
place (whether to rewrite it or remove it is still open on issue #14), so it is
excluded from collection instead.

CI excludes the same two paths via ``[tool.wads.ci.testing].exclude_paths`` in
pyproject.toml, which the wads ``run-tests-uv`` action turns into ``--ignore``
flags. Repeating them here is what makes a bare ``pytest`` (no flags, e.g. a
local run or an editor's test runner) behave the same way as CI.
``tests/test_ci_collection_contract.py`` asserts the two lists stay in
agreement, so they cannot drift apart silently.
"""

collect_ignore = [
    "http2py/api_pkg_maker.py",
    "http2py/tests",
]
