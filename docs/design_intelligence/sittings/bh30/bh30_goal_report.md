# §BH30 GOAL REPORT — the open set granted on byte-exact evidence

Written 2026-09-04 at final HEAD ba67d5a. Every number below is measured
at that HEAD unless it names the commit it was measured at. Zero writes.

## 0. The commit chain (every commit predicted-then-scored)

| Commit | What | Prediction → score |
|---|---|---|
| fb9b065 | T30 — §BH30 transcribed (pure append, 195 lines) | pred_t30 → 8/8 |
| 87091c1 | (b)+(c) — acquisition (38/38 fetches sha256-equal to the §BH29 record) + intake under `static/fonts/brand2026/` (35 faces, 15 licence texts, PROVENANCE.json); (b) authority SPENT | pred_intake → 8/8 |
| — | T30h transcription attempt 1 — gate REFUSED on five findings (var/-reading tests); scored as history | score_t30h_attempt1 |
| 2ac0fd4 | (h)+(i)+(j) ONE ATOMIC COMMIT — exclusion list + 6 fixture tests, the re-run's eight records, twelve constants, the entry-44 re-pin (34 entries) + registry root-of-trust pin, three register appends inside; (i)(2) authority SPENT | pred_atomic 4f9787fa9eed3c29 → 8/8 |
| — | (d) attempt 1 — gate REFUSED: test_wit_unit_analysis.py TREE_CHECKS 863→864, one analyser check counted in an appended assertion (a census-unpredicted pin class → hard stop, ruled at (k)(2)) | pred_grants c23ff24544774ac1 → scored as history |
| 90f2649 | T30k — §BH30(k) transcribed (pure append, 55 lines), its own commit before the act | pred_t30k 2d212341a4e23b47 → 8/8 |
| ba67d5a | (d) attempt 2 — OWNER_GRANTS_BH30, 35 rows, one per face keyed by sha256; five tests (the redundant assertion dropped per (k)(2)); (d) authority SPENT | pred_grants2 42b447e41aee7c62 → 8/8 |

Hard stops named by §BH30, measured across the chain: no spend (every
acquisition free; every price in §4.1 is reportage); no fetch hashing
differently from the §BH29 record (38/38 equal); the corpus walk reaches
brand2026/ (51 rows, 35 FONT); neither machine ceiling nor guard moved;
both protected regions byte-identical at every commit (GATE
7fbeb8f1fe10b0fb, TEST b32030dc827263e4); the Noto pair
VERIFIED_FOR_PRODUCTION at every commit (measured under Django at each
scoring). The regen's two census-predicted pin classes moved by preview
(34 face_manifest entries; the registry root-of-trust pin) and none other
in the regen. FOUR stops fired in the arc, each reported frozen and ruled
before any fold: the regen sweeping in unruled material (→ (h) NARROW THE
WALK); the T30h refusal on var/-reading tests (→ (i) ONE ATOMIC COMMIT);
the E3 residual of six faces (→ (j) INSIDE THE SHAPE); and a
census-unpredicted pin class on the (d) gate — TREE_CHECKS, the WIT
analyser's denominator — (→ (k)(2) DROP THE ASSERTION, no pin moved).

## 1. Goal (1) — every activated face on the live production path

Measured at final HEAD ba67d5a under the Django shell (`goal_measure.py`, zero-write). The LIVE path today resolves the Noto pair through reportlab; a brand face enters production through the confirmed-font seam of `build_font_authority(doc, confirmed_fonts=...)` (a name and a path, no claims — the guard passes it, the source reads UNDECLARED, the verification stays LICENCE_REVIEW_REQUIRED) and then the owner-grant channel, keyed by sha256. Wiring brand faces onto the emitter's own resolution stays a separate later front.

