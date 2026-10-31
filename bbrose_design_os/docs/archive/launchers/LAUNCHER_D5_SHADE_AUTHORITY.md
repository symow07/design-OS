# LAUNCHER — D5, OWNER SHADE AUTHORITY RECORD

Paste the block below into Claude Code in the repository. Everything above the
block is context for you, not for it.

**What this closes.** `D5 — colour authority does not exist`, recorded at
`bbrose_design_os/docs/roadmap/palt_m6/open_defect_inventory.md:174–178` as
`pan_shades: NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY`.

**Why it is not a one-line edit.** I read the engine before writing this. The
gate is real code, not documentation:

- `apps/pipeline/services/palette_powder_engine.py:364–370` — `PowderShade`
  raises `PowderSpecError` on **any** authority string other than
  `PROVISIONAL_VISUALIZATION_SHADE`. Your twelve cannot be constructed today.
- `palette_powder_engine.py:382–385` — `to_dict()` hardcodes
  `"owner_colour_authority": NOT_OWNER_COLOUR_AUTHORITY` on every shade, with
  no branch.
- `apps/pipeline/tests/test_powder_engine.py:56–58` —
  `test_unknown_colour_authority_refused` asserts that `"OWNER_CONFIRMED"` is
  rejected. That test is doing its job and must keep doing it.

So the work is: widen the gate by exactly one admitted value, make the
owner-authority field honest instead of constant, add the twelve as a new
function, and leave the existing fixture untouched.

**The fixture stays.** `es3083_provisional_shade_set()`
(`palette_powder_engine.py:518–552`) is a *test set* — its docstring says so,
and it exists to exercise light/medium/dark and warm/cool across the families.
Under your ruling that engine coverage is a fixture's job and not a product's,
that function must not be edited, renamed or replaced. It keeps GLITTER
exercised. The owner twelve is a **new, separate** function. Two functions,
two purposes, no overlap.

---

