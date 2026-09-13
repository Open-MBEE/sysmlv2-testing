"""Every ledger file on disk must already be exactly what canonical_turtle
would produce from its own triples -- that's what "the CLI is the only
writer, and every write is canonicalized" is supposed to guarantee. This
test is the check on that guarantee, not a description of intent."""

from rdflib import Graph

from sysmlv2_testing.namespaces import (
    IMPLEMENTATIONS_TTL,
    PREFIXES,
    RUNS_DIR,
    SOURCES_TTL,
    TESTCASES_TTL,
)
from sysmlv2_testing.serialize import canonical_turtle


def _ledger_files():
    # SOURCES_TTL is written by document add / citation add / set-quote /
    # set-page -- same "the CLI is the only writer" guarantee applies to
    # it as to IMPLEMENTATIONS_TTL/TESTCASES_TTL/RUNS_DIR; it must not be
    # silently exempt from this check.
    files = [p for p in (SOURCES_TTL, IMPLEMENTATIONS_TTL, TESTCASES_TTL) if p.exists()]
    if RUNS_DIR.exists():
        files.extend(sorted(RUNS_DIR.glob("*.ttl")))
    return files


def test_every_ledger_file_is_already_canonical():
    files = _ledger_files()
    assert files, "expected at least one ledger file to exist for this test to mean anything"
    for path in files:
        on_disk = path.read_text(encoding="utf-8")
        g = Graph()
        g.parse(path, format="turtle")
        reserialized = canonical_turtle(g, prefixes=PREFIXES)
        assert reserialized == on_disk, f"{path} is not byte-identical to its own canonical form"


def test_canonical_turtle_is_reserialization_stable():
    """Parsing canonical_turtle's own output and re-serializing it again
    must reproduce exactly the same bytes -- the property the CLI depends
    on to avoid ever writing a file that immediately looks 'dirty'."""
    for path in _ledger_files():
        g = Graph()
        g.parse(path, format="turtle")
        once = canonical_turtle(g, prefixes=PREFIXES)
        g2 = Graph()
        g2.parse(data=once, format="turtle")
        twice = canonical_turtle(g2, prefixes=PREFIXES)
        assert once == twice
