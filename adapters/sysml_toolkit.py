"""Adapter for Open-MBEE/sysml-toolkit's `sysmlv2` CLI.

Env vars (no hidden defaults — an unset SYSMLV2_LIB_DIR is a hard error,
matching BrandFootprintML's own harness/gate.sh discipline):
  SYSMLV2_BIN      path to the pinned `sysmlv2` binary (default: "sysmlv2" on PATH)
  SYSMLV2_LIB_DIR  path to an OMG SysML v2 standard library directory
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .base import Adapter, RawResult, TestCaseSpec, UnsupportedMethod


def _binary() -> str:
    return os.environ.get("SYSMLV2_BIN", "sysmlv2")


def _lib_dir() -> str:
    lib_dir = os.environ.get("SYSMLV2_LIB_DIR")
    if not lib_dir:
        raise RuntimeError(
            "SYSMLV2_LIB_DIR must be set to an OMG SysML v2 standard "
            "library directory (e.g. a SysML-v2-Release checkout's "
            "sysml.library/)"
        )
    return lib_dir


def _order_list(container_el: dict) -> list[str | None]:
    return [
        m.get("@id")
        for m in (container_el.get("ownedFeatureMembership") or container_el.get("ownedRelationship") or [])
    ]


def _container_of(by_id: dict, element_id: str) -> tuple[str | None, str | None]:
    """(owner element id, owning-membership id) for ``element_id``, or
    (None, None) at the root."""
    e = by_id.get(element_id)
    rel_ref = e.get("owningRelationship") if e else None
    if not rel_ref or "@id" not in rel_ref:
        return None, None
    rel = by_id.get(rel_ref["@id"])
    owner_ref = rel.get("owningRelatedElement") if rel else None
    return (owner_ref["@id"] if owner_ref and "@id" in owner_ref else None), rel_ref["@id"]


def _qualified_name(by_id: dict, element_id: str | None, _depth: int = 0) -> str | None:
    """Reconstruct a `::`-qualified name by walking ownership -- compact-json
    doesn't carry a precomputed qualifiedName field. An element with no
    declaredName (an anonymous redefinition, e.g. from a bare ``ref :>>
    items = a;``) is labeled by its position in its owner's own
    ownedFeatureMembership list, e.g. ``UsageTwo::c::@0``."""
    if element_id is None or _depth > 50:  # depth guard against any cycle
        return None
    e = by_id.get(element_id)
    if e is None:
        return None
    name = e.get("declaredName")
    container_id, membership_id = _container_of(by_id, element_id)
    if container_id is None:
        return name  # root: no container to index against
    parent_qn = _qualified_name(by_id, container_id, _depth + 1)
    if name:
        label = name
    else:
        order_list = _order_list(by_id.get(container_id, {}))
        idx = order_list.index(membership_id) if membership_id in order_list else "?"
        label = f"@{idx}"
    return f"{parent_qn}::{label}" if parent_qn else label


def _describe_ref(by_id: dict, ref: dict) -> str:
    if "@ref" in ref:
        return f"UNRESOLVED:{ref['@ref']}"
    return _qualified_name(by_id, ref["@id"]) or "UNRESOLVED:unnamed"


def _resolution_facts(compact_json_elements: list[dict]) -> dict[str, str]:
    """Every explicit Redefinition's subject locator -> its actual resolved
    target locator, e.g. {"UsageTwo::c::@0": "Lib::Container::items"}."""
    by_id = {e["@id"]: e for e in compact_json_elements if "@id" in e}
    redefs = [
        e for e in compact_json_elements if e.get("@type") == "Redefinition" and not e.get("isImplied")
    ]
    by_container: dict[str | None, list[dict]] = {}
    for r in redefs:
        container_id, _ = _container_of(by_id, r["redefiningFeature"]["@id"])
        by_container.setdefault(container_id, []).append(r)

    facts: dict[str, str] = {}
    for container_id, entries in by_container.items():
        container_qn = _qualified_name(by_id, container_id)
        order_list = _order_list(by_id.get(container_id, {}))

        def _position(r: dict) -> int:
            _, mid = _container_of(by_id, r["redefiningFeature"]["@id"])
            return order_list.index(mid) if mid in order_list else 999

        entries.sort(key=_position)
        for i, r in enumerate(entries):
            facts[f"{container_qn}::@{i}"] = _describe_ref(by_id, r["redefinedFeature"])
    return facts


class SysmlToolkitAdapter(Adapter):
    slug = "sysml-toolkit"

    def run(self, spec: TestCaseSpec) -> RawResult:
        if spec.method == "structural-check":
            return self._structural_check(spec)
        if spec.method == "reference-resolution":
            return self._reference_resolution(spec)
        # sysml-toolkit's `verify`/`query` evaluate a constraint at its
        # declaration site only, not a specific usage's redefined
        # bindings (BrandFootprintML ISSUES-PROPOSED.md #1) -- there is
        # no working constraint-eval/state-execution path through this
        # tool. Recorded honestly, not faked.
        raise UnsupportedMethod(
            f"sysml-toolkit has no working {spec.method} mechanism "
            "(see ISSUES-PROPOSED.md #1: verify/query evaluate a "
            "constraint's declaration-site defaults, not a usage's "
            "actual bindings)"
        )

    def _structural_check(self, spec: TestCaseSpec) -> RawResult:
        cmd = [
            _binary(),
            "check",
            "--lib",
            _lib_dir(),
            "--strict",
            *[str(p) for p in spec.input_files],
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return RawResult(
            command=" ".join(cmd), exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def _reference_resolution(self, spec: TestCaseSpec) -> RawResult:
        """Convert to compact-json (KerML 10.4) and walk the real
        Redefinition edges by @id -- confirmed the project's own idiomatic
        test technique (its IDS.md documents the @id stability contract
        this relies on; its own tests/json.rs does the identical walk).
        Never trusts exit code/diagnostics alone for this method."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "model.json"
            cmd = [
                _binary(),
                "convert",
                "--lib",
                _lib_dir(),
                "--to",
                "compact-json",
                *[str(p) for p in spec.input_files],
                "-o",
                str(out_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            command_str = " ".join(cmd)
            if not out_path.exists():
                return RawResult(
                    command=command_str, exit_code=proc.returncode, stdout="", stderr=proc.stderr
                )
            elements = json.loads(out_path.read_text())

        facts = _resolution_facts(elements)
        lines = [
            f"{check.subject_feature}\t{facts.get(check.subject_feature, 'UNRESOLVED:not-found')}"
            for check in spec.resolution_checks
        ]
        return RawResult(
            command=command_str,
            exit_code=proc.returncode,
            stdout="\n".join(lines) + ("\n" if lines else ""),
            stderr=proc.stderr,
        )


ADAPTER = SysmlToolkitAdapter()
