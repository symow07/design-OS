# Next-phase proposal — straight_tuck_end_carton/1.2 (D-derived closure)

**Status: proposal only — do NOT implement without approval.** Prepared at
the Phase 2A-9C closeout per the user's approved architectural decision.
Also covers the parallel reverse_tuck_end_carton/1.2 (same correction,
mirrored).

## Why

STE 1.1 qualification (slice 1) proved the DECISION-016 **W-derived tuck**
(`W × 1.227`) is a real geometry defect: measured from a square 28×28×120
reference where W = D, it cannot tell panel width from opening depth, so on
wide-short cartons the lip exceeds H/2 — including the historical 90×25×92
STE die the user physically rejected. Skynte 1.0 (slice 2) validated the
correct model in production use: **tuck = D + explicit lip** (DECISION-019),
defect-free. 1.2 ports that model to STE (and RTE).

## Scope (one bounded slice, review stop at the end)

1. **New version, no mutation of 1.1.** Register `straight_tuck_end_carton/
   1.2` (and `reverse_tuck_end_carton/1.2`) in the registry + engine style
   config. 1.1 stays byte-stable and reachable by explicit pin for
   historical reproduction. No automatic migration.
2. **D-derived closure:** `tuck_total = D + lip_mm` with an explicit `lip`
   template constant (Skynte uses 16 mm); shoulder geometry compatible with
   the existing cubic-shoulder primitive (validate the curve fits inside
   the lip, as Skynte does).
3. **Dust depth bounded by the opening**, not silently clamped:
   `min(D-derived, (W/2 − clearance))` becomes an explicit formula, not a
   post-hoc clamp — the clamp boundary from 1.1 disappears because the
   formula respects it by construction.
4. **Independently derived supported domain** for 1.2 (expected far wider
   than 1.1's narrow band — the lip-vs-height defect is gone), its own
   property sweep (new seed), boundary fixtures, folded simulation and
   qualification matrix.
5. **No silent dust-depth clamping; no width-ratio tuck anywhere in 1.2.**
6. **Full property qualification** via the existing framework (add a
   `contract` + `domain` + adapter; reuse the STE closure family with a
   D-derived variant, or a new closure model).
7. **1.1 marked superseded for NEW production selection only after 1.2
   passes** — never retroactively; historical jobs keep 1.1.

## Effort / risk

~1 review slice. Risk: medium — 1.2 changes emitted geometry (that is the
point), so it must be a new version with fresh golden fixtures; the main
work is deriving the wider domain honestly and confirming the shoulder/lip
interaction across it. RTE 1.2 rides along (~+0.25 slice) since it is the
mirror.

## Explicitly NOT in this proposal

- No change to 1.1 geometry, hashes, or domain.
- No auto-bottom work (`MEASURED_REFERENCE_REQUIRED`).
- No production authority — 1.2 would land as
  `TECHNICALLY_QUALIFIED_DOMAIN`, physical validation tracked separately.
- No task #47 / #50 changes.
