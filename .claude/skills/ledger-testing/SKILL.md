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

## Choosing `--method` when you construct a TestCase

Each `Implementation` is a candidate realization of a transition function
`f`; a TestCase states `x+ = f(x, u)` for prior state `x`
(`--prior-state`, almost always omitted) and command `u`. `--method`
picks which fact about `x+` is checked:

| method | checks | needs |
|---|---|---|
| `structural-check` | is `u` even admissible (`u` in `U_x`) — exit code / diagnostics, `clean` or `violated` | just the input files |
| `constraint-eval` | a fact about the actual `x+`: a boolean | `--eval-expression` and `--eval-subject` (the usage FQN) |
| `state-execution` | a fact about the actual `x+`: the comma-joined states visited | `--eval-subject` (the state machine FQN); `--events` is the command `u` |
| `reference-resolution` | facts about the actual `x+`: does each named feature really resolve to the target it should — by real object identity, never diagnostics | `--resolves "<subjectFeature>=<expectedTarget>"`, repeatable |

`structural-check` only tells you the input was *legal* — it cannot catch
"ran clean but resolved to the wrong thing" (a real bug this rig found in
its own seeded data — see `docs/design-notes.md`). If your test case is
really about what a reference resolves to, use `reference-resolution`,
not `structural-check`.

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
