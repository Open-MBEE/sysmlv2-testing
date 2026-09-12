"""Adapter for Open-MBEE/sysml-toolkit's `sysmlv2` CLI.

Env vars (no hidden defaults — an unset SYSMLV2_LIB_DIR is a hard error,
matching BrandFootprintML's own harness/gate.sh discipline):
  SYSMLV2_BIN      path to the pinned `sysmlv2` binary (default: "sysmlv2" on PATH)
  SYSMLV2_LIB_DIR  path to an OMG SysML v2 standard library directory
"""

from __future__ import annotations

import os
import subprocess

from .base import Adapter, RawResult, TestCaseSpec, UnsupportedMethod


class SysmlToolkitAdapter(Adapter):
    slug = "sysml-toolkit"

    def run(self, spec: TestCaseSpec) -> RawResult:
        if spec.method != "structural-check":
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
        binary = os.environ.get("SYSMLV2_BIN", "sysmlv2")
        lib_dir = os.environ.get("SYSMLV2_LIB_DIR")
        if not lib_dir:
            raise RuntimeError(
                "SYSMLV2_LIB_DIR must be set to an OMG SysML v2 standard "
                "library directory (e.g. a SysML-v2-Release checkout's "
                "sysml.library/)"
            )
        cmd = [binary, "check", "--lib", lib_dir, "--strict", *[str(p) for p in spec.input_files]]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return RawResult(
            command=" ".join(cmd),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


ADAPTER = SysmlToolkitAdapter()
