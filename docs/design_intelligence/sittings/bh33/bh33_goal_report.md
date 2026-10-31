# §BH33 GOAL REPORT — THE FONT SMALLS

Written 2026-09-05 at final HEAD 8b5e70e. Every number below is measured at
that HEAD unless it names the commit it was measured at.

## 0. The commit chain (every commit predicted-then-scored)

| Commit | Concern | Prediction → score |
|---|---|---|
| b12bdcd | T33 — §BH33 transcribed (pure append, 118 lines: the owner's 50 typed lines verbatim, the executor's reading with the variable-face census and five readings for the owner) | pred_t33 4f28fd03f8ac1ab5 → 8/8 |
| 04faa08 | (1) ARABIC RE-RANK — each Arabic chain Naskh → REFUSAL; Cairo-Bold out of every Arabic chain, its Latin display role kept | pred_rerank a70dd40f803875ec → 8/8 (first launch from the wrong root exited 127 before the gate ran; relaunched, prediction unchanged) |
| 5a3627b | (2) VARIABLE INSTANCE PIN — heading 700 / body 400 for every variable face; the instance derived from the granted file and embedded by name; the record hashes the granted bytes and names the instance; the counter reconciles on the embedded name | pred_instances a82e69d9438703cc → 8/8 (first launch from the wrong root exited 127 before the gate ran; relaunched through a launcher that pins the inner root) |
| 660f6ca | (3) HARAKAT KEPT — the non-exempt drawer keeps harakat and tanween; the sticker proved byte-identical on its content streams; capability counts the marks | pred_harakat fc4fa0df45f5a600 → 8/8 |
| 8b5e70e | (4) ARABIC ROLE ROWS SPLIT — three distinct Arabic rows, never collapsed; the channel proofs and the reconstruct contract pin the shape | pred_rows eb3de02e33e9bfbf → 8/8 |

## 1. Goal state, measured at final HEAD

