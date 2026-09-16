---
name: ledger-testing
description: How to ledger a SysML v2 implementation test end to end using the `svt` CLI only — register an implementation/version, add a test case, run it, read back a report. Never hand-edit ledger/*.ttl.
---

# ledger-testing

`svt` is the only thing that writes to this repo's ledger. This skill is
the catechism for using it — never hand-author or hand-edit a `.ttl` file
under `ledger/`. If you find yourself about to write RDF by hand, stop:
there is a CLI command for it, or one is missing and should be added, not
worked around.

Run every command with `uv run svt ...` from the repo root.

**For the exact commands, in order, see `docs/workflow.md`** — construct
→ verify construction → human-validate → run → report → human review →
issue-decide. This skill covers what that document doesn't: how an agent
specifically should behave at each step.

## Before `svt run`: the environment is part of the evidence

Each implementation needs env vars set before it can run — **README's
setup table is the source of truth**; read it rather than inferring the
list from an adapter's code, which is how this was got wrong once already.
As of now: `SYSMLV2_BIN`/`SYSMLV2_LIB_DIR` (sysml-toolkit),
`PILOT_GLUE_CLASSPATH`/`SYSML_LIBRARY_DIR` plus a JDK 21 on `PATH`
(Pilot), `OPENSYSML_VERSION` (OpenSysML, optional).

Why this matters more than ordinary setup friction: a missing standard
library does **not** make these tools fail loudly. The Pilot with no
`SYSML_LIBRARY_DIR` resolves nothing, reports errors on every import, and
still returns a verdict — one that can coincidentally match the expected
value and be recorded as `passed` for entirely the wrong reason. The
adapters now raise `RuntimeError` rather than let that reach the ledger
(`adapters/pilot_implementation.py`'s `_library_dir()`,
`adapters/sysml_toolkit.py`'s `_lib_dir()`), so **if you see one of those
errors, fix the environment — never work around it**, and never treat the
resulting `earl:inapplicable` from some other path as equivalent.

If a run's captured output shows unresolved references to standard-library
names (`ScalarValues`, `Parts::Part`, `Connections`) that the TestCase
never meant to test, stop and check the environment before believing the
verdict.

## The run must be the artifact the Version names

Every `svt:Invocation` records `svt:toolDigest` — the sha256 of the tool
that actually produced its output. When the target `Version` pins an
`svt:artifactDigest` and they differ, `svt run` **refuses and writes
nothing**. Fix the environment so it points at the pinned artifact, or
register what you have as its own `Version` with `svt version add`. Never
work around it: recording a run against a Version it did not execute is
precisely the false provenance this ledger exists to prevent.

A tool's self-reported version is *not* sufficient to tell artifacts apart —
sysml-toolkit's release asset and a local build of the identical source tree
both say `sysmlv2 0.6.0`. Only the digest catches it.

## Re-running is safe: it will not duplicate

`svt run` against an already-recorded (testcase, implementation, version)
does **not** append a second TestRun. Depending on what it finds it
records a `svt:reconfirmedAt` timestamp (same party, same answer), a
`svt:Reproduction` (different party, same answer), or — only when the
answer actually differs — a new TestRun, printing a warning that names
the run it contradicts. The CLI says which of the three happened.

So do not avoid re-running for fear of polluting the ledger, and do not
hand-check for an existing run first; that is the CLI's job and it is
mechanical. Pass `--as <party-id>` when you know which machine you are
(register it with `svt party add`); omit it and the run is
"unattributed", which counts as a party of its own.

If you see the contradiction warning, **stop and check the environment
before believing either result** — a missing standard library produces
confident wrong verdicts, which is what the adapter guards exist for.

## Choosing `--method` when you construct a TestCase

`--method` picks which fact about the state transition `x+ = f(x, u)`
this TestCase checks (see AGENTS.md for the full framing -- each
`Implementation` is a candidate realization of `f`; `x` is
`--prior-state`, almost always omitted; `u` is the command):

| method | checks | establishes | needs |
|---|---|---|---|
| `structural-check` | is `u` even admissible (`u` in `U_x`) — exit code / diagnostics, `clean` or `violated` | `admissibility` only | just the input files |
| `constraint-eval` | a fact about the actual `x+`: a boolean | `posterior-state` | `--eval-expression` and `--eval-subject` (the usage FQN) |
| `state-execution` | a fact about the actual `x+`: the comma-joined states visited | `posterior-state` | `--eval-subject` (the state machine FQN); `--events` is the command `u` |
| `reference-resolution` | facts about the actual `x+`: does each named feature really resolve to the target it should — by real object identity, never diagnostics | `posterior-state` | `--resolves "<subjectFeature>=<expectedTarget>"`, repeatable |

The **establishes** column is what `--method` is checked against: it must
cover the `svt:concerns` of the `--intent` you give. A `posterior-state`
intent whose test cases are all `structural-check` is SHACL-rejected, so
you cannot record a question nothing in the family can answer.

`structural-check` only tells you the input was *legal* — it cannot catch
"ran clean but resolved to the wrong thing" (a real bug this rig found in
its own seeded data — see `docs/design-notes.md`). If your test case is
really about what a reference resolves to, use `reference-resolution`,
not `structural-check`.

**Every TestCase needs `--intent`**, naming a `svt:TestIntent` registered
with `svt intent add --id <slug> --question "...?" --concerns
<admissibility|posterior-state>`. Reuse an existing intent whenever one
fits rather than minting a near-duplicate: test cases sharing an intent
are exactly what makes `svt view --intent <slug>` useful, and what stops
a weak `structural-check` `passed` being read as if it settled a question
about `x+`. Write `--question` as a real question — the trailing `?` is
SHACL-enforced, precisely because a statement is where "here is what I
already found" hides.

**Write `--description` as the requirement, not as a report of what
happened.** It should read identically whether written before or after
anything has ever run against it — see AGENTS.md's "Construction vs.
validation."

**If you don't yet know the correct answer** (e.g. two implementations
disagree and it isn't settled which matches the spec), omit `--expected`
rather than guess. A `TestRun` against an unsettled test case mechanically
records `earl:cantTell`, with the real captured output kept for whoever
adjudicates it later.

## The two steps an agent must never perform

Steps 3 (`svt testcase validate`) and 7 (`svt testrun link-issue`, when
warranted) in `docs/workflow.md` are human-only, enforced by a CLI
denylist (`claude`, `llm`, `ai`, `agent`, ...) on `--by`. **If you are an
agent and just constructed a test case (or triggered a run), stop at
whichever of these steps comes next and hand it to the human directing
your work** — don't attempt to satisfy either yourself by any means,
including with the human's own name supplied. `docs/walkthrough.md`
records exactly that exchange happening once, for real.

## What you will never need to do

- Compute a `TestRun`'s IRI, timestamp, or outcome by hand.
- Decide `passed` vs `failed` yourself — that's `adapters/compare.py`.
- Edit a fixture file after a `TestRun` already cites it — add a new test
  case instead.

## What an agent must never do

- Run `svt testcase validate` on a TestCase it authored, or with any
  `--by` name other than the actual human it's working for.
- Run `svt testrun annotate`/`link-issue` on its own behalf, or with any
  `--by` name other than the actual human it's working for — same
  reasoning, same denylist.
- Treat "SHACL passed" as "this claim is correct" — those are different
  claims; only a human `Validation` record makes the latter one.

A ledger explorer/browser is out of scope for now — `svt view` (see
`docs/workflow.md` for its two report kinds) is the read path; prefer it
over reading the `.ttl` files directly.
