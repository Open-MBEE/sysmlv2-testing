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

## Why `expected` can still be unset

`svt:expected` is only ever set once it's actually grounded. A test case
whose correct behavior genuinely isn't settled by the locally-held sources
should stay unset rather than get a guessed value — a `TestRun` against
it then mechanically records `earl:cantTell` (see AGENTS.md's "no LLM in
the run/compare/log path"). None of the five seeded test cases are
currently in that state, but the mechanism exists for the next one that
is.
