# PALT-M4C — INTERIM EXECUTION CHECKPOINT

**Status: `INTERIM_EXECUTION_CHECKPOINT_NOT_A_FINAL_REPORT`**
**Date: 2026-08-06 · Branch: `v2-features-phase12-14`**

This is not a completion report. Work stopped at a committed boundary, not
at a finished roadmap. Nothing here is owner-approved.

---

## 1. What the owner selected, and what it changed

`PALETTE_SELECTED_CONCEPT: ES3083吸塑_展盒刀线 — BBROSE OUTER GLOW EYESHADOW PALETTE`

ES3083 uses **rectangular** pans. PALT-P1 assumed nine **circular** ones.
Both pilots are preserved with distinct roles, and neither replaces the
other:

| | PALT-P1A | PALT-P1B |
|---|---|---|
| Role | `ENGINEERING_REGRESSION_FIXTURE` | `OWNER_DESIGN_INTENT_PILOT` |
| Pockets | 9 circular, 3×3 | 12 rectangular, 4×3 |
| Identity | `ec65ea9402c16230` (frozen, asserted unchanged) | `999db34286f2b789` |

## 2. Delivered this block

| Node | Commit | State |
|---|---|---|
| §8 rectangular metal pan family | `d494bb5` | COMPLETE |
| §8 recessed rectangular pockets | `6b1b8a2` | COMPLETE |
| §8 pan/pocket datum linkage | `a2124f0` | COMPLETE |
| M4C-7 Design Graph projection | `a0a2d0b` | COMPLETE |
| M4C-8 design fidelity (10 metrics) | `a0a2d0b`, `2a84af7` | COMPLETE |
| M4C-9 geometric two-variant proof | `a0a2d0b` | COMPLETE — PASS |
| §5B fail-closed evidence manifest | `40abf19` | **PARTIAL** |
| §9 FB3093/FB3090 comparison | `758a46c` | COMPLETE |
| §13 continuation state | `872d920`, `67830bc` | MAINTAINED |

## 3. Three defects found and fixed, not worked around

**The radial-vs-normal offset defect recurred a third time.** The
rectangular pan's wall offset moved points radially from the rectangle
centre, thinning the corners — the same defect A3R localized in the round
pocket and A3F fixed in the cup wall. Each loop point now carries the
inward normal of its **own** corner arc. A test asserts `min == max ==
inset`, so it is guarded by assertion rather than by care.

**The M4B-A datum defect recurred in a new module.** The tray took
`pocket_width_mm` as sharp-wall-at-deck while `pocket_envelope()` returns
the **functional** section at the seating datum. A drafted pocket narrows
downward, so feeding one into the other tightened the real fit. Now:
`solve_rect_sharp_wall_for_functional()` converts between the datums, the
tray's pocket defaults are **derived from the pan contract at import**, and
the bare names are refused with the datum they should have been. The
hand-copied 25.026189 was wrong; solved 24.953903. The built pocket
measures 24.8 × 18.8 at the seating datum — clearance exactly 0.400000 per
side.

**The fidelity score was partly self-referential.** It reached 1.0, which
reads as "the build fully realises the design"; it substantially measured
the internal coherence of my own defaults. Four of ten metrics cannot fail
for a default build. Each metric now declares its `discriminating_power`
and the report leads with **6/6 discriminating metrics pass; 2 by
construction, 1 with large headroom, 1 guaranteed** instead of the
aggregate.

## 4. What was deliberately NOT claimed

- Pantone 621 C / 627 C stay **named**. No licensed conversion exists here,
  so the Design Graph carries the name as authority and a visibly neutral
  placeholder. Inventing an RGB would create a colour nobody specified.
- **No pixel overlay.** The ES3083 sheet has no calibrated scale, so an
  overlay would report a number with no unit behind it.
- **No dimension is authoritative.** The sheet carries no readable
  millimetre value. Every PALT-P1B dimension is
  `PROVISIONAL_DESIGN_DEFAULT`.
- The **41 diagnostic image names** were never persisted to this
  repository. Inventing 41 plausible filenames would produce a manifest
  that looks complete and is not.
- The ES3083 **display box is linked, never merged** — merging would let a
  carton dimension present itself as a palette dimension.

## 5. What is NOT done, and why

| Outstanding | Why |
|---|---|
| §5B — the 41 renders (13 A3R + 16 A3F + 12 A3M) | Needs the pinned Blender 4.5.12 runtime. The **gate** is built and enforced; the **images** are not produced. |
| M5 pilot evidence package | Blocked on those renders |
| M4B-B hinge / clasp / mirror | Not started |
| M6 artwork + .AI export | Not started (Illustrator 2026 IS available) |
| M7 PALT-P2 / P3 | `PALT_P2_SELECTED_CONCEPT: PENDING_OWNER_SELECTION` |

## 5b. Verification

Canonical pytest (`-m "not pacdora"`), run alone against the shared
database, four times across this block:

| Through | Result |
|---|---|
| `a2124f0` | 5574 passed |
| `a0a2d0b` | 5601 passed |
| `40abf19` | 5609 passed |
| `2a84af7` | **5612 passed, 1 deselected, 38 subtests, 0 failed** |

Session baseline at start: 5513. Ruff clean across `apps/`.

Both new mesh families validate manifold, watertight, Euler characteristic
2, zero non-manifold edges, zero inconsistent half-edges, zero
self-intersecting pairs, `weld_count: 0`.

## 6. Authority states — unchanged

```
PALT_P1_FINAL_DIMENSIONS ......... NOT_APPROVED
PALT_P1_MANUFACTURING_AUTHORITY .. NOT_ESTABLISHED
PALT_P1_OWNER_APPROVAL ........... NOT_GRANTED
GATE_2 ........................... BLOCKED
PALT_M5 .......................... BLOCKED
PALT_P2_SELECTED_CONCEPT ......... PENDING_OWNER_SELECTION
ES3083_INTENT_CONFIRMATION ....... AI_DESIGN_INTENT_DRAFT_PENDING_OWNER_CONFIRMATION
PALT_VISUAL_EVIDENCE ............. 41_IMAGES_NOT_PRODUCED_GATE_ENFORCED
```

No provider call, no image-generation call, no OCR call. No original asset
moved, overwritten or relabelled. No Image Trace. No previous evidence,
decision or identity rewritten.

## 7. Owner decisions waiting

1. **Confirm the ES3083 intent** at `/dashboard/palette/intent-confirmation/`.
   The whole draft is `PENDING_OWNER_CONFIRMATION`; the 4×3 grid is SOFT at
   confidence 0.55 and is explicitly unresolved.
2. **PALT-P2 concept.** FB3093/FB3090 is a pressed-powder compact, not a
   second eyeshadow palette — see `m4c9_p2_candidate_comparison.json`.
3. **Whether to produce the 41 renders** before M5, or accept the gap as
   recorded.
