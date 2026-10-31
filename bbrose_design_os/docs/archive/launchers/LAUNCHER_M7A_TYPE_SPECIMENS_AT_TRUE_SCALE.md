# LAUNCHER — M7a, THE FIRST ACT OF ARTWORK

Follows `509c0ab`. Two owner rulings, a font census with a licensing question
that has to be asked before anything is drawn, and one specimen sheet you can
actually look at.

This is the first act in this arc that produces a design artifact rather than
a correction. It is deliberately narrow: it chooses no layout, draws no lid,
and commits no artwork. It puts the twelve names in front of you at the size
they will actually be printed.

---

## THE TWO RULINGS

**Asked and answered 2026-08-13.**

**One — the artwork is exempt from the M6 dependency.** M7's artwork half
(ES3083 artwork, shade labels, editable `.AI`) proceeds while M6 remains
parked, because it consumes no family verdict. The dependency edge is narrowed
to M7's second half — the PALT-P2 and PALT-P3 pilots — which do need the
material engine. M6 stays parked and nothing is closed prematurely.

**Two — the typeface direction is old-style / humanist serif.** Garamond,
Sabon, Jenson lineage. Not Didone, which is the category default and fragile
at 16 mm. The reasoning is on record: the palette was just ruled restrained
olive-on-olive with the gold struck, and the lettering should agree with that
decision rather than fight it.

The specific face is not chosen. That is what this act exists to inform.

---

## WHY LICENSING COMES FIRST

The library holds 3,741 font files. **Presence in `materials/Fonts` is not a
licence to use.** That library is described in `.gitignore:54` as historical
source material — *"28GB of historical .ai, assets, fonts"* — harvested from
past production work, quite possibly under licences held by other parties for
other products.

Setting BBROSE's brand lettering and twelve shade names in a face BBROSE does
not hold a commercial licence for would put the exposure directly on the
finished product, at the point where it is hardest to undo. This is exactly
the kind of premise that has gone unchecked four times in this arc, and it is
the one where being wrong costs real money rather than a rewritten record.

So the census reports licence status, and where it cannot be determined it
says so rather than assuming.

---

## THE GEOMETRY THE ARTWORK SITS ON

Two things are true at once and both must be declared before anything is
drawn.

**Measured, at true scale, from the production sheet** —
`ES3083_DIMENSION_FINDINGS.md`:

| | |
|---|---|
| shade-name label | **77.00 × 16.00 mm**, 24 off, 3 cols × 8 rows |
| shade-label pitch | **83.00 × 22.00 mm** |
| shade-label sheet | **263.00 × 190.00 mm** |
| back label, printed | **49.50 × 49.50 mm**, 2.0 pt keyline |
| back label, die/bleed | **55.00 × 55.00 mm**, pitch 58.4 mm |
| display box, principal panel | **275.00 mm** |

**Not measured** — the pan cavity. `ES3083_DIMENSION_FINDINGS.md:104` is
explicit: *"So the pan cavity dimensions are still not measured. The blocker
narrows but does not close."* `ES3083_DIMENSIONS_UNREADABLE` stands, and
ES3083 geometry remains `DERIVED_BOUNDED_NOT_MEASURED`.

**And one unresolved contradiction**, recorded at
`ES3083_DIMENSION_FINDINGS.md:135-137`: the shade-name label is 77.00 mm wide
and the case is 65 mm. *"Either it is not applied to the palette, or it is
applied to something else in the pack, or the case is wider than the lid
decal."* Nobody has resolved this and the artwork is about to be built on the
label grid. It gets resolved or explicitly bounded first.

**The consequence for how the artwork is built:** everything must be
parametric on the geometry, never hard-coded to it. When you eventually put
calipers on an ES3083, the artwork should re-flow rather than need redrawing.
That is a construction instruction, not a preference.

---

## THE PROMPT

