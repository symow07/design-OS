"""2C-2E §15 — ACTUAL visual fidelity of the reconstructed dropper bottle
against the human-confirmed geometry and the selected concept.

This measures the EMITTED document — real node geometry and opacities — not
metadata labels. Every axis reports value / target / tolerance / state;
failures use the mandated stable codes and BLOCK the reconstruction gate (a
generic schematic bottle must not pass). Axes whose targets are absent are
UNMEASURED, never silently passed.
"""
from __future__ import annotations

ASPECT_RATIO_FAILED = "CONTAINER_ASPECT_RATIO_FIDELITY_FAILED"
SILHOUETTE_MISMATCH = "CONTAINER_SILHOUETTE_GEOMETRY_MISMATCH"
CAP_GEOMETRY_FAILED = "CONTAINER_CAP_GEOMETRY_FIDELITY_FAILED"
MATERIAL_RELATIONSHIP_FAILED = "CONTAINER_MATERIAL_RELATIONSHIP_FAILED"
TRANSPARENCY_RELATIONSHIP_FAILED = "CONTAINER_TRANSPARENCY_RELATIONSHIP_FAILED"
GENERIC_LABEL_FALLBACK_USED = "CONTAINER_GENERIC_LABEL_FALLBACK_USED"
# 2C-2E-CORR-1 §12 — these MUST fail when a generic block shape is emitted;
# nominal-dimension agreement alone never passes.
CYLINDRICAL_FORM_NOT_PRESERVED = "CONTAINER_CYLINDRICAL_FORM_NOT_PRESERVED"
COLLAR_SCALE_MISMATCH = "CONTAINER_COLLAR_SCALE_MISMATCH"
BULB_PROPORTION_FAILED = "CONTAINER_BULB_PROPORTION_FAILED"
NECK_CONNECTION_FAILED = "CONTAINER_NECK_CONNECTION_FAILED"
GLASS_CURVATURE_FAILED = "CONTAINER_GLASS_CURVATURE_FAILED"
FILL_LEVEL_MISINTERPRETED = "CONTAINER_PRODUCT_FILL_LEVEL_MISINTERPRETED"
TYPOGRAPHY_NOT_PRESERVED = "CONTAINER_SELECTED_TYPOGRAPHY_NOT_PRESERVED"
SHOULDER_GEOMETRY_FAILED = "CONTAINER_SHOULDER_GEOMETRY_FAILED"
NECK_GEOMETRY_MISSING = "CONTAINER_NECK_GEOMETRY_MISSING"
COLLAR_GEOMETRY_FAILED = "CONTAINER_COLLAR_GEOMETRY_FIDELITY_FAILED"
COLLAR_MATERIAL_FAILED = "CONTAINER_COLLAR_MATERIAL_FIDELITY_FAILED"
BULB_GEOMETRY_FAILED = "CONTAINER_BULB_GEOMETRY_FIDELITY_FAILED"
CLOSURE_PROPORTION_FAILED = "CONTAINER_CLOSURE_PROPORTION_FAILED"
FROSTED_GLASS_VIZ_FAILED = "CONTAINER_FROSTED_GLASS_VISUALIZATION_FAILED"
SHEET_PRESENTATION_FAILED = "CONTAINER_CONCEPT_SHEET_PRESENTATION_FAILED"
LOGO_ZONE_MISMATCH = "CONTAINER_LOGO_ZONE_MISMATCH"

SCHEMA = "container_concept_fidelity/1.0"

#: §6 objects that must exist as INDEPENDENT nodes (visualization objects
#: are nonprinting but must still be separate, editable geometry)
REQUIRED_MATERIAL_OBJECTS = (
    "GLASS_OUTER_WALL", "GLASS_INNER_WALL", "FROST_TREATMENT",
    "PRODUCT_FILL_APPEARANCE", "LEFT_EDGE_CURVATURE",
    "RIGHT_EDGE_CURVATURE", "CENTRAL_GLASS_LIGHT", "GLASS_SPECULAR",
    "SHOULDER_REFRACTION", "GLASS_BASE_THICKNESS", "BASE_REFRACTION",
    "COLLAR_ROSE_GOLD_BASE", "COLLAR_ROSE_GOLD_LIGHT",
    "COLLAR_ROSE_GOLD_SPECULAR", "COLLAR_ROSE_GOLD_SHADOW",
    "COLLAR_TOP_RIM", "COLLAR_BOTTOM_RIM", "BULB_DARK_PLUM",
)

#: OWNER RULED 2026-08-27 — ceiling on the logo's share of the front-zone
#: width. Was an inline 0.50. Raised to 0.56 because 0.50 and the 12.0 mm print
#: floor were JOINTLY UNSATISFIABLE on the confirmed 22.0 mm zone. That is how
#: the collision surfaced: implementing §BC(h)'s ruled 0.55 share turned four
#: container-confirmation tests red, and the arithmetic showed that no share
#: value would have satisfied both rules —
#:
#:      print floor needs     share >= 12.0 / 22.0 = 0.5455
#:      this ceiling allowed  share <= 0.50
#:      widest mark permitted 0.50 * 22.0 = 11.0 mm — 1.0 mm SHORT of the floor
#:
#: THE HIERARCHY, RULED EXPLICITLY SO THIS COLLISION DOES NOT SILENTLY RE-ARM.
#: The 12.0 mm print floor (`container_brand_usage.MINIMUM_WIDTH_MM_PRINT`) is
#: a PHYSICAL PRODUCTION constraint and the owner ruled it unwaivable. The
#: 22.0 mm zone is anchored to confirmed real-bottle geometry
#: (`container_contract.py:551`, `round(31.5 * 0.7, 1)`) and the owner ruled it
#: unwidenable. This ceiling is an EDITORIAL preference and yields to both.
#: A later edit that puts this value below MINIMUM_WIDTH_MM_PRINT / zone_width
#: re-creates the empty band; it does not tighten a rule.
#:
#: The owner's rationale in the owner's own terms: 0.50 was a proportional
#: expression of "the product name leads", that intent survives at 0.55, and
#: 0.56 gives the ruled share the same headroom philosophy C10 itself bought by
#: choosing 0.55 over 0.5455.
#:
#: Measured beside that rationale rather than folded into it, because a ratio
#: is not a reading of the page: at 0.55 the mark is 55% of the zone WIDTH. So
#: "the product name leads" is carried by the name's own prominence on the
#: emitted document, not by this ratio. The owner ruled the matching condition
#: at the same time — if a test fails because the name does NOT visually lead
#: the logo ON THE EMITTED DOCUMENT, that is a real defect to report, not a
#: number to adjust.
LOGO_ZONE_SHARE_CEILING = 0.56

#: §BH50(a), OWNER RULED 2026-09-13 — THE FIVE GEOMETRY RULES RE-RULED TO THE CHOSEN DESIGN.
#: 85bf7f7 (2026-07-27) wrote them against the generic composer's rounded-rectangle bottle, one-sided or
#: wide: top/body <= 0.45 (read by the cylindrical-form AND the shoulder rule), 0.18 <= neck/body <= 0.45,
#: 1.3 <= collar w/h <= 2.7 ("w/h about 2.0"), bulb width <= 0.62 x collar and bulb aspect >= 1.25. That
#: origin stays here as history. The owner chose the accepted M3 concept as the product's geometry
#: (§BH49(a)) and ruled each threshold re-derived from the chosen render's measured value, with a band per
#: rule. Each CENTRE below is the rule's own reader, unrounded, on the M3 drawing
#: (`compose_dropper._bottle_group_m3`, docs/visual_quality/vq1_master/master_fit_m3.json): exact ratios of
#: the frozen fit's pixels -- 107.5/172.7; 107.5/172.7 - 0.6/31.5; 217/183; 169/217; 201/169 -- measured on
#: the control hull, whose body width is 345.4 px where the fit records 343.0 px. Between runs they vary by
#: nothing: 217/183 and 201/169 sit a fixed 3.3e-6 off from rounding the profile height, and the retained
#: inputs leave all five bit-identical, so a band's width is a policy choice, not a noise measurement (§T1,
#: OWNER_BLOCKER_CLEARANCE.md:491-518, its clause (d)). Each centre is MEASURED; each width is the executor's
#: PROPOSAL under §BH50(a) -- the fit's own largest contour residual (GLASS 5.1 px, COLLAR 1.25 px,
#: DARK_CLOSURE 1.39 px) carried to the ratio (0.0295, 0.0295, 0.0303, 0.0221, 0.0367) and rounded up to
#: 0.01 -- recorded PROVISIONAL_PENDING_OWNER_CALIBRATION until the owner's line calibrates it (three times
#: the mean residual, 0.006 to 0.027, is the priced alternative). Every band is two-sided, because the one-sided July
#: literals let July's bottle (0.2857, 0.2667, 1.9907, 0.5116, 2.0182) pass; it misses every band by at
#: least 0.23. THREE CAVEATS, stated with the ruling: the bands describe the M3 DRAWING, not the numbers
#: (the same derived numbers drawn by the parametric group read collar w/h 1.0945 and bulb aspect 1.2643,
#: outside two bands); rule 3 measures a NECK_GLASS box the collar covers completely; rule 5's width and
#: aspect are set by the flared skirt where the closure meets the collar, not by the dome. The count and
#: presence legs (curves >= 4, bulb cubics >= 2, SHOULDER_ELLIPSE, COLLAR_TOP_RIM) measure structure, not
#: proportion, and keep their July values. Dimensionless ratios: (centre, half-width).
#:
#: §BH50(f)(8), OWNER RULED 2026-09-13 — "THE (a) RANGES AND THE THREE CAVEATS: propose each — the band per rule
#: from its own nature, the alternative you recommend per caveat, with your reason. The list is the ruling; I veto
#: any line after reading, as with the re-pin list." The list is transcribed in the §BH50(f) register block
#: (OWNER_BLOCKER_CLEARANCE.md, a21e172). Under it the widths below are OWNER_CALIBRATED: the list is the ruling
#: until a line is vetoed, and every line names its fallback — the landed width, which it equals. No landed width
#: tightens and none is widened by the executor. ONE METHOD, stated once: each edge of each extent a ratio reads
#: moves by the larger of the fit's local-normal residual at that edge and the concept's 0.5 px edge quantisation
#: — and, where the extent is a band boundary on the fit's 3 px sample grid, by that grid — the worst case over
#: edges carried to the ratio and rounded up to the 0.01 the record prints. LINE 1, rules 1 and 2 (top/body, one
#: quantity through the shared narrow test): ±0.03 kept — the method gives ±0.025 once the sample-to-sample
#: variation at the glass band's start row is charged (4 px between adjacent samples at rows 664/667), and ±0.02
#: would refuse a drawing of this product that starts the glass at the collar's edge; a caveat, new: this leg reads
#: the glass top INSIDE the collar (row 664, 1.22 sheet mm in, within 0.45 % of the collar's own width), visible
#: only as the silhouette stroke drawn over the opaque collar — kept, since line 7 reads the visible waist.
#: LINE 3, rule 4 (collar w/h, an aspect of one object): ±0.04 kept — its vertical extents are band boundaries on
#: the 3 px grid (COLLAR [492, 676] overlapping DARK [292, 498] and GLASS [664, 1348]), which the residual does
#: not measure; the method gives ±0.015–0.046 by attribution and the landed width sits inside it. LINE 4, rule 5
#: (bulb width over collar): ±0.03 kept — the skirt's width edges carry the adjudicated 1.84 px seam; the method
#: gives 0.0206 and, with the grid, up to 0.03. LINE 5, rule 5 (bulb box aspect): ±0.04 kept, and stated plainly:
#: with the closure's real grid gaps (skirt 496 against band end 498; apex between 292 and 295) the method gives
#: ±0.042–0.057, ABOVE the landed width, and widening would soften a rule that describes the bulb — his line, not
#: an executor move. LINE 2 / LINE 7 (rule 3, the visible waist) and LINE 8 (rule 5's dome) are their own commits.
#: [§BH54(c), OWNER RULED 2026-09-18 — "EVERY BAND TAKES ITS OWN METHOD'S VALUE. Line 5's ±0.04 sits below the
#: 0.042–0.057 its method produces; widen it." WIDENED to ±0.06: the method's worst case over edges is 0.0567191
#: (both vertical extents are band boundaries on the 3 px grid — apex gap 3, skirt gap 2), rounded up to the 0.01
#: the record prints, the round-up kept apart in GEOMETRY_BAND_WIDTH_SOURCES. The sentence above stays as history.]
#: Hard stop 1 governs the centres, as T50 read it (:21262); the widths come from the concept fit's residuals and
#: its grid, not from a reading of the render — said here so he may read the stop otherwise.
GEOMETRY_BANDS_ORIGIN = "§BH50(a) 2026-09-13, on the M3 render; the 2026-07-27 thresholds of 85bf7f7 kept as history"
GEOMETRY_BAND_WIDTH_STATUS = "OWNER_CALIBRATED"   # §BH50(f)(8): the widths, by the list; every centre is MEASURED
GEOMETRY_BAND_PROVENANCE = ("§BH50(f)(8): the list is the ruling until a line is vetoed — OWNER_BLOCKER_CLEARANCE.md, "
                            "the §BH50(f) block (a21e172), lines 1, 3, 4 and 5; widths from the concept fit's "
                            "residuals and its 3 px grid by the one method stated above; centres MEASURED on the "
                            "M3 render"
                            # §BH50(f)(8) line 7, annotated at its own commit (§AZ0(u)): rule 3's band is the
                            # visible waist's, its centre set by the waist reader, its ±0.01 the list's
                            "; line 7: rule 3's waist band, centre set by the waist reader, width ±0.01 by the list"
                            # §BH50(f)(8) line 8, annotated at its own commit (§AZ0(u))
                            "; line 8: rule 5's shaft and slenderness bands, centres set by the dome reader, widths "
                            "±0.01 and ±0.05 by the list"
                            # §BH50(g)(3), re-typed §BH53(a) (OWNER_BLOCKER_CLEARANCE.md :21610-21614), annotated at
                            # its own commit (§AZ0(u)): every line's width source is saved beside its width
                            "; §BH50(g)(3): every band line carries where its width came from — GEOMETRY_BAND_WIDTH_SOURCES, "
                            "saved on each axis as tolerance_source; the waist and shaft ±0.01 DERIVED by the one method "
                            "(measured ±0.00790 and ±0.00696, rounded up to the printed 0.01), not widened")
