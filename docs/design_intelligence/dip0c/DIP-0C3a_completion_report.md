# DIP-0C3a — Completion Report

**Slice:** brand/logo technical + relationship audit. **Status:** complete, held for
review before DIP-0C3b.

**Scope guard:** C3a audits **technique and relationships only.** It infers **no**
ownership, **no** licence, **no** canonical status and **no** permission — those are
C3b/C3d. Every permission is false. `BBROSE_OWNED_CONFIRMED`, `LICENSE_APPROVED` and
`CANONICAL_BRAND_MASTER` are human-only and **unreachable from machine code**.

Reproduce: `python -m tools.dip0c.run_c3a` (read-only).
Frozen pilot: [`c3_pilot_manifest.json`](c3_pilot_manifest.json) (commit `c78da01`).
DIP-0C2 milestone: `c3756222b1771e6ea5b7a5c92c90267a6e6f8675`.

---

## The headline finding

> **There is no confirmed BBROSE logo master in this library.**

The only two files that **provably** say "BBROSE" — read directly from live text —
are `BBROSE.pdf` and `BBROSE-1.pdf`, and both are **design compositions that can
never be masters**. Meanwhile the two *plausible* master candidates say nothing at
all:

| File | Live text says | Can it be a master? |
|---|---|---|
| `BBROSE.pdf` | **"BBROSE"** (DIRECT) | **No** — 80 % raster design composition |
| `BBROSE-1.pdf` | **"BBROSE"** (DIRECT) | **No** — 81 % raster design composition |
| `logo.pdf` | *nothing* — the wordmark is **outlined** | nominated, brand unknown |
| `LOGO6.ai` | **"global logistics services"** | nominated, and **probably not a cosmetics logo at all** |

`LOGO6.ai` is the single most important thing a human must look at. It is
`TECHNICALLY_READY`, it sits in the BBROSE office folder, it is one of only two
brand-master candidates — and its own live text reads **"global logistics
services"**. The machine does not conclude anything from that; it hands the
extracted text to the reviewer and declines to name the brand.

## Pilot

21 files (7 of them the source files behind the 18 C2d Queue-I candidates).
Formats: 11 `.ai`/`.pdf`, 3 `.png`, 1 `.ase`, and the rest.

## Classification overrides (DIP-0A never rewritten)

| File | DIP-0A | C3 override | Reuse posture |
|---|---|---|---|
| `BBROSE.pdf` | `BRAND_MASTER` | **`DESIGN_COMPOSITION`** | `REFERENCE_ONLY` |
| `BBROSE-1.pdf` | `BRAND_MASTER` | **`DESIGN_COMPOSITION`** | `REFERENCE_ONLY` |

Evidence: ~80 % raster coverage · 18 / 29 embedded images · live text across 7 / 6
fonts · large composition-style files · **not isolated logo geometry**.
`override_confidence` 0.85, `human_confirmed_category` **blank**,
`cannot_be_canonical_master` **true**. The original `BRAND_MASTER` label survives as
the historical record, and **both the label and the contradictory evidence go to the
human-review queue**.

## Brand-name detection

**A brand name is asserted only when the live text contains a known brand token.**
Otherwise the extracted text is *evidence*, not a name — the largest span in a
composition is a headline, not a wordmark.

- **DIRECT (7):** `BBROSE.pdf` → BBROSE · `BBROSE-1.pdf` → BBROSE ·
  `JOJIA LOGO.ai` → JOJIA · the four `ATC PRESENTATION` decks → ATC.
- **REQUIRES_HUMAN (5 outlined wordmarks):** `logo.pdf`, `ATC LOGO.ai`,
  `LOGO ATC.ai`, `9993170.ai`, `9347862.ai` — 0 live-text spans, so the wordmark is
  outlined geometry. **No OCR** (deferred to DIP-0E), and the filename is never used
  to assert a name.
- **Text extracted but no known token:** `LOGO6.ai` ("global logistics services")
  and others — the text is recorded with page/font/size/bbox provenance and offered
  to the reviewer.

## Isolated logo candidates vs raster-heavy compositions

- **Isolated logo candidates (7):** `logo.pdf`, `LOGO6.ai`, `ATC LOGO.ai`,
  `JOJIA LOGO.ai`, `LOGO ATC.ai`, plus two Queue-I vector assets.
