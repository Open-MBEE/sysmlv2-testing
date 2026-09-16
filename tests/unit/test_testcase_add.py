"""`svt testcase add` -- previously untested for its actual write path
(fixture-file copying, --resolves parsing). Isolated ledger, same
reasoning as test_testrun_annotate.py.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import RDF
from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import ids
from sysmlv2_testing.graph import load_full_ledger
from sysmlv2_testing.namespaces import SVT

runner = CliRunner()


def _register_fake_citation() -> str:
    """A real, gate-passing SpecCitation any grounded TestCase in these
    tests can point at -- returns its --id."""
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
    return "fake-citation"


def test_testcase_add_copies_fixture_files_and_records_them(isolated_ledger, tmp_path: Path):
    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    result = runner.invoke(
        cli_module.app,
        [
            "testcase",
            "add",
            "--id",
            "new-testcase",
            "--description",
            "a fake requirement, written prospectively",
            "--intent",
            isolated_ledger["intent"],
            "--input-file",
            str(src),
            "--method",
            "structural-check",
            "--expected",
            "clean",
        ],
    )
    # SHACL gate failures exit 1 (distinct from a CLI-level validation
    # error like "unknown testcase", which exits 2)
    assert result.exit_code == 1, result.output  # no --grounds for an --expected value
    assert "groundedIn" in result.output

    # the fixture file must not have been left behind by the failed,
    # ungrounded attempt -- only a successful, SHACL-gated write should
    # ever populate ledger/fixtures/.
    copied = isolated_ledger["fixtures_dir"] / "new-testcase" / "input.sysml"
    assert not copied.exists(), "a rejected write must not leave a fixture file behind"


def test_testcase_add_lands_correctly_when_grounded(isolated_ledger, tmp_path: Path):
    citation_id = _register_fake_citation()

    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    result = runner.invoke(
        cli_module.app,
        [
            "testcase",
            "add",
            "--id",
            "new-testcase",
            "--description",
            "a fake requirement, written prospectively",
            "--intent",
            isolated_ledger["intent"],
            "--input-file",
            str(src),
            "--method",
            "structural-check",
            "--expected",
            "clean",
            "--grounds",
            citation_id,
        ],
    )
    assert result.exit_code == 0, result.output

    ledger = load_full_ledger()
    tc_iri = ids.slug_id("testcase", "new-testcase")
    assert (tc_iri, RDF.type, SVT.TestCase) in ledger
    assert str(ledger.value(tc_iri, SVT.hasInputFile)) == "input.sysml"

    copied = isolated_ledger["fixtures_dir"] / "new-testcase" / "input.sysml"
    assert copied.exists()
    assert copied.read_text(encoding="utf-8") == src.read_text(encoding="utf-8")


def test_testcase_add_resolves_parses_subject_equals_target(isolated_ledger, tmp_path: Path):
    citation_id = _register_fake_citation()

    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    result = runner.invoke(
        cli_module.app,
        [
            "testcase",
            "add",
            "--id",
            "resolution-testcase",
            "--description",
            "a fake resolution requirement",
            "--intent",
            isolated_ledger["intent"],
            "--input-file",
            str(src),
            "--method",
            "reference-resolution",
            "--resolves",
            "Usage::c::@0=Lib::Container::items",
            "--grounds",
            citation_id,
        ],
    )
    assert result.exit_code == 0, result.output

    ledger = load_full_ledger()
    tc_iri = ids.slug_id("testcase", "resolution-testcase")
    checks = list(ledger.objects(tc_iri, SVT.checksResolution))
    assert len(checks) == 1
    assert str(ledger.value(checks[0], SVT.subjectFeature)) == "Usage::c::@0"
    assert str(ledger.value(checks[0], SVT.expectedTarget)) == "Lib::Container::items"


def test_testcase_add_rejects_malformed_resolves_pair(isolated_ledger, tmp_path: Path):
    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    result = runner.invoke(
        cli_module.app,
        [
            "testcase",
            "add",
            "--id",
            "bad-resolution-testcase",
            "--description",
            "a fake resolution requirement",
            "--intent",
            isolated_ledger["intent"],
            "--input-file",
            str(src),
            "--method",
            "reference-resolution",
            "--resolves",
            "no-equals-sign-here",
        ],
    )
    assert result.exit_code == 2, result.output
    assert "--resolves must be" in result.output
