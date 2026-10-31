# LAUNCHER — D5g, WHAT M7 IS

Follows `7d985bb`. An owner ruling, a scope correction, and two small repairs
that ride along. No rendering, no new instrument, no design decision.

---

## THE RULING

**Asked and answered 2026-08-13. M7's artwork is BBROSE original.**

M7 puts BBROSE's own lid design, brand lettering and twelve shade names onto
ES3083 geometry. It does not reproduce the vendor's lid artwork. The outlined
type in `materials/historical AI production designs/ES3083吸塑 展盒刀线.ai` was
only ever the vendor's mockup of their own case.

Three things in the record already pointed this way and none of them was
consulted before the blocker was raised: PALT-P3 is specified as *"New original
outer silhouette · not copied from any existing brand · presentable to
customers"*; the programme's stated objective is a client-approvable BBROSE
design; and VQ2 resolved the identical question for the bottle by approving a
substitute face rather than recovering the vendor's.

**Consequence:** `ES3083_TYPEFACE_UNIDENTIFIED` is withdrawn. What remains is
the owner choosing a typeface for their own artwork, which is a design decision
and not an evidence gap. It does not gate M7 and it is not a blocker.

That is the second of the four standing blockers to fall by checking a premise
rather than by doing work. Worth noticing as a pattern.

---

## THE DRIFT, WHICH IS THE MORE USEFUL FINDING

`7d985bb` reported that the two records defining M7 "disagree." They do not
disagree. One drifted, and the drift is diagnostic.

The founding plan, `docs/roadmap/palt_m1/palette_roadmap.md:39–45`:

| | founding definition | gate |
|---|---|---|
| **PALT-M4** | powder material engine via GME-M1 + finish-differentiation board | owner accepts finishes side by side |
| **PALT-M6** | artwork + shade system + `.AI` export + PNG preview | artwork authority review |
| **PALT-M7** | PALT-P2 and PALT-P3 pilots | strict owner visual review |

The tracker, recomputed 2026-08-05:

- id `palettes.palt_m6_artwork_shades`, title *"PALT-M6 — powder & eyeshadow
  material engine…"* — **the id still carries M6's founding meaning while the
  title describes M4's content.**
- id `palettes.palt_m7_pilots_p2_p3`, title *"PALT-M7 — ES3083 artwork + shade
  labels + editable .AI (Illustrator 2026); then PALT-P2 / PALT-P3"* — M6's
  founding deliverable has moved in front of M7's own.

So M6 was captured by the powder material engine, and the artwork-and-`.AI`
deliverable that M6 owed slid into M7. The id never changed, so nothing flagged
it, and no control compares a milestone's title to its id or to the founding
plan.

**This is the mechanical explanation for something the owner has been
complaining about for weeks.** M6 has felt self-extending because it has been
executing M4's mandate while its own deliverable waits one milestone ahead.
That is not a work-rate problem and it is not anyone's fault; it is a scope
boundary that moved and was never written down.

The owner has ruled that this gets recorded, not just noted.

---

## TWO REPAIRS RIDING ALONG

**The stale coefficient constant.** `palette_marbling_rig.py:72–76` declares
`DERIVED_COEFFICIENTS` as *"component colours derived by x0.55 (darker) and
x1.35+0.05 (lighter) — undeclared builder coefficients, the source of every
chroma number below."* The live builder **rejects that form outright** —
`_derived_components` raises unless `form == PER_CHANNEL_ASYMMETRIC_CHROMATIC`.
Both this launcher's predecessor and `0e4ef34`'s analysis were misled by it.
Two documents in two days. It should not survive to mislead a third.

**Attar.** `7d985bb` measured BAKED as indistinguishable from its base at Moss
Garden's depth. Attar is BAKED, at `#C9916B` — far lighter, scene-linear peak
around 0.58. The finding almost certainly does not transfer, but "almost
certainly" is how the last four defects were introduced. It is one render at a
value we already have a rig for.

---

## THE PROMPT

