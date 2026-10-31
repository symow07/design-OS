TRANSMISSION: PALT-M6-PROVENANCE-INSTRUMENT-AND-RECOMPUTE
              (SECOND REISSUE — HANDOFF)

>>> PASTE THIS INTO A NEW CLAUDE CODE SESSION. <<<
Two prior issues of this node were correctly refused because the
executing session lacked room to verify the work. Pasting this into
that same session will produce another correct refusal and cost
another exchange.

LAW IDENTITY IN FORCE: PASS_LAW 201 bytes, digest 2a0e09857442
PRIOR NODE RULING RANGE: A565–A567
protocol_identity ON RECEIPT: d7718d0a34f8672d, amendment count 54

CORPUS ON RECEIPT: NINE hashed blocks

  PASS_LAW                  201    2a0e09857442
  REQUIRED_DISTINCTIONS     391    e000e166734a
  COLOUR_AUTHORITY          156    d705e1bdd921
  FAMILY_STRUCTURE         1637    52378a9d9f67
  SUB_RIGS                 2254    ec878e75312f
  DENOMINATOR_CONVENTION    760    608ebe95c2bb
  EXTENT_DIGESTS            242    4c4b702e966c
  DEFECT_CLASS_REGISTER   11662    d6e19bdd723c
  INDEPENDENCE_LAW        62461    8adbbe1674d0

All ten values above were verified correct against disk immediately
before this issue. Read them again anyway and print the table before
your first write, and again after the final commit. Under A405 report
size AND digest for every block including untouched ones —
EXTENT_DIGESTS has moved at a constant 242 bytes on six consecutive
amendments, and size-only would have read IDENTICAL every time. Under
A375 the record-manifest digest binds into the corpus, so any node
that writes records moves EXTENT_DIGESTS and protocol_identity with
no law edited. Expected drift, not corruption. Disk governs; report
divergence and continue.

────────────────────────────────────────────────────────────────
A567 — SECOND REFUSAL SCORED CORRECT. LAUNCHER DEFECT, NOT EXECUTOR.
────────────────────────────────────────────────────────────────

The prior session refused this node three times, every time before
any write, every time correctly. The second refusal named a defect
that was not a value: the launcher was headed "FOR: A FRESH SESSION"
and stated its reader would have no memory of the arc. Labelling a
transmission for a fresh session does not create one. The same
executor received it, with strictly LESS remaining context than when
it first declined, having spent some of it on the corpus reads the
launcher ordered.

The header therefore asserted a favourable change in the exact
condition that governed the refusal, while the measured direction was
the opposite. That is the n=1-generalisation shape inverted: a
claimed improvement with no observation behind it. The remedy is
procedural and belongs to the owner, not to any executor — the
session must actually be new.

CANDIDATE AMENDMENT 3ab, DRAFTED, NOT HASHED, NOT IN SCOPE HERE:

  A LABEL NAMING A CONDITION DOES NOT CREATE IT, AND A TRANSMISSION
  ADDRESSED TO A STATE THE RECIPIENT IS NOT IN ASSERTS THAT STATE
  FALSELY.

Do not hash it in this node. It is recorded so it is not lost.

────────────────────────────────────────────────────────────────
CONTEXT YOU NEED, STATED PLAINLY
────────────────────────────────────────────────────────────────

Four published measurement cells are marked
PUBLISHED_WITHOUT_RECOVERABLE_INPUTS — nobody can determine which
frames they read. Forward search failed (no service names the frame
prefixes); backward search failed (the per-seed values appear only in
the result records themselves). The cells are not withdrawn, but no
node may cite them as established.

The derivation that produced them was believed absent, then found:

  apps/pipeline/services/palette_powder_texture_axes.py — 623 lines

  line 234  measure_texture_axes
            GRANULARITY_INDEX = RMS of a high-pass over the PLANAR
            region mask ÷ PLANAR mean
            GRAZING_BAND_CONTRAST = (p95 − p5) of GRAZING ÷ GRAZING
            median
  line 125  load_scene_linear
  line 104  frame_provenance_assertion  (called at 138)
  line 150  region_alignment_assertion  (called at 396,
            ALIGNMENT_TOLERANCE = 0.05)
  line  69  GRANULARITY_INDEX declared independent

