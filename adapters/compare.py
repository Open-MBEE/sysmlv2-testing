"""Scripted comparators — the only place a pass/fail/cantTell verdict is
decided. Keyed by TestCase.method. Plain code, deterministic, no LLM.

The full raw stdout/stderr live on the Invocation (see cli.py's run_cmd) --
this module's ``info`` is a short, precise summary of the comparison
itself (what was expected, what was actually computed), not a place to
re-dump the whole captured output.

Each method checks a different fact about the state transition x+ =
f(x, u) an Implementation computes (see AGENTS.md / vocabulary comments):
structural-check checks whether u is even admissible (u in U_x);
constraint-eval/state-execution/reference-resolution each check a
specific fact about the actual x+, given an admissible u.
"""

from __future__ import annotations

from .base import RawResult, TestCaseSpec

# The closed set of outcomes -- mirrors shapes/testrun.shapes.ttl's
# TestResultOutcomeShape sh:in list (that's the SHACL-enforced source of
# truth for the ledger itself; this is the single Python-side copy other
# code should import rather than re-typing the same five strings).
OUTCOMES = ("passed", "failed", "cantTell", "inapplicable", "untested")


def compare(spec: TestCaseSpec, result: RawResult) -> tuple[str, str | None, str]:
    """Return (outcome, actual, info).

    ``outcome`` is one of the five EARL literals. ``actual`` is the bare
    literal value this method's comparator derived from ``result`` --
    recorded verbatim as svt:actual so a reader can see exactly what was
    compared without re-deriving it from raw stdout. ``info`` is a short
    human-readable note.
    """
    if spec.method == "reference-resolution":
        return _compare_resolution(spec, result)

    if spec.method == "structural-check":
        actual = "clean" if result.exit_code == 0 else "violated"
        matches = lambda exp: actual == exp  # noqa: E731
    elif spec.method == "constraint-eval":
        actual = result.stdout.strip().lower()
        matches = lambda exp: actual == exp.strip().lower()  # noqa: E731
    elif spec.method == "state-execution":
        actual = result.stdout.strip()
        matches = lambda exp: actual == exp.strip()  # noqa: E731
    else:
        raise ValueError(f"unknown method: {spec.method!r}")

    # If expected is unset, the outcome is mechanically cantTell -- the
    # correct behavior hasn't been settled (e.g. pending a spec-text
    # read), so this records what happened without declaring a winner;
    # actual is still computed and recorded, just not compared to anything.
    if spec.expected is None:
        return "cantTell", actual, f"actual={actual!r}; expected not yet settled"

    outcome = "passed" if matches(spec.expected) else "failed"
    info = f"expected={spec.expected!r} actual={actual!r}"
    return outcome, actual, info


def _compare_resolution(spec: TestCaseSpec, result: RawResult) -> tuple[str, str | None, str]:
    """reference-resolution checks a *set* of facts about x+, not one
    scalar: for each ResolutionCheck, does subject_feature actually
    resolve to expected_target? Adapters report this as one line per
    check, ``<subjectFeature>\\t<actualTarget>`` (``UNRESOLVED`` when the
    implementation couldn't resolve it), in the same order as
    spec.resolution_checks -- see each adapter's own docstring for its
    exact resolution mechanism (compact-json @id walk, EMF object
    identity, etc; never diagnostics alone)."""
    if not spec.resolution_checks:
        return "cantTell", None, "no svt:checksResolution facts defined for this TestCase"

    actual_by_subject: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        subject, _, target = line.partition("\t")
        actual_by_subject[subject] = target.strip()

    facts: list[str] = []
    all_match = True
    for check in spec.resolution_checks:
        actual_target = actual_by_subject.get(check.subject_feature, "UNRESOLVED")
        ok = actual_target == check.expected_target
        all_match = all_match and ok
        facts.append(f"{check.subject_feature}->{actual_target}")

    actual = "; ".join(facts)
    outcome = "passed" if all_match else "failed"
    info = f"{len(spec.resolution_checks)} resolution check(s), all_match={all_match}"
    return outcome, actual, info
