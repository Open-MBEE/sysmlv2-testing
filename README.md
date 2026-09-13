# sysmlv2-testing

A knowledge-graph testing ledger for SysML v2 implementations, built on
[W3C EARL](https://www.w3.org/TR/EARL10-Schema/) and
[PROV-O](https://www.w3.org/TR/prov-o/).

This is a **pipeline, not a platform** (see `AGENTS.md` for the full
`x+ = f(x, u)` state-transition framing this ledger is built around):

```
TestCase input files (u)  ->  pinned tool for (Implementation, Version)  ->  raw stdout/stderr/exit code
        ->  scripted comparator (keyed by TestCase.method) vs the expected x+  ->  earl:outcome
        ->  canonical Turtle, SHACL-validated, appended to the ledger
```

No LLM anywhere in the run/compare/log path. Every claim is grounded in
a verbatim-quoted spec citation and confirmed by a named human (never an
agent) before `svt run` will execute it — see `AGENTS.md` for the full
contract.

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
| `kerml-1-1-beta2` | Kernel Modeling Language (KerML) | https://www.omg.org/spec/KerML/ — this repo's copy is v1.1 Beta 2 (2026-07), *not* the v1.0 the March-2026 SysML spec cross-references; noted honestly in that citation's `svt:rationale` rather than assumed identical |

Download your own copy of each, save it at the `svt:localPath` recorded
for it in `sources/sources.ttl`, and confirm it's the same edition:
`shasum -a 256 <file>` should match that record's `svt:sha256`. Register
a new document with `svt document add` — never hand-edit
`sources/sources.ttl`.

### 2. The implementations under test

| implementation | how to get it locally | env vars `svt run` needs |
|---|---|---|
| OpenSysML | nothing to clone — `opensysml==<version>` is a real PyPI package (a project dependency; `uv sync` installs it), and the matching `sysml-grpc` server binary is auto-fetched by `opensysml.binary.ensure_binary(...)` on first use | `OPENSYSML_VERSION` (optional — see `adapters/opensysml.py` for the default) |
| sysml-toolkit | `toolchain/get-sysml-toolkit.sh` downloads a pinned release binary (**no PyPI wheel exists** — `pip install sysmlv2` gets an unrelated placeholder, never use it) | `SYSMLV2_BIN` (optional — defaults to `sysmlv2` on PATH, see `adapters/sysml_toolkit.py`), `SYSMLV2_LIB_DIR` (an OMG SysML v2 standard library directory, required — the v0.6.0 release asset does **not** vendor one, verified directly; use a `SysML-v2-Release` checkout, or the Pilot Implementation's own `sysml.library/` if you already have that cloned) |
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

## Where to go next

- **[`docs/workflow.md`](docs/workflow.md)** — the canonical, TestCase-
  agnostic step-by-step procedure: construct → verify construction →
  human-validate → run → report → review → issue-decide. Start here to
  ledger a new test.
- **[`docs/walkthrough.md`](docs/walkthrough.md)** — the same procedure
  worked end to end against real TestCases, with real commands and real
  captured output at every step (including committed report snapshots
  under `docs/walkthrough-reports/`). Read this before adding your own
  first real TestCase.
- **`AGENTS.md`** — the contributor contract: the state-transition
  framing, the no-LLM-in-run/compare/log rule, and why a human (never an
  agent) must validate a claim before it can run.
- **[`docs/design-notes.md`](docs/design-notes.md)** — retrospective
  rationale for past design decisions, including a real bug this rig's
  own seeded data caught (why `structural-check` alone isn't enough).
- **`.claude/skills/ledger-testing/SKILL.md`** — the same workflow,
  framed for an agent to follow.

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
docs/         workflow.md (the SOP), walkthrough.md (a full worked example,
              + its committed report snapshots under walkthrough-reports/),
              design-notes.md (retrospective rationale for past decisions)
```
