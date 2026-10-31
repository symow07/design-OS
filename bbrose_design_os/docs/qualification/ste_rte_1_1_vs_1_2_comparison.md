# STE/RTE 1.1 vs 1.2 — geometry comparison (2A-9D S10)

1.2 is NOT backward-compatible output: the D-derived tuck changes the
emitted geometry for every carton (content hashes differ everywhere).
It is a NEW version, selected only by explicit pin. The table is STE;
RTE mirrors it (same reach model, tuck columns swapped).

| case | W×D×H | tuck 1.1 | tuck 1.2 | domain 1.1 | domain 1.2 | same geometry? |
|---|---|---|---|---|---|---|
| shallow | 70×15×100 | 86 mm | 31 mm | TUCK_LIP_VS_HEIGHT | OK | NO |
| square | 28×28×120 | 34 mm | 44 mm | DUST_PAIR_CLEARANCE | DUST_PAIR_CLEARANCE | NO |
| medium | 60×20×130 | 74 mm | 36 mm | OK | OK | NO |
| deep | 60×45×150 | 74 mm | 61 mm | OK | OK | NO |
| wide_short | 90×25×92 | 110 mm | 41 mm | TUCK_LIP_VS_HEIGHT | OK | NO |

## Where 1.2 removes the 1.1 narrow-domain defect

- **shallow (70×15×100)** and **wide-short (90×25×92)**: 1.1 REJECTED
  (`TUCK_LIP_VS_HEIGHT` — the W-derived tuck lip exceeds H/2); 1.2
  SUPPORTED (fixed 16 mm lip). This is the exact 90×25×92 geometry class
  the user physically rejected on task #50's earlier STE die.
- **medium/deep**: both supported, but the tuck reach differs — 1.2 is
  the corrected die, not the same one.

## Where 1.2 does NOT widen

- **square (28×28×120)**: REJECTED by BOTH — the `W >= 1.262 D` dust
  clearance edge is unchanged from 1.1 (shared with the validated Skynte
  model). 1.2 widens only in the wide-short (lip) direction.

## Tuck reach model

- 1.1: `tuck = W × 1.227` (W-derived; the defect)
- 1.2: `tuck = D + 16` (D-derived reach + explicit fixed lip); shoulder
  span `0.5 × lip = 8 mm` (lip-derived, always fits). Shoulder INSET
  stays `W × 0.227` (flap-width geometry — the main-panel tuck is W
  wide), which is not a closure-depth dependency.
