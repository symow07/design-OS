# LAUNCHER — D5f, WHAT THE NINE FAMILIES CAN ACTUALLY DELIVER

Follows `0e4ef34`. One act, timeboxed. It exists because MARBLED turned out to
promise something its construction cannot produce, and nobody has asked whether
the other eight do the same.

---

## WHY THIS AND NOT THE MOSS GARDEN DECISION

`0e4ef34` established that MARBLED's components are chroma-identical by
construction: `×0.55` is multiplicative and preserves `R:G:B` exactly, so the
only chroma mover is the `+0.05` additive term, and it moves the wrong way. The
family delivers a **luminance** marble. Restrained antique-gold-and-olive is not
achievable at any lightness, because gold requires a hue the builder never
computes.

The obvious next move is to pick Moss Garden a different family. That move is
premature, and here is the reason.

**Four of the twelve pans are sold on a second visual element.** Dew's pearl,
Attar's antique rose-gold, Copper Leaf's copper, Midnight Bloom's metal. Each
of those is a promise to a customer about something appearing *on top of* the
base colour. MARBLED's promise turned out to be undeliverable by construction,
and that was found only because the owner asked about one pan. Nothing has
checked the other eight families, and moving Moss Garden onto an unchecked one
would be picking blind.

### What the builder's own docstring already says

`blender_scripts/powder_materials.py:4–28` gives the structural spine, and it
is more informative than it looks:

- **MATTE / SATIN / PRESSED** — real bump microstructure, geometry-level
  normals. No second colour is claimed and none is delivered. Honest.
- **SHIMMER / METALLIC** — per-cell Voronoi flake fields, *"every cell is one
  flake with its own facet normal and reflectivity."* Same construction, two
  different censuses.
- **GLITTER** — the same per-cell construction at resolvable particle scale.
- **BAKED** — crust-over-dome, and *"the dome itself is GEOMETRY (built by the
  powder-volume builder, not here); this graph only supplies the vitrified
  crust."*
- **MARBLED** — *"mixes 2-3 derived colour components."* The only family that
  mixes colours, and the one now known to be broken at it.
- **CREAM** — no granular structure at all; its distinction is the absence.

Read that list against the failure and a hypothesis falls out. MARBLED's second
element is **albedo-derived**, so it scales with the base and dies in the dark.
SHIMMER, METALLIC and GLITTER deliver their second element through **facet
normal and reflectivity** — specular, not albedo. A specular highlight does not
scale with base albedo the way a mixed colour does, so those three may survive
at depth precisely where MARBLED fails.

If that is right it is good news and it is the direct answer to Moss Garden. If
it is wrong — if flake colour is also derived from the base by a coefficient —
then Copper Leaf and Midnight Bloom have MARBLED's problem too, and two more
pans are making a promise the builder cannot keep.

Either way the census is cheap: it is a code read, not a render. The MARBLED
defect was found by reading coefficients, not by looking at pictures.

### One source to start from

`docs/roadmap/palt_m6/builder_constant_census.json` already exists and is what
`palette_marbling_rig.py` cites as the origin of the `×0.55 / ×1.35+0.05`
coefficients. It is the right first read, and if it is complete this act is
mostly extraction rather than investigation.

---

## THE TWO QUESTIONS RIDING ALONG

Both can *remove* work, which is why they belong here rather than in a queue.

**Does the `SUBJECT_WINDOW` guard ever fire?** `0e4ef34` noted that the
texture-axis path calibrates energy toward 0.88 before `:661` is reached, and
that `POWDER_METALLIC` — one of the nine *proven* families — renders at 0.1767,
itself below the 0.35 floor. If a proven family sits below the floor and nothing
refused it, then D8 may be a guard that never fires rather than a palette
outside its instrument. I raised that alarm; the evidence partly deflates it and
I would rather that were settled than cited.

**Does M7 need the vendor's typeface at all?** `MATERIALS_LIBRARY_ABSENT` was
correctly re-scoped to `ES3083_TYPEFACE_UNIDENTIFIED`. But the outlined type on
that dieline is the *vendor's* lid mockup, not BBROSE's brand type — and VQ2
already fought this exact battle, searched 4,845 inventoried font files, found
the vendor faces absent, and the owner resolved it by approving Imbue with a
recorded ruling. If M7's requirement is BBROSE's own approved lettering, the
re-scoped blocker may not be a blocker either.

