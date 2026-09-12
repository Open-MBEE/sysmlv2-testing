"""svt — the ledger CLI. This is the only thing that writes to the ledger.

Every command below builds triples in plain rdflib, gates them through the
SHACL shapes (against the *whole* ledger, so cross-file references like a
TestRun's earl:test pointing into testcases.ttl are checked properly),
canonicalizes, and writes. `svt run` is the pipeline: pipe a TestCase's
fixture files into the adapter for (implementation, version), capture raw
output, compare it to `expected` with a scripted comparator, log a TestRun.
See AGENTS.md.
"""

from __future__ import annotations

import importlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import typer
from rdflib import RDF, Graph, Literal, URIRef
from rdflib.namespace import RDFS, XSD

from . import ids
from .graph import fixtures_dir_for, load_full_ledger, load_graph, load_shapes, save_graph
from .namespaces import (
    EARL,
    IMPLEMENTATIONS_TTL,
    PROV,
    RUNS_DIR,
    SVT,
    SVTID,
    TESTCASES_TTL,
    ROOT,
    runs_ttl,
)
from .verify import verify as shacl_verify

sys.path.insert(0, str(ROOT))  # adapters/ lives at repo root, not under src/

app = typer.Typer(help="svt — the sysmlv2-testing ledger CLI. The CLI is the only writer.")
implementation_app = typer.Typer(help="Register implementations and their versions.")
version_app = typer.Typer(help="Register versions and stability designations.")
testcase_app = typer.Typer(help="Register test cases.")
app.add_typer(implementation_app, name="implementation")
app.add_typer(version_app, name="version")
app.add_typer(testcase_app, name="testcase")

AGENT_IRI = URIRef(f"{SVTID}agent-svt-cli")
METHODS = ("structural-check", "constraint-eval", "state-execution")
ADAPTER_MODULES = {
    "opensysml": "adapters.opensysml",
    "sysml-toolkit": "adapters.sysml_toolkit",
    "pilot-implementation": "adapters.pilot_implementation",
}


def _now() -> Literal:
    return Literal(
        datetime.now(timezone.utc).replace(microsecond=0).isoformat(), datatype=XSD.dateTime
    )


def _gate_and_save(modified: Graph, path: Path) -> None:
    """Validate ``modified`` (the new state of one ledger file) against the
    *whole* ledger — every other file as currently on disk, plus these new
    triples — before writing anything. Nothing is written if it fails."""
    shapes = load_shapes()
    union = Graph()
    for ttl in (IMPLEMENTATIONS_TTL, TESTCASES_TTL):
        if ttl.exists() and ttl != path:
            union.parse(ttl, format="turtle")
    if RUNS_DIR.exists():
        for ttl in sorted(RUNS_DIR.glob("*.ttl")):
            if ttl != path:
                union.parse(ttl, format="turtle")
    for t in modified:
        union.add(t)
    result = shacl_verify(union, shapes)
    if not result.conforms:
        for f in result.findings:
            if f.severity == "Violation":
                typer.echo(f"VIOLATION\t{f.rule}\t{f.focus}\t{f.message}", err=True)
        typer.echo("error: SHACL gate failed, nothing written", err=True)
        raise typer.Exit(1)
    save_graph(modified, path)


@implementation_app.command("add")
def implementation_add(
    name: str = typer.Option(..., "--name", help="slug, e.g. opensysml"),
    repo: str = typer.Option(..., "--repo"),
    language: str = typer.Option(..., "--language"),
) -> None:
    g = load_graph(IMPLEMENTATIONS_TTL)
    iri = ids.slug_id("implementation", name)
    g.add((iri, RDF.type, SVT.Implementation))
    g.add((iri, SVT.name, Literal(name)))
    g.add((iri, SVT.repositoryURL, Literal(repo, datatype=XSD.anyURI)))
    g.add((iri, SVT.primaryLanguage, Literal(language)))
    _gate_and_save(g, IMPLEMENTATIONS_TTL)
    typer.echo(str(iri))


@version_app.command("add")
def version_add(
    implementation: str = typer.Option(..., "--implementation"),
    commit: str = typer.Option(..., "--commit"),
    label: Optional[str] = typer.Option(None, "--label"),
    source_url: Optional[str] = typer.Option(None, "--source-url"),
    artifact_digest: Optional[str] = typer.Option(None, "--artifact-digest"),
) -> None:
    g = load_graph(IMPLEMENTATIONS_TTL)
    impl_iri = ids.slug_id("implementation", implementation)
    if (impl_iri, RDF.type, SVT.Implementation) not in g:
        typer.echo(
            f"error: unknown implementation {implementation!r} "
            "(register it first with `svt implementation add`)",
            err=True,
        )
        raise typer.Exit(2)
    version_iri = ids.mint("version", f"{implementation}|{commit}")
    g.add((version_iri, RDF.type, SVT.Version))
    g.add((version_iri, SVT.ofImplementation, impl_iri))
    g.add((impl_iri, SVT.hasVersion, version_iri))
    g.add((version_iri, SVT.commitHash, Literal(commit)))
    if label:
        g.add((version_iri, SVT.versionLabel, Literal(label)))
    if source_url:
        g.add((version_iri, SVT.sourceURL, Literal(source_url, datatype=XSD.anyURI)))
    if artifact_digest:
        g.add((version_iri, SVT.artifactDigest, Literal(artifact_digest)))
    _gate_and_save(g, IMPLEMENTATIONS_TTL)
    typer.echo(str(version_iri))


