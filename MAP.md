# MAP — where everything is

Written on 2026-10-05, at the end of the clean-up you asked for on 2026-10-04 (the register, `4414b0f`). One page:
what each folder holds, where the things you look for live, what the code names mean, how to start and test the site,
and where every moved or renamed item went.

## The top level (`~/Desktop/bbrose-systemOS/`)

| Folder or file | What it holds |
|---|---|
| `bbrose_design_os/` | The site itself: the Django app, its tests, its docs, its tools, its logs. Everything you run is in here. |
| `docs/` | `audit/` holds rescue daily reports, immutable samples and local ignored runtime evidence; `brand/` holds the house-reference drop. `design_intelligence/` holds the design-intelligence records (tiers, captions, sittings, the DIP manifests). It stays here because checksum-pinned records name its path (on `AFTER_THE_TEST_DAY.md`, with the safe way to merge it). |
| `var/` | Generated data: the brain's index (`var/brain/`), the design-intelligence audits (`var/design_intelligence/`), and the M6 render frames (`var/m6/`, kept as they were). Git-ignored. |
| `materials/` | Your design stock and fonts, read-only to the site. Git-ignored. |
| `archive/` | History moved out of the way, never deleted: the executor's 58 work folders (`archive/work/`, named by what they hold — `archive/work/INDEX.md`), four Desktop items (`archive/desktop/`), old var output (`archive/var/`), and this clean-up's own working folders (`archive/cleanup/`). `archive/MANIFEST.tsv` lists every move. Git-ignored. |
| `brain_vault/` | The brain's generated notes (it was `vault/`). Rebuilt by the brain; git-ignored. |
| `OWNER_BLOCKER_CLEARANCE.md` | **The register** — your rulings and the executor's records, append-only. |
| `OWNER_REVIEW_QUEUE.md` | **The review queue.** |
| `CLAUDE.md` | The executor's standing instructions (the brain's three lines). |
| `README.md`, `AUDIT_REPORT.md` | The project readme and the July audit. |
| `MAP.md` | This page. |

The REMOVE folder is **outside** the project: `~/BBROSE_REMOVED_2026-10-04/`. Everything the clean-up removed is there,
moved, never deleted, with `MANIFEST.tsv` listing every move. It is yours to delete.

## The app folder (`bbrose_design_os/`)

| Folder | What it holds |
|---|---|
| `apps/` | The code (see the glossary below for each app's name). |
| `config/` | Settings, URLs, Celery. |
| `templates/`, `static/` | The pages, their scripts and styles. |
| `docs/` | The app's records: `roadmap/` (incl. `AFTER_THE_TEST_DAY.md`, `bh55/ACCEPTANCE_TIME_LIST.md`, `palt_m6/` — the gate's records), `brand/`, `brand_gov/`, `production_authority/` and `production_authority_intake/` (gates A–E and the spec pack), `complete_product/`, `product_container/`, `qualification/`, `visual_quality/`, `security/`, `research/`, and `archive/` (old notes, launchers and the supplier records you kept, as history). |
| `tools/` | The one tools folder: the gate (`guarded_commit.sh`, `launch_gate.sh`, `tier2_gate.py` and its checks), the brain (`tools/brain/`), the three materials tools (`dip0/`, `dip0b/`, `dip0c/`), the restart scripts (`restart_site.sh`, `restart_worker.sh`). |
| `logs/` | The site's and the worker's logs (`site.log`, `worker.log`, and the older numbered ones), and the gate's seals. Git-ignored. |
| `media/` | Your designs' files (the site writes here; tests never do). |
| `exports/` | The files of designs made before 10 July, which the site still serves. Git-ignored. |
| `vendor/fonts/` | Two open-licence fonts the tests read. Git-ignored. |
| `scripts/` | `run_dev.sh`, `backup.sh`, `restore.sh`. |
| `venv/` | The Python environment. |
| `manage.py`, `requirements*.txt`, `RUNBOOK.md`, `Dockerfile`, `THIRD_PARTY_NOTICES.md` | Django's command, the packages, the runbook, the container build, the font and code licences. |

## Where things live

| You want | It is at |
|---|---|
| Your rulings, every decision | `OWNER_BLOCKER_CLEARANCE.md` (top level) |
| What waits for after your test day | `bbrose_design_os/docs/roadmap/AFTER_THE_TEST_DAY.md` |
| The instrument questions that wait for a design you are accepting | `bbrose_design_os/docs/roadmap/bh55/ACCEPTANCE_TIME_LIST.md` |
| The questions the September queue-emptying left for you | `bbrose_design_os/docs/roadmap/bh55/PHASE4_WAITS_ON_HIM.md` |
| Your designs' files | `bbrose_design_os/media/` (and the site's History page) |
| Your design-page tries (explorations) | `~/bbrose_explorations/` |
| The site's log, the worker's log | `bbrose_design_os/logs/site.log`, `bbrose_design_os/logs/worker.log` |
| Everything removed | `~/BBROSE_REMOVED_2026-10-04/` (+ `MANIFEST.tsv`) |
| Everything archived | `archive/` (+ `MANIFEST.tsv`) |

