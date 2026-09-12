"""SHACL gate over the ledger — adapted from cds's core/verify.py, thinned:
no waivers (every shape here is a required-field/closed-vocabulary check,
i.e. effectively T1 already), just conforms + the findings that explain why
not.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyshacl
from rdflib import RDF, Graph
from rdflib.namespace import SH


def _local_name(iri: str) -> str:
    for sep in ("#", "/"):
        if sep in iri:
            iri = iri.rsplit(sep, 1)[-1]
    return iri


@dataclass(frozen=True)
class Finding:
    severity: str  # "Violation" | "Warning" | "Info" (SHACL's own vocabulary)
    rule: str  # the shape's stable name
    focus: str  # the node the shape fired on
    message: str


@dataclass(frozen=True)
class VerifyResult:
    conforms: bool
    findings: tuple[Finding, ...]


def _findings(report: Graph) -> tuple[Finding, ...]:
    out: list[Finding] = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        sev = report.value(result, SH.resultSeverity)
        shape = report.value(result, SH.sourceShape)
        message = report.value(result, SH.resultMessage)
        focus = report.value(result, SH.focusNode)
        out.append(
            Finding(
                severity=_local_name(str(sev)) if sev is not None else "Violation",
                rule=_local_name(str(shape)) if shape is not None else "",
                focus=str(focus) if focus is not None else "",
                message=str(message) if message is not None else "",
            )
        )
    return tuple(sorted(out, key=lambda f: (f.severity, f.rule, f.focus)))


def verify(data: Graph, shapes: Graph) -> VerifyResult:
    conforms, report, _text = pyshacl.validate(
        data,
        shacl_graph=shapes,
        advanced=True,
        inference="none",
        allow_infos=True,
        allow_warnings=True,
    )
    return VerifyResult(conforms=bool(conforms), findings=_findings(report))
