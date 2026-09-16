"""svt run must refuse an unvalidated TestCase outright -- being SHACL-valid
RDF is not the same thing as a human having confirmed the claim against the
spec (see AGENTS.md's "Construction vs. validation"). This is the literal
enforcement of that gate, not just documentation of the rule.

This used to find an unvalidated TestCase by scanning the real ledger,
which worked only while some seeded TestCase remained unvalidated. Every
one is now validated, so that approach fails -- as the old helper's own
assertion message predicted it would ("if every TestCase now has a
Validation record, this test needs a dedicated unvalidated fixture
instead"). It builds its own unvalidated TestCase in an isolated ledger
now: the gate is a property of the code, and a test of it should not go
red because a human did the validating work the gate exists to require.
"""

from typer.testing import CliRunner

from sysmlv2_testing.cli import app

from conftest import FAKE_COMMIT, FAKE_IMPLEMENTATION, FAKE_TESTCASE

runner = CliRunner()


def test_run_refuses_an_unvalidated_testcase(isolated_ledger):
    """The isolated ledger's TestCase deliberately has no svt:Validation."""
    result = runner.invoke(
        app,
        ["run", "--testcase", FAKE_TESTCASE,
         "--implementation", FAKE_IMPLEMENTATION, "--version", FAKE_COMMIT],
    )
    assert result.exit_code == 2, result.output
    assert "no svt:Validation record" in result.output
    assert f"svt testcase validate --id {FAKE_TESTCASE}" in result.output


def test_the_gate_fires_before_adapter_dispatch(isolated_ledger):
    """FAKE_IMPLEMENTATION has no registered adapter, so if the validation
    gate ever moved below adapter lookup this would still exit 2 -- but
    with a different message. Pins the ordering, not just the exit code."""
    result = runner.invoke(
        app,
        ["run", "--testcase", FAKE_TESTCASE,
         "--implementation", FAKE_IMPLEMENTATION, "--version", FAKE_COMMIT],
    )
    assert "no svt:Validation record" in result.output
    assert "no adapter registered" not in result.output


def test_run_proceeds_past_the_gate_once_a_validation_exists(isolated_ledger):
    """The complement: the gate must not be unconditional. After a real
    `testcase validate`, `svt run` gets far enough to fail on the *next*
    thing (no adapter for the fake implementation) instead of on the gate."""
    assert runner.invoke(
        app,
        ["testcase", "validate", "--id", FAKE_TESTCASE, "--by", "Test Human"],
    ).exit_code == 0

    # run_cmd checks fixture files before adapter dispatch, so without this
    # the run would stop at "missing fixture files" and never reach the
    # lookup this test is about.
    fixture = isolated_ledger["fixtures_dir"] / FAKE_TESTCASE / "input.sysml"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text("package Example { part def Thing; }\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["run", "--testcase", FAKE_TESTCASE,
         "--implementation", FAKE_IMPLEMENTATION, "--version", FAKE_COMMIT],
    )
    assert "no svt:Validation record" not in result.output
    assert "no adapter registered" in result.output


def test_validate_refuses_llm_flavored_by_names(isolated_ledger):
    for bad_name in ("claude", "AI", "llm", "Agent"):
        result = runner.invoke(
            app,
            ["testcase", "validate", "--id", FAKE_TESTCASE, "--by", bad_name],
        )
        assert result.exit_code == 2, (bad_name, result.output)
        assert "not a human" in result.output