**(i) The bilingual document re-emitted with Naskh on every Arabic run and tanween visible** (bilingual.ai, tagged non-exempt, through the live emitter and the seam):
- roles resolved: bold → Poppins-Light (VERIFIED_FOR_PRODUCTION), regular → Poppins-Regular (VERIFIED_FOR_PRODUCTION), caption → Poppins-Light (VERIFIED_FOR_PRODUCTION), arabic-display → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION), arabic-heading → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION), arabic-body → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION); all_production_verified True; gate codes none; skipped candidates none
- the record's Arabic rows — three, distinct: arabic-display → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION), arabic-heading → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION), arabic-body → NotoNaskhArabic-Regular (VERIFIED_FOR_PRODUCTION)
- RTL: 5 Arabic spans, every one in an Arabic-capable face (True), the faces drawing Arabic ['NotoNaskhArabic-Regular']; per-line read-back 5 of 5 lines exact (marks stripped for the comparison), 0 unresolved
- harakat: the span extraction returns 1 fathatan (U+064B), in ['NotoNaskhArabic-Regular'] — the body run صباحاً ومساءً carries two, and both are DRAWN (§3, the instrument's limit at a line's visual start). By eye on the rendered page (`goal_docs/bilingual.png`, 200 dpi): both tanween are drawn — on the alef of صباحاً and on the hamza of ومساءً — with every letter present and joined in Noto Naskh Arabic (`goal_docs/bilingual_body_line_600dpi.png`, the body line at 600 dpi); the title, the label name, the heading and the mixed caption read as written. The span extraction returns ONE U+064B for this 5 pt line (PyMuPDF merges the zero-advance mark at the line's visual start); at 8 pt the (3) test extracts both — an instrument limit, recorded in §3, not a rendering defect: the page is the evidence.
- usage: reconciliation RECONCILED, agree True, codes none; faces that drew ['NotoNaskhArabic-Regular', 'Poppins-Light', 'Poppins-Regular']; counted ['NotoNaskhArabic-Regular', 'Poppins-Light', 'Poppins-Regular']; declared without glyphs ['Helvetica']

| Face | roles | scripts | runs | chars | instance of | outside layer |
|---|---|---|---|---|---|---|
| NotoNaskhArabic-Regular | body, caption, display, heading | arabic | 5 | 66 |  |  |
| Poppins-Light | caption, display | latin | 4 | 55 |  |  |
| Poppins-Regular | body | latin | 3 | 41 |  |  |

**(ii) The Latin document embedding Montserrat-Bold and Montserrat-Regular by name where the heading and body roles draw:**
- the Latin all-roles document (latin_all_roles.ai): roles bold → Poppins-Light (VERIFIED_FOR_PRODUCTION), heading → Montserrat-Bold (VERIFIED_FOR_PRODUCTION), regular → Poppins-Regular (VERIFIED_FOR_PRODUCTION), body → Poppins-Regular (VERIFIED_FOR_PRODUCTION), caption → Poppins-Light (VERIFIED_FOR_PRODUCTION), script-accent → GreatVibes-Regular (VERIFIED_FOR_PRODUCTION); instance rows on the record: heading: Montserrat-Bold = Montserrat[wght] at wght 700 (granted sha 0f7b311b2f3279e4…, derived sha 90cd4f1a7d9b707f…, source default instance Montserrat-Thin); the artefact's embedded faces ['GreatVibes-Regular', 'Helvetica', 'Montserrat-Bold', 'Poppins-Light', 'Poppins-Regular']; usage instances [['Montserrat-Bold', '90cd4f1a7d9b707f', {'stem': 'Montserrat[wght]', 'sha256': '0f7b311b2f3279e4eef9b2f968bcdbab6e28f4daeb1f049f4f278a902bcd82f7', 'axes': {'wght': 700.0}, 'source_default_instance': 'Montserrat-Thin'}]]; reconciliation RECONCILED, agree True, codes none; faces that drew ['GreatVibes-Regular', 'Montserrat-Bold', 'Poppins-Light', 'Poppins-Regular']; counted ['GreatVibes-Regular', 'Montserrat-Bold', 'Poppins-Light', 'Poppins-Regular']; declared without glyphs ['Helvetica']
- the body pin, proved on a twin whose body chain is LED BY Montserrat[wght] for the proof only (latin_body_pin_montserrat.ai; chain used ['Montserrat[wght]', 'Poppins-Regular', 'NotoSans-Regular']; the RULED body chain stays ['Poppins-Regular', 'NotoSans-Regular'] — recorded in §3): roles bold → Poppins-Light (VERIFIED_FOR_PRODUCTION), heading → Montserrat-Bold (VERIFIED_FOR_PRODUCTION), regular → Montserrat-Regular (VERIFIED_FOR_PRODUCTION), body → Montserrat-Regular (VERIFIED_FOR_PRODUCTION); instance rows heading: Montserrat-Bold = Montserrat[wght] at wght 700 (granted sha 0f7b311b2f3279e4…, derived sha 90cd4f1a7d9b707f…, source default instance Montserrat-Thin); regular: Montserrat-Regular = Montserrat[wght] at wght 400 (granted sha 0f7b311b2f3279e4…, derived sha 1f146b69141b4210…, source default instance Montserrat-Thin); body: Montserrat-Regular = Montserrat[wght] at wght 400 (granted sha 0f7b311b2f3279e4…, derived sha 1f146b69141b4210…, source default instance Montserrat-Thin); embedded faces ['Helvetica', 'Montserrat-Bold', 'Montserrat-Regular', 'Poppins-Light']; reconciliation RECONCILED, agree True, codes none; faces that drew ['Montserrat-Bold', 'Montserrat-Regular', 'Poppins-Light']; counted ['Montserrat-Bold', 'Montserrat-Regular', 'Poppins-Light']; declared without glyphs ['Helvetica']

| Face | roles | scripts | runs | chars | instance of | outside layer |
|---|---|---|---|---|---|---|
| GreatVibes-Regular | script-accent | latin | 1 | 9 |  |  |
| Montserrat-Bold | heading | latin | 1 | 22 | Montserrat[wght] wght 700 |  |
| Poppins-Light | caption, display | latin | 5 | 81 |  |  |
| Poppins-Regular | body | latin | 4 | 75 |  |  |

**(iii) The record showing three Arabic rows:** see (i) — arabic-display, arabic-heading, arabic-body as distinct rows on `container_font_authority/1.0`, no collapsed `arabic` row; on the real reconstruct path the persisted record carries the distinct rows (the reconstruct-contract test of (4)); the live exempt composition still records bold / regular / arabic as at 41604ac.

**(iv) Sticker byte-identical:** the regulatory sticker's preview .ai at final HEAD hashes its content streams (drawing + font subsets, inflated) to 35060d5da26f8506… (31274 bytes) — the value pinned in the (3) test measured at the HEAD before (3): 35060d5da26f8506… — equal: True. The raw file differs run to run only by reportlab's creation date and file ID.

**(v) Counter == artefact:** every document above reconciles with agreement True and no usage code; the live path (task 54, output 41, rolled back — database unchanged True) persists a usage record with agreement True and font readiness codes none; its faces [('bold', 'NotoSans-Bold', 'VERIFIED_FOR_PRODUCTION'), ('regular', 'NotoSans-Regular', 'VERIFIED_FOR_PRODUCTION')] (an exempt surface — the Noto pair, as at 41604ac).

**(vi) Gate GREEN, worktree clean, every commit scored:** table §0; porcelain clean at final HEAD; the ledger append-only at every landing.

The pair and the 35 unchanged: brand2026 all at PROVENANCE (True); the Noto files {'NotoSans-Regular.ttf': '478c558ea716033c', 'NotoSans-Bold.ttf': '1df075a380fc7cb8', 'NotoNaskhArabic-Regular.ttf': '6f0a92031367b2f5'} equal the recorded {'NotoSans-Regular.ttf': '478c558ea716033c', 'NotoSans-Bold.ttf': '1df075a380fc7cb8', 'NotoNaskhArabic-Regular.ttf': '6f0a92031367b2f5'}: True. The eight M7 artefacts equal the baseline: True.


## 2. The variable faces — measured, not assumed ((2): "its instance stated in the report")

| Face (granted file) | default instance (never rendered) | wght axis | heading = 700 | body = 400 | display / caption / script-accent |
|---|---|---|---|---|---|
| Montserrat-Italic[wght] | Montserrat-ThinItalic | 100–900 | MontserratItalic-BoldItalic (0e25c6d0c603ca2d…) | MontserratItalic-Italic (196e705c9838d99a…) | unpinned — never handed out, skipped with VARIABLE_INSTANCE_UNPINNED |
| Montserrat[wght] | Montserrat-Thin | 100–900 | Montserrat-Bold (90cd4f1a7d9b707f…) | Montserrat-Regular (1f146b69141b4210…) | unpinned — never handed out, skipped with VARIABLE_INSTANCE_UNPINNED |
| PlayfairDisplay-Italic[wght] | PlayfairDisplay-Italic | 400–900 | PlayfairDisplayItalic-BoldItalic (4e4d1726f79bc8c5…) | PlayfairDisplayItalic-Italic (7b4cd76406169221…) | unpinned — never handed out, skipped with VARIABLE_INSTANCE_UNPINNED |
| PlayfairDisplay[wght] | PlayfairDisplay-Regular | 400–900 | PlayfairDisplayRoman-Bold (16e500581cbc3bcc…) | PlayfairDisplayRoman-Regular (8d93e94502a6db13…) | unpinned — never handed out, skipped with VARIABLE_INSTANCE_UNPINNED |
| Quicksand[wght] | Quicksand-Light | 300–700 | Quicksand-Bold (31ece1fb39f8798c…) | Quicksand-Regular (795c0db0cd310f30…) | unpinned — never handed out, skipped with VARIABLE_INSTANCE_UNPINNED |

Five of the 35 are variable (an fvar table); the other 30 and the Noto trio are static. Each instance is derived at emit time from the granted file with fontTools' instancer (timestamps untouched, so the bytes are deterministic — the sha256 in brackets), named by the font's own STAT / fvar named instance, written under the OS temp dir, never into static/ and never granted separately. Of the five, only Montserrat[wght] sits in a ruled chain (heading); the other four are reachable only as a 2A-6E confirmed face at the display role — unpinned there, so never rendered.


## 3. Recorded, not repaired / not resolved (the sentence governs)

- **(2) does not re-rule the body chain.** The ruled body chain stays (Poppins-Regular, NotoSans-Regular) by §BH32(a); on the Latin exercise document the body role draws Poppins-Regular. The body pin (wght 400 = Montserrat-Regular) is proved on a twin whose body chain is led by Montserrat[wght] for the proof only, and by the (2) test. A body chain led by Montserrat[wght] is one ruled line.
- **"The same rule" for the other four variable faces:** heading = 700 and body = 400, named by each font's own STAT (§2). For any other role (display, caption, script-accent) a variable face has no ruled instance and is never rendered at its default: the candidate is skipped on the record with VARIABLE_INSTANCE_UNPINNED and the chain continues. Whether those roles get a weight is a ruling.
- **Instance bytes are derived, never granted.** The instance is derived from the granted variable file at emit time (fontTools instancer, timestamps untouched → deterministic bytes), written under the OS temp dir, never into static/. The record row keeps the granted file's sha256 and file_identity as the verification subject (the channel and the join key on it) and names the instance (postscript_name, axes, the derived bytes' sha256 and path, the source default-instance name); the usage counter counts the embedded name with the derived sha256 and an `instance_of`. A grant of the derived bytes themselves would be the owner's, not mine.
- **A same-name edge, recorded:** the static Montserrat-Regular is its own granted file in the 35 and the wght-400 instance of Montserrat[wght] carries the same PostScript name. reportlab embeds the name from the file, so if both ever drew in one document the usage record would count them under one name (the layer registers the instance under a disambiguated label in that case). Under the ruled chains neither is reachable except a 2A-6E confirmed face at display, where the variable face is unpinned.
- **Harakat on exempt surfaces stay deleted** — the sticker family, the dropper sheet, the back panel, the container composition, the 2A-7 golden path, the previews, the 2A handoff draw exactly as at 41604ac; the shaping function is one and takes the default there. The regulatory sticker's content streams are pinned; the raw file differs run to run only by reportlab's creation date and file ID, so the pin is on the inflated streams, not the raw bytes.
- **The read-back instrument drops a mark at a line's visual start:** in the emitted bilingual document the body line carries both tanween (drawn, confirmed at 600 dpi), but PyMuPDF's extraction — span and per-character alike — returns one U+064B: the mark drawn before the hamza at the line's visual start (no base precedes it in drawing order) is dropped by the text device, while the mark after the alef of صباحاً is kept. At 8 pt on the (3) test document both extract. The rendered page is the evidence; the extraction is the instrument, and its limit is recorded here rather than worked around.
- **Mark placement under reportlab:** reportlab applies no GPOS mark anchors; a zero-advance mark draws at the pen where its base is drawn (in visual order the mark precedes its base), so marks sit where the face's outline puts them, not where an OpenType shaper would. Read by eye on the goal page.
- **The WIT denominator, held by the census:** the first draft of (3) added a count comparison (`j < len(text)`) that moved TREE_CHECKS 863 → 864; caught before any gate and rewritten as a truthiness guard. No pin moved in §BH33.
- **Two launcher slips, recorded as history (no gate refused):** the (1) and (2) gates were first launched from the outer root, where tools/guarded_commit.sh does not exist — exit 127 at the launcher, nothing ran, no ledger line; both relaunched with the prediction unchanged, the second through a launcher that pins the inner root. §BH24 0/3 throughout.
- **Queued from §BH32, still queued:** each exempt surface's adoption of the theme (one ruling each); the sticker finding ((h)(4)); the EAN-13 widget's Helvetica ((h)(5)); the §BH32(g) Kufi + Sahel hunt.