- **Raster-heavy design compositions (6):** the two BBROSE PDFs and the four ATC
  presentation decks.

## Third-party candidates — all inside the BBROSE office folder

**7 files:** `ATC LOGO.ai`, `LOGO ATC.ai` (which DIP-0A had mis-shelved as
`REUSABLE_VECTOR_ASSET`), `JOJIA LOGO.ai`, and 4 `ATC PRESENTATION*.pdf`. **Every
one of them sits in the BBROSE office folder** — which grants **no** ownership and
**no** usage right. `JOJIA LOGO.ai` proves its own contamination: the third-party
brand is read **directly from its live text**.

None is nominated. None has any permission. All are `approved_for_bbrose: false`,
`production_use_allowed: false`.

## Canonical-master nominations

**2 — `logo.pdf` and `LOGO6.ai`** — and both are *nominations only*.
`canonical_brand_master` is `null` on every record. Compositions and third-party
marks are structurally excluded from nomination, as is any file that is not a brand
asset at all.

## Relationship hypotheses

**83 edges** among the 15 brand assets: `UNKNOWN_BRAND_RELATIONSHIP` 55 ·
`POSSIBLE_PRODUCT_VARIANT` 15 · `SAME_BRAND_VARIANT` 7 · `POSSIBLE_LOCKUP_VARIANT` 6.

Every hypothesis carries **positive *and* contradictory evidence**, and
`human_confirmed` is blank. The 55 `UNKNOWN` edges are mostly "these two share a
folder", emitted at confidence **0.1** with the explicit contradiction *"a shared
folder NEVER proves a brand relationship — three of the five vector logos in this
folder are third-party."*

## Machine guards verified (all true)

`human_only_states_absent_from_output` · `all_permissions_false` ·
`no_composition_or_third_party_nominated` · `dip0a_classification_preserved` ·
`human_fields_blank` · `ownership_not_assessed_in_c3a` ·
`license_not_assessed_in_c3a`. `machine_ownership()`, `machine_license()` and
`machine_brand_master()` raise `HumanOnlyStateViolation` on the confirmed values.

## Three over-claims caught before shipping

1. **The "brand name" was a headline.** Taking the largest live-text span produced
   `BBROSE.pdf` → *"OIL"*, `ATC PRESENTATION` → *"A"*, `LOGO6.ai` → *"global
   logistics services"* — all asserted as brand names. A brand name is now asserted
   **only** on a known-token match; otherwise the text is evidence and the name is
   `REQUIRES_HUMAN`.
2. **184 relationship edges of noise.** `POSSIBLE_THIRD_PARTY_ASSET` was emitted per
   *pair* (119 times) when third-party-ness is a property of a **file**; and
   baby-patterns were being compared with logos. Third-party is now recorded once
   per record, and brand relationships are proposed only between brand assets.
   Edges: 184 → 83.
3. **A background and a sticker sheet were nominated as brand-master candidates.**
   Being clean isolated vector art is *necessary* but never *sufficient*; nomination
   is now restricted to files that are brand assets in the first place.

## Tests / lint / runtime / integrity

- `pytest tools/dip0c/tests/test_c3a.py` — **23 passed**.
- `ruff check tools/dip0c` — clean.
- Runtime 8.8 s; heavy output 178 KB in git-ignored `var/…/dip0c/c3a/`.
- **Materials snapshot unchanged**; output resolves outside the source tree.

## Findings requiring adjustment before C3b

1. **`LOGO6.ai` may not be a BBROSE asset at all** ("global logistics services").
   C3b must not assume a BBROSE-folder file is a BBROSE asset — the ownership model
   has to be able to say `OWNERSHIP_UNKNOWN` for a file the business *thinks* is its
   own logo.
2. **The brand assets have no licence evidence anywhere near them.** All ~85
   licence files sit in font/stock packages. C3b will return `NO_LICENSE_EVIDENCE`
   for the entire brand set — that is a finding, not a gap.
3. **The only provable BBROSE artefacts cannot be masters.** C3b/C3d must present
   this plainly: the business may believe it has a logo master here, and the evidence
   does not support it.
4. **`logo.pdf`'s brand is unknowable without OCR or a human.** It is outlined. If
   the reviewer cannot identify it by eye, DIP-0E (OCR) becomes the blocking
   dependency for the brand question.

**HOLD** for review before starting DIP-0C3b.
