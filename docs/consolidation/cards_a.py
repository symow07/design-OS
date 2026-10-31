"""Card texts, rows 1–20 (read from each engine's code; the run's numbers come from engines/runs/<nn>.json)."""
CARDS = {}

CARDS[1] = dict(slug='dieline-engine-core', step='Cartons (anything that folds: the die first)', verdict='GOOD', does="""
`calculate_dieline` (engine.py:437) takes a validated `DielineInputJSON` and dispatches it: the 1.4 trade tuck ends
first (`trade_tuck.is_trade`), then the versioned style table (unpinned: 1.1), then the side-seam, ECMA and opposed-tuck
archetypes; anything else raises `unknown carton style`. It returns a `DielineCoordinates` (panels, fold lines, the
cut, bleed and safe polygons, flaps, slits, a `derived` record). It writes no file. `_calculate_carton` (engine.py:561,
about 590 lines) is the one carton recipe: board-thickness compensation, a slit-web guard (`_apply_slit_web_guard`
:203) and lock notches. The pinned 1.0 wrappers (`calculate_straight_tuck_end` :493 and two more) are kept to
reproduce old jobs.""", run="""
Round 3's bottle (15 × 15 × 100 mm, the brief's sizes) drawn as a carton through `calculate_dieline`, unpinned and at
1.4, for three styles, each validated; the 1.4 straight tuck end written as an SVG; the engine's geometry and trade-tuck
tests run.""", keep="""
- `calculate_dieline` — one entry for every carton, versions pinned or current, never a silent fallback.
- `_calculate_carton` — the thickness-compensated recipe with its guards.
- `primitives.sample_path` / `path_to_svg_d` — real M/L/C/Z paths from the primitives.
- `DielineCoordinates.validate` — bleed ⊃ cut ⊃ safe, polygons valid.""")

CARDS[2] = dict(slug='template-registry', step='Die solving and cartons (which template and version)', verdict='PARTLY', does="""
`_register` (registry.py:253) is the only way a template is published; `resolve(id, version=None)` (:800) returns the
current version when unpinned and raises on an unknown id or a missing pinned version (no fallback). The 1.1–1.4 carton
versions are derived by `_corrected`, `_d_derived_version`, `_print_ready_version` and `_trade_version` (:373–:471).
`production_templates` (:842) lists current versions only. The stand die is registered twice under one id:
counter_tray_header 0.1 is current and provisional (:713); 1.0 is production-ready but `current=False` (:762), so an
unpinned caller gets 0.1.""", run="""
Every published template listed with the version an unpinned caller gets and its production flag; 1.0 resolved by
pin; the registry's two test files run.""", keep="""
- `resolve` — exact pinning, fails closed.
- `_trade_version` / `_print_ready_version` — versions derived from one base, not copied.
- `production_templates`, `is_production_eligible`.""", partly="""
Good: resolution and derivation. Wrong today: the stand die's current version is the provisional 0.1, so an unpinned
`resolve('counter_tray_header')` gives the wrong die; 1.0 must be current once 0.1's solver is gone.""")

CARDS[3] = dict(slug='carton-templates', step='Cartons', verdict='PARTLY', does="""
Four archetype modules, each reached only through `calculate_dieline`, each returning `DielineCoordinates`:
`calculate_trade_tuck` (trade_tuck.py:89, straight and reverse tuck end 1.4: inside sizes W+t, D+t, H+t, clamped tongue,
shoulder, dust flap and glue flap, panel order glue, back, side, front, side); `calculate_ecma_ste` (ecma_ste.py:175,
ECMA A20.20.01.01, 0.1, with `collision_report` :491); `calculate_opposed_tuck` (opposed_tuck.py:201, a reference
reconstruction, 0.1, checked against its attachment map :169); `calculate_side_seam_tuck` (side_seam.py:173, Skynte 1.0).""",
    run="""
Round 3's bottle drawn on every archetype, each folded by `fold_check.check`; then the other products of the goal (a
lipstick carton 25 × 25 × 85, a lip balm carton 22 × 22 × 78, the palette box 195 × 125 × 22 mm) on the three
non-trade archetypes and on reverse tuck 1.4; the archetypes' own tests run.""", keep="""
- `calculate_trade_tuck` — the qualified 1.4 trade tuck ends: they draw every product of the goal and fold clean.""",
    partly="""
Good: the trade tuck ends (1.4). The ECMA STE 0.1, opposed tuck 0.1 and Skynte side-seam 1.0 archetypes refuse the
goal's products (see the run); they serve no product the chain makes.""")

