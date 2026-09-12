"""Namespaces and repo-relative paths, in one place so nothing drifts."""

from __future__ import annotations

from pathlib import Path

from rdflib import Namespace

SVT = Namespace("https://w3id.org/sysmlv2-testing#")
SVTID = Namespace("https://w3id.org/sysmlv2-testing/id/")
EARL = Namespace("http://www.w3.org/ns/earl#")
PROV = Namespace("http://www.w3.org/ns/prov#")

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