GEOMETRY_BAND_NOTE = ("§BH50(a): centre MEASURED on the M3 render; width " + GEOMETRY_BAND_WIDTH_STATUS
                      + " (§BH50(f)(8)); the 85bf7f7 threshold of 2026-07-27 kept as history")
#: §BH50(f)(8) line 8: rule 5's axis carries both sources — its width and aspect legs §BH50(a)'s, its shaft and
#: slenderness legs line 8's
DOME_BAND_NOTE = (GEOMETRY_BAND_NOTE + "; shaft and slenderness: §BH50(f)(8) line 8 — centres set by the dome reader "
                  "on the M3 drawing, widths by the list"
                  # §BH50(g)(3): the shaft's width source, said on the record and kept apart from the round-up
                  "; §BH50(g)(3): the shaft's ±0.01 DERIVED — measured ±0.00696 by the list's method, rounded up to the "
                  "printed 0.01; the slenderness ±0.05 a choice inside the method's grid-aware 0.041–0.063 (see "
                  "tolerance_source)")
TOP_TO_BODY_BAND = (0.6224667052692532, 0.03)            # 85bf7f7: top/body <= 0.45 (rules 1 and 2)
#: §BH50(f)(8) LINE 7, OWNER RULED 2026-09-13 — rule 3 reads the VISIBLE WAIST (option B, a reversal of the taken
#: "band the occluded rectangle", :21254): the glass outline's narrowest DRAWN width between the collar box's bottom
#: and the SHOULDER_ELLIPSE box's centre line, over the body's box width (the control-point extent the other legs
#: divide by). The centre is SET BY THE READER (`_visible_waist`) on the M3 sheet composed from the accepted fit at the
#: 31.5 mm anchor — the sheet test_vqr1 composes, whose hero group equals the undeclared (product-path) sheet's, and
#: the product-path test in test_container_confirmation_2c2e.py pins the live path reading the same centre — never a
#: preview constant; the width ±0.01 is the list's, a new quantity's band with no residual-and-grid derivation in
#: the reading, open to his veto like every line. [§BH50(g)(3), re-typed §BH53(a): DERIVED at its own commit — the
#: list's one method on the HEAD fit record gives ±0.00790 (the glass residual 1.0675 px at fit row 679 on the 100.5 px
#: plateau against the 0.5 px quantisation, the body edge 0.5 px, both extents interior, no grid term), which rounds
#: up to the 0.01 the record prints; the width is unchanged and its source is saved — GEOMETRY_BAND_WIDTH_SOURCES.]
#: Reason: the drawing shows 4.47 product mm of glass below the
#: collar narrowing to a waist of 18.46 mm, 0.586 × body — the MINIMAL_GLASS_NECK_TRANSITION the VQ-1 acceptance
#: names — and rule 3 read instead a NECK_GLASS rectangle the opaque collar covers (by 0.0327 sheet mm at the worst
#: row, an occlusion only since f430628): the rectangle's width moved the reading while the glass outline did not
#: (NECK_GLASS narrowed by 1.6 mm inside the collar moved it by 0.0416, to 0.5618 — 0.0116 below its ±0.03 band —
#: unverified as a render, since the rectangle's bottom edge meets the collar's), and a visibly pinched waist of
#: 1.64 mm a side passed it — it did not describe this product. The §BH50(a) box band 0.6034190862216339 ± 0.03 is
#: superseded and kept here as history with the 85bf7f7 threshold; fallback if this line is vetoed: that band (A).
NECK_TO_BODY_BAND = (0.5859757644664311, 0.01)          # waist/body, set by `_visible_waist` on the M3 sheet; 85bf7f7: 0.18 <= neck/body <= 0.45
WAIST_BAND_SECTION = "§BH50(f)(8) line 7"
WAIST_BAND_NOTE = ("§BH50(f)(8) line 7: centre set by the waist reader on the M3 drawing; width ±0.01 by the list, "
                   "OWNER_CALIBRATED; the §BH50(a) box band 0.6034 ± 0.03 kept as history"
                   # §BH50(g)(3): the width's source, said on the record and kept apart from the round-up
                   "; §BH50(g)(3): width DERIVED — measured ±0.00790 by the list's method on the HEAD fit record, rounded "
                   "up to the printed 0.01 (MEASURED_VARIATION; see tolerance_source)")
