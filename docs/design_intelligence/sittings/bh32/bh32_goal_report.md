# §BH32 GOAL REPORT — FONT WIRING, BUILD HALF

Written 2026-09-05 at final HEAD 4c6be16. Every number below is measured at
that HEAD unless it names the commit it was measured at.

## 0. The commit chain (every commit predicted-then-scored)

| Commit | Concern | Prediction → score |
|---|---|---|
| 6fab1e9 | T32 — §BH32 transcribed (pure append, 143 lines, the ruled tables quoted verbatim) | pred_t32 3198be4ca45f09e8 → 8/8 |
| 9243244 | (c) — the Noto Naskh Arabic grant: hash-matched to notofonts NotoNaskhArabic-v2.021 (hinted build); upstream OFL body ≡ the §BH29 Merriweather/Roboto bodies; the (c) authority SPENT | pred_naskh 8b2ce67bc5541ccd → 8/8 |
| 43d801d | (d)(i) — RTL detected by script on every text run at composition (model validator; apps/ire/text_script.py) | pred_rtl 8f39b21c02738095 → 8/8 |
| 41604ac | (d)(ii) — the Arabic face routed through the confirmed-font seam (the record, the join, the gate) | pred_seam 80eff2201833e6e3 → 8/8 |
| — | (e) attempt: the layer wide at all eight points — the broad sweep fired a census-unpredicted pin class (80 failures) → HARD STOP, reported, never sealed | hard_stop_layer_pins_report.txt |
| ce056c4 | T32h — §BH32(h) transcribed (pure append, 116 lines): NARROW THE LAYER'S SCOPE | pred_t32h c381369a54f2aa0c → 8/8 |
| 88ee894 | (e) narrowed — the layer at W1–W4 + W7 with the path-literal exemption list (ten entry points resolving as at 41604ac), the skipped-candidate record contract | pred_layer dd6eca7a125e7b98 → 8/8 |
| 3eacded | (f) — the per-run, per-face usage counter reconciled against the artefact; the EAN widget's Helvetica and the sticker bridge's strings counted | pred_usage 1ea681722698e24f → 8/8 |
| 4c6be16 | (e) capability repair — Arabic capability = the presentation forms the shaping path emits; Cairo-Bold skipped on the record with a named verdict; the chains unchanged | pred_forms 1f7fe7e3fdf66054 → 8/8 |

## 1. Goal (1) — real documents on the live path, theme faces by role, usage reconciled

**Measured at final HEAD 4c6be16, three documents through the live emitter.** All under the Django shell (`goal_emit.py`, then `rtl_lines.py`); every usage record below is the emitter's own `container_font_usage/1.0`, read back from the emitted `.ai` with PyMuPDF.

**(A) The real production path — task 54, output 41**, `reconstruct_container` exactly as `ARIAAgent.resume_after_container_profile` calls it, inside a transaction ROLLED BACK (database unchanged: True); the emitted `.ai` copied to `~/bh32_work/goal_docs/task54_container_live.ai` (True). This document is composed by `compose_container_graph`, an EXEMPT surface by §BH32(h)(1), so it resolves as at 41604ac — the Noto pair — by the owner's own sentence:
- authority record: bold → NotoSans-Bold (VERIFIED_FOR_PRODUCTION), regular → NotoSans-Regular (VERIFIED_FOR_PRODUCTION); all_production_verified True; skipped candidates none
- font readiness codes: none
- usage: reconciliation RECONCILED, agree True, codes none; faces that drew ['NotoSans-Bold', 'NotoSans-Regular']; counted ['NotoSans-Bold', 'NotoSans-Regular']; declared without glyphs ['Helvetica']

| Face | roles | scripts | runs | chars | outside layer |
|---|---|---|---|---|---|
| NotoSans-Bold | bold | latin | 6 | 95 |  |
| NotoSans-Regular | regular | latin | 4 | 53 |  |

