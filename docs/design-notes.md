# Design notes

## Where the seeded test cases came from

Five of this repo's first test cases (`ledger/testcases.ttl`) were ported
from real ad hoc dual-tool testing of `OpenSysML` and `sysml-toolkit` done
before this repo existed, in an unrelated scratch repo (`BrandFootprintML`)
and two public gists:

- `redefinition-ambiguity-2` / `redefinition-ambiguity-3plus` — from
  [a gist](https://gist.github.com/mzargham/f8be45769a7ac851a54405a65d7e723b)
  documenting anonymous `:>>` redefinition of a multi-valued reference
  feature; filed as
  [Open-MBEE/sysml-toolkit#2](https://github.com/Open-MBEE/sysml-toolkit/issues/2).
- `end-feature-redefinition-bare` / `end-feature-redefinition-explicit` —
  from [a second gist](https://gist.github.com/mzargham/7f5abd7697abb126c880ea9fada79013)
  documenting bare vs. explicit `end`-feature redefinition. Originally
  seeded with `expected` deliberately unset (looked like an unresolved
  cross-tool disagreement) — see "Grounding the seeded test cases" below
  for why that turned out to be wrong.
- `constraint-eval-declaration-site` — from `BrandFootprintML`'s
  `ISSUES-PROPOSED.md` #1, a minimal, self-contained repro of
  sysml-toolkit's `verify`/`query` evaluating a constraint at its
  declaration site rather than a specific usage's redefined bindings.

The adapter shapes (`structural-check`, `constraint-eval`,
`state-execution`) come from the same source: `BrandFootprintML`'s
`harness/gate.sh` + `tooling/*.py`, which already exercised
`sysmlv2 check --strict`, `opensysml`'s `Connection.eval(...)`, and
`Connection.execute_state(...)` against real models.

## Grounding the seeded test cases (`svt:groundedIn`)

An `expected` value with nothing backing it is just an assertion. Every
seeded test case is now grounded in a real, verbatim-quoted excerpt of the
actual OMG spec PDFs (`sources/sources.ttl`'s `SpecCitation` records,
registered via `svt document add` / `svt citation add` — never
hand-authored, same as everything else in the ledger). One of these
citations changed a recorded verdict, not just added a footnote:

- **`end-feature-redefinition-bare`'s `expected` was wrong.** It was
  seeded as unset ("looks like an unresolved disagreement"), recording
  `cantTell` for every implementation. Reading the actual spec
  (`formal/2026-03-02` §8.4.9.2's `checkFeatureEndRedefinition` constraint
  + §8.2.2.6.2's `isEnd ?= 'end' (...)` grammar rule — a feature only
  counts as an end feature, and so only satisfies that constraint, when
  the literal `end` keyword is present) shows this isn't actually
  unresolved: the bare `:>> source = a;` form (no `end`) should be
  rejected. `expected` was corrected to `"violated"` via
  `svt testcase set-expected`. sysml-toolkit's silent acceptance of the
  bare form is now a real, grounded conformance finding (`failed`), not a
  coin flip; OpenSysML's and the Pilot's rejection of it are `passed`.
- **`redefinition-ambiguity-2`/`-3plus`** are grounded in the *KerML*
  spec's `Type::removeRedefinedFeatures` operation (a general set
  operation over however many redefining memberships exist — not a
  pairwise fold), which directly corroborates `BrandFootprintML`'s own
  root-cause hypothesis that sysml-toolkit's `drop_redefined_hits`
  diverges from this normative algorithm. Note: the locally-held KerML
  copy is v1.1 Beta 2 (2026-07), not the v1.0 the March-2026 SysML spec
  cross-references — flagged honestly in the citation's `svt:rationale`
  rather than assumed identical.
- **`constraint-eval-declaration-site`** is grounded in §7.20.1 +
  §8.4.16.3 (a constraint usage evaluates against its containing
  context's actual feature values, not declaration-site defaults).

Read a test case's grounding (verbatim quotes and all) with
`svt view --testcase <id>`, not by grepping `sources/sources.ttl`.

## A new finding surfaced by wiring up the Pilot Implementation

Once the Pilot's adapter was actually built and run (see
`toolchain/get-pilot-jar.sh`), it rejected `end-feature-redefinition-explicit`
— `connection l : Link { end :>> source = a; end :>> target = b; }` — with
`"Must have at least two related elements"`, a case both OpenSysML and
sysml-toolkit accept as clean. Confirmed this is the Pilot's own behavior,
not a harness artifact: tried feeding it the two fixture files both as
separate indexed resources and as one concatenated compilation unit
(`adapters/pilot_glue/Main.java`'s current, simpler approach); both give
the same verdict. Recorded as a real three-way divergence — `expected` for
that test case stays `clean` (grounded the same way as the bare form,
since the same citations apply and the explicit form is the spec's own
normative example), so the Pilot's run there is an honest `failed`, not
adjudicated away.

## The rig's own rigor check caught a second real bug: `structural-check` alone is not enough

Z's challenge, verified rather than argued about: does this rig actually
catch "runs clean but produces the wrong answer" bugs, or only "did the
tool report an error"? Checked directly against `redefinition-ambiguity-2`
(the 2-occurrence case, seeded as `structural-check`, `expected: clean`):
sysml-toolkit exits 0 (admissible — `u` is legal at `U_x`), and the ledger
recorded `passed`. But converting that same fixture to compact-json and
walking the real `Redefinition` edges by object id showed the two
anonymous `:>> items` redefinitions resolving to **each other**, not to
`Container::items` — a real, silent, wrong-answer bug the exit-code check
structurally cannot see. This reframes the whole model: each
`Implementation` is a candidate realization of a transition function `f`;
`structural-check` only asks whether a command `u` is admissible (`u` in
`U_x`); it says nothing about whether the resulting `x+ = f(x, u)` is
actually correct.

Fixed by adding a fourth method, `reference-resolution`, which asserts a
*set* of resolved-reference facts (`svt:checksResolution` →
`svt:ResolutionCheck{subjectFeature, expectedTarget}`) checked by real
per-implementation object identity, never diagnostics:

- **sysml-toolkit**: `sysmlv2 convert --to compact-json` + walk
  `Redefinition.redefiningFeature`/`redefinedFeature` `@id` links —
  confirmed the project's own idiomatic test technique (its `IDS.md`
  documents the `@id` stability contract this relies on; its
  `tests/json.rs` does the identical walk). `redefinition-ambiguity-2`/
  `-3plus-resolution` now record real, grounded `failed`s here: the
  2-occurrence case cross-wires silently, the 3+ case leaves
  `redefinedFeature` permanently unresolved (`@ref`, never `@id`) —
  both now visible in the ledger, not hidden behind a clean exit code.
- **Pilot Implementation**: `SysMLInteractive.resolve()` +
  `Feature.getOwnedRedefinition()` + `Redefinition.getRedefinedFeature()`,
  compared by real Java object identity (`==`) — a small
  `adapters/pilot_glue/Main.java` addition (`--redef <container>` mode).
  Resolves correctly in both cases (`passed`).
- **OpenSysML**: confirmed, two ways, genuinely not possible today. Its
  `Symbol`/`Specialization`/`Query` wire protocol's only identity field
  (`SymbolInfo.id`/`Specialization.target_id`, per the actual protobuf
  schema) *is* the same colliding qualified-name string two anonymous
  siblings both get; its `to_turtle()` export assigns them distinguishable
  URIs but represents `sysml:redefines` as a bare declared-name string,
  not a link to the resolved target. Recorded as `earl:inapplicable`,
  with both findings in the `Invocation`'s stderr — a real upstream gap
  worth filing, not something to fake around.

Also added: `svt:events` (state-execution's previously-unmodeled command
`u` — an ordered event sequence) and `svt:priorState` (mostly unused today,
but now a place to record `x` explicitly for a future multi-step
scenario). Seeded the first real state-execution test cases from
`BrandFootprintML`'s own worked `Surface` state-machine example — grounded
in §7.18.2's entry-transition-succession text, which also explains
`BrandFootprintML`'s own `ISSUES-PROPOSED.md` #6 finding (a state machine
with no explicit entry transition has no well-defined initial state).

## The same conflation, still sitting in the ledger: `svt:TestIntent`

The `reference-resolution` method above fixed the *mechanism* gap — the rig
gained a way to check facts about `x+`. It did not fix the *recording* gap,
and a review prompted by a colleague's observation (that the TBox should
capture a test case's intent explicitly) found the residue still in place:

`redefinition-ambiguity-2` kept the description it was seeded with —
"Two anonymous ':>> items' redefinitions ... should both resolve to the
inherited base feature `Container::items`" — under `method:
structural-check`, `expected: clean`. That description asserts a
resolution fact. `structural-check` compares an exit code and cannot
check it. sysml-toolkit's recorded verdict there is `passed`, while
`redefinition-ambiguity-2-resolution`, over the *same fixture*, records
`failed`. Read alone, the first verdict says a tool got right what it in
fact gets wrong. `redefinition-ambiguity-3plus` had the identical defect.
Both survived four audit passes, because each element was individually
well-formed and nothing in the model related the claim to the mechanism.

The generalization: `svt:description` says what the spec requires and
`svt:method` says what gets checked, but nothing said *what question the
test case exists to answer*, so no gate — and no reader — was positioned
to notice when the two came apart.

A free-text `intent` field was considered and rejected. Every description
in this repo was authored by Claude in one session; an `intent` string
written by the same author in the same pass would have restated the
description and agreed with it. It would not have caught this.

`svt:TestIntent` (a subclass of `earl:TestRequirement`, EARL's own "a
requirement established by one or more sub-tests") is instead a shared
node: one `svt:question`, and a `svt:concerns` drawn from a closed set —
`admissibility` (is `u` in `U_x`) or `posterior-state` (a fact about the
actual `x+`). TestCases point at it with `svt:realizesIntent`. Two
consequences, both mechanical:

- **`IntentMethodAlignmentShape`** (`shapes/intent.shapes.ttl`) refuses a
  `posterior-state` intent that no realizing TestCase can establish —
  i.e. exactly the `redefinition-ambiguity-2` family as it would have
  stood had the `-resolution` siblings never been written. Same
  `sh:sparql` style as `TestCaseGroundingRequiredShape`; the
  counterexample proving it is
  `tests/shacl/counterexamples/intent_posterior_state_only_structural_checks.ttl`.
  The shape constrains the *intent*, not each TestCase, so a
  `structural-check` case coexisting with a `reference-resolution` one
  under the same question is permitted — it would contribute real evidence
  without being asked to carry the whole claim. Z's call was not to use
  that latitude here (see below).
- **`svt view` states what a verdict does and does not establish**, under
  every test case, derived from `concerns` + `method` (no per-method prose
  is stored), plus the sibling TestCases realizing the same intent.
  `svt view --intent <slug>` renders a whole family under its question.

**Two intents, not one, for the redefinition family.** The first cut put
all four redefinition TestCases under one `posterior-state` intent, so the
weak `structural-check` pair would render as "establishes admissibility
only" next to the `reference-resolution` pair that actually settles the
question — putting sysml-toolkit's `passed` and its `failed` on one page.
Z split them instead: `anonymous-sibling-redefinition-well-formed`
(`admissibility`) for the two `structural-check` cases,
`anonymous-sibling-redefinition-target` (`posterior-state`) for the two
`-resolution` cases. Every intent in the ledger is now established by
every TestCase realizing it.

The trade is deliberate and worth stating plainly. What it buys: each
intent asks exactly one question and every method under it can answer it,
so there is no "this verdict doesn't settle the question" caveat to read
past. What it costs: nothing in the ledger now links
`redefinition-ambiguity-2`'s `passed` to
`redefinition-ambiguity-2-resolution`'s `failed` over the same fixture; a
reader of the weak verdict is no longer pointed at the strong one.

That cost is smaller than it first looks, because the cross-reference was
the *aid*, not the fix. The actual defect was a description asserting a
resolution fact under a method that checks an exit code; rewording it
("must be accepted as well-formed") is what makes the weak `passed`
honest on its own terms. The grouping only ever made it additionally
legible. A future `svt:TestIntent`-to-`svt:TestIntent` relation could
restore the link without collapsing the questions again — deliberately not
added now, since nothing needs it yet.

One consequence to keep in view: no TestCase in the ledger currently
exercises the "establishes admissibility only" rendering path. It is still
enforced by `IntentMethodAlignmentShape` and covered by
`tests/shacl/counterexamples/intent_posterior_state_only_structural_checks.ttl`,
but it no longer has live data behind it.

`svt:question` must end in `?`, SHACL-enforced. Not a formatting rule: an
interrogative has no grammatical room to narrate an outcome, so the tell
that `svt:Validation` was introduced for ("...not to each other") is
structurally unavailable in this field.

The two descriptions were corrected via `svt testcase set-description` to
claim only admissibility, which is all their method adjudicates; the
resolution claim already lived on the `-resolution` siblings. Neither had
a `Validation` record, so no human's confirmation was invalidated.

Three TestCases (`membership-visibility-private-rejected`,
`state-machine-transitions-on-event`,
`redefinition-ambiguity-2-resolution`) had been validated before this
change, so their `Validation` predated the `svt:realizesIntent`
assertion and did not cover it. Attaching an intent is ordinary
construction, the same as `svt:description` always was — but the record
was only whole once a human re-read and re-validated them. Z did, and
their second `Validation` records carry an `svt:note` saying why a
second record exists. Validation is append-only, so both the original
and the re-validation stand.

## Re-running the worked examples found a third bug — in the harness, not the tools

Re-executing every recorded `TestRun` after the `svt:TestIntent` change
(to confirm the TBox work had not disturbed any recorded evidence) turned
up a defect in this repo's own rig, of exactly the kind it exists to catch.

With `SYSML_LIBRARY_DIR` unset, the Pilot Implementation loads **no
standard library** — and does not fail. It reports `Couldn't resolve
reference to Namespace 'ScalarValues'` and a cascade of consequent errors,
then returns a verdict anyway. Four of the seven Pilot rows flipped
(`clean` → `violated`, resolved targets → `UNRESOLVED:not-found`), which
is loud enough to notice. The dangerous three were the ones that still
said **`passed`**: `membership-visibility-private-rejected` expects
`violated`, and a model that resolves nothing is trivially `violated`, so
it passed for entirely the wrong reason — one error in the recorded run,
three in the broken one, same verdict. A verdict that is right by accident
is indistinguishable, in the ledger, from one that is right on purpose.

`README`'s setup table documented the variable all along. That did not
help, because the environment was reconstructed from the adapter's code
rather than the README — which is exactly what an agent in a fresh clone
will do. Documentation was never the missing piece; enforcement was.

`adapters/sysml_toolkit.py`'s `_lib_dir()` already had the right shape (a
hard `RuntimeError` when `SYSMLV2_LIB_DIR` is unset — a config error must
crash, not become ledger evidence). The Pilot adapter simply never grew
the equivalent. Both now validate, and both now also reject a path that is
set but is not a directory, since a typo fails exactly as silently as an
omission. The error is deliberately **not** `UnsupportedMethod`: `svt run`
catches that and records `earl:inapplicable`, which would turn a broken
machine into a permanent, honest-looking ledger fact.
`tests/unit/test_adapter_env_guards.py` pins all of this, including that
the guard is not an `UnsupportedMethod` — the regression that would
quietly undo it.

Also corrected here: `docs/workflow.md` claimed **two** of the seven steps
were human-gated (3 and 7) and that "an agent may perform every other
step," contradicting its own step 6 eleven lines later, AGENTS.md, and the
`NOT_A_HUMAN` denylist the code actually applies to `svt testrun annotate`.
As written it told an agent it could run a command the CLI refuses.

The re-run itself came back clean: all 27 recorded `TestRun`s reproduce
their exact `outcome` and `actual` under the updated TBox, and no new
`TestRun` was appended — nothing the comparator reads (`svt:method`,
`svt:expected`, `svt:checksResolution`, the fixture bytes) was touched by
the intent work, so duplicating the records would have added noise, not
evidence.

## Duplication vs. reproduction: `svt run` stopped writing a TestRun every time

Removing the redundant `state-machine-transitions-on-event`/opensysml pair
left the obvious question unanswered: nothing stopped it happening again,
and async multi-party work makes it the *default* outcome — two parties
running the same test produce two TestRuns a reader must compare by hand
to discover they say the same thing.

But re-running is valuable. It is how a result stops being one machine's
observation. What was missing was a way to record a successful
reproduction without recording it as new evidence about the tool.

`svt run` now decides between three records, mechanically, before minting
anything. The comparison is on `svt:inputDigest` and the computed
`(outcome, actual)` — deliberately **not** `svt:command`, which carries
absolute local paths (`/Users/z/...`, `/var/folders/...`) and therefore
can never match across machines, which is precisely the case this exists
for.

| same (testcase, version) | |
|---|---|
| same digest, same result, same party | a `svt:reconfirmedAt` timestamp on the existing run |
| same digest, same result, different party | a `svt:Reproduction` |
| same digest, different result | a new `TestRun`, with a warning naming what it contradicts |
| different digest | a new `TestRun` — different inputs, different test |

A `svt:Party` is **a machine or installation, not a person**. What a
reproduction establishes is that a result is not an artifact of one
toolchain; the person at the keyboard is beside the point. It also keeps
`svt run` agent-runnable — that step is not human-gated, so recording who
ran it must never require attributing anything to a `prov:Person`. Absence
of a Party is itself a value ("unattributed"), which is why the runs
recorded before this existed keep working and are not backfilled:
asserting provenance that was never captured is a different thing from it
being true.

A `svt:Reproduction` carries its own `svt:Invocation` and `earl:result`
rather than merely asserting agreement, so
`ReproductionMatchesRunShape` can check that its outcome, `svt:actual` and
input digest really do equal the run it names. "Reproduced" is a verified
fact here, not a word someone wrote next to a run.
`ReproductionDistinctPartyShape` enforces the same-party/different-party
split, and `TestRunNoRedundantDuplicateShape` makes the state that was
cleaned up by hand unrecordable — while still permitting a *differing*
result, which must stay recordable because it is a real finding.

Two things fell out of this that are worth noting:

- **The same-second IRI collision is gone**, not merely narrowed.
  `ids.mint` folded only `(testcase, implementation, version, ts)` with
  `ts` at second resolution, so two runs inside one second minted
  identical IRIs and silently merged their triples — documented as a
  landmine and never fixed. Runs that agree no longer mint anything, and
  runs that disagree now differ in the key because the digest and result
  are folded in.
- **A shape bug, caught by its own test.** The first
  `TestRunNoRedundantDuplicateShape` compared only outcome and
  `svt:actual`, so two runs over *different fixtures* that happened to
  agree were flagged redundant. They are not: different inputs are
  different evidence. The digest is part of the comparison now.

## Why `expected` can still be unset

`svt:expected` is only ever set once it's actually grounded. A test case
whose correct behavior genuinely isn't settled by the locally-held sources
should stay unset rather than get a guessed value — a `TestRun` against
it then mechanically records `earl:cantTell` (see AGENTS.md's "no LLM in
the run/compare/log path"). No seeded test case is currently in that
state — every one is grounded and settled — but the mechanism exists for
the next one that isn't.

## Construction vs. validation: why the gate exists

Z's catch, verbatim, on `redefinition-ambiguity-2-resolution`'s original
description ("...must resolve...to the inherited base feature
Container::items -- not to each other"): that phrasing is LLM narration of
a bug already found, not a prospective, spec-derived requirement written
before anything ran. It's a real tell, not a style nitpick — nothing in
the ledger distinguished "Claude drafted this claim" from "a human
confirmed this is what the spec actually requires." Every
`svt:description`, every `svt:expected`/`svt:checksResolution` value, and
every citation's `svt:rationale` in this repo up to this point was
authored by Claude in a single session; being SHACL-valid RDF never
implied any of it was checked against the spec by a person.

The fix — a new `svt:Validation` record, and `svt run` refusing without
one — is the normative contract in `AGENTS.md`; the exact commands are
`docs/workflow.md`'s step 3. Every seeded TestCase was authored by
Claude, and Claude will not run `svt testcase validate` against its own
claims, since that would defeat the entire point of the gate. So each
one sat unrunnable — `svt run` refusing with the exact command to fix it
— until Z read the cited spec text and validated it himself.

Z has since validated all of them, so nothing in the ledger is currently
blocked by this gate. That is a fact about today, not a property of the
design: every new TestCase starts unvalidated and unrunnable, and the
gate is exactly as load-bearing for the next one as it was for the
first. Read `svt view --testcase <id>` for a given TestCase's current
validation status rather than trusting any count written here.

The grounding requirement (`svt:expected`/`svt:checksResolution` implies
at least one `svt:groundedIn` citation) was already a convention; it is
now a SHACL-enforced shape (`shapes/validation.shapes.ttl`'s
`TestCaseGroundingRequiredShape`, a `sh:sparql` constraint in the same
style as `cds`'s `TermVerbatimGuardShape` -- `cds` is Concept Definition
Stage, an earlier, unrelated project of mine with the same
hallucination-guard discipline) — structurally required, not just a
habit an author is supposed to remember.

**Two `SpecCitation.rationale` fields overreached, and were narrowed.**
Read back against the new "is this narrating a verdict as already
settled?" standard, `rationale` mostly passes: unlike `svt:description`,
its actual job is connecting a quote to a claim, and it may legitimately
name a specific tool's observed behavior — that is not the same failure
mode. Two went further.
`citation-check-feature-end-redefinition` had stated that OpenSysML's
rejection "is spec-conformant, and sysml-toolkit's silent acceptance of
it is a real conformance gap, not an unresolved disagreement," and
`citation-remove-redefined-features` that the algorithm "independently
corroborates BrandFootprintML's own root-cause hypothesis that
sysml-toolkit's `drop_redefined_hits`...diverges from this normative
set-based algorithm." Both read less like "here is why this citation
supports this claim" and more like a settled verdict on a named
implementation's conformance, asserted with the same confidence as the
grounding itself — which is a finding a `TestRun` produces, not
something a citation establishes.

They were flagged here rather than silently rewritten, and Z's call was
to narrow them. Doing so needed a `svt citation set-rationale` command,
which did not exist (`set-quote` and `set-page` did) — a missing update
path, not a reason to hand-edit `sources/sources.ttl`. Both now keep the
quote-to-claim reasoning and the honest KerML v1.1 Beta 2 version caveat,
and drop the conformance verdicts. The findings themselves lost nothing:
they live in the `TestRun`s and the `IssueLink`, where evidence belongs.
