"""svt view: compile a deterministic Markdown report from one SPARQL query
(queries/testcase_view.rq) plus the fixture files on disk.

Ephemeral by design (reports/ is gitignored) -- fully, byte-for-byte
reproducible from the ledger + fixtures at any time, so it is never itself
a source of truth. This exists so a human can actually read the precise
input/output evidence the ledger holds, instead of grepping .ttl files.
"""

from __future__ import annotations

from rdflib import RDF, URIRef
from rdflib.namespace import RDFS

from . import ids
from .graph import fixtures_dir_for, load_full_ledger
from .namespaces import PROV, ROOT, SVT

QUERY_PATH = ROOT / "queries" / "testcase_view.rq"


def _local_slug(iri: URIRef) -> str:
    """``.../id/testcase-<slug>`` -> ``<slug>``."""
    name = str(iri).rsplit("/", 1)[-1]
    return name.split("-", 1)[1] if "-" in name else name


def _fence(text: str) -> str:
    """A fenced code block whose fence can't be broken by ``` in ``text``."""
    fence = "```"
    while fence in text:
        fence += "`"
    body = text if text else ""
    return f"{fence}\n{body}\n{fence}"


def _outcome_local(outcome) -> str:
    return str(outcome).rsplit("#", 1)[-1] if outcome is not None else ""


def _annotation_and_issue_lines(run_iri, ledger) -> list[str]:
    """svt:concernsRun is multivalued (many humans may annotate, or find a
    second related issue, over time) and shared by both svt:Annotation and
    svt:IssueLink -- deliberately not joined into queries/testcase_view.rq
    for the same reason svt:groundedIn isn't: it would multiply rows per
    run. Read directly, sorted by IRI for determinism (same discipline as
    _grounding_lines)."""
    concerning = sorted(ledger.subjects(SVT.concernsRun, run_iri), key=str)
    annotations = [c for c in concerning if (c, RDF.type, SVT.Annotation) in ledger]
    issues = [c for c in concerning if (c, RDF.type, SVT.IssueLink) in ledger]
    lines = []
    for a in annotations:
        person = ledger.value(a, PROV.wasAssociatedWith)
        name = ledger.value(person, RDFS.label) if person is not None else None
        when = ledger.value(a, PROV.startedAtTime)
        comment = ledger.value(a, SVT.comment)
        lines.append(f"- **annotation** by {name or person} ({when}): {comment}")
    for i in issues:
        person = ledger.value(i, PROV.wasAssociatedWith)
        name = ledger.value(person, RDFS.label) if person is not None else None
        when = ledger.value(i, PROV.startedAtTime)
        url = ledger.value(i, SVT.issueURL)
        label = ledger.value(i, SVT.issueLabel)
        label_part = f" ({label})" if label is not None else ""
        lines.append(f"- **issue**{label_part}: {url} -- linked by {name or person} ({when})")
    return lines


def _run_section(row, ledger) -> str:
    label = f" ({row.versionLabel})" if row.versionLabel is not None else ""
    lines = [
        f"#### {row.implName} @ `{row.commitHash}`{label}",
        "",
        f"- **outcome**: `{_outcome_local(row.outcome)}`",
    ]
    if row.actual is not None:
        lines.append(f"- **actual**: `{row.actual}`")
    if row.info is not None:
        lines.append(f"- **info**: {row.info}")
    lines += _annotation_and_issue_lines(row.run, ledger)
    lines += [
        f"- **command**: `{row.command}`",
        f"- **exit code**: `{row.exitCode}`",
        f"- **input digest**: `sha256:{row.inputDigest}`",
        f"- **started at**: {row.startedAtTime}",
        "",
        "stdout:",
        "",
        _fence(str(row.stdout)),
        "",
        "stderr:",
        "",
        _fence(str(row.stderr)),
        "",
    ]
    return "\n".join(lines)


def _grounding_lines(tc_iri: URIRef, ledger) -> list[str]:
    """svt:groundedIn is multivalued and deliberately not joined into the
    SPARQL query (same reason as hasInputFile: it would multiply rows per
    run) -- read directly, sorted by IRI for determinism."""
    citations = sorted(ledger.objects(tc_iri, SVT.groundedIn), key=str)
    if not citations:
        return ["### Grounding", "", "_none -- this is an unsupported assertion_", ""]

    lines = ["### Grounding", ""]
    for citation in citations:
        doc = ledger.value(citation, SVT.citesDocument)
        doc_number = ledger.value(doc, SVT.docNumber) if doc is not None else None
        section = ledger.value(citation, SVT.section)
        page = ledger.value(citation, SVT.page)
        quote = ledger.value(citation, SVT.quote)
        rationale = ledger.value(citation, SVT.rationale)
        lines.append(f"**{section}**, p. {page} ({doc_number})")
        lines.append("")
        lines.append(f"> {quote}")
        lines.append("")
        if rationale is not None:
            lines.append(f"*{rationale}*")
            lines.append("")
    return lines


def _resolution_check_lines(tc_iri: URIRef, ledger) -> list[str]:
    """svt:checksResolution facts -- reference-resolution's expected
    posterior state is a *set* of facts, not the single svt:expected
    scalar, so this renders instead of (never alongside) an "expected"
    line for that method."""
    checks = sorted(ledger.objects(tc_iri, SVT.checksResolution), key=str)
    lines = ["- **expected posterior state** (resolution facts):"]
    for check in checks:
        subject = ledger.value(check, SVT.subjectFeature)
        target = ledger.value(check, SVT.expectedTarget)
        lines.append(f"  - `{subject}` must resolve to `{target}`")
    return lines


