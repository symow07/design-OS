§BH25 STAGING REPORT — THE ONE REPORT, THEN STOP
=================================================
Goal: OWNER GOAL §BH25 (OFL READING, STAGING HALF), transcribed 18ab440.
Executor half only: licence text and complete authority state put in front
of the owner, verbatim and measured. NOTHING is interpreted here. The
reading is the owner's reserved act; the ruling comes as §BH26, after.

Report time: 2026-09-01. HEAD 18ab440. Porcelain EMPTY. Ledger 429==429.
HARD STOPS: NONE FIRED (verdicts measured in §1 and §4 below).

────────────────────────────────────────────────────────────────────────
§0 THE GOAL'S ONE COMMIT — T25, PREDICTED 8-LEG AND SCORED
────────────────────────────────────────────────────────────────────────
Commit 18ab440 (parent 5fa5275), message t25_msg.txt: "docs(§BC):
transcribe OWNER GOAL §BH25 — OFL reading staging half, one pure append
before any staging act".

Prediction ~/bh25_work/pred_t25.txt, SEALED before `git add`, before the
gate. SCORE: ZERO MISS.
  L1  write set: register only (mine) + ledger line (gate's)     MATCH
  L2  diff shape: +100 −0 register, +1 −0 ledger, +101 −0 / 2    MATCH
  L3  manifest/A391: no new tracked file                          MATCH
  L4  staged==declared both halves                                MATCH
  L5  commit contents: the 100-line §BC block, placeholders 0     MATCH
  L6  TIER_2=GREEN collected=8490 failures=0 apps=7684
      dip0c=671 dip0=135 — attempt 1, §BH24 standing UNUSED       MATCH
  L7  ledger 428 → 429 == 429 CLEAN (fold +1 −0)                  MATCH
  L8  empty `git diff 5fa5275 18ab440 -- bbrose_design_os/apps/`  MATCH
  C1–C5 all matched. Exit hand-captured: t25_exit.txt `exit=0`;
  two landing confirmations (exit 0 AND new HEAD, parent 5fa5275).
Pure append proved: +100 −0 numstat; 16,789-line HEAD-prefix diff rc=0.
Register 16,789 → 16,889 lines. No further commits in this goal.

────────────────────────────────────────────────────────────────────────
§1 CLAUSE (1) — EVIDENCE LOCATED BY MEASUREMENT, NOT MEMORY
────────────────────────────────────────────────────────────────────────
THE WALK (join → inventory → disk):

Step 1 — the ruled join start.
  var/design_intelligence/audits/dip0c/c4c/face_manifest.json
  (OUTER root var/ — measured; the inner bbrose_design_os/var/ tree has
  NO such file, checked first and refused from memory). 11.6 MB, schema
  font_face_manifest/1.0, 3,969 rows. The two container faces:

  face-327979ef355ce8ccd570  NotoSans-Regular
    → bbrose_design_os/static/fonts/NotoSans-Regular.ttf
    sha256 478c558ea716033cd60c03438f628dfa75694dcf6b5f6d505a2f05fd2b4f3823
  face-ac29d83abf6138679264  NotoSans-Bold
    → bbrose_design_os/static/fonts/NotoSans-Bold.ttf
    sha256 1df075a380fc7cb898acf64c1f7b3b4dd780de3caa860178bf929de35817a913

  Both rows: license_evidence [], license_evidence_mentioning_fonts [],
  source_package "bbrose_design_os/static/fonts". Row counts: exactly 2
  by face_id, exactly 2 by postscript_name. Rows extracted verbatim to
  ~/bh25_work/face_row_regular.json / face_row_bold.json.

Step 2 — back through the DIP-0A inventory.
  var/design_intelligence/audits/dip0/inventory/inventory.jsonl
  (20.1 MB, 7,590 rows, regenerated 2026-08-31 under §BH20(b)/§BH21).
  The 4 rows under bbrose_design_os/static/fonts
  (~/bh25_work/inventory_static_fonts_rows.jsonl):
    3 × ttf  — category.value FONT (extension_rule, confidence 0.95),
               license_evidence [], license_evidence_strength "none",
               license_status UNVERIFIED ("no licence file in scope"),
               review_required true
    OFL.txt  — category.value LICENSE_EVIDENCE (filename_rule, evidence
               ["filename=OFL.txt","ext=.txt","strength=strong"],
               confidence 0.9), review_required false
  DIP-0A relabels OFL.txt-class files as LICENSE_EVIDENCE — hence the
  ruled two-shape search below.

Step 3 — on-disk source under the corpus roots.
  bbrose_design_os/static/fonts/ holds exactly 4 files: the 3 ttf + one
  OFL.txt. On-disk ttf sha256s measured == the manifest values above
  (identity confirmed by hash, not name).

SEARCH EXTENTS — TWO KEY SHAPES, COUNTS RECONCILED BY SET JOIN:

  Shape A (CLASS): jq `.category.value == "LICENSE_EVIDENCE"` over ALL
  7,590 inventory rows (extent: the entire DIP-0A inventory, which
  covers both corpus roots) → 86 rows = 85 under materials/ + 1 under
  bbrose_design_os/static/fonts. All 86 verified to exist on disk.
  Artifact: ~/bh25_work/inventory_license_evidence_rows.tsv.
  (Measurement honesty: a first query keyed `.category ==
  "LICENSE_EVIDENCE"` returned 0 because `category` is an object; the
  corrected key `.category.value` returned the 86 the histogram
  predicted.)

  Shape B (FILENAME): find, case-insensitive name patterns OFL*,
  LICENSE*, LICENCE*, COPYING*, UFL*, over BOTH corpus roots
  (materials/ and bbrose_design_os/static/fonts) → 54 files.
  Artifact: ~/bh25_work/disk_licence_named_files.txt. RE-RUN AT REPORT
  TIME: byte-identical to the artifact (REFIND_IDENTICAL, 54).

  Reconciliation: filename-not-class = 0 (every filename-shape hit
  carries the class). Class-not-filename = 32 (listed complete in
  ~/bh25_work/class_not_filename.txt: Fonts.txt attribution files,
  readme.txt/.html variants, terms-of-use/EULA files, "Apache
  License.txt", "KGFonts-TOU.txt", demo-use notices, three "Terms Of
  Use.URL" pointers, "More Info.txt"). 54 + 32 = 86 EXACT.

FACE→LICENCE RESOLUTION, BY HASH NOT NAME:
  • The two face sha256s (478c558e…, 1df075a3…) appear in the 7,590-row
    corpus ONLY at bbrose_design_os/static/fonts. Zero NotoSans-named
    files exist anywhere under materials/.
  • Of the 86 class-shape files, exactly ONE mentions "noto":
    bbrose_design_os/static/fonts/OFL.txt.
  • materials/ holds 8 OFL.txt files = 7 distinct sha256s (447f6ebb…
    Bonbon; 221cc6d7… Playpen_Sans_Arabic; 0617ba03… Zen_Dots;
    4fff2814… Playwrite, twice — duplicated package; b1dffde5… Almarai;
    5774c8be… Shadows_Into_Light_Two; e564f06d… great-vibes). NONE
    equals the static/fonts file's hash; each names its own package,
    none names these faces.

ANSWER TO THE RULED QUESTION — one licence file or two:
  ★ ONE. Both container faces resolve to the SAME single licence file:
      bbrose_design_os/static/fonts/OFL.txt
      4,374 bytes
      sha256 f2095b08bed08b23a6fe26112fcd679a2bee3f002eef077eb05d215ed1051bd8
  Hard stop "fails to resolve to any on-disk licence file": DOES NOT
  FIRE (resolved, both faces). Hard stop "differing sha256": DOES NOT
  FIRE (one file, one hash — the owner reads ONE text).

────────────────────────────────────────────────────────────────────────
§2 CLAUSE (2) — THE LICENCE TEXT, COMPLETE AND BYTE-VERBATIM
────────────────────────────────────────────────────────────────────────
Durable copy: ~/bh25_work/OFL_static_fonts_copy.txt — sha256 re-measured
at report time, IDENTICAL to the original (f2095b08…). The complete text
(95 lines, no elision, no summary, no paraphrase):

Copyright 2022 The Noto Project Authors (https://github.com/notofonts/)

This Font Software is licensed under the SIL Open Font License,
Version 1.1.

This license is copied below, and is also available with a FAQ at:
http://scripts.sil.org/OFL

-----------------------------------------------------------
SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007
-----------------------------------------------------------

PREAMBLE
The goals of the Open Font License (OFL) are to stimulate worldwide
development of collaborative font projects, to support the font
creation efforts of academic and linguistic communities, and to
provide a free and open framework in which fonts may be shared and
improved in partnership with others.

The OFL allows the licensed fonts to be used, studied, modified and
redistributed freely as long as they are not sold by themselves. The
fonts, including any derivative works, can be bundled, embedded,
redistributed and/or sold with any software provided that any reserved
names are not used by derivative works. The fonts and derivatives,
however, cannot be released under any other type of license. The
requirement for fonts to remain under this license does not apply to
any document created using the fonts or their derivatives.

DEFINITIONS
"Font Software" refers to the set of files released by the Copyright
Holder(s) under this license and clearly marked as such. This may
include source files, build scripts and documentation.

"Reserved Font Name" refers to any names specified as such after the
copyright statement(s).

"Original Version" refers to the collection of Font Software
components as distributed by the Copyright Holder(s).

"Modified Version" refers to any derivative made by adding to,
deleting, or substituting -- in part or in whole -- any of the
components of the Original Version, by changing formats or by porting
the Font Software to a new environment.

"Author" refers to any designer, engineer, programmer, technical
writer or other person who contributed to the Font Software.

PERMISSION & CONDITIONS
Permission is hereby granted, free of charge, to any person obtaining
a copy of the Font Software, to use, study, copy, merge, embed,
modify, redistribute, and sell modified and unmodified copies of the
Font Software, subject to the following conditions:

1) Neither the Font Software nor any of its individual components, in
Original or Modified Versions, may be sold by itself.

2) Original or Modified Versions of the Font Software may be bundled,
redistributed and/or sold with any software, provided that each copy
contains the above copyright notice and this license. These can be
included either as stand-alone text files, human-readable headers or
in the appropriate machine-readable metadata fields within text or
binary files as long as those fields can be easily viewed by the user.

3) No Modified Version of the Font Software may use the Reserved Font
Name(s) unless explicit written permission is granted by the
corresponding Copyright Holder. This restriction only applies to the
primary font name as presented to the users.

