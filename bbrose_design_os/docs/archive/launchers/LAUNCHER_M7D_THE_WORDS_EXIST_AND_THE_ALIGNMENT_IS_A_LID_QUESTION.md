# LAUNCHER — M7d, THE WORDS EXIST, AND THE ALIGNMENT IS A LID QUESTION

Follows `37f9d54`. One record that is wrong in both halves of its central
claim, one of my own findings that the render refuted, and a failure mode that
has now happened four times under an amendment written specifically to prevent
it.

No new renders required except one verification. Short act.

---

## WHAT `37f9d54` GOT RIGHT

The de-confounding is exactly right and the set design is stated where the set
is defined rather than in a report — which is the correction landing properly
rather than being described. Four variables, four clean isolating pairs, and
the un-rendered cells justified rather than silently omitted.

**Splitting the cost table three ways was better than my two.** I asked for
per-ink against per-tolerance; the answer was that a tinted ground is neither —
it is a purchasing fact if the stock is bought tinted and an ink if the ground
is flooded, and those are different line items. That refinement is the act
improving the brief, which is the arrangement working.

The stock field copies the allocation shape exactly, and `discharged_by`
correctly names the vendor before the owner, since the sheet lives in the
vendor's production file. The licence predicate is now stated once, and the
self-report that the sweep was field-symmetric while the per-face citations
were one-sided is precise and honest.

---

## STEP 4 IS WRONG IN BOTH HALVES

`es3083_back_label_prerequisites.json` says the geometry is ready and the words
do not exist. Both clauses of the second half fail.

**"It cannot be recovered from the vendor file: the vendor's back labels carry
dense outlined text (0 live text spans) that cannot be read back as words."**

It was read back as words. `ES3083_DIMENSION_FINDINGS.md:65-78`, under a
heading that says so — **`MEASURED FROM PRINTED COPY — PRODUCT_LABEL_DECLARED`**:

> NET WT **11 g** · ITEM NO **ES3083** · EAN **5 061030 636510** · executive
> standard **QB/T 1976-2004** · approval **ZHEZHUANG20210006** · supplier
> Yiwu Yibin Trading Company · ingredients: Mica, Talc, Paraffinum Liquidum,
> Kaolin, Magnesium Stearate, Polyethylene, Silica, Ethylhexyl Palmitate,
> Simethicone, Phenoxyethanol

An earlier act read the page render at 200 dpi *because* the type was outlined.
The later act treated "0 live text spans" as proof of unreadability, which is
true of text extraction and false of the artefact.

**"NO record anywhere holds ingredients, warnings, distributor identity or a
barcode number for ES3083."**

Its stated extent: *grep `INCI|ingredient` over `docs/roadmap/palt_m1`,
`palt_m4c`, `palt_m7`.* The predicate was fine. **The population excluded the
repository root** — and `ES3083_DIMENSION_FINDINGS.md` lives there, and line 77
begins "ingredients lead: Mica, Talc, …", and the predicate would have hit it.

**The same record cites that file, two fields earlier, for the geometry.** It
read the file for millimetres and excluded it from the population when
searching for words.

---

## THE FOURTH TIME

`61ddd75` searched `docs/` and `apps/` for the M4C-4 panel and missed
`OWNER_BLOCKER_SESSION.md` at the root. The formulation then was the best of
the arc: *"the extent was correctly stated and wrongly chosen."*

It has now happened again, in the same way, at the same directory boundary,
missing a file the searching record itself cites.

A564 requires that an absence claim state its extent. It does not require that
the extent be *defensible*, and nothing checks whether the population plausibly
contains the thing being sought. Four instances, one amendment that half
covers it, and no defect entry. D9 is a blocker's premise going stale, D10 an
undeclared choice of measure, D11 a record whose halves disagree, D12 a rule
applied outside its fitted population. **A well-stated extent over a badly
chosen population is none of them**, and it is the one this programme commits
most often.

---

## AND MY ALIGNMENT ARGUMENT WAS WRONG

I wrote in M7c that "a common left edge makes the same twelve read as one
system," and asked for T4 on that basis. T4 is rendered and it does exactly
that. **The argument is still wrong, because the sheet is not the product.**

