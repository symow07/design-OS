# §BH37 GOAL REPORT — MATERIALS ADMISSION BUILD

Written 2026-09-05 at final HEAD 9241e90. Every number below is measured at
that HEAD unless it names the commit it was measured at. The owner's text is
transcribed at T37 (OWNER_BLOCKER_CLEARANCE.md, 19,363 → 19,516); the work
directory is ~/bh37_work/ (predictions, seals, scores, declarations, logs).

## 0. The commit chain (every commit predicted-then-scored)

| Commit | Concern | Prediction → score |
|---|---|---|
| e9f087a | T37 — §BH37 transcribed (pure append, 153 lines: the owner's typed lines verbatim, the receipt measurement, three readings for the owner) | pred_t37 27b81ec69c5c4fef → 8/8 |
| 2463f29 | (1) THE TIER MODEL IN CODE — materials_authority (two tiers, the ceiling by substance, the guard with two disjoint refusals, the machine record) + materials_owner_grant (the channel, keyed by sha256, evidence re-hashed on every application, fail-closed), nine tests incl. both negative controls; no rows, no regen | pred_tiers 7e0cd2ce6281f1aa → 8/8 |
| 86f8ccd | (2)+(3) ONE ATOMIC COMMIT — the three deleted exclusion lines (FONTS 2026 and the alias stay), the re-run under the sealed declarations (run 1 0b8db28f3c3a1670 → the E12 finding; run 2 5a72b040ccbb71c6 → every expectation HELD), the seven regenerated records, the twelve constants by preview, the dip1b re-pin by preview (34 entries + the registry pin); the re-pin authority spent | pred_atomic 8b3043ab6b5c66ae → 8/8 |
| 9241e90 | (4) TIERS ASSIGNED — every admitted row REFERENCE by machine (materials_tier/1.0 over the regenerated inventory); the PRODUCTION grants for the PERMISSIVE and ATTRIBUTION-REQUIRED packs through the channel, scoped to the pack, evidence pinned, credit verbatim; single-use authority spent on landing | pred_grants 9396eb589755d287 → 6/8 (one false sub-claim stated in two legs — the dip0a tree seal; §3 item 9) |

Gate runs: four, one per commit, each GREEN on its first launch (§BH24 budget
stays at 1/3 from T35 run 1; no refusal in §BH37). Ledger 468 → 472, append-only
at every step.

## 1. Goal state, measured at final HEAD

**Every file at a measured tier.** The tier record
`var/design_intelligence/audits/dip0/tiers/materials_tiers.jsonl` (untracked
audit output beside DIP-0A's; sha256 a38270318b0d0399…, 1,429,427 B, named by
the tracked summary `docs/design_intelligence/dip0a/materials_tiers_summary.json`)
carries ONE row per inventory row of the three folders: 4,832 rows, every one
joined to the inventory by path AND sha256 (4,832/4,832 present, 4,832/4,832 same
sha256, measured at report time).

**Reconciliation to the owner's 4,914.**

| Step | 17-10-2024 | ALL..MOCKUP | ADOBE STOCK | Total |
|---|---|---|---|---|
| §BH35 census (T35, all hashed) | 1,735 | 1,702 | 1,490 | 4,927 |
| − §BH36(d) quarantine (13 executables: 4 installers; the 8 KMS files + sagethumbs setup) | −4 | −9 | 0 | 4,914 = the owner's number |
| − §BH36(d)'s last sentence, applied at §BH37: AnyDesk_Reset.rar; the cracked Illustrator installer zip; its wrapper zip (DIP-0A's nested-archive flag at regen run 1, sole entry = that installer) | −3 | 0 | 0 | 4,911 on disk now |
| − junk names the walk never admits (.DS_Store and kin) | −0 | −78 | −1 | 4,832 rows |

Note: the 16 quarantined paths split 7 under 17-10-2024 and 9 under
ALL..MOCKUP (the 13 of §BH36(d) plus the three above); on disk now 1,728 /
1,693 / 1,490 = 4,911; the per-drop rows are
1,728 / 1,615 / 1,489 = on-disk files minus junk = 1,728−0 / 1,693−78 / 1,490−1.
The owner's 4,914 differs from the walked 4,911 by exactly the three further
quarantines, each recorded in ~/bh36_work/quarantine_record.json (batches 2 and
3; 16 files / 8,136,268,896 B, all hash-verified before and after the move,
never opened, never executed).

