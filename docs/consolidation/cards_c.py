"""Card texts, rows 41–57."""
CARDS = {}

CARDS[41] = dict(slug='zilal-header', step='None', verdict='UNUSED BY THE GOAL', does="""
`build` (:186) makes Day 12's display header master from the ranked sketch (`the_pick` :38 reads ranking-map.json):
it splits the painted words into hero, name and logo (`word_groups` :97, `merge_lines` :119, `name_likeness` :139),
takes the lid's vectors (`lid_assets` :151) and writes header-master.pdf, a 300 ppi flat and a finish proof into Day 12's
folder.""", run="""
Its Day 12 pick read; its master built again into a scratch folder.""", keep="""
- nothing the chain needs (round_files_dial places the round's header type).""", broken="""
Its build refuses any folder outside the repository (every record path is made relative to it).""")

CARDS[42] = dict(slug='zilal-lid-master', step='None', verdict='UNUSED BY THE GOAL', does="""
`build` (:1791) is Day 11's lid master of pick B-1.3 by the preservation path: the hero's bevel and alpha (`bevel_alpha`
:700, `read_hero` :836), potrace with a proof (`trace_alpha` :543, `prove_trace` :567), the hatch fitted
(`fit_hatch` :868), the logo and lines fitted, an engine document (`engine_document` :1451) and the files written into
Day 11's folder; `refinement` and `rank_round` are paid.""", run="""
Its Day 11 pick loaded; its tests run.""", keep="""
- nothing the chain needs.""")

CARDS[43] = dict(slug='zilal-object-sticker-box-cartons', step='None', verdict='UNUSED BY THE GOAL', does="""
Day 11–12 surfaces composed from the lid's assets: the lid's sides, inside and tray (`sides_build` :314,
`inside_master` :711, `tray_master` :1043 — crop 3 mm, upscale 2×, mirror the bleed), the base sticker
(`zilal_sticker.build` :773 with `fit`, `widowless`, `glue_ci`), the outer box (`zilal_box.build` :174) and the stick
cartons (`zilal_cartons.build` :1141 through stick_carton), each reading Day 11/12 records.""", run="""
Their tests (the Ẓilāl pack and the Day 13 lipstick carton files) run.""", keep="""
- nothing the chain needs.""")

CARDS[44] = dict(slug='zilal-lipstick-and-balm', step='None', verdict='UNUSED BY THE GOAL', does="""
Paid sketch rounds for the lipstick and the balm (`sketch`, `rank`, `crop_wraps`, reading Day 9's direction B-1) and
their masters: `zilal_lipstick_master.build`/`build_closed` (:1308, :1376: body, cap, label, A4 page, a product drawing)
and `zilal_balm_master.build` (:1666: the sketch's dashed guides cleaned by `find_dashes`/`clean_dashes`, ghost edges
rebuilt by `harmonic_fill`/`repair_ghost`).""", run="""
The balm's trim rows on an empty wrap; their tests run.""", keep="""
- nothing the chain needs.""")

CARDS[45] = dict(slug='lid-master', step='None (Day 10); the colour maths', verdict='PARTLY', does="""
`build` (:2166–:3030) is Day 10's print master of pick A-2.3: the sketch upscaled, finishes separated, live type, an
engine document (`engine_document` :1779), the relief plate; `master_facts` (:3032). The chain uses `srgb_to_lab`
(:109, sRGB to CIELAB D65, pure numpy), `delta_e00` (:122, CIEDE2000 after Sharma, Wu and Dalal), `REPO` and `rel`
(:1880). Other old modules take its constants and logo paths.""", run="""
Pure red to Lab (the known value is 53.2408, 80.0925, 67.2032); ΔE00 between round 3's three shades; its Day 10
tests run.""", keep="""
- `srgb_to_lab`, `delta_e00` — the colour maths the dial and the fold check use.""", partly="""
Good: the colour maths. Old: the lid master itself.""")

CARDS[46] = dict(slug='product-drawing', step='The pick\'s folded and loaded drawings; the built drawing', verdict='GOOD', does="""
`draw` (:162) lays a closed product's front view and three-quarter view side by side from its flat wraps, labelled
"drawing, not a render" (`view` :54, `square_view` :101, `outline` :153, `band_texture` :44) and `write_record` (:217)
records the inputs by hash. The face builder's `drawing` and `folded_drawing` and the designer's `flat_drawings` draw
through it. It takes `REPO` and `rel` from lid_master.""", run="""
Round 3's stand folded and loaded, drawn from a $0 stand-in painting by the designer's own `flat_drawings`; the drawing
tests of the face file run.""", keep="""
- `draw`, `view`, `square_view`, `outline`, `band_texture`, `write_record`.""")

