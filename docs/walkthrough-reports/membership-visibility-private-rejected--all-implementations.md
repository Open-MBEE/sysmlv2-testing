> **Snapshot, not live.** Committed as a worked example for
> `docs/walkthrough.md` -- report kind 2 (a cross-implementation comparison of one TestCase). The body below (including its own
> "never committed" line, which describes the ephemeral `reports/`
> directory in general, not this specific committed file) is copied
> verbatim from a real run. Regenerate the current version any time with:
>
> ```bash
> uv run svt view --testcase membership-visibility-private-rejected
> ```

---

# sysmlv2-testing report

Compiled by `svt view` from the ledger + fixtures. Ephemeral --
regenerate any time with the same command; never committed.

_Scope: testcase `membership-visibility-private-rejected` only._

## membership-visibility-private-rejected

**VALIDATION: confirmed by** Zargham (2026-09-13T02:00:39+00:00); Zargham (2026-09-16T00:28:32+00:00)

A part usage typed by a private part definition, referenced by qualified name from outside the definition's owning package, must be rejected -- the private member is not visible outside its owning namespace.

- **intent**: Must a model that references a private member from outside its owning namespace be rejected? (`private-membership-not-visible-outside-namespace`, concerns: admissibility)
  - this method establishes the intent's `admissibility` question directly.
- **method**: `structural-check`
- **expected**: `violated`

### Grounding

**7.2.5.2 Namespace Declaration**, p. 22 (KerML v1.1 Beta 2 (Release 2026-07) — no OMG document number assigned (beta))

> The visibility of the membership can be specified by placing one of the keywords public, protected or private before the public element declaration. If the membership is public (the default), then it is visible outside of the namespace. If it is private, then it is not visible.

*A private member's membership is not visible outside its owning namespace -- a qualified-name reference to it from outside that namespace should therefore fail name resolution. This grounds expected=violated for a part usage typed by a private part def referenced from a sibling package.*

### Input

**private-visibility.sysml**

```
package Lib {
    private part def Widget;
}

package Usage {
    part w : Lib::Widget;
}

```

### Runs

| Implementation | Version | Outcome | Actual |
|---|---|---|---|
| opensysml | `2b6c1cf6c31266396899a90d3290cfbdf44019b9` | passed | violated |
| pilot-implementation | `692170b71867353b8f90341e61556f49a5beb0e5` | passed | violated |
| sysml-toolkit | `29d57f43797a3bebc7f39ed4cc6cac6dfe9b3c73` | passed | violated |
| sysml-toolkit | `3a13c64adb93f1d069ce021c598318587126044a` | passed | violated |

#### opensysml @ `2b6c1cf6c31266396899a90d3290cfbdf44019b9` (v0.4.0) -- 2026-09-13T02:35:13+00:00

- **outcome**: `passed`
- **actual**: `violated`
- **info**: expected='violated' actual='violated'
- **command**: `Connection.load_from_content(<input files>, strict=False)`
- **exit code**: `1`
- **input digest**: `sha256:de9f631acd37024ea472b26f505839b98e889c27830b7dd738cb60aa56c5e4b2`
- **tool**: _not recorded — this run predates tool fingerprinting_
- **started at**: 2026-09-13T02:35:13+00:00

stdout:

```

```

stderr:

```
error <content>:6:14-6:25: unresolved reference: Lib::Widget
```

#### pilot-implementation @ `692170b71867353b8f90341e61556f49a5beb0e5` (2026-08+) -- 2026-09-13T02:01:05+00:00

- **outcome**: `passed`
- **actual**: `violated`
- **info**: expected='violated' actual='violated'
- **command**: `java -cp .cache/pilot/692170b71867353b8f90341e61556f49a5beb0e5/interactive-all.jar:.cache/pilot/692170b71867353b8f90341e61556f49a5beb0e5/classes svt.Main /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/membership-visibility-private-rejected/private-visibility.sysml`
- **exit code**: `1`
- **input digest**: `sha256:de9f631acd37024ea472b26f505839b98e889c27830b7dd738cb60aa56c5e4b2`
- **tool**: _not recorded — this run predates tool fingerprinting_
- **started at**: 2026-09-13T02:01:05+00:00

stdout:

```
ERRORS:
ERROR: Couldn't resolve reference to Type 'Lib::Widget'. (line 6)
ERROR: An occurrence, item or part must be typed by occurrence definitions. (line 6)

```

stderr:

```
log4j:WARN No appenders could be found for logger (org.eclipse.xtext.parser.antlr.AbstractInternalAntlrParser).
log4j:WARN Please initialize the log4j system properly.
log4j:WARN See http://logging.apache.org/log4j/1.2/faq.html#noconfig for more info.

```

#### sysml-toolkit @ `29d57f43797a3bebc7f39ed4cc6cac6dfe9b3c73` (v0.6.0 source, local build (main@29d57f4)) -- 2026-09-13T04:36:12+00:00

- **outcome**: `passed`
- **actual**: `violated`
- **info**: expected='violated' actual='violated'
- **reconfirmed** by the same party (2026-09-16T03:37:22+00:00) -- identical result, no new record
- **command**: `/Users/z/Documents/GitHub/sysml-toolkit/target/release/sysmlv2 check --lib /Users/z/Documents/GitHub/sysml-toolkit/spec-refs/SysML-v2-Release/sysml.library --strict /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/membership-visibility-private-rejected/private-visibility.sysml`
- **exit code**: `1`
- **input digest**: `sha256:de9f631acd37024ea472b26f505839b98e889c27830b7dd738cb60aa56c5e4b2`
- **tool**: _not recorded — this run predates tool fingerprinting_
- **started at**: 2026-09-13T04:36:12+00:00

stdout:

```

```

stderr:

```
warning: unresolved reference `Lib::Widget`
  --> /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/membership-visibility-private-rejected/private-visibility.sysml:6:14
   |
   |     part w : Lib::Widget;

1 warning(s)
--strict: warnings are failures

```

#### sysml-toolkit @ `3a13c64adb93f1d069ce021c598318587126044a` (v0.6.0) -- 2026-09-16T03:56:46+00:00

- **outcome**: `passed`
- **actual**: `violated`
- **info**: expected='violated' actual='violated'
- **command**: `/Users/z/Documents/GitHub/sysmlv2-testing/.cache/sysml-toolkit/v0.6.0/sysmlv2-0.6.0-aarch64-apple-darwin/sysmlv2 check --lib /Users/z/Documents/GitHub/sysml-toolkit/spec-refs/SysML-v2-Release/sysml.library --strict /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/membership-visibility-private-rejected/private-visibility.sysml`
- **exit code**: `1`
- **input digest**: `sha256:de9f631acd37024ea472b26f505839b98e889c27830b7dd738cb60aa56c5e4b2`
- **tool version**: `sysmlv2 0.6.0`
- **tool digest**: `sha256:32dcc65375614975fde29b86f12745015d2b691768a00f14f22987ad4ff768b4`
- **started at**: 2026-09-16T03:56:46+00:00

stdout:

```

```

stderr:

```
warning: unresolved reference `Lib::Widget`
  --> /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/membership-visibility-private-rejected/private-visibility.sysml:6:14
   |
   |     part w : Lib::Widget;

1 warning(s)
--strict: warnings are failures

```

