# The consolidation plan

Written 2026-10-28 for the owner's "Engine consolidation — fewer engines, each good" (CURRENT_DECISIONS.md, same
date). It is based on the 57 cards in [engines/](engines/) (`0d82b28`) and the import graph of `apps/` (AST,
function-level imports included). The plan is committed before any code moves.

## The rules this plan follows

1. **One target per job.** Each target is the best existing engine for its job (its card's verdict is GOOD). No new
   engine or module is made.
2. **A move is a move.** A part leaves its donor and enters its target, adapted to the target's code. Every module
   that imported it from the donor imports it from the target from then on. Nothing is left behind as a wrapper or a
   re-export. The part's tests move with it into the target's test file.
3. **An engine is one entry point plus the files only that entry calls.** Rows 1–4 are one engine split across four
   map rows: `calculate_dieline` dispatches the carton templates, the registry publishes them, and `qualify` checks
   them. Rows 35 and 50 are the same module (`round_files_export.py`) counted twice. After the merge each group counts
   once.
4. **Archived means moved to `archive/`, not deleted.** The move uses `git mv` into `archive/consolidation/<job>/`
   (`services/` and `tests/`, the layout of `archive/round_files_v1`), in the same commit as the job's merge. Every
   archive set is import-closed. After the move, no module left in `apps/` imports an archived module, at load or
   inside a function. The fixed check is `closed.py` over the import graph (0 open importers for the whole set, see
   below). Routes, Celery tasks and dispatch branches that serve only archived code are cut in the same commit.
5. **Nothing is archived unless it has a card and no live page needs it.** If a page the owner can open today needs
   a row at request time, that row stays where it is. Those rows are listed below as the one open exception, for the
   owner to decide. Pages this rule covers: Home, Designs, a design's page, Library, Find, Status, the old task API
   and its Celery tasks, the Round 1 balm page and the Round 1B/1C master pages. The day pages (row 56) are a map row
   and are archived.
6. **After every commit:** the fast tests (below, under ten minutes) pass. Every module in `apps/` imports cleanly.
   The closure check finds 0 open importers. Pytest runs one process at a time.

## One row per job

The owner's fourteen jobs, plus the round's runner. The runner is not on his list, but every ideas step needs it, so
it is shown.

| Job (chain step) | Target engine | Parts that move in (from) | Archived with this job |
|---|---|---|---|
| **Die solving** (the stand's die, before any design) | **6** counter_tray_header 1.0 (`counter_display.py`) | 5's product grid: `solve_product_tray`, `_product_row_parts`, `product_tray_sightlines` with `_product_plate_hit`/`_product_first_hit`, `product_tray_platform_fronts`, `product_tray_enclosure_elevations`, `product_tray_raise_rear`, `Part`, `Die`, `_rect`, `_seg`, `_r`, the sheet constants and `TEMPLATE_ID`/`TOL_MM`. 34's adapter: `solve_stand`, `build_stand`, `stand_layout`, `observed_row_placement`, `_panel_ratio`, `_number`. 7's `safe_areas`. In the registry, 1.0 becomes `current` | 5's rest (the Day 12 family display, its sway/frame checks, ray-cast scene, reference-die mapping) with its tests. Each of the 9 failing stand-adapter tests is disposed of by name |
| **Die writing** | **8** stand die files 1.0 (`counter_display_files.py`) | 7's `apply_layers`. 9's layer writer `pdf_layers` (`begin`, `end`, `spot`, `apply`, `layers_of`, `LAYERS`); its other importers are repointed | 7's rest (0.1 SVG/PDF/tiles/plan sheets), with `print_pack` and `golden_hour_fixes`, which used only those |
| **Cartons** | **1** the dieline engine (`calculate_dieline`, with 2's registry, 3's trade tuck 1.4 and 4's `fold_check`/`qualify` as its own files) | 10's `export_folded_diagnostic`, which qualification renders | 3's ECMA STE 0.1, opposed tuck 0.1 and Skynte side-seam 1.0, with their qualification adapters, if their closure holds (they refuse or fail the fold on every product of the goal: card 3). 10's rest (folded mockup, design preview, provisional preview) and the dead command `correct_dieline_output` |
| **Stand** (each stand face cut from the flat painting) | **30** face builder (`round_files_faces.py`) | 39's `turn`, `face_mm_size`, `upright_polygon`, `K` | the whole Ẓilāl cluster in one commit, because its modules import one another: 39's rest, 40, 41, 42, 43, 44, with 48's `collection_board` and `palette_board`, which used only them |
| **Painting on the die** | **30** | 45's `srgb_to_lab`, `delta_e00` (the fold's colour check) | 47, with `orn_b2`, which used only 47. 47's OCR helpers (`ocr_words`, `_near`, `OCRFailed`) move to `ire.lettering`, their one live user |
| **Live type** (placed from each face's own geometry) | **30** | 31 dial type (all), 33 ornament lettering (all), 32 picture reading (all) | — |
| **Writer** (`.ai`, live type set in the pinned fonts) | **35** writer (`round_files_export.py`) | 38's `glyph_metrics`, `shaped`, `FONT_PATHS`, `rgb`, `set_layers`, `raster` | — |
| **Logo** | **35** (`LOGO`, `LOGO_SHA256`; placed by `export_object`, positioned by 30's `marks`) | nothing: the logo already lives here (rows 35 and 50 are one module). No commit | the logo placers of 39 and 47 go with their rows |
| **Face gate** (Accept / Redraw, Make my files) | **29** owner gate (`round_files_gate.py`) | 27 files outbox (all), 28 files job (all), 37's `digest` | — |
| **Paid calls** (one boundary, one cap) | **16** paid boundary (`round_calls.py` + `spend_reservation.py`) | 15 ideas image calls (all: `IdeasContext`, the estimates), 25 image guard (all), 38's `parse_response_text`, the old pipeline's `download_image_bytes` (its importers repointed) | — |
| **Research** | **11** round designer (`round_designer.py`) | 21's `TavilySearchConnector` (`search`, `normalize`); 24's `index_row` | — |
| **Boards** | **11** | 13's `COPY_START`, `COPY_END`, `_line`, `_validation`, `read`; 14 brief contract (all) | 13's rest (the twenty-design flow), 18 |
| **Designs** | **11** | nothing more (its paid call moves with paid calls) | 55 and 56: the day services and day pages (old picks), with their four routes. 26 creativity check |
| **Product drawing** | **46** `product_drawing.py` | 45's `REPO`, `rel` | — |
| **The round's runner** (not on the owner's list) | **12** `round_flow.py` | 13's `record_break` | 17's `round_steps`, `round_sheet`, `round_report`, with their dispatch branches in `run_step_job`, and the dead form `product_round_forms`. Round 2 is complete and nothing restarts it. `round_product` stays: see the open exception |

## Every engine's end state

T = TARGET, D = DONOR (its kept parts move into the target named), A = ARCHIVED, H = held by a live page (the open
exception). For an H row, the part a target needs still moves.

| # | Engine | State | Where it goes |
|---|---|---|---|
| 1 | Dieline engine core | T | cartons |
| 2 | Template registry | D | its file is engine 1's; 1.0 made current (die solving) |
| 3 | Carton templates | D | trade tuck 1.4 stays engine 1's; ECMA, opposed and side-seam archived |
| 4 | Dieline qualification | D | `fold_check`, `qualify` stay engine 1's; the archived archetypes' adapters archived |
| 5 | counter_tray_header 0.1 | D | product grid → 6; the rest archived |
| 6 | counter_tray_header 1.0 | T | die solving |
| 7 | Stand die sheets 0.1 | D | `apply_layers` → 8, `safe_areas` → 6; the rest archived |
| 8 | Stand die files 1.0 | T | die writing |
| 9 | Carton exporters | H | `pdf_layers` → 8; the rest held (the old pipeline's container target, the dielines job API) |
| 10 | Die previews and mockups | D | `export_folded_diagnostic` → 1; the rest archived |
| 11 | Round designer | T | research, boards, designs |
| 12 | Round state machine | T | the round's runner |
| 13 | Twenty-design flow | D | helpers → 11 and 12; the rest archived |
| 14 | Brief contract | D | → 11 |
| 15 | Ideas image calls | D | → 16 |
| 16 | Paid boundary | T | paid calls |
| 17 | Whole-object round | A | archived, except `round_product` (held by 37) |
| 18 | Round 1 jury | A | boards commit |
| 19 | Jury J1/J2 | H | held: `lid_master` (45) imports it |
| 20 | Designer's eye (pitch) | H | held: the old pipeline (aria, the container target, pipeline.views) |
| 21 | Research: Tavily | D/H | connector → 11; the session and fetch code held by the trend board |
| 22 | Web research gateway | H | held: the trend board, visual review, pipeline.views |
| 23 | Trend board | H | held: the old pipeline's agents and autopilot (Home board) |
| 24 | Library retrieval | D/H | `index_row` → 11; the rest held by the Library page |
| 25 | Image guard | D | → 16 |
| 26 | Creativity check | A | designs commit |
| 27 | Files outbox | D | → 29 |
| 28 | Files job | D | → 29 |
| 29 | Owner gate | T | face gate |
| 30 | Face builder | T | stand, painting on the die, live type |
| 31 | Dial type | D | → 30 |
| 32 | Picture reading | D | → 30 |
| 33 | Ornament lettering | D | → 30 |
| 34 | Stand adapter | D | → 6 |
| 35 | Writer | T | writer, logo |
| 36 | Retired tracing build | A | already in archive/round_files_v1 |
| 37 | Preservation master | D/H | `digest` → 29; the rest held by the round page's master links |
| 38 | Balm round | D/H | type helpers → 35, `parse_response_text` → 16; the rest held by the Round 1 pages and 37 |
| 39 | zilal_tray | D | four helpers → 30; the rest archived |
| 40 | zilal_display | A | stand commit |
| 41 | zilal_header | A | stand commit |
| 42 | Ẓilāl lid master | A | stand commit (the Ẓilāl cluster) |
| 43 | Ẓilāl object, sticker, box, cartons | A | stand commit (the Ẓilāl cluster) |
| 44 | Ẓilāl lipstick and balm | A | stand commit (the Ẓilāl cluster) |
| 45 | Lid master | D/H | colour maths → 30, `REPO`/`rel` → 46; the rest held (48, 37, 38 and palette_open import it) |
| 46 | Product drawing | T | product drawing |
| 47 | Day 8/9 lid builds | A | painting commit |
| 48 | Palette cartons and stickers | H | `collection_board`, `palette_board` archived; `palette_box`, `palette_sticker`, `stick_carton` held (38, 37, 17) |
| 49 | Live type and fonts | H | held: the type book. The writer still reads the GRANTED census through `font_pool.files_of`/`is_excluded` |
| 50 | Approved logo placement | T | the same module as 35 |
| 51 | Tracers | H | held: the old pipeline's targets |
| 52 | Finish proof | H | held: `lid_master` imports it |
| 53 | IRE composer and emitters | H | held: the old pipeline. The writer still runs Illustrator through `illustrator_exec.run_jsx` |
| 54 | Native handoff and print pack | D/H | `print_pack`, `golden_hour_fixes` archived; `native_handoff` held by pipeline.views |
| 55 | day5_* … day14_* | A | designs commit, except `day6_critic` (held by 19) |
| 56 | day*_views | A | designs commit, with its four routes |
| 57 | Palette engine (M-series) | H | held: the ES3083 confirmation view and the old palette target |

## The open exception (for the owner)

The site's shell (every page's top bar, `context_processors` → `dashboard.board`) imports
`pipeline.targets.container` and `pipeline.autopilot` at request time. Those load the old agent pipeline (the ARIA
agents, its targets, pipeline.views), and that pipeline loads rows 9, 20, 22, 23, 51, 53 and 57. The Round 1 balm page,
the Round 1B/1C master pages and that pipeline hold 17, 19, 37, 38, 45, 48, 49, 52 and 54 (in part). Archiving them
would change or break Home, Designs, a design's page, Library, Find and Status. The owner did not ask for that, so
this plan leaves them in place and lists them:

- **Held rows: 17.** Rows 9, 19, 20, 22, 23, 37, 38, 45, 48, 49, 51, 52, 53, 54 and 57 in full, and the rests of 21
  and 24 (1,200–33,400 lines each; the cards give each one's size).
- **What would free them:** the owner's word to retire the old design pipeline's pages. That means Home's board of
  old designs, Designs, a design's page, the classic start page (already unlinked), the old task API, the Round 1
  balm page and the Round 1B/1C master pages. They would move to archive/ with the rows they hold, leaving the ten
  targets.
- **What the chain still calls in held code after the merge.** Every part a target uses from a held row moves into
  it, except these five. Each stays where it is because live old code uses the same function:
  - the writer's `font_pool.files_of`/`is_excluded` (49: the GRANTED census, also read by the type book);
  - the writer's `illustrator_exec.run_jsx` (53: Illustrator's save and reopen, also used by the old emitters);
  - the designer's `library_matches` through `dashboard.materials_library`, which reads row 24's index helpers
    (`index_items`, `facts`, `_hex_lab`; the Library page reads them too);
  - the Tavily connector's `web_research.WebPolicyError` (22: the trend board and visual review raise it too);
  - the round page's master views in `product_round_views`, which call `round_master_flow` (37). That is the held
    Round 1B/1C page, which shares its module with the chain's round page.

## Expected count and lines

- **Engines: 57 → 27 standing.** That is 10 targets plus 17 held rows, and 30 rows end as engines (13 merged in full,
  17 archived). With the owner's word on the open exception: **10**.
- **Archived (the import-closed set):** 79 modules, **37,451 lines** under apps/, plus the three provisional
  archetypes and their adapters (about 2,050 lines) if their closure holds, plus the tests that move with them.
- **Merged:** about 4,600 lines move from 22 donor files into 10 targets. Moving them adds no lines. The donor files
  that empty out are removed by the move (`git mv` of the archived rest, or deleted as empty only once every part has
  left).

## Order of the commits and the checks

One commit per job, in this order, so that each archive set is closed against what stays (amended before any move,
after the advisor's check of the first order):

1. stand (the Ẓilāl cluster with it)
2. live type
3. designs (the day pages, before row 47 goes, because day8_pick imports it)
4. painting on the die
5. die writing (before die solving, because the 0.1 sheets import 0.1)
6. die solving
7. cartons
8. writer
9. face gate
10. paid calls
11. research
12. the round's runner (its twenty-design branch cut before boards archives that flow)
13. boards
14. product drawing

Logo needs no commit.

- **Fast tests (about 4 minutes).** The flow's test files: round flow, round calls, round files faces, export and page,
  product round page and media, counter display, counter tray header, registry and registry agreement. The baseline
  is 488 passed, 6 skipped, and 9 failed, all of them the 0.1 stand-adapter tests. Add the test files of every module
  the commit touches, `test_round_balm.py`, `test_palette_statistics.py`, the Tavily and day-7 library tests, and
  the dielines app's tests.
- **The import check.** Every module under `apps/` is imported; none may fail.
- **The closure check** (`dangling.py`, baseline `engines/runs/dangling-baseline.json`). No import under `apps/`
  (tests included) and no `patch('apps.…')` path may name a module or name that no longer exists, beyond the
  baseline's 82, which are older patch strings of nested attributes. `import_check.py` imports every module; its
  baseline is 12 failing modules, all Blender scripts needing `bpy`.
- **The before/after run.** `chain_run.py` ran round 3 end to end at $0 before any move
  (`engines/runs/chain-before.json`). The same run after the last commit must give the same die, template, proof and
  read-back.
- **At the end.** Round 3 runs end to end at $0 on a copy in the scratchpad, never the round's own folder: the die
  drawn, the template sheet, the faces placed, and Make my files writing the .ai, DXF, CF2, 1:1 PDF and previews.
  ENGINE_MAP.md is rewritten as the new list.

## As carried out (2026-10-28)

The fourteen jobs went in thirteen commits, `8a57d46` … `3984081`; logo needed none. These are the places the work
departed from the plan above, each for the reason given in its commit:

- **Held, not archived (rule 5, found while archiving):**
  - Rows 13, 17 and 18. Round 2 (a twenty-design ideas round) and r2-gloss (a whole-object round) are on the live
    Rounds page, through round_flow's branches for them.
  - Row 3's ECMA STE 0.1, opposed tuck 0.1 and Skynte 1.0. The old carton choosers (template_selection, gift_set)
    offer the registry's templates.
  - day5_master, day6_critic, day5_views and day6_views. The Day 4–6 stand and serum master pages link
    stand-master/ and serum-master/.
- **Not moved:**
  - Row 24's `index_row`. Its closure is the whole card index the Library page reads.
  - Row 37's `digest`. The files job had the same function, byte for byte.
- **Moved elsewhere or earlier than planned:**
  - Row 47 was archived with the day services (designs), because the two rows import each other.
  - `safe_areas` moved with die writing, because the sheets left in that commit.
  - The stand adapter's `build_stand` went to the gate, not the die solver: the dielines app does not import the
    pipeline.
- **The registry:** counter_tray_header 1.0 stays pinned-only. If it were current, the carton choosers would offer it.
  `resolve` resolves a pinned-only template by its number, and an unpinned resolve fails closed.
- **The count:** 57 → 30 standing (10 targets, 20 held), not the 27 expected, because of the four held groups above.
- **The checks:** after every commit, the closure check was at its baseline of 82, the import check at its 12, the chain
  run on round 3 the same as on 26db887, and the fast tests failing only their pre-existing tests. Those were the 5
  palette guard tests, plus the 9 0.1 stand-adapter tests until die solving disposed of them by name.

## Owed to the owner: four repo checks that name archived files (2026-10-29)

The full suite ran once after the last job (10,473 passed, 19 failed, 1 h 50 min). It ran while the paid calls' part 2
was being written, so three of its failures (the master path in test_round_flow and test_product_round_media) were the
suite reading a half-edited `round_calls`; after `7be1f95` they pass. Of the other sixteen, eight fail the same way on
26db887 (five in test_palette_statistics, three in test_av2_brand_strings), one is the brain's index being older than
the last commits (the rebuild closes it), and the rest are three checks the archive made red. A fourth check, outside
pytest, also names archived files. Each of the four is a repo record the owner has always re-pinned by his own word:
§BH69 on 2026-09-26 ("Yes, 813 to 804"), and the module moves on 2026-10-28 ("Re-pin the two repo checks owed from the
module moves"). None of them was edited here.

| Check | What names archived files | Red now | What a yes would change |
|---|---|---|---|
| The fallback register, `gate_baseline.json` | 105 keys and their 105 registrations, in 18 archived files: 16 day modules, round_files_job (4 keys already stale before the moves) and round_files_stand (4, its code now in apps/dielines, outside the scan) | test_gate_baseline_registration: `test_every_file_a_register_names_resolves_to_exactly_one_file` | the 105 keys and registrations moved, whole, into an archive record; `n` 1,251 → 1,146; `n_pre_registration` stays 804 (all 105 are later keys) |
| The unit register, `test_wit_unit_analysis.py` | `("day6_surface_fidelity.py", 482)`: its file went with the day modules | `test_how_much_of_the_register_rests_on_the_coefficient_assumption` (3 certain, not 4) | the key out with a dated note; `CERTAIN_FINDINGS` 4 → 3; the false-positive set loses day6_surface_fidelity.py |
| The exemption list, `font_roles.EXEMPT_SURFACES` (§BH32(h), LIVE) | `design_preview.py::export_design_preview_ai`: archived with the die previews (`16ddcf2`); nothing stamps its tag now | test_pdf_ai_emitter: `test_the_exemption_list_is_path_literal_and_names_entry_points_not_test_files` | the entry out in its three places: font_roles (7 → 6), the §BH48 test's `stayed` set, brand_library's `EXEMPT_WORDS` |
| The declared test list, `suite_file_manifest.json` | 20 archived test files (on 26db887 it matched the disk) | no pytest test; `tools/tier2_gate.py`'s manifest check would refuse | the list regenerated by the tool; a third approved removal in test_characterization_protocol's diff-log test; `EXTENT_DIGESTS`, the protocol identity and `record_digest_manifest` re-pinned, as in `6ef7218` |

Red on 26db887 already, and left so:
- The unit register's other tests. The ornament's MIXED finding was never classified; it moved with its code from
  round_files_ornament.py:94 to round_files_faces.py:1069. Its denominator test passes now only because the archived
  finding and that one cancel (8 = 8).
- The fallback occurrence test: 87 on 26db887, 90 now. 23 occurrences moved with their code, `stand_layout`'s left the
  scan with the stand adapter, and `download_image_bytes`' 4 are newly scanned in round_calls. None was registered
  here (§R4(b)).

The register was re-keyed 29 times. Each key's code moved unchanged into its target: the same symbol and shape, with
a `rekeyed` record on its registration. `n` is still 1,251. Any one of them can be vetoed.

**The question:** should the four checks be re-pinned for the archived files, as in the last column? One line closes it.

## 2026-10-29 — the history pages retired

The owner's goal of 2026-10-29 (`be9eba9`), §0: "Retire the history pages (Round 1/1B/1C/2, Day 4–6 masters) to
archive/ … archive any held engine nothing live needs." Four commits; everything went to
archive/consolidation/retire/ by `git mv`, or verbatim into its `merged/` files (nothing deleted). apps/, templates
and tools: +274 / −34,956 lines; 45 service modules, 2 ire modules, 8 view modules, 11 templates, 1 tool and 22 test
files moved, plus 28 new archive files (the verbatim parts and whole copies of the split tests).

| Commit | What retired |
|---|---|
| `a634230` the round kinds | `round_flow` keeps the designer flow alone. The twenty-design kind (Round 2) and the whole-object kind (Rounds 1/2: the r2-gloss repair, the marks and their deadline) leave it verbatim. The kinds' engines go too: round_ideas, round_steps, round_sheet, round_report, round_jury_completion, product_round_forms. A retired round still in the database answers in words on the list and its page, with no action and no file (`product_round_retired.html`, its test). |
| `32f27f3` the pages | 25 routes: round-1-balm/, rounds/<pk>/master/, stand-master/, serum-master/, day5/, day6/, fidelity/. Out with them: their 7 views and 9 templates, tools/round_balm.py, the master engines (round_master_flow, round_master_art, round_master_files), round_calls' MasterContext and master_scoped_spend, and the run_round_master task. The authored-master boundary answers "retired" (410) instead of redirecting into a retired route. |
| `ba16e80` the freed engines | rows 17, 18, 19, 38 (14 modules), 45, 48, 52 and 55 whole, row 49's lettering and arabic_display, row 51's traced_text, and what only they used (palette_open, whole_object_check, hayat_master_page, balm_leaflet, fidelity_checks, fidelity_native, display_concepts, production_finishes, orn_b1, orn_c1, two Day 5 Blender scripts) |
| `b1e3c4a` the check | `ArchiveIsNeverImportedTests` (test_two_roots_collision_guard): 621 modules imported, 0 loaded from archive/, with a negative control |

**What stays held, by root** (function-level graph, c/heldfree.py):
- `targets.composite::complete_product_preflight`, the restart script's own preflight: rows 3, 9 (but production_pdf
  and export_service), 20, 21, 22, 24 (captions, previews), 51 (line_art, flat_motif) and 53.
- The old task API (`pipeline.views`): 23 (TrendPickView), 24 (materials_retrieval, ConceptReferenceCandidatesView)
  and 54 (GenerateHandoffView).
- `dielines.api.views::QualifyDimensionsView`: 9's production_pdf and export_service.
- `dashboard.views::palette_intent_confirmation`: 13 of row 57's palette modules.
- `round_files_views::make_files`, the chain itself: 49's font_pool.
- Row 57's other 76 palette modules nothing live reaches. They stay because the M6 guard chain names them:
  `tools/allowlist_census.MEASUREMENT_MODULES` (11), `palette_powder_protocol` (palette_material_swatch.py) and the
  palt_m6 records. Archiving them needs the allowlist register re-pinned too.

Not changed here (the owed re-pins, for the end of §0): the fallback register still keys the archived files, and the
unit register, the exemption list and the declared test list are as they were. The import check's baseline is now
10 Blender scripts, not 12.

## 2026-10-29 — Home, Designs and Library on the rounds

The owner's goal of 2026-10-29, §0: "Keep Home, Designs and Library, switched to the chain engines" (`8e84af3`). One
classification of a round, `dashboard.views.round_card`, reads the round's own record and its files build's. It
gives where the round stands, what happens next in words, the one place to go and the picked design's picture.

| Page | Now reads | No longer reaches (function graph) |
|---|---|---|
| Home (`views.index`) | the rounds: Needs attention, four lanes of the designer flow, retired rounds folded | `board.classify` over the old tasks, and with it `autopilot`, `pipeline.views`, `targets.container`, `agents.aria`, `trend_board`, `designers_eye`, `ire.compose`, `pdf_ai` (263 → 19 modules) |
| The top bar's round pills (`context_processors.round_activity`) | the same `round_card`, so the bar and Home agree | — (its old-task pills and bell still read `board`) |
| Designs (`history_views.history_index`) | the designer rounds, by month; words over the brief, state, dates, order, mine | the old task list and its classification (265 → 40) |
| Library (`views.library`, `finished_designs`) | finished designs = rounds whose files are made | `library_views`, `board.title_of`, `targets.container`, and through the products split `autopilot` (265 → 43; products 263 → 15) |

Filters dropped with the old tasks: kind, product, brand, record state, renders, rejections, the test fold (Designs);
brand and category (finished designs). The old tasks and outputs keep their own pages, unlisted
(`/history/tasks/<id>/`, `/designs/<id>/`, `/library/finished/<id>/`).

Held rows 20, 23, 24, 53 and 57 are unchanged by this: their roots are the restart preflight, the old task API and
the palette confirmation page, not these pages. The replaced code is in `archive/consolidation/rounds-pages/`.

## 2026-10-29 — the carton dies on the one writer (`daa57b6`)

The owner's §0: "switch them to the one die writer (counter_display_files) and archive row 9."

- **Moved into `counter_display_files`, as its own functions:**
  - production_pdf, whole: `write_carton_pdf` (the CMYK production sheet: CutContour and Crease on the writer's own
    spot plates, /All registration marks, dimension callouts, title block, legend, TrimBox/BleedBox, the output
    intent), its drawing helpers, and the font resolvers `_resolve_fonts`, `_resolve_arabic_font`,
    `_resolve_arabic_bold_font`, `_register_ttf`, `_repo_font`;
  - svg_exporter: `write_carton_svg`, `write_svg`;
  - ai_exporter: `carton_ai_from_pdf`, `carton_ai_from_svg`;
  - the bridge `carton_lines` (a carton's coordinates as the writer's layers). The stand's DXF and CF2 encoders
    (`_write_dxf`, `_write_cf2`, the stand's bytes unchanged) write the carton's: `write_carton_dxf`,
    `write_carton_cf2`.
- **Repointed:** export_service (now also writes the carton's DXF and CF2), qualification/runner,
  structural_comparison, info_panel, label_layout, ire compose, compose_container, container_font_authority,
  font_roles, and 15 test files.
- **Archived:** production_pdf, svg_exporter, ai_exporter → archive/consolidation/cartons/merged/.
- **Stays held:** artwork_layers and label_layout (the IRE uses them; neither writes a die), and export_service (the
  old ARIA path calls it; it writes through the one writer now).

**Before and after, three cartons** (reverse tuck end 1.4 at 22 × 22 × 105, straight tuck end 1.4 at the same size,
straight tuck end at 28 × 28 × 120). Script: docs/consolidation/quality/carton_measure.py; runs in
quality/runs/carton-before and carton-after.

| | Before (production_pdf + svg_exporter + ai_exporter) | After (counter_display_files) |
|---|---|---|
| PDF cut and crease read-back, both ways | 0.0 mm | 0.0 mm |
| TrimBox / BleedBox against the cut / bleed | 0.0 / 0.0 mm | 0.0 / 0.0 mm |
| CutContour, Crease and All plates | present | present |
| Fonts | Noto embedded, plus an unembedded Helvetica declared | Noto embedded, nothing else |
| DXF | none | 544–600 entities, read back within 0.0001 mm |
| CF2 | none | 185–190 lines, read back within 0.0007 mm (3 decimals) |
| .ai | a copy of the PDF | a copy of the PDF |

## 2026-10-29 — the owed checks re-pinned and the old reds fixed

On the owner's message of 2026-10-29 ("Re-pin the four checks per PLAN.md. Fix your three checks that name archived
files." and "Fix the 5 fast tests that already failed before the merge … The fast set ends fully green."), one commit each:

| Check | Before | After | Commit |
|---|---|---|---|
| The fallback register (gate_baseline.json) | 1,251 keys, 447 registrations; 257 keys in 49 archived files did not resolve | 257 keys with their registrations moved whole to archive/consolidation/registers/gate_baseline_archived.json; n 994, then 1,083 with the 89 below; n_pre_registration 804 unchanged | `99b3707` |
| The §BH32(h) exemption list | 7 entries, one naming archived design_preview, two naming archived production_pdf | 6: the previews' entry out, the resolvers re-pathed to counter_display_files (its three places) | `6810bcb` |
| The unit register | 4 tests red: the ornament line never classified, the archived Day 6 finding | Day 6's key out; round_files_faces' band-size line classified FALSE_POSITIVE_COEFFICIENT (pt per mm read as a coefficient, the assumption's declared cost); 8 findings, 3 certain, 1,668 checks ≥ floor 1,512 | `6df45df` |
| Brand strings | 3 red: UNKNOWN_BRAND_KIND 'TextType.POINTTEXT' | ruled out by name in NOT_OURS (Illustrator's native text-frame type, owned by the writer's read-back); BRAND_STRINGS_OK | `a73ad5d` |
| The fallback count | 90 unregistered occurrences; palette guard 5 red | 2 fixed at the source (provider_check, reading_notes), 89 registered one by one; 1q allowlist: 2 reviewed dispositions; 0 unregistered | `6b52b9d` |
| The declared test list and its chain | 447 files, 42 archived among them | 405; diff-log entry 2026-10-28T20:47:11.922378Z as his third approved removal; records regenerated (+0 −0 ~5); both digests rebound; protocol_identity 3d52199c98f359ce (equal to its preview) | `c2d1e41` |

The list of fallback judgments: [fallback-judgments-1029.md](fallback-judgments-1029.md).

Measured after the last commit: the nine guard files (test_palette_statistics, test_gate_baseline_registration,
test_wit_unit_analysis, test_av2_brand_strings, test_pdf_ai_emitter, test_characterization_protocol,
test_two_roots_collision_guard, test_wig_source_string_guards, apps/core/tests.py) 566 passed, 0 failed; the fast set
923 passed, 0 failed; the round 3 chain SAME on all seven parts; dangling 82; imports 10 (Blender); record integrity OK;
the brain rebuilt.

Left for the owner: the tier-2 gate's total floor is 10,949 and 9,890 tests are now collected (the archived tests'
share). The tool never lowers a floor, so that clause of tools/tier2_gate.py refuses until he rules it.

## 2026-10-29 — round 3's faces at 300 ppi, the product nets, the flat hand-off

The owner's goal of 2026-10-29, §3 and §1. Four pieces, all at $0 (fixtures and stand-ins; no paid call):

- **Each stand face at 300 ppi** (`d4981e0`). The whole-die painting is the idea (one edit of the die: 2.35 px/mm,
  59.8 ppi on round 3). With a claim whose policy says `panels: full`, each stand face is then drawn again on its own
  outline: one edit on a sheet at 300 ppi (both sides ×16, aspect 1:3–3:1, 0.65–3.69 MP), with image 2 its crop of the
  whole-die painting. Each is checked against that crop: a 16 × 16 grid of mean colours, CIEDE2000, median and p90
  against the bar 10 / 20. A face over the bar is flagged for the owner, never passed or redrawn. Every edit is recorded
  on the claim before it is sent, and refused in words if its hold would pass the claim's cap. The hold scales with
  the canvas's pixels.
- **Make my files at 300 ppi** (`d4981e0`). The stand's raster is composed at 11.81 px/mm. A panel drawing is turned
  onto the die by whole quarter turns and scaled once. Each placement records its native and composed ppi.
- **The bottle and cap die-first** (`60472d6`). Each product's printed sides are laid out flat as a counter_display
  part (the bottle's four body sides; the cap's four sides and its top). The part is painted with one edit, the die is
  applied again, the front is cut for the files and the real sides go into the wrap view. A policy chooses it with
  `product_nets: true`.
- **The flat hand-off** (`15cbaac`), the chain's one break. A flat pick starts its files.
  - Its reading is $0: its own die's faces are the panels, and no words are read.
  - Its die, solved again, must be the die it was painted on.
  - Its painting is installed as picked, at $0, and the faces are drawn per panel and on nets.
  - A flat pick's faces carry no live type yet; that is said on its reading.

Round 3, measured at $0 (`docs/consolidation/quality/runs/faces-1029.json`):

| Face | Frame with bleed (mm) | Before | After (canvas) | Hold |
|---|---|---|---|---|
| header | 113 × 84.25 | 59.8 ppi | 300 ppi (1408 × 1072) | $0.35 |
| header back | 113 × 85.75 | 59.8 | 300 (1408 × 1088) | $0.35 |
| front strip | 113 × 24.2 | 59.8 | 300 (1408 × 480) | $0.35 |
| right / left side | 88 × 149.78 | 59.8 | 300 (1104 × 1840) | $0.452 each |
| back | 113 × 149.78 | 59.8 | 300 (1408 × 1840) | $0.5765 |
| bottle net | 66 × 76 | — | 375.6 (1024 × 1536) | $0.35 |
| cap net | 66 × 51 | — | 486.1 (1536 × 1024) | $0.35 |

The composed stand is 300 ppi (4901 × 4904 px). The holds for one whole-die painting, six panels and two nets total
$3.58, against the owner's $3 cap for this goal's paintings. Holds are reserved one call at a time and settle at the
provider's usage (round 3's high edits settled at about $0.18–0.21 on 1536 × 1024). A late call whose hold no longer
fits the cap is refused in words.

## 2026-10-29 — round 3's first real run, and the painting's proof as a gate

Attempt 3 ran on round 3 (the die solved again inside the owner's ruled size; one whole-die painting; six panels at
300 ppi; the two nets): $1.76 of its $3 claim. The painting stretched the die non-uniformly (the back ×1.48, the header
×1.3, the floor ×0.91); its proof measured it (registration IoU 0.53; coverage left side 0.26, right side 0.31; the
front strip left in the template's grey) and nothing acted on it. The panels for the front strip and both side walls
followed crops the painting never filled; the back passed its ΔE check but came back with an invented gauge on a face
the owner calls plain. The header, the header back and both nets are right.

- `261d9ce`: a crop is followed only where the painting kept the face (coverage ≥ 0.9, at most half left unpainted);
  else the picked picture's own view of the face, else for a face the policy names plain a swatch of the stand's
  board; else refused in words. Plain faces checked (≤ 2 % over ΔE00 15 from their own colour). One system redraw per
  flagged panel, under the claim's cap, never a second.
- `38c6e4c`: the proof sheet at real size and the views from the current panels, made at $0 when the faces settle.

Measured on a copy (quality/runs/round3-attempt3.json): reliable crops header, header back, back; not front (100 %
unpainted), left (0.26), right (0.31). With `plain_faces: [side, left, back, header_back]` in round 3's policy (not
yet there: the policy is the owner's record), the next run redraws five faces once each — back (from its crop, plain:
4.7 % off its colour), left and right (from the board swatch, the middle of the header back's drawing), front (from the
picked picture's stand_base view), header back (2.6 %: the header's dial crossed the fold onto it) — holds $0.58, $0.45,
$0.45, $0.35, $0.35, each reserved against the $3 when it is sent.
Round 3's committed die is now the one solved inside the ruled size (by the run's restand), so the chain run against
chain-before.json differs in the die, its proof, its files and the stand's .ai: its baseline is owed a renewal.

## 2026-10-29 — the chain's dead ends (§1)

Found by the function graph from every live page, task, command and tool (tests excluded), each confirmed by search:
- **Moved to archive/consolidation/dead/, verbatim** (nothing live or in the tests called them): round_files_faces'
  `_face_for`, `drawing_findings`, `type_rows_of`, `upright_picture`, `write`, `zone_mask`; product_drawing's
  `write_record`.
- **Reached only by their tests, kept as instruments:** counter_display's `qualify`, `compare`, `strength_check`,
  `trade_rules`, `template_definition` and the `_overlap` and `_parallel` they call (the qualification matrix that proves
  the die), counter_display_files' `layers_of` (the layer read-back).
- **Reached only by tests of retired behaviour, not yet moved** (their test functions must be split out with them):
  round_designer's `printed_copy` (three page and flow tests assert it), round_calls' Day 8–12 image log (`audit`,
  `guarded_call`, `log_call`, `_is_approved_logo`; test_day8_concepts, test_day9_builds, test_day10_master,
  test_day12_pages), round_files_export's `fit_type_envelope` (its envelope tests).
Two first tries were wrong and put back before the commit: `_overlap`/`_parallel` (the matrix calls them) and
`fit_type_envelope` (tested); the fast set then 964 passed, 0 failed.
