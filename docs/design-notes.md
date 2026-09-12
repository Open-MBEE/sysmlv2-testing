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
  documenting bare vs. explicit `end`-feature redefinition, an
  unresolved cross-tool disagreement (not filed; `expected` is
  deliberately left unset).
- `constraint-eval-declaration-site` — from `BrandFootprintML`'s
  `ISSUES-PROPOSED.md` #1, a minimal, self-contained repro of
  sysml-toolkit's `verify`/`query` evaluating a constraint at its
  declaration site rather than a specific usage's redefined bindings.

The adapter shapes (`structural-check`, `constraint-eval`,
`state-execution`) come from the same source: `BrandFootprintML`'s
`harness/gate.sh` + `tooling/*.py`, which already exercised
`sysmlv2 check --strict`, `opensysml`'s `Connection.eval(...)`, and
`Connection.execute_state(...)` against real models.

## Why `expected` is sometimes unset

Two of the seeded test cases (the "bare `end` redefinition" pair) record a
genuine, unresolved cross-tool disagreement — `sysml-toolkit` accepts the
bare form, `OpenSysML` rejects it, and it isn't settled which (if either)
matches the OMG spec's intent. Rather than guess, `expected` is left
unset, and a `TestRun` against that `TestCase` mechanically records
`earl:cantTell`. See `AGENTS.md`'s "no LLM in the run/compare/log path".
