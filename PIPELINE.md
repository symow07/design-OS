# The fixed pipeline

**Brief in.** Any product—bottle, palette, lipstick or another kind—with its
specifications. Sizes may be estimates, marked provisional. Missing measurements
never block the ideas half.

**Ideas half — the designer flow.** "New design" starts it. The system researches
the category as a designer would, on the web through Tavily (category, recent launches,
materials, finishes, colour, type; every source kept with a one-line takeaway)
and in the house library (the top twelve matches by the brief's words and
colours). Only words reach the board plan; no web picture ever reaches the image
model, and a board may be drawn from at most three house-tier library pictures,
recorded by hash. It makes three mood boards, each ONE picture
(swatches with hex, materials and finishes, type character, motif and texture)
with its idea line as live text on the page: one bold, one refined, one
unexpected, each linked to a product truth in at most eight words. The owner
picks one board, with an optional reason. Then the die comes first (owner,
2026-10-28): the engine solves the stand's die (counter_tray_header 1.0) from the
brief's grid and the product records, before any design is drawn, and renders
its flat template sheet (every face outlined and named, the bleed, the unprinted
parts greyed, creases with their fold direction, each face's way up, the
shopper's faces marked FRONT). From the board the system plans 3 designs,
differing in composition. Each design is ONE edit of that template with the
picked board as its style reference: artwork painted into the printed faces and
their bleed only, with no lettering. The engine then applies the die again:
anything painted outside a printed face and its bleed is cut away, and every
unprinted part is the template's own. The die-match proof and the colour across
each fold are recorded. Each design is shown three ways: the flat die with its
artwork (the main view), our own folded drawing of it, and the stand with the
products standing in it (both drawings, not renders). A quick quality check
(banned motifs absent, no lettering painted, every printed face painted) is shown
beside each design and never removes one. The owner picks 1 from the flat die,
with a reason: what is picked is what prints. At each pick, "None of these" with
one line makes three new boards or designs, once. Every pick and reason is kept
as taste memory for later boards.

**Execution half — the face method (owner, 2026-10-28: the owner is the gate).**
From the picked picture, the system makes printable `.ai` files, for every product
type. The unit is the FACE: any flat printed surface (a bottle face, the cap, each
stand face, a palette lid, a carton panel). Each face is its own job, and one face
failing never blocks another:

1. **Draw** it. A stand face is cut straight from the picked flat artwork at the
   die's transform: nothing is cropped, redrawn or re-fitted. A product face (the
   bottle, the cap) is one gpt-image-2 edit on its own flat face template, guided
   by the picked picture's view of it, with **no lettering**. Nothing is erased
   after drawing.
2. **Place** its words as live type from the brief's COPY, and the approved logo,
   from the face's own geometry.
3. **Preview** it flat, written by the same writer and placement the files use.
4. **The eye** looks once per drawing, cheaply; its notes are advice, never a block.
5. **The owner** Accepts the face or asks for a Redraw (one edit, an optional
   one-line note; a note about the words is kept, never drawn). A stand face's
   Redraw repaints that one face on the same template, every other face kept
   byte for byte.

"Make my files" opens once every face is Accepted: the stand's one flat raster is
placed on the dieline engine's die at 1:1 with each face's live type and logo, and
the layered `.ai` files, the die's 1:1 PDF (its ARTWORK layer carrying the
raster), DXF and CF2, flat previews, the built drawing and a zip are written. No review follows. One spend cap per round; a call whose
outcome is unknown is checked once against the provider, then used or closed, and
is never a permanent stop.

Modules the method uses (all existing, reused):
- `apps/dielines/exporters/counter_display_files` — the flat template, the die
  applied again, the die-match proof, the 1:1 PDF read back, the folds' pairs.
- `round_files_gate` — the board, the face jobs, the flat painting's claimed
  attempts, Accept / Redraw / Make my files.
- `round_files_faces` — face geometry, the flat painting's prompt and settling,
  each stand face cut from it, the product faces' template and edit prompt, live
  type placement (`marks`, `upright_marks`), the preview spec, the composer, the
  folded and loaded drawings.
