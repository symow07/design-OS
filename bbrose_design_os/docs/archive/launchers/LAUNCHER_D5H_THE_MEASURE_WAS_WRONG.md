# LAUNCHER — D5h, THE MEASURE WAS WRONG

Follows `61ddd75`. Three findings from verifying that commit, one of which
undoes part of its own last section. No new renders if the EXRs survived.

---

## WHAT 61ddd75 GOT RIGHT

The ruling is recorded at `palt_m4c/m7_artwork_scope_ruling.json` and the
placement reasoning is sound — a roadmap scope ruling belongs next to the
continuation state whose blocker it resolves, not in a manufacturing
directory. The blocker chain survived intact. The id correction went the right
way: the title described what M6 actually did, the slug described what the
founding plan had assigned, and the slug was the stale part. Correcting toward
the work rather than toward the plan is right, because the plan is history and
the work is fact.

The coefficient sweep was good work with a stated extent, and its class
judgment was correct.

Three things need repair.

---

## FINDING 1 — THE M4C-4 CHECK LOOKED IN THE WRONG PLACE

`61ddd75` reports that no committed record shows the M4C-4 panel confirmed,
and that two committed records say it was never confirmed at all.

The search extent was `docs/`. The record is at the repo root.
`OWNER_BLOCKER_SESSION.md:66` reads **"STEP 1 — CONFIRM THE M4C-4 PANEL —
✅ CLOSED 2026-08-12"**, and carries the version identities `e2e81bcd60d7f35f`
/ 20 actions, `ad8dc32c8987f953` / 21 actions, a third at 21 actions with
`regulatory_zones` confirmed, gate decisions 57 and 58, scope
`VISIBLE_COMPOSITION_ONLY`, draft `9b3603e17e85746c` never mutated. It also
records that `pan_count`, `rows` and `columns` were reclassified to HARD in
that same session.

So the brief was right and the check was under-scoped. A564 requires the
extent be stated, and it was — that is why this is correctable rather than
silent.

**But the finding underneath it is real and better than it was reported.**
`palette_roadmap_continuation_state.json:369-372` still carries
`VQ1_HUMAN_STRUCTURAL_REVIEW` with the detail *"the M4C-4 confirmation panel
is drafted and served but has NOT been confirmed by the owner in the
browser."* `open_defect_inventory.md:170-172` says the same: *"served but
never confirmed by the owner in a browser. No amount of engineering closes
this one."* Both have been false since 12 August.

Which means the standing-blocker count reported at `61ddd75` is wrong. It is
not three. And this is D9 a third time, now with a confirmed instance instead
of an inferred one.

---

## FINDING 2 — THE FAMILY CENSUS WAS MEASURED WHERE THE FAMILIES DO NOT LIVE

`family_candidates/_measures.json` is PLANAR-scoped throughout. Two families
scored **below the matte control** on planar luminance:

| | lum p99/med | lum max/med | chroma spread |
|---|---|---|---|
| POWDER_MATTE (control) | 1.2400 | 1.3927 | 0.001547 |
| BAKED | 1.2156 | 1.3922 | 0.001272 |
| PRESSED_POWDER | **1.1779** | **1.2507** | 0.001616 |

