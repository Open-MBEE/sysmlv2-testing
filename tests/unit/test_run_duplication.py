"""Re-running a test must not duplicate it.

`svt run` used to write a new TestRun unconditionally, so re-running one
appended a record identical in every evidentiary respect but its
timestamp. The ledger carried such a pair until it was removed by hand.
This pins every row of the decision table that replaced that behaviour:

  same digest, same result, same party      -> svt:reconfirmedAt timestamp
  same digest, same result, different party -> svt:Reproduction
  same digest, different result             -> a new TestRun, with a warning
  different digest                          -> a new TestRun

Exercised through the real CLI against an isolated ledger, with the stub
adapter standing in for a pinned binary (as test_run_success.py does).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import RDF
from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import ids
from sysmlv2_testing.graph import load_full_ledger
from sysmlv2_testing.namespaces import EARL, SVT

runner = CliRunner()

TESTCASE = "dup-testcase"


def _ok(result):
    assert result.exit_code == 0, result.output
    return result


@pytest.fixture()
def ready(isolated_ledger, tmp_path: Path, monkeypatch):
    """An isolated ledger with one validated, grounded, runnable TestCase
    and the stub adapter wired in -- the state `svt run` needs."""
    implementation = isolated_ledger["implementation"]
    monkeypatch.setitem(cli_module.ADAPTER_MODULES, implementation, "_stub_adapter")

    _ok(runner.invoke(cli_module.app, [
        "document", "add", "--id", "fake-doc", "--doc-number", "fake/0000",
        "--title", "Fake Spec", "--local-path", "sources/local/fake.pdf",
        "--sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"]))
    _ok(runner.invoke(cli_module.app, [
        "citation", "add", "--id", "fake-citation", "--document", "fake-doc",
        "--section", "1", "--page", "1", "--quote", "a thing must be a thing"]))

    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")
    _ok(runner.invoke(cli_module.app, [
        "testcase", "add", "--id", TESTCASE,
        "--description", "a fake requirement, written prospectively",
        "--intent", isolated_ledger["intent"], "--input-file", str(src),
        "--method", "structural-check", "--expected", "clean",
        "--grounds", "fake-citation"]))
    _ok(runner.invoke(cli_module.app, [
        "testcase", "validate", "--id", TESTCASE, "--by", "Test Human"]))
    return {**isolated_ledger, "src": src}


def _run(ready, party=None):
    args = ["run", "--testcase", TESTCASE,
            "--implementation", ready["implementation"], "--version", ready["version"]]
    if party is not None:
        args += ["--as", party]
    return runner.invoke(cli_module.app, args)


def _counts():
    """(TestRuns, Reproductions) for TESTCASE only -- isolated_ledger seeds
    its own unrelated TestRun, so a whole-ledger count would start at 1."""
    g = load_full_ledger()
    tc = ids.slug_id("testcase", TESTCASE)
    runs = [r for r in g.subjects(EARL.test, tc) if (r, RDF.type, SVT.TestRun) in g]
    reps = [
        rep
        for rep in g.subjects(RDF.type, SVT.Reproduction)
        if g.value(rep, SVT.concernsRun) in runs
    ]
    return len(runs), len(reps)


def _my_run(g):
    runs = [r for r in g.subjects(EARL.test, ids.slug_id("testcase", TESTCASE))
            if (r, RDF.type, SVT.TestRun) in g]
    assert len(runs) == 1, runs
    return runs[0]


def test_first_run_writes_a_testrun(ready):
    _ok(_run(ready))
    assert _counts() == (1, 0)


def test_same_party_rerun_reconfirms_instead_of_duplicating(ready):
    _ok(_run(ready))
    result = _ok(_run(ready))

    assert "reconfirmed" in result.output
    assert _counts() == (1, 0), "a re-run that agrees must not create a second TestRun"

    g = load_full_ledger()
    assert len(list(g.objects(_my_run(g), SVT.reconfirmedAt))) == 1


def test_unattributed_runs_count_as_the_same_party(ready):
    """Absence of a Party is itself a value, not a wildcard -- otherwise
    every re-run on an unattributed legacy run would look independent."""
    _ok(_run(ready))
    _ok(_run(ready))
    assert _counts() == (1, 0)


def test_different_party_same_result_writes_a_reproduction(ready):
    _ok(runner.invoke(cli_module.app, [
        "party", "add", "--id", "machine-b", "--label", "machine B"]))
    _ok(_run(ready))
    result = _ok(_run(ready, party="machine-b"))

    assert "reproduced" in result.output
    assert _counts() == (1, 1), "an independent confirmation is a Reproduction, not a TestRun"

    g = load_full_ledger()
    rep = next(iter(g.subjects(RDF.type, SVT.Reproduction)))
    assert g.value(rep, SVT.concernsRun) == _my_run(g)
    assert g.value(rep, SVT.ranBy) == ids.slug_id("party", "machine-b")
    # It carries its own evidence, which is what makes the match checkable.
    assert g.value(rep, SVT.hasInvocation) is not None
    assert g.value(rep, EARL.result) is not None


def test_divergent_rerun_writes_a_second_testrun_and_warns(ready, monkeypatch):
    """A contradiction over identical inputs is real evidence -- possibly
    nondeterminism, possibly a broken environment -- so it is recorded,
    nothing is retracted, and it must not pass silently."""
    import _stub_adapter
    from adapters.base import RawResult

    _ok(_run(ready))

    monkeypatch.setattr(
        _stub_adapter.ADAPTER, "run",
        lambda spec: RawResult(command="fake-tool check input.sysml",
                               exit_code=1, stdout="violated", stderr=""),
    )
    result = _run(ready)
    assert result.exit_code == 0, result.output
    assert "WARNING" in result.output and "contradicts" in result.output
    assert _counts() == (2, 0), "a differing result is new evidence and gets its own TestRun"


def test_changed_inputs_write_a_second_testrun(ready):
    """Different input bytes are a different test, not a reproduction of
    this one -- even when the verdict happens to match."""
    _ok(_run(ready))
    fixture = ready["fixtures_dir"] / TESTCASE / "input.sysml"
    fixture.write_text("package Example { part def Other; }\n", encoding="utf-8")

    _ok(_run(ready))
    assert _counts() == (2, 0)


def test_unknown_party_is_refused(ready):
    result = _run(ready, party="no-such-machine")
    assert result.exit_code == 2, result.output
    assert "unknown party" in result.output
    assert _counts() == (0, 0)