| Measure | Result |
|---|---|
| Activated faces (the 35 under brand2026) on the confirmed-font seam + channel | 35/35 VERIFIED_FOR_PRODUCTION / USER_CONFIRMED / is_fallback False, sha256 as pinned, licence_evidence = the in-corpus licence path + its sha256, all_production_verified True |
| Same faces through the channel over a bare record (the tests' path) | 35/35 VERIFIED_FOR_PRODUCTION |
| Deferred faces (the §BH29 library files not activated), governed by the walk | 53/53 at LICENCE_REVIEW_REQUIRED / UNDECLARED — honest non-granted (the channel confers nothing on an unnamed sha256) |
| Deferred faces NOT in the walked corpus | 2 — BORELA, Blisey (bytes only under the excluded FONTS 2026 drop) — reported, not measured |

Activated faces by origin: ACQUIRED_UPSTREAM_RELEASE 29, LIBRARY_COPY_HASH_MATCHED 6.
Deferred faces by §BH29 status: BUNDLED 7, OPEN_LICENCE_TEXT_STORED 37, UNRESOLVED 7, FREE_FOR_PERSONAL_USE 3, COMMERCIAL 1.

## 2. Goal (2) — fail-closed proven (negative controls)

Both controls run live at final HEAD against the landed tuple (and pinned by the five (d) tests):

- Hash mismatch: the grant naming Poppins/Poppins-Black.ttf with its licence_evidence_sha256 zeroed ⇒ verification LICENCE_REVIEW_REQUIRED, source PLACEHOLDER_FALLBACK, licence_id empty — the VOID path, a machine value, never an error-shaped pass; the Noto pair, whose grant was not voided, still confers. GREEN.
- Unknown sha256: a real non-font file's record ⇒ returned untouched (verification UNVERIFIED, source PLACEHOLDER_FALLBACK). GREEN.
- No sha256 is named by two grants; every BH30 row names exactly one face; the rows name exactly the 35 corpus faces (test_every_bh30_grant_row_describes_bytes_that_exist_and_hash_as_pinned).

## 3. Goal (3) — gate green, worktree clean, authorities spent

At final HEAD ba67d5a: the gate GREEN on all three legs — the landing's own line `TIER_2=GREEN collected=8510 failures=0 apps=7698 dip0c=671 dip0=141`, worktree clean, ledger clean (every line the gates' own), every commit predicted-then-scored (table §0). Single-use authorities: (b) acquisition SPENT on 87091c1; (i)(2) entry-44 re-pin SPENT on 2ac0fd4; (d) grants SPENT on ba67d5a; no other authority invoked. Both protected regions byte-identical at every commit (GATE 7fbeb8f1fe10b0fb, TEST b32030dc827263e4); neither ceiling nor guard moved; protocol_identity unchanged throughout.

## 4. Goal (4) — purchase list, defers, Noto regression

### 4.1 Purchase list (§BH30(f): reportage only; no spend; the buying sitting is the owner's)

Prices are quoted as the §BH29 hunt stored them from the vendors' own
pages (dates as recorded there); nothing was re-fetched for this report.
"Tier needed" names the vendor's tier that covers print/static packaging
artwork, which is the studio's use — a reading of the vendor's own tier
description, not legal advice.

| Family (library file) | Vendor / where sold | Tier needed for this use | Price as published | Bundled terms already covering |
|---|---|---|---|---|
| BORELA (Borela-6YX71.otf) | MaikoHatta — Creative Market product 27129461; Envato Elements user maikohatta; Creative Fabrica listing named by fontspace | Desktop | Creative Market (fetch-proxy summary, page itself HTTP 403): Desktop $18.00 · Webfont $20.00 · E-pub $36.00 · App $144.00 | none — the free file is PERSONAL USE ONLY by the author's own note |
| Blisey (Blisey.otf) | Syauqi Studio — Gumroad syauqistudio.gumroad.com/l/blisey; MyFonts; Fontspring | Desktop | Gumroad: $21.00 (family) · MyFonts: $17.00 per style, family $21.00 (6 styles; licence types Desktop / Company Desktop / Webfonts / App / Digital Ad-Email / Electronic Doc) | none — the free file is a personal-use demo |
| Figerona Black (FontsFree-Net-Figerona-VF(1).ttf) | Drizy Studio — drizystudio.com/product/figerona/ (own store); drizyfont.com (second own site) | Desktop License (commercial) | drizystudio.com: Personal License $12; Desktop License "1 User, 5 Commercial Project, Unlimited Personal Project, 2 Computer Installation" (price not captured in the stored text); drizyfont.com: Family Package $57.99 (non-commercial personal) / $84.99 (freelance professionals) — the two sites differ, recorded as reportage | none — the dafont file is PERSONAL USE ONLY by the author's own note |
| Nexa Heavy (Nexa-Heavy.ttf) | Fontfabric — fontfabric.com/fonts/nexa/ | Desktop ("print or static digital images, such as logos, packaging" — perpetual) | Desktop from $29 per style; "Nexa - 18 font styles" $175 (includes Nexa Heavy); Complete Family 36 styles $249 | none — retail font; the openly published Fontfabric Commercial EULA is stored, a purchase certificate would be the evidence |
| Square721 BT (bundled with CorelDRAW) | Bitstream → Monotype; retail via MyFonts | Desktop (retail path) if used outside the bundling product | MyFonts: individual styles from $29.99; complete family of 6 $140.99 | Corel: fonts in Corel products are licensed from vendors; "contact Bitstream … not Corel"; the Corel EULA governs redistribution — the bundle covers use inside the Corel product per its EULA (reportage) |

Bundled families with NO purchase proposed (their bundling terms are the
evidence, quoted as stored, not assessed):
- Bauhaus 93, Colonna MT — Microsoft 365 / Office cloud fonts: Office 2024
  terms clause (iv) "use its fonts to display and print content … embed
  fonts in content only as permitted by the embedding restrictions in the
  fonts"; cloud fonts "available to Microsoft 365 subscribers".
- Arial, Bahnschrift — Windows-supplied: Microsoft's font redistribution
  FAQ places no restriction on print output and treats graphic files "as
  essentially the same as printing"; Product Terms "Font Components": display
  and print, embed only as the font's embedding bits permit.
