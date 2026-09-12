"""adapters/compare.py is the only place a verdict is decided — these are
the cases that matter: each method's happy/unhappy path, and the rule that
an unset ``expected`` mechanically means ``cantTell``, never a guess."""

from adapters.base import RawResult
from adapters.compare import compare


def _result(exit_code=0, stdout="", stderr=""):
    return RawResult(command="cmd", exit_code=exit_code, stdout=stdout, stderr=stderr)


def test_structural_check_clean_matches_expected_clean():
    outcome, _ = compare("structural-check", "clean", _result(exit_code=0))
    assert outcome == "passed"


def test_structural_check_violated_but_expected_clean_fails():
    outcome, _ = compare("structural-check", "clean", _result(exit_code=1))
    assert outcome == "failed"


def test_structural_check_violated_matches_expected_violated():
    outcome, _ = compare("structural-check", "violated", _result(exit_code=1))
    assert outcome == "passed"


def test_constraint_eval_matches_boolean_expected():
    outcome, _ = compare("constraint-eval", "false", _result(stdout="false"))
    assert outcome == "passed"
    outcome, _ = compare("constraint-eval", "true", _result(stdout="false"))
    assert outcome == "failed"


def test_state_execution_matches_state_string():
    outcome, _ = compare("state-execution", "dormant,active", _result(stdout="dormant,active"))
    assert outcome == "passed"
    outcome, _ = compare("state-execution", "dormant", _result(stdout="dormant,active"))
    assert outcome == "failed"


def test_unset_expected_is_mechanically_canttell_regardless_of_method_or_output():
    outcome, info = compare("structural-check", None, _result(exit_code=1, stderr="boom"))
    assert outcome == "cantTell"
    assert "boom" in info


def test_unknown_method_raises():
    import pytest

    with pytest.raises(ValueError):
        compare("not-a-real-method", "clean", _result())