- `round_files_dial` — type placed from a drawn dial's bands and ring.
- `round_files_reading` — reading the picture: panels, crops, COPY fields.
- `round_files_stand` + `apps/dielines/geometry/counter_display` (counter_tray_header
  1.0) — the die, solved from the brief alone when no picture exists.
- `zilal_tray` (turn) — each face as it folds.
- `round_files_export` — the writer: live type in the pinned fonts, the approved
  logo, the die locked, Illustrator's own save and reopen.
- `product_drawing` — the drawings; `round_calls` — the paid boundary (image edits
  stream, so a tunnel's cut of a silent connection does not lose them).

Annotation, 2026-10-28 (the engine consolidation, docs/consolidation/PLAN.md; the order above
is unchanged): the dial type, the picture's reading and the ornament lettering are now
sections of `round_files_faces`, and so is `zilal_tray`'s turn; the stand's die is solved
from the brief by `counter_display.solve_stand` (its files written by
`round_files_gate.build_stand`); the files outbox and job are sections of
`round_files_gate`; `round_calls` also holds the image guard and the ideas half's image
calls. The engines are listed in docs/ENGINE_MAP.md.

**Anything that folds: the die first (owner, 2026-10-28).** For every stand and
every carton, the dieline engine draws the flat die first — every panel, flap,
tab, glue zone, insert and header leaf, at 1:1 mm with bleed — and the design is
painted onto that flat die. The image model never draws geometry; it paints only
inside the die's printed faces. For the product itself (bottle, cap, wrap), the
flat wrap or face template comes first in the same way. Not built yet: the
product's own flat face templates. Until they exist, Build the files takes a flat
pick only where the product faces were already drawn (round 3), and a new round's
flat pick says so in words instead of starting.

**THE CONTRACT — FROZEN.** The ideas half outputs one full-size picture per
design. Amended by the owner on 2026-10-27: "The picked picture is the design
intent. Execution draws each flat face front-on as an edit guided by that
picture, and the eye checks each face against it. The die always comes from
the dieline engine." Amended by the owner on 2026-10-28 for anything that folds:
"The stand is never designed as a folded picture. ... the dieline engine draws
the flat die first ... and the design is painted onto that flat die. The design I
pick is already in the shape of the print file." Every future prompt must name
which half it changes and may not change this contract.

**Out of scope unless the owner asks:** cartons, leaflets and regulated copy.

Annotation, 2026-10-29 (the owner's goal of 2026-10-29, §1: the chain traced in code; the order above is unchanged).
Each hand-off, the function that passes it on, and the test that proves it. Paths are under
`bbrose_design_os/apps/`; S = `pipeline/services/`, T = `pipeline/tests/`. The page views are `dashboard/
product_round_views.py` and `dashboard/round_files_views.py`; the worker's two tasks (`pipeline/tasks.py`:
`run_creative_round_step`, `run_round_files`) are thin wrappers.

| Step | Engine | Function that passes it on | Test that proves it |
|---|---|---|---|
| Brief → research | round runner (S/round_flow.py) | `product_round_views.new` → `round_flow.create_round` → `run_step_job` → `round_designer.research` | T/test_round_flow.py::test_designer_flow_runs_from_start_to_the_frozen_handoff_with_one_redo_per_pick; T/test_product_round_page.py::test_new_design_starts_the_designer_flow_and_the_classic_page_is_kept_unlinked |
| Research → three boards | round designer (S/round_designer.py) + paid boundary (S/round_calls.py) | `round_designer.boards` (`text_call`, `design_image_call`) | the omnibus above; T/test_round_flow.py::test_designer_tavily_failure_carries_on_with_library_and_knowledge_and_says_so |
| Boards → board pick | round runner | `product_round_views.board` → `round_flow.submit_board_pick` → `round_designer.board_pick` | the omnibus; T/test_product_round_page.py::test_decision_posts_go_through_round_service |
| Board pick → three designs on the flat die | round designer + stand die (dielines/geometry/counter_display.py) + die writer (dielines/exporters/counter_display_files.py) | `round_designer.designs` → `die_first` (`round_files_gate.build_stand` → `counter_display.solve_stand`; `round_files_faces.flat_setup`) → `design_image_call(template)` → `settle_flat` → `flat_drawings` → `pick_page` | the omnibus; dielines/tests/test_counter_display.py::test_the_die_comes_first_and_is_applied_again_to_a_painting_exactly |
| Design pick (sealed) | round runner → round designer | `product_round_views.pick` → `round_flow.submit_pick` → `round_designer.finalize_pick` (`flat_die_handoff/1`) | the omnibus |
| Pick → the die (files build) | owner gate (S/round_files_gate.py) + stand die | `round_files_views.start` → `round_files_gate.start` → `input_snapshot` (a flat pick: `flat_reading`, `install_pick`) → `run` → `restand` / `flatten` → `prepare_stand` → `build_stand` → `solve_stand` (rows inside the ruled size, `SIGHTLINE_REVISION`) | T/test_round_files_faces.py::test_a_flat_pick_starts_its_files_and_reaches_every_face_waiting_for_the_owner; ::test_a_flat_pick_whose_die_changed_is_refused_in_words; ::test_a_stand_solved_before_the_sightline_fix_is_solved_again_inside_its_size; dielines ::test_round_3s_stand_shows_every_top_band_and_the_headers_safe_area_inside_its_ruled_size |
| Die → painting on the whole die (the idea) | owner gate + face builder (S/round_files_faces.py) + paid boundary | `work` → `_paint` → `round_files_faces.paint_flat` → `FilesContext.face_edit` → `settle_flat` | T/test_round_files_faces.py::test_every_face_is_drawn_previewed_and_advised_then_waits_for_the_owner; ::test_a_lost_painting_waits_for_the_owner_and_a_redraw_paints_the_die_again |
| Painting → stand faces at 300 ppi, each on its own outline | face builder + owner gate | `_draw` → `_cut` → `claimed_call` → `round_files_faces.panel_face` (`panel_sheet`, `against_painting`) | ::test_stand_faces_are_drawn_per_panel_at_300_ppi_checked_against_the_painting_and_composed_at_300; ::test_a_panel_canvas_keeps_to_the_models_range_and_its_hold_scales |
| Product faces on their nets (die-first) | face builder | `_draw` → `round_files_faces.net_setup` / `draw_net` | ::test_the_bottle_and_cap_are_painted_on_their_own_flat_nets_die_first; ::test_a_new_flat_attempt_with_panels_and_nets_draws_every_face_again_one_call_each |
| Faces → the gate (Accept / Redraw) | owner gate | `round_files_views.accept_face` → `round_files_gate.accept`; `redraw_face` → `redraw` → `_wake` | ::test_accepting_every_face_opens_make_my_files_and_no_review_follows; ::test_a_redraw_is_one_edit_with_its_note_and_the_other_faces_keep_their_accept |
| Gate → Make my files | owner gate | `round_files_views.make_files` → `round_files_gate.make_files` → `run` → `make` | ::test_accepting_every_face_opens_make_my_files_and_no_review_follows |
| Make my files → layered .ai, DXF, CF2, 1:1 PDF, previews, zip | writer (S/round_files_export.py) + die writer + face builder + product drawing (S/product_drawing.py) | `make` → `build_outputs` → `round_files_faces.compose_stand` (300 ppi) → `round_files_export.export_object` (+ `native_roundtrip`) → `counter_display_files.write_all` → the zip | ::test_accepting_every_face_opens_make_my_files_and_no_review_follows; dielines ::test_the_die_makers_files_carry_their_layers_and_read_back; T/test_round_files_export.py::test_files_export_full_stand_die_visible_after_actual_native_reopen |

Outside these engines the chain still calls held code in five places: `web_research.WebPolicyError` (research),
`dashboard.materials_library` and `materials_retrieval.index_row` (the house library), `ire.font_pool` (the granted
fonts), `ire.handoff.illustrator_exec.run_jsx` (Illustrator's own save and reopen), and
`dashboard.product_round_views.publication` (read by `input_snapshot`).

Annotation, 2026-10-30 (the owner's part 1 of 3, CURRENT_DECISIONS.md; the rules below hold for every round, product and die,
and supersede the steps above where they differ):

**1. The painting prints whole.** The painting is the artwork. A print file's only layers are PAINTING, FOIL, RELIEF, TYPE, LOGO,
DIE and GUIDES (`round_files_export.LAYERS`): no fitted vector piece is laid over the painting, and the writer refuses one.
`round_files_export.print_check` reads every written file back and fails it in words if it has any other layer, a vector on the
painting, or anything that prints outside the die's printed faces plus their bleed. This replaces "built in layers" (2026-10-29)
and its vector share. The one exception is a clear surface: its painted ground and window carry no ink, so only its woven art
prints (`round_files_faces.clear_painting`).

**2. One ground across every panel.** The design's ground is the picked board's palette colour whose role names the ground
(`design_ground`). It is painted into the picture, never supplied by a flat layer. The wrap's own pixels are toned to it at $0
(`ground_tone`: its largest colour moved, its threads and fruit kept, one tone for the whole picture, and only when it is under
ΔE00 12 off). Each panel is then measured on the raster that prints (`ground_check`, ΔE00 4). A panel still off is repainted once,
inside the cap (`round_files_gate.ground_repairs`); after that the page says so, and it is never repainted again. The cap's own
gold and the bottle's clear body are their own grounds (`OWN_GROUND`).

**3. The panels link across the folds.** Panels that meet at a fold are one picture: joined in one plane (`wrap_layout`; a stand:
`STAND_WRAP`, right wall, back, left wall, front strip, the header back above the back), painted in one edit (`paint_wrap`), then
cut along the die, each face upright with its bleed (`wrap_face`, source 'wrap'). A strip has one fold it cannot join by
construction (front strip to right wall): only ground and bands are asked to reach it, and it is checked like every other. A
face at its own quality (the header at high) and a Redraw are painted alone on the art they join, which stays byte for byte.
`fold_check` measures every fold on the raster that prints: the two sides' grounds within ΔE00 3; every gold band of either side
found on the other within 0.5 mm (a band is a row at least 20 L lighter than what is around it), a band with nothing to meet
failing. Pixel to pixel beside it is a note, not the bar: a fold through one picture measures median 3.3 there, because a thread is
not a colour. A plain area a face's words stand in, lost by the wrap, is put back at $0 from the art that had it
(`restore_word_place`), since a repaint alone moves its bands; a face still without one says so on its card.
The stand folded from the front three-quarter and from behind is on the page (`three_quarter_drawing`). Each measure takes its
panels and folds as data; each rule is tested on a generic carton as well as the stand. A wrap of the whole stand is 3840 × 1664 px
at about 250 PPI, composed at 300.

**The chain now reads:** die → the picked painting installed → **one wrap, $0 cuts** → the header on what it joins → bottle and cap
on their nets → the owner's Accept or Redraw per face, or Accept all → Make my files. The page works in place: no reload, the scroll
and a note being typed kept, and it asks again while a job runs (`static/js/round-files.js`). `round_files_gate.relink` is the
owner's order to rebuild an existing round on these rules: its cap raised in his words, its panels measured first, and the wrap
claimed once if they do not hold.

Annotation, 2026-10-30 (the owner's part 1B, CURRENT_DECISIONS.md; for every round, product and die, and superseding part 1's "the painting prints whole" and "painted into the picture itself"):

**The file's law.** Every print file, top to bottom: DIE (locked, sub-layers CUT, CREASE, GLUE, SAFE, BLEED), WORDS (the approved logo, live type), FOIL, RELIEF, MOTIFS (a sub-layer per panel, each motif its own named object, as "header / doe medallion", "back / bloom 07"), GROUND (one flat colour per design, a vector shape per panel). `round_files_export.law_check` reads what was written and what Illustrator holds, and fails the file if the die merges with art, a motif is not its own object, or the ground is not one flat colour. Each object is imported on its own into its sub-layer and named (`spec_ops`, `native_roundtrip`).

**Each motif on its own, in its true medium.** A vector the engine draws (`woven_band`, `sprig`, `small_flower`, `rosette`, `double_frame`), in clean curves, never traced. A picture the image model paints alone on a plain ground: one sheet, one medium call (`sheet_template`, `paint_sheet`), the hero and the design's registers each in a cell, cut apart by `cut_sheet` with a clean mask, the ground unmixed from their edges; a cell that is empty or ran out of its edge is dropped and listed. Saved once in `files/motifs/` (file, mask, size, colours, hash) and reused on every face. A house piece is judged from its file, not its caption (`library_piece_verdict`), and the ranking is shown; placing one is not built yet.

**Placement by rules, one record.** `plan_face` writes each face's placement record: its words and quiet zones first (a logo's height round the logo, a line's cap height round a line), then the hero where the design names it (never the header back), the bands level round the stand (each panel's band whole units to its fold, a matched pair), the blooms on the design's measured pitch, sprigs in the columns between. A motif never crosses a fold, a glue flap, a cut line or the bleed edge. The same record drives the preview, the print file and the drawings (`plan_spec`, `stand_pieces`). `placement_check` fails a motif in a quiet zone, over a fold, on another, or words under 4.5:1 (`word_colour` takes the design's own colour that reads). `press_check` holds foil to 0.1 mm lines and 0.2 mm gaps, relief to 0.3 mm, vectors closed and clean, pictures to 300 PPI at print size; a failing finish drops to ink and is listed.