**(B) A Latin document exercising every Latin role** — composed by the production composer, with role-tagged runs added (heading, body, caption, script-accent) and tagged NON-exempt per (h)(7), emitted through `emit_pdf_ai`, its record built through the seam and the channel (latin_all_roles.ai):
- roles resolved: bold → Poppins-Light (VERIFIED_FOR_PRODUCTION), heading → Montserrat-Thin (VERIFIED_FOR_PRODUCTION), regular → Poppins-Regular (VERIFIED_FOR_PRODUCTION), body → Poppins-Regular (VERIFIED_FOR_PRODUCTION), caption → Poppins-Light (VERIFIED_FOR_PRODUCTION), script-accent → GreatVibes-Regular (VERIFIED_FOR_PRODUCTION); all_production_verified True; gate codes none; skipped candidates: none
- usage: reconciliation RECONCILED, agree True, codes none; faces that drew ['GreatVibes-Regular', 'Montserrat-Thin', 'Poppins-Light', 'Poppins-Regular']; counted ['GreatVibes-Regular', 'Montserrat-Thin', 'Poppins-Light', 'Poppins-Regular']; declared without glyphs ['Helvetica']

| Face | roles | scripts | runs | chars | outside layer |
|---|---|---|---|---|---|
| GreatVibes-Regular | script-accent | latin | 1 | 9 |  |
| Montserrat-Thin | heading | latin | 1 | 22 |  |
| Poppins-Light | caption, display | latin | 5 | 81 |  |
| Poppins-Regular | body | latin | 4 | 75 |  |

**(C) A bilingual document exercising the Arabic chain with correct RTL** (bilingual.ai; product name رحيق الورد, Arabic body, heading and mixed caption runs added, tagged NON-exempt):
- roles resolved: bold → Poppins-Light (VERIFIED_FOR_PRODUCTION), regular → Poppins-Regular (VERIFIED_FOR_PRODUCTION), caption → Poppins-Light (VERIFIED_FOR_PRODUCTION), arabic → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION), arabic-display → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION); all_production_verified True; gate codes none
- skipped candidates on the record ((h)(3) contract): arabic-display: Cairo-Bold (Cairo-Bold) skipped — ARABIC_PRESENTATION_FORMS_MISSING(36), FONT_CHAIN_CANDIDATE_SKIPPED; arabic-heading: Cairo-Bold (Cairo-Bold) skipped — ARABIC_PRESENTATION_FORMS_MISSING(36), FONT_CHAIN_CANDIDATE_SKIPPED
- usage: reconciliation RECONCILED, agree True, codes none; faces that drew ['NotoNaskhArabic-Regular', 'Poppins-Light', 'Poppins-Regular']; counted ['NotoNaskhArabic-Regular', 'Poppins-Light', 'Poppins-Regular']; declared without glyphs ['Helvetica']
- RTL: 5 Arabic spans drawn, every one in an Arabic-capable face (True), the faces drawing Arabic ['NotoNaskhArabic-Regular']; Latin spans in Latin faces only (True). Read-back per line (PyMuPDF returns Arabic in LOGICAL order with joining forms, so a correctly drawn line reads back as the reshaped logical text): 5 of 5 Arabic lines exact, 0 consistent with unmapped glyphs, 0 unresolved. By eye on the rendered page (`goal_docs/bilingual.png`, 200 dpi): every Arabic run is drawn in Noto Naskh Arabic with every letter present and correctly joined — رحيق الورد as the title and on the label, سيروم مرطب للوجه, يوضع قطرتان صباحا ومساء (the tanween stripped by the shaping path's default, §5), and الحجم with its number and unit placed by the bidi algorithm; every Latin run unchanged. Before the repair the same document rendered in Cairo-Bold with letters dropped (`goal_docs/bilingual_before_repair.png`, §5).

| Face | roles | scripts | runs | chars | outside layer |
|---|---|---|---|---|---|
| NotoNaskhArabic-Regular | body, caption, display, heading | arabic | 5 | 64 |  |
| Poppins-Light | caption, display | latin | 4 | 55 |  |
| Poppins-Regular | body | latin | 3 | 41 |  |

Note on the heading role: the ruled default Montserrat[wght] renders its default instance (Montserrat-Thin) under reportlab, as recorded in §5.


## 2. Goal (2) — Naskh VERIFIED_FOR_PRODUCTION on the live path; the pair and the 35 unchanged

- On the live path (A) the record's faces resolve as at 41604ac — an exempt surface — and Naskh appears there only when the document carries an RTL run (task 54's does not).
- On the bilingual non-exempt document (C) the Arabic roles resolve through the seam: arabic → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION/USER_CONFIRMED), arabic-display → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION/USER_CONFIRMED) — Naskh VERIFIED_FOR_PRODUCTION / USER_CONFIRMED on the live emitter path in both Arabic record rows (the arabic-heading and arabic-body resolutions collapse into the `arabic` row by the (d)(ii) record vocabulary — §5); the usage counter shows Naskh drawing the display, heading, body and caption runs; the theme's arabic-body face is NotoNaskhArabic-Regular.
- The pair and the 35 unchanged: every brand2026 file equals its PROVENANCE.json sha256 (True); the Noto files {'NotoSans-Regular.ttf': '478c558ea716033c', 'NotoSans-Bold.ttf': '1df075a380fc7cb8', 'NotoNaskhArabic-Regular.ttf': '6f0a92031367b2f5'} against the recorded {'NotoSans-Regular.ttf': '478c558ea716033c', 'NotoSans-Bold.ttf': '1df075a380fc7cb8', 'NotoNaskhArabic-Regular.ttf': '6f0a92031367b2f5'} — equal: True.