4) The name(s) of the Copyright Holder(s) or the Author(s) of the Font
Software shall not be used to promote, endorse or advertise any
Modified Version, except to acknowledge the contribution(s) of the
Copyright Holder(s) and the Author(s) or with their explicit written
permission.

5) The Font Software, modified or unmodified, in part or in whole,
must be distributed entirely under this license, and must not be
distributed under any other license. The requirement for fonts to
remain under this license does not apply to any document created using
the Font Software.

TERMINATION
This license becomes null and void if any of the above conditions are
not met.

DISCLAIMER
THE FONT SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT
OF COPYRIGHT, PATENT, TRADEMARK, OR OTHER RIGHT. IN NO EVENT SHALL THE
COPYRIGHT HOLDER BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
INCLUDING ANY GENERAL, SPECIAL, INDIRECT, INCIDENTAL, OR CONSEQUENTIAL
DAMAGES, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF THE USE OR INABILITY TO USE THE FONT SOFTWARE OR FROM
OTHER DEALINGS IN THE FONT SOFTWARE.

[END OF FILE — 95 lines, byte-verbatim from sha256 f2095b08…]

────────────────────────────────────────────────────────────────────────
§3 CLAUSE (3) — AUTHORITY STATE TABLE, MEASURED LIVE AT THE SEAM
────────────────────────────────────────────────────────────────────────
Measured by ~/bh25_work/measure_faces.py (READ-ONLY: records built in
memory, printed, nothing written to the repo), harness-identical doc
(test_container_font_authority._doc, :29-35). Full output:
~/bh25_work/face_records_measured.json. rc=0.