## The code's names, in plain words

| Name | What it is |
|---|---|
| `ire` | **The vector drawing engine** — it composes every design as editable vector objects (the Design Graph) and writes the `.ai` and PDF files. ("IRE" is its first name: the Illustrator Reconstruction Engine, as `apps/ire/apps.py` still calls it. Renaming it `vector_engine` is on `AFTER_THE_TEST_DAY.md`, your K1 answer.) |
| `pipeline` | The design run: the brief, ARIA, the planner, the concept pictures, Gate 1, the size and shape steps, Gate 2. |
| ARIA | The pipeline's conductor — the agent that runs a design from brief to files (`apps/pipeline/agents/aria.py`). |
| `dielines` | Cartons: the die geometry, its validators and its exports. |
| `intelligence` | The design-intelligence records (the materials tiers, captions, references). |
| `core` | Brands, products, colour systems; the launch and system checks. |
| `dashboard` | The pages you use: the board, New design, a design's page, History, Status. |
| `accounts` | Users and roles. |
| Design map | The reading of a chosen concept picture — its parts, boxes, colours and words — that the drawing is made from. |
| M3 | The accepted dropper drawing (the one engine for a bottle with a dropper cap). |
| Gate 1, Gate 2 | Choosing the concept picture; approving the finished files. |
| The gate | The commit gate: every commit runs the whole test suite (`tools/guarded_commit.sh`). |
| The brain | The executor's index of the register, queue, sittings and memory (`tools/brain/`), consulted before every proposal. |
| DIP | The design-intelligence programme (the materials tiers and the manifests that pin them). |

**By design, not half-done:** the materials-retrieval contract (`apps/ire/materials_retrieval.py`, which the brain
implements) and three abstract base methods (`targets/base.py`, `dielines/qualification/domain.py`,
`intelligence/semantic_encoder.py`) raise `NotImplementedError` on purpose — each is a contract its subclasses fill.

## Starting the site and the worker

From `bbrose_design_os/`:

