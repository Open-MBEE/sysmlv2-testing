"""Loading, saving and merging the ledger's Turtle files.

Every write goes through ``save_graph``, which canonicalizes before writing
— so a file on disk is always exactly what ``canonical_turtle`` would
produce from its own triples, and the determinism test (parse, reserialize,
diff) always passes by construction.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Graph

from .namespaces import (
    FIXTURES_DIR,
    IMPLEMENTATIONS_TTL,
    LEDGER_DIR,
    PREFIXES,
    RUNS_DIR,
    SHAPES_DIR,
    TESTCASES_TTL,
    VOCABULARY_DIR,
)
from .serialize import canonical_turtle


def load_graph(path: Path) -> Graph:
    g = Graph()
    if path.exists():
        g.parse(path, format="turtle")
    return g


def save_graph(graph: Graph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_turtle(graph, prefixes=PREFIXES), encoding="utf-8")


def load_vocabulary() -> Graph:
    g = Graph()
    for ttl in sorted(VOCABULARY_DIR.glob("*.ttl")):
        g.parse(ttl, format="turtle")
    return g


def load_shapes() -> Graph:
    g = Graph()
    for ttl in sorted(SHAPES_DIR.glob("*.ttl")):
        g.parse(ttl, format="turtle")
    return g


def load_full_ledger() -> Graph:
    """Every triple the ledger currently holds: implementations, test cases,
    and every implementation's recorded runs."""
    g = Graph()
    for ttl in (IMPLEMENTATIONS_TTL, TESTCASES_TTL):
        if ttl.exists():
            g.parse(ttl, format="turtle")
    if RUNS_DIR.exists():
        for ttl in sorted(RUNS_DIR.glob("*.ttl")):
            g.parse(ttl, format="turtle")
    return g


def fixtures_dir_for(testcase_id: str) -> Path:
    return FIXTURES_DIR / testcase_id


__all__ = [
    "load_graph",
    "save_graph",
    "load_vocabulary",
    "load_shapes",
    "load_full_ledger",
    "fixtures_dir_for",
    "LEDGER_DIR",
    "RUNS_DIR",
]
