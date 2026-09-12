# sysmlv2-testing

A knowledge-graph testing ledger for SysML v2 implementations, built on
[W3C EARL](https://www.w3.org/TR/EARL10-Schema/) and
[PROV-O](https://www.w3.org/TR/prov-o/).

This is a **pipeline, not a platform**:

```
TestCase input files  ->  pinned tool for (Implementation, Version)  ->  raw stdout/stderr/exit code
        ->  scripted comparator (keyed by TestCase.method) vs TestCase.expected  ->  earl:outcome
        ->  canonical Turtle, SHACL-validated, appended to the ledger
```

No LLM anywhere in the run/compare/log path. See `AGENTS.md` for the full
contract.

## Quick start

```bash
uv sync
uv run svt --help
uv run svt verify   # SHACL gate over the whole ledger
uv run svt report   # pass/fail/cantTell/inapplicable/untested census
```

To ledger a new test, see
`.claude/skills/ledger-testing/SKILL.md` — or in short:

```bash
uv run svt implementation add --name <slug> --repo <url> --language <lang>
uv run svt version add --implementation <slug> --commit <full-git-sha>
uv run svt testcase add --id <slug> --description "..." \
  --input-file <path>... --method structural-check --expected clean
uv run svt run --testcase <slug> --implementation <slug> --version <commit>
uv run svt report
```

## What's in the ledger already

Five seeded test cases (ported from real ad hoc testing — see
`docs/design-notes.md`), run against real, pinned builds of
[OpenSysML](https://github.com/Open-MBEE/OpenSysML) and
[sysml-toolkit](https://github.com/Open-MBEE/sysml-toolkit):

```
$ uv run svt report
passed        6
failed        1
cantTell      2
inapplicable  1
untested      0
```

The one real `failed` is a genuine sysml-toolkit bug (anonymous `:>>`
redefinition of a multi-valued reference feature becomes falsely
"ambiguous" at 3+ occurrences — OpenSysML resolves it cleanly); the two
`cantTell`s are an unresolved cross-tool disagreement recorded honestly,
not adjudicated by guesswork; the one `inapplicable` is sysml-toolkit's
`verify` mechanism honestly reporting it can't perform a per-usage
constraint evaluation. Every one of those is a real adapter run against a
real pinned binary — nothing here is a fixture standing in for a result.

The third implementation, the OMG's own
[Pilot Implementation](https://github.com/Systems-Modeling/SysML-v2-Pilot-Implementation)
(Java), is registered in the ledger; its adapter (`adapters/pilot_implementation.py`,
`adapters/pilot_glue/Main.java`) drives its headless
`org.omg.sysml.interactive.SysMLInteractive` engine. Wiring it up needs a
one-time local Maven/Tycho build, `toolchain/get-pilot-jar.sh` — **which
needs JDK 21 specifically**. Confirmed on the machine this was built on: a
JDK 26 makes the Pilot's Xtend compilation fail with ~150,000 JRE-type-
resolution errors (Xtend/Xbase's classpath indexing doesn't handle that
JDK's layout) — a real, understood incompatibility, not a flaky build. See
the script's header before running it.

## Repo layout

```
vocabulary/   the T-box: four classes, all subclassing EARL/PROV-O
shapes/       SHACL shapes gating every write (named, never anonymous)
sources/      the two OMG spec PDFs' citation register (files gitignored)
ledger/       the data: implementations, test cases, fixtures, runs
adapters/     one module per implementation + the scripted comparators
toolchain/    pinned-binary/build scripts for implementations under test
src/          the svt CLI
tests/        unit, SHACL counterexamples, determinism, PROV consistency
```
