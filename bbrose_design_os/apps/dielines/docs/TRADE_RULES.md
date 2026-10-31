# Tuck-end cartons: the trade's rules, and what version 1.4 draws

His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "TOP-TIER DIELINES ... Do
NOT rely on what the system already believes about dielines ... STRICT RESEARCH (one-time, thorough, time-boxed to a
few hours) ... Turn it into written rules ... List what you changed and why."

This file is those written rules. The research behind it, kept whole with its sources and their terms, is in
`research/` beside it: `STANDARDS.md` (the rules by topic, each graded by its evidence), `sources.md` (every source),
`REFERENCES.md` (the published professional dielines tried, their terms, and the two obtained and measured). The
geometry is `apps/dielines/geometry/trade_tuck.py`; the fold check is `apps/dielines/geometry/fold_check.py`.

## 0. What the trade settles, and what it leaves to the house

The ECMA Code — the trade's catalogue of carton styles — says of itself that it "was never developed with the intention
of becoming a mandatory construction manual" (ECMA p.4). What the trade does share is: which panel carries which flap
(the style's topology, coded); how a carton is measured; that cuts are solid and creases dashed; and the printers' file
and print rules (bleed, safe area, glue areas free of ink, the die on its own overprinting layer). Tongue, dust-flap,
glue-flap, slit and notch sizes are each converter's house standard. Version 1.4 takes those sizes from the evidence
below — the ECMA drawings' proportions, converters' sheets and the two licensed professional generators — and names
each one's source; where the sources disagree, the choice and its reason are written beside it.

## 1. The styles (S1, S2, S5)

Panels are numbered from the glue seam (ECMA p.17): glue flap | 1 back (A) | 2 left side (B) | 3 front (A) | 4 right
side (B, its free edge lapping over the glue flap).

| Style | ECMA code | Topology | Template, version 1.4 |
|---|---|---|---|
| Straight tuck end (STE, "airplane") | A20.20.01.01 (old A2320) | both tucks hang from the same panel — panel 1 | `straight_tuck_end_carton` |
| Reverse tuck end (RTE, "French reverse") | A20.20.03.01 (old A2120) | top tuck from panel 1, bottom tuck from panel 3 | `reverse_tuck_end_carton` |

Every carton a design draws is now the **reverse tuck end at 1.4** — the opposed layout the house's approved reference
die has (DECISION-003), drawn and named as the trade names it. Versions 1.0–1.3 of `straight_tuck_end_carton` drew this
same opposed layout under the straight tuck's name, and 1.0–1.3 of `reverse_tuck_end_carton` drew its mirror
(A20.20.01.03); both stay registered, untouched, so a historical job draws as it shipped. The true straight tuck end is
available at 1.4 for a design that asks for it.

## 2. How a carton is measured (D1–D5, T7)

- The width, depth and height confirmed at the size step are the carton's **inside** dimensions — what the product
  needs (the North American converters' convention, and Box Blanks' "inside" mode).
- Every crease sits at inside + t, t the board's caliper: panel crease widths A = W + t and B = D + t, the height between
  the dust flaps' hinges H + t. The crease sits on the board's mid-plane, so each wall takes t/2 inside and t/2 outside.
- Inside W × D × H, crease-to-crease (W+t) × (D+t) × (H+t), outside (W+2t) × (D+2t) × (H+2t): outside less inside is
  2t, never 4t (1.3 reported 4t — X9).
- Every panel takes the same t: opposite panels are equal, so the tube closes square.

## 3. The rules version 1.4 draws

| Id | Rule | 1.4 | Sources |
|---|---|---|---|
| K1, K3 | The lid hangs from the tuck panel's hinge crease and spans the opening: hinge to tuck fold = the side panel's crease width, so the fold lands on the far wall's top edge | lid depth = B | ECMA drawings p.24–25; Box Blanks (lid = side crease width) |
| T3 | The tuck panel's hinge crease sits one caliper further out than the dust flaps' hinges, so the lid closes flat over their ply | +t at each tucked end | pack.ly; DDR68 (`y_top_t = y_top + S`) |
| T4 | The lid and the dust flaps are inset t/2 from each upright crease — a t-wide relief between neighbours; the tongue is set back t each side | lid = A − t; tongue = A − 3t | Box Blanks (flaps panel − t, a t slot); Fortis (closure width reduction and tuck setback ≈ t) |
| K4 | The tongue, tuck fold to tip | 0.26 × lid depth, 8 to 20 mm | Box Blanks max(8, 0.26 lid); ECMA ≈ 0.25–0.30 B; Klearfold ≈ 0.25 B; the house reference ≈ 0.23 B |
| K5 | The tongue's corners strongly rounded | r = min(0.6 × tongue, ¼ tongue width) | ECMA drawings; svg.design (60 % default); the house reference |
| K6 | Lock slits cut along both ends of the tuck fold, the crease between them; the dust flaps' shoulders catch in them | slit = shoulder + 1 mm | ECMA tuck-fold ticks p.24/25/29; US 2004/0031843 A1; Klearfold "notch locks"; MOD-PAC |
| F1 | A dust flap on each side panel at each end, hinged on the body crease | 4 dust flaps | ECMA p.7 and drawings |
| F2 | A dust flap stops short of the opening's middle (two never meet) and short of the lid (the lid covers it) | depth = min(B − t, A/2 − 1) | Box Blanks min(W − t, L/2 − 1); ECMA ≈ 0.62–0.66 B within that cap |
| F3 | The dust flap is asymmetric: straight on the side of the panel carrying the lid; a 45° shoulder, then a taper, on the side of the panel the tongue enters | shoulder = 0.075 × B (1.25–3 mm); tip set in 0.21 of its width | ECMA p.24/25/29 (shoulder ≈ 0.07–0.08 B); Klearfold "minor flap shoulder"; Box Blanks (tip inset 0.21) |
| G1, G2 | The glue flap hangs from panel 1 across the body height and laps under panel 4's free edge, clear of panel 4's far crease | 8 mm to B − 3 mm; 12 mm by default | Klearfold 12.7; Box Blanks 12; DDR68 (B ≥ glue + 3) |
| G3 | The glue flap's ends tapered from its crease to its free edge | taper = G/3 over its width (≈ 18°) | ECMA ≈ 15°; Box Blanks 4 over 12 |
| G4 | The glue area is free of ink and coating; the artwork stops at the glue crease past its bleed | the GLUE layer marks it; the outside's ground stops at the crease | PaperWorks; Lewisburg; pack.ly; Sttark |
| N1 | A half-round thumb notch, centred in the top edge of the panel the top tongue tucks behind | r = 0.18 × A, 3.5–9 mm | svg.design; PakFactory; Boxshot (size not settled; Die Cut Studio R 3.96 at 22 mm) |
| L1, L3 | Cuts solid, creases dashed; a crease only where a flap hinges, never along a cut edge | per hinge; tuck folds creased between their slits | ECMA p.6; Lewisburg; DDR68 |
| B1 | Bleed 3 mm past every cut | 3 mm | PaperWorks 3.2; GLBC ⅛"; Sttark 3.175 |
| B2 | Type and art kept off creases and cuts | safe margin 4 mm (in the trade's 2–6.35 mm) | PaperWorks; GLBC; Sttark |
| E1, E2 | The die on its own layers, in named spot colours set to overprint; cut solid, crease dashed | CUT and CREASE layers, CutContour (magenta) and Crease (cyan) spots, overprinting, in every file | PaperWorks; The Print Remedy; Willowpack |
| R1 | The grain direction printed on the die | "grain parallel to the height", for the converter to confirm | ECMA p.6; Lewisburg; Iggesund p.38 |

## 4. What changed from 1.3, and why

| # | 1.3 drew | 1.4 draws | Why |
|---|---|---|---|
| 1 | the opposed tucks named "straight tuck end" | the same opposed tucks named reverse tuck end (A20.20.03.01); a true straight tuck end beside it | S1/S2: a straight tuck end hangs both tucks from one panel; a printer reading "STE" on an opposed die is misled (X1–X3) |
| 2 | sizes read as score-to-score; back +2t, sides +t, front +0 | sizes read as inside; every crease at inside + t | D1–D5, T7: no source has 1.3's scheme; its front and back differed by 2t, so the tube did not close square (X6, X7) |
| 3 | a tongue of 16 mm − t whatever the carton's size | 0.26 × lid depth, 8–20 mm (8 mm at 119's size) | K4: 16 mm was an assumption (DECISION-019), about 2× the trade's proportion at 119's size (X16) |
| 4 | the tongue's shoulders inset 0.227 × the panel's width | the tongue set back t each side, its corners rounded | T4, K5: 0.227 was measured on one square carton and describes the corner, not a share of the width (X15) |
| 5 | a stadium "friction slit" hole cut in each tongue | no hole in the tongue | K7: no standard, converter sheet or generator shows one; the trade's lock is the slit at the tuck fold (X11) |
| 6 | a 2t square notch at each corner of each lid's hinge | the lid inset t/2 each side; no notch | T4: the trade's relief is the t slot between flaps; no source draws a notch there (X25) |
| 7 | dust flaps 0.631 × D deep, symmetric, notched both sides | min(B − t, A/2 − 1) deep, shouldered only toward the panel the tongue enters | F2, F3: at 119's size 1.3's two dust flaps (13.9 mm each on a 22 mm opening) overlapped by 5.8 mm when closed; ECMA's flaps are asymmetric (X13, X14) |
| 8 | lock slits 2–4 mm, sized to the lid's width | the slit = the dust flap's shoulder + 1 mm | K6: the slit and the shoulder are one lock and are sized together (X12) |
| 9 | the lid hinged on the same line as the dust flaps | the lid hinged one caliper further out | T3 (X8) |
| 10 | a glue flap of 10 mm, 45° corners at its free edge only | 12 mm by default, its ends tapered ≈ 18° from the crease | G2, G3 (X17) |
| 11 | a thumb notch 0.22 × the panel's width | 0.18 × the panel's width, 3.5–9 mm | N1 (size not settled; Die Cut Studio's at 22 mm) |
| 12 | inner = size − 2t, outer = size + 2t | inner = the size, outer = size + 2t | D5 (X9) |
| 13 | SVG cut blue, crease red; the production PDF's die not overprinting; no grain mark | every file: cut magenta (CutContour), crease cyan dashed (Crease), overprinting; the grain direction on the die | E1, E2, R1 (X19–X21) |
| 14 | a die checked only for its outline's validity | the fold check on every die before he sees it | his item 2 |

## 5. The fold check

`apps/dielines/geometry/fold_check.py` folds the die as drawn — pure geometry, a rigid 90° turn about each crease, no
3D render, about 2 ms — and checks: one closed cut and no flaps overlapping on the sheet; every crease across board, never
along a cut edge; the tube square (opposite panels equal); the glue flap clear of panel 4's far crease and within its
height, its ends tapered; at each end, the lid reaching across the opening to the far wall (the tuck reaches its slot),
its hinge one caliper outside the dust flaps', its width the opening's, its tongue 8 mm to the lid's depth and set back
from the lid's edges; each dust flap fitting between the walls, shouldered toward the panel the tongue enters, its
shoulder caught by the lid's slit, the two never meeting across the opening and both under the lid; the thumb notch in
the right edge; the bleed 3 mm past every cut. It runs in `export_service.generate_exports` on every die; a failure is
recorded, said beside Approve and holds Gate 2 by name (`DIELINE_FOLD_CHECK_FAILED`) — never hidden.

## 6. What the trade does not settle (open)

- No numeric standard exists for the tongue, the dust flap, the glue flap, the slit or the thumb notch: 1.4's are the
  evidence's middle, each sourced above. A converter's house standard or a physical sample may move them.
- Grain direction for tuck-end cartons is contested; the die says "parallel to the height" for the converter to confirm.
- The crash-lock (auto) bottom (ECMA A60.20.00.03) is not drawn to lock: the fold check says so on any die of that style.
- The house's reference die `SLIMMING_CREAM_R-108-A.ai` (DECISION-016) was not found on this machine; it would settle
  the tongue and the slit against the house's own converter.

## 7. The professional reference for 119

Box Blanks (boxblanks.com) — its terms: "Dielines you generate here, on this site, are yours to use for any purpose,
including commercial work. You may modify them, share them". Its reverse and straight tuck ends at inside
22 × 22 × 105 mm, 0.45 mm board, are in `research/refs/` with their terms and hashes (`research/refs/TERMS.md`). Die Cut
Studio's are the second opinion. A converter's own production die could not be had without an account or a licence
(`research/REFERENCES.md` §1).