Label 77 × 16 mm at a pitch of 83 × 22 leaves a 6 mm gutter on both axes.
That is a die-cut gutter. These twenty-four labels are cut apart and applied
individually, and the moment they are, the shared left edge I was judging
ceases to exist. Nobody outside the print works ever sees the sheet.

What survives the die is one name inside one 77 × 16 mm frame. Whether it
should sit centred or ranged left depends entirely on what it sits next to on
the pack — centred if it is captioning a pan, ranged left if it is one line in
a list. **That is a lid-layout question**, and the lid is gated on the 65 mm
case, which is calipers, which is BBrose.

So the alignment cell is real and correctly rendered, and it cannot be decided
yet. The ink cell and the ground cell can. Saying which of the four are live
is more useful right now than adding a fifth.

---

## THE PROMPT

```
GOAL — correct a back-label record that is wrong in both halves of its central
claim, adjudicate what of the recovered vendor copy BBROSE may and may not
reuse, restate what the back label is actually gated on, verify the die-cut
reading and state which treatment cells are decidable now, and name a failure
mode that has recurred four times. Build nothing. Render nothing except the
verification in STEP 4 if it needs one.

CONTEXT
  docs/roadmap/palt_m7/es3083_back_label_prerequisites.json   (the record to correct)
  ES3083_DIMENSION_FINDINGS.md:65-78                          (PRODUCT_LABEL_DECLARED)
  ES3083_DIMENSION_FINDINGS.md:85-105                         (the absence claims that WERE done properly)
  docs/roadmap/palt_m4c/m7_artwork_scope_ruling.json          (BBROSE-original)
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json (SUPPLIER_DATA, deferred)
  docs/production_authority/supplier_outreach_deferral.json
  docs/roadmap/palt_m6/open_defect_inventory.md               (D9-D12)
  apps/pipeline/services/palette_es3083_intent.py:115         (regulatory_zones HARD)
  docs/roadmap/palt_m7/es3083_artwork_geometry_substrate.json

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — VERIFY THE PREMISE BEFORE ACTING ON IT

  Read ES3083_DIMENSION_FINDINGS.md:65-78 and confirm or refute:

    a. it records product copy read from the vendor's printed back labels —
       net weight, item number, EAN, executive standard, approval number,
       supplier identity and an ingredients list
    b. it was obtained by reading the page render at 200 dpi, NOT by text
       extraction, and the outlined type is why
    c. the file sits at the repository ROOT, outside the three palt_*
       directories the back-label record's extent named
    d. the predicate INCI|ingredient WOULD have matched line 77

  If any part is wrong, say so and STOP. The rest of this brief rests on it.

STEP 2 — CORRECT THE RECORD, AND ADJUDICATE REUSE SEPARATELY

  These are two different questions and the corrected record must not merge
  them:

    QUESTION ONE — what copy is RECOVERED? Answer from :65-78. State the
    confidence: this was read off a 200 dpi raster, so transcription is a real
    risk, and an ingredients list or a barcode digit read wrong is a
    regulatory error rather than a typo. Say what would firm it up.

    QUESTION TWO — what may BBROSE REUSE? This is a judgment and it differs
    item by item. Do not answer it uniformly. Consider at least:

      - the INCI ingredients list is a factual declaration of a formulation,
        not authored copy — but it is only BBROSE's to declare IF BBROSE's
        product is that formulation, which is a SUPPLIER question
      - net weight and executive standard are product facts on the same footing
      - supplier identity, the approval number ZHEZHUANG20210006, and the EAN
        are IDENTIFIERS BELONGING TO OTHER PARTIES and are not BBROSE's to
        print, whatever the artwork ruling says about originality

    On the EAN specifically: 5 061030 636510 begins with a GS1 prefix
    associated with the UK, on a label from a Chinese vendor. Do not conclude
    anything from that. Record it as a QUESTION FOR THE OWNER — whose barcode
    is it — because printing another party's GS1 number is a real problem and
    printing BBROSE's own is fine, and only the owner knows which it is.

STEP 3 — RESTATE THE GATE

  The record currently says the back label is gated on "copy nobody has
  written." Replace that with what is actually true after Step 2.

  My reading, to confirm or refute: it is gated substantially on the SAME
  SUPPLIER_DATA blocker the owner already deferred (formulation, and therefore
  the INCI list; plus manufacture standard and approval), PLUS owner-supplied
  responsible-person / distributor identity, which no supplier can provide and
  which a Chinese vendor's approval number does not satisfy for a UK or EU
  sale. If that is right, the back label is not a new gate — it is an existing
  deferred gate plus one owner fact.

  Say which, and update the blocker record's chain if the relationship is real
  so a later reader sees it. Do not open a new blocker if this is the old one
  wearing a different name — that is exactly the D11 shape.

STEP 4 — VERIFY THE DIE READING, THEN SAY WHICH CELLS ARE LIVE

  I claimed the 24 labels are individually die-cut, from the 6 mm gutter that
  83 x 22 pitch leaves around a 77 x 16 label. That is an inference, not a
  measurement. Check the vendor file for a die, cut, kiss-cut or thru-cut
  layer, spot-colour or stroked path set around the label rects, and confirm
  or refute. State the extent.

  If the labels ARE cut apart, then sheet-level column alignment is destroyed
  at the die and my M7c argument for ranged-left was made about an artefact no
  customer sees. Say so plainly — it was my error, not the renderer's, and T4
  is correctly built either way.

  Then state, for each of the four variables, whether it is DECIDABLE NOW or
  DOWNSTREAM, and of what:
    ALIGNMENT (T1 vs T4), KEYLINE (T4 vs T2), INK (T1 vs T3), GROUND (T1 vs T5)

  Be specific about what each downstream one waits on. If any of them is
  decidable now and I have implied otherwise, say that too.

STEP 5 — NAME THE FOURTH INSTANCE

  Four times an absence claim has stated its extent correctly and chosen its
  population badly: 61ddd75 (searched docs/ and apps/, missed
  OWNER_BLOCKER_SESSION.md at the root) and 37f9d54 (searched three palt_*
  directories, missed ES3083_DIMENSION_FINDINGS.md at the root — a file the
  same record cites for geometry). Sweep for the other instances rather than
  taking my count on trust; state your extent, and if there are only two, say
  two.

  A564 mandates stating the extent. Nothing checks whether the population
  plausibly contains the thing sought. Decide whether that gap is D10's, its
  own, or something already covered, and open or extend ONCE.

  Then propose — do not implement — the cheapest control that would have
  caught both instances. One paragraph. If the honest answer is that no cheap
  mechanical control would work and it is a discipline rather than a check,
  say that instead of inventing a check that would not have fired.

DO NOT
  - build or draw the back label
  - write, invent or draft any regulatory copy
  - reuse the supplier identity, the approval number or the EAN in any artwork
  - decide the barcode question
  - re-render the label sheet or change any geometry, fit rule or treatment
  - choose a treatment, alignment, ink, ground or stock
  - open a new blocker if this is SUPPLIER_DATA wearing a different name
  - open more than one defect entry
  - use Adobe Caslon Pro, or outline any type
  - close D5

REPORT BACK
  - Step 1: confirmed or refuted, all four parts
  - the recovered copy, its confidence, and the reuse adjudication item by item
  - the EAN question as a question
  - Step 3: what the back label is really gated on, and whether it is the old
    blocker
  - Step 4: die confirmed or refuted with extent; and the four variables marked
    DECIDABLE NOW or DOWNSTREAM OF WHAT
  - Step 5: the sweep's real count, what was opened or extended, and the
    proposed control or the honest statement that there isn't one
  - anything in this brief that was wrong
```

---

## WHAT COMES BACK TO YOU

**A back label that is much closer than it looked an hour ago.** Its geometry
was already measured; now roughly half its copy turns out to be sitting in a
file we have been citing all week. What is genuinely missing is smaller and
more specific than "the words do not exist."

**And an honest list of which decisions you can actually make today.** Of the
four treatment variables, my reading is that ink and ground are yours now,
keyline is nearly so, and alignment is not — it is a lid question in disguise,
and the lid is still waiting on the one measurement only you can take.

**Plus one question worth answering before anything else here:** whose barcode
is `5 061030 636510`. If it is yours, that is one fewer thing to source. If it
is not, it must never reach artwork.
