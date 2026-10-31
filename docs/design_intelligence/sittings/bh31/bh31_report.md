# §BH31 REPORT — FONT WIRING, PROPOSAL HALF

Written 2026-09-04 at HEAD 21601ea (T31 21601ea, the §BH31 transcription,
scored 8/8). Zero writes outside that transcription and `~/bh31_work/`.
Every measurement below is read-only against the repository and the
`materials/` corpus; nothing was built.

## 1. The resolution as it is (goal 1)

**Search extents, two shapes.** (a) THE CALL GRAPH, followed from the three emitters that produce artwork or production documents — the IRE `.ai`/PDF emitter (`apps/ire/emitters/pdf_ai.py`), the dieline production PDF / back-label sticker (`apps/dielines/exporters/production_pdf.py`, `info_panel.py`, `design_preview.py`) and the M7 `.ai` emitter (`apps/pipeline/services/palette_m7_ai_emitter.py`) — through every function they call to choose a face, read under Django with the values measured on a real document. (b) THE LITERAL SWEEP: every production module under `bbrose_design_os/apps/` (`*.py|html|css|js`, tests and migrations excluded — 507 files) and `static/**/*.css|js|html` (vendor and fonts excluded), for family names, font-file names, registration labels, `font-family`, `registerFont`/`TTFont(`/`setFont(` and the resolver names: 1,121 hits in 198 files, all `.py` (no template names a font-family); 53 hits under `static/`, all dashboard CSS (not the emitter). Classified: 97 resolver/draw calls, 214 family-name literals, 54 font-file literals, 13 SVG font-family literals, 107 authority/evidence records, 636 other `font_` identifiers (`~/bh31_work/resolution_sweep.json`). Real documents measured: the 21 stored `PackagingOutput` records (7 carry `container_font_authority/1.0`, 1 carries `confirmed_font`), the test harness document `_doc()` and an in-memory document composed with an Arabic product name, all under the Django shell; the 8 committed M7 artefacts read with PyMuPDF.

**The choice points, in the order a document meets them.**

