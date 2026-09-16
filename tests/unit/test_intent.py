"""`svt intent` and the intent/method alignment gate.

The point of svt:TestIntent is that a TestCase's stated question and the
method that is supposed to answer it are checked against each other
mechanically, not left to an author to notice. These tests assert the gate
actually refuses -- documenting that it should would be exactly the kind of
unenforced convention this element exists to replace. Isolated ledger, same
reasoning as test_testcase_add.py.
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


def _add_intent(id_: str, question: str, concerns: str):
    return runner.invoke(
        cli_module.app,
        ["intent", "add", "--id", id_, "--question", question, "--concerns", concerns],
    )


def _add_testcase(id_: str, intent: str, method: str, src: Path, extra: list[str] | None = None):
    return runner.invoke(
        cli_module.app,
        [
            "testcase",
            "add",
            "--id",
            id_,
            "--description",
            "a fake requirement, written prospectively",
            "--intent",
            intent,
            "--input-file",
            str(src),
            "--method",
            method,
            *(extra or []),
        ],
    )


def test_intent_add_lands_with_question_and_concerns(isolated_ledger):
    result = _add_intent(
        "new-intent", "Does the tool accept this model?", "admissibility"
    )
    assert result.exit_code == 0, result.output

    ledger = load_full_ledger()
    iri = ids.slug_id("intent", "new-intent")
    assert (iri, RDF.type, SVT.TestIntent) in ledger
    assert str(ledger.value(iri, SVT.question)) == "Does the tool accept this model?"
    assert str(ledger.value(iri, SVT.concerns)) == "admissibility"


def test_intent_add_refuses_a_question_that_is_not_a_question(isolated_ledger):
    """The trailing '?' is SHACL-enforced precisely because a statement is
    where outcome-narration hides -- this text is a verdict, not a
    question, and must not be recordable as an intent."""
    result = _add_intent(
        "narrated-intent",
        "sysml-toolkit cross-wires the two redefinitions to each other.",
        "posterior-state",
    )
    # SHACL gate failures exit 1 (a CLI-level validation error exits 2).
    assert result.exit_code == 1, result.output
    assert "TestIntentQuestionShape" in result.output

    assert (
        ids.slug_id("intent", "narrated-intent"),
        RDF.type,
        SVT.TestIntent,
    ) not in load_full_ledger()


def test_intent_add_refuses_an_unknown_concerns_value(isolated_ledger):
    result = _add_intent("odd-intent", "Does it work?", "whatever-the-tool-does")
    assert result.exit_code == 2, result.output
    assert "--concerns must be one of" in result.output


def test_testcase_add_refuses_an_unregistered_intent(isolated_ledger, tmp_path: Path):
    """A dangling intent reference is worse than none -- same rule as
    --grounds, and it must fail before any fixture file is copied."""
    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    result = _add_testcase("orphan-testcase", "no-such-intent", "structural-check", src)
    assert result.exit_code == 2, result.output
    assert "unknown intent" in result.output

    copied = isolated_ledger["fixtures_dir"] / "orphan-testcase" / "input.sysml"
    assert not copied.exists(), "a refused write must not leave a fixture file behind"


def test_posterior_state_intent_with_only_structural_checks_is_refused(
    isolated_ledger, tmp_path: Path
):
    """The live defect this whole element exists for, at the CLI level.

    ledger/testcases.ttl held a structural-check TestCase whose description
    asserted a fact about x+, and recorded `passed` -- while a sibling
    reference-resolution case over the same fixture recorded `failed`.
    Stating the question once makes that mismatch refusable at the gate.
    """
    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    assert (
        _add_intent(
            "resolution-intent",
            "Do two anonymous ':>> items' redefinitions each resolve to the base feature?",
            "posterior-state",
        ).exit_code
        == 0
    )

    result = _add_testcase("weak-testcase", "resolution-intent", "structural-check", src)
    assert result.exit_code == 1, result.output
    assert "IntentMethodAlignmentShape" in result.output

    ledger = load_full_ledger()
    assert (ids.slug_id("testcase", "weak-testcase"), RDF.type, SVT.TestCase) not in ledger


def test_a_method_that_can_establish_the_intent_admits_the_weak_one_alongside(
    isolated_ledger, tmp_path: Path
):
    """The shape constrains the intent, not each TestCase: once a method
    that *can* settle the question exists, a structural-check case under
    the same intent is legitimate -- it contributes real evidence (the
    input was admissible) without being asked to carry the whole claim.
    That coexistence is the arrangement the real ledger is now in.
    """
    src = tmp_path / "input.sysml"
    src.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    assert (
        _add_intent(
            "resolution-intent",
            "Do two anonymous ':>> items' redefinitions each resolve to the base feature?",
            "posterior-state",
        ).exit_code
        == 0
    )

    strong = _add_testcase(
        "strong-testcase",
        "resolution-intent",
        "reference-resolution",
        src,
        ["--resolves", "Usage::c::@0=Lib::Container::items"],
    )
    assert strong.exit_code == 1, "ungrounded resolution facts should still need a citation"
    assert "groundedIn" in strong.output

    # Ground it properly, then the weak sibling becomes admissible too.
    runner.invoke(
        cli_module.app,
        [
            "document", "add", "--id", "fake-doc", "--doc-number", "fake/0000",
            "--title", "Fake Spec", "--local-path", "sources/local/fake.pdf",
            "--sha256", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        ],
    )
    runner.invoke(
        cli_module.app,
        [
            "citation", "add", "--id", "fake-citation", "--document", "fake-doc",
            "--section", "1", "--page", "1", "--quote", "a thing must be a thing",
        ],
    )
    strong = _add_testcase(
        "strong-testcase",
        "resolution-intent",
        "reference-resolution",
        src,
        ["--resolves", "Usage::c::@0=Lib::Container::items", "--grounds", "fake-citation"],
    )
    assert strong.exit_code == 0, strong.output

    weak = _add_testcase("weak-testcase", "resolution-intent", "structural-check", src)
    assert weak.exit_code == 0, weak.output
