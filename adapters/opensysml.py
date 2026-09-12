"""Adapter for Open-MBEE/OpenSysML, via its Python client `opensysml`.

The server version is pinned by OPENSYSML_VERSION (default matches the
version BrandFootprintML's own fixtures were exercised against, "v0.4.0")
— never "whatever's installed." Each call opens a fresh, version-pinned
connection and closes it when done. No LLM anywhere in this path.
"""

from __future__ import annotations

import os

from .base import Adapter, RawResult, TestCaseSpec, UnsupportedMethod

DEFAULT_VERSION = "v0.4.0"


class OpenSysMLAdapter(Adapter):
    slug = "opensysml"

    def _connect(self):
        import opensysml
        import opensysml.binary

        version = os.environ.get("OPENSYSML_VERSION", DEFAULT_VERSION)
        opensysml.binary.ensure_binary(version=version)
        return opensysml.connect(version=version)

    def run(self, spec: TestCaseSpec) -> RawResult:
        content = "\n".join(p.read_text() for p in spec.input_files)
        conn = self._connect()
        try:
            if spec.method == "structural-check":
                return self._structural_check(conn, content)
            if spec.method == "constraint-eval":
                return self._constraint_eval(conn, content, spec)
            if spec.method == "state-execution":
                return self._state_execution(conn, content, spec)
            raise UnsupportedMethod(
                f"opensysml adapter has no handler for method {spec.method!r}"
            )
        finally:
            conn.close()

    def _structural_check(self, conn, content: str) -> RawResult:
        command = "Connection.load_from_content(<input files>, strict=False)"
        model = conn.load_from_content(content, strict=False)
        if model.ok:
            return RawResult(command=command, exit_code=0, stdout="clean", stderr="")
        # Full precise detail the client actually returns per diagnostic --
        # not just severity+message, so the captured stderr is as precise
        # as the tool's own Diagnostic object, not a summary of it.
        messages = "\n".join(
            f"{d.severity} {d.file}:{d.start_line}:{d.start_column}-"
            f"{d.end_line}:{d.end_column}: {d.message}"
            for d in model.diagnostics
        )
        return RawResult(command=command, exit_code=1, stdout="", stderr=messages)

    def _constraint_eval(self, conn, content: str, spec: TestCaseSpec) -> RawResult:
        if not spec.eval_expression or not spec.eval_subject:
            raise UnsupportedMethod(
                "constraint-eval requires --eval-expression and --eval-subject "
                "on the TestCase"
            )
        model = conn.load_from_content(content, strict=False)
        command = f"Model.eval({spec.eval_expression!r}, subject={spec.eval_subject!r})"
        value = model.eval(spec.eval_expression, subject=spec.eval_subject)
        return RawResult(command=command, exit_code=0, stdout=str(bool(value)).lower(), stderr="")

    def _state_execution(self, conn, content: str, spec: TestCaseSpec) -> RawResult:
        if not spec.eval_subject:
            raise UnsupportedMethod(
                "state-execution requires --eval-subject (the state machine's FQN) "
                "on the TestCase"
            )
        model = conn.load_from_content(content, strict=False)
        command = f"Model.execute_state({spec.eval_subject!r})"
        result = model.execute_state(spec.eval_subject)
        return RawResult(
            command=command,
            exit_code=0,
            stdout=",".join(result.get("states_visited", [])),
            stderr="",
        )


ADAPTER = OpenSysMLAdapter()
