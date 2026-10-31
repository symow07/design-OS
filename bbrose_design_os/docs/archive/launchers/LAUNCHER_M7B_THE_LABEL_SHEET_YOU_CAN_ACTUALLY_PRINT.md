# LAUNCHER — M7b, THE LABEL SHEET YOU CAN ACTUALLY PRINT

Follows `e595a2d`. One owner ruling with an awkward shape, one deliverable
whose geometry is fully measured, and a substitution test that has to actually
be run rather than promised.

This is the first act that produces a piece of the M7 deliverable itself.

---

## THE RULING, AND WHY IT IS AWKWARD

**Asked and answered 2026-08-14.**

**The face is Adobe Caslon Pro.** It was chosen on the specimen, on design
grounds, and the grounds are legible in the numbers: under the sheet's uniform
sizing rule Caslon set at the largest cap height of the four — **7.37 mm**
against Garamond's 7.20, Minion's 6.86 and Crimson Text's 6.01. Inside a 16 mm
label that difference is the difference between type sitting in the frame and
type owning it.

**And BBROSE does not hold a licence for it.** Illustrator 2026 here is a
perpetual or otherwise non-subscription licence, so the Adobe Fonts activation
route that `es3083_font_census.json` names is **not available**. The six loose
OTFs in `materials/Fonts` remain exactly what the census said they were:
`fsType 8`, `nameID14 = adobe.com/type/legal.html`, no grant anywhere in the
repository. UNDETERMINED, and UNDETERMINED is not a licence.

A perpetual desktop licence for the family is purchasable — Adobe Originals
are carried by resellers, and Adobe's own Font Folio is a perpetually-licensed
collection — but nothing has been bought, so nothing may be built on it.

**So the chosen face and the buildable face are two different faces right
now.** That is not a failure of the census; it is the census working. It cost
a font scan to learn, rather than a redraw.

---

## WHAT THIS ACT DOES ABOUT IT

It refuses to do the two easy wrong things.

It does **not** set the sheet in Caslon and note the licence in a comment. A
deliverable built on an unlicensed face is a liability that gets harder to
remove the further downstream it travels, and this is precisely the point in
the programme where it starts travelling.

It does **not** overturn the owner's choice because the licensing is
inconvenient. The choice stands and gets recorded as the target.

Instead it **lands the sheet in Crimson Text — which is licence-clear today,
OFL, `fsType 0` — and makes the typeface a parameter rather than a fact.**
BBrose gets a real, printable, fully-licensed artifact now, and buying the
Caslon licence later changes one field rather than one artwork.

That is the same construction rule already binding on the geometry, applied to
the second thing that turned out to be uncertain. `es3083_artwork_geometry_substrate.json`
made the artwork re-flow under a caliper session. This makes it re-flow under
a licence purchase.

**And the claim gets tested, not asserted.** Step 4 renders the identical
layout in both faces and reports what moves. If the layout only works in one
of them, the substitutability is false and this act should say so.

---

## WHY THE LABEL SHEET AND NOT THE LID

Because the lid is the one thing the unresolved contradiction actually
constrains, and the label sheet is the one thing it does not.

`e595a2d` bounded rather than resolved the 77.00 mm label against the 65 mm
case: the labels in the vendor file are blank, the only photograph of them in
use shows them on the shipping blister bag, and it is raster and unmeasurable.
What that bound constrains is **where a 77 mm label can go on the pack** —
which is a lid-layout question.

It does not constrain the sheet. The sheet's geometry is measured end to end:

| | |
|---|---|
| label | **77.00 × 16.00 mm**, 24 off, 3 cols × 8 rows |
| pitch | **83.00 × 22.00 mm** |
| sheet | **263.00 × 190.00 mm** |

**And those four numbers make a prediction worth checking.** Three columns at
83 mm pitch put the last label's right edge at 243.00 mm; eight rows at 22 mm
pitch put the last label's bottom edge at 170.00 mm. Against a 263 × 190 sheet
that is exactly **10.00 mm of margin on all four sides**. If that falls out,
the measurement corroborates itself. If it does not, something in the geometry
is wrong and this act should find it before drawing on it.

So: build the half that rests on measured ground. The lid waits for the case
width, which is a caliper question and yours.

---

## THE PROMPT

