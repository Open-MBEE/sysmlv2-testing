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
    SOURCES_TTL,
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
document_app = typer.Typer(help="Register spec documents (sources/sources.ttl).")
citation_app = typer.Typer(help="Register spec citations grounding a TestCase's expected value.")
testrun_app = typer.Typer(
    help="Post-run human review: annotate a TestRun, link it to an issue. "
    "(svt run itself stays a top-level command -- this sub-app covers only "
    "the actions a human takes after a run already exists.)"
)
app.add_typer(implementation_app, name="implementation")
app.add_typer(version_app, name="version")
app.add_typer(testcase_app, name="testcase")
app.add_typer(document_app, name="document")
app.add_typer(citation_app, name="citation")
app.add_typer(testrun_app, name="testrun")

AGENT_IRI = URIRef(f"{SVTID}agent-svt-cli")
METHODS = ("structural-check", "constraint-eval", "state-execution", "reference-resolution")
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
    for ttl in (SOURCES_TTL, IMPLEMENTATIONS_TTL, TESTCASES_TTL):
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


@document_app.command("add")
def document_add(
    id_: str = typer.Option(..., "--id", help="slug, e.g. formal-2026-03-02"),
    doc_number: str = typer.Option(
        ..., "--doc-number", help="exactly as printed on the document's own cover page"
    ),
    title: str = typer.Option(..., "--title"),
    local_path: str = typer.Option(..., "--local-path"),
    sha256: str = typer.Option(..., "--sha256"),
) -> None:
    g = load_graph(SOURCES_TTL)
    iri = ids.slug_id("spec", id_)
    g.add((iri, RDF.type, SVT.SpecDocument))
    g.add((iri, RDFS.label, Literal(title)))
    g.add((iri, SVT.docNumber, Literal(doc_number)))
    g.add((iri, SVT.localPath, Literal(local_path)))
    g.add((iri, SVT.sha256, Literal(sha256)))
    _gate_and_save(g, SOURCES_TTL)
    typer.echo(str(iri))


@citation_app.command("add")
def citation_add(
    id_: str = typer.Option(..., "--id"),
    document: str = typer.Option(..., "--document", help="the spec document's --id"),
    section: str = typer.Option(..., "--section"),
    page: str = typer.Option(..., "--page"),
    quote: str = typer.Option(..., "--quote", help="verbatim -- never paraphrased"),
    rationale: Optional[str] = typer.Option(None, "--rationale"),
) -> None:
    doc_iri = ids.slug_id("spec", document)
    g = load_graph(SOURCES_TTL)
    if (doc_iri, RDF.type, SVT.SpecDocument) not in g:
        typer.echo(
            f"error: unknown document {document!r} (register it first with `svt document add`)",
            err=True,
        )
        raise typer.Exit(2)
    iri = ids.slug_id("citation", id_)
    g.add((iri, RDF.type, SVT.SpecCitation))
    g.add((iri, SVT.citesDocument, doc_iri))
    g.add((iri, SVT.section, Literal(section)))
    g.add((iri, SVT.page, Literal(page)))
    g.add((iri, SVT.quote, Literal(quote)))
    if rationale is not None:
        g.add((iri, SVT.rationale, Literal(rationale)))
    _gate_and_save(g, SOURCES_TTL)
    typer.echo(str(iri))


def _existing_citation_iri(g: Graph, id_: str) -> URIRef:
    iri = ids.slug_id("citation", id_)
    if (iri, RDF.type, SVT.SpecCitation) not in g:
        typer.echo(f"error: unknown citation {id_!r}", err=True)
        raise typer.Exit(2)
    return iri


@citation_app.command("set-quote")
def citation_set_quote(
    id_: str = typer.Option(..., "--id"),
    quote: str = typer.Option(..., "--quote", help="verbatim -- never paraphrased"),
) -> None:
    """Correct a SpecCitation's svt:quote in place -- e.g. once a closer
    read of the actual PDF shows the recorded text isn't truly verbatim
    (invented, paraphrased, or conflated with a different passage)."""
    g = load_graph(SOURCES_TTL)
    iri = _existing_citation_iri(g, id_)
    g.remove((iri, SVT.quote, None))
    g.add((iri, SVT.quote, Literal(quote)))
    _gate_and_save(g, SOURCES_TTL)
    typer.echo(str(iri))


