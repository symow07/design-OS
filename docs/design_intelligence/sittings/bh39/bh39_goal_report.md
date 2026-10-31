# §BH39 GOAL REPORT — COLOURS AND MATERIALS WIRING, BUILD HALF

Written 2026-09-08 at final HEAD 178a9a7. Every number is measured at that HEAD
unless it names the commit it was measured at. Work directory `~/bh39_work/`.

## 0. The commit chain (every commit predicted-then-scored)

| Commit | Concern | Prediction → score |
|---|---|---|
| 9bf963e | T39 — §BH39 transcribed (pure append, 206 lines: the 76 typed lines verbatim, the ruled tables and option A quoted verbatim, Warm Gold's 24 files, the own-work packs) | pred_t39 c5c13590966e5ccd → 8/8 |
| 1f1b5a0 | (a) brand_gov naming + roles — "Warm Gold" #CBA87D in both canonical systems with its provenance; the eight measured roles as the brand's colour roles (docs/brand_gov/colour_roles_1_0.json); the dark accents hold no role; the seed run on the dev database | pred_a e5f8da068bde3791 → 8/8 |
| 50b1d74 | (c) own work PRODUCTION BY OWNER DECLARATION — three packs, 126 rows, the declaration record as evidence; the Freepik-tagged PSD withheld | pred_c 0a44bb37d9cc4b58 → 7/8 (two unpredicted test pins of the executor's own (4) section; every value exact) |
| 98714bd | (d)-0 the Coolvetica EULA row returns to REFERENCE | pred_d0 a086c3a7560eb775 → 8/8 |
| 90484bc | (d) the placement record on the Image seam, the credit node, the refusals; the retrieval contract as an interface | pred_d 2c866c6020ad34c7 → 8/8 |
| d6fbff0 | (e) the colour layer (colour_roles.py), the emitter hook, the post-hoc check on the layer's roles | pred_e 369e8247724ddcd5 → 8/8 |
| 178a9a7 | (f) the counters reconciled; the goal documents | pred_f fca96c670e42a296 → 8/8 |

## 1. Goal state, measured at final HEAD

Each item of the ruled GOAL STATE, with where it was measured:

- **A real non-exempt document emitted with every colour role resolving through the layer to brand_gov, Warm Gold included, counter == fills.** `colour_roles.compose_goal_exercise()` — one field per role, a live text line, tagged `bh32/goal-exercise` (non-exempt), every literal declared as a role in its role map — emitted through the real emitter (`emit_pdf_ai`) under the gate at 178a9a7 (`test_goal_a_real_non_exempt_document_draws_every_colour_role_from_brand_gov_and_the_counter_equals_its_fills`): the artefact's fills carry `#CBA87D` (Warm Gold) drawn from brand_gov; every colour resolved from brand_gov is a role's brand swatch; `colour_usage/1.0`'s reconciliation agrees — no unreconciled fill, no counted-but-absent colour; the only fills outside brand_gov are the two roles with no brand colour (`accent_dark` `#231916`, `ink` black), recorded as the surface's literals and process black. 
- **One document placing a PRODUCTION asset with its credit in the record and visible.** A Freepik-credited JPEG of the tier record (a PRODUCTION row with its condition) placed as an `Image` with its `materials_placement/1.0` record and its credit node: PLACED, the record carrying the row's evidence and its verbatim condition, the credit's print form visible on the artefact's page, `placement_usage/1.0` reconciled — placed == embedded images (1 == 1). 
- **One negative control proving a REFERENCE asset cannot be placed and a REFERENCE palette cannot be written.** A REFERENCE row's JPEG placed with a record: the emitter raises `REFUSED_REFERENCE_ASSET` ahead of every byte and no file exists; for every one of the eight roles a REFERENCE candidate receives `INSPIRATION_ONLY` and no resolution carries its hex or a REFERENCE tier. 
- **Own-work rows measured PRODUCTION with the declaration as evidence.** 126 rows (three packs) at PRODUCTION, `tier_source` OWNER_GRANT, `terms_class` OWNER_DECLARATION, `evidence` = the tracked declaration record by path + sha256 06d9cfcc32493589…, re-hashed on every application (the (c) tests under the gate at 50b1d74; the record at HEAD: 4,832 rows = 4,691 REFERENCE + 141 PRODUCTION).
- **Gate GREEN, worktree clean, ledger clean, every commit predicted-then-scored, authority spent only on its landing.** Seven gates, seven GREEN first launches; ledger 477 → 483, append-only at every step; every commit's prediction sealed before git add ((c) and (d)-0 before the write) and scored; the (c) authority (the owner's declaration) spent at 50b1d74; the (a) naming spent at 1f1b5a0; no other authority.

## 2. What each ruling became (a)–(f)

**(a) COLOUR ROLES: ACCEPTED AS MEASURED.** The tracked record `bbrose_design_os/docs/brand_gov/colour_roles_1_0.json` (brand_colour_roles/1.0) carries the eight measured roles in the ruled order — `ground_cream`, `ground_gold`, `ground_blush`, `accent_light`, `accent_blush`, `accent_nude`, `accent_dark`, `ink` — each with the brand swatch it maps to, the measured hex, the files led and the ΔE, and the measured clusters of §BH38 §3d beneath. "Warm Gold" entered brand_gov by the owner's sentence as a Ground swatch of BOTH canonical systems in `seed_bbrose.py` — hex `#CBA87D`, the measured value; provenance "§BH39(a) · measured 2026-09-07 by structure from 24 historical design files · docs/brand_gov/colour_roles_1_0.json" — and the 24 files are listed by path in the record and in the T39 register block. The seed was run once on the dev database after 1f1b5a0 landed (idempotent update_or_create): CS-001 and CS-002 each carry exactly one Warm Gold; `get_brand_hexes` carries `#CBA87D`. Deep Rose `#8B3A52` and Cocoa Rose `#7A4A42` stay in the record under `no_role`; no role names them. `accent_dark` (`#231916`) and `ink` (black) are the two roles with no brand colour — recorded as such, not named (the ruling names Warm Gold only).

**(b) AUTHORITY: brand_gov FIRST — option A, narrowed.** The layer resolves a role with a brand colour to brand_gov and refuses every library candidate for it (`CANDIDATE_REFUSED_ROLE_HAS_BRAND_COLOUR`); a role without a brand colour may take a PRODUCTION-palette candidate (`CANDIDATE_ADMITTED`, only from a PRODUCTION tier row); a REFERENCE row's colour is `INSPIRATION_ONLY` and no resolution ever carries a REFERENCE tier. The owner's sentence ("candidates only where a role has no brand colour") is what the code does; option A's "within a measured distance (ΔE) of a brand swatch" clause was not built.

**(c) OWN WORK: PRODUCTION BY OWNER DECLARATION.** The tracked declaration record `docs/design_intelligence/dip0a/own_work_declaration_bh39.json` (own_work_declaration/1.0, sha256 06d9cfcc32493589…) quotes the (c) sentence verbatim, names the T39 commit 9bf963e, and carries, per pack, the path, the file count, the withheld file and the full sha256 set. Three grants of terms_class OWNER_DECLARATION (granted_at 2026-09-08, no condition) pin that record by path + sha256, re-hashed on every application — 126 rows: `skin care لورنزا` 52 (of 53), `BOTTLEتعديل لون` 40, `feonca 5 to jouman` 34. Withheld and reported: `skin care لورنزا/FACE WASH FOAM/بخاخ تيوب 2.psd`, whose own XMP says `dc:rights = Freepik Company S.L.` — not the company's own work by its own metadata; it stays REFERENCE. Not granted because the §BH38 report did not list them: the 47 loose files at the Telegram Desktop root (among them Freepik-pattern names, two vecteezy files, two stock vectors by KAOKIEMONKEY, an Apple-copyright image and 16 .rar archives) and the packs ستيلا (12), ستيلا عبوات (11), stella (1) (9), M308 MIACARA (1) — one sentence away.

**(d) MATERIALS: ACCEPTED AS PROPOSED — built at 90484bc.** `apps/ire/materials_placement.py` (materials_placement/1.0): a composer attaches, per placed asset, the tier row (path, sha256, tier, evidence, condition, terms_class), the placement (node, mm box, clip) and the credit node it names; `credit_text` lifts the verbatim PRINT form the terms state and `credit_node` is a live TextRun named `credit-<node>`. The seam is the emitter: ahead of every byte, beside the provisional gate, `refuse_or_skip` resolves every Image — an ungoverned media/ image places as today; a `materials/` source without its record is REFUSED (`REFUSED_NO_PLACEMENT_RECORD`); a REFERENCE row is REFUSED (`REFUSED_REFERENCE_ASSET`) and no file is written; a conditioned PRODUCTION asset whose credit is not visible resolves `RESOLVED_REFERENCE_NO_VISIBLE_CREDIT` for that output (its Image is not drawn, the resolution recorded); with its credit node it is PLACED. `placement_usage/1.0` rides in `usage_out` beside the §BH32(f) font usage. `apps/ire/materials_retrieval.py` (materials_retrieval/1.0) is the interface: the query shape, the row fields (sha256, tier, category, pack, caption, palette, layout_metadata, evidence, condition, the copy prohibitions verbatim), the forbidden fields (path, locator, bytes …) refused by schema, and a `query` that validates and refuses — the BRAIN implements it; there is no server. The WIT denominator moved 863 → 864 for the credit node's `size_pt` (located, predicted).

**(d)-0 The Coolvetica EULA row returns to REFERENCE.** The generator's rule "a grant's own evidence file is never a granted row" retired the coolvetica PERMISSIVE grant (its only remaining file was its EULA): 10 grants, 141 PRODUCTION rows (15 Freepik with the credit, 126 by declaration, 0 PERMISSIVE), 4,691 REFERENCE; the EULA pdf REFERENCE by machine, proved by the appended control.

**(e) THE COLOUR LAYER — built at d6fbff0.** `apps/ire/colour_roles.py` (colour_roles/1.0) in the font_roles idiom: the eight roles; the record read from `docs/brand_gov/colour_roles_1_0.json` and, when a database is at hand, the LIVE ColorSystem swatch it names (brand_gov proper); `library_candidate` — the seam: a colour read from a file resolves only through that file's tier row, PRODUCTION admitted (and only where the role has no brand colour), REFERENCE `INSPIRATION_ONLY`, anything else refused; `resolve_role` — an exempt or untagged document receives the surface's own literal untouched, a non-exempt document brand_gov FIRST, then an admitted candidate, then the literal recorded as `SURFACE_FALLBACK`; the document role map (a composer declares which of its literals are roles) and `resolve_fill` for the emitter; `brand_hexes_for_check`. The emitter: `_rl_color(color, ctx)` — on a non-exempt document a declared colour resolves through the layer and is counted; an exempt document draws every literal as today (`ctx.colour_doc` is None). The post-hoc palette check (`qa_reviewer`) measures against the layer's roles — Warm Gold included, neither dark accent — falling back to `get_brand_hexes`; `build_brand_context` (the prompt path) keeps its seeded palettes. Untouched by design: the design language's literals (its surfaces are exempt), the M7 emitter's substrate/PANTONE record, the PALT powder engine's shade authority.

**(f) USAGE MEASURED — built at 178a9a7.** `colour_usage/1.0` carries its reconciliation (`reconcile_fills`: every vector fill of the emitted artefact must be a counted colour or process black/white, every counted colour must appear; unreconciled fills and counted-but-absent colours named) and `placement_usage/1.0` its own (`reconcile_images`: placed == embedded image XObjects, the surplus named); both per run, in `usage_out`, `agree` a measured boolean. The goal documents live in the emitter's tests and ran under the gate: the goal exercise drew Warm Gold from brand_gov with counter == fills; the credited PRODUCTION asset placed and visible with placed == embedded; the REFERENCE asset refused and the REFERENCE palette never written — all three green under the gate at 178a9a7.

## 3. Recorded, not resolved (the sentence governs)

1. **Option A, narrowed.** The owner's (b) sentence admits library candidates "only where a role has no brand colour"; option A's ΔE clause was not built. The two roles with no brand colour today are `accent_dark` (`#231916`) and `ink`; the layer records them as the surface's literal until a PRODUCTION candidate or a naming arrives.
2. **The withheld PSD.** `skin care لورنزا/FACE WASH FOAM/بخاخ تيوب 2.psd` carries `dc:rights = Freepik Company S.L.` in its own XMP and stayed REFERENCE outside the owner's declaration — one word decides it.
3. **The packs the report did not list.** The Telegram Desktop root (47 files, several with third-party signals) and the packs ستيلا, ستيلا عبوات, stella (1), M308 MIACARA are not granted; a sentence naming them is a (c)-shaped grant each.
4. **The same bytes at the drop root.** `17-10-2024/face wash tube.ai` is byte-identical to an own-work file and stays REFERENCE by scope (outside the declared pack).
5. **The (c) pin census.** Two test pins of the (4) section moved that the prediction had not named (the scope of a declaration grant; the evidence's category) — scored 7/8, recorded in `score_c.txt`.
6. **The WIT denominator moved once, 863 → 864**, located to the credit node's `size_pt` (predicted at (d)).
7. **brand_gov swatches carry no CMYK.** The layer emits a brand role as an RGB fill (the hex) unless a CMYK is ruled; the design language's swatches carry their own CMYK and are exempt-surface literals. A print-intent CMYK per brand swatch is a data ruling, not built.
8. **The live record is per database.** The seed is the record in the repo; the dev database was seeded once after (a); any other environment folds Warm Gold in when its seed runs.
9. **The retrieval contract is an interface.** `MaterialsRetrieval.query` validates and refuses; the BRAIN front implements it (§BH34 front 3).
10. **The summary's withheld counter** (`license_evidence_rows_withheld` = 18) counts the 17 texts and the EULA together; the name is narrower than the count.

## 4. Hard stops

- *any REFERENCE asset or palette reaching an output* — never fired: the emitter refuses a REFERENCE asset ahead of every byte; a REFERENCE palette receives `INSPIRATION_ONLY` and never resolves; both proved under the gate.
- *a colour outside brand_gov + the PRODUCTION palette resolving as a default* — never fired: a role resolves to brand_gov, or to an admitted PRODUCTION candidate, or to the surface's own literal (the value the engine drew before the layer), which is recorded as `SURFACE_FALLBACK` and never invented.
- *any exempt surface changing* — never fired: no composer changed; the ten exempt-surface pin files (the golden baselines, the WI pins, the sticker) passed alone before every seal and under every gate; the emitter draws an exempt document's literals with `ctx.colour_doc` None.
- *M7 or PALT records moving* — never fired: `palette_m7_ai_emitter.py`, `palette_powder_engine.py` untouched across the chain (measured in §5); the eight M7 artefacts == baseline at every landing.
- *a census-unpredicted pin class* — never fired: no ruled pin class moved unpredicted (the WIT move was predicted; the two (c) test pins were pins of the executor's own tests, recorded).
- *a third infrastructure refusal* — never fired: seven launches, seven GREEN; §BH24 stays 2/3.

## 5. Nothing else moved

Measured at HEAD 178a9a7 after the last landing (`~/bh39_work/closing39.sh`, output `closing39_output.txt`): worktree clean; the chain since T39 is exactly the six ruled commits; the paths touched are the register (T39), the seed and its tests and the brand_gov record ((a)), the channel module, its tests, the tier summary and the declaration record ((c), (d)-0), the emitter, the two materials modules, the layer, the QA reviewer and the emitter's tests ((d), (e), (f)), plus the gate's ledger lines; the DIP-0A inventory 3b3cfdc2bf4fc6c0… unchanged; the exclusion list's two entries at HEAD; the three folders' file counts unchanged and nothing newer than the transcription; no write outside the landed paths and `~/bh39_work/` but the gate's own ignored side-outputs (the tier record regenerated by (c)/(d)-0 under `var/`, and 38 per-candidate JSONs under `var/design_intelligence/audits/dip0c/candidates/` written by the gate's dip0c leg at 18:01Z inside the (f) gate window — `OUT_CANDIDATES`, git-ignored — not the measurement's); the WIT denominator 864 at its one located move; `palette_m7_ai_emitter.py`, `palette_powder_engine.py`, `design_language.py`, `font_roles.py` and `container_font_authority.py` untouched across the chain; the protected regions, the tree seals since their last predicted move, and the eight M7 artefacts byte-identical; the font theme unchanged under Django.

Raw output:

```
HEAD 178a9a7
=== porcelain ===
(porcelain RC=0)
=== the chain since T39 ===
178a9a7 feat(§BH39(f)): USAGE MEASURED — per-run, per-colour counter reconciled against the artefact's actu
d6fbff0 feat(§BH39(e)): THE COLOUR LAYER — apps/ire/colour_roles.py in the font_roles idiom: the eight rule
90484bc feat(§BH39(d)): MATERIALS — the placement record on the Image seam with the credit node, §BH37's a
98714bd fix(§BH39(d)): the Coolvetica EULA row returns to REFERENCE — the evidence file itself is never a g
50b1d74 feat(§BH39(c)): OWN WORK — PRODUCTION BY OWNER DECLARATION: the three Telegram Desktop packs the §
1f1b5a0 feat(§BH39(a)): brand_gov naming + roles — "Warm Gold" #CBA87D enters both canonical colour systems
9bf963e docs(§BC): transcribe OWNER RULING/GOAL §BH39 — COLOURS AND MATERIALS WIRING, BUILD HALF: the §BH
=== paths touched since T39 (excluding the ledger) ===
bbrose_design_os/apps/core/management/commands/seed_bbrose.py
bbrose_design_os/apps/core/tests.py
bbrose_design_os/apps/ire/colour_roles.py
bbrose_design_os/apps/ire/emitters/pdf_ai.py
bbrose_design_os/apps/ire/materials_owner_grant.py
bbrose_design_os/apps/ire/materials_placement.py
bbrose_design_os/apps/ire/materials_retrieval.py
bbrose_design_os/apps/ire/tests/test_pdf_ai_emitter.py
bbrose_design_os/apps/ire/tests/test_wit_unit_analysis.py
bbrose_design_os/apps/pipeline/agents/qa_reviewer.py
bbrose_design_os/apps/pipeline/tests/test_container_font_owner_grant.py
bbrose_design_os/docs/brand_gov/colour_roles_1_0.json
docs/design_intelligence/dip0a/materials_tiers_summary.json
docs/design_intelligence/dip0a/own_work_declaration_bh39.json
=== exclusion list vs HEAD ===
2
=== inventory ===
3b3cfdc2bf4fc6c0
17-10-2024: 1728 files, newer than the §BH39 transcription: 0
ALL..MOCKUP: 1693 files, newer than the §BH39 transcription: 0
ADOBE STOCK: 1490 files, newer than the §BH39 transcription: 0
=== writes since the §BH39 transcription outside the landed paths (repo tree; excluding materials/, venv, .git, caches, gate outputs, media/generated) ===
tracked: ./bbrose_design_os/docs/brand_gov/colour_roles_1_0.json
tracked: ./bbrose_design_os/apps/pipeline/tests/test_container_font_owner_grant.py
tracked: ./bbrose_design_os/apps/pipeline/agents/qa_reviewer.py
tracked: ./bbrose_design_os/apps/core/management/commands/seed_bbrose.py
tracked: ./bbrose_design_os/apps/core/tests.py
tracked: ./bbrose_design_os/apps/ire/materials_retrieval.py
tracked: ./bbrose_design_os/apps/ire/tests/test_wit_unit_analysis.py
tracked: ./bbrose_design_os/apps/ire/tests/test_pdf_ai_emitter.py
tracked: ./bbrose_design_os/apps/ire/materials_placement.py
tracked: ./bbrose_design_os/apps/ire/colour_roles.py
tracked: ./bbrose_design_os/apps/ire/materials_owner_grant.py
tracked: ./bbrose_design_os/apps/ire/emitters/pdf_ai.py
UNTRACKED: ./var/design_intelligence/audits/dip0/tiers/materials_tiers.jsonl
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__DOWNLOADS 12-2025__acid-cosmetics-make-up-stickers-collection__9347862.ai.c2b.json
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__DOWNLOADS 12-2025__abstract-graphical-seamless-pattern-vector-illustration__00b8725f-e97e-4e94-91ac-e0f1f8b82b7c.jpg.c2b.json
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__DOWNLOADS 12-2025__background-remover(1)__Weixin Image_20250919141742_67_18.png.json
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__خدمات لوجستيه وشركات شحن__transport-logistic-manager-checking-control-logistic-network-distribution-customer.jpg.json
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__نماذج عامة من  01الانترنيت__1_5061030170064.svg.json
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__24-hours-day-concept-clock-face-with-dial-arrow-around-day-night-interface-icon-use-web-design__icsinto_499.eps.json
UNTRACKED: ./var/design_intelligence/audits/dip0c/candidates/materials__DOWNLOADE 2026__24-hours-day-service-availability-fluid-background__SL-041222-49680-07.jpg.json
(end)
=== ~ writes since the transcription outside ~/bh39_work ===
(end)
=== WIT denominator ===
1400:TREE_CHECKS = 864
=== untouched by ruling: the M7 emitter, the PALT powder engine, the design language, the exempt list ===
(empty = untouched)
GATE [514:541] 7fbeb8f1fe10b0fb (7fbeb8f1fe10b0fb) lines 593
TEST b32030dc827263e4 (b32030dc827263e4)
seal docs/design_intelligence/dip0c c22592930c75001c
seal docs/design_intelligence/dip0a d72072760ab20a6a
M7 artefacts == baseline: True
```

## 6. What remains

- Front 3 — THE BRAIN — opens with its own goal, as ruled: it implements `materials_retrieval/1.0` over the tier record and serves the REFERENCE rows as inspiration cards and prompt vocabulary.
- The readings of §3 (items 1–4, 7) each close with one sentence.
- No composer other than the goal exercise declares a role map yet: the exempt surfaces keep their literals by ruling; a surface adopts the layer by declaring a non-exempt tag and a role map — a ruling per surface, as at §BH32(h).
