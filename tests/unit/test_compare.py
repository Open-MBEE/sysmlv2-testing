"""adapters/compare.py is the only place a verdict is decided — these are
the cases that matter: each method's happy/unhappy path, the `actual`
value it records verbatim, and the rule that an unset ``expected``
mechanically means ``cantTell``, never a guess."""

from adapters.base import RawResult
from adapters.compare import compare


def _result(exit_code=0, stdout="", stderr=""):
    return RawResult(command="cmd", exit_code=exit_code, stdout=stdout, stderr=stderr)


def test_structural_check_clean_matches_expected_clean():
    outcome, actual, _ = compare("structural-check", "clean", _result(exit_code=0))
    assert outcome == "passed"
    assert actual == "clean"


def test_structural_check_violated_but_expected_clean_fails():
    outcome, actual, _ = compare("structural-check", "clean", _result(exit_code=1))
    assert outcome == "failed"
    assert actual == "violated"


def test_structural_check_violated_matches_expected_violated():
    outcome, actual, _ = compare("structural-check", "violated", _result(exit_code=1))
    assert outcome == "passed"
    assert actual == "violated"


def test_constraint_eval_matches_boolean_expected():
    outcome, actual, _ = compare("constraint-eval", "false", _result(stdout="false"))
    assert outcome == "passed"
    assert actual == "false"
    outcome, actual, _ = compare("constraint-eval", "true", _result(stdout="false"))
    assert outcome == "failed"
    assert actual == "false"


def test_state_execution_matches_state_string():
    outcome, actual, _ = compare(
        "state-execution", "dormant,active", _result(stdout="dormant,active")
    )
    assert outcome == "passed"
    assert actual == "dormant,active"
    outcome, actual, _ = compare("state-execution", "dormant", _result(stdout="dormant,active"))
    assert outcome == "failed"


def test_unset_expected_is_mechanically_canttell_but_actual_is_still_recorded():
    outcome, actual, info = compare("structural-check", None, _result(exit_code=1))
    assert outcome == "cantTell"
    assert actual == "violated"
    assert "not yet settled" in info


def test_info_states_expected_and_actual_precisely_not_a_raw_output_dump():
    _, _, info = compare("structural-check", "clean", _result(exit_code=1, stderr="boom"))
    assert "expected='clean'" in info
    assert "actual='violated'" in info
    # the full raw stderr belongs on the Invocation, not squashed into info
    assert "boom" not in info


def test_unknown_method_raises():
    import pytest

    with pytest.raises(ValueError):
        compare("not-a-real-method", "clean", _result())