- the site: `zsh tools/restart_site.sh` (Django on http://127.0.0.1:8000/, logging to `logs/site.log`);
- the worker: `zsh tools/restart_worker.sh` (Celery, logging to `logs/worker.log`; it prints whether the worker runs the
  repository's revision).

Both refuse while a test run or a gate is going.

## Running the tests and the wiring check

From `bbrose_design_os/`:

- the whole suite, as the gate runs it: `venv/bin/python tools/tier2_gate.py --check`;
- one file: `venv/bin/python -m pytest -q apps/pipeline/tests/test_<name>.py`;
- **the wiring check** — every design type from its brief to its finished file, every paid service stubbed:
  `venv/bin/python -m pytest -q apps/pipeline/tests/test_wiring_check.py` (about a minute and a half). It runs inside
  every gate.

## Old → new

Every item the clean-up moved or renamed, from its own records. Nothing was deleted: what was removed is in the REMOVE folder, what was archived is in `archive/`, and each manifest there lists every file.

### Moved inside the project

| Old | New | How |
|---|---|---|
| `bbrose_design_os/docs/production_authority/supplier_dispatch_manifest.json` | `bbrose_design_os/docs/archive/supplier/supplier_dispatch_manifest.json` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/supplier_dispatch_manifest.pdf` | `bbrose_design_os/docs/archive/supplier/supplier_dispatch_manifest.pdf` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/supplier_dispatch_manifest.png` | `bbrose_design_os/docs/archive/supplier/supplier_dispatch_manifest.png` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/dispatch_pack/email/supplier_01_liquid_bottles.eml` | `bbrose_design_os/docs/archive/supplier/supplier_emails/supplier_01_liquid_bottles.eml` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/dispatch_pack/email/supplier_02_sks_bottle.eml` | `bbrose_design_os/docs/archive/supplier/supplier_emails/supplier_02_sks_bottle.eml` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/dispatch_pack/email/supplier_03_bottlestore_oberk.eml` | `bbrose_design_os/docs/archive/supplier/supplier_emails/supplier_03_bottlestore_oberk.eml` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/dispatch_pack/email/supplier_04_premium_vials.eml` | `bbrose_design_os/docs/archive/supplier/supplier_emails/supplier_04_premium_vials.eml` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/dispatch_pack/email/supplier_05_nicer_packaging.eml` | `bbrose_design_os/docs/archive/supplier/supplier_emails/supplier_05_nicer_packaging.eml` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/supplier_evidence_request_dispatch_pack.txt` | `bbrose_design_os/docs/archive/supplier/supplier_evidence_request_dispatch_pack.txt` | his S2 answer: kept, moved in git |
| `bbrose_design_os/docs/production_authority/supplier_sent_evidence_validation.json` | `bbrose_design_os/docs/archive/supplier/supplier_sent_evidence_validation.json` | his S2 answer: kept, moved in git |
| `BBROSE_DesignOS_Milestones(1).md` | `bbrose_design_os/docs/archive/BBROSE_DesignOS_Milestones_v1.md` | moved in git |
| `BBROSE_DesignOS_Milestones_v2.md` | `bbrose_design_os/docs/archive/BBROSE_DesignOS_Milestones_v2.md` | moved in git |
| `EXECUTION_STATUS.md` | `bbrose_design_os/docs/archive/EXECUTION_STATUS.md` | moved in git |
| `OWNER_INPUT_MANIFEST.md` | `bbrose_design_os/docs/archive/OWNER_INPUT_MANIFEST.md` | moved in git |
| `PROJECT_DOCUMENTATION.md` | `bbrose_design_os/docs/archive/PROJECT_DOCUMENTATION.md` | moved in git |
| `SHADE_AUTHORITY_PROPOSAL.md` | `bbrose_design_os/docs/archive/SHADE_AUTHORITY_PROPOSAL.md` | moved in git |
| `WORK_ITEMS.md` | `bbrose_design_os/docs/archive/WORK_ITEMS.md` | moved in git |
| `ES3083_DIMENSION_FINDINGS.md` | `bbrose_design_os/docs/archive/es3083/ES3083_DIMENSION_FINDINGS.md` | moved in git |
| `ES3083_VENDOR_REQUEST_V2.md` | `bbrose_design_os/docs/archive/es3083/ES3083_VENDOR_REQUEST_V2.md` | moved in git |
| `ES3083_measurement_sheet_ZH_FILLED.docx` | `bbrose_design_os/docs/archive/es3083/ES3083_measurement_sheet_ZH_FILLED.docx` | moved in git |
| `LAUNCHER_D5B_COLOUR_SPACE.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5B_COLOUR_SPACE.md` | moved in git |
| `LAUNCHER_D5C_BUNDLED_AUTHORIZATION.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5C_BUNDLED_AUTHORIZATION.md` | moved in git |
| `LAUNCHER_D5D_RENDER_THE_TWELVE.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5D_RENDER_THE_TWELVE.md` | moved in git |
| `LAUNCHER_D5E_MOSS_GARDEN_AND_MATERIALS.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5E_MOSS_GARDEN_AND_MATERIALS.md` | moved in git |
| `LAUNCHER_D5F_FAMILY_CAPABILITY_CENSUS.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5F_FAMILY_CAPABILITY_CENSUS.md` | moved in git |
| `LAUNCHER_D5G_M7_DEFINITION_RULING.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5G_M7_DEFINITION_RULING.md` | moved in git |
| `LAUNCHER_D5H_THE_MEASURE_WAS_WRONG.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5H_THE_MEASURE_WAS_WRONG.md` | moved in git |
| `LAUNCHER_D5I_MOSS_GARDEN_RULED_AND_THE_INELIGIBLE_AXIS.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5I_MOSS_GARDEN_RULED_AND_THE_INELIGIBLE_AXIS.md` | moved in git |
| `LAUNCHER_D5J_THE_CENSUS_DID_NOT_CONTAIN_THEM.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5J_THE_CENSUS_DID_NOT_CONTAIN_THEM.md` | moved in git |
| `LAUNCHER_D5_SHADE_AUTHORITY.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_D5_SHADE_AUTHORITY.md` | moved in git |
| `LAUNCHER_M7A_TYPE_SPECIMENS_AT_TRUE_SCALE.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_M7A_TYPE_SPECIMENS_AT_TRUE_SCALE.md` | moved in git |
| `LAUNCHER_M7B_THE_LABEL_SHEET_YOU_CAN_ACTUALLY_PRINT.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_M7B_THE_LABEL_SHEET_YOU_CAN_ACTUALLY_PRINT.md` | moved in git |
| `LAUNCHER_M7C_THE_TREATMENTS_CHANGED_TWO_THINGS_AT_ONCE.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_M7C_THE_TREATMENTS_CHANGED_TWO_THINGS_AT_ONCE.md` | moved in git |
| `LAUNCHER_M7D_THE_WORDS_EXIST_AND_THE_ALIGNMENT_IS_A_LID_QUESTION.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_M7D_THE_WORDS_EXIST_AND_THE_ALIGNMENT_IS_A_LID_QUESTION.md` | moved in git |
| `LAUNCHER_M7E_FOUR_BLOCKERS_ONE_ADDRESSEE.md` | `bbrose_design_os/docs/archive/launchers/LAUNCHER_M7E_FOUR_BLOCKERS_ONE_ADDRESSEE.md` | moved in git |
| `NEXT_NODE_LAUNCHER.md` | `bbrose_design_os/docs/archive/launchers/NEXT_NODE_LAUNCHER.md` | moved in git |
| `NEXT_SESSION_LAUNCHER.md` | `bbrose_design_os/docs/archive/launchers/NEXT_SESSION_LAUNCHER.md` | moved in git |
| `OWNER_BLOCKER_SESSION.md` | `bbrose_design_os/docs/archive/launchers/OWNER_BLOCKER_SESSION.md` | moved in git |
| `tools/` | `bbrose_design_os/tools/` | 1 file, moved in git |
| `tools/dip0/` | `bbrose_design_os/tools/dip0/` | 13 files, moved in git |
| `tools/dip0/tests/` | `bbrose_design_os/tools/dip0/tests/` | 7 files, moved in git |
| `tools/dip0b/` | `bbrose_design_os/tools/dip0b/` | 26 files, moved in git |
| `tools/dip0b/tests/` | `bbrose_design_os/tools/dip0b/tests/` | 7 files, moved in git |
| `tools/dip0c/` | `bbrose_design_os/tools/dip0c/` | 71 files, moved in git |
| `tools/dip0c/tests/` | `bbrose_design_os/tools/dip0c/tests/` | 22 files, moved in git |
| `tools/brain/` | `bbrose_design_os/tools/brain/` | 9 files, moved in git |
| `vault/` | `brain_vault/` | renamed (the brain's generated notes; git-ignored) |
| `bbrose_design_os/var/` | `var/` | merged into the one var/ (the M6 frames to var/m6/, kept as they were) |
| `bbrose_design_os/.gitignore` | `.gitignore` | merged into the one .gitignore |

### Removed from the code (git keeps every line; each commit says what left and why)

| What left | Commit | On whose word |
|---|---|---|
| Pacdora: its agent, ARIA's hook, the packaging target's switch, its four settings | `a85df19` | one engine per job (your goal) |
| The carton's leftover picture-edit and "background pattern" code, the "faithful" preview and four dead switches | `0d96484` | one engine per job; pictures only on artwork (your Q3) |
| The dormant structure-confirmation flow ("Phase 2A-6"): its steps, two views and routes, its page script and its switch; task 50 stays on record | `d0426c1` | your Q1 |
| REFIT: the profile fitter, its branch and its drawing source (the 31.5 mm anchor moved into M3's module first, unchanged) | `4192377` | your REFIT answer |
| The dropper's rollback switch (`CONTAINER_STRUCTURAL_BACKBONE`) — a dropper bottle draws M3 | `f48d89a` | your Q8 |
| The old dashboard's leftovers and the APIs no page calls: the old Gate-1 regeneration API, the pre-2A run path, `/api/stats/`, the Library and batch APIs, the pre-merge dieline routes | `63f8bdd` | your goal, part 2 |
| What those removals left uncalled: the carton export's style-composer branch, the old generate API's helper, the old spend summary | `26a00d1` | one engine per job |
| Settings the site no longer reads (`.env.example` now names every one it does) | `f552595` | your goal, part 2 |
| Tracked junk (the duplicate lettering zip, two stray demo scripts) and the supplier files nothing reads — also in the REMOVE folder, below | `bee55ec`, `d67ceb0` | your goal; your Q4 |

### Archived (`archive/`, git-ignored; `archive/MANIFEST.tsv`)

| Old | New | Why |
|---|---|---|
| `~/bh21_work` | `archive/work/bh21_refusals_cleared_and_bh22_to_24` | archived: executor work folder, history the register cites; renamed by what it holds (67 files) |
| `~/bh25_work` | `archive/work/bh25_ofl_licence_reading` | archived: executor work folder, history the register cites; renamed by what it holds (19 files) |
| `~/bh26_work` | `archive/work/bh26_container_font_join` | archived: executor work folder, history the register cites; renamed by what it holds (105 files) |
| `~/bh27_work` | `archive/work/bh27_brand_fonts_census` | archived: executor work folder, history the register cites; renamed by what it holds (32 files) |
| `~/bh28_work` | `archive/work/bh28_used_faces_extraction` | archived: executor work folder, history the register cites; renamed by what it holds (19 files) |
| `~/bh29_work` | `archive/work/bh29_font_evidence_hunt` | archived: executor work folder, history the register cites; renamed by what it holds (393 files) |
| `~/bh30_work` | `archive/work/bh30_font_open_set_intake` | archived: executor work folder, history the register cites; renamed by what it holds (131 files) |
| `~/bh31_work` | `archive/work/bh31_font_wiring_proposal` | archived: executor work folder, history the register cites; renamed by what it holds (19 files) |
| `~/bh32_work` | `archive/work/bh32_font_wiring_build` | archived: executor work folder, history the register cites; renamed by what it holds (80 files) |
| `~/bh33_work` | `archive/work/bh33_font_smalls_and_gate_launcher` | archived: executor work folder, history the register cites; renamed by what it holds (54 files) |
| `~/bh34_work` | `archive/work/bh34_front_order_ruling` | archived: executor work folder, history the register cites; renamed by what it holds (7 files) |
| `~/bh35_work` | `archive/work/bh35_three_drop_materials_census` | archived: executor work folder, history the register cites; renamed by what it holds (313 files) |
| `~/bh36_work` | `archive/work/bh36_materials_terms_and_quarantine` | archived: executor work folder, history the register cites; renamed by what it holds (74 files) |
| `~/bh37_work` | `archive/work/bh37_materials_admission_build` | archived: executor work folder, history the register cites; renamed by what it holds (58 files) |
| `~/bh38_work` | `archive/work/bh38_colours_materials_proposal` | archived: executor work folder, history the register cites; renamed by what it holds (63 files) |
| `~/bh39_work` | `archive/work/bh39_colours_materials_build` | archived: executor work folder, history the register cites; renamed by what it holds (95 files) |
| `~/bh40_work` | `archive/work/bh40_brain_v1` | archived: executor work folder, history the register cites; renamed by what it holds (76 files) |
| `~/bh41_work` | `archive/work/bh41_test_db_flush_deadlock` | archived: executor work folder, history the register cites; renamed by what it holds (417 files) |
| `~/bh42_work` | `archive/work/bh42_brain_v2_embeddings` | archived: executor work folder, history the register cites; renamed by what it holds (465 files) |
| `~/bh43_work` | `archive/work/bh43_captions_library_vault` | archived: executor work folder, history the register cites; renamed by what it holds (52 files) |
| `~/bh44_work` | `archive/work/bh44_supplier_dispatch_staging` | archived: executor work folder, history the register cites; renamed by what it holds (45 files) |
| `~/bh45_work` | `archive/work/bh45_supplier_dispatch_corrections` | archived: executor work folder, history the register cites; renamed by what it holds (206 files) |
| `~/bh46_work` | `archive/work/bh46_no_supplier_contact_spec_pack` | archived: executor work folder, history the register cites; renamed by what it holds (389 files) |
| `~/bh47_work` | `archive/work/bh47_design_proposal` | archived: executor work folder, history the register cites; renamed by what it holds (47 files) |
| `~/bh48_work` | `archive/work/bh48_design_step1_bottle_from_picture` | archived: executor work folder, history the register cites; renamed by what it holds (176 files) |
| `~/bh49_work` | `archive/work/bh49_design_step2_m3_geometry` | archived: executor work folder, history the register cites; renamed by what it holds (91 files) |
| `~/bh50_work` | `archive/work/bh50_design_step3_rules_copy_palette` | archived: executor work folder, history the register cites; renamed by what it holds (680 files) |
| `~/bh50f_work` | `archive/work/bh50f_rules_placed` | archived: executor work folder, history the register cites; renamed by what it holds (4,257 files) |
| `~/bh51_work` | `archive/work/bh51_interface_survey` | archived: executor work folder, history the register cites; renamed by what it holds (517 files) |
| `~/bh52_work` | `archive/work/bh52_colour_study_slice1` | archived: executor work folder, history the register cites; renamed by what it holds (127 files) |
| `~/bh53_work` | `archive/work/bh53_front_bands_door` | archived: executor work folder, history the register cites; renamed by what it holds (117 files) |
| `~/bh54_work` | `archive/work/bh54_design_loop_slice2` | archived: executor work folder, history the register cites; renamed by what it holds (97 files) |
| `~/bh54b_work` | `archive/work/bh54b_block_completed` | archived: executor work folder, history the register cites; renamed by what it holds (110 files) |
| `~/bh55_work` | `archive/work/bh55_ten_day_standing_order` | archived: executor work folder, history the register cites; renamed by what it holds (1,361 files) |
| `~/bh55a_work` | `archive/work/bh55a_rose_palette_brief_captions` | archived: executor work folder, history the register cites; renamed by what it holds (37 files) |
| `~/bh56_work` | `archive/work/bh56_why_the_design_was_empty` | archived: executor work folder, history the register cites; renamed by what it holds (9 files) |
| `~/bh57_work` | `archive/work/bh57_creative_wires` | archived: executor work folder, history the register cites; renamed by what it holds (31 files) |
| `~/bh58_work` | `archive/work/bh58_classifier_fix_and_pictures` | archived: executor work folder, history the register cites; renamed by what it holds (21 files) |
| `~/bh60_work` | `archive/work/bh60_clone_test_fb2060` | archived: executor work folder, history the register cites; renamed by what it holds (91 files) |
| `~/bh61_work` | `archive/work/bh61_form_vocabulary` | archived: executor work folder, history the register cites; renamed by what it holds (12 files) |
| `~/bh61a_work` | `archive/work/bh61a_no_bottle_fallback` | archived: executor work folder, history the register cites; renamed by what it holds (6 files) |
| `~/bh61b_work` | `archive/work/bh61b_refusal_at_the_door` | archived: executor work folder, history the register cites; renamed by what it holds (5 files) |
| `~/bh62_work` | `archive/work/bh62_mood_board` | archived: executor work folder, history the register cites; renamed by what it holds (54 files) |
| `~/bh62a_work` | `archive/work/bh62a_board_record_fix` | archived: executor work folder, history the register cites; renamed by what it holds (2 files) |
| `~/bh63_work` | `archive/work/bh63_gate_waiter_rules` | archived: executor work folder, history the register cites; renamed by what it holds (4 files) |
| `~/bh64_work` | `archive/work/bh64_screen_enumeration_repairs` | archived: executor work folder, history the register cites; renamed by what it holds (40 files) |
| `~/bh65_work` | `archive/work/bh65_composer_taught` | archived: executor work folder, history the register cites; renamed by what it holds (115 files) |
| `~/bh66_work` | `archive/work/bh66_ruling_collisions_face_front` | archived: executor work folder, history the register cites; renamed by what it holds (90 files) |
| `~/bh67_work` | `archive/work/bh67_master_block_fixes` | archived: executor work folder, history the register cites; renamed by what it holds (190 files) |
| `~/bh68_work` | `archive/work/bh68_planner_check_and_containment` | archived: executor work folder, history the register cites; renamed by what it holds (143 files) |
| `~/bh69_work` | `archive/work/bh69_rounds_logo_trace_ui_build` | archived: executor work folder, history the register cites; renamed by what it holds (1,284 files) |
| `~/bh69g_work` | `archive/work/bh69g_cleanout_and_inspiration_picture` | archived: executor work folder, history the register cites; renamed by what it holds (77 files) |
| `~/bh70_work` | `archive/work/bh70_new_design_cards` | archived: executor work folder, history the register cites; renamed by what it holds (423 files) |
| `~/bh71_work` | `archive/work/bh71_trends_shapes_every_form` | archived: executor work folder, history the register cites; renamed by what it holds (859 files) |
| `~/td1_work` | `archive/work/td1_design116_finding` | archived: executor work folder, history the register cites; renamed by what it holds (128 files) |
| `~/td2_work` | `archive/work/td2_design117_print_areas` | archived: executor work folder, history the register cites; renamed by what it holds (87 files) |
| `~/td3_work` | `archive/work/td3_design117_redrawn` | archived: executor work folder, history the register cites; renamed by what it holds (175 files) |
| `~/td4_work` | `archive/work/td4_design_map_and_findings_118_119` | archived: executor work folder, history the register cites; renamed by what it holds; N8 then re-pointed r119/redraw.py and checks/score117.py at their … (1,249 files) |
| `~/Desktop/BBROSE_REPORT_2026-09-27_to_2026-10-03.md` | `archive/desktop/BBROSE_REPORT_2026-09-27_to_2026-10-03.md` | archived: a BBROSE item on the Desktop; history (1 file) |
| `~/Desktop/map117.png` | `archive/desktop/map117.png` | archived: a BBROSE item on the Desktop; history (1 file) |
| `~/Desktop/bbrose-forensics` | `archive/desktop/bbrose-forensics` | archived: a BBROSE item on the Desktop; history (6 files) |
| `~/Desktop/bbrose_ai_drift_quarantine_2026-08-18` | `archive/desktop/bbrose_ai_drift_quarantine_2026-08-18` | archived: a BBROSE item on the Desktop; history (3 files) |
| `var/bh62_board` | `archive/var/bh62_board` | archived: the §BH62 board scratch; only the register names it (107 files) |
| `~/cleanup_survey` | `archive/cleanup/cleanup_survey` | archived last, after the clean-up's final check: the clean-up's survey |
| `~/cleanup_work` | `archive/cleanup/cleanup_work` | archived last, after the clean-up's final check: the clean-up's ledgers, checks, predictions, scores and gate logs |

### Removed (`~/BBROSE_REMOVED_2026-10-04/`, outside the project; `MANIFEST.tsv` there)

A row written `<X.paths.txt>` moved the files that list names, one per line; the list is in the REMOVE folder, and each file keeps its old path under the folder's own.

| Old | New | Why |
|---|---|---|
| `CLEANUP_GOAL.md` | `~/BBROSE_REMOVED_2026-10-04/CLEANUP_GOAL.md` | removed: his prompt replaces it (1 file) |
| `bbrose_design_os/db.sqlite3` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/db.sqlite3` | removed: empty; the app uses Postgres (1 file) |
| `bbrose_design_os/logs/celery_worker.log` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/logs/celery_worker.log` | removed: a July worker log (1 file) |
| `var/brain.aside_bh43a` | `~/BBROSE_REMOVED_2026-10-04/var/brain.aside_bh43a` | removed: a stale copy of the brain from 2026-09-09; nothing names it (391 files) |
| `~/scratch_venv` | `~/BBROSE_REMOVED_2026-10-04/home/scratch_venv` | removed: a one-off Python environment; rebuildable (4,666 files) |
| `~/.bbrose_env_recovery` | `~/BBROSE_REMOVED_2026-10-04/home/.bbrose_env_recovery` | removed: July env-recovery leftovers; may hold secrets (not opened) (27 files) |
| `~/bh35_work/venv` | `~/BBROSE_REMOVED_2026-10-04/home/bh35_work/venv` | removed: a Python environment inside a work folder; breaks on any move, rebuildable (5,609 files) |
| `~/bh42_work/embed_venv` | `~/BBROSE_REMOVED_2026-10-04/home/bh42_work/embed_venv` | removed: a Python environment inside a work folder; breaks on any move, rebuildable (4,686 files) |
| `~/Desktop/bbrose-acceptance-fixtures` | `~/BBROSE_REMOVED_2026-10-04/Desktop/bbrose-acceptance-fixtures` | removed: four 1-pixel test fixtures from 1 Aug; nothing uses them (4 files) |
| `<R3.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<R3.paths.txt>` | removed: caches (rebuilt on the next run) (batch of 66; 0 listed but already gone) (1,494 files) |
| `.git/<R13.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/git/<R13.paths.txt>` | removed: half-written git objects from interrupted writes; git never reads them (batch of 151; 0 listed but already gone) (151 files) |
| `<R4.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<R4.paths.txt>` | removed: Finder clutter (batch of 9; the 2 inside the read-only owner_inputs/…/originals/ folder are left untouched) (9 files) |
| `bbrose_design_os/media/brand/.DS_Store` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/media/brand/.DS_Store` | removed: Finder clutter (1 file) |
| `.claude/worktrees/agent-a30cad04ca02ec9ca` | `~/BBROSE_REMOVED_2026-10-04/.claude/worktrees/agent-a30cad04ca02ec9ca` | removed: a full second copy of the project (the leftover agent worktree); its 7 changed files are the uncommitted draft of cd02179, saved as … (7,839 files) |
| `stash@{0}` | `~/BBROSE_REMOVED_2026-10-04/git/stash-bh68-wt68-pre-rebuild.patch` | removed: the stash 'bh68 wt68 pre-rebuild', saved as a patch then dropped (1 file) |
| `bbrose_design_os/media/<R9.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/media/<R9.paths.txt>` | removed: Q7: media files named by no record and no tracked file, written inside a gate window before the 2026-09-25 media fix (4ead249) — test output (batch … (676,201 files) |
| `/private/var/folders/c4/9p68gjd95pvg5_s8dwywwg200000gn/T/<R11.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/tmp/<R11.paths.txt>` | removed: test (and drawing-step) leftovers in the system temp folder; named prefixes only (batch of 79030; 0 listed but already gone; 0 refused by the … (199,996 files) |
| `Rose_Damascena_Custom_Lettering_Package.zip` | `~/BBROSE_REMOVED_2026-10-04/Rose_Damascena_Custom_Lettering_Package.zip` | removed: its 5 files are byte-identical to the tracked docs/visual_quality/vq2/received/ copies (1 file) |
| `bbrose_design_os/demo_walkthrough.py` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/demo_walkthrough.py` | removed: a stray demo script (his goal names it) (1 file) |
| `bbrose_design_os/eyeliner_task.py` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/eyeliner_task.py` | removed: a stray demo script (his goal names it) (1 file) |
| `bbrose_design_os/.gitignore` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/.gitignore` | removed: merged into the git root's .gitignore (one ignore file); content kept line for line there (1 file) |
| `tools/__pycache__` | `~/BBROSE_REMOVED_2026-10-04/tools/__pycache__.regenerated` | removed: a cache regenerated in the git root's emptied tools/ after R3 (rebuilt by the next run) (1 file) |
| `/private/tmp/<R11b.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/tmp_fixed/<R11b.paths.txt>` | removed: fixed-path test leftovers in /tmp (test_wiu_front_collision's /tmp/_wiu_* files, test_concept_references' /tmp/bh60-withheld* folders), now made in … (35 files) |
| `<M2.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<M2.paths.txt>` | removed: Q5: unrelated stock (restaurants, shipping, bathrooms, logistics, buildings, card game, workwear, space, misc art) (batch of 46; 0 listed but already … (133 files) |
| `<M3.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<M3.paths.txt>` | removed: Q5: the check stock (Traffic lights, Candy, fruits2, EDUME, FAIRY; sanitary/tampon/wet-wipe and carton mockups) (batch of 150; 0 listed but already … (677 files) |
| `<M4.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<M4.paths.txt>` | removed: Q6: pirated Cracked-by fonts (the FONTS 2026 faces and their byte-identical Fonts/3333 copies) (batch of 7; 0 listed but already gone; 48 refused by … (7 files) |
| `<M5.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<M5.paths.txt>` | removed: Q5: Windows .fon screen fonts, unusable in print (batch of 56; 0 listed but already gone; 4 refused by the filesystem, left in place, listed in … (56 files) |
| `<M6.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<M6.paths.txt>` | removed: Q5: an empty pirated-software folder (a Photoshop Portable download, empty folders only) (batch of 1; 0 listed but already gone; 0 refused by the … (0 files) |
| `<DL.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<DL.paths.txt>` | removed: his DL line: unrelated stock in DOWNLOADE 2026 on no row (batch of 207; 0 listed but already gone; 0 refused by the filesystem, left in place, listed … (386 files) |
| `<M1.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/<M1.paths.txt>` | removed: Q5: exact duplicate copies (inventory sha256); the copy a record names stays; Fonts/X stays and Fonts/3333/X leaves (batch of 1053; 0 listed but … (1,059 files) |
| `materials/<M4.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/materials/<M4.paths.txt>` | removed: the same group's files Finder had locked (uchg): unlocked to move, locked again at the destination (48 files) |
| `materials/<M5.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/materials/<M5.paths.txt>` | removed: the same group's files Finder had locked (uchg): unlocked to move, locked again at the destination (4 files) |
| `materials/<M1.paths.txt>` | `~/BBROSE_REMOVED_2026-10-04/materials/<M1.paths.txt>` | removed: the same group's files Finder had locked (uchg): unlocked to move, locked again at the destination (8 files) |
| `bbrose_design_os/docs/production_authority/dispatch_pack` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/docs/production_authority/dispatch_pack` | removed: the supplier dispatch pack: nothing opens, lists or hashes its 15 files (his fourth answer, Q4) (15 files) |
| `bbrose_design_os/docs/production_authority/supplier_outreach_deferral_d9_check.json` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/docs/production_authority/supplier_outreach_deferral_d9_check.json` | removed: nothing reads it (Q4) (1 file) |
| `bbrose_design_os/docs/production_authority/supplier_sent_evidence/README.txt` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/docs/production_authority/supplier_sent_evidence/README.txt` | removed: nothing reads it; the review page's sentence pointing at it is edited (Q4) (1 file) |
| `ES3083_VENDOR_REQUEST.md` | `~/BBROSE_REMOVED_2026-10-04/ES3083_VENDOR_REQUEST.md` | removed: the first ES3083 vendor letter; nothing reads it (Q4) (1 file) |
| `ES3083_measurement_sheet_AR.docx` | `~/BBROSE_REMOVED_2026-10-04/ES3083_measurement_sheet_AR.docx` | removed: a blank measurement form; nothing reads it (Q4) (1 file) |
| `ES3083_measurement_sheet_ZH.docx` | `~/BBROSE_REMOVED_2026-10-04/ES3083_measurement_sheet_ZH.docx` | removed: a blank measurement form; nothing reads it (Q4) (1 file) |
| `bbrose_design_os/docs/roadmap/palt_m2/supplier_reference_shortlist.json` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/docs/roadmap/palt_m2/supplier_reference_shortlist.json` | removed: nothing reads it; named only in an unread tracker's deliverables list (Q4) (1 file) |
| `bbrose_design_os/docs/roadmap/palt_m2/supplier_technical_drawing_request.md` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/docs/roadmap/palt_m2/supplier_technical_drawing_request.md` | removed: nothing reads it (Q4) (1 file) |
| `bbrose_design_os/docs/roadmap/palt_m3/supplier_request_package.md` | `~/BBROSE_REMOVED_2026-10-04/bbrose_design_os/docs/roadmap/palt_m3/supplier_request_package.md` | removed: nothing reads it (Q4) (1 file) |

## Rescue authoring routes — 18 October 2026

- `/dashboard/serum-master/`: the Day 2 software proof, now explicitly superseded pending the concept147 fidelity master. Stored files remain unchanged.
- `/dashboard/stand-master/`: immutable stepped-display geometry, its original144/146 refusals and one checked package download. No approval action.
- `apps/pipeline/services/assembly_spec.py`: independent `assembly_spec/1.0` and explicit pinned/declared product identities.
- `apps/ire/stepped_display.py`, `assembly_drawings.py`: deterministic constraints, sightlines and shared SVG/PDF scene.
- `manage.py build_stepped_display --case family-proposal --output NEW_DIRECTORY`: reproduce a bundle without providers or database writes.
- `docs/audit/day-3/`: comparison, real-size plan, original-brief diagnostics and the Day4 handoff. `CURRENT_DECISIONS.md` governs the rescue; historical registers remain unchanged.


## Rescue Day 4 review routes

`/dashboard/serum-master/` shows concept147 beside fidelity revision2; `/dashboard/stand-master/` shows the pinned twelve-position family and its surface proofs. Both are authenticated, read-only and have no Approve. Files are hash-checked against `docs/audit/day-4/publication.json`. Day2/3 authoring pages remain under the respective `/legacy/` route; historical task routes are preserved. The Day4 packet and known failures are documented in `docs/audit/day-4/README.md`. `fidelity_master.py`, `fidelity_checks.py`, `identity_assembly.py` and `identity_sightlines.py` implement the bounded measured route; `day4_proofs.py` builds review sheets. `tools/rescue_day4_package.py` packages existing artifacts without paid calls. Material/UV rendering remains Day5.
