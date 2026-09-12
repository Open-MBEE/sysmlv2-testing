"""Every shape has a counterexample that violates exactly it, and one
conforming record set passes clean -- the same discipline og-caie-spec and
cds use: a SHACL shape without a counterexample is unverified."""

from pathlib import Path

import pyshacl
from rdflib import RDF, Graph
from rdflib.namespace import SH

from sysmlv2_testing.graph import load_shapes

COUNTEREXAMPLES_DIR = Path(__file__).parent / "counterexamples"

EXPECTED_VIOLATIONS = {
    "implementation_missing_name": "ImplementationNameShape",
    "version_bad_commit_hash": "VersionCommitHashShape",
    "stabilitydesignation_missing_time": "StabilityStartedAtTimeShape",
    "testcase_bad_method": "TestCaseMethodShape",
    "testrun_missing_result": "TestRunResultShape",
    "testresult_bad_outcome": "TestResultOutcomeShape",
}


def _violated_shape_names(data: Graph, shapes: Graph) -> set[str]:
    _conforms, report, _text = pyshacl.validate(
        data, shacl_graph=shapes, advanced=True, inference="none"
    )
    names = set()
    for result in report.subjects(RDF.type, SH.ValidationResult):
        shape = report.value(result, SH.sourceShape)
        if shape is not None:
            names.add(str(shape).rsplit("#", 1)[-1])
    return names


def test_each_counterexample_violates_exactly_its_shape():
    shapes = load_shapes()
    for stem, expected_shape in EXPECTED_VIOLATIONS.items():
        path = COUNTEREXAMPLES_DIR / f"{stem}.ttl"
        assert path.exists(), f"missing counterexample fixture {path}"
        data = Graph()
        data.parse(path, format="turtle")
        violated = _violated_shape_names(data, shapes)
        assert expected_shape in violated, (
            f"{stem}: expected {expected_shape} to be violated, got {violated}"
        )


def test_a_conforming_record_set_passes():
    shapes = load_shapes()
    data = Graph()
    data.parse(COUNTEREXAMPLES_DIR / "_conforms.ttl", format="turtle")
    conforms, _report, _text = pyshacl.validate(
        data, shacl_graph=shapes, advanced=True, inference="none",
        allow_infos=True, allow_warnings=True,
    )
    assert conforms