CARDS[4] = dict(slug='dieline-qualification', step='Cartons (qualified before production)', verdict='PARTLY', does="""
`runner.qualify(user, adapter)` (runner.py:162) evaluates the dimension domain, draws the die through
`calculate_dieline`, runs `invariants.check_invariants` and the adapter's collision report, and returns a
`QualificationResult` (supported, violations, geometry hash). `qualification_matrix` (:223) runs the committed fixtures
(with `render_dir`, an SVG and a folded diagnostic per case); `seeded_property_sweep` (:272) is a seeded random sweep.
`fold_check.check(coords)` (geometry/fold_check.py:39) is a pure fold test of one carton. `closure.py` holds
declarations only. `adapter_for` (:139) has six adapters: none for the 1.3/1.4 trade tuck, ECMA or the stand.""", run="""
Round 3's bottle qualified on every registered adapter; the framework's and the opposed tuck's qualification tests run.""",
    keep="""
- `fold_check.check` — a pure, fast fold test the trade tuck tests already use.
- `qualify` + `check_invariants` — the domain → die → invariants → collisions sequence.""", partly="""
Good: `fold_check.check` and the qualify sequence. Missing: no adapter for the 1.4 trade tuck the goal's cartons use,
so the qualification never sees the cartons that would print.""")

CARDS[5] = dict(slug='counter-tray-header-0-1', step='Die solving (the stand)', verdict='PARTLY', does="""
4,241 lines with two solvers under one template id. The family display (Day 12): `solve` (:481) from house values and
products, `_tray`/`_insert`/`_platform` parts, `fold_check` (:2005, ~600 lines of folding, sway, frame and gusset
checks), `scene`/`_sight`/`sightlines` (:2702–:3090, a ray-cast sightline model) and the reference-die measurer
(`measure_reference_die` :3618, `reference_mapping` :3977). The product-grid branch: `solve_product_tray` (:3091),
`_product_row_parts`, `build_product_tray_die`, `product_tray_fold_check`, `product_tray_platform_fronts`,
`product_tray_enclosure_elevations`, `product_tray_raise_rear`, `product_tray_sightlines` (:3187–:3617). Its
`build_die` and `fold_check` hand a 1.0 record on to counter_display (:1279, :2011). The 1.0 solver imports this module
for `solve_product_tray`, `Part`, `Die`, `_rect`, `_seg`, `_r`, `_product_row_parts` and the sheet constants, and the
stand adapter calls its sightlines, platform fronts, enclosure elevations and rear raise.""", run="""
The family display solved from its own defaults, its die built and fold-checked; the product-grid branch solved for
round 3's 4 × 3 grid and fold-checked; this module's test file run (it also holds the stand adapter's tests).""", keep="""
- `solve_product_tray`, `_product_row_parts`, `Part`, `Die`, `_rect`, `_seg`, `_r` and the sheet constants — what 1.0 is
  built on.
- `product_tray_sightlines`, `_product_plate_hit`, `_product_first_hit` — the seats' sightline check 1.0 reports.
- `product_tray_platform_fronts`, `product_tray_enclosure_elevations`, `product_tray_raise_rear` — the elevations the
  stand adapter and the drawings use.""", partly="""
Good: the product-grid functions above, which 1.0 already depends on. Not needed: the Day 12 family display (solve,
_tray, _insert, sway and frame checks, scene, reference-die mapping); no chain step builds it.""")

