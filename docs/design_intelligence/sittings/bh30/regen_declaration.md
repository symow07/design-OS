§BH30(e) REGEN DECLARATION — sealed BEFORE the regeneration executes (§BH21(c) discipline).
Written 2026-09-03 with the intake commit in its gate; the regen runs only after that commit LANDS.

WHAT RUNS, in order, from the OUTER root, each as a declared act:
  1. DIP-0A:  bbrose_design_os/venv/bin/python -m tools.dip0.run --milestone
     (walk both corpus roots — materials/ and bbrose_design_os/static/fonts — hash, detect,
     classify; writes var/design_intelligence/audits/dip0/** (untracked) and, with --milestone,
     the committed docs/design_intelligence/dip0a milestone record: summary + pilot manifest).
  2. dip0c C4a: DIP0C_ALLOW_MILESTONE_WRITE=1 … -m tools.dip0c.run_c4a
     (per-face audit over the inventory's FONT rows; writes var/…/dip0c/c4a/** and the tracked
     docs/design_intelligence/dip0c/c4a_family_summary.json + c4a_reconciliation.json).
  3. dip0c C4c: DIP0C_ALLOW_MILESTONE_WRITE=1 … -m tools.dip0c.run_c4c
     (C4a+C4b reused; writes var/…/dip0c/c4c/face_manifest.json etc. and the tracked
     font_review_queue_summary.json, font_batch_review_manifest.json,
     c4c_curated_starter_candidates.json, c4c_reconciliation.json).
  The frozen-milestone guard is opted into EXPLICITLY (DIP0C_ALLOW_MILESTONE_WRITE=1); never
  worked around. materials/ is never written (the runner's pre/post snapshot proves it).

EXPECTATIONS (the measured set governs; each is scored, none is forced):
  E1  DIP-0A inventory rows: 7,590 → 7,641 (+51: the 35 fonts, 15 licence texts and
      PROVENANCE.json under static/fonts/brand2026 — every file the walk reaches).
  E2  FONT-category rows: 4,886 → 4,921 (+35). LICENSE_EVIDENCE rows: 86 → 101 (+15: 14
      OFL-named files by the filename rule + Open_Sans/LICENSE.txt). PROVENANCE.json: one
      row of whatever class the detector gives .json (recorded, not predicted).
  E3  C4a faces: 3,969 → 4,004 (+35) IF every new file yields exactly one face record
      (variable fonts as one record each); files_unique and duplicate counts move by the
      measured overlap (Cairo-Bold.ttf, Montserrat-Regular.ttf, Raleway-Light.ttf,
      Rubik-Bold.ttf, Lato-Black.ttf, OpenSans-Semibold.ttf are byte-identical to files
      already in materials/Fonts/FONTS 2026 → +6 to files_in_duplicate_groups is plausible;
      measured).
  E4  C4c face_manifest rows: 3,969 → 4,004 correspondingly; the two Noto faces' rows
      unchanged in content (face ids face-327979ef…, face-ac29d83a…) — REGRESSION CHECK.
  E5  The hardcoded pins that move (pass 2 rewrites by measurement): test_c4a.py:311-315
      (4886/3944/941/1883), test_c4c.py:265-270 (4886/3944/3969/2834/48/941),
      test_c5.py:307-309 (3969/1880/3), test_c4b.py:371/481-482 (933/706/130) — only those
      the regen actually moves; each written to its measured value.
  E6  Tracked files that move: docs/design_intelligence/dip0a/{summary.md, pilot_manifest.json}
      (+ any other milestone file the runner refreshes — recorded), docs/design_intelligence/
      dip0c/{c4a_family_summary.json, c4a_reconciliation.json, c4c_curated_starter_candidates
      .json, c4c_reconciliation.json, font_batch_review_manifest.json,
      font_review_queue_summary.json}. The tree seals dip0c 36f08a31ad581c3b and dip0a
      2e339a7e23a46c00 MOVE (they are corpus records here, not protected regions).
  E7  NO record digest moves (record_integrity roots = docs/roadmap only); NO
      protocol_identity move; NO suite-manifest regeneration (no test file added). A pin
      CLASS outside E5/E6 is the hard stop.
  E8  The gate's dip0c leg (671) and dip0 leg (135) counts do not change (no test added).
  E9  The Noto pair VERIFIED_FOR_PRODUCTION under Django after the regen (hard stop).

COMMITS AFTER THE REGEN (each 8-leg): (i) DOCS — the moved milestone files, as measured;
(ii) PASS 2 — the test constants, measured values only (pass 1 is EMPTY: nothing measured
wrong before the regen — recorded); then (d) GRANTS.

ADDENDUM (measured after sealing, before the regen; the seal above stands): the committed
docs/design_intelligence/dip0a/summary.md still reads "Indexed files: 7586" — the 2026-08-31
regen (§BH20(b)) wrote var/ only and did not use --milestone. So E6's summary.md /
pilot_manifest.json move from the ORIGINAL milestone values (7586 indexed, 109 junk, 1017 dup
groups …) to the measured post-intake values, not from 7,590. var/'s inventory moves 7,590 →
measured (E1). Recorded so the docs commit's diff is read correctly.
