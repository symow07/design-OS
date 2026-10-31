# LAUNCHER — D5b, THE COLOUR-SPACE BOUNDARY

Follows commit `6341794`. Two corrections and one costed decision.

---

## WHAT I CHECKED BEFORE WRITING THIS

**The direction of the error is inverted in the committed record.** D5's
Residual 2 says these twelve "render materially darker than chosen." They
render **lighter**, and this is arithmetic rather than opinion.

A scene-linear albedo `L` reaches the display through the sRGB OETF:

```
display(L) = 1.055 · L^(1/2.4) − 0.055     for L > 0.0031308
```

That function is strictly greater than `L` for every `L` in (0, 1). Check it
anywhere: 0.01→0.100, 0.29→0.575, 0.50→0.735, 0.90→0.955. So feeding an
sRGB-encoded value into a linear socket can only ever produce a **lighter,
less saturated** surface than intended. Never darker.

Midnight Bloom, worked through: intended `#4A2E3B`, fed as linear
0.2902 / 0.1804 / 0.2314, arrives on screen at roughly 0.575 / 0.462 / 0.518 —
about **`#93768A`, a pale dusty mauve.** Not a deep plum. Not darker.

**And the damage is not uniform, which is the part that matters commercially.**
The error is negligible at the light end (Petal Veil 0.949 → 0.978, invisible)
and severe at the deep end (Midnight Bloom roughly doubles). The palette's
whole structure is the depth run the owner named — Damascena → Blush Hour →
Old Rose → Thorn. Through this path that run **flattens**: the pale pans land,
the deep pans wash out, and the thing the palette was designed around is the
thing that breaks. Record it that way, because "renders wrong" and "renders
the design intent inside-out" are different findings.

**The stated reason for not fixing it is also wrong, though the refusal was
right.** The report says changing the shader "moves every material_identity in
the programme." It does not: `material_identity()`
(`palette_powder_engine.py:510–516`) digests schema, version, family, seed,
`shade.to_dict()` and params. `blender_scripts/powder_materials.py` is not an
input to it. Editing the shader would move no material identity at all.

The real constraint is a different and better one, and it is recorded at
`docs/roadmap/palt_m6/independence_amendment_phase4.json:76` — that builder is
the **frozen instrument**, and editing it "is M6-CONTRACT-INTEGRITY-REPAIR's
jurisdiction." Every M6 measurement was taken through it. So the refusal
stands; only its justification changes. Good instinct, wrong reason, and the
wrong reason would have made the fix look more expensive than it is.

---

## THE PROMPT