CARDS[47] = dict(slug='day-8-9-lid-builds', step='None', verdict='UNUSED BY THE GOAL', does="""
The Day 8–9 rebuilds of a lid from a sketch's spec: `truthful_concept.layout`/`document`/`render`/`paint_plate` (paid)/
`prove_plate` (tesseract), `rich_concept.layout`/`make_plate`/`checks`, `rich_plate.prove_rich_plate` and
`clean_small`, `lid_devices.gravure`/`interference`/`astrolabe` (pure ornament geometry), `day9_recipes.recipe` and the
paid `day9_sketches.make`/`concept_sketches.make`. Their constants point at Day 8 and Day 9 folders.""", run="""
The gravure and astrolabe devices drawn; the Day 8 concept and Day 9 ornament tests run.""", keep="""
- nothing the chain needs (rebuilding a design from its spec is the redrawing the owner ruled out).""")

CARDS[48] = dict(slug='palette-cartons-and-stickers', step='Cartons (Day 10–13 cartons; none in the chain yet)', verdict='PARTLY', does="""
`palette_box.build` (:199) the palette's outer box on reverse tuck 1.4 from Day 10's lid and sticker (`die` :45 reads a
saved spec), `fold_check_record` (:435), `clean_parts` (:508); `palette_sticker.build` (:605, EN/ES/AR back sticker,
`wrap`, `fit`, `document`); `stick_carton.build` (:1649, the lipstick and lip balm cartons on straight tuck 1.4 through
`registry.print_ready_version`, `die` :224, `lay` :601, `bands_for` :714, refusing without translations);
`palette_board.build` and `collection_board.build` (boards of pictures). Every default path is a Day 10–13 folder.""",
    run="""
The lipstick carton's die and the palette box's die drawn by their own `die`; the Day 11 carton tests run.""", keep="""
- `stick_carton.die`, `palette_box.die` — the goal's cartons on the qualified 1.4 trade tuck.
- `palette_box.fold_check_record`, `clean_parts`, `stick_carton.lay` — ink against creases, copy laid in a panel.""",
    partly="""
Good: the dies and the fold record. Day-bound: every build reads a dated folder; the chain makes no carton yet.""")

CARDS[49] = dict(slug='live-type-and-fonts', step='Live type (the fonts the writer may use)', verdict='PARTLY', does="""
`font_pool` (223 lines) reads the GRANTED, unverified and blocked font census (Day 6) and the exclusions (Day 7):
`pool` (:14), `files_of` (:19), `excluded` (:55), `is_excluded` (:68), plus the type book's `classify`,
`catalogue_entries`, `chain`, `day7_grants`. The writer uses only `files_of('granted')` and `is_excluded`.
`lettering` (1,668 lines) builds a logotype from a licensed face's outlines (`set_word` :590, `logotype` :1292);
`arabic_display` (1,334 lines) derives Arabic display fonts through HarfBuzz (`derive` :405, `ensure_chosen` :1141).""",
    run="""
The GRANTED census's size, the exclusions, and the two faces the writer validates; the Day 7 font tests run.""", keep="""
- `font_pool.files_of`, `is_excluded` — the licence check the writer makes on its two pinned faces.""", partly="""
Good: the census reader. Unused by the chain: `lettering` and `arabic_display` (the old pipeline's type book).""")

CARDS[50] = dict(slug='approved-logo-placement', step='Logo', verdict='GOOD', does="""
The same module as row 35: `LOGO` (round_files_export.py:28, docs/brand/mark/bbrose-logo.svg) and `LOGO_SHA256` (:29)
pin the approved vector logo; `export_object` places each spec's `logos` and refuses a logo that is not the approved
file; the face builder's `marks` places the front strip's logo over its line inside the safe area.""", run="""
The logo file against its pin; the writer's logo refusal test run.""", keep="""
- `LOGO`, `LOGO_SHA256` and the placement in `export_object` and `marks`.""")

