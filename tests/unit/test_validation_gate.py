"""svt run must refuse an unvalidated TestCase outright -- being SHACL-valid
RDF is not the same thing as a human having confirmed the claim against the
spec (see AGENTS.md's "Construction vs. validation"). This is the literal
enforcement of that gate: every seeded TestCase in this repo is, by design,
unvalidated (nobody has ever run `svt testcase validate` against them --
see docs/design-notes.md), so a real run against any of them must be
refused, not just documented as a rule.
"""

from typer.testing import CliRunner

from sysmlv2_testing.cli import app
from sysmlv2_testing.graph import load_full_ledger
from sysmlv2_testing.namespaces import SVT

runner = CliRunner()


def _an_unvalidated_testcase_id() -> str:
    """Every seeded TestCase in this ledger is unvalidated by construction
    (see AGENTS.md) -- this just picks one and confirms that premise still
    holds, rather than hard-coding an id that could silently go stale."""
    ledger = load_full_ledger()
    from rdflib import RDF  # noqa: PLC0415

    for tc_iri in ledger.subjects(RDF.type, SVT.TestCase):
        if not any(ledger.subjects(SVT.validates, tc_iri)):
            # ids are minted as .../id/testcase-<slug>; slug may itself
            # contain hyphens, so split on the first one instead
            slug = str(tc_iri).rsplit("/", 1)[-1]
            return slug.split("-", 1)[1]
    raise AssertionError(
        "expected at least one unvalidated TestCase in the ledger for this "
        "test to mean anything -- if every TestCase now has a Validation "
        "record, this test needs a dedicated unvalidated fixture instead"
    )


def _a_registered_version() -> tuple[str, str]:
    """(implementation slug, commit hash) for any real registered Version --
    the gate fires before adapter dispatch, so this need not be runnable."""
    ledger = load_full_ledger()
    from rdflib import RDF  # noqa: PLC0415

    for v_iri in ledger.subjects(RDF.type, SVT.Version):
        impl_iri = ledger.value(v_iri, SVT.ofImplementation)
        commit = ledger.value(v_iri, SVT.commitHash)
        impl_slug = str(impl_iri).rsplit("/", 1)[-1].split("-", 1)[1]
        return impl_slug, str(commit)
    raise AssertionError("expected at least one registered Version")


def test_run_refuses_an_unvalidated_testcase():
    testcase_id = _an_unvalidated_testcase_id()
    impl_slug, commit = _a_registered_version()
    result = runner.invoke(
        app,
        ["run", "--testcase", testcase_id, "--implementation", impl_slug, "--version", commit],
    )
    assert result.exit_code == 2, result.output
    assert "no svt:Validation record" in result.output
    assert f"svt testcase validate --id {testcase_id}" in result.output


def test_validate_refuses_llm_flavored_by_names():
    for bad_name in ("claude", "AI", "llm", "Agent"):
        result = runner.invoke(
            app,
            ["testcase", "validate", "--id", "does-not-matter", "--by", bad_name],
        )
        assert result.exit_code == 2, (bad_name, result.output)
        assert "not a human" in result.output
