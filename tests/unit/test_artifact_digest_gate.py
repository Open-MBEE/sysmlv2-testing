"""A TestRun must not be recorded against a Version it did not execute.

`svt run --version` never reaches an adapter -- each picks its tool from the
environment -- so a Version's `earl:subject` was a label nothing checked. The
Version's `svt:artifactDigest` is the only thing that can tie the claim to
what ran, and these pin that it actually does.

The failure this prevents is not hypothetical or exotic: sysml-toolkit's
release asset and a local build of the byte-identical source tree both report
`sysmlv2 0.6.0`, so the self-reported version string cannot tell them apart.
Only the digest can.
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

TESTCASE = "digest-testcase"
OTHER_DIGEST = "0" * 64


def _ok(result):
    assert result.exit_code == 0, result.output
    return result


@pytest.fixture()
def ready(isolated_ledger, tmp_path: Path, monkeypatch):
    """Isolated ledger with a runnable TestCase and a stub adapter that
    reports a tool fingerprint, as the real adapters now do."""
    import _stub_adapter
    from adapters.base import RawResult

    monkeypatch.setitem(
        cli_module.ADAPTER_MODULES, isolated_ledger["implementation"], "_stub_adapter"
    )
    monkeypatch.setattr(
        _stub_adapter.ADAPTER, "run",
        lambda spec: RawResult(
            command="fake-tool check input.sysml", exit_code=0, stdout="clean", stderr="",
            tool_version="fake-tool 1.0", tool_digest="a" * 64,
        ),
    )

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
    return isolated_ledger


def _run(ready):
    return runner.invoke(cli_module.app, [
        "run", "--testcase", TESTCASE,
        "--implementation", ready["implementation"], "--version", ready["version"]])


def _pin(ready, digest):
    return runner.invoke(cli_module.app, [
        "version", "add-artifact-digest", "--implementation", ready["implementation"],
        "--version", ready["version"], "--digest", digest])


def _runs():
    g = load_full_ledger()
    return [r for r in g.subjects(EARL.test, ids.slug_id("testcase", TESTCASE))
            if (r, RDF.type, SVT.TestRun) in g]


def test_unpinned_version_records_what_ran_and_says_how_to_pin(ready):
    """Nothing existing breaks: a Version with no artifactDigest still runs,
    and the digest is surfaced so it can be pinned rather than guessed."""
    result = _ok(_run(ready))
    assert "has no svt:artifactDigest" in result.output
    assert "add-artifact-digest" in result.output

    g = load_full_ledger()
    inv = g.value(_runs()[0], SVT.hasInvocation)
    assert str(g.value(inv, SVT.toolDigest)) == "a" * 64
    assert str(g.value(inv, SVT.toolVersion)) == "fake-tool 1.0"


def test_matching_digest_proceeds(ready):
    _ok(_pin(ready, "a" * 64))
    _ok(_run(ready))
    assert len(_runs()) == 1


def test_any_pinned_digest_matches(ready):
    """A release ships one artifact per platform, so the pins are a set: a
    second party on another OS adds theirs beside yours rather than
    overwriting it, and either is accepted. Found the hard way -- a linux
    and a macOS build of OpenSysML v0.8.0 have different, both-valid
    digests, and a single-valued pin refused the second one."""
    _ok(_pin(ready, OTHER_DIGEST))
    _ok(_pin(ready, "a" * 64))
    _ok(_run(ready))
    assert len(_runs()) == 1


def test_mismatched_digest_is_refused_and_writes_nothing(ready):
    _ok(_pin(ready, OTHER_DIGEST))
    result = _run(ready)

    assert result.exit_code == 2, result.output
    assert "not the artifact" in result.output
    assert OTHER_DIGEST in result.output and "a" * 64 in result.output
    assert _runs() == [], "a run against a Version it did not execute must not be recorded"


def test_adapter_reporting_no_digest_still_runs(ready, monkeypatch):
    """An adapter that cannot fingerprint its tool must not be blocked --
    there is simply nothing to contradict."""
    import _stub_adapter
    from adapters.base import RawResult

    monkeypatch.setattr(
        _stub_adapter.ADAPTER, "run",
        lambda spec: RawResult(command="fake", exit_code=0, stdout="clean", stderr=""),
    )
    _ok(_pin(ready, OTHER_DIGEST))
    _ok(_run(ready))
    assert len(_runs()) == 1

    g = load_full_ledger()
    assert g.value(g.value(_runs()[0], SVT.hasInvocation), SVT.toolDigest) is None


def test_set_artifact_digest_refuses_an_unknown_version(ready):
    result = runner.invoke(cli_module.app, [
        "version", "add-artifact-digest", "--implementation", ready["implementation"],
        "--version", "0000000000000000000000000000000000000000", "--digest", "b" * 64])
    assert result.exit_code == 2, result.output
    assert "unknown version" in result.output
