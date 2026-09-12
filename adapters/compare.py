"""Scripted comparators — the only place a pass/fail/cantTell verdict is
decided. Keyed by TestCase.method. Plain code, deterministic, no LLM.
"""

from __future__ import annotations

from .base import RawResult

_OUTCOMES = ("passed", "failed", "cantTell", "inapplicable", "untested")


def compare(method: str, expected: str | None, result: RawResult) -> tuple[str, str]:
    """Return (outcome, info). ``outcome`` is one of the five EARL literals.

    If ``expected`` is unset, the outcome is mechanically ``cantTell`` — the
    correct behavior hasn't been settled (e.g. pending a spec-text read), so
    this records what happened without declaring a winner.
    """
    info = f"exit_code={result.exit_code}\nstdout: {result.stdout}\nstderr: {result.stderr}"

    if expected is None:
        return "cantTell", info

    if method == "structural-check":
        actual = "clean" if result.exit_code == 0 else "violated"
        return ("passed" if actual == expected else "failed"), info

    if method == "constraint-eval":
        actual = result.stdout.strip().lower()
        return ("passed" if actual == expected.strip().lower() else "failed"), info

    if method == "state-execution":
        actual = result.stdout.strip()
        return ("passed" if actual == expected.strip() else "failed"), info

    raise ValueError(f"unknown method: {method!r}")
