"""`svt implementation add` / `svt version add` -- the two most
foundational "register a fact" commands, previously untested (every
other test either checks a refusal path or reads pre-seeded fixture
data). Isolated ledger, same reasoning as test_testrun_annotate.py: an
agent-authored write must never land in the real project ledger.
"""

from __future__ import annotations

from rdflib import RDF
from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import ids
from sysmlv2_testing.graph import load_full_ledger
from sysmlv2_testing.namespaces import SVT

runner = CliRunner()


def test_implementation_add_lands_correctly(isolated_ledger):
    result = runner.invoke(
        cli_module.app,
        [
            "implementation",
            "add",
            "--name",
            "new-impl",
            "--repo",
            "https://example.org/new-impl",
            "--language",
            "Rust",
        ],
    )
    assert result.exit_code == 0, result.output

    ledger = load_full_ledger()
    impl_iri = ids.slug_id("implementation", "new-impl")
    assert (impl_iri, RDF.type, SVT.Implementation) in ledger
    assert str(ledger.value(impl_iri, SVT.repositoryURL)) == "https://example.org/new-impl"
    assert str(ledger.value(impl_iri, SVT.primaryLanguage)) == "Rust"


def test_version_add_lands_and_links_to_implementation(isolated_ledger):
    commit = "1" * 40
    result = runner.invoke(
        cli_module.app,
        [
            "implementation",
            "add",
            "--name",
            "new-impl",
            "--repo",
            "https://example.org/new-impl",
            "--language",
            "Rust",
        ],
    )
    assert result.exit_code == 0, result.output

    result = runner.invoke(
        cli_module.app,
        [
            "version",
            "add",
            "--implementation",
            "new-impl",
            "--commit",
            commit,
            "--label",
            "v1.0.0",
        ],
    )
    assert result.exit_code == 0, result.output

    ledger = load_full_ledger()
    impl_iri = ids.slug_id("implementation", "new-impl")
    version_iri = ids.mint("version", f"new-impl|{commit}")
    assert (version_iri, RDF.type, SVT.Version) in ledger
    assert ledger.value(version_iri, SVT.ofImplementation) == impl_iri
    assert str(ledger.value(version_iri, SVT.commitHash)) == commit
    assert str(ledger.value(version_iri, SVT.versionLabel)) == "v1.0.0"
    # the inverse direction (svt:hasVersion) must also round-trip -- this
    # is exactly what shapes/implementation.shapes.ttl's new
    # ImplementationHasVersionShape enforces structurally; confirming it
    # here too catches a regression even before `svt verify` would.
    assert ledger.value(impl_iri, SVT.hasVersion) == version_iri


def test_version_add_refuses_unknown_implementation(isolated_ledger):
    result = runner.invoke(
        cli_module.app,
        [
            "version",
            "add",
            "--implementation",
            "no-such-implementation",
            "--commit",
            "2" * 40,
        ],
    )
    assert result.exit_code == 2, result.output
    assert "unknown implementation" in result.output or "register it first" in result.output
