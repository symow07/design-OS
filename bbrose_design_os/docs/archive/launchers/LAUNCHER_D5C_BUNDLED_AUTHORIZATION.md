# LAUNCHER — D5c, THE BUNDLED AUTHORIZED ACT

Follows `5cb30f3`. Approves recommendation (e), authorizes the hashed
amendment, adds one requirement neither of us wrote down, and opens a new
defect that the blast-radius survey found by accident.

---

## THE APPROVAL, AND WHY

**Recommendation (e) is right and the argument for it is better than the
argument I would have made.** Deriving colour space from authority satisfies
3aa without a new field, because `authority` is already inside `to_dict()` and
therefore already inside the identity chain. Zero identity moves, zero record
rewrites, zero reproducibility breaks — against 671 identities and 1,067
load-bearing frames for the `colour_space`-field design. That is not a close
call, and the self-argument against (e) before recommending it is what makes it
trustworthy.

The coarseness is real and acceptable. Colour space stated per authority rather
than per shade is honest as long as the mapping is total and every admission of
a new authority is forced to decide it — which it is, because
`SHADE_AUTHORITIES` is a declared tuple and the mapping will fail loudly on a
key it does not hold.

**The class 23 hole stands and should be named, not closed.** A caller can
construct an `OWNER_CHOSEN_DESIGN_INTENT` shade from raw non-sRGB values and
the mapping will transform them wrongly. Inside this repository that cannot
happen — `es3083_owner_shade_set()` builds every one through
`hex_to_srgb_triple()`. Record the hole with its reachability stated. Do not
add a validator that guesses whether a triple "looks like" sRGB; there is no
such test and pretending there is would be worse than the hole.

---

## THE ONE THING NEITHER OF US WROTE DOWN

Under (e), the chain that determines what reaches the shader becomes:

```
material_identity  ->  authority  ->  COLOUR_SPACE_BY_AUTHORITY  ->  display_rgb
```

`authority` is digested. `COLOUR_SPACE_BY_AUTHORITY` **is not**. So the mapping
constant is an undigested input to a value that a rendered frame depends on,
and it can be edited without moving any identity and without any gate firing.
That is precisely the shape of defect this programme exists to catch, and (e)
introduces it as a side effect of being cheap.

The fix is small: bind the mapping into the record digest manifest so it cannot
drift silently. Do that in the same act, or (e) trades one honest gap for a
quieter one.

---

## THE NEW DEFECT — FOUND BY THE SURVEY, NOT BY THE TASK

Answer (d) is the most important thing in the last report and it is not about
colour at all. **No mechanical control anywhere compares a computed material
identity to a stored one.** 1,067 load-bearing identities sit in the M6
measurement frames, and nothing verifies a single one. `record_integrity.py`
and `tier2_gate.py` contain zero references; the gate binds record bytes, not
identity agreement.

The consequence, stated plainly: an accidental change to the powder engine
would silently invalidate the entire M6 measured corpus, every test would stay
green, and the gate would stay green. The corpus is labelled with identities
that nothing checks. That is not a colour bug and it is not D5's business — it
gets its own defect entry, opened honestly and left open, because M6 is parked
and inventing a verifier now would be work on a system nobody is currently
extending.

---

## THE PROMPT

