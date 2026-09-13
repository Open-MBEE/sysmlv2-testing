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

## Why `expected` can still be unset

`svt:expected` is only ever set once it's actually grounded. A test case
whose correct behavior genuinely isn't settled by the locally-held sources
should stay unset rather than get a guessed value — a `TestRun` against
it then mechanically records `earl:cantTell` (see AGENTS.md's "no LLM in
the run/compare/log path"). None of the five seeded test cases are
currently in that state, but the mechanism exists for the next one that
is.

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

The fix (see AGENTS.md's "Construction vs. validation: the LLM's role is
bounded" for the normative contract): a new `svt:Validation` record — a
named `prov:Person`, never this repo's own `svt-cli` agent identity,
confirming they read the cited spec text and it says what the claim needs
it to say — is now required before `svt run` will execute a TestCase at
all (`src/sysmlv2_testing/cli.py`'s `run_cmd`, the `_gate_and_save`-style
check right after the version-existence check). `svt testcase validate
--id <id> --by <name>` is the only way to record one, and it refuses a
denylist of LLM/agent-flavored `--by` names. **All ten TestCases seeded so
far are, as of this commit, unvalidated under this gate** — every one was
authored by Claude, and Claude will not run `svt testcase validate`
against its own claims, since that would defeat the entire point of the
gate. `svt run` against any of them refuses with the exact command to fix
it; Z validates each one himself, on his own schedule, once he's read the
cited spec text and confirms it.

The grounding requirement (`svt:expected`/`svt:checksResolution` implies
at least one `svt:groundedIn` citation) was already a convention; it is
now a SHACL-enforced shape (`shapes/validation.shapes.ttl`'s
`TestCaseGroundingRequiredShape`, a `sh:sparql` constraint in the same
style as `cds`'s `TermVerbatimGuardShape`) — structurally required, not
just a habit an author is supposed to remember.

**Flag for Z's own review, not silently rewritten:** the four
`SpecCitation.rationale` fields that exist as of this commit
(`citation-assert-constraint-per-usage-evaluation`,
`citation-check-feature-end-redefinition`,
`citation-remove-redefined-features`,
`citation-state-initial-via-entry-succession`) were read back against the
new "is this narrating a verdict as already settled?" standard. Unlike
`svt:description` (which this same commit rewords for exactly that
reason — see the ten `svt testcase set-description` calls in this
commit's diff), `rationale`'s actual job is connecting a quote to a claim,
and legitimately may name a specific tool's observed behavior — that is
not the same failure mode. But at least two of the four go further than
that: `citation-check-feature-end-redefinition` states outright
"OpenSysML's rejection...is spec-conformant, and sysml-toolkit's silent
acceptance of it is a real conformance gap, not an unresolved
disagreement," and `citation-remove-redefined-features` states
"independently corroborates BrandFootprintML's own root-cause hypothesis
that sysml-toolkit's `drop_redefined_hits`...diverges from this normative
set-based algorithm" — both read less like "here is why this citation
supports this claim" and more like a settled verdict on a specific
implementation's conformance, asserted with the same confidence as the
grounding itself. Left as-is deliberately (this plan's scope was the
construction/validation boundary, not unilaterally re-editing content Z
should review himself) — worth Z's own judgment on whether either crosses
the line, and if so, whether the fix is rewording or is itself something
only a `Validation` pass can settle.
