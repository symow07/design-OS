# Engine map

Rewritten 2026-10-29, at the end of the owner's goal "Quality, not count"; updated the same day for "Execution: match the pick, build in layers" (the shape check, the faces in layers, the chain's own preflight) (CURRENT_DECISIONS.md, 2026-10-29); updated 2026-10-30: part 1B, the artwork made of separate pieces (the wrap of part 1 is held only for a build on it); updated 2026-10-31: part 2, the stand family (no new engine: the stand die and the die writer extended). The
57-row map of 2026-10-28 is `eed52e1`; the 30-engine map after the consolidation is `3e147ba`. Each engine below has a
quality file in [consolidation/quality/](consolidation/quality/): its job, its bar in numbers, a before/after on the
same real input (the best donor against the merged engine), its verdict and its weakest point.

**57 engines → 21 standing:** the 10 below, which make the chain, and 11 old engines that only the old layer still loads
still loads (further down).

## The ten engines of the chain

The chain: brief → research → three boards → board pick → three designs painted on the flat die → design pick → the
die (files build) → the whole die painted for the idea → each stand face at 300 ppi on its own outline, the bottle and
cap on their flat nets → the owner's Accept or Redraw per face → Make my files. Traced function by function, with the
test that proves each hand-off, in PIPELINE.md (annotation of 2026-10-29).

| Engine | Files | Its job | Verdict | Key number |
|---|---|---|---|---|
| **The dieline engine** | `apps/dielines/geometry/engine.py`, `trade_tuck.py`, `fold_check.py`, `ecma_ste.py`, `opposed_tuck.py`, `side_seam.py`; `apps/dielines/registry.py`, `qualification/` | a carton's flat die at 1:1, qualified; its three carton styles (the old row 3) are its own | SAME (nothing changed) | carton die read back 0.0 mm, cut and crease, both ways; opposed tuck 12/17 and Skynte 10/13 fixtures, 0 sweep failures |
| **The stand die** (the family, 2026-10-31; 1.0 kept for what was read from a picture) | `apps/dielines/geometry/counter_display.py`, `stand_templates.py`, `stand_fold.py`, `stand_types.py`; rules in `docs/research/stands/rules/` | every stand's die from the product records and the envelope: five working templates, each read back through one fold model; 15 stand types on record | **BETTER** | round 4: every product's top 38 mm and the whole header seen from both eyes (rows 2 and 3 were hidden), 16 locks, 0 glue, 22 joints within 0.5 mm |
| **The die writer** | `apps/dielines/exporters/counter_display_files.py`, `stand_sheets.py` | every die's files: 1:1 PDF, .ai, DXF, CF2, true-shape nest, the fold-up, the assembly sheet, the tiled 1:1 PDF; stand and carton | **BETTER** | four writers → one; a stand's nest from 24 % to 41 % of its sheet; every file read back by a real reader, its .ai by Illustrator |
| **The round designer** | `apps/pipeline/services/round_designer.py` | research, boards, designs on the flat die, the pick page; the house library (moved in, 2026-10-29) | **BETTER** | the library's top twelve: word hits 32 → 37, still 12 of 12 with words and a colour, reference pictures 1 → 3 |
| **The round's runner** | `apps/pipeline/services/round_flow.py` | each designer step as a worker job | SAME (moved verbatim) | three kinds of round → one |
| **The paid boundary** | `apps/pipeline/services/round_calls.py`, `spend_reservation.py` | every paid call: reserved before, settled at usage, never twice; one $2.00 cap over a whole round | **BETTER** | five spending paths → one; a round's calls under every prefix held to one cap; each step's cost on its page |
| **The owner gate** | `apps/pipeline/services/round_files_gate.py` | each face's jobs, Accept / Redraw, Make my files | **BETTER** | the flat pick → files (was refused); one system repair, then the owner's |
| **The face builder** | `apps/pipeline/services/round_files_faces.py` | each face's placement record: motifs made alone (vector builders, the one picture sheet, cut out), placed by rules, words in quiet zones; ground, fold, placement, press and seam checks; the composed views | **BETTER** | round 4: 139 motifs as separate objects from a $0.067 sheet, 0 cracks, every band meeting at 0.0 mm |
| **The writer** | `apps/pipeline/services/round_files_export.py` | the .ai by the file's law (GROUND, MOTIFS by panel, RELIEF, FOIL, WORDS, DIE with its sub-layers), each piece its own named object; Illustrator's save and reopen; `print_check` and `law_check` on each file before and after Illustrator; `illustrator_proof` | **BETTER** | a fused raster with no objects → every motif movable by name; the stand 39 MB → about 3 MB |
| **Product drawing** | `apps/pipeline/services/product_drawing.py` | our own folded and loaded drawings | SAME (nothing merged in) | same bytes on the same input |