CARDS[51] = dict(slug='tracers', step='None (the die-first method paints; nothing is traced)', verdict='UNUSED BY THE GOAL', does="""
`line_art.trace_lines`/`trace_frame`/`trace_window` (:276–:577) skeletonise line art into strokes;
`flat_motif.read_flat` (:236, the ink, ground and stroke of a flat picture), `trace_flat` (:296, potrace outlines),
`colour_art`, the paid `redraw_flat`, `colour_check`, `shape_whole`; `traced_text.inspect_bundle` (:157) checks a
bundle's live text and OCRs its raster layers. Imported by the old agent pipeline's targets.""", run="""
`read_flat` on round 3's drawn header face; the traced-text test run.""", keep="""
- nothing the chain needs.""")

CARDS[52] = dict(slug='finish-proof', step='None', verdict='UNUSED BY THE GOAL', does="""
`prove_build` (:1184) shades a flat under a softbox with the engine .ai's foil and emboss plates (`render_proof` :1087)
and measures them (`coverage` :553, `foil_limits` :767, `line_density` :878); it reads only plates written by
`pdf_ai._draw_finish_plates`.""", run="""
Its foil and relief tests run.""", keep="""
- nothing the chain needs (the round's .ai carries no finish plates).""")

CARDS[53] = dict(slug='ire-composer-and-emitters', step='Make my files (one part: Illustrator\'s save and reopen)', verdict='PARTLY', does="""
`compose.compose_components_graph` (:203) builds the old pipeline's design graph per carton panel; `pdf_ai.emit_pdf_ai`
(:51) writes a PDF-compatible .ai with ReportLab; `native_ai.tree`/`script`/`build` (:898–:1443) drive Illustrator
through JSX; `illustrator_exec.illustrator_available` (:23) and `run_jsx` (:38) run a script through osascript — the
round writer's `native_roundtrip` uses `run_jsx`.""", run="""
Illustrator present on this machine; the .ai emitter's tests run.""", keep="""
- `illustrator_exec.run_jsx`, `illustrator_available` — Illustrator's own save and reopen.""", partly="""
Good: `run_jsx`. Old: the design-graph composer and the emitters (the old pipeline's).""")

CARDS[54] = dict(slug='native-handoff-and-print-pack', step='None', verdict='UNUSED BY THE GOAL', does="""
`native_handoff.generate_native_handoff` (:97) packages a DielineJob output for Illustrator; `print_pack.build` (:948)
builds Day 13's print pack from earlier days' PDFs; `golden_hour_fixes` is Day 11's Golden Hour repair.""", run="""
The print pack's read-back tests run.""", keep="""
- nothing the chain needs.""")

CARDS[55] = dict(slug='day5-to-day14-services', step='None', verdict='UNUSED BY THE GOAL', does="""
Thirty-four modules, one per rescue day: masters, proofs, scenes, mockups and pick pages for Days 4–14. Twenty-two are
imported by nothing outside tests; the dashboard's day pages import day5_master, day8_pick, day9_pick, day10_master and
day13_creativity_page; jury.py imports day6_critic.""", run="""
Day 8's pick record and Day 13's page state read; the Day 5 and Day 13 page tests run.""", keep="""
- nothing the chain needs.""")

CARDS[56] = dict(slug='day-views-dashboard', step='None', verdict='UNUSED BY THE GOAL', does="""
The day pages: day5_views and day6_views (stand-master and serum-master pages of Days 4–6), day8_views (the palette
pick page with Days 9–10 on it) and day13_views (the creativity check and the owner's ranking). Each serves files only
while their pinned hashes match.""", run="""
Every day route resolved; the creativity page's tests run.""", keep="""
- nothing the chain needs.""")

CARDS[57] = dict(slug='palette-engine-m-series', step='None (palettes are in the goal; this engine is not on its path)', verdict='UNUSED BY THE GOAL', does="""
Eighty-four palette_* modules (about 30,000 lines): the PALT-M2 layout kernel (`palette_layout_kernel.resolve_layout`),
mechanism and tray geometry, moulded and recessed pans, the ES3083 design intent and owner confirmation, the M5
material characterisation, the M6 powder and flake rigs and gates, governance and statistics guards, an M7 .ai emitter,
and Day 10's palette products. The dashboard's ES3083 confirmation view, the old palette target, the container
silhouettes and two evidence modules import parts of it.""", run="""
Its file and line count; the layout kernel's tests run.""", keep="""
- nothing the chain calls (a palette in New design is a lid face and its carton, drawn by the face method).""")
