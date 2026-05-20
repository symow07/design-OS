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
Status: LOCKED
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
Status: LOCKED
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
