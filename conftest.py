"""Pytest configuration for the http2py repository.

``http2py/tests`` stands up a real ``py2http`` web service, so it depends on a
test-only package that is not one of http2py's declared dependencies. Under
``--doctest-modules`` an unimportable module is not a single failing test: it
aborts collection for the whole session. So that directory is excluded here.

CI excludes the same path via ``[tool.wads.ci.testing].exclude_paths`` in
pyproject.toml, which the wads ``run-tests-uv`` action turns into ``--ignore``
flags. Repeating it here is what makes a bare ``pytest`` (no flags, e.g. a local
run or an editor's test runner) behave the same way as CI.
``tests/test_ci_collection_contract.py`` asserts the two lists stay in
agreement, so they cannot drift apart silently.
"""

collect_ignore = [
    "http2py/tests",
]
