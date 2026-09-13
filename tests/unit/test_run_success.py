"""`svt run`'s actual success path -- previously only tested for its
pre-dispatch refusal (an unvalidated TestCase). This exercises the real
thing: adapter dispatch -> adapters.compare.compare() -> a genuine
TestRun/Invocation/TestResult written to the ledger, via a fake, in-repo
stub adapter (tests/unit/_stub_adapter.py) standing in for a real pinned
implementation binary.
"""

from __future__ import annotations

from rdflib import RDF
from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import ids
from sysmlv2_testing.graph import load_full_ledger
from sysmlv2_testing.namespaces import EARL, SVT

runner = CliRunner()


def test_run_writes_a_real_passed_testrun_via_a_stub_adapter(isolated_ledger, tmp_path, monkeypatch):
    implementation = isolated_ledger["implementation"]
    version = isolated_ledger["version"]
    testcase = "run-success-testcase"  # distinct from isolated_ledger's pre-seeded TestCase

    # Stand in for a real pinned implementation binary -- everything
    # downstream of dispatch (compare(), the TestRun/Invocation/TestResult
    # write) is the real, unmodified code under test.
    monkeypatch.setitem(cli_module.ADAPTER_MODULES, implementation, "_stub_adapter")

    # Ground it (required since --expected is set), via the real CLI.
    result = runner.invoke(
        cli_module.app,
        [
            "document",
            "add",
            "--id",
            "fake-doc",
            "--doc-number",
            "fake/0000",
            "--title",
            "Fake Spec",
            "--local-path",
            "sources/local/fake.pdf",
            "--sha256",
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(
        cli_module.app,
        [
            "citation",
            "add",
            "--id",
            "fake-citation",
            "--document",
            "fake-doc",
            "--section",
            "1",
            "--page",
            "1",
            "--quote",
            "a thing must be a thing",
        ],
    )
    assert result.exit_code == 0, result.output

    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")
    result = runner.invoke(
        cli_module.app,
        [
            "testcase",
            "add",
            "--id",
            testcase,
            "--description",
            "a fake requirement for testing the run success path",
            "--input-file",
            str(src),
            "--method",
            "structural-check",
            "--expected",
            "clean",
            "--grounds",
            "fake-citation",
        ],
    )
    assert result.exit_code == 0, result.output

    # A throwaway test fixture, not a real claim -- see
    # tests/unit/test_testrun_annotate.py for the same "isolated ledger,
    # not the real project one" reasoning.
    result = runner.invoke(
        cli_module.app, ["testcase", "validate", "--id", testcase, "--by", "Test Author"]
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli_module.app,
        ["run", "--testcase", testcase, "--implementation", implementation, "--version", version],
    )
    assert result.exit_code == 0, result.output
    assert result.output.startswith("passed\t")

    ledger = load_full_ledger()
    tc_iri = ids.slug_id("testcase", testcase)
    version_iri = ids.mint("version", f"{implementation}|{version}")
    runs = [
        r
        for r in ledger.subjects(RDF.type, SVT.TestRun)
        if ledger.value(r, EARL.test) == tc_iri and ledger.value(r, EARL.subject) == version_iri
    ]
    assert len(runs) == 1, runs
    run_iri = runs[0]
    result_iri = ledger.value(run_iri, EARL.result)
    invocation_iri = ledger.value(run_iri, SVT.hasInvocation)
    assert ledger.value(result_iri, EARL.outcome) == EARL.passed
    assert str(ledger.value(result_iri, SVT.actual)) == "clean"
    assert str(ledger.value(invocation_iri, SVT.command)) == "fake-tool check input.sysml"
    assert int(ledger.value(invocation_iri, SVT.exitCode)) == 0
