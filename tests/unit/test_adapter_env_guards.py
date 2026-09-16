"""An adapter must refuse to run at all when its standard-library
environment is missing or wrong -- never produce a verdict from it.

This is not hypothetical. Re-running the worked examples on a machine
where SYSML_LIBRARY_DIR was unset, the Pilot loaded no standard library
and still answered: every fixture importing ScalarValues/Parts failed to
resolve, so models that check clean reported `violated` -- and
membership-visibility-private-rejected, which *should* be rejected, still
reported `violated` and would have been recorded `passed`, for entirely
the wrong reason. A plausible-looking false verdict is worse than a crash,
because only the crash is visible.

The guards must raise RuntimeError, not UnsupportedMethod: `svt run`
catches UnsupportedMethod and writes earl:inapplicable into the ledger
(cli.py's run_cmd), so a misconfigured environment would otherwise become
a permanent, honest-looking ledger fact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from adapters.base import TestCaseSpec, UnsupportedMethod
from adapters.pilot_implementation import ADAPTER as PILOT
from adapters.sysml_toolkit import ADAPTER as TOOLKIT

STRUCTURAL = TestCaseSpec(
    input_files=[Path("input.sysml")], method="structural-check", expected="clean"
)


@pytest.mark.parametrize(
    ("adapter", "var", "other_vars"),
    [
        (PILOT, "SYSML_LIBRARY_DIR", {"PILOT_GLUE_CLASSPATH": "/tmp/fake.jar"}),
        (TOOLKIT, "SYSMLV2_LIB_DIR", {}),
    ],
)
def test_missing_library_dir_raises_rather_than_producing_a_verdict(
    adapter, var, other_vars, monkeypatch
):
    monkeypatch.delenv(var, raising=False)
    for k, v in other_vars.items():
        monkeypatch.setenv(k, v)

    with pytest.raises(RuntimeError) as exc:
        adapter.run(STRUCTURAL)
    assert var in str(exc.value)


@pytest.mark.parametrize(
    ("adapter", "var", "other_vars"),
    [
        (PILOT, "SYSML_LIBRARY_DIR", {"PILOT_GLUE_CLASSPATH": "/tmp/fake.jar"}),
        (TOOLKIT, "SYSMLV2_LIB_DIR", {}),
    ],
)
def test_nonexistent_library_dir_raises_too(adapter, var, other_vars, monkeypatch, tmp_path):
    """A typo'd path fails exactly as silently as an unset one -- the tool
    loads nothing and answers anyway -- so presence alone is not enough."""
    monkeypatch.setenv(var, str(tmp_path / "does-not-exist"))
    for k, v in other_vars.items():
        monkeypatch.setenv(k, v)

    with pytest.raises(RuntimeError) as exc:
        adapter.run(STRUCTURAL)
    assert "not a directory" in str(exc.value)


def test_the_guard_is_not_an_unsupportedmethod(monkeypatch):
    """Guard against the regression that would quietly undo all of this:
    UnsupportedMethod is caught by `svt run` and recorded as
    earl:inapplicable, so raising it here would turn a broken environment
    into ledger evidence."""
    monkeypatch.delenv("SYSML_LIBRARY_DIR", raising=False)
    monkeypatch.setenv("PILOT_GLUE_CLASSPATH", "/tmp/fake.jar")

    with pytest.raises(RuntimeError) as exc:
        PILOT.run(STRUCTURAL)
    assert not isinstance(exc.value, UnsupportedMethod)
