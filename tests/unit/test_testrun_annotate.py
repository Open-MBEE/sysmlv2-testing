"""svt testrun annotate / svt testrun link-issue -- the post-run pair to
svt testcase validate. Uses the isolated_ledger fixture (conftest.py)
because, unlike the refusal-only checks in test_validation_gate.py, these
tests exercise the real write path -- and an agent-authored Annotation/
IssueLink must never land in the actual project ledger (same governance
reason an agent must never run `svt testcase validate` on a real
TestCase; see AGENTS.md).
"""

from __future__ import annotations

from rdflib import Graph, Literal
from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import ids
from sysmlv2_testing.namespaces import EARL

from conftest import FAKE_COMMIT, FAKE_IMPLEMENTATION, FAKE_TESTCASE, add_full_test_run

runner = CliRunner()

IMPLEMENTATION = FAKE_IMPLEMENTATION
COMMIT = FAKE_COMMIT
TESTCASE = FAKE_TESTCASE


def _annotate_args(**overrides):
    args = {
        "testcase": TESTCASE,
        "implementation": IMPLEMENTATION,
        "version": COMMIT,
        "by": "A Real Human",
        "comment": "the output looked suspicious",
        "at": None,
    }
    args.update(overrides)
    cmd = [
        "testrun",
        "annotate",
        "--testcase",
        args["testcase"],
        "--implementation",
        args["implementation"],
        "--version",
        args["version"],
        "--by",
        args["by"],
        "--comment",
        args["comment"],
    ]
    if args["at"] is not None:
        cmd += ["--at", args["at"]]
    return cmd


def test_annotate_succeeds_against_a_real_run(isolated_ledger):
    result = runner.invoke(cli_module.app, _annotate_args())
    assert result.exit_code == 0, result.output
    on_disk = (isolated_ledger["runs_dir"] / f"{IMPLEMENTATION}.ttl").read_text()
    assert "Annotation" in on_disk
    assert "the output looked suspicious" in on_disk


def test_annotate_refuses_llm_flavored_by_name(isolated_ledger):
    result = runner.invoke(cli_module.app, _annotate_args(by="claude"))
    assert result.exit_code == 2, result.output
    assert "not a human" in result.output


def test_annotate_refuses_unknown_testcase(isolated_ledger):
    result = runner.invoke(cli_module.app, _annotate_args(testcase="no-such-testcase"))
    assert result.exit_code == 2, result.output
    assert "unknown testcase" in result.output


def test_annotate_refuses_no_matching_run(isolated_ledger):
    result = runner.invoke(cli_module.app, _annotate_args(version="0" * 40))
    assert result.exit_code == 2, result.output
    assert "unknown version" in result.output


def test_annotate_then_conflicting_by_name_is_refused(isolated_ledger):
    """'Z' and 'z' slugify (ids.slug_id lowercases) to the identical
    person_iri -- exactly the cross-file identity gap the design review
    caught: the same IRI must not silently pick up two different labels."""
    first = runner.invoke(cli_module.app, _annotate_args(by="Z"))
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli_module.app, _annotate_args(by="z"))
    assert second.exit_code == 2, second.output
    assert "resolves to the same person" in second.output


def test_link_issue_succeeds_and_appears_in_view(isolated_ledger):
    result = runner.invoke(
        cli_module.app,
        [
            "testrun",
            "link-issue",
            "--testcase",
            TESTCASE,
            "--implementation",
            IMPLEMENTATION,
            "--version",
            COMMIT,
            "--by",
            "A Real Human",
            "--url",
            "https://github.com/Open-MBEE/sysml-toolkit/issues/2",
            "--label",
            "cross-wired redefinition",
        ],
    )
    assert result.exit_code == 0, result.output
    on_disk = (isolated_ledger["runs_dir"] / f"{IMPLEMENTATION}.ttl").read_text()
    assert "IssueLink" in on_disk
    assert "sysml-toolkit/issues/2" in on_disk


def test_ambiguous_multiple_runs_refuses_without_at(isolated_ledger):
    """A second real TestRun for the identical (testcase, implementation,
    version) triple, at a different timestamp, must force --at rather than
    silently picking one (see the plan's design-review finding).

    The second run records a *different* outcome deliberately: two runs of
    one triple that agree are no longer a legal ledger state (they would be
    a Reproduction or a reconfirmedAt timestamp), so divergence is now the
    only way genuine --at ambiguity arises."""
    run_ts2 = Literal("2026-02-02T00:00:00+00:00", datatype=cli_module.XSD.dateTime)
    tc_iri = ids.slug_id("testcase", TESTCASE)
    version_iri = ids.mint("version", f"{IMPLEMENTATION}|{COMMIT}")
    run_iri2 = ids.mint("run", f"{TESTCASE}|{IMPLEMENTATION}|{COMMIT}|{run_ts2}")
    g = Graph()
    g.parse(isolated_ledger["runs_dir"] / f"{IMPLEMENTATION}.ttl", format="turtle")
    add_full_test_run(g, run_iri2, tc_iri, version_iri, run_ts2, outcome=EARL.failed)
    (isolated_ledger["runs_dir"] / f"{IMPLEMENTATION}.ttl").write_text(
        g.serialize(format="turtle"), encoding="utf-8"
    )

    result = runner.invoke(cli_module.app, _annotate_args())
    assert result.exit_code == 2, result.output
    assert "disambiguate with --at" in result.output
    assert "2026-01-01" in result.output
    assert "2026-02-02" in result.output

    disambiguated = runner.invoke(cli_module.app, _annotate_args(at="2026-02-02T00:00:00+00:00"))
    assert disambiguated.exit_code == 0, disambiguated.output