- Adobe Arabic, Myriad Pro — Adobe Acrobat/Reader-supplied ("always available
  in Acrobat and Adobe Reader, and do not need to be embedded"); Adobe Fonts
  library "cleared for both personal and commercial use" for subscribers;
  Adobe's own FAQ says fonts installed in the computer's Fonts folder are
  under their own EULAs — the library's copies are such files, so their
  evidence is the bundling product's EULA, not Adobe Fonts.
- Dubai — Microsoft 365 cloud font AND The Executive Council's own EULA
  (free of charge, "use the fonts freely … private or commercial", "not
  allowed to distribute") — listed under the defers because the official
  EULA page itself was not stored (Font Squirrel mirror only).

### 4.2 Defers (§BH30(g) and the ruling's own list)

Excluded-until-evidence, ungoverned and ungranted, measured below at their
honest non-granted states where their bytes are in the walked corpus:
Komika Axis, 2 Narenj, HASOOB, Hayah, Bebas (original), Dubai — the
ruling's list — plus Hacen Liner XL (UNRESOLVED in the §BH29 record).
GRANTED-NOT-ACTIVATED (open licence text stored, no byte-exact evidence for
the library's bytes): the library's own copies of Cairo (Regular,
SemiBold), Montserrat (8 static files), Poppins (6), Bebas Neue (3), Great
Vibes, Quicksand, Amatic, Merriweather, Playfair Display, Raleway-Thin,
Roboto (2), Shadows Into Light Two, Selima, Nickainley, Goli (5),
ae_AlMothnna — each activates only through its own byte-exact evidence per
§BH30(a). COMMERCIAL (4.1): BORELA, Blisey, Figerona Black, Nexa. Bundled
(4.1). Absent at ≥4 references and not in the corpus: GoodDog, Aquire,
Angora (Grand Hotel was acquired and is activated).

### 4.3 Noto regression at final HEAD

At final HEAD ba67d5a, the live doc (`_doc()`) through build_font_authority + apply_owner_grant with the full tuple (OWNER_GRANT_BH26 first): bold VERIFIED_FOR_PRODUCTION / USER_CONFIRMED / is_fallback False; regular VERIFIED_FOR_PRODUCTION / USER_CONFIRMED / is_fallback False; all_production_verified True; the two sha256s equal OWNER_GRANT_BH26's (True). §BH26 state untouched by the regen: the Noto grant byte-identical, the two Noto face rows byte-identical with the same face ids in the regenerated manifest (E4 held at every regen).

## 5. Records and divergences riding (recorded, not resolved)

- Twelve corpus constants moved where §BH30(j) names eleven: test_c4c.py:269
  (source packages 48→62) was unreached by the printed table because the
  C4c real-corpus test halts at its first failing line; written under
  §BH30(i)(1) "rewritten to the values the re-run measures" — RATIFIED at
  §BH30(k)(1): (j)'s table was the printed extent, not an exclusive list;
  recorded, not a defect; no revert.
- The (d) gate's attempt 1 refused on the WIT analyser's pinned denominator
  (863→864): my appended assertion comparing two counts was the one extra
  check; ruled at §BH30(k)(2) DROP THE ASSERTION — removed, no pin moved,
  the write set unchanged; attempt 1 scored as history.
- The six hash-matched brand2026 copies are six faces the corpus already
  governed (content-derived face ids): re-homed under brand2026, not added
  (E3 = 3,998 = 3,969 + 29) — ruled at (j); enumerated by face id, old path,
  new path in hard_stop_e3_residual_report.txt.
- HEAD's tracked dip0a/dip0c records lagged the §BH26 static/fonts rows
  (never milestone-written); the atomic commit's record diff carries that
  catch-up (+55 rows / +38 fonts / +1 junk vs the records; +51 / +35 / 0 vs
  the corpus) — ruled the same lag at (j).
- The (d) rows carry the §BH26(a) shape's field names granted_by /
  granted_at for the ruling's "approved_by me, approved_at the landing
  date" — a mapping, stated in the commit message.
- BORELA and Blisey have bytes only under the excluded `materials/Fonts/
  FONTS 2026` drop; they are not in the walked corpus at this HEAD and are
  reported, not measured, on the channel.
- The 2026-08-31 var/ bytes are unrecoverable and irrelevant (§BH30(i)(4));
  the var/ state every test now pins is this HEAD's deterministic re-run.
- The T30h transcription attempt 1 refusal stands scored as history
  (finding, not flake; §BH24 budget 0/3 throughout).

## 6. What remains (not started; each its own front or ruling)

- WIRING — brand faces onto the emitter's live resolution (today the live
  doc resolves only the Noto pair; brand faces enter through the confirmed-
  font seam, measured in §1). A separate later front per §BH30's ORDER.
- The three drops (`materials/17-10-2024`, `materials/ALL..MOCKUP`,
  `materials/ADOBE STOCK`) and the `FONTS 2026` library stay excluded by
  ruling; each enters DIP-0A only through its own census and admission
  ruling; ADOBE STOCK only after its licence terms are staged for the
  owner's reading (§BH30(h)(4)).
- The purchase sitting (4.1) is the owner's.
