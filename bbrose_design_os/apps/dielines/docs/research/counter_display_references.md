# Counter display references — what the house's own dies teach (2026-10-28)

**Sources.** Eight display and tray dies from `materials/house-designs/`:
- ES3083;
- the house references 008 (LP-2015), 020 (HL6005), 052 (ES5894), 053 (BL5883) and 056 (LM5912);
- BL-2050 STAND and FL-2029 STAND.

**Method.** Each die was measured from its vector paths with PyMuPDF. Labels printed on an artboard were read as labels; anything taken from a picture is marked *inferred*. The numbers are in `counter_display_references.json`, and the comparison is `counter_display.compare()`.

## What they share

- **Construction.** Every display die is one piece, a winged tray: floor, front lip, end wall, and two side walls whose trapezoid wings tuck, closed by lock stubs. None carries a glue flap; FL-2029's separate carton has a 52.5 mm one. None carries a dust flap.
- **Line colours.** Cut lines are near-black, creases red (green on ES5894), all solid. The die lines carry no spot names; Pantone appears only in the artwork.
- **Board compensation, one caliper at a fold.** The wall creases are inset from the floor's corner by 0.5 mm on white card (BL5883, LM5912) and by 1.5 mm on ES3083. No die states its board thickness. The only label is HL6005's "E坑 白瓦楞" (E-flute).
- **Lock slots.** Each side crease is broken by 30 or 35 mm gaps, the slots the end walls lock into.
- **Sizes.**
  - Front lips are 15–25 mm.
  - Stand-tray side walls are 19 mm.
  - End walls are 27.6 mm on trays with an insert, and 37.5–92 mm on the tall boxes.
- **Inserts.**
  - Square, round and oblong holes are used.
  - The pitch is the hole plus 8.5–9 mm.
  - Two plies, the second 3 mm larger (LP-2015, BL-2050).
- **Radii.** Tuck corners are about r 10 and slot ends r 9.

## What changed in the die (counter_tray_header 1.0)

- **Board presets.**
  - E-flute 1.5 mm, SBS 1.5 mm, and the references' 0.5 mm white card.
  - Each fold's compensation is recorded: one caliper, as the references' wall creases are inset.
- **The header.**
  - It is the back panel's own board, doubled over, with no crease, so no hinge.
  - The folded leaf is one caliper shorter so it closes flat, and it locks with a tab through a slot at the back panel's top.
  - The shopper-facing leaf is the printed "header front" (fixing 0.1's swapped label).
- **Glue flaps.** The corner glue flaps are tapered at both ends. Their glue zones are marked 2 mm clear of the crease and 1.5 mm inside the edges.
- **The insert.** The plate is at 30% of the product, at least 6 mm. Its tabs pass through slots in the side walls with 0.3 mm play, and its feet are glued. Each opening is the product plus clearance, with retention tongues reaching 0.6 mm into the product.
- **Trade rules.**
  - No cut within 3 mm of a crease end, unless the crease ends on it.
  - No panel narrower than three calipers, so the tiered collars' legs went from 2 to 3 calipers.
  - Grain is marked.
  - Bleed runs only past printed faces.
- **Files.**
  - A layered PDF at 1:1 mm: CUT, CREASE, PERF, GLUE, BLEED, ARTWORK, DIMENSIONS, with CutContour and Crease spots.
  - DXF R12, which reads back in ezdxf with 0 errors.
  - CF2.
  - A shelf nest on standard sheets, with its yield.
  - An A3 assembly drawing: flat, folded front and side, and exploded.
- **Qualification.**
  - Fold, strength (racking as a mechanism, and lock lean ≤ 3°), sightline, trade rules, and the comparison.
  - The matrix: bottle, jar, palette and stick; square, round and oblong openings; flat and tiered; the three boards.

## Where ours differs, and why

- **Glued corners, not tucking wings.** Our header is a tall sign on the back panel. Gluing the corners makes the base a closed box that cannot rack under it. The references carry nothing above their end walls.
- **Side walls rise to the back panel's top** to brace it.
- **The lock slots hold the insert, not the end walls.** This answers Day 12's racking finding, where 25.5° became at most 2.9°.
- **One ply with tongues, not two plies.**

## What still needs the folded sample

- The board's stiffness under the header.
- The glue's strength.
- The tongues' grip on a real bottle.
- A loaded stand's sway under a push.
- Whether the shop's CAD reads the CF2.

These are notes for the colleague who test-fits, not holds (§BH70(3)).
