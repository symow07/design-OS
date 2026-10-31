§BH37(3) REGEN DECLARATION — sealed BEFORE the re-run under the three deleted lines of (2).
Written 2026-09-05, base HEAD = the (1) landing. Every expectation below is measured from the §BH35
census, the §BH36/§BH37 quarantine record and DIP-0A's own rules applied to the census rows, or
stated as NOT pre-declared (rewritten to the re-run's own measurement, previewed before the write).

THE WALK: the three folders enter; materials/Fonts/FONTS 2026 and materials/FONTS 2026 stay excluded.
  On disk in the three folders: 4,912 files (the §BH35 census 4,927 minus 15 quarantined — the owner's
  13 of §BH36(d) plus the two archives carrying executable content, quarantined under (d)'s last
  sentence before this run and recorded as a divergence from (2)'s "minus the 13"); 88,847,101,882 B.
  DIP-0A's junk rule (config.JUNK_NAMES/JUNK_GLOBS) drops 79 of them (78 Thumbs.db, one ~ai-…tmp),
  counted as junk, never rows; no directory under the three is a SKIP_DIR_NAME or hidden.
E1  inventory rows            7,641 → 12,474   (+4,833 = 4,912 − 79 junk)
E2  categories, PREVIEW by DIP-0A's classifier applied to the census rows (signature approximated;
    the run decides the exact split — a difference is reported, not folded):
      FONT 4,921 → 5,212 (+291: 203 .ttf, 86 .otf, 1 .woff, 1 .woff2 — every font file by magic);
      LICENSE_EVIDENCE 101 → 261 (+160); PRODUCT_REFERENCE 90 → 1,604 (+1,514);
      REUSABLE_VECTOR_ASSET 374 → 1,726 (+1,352); RASTER_DESIGN_ASSET 1,292 → 2,219 (+927);
      PATTERN 241 → 459 (+218); BACKGROUND 198 → 400 (+202); MOTIF 137 → 190 (+53);
      ICON 63 → 107 (+44); OUT_OF_SCOPE 48 → 75 (+27); UNKNOWN 1 → 26 (+25: 18 .rar, .ovpn, .jpf …);
      ARCHIVE 76 → 95 (+19); COLOR_PALETTE 1 → 2 (+1); the rest unchanged.
E3  C4c faces                 3,998 → 4,182   (+184: of the 291 font files, 107 have a sha256 already in
    the corpus — the same face by content, C4c's face id = f(sha256, index, PostScript name) — and 184
    mint new ids; no TTC among them)
E4  the two Noto face rows byte-identical in content, same face ids; the 35 brand2026 faces unchanged
E5  the constants pass (one pass, each literal previewed from the re-run's own outputs immediately
    before the write and re-read after): test_c4a.py:311 4921→5212, :313 3973→4157, :314 942→1047,
    :315 1890→2102; test_c4c.py:265 4921→5212, :266 3973→4157, :267 3998→4182, :270 942→1047;
    NOT pre-declared (rewritten to the measured value): test_c4c.py:268 family groups (2,837 today),
    :269 source packages (62 today); test_c5.py:307 3998→4182, :308 rights groups (1,887 today);
    test_c4b.py:481/482 (706/130, computed live — measured, may move).
E6  tracked files that move: the eight records — docs/design_intelligence/dip0a/{summary.md,
    pilot_manifest.json}, dip0c/{c4a_family_summary.json, c4a_reconciliation.json,
    c4c_curated_starter_candidates.json, c4c_reconciliation.json, font_batch_review_manifest.json,
    font_review_queue_summary.json}; the tree seals dip0c 5ae44035bd03bae1 and dip0a 4fe747b806ed71bd
    MOVE (records, not protected); tools/dip0/config.py (three deleted lines + the comment);
    tools/dip0/tests/test_corpus_roots.py (five → two, the three admitted proved walked); the twelve
    literals' files; docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json (34 entries → the
    regenerated face_manifest's sha256 by preview) and dip1b_evidence_integrity_registry_1_0.json
    (one pin → the manifest's bytes as written, by preview).
E7  NO docs/roadmap record moves but the gate's ledger; NO protocol_identity move; NO apps/ path;
    NO suite-manifest regeneration; the GATE/TEST regions byte-identical; a pin class outside E5/E6
    is the hard stop.
E8  the gate's dip0c leg 671 and dip0 leg 141 (the fixture tests re-anchored, count unchanged).
E9  the Noto trio VERIFIED_FOR_PRODUCTION under Django after the re-run and at scoring; the 35 at
    their PROVENANCE hashes.
E10 the runner prints the TWO excluded entries with their bytes (FONTS 2026 [dir] 4,084 files
    1,524,268,923 B; the alias [file] 1,040 B); ZERO rows under either; the 15 quarantined paths
    absent from the inventory (not on disk); junk 79 counted; the walk's row count for the three
    folders 4,833 exactly.
E11 VERIFIED faces after the regen: exactly the 38 whose sha256 the owner grants name (35 brand2026
    + the Noto trio); none of the 291 drop fonts shares a granted sha256 (measured: 0), so no drop
    font is the same face as a granted one; every drop font's face rows carry machine states only.
E12 NO executable content surfaces: the 19 remaining zips carry no executable entry by the §BH35
    listing; DIP-0A's archive inspection (zip `suspicious[]`) is read after the run — any hit is
    the hard stop, reported.
A residual beyond E1/E3 is REPORTED with its explanation (content identity as at §BH30(j), or the
classifier's signature split) and RULED, not rounded.