```
GOAL — record two owner rulings, census the font library for a licensed
old-style serif, resolve or bound one geometric contradiction, and produce ONE
specimen sheet at true print scale for owner judgment. Draw no lid artwork.
Choose no layout. Commit no typeface.

OWNER RULINGS — GRANTED AND RECORDED 2026-08-13, both by PROJECT_OWNER.

  RULING 1 — M7's ARTWORK HALF IS EXEMPT FROM THE M6 DEPENDENCY. ES3083
  artwork + shade labels + editable .AI proceed while M6 remains PARKED,
  because the artwork consumes no family verdict. The dependency on
  palettes.palt_m6_powder_material_engine is NARROWED to M7's second half,
  the PALT-P2 / PALT-P3 pilots. M6 is not closed and nothing about M6's
  open verdicts changes.

  RULING 2 — TYPEFACE DIRECTION IS OLD-STYLE / HUMANIST SERIF. Garamond,
  Sabon, Jenson lineage. NOT Didone. The specific face is NOT chosen and
  remains an open owner decision.

CONTEXT
  ES3083_DIMENSION_FINDINGS.md                       (measured geometry; :104 and :135-137)
  docs/roadmap/palt_m6/es3083_shade_authority.json   (the twelve, now at 1.3)
  docs/roadmap/palt_m4c/m7_artwork_scope_ruling.json (BBROSE-original ruling)
  docs/roadmap/palt_m4c/m4c4_panel_confirmation.json (pan_count/rows/columns HARD)
  docs/roadmap/progress_tracker.json                 (the M7 dependency edge)
  docs/visual_quality/vq2/                           (Imbue — scope-limited, see STEP 4)
  materials/Fonts/                                   (3,741 files, READ ONLY)
  .gitignore:54                                      (what materials/ is)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — RECORD BOTH RULINGS

  Ruling 1 changes a dependency edge, so read the authorization route for
  progress_tracker.json again rather than assuming 61ddd75's answer still
  holds — you are editing a dependency this time, not a title.

  Record, alongside the ruling, what it does NOT do: it does not close M6, it
  does not establish the three diffuse verdicts, it does not touch D7 or D8,
  and it does not exempt the PILOTS. If a later reader could mistake this for
  M6 being discharged, the wording is wrong.

  Ruling 2 goes wherever design-direction decisions belong. Record explicitly
  that the direction is chosen and the FACE is not.

STEP 2 — THE FONT CENSUS, AND THE LICENCE QUESTION FIRST

  materials/Fonts holds 3,741 files. PRESENCE IS NOT A LICENCE. That library
  is historical source material harvested from past production work and the
  licences may belong to other parties for other products.

  For every candidate you shortlist, report:
    - the family and its classification, and whether it is genuinely
      old-style/humanist rather than transitional or Didone wearing a serif
    - the file format and whether it is usable in Illustrator 2026
    - glyph coverage for what is actually needed: the twelve shade names
      exactly as authored, the BBROSE wordmark, and any accented or special
      characters those require
    - LICENCE STATUS — embedded fsType bits, any accompanying licence file,
      EULA text, foundry, and whether anything in the repository or the
      library establishes that BBROSE holds commercial rights

  Where licence status cannot be determined from what is present, say
  UNDETERMINED. Do not infer a licence from the file being there, from the
  foundry being well known, or from the font shipping with an operating
  system — OS bundling is a licence for OS use, not for product packaging.

  State your search extent: the predicate, the glob, and the population
  searched. A564.

  If NO candidate in the library is both suitable and licence-clear, say that
  plainly. That is a real and useful result and it tells the owner they need
  to buy a licence, which is a small cost caught early rather than a large one
  caught late.

STEP 3 — RESOLVE OR BOUND THE 77mm / 65mm CONTRADICTION

  ES3083_DIMENSION_FINDINGS.md:135-137 records that the shade-name label
  measures 77.00 mm wide against a 65 mm case, unresolved, with three
  candidate explanations.

  Investigate it with what is in the repository and the library. If it
  resolves, record which explanation holds and on what evidence. If it does
  not, record it as a BOUND on the artwork: state exactly which artwork
  decisions depend on it and which do not, so the specimen work can proceed on
  the parts that do not.

  Do not resolve it by picking the convenient answer. If the evidence is
  absent, the answer is that it is unresolved and here is what it constrains.

STEP 4 — CHECK ONE SCOPE BOUNDARY BEFORE SETTING TYPE

  The VQ2 Imbue approval is scoped, per the record, to "VQ-2 concept-front
  artwork only" with approved_words ['Rose','Damascena']. Read it and state
  whether it reaches M7 lid artwork AT ALL.

  My reading is that it does not — it is a bottle-programme approval and M7 is
  a different deliverable — and that nothing in it constrains or authorizes
  what this act produces. Confirm or refute. If I am wrong and it does reach
  M7, STOP and report, because it would mean the shade names are governed by
  an approved-words list.

STEP 5 — ONE SPECIMEN SHEET, AT TRUE PRINT SCALE

  Produce a single specimen sheet. Its purpose is owner judgment, not
  approval, and it commits nothing.

  It must carry, for each shortlisted licence-clear face (three or four, not
  more):
    - all TWELVE shade names, set exactly as authored in
      es3083_shade_authority.json 1.3, at TRUE SCALE within the measured
      77.00 x 16.00 mm label
    - the BBROSE wordmark at a stated size
    - the face named, and its licence status stated ON the sheet next to it

  TRUE SCALE IS THE POINT. Do not set the specimens large and let the owner
  imagine them small. 16 mm label height is where hairline strokes drop out,
  where optical sizes matter, and where the choice is actually decided. If a
  face fails at that size, the sheet should show it failing rather than
  flatter it.

  Set the real names. "Petal Veil", "First Light", "Dew", "Damascena", "Blush
  Hour", "Attar", "Copper Leaf", "Sage Stem", "Old Rose", "Thorn", "Moss
  Garden", "Midnight Bloom" — read them from the record, do not retype them
  from this brief. Their lengths differ by a factor of three and that
  difference is half of what the owner is judging.

  Include a rendered PNG for viewing. Whether the specimen itself is built as
  .AI is your call — say which you chose and why.

STEP 6 — DECLARE THE GEOMETRIC SUBSTRATE

  Before any artwork is built on it, state in one short record what the
  artwork's geometry rests on: which dimensions are MEASURED at true scale,
  which are DERIVED_BOUNDED_NOT_MEASURED, and which are unresolved per Step 3.

  Then state the construction rule and make it binding on later acts: the
  artwork is built PARAMETRIC on the geometry, never hard-coded to it, so that
  a caliper session re-flows the artwork rather than requiring it to be
  redrawn. Say where that rule is recorded so a later act cannot miss it.

DO NOT
  - choose the typeface — produce specimens, the owner chooses
  - design or draw the lid layout
  - produce the M7 artwork deliverable or the editable .AI of it
  - use any font whose licence status is UNDETERMINED in the specimen without
    labelling it UNDETERMINED on the sheet
  - infer a commercial licence from a font's presence in materials/
  - close M6, or read Ruling 1 as discharging any M6 obligation
  - reclassify any pan or touch the shade record's colours or families
  - hard-code any dimension that is DERIVED_BOUNDED_NOT_MEASURED
  - close D5

REPORT BACK
  - where both rulings were recorded, and the tracker's authorization route
  - the font census: extent, shortlist, and licence status per candidate,
    with UNDETERMINED stated as UNDETERMINED
  - whether any licence-clear candidate exists at all
  - Step 3: resolved, or bounded and constraining exactly what
  - Step 4: does VQ2 Imbue reach M7, yes or no
  - the specimen sheet, and which faces failed at 16 mm
  - where the parametric construction rule was recorded
  - anything in this brief that was wrong about the code or the geometry
```

---

## WHAT COMES BACK TO YOU

**A sheet with your twelve names on it, at the size they will be printed.**
After months of material engines and axis eligibility, this is the first thing
in the arc you look at rather than read.

**And possibly an unwelcome but cheap finding** — that nothing in a 3,741-file
library is licence-clear for commercial packaging, and you need to buy a face.
If that is true, it is far better to learn it now than after the artwork is
drawn around it. A text licence is a small line item; redrawing finished
packaging artwork is not.

**Then the lid layout**, which is the last decision only you can make before
the artwork itself gets built. I would rather show you options at true scale
than ask you to choose in the abstract, so that will follow the same shape as
this one.