No engine is WORSE. A SAME is an engine whose parts moved verbatim (checked part by part against the archived donors:
consolidation/quality/runs/moved-parts.json) and which was not meant to change what it makes.

**The weakest point left in the system:** placement is by rules, so a face reads more formal and less dense than a painted millefleur; house library pieces are ranked and judged but not yet placed, and its .eps files are unread; a cut-out's quality is seen, not measured.

## Held: old engines that only the old layer still loads

The chain imports none of these (since `c411581`: its worker tasks in [round_tasks.py](../bbrose_design_os/apps/pipeline/round_tasks.py),
the house library and web research's one error in the round designer, the font check in the writer). What still loads
each, from the roots Django and Celery load ([consolidation/retire_scan.py](consolidation/retire_scan.py), record
[retire-scan.json](consolidation/engines/runs/retire-scan.json)), is the old layer only: the old task API (under /api/), the
dielines API, the intelligence pages, the old ARIA tasks and signals, the old commands and the old dashboard pages.

| Row | Engine | What still loads it |
|---|---|---|
| 9 (part) | `artwork_layers`, `label_layout`, `export_service` (its dies now written by the die writer) | the IRE composer; the dielines API |
| 20 | Designer's eye (pitch) | the ARIA agent, the old container target, the old task API |
| 21 | Tavily session and fetch | the trend board; the old comparison anchors |
| 22 | Web research gateway | the trend board; visual review; the old task API |
| 23 | Trend board | the old ARIA tasks, autopilot and agents; the old task API |
| 24 | Library retrieval | the Library and Status pages; the trend board; the old references |
| 49 (part) | `font_pool` | the IRE's type book and font roles |
| 51 (part) | `line_art`, `flat_motif` | the old targets |
| 53 | IRE composer and emitters | the ARIA agent; about 30 IRE modules; 7 tools |
| 54 (part) | `native_handoff` | the old task API (`GenerateHandoffView`); the packaging target |
| 57 | Palette M-series | the palette pages in the dashboard; the old palette target; `tools/tier2_gate` |

The 76 live modules that import them, each with its verdict ([holders-verdicts-1029.json](consolidation/engines/runs/holders-verdicts-1029.json)):
51 are held only by the old roots and 25 are loaded by nothing; none is needed by the chain, so each goes to archive
with its engine. Not done yet: cutting the old roots leaves 228 of the 859 modules (the chain, its pages and the app's
models, migrations and admin); the other 631 — 296 held only by the old roots, 335 loaded by nothing — go to archive
with 251 test files (about 6,000 tests), taking the collected count from 9,890 to about 3,900, below the floor the owner
set. Home, the shell's pulse and find, and the Library and Status pages load the old layer today and are rebuilt on
the chain first.

## Archived (in `archive/`, by `git mv`; nothing deleted)

- The consolidation of 2026-10-28 (`8a57d46` … `7be1f95`): see `3e147ba`'s map and PLAN.md "As carried out".
- 2026-10-29: the two old round kinds (`a634230`); the history pages — Round 1 balm, the Round 1B/1C masters, the Day
  4–6 stand and serum masters — with their views, templates and tests (`32f27f3`); the 39 engines they freed, rows 17,
  18, 19, 38, 45, 48, 52, 55 whole and parts of 49 and 51 (`ba16e80`); the old pages Home, Designs and Library read
  (`8e84af3`); the carton writers production_pdf, svg_exporter, ai_exporter (`daa57b6`); the register entries of the
  archived files (`99b3707`); the chain's dead ends (`f76ffaf`).

## How it is checked

- `consolidation/dangling.py`: every import and `patch('apps…')` path resolves (baseline 82 nested patch strings).
- `consolidation/import_check.py`: every module imports (baseline 10 Blender scripts).
- The archive is never imported: `test_two_roots_collision_guard.ArchiveIsNeverImportedTests` (a fresh interpreter
  imports every module; a negative control).
- `consolidation/chain_run.py`: round 3 end to end at $0 on a copy; `--live` from its real current drawings.
- `consolidation/quality/moved_parts.py`: every moved part against its donor.