**The chain now reads:** die → the picked painting read for its rhythm → one motif sheet → every face placed at $0 → Accept per face or Accept all → Make my files. A Redraw with no note places the face again at $0. A Redraw with a note paints a new sheet, since motifs are shared, and every face is placed again for the owner's Accept. The wrap of part 1 is held only for a build already on it. `round_files_gate.pieces_view` builds "What you'll get": each layer alone, the library, every check, every fold at 400 % (`seam_proof`), and Illustrator's own proof on copies (`illustrator_proof`). `round_files_gate.rebuild_pieces` moves an existing round onto this path, keeping any library it has.

Annotation, 2026-10-31 (the owner's part 2, CURRENT_DECISIONS.md; for every round and every stand):

**The stand is chosen, then solved.** New design shows the types the engine can build, each with a small drawing and one line; the engine suggests one by its rules (`stand_types.suggest`), the owner chooses, and the size it will build is shown live before Start (`product_round_views.stand_preview`). The choice rides in the brief as `stand.type`.

**One model of the die folded.** `stand_templates` draws a template's die from the product records and the envelope, never from a picture. `stand_fold` folds that die in three dimensions, the board by its mid-plane, and every proof reads that one model: the closed size, each joint (0.0–0.5 mm), panels passing through each other, each lock's tab in its slot, each product's seat and clearance, art under a flap or in a glue zone, the sightlines from both of the owner's eyes (500/350 and 550/500 mm), and the line drawings. `stand_templates.qualify` gathers them with the grain, the allowance of every fold, the trade rules and the rules file. A template is done only if all hold.

**Least change, listed.** Rows rise until every product's bar is seen; the back wall stands until the whole header's safe area is; a depth grows only as far as its openings and webs need. Each change from the brief's size is in the record's `changes` and on the page. Unknowns are ⟪PROVISIONAL⟫, printed on the drawings, and never block.

**The templates:** `counter_tray_header` 2.0, `stepped_tiered`, `lid_header_tray`, `slanted_front`, `tester_unit`. `counter_display.solve_stand` gives the chain the same result shape from a template when the die comes first (no picture, or a chosen type). A stand read from a picture keeps 1.0. The printed faces stay the chain's six; a slot-in header's leaves are on their own part (`counter_display.piece_of`, `round_files_faces.die_face`). Rims, inner leaves and stairs carry only the flat ground (`die.ground_faces`, `ground_only`).

**The file's law, extended.** DIE's sub-layers are CUT, CREASE, PERF, HALF-CUT, GLUE, SAFE, BLEED, each always present, and `law_check` fails a file without one.

**The die's files** (`counter_display_files.write_template`, written when the stand is solved, in `files/stand/sheets/`): die.pdf, die.ai, die.dxf, die.cf2, fold-up.pdf, assembly.pdf, cut-and-fold-1to1.pdf (A3, tiled), nest.pdf, each read back (`opens`: PyMuPDF, ezdxf; CF2 by our own reader, no die maker's CAD being here). die.ai is Illustrator's own, drawn by the law and read back (`native_die_ai`). The round's page shows them. `tools/stand_family_proofs.py --illustrator` writes every template's set to `docs/research/stands/templates/`.

**An existing round.** `round_files_gate.redie` is the owner's order to move a round onto a template at $0: the old stand kept in `files/superseded/`, then `rebuild_pieces`. `restand` leaves a template stand alone.
