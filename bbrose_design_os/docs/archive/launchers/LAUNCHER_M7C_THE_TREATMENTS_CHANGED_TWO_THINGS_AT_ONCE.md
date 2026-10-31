# LAUNCHER — M7c, THE TREATMENTS CHANGED TWO THINGS AT ONCE

Follows `9ef340d`. One confounded comparison to de-confound, one undeclared
parameter to declare, two record lines to correct, and the back label — which
turns out to be as fully measured as the sheet was.

Small act. The sheet itself is sound and is not being rebuilt.

---

## WHAT `9ef340d` GOT RIGHT

**Step 4 was the right call and it was made against the brief.** My Step 1
mandated a record saying the Caslon OTFs must not be used in any render, and
my Step 4 instructed a Caslon render. Those cannot both be obeyed. It followed
the record, took the third-face route, and said so. That is the escape hatch
working as intended, and it is the second time in this arc a brief's own
contradiction was caught by the act executing it.

**The geometry was verified rather than accepted.** 24 rects at exactly 77.000
× 16.000, column pitches 83.002/82.998, row pitches 21.999–22.003, margins
10.000 on all four sides — checked against the vendor file's geometry, not
against my arithmetic. Independently reconfirmed here.

**The parametric claim is real.** One field changed the family and everything
re-solved: 26.16 pt → 24.00 pt, cap 6.01 → 6.31 mm, Midnight Bloom 60.36 mm
(85.0%) → 70.66 mm (99.5%, width-pinned), zero manual adjustments. That is the
proof the act was for, and it passed.

**And the format answer was honest.** No `.ai` claimed, none delivered. The PDF
is a real one — MediaBox exactly 263.00 × 190.00 mm, 24 live text spans, the
Crimson subset embedded as `AAAAAA+CrimsonText-Regular`, verified here by text
extraction. The spot-colour limitation was stated rather than glossed.

---

## THE CONFOUND

Three treatments, two variables moved together.

| | alignment | keyline | colour |
|---|---|---|---|
| **T1** | centred | none | black |
| **T2** | **ranged left** | **0.25 pt** | black |
| **T3** | centred | none | 627 C |

T1 against T3 isolates colour cleanly. T1 against T2 moves alignment **and**
keyline at once, and there is no fourth cell. So the sheet cannot answer the
question it most needs to answer: **is ranged left better than centred?** —
because every ranged-left label on the sheet also has a box drawn round it.

This matters because the two variables have completely different costs.
Alignment is free. A printed keyline at the die edge is the highest-risk
element on the sheet: it makes every millimetre of die drift visible as an
uneven border, and `9ef340d` correctly priced it as tightening the tolerance
the vendor must hold. Bundling a free decision with an expensive one means the
owner cannot take the first without buying the second.

**And on the renders, alignment looks like the decision that matters.** The
names run from "Dew" to "Midnight Bloom" — a factor of three in set width — in
a fixed 77 mm frame. Centred, the short names float in the middle of their
labels and the sheet reads as twelve unrelated items. A common left edge makes
the same twelve read as one system. That is a judgment, not a measurement,
which is exactly why it needs to be shown uncontaminated rather than argued.

---

## THE UNDECLARED PARAMETER

A search of `docs/roadmap/palt_m7/` and `ES3083_DIMENSION_FINDINGS.md` for
stock, paper, substrate colour, adhesive, lamination or varnish returns
**nothing**. Extent: case-insensitive grep over that subtree and that file.

So all three treatments are being judged as ink on white, and nothing in the
programme establishes that the stock is white. This is D10's shape — an
undeclared choice that quietly conditions a judgment. 627 C on white, 627 C on
uncoated cream and 627 C on a 621 C tint are three different decisions, and
**621 C is already a measured token in the substrate**, so the tinted option
was available and was not shown.

The point is not that white is wrong. It is that white was never chosen.

---

## AND THE BACK LABEL IS ALSO MEASURED

Worth noticing, because it changes what is available to build:

| | |
|---|---|
| back label, printed | **49.50 × 49.50 mm**, 2.0 pt keyline |
| back label, die/bleed | **55.00 × 55.00 mm**, pitch 58.4 mm |

That is measured geometry, like the shade sheet and unlike the lid. It is not
in this act's scope — it needs its copy settled first, and copy on a back label
is regulatory as well as aesthetic — but it means the lid is not the only thing
left, and the caliper session is not gating as much as it appears to.

---

## THE PROMPT