---

## TIMEBOX

This is one act with three answers. It is not a milestone, it does not get a
closure queue, and it does not get a new rig. The failure mode this programme
has demonstrated repeatedly is that a survey becomes an arc. If the census
cannot be completed by reading code, report how far it got and stop — a partial
census with its extent stated is worth more than a complete one that took a
week.

---

## THE PROMPT

```
GOAL — establish what each of the nine powder families can actually deliver as
a second visual element, so the owner can choose Moss Garden's family from
things that demonstrably work rather than from things that are named. Plus two
questions that may remove standing work.

This is a SURVEY AND ONE SMALL RENDER. It is timeboxed to one act. Do not
build a rig, do not open a closure queue, do not schedule follow-on work.

CONTEXT
  apps/pipeline/services/blender_scripts/powder_materials.py  (FROZEN — read
      only; the structural spine is in its docstring at lines 4-28)
  docs/roadmap/palt_m6/builder_constant_census.json           (read FIRST)
  docs/roadmap/palt_m6/marbling_commissioning.json            (the FAIL_diagnosis)
  apps/pipeline/services/palette_powder_engine.py
  apps/pipeline/services/palette_powder_texture_axes.py       (SUBJECT_WINDOW)
  apps/pipeline/services/palette_energy_recovery.py
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json
  docs/visual_quality/vq2/                                    (the Imbue ruling)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — THE FAMILY CAPABILITY CENSUS, FROM CODE

  For each of the nine families, answer four questions. Answer them by reading
  the builder and the constant census, not by rendering.

    a. What is the family's SECOND VISUAL ELEMENT — the thing that appears on
       top of the flat base colour? State "none" where none is claimed;
       MATTE, SATIN, PRESSED and CREAM may honestly have none and saying so
       is a valid answer.

    b. Is that element ALBEDO-DERIVED or SPECULAR/NORMAL-DERIVED? Precisely:
       does it get its appearance from a colour computed off the base, or
       from facet normals and reflectivity that do not read the base colour?
       Cite the lines.

    c. If albedo-derived, WHAT IS THE DERIVATION? Give the coefficients
       exactly as MARBLED's ×0.55 and ×1.35+0.05 were given. Then state
       whether the derivation is multiplicative, additive, or mixed, and
       therefore whether the element's CHROMA separation from the base is
       invariant, growing, or collapsing as the base darkens. MARBLED is the
       worked example: multiplicative term preserves the chroma ratio
       exactly, so the additive term is the only chroma mover.

    d. Does the element survive at Moss Garden's depth — scene-linear base
       around 0.064/0.098/0.049? Answer as a prediction with its reasoning,
       and mark it PREDICTED, not measured. Step 2 tests it.

  Present this as one table plus the reasoning. State your search extent.

  I EXPECT the flake families (SHIMMER, POWDER_METALLIC, GLITTER) to be
  specular-derived and therefore base-independent, and MARBLED to be the only
  albedo-mixing family. TRY TO FALSIFY THAT. If flake colour is also derived
  from the base by a coefficient, say so plainly, because it means Copper Leaf
  and Midnight Bloom carry MARBLED's defect and two more pans are making a
  promise the builder cannot keep.

  BAKED needs care and is the one most likely to be misread. Its docstring
  says the dome is GEOMETRY built by the powder-volume builder and that this
  graph supplies only the vitrified crust. So answer (a) and (b) for BAKED
  across BOTH halves, or say explicitly that one half is out of this file's
  reach and where it lives.

STEP 2 — RENDER ONLY WHAT THE CENSUS SAYS CAN WORK

  Take the families the census predicts CAN deliver a second element at depth.
  Render Moss Garden's exact authored colour (#48583F, transform applied, seed
  = pan 11) in each of them, plus a POWDER_MATTE control at the same colour
  and seed.

  Same rig, same lighting, same exposure, same camera. Do not tune per family.
  If a family needs a parameter the owner shades do not carry, say which and
  use the recorded default rather than inventing one.

  Compose ONE image: the matte control first, then each candidate, labelled
  with family name. Flat composition, no case, same view transform as the
  829c598 pair, stated in the caption.

  Measure, per candidate, whether the second element is distinguishable from
  the base — using a stated method, since 0e4ef34 established the marbling
  axes were superseded and their replacements are unimplemented. Choose an
  honest measure, say why you chose it, and DO NOT present it as certification.
  This is a look-at-it aid for the owner, not a proof. Label it that way.

  If the census says NO family can deliver a chromatic second element at that
  depth, do not render a consolation set. Say so, render nothing, and report
  it — that is a cleaner answer than four pictures of nothing.

STEP 3 — DOES THE SUBJECT_WINDOW GUARD EVER FIRE?

  D8 was opened on my reading that the palette sits outside the rig's window.
  Your own report partly deflates it: the texture-axis path calibrates energy
  toward 0.88 before :661 is read, and POWDER_METALLIC — a PROVEN family —
  renders at 0.1767, below the floor, apparently without being refused.

  Determine whether the guard at palette_powder_texture_axes.py:661 can fire
  on any path actually taken by the pipeline, or whether energy recovery
  normalizes every subject before it is reached. Trace the callers. State the
  extent.

    - if it can fire, D8 stands as written
    - if it cannot, D8 is not what I said it was, and it should be REWRITTEN
      to say what is actually true — either a dead guard, or a guard whose
      real precondition is different from the one I claimed

  Correct D8 either way. Do not close it silently and do not leave my wording
  standing if it is wrong. If my alarm was overstated, the record should say
  so in my words, not soften it.

STEP 4 — IS ES3083_TYPEFACE_UNIDENTIFIED ACTUALLY A BLOCKER?

  You re-scoped MATERIALS_LIBRARY_ABSENT to ES3083_TYPEFACE_UNIDENTIFIED
  because the dieline's type is fully outlined and no record names the face.
  Correct. But the question underneath was never asked: whose typeface does M7
  need?

  The outlined type on that dieline is the VENDOR's lid mockup. VQ2 already
  ran this exact search for the bottle arc — vq2_product_lettering_search.json
  records that MOXA Bestine and MAREGY Regular are absent from all 4,845
  inventoried font files with only embedded subsets present — and the owner
  resolved it by approving Imbue, recorded in vq2_lettering_owner_approval.json
  and vq2_owner_ruling_baked_compression.json.

  Establish, from the recorded M7 requirements and not from judgement:

    a. does M7 require reproducing the vendor's lid artwork, or producing
       BBROSE's own lid artwork on ES3083 geometry?
    b. if the latter, is BBROSE's brand typeface already settled and recorded,
       and where?
    c. does the VQ2 Imbue ruling extend to the palette arc, or is it scoped to
       the bottle?

  Then say whether ES3083_TYPEFACE_UNIDENTIFIED is a real blocker on M7, a
  blocker on something else, or not a blocker. If it is not, withdraw it the
  same way you withdrew its predecessor, with the reason recorded.

  If (a) genuinely cannot be answered from the record, say so with the extent
  and leave the blocker standing. Do not decide the owner's design question
  for them.

DO NOT
  - edit the frozen builder
  - build or re-commission any rig
  - implement C2_CHROMA_HISTOGRAM_L1 or C3_HUE_CIRCULAR_STD
  - change any recorded shade value, hex or family
  - present any Step 2 measurement as certification
  - schedule follow-on work
  - close D5

REPORT BACK
  - the nine-family census table, with the albedo-vs-specular call per family
    and coefficients where they exist
  - whether my flake-families-are-specular expectation survived
  - BAKED's answer across both halves, or where the other half lives
  - the Step 2 image by path, and what the candidates measured
  - whether the SUBJECT_WINDOW guard can fire, and D8's corrected wording
  - the three typeface answers and the blocker's fate
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

**A short list of families that can actually put a second colour on a deep
olive**, and one image of Moss Garden in each. That is what you need to make
the call, and it is a call you can make by looking rather than by argument —
which is the standard this whole arc has been trying to reach.

The worst outcome is that the list is empty, and that is still worth knowing
today. It would mean the deep end of your palette can only ever be flat, that
your hero pan should be `POWDER_MATTE` and honestly labelled, and that "finish
variety at depth" is a capability this engine does not have and has never
claimed to in writing.

**And possibly one fewer blocker again.** If M7 needs your lettering rather
than the vendor's, `ES3083_TYPEFACE_UNIDENTIFIED` withdraws the same way
`MATERIALS_LIBRARY_ABSENT` did — by someone finally checking the premise.
