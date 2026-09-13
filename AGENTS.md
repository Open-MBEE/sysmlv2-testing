# AGENTS.md — contributor contract for sysmlv2-testing

## What this repo is

A testing ledger for SysML v2 implementations: a knowledge graph (W3C EARL
and PROV-O) recording which `Implementation` × `Version` was run against
which `TestCase`, and what actually happened. Each `Implementation` is a
candidate realization of a state-transition function `f`; a `TestCase`
states the correct `x+ = f(x, u)` for a prior state `x` (`svt:priorState`)
and command `u` (input files, plus a method-specific piece), and
`svt:method` says which fact about that transition is being checked —
`structural-check` only asks whether `u` is admissible at all (`u` in
`U_x`), which is a genuinely different, weaker question than whether the
resulting `x+` is actually correct (`constraint-eval`/`state-execution`/
`reference-resolution` each check a real fact about `x+`). Conflating the
two is a real bug this rig found in its own seeded data — see
`docs/design-notes.md`. It is a **pipeline, not a platform** — see the
diagram in `README.md`. Keep it that way. Do not add a dashboard, a web
UI, or a query service; a ledger explorer is explicitly deferred (`svt
view` compiles a read-only Markdown report instead — see `docs/`).

## The one rule that matters: no LLM in the run/compare/log path

Every step from "here is a test case's input" to "here is the recorded
outcome" is deterministic, scripted code — plain Python, a subprocess, a
small Java shim. Never an LLM judgment call.

- **Input**: a `TestCase`'s fixture files go to the tool under test exactly
  as it expects them (file args or stdin) — untouched.
- **Run**: an adapter (`adapters/*.py`) shells out to the pinned
  binary/process for one implementation+version and captures raw
  stdout/stderr/exit code verbatim.
- **Compare**: `adapters/compare.py` checks the captured output against
  `svt:expected`, keyed by `svt:method`. If `expected` is absent, the
  outcome is mechanically `earl:cantTell` — never guessed.
- **Log**: `svt` (`src/sysmlv2_testing/cli.py`) is the only thing that
  writes the ledger.

An LLM/agent may *invoke* `svt` (to register a test case, trigger a run,
etc.) — but the code it triggers is the same deterministic path every
time, regardless of who or what invoked it. If you are an agent working in
this repo: never write to `ledger/*.ttl` directly, never hand-author a
`TestRun`, and never decide an `earl:outcome` yourself — call `svt run`
and let the comparator decide.

## Construction vs. validation: the LLM's role is bounded

The rule above covers *execution* (no LLM in run/compare/log). It says
nothing about *construction* — and an LLM constructing a TestCase via the
CLI can still produce SHACL-valid RDF around an invented claim. Being
structurally well-formed is not the same thing as being true. So:

- **Construct** — an agent may draft a `TestCase` via `svt testcase add`
  (description, method, expected/`--resolves`, `--grounds`). This is
  fine — the CLI's own gate keeps it correct-by-construction.
- **SHACL-gate** — every write already goes through `_gate_and_save`
  (`src/sysmlv2_testing/cli.py`). This confirms the RDF is well-formed
  and, since the grounding-required shape landed, that any `expected`/
  `checksResolution` cites at least one `SpecCitation`. It does **not**
  confirm the citation actually says what the claim needs it to say —
  that's still just an LLM's or a human's assertion at this point.
- **Human-validate** — `svt testcase validate --id <id> --by <name>`
  records that a **named human** (never an LLM/agent name — the CLI
  refuses a denylist of those) actually read the cited spec text and
  confirmed the claim. This is the step that makes a claim trustworthy,
  and it is the one step an agent must never perform on its own behalf.
- **Run** — `svt run` refuses outright if no `svt:Validation` record
  exists for the target TestCase. Constructing and SHACL-gating a claim
  is necessary but not sufficient to make it runnable.

**If you are an agent: never call `svt testcase validate` for a TestCase
you authored, or with any name other than the actual human directing your
work.** Doing so would make the ledger indistinguishable from one where a
human genuinely checked every claim against the spec, which is the exact
failure mode this gate exists to prevent.

**`svt:description` is a requirement statement, not commentary.** Write
it the way the spec states the requirement — it should read identically
whether written before or after anything has ever been run against it.
Never phrase it as narration of an outcome ("...not to each other",
"...confirms the bug", "...as expected") — that reads as an LLM
describing what it just found, which is precisely the tell that a claim
was invented to match an observation rather than derived from the spec
first. `svt:rationale` (on a `SpecCitation`) is different and may
legitimately connect a quote to a claim, including naming a specific
tool's behavior the citation settles — that is rationale's actual job.

## Authority tiers

| Tier | Paths | Rule |
|---|---|---|
| Vocabulary | `vocabulary/`, `shapes/` | Hand-edited. Every class must be `rdfs:subClassOf` an EARL or PROV-O class — extend by subclassing, never redefine. Adding a property is fine; changing what an existing one means is not (it's load-bearing for every past `TestRun`). |
| Ledger | `ledger/*.ttl`, `ledger/runs/*.ttl` | **Never hand-edit.** Written only by `svt` commands. If a file doesn't match what `svt` would produce from its own triples, something is wrong — regenerate, don't patch. |
| Fixtures | `ledger/fixtures/<testcase-id>/` | Written by `svt testcase add` (it copies the files you pass it). Don't edit a fixture after a `TestRun` cites it — add a new `TestCase` instead; a `TestRun`'s evidentiary value depends on the input it actually saw. |
| Sources | `sources/sources.ttl` (committed), `sources/local/` (gitignored) | The two OMG spec PDFs are copyrighted and held locally only. `sources.ttl`'s sha256 entries are how anyone confirms their own copy is the same edition — keep them in sync if a PDF is replaced. |
| Adapters/toolchain | `adapters/`, `toolchain/` | Plain code. A new implementation gets a new adapter module implementing `adapters.base.Adapter`; it should raise `UnsupportedMethod` honestly rather than fake a result for a method it can't perform. |

## Adding a test case, in one sentence

Use the `ledger-testing` skill (`.claude/skills/ledger-testing/SKILL.md`),
or directly: `svt testcase add` with your fixture files, ground it,
**have a human run `svt testcase validate`**, then `svt run` it against
each `Implementation`/`Version` you care about, then `svt report`.

## Reproducibility

- `uv sync` reproduces the whole Python environment (`uv.lock` is
  committed).
- Each implementation under test is pinned independently: OpenSysML via
  `opensysml==<version>` (the client) plus its own
  `opensysml.binary.ensure_binary(version=...)` (the server binary);
  sysml-toolkit via `toolchain/get-sysml-toolkit.sh` (no PyPI wheel exists
  — never `pip install sysmlv2` expecting Open-MBEE's tool, that name is
  an unrelated placeholder); the Pilot Implementation via
  `toolchain/get-pilot-jar.sh` (a one-time local Maven/Tycho build; needs
  a JDK).
- A `Version`'s `commitHash` (and, where applicable, `artifactDigest`) are
  both required so a `TestRun` is reproducible from the ledger alone.

## Design source

Several seeded test cases and the adapter shapes (`structural-check`,
`constraint-eval`, `state-execution`, `reference-resolution`) come from
real ad hoc dual-tool testing the repo's author did before this repo
existed — see the credit in `docs/design-notes.md`. When adding a new
test case, prefer a real, reproducible divergence you actually observed
over an invented one.