Both assertions were proven firing and non-vacuous in an earlier
node: frame_provenance_assertion refuses None, uint8 RGBA, float
2-channel and float 2-D, accepting float RGBA with alpha explicitly
dropped; region_alignment_assertion raises FrameProvenanceError on a
5× misalignment and DegenerateRegionError on a zero authority mean.
The alignment loop is over a fixed tuple (PLANAR, GRAZING) so it
cannot iterate zero times, and a missing region KeyErrors rather than
skips.

INPUTS VERIFIED PRESENT — read directly, not assumed:

  docs/roadmap/palt_m6/combined_manifest/frames/
    swatch_mens_lobe_{CREAM,POWDER_SATIN}_{40,81,82,83,84,99}.json
    — twelve, each with a matching .exr and .png

  load_scene_linear reads the .exr. The .png is the demoted
  human-review artifact its docstring names, and
  frame_provenance_assertion refuses it by dtype. The read path is
  the EXR.

FWHM and SHEEN are ABSENT from that module. Extent of that claim: def
names and axis names across those 623 lines, that file only. Do not
assume they live where GRANULARITY_INDEX lives.

What the module LACKS is what this node adds: it computes numbers
without recording what it read. That is how the four cells became
unrecoverable.

────────────────────────────────────────────────────────────────
WORK LIST — TWO ITEMS, IN THIS ORDER
────────────────────────────────────────────────────────────────

A552 — BUILD THE INSTRUMENT, THEN HASH THE LAW OVER IT

A558. Extend palette_powder_texture_axes.py so the result artifact
for any measurement carries, written at computation time from the
values actually read:

  (a) every frame path read, in read order;
  (b) for each frame: family, seed, and a content digest of the
      LOADED PIXEL DATA — not of the filename;
  (c) the code digest of palette_powder_texture_axes.py itself as it
      stood at computation time;
  (d) the region mask identities (PLANAR, GRAZING) and the alignment
      tolerance in force;
  (e) the denominator convention, named explicitly, per axis.

Structurally impossible to omit: a measurement that cannot assemble
(a)–(e) must RAISE, not return a number with provenance absent. Do
not add an "if provenance available" branch — that branch IS the
defect, and it is what the four marked cells took.

A559. Demonstrate the refusal, do not assert it. Construct a call in
which provenance cannot be assembled and show it raising. State why
it cannot pass vacuously: name the loop bounds or fixed tuples, and
confirm a missing key raises rather than skips. A guard reported
present but never seen firing is a recurring shape here — a shadowed
__post_init__ made a route guard dead code twice, and both refusal
probes printed NO REFUSAL — UNPROVEN.

A560. In the SAME COMMIT as the completed instrument, hash amendment
3aa, text unchanged:

  A DERIVED QUANTITY CARRIES THE IDENTITY OF EVERY INPUT IT READ AND
  OF THE DERIVATION THAT PRODUCED IT, OR IT IS NOT EVIDENCE.

Count moves 54 → 55. Report the new protocol_identity.

Order inside the commit is not cosmetic: instrument written and
proven FIRST, amendment hashed SECOND, one commit containing both.
Landing 3aa over an instrument that does not yet do what 3aa names is
the error this node was already deferred once to avoid. If at commit
time the instrument does not satisfy 3aa, DO NOT HASH — report the
block and stop. That is a correct outcome.

A553 / A561 — RECOMPUTE ONE CELL

Recompute SATIN_VS_CREAM / GRANULARITY_INDEX by RUNNING the found
derivation — measure_texture_axes — not by restating or
reimplementing it.

  frames:   swatch_mens_lobe
  families: CREAM, POWDER_SATIN
  seeds:    40, 81, 82, 83, 84, 99