## 4. Hard stops

- *Any exempt surface's output changing* — did NOT fire: the sticker's content streams equal the pin measured before (3); the exempt drawer, the legacy resolutions and the legacy record shape are untouched (the exempt twin of the tanween document draws no mark; the live exempt composition still persists bold / regular / arabic).
- *A variable face whose instance cannot be pinned by name in the artefact* — did NOT fire: every variable face carries STAT-named instances; the artefacts embed "Montserrat-Bold" and "Montserrat-Regular" by name.
- *A census-unpredicted pin class* — did NOT fire: the WIT denominator held at 863 (the one move caught by the census before any gate and undone); records, identity and corpus constants untouched; the manifest untouched (no new test file).
- *Either protected region or any M7 artefact changing* — did NOT fire: GATE 7fbeb8f1fe10b0fb at [514:541] and TEST b32030dc827263e4 at every scoring; the eight M7 artefacts equal the baseline at every commit.


## 5. What remains

- **For a ruling:** a body chain led by Montserrat[wght] (today Poppins-Regular draws body); weights for the display / caption / script-accent roles of variable faces (unpinned today); each exempt surface's adoption of the theme, one ruling each; the sticker finding; the EAN-13 widget's face; the Kufi + Sahel hunt.
- **Nothing in flight.** Worktree clean at final HEAD; the ledger append-only; no authority invoked in §BH33.

