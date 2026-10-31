# §BH38 REPORT — COLOURS AND MATERIALS WIRING, PROPOSAL HALF (in §BH31's shape)

Written 2026-09-07 at final HEAD 4a9043d. Nothing was built. Every number is
measured on this machine at that HEAD; every proposal in §4 is for the owner to
rule. Work directory `~/bh38_work/` (greps, extractions, previews, predictions,
seals, scores).

## 0. What landed before the measurement (the ruled order)

| Commit | Concern | Prediction → score |
|---|---|---|
| ff7b11a | T38 — §BH38 transcribed (pure append, 158 lines: the 64 typed lines verbatim, the riding ruling's receipt, one reading applied narrow) | pred_t38 74c8010e33b408e2 → 8/8 |
| 4a9043d | the riding ruling — the 17 terms and read-me texts return to REFERENCE; preview-is-prediction | pred_riding 0414581dae68899f → 8/8 (values exact; line shape stated as measured-at-scoring) |

**The riding ruling, landed.** The 17 LICENSE_EVIDENCE rows of the granted packs are REFERENCE again: the generator that wrote the §BH37(4) grants gained one rule (a row whose DIP-0A category is LICENSE_EVIDENCE is never a granted file), the tuple was regenerated (10 → 8 grants: baloo and codex named only their text; 33 → 16 (sha256, path) pairs; every evidence pin unchanged), the tier record and the tracked summary were regenerated through the channel (4,832 rows = 4,816 REFERENCE + 16 PRODUCTION, 15 with the Freepik credit), and one negative control was appended to the channel's test file (no LICENSE_EVIDENCE row PRODUCTION, no grant names one, every grant names a file, every text REFERENCE by machine). The dry run's values were sealed as the prediction before the write and every written value equals them (the written tuple equals its preview as a set). The narrow reading stands recorded: the coolvetica EULA pdf — the pack's own terms text, PRODUCT_REFERENCE by the classifier — is the one PERMISSIVE PRODUCTION row until the owner's word (§7.1).

## 1. The resolution as it is, colours (goal 1)

### 1a. The static search shape — colour literals and colour calls under apps/

Extent: every Python module under `bbrose_design_os/apps/` excluding `tests/` and `migrations/` — **571 modules** (324 test modules and 65 migrations excluded; the tests are pins, not resolution points). Two greps, both kept in `~/bh38_work/`: (i) six-digit hex literals `#RRGGBB` — **244 lines in 38 modules** (`hex_points.txt`); (ii) colour constructors and fill/stroke calls — `HexColor(`, `CMYKColor(`, `Color(`, `colors.<name>`, `setFillColor`/`setStrokeColor`, `fill_color`/`stroke_color`, `rgb(`, `cmyk`, and 0..1 float triples — **207 lines in 46 modules** (`colour_calls.txt`). Every module is classified below by whether it lies on a production path (a document a client or a printer receives) or is diagnostic / one-off review tooling; the classification is the transcriber's reading of each module's own header.

| Module (file:line of the first literal) | Literals | What it resolves to on a real document | Governance record consulted? |
|---|---|---|---|
| `apps/ire/design_language.py:92–112` | 12 hex + CMYK per swatch | The IRE **SwatchSets**: `DEFAULT_SWATCHES` (GROUND_TOP #E8C9B3, GROUND_BOTTOM #F0DECB, LINE_LIGHT #F7EFE4, LINE_DEEP #D9B49A, ACCENT_FOIL #B76E79, INK #59283A) and `POWDER_CONSTELLATION_SWATCHES` (WARM_IVORY_BASE #FAF3EC, BLUSH_PINK #F2C4CE, SOFT_PEACH_PARTICLES #F0C9A8, DUSTY_PINK_TYPE #C98B96, ROSE_GOLD_PLACEHOLDER #B76E79, WARM_GREY_SUPPORTING_TEXT #8A7F78) + WHITE_TYPE_HIGHLIGHT #FDFBF7, SOFT_MINT_WASH #E8F5F0. Every named swatch becomes a CMYK fill in the emitted .ai/.pdf (`pdf_ai._rl_color` prefers the CMYK override). The language is chosen by `resolve_language` — lexical matching of the approved variation's text against each language's keywords — never by a colour record. | **No.** The hexes duplicate the seeded ColorSystems by value (#E8C9B3/#F0DECB = "Nude Warm"; #FAF3EC/#F2C4CE = "Blush Core") but are literals; `ColorSystem` is not read here. |
| `apps/pipeline/targets/container/__init__.py:29–30, 1005–1082` | #C9A24B cap default, #EAD7D2 body default, #F2C4CE product fallback, #D8BEB8/#B76E79/#C9A6A0 dropper defaults | The container target's `colors` dict: body = `dominant_color_hex(concept_path)` — the **median border colour of the approved concept render** (an AI-generated image), overridden by an explicit hex found by regex in the CONFIRMED profile's `cap_color` / `body_base_color` fields ("concept authority"); defaults otherwise. These feed the composer's material stack and the transparency record. | **No** governance record: the source is the concept image + the profile's free-text fields. |
| `apps/ire/compose_container.py:135–138, 336, 873–930` | _INK #3F2620, ink #5A2C3A (direct print), material stack defaults, #FFFFFF, #FDF7F2 | The container sheet's fills: ink for live text, the frosted-bottle material objects (body/product/collar/bulb), white highlights. | No. |
| `apps/ire/compose_dropper.py:50–71, 207–246, 772, 945` | _INK #2A2426; a **material stack with named authorities** — BODY_BASE #D8BEB8 "PROCESS", PRODUCT_FILL #C9A6A0, GLASS_BASE #EFE8E3, ROSE_GOLD_BASE #BC7480 "METALLIC SPOT", ROSE_GOLD_LIGHT #EBD0BC, ROSE_GOLD_SPECULAR #FDEFE4 "NONPRINTING viz", ROSE_GOLD_SHADOW #6E3A46, BULB_DARK_PLUM #3F2A33, TYPE_WINE #5A2C3A "authority UNVERIFIED"; highlights #B79B95/#A98D88, washes #F4E9E4, page ground #F7F1EC, #8E4F5C | The dropper sheet (the WI-U/Y/V/K evidence surface): every material object of the frosted bottle and its closure, the live type, the page ground. Each literal carries a one-line authority note in the source — the closest thing to a colour record the composers have, and it names its own authority as UNVERIFIED. | No governance record; the notes are literals beside the values. |
| `apps/ire/compose.py:42–55, 265` and `apps/ire/nodes.py:62` | _TINT #EFE9E4; CUT #0000FF; FOLD #FF0000; WHITE; _INK_LIGHT #FCF8F5; ink #F7F0E6 / #59283A by luminance | The carton composer: the panel tint behind artwork, the die lines as CMYK process (cyan / red), the ink picked by the panel's luminance. | No. |
| `apps/ire/handoff/graph_schema.py:68–73` | CUT #FF0000, CREASE #0000FF, SPOT_UV #00A0A0, EMBOSS #808000, DEBOSS #606060, ROSE_GOLD_FOIL #B76E79 (each with CMYK) | The 2A handoff graph's **process layers** — named finishing swatches in the handoff, not printed colours. | No (process vocabulary by design). |
| `apps/ire/back_panel.py:359`, `apps/ire/handoff/container_adapter.py:193, 299` | #2A2426 back-panel ink; #555555 / #888888 adapter fallbacks | Back-panel copy ink; adapter placeholder colours. | No. |
| `apps/ire/emitters/pdf_ai.py:441, 554–556, 611–638` | CMYK(0,0,0,1) black; `_rl_color` | **The emitter**: every `Color` becomes a CMYK fill/stroke when it carries `cmyk`, else an RGB fill (the screen fallback). Black text is forced CMYK ink. This is the point where a colour becomes an operator in the artefact. | No — it emits what the graph carries. |
| `apps/dielines/exporters/production_pdf.py:60–69, 344, 550` | CUT = Separation "CutContour"; CREASE = "Crease"; BLEED/SAFE process greys; INK CMYK black; a cream fill RGB(0.985,0.973,0.960); a red RGB(0.75,0,0) flag | The **production dieline PDF** (Phase 2A): die plates as spot separations, guides as process grey, the info panel's ink as CMYK black. | No colour record (structural vocabulary). |
| `apps/dielines/exporters/info_panel.py` (12 hex), `svg_exporter.py` (8), `design_preview.py` (7 + `drawImage`), `attachment_overlay.py` (20), `folded_diagnostic.py` (13), `physical_test_pdf.py` (14 calls), `structural_comparison.py` (10) | greys, reds, greens, blues | The regulatory sticker and its SVG twin (ink and panel tones); the design-on-dieline preview (composites the approved concept artwork, the motif and the logo onto the panels); the attachment / folded / structural **diagnostic** overlays (review colours, not print). | No. The sticker's ink is fixed; the preview's colours come from the composited images. |
| `apps/pipeline/services/spec_sheet.py:22–25, 120, 158, 181` | BBROSE_BLUSH #F2C4CE, BBROSE_ROSE_GOLD #B5895A, BBROSE_DARK #1A1A1A, BBROSE_CREAM #F5EDD6, greys | The reportlab **spec sheet** PDF's chrome (headings, rules, grid). Brand-looking constants, hardcoded. | No. |
| `apps/pipeline/services/flat_artwork.py:156`, `artwork_segments.py:37` | #EFE9E4 default | `dominant_color_hex` — the border colour measured from the concept packshot; the panel fill around the placed artwork. | No — the source is the generated image. |
| `apps/pipeline/services/palette_powder_engine.py:62–75, 787` (PALT-M6) | none hardcoded per shade; the **twelve owner-chosen hexes** enter through `es3083_owner_shade_set` from the owner's rows | The powder shades of the ES3083 palette: each shade carries a named **colour authority** (`OWNER_CHOSEN_DESIGN_INTENT` → reported `OWNER_DESIGN_INTENT_NOT_MEASURED`; `PROVISIONAL_VISUALIZATION_SHADE`). The sRGB triple is the stored authority; Pantone / measured tiers are deliberately absent. | **Yes — the owner's shade record**, with its authority named on every shade. The precedent for the proposal. |
| `apps/pipeline/services/palette_material_engine.py:90–91, 153, 288–323` | PANTONE_621C (0.72,0.80,0.74), PANTONE_627C (0.16,0.30,0.24) display proxies; neutral tuples | Display proxies for the substrate spot colours in renders and boards. | The substrate record names the PANTONEs; the RGB proxies are literals. |
| `apps/pipeline/services/palette_m7_ai_emitter.py:42–48, 98–107` | SPOT_BY_RGB: (207,224,216) = PANTONE 621 C; (17,50,44) = PANTONE 627 C; white; any other value **raises** | The **M7 artefacts** (six .ai emissions + two label sheets): every colour of the locked SVG artwork is mapped to a recorded spot authority or refused. | **Yes — the substrate record**; no value invented. |
| `apps/core/management/commands/seed_bbrose.py:82–160` | the brand_gov palettes as data: "Blush Core" CS-001 (#F2C4CE Primary, #F7DDE3 Secondary, #8B3A52 Accent, Rose Gold "Metallic 10122 C", #FAF3EC Ground) and "Nude Warm" CS-002 (#E8C9B3, #F0DECB, …) | Seeds `ColorSystem.palette` — the governance record itself. | It IS the record. |
| Diagnostic / one-off (not a production path): `apps/ire/vq1_render.py` (9), `vq1_reset2.py` (9), `vq1_corr4.py` (6), `vq1_corr5.py` (8), `vq1_master.py` (4), `vq1_close1_package.py` (3), `vq2_artwork.py` (2), `gate_a_corr1.py` / `gate_a_corr2.py` (5 each), `gate_a_final.py`, `gate_a_roundtrip1.py`, `ai8_color.py` (3: the AI8 colour-fidelity checks, e.g. #D9BDB5), `image_checks.py` (1), the Blender scripts (`palette_csg_views.py` 8, `m4b_a_tray_views.py` 6, `validation_views.py` 3, `powder_materials.py` 3, `p1_material_studio.py` 2), `direction_content.py:404` (a docstring) | — | Review renders, correction passes and board colours. Not on a client or printer path. | No. |

**The brand_gov record and who reads it.** `apps/core/models.py:28` `ColorSystem.palette` is a JSON list of `{role, name, hex, pantone, usage}` per canonical system; `Product.color_system` links a product to one. Readers (non-test): `brand_context.build_brand_context` (the palette printed into the Creative Director's prompt text), `brand_context.get_brand_hexes` → `image_checks.palette_distance` (the QA reviewer's palette-distance check on generated images), `pacdora_agent` (`spec["color_codes"] = product.color_system.palette`, the quarantined Pacdora path), `creative_director` (a sanity check that a direction names a real ColorSystem). **No deterministic composer or emitter reads `ColorSystem`.** The record reaches outputs only through the language model's prompt and through a post-hoc distance check.

**Summary of (1), static:** the engine's deterministic colours are literals in the design language (14 named swatches), the container target's defaults plus a colour *measured* from the approved concept render, the carton composer's tint/ink/die colours, the dieline exporters' process vocabulary, the spec sheet's constants, and the PALT engine's owner-chosen shades. The only points that consult a governance record when choosing a colour are the PALT powder engine (the owner's shade record with a named authority) and the M7 emitter (the substrate's spot record). The brand_gov palettes are consulted by the prompt builder and the QA check, never by a fill.

### 1b. The runtime search shape — what real artefacts actually carry

Extent: **every tracked artefact under `docs/` — 259 files** (68 `.ai`, 98 `.pdf`, 93 `.svg`; the list is `~/bh38_work/artefacts_tracked.txt`): the six M7 emissions and their label sheets, the visual-quality review packages (vq1…vq3, the WI evidence surfaces), the qualification dielines and physical-pilot PDFs, the production-authority package, the roadmap boards. Read-only through PyMuPDF `get_drawings()` (every vector fill and stroke, with its area) and the text spans (their ink), SVGs through their `fill=`/`stroke=` attributes; the census is `~/bh38_work/artefact_fills.json`. **248 parsed; 11 could not be opened** — the AI8-format (PostScript) `.ai` fixtures and lettering files under `visual_quality/vq2` (a stated limit: PyMuPDF reads PDF-compatible `.ai` only). Each fill is then mapped back to the code point that names it — exact hex, else ΔE76 ≤ 2.5 to a governed literal of §1a — so the table answers "what does this point resolve to on a real document" by measurement, not by reading the code alone.

| Artefact family | files | distinct fills | fills mapped to a code point (hex → point, ΔE) | unmapped fills (hex × files) | text inks | images |
|---|---|---|---|---|---|---|
| M7 ai_emission | 6 | 4 | `#CFE0D8`→M7/PANTONE 621 C (substrate record) (0.0); `#FFFFFF`→compose_container/white (0.0); `#141614`→M7 boards (palette_m6_products title ink 20,22,20) (0.0) | `#787878`×1 | `#11322C`×5, `#141614`×2, `#FFFFFF`×1, `#787878`×1 | 0 |
| M7 back_label | 1 | 4 | `#FFFFFF`→compose_container/white (0.0); `#141614`→M7 boards (palette_m6_products title ink 20,22,20) (0.0); `#11322C`→M7/PANTONE 627 C (substrate record) (0.0) | `#787878`×1 |  | 0 |
| M7 label_sheet | 7 | 2 | `#141614`→M7 boards (palette_m6_products title ink 20,22,20) (0.0); `#11322C`→M7/PANTONE 627 C (substrate record) (0.0) |  | `#141614`×2 | 0 |
| M7 lid_artwork | 5 | 4 | `#11322C`→M7/PANTONE 627 C (substrate record) (0.0); `#CFE0D8`→M7/PANTONE 621 C (substrate record) (0.0); `#FFFFFF`→compose_container/white (0.0); `#141614`→M7 boards (palette_m6_products title ink 20,22,20) (0.0) |  |  | 0 |
| docs/production_authority | 4 | 0 |  |  | `#000000`×4 | 0 |
| docs/research | 1 | 1 | `#888888`→container_adapter/placeholder (0.0) |  |  | 0 |
| docs/roadmap | 22 | 6 | `#CFE0D8`→M7/PANTONE 621 C (substrate record) (0.0); `#11322C`→M7/PANTONE 627 C (substrate record) (0.0); `#C9A24B`→container/_DEFAULT_CAP_HEX (0.0); `#979798`→spec_sheet/timestamp (0.9); `#D1D1D1`→spec_sheet/grid (0.4) | `#17171B`×2 | `#3F2620`×2, `#F7F0E6`×2 | 6 |
| qualification/physical_pilot_1_2 | 6 | 1 |  | `#E0E0E0`×6 | `#BF0000`×6, `#737373`×6, `#000000`×6 | 0 |
| qualification/reference_opposed_tuck_carton_0_1 | 12 | 0 |  |  |  | 0 |
| qualification/reverse_tuck_end_carton_1_1 | 11 | 0 |  |  |  | 0 |
| qualification/reverse_tuck_end_carton_1_2 | 10 | 0 |  |  |  | 0 |
| qualification/skynte_foundation_tuck_carton_1_0 | 10 | 0 |  |  |  | 0 |
| qualification/straight_tuck_end_carton_1_1 | 10 | 0 |  |  |  | 0 |
| qualification/straight_tuck_end_carton_1_2 | 10 | 0 |  |  |  | 0 |
| visual_quality/ba4_grounds | 5 | 5 | `#EAD7D2`→container/_DEFAULT_BODY_HEX (0.0); `#C9A24B`→container/_DEFAULT_CAP_HEX (0.0); `#FBF7F6`→compose/_INK_LIGHT (1.1); `#F6EDEB`→DIAG vq1_reset2/F4EEEA (1.5); `#F9EFE2`→DEFAULT/LINE_LIGHT (1.3) |  | `#3F2620`×3, `#59283A`×2, `#000000`×1, `#5A2C3A`×1 | 8 |
| visual_quality/complete_product | 1 | 0 |  |  | `#1D1B1E`×1, `#2A2426`×1, `#9C1F1F`×1, `#000000`×1 | 7 |
| visual_quality/rbv | 4 | 0 |  |  |  | 4 |
| visual_quality/vq1 | 2 | 10 | `#D8BEB8`→compose_container/dropper body (0.0); `#B79B95`→compose_dropper/highlight B79B95 (0.0); `#A98D88`→compose_dropper/highlight A98D88 (0.0); `#FFFFFF`→compose_container/white (0.0); `#F4E9E4`→compose_dropper/glass wash (0.0); `#EFE8E3`→compose_dropper/GLASS_BASE (0.0); `#EBD0BC`→compose_dropper/ROSE_GOLD_LIGHT (0.0); `#FDEFE4`→compose_dropper/ROSE_GOLD_SPECULAR (0.0) … |  | `#2A2426`×2 | 0 |
| visual_quality/vq1_corr2 | 2 | 9 | `#E9E2DE`→DIAG vq1_render/E9E2DE (0.0); `#B9AEA9`→DIAG vq1_render/B9AEA9 (0.0); `#A79B96`→DIAG vq1_render/A79B96 (0.0); `#DDD3CE`→DIAG vq1_render/DDD3CE (0.0); `#C8B8B2`→DIAG vq1_render/C8B8B2 (0.0); `#B5A29B`→DIAG vq1_render/B5A29B (0.0); `#9B8880`→DIAG vq1_render/9B8880 (0.0); `#6B5A57`→DIAG vq1_render/6B5A57 (0.0) | `#CFC5C0`×2 | `#2A2426`×2 | 4 |
| visual_quality/vq1_corr3 | 2 | 8 | `#E9E2DE`→DIAG vq1_render/E9E2DE (0.0); `#B9AEA9`→DIAG vq1_render/B9AEA9 (0.0); `#A79B96`→DIAG vq1_render/A79B96 (0.0); `#DDD3CE`→DIAG vq1_render/DDD3CE (0.0); `#C8B8B2`→DIAG vq1_render/C8B8B2 (0.0); `#B5A29B`→DIAG vq1_render/B5A29B (0.0); `#9B8880`→DIAG vq1_render/9B8880 (0.0); `#6B5A57`→DIAG vq1_render/6B5A57 (0.0) |  | `#2A2426`×2 | 6 |
| visual_quality/vq1_corr4 | 6 | 1 | `#F5F2EF`→compose_dropper/page ground (1.5) |  | `#2A2426`×4 | 2 |
| visual_quality/vq1_corr5 | 14 | 4 | `#F5F2EF`→compose_dropper/page ground (1.5); `#D6CCC6`→DIAG vq1_reset2/DCD1CA (1.9) | `#C4B4A6`×2, `#5A484F`×2 | `#2A2426`×14 | 12 |
| visual_quality/vq1_it5_audit | 2 | 1 | `#F5F2EF`→compose_dropper/page ground (1.5) |  | `#2A2426`×2, `#A8382C`×2, `#2F6F4F`×2 | 10 |
| visual_quality/vq1_it6_review | 2 | 1 | `#F5F2EF`→compose_dropper/page ground (1.5) |  | `#2A2426`×2, `#A8382C`×2, `#7A5C2E`×2, `#2F6F4F`×2 | 6 |
| visual_quality/vq1_master | 9 | 5 | `#FFFFFF`→compose_container/white (0.0); `#9A9A9A`→spec_sheet/timestamp (0.4) | `#333333`×1, `#DCDCDC`×1, `#4A4A4A`×1 | `#000000`×3, `#1D1B1E`×2, `#2A2426`×2, `#9C1F1F`×2 | 16 |
| visual_quality/vq1_reset1 | 2 | 1 | `#F5F2EF`→compose_dropper/page ground (1.5) |  | `#2A2426`×2 | 0 |
| visual_quality/vq1_reset1a | 6 | 1 | `#F5F2EF`→compose_dropper/page ground (1.5) |  | `#2A2426`×6, `#A8382C`×4 | 0 |
| visual_quality/vq1_reset1b | 13 | 67 | `#FFFFFF`→compose_container/white (0.0); `#F5F2EF`→compose_dropper/page ground (1.5); `#030404`→production_pdf/INK (1.1); `#000000`→production_pdf/INK (0.0); `#D0D2D3`→spec_sheet/grid (1.1); `#191919`→spec_sheet/BBROSE_DARK (0.5); `#666666`→graph_schema/DEBOSS (2.5); `#999999`→spec_sheet/timestamp (0.0) … | `#120C0D`×2, `#A30046`×2, `#231E21`×2, `#666767`×2, `#0B2128`×2, `#DCDDDE`×2, `#DEDCDC`×2, `#EED3D5`×2 … | `#FFFFFF`×7, `#231F20`×6, `#2A2426`×6, `#A8382C`×6 | 381 |
| visual_quality/vq1_reset2 | 10 | 2 | `#FFFFFF`→compose_container/white (0.0); `#F5F2EF`→compose_dropper/page ground (1.5) |  | `#2A2426`×4, `#A8382C`×4, `#2F6F4F`×2 | 14 |
| visual_quality/vq2 | 44 (errors 11) | 15 | `#502525`→DIAG gate_a (AI8 approved pixels)/502525 (0.0); `#D9BDB5`→DIAG gate_a/D9BDB5 (0.0); `#705242`→DIAG gate_a/705242 (0.0); `#493034`→DIAG gate_a/493034 (0.0); `#000000`→production_pdf/INK (0.0) | `#70D0EC`×6, `#512E27`×6, `#3CB44B`×2, `#4C281F`×2, `#E6194B`×1, `#F58231`×1, `#FFE119`×1, `#4363D8`×1 … | `#1D1B1E`×12, `#2A2426`×12, `#9C1F1F`×12, `#000000`×12 | 54 |
| visual_quality/vq3 | 2 | 0 |  |  | `#1D1B1E`×2, `#2A2426`×2, `#9C1F1F`×2, `#000000`×2 | 10 |
| visual_quality/wim_front_true_scale | 6 | 14 | `#F7F1EC`→compose_dropper/page ground (0.0); `#D8BEB8`→compose_container/dropper body (0.0); `#B79B95`→compose_dropper/highlight B79B95 (0.0); `#A98D88`→compose_dropper/highlight A98D88 (0.0); `#FFFFFF`→compose_container/white (0.0); `#F4E9E4`→compose_dropper/glass wash (0.0); `#EFE8E3`→compose_dropper/GLASS_BASE (0.0); `#EBD0BC`→compose_dropper/ROSE_GOLD_LIGHT (0.0) … |  | `#5A2C3A`×6, `#3A2A30`×1, `#2A2426`×1, `#8E4F5C`×1 | 0 |
| visual_quality/wiu_front_collision | 6 | 0 |  |  | `#5A2C3A`×6, `#3A2A30`×1 | 0 |
| visual_quality/wiv_leading | 4 | 0 |  |  | `#5A2C3A`×4, `#3A2A30`×1 | 0 |
| visual_quality/wiy_leading_floor | 2 | 0 |  |  | `#5A2C3A`×2, `#3A2A30`×2 | 0 |

**What the runtime shape shows.** Every fill on a client- or printer-bound artefact traces to a literal of §1a: the M7 emissions carry exactly the two substrate PANTONE proxies plus white (the recorded-vocabulary emitter, no other value); the dropper evidence surfaces (WI-M/U/V/Y) carry the dropper composer's material stack and its page ground `#F7F1EC`, and their inks the TYPE_WINE `#5A2C3A`; the BA4 grounds carry the container target's defaults (`#EAD7D2`, `#C9A24B`) and the design language's LINE_LIGHT; the roadmap boards carry the M7 proxies and the spec sheet's greys. Nothing on these artefacts came from a brand_gov `ColorSystem` swatch by name: the closest a brand hex comes to an artefact is the container fallback `#F2C4CE` and the design language's duplicates, which are literals. The unmapped fills are the review renders' greys (vq1 corrections), the AI8 approved-pixel set of the Gate A one-offs, and computed tints; none is on a production path.

## 2. The resolution as it is, materials (goal 2)


Extent, static shape: the same 571 modules, grep `material_points.txt` (Image.open / paste / alpha_composite / composite / drawImage / ImageReader / texture / mockup / smart object / .psd / stock / materials/ / reference_image / background_image / blend) — **532 lines in 61 modules**, read module by module. Runtime shape: the same artefact set as §1b (the placements are visible as image XObjects in the emitted PDFs and as `<image>` elements in the SVGs).

**Points that place or composite an external raster into an output:**

| Point (file:line) | What is placed | Where the asset comes from | Any governed library consulted? |
|---|---|---|---|
| `apps/ire/compose.py:177–183` → `Image` nodes `motif-<panel>` / `motif-<panel>-el<i>` | The carton's decorative raster per panel (the full-face front artwork or the text-free motif, or its segmented elements) | `media/` — images generated by the image model for THIS task (`flat_artwork.make_flat_artwork`, `artwork_segments`); never a library file | **No.** |
| `apps/ire/compose_vector_art.py:445` → `Image` node `logo-front-…` | The brand logo raster as the one controlled fallback | `settings.BRAND_LOGO_PATH` (= `media/brand/logo.png`) or the task's uploaded logo | No — a fixed brand asset. |
| `apps/ire/emitters/pdf_ai.py:254, 531–545` `_draw_image` | Any `Image` node becomes an embedded raster XObject in the .ai/.pdf ("no embedded raster except an explicit Image node") | whatever `node.src` names | No — the emitter embeds what the graph carries. **This is the seam a PRODUCTION material would pass through.** |
| `apps/dielines/exporters/design_preview.py:137, 319–387` `drawImage` | The Gate-1-approved concept artwork, the motif, the artwork segments and the logo composited onto the dieline panels (a reviewer's preview PDF, and its .ai twin) | `media/` generated images + the logo | No. |
| `apps/dielines/exporters/mockup_3d.py:41, 123, 134` | The flat design preview PNG warped into an isometric "erected carton" PNG (paste with mask onto a generated background) | the exporter's own preview PNG | No — a synthesized mockup, not a library scene. |
| `apps/pipeline/services/flat_artwork.py:162, 188` | Opens the concept packshot to measure its border colour and to lift a motif; writes derived PNGs into `media/` | the generated packshot | No. |
| `apps/pipeline/services/image_checks.py` | Opens generated images for QA (palette distance to `get_brand_hexes`, ratio) | generated images | Reads `ColorSystem` hexes for the check — a check, not a placement. |

**Points that reference an external asset for inspiration (read, never placed):**

| Point | What is read | From where | Governance consulted? |
|---|---|---|---|
| `apps/pipeline/services/concept_references.py:167–225` `_material_candidates` | Displayable rasters (.png/.jpg/.jpeg/.webp) of DIP-0A category PATTERN / BACKGROUND / MOTIF / RASTER_DESIGN_ASSET / REUSABLE_VECTOR_ASSET / ICON, scored by filename tokens against the brief, at most 4 per task, streamed to the Creative Director as `ConceptReference` candidates (a user must APPROVE 2–4; `production_use_allowed` is structurally False; the influence plan carries principles and no locator) | **`var/design_intelligence/audits/dip0/inventory/inventory.jsonl`** — the DIP-0A inventory, resolved against `MATERIALS_ROOT` read-only | Reads the inventory's `ownership_status` and `license_status` into the candidate row. **Does not read the tier record** (`materials_tiers.jsonl`, §BH37): a REFERENCE-tier and a PRODUCTION-tier file are candidates alike, and a file's tier is invisible at approval. |
| `apps/pipeline/services/concept_references.py:114–165` `_historical_candidates` | `DesignReference` rows (the house production-file index: the owner's own historical designs imported into `media/`) | `media/` | The house library; no tier (owner-owned). |
| `apps/pipeline/services/reference_index.py` `tag_reference` / `select_references` | A one-time vision tag per imported reference (category, product type, motifs, finishes, **palette as colour words**, summary) and product-aware selection of the best PNGs for the Creative Director | `media/` + a model call | No. The "palette" is words, never a hex. |
| `apps/pipeline/services/container_material_influence.py` / `container_material_realization.py:84` | Per approved reference, which dimensions (palette, typography, motif, …) it may influence; realization = "named swatches emitted" for palette | the influence plan | No colour value crosses: palette influence is REALIZED when the composer emits any `swatch-*` node, whatever its colour. |

**Points that do not exist today (said exactly):** there is **no** point where the engine places a library mockup scene, fills a smart object, applies a texture or background from `materials/`, or embeds stock imagery. No module opens a `.psd` (psd-tools is not a dependency of the engine; the census's PSD measurement lives in `~/bh35_work/`'s tooling). No module reads `materials_tiers.jsonl`. The word "mockup" in the engine names the synthesized isometric carton only. The word "texture" names an influence dimension and a Blender shader parameter, never a file.

**The first placement point, named (for the proposal):** the IRE `Image` node → `pdf_ai._draw_image` seam is the only path by which a raster reaches a client artefact, and `compose.py:177` / `compose_vector_art.py:445` are its only two callers. A PRODUCTION material would enter as an `Image` node authored by a composer, with its tier row and credit condition attached to the node's record — the proposal's §4b. The first consultation point for REFERENCE materials is `concept_references._material_candidates`, which already reads the DIP-0A inventory and only needs the tier record beside it.

## 3. What the libraries offer, tier-split (goal 3)

### 3a. Colours the libraries offer, by source pack and tier

Extraction is by STRUCTURE only (the §BH35 rule — never guessed from pixels): Illustrator/Photoshop **XMP swatch groups** (`xmpTPg:SwatchGroups`, named document swatches, CMYK/RGB/GRAY converted to hex without an ICC profile — an approximation), the one **.ase** swatch file (RGB, exact), **SVG declared colours** (exact), **PDF separations** and XMP **spot swatches** (PANTONE names — no hex invented), and **DSC custom colours** in EPS prologs (CMYK, approximated). Tier = the row of the tier record at HEAD.

**PRODUCTION (embeddable) — 1 colour-bearing pack** (of the 16 PRODUCTION rows, only the layered .ai carries structural colour; the rasters carry pixels, which the rule does not read):

| Pack | Files with swatches | Process swatches (hex, CMYK→sRGB approx.) | Spot swatches (names) |
|---|---|---|---|
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits | 2 | `#231F20`×4, `#ED1C24`×4, `#FFFFFF`×2, `#FFF200`×2, `#00A651`×2, `#00AEEF`×2, `#2E3192`×2, `#EC008C`×2, `#BE1E2D`×2, `#EF4136`×2, `#F15A29`×2, `#F7941E`×2, `#FBB040`×2, `#F9ED32`×2, `#D7DF23`×2, `#8DC63F`×2 | PANTONE 1345 C, PANTONE 7411 C, PANTONE 7412 C, PANTONE 178 C, PANTONE Warm Red C, PANTONE 7527 C, PANTONE 3025 C, PANTONE 3035 C, PANTONE 303 C, PANTONE 179 C, PANTONE 180 C, PANTONE 181 C |

**REFERENCE (inspiration only) — 410 colour-bearing packs**: 406 with XMP swatch groups, 42 with spot swatches, 31 with PDF separations, 1 with SVG colours, 1 with an .ase file, 6 with DSC custom colours. Illustrator's default swatch set (White, Black, CMYK Red …) dominates the XMP counts; the packs' OWN swatches are the spot names and the non-default process colours. Top packs by structural colour count:

| Pack | Files w/ swatches | Distinct process hex | Spot names (top) | Separations (top) | Other |
|---|---|---|---|---|---|
| 17-10-2024 | 28 | 60 | PANTONE 7408 C, PANTONE 2612 C, PANTONE 189 C, PANTONE 7653 C, PANTONE 1345 C | Black, Magenta, Yellow, Cyan, PANTONE 1345 C | .ase: `#FAB4BF`, `#FFD2C7`, `#FFF1DD`, `#FFE2E8`, `#F8FFB5` |
| 17-10-2024/Telegram Desktop | 19 | 60 | PANTONE 494 C, PANTONE 9243 C, PANTONE 9243 U, PANTONE 7432 C, PANTONE 305 C | PANTONE 494 C, Black, PANTONE 9243 C, Yellow, Magenta |  |
| ALL..MOCKUP/27-4-2024 | 5 | 56 | PANTONE 293 C, PANTONE Reflex Blue C, PANTONE 1585 C, PANTONE 802 C | PANTONE 293 C, PANTONE Reflex Blue C, PANTONE 1585 C, PANTONE 802 C | SVG: `#000000`, `#E8E8E8`, `#030303`, `#F1F1F1`, `#E5E5E5`, `#010101` |
| 17-10-2024/abstract-boho-contemporary-cover-collection | 1 | 60 | ANPA 754-0 AdPro, ANPA 703-0 AdPro, ANPA 703-6 AdPro, ANPA 703-8 AdPro, ANPA 757-0 AdPro |  | DSC: `#FF9172` ANPA 756-8 AdPro |
| 17-10-2024/Telegram Desktop/BOTTLEتعديل لون/BOTTLEتعديل لون | 20 | 60 | PANTONE Orange 021 C, PANTONE 318 C, PANTONE 134 C, PANTONE Yellow 0131 C, PANTONE 494 C | PANTONE 134 C, Black, Magenta, Yellow, PANTONE 494 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face wac | 1 | 55 | PANTONE Orange 021 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day crea | 1 | 55 | PANTONE 189 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C | Black, Cyan, Magenta, PANTONE 1345 C, PANTONE 1665 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/LIP PALM | 1 | 56 | PANTONE 7408 C, PANTONE 7653 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/day crea | 1 | 55 | PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C, PANTONE 7408 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/hair oil | 1 | 55 | PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C, PANTONE 7408 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/SUN SCRE | 1 | 55 | PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C, PANTONE 1345 C, PANTONE 7408 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/FACE OIL | 1 | 55 | PANTONE 2612 C, PANTONE 1345 C, PANTONE 486 C, PANTONE 189 C, PANTONE 635 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/face ser | 1 | 55 | PANTONE 189 C, PANTONE 486 C, PANTONE 7408 C, PANTONE 7653 C, PANTONE 2612 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |
| 17-10-2024/Telegram Desktop/skin care لورنزا/skin care لورنزا/NIGHT DA | 1 | 55 | PANTONE 7408 C, PANTONE 7653 C, PANTONE 1665 C, PANTONE 635 C, PANTONE 2612 C | Black, Magenta, PANTONE 1345 C, PANTONE 1665 C, PANTONE 189 C |  |

Across REFERENCE: **145 distinct spot swatch names** (top: PANTONE 1665 C ×25, PANTONE 7408 C ×24, PANTONE 2612 C ×24, PANTONE 189 C ×24, PANTONE 7653 C ×24, PANTONE 1345 C ×24, PANTONE 486 C ×24, PANTONE 635 C ×24); **53 distinct separation colorants** (top: Yellow ×52, Magenta ×51, Black ×50, PANTONE 1345 C ×24, PANTONE 1665 C ×24, PANTONE 189 C ×24); **1926 distinct process hexes** — the whole list is in `~/bh38_work/libraries.json`. The one .ase file (`17-10-2024/AdobeColor Spring Peach.ase`, REFERENCE) carries `#FAB4BF #FFD2C7 #FFF1DD #FFE2E8 #F8FFB5`.

### 3b. Materials the libraries offer, by tier

**PRODUCTION (16 rows — the assets the channel raised; each carries its pack's evidence and, for the Freepik packs, the credit condition):**

| File | Kind | Canvas / page | Colour mode, depth, dpi | Layers / smart objects / replaceable-by-name | Profile |
|---|---|---|---|---|---|
| 17-10-2024/pile-online-shopping-package-mockups/65757.psd | PSD (layered mockup) | 5000×3337 px | RGB, 16-bit, 300 dpi | 2 / 1 / — | — |
| ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.psd | PSD (layered mockup) | 3600×2400 px | RGB, 8-bit, 300 dpi | 8 / 1 / REPLACE THIS SCREEN | — |
| ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512866.psd | PSD (layered mockup) | 4800×3000 px | RGB, 8-bit, 300 dpi | 18 / 2 / Place your design here (Double click to , Place your design here (Double click to  | — |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTKC-8.ai | AI (PDF-compatible) | 176.39×176.39 mm | — | images on page 0: 0; separations: none | — |
| ALL..MOCKUP/27-4-2024/fonts bold/coolvetica/Typodermic Desktop EULA 2023.pdf | PDF vector | 215.9×279.4 mm | — | fonts: ArialMT, Calibri, Calibri-Bold; separations: none | — |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK5-790.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.eps | EPS vector | (EPS: no page box read) | — | fonts: —; separations: none | — |
| 17-10-2024/pile-online-shopping-package-mockups/65757.jpg | JPEG raster | 5000×3337 px | RGB, dpi 300 | — | Adobe RGB (1998) |
| ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/130.jpg | JPEG raster | 3600×2400 px | RGB, dpi 300 | — | Adobe RGB (1998) |
| ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/2512865.jpg | JPEG raster | 4800×3000 px | RGB, dpi 300 | — | sRGB IEC61966-2.1 |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/116297-OPHTK7-614.jpg | JPEG raster | 2000×2000 px | RGB, dpi — | — | sRGB IEC61966-2.1 |
| ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set-with-mascara-powder-isolated-vector-illustration/16260.jpg | JPEG raster | 4500×4500 px | RGB, dpi 100 | — | none |
| ALL..MOCKUP/عبوات مواد تجميل/nail-polish/7077.jpg | JPEG raster | 4500×4500 px | RGB, dpi 100 | — | none |
| ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/18207.jpg | JPEG raster | 4500×4500 px | RGB, dpi 720 | — | none |

**REFERENCE (inspiration only):**

- **Layered PSD: 454 files** — 380 with ≥1 smart object, 391 with a replaceable-by-name layer ("Place your design here", "REPLACE THIS SCREEN" …); modes RGB 403, GRAYSCALE 50, CMYK 1; depth 8-bit 439, 16-bit 15; dpi 300 ×250, 72 ×123, 48 ×50, 240 ×20; canvases (top) 256×256 ×50, 4000×3000 ×39, 5376×3584 ×21, 3584×5376 ×18, 3333×5000 ×9; 309 at ≥ 12 Mpx; median 14 layers.
- **Layered AI (PDF-compatible): 362 files** — 100 carry separations (spot plates), 116 carry a placed image on page 0; page sizes (top) 176×176 mm ×92, 265×176 mm ×32, 210×297 mm ×30, 307×220 mm ×26.
- **Vectors: 1408 files** — .ai 680, .eps 656, .svg 53, .pdf 17; 8 with separations.
- **Rasters: 2079 files** — modes RGB 1949, RGBA 101, P 28, CMYK 1; 1351 with a long side ≥ 3000 px; 856 declare ≥ 300 dpi; embedded profiles none 1217, sRGB IEC61966-2.1 478, Adobe RGB (1998) 332, Generic RGB Profile 19.
- Not in the record: 1 vector row (`ADOBE STOCK/girls makeup/~ai-…_.tmp`, a junk name the walk never admits).

### 3d. The owner's own designs — colour usage of the 254 design PDFs, by structure

Extent: the owner's **254 design PDFs** = the §BH28 extraction's 226 `.ai` (PDF-compatible) + 28 `.pdf` — 91 under `materials/historical AI production designs`, the rest under `materials/DOWNLOADE 2026` (the office archive, the internet samples, the downloads) — all 254 present and parsed (`~/bh38_work/design_pdf_colours.json`); the 122 `.eps` of the same extraction are PostScript and were not read (limit). Method, by structure: on page 0 every vector fill weighted by its drawn area and every text span by its glyph area (PyMuPDF); a fill covering ≥ 90 % of the page is the **artboard backdrop**, not the design (168 files carry one — `#232424` in 67 of the 91 historical designs, white in 47, `#FFFEFA` 4, black 4), and is set aside; the **dominant** is then the largest remaining fill, the **accents** the next fills at ≥ 3 % of the drawn area, the **ink** the largest text colour. Raster content is counted, never sampled: 50 files are raster-dominated (a placed image ≥ 50 % of the page — packshots and mockups), 12 expose no vector fill at all, 68 carry live text. Across files the colours are clustered at ΔE76 ≤ 8 and each cluster mapped to the nearest brand_gov swatch and the nearest design-language swatch with its ΔE (`~/bh38_work/design_roles.json`).


**DOMINANT** — clusters (ΔE76 ≤ 8) ranked by files led:

| # | centre | files | nearest brand_gov swatch (ΔE) | nearest design-language swatch (ΔE) |
|---|---|---|---|---|
| 1 | `#F2E8E2` | 61 | CS-001 Blush Core / Ground Warm Cream (3.8) | DEFAULT/LINE_LIGHT (3.4) |
| 2 | `#CBA87D` | 24 | CS-002 Nude Warm / Primary Warm Nude (17.0) | DEFAULT/LINE_DEEP (10.4) |
| 3 | `#FFFFFF` | 22 | CS-001 Blush Core / Ground Warm Cream (5.8) | WHITE_TYPE_HIGHLIGHT (2.5) |
| 4 | `#000000` | 17 | CS-002 Nude Warm / Accent Cocoa Rose (43.7) | DEFAULT/INK (34.2) |
| 5 | `#EEC7CE` | 12 | CS-001 Blush Core / Primary Blush (3.1) | POWDER/BLUSH_PINK (3.1) |
| 6 | `#1D1D1B` | 11 | CS-002 Nude Warm / Accent Cocoa Rose (35.0) | DEFAULT/INK (28.4) |
| 7 | `#DDC8B7` | 6 | CS-002 Nude Warm / Primary Warm Nude (5.0) | DEFAULT/GROUND_TOP (5.0) |
| 8 | `#0A1640` | 5 | CS-001 Blush Core / Accent Deep Rose (47.9) | DEFAULT/INK (33.3) |
| 9 | `#FFC300` | 5 | CS-002 Nude Warm / Primary Warm Nude (68.7) | POWDER/SOFT_PEACH_PARTICLES (62.1) |
| 10 | `#323333` | 5 | CS-002 Nude Warm / Accent Cocoa Rose (28.7) | DEFAULT/INK (25.4) |
| 11 | `#D6E3E3` | 4 | CS-001 Blush Core / Ground Warm Cream (10.5) | SOFT_MINT_WASH (6.7) |
| 12 | `#454871` | 3 | CS-001 Blush Core / Accent Deep Rose (38.4) | DEFAULT/INK (28.8) |

**ACCENT** — clusters (ΔE76 ≤ 8) ranked by files led:

| # | centre | files | nearest brand_gov swatch (ΔE) | nearest design-language swatch (ΔE) |
|---|---|---|---|---|
| 1 | `#FFFFFF` | 105 | CS-001 Blush Core / Ground Warm Cream (5.8) | WHITE_TYPE_HIGHLIGHT (2.5) |
| 2 | `#F2E8E2` | 70 | CS-001 Blush Core / Ground Warm Cream (3.8) | DEFAULT/LINE_LIGHT (3.4) |
| 3 | `#231916` | 53 | CS-002 Nude Warm / Accent Cocoa Rose (32.2) | DEFAULT/INK (25.0) |
| 4 | `#BCB3AB` | 13 | CS-002 Nude Warm / Primary Warm Nude (14.9) | DEFAULT/GROUND_TOP (14.9) |
| 5 | `#DDC8B7` | 13 | CS-002 Nude Warm / Primary Warm Nude (5.0) | DEFAULT/GROUND_TOP (5.0) |
| 6 | `#FAC9D1` | 12 | CS-001 Blush Core / Primary Blush (2.5) | POWDER/BLUSH_PINK (2.5) |
| 7 | `#A49483` | 11 | CS-002 Nude Warm / Primary Warm Nude (21.6) | POWDER/WARM_GREY_SUPPORTING_TEXT (10.2) |
| 8 | `#F7AFB8` | 11 | CS-001 Blush Core / Primary Blush (11.8) | POWDER/BLUSH_PINK (11.8) |
| 9 | `#F7DBE0` | 11 | CS-001 Blush Core / Secondary Pale Petal (1.1) | POWDER/BLUSH_PINK (9.8) |
| 10 | `#756762` | 10 | CS-002 Nude Warm / Accent Cocoa Rose (18.8) | POWDER/WARM_GREY_SUPPORTING_TEXT (9.4) |
| 11 | `#F9EBD5` | 9 | CS-002 Nude Warm / Secondary Soft Sand (4.7) | DEFAULT/GROUND_BOTTOM (4.7) |
| 12 | `#000000` | 8 | CS-002 Nude Warm / Accent Cocoa Rose (43.7) | DEFAULT/INK (34.2) |

**INK** — clusters (ΔE76 ≤ 8) ranked by files led:

| # | centre | files | nearest brand_gov swatch (ΔE) | nearest design-language swatch (ΔE) |
|---|---|---|---|---|
| 1 | `#000000` | 12 | CS-002 Nude Warm / Accent Cocoa Rose (43.7) | DEFAULT/INK (34.2) |
| 2 | `#FFFFFF` | 10 | CS-001 Blush Core / Ground Warm Cream (5.8) | WHITE_TYPE_HIGHLIGHT (2.5) |
| 3 | `#676767` | 7 | CS-002 Nude Warm / Accent Cocoa Rose (24.6) | POWDER/WARM_GREY_SUPPORTING_TEXT (12.0) |
| 4 | `#231F20` | 5 | CS-002 Nude Warm / Accent Cocoa Rose (32.9) | DEFAULT/INK (25.3) |
| 5 | `#9A8E83` | 5 | CS-002 Nude Warm / Primary Warm Nude (25.0) | POWDER/WARM_GREY_SUPPORTING_TEXT (6.2) |
| 6 | `#28275A` | 3 | CS-001 Blush Core / Accent Deep Rose (43.0) | DEFAULT/INK (31.3) |
| 7 | `#9B999F` | 2 | CS-001 Blush Core / Primary Blush (25.8) | POWDER/WARM_GREY_SUPPORTING_TEXT (12.7) |
| 8 | `#303C44` | 2 | CS-002 Nude Warm / Accent Cocoa Rose (32.2) | DEFAULT/INK (28.1) |
| 9 | `#FCD9C6` | 1 | CS-002 Nude Warm / Primary Warm Nude (6.4) | DEFAULT/GROUND_TOP (6.4) |
| 10 | `#BBD0FC` | 1 | CS-001 Blush Core / Secondary Pale Petal (26.3) | SOFT_MINT_WASH (28.6) |
| 11 | `#00FFFF` | 1 | CS-001 Blush Core / Ground Warm Cream (52.8) | SOFT_MINT_WASH (45.7) |
| 12 | `#5393F1` | 1 | CS-001 Blush Core / Primary Blush (59.7) | POWDER/WARM_GREY_SUPPORTING_TEXT (59.3) |

**Reading the usage.** The owner's designs sit on a **warm cream ground** (`#F2E8E2`, 61 files — ΔE 3.8 from the seeded Warm Cream `#FAF3EC`), a **warm gold ground** (`#CBA87D`, 24 files — nearest LINE_DEEP at ΔE 10.4, no brand_gov swatch within ΔE 17: a colour the record does not hold), white, and a **blush ground** (`#EEC7CE`, 12 files — ΔE 3.1 from the seeded Blush `#F2C4CE`); the accents are cream, a near-black `#231916`, the nude `#DDC8B7` (ΔE 5.0 from Warm Nude `#E8C9B3`), the blush pair `#FAC9D1` / `#F7DBE0` (ΔE 2.5 from Blush, **ΔE 1.1 from Pale Petal** `#F7DDE3`), the sand `#F9EBD5` (ΔE 4.7 from Soft Sand `#F0DECB`), and the warm greys `#A49483` / `#756762` (nearest WARM_GREY_SUPPORTING_TEXT at ΔE 9–10); the inks are black, white, `#676767` and the warm grey `#9A8E83` (ΔE 6.2 from WARM_GREY_SUPPORTING_TEXT). Five of the six seeded brand_gov hexes are within ΔE ≈ 5 of a measured role; the two seeded accents (Deep Rose `#8B3A52`, Cocoa Rose `#7A4A42`) are **not** what the designs use as accent — the designs' dark accent is the near-black `#231916`/`#231F20` and their warm accent is the gold `#CBA87D`, which no record names. The `#232424` backdrop of the historical designs is a template artboard fill, not a design colour.

## 4. The proposal (ruled by the owner after; nothing here is built)

### 4a. Colours — a palette layer consulting the materials seam

**Shape.** One module, `apps/ire/colour_roles.py`, in the house idiom of `font_roles.py` (§BH32): a role map, a chain per role, a verdict per candidate, a record row per resolved colour. It sits BETWEEN the colour sources and the composers: a composer asks the layer for a role (the six the design language's `SwatchSet` already names — `ground_top`, `ground_bottom`, `line_light`, `line_deep`, `accent`, `ink` — plus `highlight` and `wash`, its two loose swatches; §3d's measured roles map onto them) and receives a `Color` carrying `hex`, `cmyk` (where the source carries one), `source`, `authority`, `evidence` and `tier`. The layer never invents a value: every candidate is a row of a governed source, and the fallback is the existing brand_gov `ColorSystem` palette, then the design language's own swatch (the value the engine draws today), so the artefact can never draw a colour the record cannot name.

**Roles from measured usage** (§4a-i, the numbers in §3d): from §3d, eight roles the designs actually use — `ground_cream` (#F2E8E2 → Warm Cream), `ground_gold` (#CBA87D — unnamed today), `ground_blush` (#EEC7CE → Blush), `accent_light` (white / cream), `accent_blush` (#FAC9D1, #F7DBE0 → Blush / Pale Petal), `accent_nude` (#DDC8B7 → Warm Nude; #F9EBD5 → Soft Sand), `accent_dark` (#231916 — unnamed today), `ink` (black; #676767 / #9A8E83 → WARM_GREY_SUPPORTING_TEXT) — each with the seeded swatch it is within ΔE ≈ 5 of, and two (`ground_gold`, `accent_dark`) that no record names: the owner rules whether they enter the record as new brand_gov swatches (a data ruling) or stay measured-only.

**Candidates, by tier — the line the layer may not blur:**
- PRODUCTION palettes = colours extracted by structure from the 16 PRODUCTION rows only (their XMP swatch groups, .ase swatches, separations): these are the only library colours a composer may WRITE into an output, each row carrying the pack's evidence path + sha256 and the credit condition exactly as the tier record does for the file.
- REFERENCE palettes = the 410 colour-bearing REFERENCE groups: surfaced as **inspiration suggestions** — a ranked list the dashboard shows beside a task and the Creative Director's prompt names as words and hexes — and NEVER written into an output by the layer: a REFERENCE candidate's verdict is `INSPIRATION_ONLY`; `resolve_role` cannot return it; a test pins that no `Color` with `tier == REFERENCE` can reach `pdf_ai`.
- brand_gov `ColorSystem` = the fallback chain and, by the owner's option A below, the authority.

**Usage measured per colour on real documents.** Every resolved role writes a row to a `colour_usage/1.0` record on the document (role, hex, cmyk, source, tier, evidence, node names). At emission the layer reads the artefact back (the same PyMuPDF `get_drawings` census as §1b) and reconciles: every fill in the artefact must be either a resolved role's colour, a process colour (die/registration), or an embedded image; anything else is `UNRECONCILED_FILL` and named. The build half's usage measurement lands on the real documents of §1b first.

**Options with consequences (the choice is the owner's):**
- **A. brand_gov stays authoritative over library palettes.** A library colour can enter only as a candidate under a brand role and only when within a measured distance (ΔE) of a brand swatch, or as an explicitly ruled addition. Consequence: outputs stay inside the seeded palettes; the library changes tone, never the palette; the 14 literal swatches in `design_language.py` are re-pinned to the record so the duplicates cannot drift.
- **B. Library PRODUCTION palettes rank above brand_gov for the packs' own assets.** When a PRODUCTION material is placed, its pack's colours become the document's candidates first. Consequence: a document carrying a Freepik asset may draw that asset's palette; the brand palette remains the fallback; a document can look pack-led.
- **C. Two records, one authority per document.** The owner rules, per product or per task, which of A/B governs, recorded on the document. Consequence: more rulings, the least surprise.
- **D. Roles derived by measurement replace the seeded roles.** The §3d extraction defines the roles' names and the brand swatch each role maps to; the seeded palettes are re-labelled to match. Consequence: the design language's vocabulary follows the owner's own designs; a migration of the seeded records is a data change (a §BC ruling, not a build).

### 4b. Materials — placement, attribution, retrieval

**PRODUCTION assets (the 16 rows): the placement point(s).** The IRE `Image` node → `pdf_ai._draw_image` is the one seam by which a raster reaches an artefact (§2). Proposal: a `materials_placement/1.0` node record authored by the composer — the tier row (path, sha256, tier, evidence, condition), the placement (panel/zone, mm box, clip), and the credit's rendering — attached to the `Image` node; `pdf_ai` refuses an `Image` whose src lies under `materials/` unless such a record is attached and the tier is PRODUCTION. For vector packs (.eps/.ai assets among the 16), a second seam: `compose_vector_art` imports the asset's paths as a `Group` with the same record — proposed, not measured (the importer does not exist today).

**Attribution enforcement (§BH37).** For a row with a condition: (i) the credit lands in the artefact's record (`materials_placement` + the document's `attribution/1.0` list); (ii) where the terms say VISIBLY — the Freepik free licence requires the credit "in the appropriate place" of the product — the composer places a live-text credit node in the role the owner rules (the info panel / the back panel's regulatory block, at the floor size the production-method table already enforces); (iii) an artefact whose record shows a conditioned asset without the visible credit node resolves that asset as REFERENCE for that output — the placement is refused at emission and the refusal named — exactly §BH37's "else the asset resolves REFERENCE".

**REFERENCE assets: the retrieval contract (the BRAIN front serves it; the contract is proposed, not the server).**
`materials_retrieval/1.0` — a read-only query over the governed record, answering with rows that carry NO bytes of the asset and NO locator a composer could place:
- query: `{task_tokens, product_category, wanted: [palette|composition|motif|texture|finish], k}`;
- row: `{sha256, tier, category, pack, caption, palette: [hex…] (from the §3 structural extraction, never sampled from the image at query time), layout_metadata: {canvas_mm|px, mode, smart_object_count, replaceable_names}, evidence: {path, sha256, class}, condition, prohibited: PROHIBITED_FROM_COPYING}`;
- guarantees: a REFERENCE row's `locator` is absent by schema (the existing `_assert_no_locator` discipline); a PRODUCTION row's locator is present only for the placement seam above; the server (the BRAIN, §BH34 front 3) is derived from the record and gate-checked; the dashboard shows REFERENCE rows as inspiration cards; the Creative Director receives captions + palettes as words and hexes.
The existing `concept_references._material_candidates` becomes the first client of this contract: it reads the tier beside the inventory, shows the tier on the candidate card, and refuses to mark a REFERENCE row as anything but inspiration.

### 4c. What the build half would land, in §AC order (for the owner to rule)
1. `colour_roles.py` + the record contract + the reconciliation test on §1b's artefacts (usage measured on real documents);
2. the design language's 14 swatches re-pinned to the governance record (option A) or the measured roles (option D);
3. `materials_placement/1.0` on the `Image` seam with the emitter's refusal and the credit node;
4. `materials_retrieval/1.0` contract + `_material_candidates` reading the tier;
5. the vector import seam — only if the owner wants the 13 vector PRODUCTION assets placeable.

## 5. Nothing moved (goal 5)

Measured at HEAD 4a9043d after the report's extractions (`~/bh38_work/closing38.sh`, output `closing38_output.txt`):

- **Worktree clean** (porcelain empty, untracked included). Two commits only since the transcription order: ff7b11a (the register) and 4a9043d (the riding commit: `apps/ire/materials_owner_grant.py`, the channel's test file, `docs/design_intelligence/dip0a/materials_tiers_summary.json`, plus the gate's ledger lines); the untracked tier record under `var/` regenerated by that commit's generator.
- **Zero writes outside the allowed set by the measurement.** Every script, extraction, preview, prediction, seal, score and this report live under `~/bh38_work/`; no other `~/bh*_work/` file is newer than the transcription. Inside the repo tree the only files newer than the transcription outside the register, the riding commit's paths and the tier record are the gate's own ignored side-outputs (`.tier2_captures/*`, `.opt_out_harness_log`, `.record_integrity_output`, `.brand_strings_output`, `.reserved_copy_output`) and 570 PNGs under the ignored `media/generated/` written by the Django test suite during the two gate runs (timestamps 15:24Z and 15:39Z, inside the gate windows) — the gate's writes, not the measurement's; recorded, not hidden.
- **Protected regions byte-identical:** GATE 7fbeb8f1fe10b0fb at [514:541] of the 593-line `container_font_authority.py`; TEST b32030dc827263e4.
- **Tree seals:** dip0c c22592930c75001c unchanged through both commits; dip0a moved once, at the riding commit, because the tracked summary lives there (predicted) → e76dd129dca51f3c; unchanged since.
- **The eight M7 artefacts == `~/bh32_work/m7_baseline.txt`.**
- **Font theme unchanged** under Django at 4a9043d: the Noto trio VERIFIED_FOR_PRODUCTION (USER_CONFIRMED), the 35 (+ licence texts, 50 files) at their PROVENANCE hashes, catalogue 38, arabic-capable = NotoNaskhArabic-Regular only.
- **WIT denominator censused:** `TREE_CHECKS = 863` at `apps/ire/tests/test_wit_unit_analysis.py:1397`, untouched; the riding commit's one test compares strings and tiers (the gate's apps leg 7757 → 7758 = the one test).
- **The corpus untouched:** the DIP-0A inventory 3b3cfdc2bf4fc6c0… (31,026,591 B, mtime unchanged since regen run 2); the exclusion list's two entries at HEAD; the three folders 1,728 / 1,693 / 1,490 files, none newer than the transcription; `materials/` read only.

Raw output:

```
HEAD 4a9043d
=== porcelain ===
(porcelain RC=0)
=== exclusion list vs HEAD ===
2
=== inventory ===
3b3cfdc2bf4fc6c0
size 31026591 mtime Sep  5 16:14:55 2026
17-10-2024: 1728 files, newer than the §BH38 transcription: 0
ALL..MOCKUP: 1693 files, newer than the §BH38 transcription: 0
ADOBE STOCK: 1490 files, newer than the §BH38 transcription: 0
=== writes since the §BH38 transcription outside the allowed set (repo tree; excluding materials/, venv, .git, caches, gate outputs, the ledger, the register, the riding commit's paths, var/ tier record) ===
./bbrose_design_os/.opt_out_harness_log
./bbrose_design_os/.record_integrity_output
./bbrose_design_os/.tier2_captures/20260907T153411Z_0295fcc_dip0c.txt
./bbrose_design_os/.tier2_captures/20260907T155007Z_ff7b11a_dip0c.txt
./bbrose_design_os/.tier2_captures/20260907T155007Z_ff7b11a.txt
./bbrose_design_os/.tier2_captures/20260907T153411Z_0295fcc_dip0.txt
./bbrose_design_os/.tier2_captures/20260907T153411Z_0295fcc.txt
./bbrose_design_os/.tier2_captures/20260907T155007Z_ff7b11a_dip0.txt
./bbrose_design_os/.brand_strings_output
./bbrose_design_os/.reserved_copy_output
./bbrose_design_os/media/generated/v3_k9Drb7Z.png
./bbrose_design_os/media/generated/task_620_var_3_hclvfZb.png
./bbrose_design_os/media/generated/c_UajZAtY.png
./bbrose_design_os/media/generated/c_jls98zU.png
./bbrose_design_os/media/generated/c1_keIe52x.png
./bbrose_design_os/media/generated/task_409_var_1_s2kkaYw.png
./bbrose_design_os/media/generated/v2_DPac87R.png
./bbrose_design_os/media/generated/concept_9KO3v0b.png
./bbrose_design_os/media/generated/c_Vj5JFFL.png
./bbrose_design_os/media/generated/task_619_var_1_8T39t8a.png
(end)
=== ~ writes since the transcription outside ~/bh38_work ===
(end)
=== WIT denominator ===
1397:TREE_CHECKS = 863
GATE [514:541] 7fbeb8f1fe10b0fb (7fbeb8f1fe10b0fb) lines 593
TEST b32030dc827263e4 (b32030dc827263e4)
seal docs/design_intelligence/dip0c c22592930c75001c
seal docs/design_intelligence/dip0a e76dd129dca51f3c
M7 artefacts == baseline: True
```

## 6. Hard stops

- *a proposal reaching any REFERENCE asset for embedding* — never fired: §4 names REFERENCE rows only in the retrieval contract, whose rows carry no bytes and no locator by schema; the placement seam is proposed for PRODUCTION rows only, with the emitter refusing a `materials/` source that lacks a PRODUCTION tier record; a test is proposed that no `Color` or `Image` with `tier == REFERENCE` can reach `pdf_ai`.
- *a colour or asset outside the governed libraries and existing brand_gov proposed as a default* — never fired: every default in §4a is a brand_gov `ColorSystem` swatch or the design language's existing swatch (the value the engine draws today); the library enters as candidates, never as a default; no new colour is proposed.
- *any write outside the allowed set* — never fired: the writes are the T38 transcription (ff7b11a), the riding commit (4a9043d: three tracked paths + the untracked tier record), and `~/bh38_work/`; §5 lists the measurement.
- *the resolution unlocatable by measurement* — never fired: every colour point in §1 is a file:line reached by the static grep and, where it emits, confirmed by the runtime census of §1b; every materials point in §2 is a file:line; where no point exists the report says so exactly (§2, "points that do not exist today").

## 7. Recorded, not resolved

1. **The coolvetica EULA pdf.** The riding ruling's count (17) matches the LICENSE_EVIDENCE rows and excludes `Typodermic Desktop EULA 2023.pdf`, the coolvetica pack's own terms text (PRODUCT_REFERENCE by DIP-0A's classifier); the description ("terms and read-me texts of the granted packs") includes it. Applied narrow: the pdf is the one PERMISSIVE PRODUCTION row. One word returns it.
2. **The riding commit's line shape.** The summary file measured 46 lines where the prediction said 47 (the new `license_evidence_rows_withheld` field arrived as the PRODUCTION/LICENSE_EVIDENCE category line left); the module 286 lines where the prediction said "about 287"; the test file 494 where it said "about 492". Values held exactly; the line counts were stated as measured-at-scoring.
3. **The generator's first count.** The riding generator's first dry run reported 55 rows withheld — it counted every LICENSE_EVIDENCE row met before the pack ruling filter; moved after the filter it reports the 17. Both dry runs are kept (`riding_dry_run.txt` is the second); the sealed prediction carries 17.
4. **Two of the 254 "design PDFs" are the owner's number, not a file type.** The 254 = 226 `.ai` (PDF-compatible) + 28 `.pdf`; the 122 `.eps` of the same extraction are PostScript and were not read for colour (a limit, stated in §3d).
5. **Colour from vectors only.** §3d extracts fills and text by structure; raster content is counted (image area share) and never sampled; files whose page is ≥ 50 % raster are listed as raster-dominated and their "dominant" colour is the vector residue, not the picture.
6. **CMYK → sRGB is an approximation.** XMP swatch groups and DSC custom colours are CMYK; the hex shown is the naive conversion (no ICC), stated per table; the CMYK values themselves are in `libraries.json`.
7. **PANTONE names carry no hex.** Separations and spot swatches are listed by name; no value is invented.
8. **The dip0a tree seal moved with the riding commit** (the summary lives in that tree) — predicted this time.
9. **T38a's history** (from the previous session, carried): run 1 killed by the session teardown, run 2 refused by the environment (PostgreSQL down after a reboot); §BH24 budget 2/3.
10. **"Roles from my designs" depends on what the PDFs expose.** Where a design's colour lives in a placed raster (a photographic packshot or a rendered mockup), structure exposes nothing — those files are counted, not read; the proposal's role names come from the files that expose fills.
11. **Own-work packs at REFERENCE.** The `17-10-2024/Telegram Desktop/…` packs (the LORENZA skincare line, the BOTTLE colour edits, the bow/جيجي files) are the owner's own client designs, with their PANTONE swatches, and are REFERENCE only because no terms text sits beside them (the machine cannot write ownership). Like `historical AI production designs`, they would be PRODUCTION by ownership, not by licence — a ruling the owner can make in one sentence, then one grant commit through the channel with an ownership evidence kind the channel does not yet have (it pins a terms text). Reported; not resolved.
12. **The `#232424` backdrop.** 67 of the 91 historical designs carry a page-covering `#232424` rectangle; the roles exclude page-covering fills as artboard backdrops. If the owner reads that backdrop as a design colour, the dominant role changes.
13. **Structural colour on the PRODUCTION side is thin.** Of the 16 PRODUCTION rows only the delicious-summer-fruits `.ai` carries XMP swatches (Illustrator's default set plus five PANTONE spots); the seven JPEGs and three PSDs carry pixels, which the §BH35 rule never reads, and the four EPS carry no DSC custom colours. A PRODUCTION palette in the layer's sense would come from the vector rows' fills read by structure at placement time (the same PyMuPDF census applied to the placed asset) — proposed in §4a, not measured here beyond the swatch groups.
14. **11 artefacts and 12 design files unread for colour** — the AI8-format `.ai` under vq2 (PostScript), and 12 design files exposing no vector fill (raster-only or empty pages); 50 design files are raster-dominated. Counted, stated, not sampled.
15. **The gate's own writes** (`media/generated/*.png`, the captures) are the only files newer than the transcription outside the allowed set — the test suite's, not the measurement's (§5).
