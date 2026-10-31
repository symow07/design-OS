# Geometry Decisions — Locked Structural Rules

This file records every structural decision in the STE dieline engine
with the physical reason behind it. **Read this before changing any
geometry.** Every locked decision exists because a real cutting
machine, folding step, or print-shop convention demands it. Changing a
locked value without understanding the reason will produce an
unprintable dieline.

When you add a new locked decision, follow the existing entry format
exactly and bump the next free `DECISION-NNN` number.

---

## [DECISION-001] Fold lines body-only, not full height
Date: 2026-05-18
Status: LOCKED
Problem: fold lines extending through flap regions would crack flaps
on first fold.
Decision: vertical fold lines span body height only
(y = tuck_h to y = tuck_h + height_mm).
Reason: crease lines through dust flaps cause material failure on
real cutting equipment.
Do not change unless: moving to corrugated stock which requires a
different crease strategy.

## [DECISION-002] Round joins on bleed buffer
Date: 2026-05-18
Status: LOCKED
Problem: mitre joins produced 26 mm spikes at dust-tuck notch
junctions.
Decision: Shapely `buffer(..., join_style=1)` (round).
Reason: smooth bleed matches industry convention, never tighter than
3 mm anywhere on cut path.
Do not change unless: printer explicitly requests mitre joins in
their spec sheet.

## [DECISION-003] Two tuck flaps only
Date: 2026-05-18
Status: LOCKED
Problem: four tuck flaps create the wrong STE layout for the approved
reference; the far-right top flap must be a short dust flap, not a
tall tuck.
Decision: one rounded top tuck on the back panel and one rounded
bottom tuck on the front panel. Both use `width_mm × 1.227`.
Reason: matches the approved Pacdora-style reference layout.
Do not change unless: changing to reverse tuck end template (a
different template entirely).

## [DECISION-004] Dust flap height less than tuck
Date: 2026-05-18
Status: LOCKED
Problem: equal-height dust and tuck flaps cannot fold in sequence —
dust must fold before tuck.
Decision: `dust_flap_height = depth × 0.631`.
Reason: measured from the approved reference; dust flaps are visibly
shorter than tuck flaps.
Do not change unless: board thickness changes significantly
(> 0.5 mm stock).

## [DECISION-005] Lip-gloss tuck guard lowered to 12 mm
Date: 2026-05-18
Status: LOCKED
Problem: spec said tuck ≥ 15 mm but 15×15×90 produces tuck = 13.5 mm.
Decision: minimum tuck guard = 12 mm.
Reason: 12 mm is the physical minimum for a working friction lock on
slim cosmetic cartons.
Do not change unless: product line moves to width/depth < 14 mm.

## [DECISION-006] Cut lines blue, crease lines red
Date: 2026-05-18
Status: LOCKED
Decision: `cut = #0000FF`, `crease = #FF0000`, `bleed = #00FF00`,
`safe = #00FF00`.
Reason: industry-standard print colour conventions.
Do not change: this is non-negotiable for print-shop compatibility.

## [DECISION-010] Friction slit is stadium-shaped
Date: 2026-05-18
Status: LOCKED
Problem: rectangular slit corners are stress concentration points —
the slit tears from the corners after a few open/close cycles.
Decision: slit ends are semicircular, radius = 0.75 mm (slit total
height = 1.5 mm).
Reason: distributes stress evenly around the slit perimeter —
industry standard for friction-lock slots.
Do not change unless: moving to laser cutting (corners are fine with
laser, problematic only with steel-rule dies).

## [DECISION-011] Dust flap taper is 60° not 45°
Date: 2026-05-18
Status: SUPERSEDED by DECISION-016 — the dust flap is now the measured
6-vertex shape (3 mm base notch + 6 mm top chamfer), not a tapered trapezoid.
Problem: 45° chamfer produces a wide flat top on the dust flap that
catches on the tuck during closing.
Decision: 60° taper — `chamfer = dust_flap_height × tan(30°) ≈
height × 0.577`. Cap at `(base_width / 2) − 1` to keep a 2 mm
minimum top width.
Reason: steeper taper guides the tuck flap smoothly over the dust
flap on closing. Industry standard for slim cosmetic cartons.
Do not change unless: depth > 40 mm where a shallower taper is
needed for structural strength.

## [DECISION-012] Stadium slits on tuck flaps
Date: 2026-05-18
Status: LOCKED
Problem: rectangular slit corners tear under repeated open/close
cycles.
Decision: one stadium slit on the top back tuck and one stadium slit
on the bottom front tuck. Model each as a polygon-difference hole.
Reason: rounded slit ends distribute stress and match the reference
geometry.
Do not change unless: printer explicitly requires straight cuts.

