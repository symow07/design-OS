"""Card texts, rows 21–40."""
CARDS = {}

CARDS[21] = dict(slug='research-tavily', step='Research (the web half)', verdict='PARTLY', does="""
`TavilySearchConnector.search` (:111) checks the spend cap, reads the key, posts one search under `paid_operation` and
writes a ledger row; `normalize` (static) keeps results with their page and drops Tavily's own answer. The designer
flow uses only these two (round_designer.py:140, :159). The rest is the older product research: `run_tavily_session`
(:294, DB session rows and the pilot packet), `plan_queries_v2` (:62, twelve fixed queries about a rose night serum),
`_retain_results`, `_fetch_phase`, `_fetch_images` and `HostManners`, which the trend board uses.""", run="""
Round 3's six saved searches read again (no search bought) and one reply normalised by the connector; the sources the
research kept counted; the Tavily tests run.""", keep="""
- `TavilySearchConnector.search` and `normalize` — the designer flow's six searches, metered and capped.""", partly="""
Good: the connector. Old: the session, the fixed serum queries and the fetch phases (the trend board's path).""")

CARDS[22] = dict(slug='web-research-gateway-aria', step='None directly; Tavily imports its policy helpers', verdict='PARTLY', does="""
A policy layer: `check_url_policy` (:96, scheme and private-address block), `robots_rules`/`robots_file`/`robots_verdict`
(:156–:230), `governed_fetch` (:308, redirects checked hop by hop, robots, a MIME allow-list, a byte cap, the body's
sha256), `normalize_url` (:290), `html_to_text`, `classify_tier`, `quarantine_write`. Its own search, `run_search`
(:462), always raises: no provider has a connector here, so `run_research_session` (:476) can only end BLOCKED.""",
    run="""
Each of round 3's research sources normalised and checked against the URL policy; its own search tried; its tests run.""",
    keep="""
- `governed_fetch`, `check_url_policy`, `normalize_url`, the robots helpers — imported by the Tavily connector.""",
    partly="""
Good: the policy helpers. Broken by design: `run_search` has no connector, so its research session cannot run.""")

CARDS[23] = dict(slug='trend-board', step='None (round_designer.research does the designer flow\'s research)', verdict='UNUSED BY THE GOAL', does="""
DB-bound on a design task of the old pipeline: `plan` (:392) scopes searches by platform; `build` (:465) creates a
TrendBoard and a research session, searches (Tavily), picks (`_pick` :543, caps per platform), fetches under robots
(`_fetch` :740) and reads pictures with a model (`_read` :971); `write_brief` (:1483) is one Claude call;
`mark_near_copies` (:1380, an 8 × 8 average hash).""", run="""
Its tests (in the Tavily and container-target files) run; it needs a design task of the old pipeline to do more.""",
    keep="""
- nothing the chain needs.""")

CARDS[24] = dict(slug='library-retrieval', step='Research (the house library) and the boards\' references', verdict='PARTLY', does="""
`materials_previews.run` (:148) renders one 1,600 px preview per unique house file; `materials_captions.run` (:138) is
the paid captioning (Day 7) and `build_index` (:282) merges captions, measured colours and rights into the materials
index; `materials_retrieval` reads it: `cards` (:104), `score` (:141), `rank` (:178), `select` (:191), `candidates`
(:225), `index_row` (:119). The designer flow's `library_matches` uses the dashboard's `materials_library.search_index`
and `preview_file`, and only `index_row` from here.""", run="""
The materials index's size; the dashboard's search run for round 3's words and each shade colour; the library's golden
tests run.""", keep="""
- `index_row`, the index and its previews — what library_matches reads.
- `build_index` — how the index is made.""", partly="""
Good: the index and `index_row`. Unused by the chain: `rank`, `select`, `candidates` (the older ConceptReference path).""")

CARDS[25] = dict(slug='image-guard', step='Every paid image call (its inputs and words)', verdict='PARTLY', does="""
`check` (:213) refuses an image call's inputs before payment: a non-OpenAI provider, another model, a competitor's name
in the words, a missing file, a rejected house design, a web picture, a file outside `ALLOWED_ROOTS`. `guarded_call`
(:255) logs every call to `CALL_LOG`. `denylist` (:160) hashes every rejected and web picture. Its roots and log are
pinned to Day 12 (`ALLOWED_ROOTS` :57, `CALL_LOG` docs/audit/day-12/image-calls.jsonl, `TODAY_OPERATION_PREFIX`
'day12/'). The flow does not call `check`: round_calls, round_ideas_calls, round_files_job, round_files_faces and
round_designer use `competitor_in`, `_under` with `WEB_ROOTS`, `APPROVED_LOGO` and `denylist`.""", run="""
`check` given round 3's own inputs as a flat painting would send them (the picked picture, the flat template) and a
prompt with a competitor's name; its refusal tests run.""", keep="""
- `competitor_in`, `_under` + `WEB_ROOTS`, `APPROVED_LOGO`, `denylist` — what the flow uses.""", partly="""
Good: the four parts the flow uses. Broken for the chain: `check` refuses the round's own pictures, because its roots
are Day 12's; the flow never calls it.""")

