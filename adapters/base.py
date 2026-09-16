"""Adapter protocol.

Every adapter is a plain subprocess/library call against one implementation's
own tool — no LLM anywhere in this path. `svt run` builds a TestCaseSpec from
the ledger, hands it to the adapter registered for the target Implementation,
and gets back a RawResult with the exact command and raw captured output.
Comparison against `expected` happens afterward, in ``compare.py`` — never
inside an adapter.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
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
    # Not a pytest test class -- the name just collides with pytest's
    # default `Test*` discovery pattern. Silences the collection warning
    # this triggers on every test run.
    __test__ = False

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
    # What actually ran, as opposed to what the ledger is about to claim ran.
    # `svt run --version` never reaches an adapter -- each picks its tool from
    # the environment -- so without these a TestRun's earl:subject is a label
    # nothing checks. Optional with defaults so an adapter that cannot
    # determine them still works; `svt run` records whatever it gets and
    # refuses when a digest contradicts the target Version's artifactDigest.
    tool_version: str | None = None
    tool_digest: str | None = None


def with_fingerprint(result: RawResult, version: str | None, digest: str | None) -> RawResult:
    """Attach what actually ran to a result an adapter already built.

    Applied once at dispatch rather than at each RawResult construction
    site, so a new method handler cannot forget it and quietly produce a
    run with no provenance."""
    return replace(result, tool_version=version, tool_digest=digest)


def digest_of(path: Path) -> str | None:
    """sha256 of an executable/jar, cached by (path, mtime, size): the Pilot
    jar is ~137 MB and would otherwise be re-hashed on every invocation."""
    try:
        st = path.stat()
    except OSError:
        return None
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key not in _DIGEST_CACHE:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        _DIGEST_CACHE[key] = h.hexdigest()
    return _DIGEST_CACHE[key]


_DIGEST_CACHE: dict[tuple[str, int, int], str] = {}


class Adapter:
    slug: str = ""

    def run(self, spec: TestCaseSpec) -> RawResult:
        raise NotImplementedError
