# Walkthrough: one real pass, end to end

A worked example of the full pipeline this repo is built around, done
once, deliberately, before scaling up to running many test cases:
construct → verify construction → human-validate → run → report → human
review/annotate → decide-and-link-an-issue. Distinct from
`docs/design-notes.md` (retrospective rationale for past decisions) and
`AGENTS.md`/the skill (the normative contract) -- this is a runbook you
can literally re-follow, with a real example at every step.

Two of the seven steps below are **governance-gated to a human, not an
agent** (see AGENTS.md's "Construction vs. validation"): step 3
(validate) and step 7 (decide on an issue). An agent must never perform
either on its own behalf, even to "finish the demo" -- that would defeat
the entire point of the gate. So this walkthrough is, honestly, a
two-session document: an agent gets it to the point where a human's
judgment is the only thing missing, and a human finishes it.

## Why this exists

Z's catch on `redefinition-ambiguity-2-resolution`'s original description
led to the construction/validation governance model (`svt:Validation`,
the `svt run` gate -- see `docs/design-notes.md`). Actually *using* that
gate -- pulling up the real cited spec pages for each of the 9 seeded
TestCases so Z had something concrete to check, rather than a citation ID
to trust -- surfaced two real defects in the citations themselves (a
fabricated code example inside one `svt:quote`, and four off-by-one page
numbers), all fixed via new `svt citation set-quote`/`set-page`
commands. That, in turn, made clear the pipeline had never been run
straight through, end to end, as one deliberate act -- and that two steps
in it (a human's comment on a completed run, and linking a run to an
external issue) had no vocabulary, shape, or CLI command at all. This
walkthrough is that first real pass, and the document recording it.

## The example: `membership-visibility-private-rejected`

**Claim**: a part usage typed by a `private part def`, referenced by
qualified name from outside the definition's owning package, must be
rejected -- a private member's membership is not visible outside its
owning namespace.

**Grounded in**: KerML v1.1 Beta 2, §7.2.5.2 "Namespace Declaration",
p.22 -- *"The visibility of the membership can be specified by placing
one of the keywords public, protected or private before the public
element declaration. If the membership is public (the default), then it
is visible outside of the namespace. If it is private, then it is not
visible."* (verbatim, verified directly against the PDF page, not
re-trusted from a paraphrase -- see the page image sent alongside this
walkthrough).

**Fixture** (`ledger/fixtures/membership-visibility-private-rejected/private-visibility.sysml`):

```sysml
package Lib {
    private part def Widget;
}

package Usage {
    part w : Lib::Widget;
}
```

### Step 1 — Construct

```bash
uv run svt citation add --id membership-visibility-private \
  --document kerml-1-1-beta2 \
  --section "7.2.5.2 Namespace Declaration" --page "22" \
  --quote "The visibility of the membership can be specified by placing one of the keywords public, protected or private before the public element declaration. If the membership is public (the default), then it is visible outside of the namespace. If it is private, then it is not visible." \
  --rationale "A private member's membership is not visible outside its owning namespace -- a qualified-name reference to it from outside that namespace should therefore fail name resolution. This grounds expected=violated for a part usage typed by a private part def referenced from a sibling package."

uv run svt testcase add --id membership-visibility-private-rejected \
  --description "A part usage typed by a private part definition, referenced by qualified name from outside the definition's owning package, must be rejected -- the private member is not visible outside its owning namespace." \
  --input-file private-visibility.sysml \
  --method structural-check --expected violated \
  --grounds membership-visibility-private
```

