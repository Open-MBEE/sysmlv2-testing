"""Shared fixtures for tests that need a real, SHACL-conformant ledger
write path but must never touch the actual project ledger under
`ledger/`. An agent-authored write (an Annotation, IssueLink, or
Validation) must never land in the real ledger -- see AGENTS.md -- so any
test exercising the CLI's write path works against an isolated, synthetic
copy instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import RDF, Graph, Literal

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import graph as graph_module
from sysmlv2_testing import ids
from sysmlv2_testing.namespaces import EARL, PROV, SVT

FAKE_IMPLEMENTATION = "fake-impl"
FAKE_COMMIT = "abc123def4567890abc123def4567890abc123d"
FAKE_TESTCASE = "fake-testcase"


def add_full_test_run(g: Graph, run_iri, tc_iri, version_iri, ts) -> None:
    """A SHACL-conformant TestRun (+ its Invocation/TestResult/agent) --
    every property TestRunShape/TestResultShape/InvocationShape require,
    so a test's real focus (an Annotation, IssueLink, or a view render)
    is the only thing under test, not incidentally tripped up by an
    already-incomplete fixture."""
    key = str(run_iri)
    agent_iri = ids.slug_id("agent", "fake-svt-cli")
    result_iri = ids.mint("result", key)
    invocation_iri = ids.mint("invocation", key)
    g.add((agent_iri, RDF.type, EARL.Software))
    g.add((run_iri, RDF.type, SVT.TestRun))
    g.add((run_iri, EARL.test, tc_iri))
    g.add((run_iri, EARL.subject, version_iri))
    g.add((run_iri, EARL.assertedBy, agent_iri))
    g.add((run_iri, EARL.mode, EARL.automatic))
    g.add((run_iri, EARL.result, result_iri))
    g.add((run_iri, SVT.hasInvocation, invocation_iri))
    g.add((run_iri, PROV.startedAtTime, ts))
    g.add((result_iri, RDF.type, EARL.TestResult))
    g.add((result_iri, EARL.outcome, EARL.passed))
    g.add((invocation_iri, RDF.type, SVT.Invocation))
    g.add((invocation_iri, SVT.command, Literal("fake-tool check input.sysml")))
    g.add((invocation_iri, SVT.exitCode, Literal(0)))
    g.add((invocation_iri, SVT.stdout, Literal("clean")))
    g.add((invocation_iri, SVT.stderr, Literal("")))
    g.add(
        (
            invocation_iri,
            SVT.inputDigest,
            Literal("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        )
    )
    g.add((invocation_iri, PROV.startedAtTime, ts))


@pytest.fixture()
def isolated_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A minimal, synthetic ledger -- one Implementation, one Version, one
    TestCase, one TestRun -- isolated from the real project ledger, with
    cli.py's and graph.py's path constants monkeypatched to point at it."""
    ledger_dir = tmp_path / "ledger"
    runs_dir = ledger_dir / "runs"
    runs_dir.mkdir(parents=True)
    sources_ttl = tmp_path / "sources.ttl"
    implementations_ttl = ledger_dir / "implementations.ttl"
    testcases_ttl = ledger_dir / "testcases.ttl"

    impl_iri = ids.slug_id("implementation", FAKE_IMPLEMENTATION)
    version_iri = ids.mint("version", f"{FAKE_IMPLEMENTATION}|{FAKE_COMMIT}")
    tc_iri = ids.slug_id("testcase", FAKE_TESTCASE)
    run_ts = Literal("2026-01-01T00:00:00+00:00", datatype=cli_module.XSD.dateTime)
    run_iri = ids.mint("run", f"{FAKE_TESTCASE}|{FAKE_IMPLEMENTATION}|{FAKE_COMMIT}|{run_ts}")

    sources_ttl.write_text("", encoding="utf-8")

    impl_g = Graph()
    impl_g.add((impl_iri, RDF.type, SVT.Implementation))
    impl_g.add((impl_iri, SVT.name, Literal(FAKE_IMPLEMENTATION)))
    impl_g.add((impl_iri, SVT.repositoryURL, Literal("https://example.org/fake-impl")))
    impl_g.add((impl_iri, SVT.primaryLanguage, Literal("Go")))
    impl_g.add((version_iri, RDF.type, SVT.Version))
    impl_g.add((version_iri, SVT.ofImplementation, impl_iri))
    impl_g.add((version_iri, SVT.commitHash, Literal(FAKE_COMMIT)))
    implementations_ttl.write_text(impl_g.serialize(format="turtle"), encoding="utf-8")

    tc_g = Graph()
    tc_g.add((tc_iri, RDF.type, SVT.TestCase))
    tc_g.add((tc_iri, SVT.description, Literal("a fake testcase for isolated testing")))
    tc_g.add((tc_iri, SVT.hasInputFile, Literal("input.sysml")))
    tc_g.add((tc_iri, SVT.method, Literal("structural-check")))
    testcases_ttl.write_text(tc_g.serialize(format="turtle"), encoding="utf-8")

    run_g = Graph()
    add_full_test_run(run_g, run_iri, tc_iri, version_iri, run_ts)
    (runs_dir / f"{FAKE_IMPLEMENTATION}.ttl").write_text(
        run_g.serialize(format="turtle"), encoding="utf-8"
    )

    for mod in (cli_module, graph_module):
        monkeypatch.setattr(mod, "SOURCES_TTL", sources_ttl)
        monkeypatch.setattr(mod, "IMPLEMENTATIONS_TTL", implementations_ttl)
        monkeypatch.setattr(mod, "TESTCASES_TTL", testcases_ttl)
        monkeypatch.setattr(mod, "RUNS_DIR", runs_dir)
    monkeypatch.setattr(cli_module, "runs_ttl", lambda slug: runs_dir / f"{slug}.ttl")

    # view.py imports fixtures_dir_for from .graph; a nonexistent fixtures
    # dir is handled gracefully (view.py shows "(missing on disk)"), so no
    # separate FIXTURES_DIR isolation is needed for these tests.

    return {
        "run_iri": run_iri,
        "runs_dir": runs_dir,
        "testcase": FAKE_TESTCASE,
        "implementation": FAKE_IMPLEMENTATION,
        "version": FAKE_COMMIT,
    }