A matte control out-varying a compaction-ring family on the flat region is the
measure failing, not the family. The frozen builder's own docstring says
MATTE/SATIN/**PRESSED** carry *"real bump microstructure — the grazing
response comes from geometry-level normals, never colour+roughness alone."*
Grazing response is the one thing a flat region cannot show.

PRESSED_POWDER is **Old Rose, pan 9**. It was cleared on a measure blind to
its declared distinction, exactly as BAKED was.

SHIMMER and POWDER_METALLIC survive the doubt on their own numbers —
1.8569 and 3.9515 max/median. Flake families read on luminance even with flat
chroma, which is correct. MARBLED is albedo-derived and chroma is the right
axis for it, so its 9.8× stands. The exposure is BAKED and PRESSED only.

---

## FINDING 3 — THE ATTAR RE-MEASURE USED A SCALAR THE INSTRUMENT RETIRED

This is the sharpest of the three and it undoes `61ddd75`'s own last section.

The Attar correction was measured as **max/median on QUARTER_CYLINDER and
BEVEL** — 1.6099 vs 1.5494, and 1.4826 vs 1.4499.

`palette_characterization_rig.py:269-274` is explicit that this is the wrong
quantity:

> §6 independence: five of the six axes previously read the SAME scalar —
> peak divided by median — from five regions. Those are transformations of one
> quantity, not five independent axes, and they all describe how TALL a
> highlight is. What separates a matte from a satin is how WIDE it is, so each
> region axis now reports its own lobe width.

The repair removed peak-over-median from five of six axes precisely because it
does not discriminate. `axes_from` now reads `highlight_fwhm_fraction` on
QUARTER_CYLINDER, GRAZING, SHALLOW_CURVE and BEVEL, plus
`specular_to_diffuse_ratio` and `scene_linear_p999`.

So `61ddd75` found a ~4% margin on a scalar the instrument retired for being
non-discriminating, and reported it as BAKED reading in the gloss direction.
That conclusion is not supported. It may still be true — but it has not been
measured. And the re-measure skipped **GRAZING** entirely, which is the region
the frozen builder names for exactly this class of family.

This is the same root as the coefficient defect: a repair landed, and the
analysis that came after it used the pre-repair form. Third instance in this
arc, and the first two were both in files. This one was not in a file, which
is worth noticing, because a sweep of files would never have caught it.

---

## THE PROMPT

```
GOAL — correct three things that verification of 61ddd75 found: a check that
looked in the wrong place, a census measured on the wrong region, and a
re-measure that used a scalar the instrument retired. No new renders if the
EXRs survived. No design decisions. No new instruments.

CONTEXT
  OWNER_BLOCKER_SESSION.md:66-86                  (the M4C-4 confirmation, at the REPO ROOT)
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json:369-372
  docs/roadmap/palt_m6/open_defect_inventory.md:170-172   (D4)
  docs/roadmap/palt_m6/family_candidates/_measures.json
  apps/pipeline/services/palette_characterization_rig.py:258-290  (axes_from, and §6)
  apps/pipeline/services/blender_scripts/powder_materials.py:4-28  (FROZEN, read only)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — THE M4C-4 RECORD

  Your Step 1 check at 61ddd75 searched docs/ and concluded no committed
  record shows the panel confirmed. OWNER_BLOCKER_SESSION.md at the repo root
  is a committed record and states it was confirmed 2026-08-12, with three
  version identities, gate decisions 57 and 58, and scope
  VISIBLE_COMPOSITION_ONLY. Read it before doing anything else and confirm or
  refute that reading. If I have misread it, say so and stop this step.

  If it holds:

    a. Land the confirmation where docs/ can see it. A confirmation that
       exists only in the DB and in a root-level markdown file is why this
       was missable. Decide where it belongs and say why.
    b. Withdraw VQ1_HUMAN_STRUCTURAL_REVIEW — withdraw, do not delete, same
       treatment as ES3083_TYPEFACE_UNIDENTIFIED. Its detail has been false
       since 2026-08-12.
    c. BEFORE withdrawing it, answer one question: does confirming the panel
       actually discharge what this blocker gates, or was the blocker's
       stated detail always a narrower thing than its purpose? The
       confirmation granted NO gate approval — all four authority flags are
       unchanged. If the blocker is really about owner structural judgment
       and the panel was only its first step, then it is not resolved and
       what needs correcting is its WORDING, not its status. Decide, and say
       which.
    d. Update D4 to match whatever (c) decided.
    e. Restate the standing-blocker count and list.

STEP 2 — RE-MEASURE THE CENSUS ON THE INSTRUMENT'S OWN AXES

  First: state whether the family_candidates EXRs survive. D7 established that
  597/671 M6 EXRs are permanently unrecoverable, so do not assume. If they are
  gone, say so and re-render only what Step 3 actually needs.

  Re-measure all seven candidate families, plus Attar's BAKED and its control,
  on the axes axes_from() declares — highlight_fwhm_fraction at
  QUARTER_CYLINDER, GRAZING, SHALLOW_CURVE and BEVEL, plus
  SPECULAR_TO_DIFFUSE_RATIO and HIGHLIGHT_PEAK.

  Do NOT report peak-over-median as a discriminator. palette_characterization_
  rig.py:269-274 retired it from five of six axes for not discriminating. If
  you report it at all, report it as context and say that the instrument
  retired it.

  GRAZING is mandatory. It is the region powder_materials.py:4-28 names for
  the bump-microstructure families and 61ddd75's re-measure skipped it.

  Keep chroma spread for MARBLED. It is albedo-derived, chroma is the right
  axis, and PLANAR is a legitimate place to read it.

STEP 3 — RE-ADJUDICATE WHAT THE CENSUS CLEARED AND WHAT IT DIDN'T

  Say plainly, family by family, whether the new measurement changes the
  verdict 7d985bb reached. In particular:

    - BAKED. 61ddd75 said it reads in the gloss direction at Attar's value on
      a retired scalar. Does it read on the declared axes? Yes or no.
    - PRESSED_POWDER. It scored BELOW the matte control on planar luminance
      (1.1779 vs 1.2400 p99/median). That is Old Rose, pan 9. Does its
      compaction ring read on GRAZING?

  If either does not read, say so plainly. That would mean a pan is making a
  promise the builder does not keep, and the owner needs it before choosing
  anything else. Do not tune to make it read. Do not reclassify any pan —
  that is the owner's decision and this step only supplies the evidence.

STEP 4 — HOW WIDE DOES THIS GO

  Two verdicts in this arc were reached on a measure that could not see what
  it was judging. Sweep for others: any recorded verdict resting on a
  PLANAR-only reading of a family whose declared distinction is geometric or
  specular, or on peak-over-median after the §6 repair retired it. State your
  search extent.

  Then judge the class. The coefficient defect and this one share a root — a
  repair landed and later analysis used the pre-repair form — but the
  coefficient form was stated in FILES and this one was not stated anywhere.
  A file sweep could never have caught it. If that is a different defect,
  open it. If it is D9's, extend D9. Do not open two entries for one hole,
  and do not fold two holes into one entry to avoid opening a second.

STEP 5 — DOES ANY OF THIS TOUCH MOSS GARDEN

  Moss Garden is MARBLED, which is albedo-derived, and its 9.8×-over-control
  figure is a chroma measurement on the flat region. My reading is that this
  is legitimate and the figure stands untouched by Findings 2 and 3. Confirm
  or refute in no more than four sentences. If it stands, say so, because the
  owner has a decision waiting on it.

DO NOT
  - choose a typeface, a lid layout, or Moss Garden's family
  - reclassify any pan's family
  - edit the frozen builder
  - renumber milestones, move work between them, or recompute percentages
  - delete a withdrawn blocker rather than withdrawing it
  - tune any material to make a family read
  - close D5

REPORT BACK
  - whether OWNER_BLOCKER_SESSION.md:66 reads as I said it does
  - what Step 1(c) decided and why — withdrawn, or reworded
  - the standing-blocker count and list
  - whether the EXRs survived
  - the re-measured table on the declared axes, with GRAZING present
  - BAKED yes/no and PRESSED_POWDER yes/no, plainly
  - Step 4's extent, and whether D9 was extended or a new defect opened
  - Moss Garden in four sentences
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

**A blocker board you can trust.** Two of the three you were told about last
commit are settled or mis-stated; what survives should be only the things that
genuinely need you.

**An honest answer on Old Rose.** Pan 9 was cleared by a measurement that
could not see a compaction ring. If PRESSED reads on GRAZING, nothing changes
and you have lost nothing. If it does not, you would rather know now than
after the artwork is drawn around twelve pans.

**And Moss Garden, still waiting.** My recommendation has not moved and none
of this touches it: keep MARBLED, drop "antique-gold" from the note, and let
the pan be restrained olive-on-olive marbling. That is what the engine can
honestly deliver and what the measurement says it does deliver at 9.8× the
matte control. It is your call and it is the last thing standing between you
and M7's artwork.
