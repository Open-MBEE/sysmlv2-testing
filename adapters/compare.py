"""Scripted comparators — the only place a pass/fail/cantTell verdict is
decided. Keyed by TestCase.method. Plain code, deterministic, no LLM.

The full raw stdout/stderr live on the Invocation (see cli.py's run_cmd) --
this module's ``info`` is a short, precise summary of the comparison
itself (what was expected, what was actually computed), not a place to
re-dump the whole captured output.
"""

from __future__ import annotations

from .base import RawResult

_OUTCOMES = ("passed", "failed", "cantTell", "inapplicable", "untested")


def compare(method: str, expected: str | None, result: RawResult) -> tuple[str, str | None, str]:
    """Return (outcome, actual, info).

    ``outcome`` is one of the five EARL literals. ``actual`` is the bare
    literal value this method's comparator derived from ``result`` (e.g.
    "clean"/"violated", "true"/"false", a joined state list) -- recorded
    verbatim as svt:actual so a reader can see exactly what was compared
    without re-deriving it from raw stdout. ``info`` is a short
    human-readable note.

    If ``expected`` is unset, the outcome is mechanically ``cantTell`` —
    the correct behavior hasn't been settled (e.g. pending a spec-text
    read), so this records what happened without declaring a winner;
    ``actual`` is still computed and recorded, just not compared to
    anything.
    """
    if method == "structural-check":
        actual = "clean" if result.exit_code == 0 else "violated"
        matches = lambda exp: actual == exp  # noqa: E731
    elif method == "constraint-eval":
        actual = result.stdout.strip().lower()
        matches = lambda exp: actual == exp.strip().lower()  # noqa: E731
    elif method == "state-execution":
        actual = result.stdout.strip()
        matches = lambda exp: actual == exp.strip()  # noqa: E731
    else:
        raise ValueError(f"unknown method: {method!r}")

    if expected is None:
        return "cantTell", actual, f"actual={actual!r}; expected not yet settled"

    outcome = "passed" if matches(expected) else "failed"
    info = f"expected={expected!r} actual={actual!r}"
    return outcome, actual, info
