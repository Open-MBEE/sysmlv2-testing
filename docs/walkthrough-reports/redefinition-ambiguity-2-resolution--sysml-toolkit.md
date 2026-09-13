> **Snapshot, not live.** Committed as a worked example for
> `docs/walkthrough.md` -- report kind 1 (one TestCase against one Implementation) -- the failing case. The body below (including its own
> "never committed" line, which describes the ephemeral `reports/`
> directory in general, not this specific committed file) is copied
> verbatim from a real run. Regenerate the current version any time with:
>
> ```bash
> uv run svt view --testcase redefinition-ambiguity-2-resolution --implementation sysml-toolkit
> ```

---

# sysmlv2-testing report

Compiled by `svt view` from the ledger + fixtures. Ephemeral --
regenerate any time with the same command; never committed.

_Scope: testcase `redefinition-ambiguity-2-resolution`, implementation `sysml-toolkit` only._

## redefinition-ambiguity-2-resolution

**VALIDATION: confirmed by** Zargham (2026-09-13T02:49:00+00:00)

Each anonymous ':>> items' redefinition under part c must resolve, by real object identity, to the inherited base feature Container::items.

- **method**: `reference-resolution`
- **expected posterior state** (resolution facts):
  - `UsageTwo::c::@0` must resolve to `Lib::Container::items`
  - `UsageTwo::c::@1` must resolve to `Lib::Container::items`

### Grounding

**8.3.3.1.10 Type (removeRedefinedFeatures operation)**, p. 147 (KerML v1.1 Beta 2 (Release 2026-07) — no OMG document number assigned (beta))

> removeRedefinedFeatures(memberships : Membership [0..*]) : Membership [0..*] -- Return a subset of memberships, removing those Memberships whose memberElements are Features and for which either of the following two conditions holds: 1. The memberElement of the Membership is included in redefined Features of another Membership in memberships. 2. One of the redefined Features of the Membership is a directly redefinedFeature of an ownedFeature of this Type. [...] body: let reducedMemberships : Sequence(Membership) = memberships->reject(mem1 | memberships->excluding(mem1)-> exists(mem2 | allRedefinedFeaturesOf(mem2)-> includes(mem1.memberElement))) in let redefinedFeatures : Set(Feature) = ownedFeature.redefinition.redefinedFeature->asSet() in reducedMemberships->reject(mem | allRedefinedFeaturesOf(mem)-> exists(feature | redefinedFeatures->includes(feature)))

*This is a general set operation over the whole memberships collection (existential quantification, not a pairwise fold) -- it is defined the same way regardless of how many redefining memberships exist. Nothing in this algorithm conditions correctness on sibling count, so 2 vs 3+ anonymous redefinitions of the same base feature should resolve identically. This directly supports expected=clean for both redefinition-ambiguity-2 and redefinition-ambiguity-3plus, and independently corroborates BrandFootprintML's own root-cause hypothesis that sysml-toolkit's drop_redefined_hits (a suspected pairwise fold) diverges from this normative set-based algorithm. Version caveat: this is KerML v1.1 Beta 2 (Release 2026-07), not the v1.0 release the SysML v2.0 Language Specification (formal/2026-03-02, March 2026) cross-references as '[KerML, ...]' -- used as the best locally-held proxy; this is a foundational, long-stable KerML mechanism unlikely to have changed in a way that would flip this conclusion, but the version mismatch is real and noted rather than glossed over.*

### Input

**lib.sysml**

```
library package Lib {
  private import ScalarValues::*;

  part def Item { attribute name : String; }

  part def Container {
    ref part items : Item[*];
  }
}

```

**usage-two-ok.sysml**

```
package UsageTwo {
  private import Lib::*;

  part a : Item { :>> name = "a"; }
  part b : Item { :>> name = "b"; }

  part c : Container {
    ref :>> items = a;
    ref :>> items = b;
  }
}

```

### Runs

| Implementation | Version | Outcome | Actual |
|---|---|---|---|
| sysml-toolkit | `3a13c64adb93f1d069ce021c598318587126044a` | failed | UsageTwo::c::@0->UsageTwo::c::@2; UsageTwo::c::@1->UsageTwo::c::@1 |

#### sysml-toolkit @ `3a13c64adb93f1d069ce021c598318587126044a` (v0.6.0)

- **outcome**: `failed`
- **actual**: `UsageTwo::c::@0->UsageTwo::c::@2; UsageTwo::c::@1->UsageTwo::c::@1`
- **info**: 2 resolution check(s), all_match=False
- **issue** (sysml-toolkit v0.6.0 (3a13c64a): cross-wires anonymous :>> items redefinitions to each other instead of the base feature): https://github.com/Open-MBEE/sysml-toolkit/issues/2 -- linked by Zargham (2026-09-13T02:50:03+00:00)
- **command**: `/Users/z/Documents/GitHub/sysml-toolkit/target/release/sysmlv2 convert --lib /Users/z/Documents/GitHub/sysml-toolkit/spec-refs/SysML-v2-Release/sysml.library --to compact-json /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/redefinition-ambiguity-2-resolution/lib.sysml /Users/z/Documents/GitHub/sysmlv2-testing/ledger/fixtures/redefinition-ambiguity-2-resolution/usage-two-ok.sysml -o /var/folders/_z/k9fkf53x4q7dm02s4lr__qq00000gn/T/tmpgae1xsfd/model.json`
- **exit code**: `0`
- **input digest**: `sha256:dd8e5e69f050f6548c2e6e2e7cb21b17e84b79019c80fd3ffacb29d95c05e35a`
- **started at**: 2026-09-13T00:19:09+00:00

stdout:

```
UsageTwo::c::@0	UsageTwo::c::@2
UsageTwo::c::@1	UsageTwo::c::@1

```

stderr:

```

```