## [DECISION-008] Horizontal crease lines start at glue tab edge, not x=0
Date: 2026-05-18
Status: LOCKED
Problem: crease lines under the glue tab create a false fold score on
the tab itself.
Decision: horizontal creases start at `x = glue_tab_mm`.
Reason: the glue tab has no fold — it is glued flat. A crease line
through it weakens the adhesion area.
Do not change unless: switching to a scored glue-tab design
(non-standard).

## [DECISION-009] Safe area excludes glue tab
Date: 2026-05-18
Status: LOCKED
Problem: safe area extending into the glue tab misleads the designer
— the glue tab gets no artwork.
Decision: safe area `x_start = glue_tab_mm + safe_margin_mm`.
Reason: the glue tab is always covered by adhesive and folded behind
— artwork in this zone is wasted and can interfere with gluing.
Do not change.

## [DECISION-007] `top_flap_mm` / `bottom_flap_mm` removed from input schema
Date: 2026-05-18
Status: LOCKED
Problem: user-supplied flap heights caused incorrect geometry — the
engine must control these.
Decision: engine derives all flap heights from `depth × ratio`, not
from user input.
Reason: flap proportions are structural — a wrong value produces an
unfoldable carton.
Do not change unless: adding a custom flap override as an
advanced/expert mode with hard validation.

## [DECISION-014] Shoulder radius = min(W × 0.20, 6 mm); tuck inset 2 mm
Date: 2026-05-19
Status: SUPERSEDED by DECISION-016 — tuck shoulders are now the measured
cubic-bezier form (inset = W × 0.227, curve_h = W × 0.218), not a radius/inset pair.
Problem: W × 0.35 with 3 mm inset produced too-deep an arch — narrow
and tall — that does not match industry-standard cosmetic carton
proportions.
Decision: shoulder_r = min(W × 0.20, 6 mm); tuck inset = 2 mm (fixed)
on both front and back tuck flaps. The arc spans only the top edge of
the trapezoid; if W − 2·inset < 2·shoulder_r the two arcs meet at the
centre with zero flat top, otherwise a flat segment of width
W − 2·inset − 2·shoulder_r remains between them.
Reason: matches Pacdora reference — a wide, gentle shoulder funnels
the flap into the friction slit while the trapezoid sides clear the
dust flap on fold-down.
Do not change unless: switching to a product family where the
reference shoulder factor is different (e.g. perfume sleeve).

## [DECISION-015] Shoulder lock cuts at tuck base
Date: 2026-05-19
Status: LOCKED
Problem: tuck flap corners catch on board thickness when folding,
causing crease damage at the shoulder.
Decision: shoulder lock cuts apply only to the two active tuck flaps
(top back and bottom front). Notch size = board_thickness × 2 when
notches are present.
Reason: standard die-cut feature on all cosmetic straight-tuck
cartons — without these the tuck tears the shoulder on first fold.
Do not change unless: board_thickness changes, then notch =
board_thickness × 2.

## [DECISION-016] Tuck + dust geometry from measured AI file
Date: 2026-05-19
Status: LOCKED
Source: SLIMMING_CREAM_R-108-A.ai — professional Illustrator dieline,
measured directly from the PDF path data.
Tuck flaps (top back and bottom front):
  total_h = W × 1.227
  inset   = W × 0.227   (each side, from base to top edge)
  curve_h = W × 0.218   (vertical span of the shoulder arc)
  Shoulders are cubic beziers with a vertical tangent at the curve
  start and a horizontal tangent at the flat top (the v / y PDF
  operators in the source file).
Dust flap (6-vertex shape, side panels):
  height        = D × 0.631
  base_notch    = 3 mm fixed (step in at each base corner)
  top_chamfer   = 6 mm fixed (each side)
  top_width     = D − 2 × top_chamfer
Reason: these ratios come from a real, printed, approved cosmetic
carton dieline — they are not derived but measured.
Do not change: unless replacing with measurements from a different
approved professional reference file.