CARDS[26] = dict(slug='creativity-check-day-13', step='None', verdict='UNUSED BY THE GOAL', does="""
`build(out)` (:566) copies nine Day 9–13 record pictures to K1…K9 under a deterministic shuffle, writes the sheet,
map and two request files; `verdict` (:312) is pure; `day13_creativity_page.state` (:214) and `write` (:284, once) are
the page's. Every path is relative to the repository.""", run="""
Its build written again into a scratch folder; its two test files run.""", keep="""
- nothing the chain needs.""", broken="""
Its build wrote the nine tiles and the sheet, then refused to record them outside the repository (every record path is
made relative to it).""")

CARDS[27] = dict(slug='files-outbox', step='Make my files (starts and queues the execution half)', verdict='GOOD', does="""
`start` (:112) opens a files build for a picked design (a flat pick refuses in words until the product's flat face
templates exist: `flat_pick` :105), `enqueue` (:135), `run` (:208, one step under the build's lock, then the next),
`recover`, `retry` (:158), `retain_failure`/`fail` (:174–:183, using round_ideas.record_break and
round_master_flow.digest), `progress` (:293), `files_brief` (:32, the brief plus the round's committed Arabic shade
names).""", run="""
Its tests (the files page file) run.""", keep="""
- `start`, `enqueue`, `run`, `retry`, `fail`, `files_brief`, `progress`.""")

CARDS[28] = dict(slug='files-job', step='Make my files (the build\'s steps and its paid context)', verdict='GOOD', does="""
`run_step` (:501) runs read, stand, faces and files; `execution_brief` (:74) turns missing sizes into marked estimates;
`read_picture` (:331) is the paid reading of the picked picture; `prepare_stand` (:432); `build_outputs` (:446) writes
every object and the drawing; `provider_check` (:36), `checked_inputs` (:318), `input_snapshot` (:93), `tag_completed`
(:480); its paid face context downloads through image_producer.download_image_bytes.""", run="""
Round 3's brief made an execution brief; the job tests of the files page file run.""", keep="""
- `execution_brief`, `read_picture`, `prepare_stand`, `build_outputs`, `run_step`.""")

CARDS[29] = dict(slug='owner-gate', step='The owner accepts or redraws each face; Make my files', verdict='GOOD', does="""
The face as the unit: `work` (:297) draws each face job (a stand face cut from the flat painting, a product face as one
edit), places its type, previews it and asks the eye once (`advise` :206, advice only); `accept` (:365), `redraw`
(:383, one edit with a one-line note; a stand face repaints only its own face), `ready` (:414), `make_files` (:426) and
`make` (:440: every accepted face checked by hash, the objects written, the die's files from counter_display_files,
the zip). `flat_page`, `open_flat`, `flatten`, `migrate`, `restand` move older builds onto the die-first method.""",
    run="""
Each face's size on round 3's die; the gate's tests (accept, redraw, make) in the face file run.""", keep="""
- `work`, `accept`, `redraw`, `ready`, `make_files`, `make`, `die_sizes`, `restand`.""")

CARDS[30] = dict(slug='face-builder', step='Painting on the die; the stand\'s faces; type placement; the drawings', verdict='GOOD', does="""
Per face: `face_geometry` (:71), `template` (:203) and `prompt` (:276) for a product face's edit; the flat half —
`flat_setup` (:358), `flat_prompt` (:377), `paint_flat` (:499), `settle_flat` (:434: the die applied again, the proof,
the 1:1 PDF read back, ΔE00 across every fold by `seam_colour`), `painted_face` (:516), `flat_face` (:534),
`repaint_face` (:554); type: `marks` (:97, the header's from round_files_dial, the front strip's centred), `upright_marks`;
the composer `compose_stand` (:660, one raster on the die); `face_spec`, `product_spec`, `specs`, `face_views`;
`drawing` (:792) and `folded_drawing` (:851) through product_drawing; the eye's `advice_prompt` (:927). It takes
`face_mm_size`, `turn`, `upright_polygon` and `K` from zilal_tray, `glyph_metrics` from round_balm_master, and
`srgb_to_lab`/`delta_e00` from lid_master.""", run="""
Round 3 at $0: a stand-in painting (the real two were lost to the network) settled on the die, every stand face cut
from it, and the stand composed on the die with its live type and logo; the face file's tests run.""", keep="""
- `flat_setup`, `paint_flat`, `settle_flat`, `painted_face`, `flat_face`, `repaint_face` — the die-first painting.
- `marks`, `upright_marks`, `compose_stand`, `face_spec`, `specs` — type and the composition on the die.""", finding="""
The stand-in paints each face its own colour on purpose, so the colour across the folds it reports (ΔE00 up to about
39) measures the stand-in, not a design. The composed stand is one raster with 5 live type runs and 1 logo.""")

