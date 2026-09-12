"""Deterministic IRI minting.

Every minted record's identity is a sha256 of a stable, content-derived key
— never a random UUID and never a bare counter — so the same logical fact
always gets the same IRI. (A TestRun's own *timestamp* is still real wall
-clock time, since it is recording when a real invocation happened; that's
data, not identity. See tests/determinism for what "deterministic" actually
means here: re-serializing a committed ledger file is byte-stable, not
"re-running produces the same timestamp.")
"""

from __future__ import annotations

import hashlib
import re

from rdflib import URIRef

from .namespaces import SVTID

_SLUG_UNSAFE = re.compile(r"[^a-z0-9\-]+")


def slugify(text: str) -> str:
    return _SLUG_UNSAFE.sub("-", text.strip().lower()).strip("-")


def slug_id(kind: str, name: str) -> URIRef:
    """A human-readable IRI for a record with a natural key (Implementation's
    name, a TestCase's user-supplied id) — kept readable on purpose, per the
    "interpretable and navigable" goal; not every record needs a hash."""
    return URIRef(f"{SVTID}{kind}-{slugify(name)}")


def mint(kind: str, key: str) -> URIRef:
    """A stable IRI for a derived/event record (e.g. "version", "run") with
    no natural human key, minted from a content-derived ``key``."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return URIRef(f"{SVTID}{kind}-{digest}")