CARDS[6] = dict(slug='counter-tray-header-1-0', step='Die solving (the stand), the die first', verdict='GOOD', does="""
`solve(product=, board=, product_grid=)` (counter_display.py:68) takes the brief's grid, starts from 0.1's
`solve_product_tray`, compensates for the board (`BOARDS`), locks the header from the back panel, sizes the holder,
insert tabs and retention tongues (`_tongues` :145) and returns the 1.0 record. `build_die` (:197) draws the tray,
holder rows and seats as parts with faces, creases, glue zones and slots and lays them on a sheet. `trade_rules`,
`fold_check`, `strength_check`, `sightline_check` (0.1's code) and `compare` (against the house's measured display
dies) are run together by `qualify` (:553).""", run="""
Round 3's stand solved again exactly as the files build solves it (the brief plus the picked picture's saved reading)
and compared leaf by leaf with the committed record; solved from the brief alone; qualified; its tests run.""", keep="""
- `solve` / `build_die` — the production die the flow uses.
- `trade_rules`, `fold_check`, `strength_check`, `compare`, `qualify` — every check in one call.
- `cut_polygons`, `bleed_area`, `layer_geometry` — the die's layers for the writer.""", finding="""
Round 3's own die fails its sightline check (0.1's `product_tray_sightlines`), while fold, strength, trade rules and
the comparison pass. Recorded as found; the stand-die merge keeps the same result and does not change it.""")

CARDS[7] = dict(slug='stand-die-sheets-0-1', step='Die writing', verdict='PARTLY', does="""
Writes a counter_tray_header die (0.1 or 1.0's parts) as an SVG with Inkscape layers (`write_svg` :131), a layered die
PDF (`write_die_pdf` :284, layers ARTWORK, CUT, CREASE, SAFE, BLEED, WORDS), A3 tiles (`write_tiles_pdf` :342), a plan
and elevation sheet (`write_plan_elevation` :568) and a PNG of a PDF (`render_png` :767). `apply_layers` (:301) turns
marked content into optional-content groups with fitz; the 1.0 writer imports it.""", run="""
Round 3's 1.0 die written as an SVG and a layered die PDF; the PDF read back for its layers.""", keep="""
- `apply_layers` — the layer (OCG) writer the 1.0 die files use.
- `safe_areas` — each face's safe area for the sheets.""", partly="""
Good: `apply_layers`, which 1.0 already calls. The rest writes the same die the 1.0 writer writes (die PDF, sheets),
in a second format nobody downloads; Make my files does not call it.""")

CARDS[8] = dict(slug='stand-die-files-1-0', step='Die writing; painting on the die', verdict='GOOD', does="""
`write_all(record, folder, artwork)` (counter_display_files.py:295) writes the die as a layered 1:1 PDF (`write_pdf` :57,
layers ARTWORK, CUT, CREASE, PERF, GLUE, BLEED, DIMENSIONS, spot cut and crease), DXF (`write_dxf` :102), CF2
(`write_cf2` :127), a nested sheet (`nest` :148) and an A3 assembly drawing (`assembly_drawing` :199). The flat half:
`flat_frame` (:321) fixes one mm→px transform, `flat_masks` (:355) and `flat_template` (:442) draw the painting's
template and the owner's sheet, `apply_die` (:528) re-applies the die to a painting, `die_proof` (:551) measures it,
`pdf_readback` (:587) reads the written PDF's cut, crease and artwork box back, `fold_pairs` (:626) samples each fold.""",
    run="""
Round 3's committed die written (every file), the 1:1 PDF read back; its flat template made again and compared byte for
byte with the round's own; a $0 stand-in painting (each printed face's pixels coloured and textured, moved 3 px down and
2 px right) settled by the die and proved.""", keep="""
- `write_pdf`, `write_dxf`, `write_cf2`, `nest`, `assembly_drawing`, `write_all` — the die-maker's files.
- `flat_frame`, `flat_masks`, `flat_template`, `apply_die`, `die_proof`, `pdf_readback`, `fold_pairs` — the die-first
  method, measured.""", finding="""
The stand-in was moved 3 px down and 2 px right; the proof's best shift is [2, 3] (x, y): the drift found exactly.
After the die was applied again, 0 of the 1,285,946 pixels off the printed faces differ from the template; the 1:1 PDF
reads back within 0.0003 mm (cut), 0.0002 mm (crease) and 0.0002 mm (the artwork's box).""")

