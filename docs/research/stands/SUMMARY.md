# Stands: what the research found

*Five minutes. Written 2026-10-31 for the owner's part 2. 165 sources, each dated and linked in [sources.md](sources.md); the numbers the engine reads are in [rules/](rules/).*

## The family

| Stand | What it's for | How it's built | The engine |
|---|---|---|---|
| **Counter tray with header** | The counter's everyday unit | A tray with rolled double walls; a sign slotted into the back wall | **Built** |
| **Stepped or tiered** | Show most of a tall product, or more rows | The same tray with its walls cut to the stair; rows rise much higher | **Built** |
| **Lid-converts-to-header** | Ships filled and closed; sets up in a minute | Walls tear along perforations; the lid swings up and is braced | **Built** (our own construction: no source shows one) |
| **Slanted or angled** | One or two rows whose fronts must read | Treads fall to the back, so each product leans back toward the eye | **Built** |
| **Tester unit** | Testers taken out and put back all day | The same bed, gentler, with wider openings and a row for caps | **Built** |
| **Flat tray with testers** | The house's most-used: every product at one height, a tester at the front of each column | One deck over the floor, liners inside the side walls, a slot-in sign | **Built** (part 3) |
| Floor stand (FSDU) | Launches, seasonal, gift sets | Double side walls; shelves slotted or hinged; 1.5 m and 23 kg are retailers' limits | Recorded |
| Rotating or carousel | Many faces in a small footprint | A shell on a bearing we can't die-cut | Recorded |
| Shelf-ready tray | Fast restock on the store's own shelf | A case with a tear line round its walls | Recorded |
| Clip strip, peg hook | Sachets and cards beside a shelf | A strip or a back with hooks | Recorded |
| Gondola end, power wing | Aisle ends and sides | Hooked on a fixture or free-standing | Recorded |
| Dump bin, pallet display | Impulse, volume | Rarely fit cosmetics | Recorded |

## What makes a stand strong

- **Roll walls over.** A wall folded double is far stiffer and gives a clean printed rim, with no raw edge. Patents US10159361 and US10144549 both do it.
- **Trap the corners instead of gluing them.** A side wall's flap held between a double wall's leaves cannot open.
- **Lock the inner leaf into the floor.** A tab through a floor slot stops the wall from springing.
- **Flutes run up the stand.** Vertical flutes carry the load. Folds across the flutes are predictable. Folds along them can wander, so they get a wider crease and a sample.
- **Tall signs fail at the hinge.** Every patent answers this: a clamp, a pocket, a lever, a brace. No source names a safe height.

## What makes one read premium

The one buyer's brief we found names what to remove: visible fluting, raw edges, plastic tape. Beyond that, the sources name faults, not recipes. Our reading: one continuous skin, a defined rim, a rigid feel, few visible parts.

## The rules that matter

- **Allowance:** FEFCO Rec. 101. Inside = crease centres − one thickness, so half a caliper per crease. Outside is its mirror. Our dies are drawn to it.
- **A 180° fold:** Cito's double crease, 3–8 mm centres, or a part-through cut. We use a half-cut on the header's top (one patent's range, excerpt only).
- **Press:** gripper 8–17 mm, rule height 23.8 mm, large presses take 0.75–9 mm board.
- **Strength estimate:** McKee, BCT = 5.87 × ECT × √(perimeter × caliper); 32 % lost at 80 % humidity. It's for closed boxes, so it's only an estimate on a stand, and we mark it ⟪PROVISIONAL⟫.

## What the web could not tell us

No code for a tray with a header. No numbers for tabs, slots, webs or hole clearance in corrugated. No corrugated tear patterns. No retailer's tip test. No assembly-time target, and no published proportion for a header. Almost nothing specific from leading cosmetics brands: the award sources are mostly POPAI D-A-CH, Shop! and converters.

So those rules are **ours**, graded X in [rules/_common.json](rules/_common.json), and they print as ⟪PROVISIONAL⟫. **A folded sample decides them.** The 1:1 cut-and-fold PDF is there for that.

## The house's dies

Measured in [house-references.md](house-references.md). They share one good idea (glueless winged trays, one caliper of inset) and one weakness: **every product at one height, with no sign above and no sightline ever measured.** That is what the new templates beat. They also use more board than a single-ply tray, and they're taller. That cost is stated on each template.

## Your bar, in one line

You asked that every product's front face be seen. A full 100 mm face in the rear of three rows would need each row to rise about a whole product, a stand over 300 mm tall. So the bar we hold is **the whole cap and 8 mm of the shade below it, across the product's full width, from both eyes**: 38 mm on round 4. The stepped display holds 55 % of the product's height. Change `face_bar_cap_plus_mm` and every stand re-solves.

## Your shade rule (part 3)

Every shade shows its colour: at least half of each product's colour window seen, or on the flat tray, its tester's. So the bar above moved from the cap and 8 mm to the cap and half its window: 66 mm of a 100 mm gloss, read to the millimetre. **The cost is height.** Round 4's gloss on 3 rows: the stepped trays went from 223 mm to 281 mm, the lid tray to about 310 mm, the slanted tray to 217 mm. The flat tray with testers holds 160 mm: its testers carry the shade, and its rear rows are seen by their tops only (about 5 mm).

