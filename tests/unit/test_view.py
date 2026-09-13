"""svt view compiles a report from one SPARQL query + the fixture files --
this checks the one property that matters for an ephemeral, regenerate-
anytime artifact: given an unchanged ledger and unchanged fixtures, it is
byte-for-byte deterministic. (Same discipline as
tests/determinism/test_roundtrip.py, for a different artifact.)
"""

from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing.view import render_report

runner = CliRunner()


def test_render_report_is_deterministic_across_runs():
    once = render_report()
    twice = render_report()
    assert once == twice


def test_render_report_for_one_testcase_is_deterministic_and_scoped():
    once = render_report("redefinition-ambiguity-3plus")
    twice = render_report("redefinition-ambiguity-3plus")
    assert once == twice
    assert "redefinition-ambiguity-3plus" in once
    # scoped to just this test case -- another seeded id shouldn't appear
    assert "constraint-eval-declaration-site" not in once


def test_render_report_includes_real_input_and_raw_output_not_just_a_verdict():
    report = render_report("redefinition-ambiguity-3plus")
    # the actual SysML source, not a filename-only pointer
    assert "connection def Link" in report or "part def Container" in report
    # the real captured stdout/stderr, not a summarized code
    assert "```" in report


def test_unknown_testcase_yields_no_matching_section():
    report = render_report("not-a-real-testcase-id")
    assert "no matching test case found" in report


def test_report_shows_the_grounding_not_just_a_bare_expected_value():
    report = render_report("redefinition-ambiguity-3plus")
    assert "### Grounding" in report
    # the verbatim quote, not just a citation ID or page number
    assert "removeRedefinedFeatures" in report


def test_reference_resolution_testcase_shows_facts_not_a_bare_expected_line():
    """The posterior state x+ this method checks is a *set* of facts, not
    one scalar -- the report must show what those facts are, not fall
    back to "expected: not yet settled" just because svt:expected is
    unset for this method."""
    report = render_report("redefinition-ambiguity-2-resolution")
    assert "resolution facts" in report
    assert "Lib::Container::items" in report
    assert "not yet settled" not in report


def test_reference_resolution_testcase_shows_the_real_cross_wiring_bug():
    report = render_report("redefinition-ambiguity-2-resolution")
    assert "failed" in report
    # sysml-toolkit's actual (wrong) resolved target, not just a verdict code
    assert "UsageTwo::c::@2" in report or "UsageTwo::c::@1" in report


def test_state_execution_testcase_shows_the_command_events():
    report = render_report("state-machine-transitions-on-event")
    assert "**command (u): events**" in report
    assert "EngagementEvent" in report


def test_report_renders_multiple_annotations_and_issue_links_deterministically(isolated_ledger):
    """_run_section reads svt:concernsRun directly off the ledger (not
    through queries/testcase_view.rq, same reasoning as svt:groundedIn) --
    this must stay sorted and stable with more than one Annotation/
    IssueLink on the same TestRun, or render_report's determinism
    (asserted elsewhere in this file) would go flaky the moment a run
    has more than one of either."""
    testcase = isolated_ledger["testcase"]
    implementation = isolated_ledger["implementation"]
    version = isolated_ledger["version"]

    def _annotate(by, comment):
        result = runner.invoke(
            cli_module.app,
            [
                "testrun",
                "annotate",
                "--testcase",
                testcase,
                "--implementation",
                implementation,
                "--version",
                version,
                "--by",
                by,
                "--comment",
                comment,
            ],
        )
        assert result.exit_code == 0, result.output

    def _link_issue(by, url):
        result = runner.invoke(
            cli_module.app,
            [
                "testrun",
                "link-issue",
                "--testcase",
                testcase,
                "--implementation",
                implementation,
                "--version",
                version,
                "--by",
                by,
                "--url",
                url,
            ],
        )
        assert result.exit_code == 0, result.output

    _annotate("Zargham", "first observation")
    _annotate("A Colleague", "second observation")
    _link_issue("Zargham", "https://example.org/issues/1")
    _link_issue("Zargham", "https://example.org/issues/2")

    once = render_report(testcase)
    twice = render_report(testcase)
    assert once == twice
    assert "first observation" in once
    assert "second observation" in once
    assert "https://example.org/issues/1" in once
    assert "https://example.org/issues/2" in once
