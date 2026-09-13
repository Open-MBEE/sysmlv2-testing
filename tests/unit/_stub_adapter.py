"""A fake adapters.base.Adapter, used only by test_run_success.py to
exercise `svt run`'s actual success path (adapter dispatch -> compare()
-> a real TestRun/Invocation/TestResult written to the ledger) without
needing a real pinned implementation binary. Never imported by anything
under src/ or adapters/ -- test-only.
"""

from __future__ import annotations

from adapters.base import Adapter, RawResult, TestCaseSpec


class _StubAdapter(Adapter):
    slug = "fake-impl"

    def run(self, spec: TestCaseSpec) -> RawResult:
        return RawResult(
            command="fake-tool check input.sysml",
            exit_code=0,
            stdout="clean",
            stderr="",
        )


ADAPTER = _StubAdapter()