CARDS[9] = dict(slug='carton-exporters', step='Cartons (writing a carton die and its artwork)', verdict='PARTLY', does="""
`export_svg` (svg_exporter.py:99) writes a carton's print SVG; `export_production_pdf` (production_pdf.py:191) the CMYK
production PDF with CutContour and Crease spots, registration marks, dimensions and a title block;
`export_ai_from_production_pdf` (ai_exporter.py:43) copies that PDF to .ai; `pdf_layers` (`begin` :22, `end` :27,
`apply` :40, `layers_of` :66) is the optional-content writer both stand die writers use; `label_layout.plan_label`
(:483) fits a label's copy down to a 3 pt floor; `export_service.generate_exports` (:82) runs geometry and every
exporter for a DielineJob row (the dielines app's API). `production_pdf.py:86` names a Linux font folder that does not
exist here; the bundled Noto fonts are found first.""", run="""
Round 3's bottle carton (straight tuck 1.4) written as SVG, CMYK production PDF and .ai; the PDF's layers read back;
the SVG and production PDF tests run.""", keep="""
- `pdf_layers.begin/end/apply/layers_of` — the PDF layer writer (used by the 1.0 die files).
- `export_production_pdf` — spot cut and crease, registration and title block for a carton.
- `label_layout.plan_label` — copy fitted to a panel with a floor.""", partly="""
Good: the layer writer and the production PDF. Old: `generate_exports` and the job API serve the dielines app's jobs,
which the chain never starts; the round's .ai is written by round_files_export.""")

CARDS[10] = dict(slug='die-previews-and-mockups', step='None (the chain draws its own folded drawing)', verdict='UNUSED BY THE GOAL', does="""
`export_folded_mockup` (mockup_3d.py:26) writes an isometric folded PNG of a carton from a flat picture;
`export_design_preview_svg` (design_preview.py:83) embeds artwork clipped to panels, `export_design_components_ai`
(:239) and `export_design_preview_ai` (:427) write .ai files; `export_folded_diagnostic` (folded_diagnostic.py:75)
draws a four-stage fold (it needs the qualification's collision and closure records). `generate_provisional_preview`
(services/provisional_preview.py:72) writes a nine-item provisional package for a DielineJob.""", run="""
Round 3's bottle carton previewed: the folded diagnostic, the folded mockup of a flat design picture, the design
preview SVG; the design-preview tests run.""", keep="""
- `export_folded_diagnostic` — a fold shown in stages (only with the qualification's records).""")

CARDS[11] = dict(slug='round-designer', step='Research, boards, board pick, the die first, designs, the pick', verdict='GOOD', does="""
The ideas half as one module. `research` (:304): six Tavily searches from fixed topic words (`search_queries` :114,
never the brand), the library's twelve matches (`library_matches` :243, house-tier previews by the brief's words and
each shade's colour, the image guard's denylist), one Claude call that keeps every source with a takeaway. `boards`
(:490): one plan call, three board pictures (bold, refined, unexpected) with at most three library references.
`board_pick` (:530), `die_first` (:549: the stand solved from the brief by round_files_stand and its flat template by
counter_display_files), `designs` (:650: each design one edit of the template with the board as style), `flat_drawings`
(:626: folded and loaded drawings), the quick check (`check_prompt` :702), `pick_page` (:753) and `finalize_pick` (:789).
It takes COPY_START/COPY_END, `_line`, `_validation` and `read` from round_ideas.""", run="""
Round 3's brief at $0: the six queries; the library's matches compared with the round's own library.json; the die
solved from the brief alone and its template sheet drawn; the boards prompt built; the designer tests of the round flow
file run.""", keep="""
- `search_queries`, `tavily_searches`, `library_matches`, `research` — research as a designer does it, every source kept.
- `boards_prompt`, `board_image_prompt`, `boards`, `board_pick` — the three boards.
- `die_first`, `designs_prompt`, `design_image_prompt`, `designs`, `flat_drawings`, `check_prompt`, `pick_page`.""")

