§BH30(h)(3) FRESH REGEN DECLARATION — sealed BEFORE the re-run under the ruled exclusion.
The prior declaration (regen_declaration.md, 5e42379dfb800966) stands FALSIFIED as history
(E1/E2/E3 falsified by the sweep; E4/E6/E7 held). Written 2026-09-03.

RULED EXPECTATION (§BH30(h)(3)): "HEAD's corpus plus exactly the 51 brand2026 rows / 35 faces —
a residual delta beyond that is a hard stop, not a rounding." HEAD's corpus = the 2026-08-31
state the inventory carried before the intake: 7,590 rows; FONT 4,886; LICENSE_EVIDENCE 86;
C4a/C4c 3,969 faces. So:
  E1  inventory rows            7,590 → 7,641   (+51 exactly: 35 fonts, 15 licence texts,
                                                 PROVENANCE.json)
  E2  FONT rows                 4,886 → 4,921   (+35); LICENSE_EVIDENCE 86 → 101 (+15);
      PROVENANCE.json's category recorded as measured (it classified UNKNOWN in the swept run —
      recorded, not predicted; one row either way)
  E3  C4a/C4c faces             3,969 → 4,004   (+35: one record per new file; variable fonts
                                                 one record each)
  E4  the two Noto face rows byte-identical in content, same face ids (regression)
  E5  the constants pass 2 rewrites: only those the re-run moves, each to its measured value
      (test_c4a.py:311-315, test_c4c.py:265-270, test_c5.py:307-309, test_c4b.py as measured)
  E6  tracked files that move: docs/design_intelligence/dip0a/{summary.md, pilot_manifest.json}
      (from the ORIGINAL milestone values, 7,586 indexed — the Aug-31 regen never wrote the
      milestone) and docs/design_intelligence/dip0c/{c4a_family_summary.json,
      c4a_reconciliation.json, c4c_curated_starter_candidates.json, c4c_reconciliation.json,
      font_batch_review_manifest.json, font_review_queue_summary.json}; the tree seals move
  E7  NO record digest moves; NO protocol_identity move; NO suite-manifest regeneration; a pin
      CLASS outside E5/E6 is the hard stop
  E8  the gate's dip0c leg 671 and dip0 leg 135 + the six new exclusion tests (dip0 = 141)
  E9  the Noto pair VERIFIED_FOR_PRODUCTION under Django after the re-run and at every commit
  E10 the runner prints the five excluded entries with their bytes; the excluded set's rows
      are ABSENT from the inventory (0 rows under any of the five); indexed bytes return to
      the Aug-31 scale (29.90 GB + 7.4 MB), duplicate groups near 1,017 (+ the six
      byte-identical library copies now also under brand2026 — measured, stated)
A residual delta beyond +51 rows / +35 faces is a HARD STOP (report, do not fold).