Before committing this to the ledger, the claim was checked ad hoc
(outside the ledger, per AGENTS.md's "exploration is unaffected by the
run gate") against the Pilot Implementation directly:

```
$ java -cp "$PILOT_GLUE_CLASSPATH" svt.Main private-visibility.sysml
ERROR: Couldn't resolve reference to Type 'Lib::Widget'. (line 6)
ERROR: An occurrence, item or part must be typed by occurrence definitions. (line 6)
```

and the counterpart (no `private` keyword -- public is the default) was
confirmed to resolve cleanly:

```
$ java -cp "$PILOT_GLUE_CLASSPATH" svt.Main public-visibility.sysml
CLEAN
```

confirming the claim is real and checkable before it ever went into the
ledger -- not invented to match a guess.

### Step 2 — Verify construction

"SHACL didn't complain" is necessary but not sufficient -- verified three
separate things, not just one:

```bash
$ uv run svt verify
VERDICT: PASS

$ ls ledger/fixtures/membership-visibility-private-rejected/
private-visibility.sysml          # svt:hasInputFile resolves to a real file

$ shasum -a 256 sources/local/kerml-1.1-beta2.pdf
e8b7f33d9dac1a3fdd4eaa64b052608a989b92c580de91fdadb7038d33df99af  sources/local/kerml-1.1-beta2.pdf
# matches svt:sha256 recorded on the cited SpecDocument exactly --
# the citation really points at the PDF actually on disk, not a
# stale or substituted copy.
```

### Step 3 — Human validates *(pending -- this is Z's step)*

```bash
uv run svt testcase validate --id membership-visibility-private-rejected --by <your name>
```

The cited page (KerML p.22) was sent alongside this document for you to
read directly. Confirmed already, mechanically: `svt run` refuses this
TestCase right now --

```
$ uv run svt run --testcase membership-visibility-private-rejected \
    --implementation pilot-implementation --version 692170b71867353b8f90341e61556f49a5beb0e5
error: testcase 'membership-visibility-private-rejected' has no svt:Validation record -- ...
```

-- proof the gate is really blocking, not just documenting, this claim
until you've read the spec text yourself and run the command above.

### Step 4 — Trigger the run *(after step 3)*

```bash
uv run svt run --testcase membership-visibility-private-rejected \
  --implementation pilot-implementation \
  --version 692170b71867353b8f90341e61556f49a5beb0e5
```

Real captured stdout/stderr/exit code get logged into
`ledger/runs/pilot-implementation.ttl` via `svt:Invocation`, compared by
`adapters/compare.py`, and recorded as a `TestRun` -- no LLM in this
step, ever (see AGENTS.md).

### Step 5 — Report

```bash
uv run svt view --testcase membership-visibility-private-rejected
```

### Step 6 — Human review + operator annotation *(after step 4)*

```bash
uv run svt testrun annotate \
  --testcase membership-visibility-private-rejected \
  --implementation pilot-implementation \
  --version 692170b71867353b8f90341e61556f49a5beb0e5 \
  --by <your name> --comment "..."
```

### Step 7 — Decide on an issue *(this is your call, not an agent's)*

If this looks like a real conformance gap in some implementation rather
than settled, correct behavior everywhere: `svt testrun link-issue
--testcase ... --implementation ... --version ... --by <your name> --url
<issue-url> [--label "..."]`. If not: nothing to do, the `TestRun` stands
on its own.

## What this pass built (not just this one TestCase)

Getting to a runnable step 1 required two new post-run capabilities that
didn't exist before this walkthrough:

- `svt:Annotation` / `svt testrun annotate` -- a human's comment on an
  already-completed `TestRun`.
- `svt:IssueLink` / `svt testrun link-issue` -- a human's record that a
  `TestRun` relates to an external issue-tracker entry.

Both are `prov:Activity`-typed, append-only, unbounded-multivalued per
run, gated by the same human-only `NOT_A_HUMAN` denylist as `svt
testcase validate` (factored into one shared `_mint_person` helper so the
refusal behavior can never quietly diverge across commands) -- see
`vocabulary/sysmlv2-testing-core.ttl` and `shapes/annotation.shapes.ttl`.

## Cruft / drift / inconsistency found along the way

Recorded here, not fixed ad hoc -- this list is the seed for a separate,
explicit cleanup pass, not something to silently patch mid-walkthrough:

1. **Citation defects in the existing ledger** (fixed this pass, but
   worth noting *why* they went undetected for as long as they did): one
   `svt:quote` had a fabricated code example inside it
   (`citation-check-feature-end-redefinition`), and four of five
   citations had an off-by-one `svt:page`. All five were only caught by
   opening the actual PDF pages, not by re-reading the citation text --
   the lesson: a citation's own internal consistency (SHACL) says
   nothing about whether it's actually correct, same lesson as
   `svt:Validation`'s whole reason for existing.
2. **`prov:Person` records are duplicated, not shared, across ledger
   files.** `_mint_person`'s new conflicting-label guard (this pass) is a
   stopgap, not the real fix -- the real fix is one canonical
   `ledger/people.ttl` home for every `prov:Person`, which touches
   `_gate_and_save`'s and `load_full_ledger`'s hardcoded per-file tuples
   in `cli.py`/`graph.py`.
3. **`svt run`'s same-wall-clock-second rerun landmine.**
   `ids.mint("run", f"{testcase}|{implementation}|{version}|{ts}")`
   truncates `ts` to the second, so two runs of the identical triple
   within the same second mint the identical IRI and the second write
   fails the SHACL gate outright. Not fixed (documented only) -- a
   genuine rerun just needs to be at least a second apart. (`testrun
   annotate`/`link-issue`'s own mint keys were widened this pass to fold
   in the comment/URL, narrowing but not eliminating the same class of
   collision for *those* two commands.)
4. **`svt run` (top-level) vs. `svt testrun ...` (sub-app) naming
   asymmetry.** Accepted deliberately -- renaming the existing top-level
   `run` would be a breaking CLI change for no real benefit -- but worth
   naming explicitly rather than looking like an oversight.
5. **AGENTS.md / the skill / README.md** should be spot-checked against
   actual current CLI behavior now that `citation set-quote`/`set-page`
   and `testrun annotate`/`link-issue` exist -- not assumed still
   accurate just because new sections were appended.

## Verification this pass ran

- `uv run pytest -q` -- 38 passed.
- `uv run svt verify` -- clean.
- New SHACL shapes (`AnnotationShape`, `IssueLinkShape`): counterexamples
  each fail exactly the shape they target; `_conforms.ttl` passes clean
  with both new classes represented.
- `svt testrun annotate`/`link-issue`: refuse a denylisted `--by`;
  refuse an unknown testcase/version; refuse when more than one `TestRun`
  matches without `--at` (printing every candidate's exact timestamp);
  refuse a `--by` name that collides on `ids.slug_id` with a
  previously-recorded different label; succeed against a real completed
  `TestRun` and appear in `svt view`, sorted deterministically with more
  than one of either.
- This walkthrough's own TestCase: SHACL-valid, fixture file present and
  matching, citation's document sha256 verified against the actual PDF
  on disk, claim checked ad hoc against the Pilot Implementation before
  ever entering the ledger, and `svt run` confirmed to refuse it pending
  validation.
