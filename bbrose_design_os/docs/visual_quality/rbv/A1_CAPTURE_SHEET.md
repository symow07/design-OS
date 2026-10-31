# A1 CAPTURE SHEET — P1 bottle reference pack

> **STATUS: A1 CLOSED — 2026-08-27, by owner ruling.**
> Photographs shot and filed at the canonical path; all four landmark
> questions answered by the owner in the sitting of 2026-08-27. The
> closure record — including the two rulings the owner *reversed* during
> the sitting — is
> `owner_inputs/2026-08-27/a1_closeout.json`.
>
> This sheet is retained as the brief that was taken to the bench, with
> the owner's answers written in below. It is no longer an open action.

**Owner committed to shooting: Thursday 2026-08-27** (§BC, this sitting).
**Shot 2026-08-27.** 13 frames at
`bbrose_design_os/docs/visual_quality/rbv/captures/` (IMG_3332–IMG_3344).

This one page is everything needed. Take it to the bench with the bottle.
A1 is the single highest-leverage blocking row in the manifest: it unblocks
`quality.rbv1_reference_standard`, and through it
`quality.rbv2_visualization_renderer`, `quality.rbv5_comparison_gate` and
`pc.vqr2b_reconstruction_measurement`.

---

## THE CALIBRATION RULE — verbatim, and it is why the existing 23 photos cannot count

> A rule or scale lying in the **same plane as the surface being measured**, in
> shot, in focus, at the **same distance from the lens** as that surface. A
> ruler beside the bottle rather than in its plane does not calibrate anything.

The 23 photographs already on file are perspective/uncalibrated and can **never**
be promoted to calibrated evidence. This is not a quality judgement about them;
a scale at a different depth from the surface it is measuring encodes an unknown
magnification, and no post-processing recovers it. If in doubt on any single
frame: move the ruler until it is touching, or level with, the surface whose
millimetres you want.

---

## THE FIVE SHOTS

These five and no others. The names match the P1_V4 view keys exactly, so the
comparison gate binds without a rebinding step
(`docs/visual_quality/rbv/review_packages/p1_v4/review_package_manifest.json`).

| # | view key | what is square to the lens | ruler lies in the plane of |
|---|---|---|---|
| 1 | `front` | the front face, bottle upright | the front face |
| 2 | `side` | the side face, rotated 90° from front | the side face |
| 3 | `top` | looking straight down the bottle axis | the closure's top face |
| 4 | `closure_detail` | the closure/collar, filling the frame | the collar face being measured |
| 5 | `three_quarter_diagnostic` | 45° between front and side | the front face (the near one) |

Constant across all five: same lens, same focal length, same lighting, bottle
in the same place. Only the bottle's rotation and the camera height change. If
the phone/camera moves closer for shot 4, that is fine — the ruler moves with it.

For reference, the existing V4 fixture renders the front at **37.36 mm** wide
against a contract extent of **37.4 mm**, at **0.05819 mm/px**. Real photographs
do not have to match that scale; the ruler is what establishes scale.

---

## THE FOUR LANDMARK QUESTIONS — ANSWERED 2026-08-27

Answer each in one line, holding the bottle. These resolve ambiguities in
existing figures — the numbers below are what the record currently believes, and
the question in each case is *what the number is measuring*, not whether it is
right.

1. **66 mm — is that the straight-wall end?**
   i.e. the point where the vertical wall stops being vertical and the shoulder
   curve begins.
   → **YES — `body_height_before_shoulder_begins`. A caliper landmark in its
   own right; it stands.** (Owner ruling 2026-08-27. Note: mid-sitting the
   owner first adopted the photogrammetric 69 mm tangent and RETIRED 66 —
   then **reversed that retirement** on being shown that 66 and 69 are two
   separately named fields in the owner's own caliper submission.)

2. **69 mm — is that the shoulder-curve point?**
   i.e. a defined point on the shoulder curve itself, and if so which one — the
   curve's start, its midpoint, or where it meets the neck.
   → **YES — `shoulder_start_height_from_base`, a SECOND and DISTINCT caliper
   landmark. Both 66 and 69 stand; neither supersedes the other.** The
   photographs corroborate both within their ±3.5 mm bar and separate
   neither — that, and only that, is the photographs' contribution here.

3. **18.11 mm neck height — measured from where to where?**
   The method, not the number: which two surfaces are the tape's two ends on.
   → **Shoulder/neck junction → glass mouth. It is a HEIGHT, confirmed.**
   (Assumption A3 CONFIRMED. Mid-sitting the owner ruled it a diameter
   misfiled in a height field and instructed a stop-and-return if provenance
   showed otherwise; provenance did, the stop condition fired, and the owner
   re-ruled it a height. **Do not record any "neck height 15.6" entry** — the
   collision with `neck_outside_diameter` = 15.6 is exactly the confusion
   being avoided.)

4. **105 mm — is that bulb top to pipette tip?**
   i.e. the full dropper assembly length, closure included, not the bottle.
   → **YES — the overall dropper assembly length, bulb top to pipette tip,
   closure included.** (Assumption A4 CONFIRMED; corroborated at 105.77 mm
   from IMG_3341, next-nearest span 68.47 mm.)

**Side view:** SATISFIED_BY_SYMMETRY — the bottle measured 0.96 % out of
round (axis ratio 0.9904, calibration-free, two independent frames), so a
separate side frame adds nothing the front frame does not already carry.

---

## WHAT THE PHOTOGRAPHS WERE ALLOWED TO BE — owner precision ruling

The paragraph below was the plan. **It was not what happened**, and the
difference is the most important thing on this page:

> ~~They get ingested as **OWNER_MEASURED** — the highest authority class the
> record has — which is the whole point of the ruler being in the plane.~~

**Owner ruling 2026-08-27:** every pixel-derived number is
**DERIVED_INDICATIVE with its error bar, and none is OWNER_MEASURED.** The
**caliper record remains the dimensional authority**; the photographs are
recorded as **corroborating evidence with stated precision**. Comparison
gates must consume the error bars, not false precision.

A residual 4–5 % scale discrepancy between the frames and the caliper record
could not be explained (EXIF stripped) and is closed as
**UNRESOLVED_ACCEPTABLE**, since nothing in the record now depends on a
pixel-derived height.

The closing sentence of the original brief stands, and is what produced the
stop-and-return on Q3:

> Nothing in this pack may be recorded as measured if it was estimated, and a
> photograph whose calibration is uncertain is worth more as an honest
> UNMEASURED than as a MEASURED number nobody can defend later.