CARDS[31] = dict(slug='dial-type', step='Live type on the stand header', verdict='GOOD', does="""
`header_type` (:357) reads the drawn header: `band_masks` (:50) finds each shade band by colour (ΔE00 against the
brief's hexes, through lid_master's colour maths), `dial_centre` (:100), `label_windows` (:144) and `shade_labels`
(:165) set each shade's label on its own band, `free_ring`/`ring_type` (:212, :247) set BBROSE upright and ملمع شفاه along
the navy ring (round_files_ornament.layout_runs); metrics from round_balm_master.glyph_metrics.""", run="""
Round 3's drawn header face (faces/header/face.png) read and its type placed through the face builder's `marks`; the
dial tests run.""", keep="""
- `band_masks`, `dial_centre`, `label_windows`, `shade_labels`, `free_ring`, `ring_type`, `header_type`.""")

CARDS[32] = dict(slug='picture-reading', step='Reading the picked picture (panels, COPY fields)', verdict='GOOD', does="""
`copy_fields` (:31) gives the only printable characters (from the brief's COPY); `normalise_reading` (:171) repairs a
reading item by item and drops only the bad one; `shade_loading` (:255) reads each seat's shade; `validate_inspection`
(:299); `text_rows` (:355) and `ornament_rows` (:362) turn the reading's text into rows the faces place.""", run="""
Round 3's COPY fields and its saved reading's panels; the reading tests run.""", keep="""
- `copy_fields`, `normalise_reading`, `validate_inspection`, `text_rows`, `ornament_rows`, `shade_loading`.""")

CARDS[33] = dict(slug='ornament-lettering', step='Live type along a band', verdict='GOOD', does="""
`layout_runs` (:66) sets COPY as live words along an ornament zone's path, in visual order, each word turned to the path
(Arabic right to left); `zone_mask` (:35), `zone_record` (:44), `ornament_copy` (:27).""", run="""
Its tests (live words on an arc, read back) run.""", keep="""
- `layout_runs`, `zone_record`.""")

CARDS[34] = dict(slug='stand-adapter', step='Die solving (the stand from the brief and the picture\'s reading)', verdict='PARTLY', does="""
`solve_stand` (:130) turns the brief (and, if any, the picked picture's reading) into 1.0's product grid: the opening
with clearance, three-board webs, a provisional width/depth/height grown to fit, the header and front heights from the
reading's panel ratios (`_panel_ratio` :56), seats raised to the pictured rows (`observed_row_placement` :73); it then
calls counter_display.solve and 0.1's build_die, fold_check, sightlines, platform fronts and (optionally) the enclosure
elevations and rear raise, and writes the round's stand.json (`build_stand` :265).""", run="""
Round 3's stand solved (row 6's run); the adapter's tests in the 0.1 file and the face file run.""", keep="""
- `solve_stand`, `stand_layout`, `observed_row_placement`, `build_stand` — the brief to the 1.0 grid.""", partly="""
Good: the translation from brief to grid. Failing: nine of its tests in test_counter_tray_header.py (they expect the
older vision-count behaviour; the brief's grid now wins, 2026-10-28). It still calls 0.1's module for six functions.""")

CARDS[35] = dict(slug='writer-round-files', step='Make my files (the layered .ai, live type, the logo)', verdict='GOOD', does="""
`export_object(spec, folder, native=)` (:1023) writes one object as a six-layer 1:1 .ai: the raster artwork, live type
in the two pinned fonts (`font_records` :56 checks each against the GRANTED census and its pin), the approved logo by
its pin (`LOGO`, `LOGO_SHA256`), foil, the die locked; `measure_type`/`fit_type_envelope` (:185, :233) keep each word
in its box; `read_back_ai` (:714) re-reads layers, type, colours and the die; `native_roundtrip` (:920) has Illustrator
save and reopen it (ire.handoff.illustrator_exec.run_jsx). It takes FONT_PATHS, `rgb`, `glyph_metrics`, `shaped` and
`set_layers` from round_balm_master.""", run="""
Round 3's drawn header face written as a layered .ai with its live type and the logo (Illustrator's save not run here)
and read back; the writer's tests run.""", keep="""
- `export_object`, `font_records`, `measure_type`, `measure_turned_type`, `fit_type_envelope`, `read_back_ai`,
  `render_flat`, `native_roundtrip`.""")

