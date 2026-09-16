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
from .namespaces import POSTERIOR_STATE_METHODS, PROV, ROOT, SVT

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
    reproductions = [c for c in concerning if (c, RDF.type, SVT.Reproduction) in ledger]
    lines = []
    # Confirmations first: whether a result has held elsewhere changes how
    # much weight everything below it carries.
    for ts in sorted(str(o) for o in ledger.objects(run_iri, SVT.reconfirmedAt)):
        lines.append(f"- **reconfirmed** by the same party ({ts}) -- identical result, no new record")
    for r in reproductions:
        party = ledger.value(r, SVT.ranBy)
        name = ledger.value(party, RDFS.label) if party is not None else None
        when = ledger.value(r, PROV.startedAtTime)
        lines.append(f"- **reproduced** by {name or party} ({when}) -- independently, same result")
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
    # The timestamp is part of the heading, not just a field further down:
    # without it two runs of the same impl@commit render under identical
    # headings and a reader cannot tell which section is which.
    lines = [
        f"#### {row.implName} @ `{row.commitHash}`{label} -- {row.startedAtTime}",
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


def _intent_lines(tc_iri: URIRef, method: str, ledger) -> list[str]:
    """The question this TestCase bears on, and -- the part that makes a
    verdict readable -- whether this TestCase's method can actually settle
    it. A structural-check under a posterior-state intent contributes real
    evidence (the input was admissible) but cannot establish the intent, so
    its `passed` must not be read as confirming the question. Saying so
    here, next to the method, is what stops a reader doing exactly that.

    Derived entirely from svt:concerns + svt:method + svt:realizesIntent --
    no per-method prose is stored anywhere; POSTERIOR_STATE_METHODS is the
    same partition shapes/intent.shapes.ttl enforces.
    """
    intent = ledger.value(tc_iri, SVT.realizesIntent)
    if intent is None:
        return ["- **intent**: _none recorded_"]

    question = ledger.value(intent, SVT.question)
    concerns = str(ledger.value(intent, SVT.concerns))
    lines = [f"- **intent**: {question} (`{_local_slug(intent)}`, concerns: {concerns})"]

    establishes = concerns == "admissibility" or method in POSTERIOR_STATE_METHODS
    if establishes:
        lines.append(f"  - this method establishes the intent's `{concerns}` question directly.")
    else:
        lines.append(
            "  - **this method establishes admissibility only** -- a verdict here says the "
            "input was accepted, not that the intent's question about `x+` is settled."
        )

    siblings = sorted(
        (s for s in ledger.subjects(SVT.realizesIntent, intent) if s != tc_iri), key=str
    )
    if siblings:
        names = ", ".join(f"`{_local_slug(s)}`" for s in siblings)
        lines.append(f"  - also realized by: {names}")
    elif not establishes:
        lines.append(
            "  - no other test case realizes this intent, so nothing here settles it yet."
        )
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
    ]
    lines += _intent_lines(tc_iri, str(first.method), ledger)
    lines.append(f"- **method**: `{first.method}`")
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


def render_report(
    testcase_id: str | None = None,
    implementation_slug: str | None = None,
    intent_id: str | None = None,
) -> str:
    """The whole compiled Markdown report, as a string. Deterministic:
    same ledger state + same fixtures -> byte-identical output, every time.

    Three independent, orthogonal filters. ``testcase_id`` alone (or no
    filter at all) is kind 2, a cross-implementation comparison of one
    TestCase (or the whole ledger); with ``implementation_slug`` too it is
    kind 1, one TestCase against exactly one Implementation.

    ``intent_id`` is the third: every TestCase bearing on one question,
    together. That grouping is the point of a shared svt:TestIntent -- a
    weak structural-check `passed` and the reference-resolution `failed`
    that actually settles the same question are misleading read apart and
    correct read together.
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

    # An intent selects a *set* of test cases, so it can't be pre-bound the
    # way ?testcase and ?implementation are -- filter the rows instead.
    keep: set[URIRef] | None = None
    if intent_id is not None:
        keep = set(ledger.subjects(SVT.realizesIntent, ids.slug_id("intent", intent_id)))

    by_testcase: dict[URIRef, list] = {}
    order: list[URIRef] = []
    for row in results:
        tc = row.testcase
        if keep is not None and tc not in keep:
            continue
        if tc not in by_testcase:
            by_testcase[tc] = []
            order.append(tc)
        by_testcase[tc].append(row)

    header = (
        "# sysmlv2-testing report\n\n"
        "Compiled by `svt view` from the ledger + fixtures. Ephemeral --\n"
        "regenerate any time with the same command; never committed.\n\n"
    )
    if testcase_id is not None or implementation_slug is not None or intent_id is not None:
        scope_parts = []
        if intent_id is not None:
            scope_parts.append(f"intent `{intent_id}`")
        if testcase_id is not None:
            scope_parts.append(f"testcase `{testcase_id}`")
        if implementation_slug is not None:
            scope_parts.append(f"implementation `{implementation_slug}`")
        header += f"_Scope: {', '.join(scope_parts)} only._\n\n"
    if intent_id is not None:
        intent_iri = ids.slug_id("intent", intent_id)
        question = ledger.value(intent_iri, SVT.question)
        concerns = ledger.value(intent_iri, SVT.concerns)
        if question is not None:
            header += f"**Question:** {question}\n\n_Concerns: {concerns}._\n\n"
    sections = [_testcase_section(tc, by_testcase[tc], ledger) for tc in order]
    if not sections:
        return header + "_no matching test case found_\n"
    return header + "\n---\n\n".join(sections) + "\n"
