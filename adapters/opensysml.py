"""Adapter for Open-MBEE/OpenSysML, via its Python client `opensysml`.

The server version is pinned by OPENSYSML_VERSION (default matches the
version BrandFootprintML's own fixtures were exercised against, "v0.4.0")
— never "whatever's installed." Each call opens a fresh, version-pinned
connection and closes it when done. No LLM anywhere in this path.
"""

from __future__ import annotations

import os

from .base import Adapter, RawResult, TestCaseSpec, UnsupportedMethod, with_fingerprint

DEFAULT_VERSION = "v0.4.0"


def _requested_version() -> str:
    """OPENSYSML_VERSION, then OPENSYSML_GRPC_VERSION, then the default.

    The second is the upstream client's own variable. This adapter passes a
    version explicitly to ensure_binary(), which overrides it -- so without
    this fallback, somebody pinning the server the documented upstream way
    would be silently ignored and get a different binary than they asked
    for, with a plausible-looking result recorded against it.
    """
    return (
        os.environ.get("OPENSYSML_VERSION")
        or os.environ.get("OPENSYSML_GRPC_VERSION")
        or DEFAULT_VERSION
    )


def _tool_fingerprint() -> tuple[str | None, str | None]:
    """What the client says it actually installed: the release version and
    the sha256 of that binary, straight from its own cache metadata (it
    verifies the download against upstream's pinned digests, so this is
    upstream's digest and not merely a hash of whatever is on disk)."""
    import opensysml.binary

    try:
        meta = opensysml.binary.read_metadata() or {}
    except Exception:  # noqa: BLE001 - never fail a run over provenance metadata
        return None, None
    return meta.get("version"), meta.get("sha256")


class OpenSysMLAdapter(Adapter):
    slug = "opensysml"

    def _connect(self):
        import opensysml
        import opensysml.binary

        version = _requested_version()
        opensysml.binary.ensure_binary(version=version)
        return opensysml.connect(version=version)

    def run(self, spec: TestCaseSpec) -> RawResult:
        content = "\n".join(p.read_text() for p in spec.input_files)
        conn = self._connect()
        version, digest = _tool_fingerprint()
        try:
            if spec.method == "structural-check":
                return with_fingerprint(self._structural_check(conn, content), version, digest)
            if spec.method == "constraint-eval":
                return with_fingerprint(
                    self._constraint_eval(conn, content, spec), version, digest
                )
            if spec.method == "state-execution":
                return with_fingerprint(
                    self._state_execution(conn, content, spec), version, digest
                )
            if spec.method == "reference-resolution":
                # Confirmed two ways, not one, not a client-wrapping gap:
                # (1) the wire protocol's only identity field (SymbolInfo.id
                # / Specialization.target_id, per sysml_pb2.pyi) *is* the
                # collision-prone qualified-name string -- both anonymous
                # `ref :>> items = a/b;` redefinitions under the same
                # container get the identical synthesized id, and
                # GetSymbol on it 404s; (2) model.convert('turtle') *does*
                # assign distinguishable per-element URIs to the two
                # siblings (positional @0/@1 naming), but its
                # `sysml:redefines` predicate is a bare declared-name
                # string literal ("items"), not a link to the resolved
                # target element -- so even the richer export can't
                # answer "resolves to which one." A real upstream gap,
                # not engineered around client-side.
                raise UnsupportedMethod(
                    "opensysml has no way to check reference-resolution facts for "
                    "anonymous features: its Symbol/Query wire protocol's only "
                    "identity field is the same colliding qualified-name string "
                    "(confirmed via sysml_pb2.pyi), and its to_turtle() export's "
                    "sysml:redefines predicate is a bare name string, not a link "
                    "to the resolved target -- worth filing upstream"
                )
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
        # spec.events is the command u: an ordered, comma-joined event
        # sequence to feed the state machine (absent = the zero-event
        # default -- does it settle correctly with nothing to react to).
        events = [e.strip() for e in spec.events.split(",") if e.strip()] if spec.events else None
        model = conn.load_from_content(content, strict=False)
        command = f"Model.execute_state({spec.eval_subject!r}, events={events!r})"
        result = model.execute_state(spec.eval_subject, events=events)
        return RawResult(
            command=command,
            exit_code=0,
            stdout=",".join(result.get("states_visited", [])),
            stderr="",
        )


ADAPTER = OpenSysMLAdapter()