@citation_app.command("set-page")
def citation_set_page(
    id_: str = typer.Option(..., "--id"),
    page: str = typer.Option(..., "--page"),
) -> None:
    """Correct a SpecCitation's svt:page in place -- e.g. once checked
    against the actual PDF and the quoted text turns out to live on a
    different page than first recorded."""
    g = load_graph(SOURCES_TTL)
    iri = _existing_citation_iri(g, id_)
    g.remove((iri, SVT.page, None))
    g.add((iri, SVT.page, Literal(page)))
    _gate_and_save(g, SOURCES_TTL)
    typer.echo(str(iri))


def _resolved_citation_iris(grounds: List[str]) -> List[URIRef]:
    """Every --grounds id must already exist as a svt:SpecCitation -- a
    dangling citation reference is worse than no citation at all."""
    if not grounds:
        return []
    sources = load_graph(SOURCES_TTL)
    iris = []
    for citation_id in grounds:
        iri = ids.slug_id("citation", citation_id)
        if (iri, RDF.type, SVT.SpecCitation) not in sources:
            typer.echo(
                f"error: unknown citation {citation_id!r} "
                "(register it first with `svt citation add`)",
                err=True,
            )
            raise typer.Exit(2)
        iris.append(iri)
    return iris


@testcase_app.command("add")
def testcase_add(
    id_: str = typer.Option(..., "--id"),
    description: str = typer.Option(..., "--description"),
    input_file: List[Path] = typer.Option(..., "--input-file"),
    method: str = typer.Option(..., "--method"),
    expected: Optional[str] = typer.Option(None, "--expected"),
    prior_state: Optional[str] = typer.Option(
        None, "--prior-state", help="x: absent means the default (fresh, nothing but stdlib)"
    ),
    eval_expression: Optional[str] = typer.Option(None, "--eval-expression"),
    eval_subject: Optional[str] = typer.Option(None, "--eval-subject"),
    events: Optional[str] = typer.Option(
        None, "--events", help="method=state-execution: comma-joined event names (the command u)"
    ),
    resolves: List[str] = typer.Option(
        [],
        "--resolves",
        help='method=reference-resolution: "<subjectFeature>=<expectedTarget>"; repeatable',
    ),
    grounds: List[str] = typer.Option(
        [], "--grounds", help="a svt:SpecCitation --id backing --expected; repeatable"
    ),
) -> None:
    if method not in METHODS:
        typer.echo(f"error: --method must be one of {', '.join(METHODS)}", err=True)
        raise typer.Exit(2)
    citation_iris = _resolved_citation_iris(grounds)
    g = load_graph(TESTCASES_TTL)
    iri = ids.slug_id("testcase", id_)
    g.add((iri, RDF.type, SVT.TestCase))
    g.add((iri, SVT.description, Literal(description)))
    g.add((iri, SVT.method, Literal(method)))
    if prior_state is not None:
        g.add((iri, SVT.priorState, Literal(prior_state)))
    if expected is not None:
        g.add((iri, SVT.expected, Literal(expected)))
    if eval_expression is not None:
        g.add((iri, SVT.evalExpression, Literal(eval_expression)))
    if eval_subject is not None:
        g.add((iri, SVT.evalSubject, Literal(eval_subject)))
    if events is not None:
        g.add((iri, SVT.events, Literal(events)))
    for pair in resolves:
        subject, sep, target = pair.partition("=")
        if not sep:
            typer.echo(f"error: --resolves must be '<subject>=<target>', got {pair!r}", err=True)
            raise typer.Exit(2)
        check_iri = ids.mint("resolutioncheck", f"{id_}|{subject}|{target}")
        g.add((check_iri, RDF.type, SVT.ResolutionCheck))
        g.add((check_iri, SVT.subjectFeature, Literal(subject)))
        g.add((check_iri, SVT.expectedTarget, Literal(target)))
        g.add((iri, SVT.checksResolution, check_iri))
    for citation_iri in citation_iris:
        g.add((iri, SVT.groundedIn, citation_iri))

    for src in input_file:
        g.add((iri, SVT.hasInputFile, Literal(src.name)))
    # Gate before touching disk -- a SHACL-rejected write must leave no
    # trace, fixture files included. Copying first and gating after (the
    # previous order) meant a rejected `testcase add` still left files
    # sitting under ledger/fixtures/<id>/, even though _gate_and_save's
    # whole point is "nothing is written if it fails."
    _gate_and_save(g, TESTCASES_TTL)
    fixtures_dir = fixtures_dir_for(id_)
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    for src in input_file:
        dest = fixtures_dir / src.name
        dest.write_bytes(src.read_bytes())
    typer.echo(str(iri))