@version_app.command("set-stable")
def version_set_stable(
    implementation: str = typer.Option(..., "--implementation"),
    version: str = typer.Option(..., "--version", help="the commit hash"),
) -> None:
    g = load_graph(IMPLEMENTATIONS_TTL)
    impl_iri = ids.slug_id("implementation", implementation)
    version_iri = ids.mint("version", f"{implementation}|{version}")
    if (version_iri, RDF.type, SVT.Version) not in g:
        typer.echo(
            f"error: unknown version {version!r} of {implementation!r} (register it first)",
            err=True,
        )
        raise typer.Exit(2)
    ts = _now()
    designation_iri = ids.mint("stability", f"{implementation}|{version}|{ts}")
    g.add((designation_iri, RDF.type, SVT.StabilityDesignation))
    g.add((designation_iri, SVT.designates, version_iri))
    g.add((designation_iri, SVT.forImplementation, impl_iri))
    # prov:startedAtTime, not prov:generatedAtTime: this is a prov:Activity,
    # and generatedAtTime's rdfs:domain is prov:Entity (PROV-O declares the
    # two disjoint) -- see tests/unit/test_prov_consistency.py.
    g.add((designation_iri, PROV.startedAtTime, ts))
    _gate_and_save(g, IMPLEMENTATIONS_TTL)
    typer.echo(str(designation_iri))


@testcase_app.command("add")
def testcase_add(
    id_: str = typer.Option(..., "--id"),
    description: str = typer.Option(..., "--description"),
    input_file: List[Path] = typer.Option(..., "--input-file"),
    method: str = typer.Option(..., "--method"),
    expected: Optional[str] = typer.Option(None, "--expected"),
    eval_expression: Optional[str] = typer.Option(None, "--eval-expression"),
    eval_subject: Optional[str] = typer.Option(None, "--eval-subject"),
) -> None:
    if method not in METHODS:
        typer.echo(f"error: --method must be one of {', '.join(METHODS)}", err=True)
        raise typer.Exit(2)
    g = load_graph(TESTCASES_TTL)
    iri = ids.slug_id("testcase", id_)
    g.add((iri, RDF.type, SVT.TestCase))
    g.add((iri, SVT.description, Literal(description)))
    g.add((iri, SVT.method, Literal(method)))
    if expected is not None:
        g.add((iri, SVT.expected, Literal(expected)))
    if eval_expression is not None:
        g.add((iri, SVT.evalExpression, Literal(eval_expression)))
    if eval_subject is not None:
        g.add((iri, SVT.evalSubject, Literal(eval_subject)))

    fixtures_dir = fixtures_dir_for(id_)
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    for src in input_file:
        dest = fixtures_dir / src.name
        dest.write_bytes(src.read_bytes())
        g.add((iri, SVT.hasInputFile, Literal(src.name)))
    _gate_and_save(g, TESTCASES_TTL)
    typer.echo(str(iri))