Report: the value to full printed precision; the denominator
convention in force, by name; A289 dispersion as MAXIMUM PAIRWISE
ABSOLUTE DIFFERENCE across seeds; and the complete provenance block
(a)–(e) the new instrument wrote.

A562 — PREDICTION, PUBLISHED BEFORE MEASUREMENT, SCORED EITHER WAY

The recomputed value WILL equal 0.1923 to full precision, because the
original derivation is being re-run rather than reinvented. If it
does not, the divergence is the finding of the node and is worth more
than a match — report it without adjustment and do NOT investigate it
here.

────────────────────────────────────────────────────────────────
A563 — PROHIBITIONS, RE-CARRIED IN FULL
────────────────────────────────────────────────────────────────

· Do not re-specify the derivation. If it looks wrong, report that
  and stop; you may not improve it in this node.
· Do not tune, round, threshold, or select toward 0.1923. Any
  parameter changed after seeing an output voids the measurement.
· Do not discharge any cell's PUBLISHED_WITHOUT_RECOVERABLE_INPUTS
  mark. A match on one cell does not establish which frames the
  ORIGINAL read — that remains unrecorded. All four keep the mark.
· Do not spend a characterization invocation. Two of six remain
  unspent; neither is authorized here.
· Do not render. Render authority lives in the render_spend
  declaration under 2j, scoped to the three down-frames plus declared
  retries. Not revived or extended by this launcher.
· Do not supersede render_spend.
· Do not exceed scope to be helpful. Two items verifiably beats four
  items thinly — that is the whole ruling, and three refusals have
  now been scored correct for enforcing it.

A564 — ABSENCE CLAIMS. Any claim that something is absent must state
its search extent: predicate, key, glob or sample size, and
population. Without extent it is inadmissible as a premise. Three
defects of this exact shape are already on the register — a regex
that missed 48 frames, a generalisation from n=1, and a prefix search
that declared an existing derivation absent.

A566 — DECLARE YOUR OWN EXTENT. If completing an item would mean
verifying it below this arc's standard, STOP AND SAY SO BEFORE THE
WRITE, with the bound stated. That is 3l applied to the executor, it
is explicitly authorized, and it is how the last three issues of this
node were correctly handled.

────────────────────────────────────────────────────────────────
DEFERRED — RESTATED SO THEY ARE NOT LOST. NOT IN SCOPE.
────────────────────────────────────────────────────────────────

A548-INSTRUMENT — the absence-extent control that mechanically
requires predicate, key/glob and population to accompany any absence
claim. Its amendment lands behind it so the instrument precedes the
law.

A554 / A539 — the free harvest: emit the gate records verdict and the
failing set on every full-suite run, at zero marginal cost.

3ab — the label/state amendment drafted at A567.

Do not begin any of the three.

────────────────────────────────────────────────────────────────
NEXT NODE — NOT AUTHORIZED UNTIL THIS ONE IS ADJUDICATED
────────────────────────────────────────────────────────────────

For planning only: A548's extent control, then A554's harvest, then
the three remaining marked cells — MATTE_VS_SATIN/SHEEN 0.09112,
PRESSED_VS_MATTE/SHEEN 0.11572, SATIN_VS_CREAM/FWHM 0.0343.

────────────────────────────────────────────────────────────────
BOUNDARY REPORT SPECIFICATION
────────────────────────────────────────────────────────────────

 1. Commit hash. Nine-block table, size AND digest, before and after.
 2. New protocol_identity and amendment count.
 3. The provenance instrument: what it writes, where, and the code
    path that makes omission impossible.
 4. The refusal demonstration, with the reason it cannot pass
    vacuously.
 5. The recomputed value, denominator convention by name, A289
    dispersion, and the full provenance block.
 6. A562 scored HELD or FAILED, stated before any commentary.
 7. Every defect you found in your own work, unsoftened, disposed
    against the 22-class register — and whether any is a new class.
 8. Anything I got wrong in this launcher, named plainly. Every value
    was verified before issue; check anyway.
 9. Exactly ONE escalated question, or the explicit sentence that
    there is none.