CARDS[12] = dict(slug='round-state-machine', step='Runs every step of the ideas half as a worker job', verdict='GOOD', does="""
`create_round` (:199) writes the brief and the first step; `run_step_job` (:466) runs one step under the round's lock
(dispatching to round_designer, round_ideas or round_steps by the brief's flow), records failures, commits the
round's records (`commit_artifacts` :118) and queues the next step; `submit_pick` (:629), `submit_board_pick` (:659),
`none_of_these` (:694), `retry_round` (:735), `summary` (:773). It imports Round 1/2's sheet, product brief, report and
steps for the older flows.""", run="""
Round 3's brief: is it a designer round, and its steps; the round flow file's tests run.""", keep="""
- `run_step_job`, `create_round`, `submit_board_pick`, `submit_pick`, `none_of_these`, `retry_round` — the runner.
- `write_json`, `append_json`, `round_root`, `commit_artifacts` — the records every step writes.""")

CARDS[13] = dict(slug='twenty-design-flow', step='None (replaced by the designer flow); five helpers', verdict='PARTLY', does="""
`seeds` (:108, one paid text call for twenty ids), `designs` (:182, twenty pictures), `pairwise` (:232, a two-juror
jury over 190 pairs), `pick_page` (:278), `finalize_pick` (:299). Still used: `COPY_START`/`COPY_END` (:26–27, the
delimiters that keep printed copy apart from instructions), `_line` (:43), `_validation` (:34, rejects a paid reply
that does not validate), `read` (:30) and `record_break` (:328, appends a failure to BREAKS.md once, under a lock).""",
    run="""
Its pair plan for twenty ids; the ideas tests of the media round file run.""", keep="""
- `COPY_START`/`COPY_END`, `_line`, `_validation`, `read` — used by round_designer.
- `record_break` — used by round_flow and round_files_flow.""", partly="""
Good: the five helpers. The twenty-design flow itself is never started (New design is the designer flow).""")

CARDS[14] = dict(slug='brief-contract', step='Brief in', verdict='GOOD', does="""
`normalize_ideas_brief` (:57) whitelists a brief's printed copy (brand, product, shade names) and keeps geometry and
creative direction out of the copy; `printed_copy` (:123) is the only source lettering may come from;
`is_designer_brief` (:15) marks the designer flow; `gloss_brief` (:131) is the lip gloss default.""", run="""
Round 3's brief normalised and its printed copy read; the brief tests of the round flow file run.""", keep="""
- `normalize_ideas_brief`, `printed_copy`, `is_designer_brief`.""")

CARDS[15] = dict(slug='ideas-image-calls', step='Boards and designs (their paid image calls)', verdict='GOOD', does="""
`IdeasContext(RoundContext)` (:52) is the paid context the boards and designs are bought through: `design_image_call`
(:68) generates, or edits with references or a flat template, saves the raw bytes, request, response and billing,
returns the saved record on replay and refuses changed bytes; `image_attempt_cap` 40. `design_image_estimate` (:21)
and `reference_image_estimate` (:44) are the reservations.""", run="""
The reservation one design picture holds, the attempt cap; the ideas and flat tests of the paid-boundary file run.""",
    keep="""
- `IdeasContext.design_image_call` — the flat-template edit and the boards' generate, saved, never bought twice.
- `design_image_estimate`, `reference_image_estimate`.""")