```
GOAL — correct an inverted claim now in a committed record, then measure what
the real fix would cost. Do not perform the fix. Read the whole brief first.

CONTEXT
  docs/roadmap/palt_m6/open_defect_inventory.md      (D5, Residual 2)
  the es3083_shade_authority/1.0 record you wrote at 6341794
  apps/pipeline/services/palette_powder_engine.py    (realize, material_identity)
  blender_scripts/powder_materials.py                (the frozen builder)
  docs/roadmap/palt_m6/independence_amendment_phase4.json:76

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa: a derived quantity carries the identity of its inputs. A564:
no absence claim without its search extent.

STEP 1 — CORRECT THE DIRECTION, AND PROVE IT RATHER THAN ASSERTING IT

  Residual 2 in D5, and the equivalent wording in the shade authority record,
  say these shades render "materially darker than chosen." That is inverted.

  Prove the direction in code, not in prose. Write a test that asserts, over
  the whole 0..1 range:

      srgb_to_linear(x) < x   for all x in (0, 1)

  and therefore that a value passed through unconverted arrives brighter.
  Sample it densely and include the endpoints' behaviour. This is a property
  of the transfer function, so a property test is the honest form.

  Then rewrite Residual 2 in both places to say what is true:

    - the twelve reach a scene-linear consumer as sRGB-encoded values, so
      every pan renders LIGHTER and less saturated than chosen
    - the error is negligible at the light end and severe at the deep end
    - state the consequence in design terms, not only numerical ones: the
      depth run Damascena -> Blush Hour -> Old Rose -> Thorn compresses,
      because its pale members are nearly correct and its deep members are
      not. The palette's own structure is what degrades.
    - give one worked example with its arrival colour, computed not guessed

  While you are in there, correct the stated reason the fix was deferred.
  material_identity() does not digest powder_materials.py, so editing the
  shader would move no material identity. The actual constraint is the frozen
  instrument contract at independence_amendment_phase4.json:76. Cite that.

  If any of the three claims in this step turns out to be wrong when you check
  it, say so and stop. Do not correct a record toward a second wrong thing.

STEP 2 — MEASURE THE BLAST RADIUS. DO NOT PERFORM ANYTHING IN THIS STEP.

  The fix does not belong in the frozen builder. It belongs at the engine
  boundary: realize() emits display_rgb, and realize()'s output is not an
  input to material_identity(), so the correction can be made without touching
  the instrument and without moving a single material identity.

  But it cannot be applied unconditionally. The provisional fixture shades
  were authored as raw 0..1 values that never declared a colour space — see
  es3083_provisional_shade_set(). Transforming those would silently change
  what every M6 measurement means. So the transform has to be conditional on a
  colour space the shade declares, which means PowderShade needs a
  colour_space field, which means shade.to_dict() changes, which DOES move
  every material_identity because to_dict() is digested at line 514.

  That is the actual cost and I want it measured, not estimated. Report:

  a. How many recorded material identities exist across the repository, and
     where. Search records, ledgers, manifests, test pins and roadmap state.
     State your search extent per A564.
  b. Which of those are load-bearing evidence (an M6 measurement whose
     reproducibility depends on the identity) versus incidental pins.
  c. How many tests pin a material identity literal, by file.
  d. Whether the record gate treats a material_identity change as a rebinding
     or as an amendment, and which authorization route it would need.
  e. Whether any alternative exists that keeps material_identity stable AND
     keeps the colour space honest. Argue against your own answer before you
     give it. If the only stable alternative is to leave colour space
     undeclared, say plainly that the stable option is the dishonest one.

  Then state, in one paragraph, what you would recommend and what it costs.
  Recommend; do not act.

STEP 3 — THE STALE HASHED BLOCK, REPORTED NOT TOUCHED

  palette_powder_protocol.py:1764-1768 still declares
  pan_shades: NO_AUTHORITATIVE_SOURCE_NEUTRAL_PLACEHOLDERS_ONLY inside a block
  that feeds protocol_identity(). You were right to flag rather than fix it.

  Report only: the exact replacement text you would write, which identities
  move, which authorization route applies, and whether it can be bundled with
  the Step 2 change into ONE authorized act rather than two. Bundling matters
  — every identity move is a separate reproducibility break, and two breaks
  where one would do is a self-inflicted cost.

DO NOT
  - edit blender_scripts/powder_materials.py
  - edit palette_powder_protocol.py's COLOUR_AUTHORITY block
  - add colour_space to PowderShade or to to_dict()
  - move any material identity
  - close D5

REPORT BACK
  - the property test, and whether it passed first time
  - the corrected Residual 2 wording, verbatim
  - the five answers from Step 2, with search extents
  - the Step 3 replacement text and whether bundling is possible
  - the one-paragraph recommendation and its cost
```

---

## WHAT YOU DECIDE AFTER IT REPORTS

Only one question really comes back to you, and it is a trade, not a
technicality: **declaring colour space honestly costs every recorded material
identity.** Leaving it undeclared costs nothing today and ships a palette whose
deep pans render as pale mauve.

M6 is parked, which is the cheapest this will ever be. It gets more expensive
the moment M6 resumes or M7 renders anything. But it is your call and the
report will price it before you make it.