COLLAR_WIDTH_TO_HEIGHT_BAND = (1.185789055868289, 0.04)  # 85bf7f7: 1.3 <= collar w/h <= 2.7
BULB_WIDTH_TO_COLLAR_BAND = (0.7788018433179724, 0.03)   # 85bf7f7: bulb width <= 0.62 x collar
BULB_ASPECT_BAND = (1.189352416173569, 0.06)             # 85bf7f7: bulb aspect >= 1.25; ±0.04 until §BH54(c)
LINE5_BAND_SECTION = "§BH50(a) centre; width §BH54(c)"
#: §BH50(f)(8) LINE 8, OWNER RULED 2026-09-13 — rule 5 measures the DOME beside the box (option γ, adding to the
#: taken "band the full box"): the SHAFT — the widest DRAWN width of the bulb outline over the middle third of its
#: box height — over the collar's box width, and the SLENDERNESS — the bulb box height over that shaft (both
#: denominators the control-point extents the box legs already use). Centres SET BY THE READER (`_dome`) on the M3
#: sheet, and pinned on the product path in test_container_confirmation_2c2e.py, never a preview constant; widths by
#: the list — ±0.01 for the shaft, with no residual-and-grid derivation in the reading [§BH50(g)(3), re-typed §BH53(a):
#: DERIVED at its own commit — the method gives ±0.00696 (residual 0.0 along the 54.5 px run at fit rows 346–448, so the
#: 0.5 px quantisation on each edge, the collar's edges 0.5 px, interior), rounding up to the printed 0.01; the width
#: unchanged, its source saved in GEOMETRY_BAND_WIDTH_SOURCES], and ±0.05 for the slenderness,
#: where the grid-aware method gives ±0.041–0.063 and ±0.03 would refuse a same-concept drawing whose apex or skirt
#: edge lands one grid step away — each open to his veto like every line. Reason: the rule's code, its target
#: ("domed (curved), never egg/block") and its origin — the 27 July "broad, blunt and paddle-like" finding — describe
#: the closure's slimness, and the box legs are set by the flared skirt where the closure meets the collar: widening
#: the dome and shaft to 1.55× leaves the box readings unchanged and the box-only rule passing. Stated plainly: the
#: shaft leg does not discriminate July (0.5116 against 0.5023, inside by 0.0007); the slenderness leg does (July
#: fails by 0.124, the 1.2× paddle by 0.257). Both box legs and the cubics are kept. Fallback if vetoed: the box only.
SHAFT_TO_COLLAR_BAND = (0.5023041474654419, 0.01)        # shaft width / collar width, set by `_dome` on the M3 sheet
BULB_SLENDERNESS_BAND = (1.8440418195718484, 0.05)       # bulb box height / shaft width, set by `_dome` on the M3 sheet
DOME_BAND_SECTION = "§BH50(f)(8) line 8"
#: §BH50(g)(3), OWNER RULED — typed 2026-09-17, re-typed in OWNER RULING §BH53(a) (OWNER_BLOCKER_CLEARANCE.md
#: :21610-21614): "A BAND WITHOUT A DERIVATION IS NOT EVIDENCE. Every band line carries where its width came from —
#: measured variation, a physical tolerance, or my typed word. The waist and shaft ±0.01 have none: derive or widen
#: them to what measurement supports, and say which." Said here, once per line of the §BH50(f)(8) list, and saved on
#: every axis record as `tolerance_source`. The two he named are DERIVED, not widened: the list's one method on the
#: HEAD fit record (docs/visual_quality/vq1_master/master_fit_m3.json, a407ef38) gives the measured half-width below, and
#: the step up to the 0.01 the record prints is the list's print-precision policy, stated apart — never one measured
#: number. No landed width moves. Line 5 says plainly that its width sits below its own method's range: not supported
#: by its derivation, named for his line, not moved by the executor (a rule that describes the bulb is never softened
#: here). The derivation is reproducible: archive/work/bh53_front_bands_door/g3/derive_bands.py over the §BH50(f) mapping's per-row residual
#: record; its output is quoted in the commit. Classes: MEASURED_VARIATION (his first class — the fit's residual and
#: quantisation by the method), BELOW_METHOD (a width the method does not support); no line here rests on a physical
#: tolerance (the spec pack holds no document, §BH46) or on his typed number (every centre is measured; every width the
#: list's, ratified §BH50(f)(8)). "half" is the dimensionless half-width the tuple carries.
#: [§BH54(c), 2026-09-18: line 5 is WIDENED to its own method's value, so no line sits below its method any more;
#: "BELOW_METHOD … not moved by the executor" above is the history it was. The nineteen inline limits of this module
#: are recomputed under their own methods in INLINE_LIMIT_SOURCES, below this table.]
GEOMETRY_BAND_WIDTH_SOURCES = {
    "TOP_TO_BODY_BAND": {
        "line": "§BH50(f)(8) line 1 (rules 1 and 2, top/body)", "half": TOP_TO_BODY_BAND[1], "class": "MEASURED_VARIATION",
        "decision": "KEPT", "measured_half": 0.025,
        "derivation": "the list's one method: the glass band's start-row sample-to-sample variation (4 px between fit rows "
                      "664 and 667) with the 0.5 px quantisation, carried to the ratio — 0.025, rounded up to the printed 0.03",
        "ruling": "§BH50(f)(8) line 1 (a21e172); the source recorded under §BH50(g)(3), re-typed §BH53(a)"},
    "NECK_TO_BODY_BAND": {
        "line": "§BH50(f)(8) line 7 (rule 3, the visible waist)", "half": NECK_TO_BODY_BAND[1], "class": "MEASURED_VARIATION",
        "decision": "DERIVED", "measured_half": 0.0079, "rounded_to": 0.01, "round_up_share_of_width": 0.21,
        "derivation": "the list's one method on the HEAD fit record: the glass local-normal residual 1.0675 px at fit row 679 "
                      "on the 100.5 px waist plateau against the 0.5 px quantisation, the body edge 0.5 px; both extents interior "
                      "to GLASS [664, 1348], no grid term; carried to the ratio and rounded up to the 0.01 the record prints",
        "cross_check": "the VQ-1 accepted neck local-normal maximum, 0.004073 of the body width on both flanks: 0.0081 — a "
                       "cross-check, not the source (§U forbids carrying a statistic across without its own derivation)",
        "ruling": "§BH50(g)(3), re-typed §BH53(a): derive or widen, and say which — DERIVED, not widened; the width unchanged"},
    "COLLAR_WIDTH_TO_HEIGHT_BAND": {
        "line": "§BH50(f)(8) line 3 (rule 4, collar w/h)", "half": COLLAR_WIDTH_TO_HEIGHT_BAND[1], "class": "MEASURED_VARIATION",
        "decision": "KEPT", "method_range": [0.015, 0.046],
        "derivation": "its vertical extents are band boundaries on the fit's 3 px sample grid (COLLAR [492, 676] against DARK "
                      "[292, 498] and GLASS [664, 1348]); the method gives 0.015–0.046 by attribution, and the landed 0.04 is "
                      "a choice inside that range",
        "ruling": "§BH50(f)(8) line 3 (a21e172); the source recorded under §BH50(g)(3), re-typed §BH53(a)"},
    "BULB_WIDTH_TO_COLLAR_BAND": {
        "line": "§BH50(f)(8) line 4 (rule 5, bulb width over collar)", "half": BULB_WIDTH_TO_COLLAR_BAND[1],
        "class": "MEASURED_VARIATION", "decision": "KEPT", "measured_half": 0.0206, "method_range": [0.0206, 0.03],
        "derivation": "the skirt's width edges carry the adjudicated 1.84 px seam: the method gives 0.0206 and, with the "
                      "grid, up to 0.03 — the landed width",
        "ruling": "§BH50(f)(8) line 4 (a21e172); the source recorded under §BH50(g)(3), re-typed §BH53(a)"},
    "BULB_ASPECT_BAND": {
        "line": "§BH50(f)(8) line 5 (rule 5, bulb box aspect)", "half": BULB_ASPECT_BAND[1],
        "class": "MEASURED_VARIATION", "decision": "WIDENED", "measured_half": 0.0567191, "rounded_to": 0.06,
        "round_up_share_of_width": 0.055, "method_range": [0.04188, 0.05672],
        "derivation": "the list's one method: both vertical extents of the bulb box are DARK band boundaries on the fit's "
                      "3 px grid ([292, 498]; first sample 295, gap 3; last sample 496, gap 2) and the width edges carry "
                      "the adjudicated 1.84 px skirt seam — the worst case over edges is 0.0567191, rounded up to the 0.01 "
                      "the record prints; the residual-over-real-gap case gives 0.04188, the list's 0.042",
        "history": "±0.04 until 2026-09-18 — class BELOW_METHOD, decision KEPT_FOR_HIS_LINE under §BH50(g)(3): the width "
                   "sat below its own method's 0.042–0.057 and was named for his line, which §BH54(c) is",
        "ruling": "§BH54(c): \"Line 5's ±0.04 sits below the 0.042–0.057 its method produces; widen it.\" — widened "
                  "2026-09-18; the source first recorded under §BH50(g)(3), re-typed §BH53(a); centre §BH50(f)(8) line 5"},
    "SHAFT_TO_COLLAR_BAND": {
        "line": "§BH50(f)(8) line 8 (rule 5's dome, the shaft over the collar)", "half": SHAFT_TO_COLLAR_BAND[1],
        "class": "MEASURED_VARIATION", "decision": "DERIVED", "measured_half": 0.00696, "rounded_to": 0.01,
        "round_up_share_of_width": 0.304,
        "derivation": "the list's one method on the HEAD fit record: the dark closure's residual is 0.0 px along the 54.5 px "
                      "run at fit rows 346–448 (the middle third of its box), so the 0.5 px quantisation moves each shaft edge, "
                      "and the collar's width edges move 0.5 px; both interior; carried to the ratio and rounded up to the 0.01 "
                      "the record prints",
        "ruling": "§BH50(g)(3), re-typed §BH53(a): derive or widen, and say which — DERIVED, not widened; the width unchanged"},
    "BULB_SLENDERNESS_BAND": {
        "line": "§BH50(f)(8) line 8 (rule 5's dome, the slenderness)", "half": BULB_SLENDERNESS_BAND[1],
        "class": "MEASURED_VARIATION", "decision": "KEPT", "method_range": [0.041, 0.063], "residual_only_half": 0.0268,
        "derivation": "its extents are grid boundaries: the grid-aware method gives 0.041–0.063 and the landed 0.05 is a choice "
                      "inside that range; the residual-only 0.027 is not applied, since that would tighten, which the list "
                      "forbids",
        "ruling": "§BH50(f)(8) line 8 (ffff333); the source recorded under §BH50(g)(3), re-typed §BH53(a)"},
}
#: §BH54(c), OWNER RULED 2026-09-18 (OWNER_BLOCKER_CLEARANCE.md :21712-21717): "The nineteen inline literals: recompute
#: each under its own method and take the result, recording the measured figure and any round-up apart, as (g)(3) did.
#: A band tighter than the measurement that made it is not evidence. Report the list; do not wait for me." Every one of
#: the nineteen is recomputed here, on the HEAD fit record (docs/visual_quality/vq1_master/master_fit_m3.json) and the M3
#: sheet, the measured figure, the round-up and the class kept apart. NO LITERAL MOVES IN THIS COMMIT, and the reason is
#: said: no method value is WIDER than its literal anywhere; for eight readings (nine literals) it is TIGHTER, and
#: applying a tighter value is the act the list he ratified forbade — "NO landed width tightens and none is widened by
#: the executor" (§BH50(f)(8), :21464) — while his (c) says "take the result": two of his own sentences, so the values
#: are written as `method_value` and applied on his one word. Rounding never tightens: a band or ceiling rounds UP, a
#: floor DOWN, a range outward. `limit_text` is the text the axis prints for the literal (None where it prints none).
#: Carried on the fourteen axes the literals decide as `tolerance_source`; the top-edge window feeds `_top_width`,
#: whose two axes already carry line 1's source. The numbers reproduce from archive/work/bh54_design_loop_slice2/maps/bands.md's scripts.
INLINE_LIMIT_CLASSES = ("MEASURED_VARIATION", "COMPOSER_CONSTANT", "READER_PARAMETER", "EDITORIAL", "OWNER_TYPED")
INLINE_LIMIT_DECISIONS = ("APPLIED", "HELD_AT_ITS_LITERAL", "UNITS_CORRECTED", "QUANTITY_RE_RULED", "SAME",
                          "COMPOSER_VALUE_RECORDED",
                          "READER_PARAMETER_RECORDED", "NO_MEASURED_METHOD", "OWNER_TYPED")
_LIST_METHOD = ("the list's one method (§BH50(f)(8)): each edge moves by the larger of the fit's local-normal residual and "
                "the 0.5 px quantisation, plus the 3 px grid where the extent is a band boundary; worst case over edges, "
                "carried to the ratio")
_NOT_APPLIED = ("his (c) says take the result; the list he ratified says no landed width tightens (§BH50(f)(8), :21464) "
                "— written here, applied on his one word")          # 37ba1bb's words, kept as the history they are
#: §BH54(b), the second block, (m), OWNER RULED 2026-09-19: "THE EIGHT TIGHTENINGS: APPLY, with one check. A band looser
#: than its own method passes what the measurement says it should not, and is no more evidence than a band tighter than
#: it. Before landing, run each tightened band against every render I have seen … if a tightened band would refuse a
#: render I have accepted or am being shown, do not apply that one: report the pair and leave its literal, because a
#: rule that refuses my own chosen design is describing something other than my design. Apply the rest." And his hard
#: stop: "a band applied that refuses a design I have been shown." THE CHECK, read-only, over every stored record of a
#: render he has been shown — July's four, REFIT (shown full-size in the §BH48 report), the PARAMETRIC renders of §BH50,
#: eight M3 records, task 52 as re-rendered, and the 18 exploration records (none turns a geometry knob) — in exact
#: arithmetic, against the rounding this module itself persists (2, 3 or 4 places by axis): a pass whose band edge lies
#: inside that rounding is NOT ESTABLISHED. Every M3 record passes all nine, robustly. FOUR literals are refused by no
#: shown render and are APPLIED. FIVE are HELD_AT_ITS_LITERAL, each with its pairs: three refuse a shown render outright,
#: two cannot be established from the persisted values (REFIT cannot be re-drawn on this tree — the product path draws
#: M3 by construction, §BH49(a) — and the documents themselves were never persisted). WHICH RENDERS COUNT IS HIS TO SAY.
#: His reason names his CHOSEN design: July's he rejected and REFIT he did not choose, so by (m) and its reason they
#: block nothing, every render of the chosen design passes, and all nine would apply. The hard stop's words alone —
#: "a design I have been shown" — read wider, and July's and REFIT are designs he has been shown. The five are HELD on
#: that wider reading because a held band is exactly what it was, so holding loses nothing, where applying against a
#: hard stop cannot be taken back as cheaply. The question is put to him; on his word they apply as one commit.
_APPLIED = ("§BH54(b) (m): applied 2026-09-19 — checked against every stored record of a render he has been shown (July's, "
            "REFIT, PARAMETRIC, M3, task 52 as re-rendered, the explorations): none is refused by it, robustly to the rounding")
_HELD_RULE = ("§BH54(b) (m): NOT applied, on the WIDER of two readings of his words, until he says which — hard stop: \"a "
              "band applied that refuses a design I have been shown\"; (m): \"a render I have accepted or am being shown "
              "… because a rule that refuses my own chosen design is describing something other than my design\". Every "
              "render of the CHOSEN design passes the tightened value; the standing literal passes every pair named "
              "here, none of which is a render he chose. PAIRS: ")