@testcase_app.command("ground")
def testcase_ground(
    id_: str = typer.Option(..., "--id"),
    grounds: List[str] = typer.Option(
        ..., "--grounds", help="a svt:SpecCitation --id; repeatable"
    ),
) -> None:
    """Append svt:groundedIn citations to an existing TestCase (there is no
    `testcase add` update path, and re-adding would duplicate fixtures)."""
    citation_iris = _resolved_citation_iris(grounds)
    g = load_graph(TESTCASES_TTL)
    iri = ids.slug_id("testcase", id_)
    if (iri, RDF.type, SVT.TestCase) not in g:
        typer.echo(f"error: unknown testcase {id_!r}", err=True)
        raise typer.Exit(2)
    for citation_iri in citation_iris:
        g.add((iri, SVT.groundedIn, citation_iri))
    _gate_and_save(g, TESTCASES_TTL)
    typer.echo(str(iri))


@testcase_app.command("set-description")
def testcase_set_description(
    id_: str = typer.Option(..., "--id"),
    description: str = typer.Option(..., "--description"),
) -> None:
    """Correct a TestCase's svt:description in place -- e.g. once grounding
    settles a claim the original prose called unresolved."""
    g = load_graph(TESTCASES_TTL)
    iri = ids.slug_id("testcase", id_)
    if (iri, RDF.type, SVT.TestCase) not in g:
        typer.echo(f"error: unknown testcase {id_!r}", err=True)
        raise typer.Exit(2)
    g.remove((iri, SVT.description, None))
    g.add((iri, SVT.description, Literal(description)))
    _gate_and_save(g, TESTCASES_TTL)
    typer.echo(str(iri))


@testcase_app.command("set-expected")
def testcase_set_expected(
    id_: str = typer.Option(..., "--id"),
    expected: str = typer.Option(..., "--expected"),
) -> None:
    """Correct a TestCase's svt:expected in place (remove-then-add on that
    one predicate). Unlike `version set-stable`, this is not meant to
    preserve history -- it's fixing a claim that was wrong, e.g. once a
    real spec citation settles what should have been asserted all along.
    Existing TestRuns against this TestCase were computed under the old
    value and are now stale evidence for the new one -- there is no
    delete/supersede mechanism for a TestRun (append-only, like
    everything else in ledger/runs/), so the fix is simply to `svt run`
    again: the fresh TestRun is the current evidence, the old one stays
    in the ledger as history of what this claim used to say."""
    g = load_graph(TESTCASES_TTL)
    iri = ids.slug_id("testcase", id_)
    if (iri, RDF.type, SVT.TestCase) not in g:
        typer.echo(f"error: unknown testcase {id_!r}", err=True)
        raise typer.Exit(2)
    g.remove((iri, SVT.expected, None))
    g.add((iri, SVT.expected, Literal(expected)))
    _gate_and_save(g, TESTCASES_TTL)
    typer.echo(str(iri))


# A blunt, real guard: this CLI must never record an LLM/agent as the
# human who validated a TestCase's claim against the spec. Not a security
# boundary (nothing stops someone from typing a different name) -- the
# same trust model as git commit authorship. See AGENTS.md.
NOT_A_HUMAN = {"svt", "svt-cli", "cli", "claude", "llm", "ai", "agent", "bot", "assistant"}


