"""Adapter protocol.

Every adapter is a plain subprocess/library call against one implementation's
own tool — no LLM anywhere in this path. `svt run` builds a TestCaseSpec from
the ledger, hands it to the adapter registered for the target Implementation,
and gets back a RawResult with the exact command and raw captured output.
Comparison against `expected` happens afterward, in ``compare.py`` — never
inside an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class UnsupportedMethod(Exception):
    """Raised when an implementation's tool has no working mechanism for a
    TestCase's method (an honest, first-class limitation — not guessed at,
    not silently faked). ``svt run`` catches this and records
    earl:inapplicable with the message as earl:info."""


@dataclass(frozen=True)
class ResolutionCheck:
    subject_feature: str
    expected_target: str


@dataclass(frozen=True)
class TestCaseSpec:
    input_files: list[Path]
    method: str
    expected: str | None
    eval_expression: str | None = None
    eval_subject: str | None = None
    events: str | None = None  # method=state-execution: comma-joined event names (the command u)
    resolution_checks: tuple[ResolutionCheck, ...] = ()  # method=reference-resolution


@dataclass(frozen=True)
class RawResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str


class Adapter:
    slug: str = ""

    def run(self, spec: TestCaseSpec) -> RawResult:
        raise NotImplementedError