```
GOAL — de-confound the label-sheet treatments so the alignment decision can be
made on its own, declare the stock parameter that nothing has declared,
correct two licence lines, and state what the back label would need. Do not
rebuild the sheet. Do not choose a treatment. No lid artwork.

CONTEXT
  docs/roadmap/palt_m7/label_sheet/render_label_sheet.py
  docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json
     LABEL_SHEET_CONSTRUCTION_2026_08_14 / TYPEFACE_SPEC_2026_08_14
  docs/roadmap/palt_m4c/m7_typeface_face_ruling.json
  docs/roadmap/palt_m7/typeface_specimen/es3083_font_census.json
  ES3083_DIMENSION_FINDINGS.md                       (back label geometry)
  docs/roadmap/palt_m5/m5_validation_report.json:98  (the Pantone tokens)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — DE-CONFOUND THE TREATMENTS

  T1 (centred / no keyline / black), T2 (ranged left / 0.25 pt keyline /
  black) and T3 (centred / no keyline / 627 C) move alignment and keyline
  together. T1 vs T3 isolates colour; nothing isolates alignment.

  Render the missing cells so that EACH variable can be judged alone. At
  minimum the sheet needs ranged-left-WITHOUT-keyline, because alignment is
  free and a die-edge keyline is not, and the owner must be able to take one
  without the other.

  Decide the full set yourself — I am not going to specify a matrix you may
  have good reason to trim. But state the design of the set explicitly: which
  variable each pair isolates, and which cells you chose not to render and
  why. A comparison whose structure is not stated is the defect this step
  exists to remove, so do not reproduce it.

  Keep the existing three so nothing already judged is invalidated. Add,
  do not replace. Reuse the renderer; change no geometry and no fit rule.

  Restate the print cost per cell, and separate the costs that are per-INK
  from the costs that are per-TOLERANCE. Those are different kinds of money
  and the previous table blended them.

STEP 2 — DECLARE THE STOCK

  Nothing in docs/roadmap/palt_m7/ or ES3083_DIMENSION_FINDINGS.md mentions
  stock, paper, substrate colour, adhesive, lamination or varnish. Confirm or
  refute that, and state your search extent per A564.

  If confirmed: record stock as an EXPLICIT, NAMED, UNDETERMINED parameter in
  the substrate, in one field, with the build assumption stated (white) and
  the note that every treatment judged so far was judged against it. Do not
  bury it in prose — it must be a field that a later act reads, the same way
  the 24/12 allocation was handled at 9ef340d. That handling was correct; copy
  its shape.

  Then render ONE additional cell on a 621 C tinted ground — the token is
  already measured in the substrate — so the assumption becomes visible rather
  than invisible. Mark clearly that the stock is UNDETERMINED and this cell is
  showing a question, not proposing an answer.

  State what would discharge it: a vendor stock specification, or the owner's
  decision. Say which of those it actually is.

STEP 3 — CORRECT TWO LICENCE LINES

  (a) Merriweather-Bold.ttf's two licence fields disagree with each other:
      nameID13 carries the verbatim SIL OFL 1.1 text, nameID14 points to
      http://sorkintype.com/eula.html. The TEST_FACE record cites only
      nameID13. Verify both fields yourself, then record BOTH, and note that
      the file's halves disagree — it is D11 occurring inside a font file, and
      a one-sided licence line is the thing this programme keeps catching.
      The test artifact stays valid and stays marked; only the record changes.

  (b) The two licence-clear determinations in this programme rest on DIFFERENT
      fields: Crimson Text Regular has nameID14 and NO nameID13; Merriweather
      Bold has nameID13 and a contradicting nameID14. Verify that, then state
      the census's licence predicate ONCE, explicitly — which fields count,
      whether either alone suffices, and what a disagreement between them
      means. Record it where the census lives.

      Do NOT re-run the 4,677-file census. This is a statement of the
      predicate already used, not a new scan. If stating it plainly reveals
      that the predicate was applied inconsistently across the census, say so
      — that is a real finding — but do not go looking for work.

STEP 4 — SAY WHAT THE BACK LABEL WOULD NEED

  ES3083_DIMENSION_FINDINGS.md measures the back label: 49.50 x 49.50 mm
  printed with a 2.0 pt keyline, 55.00 x 55.00 mm die/bleed, pitch 58.4 mm.
  That is measured geometry, unlike the lid.

  Do not build it. State, in one short record, what a back-label act would
  need before it could start — specifically what COPY it must carry, where
  that copy would come from, and which parts of it are regulatory rather than
  aesthetic. Name the records that would govern it if any exist, and say
  plainly if none do.

  The purpose is to tell the owner what is actually reachable without a
  caliper session. If the honest answer is that the back label is gated on
  copy nobody has written, say that in one sentence.

DO NOT
  - rebuild the sheet, or change any geometry, pitch, margin or fit rule
  - choose a treatment, an alignment, a colour or a stock
  - re-run the font census
  - use Adobe Caslon Pro anywhere
  - outline any type
  - hard-code any millimetre value or point size
  - draw the lid, the back label, or resolve the 77mm/65mm question
  - invent copy, marks or ornaments
  - close D5

REPORT BACK
  - the de-confounded set, its stated design, and which variable each pair
    isolates
  - the per-ink and per-tolerance costs, separated
  - Step 2: confirmed or refuted with extent; where the stock field landed;
    and whether the 621 C ground changes your reading of anything
  - Step 3: both licence corrections, and the predicate stated once
  - Step 4: what the back label is actually gated on
  - anything in this brief that was wrong
```

---

## WHAT COMES BACK TO YOU

**A comparison you can actually decide from.** Right now the sheet asks you to
approve alignment and a die-edge keyline as a package. After this you can take
the alignment, which is free, and decline the keyline, which is not — or take
both, but knowingly.

**And a visible question about the stock**, which has been quietly answered
"white" by nobody in particular for three treatments. Seeing 627 C on a 621 C
ground once may settle it in either direction, and either is progress.

**Then the treatment is yours to choose**, and after that the reachable work
is the back label — gated on copy, not on calipers. The lid still waits for the
65 mm case, and that is still the one thing only you can measure.