## [DECISION-017] Slit web guard; slit-width and shoulder-tangent constants provisional
Date: 2026-07-03
Status: LOCKED (guard) / PROVISIONAL (constants)
Problem: on narrow cartons a friction-slit end sitting too close to the
tuck flap's free side edge leaves a sliver of board that tears through
on first use. Separately, `_SLIT_WIDTH_FACTOR = 0.327` and the shoulder
cubic tangent factor `_TUCK_SHOULDER_K = 0.55228…` (the standard
quarter-ellipse Bezier constant) were never measured from the approved
reference file.
Decision (guard, LOCKED): keep at least 2 mm of solid web between each
slit end and the flap side edge, measured at the slit's own height
(3 mm below the flap tip) along the DECISION-016 shoulder cubic. If the
nominal slit (`max(5 mm, W × 0.327)`) violates the web, shrink the slit
symmetrically — never below 3 mm, the functional minimum for a friction
lock; below that the engine raises `GeometryError` instead of emitting
a non-locking slit. Within the current schema bounds (W ≥ 12 mm) the
guard never actually triggers (web ≈ 3.5 mm at W = 12); it is a
defensive invariant for future template variants.
Decision (constants, PROVISIONAL): Milestone 9.3 attempted to re-derive
both constants from `28x28x120_coordinate_dump.json`, but that dump
predates DECISION-010/012/014/016 — it contains rounded-rectangle tucks
and straight slit lines, none of the curve/slit points needed. The
constants stay provisional until the coordinates listed in
`MEASUREMENT_NEEDED.md` are extracted from SLIMMING_CREAM_R-108-A.ai.
Reason: a slit that tears or fails to lock is a functional product
failure; the guard is geometry-safety, the constants are fidelity.
Do not change the guard unless: the slit moves away from the flap tip
region or the template family changes. Replace the provisional
constants only with values measured from the approved reference file.

## [DECISION-018] Side-seam straight-tuck archetype (own module, STE untouched)
Date: 2026-07-20
Status: LOCKED (layout) / template parameters versioned
Problem: the Skynte Foundation manufacturing reference reads
glue flap | 32 side | 42 main | 32 side | 42 main — the glue seam leads a
SIDE panel. The locked STE engine draws glue | back W | side D | front W |
side D, so its flat can never match the supplied reference regardless of
dimensions.
Decision: a separate parametric archetype in
`apps/dielines/geometry/side_seam.py` with its own coordinate contract
(x1 = G, x2 = x1 + D + t, x3 = x2 + W, x4 = x3 + D + t, x5 = x4 + W + 2t).
ECMA allowances re-expressed for this order: front = W (reference panel),
sides = D + t, back = W + 2t (glue joint), flat +4t total — the same
physical rule as the STE engine. `engine.calculate_dieline` dispatches to it
by template name; `_calculate_carton` is not modified and the STE reference
snapshot stays byte-identical. Template versions are frozen
`SideSeamTuckSpec` instances (skynte_foundation_tuck_carton/1.0); user input
still supplies only the six schema fields + board settings (DECISION-007).
Reason: reproducing the customer's die requires the customer's panel
sequence; guessing with the wrong archetype produced the Gate-2 failure on
task #47.
Do not change unless: a measured Skynte die file replaces the parametric
assumptions — then publish a new template version, never edit 1.0.

## [DECISION-019] Tuck height = D + lip (not W × 1.227) for non-square sections
Date: 2026-07-20
Status: LOCKED (model) / lip value is a versioned template parameter
Problem: DECISION-016's factor (total_h = W × 1.227) was measured on a
square-section 28×28×120 carton where W = D, so it cannot distinguish the
fold-over span from the tuck lip. On a 42 × 32 section it yields a 51.5 mm
tuck whose fold-over portion would be 42 mm deep against a 32 mm opening —
physically wrong.
Decision: in the side-seam archetype, tuck_total_h = D + tuck_lip_mm per
end. The lip is a template parameter (16 mm in
skynte_foundation_tuck_carton/1.0, recorded as an ASSUMPTION because the
customer tables do not state closure depths). The shoulder cubic must fit
inside the lip (guarded).
Reason: the tuck folds across the D-deep opening, then tucks down inside;
only the lip is discretionary.
Do not change unless: replacing with values measured from the customer's
die — via a new template version.

## [DECISION-020] Tuck-base entry slits; per-panel crease segments
Date: 2026-07-20
Status: LOCKED
Problem: (a) the reference die shows short CUT segments at each end of the
tuck-base fold (shoulder-lock entry slits) — the STE engine has no cut/crease
split along a fold; (b) the STE engine draws full-width horizontal creases
x1..x5 at y1/y2, which run a false score along the front panel's top edge
and back panel's bottom edge — those edges are plain cut edges in a tuck
closure.
Decision: the side-seam archetype emits horizontal creases per hinge only
(dust hinges on the side columns, tuck hinges on the main columns), shortens
each tuck-base crease by lock_notch + entry_slit_mm at each end, and
publishes the cut segments in `coords.slit_lines`. Both exporters draw
`slit_lines` on the cut layer/plate. The SVG validator now checks the fold
count against `coords.fold_lines` instead of a hard-coded 6.
Reason: a crease over a cut edge is a die-making error; the entry slits are
what let the tuck shoulder lock behind the panel edge.
Do not change unless: the archetype's closure system changes (then a new
DECISION entry is required).

