# LAUNCHER — D5d, RENDER THE TWELVE

Follows `beb1fe5`. The colour path is now correct and nothing has been put
through it. This is the launcher that produces the first thing you can look at.

---

## ONE DEFECT THE REPORT MISSED

`es3083_owner_shade_set()`'s docstring, `palette_powder_engine.py:796–800`,
still reads:

> *"…so a renderer wants `srgb_to_linear` applied and **this engine does not
> apply it.** That is stated, not silently handled."*

As of `beb1fe5` the engine **does** apply it, in `realize()`, roughly two
hundred lines above. The docstring now states the opposite of what the code
does. It was true when written and the commit that made it false did not
revisit it.

Small, but it is the same class as the thing this whole arc has been about: a
statement of fact that stopped being true and stayed in place because nothing
checked it. Worth fixing in the same breath as the render, not on its own.

## ONE DEBT THAT NEEDS AN ADDRESS

`display_rgb` is retained as a frozen-contract alias, documented in the module,
and the reasoning is right — a rename would `KeyError` nine reads inside a file
that may not be edited. But the debt is recorded *where it is carried*, not
*where it will be paid*. When `M6-CONTRACT-INTEGRITY-REPAIR` eventually
unfreezes that builder, whoever does it needs to find "and delete the alias" in
their own brief, not in a docstring two modules away.

## ONE QUESTION D7 LEFT OPEN THAT IS CHEAPER TO ANSWER THAN TO CARRY

D7 closes with: *"which presumes the specs were recorded alongside the
identities, and that has not been checked."*

That sentence decides what D7 actually is. If the specs were recorded, D7 is a
verifier somebody owes. If they were not, then 1,067 load-bearing identities
are **permanently unverifiable** and the M6 corpus can never be re-derived from
anything — which is a categorically worse finding and one M7 would inherit,
because M7 builds on M6's family rulings.

M6 being parked is a good reason not to build the verifier. It is not a reason
to not know which of those two situations we are in. It is one survey.

---

## AND THEN THE POINT OF ALL OF THIS

Everything since the twelve were decided has been plumbing. The question that
actually matters has not been asked yet: **do these twelve shades look like a
palette worth selling?**

Two specific things the render decides, both of which were argued rather than
seen:

- **Moss Garden.** You called it the potential hero pan, and MARBLED here means
  restrained antique-gold and olive marbling, not bright gold veining. The
  render is where that note either held or did not.
- **Midnight Bloom.** POWDER_METALLIC was chosen over SHIMMER on the argument
  that `#4A2E3B` is too dark for a pearl load to read. That was reasoning. The
  render is the test.

**What the render must NOT do.** It must not render the case. ES3083's geometry
is `DERIVED_BOUNDED_NOT_MEASURED` — a 3D case render would put derived
dimensions on screen looking exactly as authoritative as measured ones, and
that is the tier confusion this programme exists to prevent. Swatches through
the proven rig, composed flat into the 4×3 grid. The composition claims nothing
about geometry; it only puts each shade where it sits so the colour story
reads.

---

## THE PROMPT

