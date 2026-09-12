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

## 1. Is the implementation and version already registered?

```bash
uv run svt implementation add --name <slug> --repo <url> --language <lang>
uv run svt version add --implementation <slug> --commit <full-git-sha> \
  [--label <tag-or-date>] [--source-url <url>] [--artifact-digest <sha256>]
```

`--commit` must be the exact git SHA — that's the whole point of the
ledger's identity model. `--label` is just a human-readable tag/date, not
a substitute. If a version is the one you want future runs to default to
thinking of as "current," also run:

```bash
uv run svt version set-stable --implementation <slug> --version <commit>
```

This *appends* a new stability record; it never overwrites history — old
`TestRun`s stay interpretable against what was stable when they ran.

## 2. Write the test case as a concrete input → expected-output claim

A test case is: some input files, a `method` telling `svt run` which
scripted comparator to use, and (usually) an `expected` value that
comparator checks against.

| method | what it checks | needs |
|---|---|---|
| `structural-check` | exit code / diagnostics, `clean` or `violated` | just the input files |
| `constraint-eval` | a boolean, vs. `expected` (`true`/`false`) | `--eval-expression` and `--eval-subject` (the usage FQN) |
| `state-execution` | the comma-joined states a state machine visits | `--eval-subject` (the state machine FQN) |

```bash
uv run svt testcase add --id <slug> \
  --description "when you do X, it should produce Y" \
  --input-file path/to/one.sysml [--input-file path/to/two.sysml ...] \
  --method structural-check --expected clean
```

**If you don't yet know the correct answer** (e.g. two implementations
disagree and it isn't settled which matches the spec), omit `--expected`.
Do not guess to fill the field. A `TestRun` against an unsettled test case
mechanically records `earl:cantTell` — the honest outcome — with the real
captured output kept in `earl:info` for whoever adjudicates it later.

## 3. Run it

```bash
uv run svt run --testcase <slug> --implementation <slug> --version <commit>
```

This pipes the test case's fixture files into that implementation's own
tool (see `adapters/`), captures the raw output, and logs a `TestRun`.
Nothing about this step is negotiable by an agent — the comparator
decides the outcome, not you. If the implementation's adapter can't
perform this test case's `method` at all (a real, honest limitation, not a
guess), the run records `earl:inapplicable` with why.

Repeat for every `(testcase, implementation, version)` combination you
care about — that's the whole point of a differential ledger.

## 4. Read it back

```bash
uv run svt report                          # everything
uv run svt report --implementation <slug>  # one implementation
uv run svt report --stable-only            # only currently-designated-stable versions
uv run svt verify                          # SHACL gate over the whole ledger
```

`svt verify` should always pass — every write already went through this
same gate before being saved. If it doesn't, something touched
`ledger/*.ttl` outside `svt`; find it and fix it at the source, don't
patch the symptom.

## What you will never need to do

- Compute a `TestRun`'s IRI, timestamp, or outcome by hand.
- Decide `passed` vs `failed` yourself — that's `adapters/compare.py`.
- Edit a fixture file after a `TestRun` already cites it — add a new test
  case instead.

A ledger explorer/browser is out of scope for now; read the `.ttl` files
directly, or `svt report`, until one exists.