def _mint_person(ledger: Graph, g: Graph, name: str) -> URIRef:
    """Mint (or reuse) a prov:Person record for ``name`` inside graph
    ``g``, checking the conflicting-label guard against the already-loaded
    full ``ledger`` (never re-parses it here -- follow the same pattern as
    ``_resolve_testcase_iri``/``_resolve_version_iri``/``_resolve_run_iri``,
    which all take a pre-loaded ledger rather than loading their own
    copy). Shared by every command that attributes a record to a human
    (testcase validate, testrun annotate, testrun link-issue) so the
    denylist refusal can never quietly diverge at one call site -- that
    denylist is the actual point of AGENTS.md's "an agent must never
    validate/annotate its own claims" rule.

    A real cross-file identity gap this guards against: ``person_iri`` is
    minted from ``name`` alone (via ``ids.slug_id``), so the same human
    named slightly differently across two commands/files ("Z" once,
    "Zargham" another time) would otherwise silently pick up two
    different rdfs:label values scattered across separate ledger files --
    no shape constrains rdfs:label cardinality on prov:Person, and every
    existing test (SHACL, PROV-consistency, roundtrip) only checks one
    file's own internal consistency, never compares across files. So this
    checks the *whole* ledger for a conflicting prior label and refuses
    rather than silently accepting the divergence, the same
    correct-by-construction idiom used for citation/version existence
    checks below. (The heavier real fix -- one canonical ledger/people.ttl
    home for every prov:Person -- is a deferred cleanup item; see
    docs/walkthrough.md.)
    """
    if name.strip().lower() in NOT_A_HUMAN:
        typer.echo(
            f"error: {name!r} looks like an LLM/agent name, not a human -- "
            "this must be attributed to the actual person who did this",
            err=True,
        )
        raise typer.Exit(2)
    person_iri = ids.slug_id("person", name)
    existing_label = ledger.value(person_iri, RDFS.label)
    if existing_label is not None and str(existing_label) != name:
        typer.echo(
            f"error: --by {name!r} resolves to the same person as "
            f"previously-recorded {str(existing_label)!r} -- use the same "
            "name every time",
            err=True,
        )
        raise typer.Exit(2)
    g.add((person_iri, RDF.type, PROV.Person))
    g.add((person_iri, RDFS.label, Literal(name)))
    return person_iri


def _resolve_testcase_iri(ledger: Graph, testcase: str) -> URIRef:
    tc_iri = ids.slug_id("testcase", testcase)
    if (tc_iri, RDF.type, SVT.TestCase) not in ledger:
        typer.echo(f"error: unknown testcase {testcase!r}", err=True)
        raise typer.Exit(2)
    return tc_iri


def _resolve_version_iri(ledger: Graph, implementation: str, version: str) -> URIRef:
    version_iri = ids.mint("version", f"{implementation}|{version}")
    if (version_iri, RDF.type, SVT.Version) not in ledger:
        typer.echo(f"error: unknown version {version!r} of {implementation!r}", err=True)
        raise typer.Exit(2)
    return version_iri


def _parse_dt(value: object) -> datetime:
    """Parse an xsd:dateTime literal (or a user-supplied --at string) into
    a real datetime for instant comparison. Never compare timestamps as
    raw strings -- a user-typed --at may spell the same instant a
    different way ('Z' vs '+00:00', fractional seconds) than what's
    actually stored."""
    s = str(value).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _format_candidates(candidates: list[tuple[URIRef, object]]) -> str:
    """One timestamp per line, sorted for determinism -- shared by both
    of _resolve_run_iri's "which TestRun did you mean" error messages."""
    return "\n".join(f"  {started}" for _, started in sorted(candidates, key=lambda c: str(c[1])))