```
GOAL — one authorized act landing three things: the colour-space fix by
recommendation (e), the COLOUR_AUTHORITY amendment, and the digest binding
that (e) requires. Plus one new defect opened, not solved.

OWNER AUTHORIZATION — GRANTED for the hashed-amendment route on
palette_powder_protocol.py's COLOUR_AUTHORITY block. Authorization count moves
56 -> 57 as ONE entry covering this whole bundle, not one per file touched.
protocol_identity moves once. The pin at test_characterization_protocol.py:199
is repinned as part of the same act.

CONTEXT — your own report at 5cb30f3, answers (a) through (e) and Step 3.

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — RECOMMENDATION (e), AS YOU SPECIFIED IT

  Add COLOUR_SPACE_BY_AUTHORITY to palette_powder_engine.py, total over
  SHADE_AUTHORITIES:

      PROVISIONAL_VISUALIZATION_SHADE -> the space these were authored in,
          named honestly. They were written as raw 0..1 values that never
          declared a space, so name that state rather than asserting they are
          scene-linear. No transform is applied to them, and the reason is
          that nothing is known about them, not that something is known.
      OWNER_CHOSEN_DESIGN_INTENT      -> sRGB, transform applied

  Use a dict subscript so an admitted-but-unmapped authority raises rather
  than defaulting — same discipline you applied to
  OWNER_COLOUR_AUTHORITY_BY_AUTHORITY at 6341794, and for the same reason.

  Apply the transform in realize() ONLY. Do not touch PowderShade, to_dict(),
  material_identity(), or blender_scripts/powder_materials.py.

  realize()'s emitted field is currently named display_rgb and after this
  change that name is a lie for owner shades — it carries scene-linear values.
  Rename it to what it is, or emit both under honest names. Decide which, and
  say why in the commit. A field whose name contradicts its contents is how
  this defect happened the first time.

  Verify no consumer breaks on the rename. State your search extent.

STEP 2 — BIND THE MAPPING, WHICH THE BRIEF AT 5cb30f3 DID NOT REQUIRE

  Under (e) the chain to a rendered frame is
  material_identity -> authority -> COLOUR_SPACE_BY_AUTHORITY -> shader input.
  authority is digested; the mapping is not. So the mapping is an undigested
  input to a value a frame depends on, editable with no identity move and no
  gate firing.

  Bind it. Put COLOUR_SPACE_BY_AUTHORITY under the record digest manifest so
  it cannot drift silently, in whichever way the existing binding mechanism
  actually supports — read it before choosing, and if binding a module-level
  constant is not something the mechanism can do, say so plainly and propose
  the nearest thing it can do rather than inventing a parallel mechanism.

  If this cannot be done in this act, STOP and report. Do not land (e)
  unbound; an unbound mapping is a quieter version of the bug being fixed.

STEP 3 — THE COLOUR_AUTHORITY AMENDMENT, AS YOU DRAFTED IT

  Land your Step 3 replacement text at palette_powder_protocol.py:1764-1768
  verbatim — it is correct, it scopes to ES3083, it cites the record, and it
  leaves FB3090 and the Pantone tokens exactly where they were.

  Write the authorization entry, move the count 56 -> 57, recompute
  protocol_identity, repin test_characterization_protocol.py:199, regenerate
  the manifest and rebind. One entry for the bundle.

STEP 4 — OPEN THE NEW DEFECT. DO NOT SOLVE IT.

  Your answer (d) found something bigger than the question it was answering:
  no mechanical control compares a computed material identity to a stored one.
  1,067 load-bearing identities in the M6 measurement frames; record_integrity
  and tier2_gate reference none of them; the gate binds record bytes, not
  identity agreement.

  Open a defect in open_defect_inventory.md carrying:
    - the finding, with the search extent from your answer (d) reproduced
    - the consequence: an accidental engine change silently invalidates the
      M6 measured corpus with every test and every gate still green
    - what it is NOT: not a colour bug, not part of D5, not caused by this
      arc — it predates all of this and was found by a survey done for
      another reason
    - status OPEN, and explicitly NOT scheduled, because M6 is parked and a
      verifier for a corpus nobody is extending is work at the wrong time
    - what closing it would require, in one sentence

  Do not build the verifier. Do not scope it. Open it and leave it.

STEP 5 — TESTS

  1. COLOUR_SPACE_BY_AUTHORITY is total over SHADE_AUTHORITIES.
  2. An unmapped authority raises rather than defaulting.
  3. Every es3083_owner_shade_set() row realizes to transformed values, and
     each equals srgb_to_linear of its stored triple, per channel.
  4. Every es3083_provisional_shade_set() row realizes to its stored triple
     UNCHANGED. This is the test that protects the M6 corpus and it is the
     most important one in this act.
  5. Every material_identity in es3083_owner_shade_set() and
     es3083_provisional_shade_set() is unchanged by this commit. Pin the
     twelve provisional values against pre-change values you compute BEFORE
     editing. If any moves, stop — (e)'s entire justification was that none
     would.
  6. Midnight Bloom realizes to 0.068480/0.027323/0.043745 within tolerance.
  7. The class 23 hole is documented in the module docstring and asserted to
     be unreachable from within this repository — every
     OWNER_CHOSEN_DESIGN_INTENT shade constructed anywhere in the tree comes
     through hex_to_srgb_triple. State the search extent in the test.

  Full suite plus the TIER_2 gate. Report both counts.

DO NOT
  - move any material identity
  - edit the frozen builder
  - add a validator that guesses whether a triple "looks like" sRGB
  - build the identity verifier from Step 4
  - close D5 — it stays downgraded until something renders correctly

REPORT BACK
  - what you named the realize() field, and why
  - how the mapping got bound, or why it could not be
  - test 5's result stated explicitly: did any material identity move
  - both counts, and the new protocol_identity
  - the new defect's wording
  - anything in this brief that was wrong about the code
```

---

## WHERE THIS LEAVES THE FOUR BLOCKERS

**#3 colour** — after this act the twelve are recorded, the law agrees with the
record, and the render path is correct. D5 stays *downgraded* until something
actually renders, which is the honest state: the path is fixed but nothing has
been put through it. The first M7 render is what closes it.

**#2 geometry** — unchanged, bounded not measured, still one caliper session.

**#4 `MATERIALS_LIBRARY_ABSENT`** — still vague, still untouched, and now the
cheapest remaining item.

**New:** the unverified material-identity corpus, opened and deliberately
unscheduled.
