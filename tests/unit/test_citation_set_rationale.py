"""`svt citation set-rationale` -- the update path that didn't exist.

`set-quote` and `set-page` were already there; rationale had no correction
path, so narrowing one meant hand-editing sources/sources.ttl, which this
repo forbids. Two rationales needed exactly that: they asserted settled
verdicts on named implementations' conformance with the same confidence as
the grounding itself, which is a finding a TestRun produces, not something
a citation establishes.
"""

from __future__ import annotations

from typer.testing import CliRunner

from sysmlv2_testing import cli as cli_module
from sysmlv2_testing import ids
from sysmlv2_testing.graph import load_full_ledger
from sysmlv2_testing.namespaces import SVT

runner = CliRunner()


def _register_citation(rationale: str | None = None) -> str:
    assert runner.invoke(
        cli_module.app,
        ["document", "add", "--id", "fake-doc", "--doc-number", "fake/0000",
         "--title", "Fake Spec", "--local-path", "sources/local/fake.pdf",
         "--sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"],
    ).exit_code == 0
    args = ["citation", "add", "--id", "fake-citation", "--document", "fake-doc",
            "--section", "1", "--page", "1", "--quote", "a thing must be a thing"]
    if rationale is not None:
        args += ["--rationale", rationale]
    result = runner.invoke(cli_module.app, args)
    assert result.exit_code == 0, result.output
    return "fake-citation"


def test_set_rationale_replaces_in_place(isolated_ledger):
    _register_citation("tool X's acceptance of this is a real conformance gap")

    result = runner.invoke(
        cli_module.app,
        ["citation", "set-rationale", "--id", "fake-citation",
         "--rationale", "the quote states the rule this claim relies on"],
    )
    assert result.exit_code == 0, result.output

    iri = ids.slug_id("citation", "fake-citation")
    rationales = list(load_full_ledger().objects(iri, SVT.rationale))
    # Exactly one -- remove-then-add, not an append. SpecCitationRationaleShape
    # caps it at maxCount 1, so an append would fail the gate anyway; this
    # asserts the intended semantics rather than relying on that.
    assert len(rationales) == 1
    assert str(rationales[0]) == "the quote states the rule this claim relies on"


def test_set_rationale_adds_one_where_none_existed(isolated_ledger):
    _register_citation()  # no --rationale
    iri = ids.slug_id("citation", "fake-citation")
    assert load_full_ledger().value(iri, SVT.rationale) is None

    result = runner.invoke(
        cli_module.app,
        ["citation", "set-rationale", "--id", "fake-citation", "--rationale", "added later"],
    )
    assert result.exit_code == 0, result.output
    assert str(load_full_ledger().value(iri, SVT.rationale)) == "added later"


def test_set_rationale_refuses_an_unknown_citation(isolated_ledger):
    _register_citation()
    result = runner.invoke(
        cli_module.app,
        ["citation", "set-rationale", "--id", "no-such-citation", "--rationale", "x"],
    )
    assert result.exit_code == 2, result.output