def _resolve_run_iri(
    ledger: Graph,
    testcase: str,
    implementation: str,
    version: str,
    at: Optional[str] = None,
) -> URIRef:
    """Find the TestRun for (testcase, implementation, version). A
    TestRun's IRI is minted from a real wall-clock timestamp with no
    slug, so there's nothing to type directly -- this resolves the same
    triple `svt run` takes. Unlike `_is_current_stable`'s "latest wins"
    precedent for StabilityDesignation, this never silently picks among
    multiple matches: misattributing a human's comment to the wrong run
    is a real correctness bug, not a cosmetic one. If more than one
    TestRun matches, refuse and print every candidate's exact stored
    timestamp so the human can paste one back in via --at."""
    tc_iri = _resolve_testcase_iri(ledger, testcase)
    version_iri = _resolve_version_iri(ledger, implementation, version)
    candidates = []
    for run_iri in ledger.subjects(RDF.type, SVT.TestRun):
        if ledger.value(run_iri, EARL.test) != tc_iri:
            continue
        if ledger.value(run_iri, EARL.subject) != version_iri:
            continue
        started = ledger.value(run_iri, PROV.startedAtTime)
        if started is not None:
            candidates.append((run_iri, started))
    if not candidates:
        typer.echo(
            f"error: no TestRun found for testcase={testcase!r} "
            f"implementation={implementation!r} version={version!r} -- "
            "run `svt run` first",
            err=True,
        )
        raise typer.Exit(2)
    if at is not None:
        target = _parse_dt(at)
        matches = [run_iri for run_iri, started in candidates if _parse_dt(started) == target]
        if len(matches) != 1:
            typer.echo(
                f"error: no TestRun with prov:startedAtTime matching --at {at!r} -- "
                "candidates:\n" + _format_candidates(candidates),
                err=True,
            )
            raise typer.Exit(2)
        return matches[0]
    if len(candidates) > 1:
        typer.echo(
            f"error: {len(candidates)} TestRuns match testcase={testcase!r} "
            f"implementation={implementation!r} version={version!r} -- "
            "disambiguate with --at, one of:\n" + _format_candidates(candidates),
            err=True,
        )
        raise typer.Exit(2)
    return candidates[0][0]


@testcase_app.command("validate")
def testcase_validate(
    id_: str = typer.Option(..., "--id"),
    by: str = typer.Option(..., "--by", help="the validating human's name"),
    note: Optional[str] = typer.Option(None, "--note"),
) -> None:
    """Record that a named human reviewed this TestCase's claim (its
    description, expected posterior state, and groundedIn citations)
    against the actual spec text and confirmed it. Being SHACL-valid RDF
    is not the same thing -- `svt run` refuses to run a TestCase with no
    Validation record. This command is for a human to run on their own
    judgment; an agent should never invoke it on a TestCase it authored
    itself, and never with a non-human --by name."""
    g = load_graph(TESTCASES_TTL)
    ledger = load_full_ledger()
    person_iri = _mint_person(ledger, g, by)
    iri = _resolve_testcase_iri(g, id_)
    ts = _now()
    validation_iri = ids.mint("validation", f"{id_}|{by}|{ts}")
    g.add((validation_iri, RDF.type, SVT.Validation))
    g.add((validation_iri, SVT.validates, iri))
    g.add((validation_iri, PROV.wasAssociatedWith, person_iri))
    g.add((validation_iri, PROV.startedAtTime, ts))
    if note is not None:
        g.add((validation_iri, SVT.note, Literal(note)))
    _gate_and_save(g, TESTCASES_TTL)
    typer.echo(str(validation_iri))


@testrun_app.command("annotate")
def testrun_annotate(
    testcase: str = typer.Option(..., "--testcase"),
    implementation: str = typer.Option(..., "--implementation"),
    version: str = typer.Option(..., "--version", help="the commit hash"),
    by: str = typer.Option(..., "--by", help="the annotating human's name"),
    comment: str = typer.Option(..., "--comment"),
    at: Optional[str] = typer.Option(
        None, "--at", help="disambiguate which TestRun, if more than one matches"
    ),
) -> None:
    """Record a human's free-text observation about one already-completed
    TestRun. Distinct from `svt testcase validate`, which is about the
    TestCase's claim before any run happens -- this is about the actual
    captured outcome, reviewed via `svt view`."""
    ledger = load_full_ledger()
    run_iri = _resolve_run_iri(ledger, testcase, implementation, version, at=at)
    g = load_graph(runs_ttl(implementation))
    person_iri = _mint_person(ledger, g, by)
    ts = _now()
    # comment folded into the key (not just testcase|impl|version|by|ts):
    # two different observations minted within the same wall-clock second
    # would otherwise collide on the identical IRI -- see the same
    # same-second landmine documented for `svt run`'s run_iri. Folding in
    # the payload narrows, but does not eliminate, that collision (two
    # byte-identical comments within the same second still collide,
    # which is the accepted, documented limitation).
    annotation_iri = ids.mint(
        "annotation", f"{testcase}|{implementation}|{version}|{by}|{comment}|{ts}"
    )
    g.add((annotation_iri, RDF.type, SVT.Annotation))
    g.add((annotation_iri, SVT.concernsRun, run_iri))
    g.add((annotation_iri, PROV.wasAssociatedWith, person_iri))
    g.add((annotation_iri, PROV.startedAtTime, ts))
    g.add((annotation_iri, SVT.comment, Literal(comment)))
    _gate_and_save(g, runs_ttl(implementation))
    typer.echo(str(annotation_iri))


