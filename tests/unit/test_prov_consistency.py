"""Every svt: class subclasses an EARL or PROV-O class -- this test is the
check that doing so never puts one instance into two of PROV-O's own
mutually-disjoint classes (prov:Entity / prov:Activity / prov:Agent), which
would mean the vocabulary silently contradicts the standards it claims to
extend. Uses pinned, vendored copies of PROV-O and EARL (tests/vendor/),
never fetched live."""

from pathlib import Path

from owlrl import OWLRL_Semantics, DeductiveClosure
from rdflib import RDF, Graph
from rdflib.namespace import OWL

from sysmlv2_testing.graph import load_full_ledger, load_vocabulary

VENDOR_DIR = Path(__file__).parent.parent / "vendor"


def _closed_graph() -> Graph:
    g = Graph()
    g.parse(VENDOR_DIR / "prov-o.ttl", format="turtle")
    g.parse(VENDOR_DIR / "earl.rdf", format="xml")
    g += load_vocabulary()
    g += load_full_ledger()
    DeductiveClosure(OWLRL_Semantics).expand(g)
    return g


def test_no_instance_is_asserted_into_two_disjoint_prov_classes():
    g = _closed_graph()
    disjoint_pairs = list(g.subject_objects(OWL.disjointWith))
    assert disjoint_pairs, "expected PROV-O's own disjointness axioms to survive the closure"

    offenders = []
    for a, b in disjoint_pairs:
        both = set(g.subjects(RDF.type, a)) & set(g.subjects(RDF.type, b))
        for node in both:
            offenders.append((node, a, b))
    assert not offenders, (
        "instance(s) asserted into two disjoint PROV-O classes: "
        + "; ".join(f"{n} in both {a} and {b}" for n, a, b in offenders)
    )