CARDS[16] = dict(slug='paid-boundary', step='Paid calls (one spend cap per round)', verdict='GOOD', does="""
`RoundContext` (round_calls.py:167) is every round's paid boundary: `text_call` (:348, up to 2–3 attempts, adaptive
thinking settings, one reservation per delivery), `image_call` (:467, the masked edit with the approved logo pinned),
`streamed_edit` (:39, partial images so a tunnel cannot cut a silent connection), `retained_verdict` (:148, a reply an
older parser could not read), `scoped_spend` (:114, the round's cap). spend_reservation.py is the ledger: `reserve`,
`settle`, `paid_operation`, `close_unknown`, `totals`. It parses replies with round_balm_calls.parse_response_text and
downloads with pipeline.agents.image_producer.download_image_bytes.""", run="""
Every saved text reply of round 3 parsed again by the boundary's parser; the ledger's totals read (no call made); the
paid-boundary tests run.""", keep="""
- `RoundContext.text_call`, `image_call`, `streamed_edit`, `retained_verdict`, `scoped_spend`.
- `spend_reservation.reserve/settle/paid_operation/close_unknown/totals` — the ledger.""")

CARDS[17] = dict(slug='whole-object-round', step='None (Round 1/2)', verdict='UNUSED BY THE GOAL', does="""
`round_steps.run_step` (:743) runs Round 2's steps: twenty seeds, twenty sketches as edits, eligibility checks,
readings, a coarse jury, pairwise batches, forks, the final order, the pick page. `round_sheet.build` (:140) lays a
product's panels on one sheet; `needs_repair` (:30). `round_product.normalize_brief` (:121) and
`repair_missing_body_right` (:203, lip gloss wand only). `round_report.finalize` (:207) and `tag_if_requested` (:283,
hard-wired to the slug r2-gloss and the tag round-2-gloss-a).""", run="""
Round 2's lip gloss brief normalised and its panel sheet drawn at $0; the media round file's non-ideas tests run.""",
    keep="""
- nothing the chain needs: the designer flow replaced the panel sheet and its jury.""")

CARDS[18] = dict(slug='round-1-jury', step='None', verdict='UNUSED BY THE GOAL', does="""
`rank_round` is ordinal-jury maths: `coarse_cut` (:25), `pair_batches` (:40), `validate_pairs` (:54), `fine_order`
(:74, clean tie resolution); `coarse`, `fine` and `calibration` (:112–:156) are wired to docs/rounds/r1-balm.
`round_jury_completion.complete_batch` (:167) asks again only for missing pairs, at most three rounds per Retry.""",
    run="""
Twenty ids in batches of nine; the balm round's pair and jury tests run.""", keep="""
- nothing the chain needs: the designer flow has the owner pick, with no jury.""")

CARDS[19] = dict(slug='jury-j1-j2', step='None (the owner is the gate)', verdict='UNUSED BY THE GOAL', does="""
`ask` (:355) makes one Anthropic call per juror and writes an immutable record; `combine` (:459) takes the stricter
score per dimension and unions the hard failures; `judge` (:518) runs J1 and J2 and writes verdict.json;
`rank_sketches`/`_v2` and `idea_check`/`_v2` rank and check Day 8–9 sketches. Its rubric is a 190 × 120 mm palette lid's
(`LID_WHAT` :288).""", run="""
Its rubric read; its Day 8 tests run.""", keep="""
- nothing the chain needs (the owner's Accept/Redraw replaced juries).""")

CARDS[20] = dict(slug='designers-eye-pitch', step='None (the files eye is round_files_faces.advice_prompt)', verdict='UNUSED BY THE GOAL', does="""
`render` (:149) rasterises an .ai page; `look` (:194) asks a vision model to list differences between a concept and a
drawing; `agreed` (:290) keeps what two looks name; `check` (:537) runs up to three rounds, recolouring the document
(`recolour` :377) between them. Imported by the old agent pipeline (aria, targets.container, pipeline.views).""", run="""
Round 3's 1.0 die PDF (row 8's file) rendered; two hand-made looks given to `agreed` (it needs a look's full record —
check, part and shape — and refused the short one, as the run shows); its test in the targets file run.""", keep="""
- `agreed` — two looks reduced to what both name (an idea the files eye does not need: it looks once).""")
