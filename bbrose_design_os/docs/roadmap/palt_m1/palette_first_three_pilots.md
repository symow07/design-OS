# First Three Palette Pilots (PALT-M1 §6)

**Status: SPECIFICATION PROPOSAL — no modelling in this milestone.**
Every dimension below is tagged. Nothing is `OWNER_CONFIRMED` or
`MANUFACTURER_CONFIRMED` yet.

Tags: `ONLINE_REPORTED` · `CALCULATED` · `DESIGN_DEFAULT` ·
`OWNER_CONFIRMED` · `MANUFACTURER_CONFIRMED`

---

## PALT-P1 — Standard Eyeshadow Palette

Rectangular case · equal pans · simple grid · mirror · hinge · clasp.

| Field | Value | Tag |
|---|---|---|
| Outer silhouette | ROUNDED_RECTANGLE, corner R 4.0 mm | DESIGN_DEFAULT |
| Case outer | 116 × 92 × 15 mm | CALCULATED (from a 3×3 26 mm lattice + margins; bounded by the 83×83×12 and 150×90×15 references) |
| Pan family | 26 mm round, 3.5 mm deep | ONLINE_REPORTED (R2) |
| Pan count / layout | 9, GRID 3×3 | DESIGN_DEFAULT |
| Lattice pitch | 30.0 mm (26 + 4.0 gap) | CALCULATED |
| Outer margin | 5.0 mm | CALCULATED |
| Case wall | 2.0 mm ABS | DESIGN_DEFAULT (within the 1.5–3.0 ABS range, R14) |
| Mirror | LID_FULL, 1.0 mm | DESIGN_DEFAULT (thickness is a documented gap) |
| Hinge / clasp | PIN_HINGE / MECHANICAL_DETENT | DESIGN_DEFAULT |
| Open angle | 115° | DESIGN_DEFAULT (obtuse requirement is ONLINE_REPORTED, the number is not) |
| Pan retention | FIXED | DESIGN_DEFAULT |

*Purpose:* the reference implementation of the whole chain — lattice,
plates, hinge, mirror, artwork zones, both states.

---

## PALT-P2 — Mixed Face Palette

Eyeshadow + blush + contour + highlighter · mixed pan sizes and shapes.

| Field | Value | Tag |
|---|---|---|
| Outer silhouette | RECTANGLE, corner R 3.0 mm | DESIGN_DEFAULT |
| Case outer | 168 × 104 × 18 mm | CALCULATED (module maths below; 18 mm height matches the 15-pan mixed reference 104×61×18) |
| Module | 26 mm, gap 3.0 mm ⇒ pitch 29.0 mm | CALCULATED |
| Eye zone | 6 × (1×1) 26 mm round pans | DESIGN_DEFAULT |
| Blush / contour | 2 × (2×1) modules ⇒ 55 mm × 26 mm rounded-rectangular pans | CALCULATED from module equivalence (blush ≈ 3 eye modules, R15) |
| Highlighter | 1 × (2×2) module ⇒ 55 mm round pan | CALCULATED |
| Pan depths | eye 3.5 mm, face 5.0 mm | ONLINE_REPORTED (R2) |
| Height driver | deeper face pans set the 18 mm case | CALCULATED |
| Clasp | MAGNETIC | DESIGN_DEFAULT |
| Zones | EYE / BLUSH / CONTOUR / HIGHLIGHT tagged | DESIGN_DEFAULT |

*Purpose:* proves multi-module occupancy, mixed depths (the real driver of
case height), zoning, and mixed pan shapes on one lattice.

---

## PALT-P3 — Experimental BBROSE Palette

New original outer silhouette · irregular/modular internal layout · not
copied from any existing brand · presentable to customers · suitable for a
later manufacturing study.

| Field | Value | Tag |
|---|---|---|
| Outer silhouette | CUSTOM_SILHOUETTE — an asymmetric "petal-cut" rounded form derived from the BBROSE rose motif; ≥8 authored outline points | DESIGN_DEFAULT (originates from BBROSE brand geometry, not from any surveyed product) |
| Envelope | ~150 × 118 × 17 mm | CALCULATED |
| Layout | MODULAR, irregular occupancy on a 26 mm lattice with deliberate empty modules used as brand negative space | DESIGN_DEFAULT |
| Pans | mixed 15 / 26 / 36 mm | ONLINE_REPORTED families (R1) |
| Retention | MAGNETIC_REFILL throughout | DESIGN_DEFAULT |
| Refill promise | every slot matches a standard pan family so third-party refills fit | CALCULATED (enforced by `LAYOUT_REFILL_INCOMPATIBLE`) |
| Mirror | LID_PARTIAL following the silhouette | DESIGN_DEFAULT |
| Structure | SINGLE_LEVEL with an UNDER_TRAY_DRAWER for applicators | DESIGN_DEFAULT |

*Originality guard:* the silhouette derives from BBROSE brand geometry;
the layout is irregular by construction; the refill system uses only the
generic magnetic capability that is long-established prior art (R11), and
explicitly avoids every claimed mechanism in R10/R13 (spring tabs, living-
hinge compartment lids, angled rear stringers, claimed tray-lock/clasp
arrangements).

---

## What all three pilots share

Both CLOSED and OPEN state evidence; neutral clay validation views;
material validation views; the finish-differentiation board; artwork zones
(lid top, base back, interior, per-pan shade labels); and a full
provenance manifest. No pilot may be modelled until the architecture
decision is owner-approved.