| # | Where (file:line) | What it chooses | Resolves to today (this machine, a real document) | Seam consulted or bypassed |
|---|---|---|---|---|
| 1 | `apps/dielines/exporters/production_pdf.py:110–124` `_resolve_fonts()` | ONE cached (regular, bold) pair for the whole process: repo `static/fonts/NotoSans-Regular.ttf` + `NotoSans-Bold.ttf` (:115–117) → else Linux DejaVu at `/usr/share/fonts/truetype/dejavu` (:86–88, :118–121) → else built-in Helvetica / Helvetica-Bold (:123) | `('NotoSans', 'NotoSans-Bold')` | **Bypassed** — takes no document and no confirmation; consumers: `production_pdf.py:343, 470, 484, 510, 531–564, 590–597` (sticker/back label at 6.5–10 pt), `design_preview.py:266, 400–416, 542`, `structural_comparison.py:310`, `pdf_ai.py:63`, `text_metrics.py:152`, `container_font_authority.py:471–494 _regular_face()` |
| 2 | `production_pdf.py:127–137` `_resolve_arabic_font()` | the Arabic face: `static/fonts/NotoNaskhArabic-Regular.ttf` or None | `'NotoNaskhArabic'` (sha 6f0a92031367b2f5…, Latin 0/52, Arabic 36/36) | **Bypassed, and outside the record** — the face is drawn by `info_panel.py:143, 177–222` (per-run `is_ar`) and `pdf_ai.py:64, 197–199` (`node.rtl`), but `container_font_authority._resolved_faces` (`container_font_authority.py:447–470`) enumerates only the `bold`/`regular` roles, so no Arabic face ever enters `container_font_authority/1.0`; and the file is **not granted** (OWNER_GRANTS names the pair and the 35 only) |
| 3 | `apps/ire/text_metrics.py:135–161` `resolve_metric_faces(doc_metadata)` | the role → face map `{regular, bold, arabic}` from 1–2, then `doc.metadata["confirmed_font"]` (`name` + `path`) REPLACES the **bold** role only (:157–160); `:195 resolve_metric_font` returns the bold entry | regular `NotoSans` (`static/fonts/NotoSans-Regular.ttf`), bold `NotoSans-Bold`, arabic `NotoNaskhArabic`; `confirmed_font` absent on `_doc()` and on 20 of 21 stored outputs | **Consulted, one face, one role** — the 2A-6E "confirmed concept face" seam. Its only stored real use: output 35 / task 50, `BarlowCondensed-Bold` from `materials/Fonts/3333/`, `path` None, `production_blocker FONT_LICENSE_EVIDENCE_REQUIRED_FOR_PRODUCTION` — unloadable, so it falls back silently to `NotoSans-Bold`. Producers: `aria.py:1278–1287` and `native_handoff.py:78–86` copy `spec_sheet["confirmed_font"]` into the concept spec; no code path writes that key (owner-supplied data) |
| 4 | `apps/ire/emitters/pdf_ai.py:59–76` `emit_pdf_ai` and `:193–201 _draw_text` | `fonts = {regular, bold, arabic}` from 1–2; `confirmed_font` → `fonts["bold"]` (:70–76); per text node `face = fonts.get(node.font, regular)`; if `node.rtl`: the arabic face + `shape_ar`; `c.setFont(face, node.size_pt)` (:201) | regular NotoSans, bold NotoSans-Bold, arabic NotoNaskhArabic. Role vocabulary = `TextRun.font` ∈ {regular, bold} (`apps/ire/graph.py:167`) + `TextRun.rtl` (`graph.py:171`) | **The DRAW seam is the role string; `rtl` is set by NO producer** (grep: only the field default and this reader). Measured: a document composed with the product name `رحيق الورد` yields runs (bold, rtl False) — the emitter would set them in `NotoSans-Bold`, which carries 0/36 Arabic letters. Arabic reaches a capable face only on the sticker path (2) |
| 5 | `apps/pipeline/targets/container/__init__.py:882–910, 1244–1256, 1465, 1480` `reconstruct_container(..., confirmed_fonts=None)` | the AUTHORITY record and the gate: `join_document_fonts(doc)` (c4c manifest join, ceiling LICENCE_REVIEW_REQUIRED / MACHINE_DERIVED) → `build_font_authority(doc, confirmed_fonts)` → `apply_owner_grant` → `font_confirmation_gate` → `spec["container_font_authority/1.0"]`, `readiness["font"]` | in-memory today: bold `NotoSans-Bold`, regular `NotoSans-Regular` (VERIFIED_FOR_PRODUCTION / USER_CONFIRMED through the grant); the 7 STORED records (tasks 51–57) predate §BH26: both roles `postscript_name ''`, UNVERIFIED, PLACEHOLDER_FALLBACK, `is_fallback True`, `all_production_verified False` | **Consulted — for the record and the gate, not for the choice.** The record describes the faces 1/3/4 already chose (`_resolved_faces` → `resolve_metric_font` for bold, `_regular_face` for regular); it cannot change what is drawn, and it never sees the Arabic face (2) |
| 6 | `apps/pipeline/services/palette_m7_ai_emitter.py:35–36, 142–171, 427–430, 515–520, 583–585, 638–639` | the M7 SET_FACE: `materials/Fonts/CrimsonText-Regular.ttf` loaded once (`SetFace`, refuses a character without a glyph), the artwork REFUSED unless its `font-family` is `"Crimson Text"` (:427), embedded as `/CrimsonText-Regular`, verified in the page fonts, recorded as `set_face`. The TARGET face is Adobe Caslon Pro — `docs/roadmap/palt_m4c/m7_typeface_face_ruling.json:6`; `palt_m7/m7_ai_emitter_declaration.json:14` "remains CHOSEN_BY_OWNER_LICENCE_NOT_HELD"; `palt_m7/owner_blocker_clearance_ingestion.json:30` "ACCEPT_SET_FACE — Crimson Text (Regular, OFL) for this deliverable" | the 6 committed `.ai` (es3083 back label DRAFT, label sheet T1, lid A2, lid C3; fb3093 lid C1, C3) embed `CrimsonText-Regular` only; the 2 label-sheet PDFs embed `CrimsonText-Regular` + built-in `Helvetica`. `palette_m6_products.py:78` reads the same file for the M6 renders | **Bypassed** — the face is a module constant read from `materials/`; Crimson Text is OUTSIDE the activated 35 and the pair (OFL per the module, never through the channel); its authority is the M7 declaration, not `container_font_authority/1.0` |
| 7 | literal family names on emitted-document paths | `design_preview.py:552 c.setFont("Helvetica", 7)` (caption, bypasses 1) and `:226` SVG `Helvetica,Arial,sans-serif`; `info_panel.py:337–419` the sticker's SVG twin: `Helvetica,Arial`, `Noto Naskh Arabic,Arial`, `Helvetica`; `apps/ire/handoff/container_adapter.py:125–126` handoff fallback `NotoSans-Bold` / `NotoSans-Regular` when the record has no name, `:317` the default set; `apps/ire/handoff/graph_schema.py:180–219` the confirmed font's name into the handoff | as written | **Bypassed** — literals |
| 8 | literal family names on review / spec documents (production-adjacent, not the artwork) | `spec_sheet.py:50–156` Helvetica / Helvetica-Bold; `production_authority_package.py:53–57` system `Arial Bold.ttf` / `Helvetica.ttc` / DejaVu paths, `:113–140` Helvetica; `physical_test_pdf.py:71–185` Helvetica; `palette_review_fonts.py:6` `/System/Library/Fonts/Helvetica.ttc`; `structural_comparison.py:310` via 1 | as written | **Bypassed** — these documents are reviewed, not shipped as artwork; listed because the owner asked for every hardcoded name |

**What this means, measured not inferred.** The emitter chooses a typeface at three live points on the artwork path — the process-wide pair (1), the Arabic face (2), and the per-node role lookup (4) with (3)'s single confirmed-font override of the bold role — plus the M7 emitter's fixed face (6). The confirmed-font seam of §BH26/§BH30 (5) is consulted for the record and the gate and can block production, but it does not choose a face and never sees the Arabic one. Today every live artwork document resolves to the Noto pair (Latin) and Noto Naskh Arabic (Arabic, ungranted), or to Crimson Text (M7); none of the 35 activated faces is reachable from any of the eight points. Two defects sit on the path and are recorded, not repaired: (i) `TextRun.rtl` is never set, so Arabic text in the Design Graph is drawn with a Latin face that has no Arabic glyphs; (ii) the Arabic face is outside both the grant and the record.


