"""adapters/compare.py is the only place a verdict is decided — these are
the cases that matter: each method's happy/unhappy path, the `actual`
value it records verbatim, and the rule that an unset ``expected``
mechanically means ``cantTell``, never a guess."""

from adapters.base import RawResult, ResolutionCheck, TestCaseSpec
from adapters.compare import compare


def _spec(method="structural-check", expected=None, **kwargs) -> TestCaseSpec:
    return TestCaseSpec(input_files=[], method=method, expected=expected, **kwargs)


def _result(exit_code=0, stdout="", stderr=""):
    return RawResult(command="cmd", exit_code=exit_code, stdout=stdout, stderr=stderr)


def test_structural_check_clean_matches_expected_clean():
    outcome, actual, _ = compare(_spec(expected="clean"), _result(exit_code=0))
    assert outcome == "passed"
    assert actual == "clean"


def test_structural_check_violated_but_expected_clean_fails():
    outcome, actual, _ = compare(_spec(expected="clean"), _result(exit_code=1))
    assert outcome == "failed"
    assert actual == "violated"


def test_structural_check_violated_matches_expected_violated():
    outcome, actual, _ = compare(_spec(expected="violated"), _result(exit_code=1))
    assert outcome == "passed"
    assert actual == "violated"


def test_constraint_eval_matches_boolean_expected():
    spec = _spec(method="constraint-eval", expected="false")
    outcome, actual, _ = compare(spec, _result(stdout="false"))
    assert outcome == "passed"
    assert actual == "false"
    outcome, actual, _ = compare(_spec(method="constraint-eval", expected="true"), _result(stdout="false"))
    assert outcome == "failed"
    assert actual == "false"


def test_state_execution_matches_state_string():
    spec = _spec(method="state-execution", expected="dormant,active")
    outcome, actual, _ = compare(spec, _result(stdout="dormant,active"))
    assert outcome == "passed"
    assert actual == "dormant,active"
    outcome, actual, _ = compare(
        _spec(method="state-execution", expected="dormant"), _result(stdout="dormant,active")
    )
    assert outcome == "failed"


def test_unset_expected_is_mechanically_canttell_but_actual_is_still_recorded():
    outcome, actual, info = compare(_spec(expected=None), _result(exit_code=1))
    assert outcome == "cantTell"
    assert actual == "violated"
    assert "not yet settled" in info


def test_info_states_expected_and_actual_precisely_not_a_raw_output_dump():
    _, _, info = compare(_spec(expected="clean"), _result(exit_code=1, stderr="boom"))
    assert "expected='clean'" in info
    assert "actual='violated'" in info
    # the full raw stderr belongs on the Invocation, not squashed into info
    assert "boom" not in info


def test_unknown_method_raises():
    import pytest

    with pytest.raises(ValueError):
        compare(_spec(method="not-a-real-method", expected="clean"), _result())


def test_reference_resolution_passes_when_every_check_matches():
    spec = _spec(
        method="reference-resolution",
        resolution_checks=(
            ResolutionCheck("UsageTwo::c::@0", "Lib::Container::items"),
            ResolutionCheck("UsageTwo::c::@1", "Lib::Container::items"),
        ),
    )
    stdout = "UsageTwo::c::@0\tLib::Container::items\nUsageTwo::c::@1\tLib::Container::items\n"
    outcome, actual, info = compare(spec, _result(stdout=stdout))
    assert outcome == "passed"
    assert "Lib::Container::items" in actual
    assert "all_match=True" in info


def test_reference_resolution_fails_on_cross_wired_target():
    """The exact bug that motivated this method: two redefinitions
    resolving to each other instead of the base feature."""
    spec = _spec(
        method="reference-resolution",
        resolution_checks=(
            ResolutionCheck("UsageTwo::c::@0", "Lib::Container::items"),
            ResolutionCheck("UsageTwo::c::@1", "Lib::Container::items"),
        ),
    )
    stdout = "UsageTwo::c::@0\tUsageTwo::c::@1\nUsageTwo::c::@1\tUsageTwo::c::@0\n"
    outcome, actual, info = compare(spec, _result(stdout=stdout))
    assert outcome == "failed"
    assert "all_match=False" in info


def test_reference_resolution_with_no_checks_is_canttell():
    outcome, actual, info = compare(_spec(method="reference-resolution"), _result())
    assert outcome == "cantTell"
    assert actual is None


def test_reference_resolution_missing_line_is_unresolved_not_a_crash():
    spec = _spec(
        method="reference-resolution",
        resolution_checks=(ResolutionCheck("X", "Y"),),
    )
    outcome, actual, _ = compare(spec, _result(stdout=""))
    assert outcome == "failed"
    assert "UNRESOLVED" in actual