_HELD_BY = {
    "visible_base_thickness": "0.89×–1.07× REFUSES REFIT 0.0712/0.0591 = 1.2047×; July gate2_corr1 0.0605/0.0515 = 1.1748×; "
                              "July gate2_corr2 0.0592/0.0515 = 1.1495×; July final and §BH50 PARAMETRIC 0.0571/0.0496 = 1.1512×",
    "body_squat_floor": "the floor 1.95 REFUSES REFIT, whose body aspect is 1.83",
    "collar_scale_height": "±0.02 REFUSES REFIT, 0.349 against 0.317 — off by 0.032",
    "body_silhouette_proportion": "±3 % is NOT ESTABLISHED on REFIT, 1.83 against 1.88: 2.66 % as persisted, up to 3.2 % "
                                  "within the two-place rounding",
    "bulb_to_collar_proportion": "±9 % is NOT ESTABLISHED on July final and §BH50 PARAMETRIC, 2.06 against 2.26: 8.85 % as "
                                 "persisted, 8.43–9.27 % within the two-place rounding",
}
INLINE_LIMIT_SOURCES = {
    "bottle_aspect_ratio": {
        "limit": 0.02, "limit_text": "±2%", "was": 0.12, "kind": "BAND_RELATIVE", "class": "MEASURED_VARIATION",
        # the band is centred on the confirmed target, which the drawing sits 0.28 % off, so the limit takes the offset
        # PLUS the half-width — recorded below since 37ba1bb, its numbers untouched — and not the half-width alone
        "limit_takes": "offset_plus_half_rounded",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "bottle_aspect_ratio",
        "measured_m3": {"emitted": 3.0486, "target": 3.0573, "offset_rel": -0.0028},
        "method": _LIST_METHOD,
        "method_value": {"measured": 0.0086, "rounded": 0.01, "half_rel_residual": 0.0062, "half_rel_grid": 0.0086,
                         "offset_plus_half_rel_grid": 0.0114, "offset_plus_half_rounded": 0.02},
        "decision": "APPLIED", "why": _APPLIED, "recorded_under": "§BH54(c) (37ba1bb)",
        "ruling": "§BH54(b) (m)"},
    "body_silhouette_proportion": {
        "limit": 0.12, "limit_text": "±12%", "kind": "BAND_RELATIVE", "class": "MEASURED_VARIATION",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "body_silhouette_proportion",
        "measured_m3": {"emitted": 1.9803, "target": 1.9456, "offset_rel": 0.0179},
        "method": _LIST_METHOD + "; the centre carries a DEFINITIONAL offset — the box counts 12 px of glass hidden "
                  "inside the collar — so a band on the confirmed centre is the offset plus the half-width",
        "method_value": {"measured": 0.0298, "rounded": 0.03, "half_rel_residual": 0.0044, "half_rel_grid": 0.0119,
                         "offset_rel": 0.0179, "offset_plus_half_rel_grid": 0.0298},
        "decision": "HELD_AT_ITS_LITERAL", "why": _HELD_RULE + _HELD_BY["body_silhouette_proportion"],
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (m)"},
    "body_squat_floor": {
        "limit": 1.4, "limit_text": "<1.4", "kind": "FLOOR", "class": "MEASURED_VARIATION",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "body_squat_floor",
        "measured_m3": {"emitted": 1.9803},
        "method": _LIST_METHOD + "; a floor is the emitted value less the half-width",
        "method_value": {"floor_residual": 1.9717, "floor_grid": 1.9571, "rounded": 1.95},
        "decision": "HELD_AT_ITS_LITERAL", "why": _HELD_RULE + _HELD_BY["body_squat_floor"],
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (m)"},
    "visible_base_thickness": {
        "limit": [0.4, 2.5], "limit_text": "0.4×–2.5×", "kind": "RANGE_FACTOR", "class": "MEASURED_VARIATION",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "visible_base_thickness",
        "measured_m3": {"base_rel": 0.0561, "target_rel": 0.0571, "factor": 0.9824},
        "method": _LIST_METHOD,
        "method_value": {"range_residual": [0.9682, 0.9967], "range_grid": [0.8978, 1.0686], "rounded": [0.89, 1.07]},
        "decision": "HELD_AT_ITS_LITERAL", "why": _HELD_RULE + _HELD_BY["visible_base_thickness"],
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (m)"},
    "bulb_to_collar_proportion": {
        "limit": 0.30, "limit_text": "±30%", "kind": "BAND_RELATIVE", "class": "MEASURED_VARIATION",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "bulb_to_collar_proportion",
        "measured_m3": {"emitted": 1.0984, "target": 1.1195, "offset_rel": -0.0189},
        "method": _LIST_METHOD + "; both box heights end on band boundaries, so the grid term is the larger",
        "method_value": {"measured": 0.0825, "rounded": 0.09, "half_rel_residual": 0.0327, "half_rel_grid": 0.0635,
                         "offset_rel": -0.0189, "offset_plus_half_rel_grid": 0.0825},
        "decision": "HELD_AT_ITS_LITERAL", "why": _HELD_RULE + _HELD_BY["bulb_to_collar_proportion"],
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (m)"},
    "collar_diameter_rel_body": {
        "limit": 0.01, "limit_text": "±0.01", "was": 0.15, "kind": "BAND_ABSOLUTE", "class": "MEASURED_VARIATION",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "collar_width_over_body_width",
        "measured_m3": {"emitted": 0.62826, "target": 0.62825, "offset": 0.0},
        "method": _LIST_METHOD + "; the same reading as collar_scale_width, decided twice in this module",
        "method_value": {"measured": 0.0047, "rounded": 0.01},
        "decision": "APPLIED", "why": _APPLIED, "recorded_under": "§BH54(c) (37ba1bb)",
        "ruling": "§BH54(b) (m)"},
    "glass_wall_opacity_ceiling": {
        "limit": 0.55, "limit_text": "wall ≤0.55", "kind": "CEILING", "class": "COMPOSER_CONSTANT",
        "origin": "478d54e (2026-07-27, 2C-2E)", "reading": "glass_wall_opacity",
        "measured_m3": {"emitted": 0.5},
        "method": "the composer's own clamp, min(translucency + 0.15, 0.55) (compose_dropper.py): 0.50 at the retained "
                  "translucency 0.35, never above 0.55",
        "method_value": {"composer_maximum": 0.55},
        "decision": "SAME", "why": "the reader's ceiling is the composer's clamp", "ruling": "§BH54(c)"},
    "product_fill_opacity_range": {
        "limit": [0.15, 0.80], "limit_text": "fill 0.15–0.80", "kind": "RANGE", "class": "COMPOSER_CONSTANT",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "product_fill_opacity",
        "measured_m3": {"drawn_stops": [0.24, 0.48, 0.58], "read": 0.58},
        "method": "the composer's own gradient stops — constants, not a measured variation",
        "method_value": {"composer_range": [0.24, 0.58]},
        "decision": "COMPOSER_VALUE_RECORDED",
        "why": "the reader's range is a design range (translucent, never flat) around a composer constant; taking the "
               "constant would make the reader a pin of the composer — recorded, his word if he wants it taken",
        "ruling": "§BH54(c)"},
    "frost_opacity_ceiling": {
        "limit": 0.60, "limit_text": "frost <0.60", "kind": "CEILING", "class": "COMPOSER_CONSTANT",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "frost_opacity",
        "measured_m3": {"emitted": 0.144},
        "method": "the composer's own formula, 0.06 + 0.12 × frost_intensity, over frost 0–1",
        "method_value": {"composer_range": [0.06, 0.18]},
        "decision": "COMPOSER_VALUE_RECORDED",
        "why": "as the fill: a design ceiling over a composer formula — recorded, not taken",
        "ruling": "§BH54(c)"},
    "label_rect_opacity_floor": {
        "limit": 0.85, "limit_text": None, "kind": "READER_PARAMETER", "class": "READER_PARAMETER",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "generic_label_fallback",
        "measured_m3": {"rects_under_front_or_decoration": 0},
        "method": "none on record: the opacity at which a rectangle behind the front type reads as a label; the M3 "
                  "sheet draws no such rectangle, so nothing measures it",
        "method_value": None,
        "decision": "READER_PARAMETER_RECORDED", "why": "a reader's parameter, not a band", "ruling": "§BH54(c)"},
    "front_print_share_ceiling": {
        "limit": 0.60, "limit_text": "≤0.60", "kind": "CEILING", "class": "EDITORIAL",
        "quantity": "the PRINT — the composer's own front placements, scale-free, the records the contract's coverage "
                    "cap reads — as a share of the glass wall box",
        "was_quantity": "the front ZONE's clip box — the area he permits, not the print — as a share of the same box",
        "origin": "2a92be8 (2026-07-27, 2C-2E)", "reading": "front_print_share_of_body",
        "measured_m3": {"harness_zone_22x42.3": 0.4736, "task52_zone_22x40": 0.4478, "bh54f_zone_27.6x40": 0.5618,
                        "zone_width_mm_reaching_0.60_at_h40": 29.47, "july_zone_22x40_of_july_body": 0.39,
                        "task52_print_of_zone": 0.35, "task52_print_of_glass": 0.197, "task52_placements": 5},
        "method": "none on record for the NUMBER: an editorial ceiling — frosted glass must stay visible around the "
                  "typography. The QUANTITY is the rule's own name: print, not zone",
        "method_value": None,
        "decision": "QUANTITY_RE_RULED",
        "why": "§BH54(b) (p): it protects nothing about printing — that is the zone record's max_artwork_coverage, "
               "enforced per placement (DECORATION_COVERAGE_EXCEEDED) — and its 0.60 was July's headroom over the ZONE, "
               "which his own widening of the front (§BH54(f)) took from 0.45 to 0.56 without a mark added. Re-ruled to "
               "measure the PRINT, which its name and note are about; on the chosen design the print is 0.197 of the glass. "
               "SAID PLAINLY: 0.60 of print is a loose ceiling — three times his design. A tighter one is a number for "
               "his eye; none is typed here",
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (p)"},
    "top_edge_window_mm": {
        "limit": 1.5, "limit_text": None, "kind": "READER_PARAMETER", "class": "READER_PARAMETER",
        "origin": "85bf7f7 (2026-07-27, 2C-2E)", "reading": "top_width_window",
        "measured_m3": {"end_point_dy_mm": [0.0, 1.3352, 2.6703], "reading_invariant_over_windows_mm": [0.0, 3.0]},
        "method": "none needed: the top-width reading is the same for every window from 0 to 3.0 mm on the M3 outline",
        "method_value": None,
        "decision": "READER_PARAMETER_RECORDED",
        "why": "feeds `_top_width`, whose two axes (cylindrical_form, shoulder_geometry) carry line 1's source",
        "ruling": "§BH54(c)"},
    "collar_scale_width": {
        "limit": 0.01, "limit_text": "±0.01", "was": 0.06, "kind": "BAND_ABSOLUTE", "class": "MEASURED_VARIATION",
        "origin": "d650e94 (2026-07-27, 2C-2E-CORR)", "reading": "collar_width_over_body_width",
        "measured_m3": {"emitted": 0.62826, "target": 0.62825, "offset": 0.0},
        "method": _LIST_METHOD + "; the same reading as collar_diameter_rel_body, decided twice in this module",
        "method_value": {"measured": 0.0047, "rounded": 0.01},
        "decision": "APPLIED", "why": _APPLIED, "recorded_under": "§BH54(c) (37ba1bb)",
        "ruling": "§BH54(b) (m)"},
    "collar_scale_height": {
        "limit": 0.05, "limit_text": "±0.05", "kind": "BAND_ABSOLUTE", "class": "MEASURED_VARIATION",
        "origin": "d650e94 (2026-07-27, 2C-2E-CORR)", "reading": "collar_height_over_body_height",
        "measured_m3": {"emitted": 0.26754, "target": 0.27382, "offset": -0.0063},
        "method": _LIST_METHOD + "; the same DEFINITIONAL 12 px offset as the body silhouette",
        "method_value": {"measured": 0.0175, "rounded": 0.02, "half_residual": 0.0026, "half_grid": 0.0112,
                         "offset": -0.0063, "offset_plus_half_grid": 0.0175},
        "decision": "HELD_AT_ITS_LITERAL", "why": _HELD_RULE + _HELD_BY["collar_scale_height"],
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (m)"},
    "bulb_width_vs_collar": {
        "limit": 0.03, "limit_text": "±0.03", "was": 0.06, "kind": "BAND_ABSOLUTE", "class": "MEASURED_VARIATION",
        "origin": "d650e94 (2026-07-27, 2C-2E-CORR)", "reading": "bulb_width_over_collar_width",
        "measured_m3": {"emitted": 0.7788, "target": 0.77883, "offset": 0.0},
        "method": _LIST_METHOD + "; line 4's derivation — the same quantity BULB_WIDTH_TO_COLLAR_BAND bands at ±0.03",
        "method_value": {"measured": 0.0206, "rounded": 0.03, "rounded_is": "with the grid — line 4's landed width"},
        "decision": "APPLIED", "why": _APPLIED, "recorded_under": "§BH54(c) (37ba1bb)",
        "ruling": "§BH54(b) (m)"},
    "closure_connection_slack_mm": {
        "limit": 0.5, "limit_text": None, "kind": "READER_PARAMETER", "class": "READER_PARAMETER",
        "origin": "d650e94 (2026-07-27, 2C-2E-CORR)", "reading": "collar_reaches_neck",
        "measured_m3": {"collar_bottom_minus_neck_top_mm": 1.2239, "bulb_bottom_minus_collar_top_mm": 0.4451},
        "method": "the sheet-space quantisation (0.0556 mm) plus one grid step (0.3338 mm)",
        "method_value": {"measured_mm": 0.3894, "rounded_mm": 0.4},
        "decision": "READER_PARAMETER_RECORDED",
        "why": "a reader's slack, not a band; the M3 sheet clears it by 1.22 mm either way", "ruling": "§BH54(c)"},
    "hero_leading_ceiling": {
        "limit": 2.0, "limit_text": "≤ the ruled 2 em", "kind": "CEILING", "class": "COMPOSER_CONSTANT",
        "was": 1.45, "was_text": "≤1.45×size", "was_class": "EDITORIAL",
        "was_units": "MILLIMETRES against POINTS — 13.05 as it computed on the ruled name, which is 4.11 em",
        "origin": "d650e94 (2026-07-27, 2C-2E-CORR)", "reading": "product_name_unified_block",
        "measured_m3": {"gap_mm": 6.35, "size_pt": 9.0, "gap_em": 2.0, "ceiling_as_written": 13.05,
                        "ceiling_as_written_em": 4.11},
        "method": "both quantities in EM — the gap over the size's own millimetres — against the composer's ruled "
                  "NAME_LEADING_EM (§AC1(c)), read where the composer reads it",
        "method_value": {"leading_em_on_m3": 2.0, "ceiling_em": 2.0},
        "decision": "UNITS_CORRECTED",
        "why": "§BH54(b) (o): \"THE HERO-LEADING CHECK IS A DEFECT, not a question: it compares millimetres with points. "
               "Fix it to compare like with like.\" A unit-consistent 1.45 em would refuse the 2.0 em he ruled, so the "
               "ceiling is his ruled leading and not July's literal. Still an upper bound only: a set inside the "
               "metric floor passes here (WI-V); the floor is §AC1's, guarded on the composer's side",
        "recorded_under": "§BH54(c) (37ba1bb)", "ruling": "§BH54(b) (o)"},
    "glass_base_opacity_ceiling": {
        "limit": 0.6, "limit_text": "op ≤0.6", "kind": "CEILING", "class": "COMPOSER_CONSTANT",
        "origin": "85bf7f7 (2026-07-27, 2C-2E)", "reading": "glass_base_opacity",
        "measured_m3": {"emitted": 0.4},
        "method": "the composer's own constant, 0.40",
        "method_value": {"composer_constant": 0.4},
        "decision": "COMPOSER_VALUE_RECORDED",
        "why": "as the fill: a design ceiling over a composer constant — recorded, not taken",
        "ruling": "§BH54(c)"},
    "logo_zone_share_ceiling": {
        "limit": LOGO_ZONE_SHARE_CEILING, "limit_text": "≤0.56", "kind": "CEILING", "class": "OWNER_TYPED",
        "origin": "560f8f7 (2026-08-27, §BC(h): his 0.55 share; the ceiling raised from 0.5 to clear it)",
        "reading": "logo_restraint",
        "measured_m3": {"share": 0.55},
        "method": "his typed word — §BC(h), \"0.55 — 12.10 mm\"",
        "method_value": {"owner_share": 0.55, "ceiling": 0.56},
        "decision": "OWNER_TYPED", "why": "his number", "ruling": "§BH54(c)"},
}
#: the five codes the bands decide -- July's bottle fails all five, the M3 render none
RE_RULED_GEOMETRY_CODES = (
    CYLINDRICAL_FORM_NOT_PRESERVED, SHOULDER_GEOMETRY_FAILED, NECK_GEOMETRY_MISSING,
    COLLAR_GEOMETRY_FAILED, BULB_GEOMETRY_FAILED,
)


def _in_band(value: float, band: tuple) -> bool:
    """§BH50(a): inside a two-sided band -- the measured centre plus or minus its calibrated half-width."""
    centre, half = band
    return centre - half <= value <= centre + half


def _band_text(band: tuple, section: str = "§BH50(a)") -> str:
    """The persisted target text of a band, naming the ruling its centre and width come from — §BH50(a) for the
    bands it set, §BH50(f)(8) line 7 or 8 for the bands the list set (his (4): a label says what is true)."""
    centre, half = band
    return f"{centre:.4f} ± {half:.2f} ({centre - half:.4f}–{centre + half:.4f}, {section})"


def _nodes_by_name(doc) -> dict:
    return {str(getattr(n, "name", "")): n for n, _ in doc.walk()}


def _bbox_of_segments(segments) -> tuple | None:
    xs, ys = [], []
    for seg in segments or []:
        for attr in ("x", "x1", "x2"):
            v = getattr(seg, attr, None)
            if v is not None:
                xs.append(float(v))
        for attr in ("y", "y1", "y2"):
            v = getattr(seg, attr, None)
            if v is not None:
                ys.append(float(v))
    if not xs or not ys:
        return None
    return (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))


def _node_bbox(node) -> tuple | None:
    if getattr(node, "segments", None) is not None:
        return _bbox_of_segments(node.segments)
    if all(getattr(node, a, None) is not None for a in ("x", "y", "w", "h")):
        return (float(node.x), float(node.y), float(node.w), float(node.h))
    return None


def _opacity(node) -> float | None:
    fill = getattr(node, "fill", None)
    if fill is None:
        return None
    stops = getattr(fill, "stops", None)
    if stops:                       # gradient: the strongest stop governs
        return max(float(getattr(st, "opacity", 1.0)) for st in stops)
    op = getattr(fill, "opacity", None)
    return 1.0 if op is None else float(op)


def _flatten(segments, steps: int = 48) -> list:
    """The drawn outline as polylines (sheet mm, y-down): lines kept, cubics sampled at ``steps`` points, Z
    closing to the subpath's start. What is DRAWN, not the control cage."""
    polys, cur, start = [], None, None
    for s in segments or []:
        op = getattr(s, "op", None)
        if op == "M":
            cur = start = (float(s.x), float(s.y))
            polys.append([cur])
        elif op == "L" and cur is not None:
            cur = (float(s.x), float(s.y))
            polys[-1].append(cur)
        elif op == "C" and cur is not None:
            p0, p1 = cur, (float(s.x1), float(s.y1))
            p2, p3 = (float(s.x2), float(s.y2)), (float(s.x), float(s.y))
            for i in range(1, steps + 1):
                t = i / steps
                u = 1.0 - t
                polys[-1].append((u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                                  u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
            cur = p3
        elif op == "Z" and cur is not None and start is not None:
            polys[-1].append(start)
            cur = start
    return polys


def _width_at(polys, y: float):
    """The drawn width at the horizontal line ``y``: the span of the outline's crossings, or None below two."""
    xs = []
    for poly in polys:
        for (x0, y0), (x1, y1) in zip(poly, poly[1:]):
            if (y0 - y) * (y1 - y) <= 0 and y0 != y1:
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    return (max(xs) - min(xs)) if len(xs) >= 2 else None


def _extreme_width(polys, y_lo: float, y_hi: float, *, narrowest: bool, step: float = 0.02):
    """The narrowest (or widest) drawn width over [y_lo, y_hi], sampled every ``step`` mm, and the y it sits at."""
    if y_hi <= y_lo:
        return None, None
    best, at = None, None
    for i in range(int((y_hi - y_lo) / step) + 1):
        y = y_lo + i * step
        w = _width_at(polys, y)
        if w is None:
            continue
        if best is None or (w < best if narrowest else w > best):
            best, at = w, y
    return best, at


def _visible_waist(nodes: dict) -> dict:
    """§BH50(f)(8) line 7 — rule 3's subject: the glass outline's narrowest DRAWN width (cubics sampled) between the
    collar box's bottom and the SHOULDER_ELLIPSE box's centre line, over the body's box width (the control-point
    extent the other legs use). An empty interval, a missing object or a
    segment-less outline reads "absent" with its reason — the rule fails closed on it, never passes."""
    wall = nodes.get("GLASS_OUTER_WALL")
    collar = nodes.get("COLLAR_ROSE_GOLD_BASE")
    ell = nodes.get("SHOULDER_ELLIPSE")
    boxes = [_node_bbox(n) if n is not None else None for n in (wall, collar, ell)]
    if any(b is None for b in boxes) or not getattr(wall, "segments", None):
        return {"state": "absent", "reason": "GLASS_OUTER_WALL, COLLAR_ROSE_GOLD_BASE or SHOULDER_ELLIPSE is "
                                             "missing, or the glass outline has no segments"}
    wall_box, collar_box, ell_box = boxes
    y_lo = collar_box[1] + collar_box[3]
    y_hi = ell_box[1] + ell_box[3] / 2.0
    if y_hi <= y_lo:
        return {"state": "absent", "reason": "empty interval: the shoulder ellipse's centre line is not below "
                                             "the collar's bottom", "between_mm": [y_lo, y_hi]}
    w, at = _extreme_width(_flatten(wall.segments), y_lo, y_hi, narrowest=True)
    if w is None:
        return {"state": "absent", "reason": "the glass outline has no drawn width between the collar's bottom "
                                             "and the shoulder ellipse's centre line", "between_mm": [y_lo, y_hi]}
    return {"state": "measured", "waist_mm": w, "at_y_mm": at,
            "waist_over_body": w / max(wall_box[2], 1e-6), "between_mm": [y_lo, y_hi]}


def _axis(name, state, value=None, target=None, tolerance=None, note="", tolerance_source=None):
    a = {"axis": name, "state": state}
    if tolerance_source is not None:      # §BH50(g)(3): where the width came from travels with the width
        a["tolerance_source"] = tolerance_source
    if value is not None:
        a["value"] = value
    if target is not None:
        a["target"] = target
    if tolerance is not None:
        a["tolerance"] = tolerance
    if note:
        a["note"] = note
    return a


def _dome(nodes: dict) -> dict:
    """§BH50(f)(8) line 8 — rule 5's dome: the bulb outline's widest DRAWN width over the middle third of its box
    height (the shaft), over the collar's box width, and the box height over that shaft (slenderness). A missing
    object or a segment-less outline reads "absent" with its reason — the rule fails closed on it."""
    bulb = nodes.get("BULB_DARK_PLUM")
    collar = nodes.get("COLLAR_ROSE_GOLD_BASE")
    bulb_box = _node_bbox(bulb) if bulb is not None else None
    collar_box = _node_bbox(collar) if collar is not None else None
    if bulb_box is None or collar_box is None or not getattr(bulb, "segments", None):
        return {"state": "absent", "reason": "BULB_DARK_PLUM or COLLAR_ROSE_GOLD_BASE is missing, or the bulb "
                                             "outline has no segments"}
    y_lo = bulb_box[1] + bulb_box[3] / 3.0
    y_hi = bulb_box[1] + 2.0 * bulb_box[3] / 3.0
    shaft, at = _extreme_width(_flatten(bulb.segments), y_lo, y_hi, narrowest=False)
    if shaft is None:
        return {"state": "absent", "reason": "the bulb outline has no drawn width over the middle third of its "
                                             "box height", "between_mm": [y_lo, y_hi]}
    return {"state": "measured", "shaft_mm": shaft, "at_y_mm": at, "between_mm": [y_lo, y_hi],
            "shaft_over_collar": shaft / max(collar_box[2], 1e-6),
            "slenderness": bulb_box[3] / max(shaft, 1e-6)}


def measure_concept_fidelity(doc, confirmed: dict) -> dict:
    """Measure the emitted dropper reconstruction.

    ``confirmed`` carries the HUMAN_CONFIRMED_CONCEPT_ONLY geometry:
    total_height_mm, body_height_mm, body_diameter_mm, collar_height_mm,
    bulb_height_mm, collar_diameter_mm, base_thickness_mm. Concept-only
    targets validate concept-only geometry — nothing here is production
    authority.
    """
    nodes = _nodes_by_name(doc)
    axes: list[dict] = []
    failures: list[str] = []

    def fail(code, axis):
        failures.append(code)
        axes.append(axis)

    # --- material objects exist as independent nodes (§10) ------------------
    missing = [n for n in REQUIRED_MATERIAL_OBJECTS if n not in nodes]
    if missing:
        fail(MATERIAL_RELATIONSHIP_FAILED,
             _axis("material_object_separation", "MEASURED_FAIL",
                   value=f"missing: {missing}",
                   target="all independent objects present"))
        return {"schema_version": SCHEMA, "axes": axes,
                "failures": sorted(set(failures))}
    axes.append(_axis("material_object_separation", "MEASURED_PASS",
                      value=f"{len(REQUIRED_MATERIAL_OBJECTS)}/"
                            f"{len(REQUIRED_MATERIAL_OBJECTS)} present",
                      target="all independent objects present"))

    wall, filln = nodes["GLASS_OUTER_WALL"], nodes["PRODUCT_FILL_APPEARANCE"]
    frost = nodes["FROST_TREATMENT"]
    collar, bulb = nodes["COLLAR_ROSE_GOLD_BASE"], nodes["BULB_DARK_PLUM"]
    base = nodes["GLASS_BASE_THICKNESS"]

    # --- aspect ratio (emitted silhouette, sheet space) ----------------------
    wall_box = _node_bbox(wall)
    collar_box = _node_bbox(collar)
    bulb_box = _node_bbox(bulb)
    base_box = _node_bbox(base)
    total_h = float(confirmed.get("total_height_mm") or 0)
    body_h = float(confirmed.get("body_height_mm") or 0)
    body_w = float(confirmed.get("body_diameter_mm") or 0)
    if wall_box and bulb_box and total_h and body_w:
        emitted_total = (wall_box[1] + wall_box[3]) - bulb_box[1]
        emitted_aspect = emitted_total / max(wall_box[2], 1e-6)
        target_aspect = total_h / body_w
        ok = abs(emitted_aspect - target_aspect) <= target_aspect * 0.02          # §BH54(b) (m): was 0.12
        axes.append(_axis("bottle_aspect_ratio",
                          "MEASURED_PASS" if ok else "MEASURED_FAIL",
                          value=round(emitted_aspect, 2),
                          target=round(target_aspect, 2), tolerance="±2%",
                          tolerance_source=INLINE_LIMIT_SOURCES["bottle_aspect_ratio"]))
        if not ok:
            failures.append(ASPECT_RATIO_FAILED)
    else:
        axes.append(_axis("bottle_aspect_ratio", "UNMEASURED",
                          note="confirmed dims or emitted boxes absent"))

    # --- silhouette geometry: body proportion + visible base band ------------
    if wall_box and body_h and body_w:
        emitted_body_aspect = wall_box[3] / max(wall_box[2], 1e-6)
        target_body_aspect = body_h / body_w
        ok = abs(emitted_body_aspect - target_body_aspect) \
            <= target_body_aspect * 0.12
        # squat/bulky guard (§9): the body must stay clearly taller than wide
        squat = emitted_body_aspect < 1.4
        axes.append(_axis("body_silhouette_proportion",
                          "MEASURED_PASS" if ok and not squat
                          else "MEASURED_FAIL",
                          value=round(emitted_body_aspect, 2),
                          target=round(target_body_aspect, 2),
                          tolerance="±12%, never squat (<1.4)",
                          tolerance_source={"proportion": INLINE_LIMIT_SOURCES["body_silhouette_proportion"],
                                            "squat_floor": INLINE_LIMIT_SOURCES["body_squat_floor"]}))
        if not ok or squat:
            failures.append(SILHOUETTE_MISMATCH)
    if base_box and wall_box:
        base_rel = base_box[3] / max(wall_box[3], 1e-6)
        target_rel = float(confirmed.get("base_thickness_mm") or 3.5) \
            / max(body_h or 68.0, 1e-6)
        ok = 0.4 * target_rel <= base_rel <= 2.5 * target_rel
        axes.append(_axis("visible_base_thickness",
                          "MEASURED_PASS" if ok else "MEASURED_FAIL",
                          value=round(base_rel, 4),
                          target=round(target_rel, 4),
                          tolerance="0.4×–2.5×",
                          tolerance_source=INLINE_LIMIT_SOURCES["visible_base_thickness"]))
        if not ok and SILHOUETTE_MISMATCH not in failures:
            failures.append(SILHOUETTE_MISMATCH)

    # --- closure geometry: collar band + bulb dome proportions ---------------
    collar_h = float(confirmed.get("collar_height_mm") or 0)
    bulb_h = float(confirmed.get("bulb_height_mm") or 0)
    if collar_box and bulb_box and collar_h and bulb_h:
        emitted_ratio = bulb_box[3] / max(collar_box[3], 1e-6)
        target_ratio = bulb_h / collar_h
        ok = abs(emitted_ratio - target_ratio) <= target_ratio * 0.30
        wider = collar_box[2] > bulb_box[2]
        axes.append(_axis("bulb_to_collar_proportion",
                          "MEASURED_PASS" if ok and wider
                          else "MEASURED_FAIL",
                          value=round(emitted_ratio, 2),
                          target=round(target_ratio, 2),
                          tolerance="±30%; collar wider than bulb",
                          tolerance_source=INLINE_LIMIT_SOURCES["bulb_to_collar_proportion"]))
        if not (ok and wider):
            failures.append(CAP_GEOMETRY_FAILED)
        collar_d = float(confirmed.get("collar_diameter_mm") or 0)
        if collar_d and body_w and wall_box:
            emitted_rel = collar_box[2] / max(wall_box[2], 1e-6)
            target_rel = collar_d / body_w
            ok = abs(emitted_rel - target_rel) <= 0.01                           # §BH54(b) (m): was 0.15
            axes.append(_axis("collar_diameter_rel_body",
                              "MEASURED_PASS" if ok else "MEASURED_FAIL",
                              value=round(emitted_rel, 2),
                              target=round(target_rel, 2),
                              tolerance="±0.01",
                              tolerance_source=INLINE_LIMIT_SOURCES["collar_diameter_rel_body"]))
            if not ok and CAP_GEOMETRY_FAILED not in failures:
                failures.append(CAP_GEOMETRY_FAILED)
    else:
        axes.append(_axis("bulb_to_collar_proportion", "UNMEASURED",
                          note="closure boxes or confirmed heights absent"))

    # --- material / transparency relationships (real opacities) --------------
    wall_op, fill_op = _opacity(wall), _opacity(filln)
    frost_op = _opacity(frost)
    separate = (wall is not filln and wall_op is not None
                and fill_op is not None)
    ordered = separate and wall_op < fill_op < 1.0
    axes.append(_axis("glass_wall_vs_product_fill",
                      "MEASURED_PASS" if ordered else "MEASURED_FAIL",
                      value=f"wall {wall_op} < fill {fill_op} < 1.0"
                      if separate else "objects not separate",
                      target="separate objects; wall more transparent "
                             "than fill; neither opaque"))
    if not ordered:
        failures.append(MATERIAL_RELATIONSHIP_FAILED)
    trans_ok = (wall_op is not None and 0.0 < wall_op <= 0.55
                and fill_op is not None and 0.15 <= fill_op <= 0.80
                and frost_op is not None and 0.0 < frost_op < 0.60)
    axes.append(_axis("transparency_relationship",
                      "MEASURED_PASS" if trans_ok else "MEASURED_FAIL",
                      value={"wall": wall_op, "fill": fill_op,
                             "frost": frost_op},
                      target="wall ≤0.55, fill 0.15–0.80, frost <0.60 — "
                             "translucent, never flat",
                      tolerance_source={"wall": INLINE_LIMIT_SOURCES["glass_wall_opacity_ceiling"],
                                        "fill": INLINE_LIMIT_SOURCES["product_fill_opacity_range"],
                                        "frost": INLINE_LIMIT_SOURCES["frost_opacity_ceiling"]}))
    if not trans_ok:
        failures.append(TRANSPARENCY_RELATIONSHIP_FAILED)

    # --- generic label fallback (§4: no boxed background) --------------------
    label_like = []
    for n, parent in doc.walk():
        pname = str(getattr(parent, "name", "") or "")
        if pname not in ("FRONT_DIRECT_PRINT", "Decoration"):
            continue
        if n.type == "rect":
            op = _opacity(n)
            if op is not None and op >= 0.85:
                label_like.append(str(getattr(n, "name", "")))
    axes.append(_axis("generic_label_fallback",
                      "MEASURED_PASS" if not label_like else "MEASURED_FAIL",
                      value=label_like or "none",
                      target="no opaque field/panel behind the front "
                             "typography",
                      tolerance_source=INLINE_LIMIT_SOURCES["label_rect_opacity_floor"]))
    if label_like:
        failures.append(GENERIC_LABEL_FALLBACK_USED)

    # --- unprinted negative space on the front ------------------------------
    front = nodes.get("FRONT_DIRECT_PRINT")
    if front is not None and wall_box:
        clip = getattr(front, "clip", None)
        zone_box = (_bbox_of_segments(clip) if isinstance(clip, list)
                    else _node_bbox(clip) if clip is not None else None)
        if zone_box:
            # §BH54(b) (p), OWNER RULED 2026-09-19: "THE 0.60 FRONT-PRINT SHARE: measure what it was protecting and what it
            # reads on the chosen design. If it describes July's bottle rather than mine, re-rule it to the chosen design …
            # if it protects something real about printing, keep it and say what." MEASURED: this axis is named front PRINT
            # share and its note is "frosted glass must stay visible around the typography" — and what it measured was the
            # ZONE, the area he PERMITS, not the print. 0.60 was written 2026-07-27 over July's 22 × 40 zone (0.39 of that
            # body); on the chosen design the zone read 0.45 until he widened it to hold his own product's name, and 0.56
            # since — no mark added — and a 29.47 mm zone would have failed it as a "generic label" on glass that is four
            # fifths bare. NOTHING ABOUT PRINTING STANDS BEHIND IT: the print-side limit is the zone record's own
            # `max_artwork_coverage`, enforced per placement as DECORATION_COVERAGE_EXCEEDED (container_projection). So it
            # is RE-RULED to measure what it names: the PRINT — the composer's own front placements, scale-free, the very
            # records that coverage cap reads — as a share of the glass. The ceiling stays the one number on record. The
            # zone's share is recorded beside it and rules nothing: the zone is his to set by confirmation. A document
            # that records no front placement has no print to measure, and says UNMEASURED rather than pass.
            zone_share = (zone_box[2] * zone_box[3]) / max(
                wall_box[2] * wall_box[3], 1e-6)
            front_id = (doc.metadata or {}).get("front_zone_id")
            placed = [p for p in ((doc.metadata or {}).get("placements") or [])
                      if p.get("zone_id") == front_id and p.get("kind") != "field"]
            if placed:
                of_zone = sum(float(p["nw"]) * float(p["nh"]) for p in placed)
                share = zone_share * of_zone
                ok = share <= 0.60
                axes.append(_axis("front_print_share_of_body",
                                  "MEASURED_PASS" if ok else "MEASURED_FAIL",
                                  value={"print_of_glass": round(share, 3),
                                         "print_of_zone": round(of_zone, 3),
                                         "zone_of_glass": round(zone_share, 2),
                                         "placements": len(placed)},
                                  target="print ≤0.60 of the glass",
                                  note="frosted glass must stay visible around "
                                       "the typography — the PRINT is judged; the "
                                       "zone's share is recorded and rules nothing",
                                  tolerance_source=INLINE_LIMIT_SOURCES["front_print_share_ceiling"]))
                if not ok and GENERIC_LABEL_FALLBACK_USED not in failures:
                    failures.append(GENERIC_LABEL_FALLBACK_USED)
            else:
                axes.append(_axis("front_print_share_of_body", "UNMEASURED",
                                  value={"zone_of_glass": round(zone_share, 2), "placements": 0},
                                  target="print ≤0.60 of the glass",
                                  note="the document records no front placement, so the PRINT "
                                       "cannot be measured; the zone's share rules nothing",
                                  tolerance_source=INLINE_LIMIT_SOURCES["front_print_share_ceiling"]))

    # ------------------------------------------------------------------
    # 2C-2E-CORR-1 §12 — real-shape axes (never satisfied by labels alone)
    # ------------------------------------------------------------------
    def _cubics(node):
        return sum(1 for seg in (getattr(node, "segments", None) or [])
                   if type(seg).__name__ == "CubicTo")

    def _top_width(node):
        """x-extent of the silhouette's top edge (within 1.5mm of min y)."""
        pts = []
        for seg in (getattr(node, "segments", None) or []):
            x, y = getattr(seg, "x", None), getattr(seg, "y", None)
            if x is not None and y is not None:
                pts.append((float(x), float(y)))
        if not pts:
            return None
        y_min = min(p[1] for p in pts)
        top = [p[0] for p in pts if p[1] <= y_min + 1.5]
        return (max(top) - min(top)) if len(top) >= 2 else None

    # cylindrical form: curved silhouette + elliptical transition + a
    # narrow neck top — a rounded rectangle fails all three
    curves = _cubics(wall)
    top_w = _top_width(wall)
    narrow = (top_w is not None and wall_box       # §BH50(a): the neck top's proportion, inside its band
              and _in_band(top_w / max(wall_box[2], 1e-6), TOP_TO_BODY_BAND))
    shoulder_ok = "SHOULDER_ELLIPSE" in nodes and narrow
    cyl_ok = curves >= 4 and "SHOULDER_ELLIPSE" in nodes and narrow
    axes.append(_axis("cylindrical_form",
                      "MEASURED_PASS" if cyl_ok else "MEASURED_FAIL",
                      value=f"curves={curves}, top/body="
                            f"{round((top_w or 0) / max(wall_box[2], 1e-6), 2) if wall_box else None}",
                      target="≥4 curve segments · elliptical transition · "
                             f"neck top {_band_text(TOP_TO_BODY_BAND)} × body",
                      tolerance=TOP_TO_BODY_BAND[1], note=GEOMETRY_BAND_NOTE,
                      tolerance_source=GEOMETRY_BAND_WIDTH_SOURCES["TOP_TO_BODY_BAND"]))
    if not cyl_ok:
        failures.append(CYLINDRICAL_FORM_NOT_PRESERVED)
    axes.append(_axis("shoulder_geometry",
                      "MEASURED_PASS" if shoulder_ok else "MEASURED_FAIL",
                      value={"shoulder_ellipse": "SHOULDER_ELLIPSE" in nodes,
                             "narrow_top": bool(narrow)},
                      target="elliptical shoulder transition above a "
                             f"neck top {_band_text(TOP_TO_BODY_BAND)} × body",
                      tolerance=TOP_TO_BODY_BAND[1], note=GEOMETRY_BAND_NOTE,
                      tolerance_source=GEOMETRY_BAND_WIDTH_SOURCES["TOP_TO_BODY_BAND"]))
    if not shoulder_ok:
        failures.append(SHOULDER_GEOMETRY_FAILED)

    # §BH50(f)(8) line 7: rule 3 reads the VISIBLE WAIST — the glass outline's
    # narrowest drawn width between the collar's bottom and the shoulder
    # ellipse's centre line, over the body's box width — in place of the
    # NECK_GLASS rectangle the opaque collar covers. NECK_GLASS stays drawn;
    # closure_assembly_connection below reads its top edge. An empty interval,
    # a missing ellipse or a segment-less outline reads MEASURED_FAIL "absent",
    # never a pass. The code keeps its name; the target says what it measures.
    waist = _visible_waist(nodes)
    neck_ok = (waist["state"] == "measured"
               and _in_band(waist["waist_over_body"], NECK_TO_BODY_BAND))
    axes.append(_axis("visible_neck",
                      "MEASURED_PASS" if neck_ok else "MEASURED_FAIL",
                      value=({"waist_over_body": round(waist["waist_over_body"], 4),
                              "waist_mm": round(waist["waist_mm"], 3),
                              "between_mm": [round(v, 3) for v in waist["between_mm"]]}
                             if waist["state"] == "measured"
                             else f"absent: {waist['reason']}"),
                      target=f"waist proportion {_band_text(NECK_TO_BODY_BAND, WAIST_BAND_SECTION)} × body — "
                             "the glass outline's narrowest drawn width between the "
                             "collar's bottom and the shoulder ellipse's centre line",
                      tolerance=NECK_TO_BODY_BAND[1], note=WAIST_BAND_NOTE,
                      tolerance_source=GEOMETRY_BAND_WIDTH_SOURCES["NECK_TO_BODY_BAND"]))
    if not neck_ok:
        failures.append(NECK_GEOMETRY_MISSING)

    # collar: cylindrical (elliptical top) + 2:1 proportion + metallic
    # highlight/shadow as separate roles
    collar_ok = False
    if collar_box:
        wh = collar_box[2] / max(collar_box[3], 1e-6)
        collar_ok = ("COLLAR_TOP_RIM" in nodes
                     and _in_band(wh, COLLAR_WIDTH_TO_HEIGHT_BAND))
        axes.append(_axis("collar_cylindrical_geometry",
                          "MEASURED_PASS" if collar_ok else "MEASURED_FAIL",
                          value=round(wh, 2),
                          target="elliptical top rim · w/h "
                                 f"{_band_text(COLLAR_WIDTH_TO_HEIGHT_BAND)}",
                          tolerance=COLLAR_WIDTH_TO_HEIGHT_BAND[1], note=GEOMETRY_BAND_NOTE,
                          tolerance_source=GEOMETRY_BAND_WIDTH_SOURCES["COLLAR_WIDTH_TO_HEIGHT_BAND"]))
    if not collar_ok:
        failures.append(COLLAR_GEOMETRY_FAILED)
    fill_type = type(getattr(collar, "fill", None)).__name__
    roles = ("COLLAR_ROSE_GOLD_LIGHT", "COLLAR_ROSE_GOLD_SPECULAR",
             "COLLAR_ROSE_GOLD_SHADOW", "COLLAR_TOP_RIM",
             "COLLAR_BOTTOM_RIM")
    metallic_ok = (all(r in nodes for r in roles)
                   and fill_type == "GradientFill")
    axes.append(_axis("collar_metallic_material",
                      "MEASURED_PASS" if metallic_ok else "MEASURED_FAIL",
                      value={"roles_present": [r for r in roles
                                               if r in nodes],
                             "fill": fill_type},
                      target="six-role rose gold (base gradient + light + "
                             "specular + shadow + both rims) — never one "
                             "flat pink"))
    if not metallic_ok:
        failures.append(COLLAR_MATERIAL_FAILED)

    # §14 ratio targets (visual concept targets, never tolerances)
    if collar_box and wall_box and bulb_box:
        cb_w = collar_box[2] / max(wall_box[2], 1e-6)
        target_cb = (float(confirmed.get("collar_diameter_mm") or 24)
                     / max(body_w, 1e-6))
        ch_bh = collar_box[3] / max(wall_box[3], 1e-6)
        target_ch = (float(confirmed.get("collar_height_mm") or 11.5)
                     / max(body_h, 1e-6))
        scale_ok = (abs(cb_w - target_cb) <= 0.01                                # §BH54(b) (m): was 0.06
                    and abs(ch_bh - target_ch) <= 0.05)                          # HELD at its literal: see _HELD_BY
        axes.append(_axis("collar_scale_vs_body",
                          "MEASURED_PASS" if scale_ok else "MEASURED_FAIL",
                          value={"width_ratio": round(cb_w, 3),
                                 "height_ratio": round(ch_bh, 3)},
                          target={"width_ratio": round(target_cb, 3),
                                  "height_ratio": round(target_ch, 3)},
                          tolerance="±0.01 / ±0.05",
                          tolerance_source={"width_ratio": INLINE_LIMIT_SOURCES["collar_scale_width"],
                                            "height_ratio": INLINE_LIMIT_SOURCES["collar_scale_height"]}))
        if not scale_ok:
            failures.append(COLLAR_SCALE_MISMATCH)
        bc_w = bulb_box[2] / max(collar_box[2], 1e-6)
        target_bc = (float(confirmed.get("bulb_width_mm") or 13)
                     / max(float(confirmed.get("collar_diameter_mm") or 24),
                           1e-6))
        prop_ok = abs(bc_w - target_bc) <= 0.03                                  # §BH54(b) (m): was 0.06
        axes.append(_axis("bulb_width_vs_collar",
                          "MEASURED_PASS" if prop_ok else "MEASURED_FAIL",
                          value=round(bc_w, 3), target=round(target_bc, 3),
                          tolerance="±0.03",
                          tolerance_source=INLINE_LIMIT_SOURCES["bulb_width_vs_collar"]))
        if not prop_ok:
            failures.append(BULB_PROPORTION_FAILED)
        # continuous closure assembly: the collar must reach/enclose the
        # neck and the bulb must enter the collar
        neck2 = nodes.get("NECK_GLASS")
        neck2_box = _node_bbox(neck2) if neck2 is not None else None
        conn_ok = (neck2_box is not None
                   and collar_box[1] + collar_box[3] >= neck2_box[1] - 0.5
                   and bulb_box[1] + bulb_box[3] >= collar_box[1])
        axes.append(_axis("closure_assembly_connection",
                          "MEASURED_PASS" if conn_ok else "MEASURED_FAIL",
                          value={"collar_reaches_neck": bool(
                              neck2_box and collar_box[1] + collar_box[3]
                              >= neck2_box[1] - 0.5),
                                 "bulb_enters_collar": bool(
                              bulb_box[1] + bulb_box[3] >= collar_box[1])},
                          target="one continuous physical assembly — no "
                                 "floating collar",
                          tolerance_source=INLINE_LIMIT_SOURCES["closure_connection_slack_mm"]))
        if not conn_ok:
            failures.append(NECK_CONNECTION_FAILED)

    # §8 the fill level must not read as an open vessel
    fill_type2 = type(getattr(filln, "fill", None)).__name__
    no_level = ("INNER_PRODUCT_VOLUME" not in nodes
                and fill_type2 == "GradientFill")
    axes.append(_axis("product_fill_no_liquid_line",
                      "MEASURED_PASS" if no_level else "MEASURED_FAIL",
                      value={"fill_level_ellipse":
                             "INNER_PRODUCT_VOLUME" in nodes,
                             "fill_paint": fill_type2},
                      target="subtle vertical tonal tint — no horizontal "
                             "liquid line, no open-vessel ellipse"))
    if not no_level:
        failures.append(FILL_LEVEL_MISINTERPRETED)

    # §9 continuous curvature — never broad rectangular bars
    curved_nodes = ("CENTRAL_GLASS_LIGHT", "GLASS_SPECULAR",
                    "LEFT_EDGE_CURVATURE", "RIGHT_EDGE_CURVATURE")
    curvature_ok = all(
        getattr(nodes.get(nm), "type", "") == "path"
        and _cubics(nodes[nm]) >= 1 for nm in curved_nodes)
    axes.append(_axis("glass_curvature_objects",
                      "MEASURED_PASS" if curvature_ok else "MEASURED_FAIL",
                      value={nm: getattr(nodes.get(nm), "type", "absent")
                             for nm in curved_nodes},
                      target="curved paths following the cylinder — no "
                             "broad rectangular bars"))
    if not curvature_ok:
        failures.append(GLASS_CURVATURE_FAILED)

    # §11 the product name is ONE unified stacked block (tight leading)
    hero_runs = sorted(
        [n for n, _ in doc.walk() if n.type == "text"
         and str(getattr(n, "name", "")).startswith("product-name-hero")],
        key=lambda r: float(r.y))
    if len(hero_runs) >= 2:
        # §BH54(b) (o), OWNER RULED 2026-09-19: "THE HERO-LEADING CHECK IS A DEFECT, not a question: it compares
        # millimetres with points. Fix it to compare like with like." What stood: `gap <= size * 1.45`, the gap in
        # document MILLIMETRES, the size in POINTS — 6.35 against 9.0 × 1.45 = 13.05 on the ruled name — so the
        # ceiling it computed was 4.11 em and it admitted every leading the composer has ever set. LIKE WITH LIKE:
        # both go to EM (the gap over the size's own millimetres). THE CEILING IS NOT 1.45 EM: that literal is July's,
        # EDITORIAL, with no method on record, and a unit-consistent 1.45 em refuses the 2.0 em he ruled (§AC1(c)) —
        # "a rule that refuses my own chosen design is describing something other than my design". It is the
        # composer's own ruled NAME_LEADING_EM, read where the composer reads it: should his AC1(c) bet be lost and
        # the named fallback (3.0047 em, "it needs no new ruling to take") be taken, that ONE constant moves and this
        # check follows it. STILL AN UPPER BOUND ONLY: a set INSIDE the metric floor (1.06 em, §AC1) passes here, as
        # WI-V pinned; the floor is §AC1's and is guarded on the composer's side.
        from apps.ire.back_panel import MM_PER_PT
        from apps.ire.compose_dropper import NAME_LEADING_EM
        gap_mm = float(hero_runs[1].y) - float(hero_runs[0].y)
        size_pt = float(hero_runs[0].size_pt or 1)
        leading_em = gap_mm / (size_pt * MM_PER_PT)
        unified = leading_em <= NAME_LEADING_EM + 1e-6
        axes.append(_axis("product_name_unified_block",
                          "MEASURED_PASS" if unified else "MEASURED_FAIL",
                          value={"leading": round(gap_mm, 2),
                                 "size": round(size_pt, 2),
                                 "leading_em": round(leading_em, 4),
                                 "units": {"leading": "mm", "size": "pt"}},
                          target=f"stacked block, leading ≤ the ruled {NAME_LEADING_EM:g} em — one "
                                 "visual element",
                          tolerance_source=INLINE_LIMIT_SOURCES["hero_leading_ceiling"]))
        if not unified:
            failures.append(TYPOGRAPHY_NOT_PRESERVED)

    # bulb: slim rounded dome — narrower than the collar, never an
    # egg/block
    bulb_ok = False
    if bulb_box and collar_box:
        w_ratio = bulb_box[2] / max(collar_box[2], 1e-6)
        aspect_b = bulb_box[3] / max(bulb_box[2], 1e-6)
        # §BH50(f)(8) line 8: the dome beside the box — the shaft over the
        # collar and the slenderness join the two box legs; both box legs and
        # the cubics are kept; an absent dome fails the rule, never passes it
        dome = _dome(nodes)
        dome_ok = (dome["state"] == "measured"
                   and _in_band(dome["shaft_over_collar"], SHAFT_TO_COLLAR_BAND)
                   and _in_band(dome["slenderness"], BULB_SLENDERNESS_BAND))
        bulb_ok = (_in_band(w_ratio, BULB_WIDTH_TO_COLLAR_BAND)
                   and _in_band(aspect_b, BULB_ASPECT_BAND)
                   and _cubics(bulb) >= 2
                   and dome_ok)
        axes.append(_axis("bulb_slim_dome",
                          "MEASURED_PASS" if bulb_ok else "MEASURED_FAIL",
                          value={"width_vs_collar": round(w_ratio, 2),
                                 "aspect": round(aspect_b, 2),
                                 "curves": _cubics(bulb),
                                 "shaft_vs_collar": (round(dome["shaft_over_collar"], 4)
                                                     if dome["state"] == "measured"
                                                     else f"absent: {dome['reason']}"),
                                 "slenderness": (round(dome["slenderness"], 4)
                                                 if dome["state"] == "measured" else "absent"),
                                 "shaft_mm": (round(dome["shaft_mm"], 3)
                                              if dome["state"] == "measured" else "absent")},
                          target=f"width {_band_text(BULB_WIDTH_TO_COLLAR_BAND)} × collar · "
                                 f"aspect {_band_text(BULB_ASPECT_BAND, LINE5_BAND_SECTION)} · "
                                 f"shaft {_band_text(SHAFT_TO_COLLAR_BAND, DOME_BAND_SECTION)} × collar · "
                                 f"slenderness {_band_text(BULB_SLENDERNESS_BAND, DOME_BAND_SECTION)} · "
                                 "domed (curved), never egg/block, never a paddle",
                          tolerance={"width_vs_collar": BULB_WIDTH_TO_COLLAR_BAND[1],
                                     "aspect": BULB_ASPECT_BAND[1],
                                     "shaft_vs_collar": SHAFT_TO_COLLAR_BAND[1],
                                     "slenderness": BULB_SLENDERNESS_BAND[1]}, note=DOME_BAND_NOTE,
                          tolerance_source={"width_vs_collar": GEOMETRY_BAND_WIDTH_SOURCES["BULB_WIDTH_TO_COLLAR_BAND"],
                                            "aspect": GEOMETRY_BAND_WIDTH_SOURCES["BULB_ASPECT_BAND"],
                                            "shaft_vs_collar": GEOMETRY_BAND_WIDTH_SOURCES["SHAFT_TO_COLLAR_BAND"],
                                            "slenderness": GEOMETRY_BAND_WIDTH_SOURCES["BULB_SLENDERNESS_BAND"]}))
    if not bulb_ok:
        failures.append(BULB_GEOMETRY_FAILED)
    if CAP_GEOMETRY_FAILED in failures and \
            CLOSURE_PROPORTION_FAILED not in failures:
        failures.append(CLOSURE_PROPORTION_FAILED)

    # frosted-glass visualization: frost + curved edge shading + a CURVED
    # highlight + wall-depth hint; the base band is glass, not a white bar
    hl = nodes.get("GLASS_SPECULAR")
    hl_curved = hl is not None and getattr(hl, "type", "") == "path" \
        and _cubics(hl) >= 1
    base_op = _opacity(base)
    frost_ok = (hl_curved
                and "LEFT_EDGE_CURVATURE" in nodes
                and "RIGHT_EDGE_CURVATURE" in nodes
                and "GLASS_INNER_WALL" in nodes
                and "BASE_REFRACTION" in nodes
                and base_op is not None and base_op <= 0.6)
    axes.append(_axis("frosted_glass_visualization",
                      "MEASURED_PASS" if frost_ok else "MEASURED_FAIL",
                      value={"curved_specular": hl_curved,
                             "edge_curvature": "LEFT_EDGE_CURVATURE" in nodes
                             and "RIGHT_EDGE_CURVATURE" in nodes,
                             "inner_wall": "GLASS_INNER_WALL" in nodes,
                             "base_refraction": "BASE_REFRACTION" in nodes,
                             "base_opacity": base_op},
                      target="curved specular (no straight bars) · edge "
                             "curvature · inner wall · base refraction · "
                             "translucent base (op ≤0.6)",
                      tolerance_source=INLINE_LIMIT_SOURCES["glass_base_opacity_ceiling"]))
    if not frost_ok:
        failures.append(FROSTED_GLASS_VIZ_FAILED)

    # logo restraint: the controlled fallback never dominates the front
    # [the owner's second answer of 2026-09-25: the mark drawn from its approved vector master is held to the same
    # restraint as the raster it replaces]
    from apps.ire import brand_mark as _brand_mark
    logo_nodes = [n for n, p in doc.walk() if (n.type == "image" or _brand_mark.is_mark(n))
                  and str(getattr(n, "name", "")) == "logo"]
    if logo_nodes and front is not None:
        clip = getattr(front, "clip", None)
        zbox = (_bbox_of_segments(clip) if isinstance(clip, list)
                else _node_bbox(clip) if clip is not None else None)
        if zbox:
            rel = float(logo_nodes[0].w) / max(zbox[2], 1e-6)
            ok = rel <= LOGO_ZONE_SHARE_CEILING
            axes.append(_axis("logo_restraint",
                              "MEASURED_PASS" if ok else "MEASURED_FAIL",
                              value=round(rel, 2),
                              target=f"logo ≤{LOGO_ZONE_SHARE_CEILING} × "
                                     "front-zone width — the product name "
                                     "leads. EDITORIAL ceiling: it yields to "
                                     "the 12.0 mm print floor and to the "
                                     "confirmed zone width, which is why it "
                                     "was raised from 0.5",
                              tolerance_source=INLINE_LIMIT_SOURCES["logo_zone_share_ceiling"]))
            if not ok:
                failures.append(LOGO_ZONE_MISMATCH)

    # concept-sheet presentation: the 12-section hierarchy + exactly ONE
    # subtle hero rule
    labels = [str(getattr(n, "name", "")) for n, _ in doc.walk()
              if n.type == "text"
              and str(getattr(n, "name", "")).startswith("panel-label-")]
    hero_rules = [n for n, _ in doc.walk()
                  if n.type == "path"
                  and str(getattr(n, "name", "")).startswith("rule-")]
    names_all = {str(getattr(n, "name", "")) for n, _ in doc.walk()}
    present_ok = (len(labels) >= 8 and "census-line" in names_all
                  and "sheet-status-12" in names_all
                  and len(hero_rules) == 1)
    axes.append(_axis("concept_sheet_presentation",
                      "MEASURED_PASS" if present_ok else "MEASURED_FAIL",
                      value={"section_labels": len(labels),
                             "census": "census-line" in names_all,
                             "status": "sheet-status-12" in names_all,
                             "hero_rules": len(hero_rules)},
                      target="≥8 labelled sections · census · rejection/"
                             "correction status · exactly one subtle rule"))
    if not present_ok:
        failures.append(SHEET_PRESENTATION_FAILED)

    return {"schema_version": SCHEMA, "axes": axes,
            "failures": sorted(set(failures))}


__all__ = ["SCHEMA", "REQUIRED_MATERIAL_OBJECTS", "measure_concept_fidelity",
           "ASPECT_RATIO_FAILED", "SILHOUETTE_MISMATCH",
           "CAP_GEOMETRY_FAILED", "MATERIAL_RELATIONSHIP_FAILED",
           "TRANSPARENCY_RELATIONSHIP_FAILED", "GENERIC_LABEL_FALLBACK_USED"]
