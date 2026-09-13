# Walkthrough: one real pass, end to end

A worked example following `docs/workflow.md`'s canonical seven-step
procedure, done for real, twice, with real evidence at every step --
`docs/workflow.md` is the generic *how*; this is the concrete example.
Distinct from `docs/design-notes.md` (retrospective rationale for past
decisions).

Steps 3 (validate), 6 (annotate), and 7 (decide on an issue) are
**governance-gated to a human, not an agent** (see
`docs/workflow.md`/`AGENTS.md` -- the same `NOT_A_HUMAN` denylist covers
all three commands). An agent must never perform any of them on its own
behalf, even to "finish the demo" -- that would defeat the entire point
of the gate. When asked to run step 3 directly (even with the human's
own real name supplied), the honest answer was to decline and hand back
the one-line command instead -- see the transcript this walkthrough came
from. So this was, honestly, a two-session document in practice: an
agent got it to the point where a human's judgment was the only thing
missing (steps 1-2), a human ran step 3 himself, and the agent picked
back up for the purely mechanical steps 4-5. Steps 6-7 were the human's
alone -- both examples below ended up not needing an issue, which is a
perfectly fine outcome.

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

Three examples are worked below: one whose actual output is a rejection
(structural-check, `actual: violated`), one whose actual output is a
genuinely computed value (state-execution, `actual: dormant,active`),
and one where the comparator's own verdict is `failed` -- a real,
known, still-open divergence, not a clean pass. All three kinds of
evidence matter; a reader should see all three in this ledger, not just
the two that happen to agree with the spec.

## Example 1: `membership-visibility-private-rejected`

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