**Counts per tier per class, reconciling to 4,832** (class = DIP-0A's category
on the inventory row; tier = the record):

| Category | REFERENCE | PRODUCTION | Total |
|---|---|---|---|
| ARCHIVE | 18 | 0 | 18 |
| BACKGROUND | 202 | 0 | 202 |
| COLOR_PALETTE | 1 | 0 | 1 |
| FONT | 291 | 0 | 291 |
| ICON | 44 | 0 | 44 |
| LICENSE_EVIDENCE | 143 | 17 | 160 |
| MOTIF | 53 | 0 | 53 |
| OUT_OF_SCOPE | 27 | 0 | 27 |
| PATTERN | 218 | 0 | 218 |
| PRODUCT_REFERENCE | 1,500 | 14 | 1,514 |
| RASTER_DESIGN_ASSET | 925 | 2 | 927 |
| REUSABLE_VECTOR_ASSET | 1,352 | 0 | 1,352 |
| UNKNOWN | 25 | 0 | 25 |
| **Total** | **4,799** | **33** | **4,832** |

Per drop: 17-10-2024 1,724 REFERENCE + 4 PRODUCTION; ALL..MOCKUP 1,586 + 29;
ADOBE STOCK 1,489 + 0 (reference-only by §BH36(b)). Every REFERENCE row is
MACHINE-sourced (the machine wrote nothing above the ceiling — the guard's
MACHINE_WRITABLE_TIERS = ("REFERENCE",)); every PRODUCTION row is
OWNER_GRANT-sourced. All 291 font files in the three folders are REFERENCE
(84 / 204 / 3 per drop) — none reachable by the font layer, which resolves
only from the font catalogue (unchanged: see below).

