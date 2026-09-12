# AGENTS.md — contributor contract for sysmlv2-testing

## What this repo is

A testing ledger for SysML v2 implementations: a knowledge graph (W3C EARL
+ PROV-O) recording which `Implementation` × `Version` was run against
which `TestCase`, and what actually happened. It is a **pipeline, not a
platform** — see the diagram in `README.md`. Keep it that way. Do not add
a dashboard, a web UI, or a query service; a ledger explorer is explicitly
deferred (see `docs/`).

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
or directly: `svt testcase add` with your fixture files, then `svt run` it
against each `Implementation`/`Version` you care about, then `svt report`.

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
`constraint-eval`, `state-execution`) come from real ad hoc dual-tool
testing the repo's author did before this repo existed — see the credit
in `docs/design-notes.md`. When adding a new test case, prefer a real,
reproducible divergence you actually observed over an invented one.
