"""Adapter for Systems-Modeling/SysML-v2-Pilot-Implementation.

Drives the headless `org.omg.sysml.interactive.SysMLInteractive` engine via
a tiny Java shim (adapters/pilot_glue/Main.java) — no Eclipse, no Jupyter
protocol. Only structural-check is supported: the Pilot's interactive
engine reports parse/validation issues, not constraint evaluation or state
execution.

Env:
  PILOT_GLUE_CLASSPATH   the built interactive-all.jar plus the compiled
                         svt.Main glue class, ":"-joined (see
                         toolchain/get-pilot-jar.sh, which builds and
                         prints this)
  SYSML_LIBRARY_DIR      path to a sysml.library directory (the Pilot
                         repo's own, or an equivalent OMG stdlib checkout)
                         -- forwarded to the glue process unchanged
"""

from __future__ import annotations

import os
import subprocess

from .base import Adapter, RawResult, TestCaseSpec, UnsupportedMethod


class PilotAdapter(Adapter):
    slug = "pilot-implementation"

    def run(self, spec: TestCaseSpec) -> RawResult:
        if spec.method != "structural-check":
            raise UnsupportedMethod(
                f"pilot-implementation adapter only supports structural-check "
                f"(got {spec.method!r})"
            )
        classpath = os.environ.get("PILOT_GLUE_CLASSPATH")
        if not classpath:
            raise RuntimeError(
                "PILOT_GLUE_CLASSPATH must be set (see toolchain/get-pilot-jar.sh)"
            )
        cmd = ["java", "-cp", classpath, "svt.Main", *[str(p) for p in spec.input_files]]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return RawResult(
            command=" ".join(cmd),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


ADAPTER = PilotAdapter()