```
GOAL — render the owner's twelve shades and compose them so the palette can be
judged as a palette. Three small corrections ride along. If the render cannot
run, say so early and still do the corrections.

CONTEXT
  apps/pipeline/services/palette_powder_engine.py   (es3083_owner_shade_set)
  apps/pipeline/services/blender_scripts/material_characterization.py
  apps/pipeline/services/palette_powder_rigs.py
  docs/roadmap/palt_m6/swatches                     (prior art — read it first)
  SHADE_AUTHORITY_PROPOSAL.md                       (roles, notes, the backbone)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — RENDER THE TWELVE

  Render one swatch per owner shade through the EXISTING characterization rig,
  the same instrument the nine families were proven on. Do not build a new
  rig, do not tune lighting per shade, and do not adjust anything to make a
  shade look better. A swatch that disappoints is a result.

  Same rig, same lighting, same exposure, same camera for all twelve. If any
  parameter has to vary, that variance is a finding — record it rather than
  absorbing it.

  Seeds come from es3083_owner_shade_set() (seed = pan). Do not reseed to get
  a nicer flake pattern; that would make the picture unreproducible from the
  record.

  Read docs/roadmap/palt_m6/swatches BEFORE writing any render code. Nine
  families already rendered there in the dielectric window with zero clipping.
  Reuse that path. If it does not generalize to twelve shades, say why.

  Confirm before rendering that the values reaching the shader are the
  transformed ones — shader_input_rgb, not authored_rgb. Print the triple for
  Midnight Bloom and check it against 0.068480/0.027323/0.043745. If it is
  0.2902/0.1804/0.2314 the fix is not on this path and everything below is
  worthless; stop and report.

STEP 2 — COMPOSE, HONESTLY

  Produce ONE image the owner can look at: the twelve swatches in the 4x3 grid
  in their recorded positions, R1C1 top-left to R3C4 bottom-right, each
  labelled with its name and hex.

  This is a FLAT COMPOSITION, not a case render. Do not model, render or imply
  the palette case. ES3083 geometry is DERIVED_BOUNDED_NOT_MEASURED and a 3D
  case would present derived dimensions as if they were measured. The grid is
  layout, not geometry, and the image's caption must say so in one line.

  Produce a SECOND image: each chosen hex as a flat chip beside its rendered
  swatch, same order. This is the one that answers the question the owner
  actually has — what the finish does to the colour they chose. A flat
  #48583F and a MARBLED pan of it are not the same object.

  Do not colour-manage these two images differently from each other, and state
  what view transform they were written through. An image that proves a colour
  fix must not itself be ambiguous about colour.

STEP 3 — SAY WHAT YOU SEE, AS EVIDENCE NOT OPINION

  Measure, from the rendered swatches:
    - the realized spread of the depth run Damascena -> Blush Hour -> Old Rose
      -> Thorn, against the 0.4288 intended spread from D5. Does the run hold
      now that the transform is applied?
    - Moss Garden: is the marbling restrained antique-gold and olive, or is it
      bright gold veining? Give a measurement that distinguishes those, not an
      impression.
    - Midnight Bloom: does POWDER_METALLIC read at that depth? The argument
      for it was that a pearl load would vanish into its own base. Measure
      whether the metallic load is distinguishable from the base.
    - any shade that lost its identity — two pans that no longer read as
      different pans is a commercial defect regardless of what the engine says

  Report these as numbers with the method stated. You are not the judge of
  whether the palette is good; you are the instrument. The owner judges.

STEP 4 — THE STALE DOCSTRING

  palette_powder_engine.py:796-800, inside es3083_owner_shade_set(), still
  says the engine does not apply srgb_to_linear. As of beb1fe5 it does, in
  realize(). Correct it to describe what the code now does and cite realize().

  Then sweep for siblings: any other docstring, comment or record written
  before beb1fe5 that asserts the transform is not applied, or that
  display_rgb carries sRGB. State your search extent.

STEP 5 — GIVE THE ALIAS DEBT AN ADDRESS

  The display_rgb frozen-contract alias is documented where it is carried, not
  where it will be paid. Add it to the M6-CONTRACT-INTEGRITY-REPAIR record —
  wherever that jurisdiction is actually tracked; find it, do not invent a
  location — as an explicit item: when the builder unfreezes, powder_materials
  reads shader_input_rgb and the alias is deleted.

  If no such record exists to write into, say so with your search extent
  rather than creating one.

STEP 6 — ANSWER D7'S OPEN QUESTION. DO NOT BUILD THE VERIFIER.

  D7 says closing it "presumes the specs were recorded alongside the
  identities, and that has not been checked." Check it, because the answer
  decides what D7 is:

    - if the specs were recorded, D7 is a verifier somebody owes
    - if they were not, 1,067 load-bearing identities are PERMANENTLY
      unverifiable, the M6 corpus cannot be re-derived from anything, and M7
      inherits family rulings that can never be checked

  Sample the measurement frame directories: for a recorded material_identity,
  is the spec that produced it recorded beside it, completely enough to
  recompute the identity? Try recomputing on a sample and report the hit rate.
  State your search extent and your sample size.

  Update D7 with the answer. Do not build the verifier and do not schedule it.

DO NOT
  - build a new rig or tune any rig parameter per shade
  - reseed for a better-looking result
  - render, model or imply the palette case
  - edit the frozen builder
  - build the D7 verifier
  - close D5 — the owner closes it by looking at the image

REPORT BACK
  - the two images, by path
  - Midnight Bloom's shader triple as printed, before rendering
  - the four measurements from Step 3
  - what the docstring sweep found, with extent
  - where the alias debt was filed
  - D7's answer, with sample size and hit rate
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

An image, and four numbers. The numbers tell you whether the depth run
survived the fix. The image tells you whether the palette is any good, which is
the only question that was ever load-bearing and the first time in this
programme you can answer it by looking.

D5 closes when you say the image is right — not when the tests pass.
