# ES3083 — WHAT THE .AI ACTUALLY ESTABLISHES

Written 2026-08-13, against
`materials/historical AI production designs/ES3083吸塑 展盒刀线.ai`
(8,350,364 bytes, PDF 1.6, Adobe Illustrator 27.0, one artboard, one layer
`图层 1`, created 2025-05-18).

Addresses blocker `ES3083_DIMENSIONS_UNREADABLE`.

**You were right and my brief was wrong.** The earlier brief said no readable
dimension source existed and that the vendor email was the highest-value move.
The file was in the repository the whole time, in a catalogue of roughly ninety
sibling `.ai` files. `ES3083_VENDOR_REQUEST.md` is demoted from "first move" to
"the remaining gap", and the gap is now much narrower than that email assumes.

---

## THE ONE THING THAT MAKES EVERYTHING BELOW USABLE

The document is authored at true scale, one PDF point per point, and its
dimensions land on exact millimetres. This is not assumed — it is what the
numbers do:

- shade-name labels measure **77.00 × 16.00 mm**, twenty-four of them, at a
  pitch of exactly **83.00 mm × 22.00 mm**
- the label sheet outer boundary is **263.00 × 190.00 mm**
- the display box carries fold lines spanning exactly **275.00 mm**

Twenty-four independent artefacts landing on whole and half millimetres is not
what a rescaled or placed image does. Every measurement in this file is
therefore a real measurement, recovered by walking the PDF content stream with
the CTM tracked, not scaled off a raster.

Extent of that claim: 10,282 painting operations parsed across the single page
content stream; the numbers above are the exact bounding boxes of stroked and
filled paths after transformation, rounded to 2 dp.

---

## MEASURED — `VECTOR_MEASURED_FROM_SOURCE`

These come off the file directly. They are the strongest dimensional authority
the programme has ever held on ES3083.

| Item | Measurement | Note |
|---|---|---|
| Lid artwork, rounded square | **65.00 × 65.00 mm** | carries BBROSE / EYE SHADOW / SOMBRA DE OJOS — the exact `typography_zones` set |
| Back label, printed area | **49.50 × 49.50 mm** | rounded square, 2.0 pt keyline |
| Back label, die/bleed | **55.00 × 55.00 mm** | three instances, pitch 58.4 mm |
| Shade-name label | **77.00 × 16.00 mm** | 24 off, 3 columns × 8 rows |
| Shade-label pitch | **83.00 mm × 22.00 mm** | column × row |
| Shade-label sheet | **263.00 × 190.00 mm** | outer boundary |
| Display box, flat dieline | **637.72 × 668.48 mm** | full stroked extent |
| Display box, principal panel width | **275.00 mm** | three fold lines at exactly this span |
| Display box, largest panel | **275.00 × 197.00 mm** | |
| Display box, front panel stack | 43.00 / 35.00 / 50.00 / 35.00 / 33.50 mm | consecutive fold spacings, all 275.00 wide |
| PANTONE 621 C | Lab 87.8431, −7.0, 2.0 → sRGB 207, 224, 216 | separation, full strength |
| PANTONE 627 C | Lab 18.0392, −14.0, 0.0 → sRGB 17, 50, 44 | separation, full strength |

The two Pantone values are new in kind. The programme held the *names* as
`OWNER_STATED` HARD; it did not hold the Lab transforms. It does now.

---

## MEASURED FROM PRINTED COPY — `PRODUCT_LABEL_DECLARED`

The three back-label artworks on the sheet are legible at 200 dpi and carry
declared product data:

- **NET WT 11 g**
- ITEM NO **ES3083**
- EAN **5 061030 636510**
- executive standard **QB/T 1976-2004** (Chinese national standard for pressed
  eyeshadow)
- approval **ZHEZHUANG20210006**
- supplier: Yiwu Yibin Trading Company / Yiwu Yibin Trading Co., Ltd
- ingredients lead: Mica, Talc, Paraffinum Liquidum, Kaolin, Magnesium Stearate,
  Polyethylene, Silica, Ethylhexyl Palmitate, Simethicone, Phenoxyethanol

`11 g` is a declared value on a saleable pack, which is a real authority tier —
weaker than a drawing, considerably stronger than an estimate.

---

## NOT IN THE FILE — ABSENCE CLAIM WITH EXTENT

**No dimension callout of any kind appears anywhere on the sheet.** Extent:
`dimension_mark_candidates` is empty across the whole page in the existing
dip0b structural audit; `pdftotext -layout` returns one byte, because all type
is converted to outlines; and I read the full page render at 200 dpi in tiles.
No millimetre annotation, no leader line, no dimension arrow.

**The palette illustration is not to scale.** The open-case drawing at the
bottom left is a stylised perspective render — its pan cavities are drawn as
rounded shapes with one strongly curved edge and its lid dots decrease
monotonically in radius from 7.72 mm to 6.07 mm across the lid, which is
perspective, not geometry. Nothing may be measured off it. Extent: every path
in the region x 300–440 mm, y 175–380 mm, 15 largest by area.