3.1 THE FULL FACE RECORDS — BOTH PATHS THE SEAM CAN PRODUCE TODAY
(fields identical between the two faces except family/style/psname/
path/sha256; authority-bearing fields shown with CONSTANT NAMES):

                          PRODUCTION DEFAULT          JOIN-FED
                          (confirmed_fonts=None —     (the state §BH25
                          producer deliberately       names)
                          UNWIRED, 6ce5e6c)
  verification            UNVERIFIED                  LICENCE_REVIEW_REQUIRED
  source                  SOURCE_PLACEHOLDER_FALLBACK SOURCE_MACHINE_DERIVED
                          ("PLACEHOLDER_FALLBACK")    ("MACHINE_DERIVED")
  is_fallback             true                        true  (MACHINE_DERIVED
                                                      ∉ SOURCES_CLEARING_FALLBACK)
  licence_id              ""                          ""
  licence_evidence        ""                          ""
  approved_by             ""                          ""
  approved_at             ""                          ""
  redistribution_status   "UNVERIFIED"                "UNVERIFIED"
  production_use_status   "UNVERIFIED"                "UNVERIFIED"
  fs_type                 0                           0
  embedding_status        "installable"               "installable"
  gate codes              CONTAINER_FONT_CONFIRMATION CONTAINER_FONT_LICENSE
                          _REQUIRED +                 _REVIEW_REQUIRED +
                          CONTAINER_FONT_FALLBACK     CONTAINER_FONT_FALLBACK
                          _DETECTED                   _DETECTED
  all_production_verified false                       false

  Identity fields (both paths, per face):
    bold:    "Noto Sans" / "Bold" / NotoSans-Bold / …/NotoSans-Bold.ttf
             / sha256 1df075a3…
    regular: "Noto Sans" / "Regular" / NotoSans-Regular /
             …/NotoSans-Regular.ttf / sha256 478c558e…

