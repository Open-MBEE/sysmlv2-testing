# Workflow: the standard procedure, step by step

The canonical, TestCase-agnostic sequence for ledgering one test end to
end. Every command below is generic (`<placeholders>`, no specific
TestCase) — for a real, worked example following these exact steps, see
`docs/walkthrough.md`. For *why* each governance boundary exists, see
`AGENTS.md`; this document is the *how*.

Two of the seven steps are governance-gated to a human, never an agent
(step 3 and step 7) — see AGENTS.md's "Construction vs. validation: the
LLM's role is bounded." An
agent may perform every other step.

## 1. Construct

Register the `Implementation`/`Version` first if they aren't already
(`svt implementation add`, `svt version add`), then the `TestCase`
itself, grounded in a real, verbatim-quoted spec citation:

```bash
uv run svt document add --id <doc-slug> --doc-number "..." --title "..." \
  --local-path sources/local/<file>.pdf --sha256 <hex>   # if citing a new source

uv run svt citation add --id <slug> --document <doc-slug> \
  --section "..." --page "..." --quote "..." [--rationale "..."]

uv run svt testcase add --id <slug> --description "..." \
  --input-file <path>... --method <method> --expected <value> \
  --grounds <citation-id>
```

Write `--description` as the requirement the spec states, in the same
tense/voice whether written before or after anything has run — never as
commentary on an outcome (see AGENTS.md). `--expected`/`--resolves` with
no `--grounds` is SHACL-rejected outright.

Before this ever touches the ledger, check the claim ad hoc against at
least one real implementation (outside the ledger — a subprocess/Python
one-off, not `svt run`) so a citation and a fixture are checked against
each other, not invented to match a guess.

## 2. Verify construction

"SHACL didn't complain" is necessary but not sufficient. Check three
separate things, not just one:

```bash
uv run svt verify                          # SHACL gate over the whole ledger
ls ledger/fixtures/<slug>/                 # svt:hasInputFile resolves to a real file
shasum -a 256 sources/local/<file>.pdf      # matches the cited SpecDocument's svt:sha256
```

## 3. Human validates *(a human step, never an agent's)*

```bash
uv run svt testcase validate --id <slug> --by <your name> [--note "..."]
```

Confirms a **named human** actually read the cited spec text and it says
what the claim needs it to say — distinct from, and required in addition
to, SHACL structural validity. `svt run` refuses outright without this
record. The CLI denylists LLM/agent-flavored `--by` names; an agent must
never run this command for a TestCase it authored, or with any name
other than the actual human directing the work, even when explicitly
asked to (see AGENTS.md, and `docs/walkthrough.md` for how that
exchange actually went).

## 4. Trigger the run

```bash
uv run svt run --testcase <slug> --implementation <slug> --version <commit>
```

Pipes the TestCase's fixture files into that implementation's own tool,
captures raw stdout/stderr/exit code verbatim, compares against
`expected` with a scripted comparator (`adapters/compare.py`), and logs
a `TestRun`. No LLM anywhere in this path. Repeat for every
`(testcase, implementation, version)` combination you care about — that
is the whole point of a differential ledger.

## 5. Report — two kinds

`svt view` compiles a deterministic Markdown report (one SPARQL query +
the fixture files) under `reports/` (gitignored, ephemeral — fully
reproducible from the ledger + fixtures at any time, never itself a
source of truth).

**Kind 1 — one TestCase against one Implementation**, full detail
(grounding, real input, real command/exit code/stdout/stderr):

```bash
uv run svt view --testcase <slug> --implementation <slug>
```

**Kind 2 — a cross-implementation comparison of one TestCase**: every
implementation's run of the same TestCase, side by side, in one report
(a summary table plus each run's full detail). This is what surfaced the
real, silent cross-wiring bug this repo's own seeded data caught — a
result that only shows up when implementations are compared against
each other, not read one at a time:

```bash
uv run svt view --testcase <slug>
```

(Omitting `--testcase` too compiles every TestCase in the ledger into
one report — rarely what you want day to day, but useful as a full
snapshot. `--implementation <slug>` alone, without `--testcase`, is a
third combination `svt view` accepts: every TestCase's runs, filtered
to just that one implementation — useful for "what has this
implementation actually been tried against so far," across the whole
ledger rather than one TestCase at a time.)

A third, coarser command, `svt report [--implementation <slug>]
[--stable-only]`, is neither of these two kinds — it's a quick tally
(counts of `passed`/`failed`/`cantTell`/`inapplicable`/`untested` across
the whole ledger), useful as a dashboard-free sanity check, not a
substitute for reading an actual `svt view` report before trusting a
result.

## 6. Human review + operator annotation

```bash
uv run svt testrun annotate --testcase <slug> --implementation <slug> --version <commit> \
  --by <your name> --comment "..."
```

Records a human's free-text observation about one specific,
already-completed `TestRun` — distinct from step 3's `Validation`, which
is about the claim before any run happens. Same human-only denylist.
Multiple annotations per run are fine (an operator conversation over
time, not a single slot).

## 7. Decide on an issue *(a human step, never an agent's)*

If the run's outcome looks like a real conformance gap worth filing
upstream:

```bash
uv run svt testrun link-issue --testcase <slug> --implementation <slug> --version <commit> \
  --by <your name> --url <issue-url> [--label "..."]
```

If not — a clean pass, or an already-known, already-tracked divergence —
there is nothing to do; the `TestRun` stands on its own as the evidence.
Not every worked example needs an issue at the end.