@app.command("run")
def run_cmd(
    testcase: str = typer.Option(..., "--testcase"),
    implementation: str = typer.Option(..., "--implementation"),
    version: str = typer.Option(..., "--version", help="the commit hash"),
) -> None:
    from adapters.base import TestCaseSpec, UnsupportedMethod  # noqa: PLC0415
    from adapters.compare import compare  # noqa: PLC0415

    ledger = load_full_ledger()
    tc_iri = ids.slug_id("testcase", testcase)
    if (tc_iri, RDF.type, SVT.TestCase) not in ledger:
        typer.echo(f"error: unknown testcase {testcase!r}", err=True)
        raise typer.Exit(2)
    impl_iri = ids.slug_id("implementation", implementation)
    version_iri = ids.mint("version", f"{implementation}|{version}")
    if (version_iri, RDF.type, SVT.Version) not in ledger:
        typer.echo(f"error: unknown version {version!r} of {implementation!r}", err=True)
        raise typer.Exit(2)

    method = str(ledger.value(tc_iri, SVT.method))
    expected_node = ledger.value(tc_iri, SVT.expected)
    expected = str(expected_node) if expected_node is not None else None
    eval_expr = ledger.value(tc_iri, SVT.evalExpression)
    eval_subject = ledger.value(tc_iri, SVT.evalSubject)
    input_names = sorted(str(o) for o in ledger.objects(tc_iri, SVT.hasInputFile))
    fixtures_dir = fixtures_dir_for(testcase)
    input_files = [fixtures_dir / name for name in input_names]
    missing = [str(p) for p in input_files if not p.exists()]
    if missing:
        typer.echo(f"error: missing fixture files: {missing}", err=True)
        raise typer.Exit(2)

    spec = TestCaseSpec(
        input_files=input_files,
        method=method,
        expected=expected,
        eval_expression=str(eval_expr) if eval_expr is not None else None,
        eval_subject=str(eval_subject) if eval_subject is not None else None,
    )

    module_name = ADAPTER_MODULES.get(implementation)
    if module_name is None:
        typer.echo(f"error: no adapter registered for implementation {implementation!r}", err=True)
        raise typer.Exit(2)
    mod = importlib.import_module(module_name)

    ts = _now()
    invocation_key = f"{testcase}|{implementation}|{version}|{ts}"
    try:
        raw = mod.ADAPTER.run(spec)
    except UnsupportedMethod as exc:
        outcome, info = "inapplicable", str(exc)
        command, exit_code = "(unsupported)", -1
    else:
        outcome, info = compare(method, expected, raw)
        command, exit_code = raw.command, raw.exit_code

    run_iri = ids.mint("run", invocation_key)
    invocation_iri = ids.mint("invocation", invocation_key)
    result_iri = ids.mint("result", invocation_key)

    g = load_graph(runs_ttl(implementation))
    g.add((AGENT_IRI, RDF.type, EARL.Software))
    g.add((AGENT_IRI, RDF.type, PROV.SoftwareAgent))
    g.add((AGENT_IRI, RDFS.label, Literal("sysmlv2-testing CLI (svt)")))
    g.add((run_iri, RDF.type, SVT.TestRun))
    g.add((run_iri, EARL.test, tc_iri))
    g.add((run_iri, EARL.subject, version_iri))
    g.add((run_iri, EARL.assertedBy, AGENT_IRI))
    g.add((run_iri, EARL.mode, EARL.automatic))
    g.add((run_iri, EARL.result, result_iri))
    # prov:startedAtTime, not prov:generatedAtTime (see the note in
    # version_set_stable above); svt:hasInvocation, not prov:wasGeneratedBy,
    # since that property's domain is prov:Entity and both ends here are
    # prov:Activity.
    g.add((run_iri, PROV.startedAtTime, ts))
    g.add((run_iri, SVT.hasInvocation, invocation_iri))
    g.add((result_iri, RDF.type, EARL.TestResult))
    g.add((result_iri, EARL.outcome, URIRef(str(EARL) + outcome)))
    g.add((result_iri, EARL.info, Literal(info)))
    g.add((invocation_iri, RDF.type, SVT.Invocation))
    g.add((invocation_iri, SVT.command, Literal(command)))
    g.add((invocation_iri, SVT.exitCode, Literal(exit_code, datatype=XSD.integer)))
    g.add((invocation_iri, PROV.startedAtTime, ts))

    _gate_and_save(g, runs_ttl(implementation))
    typer.echo(f"{outcome}\t{run_iri}")


def _is_current_stable(g: Graph, impl_iri: URIRef, version_iri: URIRef) -> bool:
    latest_time: str | None = None
    latest_version: URIRef | None = None
    for d in g.subjects(RDF.type, SVT.StabilityDesignation):
        if g.value(d, SVT.forImplementation) != impl_iri:
            continue
        t = g.value(d, PROV.startedAtTime)
        v = g.value(d, SVT.designates)
        if t is None or v is None:
            continue
        if latest_time is None or str(t) > latest_time:
            latest_time, latest_version = str(t), v
    return latest_version == version_iri


@app.command("report")
def report_cmd(
    implementation: Optional[str] = typer.Option(None, "--implementation"),
    stable_only: bool = typer.Option(False, "--stable-only"),
) -> None:
    g = load_full_ledger()
    filter_impl_iri = ids.slug_id("implementation", implementation) if implementation else None
    counts = {o: 0 for o in ("passed", "failed", "cantTell", "inapplicable", "untested")}
    for run in g.subjects(RDF.type, SVT.TestRun):
        version_iri = g.value(run, EARL.subject)
        impl_iri = g.value(version_iri, SVT.ofImplementation) if version_iri else None
        if filter_impl_iri is not None and impl_iri != filter_impl_iri:
            continue
        if stable_only and not (
            impl_iri and version_iri and _is_current_stable(g, impl_iri, version_iri)
        ):
            continue
        result = g.value(run, EARL.result)
        outcome = g.value(result, EARL.outcome) if result else None
        local = str(outcome).rsplit("#", 1)[-1] if outcome else None
        if local in counts:
            counts[local] += 1
    for outcome, n in counts.items():
        typer.echo(f"{outcome}\t{n}")


@app.command("verify")
def verify_cmd() -> None:
    shapes = load_shapes()
    data = load_full_ledger()
    result = shacl_verify(data, shapes)
    for f in result.findings:
        typer.echo(f"{f.severity}\t{f.rule}\t{f.focus}\t{f.message}")
    if not result.conforms:
        typer.echo("VERDICT: FAIL", err=True)
        raise typer.Exit(1)
    typer.echo("VERDICT: PASS")


if __name__ == "__main__":
    app()