**The PRODUCTION rows (33), re-verified at report time.** Ten grants, one per
governing-text INSTANCE (the text's path beside ITS pack); 33 (sha256, path)
pairs, no pair twice; every evidence path lies inside the pack of every row it
raises; every evidence sha256 re-hashed at report time == the pinned value
(33/33; the channel re-hashes on every application, and the test
`every PRODUCTION row re-verifies its evidence` does it again under the gate).

| Pack (evidence = the text beside it) | Class | Rows | Credit condition (verbatim, both forms the text states) |
|---|---|---|---|
| 17-10-2024/pile-online-shopping-package-mockups/License free.txt | ATTRIBUTION-REQUIRED | 4 (65757.jpg, 65757.psd, both texts) | `<a href="http://www.freepik.com">Designed by rawpixel.com / Freepik</a>` \| "Designed by rawpixel.com / Freepik" |
| ALL..MOCKUP/27-4-2024/logo-mockup-luxury-box/License free.txt | ATTRIBUTION-REQUIRED | 4 (130.jpg, 130.psd, both texts) | … Designed by asylab / Freepik … |
| ALL..MOCKUP/27-4-2024/green-packaging-cosmetic-products(2)/License free.txt | ATTRIBUTION-REQUIRED | 4 (2512865.jpg, 2512866.psd, both texts) | … Designed by Freepik … |
| ALL..MOCKUP/27-4-2024/delicious-summer-fruits/License free.txt | ATTRIBUTION-REQUIRED | 5 (.eps, .jpg, .ai, both texts) | … Designed by Freepik … |
| ALL..MOCKUP/عبوات مواد تجميل/makeup-realistic-items-super-set…/License free.txt | ATTRIBUTION-REQUIRED | 4 (16260.eps, 16260.jpg, both texts) | … Designed by macrovector / Freepik … |
| ALL..MOCKUP/عبوات مواد تجميل/cosmetics-package-realistic-transparent-set/License free.txt | ATTRIBUTION-REQUIRED | 4 (18207.eps, 18207.jpg, both texts) | … Designed by macrovector / Freepik … |
| ALL..MOCKUP/عبوات مواد تجميل/nail-polish/License free.txt | ATTRIBUTION-REQUIRED | 4 (7077.eps, 7077.jpg, both texts) | … Designed by macrovector_official / Freepik … |
| ALL..MOCKUP/27-4-2024/fonts bold/coolvetica/Typodermic Desktop EULA 2023.pdf | PERMISSIVE | 2 (the EULA pdf, read-this.html) — the font files REFERENCE | (none) |
| ALL..MOCKUP/27-4-2024/fonts bold/codex/codex.txt | PERMISSIVE | 1 (the text) — the font files REFERENCE | (none) |
| ALL..MOCKUP/27-4-2024/baloo/SIL Open Font License.txt | PERMISSIVE | 1 (the text) — the font files REFERENCE | (none) |

29 rows carry the condition (ATTRIBUTION-REQUIRED → PRODUCTION WITH CONDITION;
the enforcement of the credit belongs to the wiring front, as ruled); 4 rows
PERMISSIVE without condition. The exact credit strings are in the grant tuple
(`apps/ire/materials_owner_grant.py`, MATERIAL_GRANTS) and on every row.

**Both negative controls green** (the channel's test file, under the gate):
(i) evidence re-hashing to a different sha256 → the row stays REFERENCE and
carries `grant_void` naming both hashes; (ii) a sha256 no grant names → the
row untouched; plus the §BH37(4) scope control: the same bytes outside the
granted pack stay REFERENCE (50 such copies measured — the ADOBE STOCK EDUME
packs carry the same Freepik texts; the `18207` and `16260` pairs recur under
17-10-2024 — all REFERENCE).

**Font theme unchanged.** Under Django at 9241e90 (~/bh33_work/django_l8.py): the catalogue holds 38 faces; NotoSans-Regular, NotoSans-Bold and NotoNaskhArabic-Regular are VERIFIED_FOR_PRODUCTION (USER_CONFIRMED; sha256 478c558ea716033c…, 1df075a380fc7cb8…, 6f0a92031367b2f5…); the 35 (+ their licence texts, 50 files) sit at their PROVENANCE hashes; CHAINS arabic-display/heading/body = (NotoNaskhArabic-Regular,); arabic-capable = [NotoNaskhArabic-Regular]. Nothing new VERIFIED. No font file of the three folders is in the catalogue: the font layer resolves from static/fonts only, and every one of the 291 drop fonts is a REFERENCE row of the materials record.

**Gate green, worktree clean, ledger clean, every commit scored.**
The (4) gate: `TIER_2=GREEN collected=8569 failures=0 apps=7757 dip0c=671 dip0=141` (the atomic gate: 8564 / 7752 / 671 / 141; the five appended tests are the difference). Ledger 471 → 472 at 9241e90 (HEAD~1 a byte-prefix of HEAD; the new line verdict OK, refusal_count 0, records_checked 1,738); 468 → 472 across §BH37. Porcelain clean at report time, untracked included; the DIP-0A inventory untouched since regen run 2 (sha256 3b3cfdc2bf4fc6c0…, 31,026,591 B); the three folders hold 1,728 / 1,693 / 1,490 files, none newer than the T37 transcription; the quarantine holds its 16 files. Both authorities of §BH37 —
the dip1b re-pin (spent at 86f8ccd) and the grants (spent at 9241e90) —
were spent only on their landings; the channel carries no other row.

**M7 and the protected regions byte-identical.** GATE 7fbeb8f1fe10b0fb at [514:541] of the 593-line container_font_authority.py; TEST b32030dc827263e4 (the a76242c^ blob, [82:98]); the eight M7 artefacts == ~/bh32_work/m7_baseline.txt; protocol_identity untouched; the apps/ diff of the whole §BH37 chain is the two materials modules, their tests and nothing else. Tree seals at 9241e90: dip0c c22592930c75001c (unchanged since 86f8ccd), dip0a c378ee88026e1223 (moved by the new summary file — §3 item 9).

## 2. The regen against its declaration (E1–E12)

Run 1 (declaration 0b8db28f3c3a1670): every expectation HELD but E12 — DIP-0A's
archive inspection flagged `materials/17-10-2024/AdobeIllustrator2024.zip`
(nested_archives; its sole entry the cracked installer already quarantined).
The hard stop fired; the run was NOT landed; the wrapper was quarantined under
§BH36(d)'s last sentence (hash-verified, never opened), and run 2 ran under a
new sealed declaration (5a72b040ccbb71c6). Run 2, measured
(~/bh37_work/regen_measured.json):

| E | Declared | Measured |
|---|---|---|
| E1 | inventory rows 7,641 → 12,473 (+4,832 = 4,911 − 79 junk) | 12,473; the three folders 4,832 — HELD |
| E2 | categories by the classifier's preview; a difference reported, not folded | FONT 5,212, LICENSE_EVIDENCE 261, PRODUCT_REFERENCE 1,604, REUSABLE_VECTOR_ASSET 1,726, RASTER_DESIGN_ASSET 2,219, PATTERN 459, BACKGROUND 400, MOTIF 190, ICON 107, OUT_OF_SCOPE 75, UNKNOWN 26, ARCHIVE 94, COLOR_PALETTE 2 — as previewed |
| E3 | C4c faces 3,998 → 4,182 (+184 new ids) | 4,182 — HELD |
| E4 | the two Noto face rows unchanged, same ids | HELD (face-327979ef355ce8ccd570, face-ac29d83abf6138679264) |
| E5 | the constants pass by preview | twelve literals rewritten to the measured values, each previewed then re-read: c4a 5212/4157/1047/2102; c4c 5212/4157/4182/2841/137/1047; c5 4182/2099; c4b 706/130 held |
| E6 | the eight records move; the tree seals move; config, the fixture tests, the twelve literals' files, the dip1b manifest + registry | SEVEN records moved — c4c_curated_starter_candidates.json came back byte-identical (recorded divergence: the curated starter set unchanged by the new faces); seals → dip0c c22592930c75001c, dip0a cac81c9c1ba5fade; 34 entries → 9697b040eae2622b… (12,310,903 B); registry pin → 7d31d29ff4e50093… |
| E7 | no docs/roadmap record but the ledger; no identity; no apps/ path; no suite-manifest regen; GATE/TEST regions byte-identical | HELD (E7_roadmap_moved = [], E7_apps_moved = []) |
| E8 | dip0c leg 671, dip0 leg 141 | HELD at the atomic gate: dip0c=671 dip0=141 |
| E9 | the Noto trio VERIFIED_FOR_PRODUCTION; the 35 at their PROVENANCE hashes | HELD at scoring (django_l8) |
| E10 | the TWO excluded entries printed with bytes; zero rows under either; the quarantined paths absent; junk 79 | FONTS 2026 [dir] 4,084 files 1,524,268,923 B; the alias [file] 1,040 B; 0 rows under excluded; 16 quarantined paths absent — HELD |
| E11 | exactly the 38 granted faces VERIFIED; no drop font shares a granted sha256 | 38 / 0 — HELD |
| E12 | no executable content surfaces | run 1: the wrapper zip (above) → quarantined; run 2: suspicious_archives = [], executable_rows = [] — HELD |

## 3. Recorded, not repaired / not resolved (the sentence governs)

1. **The walk sees the census minus 16, not 13.** Three further quarantines under
   §BH36(d)'s last sentence (AnyDesk_Reset.rar; the cracked Illustrator installer
   zip with Crack/*.bat; its wrapper zip). The owner's "4,914" is the census minus
   13; the walk's 4,911 is the census minus 16. Emptying the quarantine is the
   owner's act.
2. **Seven records moved, not eight.** c4c_curated_starter_candidates.json
   byte-identical after the regen (the curated starter set does not draw on the
   new faces).
3. **Scope by path narrows "keyed by sha256".** The ruling says one row per file
   keyed by sha256; the channel raises a row only when its sha256 is named AND
   its path lies in the pack the evidence sits beside. Without the scope the same
   bytes would have been raised in ADOBE STOCK (REFERENCE by (b)) and in packs
   with no PRODUCTION-ruled text (83 rows in the unscoped dry run). 50 same-sha256
   copies outside scope are REFERENCE; 7 byte-identical files that sit in two
   granted packs are named by BOTH packs' grants (each with its own path).
4. **Ten grants, one per governing-text INSTANCE.** The dry run grouped by the
   text's content (8 grants; two of them spanning two packs with the evidence
   path in only one of them). "Evidence = text's path + sha256 beside the pack"
   read literally makes the same bytes beside two packs two grants, each pinned
   to its own copy: the delicious-summer-fruits and cosmetics-package-realistic-
   transparent-set packs got their own grants (same evidence sha256, own path).
   Measured: every evidence path inside the pack of every row it raises.
5. **The terms texts themselves are PRODUCTION rows (17 of the 33).** A
   permissive or attribution text governs every file in its pack including its
   own file and the sibling "License premium.txt" (reach rule). If the owner
   meant only the design assets, the 17 LICENSE_EVIDENCE rows (and the coolvetica
   EULA pdf, category PRODUCT_REFERENCE by DIP-0A's classifier) return to
   REFERENCE by one ruling.
6. **The Freepik pairs.** Each Freepik pack carries "License free.txt"
   (ATTRIBUTION-REQUIRED) and "License premium.txt" (Freepik-premium-conditional
   → REFERENCE as a governing text). The pack is governed by the free text: the
   owner holds no premium account on the record, the free text's terms apply,
   the credit is the condition. The premium text's presence does not block the
   pack (the §BH36 reading carried into T37); the premium text FILE is a row of
   the pack (item 5).
7. **The (1) empty-channel pin retargeted.** `test_the_channel_lands_with_no_rows_at_bh37_1`
   asserted MATERIAL_GRANTS == (); (4) fills the tuple, so the pin now asserts the
   (4) state (filled, every grant well-formed) — the only edit above the appended
   test section; no new test file, the suite manifest untouched.
8. **The written tuple and its preview.** The 10-grant tuple was written by the
   run that also wrote its preview (material_grants_preview.json); the written
   value equals the preview as a set (grant order differs: the module sorts by
   evidence path). The earlier separate dry run previewed the same 33 (sha256,
   path) pairs, credits and evidence sha256s under the 8-grant grouping; the
   only values that first appeared in the writing run are the evidence PATHS of
   the two split packs (their own copies of the same text). Recorded against the
   hard stop "a written value differing from its preview" for the owner to read.
9. **The prediction's tree-seal sub-claim.** pred_grants declared the dip0a tree seal unchanged while declaring the new summary file, which lives in that tree — a self-inconsistency of the prediction, scored as a miss in L3 and L8 (6/8). No ruled pin class moved: the only file that moved in the tree is the declared one, and dip0c's seal proves the sibling tree unchanged.
10. **The owner's 4,914 vs the measured 4,911 / 4,832** — item 1 and the 79 junk
    names; no file is unaccounted for.

## 4. Hard stops (verbatim), with the measurement

- *any executable content surfacing during regen* — FIRED once, at regen run 1
  (E12: the wrapper zip). The run was not landed; the finding was treated under
  §BH36(d)'s last sentence ("Any further executable content the sort surfaces is
  treated the same and reported"): quarantined with hash verification, never
  opened, never executed; run 2 under a new sealed declaration surfaced nothing.
- *any PRODUCTION row without evidence* — never fired: 33/33 rows carry
  `evidence` = path + sha256, re-verified at report time.
- *any font outside the 35 + trio becoming VERIFIED* — never fired (E11 38/0 at
  the regen; the theme measured at final HEAD in §1).
- *FONTS 2026 or the alias entering the walk* — never fired (E10: both entries
  still excluded and printed with their bytes; 0 rows under either; the
  exclusion list untouched since 86f8ccd).
- *a census-unpredicted pin class* — never fired: every pin class that moved
  (the seven records, the twelve literals, the 34 entries, the registry pin) was
  declared before the re-run and predicted before the landing; nothing moved
  at (4) but the three declared paths and the ledger.
- *either ceiling or guard of the font module moving* — never fired:
  container_font_authority.py untouched across §BH37 (GATE 7fbeb8f1fe10b0fb at
  [514:541], TEST b32030dc827263e4, measured at every landing).
- *any M7 artefact changing* — never fired: the eight artefacts ==
  ~/bh32_work/m7_baseline.txt at every landing.
- *a written value differing from its preview* — never fired in content: the
  twelve literals and the two dip1b pins re-read after the write; the grant
  tuple equal to its preview as a set (item 8 of §3 records the sequence).

## 5. What remains

- The owner reads §3 (items 3–6 and 8 are readings the owner can overrule by a
  sentence; each returns rows to REFERENCE or raises none — no regen needed).
- The wiring proposal half for colours and materials, in §BH31's shape, is the
  next front per the owner's closing sentence — nothing of it is built.
- The credit condition on the 29 attribution rows is CARRIED, not enforced;
  enforcement belongs to the wiring front, as ruled.
- The quarantine (16 files, 8,136,268,896 B under ~/bh35_work/quarantine/) waits
  on the owner's act.
- The 14 UNCLEAR, 4 PERSONAL-USE-ONLY and 26 PURCHASE-REQUIRED texts and the
  NO-EVIDENCE packs stay REFERENCE by ruling; ADOBE STOCK stays reference-only
  "for now" — any change is a ruling, then one grant commit through the channel.