@testrun_app.command("link-issue")
def testrun_link_issue(
    testcase: str = typer.Option(..., "--testcase"),
    implementation: str = typer.Option(..., "--implementation"),
    version: str = typer.Option(..., "--version", help="the commit hash"),
    by: str = typer.Option(..., "--by", help="the human who decided to file/link this"),
    url: str = typer.Option(..., "--url"),
    label: Optional[str] = typer.Option(None, "--label"),
    at: Optional[str] = typer.Option(
        None, "--at", help="disambiguate which TestRun, if more than one matches"
    ),
) -> None:
    """Record that one already-completed TestRun relates to an external
    issue-tracker entry -- makes "this failure became issue #N" a real,
    queryable fact instead of prose in svt:stderr or a design-notes.md
    credit line."""
    ledger = load_full_ledger()
    run_iri = _resolve_run_iri(ledger, testcase, implementation, version, at=at)
    g = load_graph(runs_ttl(implementation))
    person_iri = _mint_person(ledger, g, by)
    ts = _now()
    # url folded into the key -- same reasoning as annotate's comment above.
    issue_iri = ids.mint("issuelink", f"{testcase}|{implementation}|{version}|{by}|{url}|{ts}")
    g.add((issue_iri, RDF.type, SVT.IssueLink))
    g.add((issue_iri, SVT.concernsRun, run_iri))
    g.add((issue_iri, PROV.wasAssociatedWith, person_iri))
    g.add((issue_iri, PROV.startedAtTime, ts))
    g.add((issue_iri, SVT.issueURL, Literal(url, datatype=XSD.anyURI)))
    if label is not None:
        g.add((issue_iri, SVT.issueLabel, Literal(label)))
    _gate_and_save(g, runs_ttl(implementation))
    typer.echo(str(issue_iri))


