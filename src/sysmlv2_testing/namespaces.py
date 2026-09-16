"""Namespaces and repo-relative paths, in one place so nothing drifts."""

from __future__ import annotations

from pathlib import Path

from rdflib import Namespace

SVT = Namespace("https://w3id.org/sysmlv2-testing#")
SVTID = Namespace("https://w3id.org/sysmlv2-testing/id/")
EARL = Namespace("http://www.w3.org/ns/earl#")
PROV = Namespace("http://www.w3.org/ns/prov#")

# Closed vocabularies that must read identically in the SHACL shapes and in
# the code that writes them -- kept here for the same reason the namespaces
# are: one place, so nothing drifts.
METHODS = ("structural-check", "constraint-eval", "state-execution", "reference-resolution")
CONCERNS = ("admissibility", "posterior-state")

# The methods that establish a fact about the posterior state x+, as opposed
# to merely whether the command u was admissible. This split is what makes a
# svt:TestIntent's svt:concerns checkable against a realizing TestCase's
# svt:method -- see shapes/intent.shapes.ttl's IntentMethodAlignmentShape,
# which encodes the same partition in SPARQL. Change one, change both.
POSTERIOR_STATE_METHODS = ("constraint-eval", "state-execution", "reference-resolution")

PREFIXES: dict[str, str] = {
    "svt": str(SVT),
    "svtid": str(SVTID),
    "earl": str(EARL),
    "prov": str(PROV),
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
}

# src/sysmlv2_testing/namespaces.py -> src/sysmlv2_testing -> src -> repo root
ROOT = Path(__file__).resolve().parents[2]
VOCABULARY_DIR = ROOT / "vocabulary"
SHAPES_DIR = ROOT / "shapes"
SOURCES_DIR = ROOT / "sources"
LEDGER_DIR = ROOT / "ledger"
FIXTURES_DIR = LEDGER_DIR / "fixtures"
RUNS_DIR = LEDGER_DIR / "runs"

IMPLEMENTATIONS_TTL = LEDGER_DIR / "implementations.ttl"
TESTCASES_TTL = LEDGER_DIR / "testcases.ttl"
SOURCES_TTL = SOURCES_DIR / "sources.ttl"


def runs_ttl(implementation_slug: str) -> Path:
    return RUNS_DIR / f"{implementation_slug}.ttl"