**The blister tray photograph is a raster.** One embedded image on the page. It
shows a bagged clear PET tray with a handwritten "ES3083" label — the shipping
blister that holds palettes inside the display box, not the pan tray.

**So the pan cavity dimensions are still not measured.** The blocker narrows
but does not close.

---

## DERIVED — `DERIVED_BOUNDED_NOT_MEASURED`

This tier is new and it exists so that the numbers below can be used without
ever being mistaken for the tier above. They are arithmetic over measured
inputs, stated with the arithmetic shown so you can reject any step.

**The case is square and about 65 mm.** The lid artwork is an exact 65.00 mm
square carrying the full brand typography set. Lid decals are printed to the
lid face. Corroboration, independent: the display box principal panel is
275.00 mm, which divides into four slots of 68.75 mm — a 65 mm case with 3.75 mm
of clearance and board thickness. Two unrelated measurements agreeing on the
same footprint is worth more than either alone.

**Pan cavity, from the grid and the case.** Twelve pans, four columns by three
rows, is owner-confirmed HARD (`palette_es3083_intent.py`, reclassified during
the M4C-4 confirmation). Taking 65 mm outer, 2 mm wall each side and 1.5 mm ribs:

- column pitch ≈ (65 − 4) ÷ 4 ≈ **15.25 mm**, cavity ≈ **14 mm**
- row pitch ≈ (65 − 4) ÷ 3 ≈ **20.3 mm**, cavity ≈ **19 mm**

**Pan depth, from net weight.** 11 g ÷ 12 = 0.917 g per pan. Pressed eyeshadow
runs 1.2–1.5 g/cm³, so 0.61–0.76 cm³, i.e. 610–760 mm³. Over a 14 × 19 mm
cavity that is **2.3–2.9 mm** of fill depth, and a cavity a little deeper than
the fill. This lands squarely in the normal range for pressed eyeshadow, which
is corroboration, not proof.

Note the internal tension, unresolved: the shade-name label is 77.00 mm wide,
wider than a 65 mm case. Either it is not applied to the palette, or it is
applied to something else in the pack, or the case is wider than the lid decal.
I am not choosing between those readings. It is the one measured fact that does
not sit comfortably with the derivation, and it is recorded here rather than
dropped.

---

## THE WEB-SUBSTITUTION TIER YOU AUTHORISED

You said: *"if there is any measurements that you cannot find then try to find
a similar one online, because most of these palettes change on every drop so we
cannot put one standard measurement on all of them."*

Agreed, with one condition. Your own reasoning is the argument for the
condition: if the geometry changes on every drop, then a number taken from a
comparable palette is a statement about the *class*, not about ES3083. So it
enters as **`CLASS_TYPICAL_NOT_PRODUCT_SPECIFIC`**, with the source named, the
comparator named, and the date taken. It renders, it makes artwork, it never
merges silently with a measured value and it never reaches a factory as a
specification.

Full authority order now in force on ES3083 geometry, strongest first:

1. `VENDOR_DRAWING` — a dimensioned drawing from whoever catalogues ES3083. None held.
2. `OWNER_MEASURED` — calipers on a physical sample. None held.
3. `VECTOR_MEASURED_FROM_SOURCE` — the table above. **Held.**
4. `PRODUCT_LABEL_DECLARED` — the 11 g. **Held.**
5. `DERIVED_BOUNDED_NOT_MEASURED` — the ~65 mm case and pan estimates. **Held.**
6. `CLASS_TYPICAL_NOT_PRODUCT_SPECIFIC` — comparable palettes from the web.

---

## WHAT WOULD CLOSE THE BLOCKER OUTRIGHT

One caliper session on a physical ES3083, recording six numbers: closed height,
lid height, base height, cavity length, cavity width, cavity depth. Everything
else above already bounds it. That is a fifteen-minute job if a sample exists,
and it would move the whole geometry from tier 5 to tier 2.

Failing that, the vendor email in `ES3083_VENDOR_REQUEST.md` still stands, and
it is now a much shorter ask: you already hold the dieline, the Pantones, the
label sizes and the net weight, so the only thing worth asking for is the pan
cavity and pitch.

---

## REPRODUCING THIS

No tool in `tools/dip0b` exports geometry — `geometry_policy` there reads
*"analytical measurements only; no path set is exported in SVG, DXF, AI or any
production-reusable format"*, which is a deliberate constraint of that
subsystem, not a bug. The measurements above were taken by a separate one-off
content-stream walk: `qpdf --stream-data=uncompress`, then a tokeniser tracking
`q`/`Q`/`cm` with `re`/`m`/`l`/`c`/`v`/`y` accumulated and bounding boxes taken
after transformation. If these numbers are to become a repository record rather
than a brief, that walk needs to be written as a service and the record needs
to carry the code digest and the file digest under amendment 3aa.