3.2 THE PROVENANCE CHAIN THAT PRODUCES {MACHINE_DERIVED,
LICENCE_REVIEW_REQUIRED}:
  1. DIP-0A inventory regen 2026-08-31 (§BH20(b)/§BH21) — 7,590 rows.
  2. dip0c C4c face_manifest.json — 3,969 rows (outer var/, untracked +
     git-ignored; absence is a first-class outcome, cfj :49-54).
  3. join_font_evidence (container_font_evidence_join.py :128-164)
     joins by file_sha256 → measured live: evidence_status
     EVIDENCE_READ, rows_considered 3969, BOTH faces JOINED.
  4. _confirmation (:89-125) stamps per face {provenance:
     SOURCE_MACHINE_DERIVED, verification: LICENCE_REVIEW_REQUIRED}
     (JOIN_VERIFICATION/JOIN_SOURCE, :59-60) — every value pushed
     through BOTH guards at emission (:118-119).
  5. build_font_authority(doc, confirmed_fonts=…) → guarded_confirmation
     (:251-306) → _confirmation_source (:365-387) → _face_record
     (:390-444; is_fallback derived at :421).
  Production wiring: apps/pipeline/targets/container/__init__.py :882
  (`confirmed_fonts: dict | None = None`) and :1233 (the ONLY
  production call). join_font_evidence has NO production caller — the
  producer is deliberately unwired, so the LIVE production record today
  is the DEFAULT column; the join-fed column exists wherever
  confirmed_fonts is fed (measured here by feeding the join's output).
  Chain commits verified at HEAD: a76242c (inversion) → 6ce5e6c
  (producer, unwired) → 9070991 (seam guard) → 4140bd8 (source ceiling;
  MACHINE_DERIVED measured, not invented).

3.3 WHAT THE §BH15/§BH14 CEILINGS PERMIT AND FORBID — the exact
constants, i.e. what an owner ruling would authorize that the machine
cannot do alone:

  verification (VERIFICATION_CEILING, container_font_authority.py
  :49-58):
    machine-WRITABLE:  LICENCE_REVIEW_REQUIRED, FONT_FILE_MISSING,
                       FONT_IDENTITY_MISMATCH, UNVERIFIED
    machine-FORBIDDEN: VERIFIED_FOR_PRODUCTION,
                       APPROVED_FOR_CONCEPT_ONLY
  source (SOURCE_CEILING, :162-168):
    machine-WRITABLE:  SOURCE_PLACEHOLDER_FALLBACK,
                       SOURCE_MACHINE_DERIVED, SOURCE_UNATTRIBUTED,
                       SOURCE_UNDECLARED
    machine-FORBIDDEN: SOURCE_USER_CONFIRMED
  SOURCES_CLEARING_FALLBACK (:188-189) =
    frozenset({SOURCE_USER_CONFIRMED, SOURCE_UNDECLARED})
    — only these leave is_fallback CLEAR.
  Seam arrivals (independent of what machines WRITE):
    SEAM_REFUSED_VERIFICATIONS (:237) =
      frozenset({VERIFIED_FOR_PRODUCTION}) — refused OUTRIGHT per
      §BH13(b), no owner-confirmation branch until Option C lands.
    LICENCE_CLAIM_DEFAULTS (:242-248) = licence_id "", 
      redistribution_status "UNVERIFIED", production_use_status
      "UNVERIFIED", approved_by "", approved_at "" — any field departing
      its default WITHOUT licence_evidence raises UnfoundedLicenceClaim
      (:296-304): a licence_id is refused whenever non-empty and
      unevidenced, WITHOUT regard to what it says (:265-271 — the
      machine refuses on SHAPE because reading licences is the owner's
      reserved act).

3.4 THE TWO GUARD CLAUSES, VERBATIM WITH LINE NUMBERS
(bbrose_design_os/apps/ire/container_font_authority.py):

  :75-92 —
    def machine_writable_verification(value: str) -> str:
        """Guard. Returns ``value`` only if it sits at or below the ceiling.

        A machine may record what it has found about a font; it may never record a
        state that grants. Anything outside the six is refused outright, and there
        is no pass-through for ``None`` — this module's own answer to "no state
        yet" is ``UNVERIFIED``, not absence.
        """
        if value not in VERIFICATION_CEILING:
            raise ValueError(
                f"{value!r} is not a container font verification state. "
                f"Known: {sorted(VERIFICATION_CEILING)}")
        if VERIFICATION_CEILING[value] == ABOVE_CEILING:
            raise FontStateAboveCeiling(
                f"{value!r} is above the ceiling: a machine writing it would confer "
                f"authority only a human may confer. Writable: "
                f"{list(MACHINE_WRITABLE_VERIFICATIONS)}")
        return value

  :192-207 —
    def machine_writable_source(value: str) -> str:
        """Guard. The ``source`` twin of ``machine_writable_verification``.

        Keeps the same two DISJOINT refusals, so a cap test can prove which fired:
        an unrecognised origin raises ``ValueError``, and a human-confirmation
        claim raises ``FontStateAboveCeiling``.
        """
        if value not in SOURCE_CEILING:
            raise ValueError(
                f"{value!r} is not a container font record source. "
                f"Known: {sorted(SOURCE_CEILING)}")
        if SOURCE_CEILING[value] == ABOVE_CEILING:
            raise FontStateAboveCeiling(
                f"{value!r} claims a human confirmed this face; a machine may "
                f"never write it. Writable: {list(MACHINE_WRITABLE_SOURCES)}")
        return value

3.5 DIVERGENCE RECORDED, NOT RESOLVED (house rule: machines never edit
evidence contracts absent an owner sentence):
  container_font_evidence_join.py :16-22 states: "THIS PRODUCER YIELDS
  NOTHING TODAY… the evidence holds 3,966 rows, every one of them under
  ``materials/``, zero under ``static/fonts``; the container's two
  faces… join to NO MATCH." SUPERSEDED BY MEASUREMENT: since the
  §BH20(b) regeneration the evidence holds 3,969 rows and BOTH faces
  JOIN (measured live, §3.2 step 3). The docstring is left byte-intact;
  recorded here for the owner.

────────────────────────────────────────────────────────────────────────
§4 CLAUSE (4) — NOTHING MOVED
────────────────────────────────────────────────────────────────────────
  • Zero writes to any authority-bearing field, zero state transitions
    — BY CONSTRUCTION: every staging act was a read, or a write into
    ~/bh25_work/ only; measure_faces.py builds records in memory and
    prints them (its own header: "Writes NOTHING to disk").
  • Worktree clean at report time except the committed transcription:
    `git status --porcelain` EMPTY (rc=0), measured from BOTH cwds
    (outer root and bbrose_design_os — same `git rev-parse
    --show-toplevel`, one repo). HEAD 18ab440 = the transcription.
  • Protected regions byte-identical, BOTH hashes re-verified with the
    sealed recipe (regen_decl.md:6 — `find <tree> -type f | LC_ALL=C
    sort | xargs shasum -a 256 | shasum -a 256`, 16-char prefix):
      docs/design_intelligence/dip0c → 36f08a31ad581c3b
        (132 tracked / 132 on disk)  == recorded seal
        (OWNER_REVIEW_QUEUE.md:11956-11957; regen_decl.md:125-127)
      docs/design_intelligence/dip0a → 2e339a7e23a46c00
        (5 tracked / 5 on disk)      == recorded seal
  • Gate not required for staging (per the ruling): no gate ran after
    T25; ledger stands 429 == 429 CLEAN.
  • Third hard stop ("any staging step would require touching an
    authority-bearing field"): NEVER APPROACHED — no staging step
    required any write outside ~/bh25_work/.

────────────────────────────────────────────────────────────────────────
STOP. The licence text (§2) and the complete authority state (§3) are
in front of the owner, verbatim and measured. Nothing here interprets,
anticipates, or proposes. §BH26 is the owner's ruling, typed after the
reading.
