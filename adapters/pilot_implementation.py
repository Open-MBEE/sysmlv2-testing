"""Adapter for Systems-Modeling/SysML-v2-Pilot-Implementation.

Drives the headless `org.omg.sysml.interactive.SysMLInteractive` engine via
a tiny Java shim (adapters/pilot_glue/Main.java) — no Eclipse, no Jupyter
protocol. Supports structural-check and reference-resolution; the Pilot's
interactive engine has no constraint-evaluation or state-execution API
reachable this way, so those methods are honestly unsupported.

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


def _classpath() -> str:
    classpath = os.environ.get("PILOT_GLUE_CLASSPATH")
    if not classpath:
        raise RuntimeError("PILOT_GLUE_CLASSPATH must be set (see toolchain/get-pilot-jar.sh)")
    return classpath


class PilotAdapter(Adapter):
    slug = "pilot-implementation"

    def run(self, spec: TestCaseSpec) -> RawResult:
        if spec.method == "structural-check":
            return self._structural_check(spec)
        if spec.method == "reference-resolution":
            return self._reference_resolution(spec)
        raise UnsupportedMethod(
            f"pilot-implementation adapter has no handler for method {spec.method!r} "
            "(the Pilot's SysMLInteractive engine exposes parse/validate and "
            "resolve()-based reference resolution; no constraint-eval or "
            "state-execution API reachable this way)"
        )

    def _structural_check(self, spec: TestCaseSpec) -> RawResult:
        cmd = ["java", "-cp", _classpath(), "svt.Main", *[str(p) for p in spec.input_files]]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return RawResult(
            command=" ".join(cmd), exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )

    def _reference_resolution(self, spec: TestCaseSpec) -> RawResult:
        """svt.Main --redef <container> enumerates one container's owned
        Redefinitions at a time (real EMF object identity via
        Redefinition.getRedefinedFeature() -- see Main.java); group our
        subject locators ("Container::@i") by their container and issue
        one glue invocation per distinct container."""
        classpath = _classpath()
        containers = sorted({c.subject_feature.rsplit("::@", 1)[0] for c in spec.resolution_checks})
        facts: dict[str, str] = {}
        command = ""
        stderr_parts: list[str] = []
        exit_code = 0
        for container in containers:
            cmd = [
                "java",
                "-cp",
                classpath,
                "svt.Main",
                "--redef",
                container,
                *[str(p) for p in spec.input_files],
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            command = " ".join(cmd)  # last command wins if there were several; all are equivalent shape
            exit_code = exit_code or proc.returncode
            stderr_parts.append(proc.stderr)
            for line in proc.stdout.splitlines():
                if "\t" in line:
                    subject, _, target = line.partition("\t")
                    facts[subject] = target

        lines = [
            f"{c.subject_feature}\t{facts.get(c.subject_feature, 'UNRESOLVED:not-found')}"
            for c in spec.resolution_checks
        ]
        return RawResult(
            command=command,
            exit_code=exit_code,
            stdout="\n".join(lines) + ("\n" if lines else ""),
            stderr="\n".join(stderr_parts),
        )


ADAPTER = PilotAdapter()