## 2. Usage roles from the owner's own designs (goal 2)

**Source.** The §BH28 per-file extraction (`~/bh28_work/extract_rows.json`, 376 design files; 254 PDF-compatible) re-opened read-only with PyMuPDF; every text span (font, size, text) mapped to an activated face by its subset-stripped base font name against the face's PostScript name, family+style, and — for the five variable faces — each named instance. Sizes are PDF user units (points at artboard scale). **Text-size buckets are a stated cut, not a measurement of the owner's intent:** display ≥ 36 pt, heading 18–36, body 9–18, caption < 9; the raw quantiles stand beside them so the cut can be moved. Script per span: Arabic if it holds an Arabic-block character and no Latin letter; Latin if the reverse; mixed if both; neutral (digits/punctuation) otherwise.

**Extractability.** 254 PDF-compatible files opened, 0 failed; **186 carry no text objects at all** (text outlined or rasterised) — for those the role cannot be measured and is not guessed. 68 files carry Latin text spans, **3 carry Arabic text spans**. Among the 26 files that name an activated face, 1 face-in-file cases are resource-only (the face is in the page's font resources but no span references it — Shadows Into Light Two).

**The measured role table (face → roles observed → file count → script coverage):**

| Face | design files | with text spans | resource-only | spans | size pt q10 / median / q90 / max | roles observed (bucket/script: spans) | Latin chars | Arabic chars | referenced as | script coverage (cmap) |
|---|---|---|---|---|---|---|---|---|---|---|
| Poppins/Poppins-Black.ttf | 4 | 4 | 0 | 20 | 14.0 / 14.0 / 60.0 / 60.0 | body/latin: 12, display/latin: 4, body/neutral: 4 | 268 | 0 | Poppins-Black | Latin 52/52; Arabic 0 |
| Poppins/Poppins-BlackItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-Bold.ttf | 5 | 5 | 0 | 38 | 12.9 / 14.8 / 17.0 / 30.2 | body/latin: 34, heading/latin: 3, body/neutral: 1 | 538 | 0 | Poppins-Bold | Latin 52/52; Arabic 0 |
| Poppins/Poppins-BoldItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-ExtraBold.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-ExtraBoldItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-ExtraLight.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-ExtraLightItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-Italic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-Light.ttf | 5 | 5 | 0 | 153 | 8.0 / 15.0 / 44.3 / 69.6 | body/latin: 94, caption/latin: 33, display/latin: 24, heading/latin: 2 | 3028 | 0 | Poppins-Light | Latin 52/52; Arabic 0 |
| Poppins/Poppins-LightItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-Medium.ttf | 5 | 5 | 0 | 82 | 10.0 / 11.0 / 12.0 / 22.5 | body/latin: 74, heading/latin: 8 | 557 | 0 | Poppins-Medium | Latin 52/52; Arabic 0 |
| Poppins/Poppins-MediumItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-Regular.ttf | 2 | 2 | 0 | 51 | 7.5 / 13.2 / 14.0 / 14.0 | body/latin: 38, caption/latin: 12, body/neutral: 1 | 1685 | 0 | Poppins-Regular | Latin 52/52; Arabic 0 |
| Poppins/Poppins-SemiBold.ttf | 5 | 5 | 0 | 34 | 6.9 / 14.6 / 14.6 / 14.6 | body/latin: 29, caption/latin: 5 | 255 | 0 | Poppins-SemiBold | Latin 52/52; Arabic 0 |
| Poppins/Poppins-SemiBoldItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-Thin.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Poppins/Poppins-ThinItalic.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Bebas_Neue/BebasNeue-Regular.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Great_Vibes/GreatVibes-Regular.ttf | 2 | 2 | 0 | 9 | 69.5 / 180.5 / 180.5 / 180.5 | display/latin: 9 | 61 | 0 | GreatVibes-Regular | Latin 52/52; Arabic 0 |
| Montserrat/Montserrat-Italic[wght].ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Montserrat/Montserrat[wght].ttf | 7 | 7 | 0 | 48 | 7.7 / 11.3 / 23.8 / 35.4 | body/latin: 22, caption/latin: 11, heading/latin: 10, heading/neutral: 2, body/neutral: 2, caption/neutral: 1 | 348 | 0 | Montserrat-Light, Montserrat-Bold, Montserrat-Medium, Montserrat-Black, Montserrat-SemiBold, Montserrat-Thin | Latin 52/52; Arabic 0 |
| Montserrat/Montserrat-Regular.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Quicksand/Quicksand[wght].ttf | 2 | 2 | 0 | 12 | 20.5 / 20.5 / 20.5 / 28.1 | heading/latin: 12 | 27 | 0 | Quicksand-Bold | Latin 52/52; Arabic 0 |
| Amatic_SC/AmaticSC-Bold.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Amatic_SC/AmaticSC-Regular.ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Playfair_Display/PlayfairDisplay-Italic[wght].ttf | 0 | 0 | 0 | 0 | — | not observed in any design file | 0 | 0 | — | Latin 52/52; Arabic 0 |
| Playfair_Display/PlayfairDisplay[wght].ttf | 1 | 1 | 0 | 10 | 15.9 / 15.9 / 15.9 / 15.9 | body/latin: 10 | 10 | 0 | PlayfairDisplay-Bold | Latin 52/52; Arabic 0 |
| Shadows_Into_Light_Two/ShadowsIntoLightTwo-Regular.ttf | 1 | 0 | 1 | 0 | None / None / None / None | resource only — text not extractable (outlined or no text objects) | 0 | 0 | ShadowsIntoLightTwo-Regular | Latin 52/52; Arabic 0 |
| Grand_Hotel/GrandHotel-Regular.ttf | 2 | 2 | 0 | 8 | 29.0 / 29.0 / 122.0 / 122.0 | heading/latin: 7, display/latin: 1 | 13 | 0 | GrandHotel-Regular | Latin 52/52; Arabic 0 |
| Cairo/Cairo-Bold.ttf | 2 | 2 | 0 | 11 | 48.3 / 68.3 / 112.0 / 112.0 | display/latin: 11 | 59 | 0 | Cairo-Bold | Latin 52/52; Arabic 36/36 |
| Raleway/Raleway-Light.ttf | 1 | 1 | 0 | 20 | 23.2 / 23.2 / 23.2 / 23.2 | heading/latin: 20 | 20 | 0 | Raleway-Light | Latin 52/52; Arabic 0 |
| Rubik/Rubik-Bold.ttf | 2 | 2 | 0 | 4 | 8.9 / 8.9 / 8.9 / 8.9 | caption/latin: 4 | 42 | 0 | Rubik-Bold | Latin 52/52; Arabic 0 |
| Lato/Lato-Black.ttf | 1 | 1 | 0 | 2 | 10.0 / 10.0 / 10.0 / 10.0 | body/latin: 2 | 32 | 0 | Lato-Black | Latin 52/52; Arabic 0 |
| Open_Sans/OpenSans-Semibold.ttf | 1 | 1 | 0 | 6 | 5.1 / 5.1 / 5.1 / 5.1 | caption/latin: 6 | 73 | 0 | OpenSans-Semibold | Latin 52/52; Arabic 0 |

Mapping notes, recorded: `Montserrat-Regular` referenced in one file maps to BOTH the static `Montserrat-Regular.ttf` and the variable `Montserrat[wght].ttf` (instance Regular) — counted as family-only, not attributed; `Amatic-Bold` (the designs' name) is a different family name from the activated `AmaticSC-*` and stays unmapped; `Cairo-Regular` (7 refs), `Cairo-SemiBold`, `Raleway-Thin`, `Lato-Light`, `Rubik-Black`, `BebasNeueBold/Book/Bebas`, `PlayfairDisplaySC-Regular` are activated FAMILIES whose referenced STYLE is not activated (family-only refs: {'Rubik-Black': 2, 'Rubik-BlackItalic': 2, 'Lato-Light': 2, 'BebasNeueBold': 2, 'Montserrat-Regular': 1, 'BebasNeue': 1, 'BebasNeueBook': 1, 'PlayfairDisplaySC-Regular': 1, 'Raleway-Thin': 1, 'Cairo-SemiBold': 1, 'Cairo-Regular': 7}).

**Latin roles as the owner's own files use the activated faces** (face (spans) per bucket):

- **display** (Latin): Poppins-Light.ttf (24), Cairo-Bold.ttf (11), GreatVibes-Regular.ttf (9), Poppins-Black.ttf (4), GrandHotel-Regular.ttf (1)
- **heading** (Latin): Raleway-Light.ttf (20), Quicksand[wght].ttf (12), Montserrat[wght].ttf (10), Poppins-Medium.ttf (8), GrandHotel-Regular.ttf (7), Poppins-Bold.ttf (3), Poppins-Light.ttf (2), Montserrat[wght].ttf (2)
- **body** (Latin): Poppins-Light.ttf (94), Poppins-Medium.ttf (74), Poppins-Regular.ttf (38), Poppins-Bold.ttf (34), Poppins-SemiBold.ttf (29), Montserrat[wght].ttf (22), Poppins-Black.ttf (12), PlayfairDisplay[wght].ttf (10), Poppins-Black.ttf (4), Montserrat[wght].ttf (2), Lato-Black.ttf (2), Poppins-Bold.ttf (1), Poppins-Regular.ttf (1)
- **caption** (Latin): Poppins-Light.ttf (33), Poppins-Regular.ttf (12), Montserrat[wght].ttf (11), OpenSans-Semibold.ttf (6), Poppins-SemiBold.ttf (5), Rubik-Bold.ttf (4), Montserrat[wght].ttf (1)

**Arabic in the owner's own files** (3 files; Arabic span sizes q10 / median / q90 = 9.0 / 9.0 / 13.3 pt — body-sized; Latin spans overall 7.4 / 12.9 / 36.2 pt). The faces carrying Arabic spans, **none of them activated**:

- Noto-Kufi-Arabic: arabic/body 329
- Noto-Kufi-Arabic-Bold: arabic/heading 3, arabic/body 111
- (AH)-Manal-Bold: arabic/body 16, arabic/caption 10
- (AH)-Manal-High: arabic/display 1, arabic/heading 4, arabic/body 14
- HacenLinerXL: arabic/heading 2, arabic/body 13
- Arial-BoldMT: arabic/body 7
- Sahel-Bold: arabic/body 4

No activated face carries a single Arabic span in the design files; Cairo-Bold, the one activated face with Arabic glyphs, is used by the owner only as LATIN display (48–112 pt).

**Fonts the owner's files use outside the 35** (unmapped references, top): MyriadPro-Regular (10), Square721BT-Roman (6), AngoraRegular (6), Hayah (5), Goli-Regular (5), AquireRegular (4), Bauhaus93 (4), BORELARegular (3), ClashDisplay-Medium (3), ClashDisplay-Regular (3), ClashDisplay-Light (3), ClashDisplay-Semibold (3), ClashDisplay-Bold (3), ColonnaMT (3), GoodDog (2), Selima (2).

The 26 files naming an activated face:
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/5955567.ai`
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/abstract-background-with-rounded-shapes/344195-PC2FZA-950.ai`
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/colourful-realistic-science-background/3631458.ai`
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/hand-drawn-christmas-gifts-pattern/26824-NWL0MV.ai`
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/hand-drawn-picnic-food-pattern/55838-O8JMCP-449.ai`
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/realistic-science-background-theme/3744544.ai`
- `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/vintage-background-with-phrase-smile-everyday/83530-OH0V40-228.ai`
- `materials/DOWNLOADE 2026/colorful-background-with-different-stains/309710-P950PU-277.ai`
- `materials/DOWNLOADE 2026/flat-black-friday-stickers-collection/5955567.ai`
- `materials/DOWNLOADE 2026/flat-vertical-poster-template-international-kissing-day-celebration/10512643.ai`
- `materials/DOWNLOADE 2026/hand-drawn-about-me-concept-with-happy-girl/5120470.ai`
- `materials/DOWNLOADE 2026/set-city-stamps-flat-style/251740-P4UM69-918.ai`
- `materials/DOWNLOADE 2026/sunset-sky-background-orange-color/63591-OB1D3J-49.ai`
- `materials/DOWNLOADE 2026/watercolor-floral-business-card-template/416115-PDE8QD-130.ai`
- `materials/DOWNLOADE 2026/wihte-background-with-modern-style/182539-OWQU9T-225.ai`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/BBROSE-1.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/BBROSE.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/LILARA PRESENTATION.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/Presentation MCC.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/presentation.pdf11-1.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/presentation.pdf11-2.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/presentation.pdf11-3.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/presentation.pdf11.pdf`
- `materials/DOWNLOADE 2026/محفوظات شغل  02 المكتب/محارم 1.pdf`
- `materials/DOWNLOADE 2026/نماذج عامة من  01الانترنيت/الوان جانيل.ai`
- `materials/historical AI production designs/LP-2007.ai`


## 3. Script coverage per activated face, cmap-measured (goal 3)

**Method.** fontTools over each of the 35 files under `static/fonts/brand2026/` (sha256 re-checked against PROVENANCE.json), the best cmap, glyph counts per Unicode block. "Arabic std 36" = the 26 letters U+0621–U+063A plus the 10 letters U+0641–U+064A; "Latin A–Z a–z" = the 52 basic letters. Shaping for reportlab's Arabic path uses Presentation Forms B (PF-B).

| Face (folder/file) | PostScript | var | glyphs | cmap cps | Latin A–Z a–z | Latin-1 | Ext-A | Ext-B | Arabic block | Arabic std 36 | PF-A | PF-B | Arabic runs |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Amatic_SC/AmaticSC-Bold.ttf | AmaticSC-Bold |  | 850 | 797 | 52/52 | 96 | 127 | 91 | 0 | 0/36 | 0 | 0 | never |
| Amatic_SC/AmaticSC-Regular.ttf | AmaticSC-Regular |  | 850 | 797 | 52/52 | 96 | 127 | 91 | 0 | 0/36 | 0 | 0 | never |
| Bebas_Neue/BebasNeue-Regular.ttf | BebasNeue-Regular |  | 508 | 461 | 52/52 | 96 | 127 | 10 | 0 | 0/36 | 0 | 0 | never |
| Cairo/Cairo-Bold.ttf | Cairo-Bold |  | 822 | 689 | 52/52 | 95 | 121 | 11 | 101 | 36/36 | 101 | 89 | YES |
| Grand_Hotel/GrandHotel-Regular.ttf | GrandHotel-Regular |  | 369 | 367 | 52/52 | 96 | 127 | 6 | 0 | 0/36 | 0 | 0 | never |
| Great_Vibes/GreatVibes-Regular.ttf | GreatVibes-Regular |  | 2025 | 1081 | 52/52 | 95 | 126 | 168 | 0 | 0/36 | 0 | 0 | never |
| Lato/Lato-Black.ttf | Lato-Black |  | 277 | 263 | 52/52 | 96 | 24 | 1 | 0 | 0/36 | 0 | 0 | never |
| Montserrat/Montserrat-Italic[wght].ttf | Montserrat-ThinItalic | yes | 2791 | 1312 | 52/52 | 95 | 128 | 180 | 0 | 0/36 | 0 | 0 | never |
| Montserrat/Montserrat-Regular.ttf | Montserrat-Regular |  | 1943 | 969 | 52/52 | 96 | 128 | 75 | 0 | 0/36 | 0 | 0 | never |
| Montserrat/Montserrat[wght].ttf | Montserrat-Thin | yes | 2747 | 1312 | 52/52 | 95 | 128 | 180 | 0 | 0/36 | 0 | 0 | never |
| Open_Sans/OpenSans-Semibold.ttf | OpenSans-Semibold |  | 938 | 883 | 52/52 | 96 | 128 | 17 | 0 | 0/36 | 0 | 1 | partial |
| Playfair_Display/PlayfairDisplay-Italic[wght].ttf | PlayfairDisplay-Italic | yes | 1101 | 659 | 52/52 | 95 | 128 | 30 | 0 | 0/36 | 0 | 0 | never |
| Playfair_Display/PlayfairDisplay[wght].ttf | PlayfairDisplay-Regular | yes | 1103 | 659 | 52/52 | 95 | 128 | 30 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Black.ttf | Poppins-Black |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-BlackItalic.ttf | Poppins-BlackItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Bold.ttf | Poppins-Bold |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-BoldItalic.ttf | Poppins-BoldItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-ExtraBold.ttf | Poppins-ExtraBold |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-ExtraBoldItalic.ttf | Poppins-ExtraBoldItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-ExtraLight.ttf | Poppins-ExtraLight |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-ExtraLightItalic.ttf | Poppins-ExtraLightItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Italic.ttf | Poppins-Italic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Light.ttf | Poppins-Light |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-LightItalic.ttf | Poppins-LightItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Medium.ttf | Poppins-Medium |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-MediumItalic.ttf | Poppins-MediumItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Regular.ttf | Poppins-Regular |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-SemiBold.ttf | Poppins-SemiBold |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-SemiBoldItalic.ttf | Poppins-SemiBoldItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-Thin.ttf | Poppins-Thin |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Poppins/Poppins-ThinItalic.ttf | Poppins-ThinItalic |  | 1060 | 471 | 52/52 | 96 | 107 | 8 | 0 | 0/36 | 0 | 0 | never |
| Quicksand/Quicksand[wght].ttf | Quicksand-Light | yes | 812 | 694 | 52/52 | 96 | 127 | 72 | 0 | 0/36 | 0 | 0 | never |
| Raleway/Raleway-Light.ttf | Raleway-Light |  | 672 | 598 | 52/52 | 96 | 127 | 53 | 0 | 0/36 | 0 | 0 | never |
| Rubik/Rubik-Bold.ttf | Rubik-Bold |  | 766 | 686 | 52/52 | 96 | 126 | 10 | 0 | 0/36 | 0 | 0 | never |
| Shadows_Into_Light_Two/ShadowsIntoLightTwo-Regular.ttf | ShadowsIntoLightTwo-Regular |  | 356 | 362 | 52/52 | 96 | 118 | 9 | 0 | 0/36 | 0 | 0 | never |

**Reading.** All 35 faces carry the full basic Latin alphabet, Latin-1 Supplement (95–96) and Latin Extended-A (Lato-Black the thinnest at 24; the rest 107–128), so accented Latin is safe everywhere. **Exactly one face carries Arabic: Cairo-Bold** — 101 codepoints in the Arabic block, all 36 standard letters, the Persian/Urdu additions (U+067E, U+0686, U+06AF, U+06A9, U+06CC, U+0698) and both Arabic-Indic digit sets, PF-A 101 / PF-B 89 for shaping; its only gaps are U+063B–U+063F (non-standard letters). **Every other activated face must never receive an Arabic run.** For reference, the Noto PAIR (granted) carries 0/36 Arabic letters, and the third Noto file the sticker path uses today, `NotoNaskhArabic-Regular.ttf` (sha 6f0a92031367b2f5…), carries 36/36 Arabic and 0/52 Latin but is **not granted** and outside the 35.


## 4. The proposal — for the owner to rule (goal 4)

**Scope.** A proposal, for the owner to rule; nothing here is built. Every face it names is one of the activated 35 or the Noto pair; where the corpus has a gap, the gap is stated and left to a ruling.

**4.1 The role set — derived from §2, not assumed.** The owner's files use the activated faces in four Latin size roles and one script role, and set Arabic in body and heading sizes with faces outside the 35:

| Role | Evidence in the owner's files (§2) | Notes |
|---|---|---|
| `display` | Poppins-Light 24 spans (44–70 pt), Poppins-Black 4 (60 pt), Great Vibes 9 (180 pt), Grand Hotel 1 (122 pt), Cairo-Bold 11 (48–112 pt, Latin) | product name / hero word; the Design Graph's product-name runs are semantically this role even at 8–12 pt on a 40 mm bottle |
| `heading` | Montserrat 12 (Light/Bold/Medium instances), Raleway-Light 20, Quicksand 12 (Bold instance), Poppins-Medium 8, Grand Hotel 7, Poppins-Bold 3 | |
| `body` | Poppins-Light 94, Poppins-Medium 74, Poppins-Regular 38, Poppins-Bold 34, Poppins-SemiBold 29, Montserrat 24, Poppins-Black 16, Playfair Display 10 (Bold instance), Lato-Black 2 | |
| `caption` | Poppins-Light 33, Poppins-Regular 12, Montserrat 11, OpenSans-Semibold 6, Poppins-SemiBold 5, Rubik-Bold 4 | regulatory / INCI copy lives here on the sticker |
| `script-accent` | Great Vibes (display), Grand Hotel (heading/display) | a decorative role the size buckets alone would hide |
| `arabic-body`, `arabic-heading`, `arabic-display` | 3 files, 9–13 pt body, rare heading, one display span — Noto Kufi Arabic (Regular 329, Bold 111+3), (AH) Manal, Hacen Liner XL, Sahel, Arial Bold: **none activated** | the roles exist in the owner's work; the theme can serve them today only with Cairo-Bold (§3) |

The existing vocabulary `regular` / `bold` (`graph.py:167`) maps onto this set as aliases — `regular` → `body`, `bold` → `display` for product-name runs (what `resolve_metric_font`'s docstring calls "bold/product-name runs") — so no producer breaks on day one.

**4.2 Default face per role and the fallback chain — candidates ranked by the owner's own usage; the owner picks.**

| Role | Candidates from the 35 (most-used first) | Fallback chain (proposed) |
|---|---|---|
| `display` | Poppins-Light · Poppins-Black · Cairo-Bold (Latin) · Great Vibes / Grand Hotel where script is wanted | chosen face → Poppins-Regular → NotoSans-Bold |
| `heading` | Montserrat[wght] (Medium/Bold instance) · Quicksand[wght] (Bold) · Raleway-Light · Poppins-Bold | chosen → Poppins-Bold → NotoSans-Bold |
| `body` | Poppins-Regular · Poppins-Light · Montserrat[wght] (Regular/Light) · Playfair Display[wght] | chosen → Poppins-Regular → NotoSans |
| `caption` | Poppins-Light · Montserrat[wght] · Rubik-Bold · OpenSans-Semibold | chosen → Poppins-Regular → NotoSans |
| `script-accent` | Great Vibes · Grand Hotel · Shadows Into Light Two · Amatic SC | chosen → the `display` chain |
| `arabic-*` | **Cairo-Bold — the only activated face with Arabic glyphs** | Cairo-Bold → **refuse the run** (a gate code, no render) — the chain cannot honestly end at the Noto pair, which carries 0/36 Arabic letters; today's Arabic face, Noto Naskh Arabic, is outside the 35 and the pair and is therefore NOT part of this proposal — whether it is granted (it ships beside `static/fonts/OFL.txt`) is the owner's separate ruling |

The rule the layer enforces: **an Arabic run goes only to a face whose cmap holds the 36 standard letters (§3); a Latin run only to a face with the 52 basic letters; a mixed run is split per script.** Script is measured per run from the text (Unicode blocks), because `rtl` is never set today.

**4.3 The seam it consults — so a face never renders unless it verifies.** The layer resolves a role to a candidate list; each candidate becomes a confirmed-font entry `{name, path}` for its role and passes through the existing seam exactly as §BH30 measured it on all 35 faces — `build_font_authority(doc, confirmed_fonts=…)` → `apply_owner_grant` → `font_confirmation_gate` — and is drawn **only if its record reads VERIFIED_FOR_PRODUCTION**; otherwise the next candidate; the Noto pair last. Any run whose chain is exhausted is refused with the gate code the pipeline already blocks on (`readiness["font"]`). Registration with reportlab happens after verification, from the grant row's evidence path, so the sha256 that verified is the file that renders. Neither ceiling nor guard moves: the layer sits ABOVE the seam and feeds it.

**4.4 The wiring points, from §1, and what changes at each.**

| Point | Change |
|---|---|
| W1 `pdf_ai.py:59–76` | `fonts = {regular, bold, arabic}` becomes `fonts = role_faces(doc)` — the full role map from the layer (one call), with the alias mapping for `regular`/`bold`; `:70–76`'s single `confirmed_font` override becomes one entry of that map |
| W2 `pdf_ai.py:193–201 _draw_text` | face lookup by role AND per-run script (Unicode blocks) instead of `node.rtl` alone; an Arabic run never reaches a Latin-only face; `shape_ar` unchanged |
| W3 `text_metrics.py:135–161` | `resolve_metric_faces` calls the same `role_faces(doc)` — measurement and emission stay one map, which its own docstring requires |
| W4 `container_font_authority.py:447–470 _resolved_faces` | enumerate every role the document uses (including Arabic and script runs) so `container_font_authority/1.0` records every face drawn; today it records two |
| W5 `production_pdf.py:110–137` | the sticker/back-label pair and Arabic face route through the layer's `caption` and `arabic-body` roles (or stay on the Noto trio by ruling — regulatory copy is neutral; stated as the owner's choice) |
| W6 `design_preview.py:552, :226`; `info_panel.py:337–419` (SVG twin) | take the face from the layer's record instead of the literal; or stay literal by ruling as preview-only |
| W7 `container_adapter.py:125–126, :317`; `graph_schema.py:180–219` | fallbacks read from the record the layer now completes |
| W8 M7 emitter | one of the three options in 4.6 |

**4.5 The usage measurement — proving which faces actually rendered.** (a) At emission, `_draw_text` appends one row per run to a per-document counter `{postscript, sha256, role, script, runs, chars}` persisted beside `container_font_authority/1.0` as `container_font_usage/1.0` in the output's spec sheet. (b) After emission, the artefact itself is read back (PyMuPDF: page fonts + a span census — the same instrument this report used on the owner's files) and reconciled: every face in the counter is embedded in the artefact and every embedded face is in the counter; a mismatch is a finding, not a rounding. (c) The §BH32 goal-state clause reads it: *for the N real documents emitted under the build, the usage record shows each activated face's documents and runs, cross-checked against the artefacts; zero faces rendered outside the record; zero faces rendered below VERIFIED_FOR_PRODUCTION; every Arabic run on an Arabic-capable face.*

**4.6 How the M7 build parameter relates to the theme — options with consequences; the owner chooses.**

| Option | What changes | Consequences |
|---|---|---|
| O1 REPLACED | the M7 SET_FACE constant (`palette_m7_ai_emitter.py:35–36`) becomes a theme role (`display` or a ruled face from the 35) resolved through the layer; the `font-family == "Crimson Text"` refusal (:427) becomes "equals the ruled face" | the committed M7 artefacts change appearance on re-emission; Crimson Text leaves production; the Caslon target stays unheld and unaffected |
| O2 LAYERED | the theme layer serves the IRE/container path only; M7 keeps Crimson Text as a fixed SET_FACE with its own declaration as authority | a face outside the 35 stays in production use, verified by the M7 declaration rather than the channel — the inconsistency stands and is recorded; no M7 artefact moves |
| O3 OVERRIDDEN PER DOCUMENT | the M7 emitter takes a per-document face parameter (default Crimson Text) resolved through the layer and the seam; the refusal check generalises to the declared face | each M7 document states its face; Crimson stays the default until ruled otherwise; Adobe Caslon Pro can enter later only as a granted face, if licensed — never through this proposal |


## 5. Nothing moved (goal 5)

- **Zero writes outside the §BC transcription and `~/bh31_work/`:** the only repository change in this goal is the T31 commit (register + the gate's ledger line). Files written under `~/bh31_work/`: `t31_block.md`, `t31_msg.txt`, `pred_t31.txt`, `seals.txt`, `t31_gate.log`, `score_t31.txt`, `cmap_coverage.py/.json`, `resolution_sweep.py/.json`, `usage_roles.py/.json/.log`, `arabic_census.py/.json/.log`, `build_report.py`, `fill_sections.py`, `bh31_report.md`.
- **One transcription commit, predicted then scored:** T31 21601ea — pred_t31 sealed 72422188d28f6bf1 before git add; 8/8 (`score_t31.txt`); gate line `TIER_2=GREEN collected=8510 failures=0 apps=7698 dip0c=671 dip0=141`; ledger 450 → 451.
- **Protected regions re-verified at report time:** GATE 7fbeb8f1fe10b0fb, TEST b32030dc827263e4 — byte-identical.
- **Tree seals re-verified at report time:** dip0c 5ae44035bd03bae1, dip0a 4fe747b806ed71bd — unchanged since 2ac0fd4.
- **WIT denominator censused:** `test_wit_unit_analysis.py:1397 TREE_CHECKS = 863`; the register class passes at this HEAD (6 tests); no apps file changed, so nothing could move it.
- **Worktree clean at report time:** porcelain empty at HEAD 21601ea, stash empty.
- The Noto pair at this HEAD: VERIFIED_FOR_PRODUCTION / USER_CONFIRMED ×2 under Django (the T31 scoring).


## 6. Hard stops

- *The emitter's resolution cannot be located by measurement* — did NOT fire: located at the eight points of §1, every one cited file:line and measured under Django; the two search shapes and their extents are stated there.
- *Any step would write outside `~/bh31_work/`* — did NOT fire: every measurement was read-only (PyMuPDF and fontTools opened files; the Django shell queried and composed in memory; no emission, no DB write, no stash); §5 lists every file written.
- *Any proposal would require a face outside the activated 35 or the Noto pair* — did NOT fire: every default and every fallback in §4 is one of the 35 or the pair. Two faces outside that set are in production use TODAY and are reported as findings, not required by the proposal: Noto Naskh Arabic (the sticker's Arabic face, ungranted, outside the record) and Crimson Text (the M7 SET_FACE). The Arabic chain ends in a refusal rather than the pair because the pair carries no Arabic glyphs — a gap the owner may close by a separate grant ruling, which this proposal does not presume.