```
GOAL — record an owner ruling, withdraw a blocker it resolves, correct a scope
drift, and fix two things that misled previous acts. No rendering except one
check. No design decisions. No new instruments.

OWNER RULING — GRANTED AND RECORDED 2026-08-13. M7's artwork deliverable is
BBROSE ORIGINAL artwork on ES3083 geometry, not reproduction of the vendor's
lid artwork. Recorded by PROJECT_OWNER in response to the question raised at
7d985bb Step 4(a).

CONTEXT
  docs/roadmap/palt_m1/palette_roadmap.md:39-45   (the founding milestone table)
  docs/roadmap/palt_m1/palette_first_three_pilots.md
  docs/roadmap/progress_tracker.json              (the drifted titles)
  docs/roadmap/palt_m4c/palette_roadmap_continuation_state.json
  docs/roadmap/palt_m6/open_defect_inventory.md
  apps/pipeline/services/palette_marbling_rig.py:72-76
  apps/pipeline/services/blender_scripts/powder_materials.py  (FROZEN, read only)
  docs/visual_quality/vq2/                        (the Imbue scope line)

STANDING LAW — unchanged. Declare before you realize. An honest FAIL beats a
moved bar. 3aa. A564.

STEP 1 — RECORD THE RULING

  Write the ruling where owner decisions of this kind are actually recorded —
  FIND that location, do not invent one, and if more than one candidate exists
  say which you chose and why. supplier_outreach_deferral.json is a worked
  example of the shape: a decided_by PROJECT_OWNER record with a date and a
  scope.

  The record must carry:
    - the ruling: M7's artwork deliverable is BBROSE-original artwork on
      ES3083 geometry
    - what it explicitly does NOT cover: it does not choose a typeface, it
      does not settle lid layout, and it makes no claim about ES3083 geometry
      authority, which remains DERIVED_BOUNDED_NOT_MEASURED
    - what it resolves: ES3083_TYPEFACE_UNIDENTIFIED
    - the question it answers, quoted from 7d985bb Step 4(a)

  BEFORE writing it, check one thing that could contradict it: the M4C-4 panel
  the owner confirmed on 2026-08-12. Read what that confirmation actually
  committed to. If it committed the owner to anything about vendor artwork
  fidelity, STOP and report the conflict rather than recording a ruling that
  contradicts a confirmation the owner already gave. State the extent of that
  check either way.

STEP 2 — WITHDRAW THE BLOCKER

  Withdraw ES3083_TYPEFACE_UNIDENTIFIED from
  palette_roadmap_continuation_state.json, citing the ruling.

  Withdraw it, do not delete it. The entry should remain legible as a thing
  that was raised and resolved, with its predecessor chain intact —
  MATERIALS_LIBRARY_ABSENT (false) -> ES3083_TYPEFACE_UNIDENTIFIED
  (conditional) -> WITHDRAWN (condition resolved by owner ruling). That chain
  is the most useful thing in the entry and it should survive.

  Then state the current standing-blocker count and list what remains, so the
  owner can see the board rather than infer it.

STEP 3 — CORRECT THE M6/M7 DRIFT

  progress_tracker.json carries id palettes.palt_m6_artwork_shades under the
  title "PALT-M6 — powder & eyeshadow material engine…", which is M4's content
  per palette_roadmap.md:42. And palt_m7_pilots_p2_p3 now leads with the
  artwork + .AI deliverable that palette_roadmap.md:44 assigns to M6.

  Correct the record so it states what is true. Specifically:

    a. make M6's title agree with its id and with what M6 has actually been
       doing, or make the id agree with the title — decide which, and say why.
       Do not leave an id and a title describing different milestones.
    b. make M7's two-part deliverable explicit and ordered: ES3083 artwork +
       shade labels + editable .AI FIRST, then PALT-P2 and PALT-P3.
    c. record the drift itself as a note in the tracker — when the boundary
       moved, what moved across it, and that the id was not updated. A
       corrected record that hides having been wrong is worth less than one
       that shows its own history.

  READ THE AUTHORIZATION ROUTE FOR progress_tracker.json BEFORE EDITING IT.
  You established at 7d985bb that continuation_state.json needs none; do not
  assume that generalises. If this file needs owner authorization, STOP and
  report the exact text you would land.

  Do NOT renumber milestones, do not move work between them, and do not
  recompute any percentage. This is a labelling correction. The work that has
  been done is the work that has been done.

STEP 4 — WHY NOTHING CAUGHT IT

  A milestone id and its title described different milestones for months. In
  no more than three sentences: what control would have caught that, and does
  anything in the programme compare a milestone record against the founding
  plan?

  You opened D9 at 7d985bb for the same shape of gap — a blocker whose premise
  nothing re-evaluated. If this is the same defect, say so and extend D9
  rather than opening a second entry. Two defects describing one hole is
  worse than one.

STEP 5 — THE STALE COEFFICIENT CONSTANT

  palette_marbling_rig.py:72-76 declares DERIVED_COEFFICIENTS as x0.55 and
  x1.35+0.05, describing itself as "the source of every chroma number below."
  The live builder rejects that form: _derived_components raises unless
  form == PER_CHANNEL_ASYMMETRIC_CHROMATIC, and the live derivation is
  per-channel x[0.45,0.55,0.70] / x[1.45,1.30,1.15]+[0.08,0.05,0.02] with
  components: 2 meaning the additive offsets never enter.

  Correct the constant to describe the live derivation, cite where the live
  form is enforced, and note that the previous text was accurate pre-repair
  so the correction reads as a supersession rather than an error.

  Then sweep for siblings: any other constant, docstring or record that
  states the pre-repair coefficient form. State your search extent. This is
  the second stale-statement sweep in this arc; if the two sweeps together
  suggest a class of defect rather than two incidents, say so.

  Do not edit the frozen builder. This is the rig's own constant, not the
  builder's.

STEP 6 — CHECK ATTAR, BECAUSE THE LAST FOUR DEFECTS CAME FROM "ALMOST CERTAINLY"

  7d985bb measured BAKED as indistinguishable from its base at Moss Garden's
  depth (chroma spread 0.001272 against a 0.001547 control). Attar is BAKED,
  at #C9916B — scene-linear peak around 0.58, far lighter.

  Render Attar in BAKED at its authored colour and seed, with a POWDER_MATTE
  control at the same colour and seed, same rig and same settings as the
  7d985bb candidate set. Report whether BAKED's crust reads at Attar's
  lightness, using the same measures you used there so the two are comparable.

  If it does not read, say so plainly — that would mean a second pan is making
  a promise the builder does not keep at its own value, and the owner needs
  that before choosing anything else. Do not tune to make it read.

DO NOT
  - choose a typeface, a lid layout, or Moss Garden's family
  - edit the frozen builder
  - renumber milestones or move work between them
  - recompute progress percentages
  - delete the withdrawn blocker rather than withdrawing it
  - open a second defect for the same hole as D9
  - close D5

REPORT BACK
  - where the ruling was recorded, and what the M4C-4 check found
  - the withdrawn blocker's final wording and the standing-blocker count
  - what you did to progress_tracker.json, or what you would do and why you
    stopped
  - Step 4's three sentences, and whether D9 was extended
  - what the coefficient sweep found, with extent, and whether it is a class
  - Attar's BAKED result against its control
  - anything in this brief that was wrong about the code
```

---

## WHAT COMES BACK TO YOU

**Two standing blockers instead of four**, both of the remaining two being
things only you can do: put calipers on an ES3083 if you hold one, and judge
the palette image. Neither is engineering.

**And a tracker that finally says what M6 was.** The founding plan gave M6
artwork and the `.AI` export. M6 spent months on the powder material engine
instead, which is M4's mandate, and the deliverable you have been waiting for
sat one milestone ahead the whole time. That is worth knowing before you set
any date, because it means M7 is not a fresh milestone — it is the one that
carries the thing this programme was built to produce.

Moss Garden is still open and is next. My recommendation stands: keep MARBLED,
drop "antique-gold" from the note, and let the pan be restrained olive-on-olive
marbling, which is what the engine can honestly deliver and what the
measurement says it does deliver at 9.8× the matte control.
