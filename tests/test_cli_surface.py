"""Pin ``mk_cli``'s generated command line against what argh produced.

``http2py.cli_maker`` builds a CLI out of an OpenAPI spec. The golden in
``tests/cli_goldens/mk_cli.json`` records the ``usage:`` line argh produced for
every command of ``tests/spec_fixture.SPEC``, recorded through
``ArghParser().add_commands(...)`` -- exactly the call ``mk_cli`` used to make --
before the migration to ``cw``.

Only usage lines are asserted, not full ``--help`` bodies: CPython rewrites the
option column between versions and CI spans 3.10 and 3.12. The full-body diff
(zero differences across all four surfaces) was done at migration time and is
recorded in the pull request.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

import cw

sys.path.insert(0, str(Path(__file__).parent))

from spec_fixture import SPEC  # noqa: E402

GOLDEN = json.loads(
    (Path(__file__).parent / "cli_goldens" / "mk_cli.json").read_text(encoding="utf-8")
)
EXPECTED = GOLDEN["usages"]


def _usages(parser):
    """``{command_name: normalised usage line}``, plus ``__top__`` for the parser."""
    out = {"__top__": " ".join(parser.format_usage().split())}
    for action in parser._actions:
        if getattr(action, "choices", None):
            for name, sub in action.choices.items():
                out[name] = " ".join(sub.format_usage().split())
    return out


def _parser(**kwargs):
    from http2py.cli_maker import mk_cli

    return mk_cli(openapi_spec=SPEC, **kwargs)


def test_mk_cli_returns_a_parser_with_one_command_per_route():
    parser = _parser()
    assert set(_usages(parser)) == {"__top__", "get-thing", "make", "plain"}


@pytest.mark.parametrize("command", sorted(EXPECTED))
def test_usage_matches_the_argh_recording(command):
    """Every command's grammar is byte-identical to what argh generated.

    The recorded golden used ``prog="PROG"``; a parser built during a test run
    derives its prog from ``sys.argv[0]``. Only what follows the prog is
    compared, so both sides drop ``usage:`` plus the prog tokens.
    """
    actual = _usages(_parser())
    offset = 1 if command == "__top__" else 2  # subparser progs are two tokens
    assert actual[command].split()[1 + offset :] == EXPECTED[command].split()[
        1 + offset :
    ], f"{command}: {actual[command]!r} != {EXPECTED[command]!r}"


def test_required_api_arguments_are_options_not_positionals():
    """The load-bearing consequence of ``CLI_CONVENTION``.

    Every function ``register_cli_method`` builds is all-keyword-only, so a
    required argument like ``uid`` must be spelled ``-u UID`` / ``--uid UID``.
    Under cw's ARGH default it would become a bare positional and every caller's
    command line would silently change.
    """
    usage = _usages(_parser())["get-thing"]
    assert "-u UID" in usage and "-p PID" in usage
    assert " uid" not in usage and " pid" not in usage


def test_the_convention_is_load_bearing_and_this_test_can_fail():
    """Prove the check above would catch losing ``naming=BY_NAME_IF_KWONLY``.

    If this stops holding, cw's default naming has become equivalent for this
    signature shape and ``CLI_CONVENTION``'s comment is stale -- not the other
    way round.
    """
    from http2py.cli_maker import CLI_CONVENTION, register_cli_method
    from http2py.client import HttpClient

    client = HttpClient(SPEC)
    methods = [
        register_cli_method(SPEC, m, ["api_key"])
        for _, m in client.__dict__.items()
        if getattr(m, "method_spec", None)
    ]
    default = cw.mk_parser(
        methods,
        convention=dataclasses.replace(CLI_CONVENTION, naming=cw.ARGH.naming),
        prog="PROG",
    )
    usage = _usages(default)["get-thing"]
    assert "-u UID" not in usage, (
        "cw's default naming was expected to turn the required keyword-only "
        f"arguments into positionals, but produced {usage!r}"
    )


def test_every_parameter_register_cli_method_builds_is_keyword_only():
    """The premise ``CLI_CONVENTION`` rests on, asserted rather than assumed.

    ``BY_NAME_IF_KWONLY`` reproduces argh's legacy grammar *because* these
    signatures are all keyword-only. If a future change introduced an ordinary
    positional parameter, the two policies would diverge for it and the golden
    above is what would catch it -- but this says so directly.
    """
    import inspect

    from http2py.cli_maker import register_cli_method
    from http2py.client import HttpClient

    client = HttpClient(SPEC)
    for _, method in client.__dict__.items():
        if not getattr(method, "method_spec", None):
            continue
        func = register_cli_method(SPEC, method, ["api_key"])
        for param in inspect.signature(func).parameters.values():
            assert param.kind in (
                param.KEYWORD_ONLY,
                param.VAR_POSITIONAL,
                param.VAR_KEYWORD,
            ), f"{func.__name__}.{param.name} is {param.kind}"


def test_dispatch_cli_raises_SystemExit_on_a_command_line_error():
    """``cw.run`` RETURNS the exit code; ``dispatch_cli`` must still raise it.

    argh's ``parser.dispatch()`` exited the process on a bad command line.
    Without the re-raise, a broken invocation would look like success.
    """
    from http2py.cli_maker import dispatch_cli

    argv = sys.argv
    sys.argv = ["PROG", "no-such-command"]
    try:
        with pytest.raises(SystemExit) as excinfo:
            dispatch_cli(openapi_spec=SPEC)
        assert excinfo.value.code == 2
    finally:
        sys.argv = argv


def test_the_package_no_longer_imports_argh():
    """http2py no longer declares argh; nothing may import it."""
    import subprocess

    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, http2py, http2py.cli_maker, http2py.api_pkg_maker; "
            "sys.exit(1 if 'argh' in sys.modules else 0)",
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, f"argh was imported: {proc.stderr}"