```
GOAL — record the typeface ruling and its licence position honestly, verify
the label-sheet geometry closes, build the ES3083 shade-label sheet at true
scale as a parametric artwork with the typeface as a parameter, PROVE the
typeface substitution by rendering both, and state plainly what file formats
you can honestly deliver. Draw no lid artwork. Buy nothing. Outline nothing.

OWNER RULING — GRANTED AND RECORDED 2026-08-14 by PROJECT_OWNER.

  THE FACE IS ADOBE CASLON PRO. Chosen on the true-scale specimen at
  e595a2d, on design grounds: largest cap height of the four shortlisted
  faces under the sheet's uniform sizing rule (7.37 mm vs Garamond 7.20,
  Minion 6.86, Crimson Text 6.01), crispest serifs, and inside the ruled
  old-style / humanist direction.

  AND THE LICENCE IS NOT HELD. Illustrator 2026 here is NOT a current
  Creative Cloud subscription, so the Adobe Fonts activation route named in
  es3083_font_census.json is UNAVAILABLE. The loose OTFs in materials/Fonts
  are fsType 8 with no grant on record and remain UNDETERMINED. They are NOT
  to be used.

CONTEXT
  docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json   (the parametric rule)
  docs/roadmap/palt_m7/typeface_specimen/es3083_font_census.json
  docs/roadmap/palt_m7/typeface_specimen/es3083_typeface_specimen.png
  docs/roadmap/palt_m6/es3083_shade_authority.json              (the twelve, at 1.3)
  ES3083_DIMENSION_FINDINGS.md                                  (measured geometry)
  docs/roadmap/palt_m4c/m7_artwork_scope_ruling.json            (BBROSE-original)
  docs/roadmap/palt_m4c/m7_typeface_direction_ruling.json
  materials/Fonts/                                              (READ ONLY)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — RECORD THE FACE RULING WITH ITS LICENCE POSITION ATTACHED

  One record. It must carry ALL of the following, because a later reader who
  sees only half of it will do the wrong thing:

    - the chosen face: Adobe Caslon Pro, and WHY, in the specimen's own
      numbers rather than in adjectives
    - that the licence is NOT held, that no CC subscription exists, and that
      the Adobe Fonts activation route is therefore unavailable
    - that the materials/Fonts OTFs are UNDETERMINED and MUST NOT be used in
      any deliverable, working file, or render
    - the SET FACE, which is what the artwork is actually built in today:
      Crimson Text, licence-clear, OFL, fsType 0
    - the exact condition that would let Caslon become the set face — a
      purchased desktop licence held by BBROSE, recorded with its evidence

  Name the two roles distinctly. TARGET_FACE and SET_FACE, or whatever you
  prefer, but they must be two named fields and not one field with a caveat.
  The failure mode this arc has hit three times is a record whose halves
  disagree (D11); this record has two halves that disagree BY DESIGN, so the
  design must be explicit.

  Carry forward one constraint the census raised and do not lose it: only
  CrimsonText-Regular carries nameID14. The Bold/Italic/SemiBold files carry
  fsType 0 but NO OFL declaration, so their standing is by family provenance
  only. If the sheet needs any style other than Regular, say so and say that
  the family must be fetched fresh from its source with its OFL.txt. If it
  needs only Regular, say that too — it is the cleaner answer.

STEP 2 — VERIFY THE SHEET GEOMETRY CLOSES BEFORE DRAWING ON IT

  From ES3083_DIMENSION_FINDINGS.md: label 77.00 x 16.00 mm, 24 off, 3 cols
  x 8 rows, pitch 83.00 x 22.00 mm, sheet 263.00 x 190.00 mm.

  Check the arithmetic against the vendor file rather than against my sum:
  3 columns at 83.00 pitch put the last right edge at 243.00; 8 rows at 22.00
  pitch put the last bottom edge at 170.00; against 263.00 x 190.00 that is
  10.00 mm margin on all four sides.

  Confirm or refute, from the geometry in the file. If the margins are not
  10.00 mm all round, the measurement or the pitch is wrong and you must say
  which and STOP before building on it.

  Then answer one question I do not know the answer to and have not assumed:
  THERE ARE 24 LABELS AND 12 SHADES. Is it two labels per shade, or is some
  other allocation recorded or evident? Read it from the vendor file and the
  records. If nothing establishes it, say UNDETERMINED and state what you
  assumed for the build and where that assumption is recorded so it can be
  changed in one place.

STEP 3 — BUILD THE SHEET, PARAMETRIC

  Build the ES3083 shade-label sheet at true scale from the measured geometry
  and the twelve names read from es3083_shade_authority.json 1.3. Do not
  retype the names from this brief.

  Binding construction rules, all of which must be true of the artifact and
  verifiable by reading it:

    - EVERY dimension is read from the geometry substrate record. No numeric
      literal for any millimetre value appears in the drawing code. A caliper
      session changes the record, not the code.
    - THE TYPEFACE IS A PARAMETER. Family, size, tracking and any optical-size
      choice live in one named spec that the layout reads. Changing the family
      is one field.
    - THE FIT RULE IS A CONSTRAINT, NOT A CONSTANT. The specimen's rule was
      "largest size at which the longest name fits 71 mm AND ascent+descent
      fits 12 mm." Implement it as a solve against the actual font metrics, so
      a different face resolves to its own size automatically. Do not hard-code
      26.2 pt or any other number the specimen happened to produce.
    - NO TYPE IS OUTLINED. Not in the working file, not in any intermediate.
      Outlined type cannot be re-flowed and would silently defeat everything
      above. Outlining is a step for a licensed final only.
    - The two margins, the pitch and the label frames are constructed from
      pitch and count, never placed by hand.

  State where each of these rules is recorded so a later act cannot miss them,
  and extend the geometry substrate record rather than starting a parallel one.

  On the visual treatment: produce TWO OR THREE treatments at true scale for
  owner judgment, and commit to none. The variables worth showing are the ones
  that cost money at the vendor or cannot be changed later — keyline or no
  keyline, one colour or two, centred or ranged left, and whether the label
  carries anything besides the name. Say for each treatment what it would cost
  in print terms. Do NOT invent brand elements, marks, ornaments or rules that
  are not already established in the records — the artwork is BBROSE-original
  per m7_artwork_scope_ruling.json, and originality is not licence to add
  things nobody asked for at this stage.

STEP 4 — PROVE THE SUBSTITUTION, DO NOT PROMISE IT

  Render the IDENTICAL layout twice: once in Crimson Text (the set face) and
  once in Adobe Caslon Pro (the target face), for comparison only.

  IMPORTANT — the Caslon render is a TEST ARTIFACT, not a deliverable. It
  exists to prove the parameter works. Mark it as such in its filename and in
  its record, keep it out of any deliverable directory, and state plainly that
  it may not be printed, sent, or shown to a client until a licence is held.
  If you judge that even rendering it is the wrong call, say so and instead
  substitute a THIRD licence-clear face to prove the parameter — that is an
  acceptable and arguably better test, and I would rather you make that
  judgment than follow my instruction into a mistake.

  Report what actually changed between the two renders: the solved point size,
  the cap height, the set width of the longest and shortest names, and whether
  any name's fit changed from comfortable to tight. If ANYTHING required a
  manual adjustment to work in the second face, the substitution is not
  parametric and you must say so plainly rather than fix it quietly.

STEP 5 — SAY WHAT YOU CAN HONESTLY DELIVER

  M7's deliverable names an "editable .AI (Illustrator 2026)". You do not have
  Illustrator.

  State, without softening it, what you can and cannot produce:
    - what you CAN write that opens in Illustrator 2026 with its structure,
      layers and live text intact
    - whether that is a native .AI, a PDF-compatible file carrying the .ai
      extension, an SVG, or something else — and what the practical difference
      is when BBrose opens it
    - what would be lost or degraded on that route, specifically
    - what a genuine native .AI would require

  Do not name a file .ai unless it genuinely is one. A file that opens is not
  the same as a file that is what it claims to be, and this programme has
  spent an entire arc on exactly that distinction.

  Deliver the rendered PNG at true scale with pHYs set, as at e595a2d, so the
  sheet can be judged at size regardless of the vector format question.

DO NOT
  - use Adobe Caslon Pro from materials/Fonts in any deliverable
  - set the sheet in a face whose licence status is UNDETERMINED
  - outline any type
  - hard-code any millimetre value or any point size in the drawing code
  - design or draw the lid layout, or resolve the 77mm/65mm question by
    assumption
  - invent brand marks, ornaments or copy not already in the records
  - reclassify any pan or touch the shade record's colours, names or families
  - claim a native .AI you did not produce
  - close D5

REPORT BACK
  - where the face ruling was recorded, and the two named fields for the
    target face and the set face
  - Step 2: do the margins close at 10.00 mm all round, yes or no; and the
    24-labels-to-12-shades answer, or UNDETERMINED
  - the sheet, its treatments, and what each would cost in print terms
  - Step 4: what changed between the two faces, and whether ANY manual
    adjustment was needed
  - Step 5: the honest format answer
  - anything in this brief that was wrong about the geometry, the census or
    the code
```

---

## WHAT COMES BACK TO YOU

**A printable sheet with your twelve names on it.** Not a specimen this time —
the actual artwork for the actual labels, at the actual size, in a face you
are actually licensed to use. It is the first piece of the M7 deliverable
rather than a study for it.

**And a Caslon that is one purchase away.** The point of Step 4 is that when
you buy the licence, nothing gets redrawn. If Step 4 comes back saying a
manual adjustment was needed, that is the more useful result, because it means
the parametric claim was wrong and we find out now rather than after the lid,
the box and the back label are all built on it.

**Then the lid**, which needs the 65 mm case settled — and that is calipers,
and that is yours. Everything else on the artwork side is now moving.
