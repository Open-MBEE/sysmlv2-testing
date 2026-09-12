"""svt view compiles a report from one SPARQL query + the fixture files --
this checks the one property that matters for an ephemeral, regenerate-
anytime artifact: given an unchanged ledger and unchanged fixtures, it is
byte-for-byte deterministic. (Same discipline as
tests/determinism/test_roundtrip.py, for a different artifact.)
"""

from sysmlv2_testing.view import render_report


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