@app.command("run")
def run_cmd(
    testcase: str = typer.Option(..., "--testcase"),
    implementation: str = typer.Option(..., "--implementation"),
    version: str = typer.Option(..., "--version", help="the commit hash"),
) -> None:
    from adapters.base import ResolutionCheck, TestCaseSpec, UnsupportedMethod  # noqa: PLC0415
    from adapters.compare import compare  # noqa: PLC0415

    ledger = load_full_ledger()
    tc_iri = _resolve_testcase_iri(ledger, testcase)
    impl_iri = ids.slug_id("implementation", implementation)
    version_iri = _resolve_version_iri(ledger, implementation, version)

    # Being SHACL-valid RDF is not the same thing as a human having
    # confirmed this claim against the spec -- construction and structural
    # gating alone are not sufficient to make a TestCase runnable. See
    # AGENTS.md's "construct -> SHACL-gate -> human-validate -> run".
    if not any(ledger.subjects(SVT.validates, tc_iri)):
        typer.echo(
            f"error: testcase {testcase!r} has no svt:Validation record -- "
            f"a human must confirm this claim against the spec first:\n"
            f"  svt testcase validate --id {testcase} --by <your name>",
            err=True,
        )
        raise typer.Exit(2)

    method = str(ledger.value(tc_iri, SVT.method))
    expected_node = ledger.value(tc_iri, SVT.expected)
    expected = str(expected_node) if expected_node is not None else None
    eval_expr = ledger.value(tc_iri, SVT.evalExpression)
    eval_subject = ledger.value(tc_iri, SVT.evalSubject)
    events_node = ledger.value(tc_iri, SVT.events)
    resolution_checks = tuple(
        ResolutionCheck(
            subject_feature=str(ledger.value(check_iri, SVT.subjectFeature)),
            expected_target=str(ledger.value(check_iri, SVT.expectedTarget)),
        )
        # sorted for determinism -- the ledger's set-valued objects() has no
        # guaranteed order, and adapters must see checks in a stable order
        for check_iri in sorted(ledger.objects(tc_iri, SVT.checksResolution))
    )
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
        events=str(events_node) if events_node is not None else None,
        resolution_checks=resolution_checks,
    )

    module_name = ADAPTER_MODULES.get(implementation)
    if module_name is None:
        typer.echo(f"error: no adapter registered for implementation {implementation!r}", err=True)
        raise typer.Exit(2)
    mod = importlib.import_module(module_name)

    # Pins precisely which input bytes this run saw, independent of
    # whatever the fixture files look like later -- the "precise input"
    # half of the ledger's evidence (see AGENTS.md).
    input_digest = ids.sha256_of_files(input_files)

    ts = _now()
    invocation_key = f"{testcase}|{implementation}|{version}|{ts}"
    try:
        raw = mod.ADAPTER.run(spec)
    except UnsupportedMethod as exc:
        outcome, actual, info = "inapplicable", None, str(exc)
        command, exit_code, stdout, stderr = "(unsupported)", -1, "", str(exc)
    else:
        outcome, actual, info = compare(spec, raw)
        command, exit_code, stdout, stderr = raw.command, raw.exit_code, raw.stdout, raw.stderr

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
    if actual is not None:
        g.add((result_iri, SVT.actual, Literal(actual)))
    g.add((invocation_iri, RDF.type, SVT.Invocation))
    g.add((invocation_iri, SVT.command, Literal(command)))
    g.add((invocation_iri, SVT.exitCode, Literal(exit_code, datatype=XSD.integer)))
    g.add((invocation_iri, SVT.stdout, Literal(stdout)))
    g.add((invocation_iri, SVT.stderr, Literal(stderr)))
    g.add((invocation_iri, SVT.inputDigest, Literal(input_digest)))
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
    from adapters.compare import OUTCOMES  # noqa: PLC0415

    g = load_full_ledger()
    filter_impl_iri = None
    if implementation is not None:
        filter_impl_iri = ids.slug_id("implementation", implementation)
        if (filter_impl_iri, RDF.type, SVT.Implementation) not in g:
            typer.echo(f"error: unknown implementation {implementation!r}", err=True)
            raise typer.Exit(2)
    counts = {o: 0 for o in OUTCOMES}
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


@app.command("view")
def view_cmd(
    testcase: Optional[str] = typer.Option(
        None, "--testcase", help="Report just this test case; omit for every test case."
    ),
    implementation: Optional[str] = typer.Option(
        None,
        "--implementation",
        help="Report just this implementation's runs -- combined with --testcase, "
        "this is the single-test/single-implementation report (docs/workflow.md's "
        "report kind 1); --testcase alone (or neither filter) is the "
        "cross-implementation comparison (report kind 2).",
    ),
) -> None:
    """Compile a deterministic Markdown report (one SPARQL query + the
    fixture files) so a human can actually read the ledger's precise
    input/output evidence. Ephemeral: written under reports/ (gitignored),
    fully reproducible from the ledger + fixtures at any time."""
    from .view import render_report  # noqa: PLC0415

    content = render_report(testcase, implementation)
    reports_dir = ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    name_parts = []
    if testcase is not None:
        name_parts.append(f"testcase-{testcase}")
    if implementation is not None:
        # Already-prefixed by "testcase-<id>" above when both filters are
        # given (report kind 1) -- the bare slug reads fine appended to
        # that. Filtered by --implementation alone (no --testcase), there's
        # no "testcase-" prefix to attach to, so it needs its own label.
        name_parts.append(implementation if testcase is not None else f"implementation-{implementation}")
    name = "-".join(name_parts) + ".md" if name_parts else "all.md"
    path = reports_dir / name
    path.write_text(content, encoding="utf-8")
    typer.echo(str(path))


if __name__ == "__main__":
    app()