```
GOAL — land the owner's settled twelve-shade colour authority for ES3083 as a
repository record, and close D5. Read this whole brief before editing anything.

CONTEXT YOU MUST READ FIRST
  SHADE_AUTHORITY_PROPOSAL.md                      (repo root — the decisions)
  apps/pipeline/services/palette_powder_engine.py  (§ the PowderShade class)
  apps/pipeline/services/palette_powder_protocol.py:37-48  (family constants)
  apps/pipeline/tests/test_powder_engine.py
  docs/roadmap/palt_m6/open_defect_inventory.md    (D5, ~line 174)

THE STANDING LAW THIS WORK RUNS UNDER
  - Declare before you realize. Do not write a record and then decide what it
    means.
  - An honest FAIL beats a moved bar. If a step below cannot be done as
    written, stop and say which step and why. Do not weaken a guard to make a
    step pass.
  - Amendment 3aa — a derived quantity carries the identity of every input it
    read and of the derivation that produced it, or it is not evidence.
  - A564 — any claim that something is absent must state its search extent.

STEP 1 — ADMIT EXACTLY ONE NEW COLOUR AUTHORITY

  In apps/pipeline/services/palette_powder_engine.py, beside
  PROVISIONAL_VISUALIZATION_SHADE (line 36), add:

      OWNER_CHOSEN_DESIGN_INTENT = "OWNER_CHOSEN_DESIGN_INTENT"

      #: the complete set of admitted shade authorities. Adding to this tuple
      #: is a decision about evidence, not a refactor.
      SHADE_AUTHORITIES = (PROVISIONAL_VISUALIZATION_SHADE,
                           OWNER_CHOSEN_DESIGN_INTENT)

  Change the PowderShade guard at line 365 from an equality test to
  membership in SHADE_AUTHORITIES. Keep the raise, keep PowderSpecError, and
  rewrite the message so it names the admitted set rather than a single value.

  DO NOT add any other authority string. Not OWNER_CONFIRMED, not
  PANTONE_SPECIFIED, not MEASURED_LAB. Those tiers are real and they are
  stronger than this one, but the owner does not hold them yet and a constant
  that exists is a constant something will eventually be stamped with.

  Leave the Pantone-in-name guard at lines 371-374 exactly as it is. The owner
  shade names contain no Pantone token, so it will not fire, and it is the
  thing standing between this record and a fabricated conversion.

STEP 2 — MAKE owner_colour_authority HONEST

  PowderShade.to_dict() currently emits NOT_OWNER_COLOUR_AUTHORITY
  unconditionally. That is now false for twelve shades. Branch it on
  self.authority:

      PROVISIONAL_VISUALIZATION_SHADE -> NOT_OWNER_COLOUR_AUTHORITY
      OWNER_CHOSEN_DESIGN_INTENT      -> OWNER_DESIGN_INTENT_NOT_MEASURED

  Define OWNER_DESIGN_INTENT_NOT_MEASURED as a module constant next to the
  others. Its wording matters and is the point of the whole record: the owner
  chose these colours, and choosing is not measuring. This value must never be
  read as manufacturing colour authority.

STEP 3 — ADD THE OWNER TWELVE AS A NEW FUNCTION

  Add es3083_owner_shade_set() to palette_powder_engine.py, immediately after
  es3083_provisional_shade_set(). Do not modify, rename, wrap or deprecate
  es3083_provisional_shade_set() — it is a test fixture with a different job
  and it is the reason GLITTER stays exercised.

  Signature and return shape must match the existing fixture exactly:
  a list of {"pan": int, "spec": PowderMaterialSpec}, seed = pan number.

  Each row carries name, grid position, hex, rgb triple, family, role. The
  twelve, light to deep, in grid order:

    pan  pos    name             hex        rgb (0..1, 4dp)              family
    1    R1C1   Petal Veil       #F2E3D8    0.9490 0.8902 0.8471   POWDER_MATTE
    2    R1C2   First Light      #E9CBAE    0.9137 0.7961 0.6824   POWDER_SATIN
    3    R1C3   Dew              #E4D8D4    0.8941 0.8471 0.8314   SHIMMER
    4    R1C4   Damascena        #D9A2A6    0.8510 0.6353 0.6510   POWDER_MATTE
    5    R2C1   Blush Hour       #C57E82    0.7725 0.4941 0.5098   POWDER_SATIN
    6    R2C2   Attar            #C9916B    0.7882 0.5686 0.4196   BAKED
    7    R2C3   Copper Leaf      #A85B33    0.6588 0.3569 0.2000   POWDER_METALLIC
    8    R2C4   Sage Stem        #7F846E    0.4980 0.5176 0.4314   POWDER_MATTE
    9    R3C1   Old Rose         #8D5459    0.5529 0.3294 0.3490   PRESSED_POWDER
    10   R3C2   Thorn            #5D3A42    0.3647 0.2275 0.2588   POWDER_MATTE
    11   R3C3   Moss Garden      #48583F    0.2824 0.3451 0.2471   MARBLED
    12   R3C4   Midnight Bloom   #4A2E3B    0.2902 0.1804 0.2314   POWDER_METALLIC

  Roles, for the record fields:
    1 brow-bone / all-over base      2 inner corner, warm wash
    3 warm pearl highlight           4 soft rose transition
    5 mid rose lid                   6 antique rose-gold lid
    7 copper statement               8 olive-taupe, ties to the case
    9 crease depth                  10 outer-V plum brown
   11 deep olive hero pan           12 deep plum depth shade

  Shade names go into PowderShade as written above — "Petal Veil", not
  "prov_petal_veil". The prov_ prefix belongs to the fixture and would misstate
  the authority of these.

  DO NOT compute the rgb triples yourself and DO NOT trust mine blindly.
  Verify: each triple must equal round(channel/255, 4) of its hex. If any one
  disagrees, stop and report the row. The hex is the authority; the triple is
  derived from it.

STEP 4 — THE COLOUR-SPACE QUESTION, WHICH YOU MUST NOT SILENTLY ANSWER

  The hex values are sRGB. Determine what PowderShade.rgb is actually consumed
  as downstream — trace it into the material realization and into Blender. If
  the consumer wants linear-light values, then channel/255 is wrong and an
  sRGB-to-linear transfer is required.

  Do NOT guess and do NOT convert on a hunch. Find the consumer, read it, and
  then do one of two things:
    (a) if the consumer is sRGB-referred, use the triples above and record that
        the finding was checked, with the file and line that settles it; or
    (b) if the consumer is linear-referred, keep the sRGB hex as the stored
        authority, add a separate derived linear field, name the transfer
        function used, and record both.

  Either way the record states which, with the evidence. An unstated colour
  space is how a plum becomes a mud.

STEP 5 — WRITE THE RECORD

  Create the shade authority record as a versioned JSON record in the same
  place and style as the programme's other records (find where — do not invent
  a new directory). It must carry:

    record_type      es3083_shade_authority/1.0
    target           palette / ES3083
    decided_by       owner
    decided_on       2026-08-13
    authority        OWNER_CHOSEN_DESIGN_INTENT   -- STAMPED PER SHADE, not
                                                     once at the top of the
                                                     file. Per-shade stamping
                                                     is what lets one shade be
                                                     upgraded to a Pantone or a
                                                     measured Lab later without
                                                     touching the other eleven.
    per shade        pan, grid_pos, name, hex, rgb, colour_space, family, role
    source_document  SHADE_AUTHORITY_PROPOSAL.md + its sha256
    code_identity    the digest the module already uses for identities

  Two per-shade notes are load-bearing and must travel in the record, attached
  to their shade, not left in a comment:

    Moss Garden (pan 11) — MARBLED here means restrained antique-gold and
      olive marbling, NOT bright gold veining. A renderer that reads the family
      without this note will produce the thing the owner rejected.

    Midnight Bloom (pan 12) — POWDER_METALLIC, chosen by the owner over
      SHIMMER because #4A2E3B is dark enough that a soft pearl load disappears
      into its own base. Shares its family with Copper Leaf (pan 7); they sit
      at opposite ends of the depth run. The duplication is recorded, not
      hidden.

  The record must also carry, as a first-class field and not as prose:

    not_manufacturing_authority: true
    upgrade_path: "replace hex with a Pantone number or a measured Lab value
                   and raise that shade's authority field; names, grid
                   positions and finish families do not change when the colour
                   does"

  GLITTER and CREAM are unused by this palette. Record that as a plain fact if
  you record it at all. It is NOT a gap, NOT a coverage shortfall, and no field
  named anything like family_coverage may appear anywhere in this record. A
  palette is designed for commerce, not to exercise the engine.

STEP 6 — TESTS

  Add to apps/pipeline/tests/test_powder_engine.py:

  1. es3083_owner_shade_set() returns exactly 12 rows, pans 1..12, no gaps.
  2. Every row's authority == OWNER_CHOSEN_DESIGN_INTENT and every row's
     owner_colour_authority == OWNER_DESIGN_INTENT_NOT_MEASURED.
  3. Every rgb triple round-trips to its recorded hex within 1/255.
  4. No shade name contains "PANTONE" (case-insensitive) — the existing guard
     covers construction; this covers the data.
  5. Every family named is a member of PP.POWDER_FAMILIES.
  6. An unadmitted authority string is still refused. Keep
     test_unknown_colour_authority_refused green by changing its argument from
     "OWNER_CONFIRMED" to a string that is genuinely not admitted, e.g.
     "OWNER_MEASURED_LAB". Do not delete that test.
  7. es3083_provisional_shade_set() is unchanged in every respect: still 12
     rows, still all PROVISIONAL_VISUALIZATION_SHADE, still
     NOT_OWNER_COLOUR_AUTHORITY. This test is the guard against the fixture
     being quietly repurposed as the product.

  Run the full pipeline test suite, not just this file. Report the count.

STEP 7 — CLOSE D5

  In docs/roadmap/palt_m6/open_defect_inventory.md, rewrite the D5 entry
  (~line 174). It currently says colour authority does not exist. It must now
  say, precisely:

    - pan_shades resolved to OWNER_CHOSEN_DESIGN_INTENT, citing the new record
      by path AND digest
    - the Pantone tokens 621 C / 627 C remain CASE colours, not pan shades,
      and remain governed by SPOT_COLOUR_AUTHORITY in palette_design_graph.py
      (they are UNRESOLVED_SPOT_COLOUR there and this record does not touch
      that)
    - FB3090 remains UNSOURCED — this record is ES3083 only
    - the residual: these are chosen values, not measured ones, so D5 closes as
      "sufficient to render, make artwork and put a deliverable in front of a
      client" and NOT as "manufacturing colour authority established"

  If closing D5 outright overstates what was achieved, do not close it —
  downgrade it and say exactly what remains. A moved bar is worse than an open
  defect.

DO NOT
  - touch es3083_provisional_shade_set()
  - add any colour authority constant beyond the one named in Step 1
  - weaken or delete the Pantone-name guard
  - write any coverage metric into any record
  - claim anything is absent without stating what you searched

REPORT BACK
  - the diff summary, file by file
  - the test count, before and after
  - the answer you found in Step 4, with the file and line that settles it
  - whether D5 closed or downgraded, and the exact wording you used
  - anything in this brief that turned out to be wrong about the code
```

---

## AFTER IT RUNS

Two things are then true and one is not.

**True:** the twelve exist as evidence rather than as a root-level markdown
brief, and each one can be upgraded independently when a Pantone chip or a
spectrophotometer reading arrives.

**True:** blocker #3 of the four is finished.

**Not true:** that ES3083 has manufacturing colour authority. It does not, and
the record says so in a field rather than a footnote. The upgrade is cheap and
the path is written down.

**Still open after this:** #2 ES3083 geometry, which is bounded but not
measured and needs one caliper session — see `ES3083_DIMENSION_FINDINGS.md`;
and #4 `MATERIALS_LIBRARY_ABSENT`, whose record still does not say what is
actually missing.
