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
view` compiles a read-only Markdown report instead — see
`docs/workflow.md`).

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
structurally well-formed is not the same thing as being true. The full
construct → SHACL-gate → human-validate → run → report → human review →
issue-decide sequence, with the exact commands for each step, is
`docs/workflow.md`; the two normative rules that must live here, not
just there:

- **`svt testcase validate`** records that a **named human** (never an
  LLM/agent name — the CLI refuses a denylist of those) actually read
  the cited spec text and confirmed the claim. This is the step that
  makes a claim trustworthy, and it is the one step an agent must never
  perform on its own behalf, for a TestCase it authored or with any
  `--by` name other than the actual human directing the work — doing so
  would make the ledger indistinguishable from one where a human
  genuinely checked every claim, the exact failure mode this gate
  exists to prevent. `svt run` refuses outright without this record.
- **`svt testrun annotate`/`link-issue`** (post-run: a human's comment
  on a completed `TestRun`, or a link to an external issue) are gated
  by the same denylist and the same rule — an agent must never run
  either on its own behalf. See `docs/walkthrough.md` for a worked
  example of exactly that boundary being tested and held.

**Re-running a test is not the same act as testing it.** `svt run` no
longer writes a TestRun unconditionally. Keyed on `svt:inputDigest` and
the computed `(outcome, actual)` — never on `svt:command`, which carries
absolute local paths and cannot match across machines — it writes: a
`svt:reconfirmedAt` timestamp when the same party gets the same answer
from the same bytes; a `svt:Reproduction` when a *different*
`svt:Party` does; and a new `TestRun` with a loud warning when the answer
differs, because a contradiction over identical inputs is real evidence
and nothing is retracted. A `svt:Party` is a machine or installation,
never a person — what a reproduction establishes is that a result is not
an artifact of one toolchain, and it keeps this step agent-runnable. Two
TestRuns of one TestCase against one Version that agree on outcome,
`svt:actual` and input bytes are a SHACL violation; the ledger carried
such a pair until it was removed by hand, and nothing had stopped it.

**`svt:intent` is the question; `svt:description` is the requirement.**
Every `TestCase` names exactly one `svt:TestIntent` (`--intent`), whose
`svt:question` must be an actual question — the trailing `?` is
SHACL-enforced, because an interrogative has no grammatical room to
narrate an outcome. Its `svt:concerns` (`admissibility` |
`posterior-state`) is what makes the question checkable against the
chosen `svt:method`: a `posterior-state` intent realized only by
`structural-check` test cases is refused at the gate, since nothing in
that family could answer it. Test cases share one intent when they
genuinely ask the same question — the zero-event and one-event halves of
a state-machine question, say — and get separate intents when the
questions differ, even over the same fixture: "is this model accepted"
and "does this reference resolve correctly" are two questions, not one
asked two ways. `svt view --intent <slug>` renders each family under its
question. This existed as prose in this file and nowhere in the data
until a real defect showed up in the ledger; see `docs/design-notes.md`.

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

## Adding a test case

See `docs/workflow.md` for the full step-by-step procedure, or the
`ledger-testing` skill (`.claude/skills/ledger-testing/SKILL.md`) for the
same steps framed for an agent to follow.

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
- A `Version`'s `commitHash` identifies the source; its `artifactDigest`
  identifies the exact binary. **`artifactDigest` is what makes a `TestRun`
  reproducible from the ledger alone**, and it is now enforced rather than
  asserted: every `Invocation` records `svt:toolDigest`, the sha256 of the
  tool that actually produced its output, and `svt run` refuses to write a
  run whose tool does not match the digest pinned on the `Version` it names.
  This was a real hole — `svt run --version` never reaches an adapter (each
  picks its tool from the environment), so until the digest existed a
  `TestRun`'s `earl:subject` was a label nothing checked.
- **Pin an artifact others can obtain.** sysml-toolkit's release asset and a
  local build of the byte-identical tree are different bytes and *both
  report `sysmlv2 0.6.0`* — the self-reported version cannot tell them
  apart, only the digest can. Pin the release
  (`toolchain/get-sysml-toolkit.sh`). Where no release artifact exists — the
  Pilot, which is built locally by design — the pinned digest is honestly
  specific to one build, and a second party will have to register their own
  `Version` rather than reproduce yours.

## Design source

Several seeded test cases and the adapter shapes (`structural-check`,
`constraint-eval`, `state-execution`, `reference-resolution`) come from
real ad hoc dual-tool testing the repo's author did before this repo
existed — see the credit in `docs/design-notes.md`. When adding a new
test case, prefer a real, reproducible divergence you actually observed
over an invented one.