Before committing this to the ledger, the claim was checked ad hoc --
outside the ledger, a plain subprocess call, not `svt run` (see
`docs/workflow.md`'s step 1) -- against the Pilot Implementation
directly:

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

### Step 3 — Human validates *(done -- by Zargham)*

Before this ran, `svt run` refused the TestCase outright:

```
$ uv run svt run --testcase membership-visibility-private-rejected \
    --implementation pilot-implementation --version 692170b71867353b8f90341e61556f49a5beb0e5
error: testcase 'membership-visibility-private-rejected' has no svt:Validation record -- ...
```

-- proof the gate was really blocking, not just documenting, this claim.
Z read the KerML p.22 page image sent alongside this walkthrough and ran
the validation himself, in his own terminal (the CLI's `svt` entry point
only exists inside the project's `uv`-managed venv -- `uv run svt ...`,
not bare `svt ...`):

```
$ uv run svt testcase validate --id membership-visibility-private-rejected --by Zargham
https://w3id.org/sysmlv2-testing/id/validation-4402332ac9d82d9e
```

### Step 4 — Trigger the run *(done)*

```
$ uv run svt run --testcase membership-visibility-private-rejected \
  --implementation pilot-implementation \
  --version 692170b71867353b8f90341e61556f49a5beb0e5
passed	https://w3id.org/sysmlv2-testing/id/run-b15d27028dbaff49
```

The real captured evidence, now in `ledger/runs/pilot-implementation.ttl`:
exit code 1, stdout `ERROR: Couldn't resolve reference to Type
'Lib::Widget'. (line 6)` -- exactly the ad hoc probe from step 1,
now logged through the real pipeline (no LLM in this step, ever --
`adapters/compare.py` decided `passed` because `actual == expected ==
"violated"`, not me).

### Step 5 — Report, both kinds *(done)*

This TestCase was later also run against OpenSysML and sysml-toolkit (not
shown in steps 3-4 above, which focus on the Pilot Implementation) --
`structural-check` is supported by all three adapters, so this became the
vehicle for a genuine 3-way comparison. All three: `passed`, `actual:
violated`.

**Kind 1** (one TestCase against one Implementation):

```bash
uv run svt view --testcase membership-visibility-private-rejected --implementation pilot-implementation
```

Committed snapshot:
[`docs/walkthrough-reports/membership-visibility-private-rejected--pilot-implementation.md`](walkthrough-reports/membership-visibility-private-rejected--pilot-implementation.md).

**Kind 2** (cross-implementation comparison):

```bash
uv run svt view --testcase membership-visibility-private-rejected
```

Committed snapshot:
[`docs/walkthrough-reports/membership-visibility-private-rejected--all-implementations.md`](walkthrough-reports/membership-visibility-private-rejected--all-implementations.md)
-- shows all three implementations agreeing, side by side, each with its
own real command/exit code/stdout/stderr.

Both regenerate live (gitignored, ephemeral) under `reports/`; the two
committed files above are point-in-time snapshots kept specifically as
this walkthrough's worked examples of the two report kinds. Their
filenames (`<testcase>--<implementation>.md`, `<testcase>--all-
implementations.md`) are a deliberate, human-readable naming scheme for
this doc's own linking, chosen when committing them -- not what `svt
view` itself names its live output under `reports/`
(`testcase-<id>[-<implementation>].md`); don't expect the two to match
byte-for-byte if you regenerate and compare filenames.

### Step 6 — Human review + operator annotation *(next -- your call)*

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

## Example 2: `state-machine-transitions-on-event`

Example 1's `actual` is always either `clean` or `violated` --
structural-check only ever answers "was this admissible." This example
shows the other half of the ledger: a method whose `actual` is a real,
specific computed value.

**Claim**: a `Surface`'s exhibited state machine, given one
`EngagementEvent`, must transition from `dormant` to `active`.

**Grounded in**: SysML v2.0 Part 1, §7.18.2 "State Definitions and
Usages", p.118 -- the entry-succession shorthand text (this citation was
one of the four with an off-by-one page fixed earlier this pass; the
page sent to Z for this validation was the corrected one).

**Fixture** (`ledger/fixtures/state-machine-transitions-on-event/surface.sysml`,
already seeded before this walkthrough -- reused here rather than
constructing a new TestCase from scratch, since the point of this second
example is the *kind* of output, not a new claim):

```sysml
package StateDemo {
    occurrence def EngagementEvent;

    part def Surface {
        exhibit state condition {
            entry; then dormant;
            state dormant;
            state active;
            transition first dormant accept EngagementEvent then active;
        }
    }

    part surface1 : Surface;
}
```

Confirmed by an ad hoc probe (outside the ledger) before asking Z to
spend time on it:

```
>>> model.execute_state('StateDemo::Surface::condition', events=['EngagementEvent'])
{'states_visited': ['dormant', 'active']}
```

Z read the corrected p.118 and validated it himself:

```
$ uv run svt testcase validate --id state-machine-transitions-on-event --by Zargham
https://w3id.org/sysmlv2-testing/id/validation-5df9d17405b10dce
```

Run against OpenSysML (this method has no path through sysml-toolkit or
the Pilot Implementation -- both adapters raise `UnsupportedMethod` for
`state-execution`; OpenSysML is the only one with a reachable execution
API):

```
$ uv run svt run --testcase state-machine-transitions-on-event \
    --implementation opensysml --version 2b6c1cf6c31266396899a90d3290cfbdf44019b9
passed	https://w3id.org/sysmlv2-testing/id/run-29d5c83c1e3dbdf2
```

`actual`: `dormant,active` -- the real comma-joined state sequence the
tool computed, not `clean`/`violated`, matching `expected` exactly. See
`reports/testcase-state-machine-transitions-on-event.md`.

## Example 3: `redefinition-ambiguity-2-resolution` -- a real failure

Examples 1 and 2 both settled clean. This one didn't, and stayed that
way on purpose -- a genuine, still-open divergence is exactly the kind
of evidence a differential ledger exists to hold onto, not paper over.

**Claim**: each of two anonymous `:>> items` redefinitions of a
multi-valued reference feature must resolve, by real object identity,
to the inherited base feature `Container::items` -- never to each
other.

**Grounded in**: KerML v1.1 Beta 2, §8.3.3.1.10 (`removeRedefinedFeatures`),
p.147 -- a general, sibling-count-independent set operation over the
whole memberships collection (see `reports/testcase-redefinition-ambiguity-2-resolution.md`
for the full quote).

Unlike examples 1-2, this TestCase (and its runs) predates this
walkthrough entirely -- it's the original seeded finding that led to the
whole construction/validation governance model in the first place (see
"Why this exists," above, and `docs/design-notes.md`). Steps 1-2, 4 were
already done; this pass added steps 3, 5, and 7 for real.

### Step 3 — Human validates *(done -- by Zargham)*

```
$ uv run svt testcase validate --id redefinition-ambiguity-2-resolution --by Zargham
https://w3id.org/sysmlv2-testing/id/validation-ba4d619d960026bd
```

### Step 4 — The runs *(already existed)*

| Implementation | Version | Outcome | Actual |
|---|---|---|---|
| pilot-implementation | `692170b7...` | passed | resolves correctly to `Lib::Container::items` |
| opensysml | `2b6c1cf6...` | inapplicable | honestly can't check this (confirmed two independent ways, not a client-wrapping gap -- see `docs/design-notes.md`) |
| sysml-toolkit | `3a13c64a...` (**v0.6.0**) | **failed** | cross-wired: `@0`→`@2`, `@1`→`@1`, instead of the base feature |

### Step 5 — Report, both kinds *(done)*

Committed snapshots:
[kind 1, sysml-toolkit only](walkthrough-reports/redefinition-ambiguity-2-resolution--sysml-toolkit.md),
[kind 2, all three](walkthrough-reports/redefinition-ambiguity-2-resolution--all-implementations.md).

### Step 7 — Decide on an issue *(done -- by Zargham)*

This is a real, already-known upstream conformance gap
([Open-MBEE/sysml-toolkit#2](https://github.com/Open-MBEE/sysml-toolkit/issues/2),
filed from the same ad hoc testing that seeded this TestCase in the
first place):

```
$ uv run svt testrun link-issue \
    --testcase redefinition-ambiguity-2-resolution \
    --implementation sysml-toolkit \
    --version 3a13c64adb93f1d069ce021c598318587126044a \
    --by Zargham \
    --url https://github.com/Open-MBEE/sysml-toolkit/issues/2 \
    --label "sysml-toolkit v0.6.0 (3a13c64a): cross-wires anonymous :>> items redefinitions to each other instead of the base feature"
https://w3id.org/sysmlv2-testing/id/issuelink-b36078b05596c5c6
```

**Why the version is in the label, not just the ledger's structure:**
every `TestRun` is already pinned to an exact `commitHash` -- that part
was never in question. What this makes explicit is that **this record
will never need to be edited or retracted** when the fix ships. Nobody
goes back and marks this `TestRun` "resolved" or deletes the `IssueLink`
-- both stay exactly as true as they always were: *as of sysml-toolkit
v0.6.0, this failed.* When a fixed release comes out, the correct move
is a new `Version` registration and a *new* `TestRun` against it (`svt
version add --implementation sysml-toolkit --commit <new-sha> --label
v0.7.0`, then `svt run` again) -- which checks whether the fix actually
resolves the real semantics correctly, not merely whether the old
symptom went quiet. That new, independent `TestRun` is the evidence the
bug is fixed; editing this one would only destroy evidence.

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

This section is retrospective rationale about *this walkthrough's own*
development, not a worked example -- more `docs/design-notes.md`'s kind
of content than this doc's, kept here anyway because it's tied to the
concrete findings above, not general repo history. It became the seed
for exactly the "separate, explicit cleanup pass" item 5 below asks for:
a full audit (Python codebase, RDF/shapes/ledger data, documentation)
resolved most of what's listed here, and found a good deal more besides
-- see the commit history following this walkthrough's own commits for
the complete list; not re-duplicated here.

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
5. **AGENTS.md / the skill / README.md** were duplicating the same
   step-by-step mechanics in three (then four) places, drifting further
   apart each time a command was added -- **resolved in the documentation
   pass**: `docs/workflow.md` is now the one canonical step list; the
   other three point at it instead of re-stating it.
6. **`toolchain/get-sysml-toolkit.sh` assumed the wrong tarball layout**
   (found and fixed while getting a real 3-way comparison for report
   kind 2, below): it expected a bare `sysmlv2` binary at the top level;
   the real v0.6.0 release asset extracts into its own subdirectory.
   Verified by re-running the corrected script end-to-end.
7. **`README.md` claimed sysml-toolkit's release vendors an OMG stdlib**
   (`spec-refs/SysML-v2-Release/sysml.library`) -- checked directly
   against the real v0.6.0 asset, found false (the release contains only
   the binary, `LICENSE`, and `README.md`), corrected to point at a real
   stdlib source instead.

## Verification this pass ran

- `uv run pytest -q` -- 40 passed.
- `uv run svt verify` -- clean.
- Report kind 1's `--implementation` filter: correctly drops every other
  implementation's name/command/output from a filtered report (tested
  against a TestCase with real multi-implementation runs), and is
  deterministic across repeated renders.
- Report kind 2's cross-comparison: genuine 3-way data for
  `membership-visibility-private-rejected` -- Pilot, OpenSysML, and
  sysml-toolkit all `passed`, all `actual: violated`; and for
  `redefinition-ambiguity-2-resolution` -- a genuine three-way
  *divergence* (passed/inapplicable/failed), not a clean sweep.
- `svt testrun link-issue` exercised for real, not just tested in
  isolation: a version-labeled link to a real, open upstream issue,
  correctly rendered in both report kinds.
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
  ever entering the ledger; `svt run` confirmed to refuse it before
  validation and to actually run and record `passed` (real captured
  `ERROR: Couldn't resolve reference to Type 'Lib::Widget'.`, matching
  `expected: violated`) after Zargham validated it himself.