CARDS[36] = dict(slug='retired-tracing-build-v1', step='None (retired 2026-10-28)', verdict='UNUSED BY THE GOAL', does="""
Nine modules in archive/round_files_v1 (art, line_fit, refinement_v2, repair_art, detail, attempt, attempt_art,
width_authority, extension) that traced and line-fitted the picked 3D picture onto the die; already out of the import
path, its tests beside it.""", run="""
Each archived module compiled, and its import from apps tried.""", keep="""
- nothing; the die-first method replaced tracing.""")

CARDS[37] = dict(slug='preservation-master', step='None (Round 1B/1C); one helper', verdict='PARTLY', does="""
`round_master_flow` runs an owner-started master over RoundMaster rows (`start` :31, `run` :151, `retry`, `fail`,
`tag` hard-wired to r2-gloss); `round_master_art` the steps (panels, paid detail/layout/plates, `build_files` :620,
eye, jury, publish); `round_master_files.Surface` a six-layer builder on round_balm_master's; `round_master_calls`
`MasterContext(RoundContext)` with `masked_edit` (:30, an edit with no image guard). `digest` (:23) is a stable
sha256 of any JSON value; round_files_flow.fail names failures with it.""", run="""
`digest` of a value; the master tests of the round flow file run.""", keep="""
- `digest` — used by round_files_flow.""", partly="""
Good: `digest`. Old: the Round 1B/1C master path; its pages are the round page's master links.""")

CARDS[38] = dict(slug='balm-round-1', step='None (Round 1); the type helpers and the parser', verdict='PARTLY', does="""
Fourteen modules for Round 1's lip balm (calls, master, sheet, finish, carton, run, close, review, page, …), all pinned
to docs/rounds/r1-balm. Still used by the chain: `glyph_metrics(copy, face)` (round_balm_master.py:49, fontTools
bounds and advance of a shaped string), `shaped` (Arabic reshaped and ordered), `FONT_PATHS`, `rgb`, `set_layers`
(the writer and the face builder use them) and `parse_response_text` (round_balm_calls.py:50, exactly one JSON fence or
plain JSON; the paid boundary, round_ideas and the jury completion use it).""", run="""
`glyph_metrics` of BBROSE and ملمع شفاه in the two pinned faces; `parse_response_text` on a fenced reply and on two
fences; the balm tests run.""", keep="""
- `glyph_metrics`, `shaped`, `FONT_PATHS`, `rgb`, `set_layers` — live type's metrics and the layers.
- `parse_response_text` — the one reply parser.""", partly="""
Good: the six helpers above. Old: Round 1's balm flow.""")

CARDS[39] = dict(slug='zilal-tray', step='None (Day 12); four helpers the face builder uses', verdict='PARTLY', does="""
`build` (:690) composes the Day 12 family display's faces from Ẓilāl's lid plate on the 0.1 die; `lid_banks`,
`bank_drift`, `drift_clear_of_creases`, `place_hero` and the words and marks writers do the Day 12 work. The face
builder uses only four names: `turn` (:637, a quarter-turn of a picture), `face_mm_size` (:641, a face's upright size),
`upright_polygon` (:593, its outline in the upright frame with the 3 mm bleed) and `K` (300 ppi in px/mm).""",
    run="""
The four helpers on each printed face of round 3's die; the Day 12 display tests run.""", keep="""
- `turn`, `face_mm_size`, `upright_polygon`, `K`.""", partly="""
Good: the four helpers. Old: the Day 12 tray composition.""")

CARDS[40] = dict(slug='zilal-display', step='None', verdict='UNUSED BY THE GOAL', does="""
Day 12's family display sketch round: `sheet` (:60), the paid `sketch` (:115) and `rank` (:264), `crop` (:182) at the
die's proportion, `lettering_box` (:156), `header_facts` (:39). `drawn_panel` (:147) finds the drawn panel in a picture
(rows and columns more than half non-white, inset 2 px); the engine map says the face builder takes it, but nothing in
the flow calls it today (grep).""", run="""
`drawn_panel` on round 3's drawn header, bottle and cap faces.""", keep="""
- nothing the chain calls.""")
