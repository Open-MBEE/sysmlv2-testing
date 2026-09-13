# sysmlv2-testing

A knowledge-graph testing ledger for SysML v2 implementations, built on
[W3C EARL](https://www.w3.org/TR/EARL10-Schema/) and
[PROV-O](https://www.w3.org/TR/prov-o/).

This is a **pipeline, not a platform**. Each `Implementation` is a
candidate realization of a transition function `f`; a `TestCase` states
the correct `x+ = f(x, u)` for a prior state `x` and command `u`
(`TestCase.method` says which fact about that transition is being
checked — see `AGENTS.md`):

```
TestCase input files (u)  ->  pinned tool for (Implementation, Version)  ->  raw stdout/stderr/exit code
        ->  scripted comparator (keyed by TestCase.method) vs the expected x+  ->  earl:outcome
        ->  canonical Turtle, SHACL-validated, appended to the ledger
```

No LLM anywhere in the run/compare/log path. Expected values are grounded
in verbatim-quoted spec citations, not bare assertions — see
`docs/design-notes.md`. See `AGENTS.md` for the full contract.

## Setup

Nothing below is committed to this repo (copyright, or just too large and
binary), but two kinds of local acquisition are needed before `svt run`
does anything real.

### 1. The spec documents

Cited in `sources/sources.ttl` (the citation register — committed) but
held as gitignored PDFs under `sources/local/` (OMG copyright, not
redistributable). Currently three; more may be added as this repo grows
(a new release, an errata pass, a second implementation's own spec):

| `svt document` id | document | where to get it |
|---|---|---|
| `formal-2026-03-02` | SysML v2.0 Part 1: Language Specification | https://www.omg.org/spec/SysML/2.0/ |
| `formal-2026-03-04` | Systems Modeling API and Services v1.0 | https://www.omg.org/spec/SystemsModelingAPI/1.0/ |
| `kerml-1.1-beta2` | Kernel Modeling Language (KerML) | https://www.omg.org/spec/KerML/ — this repo's copy is v1.1 Beta 2 (2026-07), *not* the v1.0 the March-2026 SysML spec cross-references; noted honestly in that citation's `svt:rationale` rather than assumed identical |

Download your own copy of each, save it at the `svt:localPath` recorded
for it in `sources/sources.ttl`, and confirm it's the same edition:
`shasum -a 256 <file>` should match that record's `svt:sha256`. Register
a new document with `svt document add` — never hand-edit
`sources/sources.ttl`.

### 2. The implementations under test

| implementation | how to get it locally | env vars `svt run` needs |
|---|---|---|
| OpenSysML | nothing to clone — `opensysml==<version>` is a real PyPI package (a project dependency; `uv sync` installs it), and the matching `sysml-grpc` server binary is auto-fetched by `opensysml.binary.ensure_binary(...)` on first use | `OPENSYSML_VERSION` (optional — see `adapters/opensysml.py` for the default) |
| sysml-toolkit | `toolchain/get-sysml-toolkit.sh` downloads a pinned release binary (**no PyPI wheel exists** — `pip install sysmlv2` gets an unrelated placeholder, never use it) | `SYSMLV2_BIN` (the binary), `SYSMLV2_LIB_DIR` (an OMG SysML v2 standard library directory — e.g. a `SysML-v2-Release` checkout, or `sysml-toolkit`'s own vendored `spec-refs/SysML-v2-Release/sysml.library`) |
| Pilot Implementation | clone [`Systems-Modeling/SysML-v2-Pilot-Implementation`](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation) yourself, then `toolchain/get-pilot-jar.sh` (**needs JDK 21 specifically** — see the script's header for why) | `PILOT_GLUE_CLASSPATH` (the script prints the value to export), `SYSML_LIBRARY_DIR` (the Pilot repo's own `sysml.library/`, trailing slash) |

Once an implementation's tool is available locally, register the exact
commit you're pinning as a `Version`
(`svt version add --implementation <slug> --commit <full-sha> ...`)
before running anything against it — `svt run` looks the version up by
commit hash, not by "whatever's on PATH."

## Quick start

```bash
uv sync
uv run svt --help
uv run svt verify           # SHACL gate over the whole ledger
uv run svt report           # pass/fail/cantTell/inapplicable/untested census
uv run svt view             # compile a readable Markdown report (reports/, gitignored)
```

To ledger a new test, see
`.claude/skills/ledger-testing/SKILL.md` — or in short:

```bash
uv run svt implementation add --name <slug> --repo <url> --language <lang>
uv run svt version add --implementation <slug> --commit <full-git-sha>
uv run svt document add --id <slug> --doc-number "..." --title "..." \
  --local-path sources/local/<file>.pdf --sha256 <hex>          # if citing a new source
uv run svt citation add --id <slug> --document <doc-id> \
  --section "..." --page "..." --quote "..." [--rationale "..."]
uv run svt testcase add --id <slug> --description "..." \
  --input-file <path>... --method structural-check --expected clean \
  --grounds <citation-id>
uv run svt run --testcase <slug> --implementation <slug> --version <commit>
uv run svt view --testcase <slug>
```

## What's in the ledger already

Ten seeded test cases across four methods (`structural-check`,
`constraint-eval`, `state-execution`, `reference-resolution`), every one
grounded in a verbatim-quoted spec citation, run against real, pinned
builds of all three implementations: [OpenSysML](https://github.com/Open-MBEE/OpenSysML)
(Go), [sysml-toolkit](https://github.com/Open-MBEE/sysml-toolkit) (Rust),
and the OMG's own
[Pilot Implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation)
(Java, driven headlessly via `org.omg.sysml.interactive.SysMLInteractive`
through a small Java shim, `adapters/pilot_glue/Main.java`):

```
$ uv run svt report
passed        14
failed        5
cantTell      0
inapplicable  5
untested      0
```

Every one of those is a real adapter run against a real pinned build —
nothing here is a fixture standing in for a result, and nothing is an
ungrounded coin flip. Two of the `failed`s are the same real bug seen two
different ways — worth calling out, since it's the reason
`reference-resolution` exists at all:

- `redefinition-ambiguity-2` (`structural-check`, exit-code only) records
  sysml-toolkit as `passed` — it exits clean. But
  `redefinition-ambiguity-2-resolution` (`reference-resolution`, checking
  what the two anonymous `:>> items` redefinitions actually resolve to by
  real object identity) shows sysml-toolkit `failed`: they resolve to
  **each other**, not to `Container::items` — a silent wrong-answer bug
  `structural-check` structurally cannot see. `redefinition-ambiguity-3plus`
  shows the same split (`passed` on exit code, `failed` on resolution —
  the 3+ case leaves the reference permanently unresolved). Both grounded
  in KerML's `Type::removeRedefinedFeatures` operation, a general set
  operation over however many redefining memberships exist (not a
  pairwise fold) — OpenSysML records `inapplicable` here (a confirmed
  upstream gap: its only per-element identity is the same colliding
  qualified-name string two anonymous siblings share), the Pilot resolves
  correctly (`passed`).
- sysml-toolkit `failed` on `end-feature-redefinition-bare`: silently
  accepts a bare `:>> source = a;` connection-end redefinition (no `end`
  keyword). Grounded in SysML v2.0 Part 1 §8.4.9.2's
  `checkFeatureEndRedefinition` constraint + §8.2.2.6.2's `isEnd` grammar
  rule — a feature only counts as an end feature when the literal `end`
  is present, so this should be rejected. OpenSysML and the Pilot both
  reject it correctly.
- Pilot Implementation `failed` on `end-feature-redefinition-explicit`:
  rejects the spec's own normative example form (`end :>> source = a;`)
  with `"Must have at least two related elements"` — a genuine
  Pilot-specific bug, not a harness artifact (confirmed against two
  different input-feeding strategies).
- The `inapplicable`s: sysml-toolkit's `verify`/`query` can't do a
  per-usage constraint evaluation (evaluates declaration-site defaults
  instead); neither sysml-toolkit nor the Pilot expose a state-execution
  API; OpenSysML has no reference-resolution path for anonymous features
  (above). All recorded honestly, never faked.

Per-implementation: `uv run svt report --implementation <slug>`. Read any
test case's full detail — grounding, real input, every implementation's
real command/exit code/complete stdout and stderr — with
`uv run svt view --testcase <slug>`.

## Repo layout

```
vocabulary/   the T-box: subclasses of EARL/PROV-O only, never redefines them
shapes/       SHACL shapes gating every write (named, never anonymous)
sources/      spec document + citation register (sources.ttl); PDFs held in sources/local/, gitignored
queries/      the SPARQL query behind `svt view`
ledger/       the data: implementations, test cases, fixtures, runs
adapters/     one module per implementation + the scripted comparators
toolchain/    pinned-binary/build scripts for implementations under test
src/          the svt CLI
tests/        unit, SHACL counterexamples, determinism, PROV consistency
```