## [DECISION-021] Generic cartons crease per hinge, never over a cut edge
Date: 2026-07-20
Status: LOCKED (v1.1 onward); v1.0 frozen with the defect for reproduction
Problem: `_calculate_carton` emitted two FULL-WIDTH horizontal creases,
`(x1, y1)-(x5, y1)` and `(x1, y2)-(x5, y2)`, for every generic style. That
single shared construction ignored two facts:
  1. only some columns carry a flap at a given end — the opposite main panel
     has a free CUT edge there (front at y1 and back at y2 on STE; mirrored
     on reverse; front at y1 on auto-bottom);
  2. the DECISION-015 lock notches cut the tuck base's outer `2t` at each
     corner, so a crease through them scores a hole.
Measured conflict at W42×D32×H140, t=0.30: straight tuck 87.00 mm, reverse
tuck 87.00 mm, tuck-top auto-bottom 43.20 mm. A crease scored along a knife
line weakens the cut and can tear the panel off on the folder-gluer — a
manufacturing defect, not a cosmetic one.
Decision: horizontal creases are built per REAL hinge by `_hinge_creases`:
  * the tuck-carrying column creases from `x_l + lock_notch` to
    `x_r - lock_notch`;
  * the two side columns (dust flaps, whose base edge spans the column)
    crease edge to edge;
  * the flapless main panel gets NO crease at that end;
  * the glue tab never creases (DECISION-008);
  * for the auto-lock bottom every body column hinges, so all four crease.
Zero-length segments are dropped, so no duplicate or empty crease can be
emitted. The fix lives in the shared layer — no template-specific
coordinates. Vertical body creases are untouched.
Reason: same principle as DECISION-020 for the side-seam archetype, applied
to the generic engines.
Versioning: v1.0 of all three generic templates stays registered and
buildable (`per_hinge_creases=False`) so a historical job reproduces exactly
what it shipped; it is marked `production_ready=False` and the Gate-2
validator refuses it with `NON_PRODUCTION_TEMPLATE_VERSION`. v1.1 is the
corrected, production-eligible geometry and is what an unpinned caller gets.
Do not change unless: a measured reference die contradicts a hinge span —
then publish a new version, never edit 1.0 or 1.1 in place.

---

## [DECISION-022] Version 1.4: the tuck-end cartons drawn to the trade's written rules (annotation, 2026-10-07)

His second goal of 2026-10-06 (OWNER_BLOCKER_CLEARANCE.md, transcribed at c34a518), item 2: "Do NOT rely on what the
system already believes about dielines. If the existing dieline rules, templates or code are wrong or weaker than the
professional standard, replace them ... List what you changed and why." The decisions above describe versions 1.0–1.3
(`geometry/engine.py`); they stay, unedited, so a historical job draws as it shipped. Version 1.4 of the straight and
the reverse tuck end (`geometry/trade_tuck.py`) is drawn to `TRADE_RULES.md`, researched once and time-boxed
(`research/`), and checked by `geometry/fold_check.py` on every die. For new work it replaces:
DECISION-003 (the opposed tucks are the reverse tuck end, ECMA A20.20.03.01, and now named so; the straight tuck end
hangs both tucks from one panel), DECISION-004 and -016's dust flap (its depth min(B − t, A/2 − 1), never two meeting
across the opening; asymmetric, shouldered toward the panel the tongue enters), DECISION-006 (one die colour scheme in
every file: the CutContour plate's magenta and the Crease plate's cyan), DECISION-010/-012/-017 (no hole in the tongue:
the lock is the slit at the tuck fold, sized with the dust flap's shoulder), DECISION-014/-016's tuck shoulders (the
tongue set back t each side, its corners rounded), DECISION-015 (no square notch at the lid's hinge: a t-wide relief
between flaps), DECISION-019 (the tongue 0.26 × the lid's depth, 8–20 mm, not a 16 mm lip), and the board allowance of
the engine's docstring (sizes read as the inside, every crease at inside + t). The full list with its reasons is
`TRADE_RULES.md` §4.