def _validation_line(tc_iri: URIRef, ledger) -> str:
    """Being SHACL-valid RDF is not the same thing as a human having
    confirmed this claim against the spec -- this is precisely the fact a
    reader needs to trust (or not yet trust) everything below it."""
    validations = list(ledger.subjects(SVT.validates, tc_iri))
    if not validations:
        return "**VALIDATION: none recorded -- `svt run` refuses this TestCase until a human validates it.**"
    by_names = []
    for v in sorted(validations, key=str):
        person = ledger.value(v, PROV.wasAssociatedWith)
        when = ledger.value(v, PROV.startedAtTime)
        name = ledger.value(person, RDFS.label) if person is not None else None
        by_names.append(f"{name or person} ({when})")
    return f"**VALIDATION: confirmed by** {'; '.join(by_names)}"


def _testcase_section(tc_iri: URIRef, rows: list, ledger) -> str:
    slug = _local_slug(tc_iri)
    first = rows[0]
    input_names = sorted(str(o) for o in ledger.objects(tc_iri, SVT.hasInputFile))
    fixtures_dir = fixtures_dir_for(slug)

    lines = [
        f"## {slug}",
        "",
        _validation_line(tc_iri, ledger),
        "",
        str(first.description),
        "",
        f"- **method**: `{first.method}`",
    ]
    prior_state = ledger.value(tc_iri, SVT.priorState)
    if prior_state is not None:
        lines.append(f"- **prior state (x)**: {prior_state}")
    events = ledger.value(tc_iri, SVT.events)
    if events is not None:
        lines.append(f"- **command (u): events**: `{events}`")

    if str(first.method) == "reference-resolution":
        lines += _resolution_check_lines(tc_iri, ledger)
    elif first.expected is not None:
        lines.append(f"- **expected**: `{first.expected}`")
    else:
        lines.append("- **expected**: _not yet settled_")

    lines += [""]
    lines += _grounding_lines(tc_iri, ledger)
    lines += ["### Input", ""]
    for name in input_names:
        path = fixtures_dir / name
        content = path.read_text(encoding="utf-8") if path.exists() else "(missing on disk)"
        lines += [f"**{name}**", "", _fence(content), ""]

    runs = [r for r in rows if r.run is not None]
    lines += ["### Runs", ""]
    if not runs:
        lines += ["_no runs recorded yet_", ""]
    else:
        lines += ["| Implementation | Version | Outcome | Actual |", "|---|---|---|---|"]
        for r in runs:
            lines.append(
                f"| {r.implName} | `{r.commitHash}` | {_outcome_local(r.outcome)} "
                f"| {r.actual if r.actual is not None else ''} |"
            )
        lines.append("")
        for r in runs:
            lines.append(_run_section(r, ledger))

    return "\n".join(lines)


def render_report(testcase_id: str | None = None, implementation_slug: str | None = None) -> str:
    """The whole compiled Markdown report, as a string. Deterministic:
    same ledger state + same fixtures -> byte-identical output, every time.

    Two independent, orthogonal filters give the two report kinds
    docs/workflow.md documents: ``testcase_id`` alone (or neither filter)
    is kind 2, a cross-implementation comparison of one TestCase (or the
    whole ledger); both filters together is kind 1, one TestCase against
    exactly one Implementation.
    """
    ledger = load_full_ledger()
    query_text = QUERY_PATH.read_text(encoding="utf-8")
    init_bindings = {}
    if testcase_id is not None:
        init_bindings["testcase"] = ids.slug_id("testcase", testcase_id)
    if implementation_slug is not None:
        # ?implementation is already a SELECTed variable, matched inside
        # the run OPTIONAL block via `?version svt:ofImplementation
        # ?implementation` -- pre-binding it the same way ?testcase is
        # pre-bound constrains that OPTIONAL match to just this
        # implementation's runs, with no query rewrite needed.
        init_bindings["implementation"] = ids.slug_id("implementation", implementation_slug)
    results = ledger.query(query_text, initBindings=init_bindings)

    by_testcase: dict[URIRef, list] = {}
    order: list[URIRef] = []
    for row in results:
        tc = row.testcase
        if tc not in by_testcase:
            by_testcase[tc] = []
            order.append(tc)
        by_testcase[tc].append(row)

    header = (
        "# sysmlv2-testing report\n\n"
        "Compiled by `svt view` from the ledger + fixtures. Ephemeral --\n"
        "regenerate any time with the same command; never committed.\n\n"
    )
    if testcase_id is not None or implementation_slug is not None:
        scope_parts = []
        if testcase_id is not None:
            scope_parts.append(f"testcase `{testcase_id}`")
        if implementation_slug is not None:
            scope_parts.append(f"implementation `{implementation_slug}`")
        header += f"_Scope: {', '.join(scope_parts)} only._\n\n"
    sections = [_testcase_section(tc, by_testcase[tc], ledger) for tc in order]
    if not sections:
        return header + "_no matching test case found_\n"
    return header + "\n---\n\n".join(sections) + "\n"