## 3. Goal (3) — the six M7 artefacts byte-identical to HEAD before this goal

The eight M7 artefacts (six `.ai` + two label-sheet PDFs) equal `m7_baseline.txt` (recorded at 21601ea, before this goal) at every commit of the chain and at final HEAD: True. `palette_m7_ai_emitter.py` is untouched; Crimson Text overrides for M7 artefacts only, by §BH32(b).


## 4. Goal (4) — gate green, worktree and ledger clean, every commit scored, (c) spent only on its landing

At final HEAD 4c6be16: the gate GREEN on all three legs — the capability-repair landing's own line quoted in its score (`score_forms.txt`); worktree clean; ledger clean (every line the gates' own); every commit predicted-then-scored (table §0, the wide (e) attempt reported and never gated); the (c) single-use authority spent on 9243244 and on nothing else; no other authority invoked.


## 5. Recorded, not repaired / not resolved

- **The ruled arabic-display and arabic-heading default cannot render on this emitter — a finding for the owner.** Rendered and read by eye before the repair (`goal_docs/bilingual_before_repair.png`), Cairo-Bold drew رحيق الورد as حيق لو and سيروم as سير: reportlab does no OpenType shaping, so the shaping path (arabic_reshaper + python-bidi) emits presentation-form codepoints that must exist in the face's cmap, and Cairo-Bold lacks 36 of the 119 forms the path emits for the 36 letters across their four positions — the non-joining letters vanished. The §BH31 cmap census counted base letters and called the face capable; that measure was incomplete for this emitter. At 4c6be16 the layer's rule ("a face without Arabic glyphs never receives Arabic runs") is measured as the forms the shaping path emits; the ruled chains are unchanged and Cairo-Bold is SKIPPED on the record with ARABIC_PRESENTATION_FORMS_MISSING(36); Noto Naskh Arabic (0 missing) renders every Arabic role. A re-ranking is one ruled line; a shaping path applying the face's own OpenType tables would be a different emitter.
- **The shaping path deletes harakat, recorded and not repaired:** arabic_reshaper's default configuration (`delete_harakat=True`, unchanged since the sticker arc) strips tanween and other vowel marks before drawing, so the body run صباحاً ومساءً renders as صباحا ومساء (confirmed by eye and by the library's own output). The face is not the cause; the setting is the emitter's and predates §BH32. Whether Arabic copy keeps its marks is a ruling for the owner.
- **The record's Arabic vocabulary is two rows, recorded and not repaired:** the (d)(ii) seam records faces under the document's own role names — Arabic runs add `arabic` and, at display, `arabic-display` — so the layer's arabic-heading and arabic-body resolutions both write the `arabic` row (the last run walked wins). Today both resolve to Noto Naskh Arabic, the row is the same face either way, and the record is complete (reconciliation agrees on all three documents). Should a later ruling rank arabic-heading and arabic-body to different faces, one of the two faces that drew would be absent from `container_font_authority/1.0`; widening the record's vocabulary to the layer's roles is a seam change — one concern, one commit, after a ruling.
- **Bidi placement of a number and unit inside an Arabic line:** الحجم 30 ml renders as "ml 30 الحجم" read left to right — the Unicode bidi algorithm's placement of European digits adjacent to Arabic, not a defect; an author wanting "30 ml" kept together writes a directional mark.
- **Read-back instrument:** PyMuPDF returns Arabic in LOGICAL order with joining forms, so a correctly drawn line reads back as the reshaped logical text; a NUL in the extraction is a glyph reportlab's subset carries no Unicode mapping for. The rendered page is the evidence for the eye.
- **The layer's scope is the owner's sentence at §BH32(h):** the theme is the default only for a surface carrying no owner-ruled typography evidence. Ten exempt entry points, path-literal in `apps/ire/font_roles.py::EXEMPT_SURFACES`, resolve exactly as at 41604ac: the dropper sheet, the back panel, the container composition, the 2A-7 vector-art golden path, the production PDF's two resolvers, the sticker's canvas and SVG twin, the dieline previews, the 2A handoff. Each exempt surface's adoption of the theme is one later ruling each.
- **A reading forced by (h)(2), recorded for the owner:** four WI files ask the metrics map with no document, so an anonymous call or an untagged document resolves as at 41604ac; a surface adopts the theme by declaring a `typography_surface` tag not in the list; the goal's exercise documents are tagged `bh32/goal-exercise` per (h)(7). The live container path (task 54) is therefore an exempt surface and renders the Noto pair by the owner's own sentence.
- **The skipped-candidate contract ((h)(3)):** a candidate a chain skips is carried in `container_font_authority/1.0` under `skipped_candidates` at its honest state with `FONT_CHAIN_CANDIDATE_SKIPPED`; the helper sits below the protected gate grouping; the channel's fail-closed tests are byte-identical.
- **The ninth choice point ((h)(5)):** the EAN-13 widget draws its digits in built-in Helvetica outside the layer; the usage record counts it and names it under `outside_layer`; reportlab's default Times-Roman is declared without a glyph and listed as such. The sticker bridge's strings are counted at the canvas under the role "sticker". Whether the widget adopts a theme face is a later ruling.
- **Variable faces render at their default instance under reportlab:** the ruled heading default Montserrat[wght] renders Montserrat-Thin on a non-exempt surface; instancing would mint bytes no grant names.
- **The sticker finding ((h)(4)), queued:** under Poppins metrics the regulatory sticker's auto-fit drops the Spanish "external use only" line at the test panel size; the sticker stays on the Noto trio by (h)(1).
- **The four repairs ratified at (h)(6)** and, this session, the counter recording PostScript names (a TrueType face's name is bytes in reportlab) — the (f) commit's own.
- **The wide (e) attempt's refusal stands as history;** §BH24 budget 0/3 throughout. T32h (5)'s transcription carries the owner's single space; a double space I introduced was corrected before the append.

## 6. Hard stops

- *A licence body I have not read* — did NOT fire: the Naskh upstream OFL body is byte-identical to the §BH29 Merriweather/Roboto bodies; the in-corpus evidence pinned is the §BH25-read file.
- *Naskh upstream hash mismatch* — did NOT fire: the local file equals the hinted build in the notofonts NotoNaskhArabic-v2.021 release zip.
- *Any face outside the 35 + Noto trio reachable from the layer* — did NOT fire: the catalogue is exactly 38 (tested); the 2A-6E confirmed concept face reaches the emitter only on the exempt 2A-7 golden path, as (h)(1) rules; the EAN widget's Helvetica is drawn by the widget and named in every usage record.
- *Any M7 artefact changing* — did NOT fire: the eight artefacts equal `m7_baseline.txt` at every commit.
- *Either ceiling or guard moving; either protected region changing* — did NOT fire: GATE 7fbeb8f1fe10b0fb at [514:541] and TEST b32030dc827263e4 at every scoring; every edit above the region was line-count neutral and the new helper sits below it.
- *A census-unpredicted pin class* — FIRED ONCE, on the wide (e), reported frozen and ruled at (h); no pin moved.
- *Counter and artefact disagreeing at report time* — did NOT fire at report time: the three documents of §1 reconcile with agreement True and no usage code; the live path's persisted record carries no usage code in the font readiness.

## 7. Queued (§BH32(g)) and what remains

- **Queued by §BH32(g):** the Noto Kufi Arabic + Sahel evidence hunt (own front); Manal and Hacen Liner XL stay deferred.
- **Queued by §BH32(h):** each exempt surface's adoption of the theme, one ruling each with its pins re-measured only then; the sticker finding ((h)(4)); whether the EAN-13 widget adopts a theme face ((h)(5)).
- **For a ruling:** the arabic-display / arabic-heading default (Cairo-Bold cannot render on this emitter; Naskh renders by the chain); whether Arabic copy keeps its harakat (the shaping path strips them today); widening the record's Arabic vocabulary beyond the two (d)(ii) rows before any ruling ranks arabic-heading and arabic-body to different faces; the heading default's rendered instance (Montserrat-Thin) on non-exempt surfaces.
