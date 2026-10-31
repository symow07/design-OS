"""counter_tray_header 0.1 — the family counter display of D-D12-2, ⟪PROVISIONAL⟫ (never production).

[The owner's decision, CURRENT_DECISIONS.md "Day 12", D-D12-2: "The family counter display: the house's own form — a
tapered counter tray with a header (house 008, 020, 052, 053, 056), not a stepped stand. ... the engine solves from the
three product records (palette 190 × 120 × 12; lipstick 80 × Ø 20; balm 70 × Ø 18), never from a picture ... The die: a
new template counter_tray_header in apps/dielines, solved from the ES3083 display-box die as the structural reference
... reference-mapping.json is required ... a fold check that outputs the closed dimensions and every clearance against
the three product records ... The sightline check, defined for this form ..."]

What this module does, in order:

* :func:`solve` — every number of the display from three sources only: the product records, the owner's ⟪PROVISIONAL⟫
  numbers, and the house's own die (ES3083, measured by :func:`measure_reference_die`, its values transcribed in
  ``HOUSE`` and re-checked against the walk by the runner). Each value is a fact ``{value, authority, source}``; the
  builder's own choices carry ``builder_provisional`` and are listed as departures. Nothing is read off a picture.
* :func:`build_die` — the flat die drawn from the solve: the tray in one piece (the house's form: floor; doubled front
  wall with lock tabs; doubled tapered sides with lock tabs; corner flaps; back wall with side flaps and lock slots; a
  doubled header with a return flap) and, on the same sheet, the slot insert and the two stick platforms, each keyed
  to the tray floor (flush tabs on its legs into floor slots, so it fits one way round, print side out, and at one
  place only: each front leg keyed tight, each platform's back leg free in depth over the stated fold allowance,
  ``FOLD_ALLOWANCE_BOARDS``). The die is drawn from the print side: the tray is seen from below, the inserts from
  above (``DIE_FACE``).
* :func:`fold_check` — reads the drawn die (panel spans measured off its faces), folds it into the closed dimensions,
  and checks every clearance against the three product records and the die's own rules; the keys stood off the
  drawing land on their slots across the whole fold allowance (and a spacing outside it does not seat), and a
  turned-round, print-side-in or swapped part fits nowhere (every translation searched).
* :func:`sightlines` — the owner's check for this form: true 3-D rays from the eye to the sticks' front faces and the
  front palette's lid, the products and the tray as occluders — at the drawn places, then at every corner of the
  keys', the holes' and the folds' play, with the margin beyond it (:func:`sight_tolerance`).
* :func:`measure_reference_die` — the analytic walk of the ES3083 vectors (PyMuPDF ``get_drawings``). The reference's
  tier is NOT_IN_TIER_RECORD: its bytes are never placed, copied or traced into an output; only numbers leave the walk.

Datums: ``z`` is height above the counter (the tray's underside, z = 0); ``h`` is height above the tray floor's top
surface (z = t + h, t the board). ``y`` is depth from the tray's front outer face (y = 0) toward the back; ``x`` is
across, 0 at the centre. On the flat die, ``X`` runs right and ``Y`` runs down, the tray's floor at
X ∈ [0, W − 2t], Y ∈ [0, D − 2t].
"""
from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
from dataclasses import dataclass, field

from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union

TEMPLATE_ID = "counter_tray_header"
VERSION = "0.1"
SCHEMA = "counter_tray_header/0.1"
FOLD_SCHEMA = "counter_tray_header_fold_check/0.1"
SIGHT_SCHEMA = "counter_tray_header_sightlines/0.1"
DECISION = "D-D12-2 (CURRENT_DECISIONS.md, Day 12)"
#: [D-D13-3, CURRENT_DECISIONS.md Day 13: "counter_tray_header is registered in apps/dielines/registry.py with the
#: registry-agreement test the other templates carry; the template is 0.1 ⟪PROVISIONAL⟫ and says so in its record."]
REGISTRATION = ("D-D13-3 (CURRENT_DECISIONS.md, Day 13): registered in apps/dielines/registry.py as "
                "COUNTER_TRAY_HEADER, 0.1 ⟪PROVISIONAL⟫ — production_ready False, ineligibility "
                "PHYSICAL_SAMPLE_VALIDATION_REQUIRED (its structure untested against a folded sample); never offered "
                "by a production chooser (registry.production_templates, registry.new_selection_templates), refused "
                "by the carton input schema (validators/schema.py DielineInputJSON names cartons only: this template "
                "is solved by this module from the product records, not by the carton engine) and by "
                "template_selection.select_template (resolved False, its ineligibility code)")

#: the two conversions, named so a millimetre is never mistaken for a point
PT_PER_MM = 72.0 / 25.4
MM_PER_PT = 25.4 / 72.0

#: a measure agrees with what it closes onto within this (mm)
TOL_MM = 0.01

OWNER = "owner_provisional"
RECORD = "product_record"
SOLVED = "solved"
HOUSE_MEASURED = "house_measured"
BUILDER = "builder_provisional"

_D12 = "D-D12-2 (CURRENT_DECISIONS.md, Day 12), ⟪PROVISIONAL⟫, the owner's to correct: "
_D13_1 = "D-D13-1 (CURRENT_DECISIONS.md, Day 13), the owner's ruling: "
#: [D-D13-1, verbatim] the back wall's height, his ruling of the solved number (the solve still finds it from the slot)
BACK_WALL_RULING = ("The display's back wall stands at 182.12 mm above the tray floor (183.62 mm over the counter). My "
                    "\"about 245\" assumed the palette standing on its short edge; it stands on its long edge (190 wide, "
                    "120 tall, leaning 15°), and the height follows from the slot. Not a departure; the record is "
                    "corrected.")
BACK_WALL_RULED_OUTER_MM = 183.62
#: [D-D13-2, verbatim, CURRENT_DECISIONS.md Day 13] the slot insert's sway closed
SWAY_DECISION = ("D-D13-2 (CURRENT_DECISIONS.md, Day 13): \"The slot insert's sway is fixed today: the die's own "
                 "departure insert_sway ... is closed — the tube keyed at both legs' feet, or a glued diagonal gusset at "
                 "each end, whichever the die's vocabulary allows; the geometry verifier's 2.00 mm stack-to-back "
                 "clearance proven to hold at every lean; the fold check re-run\"")
_ES ="ES3083 die walk (materials/house-designs/ES3083吸塑 展盒刀线.ai, measured only, never placed): "


def fact(value, authority, source):
    return {"value": value, "authority": authority, "source": source}


# --- the three product records ---------------------------------------------------------------------------------------

PRODUCT_SOURCES = {
    "palette": ("brief 124: \"190 × 120 × 12 mm closed\" (⟪PROVISIONAL⟫ until the case is measured) — "
                "apps/pipeline/services/zilal_object.py:32 SIDE_MM = 12.0"),
    "lipstick": "CURRENT_DECISIONS.md D-D11-7 (⟪PROVISIONAL⟫): round case, closed 80 × Ø 20 mm; cap 40, body 40",
    "balm": ("CURRENT_DECISIONS.md D-D11-8 / D-D12-3 (⟪PROVISIONAL⟫): slim round stick, closed 70 × Ø 18; "
             "cap 30, body 40"),
}


def default_products() -> dict:
    """The three product records, values only (their sources are ``PRODUCT_SOURCES``)."""
    return {
        "palette": {"width_mm": 190.0, "height_mm": 120.0, "thickness_mm": 12.0},
        "lipstick": {"height_mm": 80.0, "diameter_mm": 20.0, "cap_mm": 40.0, "body_mm": 40.0},
        "balm": {"height_mm": 70.0, "diameter_mm": 18.0, "cap_mm": 30.0, "body_mm": 40.0},
    }


# --- the owner's ⟪PROVISIONAL⟫ numbers (D-D12-2), each with its words ------------------------------------------------

OWNER_NUMBERS = {
    "footprint_width_mm": (250.0, "footprint 250 wide × 160 deep"),
    "footprint_depth_mm": (160.0, "footprint 250 wide × 160 deep"),
    "header_width_mm": (250.0, "header 250 × 110 above the back wall"),
    "header_height_mm": (110.0, "header 250 × 110 above the back wall"),
    "board_mm": (1.5, "board 1.5 mm E-flute or 1.0 mm card"),
    "board_alternative_mm": (1.0, "board 1.5 mm E-flute or 1.0 mm card"),
    "slot_width_mm": (194.0, "one slot 194 wide × 30 deep"),
    "slot_depth_mm": (30.0, "one slot 194 wide × 30 deep"),
    "slot_floor_mm": (60.0, "its floor raised 60 mm above the tray floor"),
    "slot_lean_deg": (15.0, "leaning 15° back"),
    "palettes_in_slot": (2, "holding two palettes one behind the other (the front one's lid faces the shopper)"),
    # Day 13, D-D13-1: the owner's "about 245" corrected by his own words (his ruling, not a departure)
    "back_wall_mm": (182.12, BACK_WALL_RULING, _D13_1),
    "front_wall_mm": (20.0, "the tray's front wall 20 mm"),
    "balm_count": (6, "the front row 6 balms in Ø 19 holes at 32 mm pitch"),
    "balm_hole_mm": (19.0, "the front row 6 balms in Ø 19 holes at 32 mm pitch"),
    "lipstick_count": (6, "the back row 6 lipsticks in Ø 21 holes at 32 mm pitch, offset half a pitch"),
    "lipstick_hole_mm": (21.0, "the back row 6 lipsticks in Ø 21 holes at 32 mm pitch, offset half a pitch"),
    "pitch_mm": (32.0, "at 32 mm pitch"),
    "row_spacing_mm": (35.0, "rows 35 mm apart"),
    "hole_clearance_mm": (1.0, "hole Ø = product + 1 mm"),
    "front_plate_mm": (20.0, "the front row's plate 20 mm above the floor"),
    "back_plate_mm": (30.0, "the back row's 30 mm (so the lipstick's body still shows below its cap)"),
    "eye_front_mm": (500.0, "from the eye at 500 mm in front of the front edge and 350 mm above the counter"),
    "eye_height_mm": (350.0, "from the eye at 500 mm in front of the front edge and 350 mm above the counter"),
    "visible_band_mm": (25.0, "pass = the top 25 mm of every stick's front face ... visible"),
}


def default_provisional() -> dict:
    return {k: entry[0] for k, entry in OWNER_NUMBERS.items()}


def owner_source(key: str) -> str:
    """An owner's number's source: the decision it was typed in (D-D12-2 unless the entry names another) and his
    words."""
    entry = OWNER_NUMBERS[key]
    return (entry[2] if len(entry) > 2 else _D12) + "\"" + entry[1] + "\""


# --- the house's die, measured (ES3083 walk; re-checked against the walk by the runner) ------------------------------

#: name -> (value, where it was measured). The runner asserts every value against measure_reference_die's output.
HOUSE = {
    "principal_width_mm": (275.00, "floor side creases x 491.94 → 766.94"),
    "floor_depth_mm": (198.00, "floor front crease y 86.85 → back crease y 284.85"),
    "side_run_mm": (196.50, "side creases y 88.35 → 284.85"),
    "side_start_mm": (1.50, "side creases start 1.50 behind the front crease (86.85 → 88.35)"),
    "spine_mm": (5.00, "front spine creases y 56.85 → 61.85; side double crease 5.0 apart"),
    "liner_short_mm": (2.00, "front liner 23.00 against its skin 25.00"),
    "liner_inset_mm": (5.50, "front liner 264.00 = 275.00 − 2 × 5.50"),
    "tab_base_mm": (35.00, "front liner tabs x 526.94 → 561.94 at y 33.85"),
    "tab_tip_mm": (31.00, "front liner tabs x 528.94 → 559.94 at y 28.85"),
    "tab_height_mm": (5.00, "front liner tabs y 33.85 → 28.85"),
    "slot_depth_mm": (4.50, "floor slots 4.50 into the floor (y 86.85 → 91.35; x 762.44 → 766.94)"),
    "front_slot_offset_mm": (85.00, "front floor slot centres ±85.00 from the floor's centre x 629.44"),
    "side_slot_centre_1_mm": (51.00, "side floor slot 1 centre 51.00 behind the side run's start"),
    "side_slot_centre_2_mm": (136.00, "side floor slot 2 centre 136.00 behind the side run's start"),
    "corner_flap_inset_mm": (4.00, "corner flap x 770.94 → 789.94: 4.00 from the floor crease"),
    "corner_flap_top_gap_mm": (2.42, "corner flap top 23.00 against the side's front height 25.42"),
    "corner_flap_length_mm": (50.00, "corner flap y 38.35 → 88.35"),
    "back_inset_mm": (1.50, "back wall body x 493.44 → 765.44 = 275.00 − 2 × 1.50"),
    "back_wall_mm": (83.00, "back wall y 284.85 → 367.85"),
    "back_flap_depth_mm": (78.50, "back flap x 765.44 → 843.94"),
    "back_flap_bottom_mm": (4.00, "back flap bottom edge y 288.85, 4.00 above the floor crease"),
    "lock_neck_mm": (21.00, "lock tab hinge crease x 794.94 → 815.94"),
    "lock_head_mm": (29.00, "lock tab head x 790.94 → 819.94 (its widest vertices)"),
    "lock_head_at_mm": (5.00, "lock tab head y 289.85 (the widest vertices' y), 5.00 below its hinge y 284.85"),
    "lock_shoulder_mm": (24.62, "lock tab x 793.13 → 817.75 at y 296.43"),
    "lock_shoulder_at_mm": (11.58, "lock tab y 296.43, 11.58 below its hinge"),
    "lock_tip_mm": (15.12, "lock tab tip x 797.88 → 813.00 at y 299.85"),
    "lock_length_mm": (15.00, "lock tab y 284.85 → 299.85"),
    "lock_relief_mm": (2.00, "relief slits y 282.85 → 284.85 at the lock tab's neck"),
    "lock_slot_width_mm": (4.50, "lock slot x 764.94 → 769.44 across the back flap crease x 765.44"),
    "lock_slot_into_body_mm": (0.50, "lock slot 0.50 into the back wall body (764.94 → 765.44)"),
    "lock_slot_length_mm": (33.00, "lock slot y 309.85 → 342.85"),
    "header_mm": (197.00, "header y 367.85 → 564.85"),
    "header_fold_mm": (98.50, "header top fold y 466.35, 98.50 above the back wall crease"),
    "return_mm": (80.00, "return flap y 564.85 → 644.85"),
    "return_short_mm": (3.00, "return flap 80.00 against the back wall 83.00"),
    "return_inset_mm": (5.00, "return flap x 496.94 → 761.94, 5.00 inside the header's edges"),
    "return_chamfer_y_mm": (3.00, "return flap chamfer y 564.85 → 567.85"),
    "return_corner_radius_mm": (10.00, "return flap corners x 751.94 → 761.94, y 634.85 → 644.85"),
    "clearance_mm": (2.00, "the house's own assembly clearance: the liner stops 2.00 short; the back flap's hinge "
                           "starts 2.00 above the floor crease"),
    "relief_arc_radius_mm": (2.00, "relief arcs at the front corners (box 4.00 × 2.00) and at the back flaps' hinge "
                                   "foot (box 2.00 × 4.00): half circles, R 2.00"),
    "lock_shoulder_curve_w_mm": (4.75, "lock tab shoulder-to-tip edges are curves: box x 793.13 → 797.88"),
    "lock_shoulder_curve_h_mm": (3.42, "lock tab shoulder-to-tip edges are curves: box y 296.43 → 299.85"),
    "side_liner_short_front_mm": (1.96, "side liner free edge (between its tabs) reflected back across the spine: "
                                        "1.96 short of the floor crease at its front end"),
    "side_liner_short_back_mm": (-1.84, "side liner free edge reflected back across the spine: 1.84 PAST the floor "
                                        "crease at its back end (the edge is straight; its tabs 5.00 beyond it)"),
}


def house(name: str) -> float:
    return HOUSE[name][0]


# --- builder's ⟪PROVISIONAL⟫ choices (each listed as a departure) ------------------------------------------------------

BUILDER_CHOICES = {
    "backrest_mm": "the backrest reaches half the palette's standing height (120 / 2 = 60 mm along the lean): it holds "
                   "the stack at its centre of mass",
    "glue_flap_mm": "the slot insert closes as a tube on a 12 mm glue flap (apps/dielines/registry.py ECMA archetypes' "
                    "glue_tab_mm default, 12.0), glued to the INSIDE of the front leg: the front leg stands outside the "
                    "glue flap, on the floor, where its keys are; so the base's front crease is one board behind the "
                    "front leg's outer face and the base is drawn one board short of the tube's footprint",
    "wing_mm": "the slot insert's two wings are as deep as the bed (the owner's 30), so they flank the whole stack",
    "minimum_web_mm": "a web between holes or slots, or a hole's edge to a fold, at least 3 × the board (4.5 mm at "
                      "1.5 mm)",
    "platform_gap_mm": "the two platforms' facing legs stand the fold allowance (3 × board) + both keys' play "
                       "(2 × 0.25) + 0.5 mm apart (never less than the house's clearance, 2.00), so the front "
                       "platform's back leg, at the full allowance and the worst play, still clears the back platform's "
                       "front leg by 0.5 mm; the edge margin of both plates is the largest equal margin that leaves it",
    "fold_allowance_mm": "a platform's folded leg spacing (its two folds) may exceed the drawn (outer-surface) "
                         "spacing by 0 … 3 × board (the lead's figure; it encloses the tray's own fold rule, outer = "
                         "crease-to-crease + 2 × board, with one board to spare); its two folds are alike, so each "
                         "adds 0 … 1.5 × board. The front legs are keyed tight; the platforms' back-leg slots run "
                         "3 × board deeper behind the leg, so every folded spacing from drawn to drawn + 3 × board "
                         "seats (x held by both legs). What lies one fold behind a keyed front leg — a plate's hole "
                         "row, the slot insert's bed/backrest junction — drifts back 0 … 1.5 × board",
    "insert_set_forward_mm": "the slot insert (its junction, and so the stack) set forward of the house's 2.00 "
                             "clearance by one fold's allowance + the key's play (1.5 × board + 0.25) + how far the "
                             "stack's top-back corner moves back at the most lean its closed tube permits (D-D13-2: the "
                             "gussets hold the back leg square on the base, and the base's two folds may stand it "
                             "0 … 2 × 1.5 × board behind its drawn place): at its rearmost seat and that lean the "
                             "corner is still 2.00 from the back's inner face",
    "insert_gusset_mm": "D-D13-2's glued diagonal gusset at each end of the slot insert's tube: a right triangle hinged "
                        "on the back leg's side edge, from its foot up as far as the backrest is long (60 mm) and along "
                        "the base as far as a wing reaches (the owner's 30: the part keeps its width on the sheet), "
                        "folded in across the tube's open end, its flap (the tube's own 12 mm glue flap) glued to the "
                        "base's top inside the tube; unprinted (inside the tube, behind the palettes)",
    "rows_forward": "the stick rows go as far forward as the house's clearance allows (nearest the shopper): the front "
                    "plate's front leg at the front wall's inner face + 2.00; the depth left over lies between the "
                    "back platform and the slot insert",
    "lock_slot_rule": "every lock slot is its tab's width + 0.5 mm (the lead's rule for this die; ES3083 measures "
                      "+0.00 for its liner tabs and +4.00 for its rear lock); a front leg's floor key slot is also the "
                      "board + 0.5 across, so a front leg plays ±0.25 mm each way; a platform's back-leg key slot is "
                      "the tab + 0.5 along (x held) and the board + 3 × board + 0.5 across: 0.25 in front of the "
                      "drawn leg, the fold allowance + 0.25 behind it",
    "floor_keys": "each platform and the slot insert is keyed to the tray floor: flush tabs on its legs' free edges "
                  "(two per leg, one the house's 35.00 liner-tab width, one the house's 21.00 lock-neck width) into "
                  "floor slots, placed so a part fits one way round, print side out, and at one place only "
                  "(positions below): a platform's back leg carries its keys at other x than its front leg, so the "
                  "part folded print side in (mirrored) fits nowhere either way round",
    "key_tab_height_mm": "a key tab is as long as the board is thick: it fills its floor slot flush with the floor's "
                         "underside, so the tray still stands flat on the counter (z = 0 unchanged)",
    "liner_tab_height_mm": "a wall liner's tab (front 2, sides 4) is the liner's 2.00 short + the board long, so "
                           "folded through its floor slot its tip stops flush with the floor's underside (z = 0): the "
                           "tray stands on its floor, not on six tab tips (ES3083's 5.00 tab, kept, would reach 1.50 "
                           "below it at this board); the house's base 35.00 and tip 31.00 kept",
    "orientation_mark": "each platform and the slot insert carries the words \"front — shopper side\" on its front "
                        "leg's REVERSE (unprinted, inner) face, drawn on the print-side die flipped top to bottom so "
                        "it reads upright on the reverse face with the plate (bed) above it — as the folder holds the "
                        "part to fold it, and as it stands; in the die's WORDS layer, which never prints with the "
                        "front side (a reverse imprint or stamp; the keys enforce the orientation regardless)",
}

#: the floor keys' widths (house-measured: the front liner tab's base and the side lock tab's neck)
KEY_TAB_HOUSE = {"wide": "tab_base_mm", "narrow": "lock_neck_mm"}
#: the floor keys' positions, x across as the shopper sees it (builder's ⟪PROVISIONAL⟫ choice): the wide key on the
#: shopper's left on the front platform and the slot insert, on the right on the back platform. A platform's back leg
#: carries its pair at other x than its front leg (±40 against ±30; ±60 against ±75): folded print side in, a platform
#: is the mirror image of itself (x → −x, or, turned, y → −y — its legs swapped), and with unlike legs neither mirror
#: seats (the reviewer's MINOR 1)
KEY_LAYOUT = {
    "front platform": {"front leg": ((-30.0, "wide"), (30.0, "narrow")),
                       "back leg": ((-40.0, "wide"), (40.0, "narrow"))},
    "back platform": {"front leg": ((75.0, "wide"), (-75.0, "narrow")),
                      "back leg": ((60.0, "wide"), (-60.0, "narrow"))},
    "slot insert": {"front leg": ((-55.0, "wide"), (55.0, "narrow"))},
}
#: the legs keyed tight (slot = board + 0.5 across); every other keyed leg's slot runs the fold allowance deeper behind
TIGHT_LEG = "front leg"
#: slot − tab (the lead's rule), both along a key and across a tight leg's key
LOCK_PLAY_MM = 0.5
#: the fold allowance, in boards (the lead's 3 × board; the tray's own rule, outer = crease-to-crease + 2 × board, lies
#: inside it): a folded spacing from a keyed front leg may exceed the drawn by 0 … this × the board
FOLD_ALLOWANCE_BOARDS = 3
GLUE_FLAP_MM = 12.0
ORIENTATION_WORDS = "front — shopper side"
MARK_MM = 4.0
#: the bleed every part's cut outline is offset by (mitre); the die's words stand clear of it
DIE_BLEED_MM = 3.0
DIE_FACE = ("drawn from the print side (the printed face toward you): the tray is seen from below, so its x runs "
            "left to right as the shopper sees it (x = X − centre); the platforms and the slot insert are seen from "
            "above, so theirs runs mirrored (x = centre − X), their front legs at the top of the sheet")


# =====================================================================================================================
# the solve
# =====================================================================================================================


def _merge(base: dict, over: dict | None) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


def _r(value, nd=4):
    return round(float(value), nd) + 0.0          # + 0.0: never a negative zero in a record


def _geometry(products: dict, own: dict) -> dict:
    """The solved numbers, plain (mm, degrees). Everything else is built from this."""
    t = float(own["board_mm"])
    W, D = float(own["footprint_width_mm"]), float(own["footprint_depth_mm"])
    pal, lip, balm = products["palette"], products["lipstick"], products["balm"]
    th = math.radians(float(own["slot_lean_deg"]))
    n_pal = int(own["palettes_in_slot"])
    stack = n_pal * pal["thickness_mm"]                       # the stack's thickness, normal to the lids
    sin_t, cos_t = math.sin(th), math.cos(th)
    clearance = house("clearance_mm")
    spine = house("spine_mm")

    # -- heights above the tray floor's top (h) -------------------------------------------------------------------------
    bed_low_h = float(own["slot_floor_mm"])                   # the bed's top at the bed/backrest junction
    stack_top_h = bed_low_h + stack * sin_t + pal["height_mm"] * cos_t
    back_wall_h = stack_top_h                                 # "the back wall as tall as the leaning palette's top"
    front_skin_h = float(own["front_wall_mm"]) - t            # the owner's 20 mm is the outer height over the counter

    # -- depths --------------------------------------------------------------------------------------------------------
    floor_w, floor_d = W - 2 * t, D - 2 * t                   # crease to crease: the walls stand outside the floor
    y_front_crease, y_back_crease = t, D - t
    # the back, from outside in: the back wall, the side skins' lock tabs, the header's return flap
    back_inner_y = D - 3 * t
    stack_rear_from_b = pal["height_mm"] * sin_t              # back-top corner behind B
    stack_front_from_b = stack * cos_t                        # front-bottom corner in front of B
    allowance = FOLD_ALLOWANCE_BOARDS * t                     # a two-fold spacing may exceed the drawn by 0 … this
    fold_each = allowance / 2                                 # … each of its folds by 0 … half of it
    slot_depth = float(own["slot_depth_mm"])
    backrest = pal["height_mm"] / 2.0
    # the insert's panels do not depend on where it stands: the front leg up to the bed's front edge, the back leg up to
    # the backrest's top, the base between them less the front leg's board (it stands outside the glue flap)
    front_leg, back_leg = bed_low_h + slot_depth * sin_t, bed_low_h + backrest * cos_t
    base = backrest * sin_t + slot_depth * cos_t - t
    # Day 13, D-D13-2: the tube closed square by its gussets leans only as far as the base's two folds let the back leg
    # stand behind its drawn place (2 × one fold's allowance); the stack's top-back corner moves back ``reserve`` at the
    # most of it — measured on the insert drawn with its junction at y = 0 (the move is the same wherever it stands)
    frame = frame_reserve(insert_linkage({
        "t": t, "theta_deg": float(own["slot_lean_deg"]), "f_y": -slot_depth * cos_t, "palette_h": pal["height_mm"],
        "stack_mm": stack, "insert": {"front_leg_mm": front_leg, "bed_mm": slot_depth, "backrest_mm": backrest,
                                      "back_leg_mm": back_leg, "base_mm": base}}), 2 * fold_each)
    # the insert's rearmost seat: one fold + its key's play; and the closed tube's lean on top of it
    set_forward = fold_each + LOCK_PLAY_MM / 2 + frame["reserve"]
    # B: the stack's back-bottom corner = bed/backrest junction, set forward so that at its rearmost seat, leaned as far
    # as its closed tube permits, the stack's top-back corner keeps the house's clearance from the back's inner face
    b_y = back_inner_y - clearance - stack_rear_from_b - set_forward
    p0_y, p0_h = b_y - stack_front_from_b, bed_low_h + stack * sin_t
    f_y, f_h = b_y - slot_depth * cos_t, front_leg                        # the bed's front edge
    r_y, r_h = b_y + backrest * sin_t, back_leg                           # the backrest's top
    insert = {
        "front_leg_mm": f_h, "bed_mm": slot_depth, "backrest_mm": backrest, "back_leg_mm": r_h,
        # the front leg stands outside the glue flap (on the floor, at its keys): the base's front crease, and the glue
        # flap's outer face, one board behind the front leg's outer face
        "base_mm": base, "glue_flap_mm": GLUE_FLAP_MM,
        "width_mm": float(own["slot_width_mm"]) + 2 * t, "wing_mm": slot_depth,
        # D-D13-2: the gussets (builder_provisional.insert_gusset_mm): up the back leg as far as the backrest is long,
        # along the base as far as a wing reaches, the tube's own glue flap
        "gusset_up_mm": backrest, "gusset_along_mm": slot_depth, "gusset_flap_mm": GLUE_FLAP_MM,
        "front_y_mm": f_y, "rear_y_mm": r_y,
    }

    # -- the platforms and rows ----------------------------------------------------------------------------------------
    wall_in_y = spine                                          # the doubled front wall's inner face
    side_in_x = W / 2 - spine                                  # the doubled side walls' inner faces
    # the facing legs: at the full fold allowance (the front platform's back leg that far behind its drawn place) and
    # both keys' play, still 0.5 apart; never less than the house's clearance
    gap = max(clearance, allowance + LOCK_PLAY_MM + 0.5)
    half_holes = (float(own["balm_hole_mm"]) + float(own["lipstick_hole_mm"])) / 2.0
    edge = (float(own["row_spacing_mm"]) - half_holes - gap) / 2.0
    front_plate_d = float(own["balm_hole_mm"]) + 2 * edge
    back_plate_d = float(own["lipstick_hole_mm"]) + 2 * edge
    front_plate_y0 = wall_in_y + clearance
    balm_y = front_plate_y0 + front_plate_d / 2
    lip_y = balm_y + float(own["row_spacing_mm"])
    back_plate_y1 = lip_y + back_plate_d / 2
    plate_len = 2 * (side_in_x - clearance)
    pitch = float(own["pitch_mm"])
    nb, nl = int(own["balm_count"]), int(own["lipstick_count"])
    offset = pitch / 2.0                                       # "offset half a pitch"
    span = (nb - 1) * pitch + offset                           # the twelve centres' span, centred
    balm_x = [-span / 2 + i * pitch for i in range(nb)]
    lip_x = [-span / 2 + offset + i * pitch for i in range(nl)]

    # -- the floor keys: each insert's legs (their board in y) and the tabs keyed into the floor -----------------------
    back_plate_y0 = back_plate_y1 - back_plate_d
    legs = {"front platform": {"front leg": (front_plate_y0, front_plate_y0 + t),
                               "back leg": (front_plate_y0 + front_plate_d - t, front_plate_y0 + front_plate_d)},
            "back platform": {"front leg": (back_plate_y0, back_plate_y0 + t),
                              "back leg": (back_plate_y1 - t, back_plate_y1)},
            "slot insert": {"front leg": (f_y, f_y + t)}}
    keys = floor_keys(legs, t)

    # -- the side skins ------------------------------------------------------------------------------------------------
    skin_y0, skin_y1 = y_front_crease + house("side_start_mm") * (t / 1.5), y_back_crease
    lock_h = back_wall_h / 2.0
    return {
        "legs": legs, "keys": keys, "allowance": allowance, "fold_each": fold_each, "set_forward": set_forward,
        "frame": frame,
        "t": t, "W": W, "D": D, "theta_deg": float(own["slot_lean_deg"]), "sin": sin_t, "cos": cos_t,
        "n_pal": n_pal, "stack_mm": stack, "clearance": clearance, "spine": spine,
        "bed_low_h": bed_low_h, "stack_top_h": stack_top_h, "back_wall_h": back_wall_h, "front_skin_h": front_skin_h,
        "header_h": float(own["header_height_mm"]), "header_w": float(own["header_width_mm"]),
        "floor_w": floor_w, "floor_d": floor_d, "y_front_crease": y_front_crease, "y_back_crease": y_back_crease,
        "back_inner_y": back_inner_y, "b_y": b_y, "p0_y": p0_y, "p0_h": p0_h, "f_y": f_y, "f_h": f_h,
        "r_y": r_y, "r_h": r_h, "stack_rear_y": b_y + stack_rear_from_b, "stack_front_y": p0_y,
        "stack_top_y": p0_y + pal["height_mm"] * sin_t,
        "insert": insert, "wall_in_y": wall_in_y, "side_in_x": side_in_x, "gap": gap, "edge": edge,
        "front_plate_d": front_plate_d, "back_plate_d": back_plate_d, "front_plate_y0": front_plate_y0,
        "balm_y": balm_y, "lip_y": lip_y, "back_plate_y1": back_plate_y1, "plate_len": plate_len,
        "front_plate_h": float(own["front_plate_mm"]), "back_plate_h": float(own["back_plate_mm"]),
        "balm_x": balm_x, "lip_x": lip_x, "pitch": pitch, "offset": offset,
        "balm_hole": float(own["balm_hole_mm"]), "lip_hole": float(own["lipstick_hole_mm"]),
        "palette_h": pal["height_mm"], "liner_tab_h": house("liner_short_mm") + t,
        "skin_y0": skin_y0, "skin_y1": skin_y1, "lock_h": lock_h,
        "return_mm": back_wall_h - house("return_short_mm"),
        "back_flap_depth": house("back_flap_depth_mm") * (skin_y1 - skin_y0) / house("side_run_mm"),
    }


def floor_keys(legs: dict, t: float, layout: dict | None = None) -> list:
    """The floor keys, in plan (x across as the shopper sees it, y depth): every tab on its leg's board, and the slot
    the tray floor gets for it — the tab + ``LOCK_PLAY_MM`` along it (centred: x held on every leg); across it, on a
    ``TIGHT_LEG`` the board + ``LOCK_PLAY_MM`` centred on the leg, on any other leg the same plus the fold allowance
    (``FOLD_ALLOWANCE_BOARDS`` × board) behind it, so a folded spacing of drawn … drawn + allowance seats.
    ``layout`` defaults to ``KEY_LAYOUT`` (a test may plant another)."""
    out = []
    room = FOLD_ALLOWANCE_BOARDS * t
    for part, by_leg in (layout or KEY_LAYOUT).items():
        for leg, tabs in by_leg.items():
            y0, y1 = legs[part][leg]
            kinds = [kind for _x, kind in tabs]
            behind = 0.0 if leg == TIGHT_LEG else room
            for i, (x, kind) in enumerate(tabs):
                w = house(KEY_TAB_HOUSE[kind])
                kid = "%s %s %s" % (part, leg, kind) + ("" if kinds.count(kind) == 1 else " %d" % (i + 1))
                out.append({"id": kid, "part": part, "leg": leg, "kind": kind,
                            "x_mm": x, "width_mm": w, "height_mm": t, "y_mm": (y0, y1), "room_mm": behind,
                            "slot_x_mm": (x - (w + LOCK_PLAY_MM) / 2, x + (w + LOCK_PLAY_MM) / 2),
                            "slot_y_mm": (y0 - LOCK_PLAY_MM / 2, y1 + behind + LOCK_PLAY_MM / 2)})
    return out


def skin_height(g: dict, y: float) -> float:
    """The side skin's height above the floor (h) at depth ``y``: the front wall's height at the front, the back
    wall's at the back (the taper)."""
    k = (y - g["skin_y0"]) / (g["skin_y1"] - g["skin_y0"])
    return g["front_skin_h"] + k * (g["back_wall_h"] - g["front_skin_h"])


def solve(products: dict | None = None, provisional: dict | None = None, *, hole_shape: str = "circle",
          product_grid: dict | None = None) -> dict:
    """The record (die.json, schema counter_tray_header/0.1): every value a fact with its authority and source."""
    if product_grid is not None:
        if products is not None or provisional is not None:
            raise ValueError("A single-product tray cannot mix in the historical family inputs")
        return solve_product_tray(**product_grid)
    _validate_hole_shape(hole_shape)
    P = _merge(default_products(), products)
    O = _merge(default_provisional(), provisional)
    g = _geometry(P, O)
    t = g["t"]
    S = lambda v, words: fact(_r(v), SOLVED, words)              # noqa: E731

    products_rec = {name: {k: fact(v, RECORD, PRODUCT_SOURCES[name]) for k, v in vals.items()}
                    for name, vals in P.items()}
    owner_rec = {k: fact(O[k], OWNER, owner_source(k) +
                         ("" if O[k] == OWNER_NUMBERS[k][0] else " — OVERRIDDEN in this solve"))
                 for k in OWNER_NUMBERS}
    house_rec = {k: fact(v, HOUSE_MEASURED, _ES + where) for k, (v, where) in HOUSE.items()}
    builder_rec = {k: fact(v, BUILDER, BUILDER_CHOICES[k]) for k, v in builder_values(g).items()}

    lean = "%g°" % g["theta_deg"]
    tray = {
        "outer_width_mm": S(g["W"], _D12 + "footprint 250 wide"),
        "outer_depth_mm": S(g["D"], _D12 + "footprint 160 deep"),
        "floor_crease_to_crease_mm": [S(g["floor_w"], "outer width − 2 × board (the side skins stand outside the "
                                                       "floor's creases)"),
                                      S(g["floor_d"], "outer depth − 2 × board (front skin and back wall outside)")],
        "front_wall_outer_mm": S(g["front_skin_h"] + t, _D12 + "the tray's front wall 20 mm, read as its outer "
                                                             "height over the counter"),
        "front_skin_panel_mm": S(g["front_skin_h"], "front wall − board (the floor under it)"),
        "doubled_wall_mm": S(g["spine"], "the house's spine: skin, gap and liner within " + "%g mm" % g["spine"]),
        "back_wall_panel_mm": S(g["back_wall_h"], "= the leaning stack's top above the tray floor: slot floor + "
                                                  "stack × sin %s + palette height × cos %s" % (lean, lean)),
        "back_wall_outer_mm": S(g["back_wall_h"] + t, "back wall panel + board: its top above the counter"),
        # Day 13, D-D13-1: the owner's ruling of this height, recorded beside the solved value (no departure)
        "back_wall_ruling": back_wall_ruling(g, O),
        "header_top_mm": S(g["back_wall_h"] + t + g["header_h"], "back wall outer + header 110"),
        "back_inner_face_y_mm": S(g["back_inner_y"], "outer depth − 3 × board: back wall, lock tabs, return flap"),
        "side_skin_front_mm": S(g["front_skin_h"], "the side tapers from the front wall's height ..."),
        "side_skin_back_mm": S(g["back_wall_h"], "... to the back wall's height"),
        "side_skin_run_mm": S(g["skin_y1"] - g["skin_y0"], "floor depth − the house's 1.50 front offset (one board)"),
        "back_flap_depth_mm": S(g["back_flap_depth"], "ES3083's 78.50 scaled to the side run (%.2f / 196.50)" %
                                (g["skin_y1"] - g["skin_y0"])),
        "lock_tab_height_mm": S(g["lock_h"], "mid-height of the side skin's back edge (ES3083: 38.50 of 77.00)"),
        "header_width_mm": fact(g["header_w"], OWNER, _D12 + "header 250 × 110"),
        "header_leaves": S(2, "doubled, as ES3083's 197 = 2 × 98.50: the rear leaf continues the back wall, the "
                              "front leaf folds over the top and down in front, its printed side to the shopper"),
        "return_flap_mm": S(g["return_mm"], "back wall − 3.00 (ES3083: 83.00 − 80.00): the return lines the back "
                                            "wall's inside, printed side forward"),
        "return_flap_width_mm": S(g["header_w"] - 2 * house("return_inset_mm"), "header − 2 × 5.00 (ES3083)"),
    }
    slot = {
        "width_mm": fact(float(O["slot_width_mm"]), OWNER, owner_rec["slot_width_mm"]["source"]),
        "bed_depth_mm": fact(float(O["slot_depth_mm"]), OWNER, owner_rec["slot_depth_mm"]["source"]),
        "floor_h_mm": fact(g["bed_low_h"], OWNER, owner_rec["slot_floor_mm"]["source"] +
                           " — read as the bed's top at its lowest point (the bed/backrest junction)"),
        "lean_deg": fact(g["theta_deg"], OWNER, owner_rec["slot_lean_deg"]["source"]),
        "palettes": fact(g["n_pal"], OWNER, owner_rec["palettes_in_slot"]["source"]),
        "stack_mm": S(g["stack_mm"], "palettes × thickness 12 (product record)"),
        "stack_top_h_mm": S(g["stack_top_h"], "slot floor + stack × sin + 120 × cos"),
        "stack_depth_footprint_mm": S(g["stack_rear_y"] - g["stack_front_y"], "stack × cos + 120 × sin"),
        "junction_y_mm": S(g["b_y"], "back inner face − house clearance 2.00 − 120 × sin (the stack's top-back "
                                     "corner leans that far behind the junction) − the insert's set-forward "
                                     "%.2f (builder_provisional.insert_set_forward_mm: one fold's allowance %.2f + "
                                     "the key's play 0.25 + %.2f, how far the corner moves back at the closed tube's "
                                     "most lean, %.2f°: so the stack keeps 2.00 at its rearmost seat at every lean)" % (
                                         g["set_forward"], g["fold_each"], g["frame"]["reserve"],
                                         g["frame"]["lean_max"])),
        "front_lid_bottom": {"y_mm": S(g["p0_y"], "junction − stack × cos"),
                             "h_mm": S(g["p0_h"], "slot floor + stack × sin")},
        "stack_top": {"y_mm": S(g["stack_top_y"], "front lid bottom + 120 × sin"),
                      "h_mm": S(g["stack_top_h"], "the front palette's top edge")},
        "stack_rear_y_mm": S(g["stack_rear_y"], "junction + 120 × sin"),
        "stack_rear_y_rearmost_mm": S(g["stack_rear_y"] + g["fold_each"] + LOCK_PLAY_MM / 2,
                                      "at the insert's rearmost seat: + one fold's allowance + the key's play"),
        "stack_rear_y_rearmost_leaned_mm": S(g["stack_rear_y"] + g["set_forward"],
                                             "at the rearmost seat, the closed tube leaned as far as its fit permits "
                                             "(D-D13-2): + the corner's move back %.2f — the back's inner face − 2.00"
                                             % g["frame"]["reserve"]),
        "bed_front_edge": {"y_mm": S(g["f_y"], "junction − 30 × cos"), "h_mm": S(g["f_h"], "slot floor + 30 × sin")},
        "backrest_mm": fact(g["insert"]["backrest_mm"], BUILDER, BUILDER_CHOICES["backrest_mm"]),
        "insert_panels_mm": insert_panel_facts(g),
    }
    platforms = {
        "front": {"plate_top_h_mm": fact(g["front_plate_h"], OWNER, owner_rec["front_plate_mm"]["source"] +
                                         " — read as the plate's top surface"),
                  "plate_depth_mm": S(g["front_plate_d"], "hole Ø + 2 × edge"),
                  "plate_y_mm": [fact(_r(g["front_plate_y0"]), BUILDER, BUILDER_CHOICES["rows_forward"]),
                                 S(g["front_plate_y0"] + g["front_plate_d"], "+ plate depth")],
                  "length_mm": S(g["plate_len"], "between the side liners, house clearance 2.00 each end"),
                  "row_y_mm": S(g["balm_y"], "plate centre"),
                  "legs": "two legs folded down from the plate's front and back edges, each keyed to the floor by two "
                          "flush tabs (keys[]), open below: each balm "
                          "stands through its hole onto the tray floor"},
        "back": {"plate_top_h_mm": fact(g["back_plate_h"], OWNER, owner_rec["back_plate_mm"]["source"] +
                                        " — read as the plate's top surface"),
                 "plate_depth_mm": S(g["back_plate_d"], "hole Ø + 2 × edge"),
                 "plate_y_mm": [S(g["back_plate_y1"] - g["back_plate_d"], "front row + 35 − half the plate"),
                                S(g["back_plate_y1"], "+ plate depth")],
                 "length_mm": S(g["plate_len"], "between the side liners, house clearance 2.00 each end"),
                 "row_y_mm": S(g["lip_y"], "front row + rows 35 apart"),
                 "legs": "two legs folded down from the plate's front and back edges, each keyed to the floor by two "
                          "flush tabs (keys[]), open below: each lipstick "
                         "stands through its hole onto the tray floor"},
        "edge_mm": S(g["edge"], "(rows 35 − (19 + 21) / 2 − gap %.2f) / 2: the largest equal edge margin" % g["gap"]),
        "gap_between_mm": fact(_r(g["gap"]), BUILDER, BUILDER_CHOICES["platform_gap_mm"]),
        "behind_back_platform_mm": S(g["insert"]["front_y_mm"] - g["back_plate_y1"],
                                     "slot insert's front − back plate's back leg: the depth the builder's "
                                     "rows_forward choice leaves over (builder_provisional.rows_forward)"),
        "held_by": "the floor keys (keys[]): each platform fits its floor slots one way round, print side out, and "
                   "at one place, its front leg keyed ±%.2f mm each way; its back leg held in x (±%.2f) and free in "
                   "depth over the fold allowance (drawn … drawn + %.2f)" % (LOCK_PLAY_MM / 2, LOCK_PLAY_MM / 2,
                                                                          g["allowance"]),
    }
    hole_words = ("x as the shopper sees it once the platform stands, keyed; on the flat the hole is drawn at the "
                  "plate's centre − x (the platform is drawn print side up, seen from above: datums.die_face)")
    holes = ([{"row": "front", "product": "balm", "index": i + 1, "x_mm": _r(x), "y_mm": _r(g["balm_y"]),
               "diameter_mm": _r(g["balm_hole"]), "flat_x_from_plate_centre_mm": _r(-x), "x_words": hole_words}
              for i, x in enumerate(g["balm_x"])] +
             [{"row": "back", "product": "lipstick", "index": i + 1, "x_mm": _r(x), "y_mm": _r(g["lip_y"]),
               "diameter_mm": _r(g["lip_hole"]), "flat_x_from_plate_centre_mm": _r(-x), "x_words": hole_words}
              for i, x in enumerate(g["lip_x"])])
    keys = [{"id": k["id"], "part": k["part"], "leg": k["leg"], "kind": k["kind"],
             "x_mm": fact(_r(k["x_mm"]), BUILDER, BUILDER_CHOICES["floor_keys"]),
             "tab_width_mm": fact(_r(k["width_mm"]), HOUSE_MEASURED, _ES + HOUSE[KEY_TAB_HOUSE[k["kind"]]][1]),
             "tab_height_mm": fact(_r(k["height_mm"]), BUILDER, BUILDER_CHOICES["key_tab_height_mm"]),
             "leg_y_mm": [S(v, "the leg's board (its outer and inner faces)") for v in k["y_mm"]],
             "floor_slot_mm": {"x": [S(v, "tab ± (tab + 0.5) / 2") for v in k["slot_x_mm"]],
                               "y": [S(v, w) for v, w in zip(k["slot_y_mm"], (
                                   "the leg's front face − 0.25",
                                   "the leg's back face + 0.25" if not k["room_mm"] else
                                   "the leg's back face + the fold allowance %.2f + 0.25" % k["room_mm"]))]},
             "room_behind_mm": fact(_r(k["room_mm"]), BUILDER, BUILDER_CHOICES["fold_allowance_mm"]),
             "flat_x_from_centre_mm": _r(-k["x_mm"])} for k in g["keys"]]
    sticks = ([{"product": "balm", "index": i + 1, "x_mm": _r(x), "y_mm": _r(g["balm_y"]),
                "z_bottom_mm": _r(t), "z_top_mm": _r(t + P["balm"]["height_mm"]),
                "z_cap_from_mm": _r(t + P["balm"]["body_mm"])} for i, x in enumerate(g["balm_x"])] +
              [{"product": "lipstick", "index": i + 1, "x_mm": _r(x), "y_mm": _r(g["lip_y"]),
                "z_bottom_mm": _r(t), "z_top_mm": _r(t + P["lipstick"]["height_mm"]),
                "z_cap_from_mm": _r(t + P["lipstick"]["body_mm"])} for i, x in enumerate(g["lip_x"])])
    record = {
        "schema": SCHEMA,
        "template": {"id": TEMPLATE_ID, "version": VERSION, "provisional": True, "production_ready": False,
                     "decision": DECISION, "registered": True,
                     "status": "%s ⟪PROVISIONAL⟫ — never production" % VERSION,
                     "registration": REGISTRATION},
        "datums": {
            "z": "height above the counter (the tray's underside, z = 0)",
            "h": "height above the tray floor's top surface (z = board + h)",
            "y": "depth from the tray's front outer face (y = 0), positive toward the back",
            "x": "across, 0 at the centre",
            "panels": "tray: creases at the inside corners (outer = crease-to-crease + 2 × board); inserts: panel "
                      "lengths are the erected outer-surface lengths, no board compensation (⟪PROVISIONAL⟫) — the "
                      "fold allowance is stated instead: a folded spacing from a keyed front leg may exceed the drawn "
                      "by 0 … %g × board (builder_provisional.fold_allowance_mm), taken up by the back legs' key "
                      "slots and by the insert's set-forward" % FOLD_ALLOWANCE_BOARDS,
            "die_face": DIE_FACE,
            "authority": "a value that IS a builder's choice carries builder_provisional (e.g. the front plate's "
                         "place, rows_forward); a value derived from one carries solved and names the builder's input "
                         "in its source (the junction from insert_set_forward_mm, the insert's base from "
                         "glue_flap_mm, the depth behind the back platform from rows_forward)",
        },
        "products": products_rec,
        "owner_provisional": owner_rec,
        "house": house_rec,
        "builder_provisional": builder_rec,
        "board": {"drawn_mm": fact(t, OWNER, owner_rec["board_mm"]["source"] + " — 1.5 mm E-flute is the drawn "
                                             "case"),
                  "alternative_mm": fact(O["board_alternative_mm"], OWNER, owner_rec["board_alternative_mm"]
                                         ["source"] + " — listed, not drawn")},
        "tray": tray,
        "slot": slot,
        "platforms": platforms,
        "holes": holes,
        "keys": keys,
        "sticks": sticks,
        "departures": departures(g, O),
    }
    if hole_shape != "circle":
        record["hole_shape"] = hole_shape
        for hole in holes:
            hole["shape"] = hole_shape
            hole["side_mm"] = hole.pop("diameter_mm")
    return record


def builder_values(g: dict) -> dict:
    """Every builder's ⟪PROVISIONAL⟫ choice with the value it gives in this solve (never null)."""
    return {
        "backrest_mm": _r(g["insert"]["backrest_mm"]),
        "glue_flap_mm": _r(g["insert"]["glue_flap_mm"]),
        "wing_mm": _r(g["insert"]["wing_mm"]),
        "minimum_web_mm": _r(3 * g["t"]),
        "platform_gap_mm": _r(g["gap"]),
        "fold_allowance_mm": {"boards": FOLD_ALLOWANCE_BOARDS, "leg_spacing_mm": [0.0, _r(g["allowance"])],
                              "each_fold_mm": [0.0, _r(g["fold_each"])], "tray_rule_mm": _r(2 * g["t"])},
        "insert_set_forward_mm": _r(g["set_forward"]),
        "insert_gusset_mm": {"up_the_back_leg_mm": _r(g["insert"]["gusset_up_mm"]),
                             "along_the_base_mm": _r(g["insert"]["gusset_along_mm"]),
                             "glue_flap_mm": _r(g["insert"]["gusset_flap_mm"]), "per_end": 1, "printed": False},
        "rows_forward": {"front_plate_y_mm": _r(g["front_plate_y0"]),
                         "left_behind_back_platform_mm": _r(g["insert"]["front_y_mm"] - g["back_plate_y1"])},
        "lock_slot_rule": {"slot_minus_tab_mm": LOCK_PLAY_MM, "key_play_each_way_mm": LOCK_PLAY_MM / 2,
                           "back_leg_slot_across_mm": _r(g["t"] + g["allowance"] + LOCK_PLAY_MM)},
        "floor_keys": {part: {leg: [{"x_mm": x, "kind": kind, "width_mm": house(KEY_TAB_HOUSE[kind])}
                                    for x, kind in tabs] for leg, tabs in by_leg.items()}
                       for part, by_leg in KEY_LAYOUT.items()},
        "key_tab_height_mm": _r(g["t"]),
        "liner_tab_height_mm": _r(g["liner_tab_h"]),
        "orientation_mark": ORIENTATION_WORDS,
    }


def back_wall_ruling(g: dict, own: dict) -> dict:
    """[D-D13-1] The owner's ruling of the back wall's height beside the solved one: the solve still finds it from the
    slot (the leaning stack's top); his figures are that height to his precision, so they must agree to it."""
    ruled, ruled_outer = float(own["back_wall_mm"]), BACK_WALL_RULED_OUTER_MM
    solved, solved_outer = g["back_wall_h"], g["back_wall_h"] + g["t"]
    return {"decision": _D13_1.rstrip(": "), "words": BACK_WALL_RULING,
            "panel_mm": fact(ruled, OWNER, owner_source("back_wall_mm")),
            "outer_mm": fact(ruled_outer, OWNER, owner_source("back_wall_mm")),
            "solved_panel_mm": _r(solved), "solved_outer_mm": _r(solved_outer),
            "agrees": abs(round(solved, 2) - ruled) < 1e-9 and abs(round(solved_outer, 2) - ruled_outer) < 1e-9,
            "departure": "none — the owner's \"about 245\" (D-D12-2) is corrected by his own words; the departure "
                         "back_wall_245 is removed from departures"}


def insert_panel_facts(g: dict) -> dict:
    """The slot insert's panels, each with its own authority (the reviewer's MINOR 3: no builder value as solved)."""
    ins = g["insert"]
    lean = "%g°" % g["theta_deg"]
    words = {
        "front_leg_mm": (SOLVED, "the bed's front edge above the floor: slot floor + 30 × sin %s" % lean),
        "bed_mm": (OWNER, _D12 + "\"one slot 194 wide × 30 deep\""),
        "backrest_mm": (BUILDER, BUILDER_CHOICES["backrest_mm"]),
        "back_leg_mm": (SOLVED, "the backrest's top above the floor: slot floor + 60 × cos %s" % lean),
        "base_mm": (SOLVED, "the backrest's top y − the bed's front edge y − board: the tube's footprint less the "
                            "front leg's board, which stands outside the glue flap (builder_provisional.glue_flap_mm)"),
        "glue_flap_mm": (BUILDER, BUILDER_CHOICES["glue_flap_mm"]),
        "width_mm": (SOLVED, "the owner's slot 194 + 2 × board (the wings fold inside it)"),
        "wing_mm": (BUILDER, BUILDER_CHOICES["wing_mm"]),
        "gusset_up_mm": (BUILDER, BUILDER_CHOICES["insert_gusset_mm"]),
        "gusset_along_mm": (BUILDER, BUILDER_CHOICES["insert_gusset_mm"]),
        "gusset_flap_mm": (BUILDER, BUILDER_CHOICES["insert_gusset_mm"]),
        "front_y_mm": (SOLVED, "junction − 30 × cos %s (the bed's front edge, the front leg's outer face)" % lean),
        "rear_y_mm": (SOLVED, "junction + 60 × sin %s (the backrest's top, the back leg's outer face)" % lean),
    }
    return {k: fact(_r(v), words[k][0], words[k][1]) for k, v in ins.items()}


def departures(g: dict, own: dict) -> list:
    # Day 13, D-D13-1: the back wall's height is the owner's ruling, not a departure (tray.back_wall_ruling): the entry
    # back_wall_245 that stood first here is removed
    return [
        {"id": "header_doubled", "owner": "header 250 × 110 above the back wall",
         "built": "250 × 110, doubled (rear leaf + front leaf, folded at the top) with a %.2f mm return flap down the "
                  "back wall's inside" % g["return_mm"],
         "why": "ES3083's header is 197 = 2 × 98.50 with its fold at mid-height and an 80 mm return 3 mm shorter than "
                "its 83 mm back wall: read as a doubled header whose front leaf shows its printed side to the shopper. "
                "A reading of the vectors, not of a picture."},
        {"id": "header_crest", "owner": "—", "built": "a straight top fold",
         "why": "ES3083's top fold rises into a shaped crest (a 61-segment crease, 201.29 × 67.07 mm). Its outline "
                "belongs to that design's artwork; the owner's header is a 250 × 110 rectangle. Not carried."},
        {"id": "side_taper_offsets", "owner": "side walls tapering from the front wall's height to the back wall's",
         "built": "exactly that: %.2f → %.2f above the floor" % (g["front_skin_h"], g["back_wall_h"]),
         "why": "ES3083's sides stand +0.42 above its front wall and 6.00 below its back wall; those offsets are not "
                "carried — the owner's words set the ends."},
        {"id": "sticks_on_floor", "owner": "each stick stands through its hole onto the floor (two supports)",
         "built": "the platforms are open below (two legs each); the plates locate, the floor carries",
         "why": "So raising the back platform cannot lift a lipstick; as a sightline remedy it only changes how much "
                "body shows. The remedy search says so when it runs."},
        {"id": "insert_allowances", "owner": "—",
         "built": "slot insert and platforms drawn at outer-surface lengths; the fold allowance stated, not "
                  "compensated: a platform's leg spacing 0 … %.2f mm (%d × board) over drawn, 0 … %.2f per fold" % (
                      g["allowance"], FOLD_ALLOWANCE_BOARDS, g["fold_each"]),
         "why": "No board compensation on the inserts until a sample is folded (⟪PROVISIONAL⟫); the tray carries the "
                "house's allowances (back wall inset 1.50, side start 1.50, liner 2.00 short). The reviewer's MJ-1: "
                "the keys' ±0.25 hung on a fold allowance the die did not state. Now stated (the lead's %d × board; "
                "the tray's own rule, outer = crease-to-crease + 2 × board = %.2f, lies inside it) and absorbed: each "
                "front leg keyed tight, each platform's back-leg slot %.2f deeper behind the leg (x still held), so "
                "every folded spacing from drawn to drawn + %.2f seats (the fold check sweeps it; outside it fails); "
                "the platforms' facing legs %.2f apart so the front platform's back leg at the full allowance and "
                "the worst play still clears the back platform by 0.50 (the plates' edge margin %.2f, still >= 3 × "
                "board; a hole row, one fold behind its keyed leg, drifts at most %.2f and its sticks still clear the "
                "back leg's open slot); the slot insert set forward %.2f (one fold's allowance + key play + the "
                "stack corner's %.2f move at the closed tube's most lean, D-D13-2) so the stack keeps the house's "
                "2.00 from the back at its rearmost seat at every lean." % (
                    FOLD_ALLOWANCE_BOARDS, 2 * g["t"], g["allowance"], g["allowance"], g["gap"], g["edge"],
                    g["fold_each"], g["set_forward"], g["frame"]["reserve"])},
        {"id": "insert_glue_flap", "owner": "—",
         "built": "the slot insert's glue flap glued to the inside of its front leg; the base %.2f (the footprint "
                  "%.2f less the front leg's board)" % (g["insert"]["base_mm"], g["r_y"] - g["f_y"]),
         "why": "The reviewer's MJ-1: the base was drawn the whole footprint long, so its front crease and the glue "
                "flap took the board the front leg's keys stand in; with the front leg outside the glue flap the "
                "insert seated a board further back (stack clearance 2.00 → 0.50). The front leg must stand outside "
                "(its foot on the floor, in its key slots); the base is one board shorter, so the glue flap rises "
                "against the front leg's inner face (fold check insert_glue_flap_vs_front_leg)."},
        {"id": "insert_print_side_in", "owner": "—",
         "built": "the slot insert keyed on one leg only (its back leg's foot is creased to the base: no free edge)",
         "why": "The reviewer's MINOR 1: folded print side in, a part is its own mirror image. Mirrored across (its "
                "front leg still at the front) the insert's keys fit nowhere; mirrored front to back (print side in "
                "and turned) its one row of keys is the same row, so the keys alone cannot refuse it — it is refused "
                "by its footprint: wherever those keys seat, its base lies over the back platform (fold check "
                "key_rejects_print_side_in:slot insert, a documented departure, tested)."},
        {"id": "lock_slot_rule", "owner": "—", "built": "lock slot = tab + 0.5 mm",
         "why": BUILDER_CHOICES["lock_slot_rule"]},
        {"id": "relief_arcs", "owner": "—", "built": "square corners at the front corner flaps and the back flaps",
         "why": "ES3083 cuts relief arcs there, half circles of R %.2f (measured: house.relief_arc_radius_mm), a "
                "cutting detail; not carried, the clearances are kept." % house("relief_arc_radius_mm")},
        {"id": "lock_shoulder_curves", "owner": "—",
         "built": "the side lock tab's shoulder-to-tip edges drawn straight (the chord between the same end points)",
         "why": "ES3083 curves them (each a Bézier in a %.2f × %.2f mm box, measured); the chord keeps the head, "
                "shoulder and tip widths and heights exactly. Drawing the curve would mean copying the reference's "
                "control points (tracing its outline), which its tier forbids." % (
                    house("lock_shoulder_curve_w_mm"), house("lock_shoulder_curve_h_mm"))},
        {"id": "side_liner_edge", "owner": "—",
         "built": "the side liner's free edge %.2f mm short of the floor crease along its whole run (the front "
                  "liner's measured 2.00)" % house("liner_short_mm"),
         "why": "ES3083's side liner edge, reflected back across its spine, runs from %.2f short of the floor at its "
                "front to %.2f past it at its back (a straight edge, its tabs 5.00 beyond it): it is not the floor "
                "line reflected. Ours is, %.2f short, so the liner never fouls the floor." % (
                    house("side_liner_short_front_mm"), -house("side_liner_short_back_mm"),
                    house("liner_short_mm"))},
        {"id": "floor_keys", "owner": "—",
         "built": "each platform and the slot insert keyed to the floor: %s" % "; ".join(
             "%s %s: %s" % (part, leg, ", ".join("%s %.2f at x %+g" % (kind, house(KEY_TAB_HOUSE[kind]), x)
                                                 for x, kind in tabs))
             for part, by_leg in KEY_LAYOUT.items() for leg, tabs in by_leg.items()),
         "why": "The reviewer's M1: nothing held the platforms or the slot insert, and the sightline depends on where "
                "they sit. Flush tabs (%.2f long = the board) in floor slots of tab + 0.5 along; across, board + 0.5 "
                "on a front leg (keyed tight) and board + %.2f + 0.5 on a platform's back leg (the fold allowance "
                "behind it): each part fits one way round, print side out, and at one place, ±%.2f mm each way (the "
                "fold check's key_* findings, with turned-round, print-side-in and swapped controls, and the seat "
                "swept across the fold allowance)." % (g["t"], g["allowance"], LOCK_PLAY_MM / 2)},
        {"id": "platform_racking", "owner": "—",
         "built": "each platform an open channel (plate and two legs), held in depth at its feet by its keys; nothing "
                  "closes the channel",
         "why": "The reviewer's MJ-1: \"an open-ended channel can rack\". The keys hold the feet, not the plate: its "
                "leg creases and its key tabs' fit are all that keep it square (a flush 1.5 × 1.5 tab leans in its "
                "2.0 slot to about 25.5°; the plate then stands up to 8.62 / 12.93 mm off its feet). Not modelled as a "
                "pose; measured in fold-check.json's racking, and the sightline is searched to 20 mm in depth with no "
                "sample lost. Squareness is the folded sample's to show (⟪PROVISIONAL⟫)."},
        _insert_sway_departure(g),
        {"id": "liner_tabs_flush", "owner": "—",
         "built": "the six wall-liner tabs (front 2, sides 4) %.2f long: the liner's %.2f short + the %.2f board, so "
                  "each tip, folded through its floor slot, stops flush with the floor's underside (z = 0); base "
                  "%.2f and tip %.2f kept from the house" % (g["liner_tab_h"], house("liner_short_mm"), g["t"],
                                                              house("tab_base_mm"), house("tab_tip_mm")),
         "why": "ES3083's liner tabs are %.2f long (measured: house.tab_height_mm, kept in the record and re-checked "
                "against the walk). Carried over, they reached %.2f mm below the tray's underside (the liner's free "
                "edge %.2f above the floor's top, the tab %.2f below that, the underside %.2f below the top), so the "
                "tray would stand on six tab tips unless they fold under or crush (the geometry verifier's minor). "
                "Shortened to flush; nothing else moves: no printed face, no other panel, no slot, the sheet (the "
                "tabs lie inside the tray's bounds), the fold check's other findings and the sightline (its scene "
                "has no tabs). The fold check's tab_tip_vs_underside:* findings read every wall tab's folded tip "
                "off the drawn die." % (house("tab_height_mm"), house("tab_height_mm") - house("liner_short_mm") -
                                        g["t"], house("liner_short_mm"), house("tab_height_mm"), g["t"])},
        {"id": "die_words_layer", "owner": "—",
         "built": "every die word (part labels, title, the bar and its words, the folder's marks) in a WORDS layer "
                  "that never prints; the folder's mark on the front leg's reverse face, drawn flipped top to bottom",
         "why": "The reviewer's MINOR 2: the words were text in no layer (they would print) and the mark sat on the "
                "front leg's print face, which faces the shopper, upside down when stood. Bleed and safe guides in "
                "the house's greys (#8C8C8C, #B3B3B3; svg_exporter.py) so they are not read as creases (MINOR 3); "
                "the part labels stand clear of the bleed (MINOR 5)."},
        {"id": "die_face", "owner": "—", "built": DIE_FACE,
         "why": "The die does not change with the face it is drawn from, but x on the flat does: the reviewer's "
                "MINOR 1. die.json's hole x is the shopper's x once stood; the flat x is listed beside it."},
        {"id": "board_alternative", "owner": "1.0 mm card ⟪PROVISIONAL⟫",
         "built": "1.5 mm E-flute drawn; the card case is listed in alternative_board, not drawn", "why": "one die"},
        {"id": "backrest", "owner": "—", "built": "%.0f mm backrest" % g["insert"]["backrest_mm"],
         "why": BUILDER_CHOICES["backrest_mm"]},
        {"id": "rows_forward", "owner": "—",
         "built": "%.2f mm left between the back platform and the slot insert" % (g["insert"]["front_y_mm"] -
                                                                                   g["back_plate_y1"]),
         "why": BUILDER_CHOICES["rows_forward"]},
    ]


# =====================================================================================================================
# the die
# =====================================================================================================================


@dataclass
class Part:
    name: str
    label: str
    faces: list = field(default_factory=list)      # (face name, Polygon, printed)
    creases: list = field(default_factory=list)    # (crease name, LineString)
    holes: list = field(default_factory=list)      # (hole name, (cx, cy), radius) — cut circles inside a face
    slits: list = field(default_factory=list)      # (slit name, LineString) — cut lines that bound no face
    tabs: list = field(default_factory=list)       # {"id", "base": LineString, "polygon", "meets"}
    slots: list = field(default_factory=list)      # {"id", "polygon", "length_mm", "width_mm"}
    joins: list = field(default_factory=list)      # (name, LineString) — in-plane joins: neither cut nor crease
    marks: list = field(default_factory=list)      # (text, (x, y), size, face, side) — words inside a face (WORDS
    #                                                layer); side "reverse": on the face's unprinted side, drawn flipped
    hole_shape: str = "circle"                    # holes store radius or half-side; legacy circle tuples stay valid

    def __post_init__(self):
        _validate_hole_shape(self.hole_shape)

    def hole_polygons(self):
        """The actual opening boundaries, used by fit, safe-area and cut exporters."""
        for name, (x, y), half in self.holes:
            yield name, (_rect(x - half, y - half, x + half, y + half)
                         if self.hole_shape == "square" else Point(x, y).buffer(half, 64))

    def hole_cut_length(self):
        return sum((8.0 if self.hole_shape == "square" else 2 * math.pi) * half
                   for _name, _centre, half in self.holes)

    def outline(self):
        return unary_union([f for _n, f, _p in self.faces])

    def cut_lines(self):
        rings = []
        for _n, f, _p in self.faces:
            rings.append(LineString(f.exterior.coords))
            rings.extend(LineString(i.coords) for i in f.interiors)
        lines = unary_union(rings)
        uncut = [c for _n, c in self.creases] + [j for _n, j in self.joins]
        if uncut:
            lines = lines.difference(unary_union(uncut).buffer(1e-6, cap_style=2))
        merged = linemerge(lines) if lines.geom_type == "MultiLineString" else lines
        out = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
        out += [s for _n, s in self.slits]
        return [ln for ln in out if ln.length > 1e-6]

    def moved(self, dx, dy) -> "Part":
        mv = lambda geom: affinity.translate(geom, dx, dy)  # noqa: E731
        return Part(self.name, self.label,
                    [(n, mv(f), p) for n, f, p in self.faces], [(n, mv(c)) for n, c in self.creases],
                    [(n, (c[0] + dx, c[1] + dy), r) for n, c, r in self.holes], [(n, mv(s)) for n, s in self.slits],
                    [dict(tb, base=mv(tb["base"]), polygon=mv(tb["polygon"])) for tb in self.tabs],
                    [dict(sl, polygon=mv(sl["polygon"])) for sl in self.slots],
                    [(n, mv(j)) for n, j in self.joins],
                    [(m[0], (m[1][0] + dx, m[1][1] + dy)) + tuple(m[2:]) for m in self.marks], self.hole_shape)


def _validate_hole_shape(value):
    if value not in ("circle", "square"):
        raise ValueError("A tray opening must be a circle or square")


def _rect(x0, y0, x1, y1):
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])


def _seg(x0, y0, x1, y1):
    return LineString([(x0, y0), (x1, y1)])


def _reflector(p0, direction):
    """Reflection across the line through ``p0`` along ``direction``."""
    dx, dy = direction
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    nx, ny = uy, -ux

    def reflect(pt):
        d = (pt[0] - p0[0]) * nx + (pt[1] - p0[1]) * ny
        return (pt[0] - 2 * d * nx, pt[1] - 2 * d * ny)
    return reflect, (nx, ny)


def _crease_run(fixed, a, b, gaps, vertical):
    """A crease from ``a`` to ``b`` along one axis, interrupted by the ``gaps`` [(g0, g1)]."""
    out, cur = [], a
    for g0, g1 in sorted(gaps):
        if g0 > cur + 1e-9:
            out.append((cur, g0))
        cur = max(cur, g1)
    if b > cur + 1e-9:
        out.append((cur, b))
    return [(_seg(fixed, s, fixed, e) if vertical else _seg(s, fixed, e, fixed)) for s, e in out]


def _tab_polygon(base_mid, along, out, base, tip, height):
    """A lock tab: ``base`` wide on its hinge, ``tip`` wide ``height`` out, centred on ``base_mid``; ``along`` and
    ``out`` are unit vectors (along the hinge, away from the panel)."""
    (mx, my), (ax, ay), (ox, oy) = base_mid, along, out
    hb, ht = base / 2, tip / 2
    pts = [(mx - hb * ax, my - hb * ay), (mx + hb * ax, my + hb * ay),
           (mx + ht * ax + height * ox, my + ht * ay + height * oy),
           (mx - ht * ax + height * ox, my - ht * ay + height * oy)]
    return Polygon(pts), LineString(pts[:2])


def _tray(g: dict) -> Part:
    """The tray in one piece, in its flat frame (X right, Y down; the floor at [0, Fw] × [0, Fd])."""
    t, Fw, Fd = g["t"], g["floor_w"], g["floor_d"]
    spine, short = g["spine"], house("liner_short_mm")
    # the liners' tabs: the house's base and tip; long enough to stop flush with the floor's underside
    # (builder_provisional.liner_tab_height_mm; departures: liner_tabs_flush)
    tab_b, tab_t, tab_h = house("tab_base_mm"), house("tab_tip_mm"), g["liner_tab_h"]
    slot_d = house("slot_depth_mm")
    slot_len = tab_b + 0.5
    part = Part("tray", "TRAY — one piece: floor, doubled front and tapered sides, back wall, doubled header, return")
    cx = Fw / 2

    # -- floor slots ---------------------------------------------------------------------------------------------------
    front_off = house("front_slot_offset_mm") * Fw / house("principal_width_mm")
    front_slots = [(cx - front_off - slot_len / 2, cx - front_off + slot_len / 2),
                   (cx + front_off - slot_len / 2, cx + front_off + slot_len / 2)]
    run0, run1 = g["skin_y0"] - t, g["skin_y1"] - t                  # the side run on the flat (Y)
    run = run1 - run0
    side_c = [run0 + house(k) * run / house("side_run_mm") for k in ("side_slot_centre_1_mm", "side_slot_centre_2_mm")]
    side_slots = [(c - slot_len / 2, c + slot_len / 2) for c in side_c]
    slot_polys = [_rect(a, 0, b, slot_d) for a, b in front_slots]
    slot_polys += [_rect(Fw - slot_d, a, Fw, b) for a, b in side_slots] + [_rect(0, a, slot_d, b) for a, b in side_slots]
    # the floor keys' slots: holes inside the floor (the tray is drawn print side up, seen from below: x = X − Fw/2,
    # y = Y + t)
    key_slots = [(k, _rect(cx + k["slot_x_mm"][0], k["slot_y_mm"][0] - t, cx + k["slot_x_mm"][1],
                           k["slot_y_mm"][1] - t)) for k in g["keys"]]
    floor = _rect(0, 0, Fw, Fd).difference(unary_union(slot_polys + [p for _k, p in key_slots]))
    part.faces.append(("floor", floor, False))
    names = ["front slot L", "front slot R", "side slot R1", "side slot R2", "side slot L1", "side slot L2"]
    for nm, poly in zip(names, slot_polys):
        part.slots.append({"id": nm, "polygon": poly, "length_mm": slot_len, "width_mm": slot_d})
    for k, poly in key_slots:
        part.slots.append({"id": "key slot " + k["id"], "polygon": poly, "length_mm": k["width_mm"] + LOCK_PLAY_MM,
                           "width_mm": t + k["room_mm"] + LOCK_PLAY_MM, "kind": "floor key", "leg": k["leg"],
                           "room_mm": k["room_mm"]})

    # -- the front wall: skin, spine, liner, tabs ------------------------------------------------------------------------
    hs = g["front_skin_h"]
    inset = house("liner_inset_mm")
    part.faces.append(("front skin", _rect(0, -hs, Fw, 0), True))
    part.faces.append(("front spine", Polygon([(0, -hs), (Fw, -hs), (Fw - inset, -hs - spine), (inset, -hs - spine)]),
                       True))
    liner_y1 = -hs - spine - (hs - short)
    part.faces.append(("front liner", _rect(inset, liner_y1, Fw - inset, -hs - spine), True))
    part.creases += [("floor / front skin %d" % (i + 1), s) for i, s in
                     enumerate(_crease_run(0, 0, Fw, front_slots, vertical=False))]
    part.creases.append(("front skin / front spine", _seg(0, -hs, Fw, -hs)))
    part.creases.append(("front spine / front liner", _seg(inset, -hs - spine, Fw - inset, -hs - spine)))
    for side, (a, b) in zip("LR", front_slots):
        poly, base = _tab_polygon(((a + b) / 2, liner_y1), (1, 0), (0, -1), tab_b, tab_t, tab_h)
        part.faces.append(("front liner tab " + side, poly, False))
        part.creases.append(("front liner / tab " + side, base))
        part.tabs.append({"id": "front liner tab " + side, "base": base, "polygon": poly,
                          "meets": "front slot " + side, "width_mm": tab_b})

    # -- the right side (then mirrored) ----------------------------------------------------------------------------------
    right = Part("right", "")
    y0f, y1f = run0, run1                                             # the skin's front and back edges on the flat
    Pa, Pb = (Fw + hs, y0f), (Fw + g["back_wall_h"], y1f)
    skin = Polygon([(Fw, y0f), (Fw, y1f), Pb, Pa])
    right.faces.append(("side skin R", skin, True))
    right.creases += [("floor / side skin R %d" % (i + 1), s) for i, s in
                      enumerate(_crease_run(Fw, y0f, y1f, side_slots, vertical=True))]
    direction = (Pb[0] - Pa[0], Pb[1] - Pa[1])
    _, nrm = _reflector(Pa, direction)
    mid = (Pa[0] + nrm[0] * spine / 2, Pa[1] + nrm[1] * spine / 2)
    refl, _ = _reflector(mid, direction)
    Pa2, Pb2 = refl(Pa), refl(Pb)
    right.faces.append(("side spine R", Polygon([Pa, Pb, Pb2, Pa2]), True))
    right.creases.append(("side skin / side spine R", LineString([Pa, Pb])))
    # the liner in the skin's own coordinates (h = X − Fw, depth Y), then reflected: the free edge 2.00 short of the
    # floor, the back end trimmed clear of the return flap, two tabs into the side slots
    y_trim = g["back_inner_y"] - g["clearance"] - t                    # erected y → flat Y
    h_top = lambda Y: skin_height(g, Y + t)                           # noqa: E731
    # the tabs' hinge points are vertices of the liner's free edge, so liner and tabs share exact points once
    # reflected (one closed outline)
    edge_pts = [(Fw + short, v) for a, b in side_slots for v in ((a + b) / 2 - tab_b / 2, (a + b) / 2 + tab_b / 2)]
    liner_pre = Polygon([(Fw + short, y0f)] + edge_pts + [(Fw + short, y_trim), (Fw + h_top(y_trim), y_trim), Pa])
    liner = Polygon([refl(p) for p in liner_pre.exterior.coords])
    right.faces.append(("side liner R", liner, True))
    right.creases.append(("side spine / side liner R", LineString([Pa2, refl((Fw + h_top(y_trim), y_trim))])))
    for i, (a, b) in enumerate(side_slots):
        c = (a + b) / 2
        pre, _base = _tab_polygon((Fw + short, c), (0, 1), (-1, 0), tab_b, tab_t, tab_h)
        poly = Polygon([refl(p) for p in pre.exterior.coords])
        base = LineString([refl(p) for p in _base.coords])
        nm = "side liner tab R%d" % (i + 1)
        right.faces.append((nm, poly, False))
        right.creases.append(("side liner / tab R%d" % (i + 1), base))
        right.tabs.append({"id": nm, "base": base, "polygon": poly, "meets": "side slot R%d" % (i + 1),
                           "width_mm": tab_b})
    # the corner flap on the skin's front edge
    ci, cg, cl = house("corner_flap_inset_mm"), house("corner_flap_top_gap_mm"), house("corner_flap_length_mm")
    corner = _rect(Fw + ci, y0f - cl, Fw + hs - cg, y0f)
    right.faces.append(("corner flap R", corner, False))
    right.creases.append(("side skin / corner flap R", _seg(Fw + ci, y0f, Fw + hs - cg, y0f)))
    # the lock tab on the skin's back edge, with its two relief slits
    lh = g["lock_h"]
    neck, head, head_at = house("lock_neck_mm"), house("lock_head_mm"), house("lock_head_at_mm")
    sh, sh_at, tip, length = (house("lock_shoulder_mm"), house("lock_shoulder_at_mm"), house("lock_tip_mm"),
                              house("lock_length_mm"))
    lx = Fw + lh
    lock = Polygon([(lx - neck / 2, y1f), (lx - head / 2, y1f + head_at), (lx - sh / 2, y1f + sh_at),
                    (lx - tip / 2, y1f + length), (lx + tip / 2, y1f + length), (lx + sh / 2, y1f + sh_at),
                    (lx + head / 2, y1f + head_at), (lx + neck / 2, y1f)])
    lock_base = _seg(lx - neck / 2, y1f, lx + neck / 2, y1f)
    right.faces.append(("side lock tab R", lock, False))
    right.creases.append(("side skin / lock tab R", lock_base))
    rel = house("lock_relief_mm")
    right.slits += [("lock relief R a", _seg(lx - neck / 2, y1f - rel, lx - neck / 2, y1f)),
                    ("lock relief R b", _seg(lx + neck / 2, y1f - rel, lx + neck / 2, y1f))]
    right.tabs.append({"id": "side lock tab R", "base": lock_base, "polygon": lock, "meets": "lock slot R",
                       "width_mm": head})

    left = Part("left", "")
    mirror = lambda geom: affinity.scale(geom, xfact=-1, yfact=1, origin=(cx, 0))  # noqa: E731
    flip = lambda s: s.replace(" R", " L")                                           # noqa: E731
    left.faces = [(flip(n), mirror(f), p) for n, f, p in right.faces]
    left.creases = [(flip(n), mirror(c)) for n, c in right.creases]
    left.slits = [(flip(n), mirror(s)) for n, s in right.slits]
    left.tabs = [dict(tb, id=flip(tb["id"]), meets=flip(tb["meets"]), base=mirror(tb["base"]),
                      polygon=mirror(tb["polygon"])) for tb in right.tabs]
    for side in (right, left):
        part.faces += side.faces
        part.creases += side.creases
        part.slits += side.slits
        part.tabs += side.tabs

    # -- the back wall, its side flaps and lock slots --------------------------------------------------------------------
    bi = house("back_inset_mm") * t / 1.5
    bh = g["back_wall_h"]
    bx0, bx1 = bi, Fw - bi
    lock_len = head + 0.5
    lw, lin = house("lock_slot_width_mm"), house("lock_slot_into_body_mm")
    lock_slots = {"R": _rect(bx1 - lin, Fd + lh - lock_len / 2, bx1 - lin + lw, Fd + lh + lock_len / 2),
                  "L": _rect(bx0 + lin - lw, Fd + lh - lock_len / 2, bx0 + lin, Fd + lh + lock_len / 2)}
    holes = unary_union(list(lock_slots.values()))
    part.faces.append(("back wall", _rect(bx0, Fd, bx1, Fd + bh).difference(holes), True))
    part.creases.append(("floor / back wall", _seg(bx0, Fd, bx1, Fd)))
    fd, fb = g["back_flap_depth"], house("back_flap_bottom_mm")
    top_at = lambda w: skin_height(g, g["skin_y1"] - w) - g["clearance"]  # noqa: E731
    for side, sgn, x_h in (("R", 1, bx1), ("L", -1, bx0)):
        flap = Polygon([(x_h, Fd + fb), (x_h + sgn * fd, Fd + fb), (x_h + sgn * fd, Fd + top_at(fd)),
                        (x_h, Fd + top_at(0))]).difference(holes)
        part.faces.append(("back flap " + side, flap, False))
        part.creases += [("back wall / back flap %s %d" % (side, i + 1), s) for i, s in enumerate(
            _crease_run(x_h, Fd + fb, Fd + top_at(0), [(Fd + lh - lock_len / 2, Fd + lh + lock_len / 2)],
                        vertical=True))]
        part.slots.append({"id": "lock slot " + side, "polygon": lock_slots[side], "length_mm": lock_len,
                           "width_mm": lw})

    # -- the header: rear leaf, top fold, front leaf, return flap ------------------------------------------------------
    hw, hh = g["header_w"], g["header_h"]
    hx0, hx1 = cx - hw / 2, cx + hw / 2
    y_b = Fd + bh
    part.faces.append(("header rear leaf", _rect(hx0, y_b, hx1, y_b + hh), True))
    part.creases.append(("back wall / header rear leaf", _seg(bx0, y_b, bx1, y_b)))
    part.faces.append(("header front leaf", _rect(hx0, y_b + hh, hx1, y_b + 2 * hh), True))
    part.creases.append(("header top fold", _seg(hx0, y_b + hh, hx1, y_b + hh)))
    y_r = y_b + 2 * hh
    ri, rc, rr = house("return_inset_mm"), house("return_chamfer_y_mm"), house("return_corner_radius_mm")
    rl = g["return_mm"]
    pts = [(hx0, y_r), (hx1, y_r), (hx1 - ri, y_r + rc), (hx1 - ri, y_r + rl - rr)]
    pts += [(hx1 - ri - rr + rr * math.cos(a), y_r + rl - rr + rr * math.sin(a))
            for a in [math.pi * k / 32 for k in range(1, 16)]]
    pts += [(hx1 - ri - rr, y_r + rl), (hx0 + ri + rr, y_r + rl)]
    pts += [(hx0 + ri + rr - rr * math.sin(a), y_r + rl - rr + rr * math.cos(a))
            for a in [math.pi * k / 32 for k in range(1, 16)]]
    pts += [(hx0 + ri, y_r + rl - rr), (hx0 + ri, y_r + rc)]
    part.faces.append(("return flap", Polygon(pts), True))
    part.creases.append(("header front leaf / return flap", _seg(hx0, y_r, hx1, y_r)))
    return part


def _insert(g: dict) -> Part:
    """The slot insert: a closed tube (front leg, bed, backrest, back leg, base, glue flap) with two wings on the
    backrest's edges that stand on the bed and hold the slot's width, and (D-D13-2) a gusset on each of the back leg's
    side edges that closes the tube's open end square."""
    ins = g["insert"]
    w = ins["width_mm"]
    part = Part("slot insert", "SLOT INSERT — the palettes' trough (bed %g°, backrest, wings, gussets)" %
                g["theta_deg"])
    order = [("front leg", ins["front_leg_mm"], True), ("bed", ins["bed_mm"], True),
             ("backrest", ins["backrest_mm"], True), ("back leg", ins["back_leg_mm"], False),
             ("base", ins["base_mm"], False), ("glue flap", ins["glue_flap_mm"], False)]
    y = 0.0
    for i, (name, length, printed) in enumerate(order):
        part.faces.append((name, _rect(0, y, w, y + length), printed))
        if i:
            part.creases.append(("%s / %s" % (order[i - 1][0], name), _seg(0, y, w, y)))
        if name == "backrest":
            for side, x0, x1, xh in (("L", -ins["wing_mm"], 0, 0), ("R", w, w + ins["wing_mm"], w)):
                part.faces.append(("wing " + side, _rect(x0, y, x1, y + length), True))
                part.creases.append(("backrest / wing " + side, _seg(xh, y, xh, y + length)))
        if name == "base":
            _gussets(part, ins, w, y)
        y += length
    # the floor keys on the front leg's free edge (its foot, flat Y = 0), and the orientation mark on the leg
    _key_tabs(part, g, w / 2, {"front leg": (0.0, -1)})
    _orientation_mark(part, w / 2, 0.0, ins["front_leg_mm"])
    return part


def _gussets(part: Part, ins: dict, w: float, y_foot: float):
    """[D-D13-2] The tube's two open ends closed square: on each of the back leg's side edges (X = 0, X = ``w``), from
    its foot (the back leg / base crease, flat Y = ``y_foot``) up ``gusset_up_mm``, a right triangle reaching
    ``gusset_along_mm`` out from the edge — folded in across the tube's end it stands on the base, its free leg along
    the base toward the front leg — and on that free leg its glue flap, which folds in flat onto the base's top inside
    the tube and is glued there. Both unprinted. The flap's edge against the base's side edge is cut (a slit, not a
    crease): only the gusset's two creases hinge it."""
    up, along, flap = ins["gusset_up_mm"], ins["gusset_along_mm"], ins["gusset_flap_mm"]
    for side, xh, sgn in (("L", 0.0, -1), ("R", w, 1)):
        xo = xh + sgn * along
        part.faces.append(("gusset " + side, Polygon([(xh, y_foot - up), (xh, y_foot), (xo, y_foot)]), False))
        part.creases.append(("back leg / gusset " + side, _seg(xh, y_foot - up, xh, y_foot)))
        part.faces.append(("gusset flap " + side, _rect(min(xh, xo), y_foot, max(xh, xo), y_foot + flap), False))
        part.creases.append(("gusset / gusset flap " + side, _seg(min(xh, xo), y_foot, max(xh, xo), y_foot)))


def _key_tabs(part: Part, g: dict, xc: float, feet: dict):
    """The floor key tabs of one insert, drawn on its flat: ``feet`` maps a leg to (its free edge's flat Y, the
    direction the tab grows in Y). The insert is drawn print side up and seen from above, so a key at x (as the
    shopper sees it) is drawn at X = ``xc`` − x. Each tab is coplanar with its leg: joined, never creased."""
    t = g["t"]
    for k in g["keys"]:
        if k["part"] != part.name:
            continue
        y_edge, sgn = feet[k["leg"]]
        X0, X1 = xc - k["x_mm"] - k["width_mm"] / 2, xc - k["x_mm"] + k["width_mm"] / 2
        poly = _rect(X0, min(y_edge, y_edge + sgn * t), X1, max(y_edge, y_edge + sgn * t))
        base = _seg(X0, y_edge, X1, y_edge)
        name = "key tab " + k["id"][len(part.name) + 1:]
        part.faces.append((name, poly, False))
        part.joins.append((name, base))
        part.tabs.append({"id": "key tab " + k["id"], "base": base, "polygon": poly, "meets": "key slot " + k["id"],
                          "width_mm": k["width_mm"], "kind": "floor key", "leg": k["leg"],
                          "slot_width_mm": t + k["room_mm"] + LOCK_PLAY_MM, "room_mm": k["room_mm"]})


def _orientation_mark(part: Part, xc: float, y0: float, leg: float):
    """The words "front — shopper side" centred on the front leg (flat Y ∈ [y0, y0 + leg]) on its REVERSE face: the
    die is drawn from the print side, so the words are drawn flipped top to bottom (their tops toward the plate, +Y):
    on the unprinted face they read upright with the plate (bed) above the leg — as the folder holds the part, and as
    it stands, seen from behind the leg. (x, y) is the baseline's left end as drawn; ``mark_box`` gives the box."""
    width = label_width(ORIENTATION_WORDS, MARK_MM)
    part.marks.append((ORIENTATION_WORDS, (xc - width / 2, y0 + leg / 2 - 0.35 * MARK_MM), MARK_MM, "front leg",
                       "reverse"))


def mark_box(mark) -> Polygon:
    """A mark's box on the flat (die mm): from its baseline's left end, ``label_width`` long; up the sheet (−Y) for a
    mark set on the print side, down the sheet (+Y, flipped) for one on the reverse face."""
    text, (x, y), size = mark[0], mark[1], mark[2]
    side = mark[4] if len(mark) > 4 else "print"
    w = label_width(text, size)
    return _rect(x, y - size, x + w, y + 0.3 * size) if side != "reverse" else _rect(x, y - 0.3 * size, x + w,
                                                                                         y + size)


def _platform(g: dict, which: str) -> Part:
    front = which == "front"
    d = g["front_plate_d"] if front else g["back_plate_d"]
    leg = g["front_plate_h"] if front else g["back_plate_h"]
    hole = g["balm_hole"] if front else g["lip_hole"]
    xs = g["balm_x"] if front else g["lip_x"]
    L = g["plate_len"]
    part = Part("%s platform" % which, "%s PLATFORM — %d %s holes Ø %g, plate %g mm up" % (
        which.upper(), len(xs), "balm" if front else "lipstick", hole, leg))
    part.hole_shape = g.get("hole_shape", "circle")
    _validate_hole_shape(part.hole_shape)
    if part.hole_shape == "square":
        part.label = part.label.replace("holes Ø", "square holes, side")
    part.faces.append(("front leg", _rect(0, 0, L, leg), True))
    part.faces.append(("plate", _rect(0, leg, L, leg + d), True))
    part.faces.append(("back leg", _rect(0, leg + d, L, 2 * leg + d), False))
    part.creases.append(("front leg / plate", _seg(0, leg, L, leg)))
    part.creases.append(("plate / back leg", _seg(0, leg + d, L, leg + d)))
    # drawn print side up (the plate seen from above, the front leg at the top of the sheet): stood with its front leg
    # toward the shopper, a hole drawn at X stands at x = L/2 − X — so the hole for x is drawn at L/2 − x
    for i, x in enumerate(xs):
        part.holes.append(("hole %d" % (i + 1), (L / 2 - x, leg + d / 2), hole / 2))
    _key_tabs(part, g, L / 2, {"front leg": (0.0, -1), "back leg": (2 * leg + d, 1)})
    _orientation_mark(part, L / 2, 0.0, leg)
    return part


@dataclass
class Die:
    parts: list
    sheet_w: float
    sheet_h: float
    labels: list          # (text, (x, y), size) — x, y the text's baseline start, mm
    bar: tuple            # (x, y, length) — the 50 mm calibration bar
    title: str


SHEET_MARGIN_MM = 25.0
PART_GAP_MM = 20.0
LABEL_MM = 6.0
#: the title's and the bar's words (mm), and the bar's words
BAR_WORDS_MM = 4.0
BAR_WORDS = "50 mm — print at 100 %: this bar measures 50 mm"


def build_die(record_or_g) -> Die:
    """The flat die on one sheet: the tray, then the slot insert and the two platforms in a column to its right."""
    if record_or_g.get("schema") == PRODUCT_GRID_SCHEMA:
        return build_product_tray_die(record_or_g)
    if record_or_g.get("schema") == "counter_tray_header/product-grid-2":     # 1.0: apps.dielines.geometry.counter_display
        from . import counter_display
        return counter_display.build_die(record_or_g)
    g = record_or_g if "floor_w" in record_or_g else _g_from_record(record_or_g)
    parts = [_tray(g), _insert(g), _platform(g, "front"), _platform(g, "back")]
    tray = parts[0]
    minx, miny, maxx, maxy = tray.outline().bounds
    m = SHEET_MARGIN_MM
    placed = [tray.moved(m - minx, m + LABEL_MM + 4 - miny)]
    col_x = placed[0].outline().bounds[2] + PART_GAP_MM
    y = m + LABEL_MM + 4
    for p in parts[1:]:
        b = p.outline().bounds
        mp = p.moved(col_x - b[0], y - b[1])
        placed.append(mp)
        y = mp.outline().bounds[3] + PART_GAP_MM + LABEL_MM + 4
    bounds = unary_union([p.outline() for p in placed]).bounds
    sheet_w = math.ceil(bounds[2] + m)
    sheet_h = math.ceil(bounds[3] + m + 20.0)
    labels = []
    for p in placed:
        b = p.outline().bounds
        # the label's descender 1.0 mm above the part's bleed (the reviewer's MINOR 5: the old place crossed it)
        labels.append((p.label, (b[0], b[1] - DIE_BLEED_MM - 1.0 - 0.3 * LABEL_MM), LABEL_MM))
    title = ("counter_tray_header %s ⟪PROVISIONAL⟫ — %s — flat die at 100 %%, board %g mm E-flute — "
             "cut, crease, artwork, safe, bleed — drawn from the PRINT SIDE (printed face toward you): the tray seen "
             "from below, the platforms and the slot insert from above" % (VERSION, DECISION, g["t"]))
    return Die(placed, sheet_w, sheet_h, labels, (m, sheet_h - 18.0, 50.0), title)


def die_word_boxes(die: Die) -> list:
    """Every free word on the die sheet, with its box (die mm): the part labels, the title and the bar's words (the
    exporters set them at these places and sizes)."""
    out = [(text, _rect(x, y - size, x + label_width(text, size), y + 0.3 * size)) for text, (x, y), size in die.labels]
    bx, by, bl = die.bar
    out.append((die.title, _rect(bx, by - 9 - BAR_WORDS_MM, bx + label_width(die.title, BAR_WORDS_MM),
                                 by - 9 + 0.3 * BAR_WORDS_MM)))
    out.append((BAR_WORDS, _rect(bx + bl + 4, by + 3 - BAR_WORDS_MM, bx + bl + 4 + label_width(BAR_WORDS, BAR_WORDS_MM),
                                 by + 3 + 0.3 * BAR_WORDS_MM)))
    return out


def label_width(text: str, size: float) -> float:
    """A generous estimate of a Helvetica line's width (mm) at ``size`` mm cap-to-descender."""
    return 0.62 * size * len(text)


def _g_from_record(record: dict) -> dict:
    """Re-solve the plain geometry from a record's own inputs (so a die is always drawn from a record)."""
    products = {name: {k: f["value"] for k, f in vals.items()} for name, vals in record["products"].items()}
    own = {k: f["value"] for k, f in record["owner_provisional"].items()}
    result = _geometry(products, own)
    shape = record.get("hole_shape", "circle")
    _validate_hole_shape(shape)
    if shape != "circle":
        result["hole_shape"] = shape
    return result


def die_summary(die: Die) -> dict:
    """Each part's outline and knife: ``cut_length_mm`` is everything the die cuts (its cut lines and slits AND its
    holes' circles — the sheet verifier's minor: the holes were left out), with the two beside it."""
    parts = []
    for p in die.parts:
        o = p.outline()
        lines = sum(ln.length for ln in p.cut_lines())
        holes = p.hole_cut_length()
        parts.append({"part": p.name, "bbox_mm": [_r(v, 2) for v in o.bounds], "area_mm2": _r(o.area, 1),
                      "faces": len(p.faces), "creases": len(p.creases), "holes": len(p.holes),
                      "cut_length_mm": _r(lines + holes, 1), "line_cut_length_mm": _r(lines, 1),
                      "hole_cut_length_mm": _r(holes, 1),
                      "crease_length_mm": _r(sum(c.length for _n, c in p.creases), 1)})
    return {"sheet_mm": [die.sheet_w, die.sheet_h], "parts": parts,
            "cut_length_mm": _r(sum(sum(ln.length for ln in p.cut_lines()) + p.hole_cut_length()
                                   for p in die.parts), 1),
            "crease_length_mm": _r(sum(c.length for p in die.parts for _n, c in p.creases), 1),
            "words": "cut_length_mm: every cut line, slit and hole circle the knife carries (a part's and the sheet's)"}


def record_bytes(record: dict) -> bytes:
    return (json.dumps(record, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def full_record(products=None, provisional=None, *, hole_shape="circle") -> dict:
    """``solve`` plus the drawn die's summary and the record's own digest (die.json)."""
    rec = solve(products, provisional, hole_shape=hole_shape)
    die = build_die(rec)
    rec["die"] = die_summary(die)
    rec["alternative_board"] = alternative_board(provisional)
    rec["digest"] = hashlib.sha256(record_bytes({k: v for k, v in rec.items() if k != "digest"})).hexdigest()
    return rec


def alternative_board(provisional=None) -> dict:
    """The 1.0 mm card case (listed, not drawn): the numbers that move."""
    own = _merge(default_provisional(), provisional)
    alt = dict(own, board_mm=own["board_alternative_mm"])
    g = _geometry(default_products(), alt)
    return {"board_mm": g["t"], "floor_crease_to_crease_mm": [_r(g["floor_w"]), _r(g["floor_d"])],
            "front_skin_panel_mm": _r(g["front_skin_h"]), "back_wall_outer_mm": _r(g["back_wall_h"] + g["t"]),
            "header_top_mm": _r(g["back_wall_h"] + g["t"] + g["header_h"]),
            "junction_y_mm": _r(g["b_y"]), "back_inner_face_y_mm": _r(g["back_inner_y"]),
            "words": "only the board allowances move; the slot, rows and platforms keep their solved positions within "
                     "%.2f mm" % abs(g["b_y"] - _geometry(default_products(), own)["b_y"])}


# =====================================================================================================================
# the fold check
# =====================================================================================================================


def _finding(out, fid, rule, ok, measured, expected, words):
    out.append({"id": fid, "rule": rule, "ok": bool(ok), "measured": measured, "expected": expected,
                "words": words})


def _face(part: Part, name: str):
    for n, f, _p in part.faces:
        if n == name:
            return f
    raise KeyError(name)


def _span(poly, axis):
    b = poly.bounds
    return (b[2] - b[0]) if axis == 0 else (b[3] - b[1])


def stood_keys(die: Die, g: dict, allowance_mm: float = 0.0) -> dict:
    """Every insert's floor key tabs read off the drawn die and stood the one way the part erects: drawn print side
    up, its plate (or bed) seen from above, its front leg toward the shopper — so x = centre − X, the centre the main
    panel's middle on the flat. In depth the front leg stands at its solved place (its outer face, ``g["legs"]``) and
    a platform's back leg where the DRAWN plate puts it, folded: the front leg's outer face + the flat distance between
    the two leg creases + ``allowance_mm`` (what the folds add, 0 … the fold allowance; a plate drawn deeper than
    solved moves the back keys off their drawn place). ``{part: [{"id", "meets", "leg", "x": (x0, x1),
    "y": (y0, y1)}]}`` in plan."""
    out = {}
    t = g["t"]
    for p in die.parts:
        if p.name not in KEY_LAYOUT:
            continue
        main = _face(p, "plate" if p.name.endswith("platform") else "bed")
        xc = (main.bounds[0] + main.bounds[2]) / 2
        legs = dict(g["legs"][p.name])
        if p.name.endswith("platform"):
            cr = dict(p.creases)
            depth = cr["plate / back leg"].coords[0][1] - cr["front leg / plate"].coords[0][1]
            y0 = legs["front leg"][0]
            legs["back leg"] = (y0 + depth + allowance_mm - t, y0 + depth + allowance_mm)
        tabs = []
        for tb in p.tabs:
            if tb.get("kind") != "floor key":
                continue
            X0, _y0, X1, _y1 = tb["polygon"].bounds
            tabs.append({"id": tb["id"], "meets": tb["meets"], "leg": tb["leg"], "x": (xc - X1, xc - X0),
                         "y": tuple(legs[tb["leg"]])})
        out[p.name] = tabs
    return out


def floor_key_slots(die: Die, g: dict) -> dict:
    """The tray floor's key slots read off the drawn die, in plan (the tray drawn print side up, seen from below:
    x = X − the floor's centre, y = Y − the floor's front crease + board). ``{slot id: ((x0, x1), (y0, y1))}``."""
    tray = next(p for p in die.parts if p.name == "tray")
    fx0, fy0, fx1, _fy1 = _face(tray, "floor").bounds
    xc = (fx0 + fx1) / 2
    out = {}
    for s in tray.slots:
        if s.get("kind") != "floor key":
            continue
        b = s["polygon"].bounds
        out[s["id"]] = ((b[0] - xc, b[2] - xc), (b[1] - fy0 + g["t"], b[3] - fy0 + g["t"]))
    return out


def key_fits(tabs: list, slots: dict) -> list:
    """Every translation (dx, dy) of a rigid set of key tabs that seats each tab wholly inside some key slot: a list
    of boxes (dx0, dx1, dy0, dy1) — the exact feasible set, searched over every slot for every tab (not by name).
    ``slots`` are the free key slots only: the house's floor slots at the floor's edges are filled by the tray's own
    wall tabs once it stands, so a key cannot drop into one."""
    boxes = [(-math.inf, math.inf, -math.inf, math.inf)]
    for tb in tabs:
        (tx0, tx1), (ty0, ty1) = tb["x"], tb["y"]
        nxt = []
        for (sx0, sx1), (sy0, sy1) in slots.values():
            lo_x, hi_x, lo_y, hi_y = sx0 - tx0, sx1 - tx1, sy0 - ty0, sy1 - ty1
            if lo_x > hi_x + 1e-9 or lo_y > hi_y + 1e-9:
                continue
            for a0, a1, b0, b1 in boxes:
                c = (max(a0, lo_x), min(a1, hi_x), max(b0, lo_y), min(b1, hi_y))
                if c[0] <= c[1] + 1e-9 and c[2] <= c[3] + 1e-9:
                    nxt.append(c)
        boxes = nxt
        if not boxes:
            break
    return sorted(set(boxes))


def turned_round(tabs: list) -> list:
    """The same tabs with the part turned 180° about the vertical (x → −x, y → −y; ``key_fits`` searches every
    translation, so the pivot does not matter)."""
    return [dict(tb, x=(-tb["x"][1], -tb["x"][0]), y=(-tb["y"][1], -tb["y"][0])) for tb in tabs]


def print_side_in(tabs: list, turned: bool = False) -> list:
    """The same tabs with the part folded print side IN: every fold the other way, so the erected part is the mirror
    image of itself. Stood with its drawn front leg at the front it is mirrored across (x → −x); turned round as well
    it is mirrored front to back (y → −y, x kept: its legs swapped). ``key_fits`` searches every translation."""
    if turned:
        return [dict(tb, y=(-tb["y"][1], -tb["y"][0])) for tb in tabs]
    return [dict(tb, x=(-tb["x"][1], -tb["x"][0])) for tb in tabs]


def seats_at(die: Die, g: dict, part: str, allowance_mm: float, slots: dict | None = None) -> bool:
    """Whether a platform, its legs folded ``allowance_mm`` further apart than drawn, seats at its drawn place (its
    drawn x, and y within its front leg's play)."""
    play = LOCK_PLAY_MM / 2
    boxes = key_fits(stood_keys(die, g, allowance_mm)[part], slots or floor_key_slots(die, g))
    return any(b[0] <= 1e-9 and b[1] >= -1e-9 and b[2] <= play + 1e-9 and b[3] >= -play - 1e-9 for b in boxes)


def seat_range(die: Die, g: dict, part: str, *, limit_mm: float = 12.0) -> tuple:
    """The folded spacings (beyond the drawn, mm) at which a platform still seats at its drawn place: (least,
    greatest), each bisected to 0.001 mm from 0 out to ±``limit_mm`` (the seat set is one interval: the back leg's
    slot is one box)."""
    slots = floor_key_slots(die, g)
    if not seats_at(die, g, part, 0.0, slots):
        return None, None
    ends = []
    for sign in (-1, 1):
        lo, hi = 0.0, sign * limit_mm
        if seats_at(die, g, part, hi, slots):
            ends.append(hi)
            continue
        while abs(hi - lo) > 0.001:
            mid = (lo + hi) / 2
            if seats_at(die, g, part, mid, slots):
                lo = mid
            else:
                hi = mid
        ends.append(lo)
    return _r(ends[0], 2), _r(ends[1], 2)


def platform_racking(g: dict, die: Die) -> dict:
    """What holds a platform against racking (its plate shifting in depth over its feet, both legs leaning — the
    reviewer's MJ-1: "an open-ended channel can rack"): only its leg creases and its key tabs' fit in their slots. A
    flush tab (board × board) leans in its slot (board + 0.5 across) until board × (cos φ + sin φ) = the slot's width;
    the plate then stands leg × sin φ off its feet. NOT modelled as a pose and not held by the die: a named
    dependency, measured here (departures: platform_racking)."""
    t = g["t"]
    w = t + LOCK_PLAY_MM
    lean = math.degrees(math.asin(min(1.0, w / (t * math.sqrt(2))))) - 45.0
    out = {"held_by": "the leg creases and the key tabs' fit only (no panel closes the channel)",
           "lean_max_deg": _r(lean, 2), "tab_mm": [t, t], "slot_across_mm": _r(w, 2), "parts": []}
    slots = floor_key_slots(die, g)
    for part, xs, yc, hole, leg_h in (("front platform", g["balm_x"], g["balm_y"], g["balm_hole"], g["front_plate_h"]),
                                      ("back platform", g["lip_x"], g["lip_y"], g["lip_hole"], g["back_plate_h"])):
        # a stick's foot (anywhere in its hole, ± the key's play) against its own back leg's slot front, at the drawn
        # place: how far the plate may rack back before a foot can reach the slot's opened front (when that back leg
        # also stands back in its slot)
        front = min(sl[1][0] for sid, sl in slots.items() if sid.startswith("key slot %s back leg" % part))
        foot = yc + hole / 2 + LOCK_PLAY_MM / 2
        out["parts"].append({"part": part, "leg_mm": _r(leg_h), "plate_drift_max_mm": _r(leg_h *
                                                                                          math.sin(math.radians(lean)), 2),
                             "stick_foot_to_back_slot_mm": _r(front - foot, 2)})
    out["words"] = ("a platform's plate can rack over its feet until its key tabs bind (lean %.2f°: %s); past the "
                    "stick-foot distances listed a foot can stand over the back leg's slot where it has opened in front "
                    "of a leg standing back in it. The sightline is searched with the rows moved up to 20 mm in depth "
                    "(sight_tolerance's rows_in_depth) and loses no sample, so racking cannot hide a stick; the "
                    "platforms' squareness is the folded sample's to show" % (
                        lean, "; ".join("%s %.2f mm" % (p["part"], p["plate_drift_max_mm"]) for p in out["parts"])))
    return out


# --- the slot insert's sway (the geometry verifier's major): named and measured on Day 12, closed by D-D13-2 ----------
# The four-bar below (insert_linkage, sway_pose, _sway_measure) is the tube WITHOUT its gussets — Day 12's measure, kept
# so the record shows what the gussets stop and so a die drawn without them fails; the closed tube is frame_pose.

INSERT_PANELS = ("front leg", "bed", "backrest", "back leg", "base")
#: what would hold the tube square — Day 12's list (D-D12-8: listed, not built then); D-D13-2 chose between the owner's
#: two (keys at both feet, or a glued diagonal gusset at each end: the second of these) — insert_sway's "choice"
SWAY_REMEDY = [
    "a tab from the back leg's top (or the backrest's top edge) reaching back across the gap into a slot in the "
    "header's return flap or the back wall: the coupler is then held at a second point on the tray and the four-bar "
    "is a rigid frame (it stops the sway both ways)",
    "end panels on the base (or the legs) folded up and glued across the tube's two open ends: a closed tube is "
    "square (it stops the sway both ways)",
    "the base glued (or keyed at its back end) to the tray floor — listed by the lead and the verifier, but NOT enough "
    "alone: the base is already the four-bar's fixed link (it lies on the floor under the stack's weight) and both "
    "legs' hinges lie on it, so the mode is the same with the base glued; it helps only with one of the two above",
]


def _lean(v, a):
    """The vector ``v`` (y, h) leaned back by ``a`` radians: an upright vector's top toward +y (the back wall)."""
    return (v[0] * math.cos(a) + v[1] * math.sin(a), -v[0] * math.sin(a) + v[1] * math.cos(a))


def insert_linkage(g: dict, panels: dict | None = None) -> dict:
    """The slot insert's tube in its side section (y depth, h above the floor's top) as the four-bar it is: the base
    the fixed link (it lies on the floor under the stack's weight); the front leg (glued to the glue flap) hinged on
    the base's front crease O1; the back leg hinged on the base's back crease O2; the bed and backrest one rigid
    coupler (held at 90° by the stack and the wings) from the front leg's top A to the back leg's top C, carrying the
    stack. ``panels`` (lengths, mm, by name) default to the solve's; the fold check passes the drawn die's. Drawn
    square: the front leg's outer face at its keyed y, both legs upright, the bed at the owner's lean; the closure
    says how far the panels miss closing that tube (0 on a die drawn from its solve)."""
    ins = g["insert"]
    pn = dict(panels) if panels else {"front leg": ins["front_leg_mm"], "bed": ins["bed_mm"],
                                      "backrest": ins["backrest_mm"], "back leg": ins["back_leg_mm"],
                                      "base": ins["base_mm"]}
    th = math.radians(g["theta_deg"])
    n, u = (math.cos(th), -math.sin(th)), (math.sin(th), math.cos(th))
    A0 = (g["f_y"], pn["front leg"])
    B0 = (A0[0] + pn["bed"] * n[0], A0[1] + pn["bed"] * n[1])
    C0 = (B0[0] + pn["backrest"] * u[0], B0[1] + pn["backrest"] * u[1])
    O2 = (C0[0], 0.0)
    O1 = (O2[0] - pn["base"], 0.0)
    ph, st = g["palette_h"], g["stack_mm"]
    return {"panels": pn, "O1": O1, "O2": O2, "A0": A0, "B0": B0, "C0": C0,
            "K0": (B0[0] + ph * u[0], B0[1] + ph * u[1]),                         # the stack's top-back corner
            "M0": (B0[0] - st / 2 * n[0] + ph / 2 * u[0], B0[1] - st / 2 * n[1] + ph / 2 * u[1]),   # its centre
            "closure_mm": {"back_leg_vs_backrest_top": C0[1] - pn["back leg"],
                           "base_front_crease_vs_front_leg_inner_face": O1[0] - (A0[0] + g["t"])}}


def sway_pose(link: dict, lean_deg: float) -> dict:
    """The four-bar with its front leg leaned ``lean_deg`` back from upright (its top toward the back wall; negative:
    toward the shopper): the back leg's lean (deg), the stack's added lean (deg, + = further back), the legs' tops,
    and ``move`` / ``rotate`` taking a drawn coupler point / direction (y, h) to its swayed place (exact: the back
    leg's top found as the circles' intersection nearest its drawn place)."""
    O1, O2, A0, C0 = link["O1"], link["O2"], link["A0"], link["C0"]
    d0 = _lean((A0[0] - O1[0], A0[1] - O1[1]), math.radians(lean_deg))
    A = (O1[0] + d0[0], O1[1] + d0[1])
    r1, r2 = math.dist(O2, C0), math.dist(A0, C0)
    d = math.dist(O2, A)
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, r1 * r1 - a * a))
    ex, ey = (A[0] - O2[0]) / d, (A[1] - O2[1]) / d
    foot = (O2[0] + a * ex, O2[1] + a * ey)
    C = min(((foot[0] - h * ey, foot[1] + h * ex), (foot[0] + h * ey, foot[1] - h * ex)),
            key=lambda p: math.dist(p, C0))
    psi = math.atan2(C[0] - O2[0], C[1] - O2[1]) - math.atan2(C0[0] - O2[0], C0[1] - O2[1])
    ts = math.atan2(C[1] - A[1], C[0] - A[0]) - math.atan2(C0[1] - A0[1], C0[0] - A0[0])
    cs, sn = math.cos(ts), math.sin(ts)

    def rotate(v):
        return (v[0] * cs - v[1] * sn, v[0] * sn + v[1] * cs)

    def move(p):
        v = rotate((p[0] - A0[0], p[1] - A0[1]))
        return (A[0] + v[0], A[1] + v[1])
    return {"lean_deg": lean_deg, "back_leg_deg": math.degrees(psi), "stack_turn_deg": -math.degrees(ts),
            "A": A, "C": C, "move": move, "rotate": rotate}


def _least_lean(f, target, hi):
    """The least lean in [0, ``hi``] (deg) at which ``f`` (falling as the lean grows) is <= ``target``, bisected to
    1e-7°; 0.0 if it already is upright, None if it never is up to ``hi``."""
    if f(0.0) <= target + 1e-9:
        return 0.0
    if f(hi) > target:
        return None
    lo = 0.0
    while hi - lo > 1e-7:
        mid = (lo + hi) / 2
        if f(mid) <= target:
            hi = mid
        else:
            lo = mid
    return hi


def _sway_measure(g: dict, die: Die | None = None) -> dict:
    """The sway's numbers, unrounded (``insert_sway`` records them; ``sight_at_sway`` stands the insert at each seat's
    limit). Off the drawn die's panels and key slots when ``die`` is given."""
    t = g["t"]
    play = LOCK_PLAY_MM / 2
    if die is not None:
        ins = next(p for p in die.parts if p.name == "slot insert")
        link = insert_linkage(g, {k: _span(_face(ins, k), 1) for k in INSERT_PANELS})
        stood, kslots = stood_keys(die, g), floor_key_slots(die, g)
        tabs = [tb for tb in stood.get("slot insert", []) if tb["meets"] in kslots]
        ins_back = min(kslots[tb["meets"]][1][1] - tb["y"][1] for tb in tabs) if tabs else play
        across = min(kslots[tb["meets"]][1][1] - kslots[tb["meets"]][1][0] for tb in tabs) if tabs else t + 2 * play
    else:
        link, ins_back, across = insert_linkage(g), play, t + 2 * play
    # the front leg's key tab (board × board) leans in its slot until its diagonal spans the slot (platform_racking's
    # rule): past that it binds
    bind = math.degrees(math.asin(min(1.0, across / (t * math.sqrt(2))))) - 45.0
    house_c, back = g["clearance"], g["back_inner_y"]
    K0, M0 = link["K0"], link["M0"]
    seats = []
    for name, behind in (("drawn", 0.0), ("rearmost", ins_back + g["fold_each"])):
        def clear(lean, behind=behind):
            return back - (sway_pose(link, lean)["move"](K0)[0] + behind)
        lost, touch = _least_lean(clear, house_c, bind), _least_lean(clear, 0.0, bind)
        limit = touch if touch is not None else bind
        seats.append({"seat": name, "behind": behind, "square": clear(0.0), "house_at": lost, "touch_at": touch,
                      "limit": limit, "at_limit": clear(limit), "at_bind": clear(bind),
                      "pose": sway_pose(link, limit)})
    return {"link": link, "bind": bind, "house": house_c, "seats": seats, "ins_back": ins_back,
            "rise": lambda lean: sway_pose(link, lean)["move"](M0)[1] - M0[1]}


# --- the closed tube (D-D13-2): a glued diagonal gusset at each end ---------------------------------------------------

#: the proof's step: the front leg's lean sampled every this many degrees over the whole permitted range
FRAME_STEP_DEG = 0.01


def frame_pose(link: dict, lean_deg: float) -> dict:
    """[D-D13-2] The closed tube with its front leg leaned ``lean_deg`` from its drawn place about its hinge on the base
    (+: its top toward the back wall): the gussets hold the back leg square on the base, so it stays upright and only
    stands further back (or forward) with the base's folds (``back_leg_moves_mm``); the coupler (bed and backrest, held
    at 90° by the stack and the wings) spans from the front leg's top to the back leg's top and turns as it must. The
    keys of ``sway_pose``: ``move`` / ``rotate`` take a drawn coupler point / direction (y, h) to its place."""
    O1, A0, C0 = link["O1"], link["A0"], link["C0"]
    d0 = _lean((A0[0] - O1[0], A0[1] - O1[1]), math.radians(lean_deg))
    A = (O1[0] + d0[0], O1[1] + d0[1])
    span, rise = math.dist(A0, C0), C0[1] - A[1]
    C = (A[0] + math.sqrt(max(0.0, span * span - rise * rise)), C0[1])
    ts = math.atan2(C[1] - A[1], C[0] - A[0]) - math.atan2(C0[1] - A0[1], C0[0] - A0[0])
    cs, sn = math.cos(ts), math.sin(ts)

    def rotate(v):
        return (v[0] * cs - v[1] * sn, v[0] * sn + v[1] * cs)

    def move(p):
        v = rotate((p[0] - A0[0], p[1] - A0[1]))
        return (A[0] + v[0], A[1] + v[1])
    return {"lean_deg": lean_deg, "back_leg_deg": 0.0, "back_leg_moves_mm": C[0] - C0[0],
            "stack_turn_deg": -math.degrees(ts), "A": A, "C": C, "move": move, "rotate": rotate}


def frame_lean_limit(link: dict, back_mm: float) -> float:
    """The front leg's lean (deg) at which the closed tube's back leg stands ``back_mm`` behind its drawn place, bisected
    to 1e-9° (the back leg's move grows with the lean)."""
    lo, hi = 0.0, 45.0
    while hi - lo > 1e-9:
        mid = (lo + hi) / 2
        if frame_pose(link, mid)["back_leg_moves_mm"] < back_mm:
            lo = mid
        else:
            hi = mid
    return hi


def frame_leans(lean_max: float, step_deg: float = FRAME_STEP_DEG) -> list:
    """Every lean the proof samples: −``lean_max`` … +``lean_max`` at most ``step_deg`` apart, both ends included."""
    n = max(2, math.ceil(2 * lean_max / step_deg))
    return [-lean_max + 2 * lean_max * i / n for i in range(n + 1)]


def frame_reserve(link: dict, back_mm: float) -> dict:
    """The closed tube's permitted lean (``frame_lean_limit``) and how far the stack's top-back corner moves back at the
    most, over every lean in [−max, +max] (``frame_leans``): the insert's set-forward takes it (never below 0)."""
    lean_max = frame_lean_limit(link, back_mm)
    K0 = link["K0"]
    worst = max((frame_pose(link, a)["move"](K0)[0] - K0[0], a) for a in frame_leans(lean_max))
    return {"lean_max": lean_max, "back_mm": back_mm, "reserve": max(0.0, worst[0]), "at_lean": worst[1]}


def insert_gussets(part: Part, g: dict, link: dict) -> list:
    """[D-D13-2] The slot insert's gussets read off its drawn faces and creases and folded into the tube's side section
    (y depth, h above the floor; the panels' outer surfaces, as ``insert_linkage``): each hinged on the back leg's side
    edge from its foot; its corner there square (so it holds the back leg square on the base); its glue flap on its
    free leg (folded flat onto the base's top inside the tube); its free leg clear of the tube's own glue flap, and its
    long edge inside the tube clear of the bed and the backrest (their boards inside their outer surfaces), both by the
    minimum web (3 × board); unprinted. ``closes``: all of it holds."""
    faces = {n: f for n, f, _p in part.faces}
    printed = {n: p for n, _f, p in part.faces}
    creases = dict(part.creases)
    t, web = g["t"], 3 * g["t"]
    lx0, _ly0, lx1, ly1 = faces["back leg"].bounds                 # the back leg's foot on the flat: Y = ly1
    ry, fy = link["O2"][0], link["A0"][0]                          # the back leg's and the front leg's outer faces
    bed_backrest = LineString([link["A0"], link["B0"], link["C0"]])
    out = []
    for side, xh in (("L", lx0), ("R", lx1)):
        tri, flap = faces.get("gusset " + side), faces.get("gusset flap " + side)
        hinge, fold = creases.get("back leg / gusset " + side), creases.get("gusset / gusset flap " + side)
        if tri is None or flap is None or hinge is None or fold is None:
            out.append({"side": side, "present": False, "closes": False})
            continue
        on_edge = (all(abs(x - xh) <= TOL_MM for x, _y in hinge.coords) and
                   abs(max(y for _x, y in hinge.coords) - ly1) <= TOL_MM)
        up = hinge.length
        free = [p for p in tri.exterior.coords[:-1] if abs(p[0] - xh) > TOL_MM]
        square = len(free) == 1 and abs(free[0][1] - ly1) <= TOL_MM
        along = abs(free[0][0] - xh) if free else 0.0
        on_leg = abs(fold.length - along) <= TOL_MM and all(abs(y - ly1) <= TOL_MM for _x, y in fold.coords)
        stood = Polygon([(ry, 0.0), (ry, up), (ry - along, 0.0)])
        glue_clear = (ry - along) - (fy + 2 * t)                    # the tube's glue flap: the board inside the front leg
        inside = stood.distance(bed_backrest) - t
        unprinted = not printed["gusset " + side] and not printed["gusset flap " + side]
        out.append({"side": side, "present": True, "up_the_back_leg_mm": _r(up, 3), "along_the_base_mm": _r(along, 3),
                    "glue_flap_mm": _r(_span(flap, 1), 3), "hinged_on_the_back_leg_from_its_foot": on_edge,
                    "corner_square": square, "glue_flap_on_its_free_leg": on_leg,
                    "clear_of_the_tubes_glue_flap_mm": _r(glue_clear, 2), "inside_the_tube_mm": _r(inside, 2),
                    "printed": not unprinted,
                    "closes": on_edge and square and on_leg and glue_clear >= web - 1e-9 and inside >= web - 1e-9 and
                    unprinted})
    return out


def _frame_measure(g: dict, die: Die | None = None, back_mm: float | None = None) -> dict:
    """The closed tube's proof, unrounded (``insert_sway`` records it, fold_check's stack_rear_vs_back_wall reads it,
    ``sight_at_sway`` stands the insert at its limits). Off the drawn die's panels, key slots and gussets when ``die``
    is given. The lean the fit permits: the back leg, square on the base (the gussets), stands 0 … ``back_mm`` behind
    its drawn place (default: the base's two folds, the glue flap's crease and the back leg's, 2 × one fold's
    allowance); the front leg's lean is sampled every ``FRAME_STEP_DEG`` over [−max, +max] at the drawn seat and at the
    rearmost (its key's play + one fold's allowance behind, as Day 12's)."""
    play = LOCK_PLAY_MM / 2
    back_mm = 2 * g["fold_each"] if back_mm is None else back_mm
    if die is not None:
        ins = next(p for p in die.parts if p.name == "slot insert")
        link = insert_linkage(g, {k: _span(_face(ins, k), 1) for k in INSERT_PANELS})
        stood, kslots = stood_keys(die, g), floor_key_slots(die, g)
        tabs = [tb for tb in stood.get("slot insert", []) if tb["meets"] in kslots]
        ins_back = min(kslots[tb["meets"]][1][1] - tb["y"][1] for tb in tabs) if tabs else play
    else:
        ins = _insert(g)
        link, ins_back = insert_linkage(g), play
    gussets = insert_gussets(ins, g, link)
    lean_max = frame_lean_limit(link, back_mm)
    leans = frame_leans(lean_max)
    back, K0 = g["back_inner_y"], link["K0"]
    corner = [frame_pose(link, a)["move"](K0)[0] for a in leans]
    seats = []
    for name, behind in (("drawn", 0.0), ("rearmost", ins_back + g["fold_each"])):
        clear = [back - (y + behind) for y in corner]
        i = min(range(len(leans)), key=clear.__getitem__)
        seats.append({"seat": name, "behind": behind, "square": back - (K0[0] + behind), "least": clear[i],
                      "least_at": leans[i], "at_max": clear[-1], "at_min": clear[0]})
    return {"link": link, "closed": len(gussets) == 2 and all(gu["closes"] for gu in gussets), "gussets": gussets,
            "back_mm": back_mm, "lean_max": lean_max, "samples": len(leans), "seats": seats, "ins_back": ins_back,
            "house": g["clearance"], "pose_max": frame_pose(link, lean_max), "pose_min": frame_pose(link, -lean_max),
            "corner_moves_mm": [min(corner) - K0[0], max(corner) - K0[0]]}


def frame_fold_corners(g: dict, link: dict) -> dict:
    """A second reading of the closed tube's fit, a cross-check of ``_frame_measure``'s envelope: every one of the
    tube's five folds — the glue flap's crease on the base, front leg / bed, bed / backrest, backrest / back leg, back
    leg / base — at either end of its allowance (0 or one fold's, added to BOTH panels it joins: 2^5 = 32 tubes), each
    solved as a closed frame (the back leg square on the base, the front leg on its hinge, the coupler rigid at 90°),
    its front leg's key at the back of its play: the least clearance between the stack's top-back corner and the back's
    inner face, and the tube that gives it."""
    fe, play = g["fold_each"], LOCK_PLAY_MM / 2
    th = math.radians(g["theta_deg"])
    n, u = (math.cos(th), -math.sin(th)), (math.sin(th), math.cos(th))
    O1, O2, A0, B0, C0, K0 = (link[k] for k in ("O1", "O2", "A0", "B0", "C0", "K0"))
    pn = link["panels"]
    stack = (K0[0] - B0[0], K0[1] - B0[1])
    back = g["back_inner_y"]
    worst = None
    for d_o1, d_a, d_b, d_c, d_o2 in itertools.product((0.0, fe), repeat=5):
        leg = (A0[0] - O1[0], A0[1] - O1[1] + d_a)
        bed, rest = pn["bed"] + d_a + d_b, pn["backrest"] + d_b + d_c
        V = (bed * n[0] + rest * u[0], bed * n[1] + rest * u[1])
        Ct = (O2[0] + d_o1 + d_o2, C0[1] + d_o2 + d_c)
        r1, r2 = math.hypot(*leg), math.hypot(*V)
        dd = math.dist(O1, Ct)
        a = (r1 * r1 - r2 * r2 + dd * dd) / (2 * dd)
        h = math.sqrt(max(0.0, r1 * r1 - a * a))
        ex, ey = (Ct[0] - O1[0]) / dd, (Ct[1] - O1[1]) / dd
        foot = (O1[0] + a * ex, O1[1] + a * ey)
        A = min(((foot[0] - h * ey, foot[1] + h * ex), (foot[0] + h * ey, foot[1] - h * ex)),
                key=lambda p: math.dist(p, A0))
        ts = math.atan2(Ct[1] - A[1], Ct[0] - A[0]) - math.atan2(V[1], V[0])
        cs, sn = math.cos(ts), math.sin(ts)
        B = (A[0] + bed * (n[0] * cs - n[1] * sn), A[1] + bed * (n[0] * sn + n[1] * cs))
        K = (B[0] + stack[0] * cs - stack[1] * sn, B[1] + stack[0] * sn + stack[1] * cs)
        clear = back - (K[0] + play)
        if worst is None or clear < worst[0]:
            worst = (clear, (d_o1, d_a, d_b, d_c, d_o2), K[0] - K0[0])
    names = ("glue flap / base", "front leg / bed", "bed / backrest", "backrest / back leg", "back leg / base")
    return {"tubes": 32, "fold_allowance_each_mm": [0.0, _r(fe, 2)], "key_behind_mm": play,
            "least_clearance_mm": _r(worst[0], 2), "stack_corner_moves_back_mm": _r(worst[2], 2),
            "at": {k: _r(v, 2) for k, v in zip(names, worst[1])},
            "kept": worst[0] >= g["clearance"] - 1e-9}


def insert_sway(g: dict, die: Die | None = None) -> dict:
    """fold-check.json's racking.slot_insert. Day 12 named and measured the sway (the tube a four-bar keyed at its front
    leg's foot only); D-D13-2 closes it: a glued diagonal gusset at each end holds the back leg square on the base, so
    the tube is a frame that leans only as far as its fit lets it — the base's two folds standing the back leg 0 … 2 ×
    one fold's allowance behind its drawn place. Measured off the die's own panels, key slots and gussets: that lean,
    the stack corner's move at it, and stack_rear_vs_back_wall at every lean in [−max, +max] (every 0.01°) at the drawn
    and the rearmost seats, every fold's corner as a cross-check; and what the four-bar does with the gussets left off
    (the control the fold check fails on a die drawn without them)."""
    m = _frame_measure(g, die)
    link = m["link"]
    K0 = link["K0"]
    four = _sway_measure(g, die)
    corners = frame_fold_corners(g, link)
    pmax, pmin = m["pose_max"], m["pose_min"]
    kmax, kmin = pmax["move"](K0), pmin["move"](K0)
    lean = m["lean_max"]
    seats = []
    for s in m["seats"]:
        seats.append({
            "seat": s["seat"] if s["seat"] == "drawn" else "rearmost (its key's play %.2f + one fold's allowance %.2f "
                                                           "behind drawn)" % (m["ins_back"], g["fold_each"]),
            "behind_drawn_mm": _r(s["behind"], 2), "square_clearance_mm": _r(s["square"], 2),
            "least_clearance_mm": _r(s["least"], 2), "least_at_lean_deg": _r(s["least_at"], 2),
            "clearance_at_most_lean_back_mm": _r(s["at_max"], 2),
            "clearance_at_most_lean_forward_mm": _r(s["at_min"], 2),
            "house_clearance_kept": s["least"] >= m["house"] - 1e-9})
    d4, r4 = four["seats"]
    unglued = {"words": "the same tube with its gussets left off — Day 12's four-bar, both legs free to lean, measured "
                        "at today's seat: it would sway until the stack rests on the back's inner face",
               "seats": [{"seat": s["seat"], "house_clearance_lost_at_deg": None if s["house_at"] is None else
                          _r(s["house_at"], 2), "touches_at_deg": None if s["touch_at"] is None else
                          _r(s["touch_at"], 2), "stack_rear_vs_back_wall_mm": _r(s["at_limit"], 2) + 0.0}
                         for s in (d4, r4)],
               "key_tab_binds_at_deg": _r(four["bind"], 2),
               "if_only_the_key_tabs_stopped_it_mm": [_r(d4["at_bind"], 2), _r(r4["at_bind"], 2)]}
    choice = {
        "chosen": "a glued diagonal gusset at each end",
        "why": ("The die's vocabulary is faces, creases, tabs, slots and joins. Keys at both feet are not open to it "
                "here: the back leg's foot is creased to the base (no free edge for a key: departures "
                "insert_print_side_in), and a key does not square the tube anyway — a flush %.2f × %.2f key in its "
                "tab + %.2f slot leans to %.2f° before it binds, where the stack's corner would stand %.2f mm (drawn "
                "seat) and %.2f mm (rearmost) from the back's inner face: no seat this tray has room for keeps 2.00 "
                "there. A gusset is two faces and two creases on the back leg's side edge, as the wings are on the "
                "backrest's, glued as the tube's own glue flap is: it holds the back leg square on the base, so the "
                "four-bar becomes a frame." % (g["t"], g["t"], LOCK_PLAY_MM, four["bind"], d4["at_bind"],
                                               r4["at_bind"])),
        "keys_at_both_feet": {"back_leg_foot": "creased to the base: no free edge", "key_binds_at_deg":
                              _r(four["bind"], 2), "stack_rear_vs_back_wall_at_bind_mm": [_r(d4["at_bind"], 2),
                                                                                          _r(r4["at_bind"], 2)]},
        "clears": "the wings (on the backrest's edges, above the bed: the gussets below it, inside the tube); the "
                  "palettes' edges (palette_vs_insert_wings unchanged: the gussets are below the bed); the side liners "
                  "(the gussets fold inside the insert's %.2f width: slot_insert_vs_side_walls unchanged); the sticks "
                  "(in front of the insert)" % g["insert"]["width_mm"],
    }
    words = ("Closed (D-D13-2): the slot insert's tube carries a glued diagonal gusset at each end, %s up the back leg "
             "and %s along the base, holding the back leg square on the base, so the tube is a frame, not a four-bar. "
             "Its fit still lets it lean: the base's two folds (the glue flap's crease and the back leg's, each 0 … "
             "%.2f) may stand the back leg up to %.2f behind its drawn place, and the frame takes that as the front "
             "leg leaning %.2f° (its top %.2f mm back, the coupler turning %.2f°, the stack's top-back corner %.2f mm "
             "back); the key's ±%.2f moves the seat, not the lean; a glue line is uniform (a parallel shift, not "
             "modelled). The insert is set forward by that corner move on top of Day 12's fold and key (%.2f in all), "
             "so at every lean in [−%.2f°, +%.2f°] (%d samples, every %.2f°) the stack keeps %.2f mm from the back's "
             "inner face at the drawn seat (least %.2f) and %.2f at the rearmost (least %.2f, at +%.2f°): the house's "
             "%.2f kept. Every fold at either end of its allowance (32 tubes, the key at the back of its play): least "
             "%.2f. Left off, the gussets would let it sway as Day 12's four-bar: at today's seat the corner touches "
             "the back at %.2f° (drawn) and %.2f° (rearmost). The sightline at the limits: sightlines.json "
             "insert_sway." % (
                 " / ".join(sorted({"%.2f" % gu["up_the_back_leg_mm"] for gu in m["gussets"] if gu["present"]})) or "—",
                 " / ".join(sorted({"%.2f" % gu["along_the_base_mm"] for gu in m["gussets"] if gu["present"]})) or "—",
                 g["fold_each"], m["back_mm"], lean, pmax["A"][0] - link["A0"][0], pmax["stack_turn_deg"],
                 kmax[0] - K0[0], LOCK_PLAY_MM / 2, g["set_forward"], lean, lean, m["samples"], FRAME_STEP_DEG,
                 seats[0]["least_clearance_mm"], seats[0]["least_clearance_mm"], seats[1]["least_clearance_mm"],
                 seats[1]["least_clearance_mm"], seats[1]["least_at_lean_deg"], m["house"],
                 corners["least_clearance_mm"], d4["touch_at"] or four["bind"], r4["touch_at"] or four["bind"]))
    return {"part": "slot insert",
            "status": "closed (D-D13-2)" if m["closed"] else "OPEN: the die's slot insert has no closing gussets",
            "decision": SWAY_DECISION,
            "built": "a glued diagonal gusset at each end of the tube: on each of the back leg's side edges a right "
                     "triangle (back leg / gusset crease), folded in across the tube's open end, its glue flap (gusset "
                     "/ gusset flap crease) glued to the base's top inside the tube; unprinted",
            "choice": choice,
            "mode": "a frame: the base on the floor; the back leg held square on it by the two gussets; the front leg "
                    "(glued to the glue flap, keyed at its foot) hinged on the base's front crease; the bed and "
                    "backrest one rigid coupler (90° held by the stack and the wings) from the front leg's top to the "
                    "back leg's. It leans only as its fit lets the back leg stand off its drawn place",
            "panels_mm": {k: _r(v, 3) for k, v in link["panels"].items()},
            "panels_from": "the drawn die's faces" if die is not None else "the solve",
            "closure_mm": {k: _r(v, 4) + 0.0 for k, v in link["closure_mm"].items()},
            "hinges_y_mm": {"front leg on the base": _r(link["O1"][0], 3), "back leg on the base": _r(link["O2"][0], 3)},
            "gussets": m["gussets"],
            "held_by": "the gussets (the back leg square on the base) and the front leg's two floor keys (its foot, "
                       "±%.2f each way)" % (LOCK_PLAY_MM / 2),
            "lean_permitted": {
                "front_leg_lean_deg": [_r(-lean, 2), _r(lean, 2)],
                "from": "the base's two folds — the glue flap's crease and the back leg / base crease — each 0 … %.2f "
                        "(one fold's allowance, builder_provisional.fold_allowance_mm): the back leg, square on the "
                        "base, stands 0 … %.2f behind its drawn place; the folds only add, so the frame leans back 0 … "
                        "+%.2f°, and the proof samples the whole of ±%.2f°" % (g["fold_each"], m["back_mm"], lean,
                                                                             lean),
                "back_leg_moves_mm": _r(pmax["back_leg_moves_mm"], 3),
                "front_leg_top_moves_mm": _r(pmax["A"][0] - link["A0"][0], 2),
                "stack_turn_deg": [_r(pmin["stack_turn_deg"], 3), _r(pmax["stack_turn_deg"], 3)],
                "stack_lean_deg": [_r(g["theta_deg"] + pmin["stack_turn_deg"], 2),
                                   _r(g["theta_deg"] + pmax["stack_turn_deg"], 2)],
                "stack_corner_moves_mm": {"at_most_lean_back": [_r(kmax[0] - K0[0], 2), _r(kmax[1] - K0[1], 2)],
                                          "at_most_lean_forward": [_r(kmin[0] - K0[0], 2), _r(kmin[1] - K0[1], 2)]},
                "key_play_mm": LOCK_PLAY_MM / 2, "glue": "a uniform line: a parallel shift, not a turn (not modelled)"},
            "proof": {"rule": "stack_rear_vs_back_wall >= %.2f at every lean in [−max, +max], at the drawn and the "
                              "rearmost seats" % m["house"],
                      "step_deg": FRAME_STEP_DEG, "samples": m["samples"], "seats": seats,
                      "every_fold_corner": corners,
                      "set_forward_mm": {"total": _r(g["set_forward"], 3), "fold": _r(g["fold_each"], 2),
                                         "key": LOCK_PLAY_MM / 2, "lean": _r(g["frame"]["reserve"], 3)}},
            "house_clearance_mm": m["house"],
            "without_the_gussets": unglued,
            "sightline_at_the_limits": "sightlines.json insert_sway",
            "words": words}


def _insert_sway_departure(g: dict) -> dict:
    """[D-D13-2] The departure Day 12 listed, closed: what was built and the proof's numbers (racking.slot_insert)."""
    s = insert_sway(g)
    d, r = s["proof"]["seats"]
    lp = s["lean_permitted"]
    return {"id": "insert_sway", "status": "closed — D-D13-2", "owner": s["decision"],
            "built": s["built"] + " (builder_provisional.insert_gusset_mm); the insert set forward %.2f "
                                  "(builder_provisional.insert_set_forward_mm)" % s["proof"]["set_forward_mm"]["total"],
            "why": ("Day 12 named it (the geometry verifier's major, final pass; its record "
                    "docs/audit/day-12/display/die/fold-check.json racking.slot_insert): a tube keyed at its front "
                    "leg's foot only sways as a four-bar, and the house's 2.00 between the stack and the back held only "
                    "while it stood square. D-D13-2 closes it with the owner's second remedy (the first, keys at both "
                    "feet, has no free edge on the back leg and would bind only at %.2f°). The gussets hold the back "
                    "leg square, so the tube leans only as its fit lets it: %.2f° either way at most (the base's two "
                    "folds, the back leg up to %.2f behind). Proven off the die: at every lean in that range (%d "
                    "samples) stack_rear_vs_back_wall is at least %.2f at the drawn seat and %.2f at the rearmost — "
                    "the house's %.2f kept; every fold at either end of its allowance, at least %.2f. The platforms' "
                    "racking is not this: it stays named (departures platform_racking) and is read on the folded "
                    "sample on Day 14.") % (
                        s["choice"]["keys_at_both_feet"]["key_binds_at_deg"], lp["front_leg_lean_deg"][1],
                        lp["back_leg_moves_mm"], s["proof"]["samples"], d["least_clearance_mm"],
                        r["least_clearance_mm"], s["house_clearance_mm"],
                        s["proof"]["every_fold_corner"]["least_clearance_mm"])}


def fold_check(record: dict, die: Die | None = None) -> dict:
    """Read the drawn die, fold it into the closed dimensions, check every clearance against the three product
    records and the die's own rules. ``{"schema", "passed", "closed", "findings", "failed", "close"}``."""
    if record.get("schema") == PRODUCT_GRID_SCHEMA:
        return product_tray_fold_check(record, die)
    if record.get("schema") == "counter_tray_header/product-grid-2":
        from . import counter_display
        return counter_display.fold_check(record, die)
    g = _g_from_record(record)
    die = die or build_die(g)
    parts = {p.name: p for p in die.parts}
    tray, ins = parts["tray"], parts["slot insert"]
    fp, bp = parts["front platform"], parts["back platform"]
    P = {name: {k: f["value"] for k, f in vals.items()} for name, vals in record["products"].items()}
    t = g["t"]
    f: list = []
    A = g["allowance"]
    stood = stood_keys(die, g)
    kslots = floor_key_slots(die, g)

    # -- the die read back: panel spans measured off its faces ----------------------------------------------------------
    floor = _face(tray, "floor")
    W = _span(floor, 0) + 2 * t
    D = _span(floor, 1) + 2 * t
    front_h = _span(_face(tray, "front skin"), 1) + t
    back_panel = _span(_face(tray, "back wall"), 1)
    back_h = back_panel + t
    header_leaf = _span(_face(tray, "header rear leaf"), 1)
    header_front = _span(_face(tray, "header front leaf"), 1)
    header_top = back_h + header_leaf
    skin = _face(tray, "side skin R")
    sx0 = floor.bounds[2]
    skin_front = max(x for x, y in skin.exterior.coords if abs(y - skin.bounds[1]) < 1e-6) - sx0
    skin_back = max(x for x, y in skin.exterior.coords if abs(y - skin.bounds[3]) < 1e-6) - sx0
    ret = _span(_face(tray, "return flap"), 1)
    ins_w = _span(_face(ins, "bed"), 0)
    slot_w = ins_w - 2 * t
    bed = _span(_face(ins, "bed"), 1)
    backrest = _span(_face(ins, "backrest"), 1)
    front_leg = _span(_face(ins, "front leg"), 1)
    fp_leg, bp_leg = _span(_face(fp, "front leg"), 1), _span(_face(bp, "front leg"), 1)
    fp_d, bp_d = _span(_face(fp, "plate"), 1), _span(_face(bp, "plate"), 1)
    closed = {
        "outer_width_mm": _r(W, 2), "outer_depth_mm": _r(D, 2),
        "back_wall_top_mm": _r(back_h, 2), "header_top_mm": _r(header_top, 2),
        "front_wall_mm": _r(front_h, 2),
        "side_wall_front_mm": _r(skin_front + t, 2), "side_wall_back_mm": _r(skin_back + t, 2),
        "header_leaves_mm": [_r(header_leaf, 2), _r(header_front, 2)], "return_flap_mm": _r(ret, 2),
        "slot_width_mm": _r(slot_w, 2), "slot_bed_mm": _r(bed, 2), "backrest_mm": _r(backrest, 2),
        "slot_bed_front_edge_mm": _r(front_leg + t, 2),
        "front_plate_top_mm": _r(fp_leg + t, 2), "back_plate_top_mm": _r(bp_leg + t, 2),
        "datum": "heights over the counter (z); tray panels read off the die + board",
    }

    def agree(fid, measured, expected, words):
        _finding(f, fid, "the die agrees with the solve", abs(measured - expected) <= TOL_MM, _r(measured, 3),
                 _r(expected, 3), words)

    agree("closed_width", W, g["W"], "Floor %.2f + 2 × %.1f board = %.2f mm wide (footprint %.0f)." % (
        _span(floor, 0), t, W, g["W"]))
    agree("closed_depth", D, g["D"], "Floor %.2f + 2 × %.1f board = %.2f mm deep (footprint %.0f)." % (
        _span(floor, 1), t, D, g["D"]))
    agree("back_wall_height", back_panel, g["back_wall_h"], "Back wall panel %.2f mm = the stack's top above the "
          "floor; %.2f mm over the counter." % (back_panel, back_h))
    agree("header_height", header_leaf, g["header_h"], "Header leaves %.2f + %.2f mm (doubled), top at %.2f mm." % (
        header_leaf, header_front, header_top))
    agree("front_wall_height", front_h, g["front_skin_h"] + t, "Front wall %.2f mm over the counter." % front_h)
    agree("side_taper_front", skin_front, g["front_skin_h"], "Side skin %.2f mm at the front = the front wall's." %
          skin_front)
    agree("side_taper_back", skin_back, g["back_wall_h"], "Side skin %.2f mm at the back = the back wall's." %
          skin_back)
    agree("return_flap", ret, g["return_mm"], "Return flap %.2f mm = back wall − 3.00 (it stops 3.00 above the "
          "floor, as ES3083's)." % ret)

    # -- clearances against the three product records -------------------------------------------------------------------
    pal, lip, balm = P["palette"], P["lipstick"], P["balm"]

    def clear(fid, rule, margin, need, words, measured=None):
        _finding(f, fid, rule, margin >= need - 1e-9, _r(measured if measured is not None else margin, 3),
                 ">= %g" % need, words)

    clear("slot_width_vs_palette", "slot width > palette width", slot_w - pal["width_mm"], 1e-6,
          "Slot %.2f mm (insert %.2f − 2 × board) against the palette's %.0f mm: %.2f mm clear (%.2f a side)." % (
              slot_w, ins_w, pal["width_mm"], slot_w - pal["width_mm"], (slot_w - pal["width_mm"]) / 2),
          measured=slot_w - pal["width_mm"])
    clear("slot_bed_vs_stack", "bed depth >= the stack", bed - g["stack_mm"], 0.0,
          "Bed %.2f mm against two palettes %.0f mm thick: %.2f mm spare in front of the front lid." % (
              bed, g["stack_mm"], bed - g["stack_mm"]))
    clear("stack_top_vs_back_wall", "back wall top >= the stack's top", back_panel - g["stack_top_h"], 0.0,
          "Back wall %.2f mm against the stack's top %.2f mm: equal by the owner's rule (\"as tall as the leaning "
          "palette's top\")." % (back_panel, g["stack_top_h"]))
    # [D-D13-1] the back wall's height against the owner's ruling, at his figures' precision
    ruled = float(record["owner_provisional"]["back_wall_mm"]["value"]) if "back_wall_mm" in record[
        "owner_provisional"] else None
    _finding(f, "back_wall_vs_owner_ruling", "the back wall stands where the owner ruled it (D-D13-1), at his figures' "
             "precision (0.01 mm)", ruled is not None and abs(round(back_panel, 2) - ruled) < 1e-9 and
             abs(round(back_h, 2) - BACK_WALL_RULED_OUTER_MM) < 1e-9,
             {"panel_mm": _r(back_panel, 4), "outer_mm": _r(back_h, 4)},
             {"panel_mm": ruled, "outer_mm": BACK_WALL_RULED_OUTER_MM},
             "Back wall %.4f mm above the tray floor (%.4f over the counter), read off the die; the owner's ruling "
             "182.12 (183.62): \"%s\"" % (back_panel, back_h, BACK_WALL_RULING))
    # [D-D13-2] the slot insert's tube closed square: each gusset read off the die and folded into the tube's section
    fm = _frame_measure(g, die)
    for gu in fm["gussets"]:
        _finding(f, "insert_gusset:%s" % gu["side"], "the slot insert's gusset closes the tube's end square: hinged on "
                 "the back leg's side edge from its foot, its corner square, its glue flap on its free leg, clear of "
                 "the tube's glue flap and inside the tube by >= 3 × board, unprinted", gu["closes"],
                 {k: v for k, v in gu.items() if k not in ("side", "closes")}, {"closes": True},
                 ("Gusset %s: %.2f up the back leg from its foot, %.2f along the base, its glue flap %.2f; %.2f clear "
                  "of the tube's glue flap, %.2f inside the bed and backrest; unprinted." % (
                      gu["side"], gu["up_the_back_leg_mm"], gu["along_the_base_mm"], gu["glue_flap_mm"],
                      gu["clear_of_the_tubes_glue_flap_mm"], gu["inside_the_tube_mm"])) if gu["present"] else
                 "Gusset %s: not on the die — the tube's end is open." % gu["side"])
    # the stack against the back at every lean the closed tube permits, at its drawn and rearmost seats (its keys as
    # far back as their slots let them, read off the die, and one fold's allowance behind its front leg)
    drawn_s, rear_s = fm["seats"]
    if fm["closed"]:
        least = min(drawn_s["least"], rear_s["least"])
        words = ("Stack's top-back corner at y %.2f as drawn (%.2f mm clear square); the back's inner face (back wall, "
                 "lock tabs, return flap) at %.2f. The tube closed square by its gussets leans only as its fit lets "
                 "it, %.2f° either way at most (the base's two folds: the back leg 0 … %.2f behind); at every lean in "
                 "[−%.2f°, +%.2f°] (%d samples, every %.2f°) the least clearance is %.2f at the drawn seat and %.2f at "
                 "the rearmost (its keys %.2f back in their slots, the junction %.2f further behind its front leg), "
                 "at +%.2f° (racking.slot_insert; departures: insert_sway, closed)." % (
                     g["stack_rear_y"], drawn_s["square"], g["back_inner_y"], fm["lean_max"], fm["back_mm"],
                     fm["lean_max"], fm["lean_max"], fm["samples"], FRAME_STEP_DEG, drawn_s["least"], rear_s["least"],
                     fm["ins_back"], g["fold_each"], rear_s["least_at"]))
    else:
        four = _sway_measure(g, die)
        least = min(s["at_limit"] for s in four["seats"])
        words = ("The slot insert's tube is not closed (%s): it sways as a four-bar until the stack's top-back corner "
                 "rests on the back's inner face — %.2f mm at the sway limit (racking.slot_insert)." % (
                     "; ".join("gusset %s %s" % (gu["side"], "does not close it" if gu["present"] else "missing")
                               for gu in fm["gussets"] if not gu["closes"]), least))
    clear("stack_rear_vs_back_wall", "the stack's top-back corner clear of the back's inner face by the house's "
          "clearance at every lean the closed tube permits, at the insert's drawn and rearmost seats (its key's play "
          "and the fold allowance taken)", least, g["clearance"], words, measured=least)
    corners = frame_fold_corners(g, fm["link"])
    every_fold = corners["least_clearance_mm"] if fm["closed"] else least
    clear("stack_rear_vs_back_wall_every_fold", "the same at every fold of the closed tube at either end of its "
          "allowance (32 tubes, each fold adding to both panels it joins; the key at the back of its play)",
          every_fold, g["clearance"],
          ("Least %.2f mm (the stack's corner %.2f back), with the folds at %s." % (
              corners["least_clearance_mm"], corners["stack_corner_moves_back_mm"],
              ", ".join("%s %.2f" % kv for kv in corners["at"].items()))) if fm["closed"] else
          "The tube is not closed: no frame to fold (stack_rear_vs_back_wall: %.2f)." % least, measured=every_fold)
    # the glue flap against the front leg (the reviewer's MJ-1): the base, read off the die, runs from the back leg's
    # outer face forward; the glue flap rises at its front end and must meet the front leg's INNER face, so the front
    # leg (outside it) stands in the board its keys stand in
    base = _span(_face(ins, "base"), 1)
    flap_y = g["r_y"] - base
    leg_y = stood["slot insert"][0]["y"] if stood.get("slot insert") else (g["f_y"], g["f_y"] + t)
    _finding(f, "insert_glue_flap_vs_front_leg", "the slot insert's glue flap rises against the inside of its front "
             "leg: the front leg's board (where its keys stand) and the glue flap's never the same board",
             abs(flap_y - leg_y[1]) <= TOL_MM,
             {"base_mm": _r(base, 3), "glue_flap_y_mm": [_r(flap_y, 3), _r(flap_y + t, 3)],
              "front_leg_y_mm": [_r(leg_y[0], 3), _r(leg_y[1], 3)]},
             {"glue_flap_front_face_y_mm": _r(leg_y[1], 3)},
             "Base %.2f mm from the back leg's outer face (y %.2f): the glue flap stands y %.2f…%.2f, the front leg "
             "(at its keys) y %.2f…%.2f — the front leg outside the glue flap, on the floor." % (
                 base, g["r_y"], flap_y, flap_y + t, leg_y[0], leg_y[1]))
    for name, hole_face, prod, plate_d, part in (("balm", g["balm_hole"], balm, fp_d, fp),
                                                 ("lipstick", g["lip_hole"], lip, bp_d, bp)):
        wanted_shape = g.get("hole_shape", "circle")
        if wanted_shape != "circle" or part.hole_shape != wanted_shape:
            _finding(f, "hole_shape_%s" % name, "drawn opening shape matches the requested profile",
                     part.hole_shape == wanted_shape, part.hole_shape, wanted_shape,
                     "The %s platform uses %s openings." % (name, part.hole_shape))
        drawn = [2 * r for _n, _c, r in part.holes]
        centres = sorted(c[0] for _n, c, _r2 in part.holes)
        dia = drawn[0]
        want_clear = float(record["owner_provisional"]["hole_clearance_mm"]["value"])
        worst = max(drawn, key=lambda v: abs(v - prod["diameter_mm"] - want_clear))
        _finding(f, "hole_vs_%s" % name, "every hole Ø = product + 1 mm (within %g)" % TOL_MM,
                 abs(worst - prod["diameter_mm"] - want_clear) <= TOL_MM, _r(worst - prod["diameter_mm"], 3),
                 _r(want_clear, 3), "%d holes drawn Ø %s against the %s's Ø %.0f: %.2f mm diametral (%.2f a side); "
                 "the owner's rule is + %.2f exactly." % (
                     len(drawn), "/".join(sorted({"%.2f" % v for v in drawn})), name, prod["diameter_mm"],
                     worst - prod["diameter_mm"], (worst - prod["diameter_mm"]) / 2, want_clear))
        webs = [b - a - dia for a, b in zip(centres, centres[1:])]
        clear("web_%s" % name, "web between holes >= 3 × board", min(webs), 3 * t,
              "Pitch %.2f − Ø %.2f = %.2f mm web." % (centres[1] - centres[0], dia, min(webs)))
        plate = _face(part, "plate")
        edge_d = (plate_d - dia) / 2
        edge_end = min(c[0] - r - plate.bounds[0] for _n, c, r in part.holes)
        edge_end = min(edge_end, min(plate.bounds[2] - c[0] - r for _n, c, r in part.holes))
        clear("hole_edge_%s_plate" % name, "a hole's edge to the plate's fold >= 3 × board", min(edge_d, edge_end),
              3 * t, "Hole edge to the plate's folds %.2f mm, to its ends %.2f mm." % (edge_d, edge_end))
        want = int(record["owner_provisional"]["%s_count" % name]["value"])
        _finding(f, "hole_count_%s" % name, "holes per row = the owner's count", len(drawn) == want, len(drawn),
                 want, "%d %s holes drawn, one per %s." % (len(drawn), name, name))
    clear("lipstick_body_visible", "the lipstick's body shows between its plate and its cap",
          lip["body_mm"] - g["back_plate_h"], 1e-6,
          "Back plate top %.0f mm, the lipstick's cap from %.0f mm: %.0f mm of body shows." % (
              g["back_plate_h"], lip["body_mm"], lip["body_mm"] - g["back_plate_h"]),
          measured=lip["body_mm"] - g["back_plate_h"])
    clear("balm_body_visible", "the balm's body shows between its plate and its cap",
          balm["body_mm"] - g["front_plate_h"], 1e-6,
          "Front plate top %.0f mm, the balm's cap from %.0f mm: %.0f mm of body shows." % (
              g["front_plate_h"], balm["body_mm"], balm["body_mm"] - g["front_plate_h"]),
          measured=balm["body_mm"] - g["front_plate_h"])
    for name, prod in (("lipstick", lip), ("balm", balm)):
        clear("%s_top_vs_back_wall" % name, "stick tops below the back wall's top and the header",
              g["back_wall_h"] - prod["height_mm"], 0.0,
              "The %s's top %.0f mm, the back wall's top (the header's foot) %.2f mm." % (
                  name, prod["height_mm"], g["back_wall_h"]))
    clear("front_wall_vs_front_row", "the front wall below the balms' top 25 mm",
          (balm["height_mm"] - 25.0) - g["front_skin_h"], 0.0,
          "Front wall %.2f mm above the floor, the balms' top band from %.0f mm." % (
              g["front_skin_h"], balm["height_mm"] - 25.0))
    clear("front_platform_vs_front_wall", "front platform clear of the doubled front wall",
          g["front_plate_y0"] - g["wall_in_y"], g["clearance"],
          "Front plate's front leg at y %.2f, the front wall's inner face at %.2f." % (g["front_plate_y0"],
                                                                                      g["wall_in_y"]))
    clear("platform_gap", "the two platforms' facing legs apart",
          (g["back_plate_y1"] - bp_d) - (g["front_plate_y0"] + fp_d), g["clearance"],
          "Front plate's back leg at y %.2f, back plate's front leg at %.2f (as drawn; at the full fold allowance the "
          "back leg stands %.2f further back: clearances_with_key_play)." % (
              g["front_plate_y0"] + fp_d, g["back_plate_y1"] - bp_d, A))
    clear("back_platform_vs_slot", "back platform clear of the slot insert",
          g["insert"]["front_y_mm"] - g["back_plate_y1"], g["clearance"],
          "Back plate's back leg at y %.2f, the slot insert's front leg at %.2f." % (
              g["back_plate_y1"], g["insert"]["front_y_mm"]))
    clear("platform_ends_vs_side_walls", "platform ends clear of the side liners",
          g["side_in_x"] - g["plate_len"] / 2, g["clearance"],
          "Plates %.2f mm long, the side liners' inner faces at ±%.2f." % (g["plate_len"], g["side_in_x"]))
    clear("slot_insert_vs_side_walls", "slot insert clear of the side liners", g["side_in_x"] - ins_w / 2,
          g["clearance"], "Insert %.2f mm wide (its wings fold inside it), the side liners at ±%.2f." % (
              ins_w, g["side_in_x"]))
    lip_top_y = g["lip_y"] + lip["diameter_mm"] / 2
    clear("lipsticks_vs_slot", "the lipsticks clear of the slot insert", g["insert"]["front_y_mm"] - lip_top_y,
          g["clearance"], "Lipsticks' backs at y %.2f, the slot insert's front at %.2f." % (
              lip_top_y, g["insert"]["front_y_mm"]))
    clear("sticks_in_plates", "every stick inside its plate's depth",
          min(g["edge"] + (g["balm_hole"] - balm["diameter_mm"]) / 2, g["edge"] +
              (g["lip_hole"] - lip["diameter_mm"]) / 2), 0.0, "Each stick's face lies inside its plate.")
    clear("palette_vs_insert_wings", "the palettes inside the wings", (slot_w - pal["width_mm"]) / 2, 0.0,
          "Each palette edge %.2f mm from its wing." % ((slot_w - pal["width_mm"]) / 2))
    # the floor's lock slots against every foot that stands on the floor, in plan (x across, y depth); a platform's
    # back leg stands anywhere from its drawn place to the full fold allowance behind it
    sl_len, sl_d, half = house("tab_base_mm") + 0.5, house("slot_depth_mm"), g["floor_w"] / 2
    fo = house("front_slot_offset_mm") * g["floor_w"] / house("principal_width_mm")
    run = g["skin_y1"] - g["skin_y0"]
    slots_plan = [_rect(sx - sl_len / 2, t, sx + sl_len / 2, t + sl_d) for sx in (-fo, fo)]
    for k in ("side_slot_centre_1_mm", "side_slot_centre_2_mm"):
        cy = g["skin_y0"] + house(k) * run / house("side_run_mm")
        slots_plan += [_rect(half - sl_d, cy - sl_len / 2, half, cy + sl_len / 2),
                       _rect(-half, cy - sl_len / 2, -half + sl_d, cy + sl_len / 2)]
    Lh = g["plate_len"] / 2
    feet = [_rect(-Lh, y0, Lh, y1) for y0, y1 in (
        (g["front_plate_y0"], g["front_plate_y0"] + t),
        (g["front_plate_y0"] + fp_d - t, g["front_plate_y0"] + fp_d + A),
        (g["back_plate_y1"] - bp_d, g["back_plate_y1"] - bp_d + t),
        (g["back_plate_y1"] - t, g["back_plate_y1"] + A))]
    feet.append(_rect(-ins_w / 2, g["insert"]["front_y_mm"], ins_w / 2, g["insert"]["rear_y_mm"] + g["fold_each"]))
    gap_plan = min(a.distance(b) for a in slots_plan for b in feet)
    play = LOCK_PLAY_MM / 2
    clear("floor_slots_clear_of_feet", "every house floor slot clear of the inserts' feet, the keys' play and the "
          "fold allowance taken", gap_plan - play, 0.5, "The nearest foot (a platform leg anywhere in its fold "
          "allowance, or the slot insert's base) stands %.2f mm from a house floor slot, %.2f with the keys' ±%.2f "
          "play." % (gap_plan, gap_plan - play, play), measured=gap_plan - play)
    lip_back_rear = lip_top_y + (g["lip_hole"] - lip["diameter_mm"]) / 2 + g["fold_each"]
    near = {"front platform to front wall": g["front_plate_y0"] - g["wall_in_y"] - play,
            "platform to platform, the front platform's back leg at the full fold allowance":
                (g["back_plate_y1"] - bp_d) - (g["front_plate_y0"] + fp_d + A) - 2 * play,
            "back platform, its back leg at the full fold allowance, to slot insert":
                g["insert"]["front_y_mm"] - (g["back_plate_y1"] + A) - 2 * play,
            "lipsticks, their row one fold back, to slot insert": g["insert"]["front_y_mm"] - lip_back_rear - 2 * play,
            "platform ends to side liners": g["side_in_x"] - g["plate_len"] / 2 - play,
            "slot insert to side liners": g["side_in_x"] - ins_w / 2 - play}
    worst_near = min(near, key=near.get)
    clear("clearances_with_key_play", "every clearance between parts holds with the keys' play and the fold allowance",
          near[worst_near], 0.5, "Each key ±%.2f mm each way, a platform's leg spacing up to %.2f over drawn (%.2f a "
          "fold): %s." % (play, A, g["fold_each"], "; ".join("%s %.2f" % kv for kv in near.items())),
          measured=near[worst_near])

    # -- the floor keys (the reviewer's M1): each insert keyed to the floor, one way round, at one place --------------
    for part_name in KEY_LAYOUT:
        tabs = stood.get(part_name, [])
        _finding(f, "key_count:%s" % part_name, "every insert carries its floor keys", len(tabs) == sum(
            len(v) for v in KEY_LAYOUT[part_name].values()), len(tabs),
            sum(len(v) for v in KEY_LAYOUT[part_name].values()), "%d key tabs on the %s." % (len(tabs), part_name))
        for tb in tabs:
            sl = kslots.get(tb["meets"])
            if sl is None:
                _finding(f, "key_lands:%s" % tb["id"], "every key tab, stood, lands in its own floor slot", False,
                         None, tb["meets"], "No floor slot named %s." % tb["meets"])
                continue
            (sx0, sx1), (sy0, sy1) = sl
            (tx0, tx1), (ty0, ty1) = tb["x"], tb["y"]
            inside = sx0 - 1e-9 <= tx0 and tx1 <= sx1 + 1e-9 and sy0 - 1e-9 <= ty0 and ty1 <= sy1 + 1e-9
            room = 0.0 if tb["leg"] == TIGHT_LEG else A
            got = [tx0 - sx0, sx1 - tx1, ty0 - sy0, sy1 - ty1]
            want = [play, play, play, play + room]
            _finding(f, "key_lands:%s" % tb["id"], "every key tab, stood at the drawn spacing, lands inside its own "
                     "floor slot: ±0.25 across x; 0.25 in front of it; behind it 0.25 on a front leg (keyed tight), "
                     "the fold allowance + 0.25 on a back leg", inside and all(abs(a2 - b2) <= TOL_MM
                                                                               for a2, b2 in zip(got, want)),
                     {"inside": inside, "play_mm": {"left": _r(got[0], 3), "right": _r(got[1], 3),
                                                    "front": _r(got[2], 3), "behind": _r(got[3], 3)}},
                     {"inside": True, "play_mm": {"left": play, "right": play, "front": play,
                                                  "behind": _r(play + room, 3)}},
                     "%s stands at x %.2f…%.2f, y %.2f…%.2f; %s is x %.2f…%.2f, y %.2f…%.2f." % (
                         tb["id"], tx0, tx1, ty0, ty1, tb["meets"], sx0, sx1, sy0, sy1))
        boxes = key_fits(tabs, kslots)
        one = (len(boxes) == 1 and boxes[0][0] <= 1e-9 and boxes[0][1] >= -1e-9 and boxes[0][2] <= 1e-9 and
               boxes[0][3] >= -1e-9 and max(abs(v) for v in boxes[0]) <= play + 1e-6)
        _finding(f, "key_one_place:%s" % part_name, "keyed: the part fits the floor at one place only, its drawn x "
                 "and y ± the play", one, {"places": len(boxes), "boxes_mm": [[_r(v, 3) for v in bx] for bx in boxes]},
                 {"places": 1, "box_mm": [-play, play, -play, play]},
                 "Searched every translation against every key slot: %d place(s)%s." % (
                     len(boxes), "" if not boxes else ", dx %.2f…%.2f, dy %.2f…%.2f" % boxes[0]))
        if "back leg" in KEY_LAYOUT[part_name]:
            # the fold allowance: every folded leg spacing from drawn to drawn + A seats the part at its drawn place,
            # and only there; a spacing outside drawn − 0.5 … drawn + A + 0.5 (the keys' play at either end) fails
            sweep = [A * i / 8 for i in range(9)]
            at = []
            for a in sweep:
                bx = key_fits(stood_keys(die, g, a)[part_name], kslots)
                at.append(len(bx) == 1 and all(abs(abs(v) - play) <= 1e-6 for v in bx[0]))
            lo, hi = seat_range(die, g, part_name)
            outside = [round(-2 * play - 0.25, 2), round(A + 2 * play + 0.25, 2)]
            refused = [not seats_at(die, g, part_name, a, kslots) for a in outside]
            ok = (all(at) and all(refused) and lo is not None and abs(lo + 2 * play) <= 0.01 and
                  abs(hi - (A + 2 * play)) <= 0.01)
            _finding(f, "key_seats_across_allowance:%s" % part_name, "folded anywhere in the fold allowance (leg "
                     "spacing drawn … drawn + %.2f) the part seats at its drawn place, at one place, ±0.25; a spacing "
                     "outside it does not seat" % A, ok,
                     {"swept_mm": [_r(a, 3) for a in sweep], "seats_at_each": at, "seat_range_mm": [lo, hi],
                      "controls_mm": outside, "controls_refused": refused},
                     {"seat_range_mm": [_r(-2 * play, 2), _r(A + 2 * play, 2)], "controls_refused": [True, True]},
                     "Back leg stood 0 … %.2f behind its drawn place (9 spacings): seats at %d of 9, each at one place "
                     "(the front leg's ±0.25 box); the seat holds from %s to %s mm over the drawn spacing; at %s mm "
                     "the part %s." % (A, sum(at), lo, hi, " and ".join("%+.2f" % a for a in outside),
                                       "seats nowhere" if all(refused) else "STILL SEATS"))
        ends = [0.0, A] if "back leg" in KEY_LAYOUT[part_name] else [0.0]
        turned = [bx for a in ends for bx in key_fits(turned_round(stood_keys(die, g, a)[part_name]), kslots)]
        _finding(f, "key_rejects_turned_round:%s" % part_name, "turned round, the part fits the floor nowhere",
                 not turned, len(turned), 0, "Turned 180° about the vertical, the %s's keys seat in %d place(s) "
                 "(every translation searched against every free key slot, its legs at %s mm over the drawn spacing; "
                 "the house's edge slots are filled by the tray's wall tabs)." % (
                     part_name, len(turned), " and ".join("%g" % a for a in ends)))
        # folded print side in (the reviewer's MINOR 1): the part is its own mirror image; across (front leg still at
        # the front) and front to back (turned as well). At every spacing in the fold allowance.
        spacings = [0.0, A] if "back leg" in KEY_LAYOUT[part_name] else [0.0]
        mirrored = {}
        for turned_too in (False, True):
            mirrored[turned_too] = [bx for a in spacings
                                    for bx in key_fits(print_side_in(stood_keys(die, g, a)[part_name], turned_too),
                                                       kslots)]
        blocked, how = [], "its keys seat nowhere either way"
        if mirrored[True] and part_name == "slot insert":
            # one keyed leg: mirrored front to back, its row of keys is the same row; the part is refused by its
            # footprint — wherever those keys seat, its base (y −rear … −front, mirrored) lies over the back platform
            bplan = _rect(-Lh, g["back_plate_y1"] - bp_d, Lh, g["back_plate_y1"])
            for bx in mirrored[True]:
                for dy in (bx[2], bx[3]):
                    fp_rev = _rect(-ins_w / 2 + bx[0], -g["r_y"] + dy, ins_w / 2 + bx[0], -g["f_y"] + dy)
                    blocked.append(fp_rev.intersection(bplan).area > 1.0)
            how = ("mirrored across, its keys seat nowhere; mirrored front to back its one row of keys seats (%d "
                   "place(s)) but there its base lies over the back platform (%d of %d seats blocked): refused by its "
                   "footprint, not by its keys — departures: insert_print_side_in" % (
                       len(mirrored[True]), sum(blocked), len(blocked)))
        ok = not mirrored[False] and (not mirrored[True] or (blocked and all(blocked)))
        _finding(f, "key_rejects_print_side_in:%s" % part_name, "folded print side in (mirrored), the part fits the "
                 "floor nowhere, either way round", ok,
                 {"mirrored_across_places": len(mirrored[False]), "mirrored_front_to_back_places": len(mirrored[True]),
                  "blocked_by_footprint": blocked},
                 {"mirrored_across_places": 0, "mirrored_front_to_back_places": 0},
                 "The %s folded print side in: %s." % (part_name, how))
    centre_y = {name: (min(v[0] for v in legs.values()) + max(v[1] for v in legs.values())) / 2
                for name, legs in g["legs"].items()}
    for a, b in (("front platform", "back platform"), ("back platform", "front platform")):
        dy = centre_y[b] - centre_y[a]
        # as drawn, a's centre moves by dy to reach b's place; turned round about the origin it sits at −centre_y[a]
        seats = [bx for sp in (0.0, A) for tabs, need in (
                     (stood_keys(die, g, sp)[a], dy), (turned_round(stood_keys(die, g, sp)[a]), centre_y[b] + centre_y[a]))
                 for bx in key_fits(tabs, kslots) if bx[2] - 10.0 <= need <= bx[3] + 10.0]
        _finding(f, "key_rejects_swap:%s" % a, "the platforms swapped, the %s fits nowhere at the other's place" % a,
                 not seats, len(seats), 0, "Moved %.2f mm to the %s's place (either way round, within 10 mm, its legs "
                 "at 0 and %g mm over the drawn spacing), the %s's keys seat in %d place(s)." % (
                     dy, b, A, a, len(seats)))
    rows_want = float(record["owner_provisional"]["row_spacing_mm"]["value"])
    rows_got = g["lip_y"] - g["balm_y"]
    hole_play = ((g["balm_hole"] - balm["diameter_mm"]) + (g["lip_hole"] - lip["diameter_mm"])) / 2
    fe = g["fold_each"]
    _finding(f, "rows_held_by_keys", "the rows stay the owner's 35 mm apart, held by the keys",
             abs(rows_got - rows_want) <= TOL_MM and all(f2["ok"] for f2 in f if f2["id"].startswith(
                 ("key_one_place:front platform", "key_one_place:back platform"))),
             {"rows_mm": _r(rows_got, 2), "holes_with_key_play_mm": [_r(rows_got - 2 * play, 2),
                                                                     _r(rows_got + 2 * play, 2)],
              "holes_with_key_play_and_fold_mm": [_r(rows_got - 2 * play - fe, 2), _r(rows_got + 2 * play + fe, 2)],
              "sticks_with_key_hole_and_fold_play_mm": [_r(rows_got - 2 * play - hole_play - fe, 2),
                                                        _r(rows_got + 2 * play + hole_play + fe, 2)]},
             {"rows_mm": _r(rows_want, 2)},
             "Rows %.2f mm apart; each platform keyed ±%.2f at its front leg, each hole row one fold behind it (0 … "
             "%.2f), so the hole rows stay %.2f…%.2f apart and the sticks' axes (± their play in the holes) "
             "%.2f…%.2f — no longer free to slide toward the slot insert." % (
                 rows_got, play, fe, rows_got - 2 * play - fe, rows_got + 2 * play + fe,
                 rows_got - 2 * play - hole_play - fe, rows_got + 2 * play + hole_play + fe))
    # the key slots: clear of the house's slots, of each other, of the floor's creases, of the sticks and other feet
    rects = {sid: _rect(x0, y0, x1, y1) for sid, ((x0, x1), (y0, y1)) in kslots.items()}
    ids = sorted(rects)
    web = 3 * t
    d_house = min(rects[i].distance(h) for i in ids for h in slots_plan)
    d_keys = min(rects[i].distance(rects[j]) for n, i in enumerate(ids) for j in ids[n + 1:])
    half_w = g["floor_w"] / 2
    d_edge = min(min(r.bounds[0] + half_w, half_w - r.bounds[2], r.bounds[1] - t, (g["D"] - t) - r.bounds[3])
                 for r in rects.values())
    clear("key_slots_web", "every key slot >= 3 × board from every other slot and from the floor's creases",
          min(d_house, d_keys, d_edge), web, "Key slots %.2f mm from the house's floor slots, %.2f from each other, "
          "%.2f from the floor's creases." % (d_house, d_keys, d_edge), measured=min(d_house, d_keys, d_edge))
    # a stick anywhere in its hole, ± the key's play, its row anywhere in its one fold's allowance (0 … fold_each
    # behind its drawn place): a back leg's slot stands open in front of the leg when the leg stands back in it
    stands = []
    for xs, yc, hole in ((g["balm_x"], g["balm_y"], g["balm_hole"]), (g["lip_x"], g["lip_y"], g["lip_hole"])):
        for x in xs:
            disc = Point(x, yc).buffer(hole / 2 + play, 64)
            stands.append(unary_union([disc, affinity.translate(disc, 0, fe)]).convex_hull)
    d_sticks = min(r.distance(c) for r in rects.values() for c in stands)
    own_feet = {"front platform": feet[:2], "back platform": feet[2:4], "slot insert": feet[4:]}
    d_feet = min(rects[sid].distance(ft) for sid in ids for name, fts in own_feet.items()
                 if not sid.startswith("key slot " + name) for ft in fts)
    clear("key_slots_clear_of_sticks_and_feet", "no stick and no other part's foot stands on a key slot",
          min(d_sticks, d_feet - play), 0.5, "The nearest stick (anywhere in its hole, ± the key's play, its row "
          "anywhere in its fold's allowance) stands %.2f mm from a key slot; the nearest other part's foot (a back "
          "leg anywhere in its fold allowance) %.2f (%.2f with the play)." % (d_sticks, d_feet, d_feet - play),
          measured=min(d_sticks, d_feet - play))
    # the orientation mark: inside each keyed part's front leg, on its reverse face (drawn flipped)
    for p in die.parts:
        if p.name not in KEY_LAYOUT:
            continue
        marks = [m for m in p.marks if m[0] == ORIENTATION_WORDS and m[3] == "front leg"]
        ok, words = len(marks) == 1, "no mark"
        if ok:
            text, size, face = marks[0][0], marks[0][2], marks[0][3]
            side = marks[0][4] if len(marks[0]) > 4 else "print"
            box = mark_box(marks[0])
            keys_holes = [tb["polygon"] for tb in p.tabs] + [polygon for _name, polygon in p.hole_polygons()]
            room = min([box.distance(k) for k in keys_holes] or [math.inf])
            ok = box.within(_face(p, face).buffer(-1.0)) and room >= 1.0 and side == "reverse"
            words = "\"%s\" on the %s's %s, %s face (drawn flipped top to bottom: upright on the unprinted face with " \
                    "the plate above), %.2f mm from its keys and holes" % (text, p.name, face, side, room)
        _finding(f, "orientation_mark:%s" % p.name, "the words \"%s\" inside the front leg, on its reverse face, clear "
                 "of keys and holes" % ORIENTATION_WORDS, ok, len(marks), 1, words + ".")

    # -- the die's own rules ---------------------------------------------------------------------------------------------
    for p in die.parts:
        o = p.outline()
        _finding(f, "one_outline:%s" % p.name, "one closed cut outline per part", o.geom_type == "Polygon" and
                 o.is_valid, o.geom_type, "Polygon", "The %s is one closed cut outline." % p.name)
        worst = 0.0
        for i, (_a, fa, _pa) in enumerate(p.faces):
            for _b, fb, _pb in p.faces[i + 1:]:
                worst = max(worst, fa.intersection(fb).area)
        _finding(f, "no_face_overlap:%s" % p.name, "no flat overlap inside a part", worst < 1e-6, _r(worst, 6), 0.0,
                 "No two panels of the %s overlap on the flat (largest %.6f mm²)." % (p.name, worst))
        bad = [n for n, c in p.creases if not c.within(o.buffer(1e-6))]
        _finding(f, "creases_inside:%s" % p.name, "creases inside the cut", not bad, len(bad), 0,
                 "Every crease of the %s lies inside its cut (%d outside)." % (p.name, len(bad)))
        hinge = []
        for n, c in p.creases:
            k = sum(1 for _fn, fc, _fp in p.faces if fc.boundary.buffer(1e-6).contains(c))
            if k != 2:
                hinge.append("%s (%d)" % (n, k))
        _finding(f, "creases_hinge:%s" % p.name, "every crease hinges exactly two panels", not hinge,
                 len(hinge), 0, "Every crease of the %s joins two panels%s." % (
                     p.name, "" if not hinge else ": not " + ", ".join(hinge)))
        out_holes = [name for name, polygon in p.hole_polygons()
                     if not any(polygon.within(fc) for _fn, fc, _fp in p.faces)]
        if p.holes:
            _finding(f, "holes_inside:%s" % p.name, "every hole inside one panel", not out_holes, len(out_holes), 0,
                     "Every hole of the %s lies inside its plate." % p.name)
    # the die's words (part labels, the title, the bar's words) clear of every cut outline AND its bleed (the
    # reviewer's MINOR 5: the labels crossed the bleed round the top tabs)
    bleeds = unary_union([p.outline().buffer(DIE_BLEED_MM, join_style=2) for p in die.parts])
    inside = [text for text, box in die_word_boxes(die) if box.intersects(bleeds)]
    clearance_w = min(box.distance(bleeds) for _t, box in die_word_boxes(die))
    _finding(f, "words_outside_cut", "the die's words outside every cut line and its %.0f mm bleed" % DIE_BLEED_MM,
             not inside, len(inside), 0,
             "Every part's name, the title and the bar's words sit outside every cut outline's bleed (nearest "
             "%.2f mm)%s." % (clearance_w, "" if not inside else ": not " + "; ".join(inside)))
    near = math.inf
    for i, a in enumerate(die.parts):
        for b in die.parts[i + 1:]:
            near = min(near, a.outline().distance(b.outline()))
    _finding(f, "no_part_overlap", "no flat overlap between parts", near > 5.0, _r(near, 2), "> 5",
             "Parts on the sheet are at least %.2f mm apart." % near)
    slots = {s["id"]: s for p in die.parts for s in p.slots}
    for p in die.parts:
        for tb in p.tabs:
            s = slots.get(tb["meets"])
            base = tb["base"].length
            if s is None:
                _finding(f, "tab_slot:%s" % tb["id"], "every lock tab meets a slot of its width + 0.5 mm", False,
                         None, _r(base + 0.5, 2), "No slot named %s." % tb["meets"])
                continue
            sb = s["polygon"].bounds
            sides = sorted([sb[2] - sb[0], sb[3] - sb[1]])          # slots are drawn square to the sheet
            if tb.get("kind") == "floor key":                       # a key: board + 0.5 across (±0.25 play)
                width_ok = abs(sides[0] - tb["slot_width_mm"]) <= TOL_MM
                width_want = _r(tb["slot_width_mm"], 2)
            else:                                                   # a wall's lock tab: the house's slot depth
                width_ok = sides[0] >= 2 * t
                width_want = ">= %g" % (2 * t)
            _finding(f, "tab_slot:%s" % tb["id"], "every lock tab meets a slot of its width + 0.5 mm",
                     abs(sides[1] - (tb["width_mm"] + LOCK_PLAY_MM)) <= TOL_MM and width_ok,
                     {"slot_length_mm": _r(sides[1], 2), "slot_width_mm": _r(sides[0], 2),
                      "tab_width_mm": _r(tb["width_mm"], 2), "tab_hinge_mm": _r(base, 2)},
                     {"slot_length_mm": _r(tb["width_mm"] + LOCK_PLAY_MM, 2), "slot_width_mm": width_want},
                     "%s (%.2f wide) meets %s (%.2f × %.2f)." % (tb["id"], tb["width_mm"], tb["meets"], sides[1],
                                                                 sides[0]))
    # -- every tab lands on its slot when folded (measured off the drawn die) ------------------------------------------
    fl_face = _face(tray, "floor")
    fx0, fy0, fx1, fy1 = fl_face.bounds
    crease = dict(tray.creases)
    for tb in tray.tabs:
        s = slots.get(tb["meets"])
        if s is None:
            continue
        sx0, sy0, sx1, sy1 = s["polygon"].bounds
        (hx0, hy0), (hx1, hy1) = tb["base"].coords[0], tb["base"].coords[-1]
        mx, my = (hx0 + hx1) / 2, (hy0 + hy1) / 2
        side = tb["id"][-2] if tb["id"][-1].isdigit() else tb["id"][-1]
        if tb["id"].startswith("front liner tab"):
            got, want, how = mx, (sx0 + sx1) / 2, "the tab's hinge centre X (folding keeps X) against the slot's"
        elif tb["id"].startswith("side liner tab"):
            A, A2 = crease["side skin / side spine " + side], crease["side spine / side liner " + side]
            (ax, ay), (bx, by) = A.coords[0], A.coords[-1]
            (cx2, cy2) = A2.coords[0]
            reflect, _n = _reflector(((ax + cx2) / 2, (ay + cy2) / 2), (bx - ax, by - ay))
            got = reflect((mx, my))[1]
            want, how = (sy0 + sy1) / 2, "the tab's hinge centre reflected back across the spine (Y) against the slot's"
        else:
            got = (mx - fx1) if side == "R" else (fx0 - mx)
            want = (sy0 + sy1) / 2 - fy1
            how = "the lock tab's neck height on the side's back edge against the lock slot's height on its crease"
        _finding(f, "tab_lands:%s" % tb["id"], "every lock tab lands on its slot when folded",
                 abs(got - want) <= TOL_MM, _r(got, 3), _r(want, 3), "%s meets %s: %s (%.3f against %.3f)." % (
                     tb["id"], tb["meets"], how, got, want))
    # -- every wall tab's tip against the tray's underside (the geometry verifier's minor: the liner tabs reached
    # 1.50 below it), read off the drawn die: the tray must stand on its floor (z = 0), not on its tabs ---------------
    hs = _span(_face(tray, "front skin"), 1)
    y_fl = crease["front spine / front liner"].coords[0][1]          # the front liner's hinge on the flat (Y)
    for tb in tray.tabs:
        poly = tb["polygon"]
        side = tb["id"][-2] if tb["id"][-1].isdigit() else tb["id"][-1]
        if tb["id"].startswith("front liner tab"):
            # the liner hangs from the wall's top (h = the skin's height) down the sheet's −Y: h = hs − (y_fl − Y)
            low = hs - (y_fl - poly.bounds[1])
            how = "the front liner hangs from the wall's top (h %.2f); its tab's tip %.2f below that" % (
                hs, y_fl - poly.bounds[1])
            through = True
        elif tb["id"].startswith("side liner tab"):
            # folded over the spine, the liner and its tabs stand where they reflect back across it: h = X − the
            # floor's crease (R) or the crease − X (L), as the skin's own height
            sk, sl = crease["side skin / side spine " + side], crease["side spine / side liner " + side]
            (ax, ay), (bx, by) = sk.coords[0], sk.coords[-1]
            reflect, _n = _reflector(((ax + sl.coords[0][0]) / 2, (ay + sl.coords[0][1]) / 2), (bx - ax, by - ay))
            xs = [reflect(p)[0] for p in poly.exterior.coords]
            low = (min(xs) - fx1) if side == "R" else (fx0 - max(xs))
            how = "the side liner's tab reflected back across the spine, its lowest point h %.2f" % low
            through = True
        else:
            # a side lock tab folds about the skin's back edge (constant Y), so its height is its X off the crease
            xs = [p[0] for p in poly.exterior.coords]
            low = (min(xs) - fx1) if side == "R" else (fx0 - max(xs))
            how = "the side lock tab folds about the skin's back edge; its lowest point h %.2f" % low
            through = False
        z = t + low
        ok = z >= -TOL_MM and (z <= t - TOL_MM if through else True)
        _finding(f, "tab_tip_vs_underside:%s" % tb["id"], "every wall tab, folded, stops at or above the tray's "
                 "underside (z >= 0: the tray stands on its floor, not on its tabs)" + (
                     "; a liner tab passes through its floor slot (z < board) and stops flush" if through else ""),
                 ok, {"tip_z_mm": _r(z, 3), "tip_h_mm": _r(low, 3)},
                 {"tip_z_mm": [0.0, _r(t, 3)] if through else ">= 0", "flush_z_mm": 0.0 if through else None},
                 "%s: %s, z %.3f over the counter (the underside z 0, the floor's top z %.2f)." % (
                     tb["id"], how, z, t))
    failed = [x["id"] for x in f if not x["ok"]]
    close = [x["id"] for x in f if x["ok"] and isinstance(x["measured"], (int, float)) and
             isinstance(x["expected"], str) and x["expected"].startswith(">=") and
             float(x["measured"]) - float(x["expected"][2:]) < 1.0 and x["rule"] != "6 holes per row (the owner's "
                                                                                   "record)"]
    racking = platform_racking(g, die)
    # the slot insert's sway (the geometry verifier's major): off the die's own panels and key slots
    racking["slot_insert"] = insert_sway(g, die)
    removed =[{"id": "stack_top_vs_header", "why": "the header's foot IS the back wall's top, so it compared one "
                "number with itself (always 0); the back wall's top against the stack is stack_top_vs_back_wall, "
                "read off the drawn die (the reviewer's MINOR 4)"}]
    return {"schema": FOLD_SCHEMA, "template": "%s/%s" % (TEMPLATE_ID, VERSION), "passed": not failed,
            "racking": racking,
            "closed": closed, "findings": f, "failed": failed, "close_under_1mm": close, "removed": removed}


# =====================================================================================================================
# the sightlines
# =====================================================================================================================


def _halfspaces_box(x0, x1, y0, y1, z0, z1):
    return [((1, 0, 0), x1), ((-1, 0, 0), -x0), ((0, 1, 0), y1), ((0, -1, 0), -y0), ((0, 0, 1), z1), ((0, 0, -1), -z0)]


def _halfspaces_oriented(origin, ax_n, ax_u, a0, a1, b0, b1, x0, x1):
    """A slab in the y-z plane spanned by ``ax_n`` and ``ax_u`` (unit 2-vectors in (y, z)), a ∈ [a0, a1] along n,
    b ∈ [b0, b1] along u, x ∈ [x0, x1]; ``origin`` (y, z)."""
    oy, oz = origin
    n3, u3 = (0, ax_n[0], ax_n[1]), (0, ax_u[0], ax_u[1])
    on, ou = oy * ax_n[0] + oz * ax_n[1], oy * ax_u[0] + oz * ax_u[1]
    return [(n3, on + a1), (tuple(-v for v in n3), -(on + a0)), (u3, ou + b1), (tuple(-v for v in u3), -(ou + b0)),
            ((1, 0, 0), x1), ((-1, 0, 0), -x0)]


def _seg_hits_convex(e, p, planes, s_max=1.0 - 1e-7):
    lo, hi = 1e-9, s_max
    d = (p[0] - e[0], p[1] - e[1], p[2] - e[2])
    for (nx, ny, nz), off in planes:
        num = off - (nx * e[0] + ny * e[1] + nz * e[2])
        den = nx * d[0] + ny * d[1] + nz * d[2]
        if abs(den) < 1e-15:
            if num < 0:
                return False
            continue
        s = num / den
        if den > 0:
            hi = min(hi, s)
        else:
            lo = max(lo, s)
        if lo > hi:
            return False
    return hi - lo > 1e-9


def _seg_hits_cylinder(e, p, cx, cy, r, z0, z1, s_max=1.0 - 1e-7):
    dx, dy, dz = p[0] - e[0], p[1] - e[1], p[2] - e[2]
    fx, fy = e[0] - cx, e[1] - cy
    a = dx * dx + dy * dy
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - r * r
    if a < 1e-15:
        return False
    disc = b * b - 4 * a * c
    if disc <= 0:
        return False
    sq = math.sqrt(disc)
    lo, hi = max((-b - sq) / (2 * a), 1e-9), min((-b + sq) / (2 * a), s_max)
    if abs(dz) < 1e-15:
        if not (z0 <= e[2] <= z1):
            return False
    else:
        sa, sb = (z0 - e[2]) / dz, (z1 - e[2]) / dz
        lo, hi = max(lo, min(sa, sb)), min(hi, max(sa, sb))
    return hi - lo > 1e-9


POSE_KEYS = ("front platform", "back platform", "slot insert", "balm", "lipstick")


def _pose(pose: dict | None) -> dict:
    """Where each part sits against its drawn place, (dx, dy) mm: the platforms and the slot insert within their keys'
    play, the sticks within their holes (on top of their platform's), the palettes across the slot (``palettes_x``)."""
    out = {k: (0.0, 0.0) for k in POSE_KEYS}
    out["palettes_x"] = 0.0
    out["insert_lean_deg"] = 0.0          # the slot insert's front leg leaned back (its closed tube: frame_pose)
    out.update(pose or {})
    return out


def _insert_place(g: dict, P: dict) -> dict:
    """The slot insert's moving panels in the pose, in (y, z): the junction ``b`` and the front lid's bottom ``p0``,
    the lean axes ``n`` (into the stack) and ``u`` (up the lean), and the front leg's slab (None: the drawn upright
    box) — at its keyed place + (dx, dy) and leaned by ``insert_lean_deg`` (D-D13-2: the closed tube's ``frame_pose``
    on ``insert_linkage``)."""
    _idx, idy = P["slot insert"]
    t = g["t"]
    n, u = (g["cos"], -g["sin"]), (g["sin"], g["cos"])
    lean = P.get("insert_lean_deg", 0.0)
    if not lean:                          # the drawn tube: exactly as before the sway was named
        return {"p0": (g["p0_y"] + idy, g["p0_h"] + t), "b": (g["b_y"] + idy, g["bed_low_h"] + t), "n": n, "u": u,
                "leg": None}
    link = insert_linkage(g)
    sw = frame_pose(link, lean)
    p0, b = sw["move"]((g["p0_y"], g["p0_h"])), sw["move"](link["B0"])
    a = math.radians(lean)
    return {"p0": (p0[0] + idy, p0[1] + t), "b": (b[0] + idy, b[1] + t), "n": sw["rotate"](n), "u": sw["rotate"](u),
            "leg": {"origin": (link["O1"][0] + idy, link["O1"][1] + t), "n": _lean((1.0, 0.0), a),
                    "u": _lean((0.0, 1.0), a), "height": link["panels"]["front leg"]}}


def _stick_xy(g: dict, P: dict) -> dict:
    """Each stick's axis (x, y) in the pose: its hole's place + its platform's shift + its own shift in its hole."""
    (fdx, fdy), (bdx, bdy) = P["front platform"], P["back platform"]
    (sbx, sby), (slx, sly) = P["balm"], P["lipstick"]
    return {"balm": [(x + fdx + sbx, g["balm_y"] + fdy + sby) for x in g["balm_x"]],
            "lipstick": [(x + bdx + slx, g["lip_y"] + bdy + sly) for x in g["lip_x"]]}


def scene(g: dict, products: dict, own: dict, pose: dict | None = None) -> list:
    """The occluders: (name, kind, data). Heights are z (over the counter). ``pose`` moves the keyed parts and the
    sticks off their drawn places (see ``_pose``); the tray never moves."""
    P = _pose(pose)
    t, W, D = g["t"], g["W"], g["D"]
    pal, lip, balm = products["palette"], products["lipstick"], products["balm"]
    sp = g["spine"]
    occ = [("front wall", "box", _halfspaces_box(-W / 2, W / 2, 0, sp, 0, g["front_skin_h"] + t)),
           ("back wall, return flap and header", "box",
            _halfspaces_box(-W / 2, W / 2, g["back_inner_y"], D, 0, g["back_wall_h"] + t + g["header_h"]))]
    slope = (g["back_wall_h"] - g["front_skin_h"]) / (g["skin_y1"] - g["skin_y0"])
    for side, sgn in (("right", 1), ("left", -1)):
        x0, x1 = (W / 2 - sp, W / 2) if sgn > 0 else (-W / 2, -W / 2 + sp)
        # z <= t + front + slope (y − y0)  ->  −slope·y + z <= t + front − slope·y0
        top = ((0, -slope, 1), t + g["front_skin_h"] - slope * g["skin_y0"])
        occ.append(("%s side wall" % side, "box",
                    _halfspaces_box(x0, x1, g["skin_y0"], g["skin_y1"], 0, g["back_wall_h"] + t + 1) + [top]))
    for which, y0, d, hgt in (("front", g["front_plate_y0"], g["front_plate_d"], g["front_plate_h"]),
                              ("back", g["back_plate_y1"] - g["back_plate_d"], g["back_plate_d"], g["back_plate_h"])):
        L = g["plate_len"] / 2
        dx, dy = P["%s platform" % which]
        y0 += dy
        occ.append(("%s platform plate" % which, "box", _halfspaces_box(-L + dx, L + dx, y0, y0 + d, t + hgt - t,
                                                                        t + hgt)))
        occ.append(("%s platform front leg" % which, "box", _halfspaces_box(-L + dx, L + dx, y0, y0 + t, t, t + hgt)))
        occ.append(("%s platform back leg" % which, "box", _halfspaces_box(-L + dx, L + dx, y0 + d - t, y0 + d, t,
                                                                           t + hgt)))
    idx, idy = P["slot insert"]
    place = _insert_place(g, P)
    n, u = place["n"], place["u"]                   # lid normal into the stack, up the lean, in (y, z)
    p0 = place["p0"]
    hw, px = pal["width_mm"] / 2, idx + P["palettes_x"]
    occ.append(("front palette", "box", _halfspaces_oriented(p0, n, u, 0, pal["thickness_mm"], 0, pal["height_mm"],
                                                             -hw + px, hw + px)))
    occ.append(("back palette", "box", _halfspaces_oriented(p0, n, u, pal["thickness_mm"], 2 * pal["thickness_mm"],
                                                            0, pal["height_mm"], -hw + px, hw + px)))
    iw = g["insert"]["width_mm"] / 2
    b = place["b"]
    occ.append(("slot bed", "box", _halfspaces_oriented(b, n, u, -g["insert"]["bed_mm"], 0, -t, 0, -iw + idx,
                                                        iw + idx)))
    occ.append(("slot backrest", "box", _halfspaces_oriented(b, n, u, 0, t, 0, g["insert"]["backrest_mm"],
                                                             -iw + idx, iw + idx)))
    if place["leg"] is None:
        occ.append(("slot front leg", "box", _halfspaces_box(-iw + idx, iw + idx, g["f_y"] + idy, g["f_y"] + idy + t,
                                                             t, g["f_h"] + t)))
    else:                                           # swayed: the leg leans on its hinge at the base's front crease
        lg = place["leg"]
        occ.append(("slot front leg", "box", _halfspaces_oriented(lg["origin"], lg["n"], lg["u"], -t, 0, 0,
                                                                  lg["height"], -iw + idx, iw + idx)))
    for side, x0, x1 in (("left", -iw, -iw + t), ("right", iw - t, iw)):
        occ.append(("slot wing %s" % side, "box", _halfspaces_oriented(b, n, u, -g["insert"]["bed_mm"], 0, 0,
                                                                       g["insert"]["backrest_mm"], x0 + idx,
                                                                       x1 + idx)))
    xy = _stick_xy(g, P)
    for i, (x, y) in enumerate(xy["balm"]):
        occ.append(("balm %d" % (i + 1), "cyl", (x, y, balm["diameter_mm"] / 2, t, t + balm["height_mm"])))
    for i, (x, y) in enumerate(xy["lipstick"]):
        occ.append(("lipstick %d" % (i + 1), "cyl", (x, y, lip["diameter_mm"] / 2, t, t + lip["height_mm"])))
    return occ


def _first_hit(e, p, occ, skip):
    for name, kind, data in occ:
        if name == skip:
            continue
        hit = _seg_hits_convex(e, p, data) if kind == "box" else _seg_hits_cylinder(e, p, *data)
        if hit:
            return name
    return None


def _sight(g: dict, products: dict, own: dict, pose: dict | None = None, *, sticks: bool = True,
           lid: bool = True) -> dict:
    P = _pose(pose)
    t = g["t"]
    pal, lip, balm = products["palette"], products["lipstick"], products["balm"]
    e = (0.0, -float(own["eye_front_mm"]), float(own["eye_height_mm"]))
    band = float(own["visible_band_mm"])
    occ = scene(g, products, own, P)
    xy = _stick_xy(g, P)
    out_sticks = []
    for prod, rec in (("balm", balm), ("lipstick", lip)) if sticks else ():
        r = rec["diameter_mm"] / 2
        top = t + rec["height_mm"]
        for i, (x, yc) in enumerate(xy[prod]):
            name = "%s %d" % (prod, i + 1)
            fy = yc - r
            samples, hidden = [], {}
            for k in range(int(band) + 1):
                z = top - band + k
                hit = _first_hit(e, (x, fy, z), occ, name)
                samples.append(hit is None)
                if hit:
                    hidden[hit] = hidden.get(hit, 0) + 1
            rays = {}
            for label, z in (("centre", t + rec["height_mm"] / 2), ("top", top)):
                hit = _first_hit(e, (x, fy, z), occ, name)
                rays[label] = {"z_mm": _r(z, 2), "visible": hit is None, "occluder": hit}
            frac = sum(samples) / len(samples)
            out_sticks.append({"item": name, "front_face_centreline": {"x_mm": _r(x, 2), "y_mm": _r(fy, 2)},
                               "band_z_mm": [_r(top - band, 2), _r(top, 2)], "samples": len(samples),
                               "visible_fraction": _r(frac, 4), "pass": frac >= 1.0 - 1e-12,
                               "limiting_occluders": sorted(hidden, key=lambda k: (-hidden[k], k)), "rays": rays})
    out = {"eye": {"x_mm": 0.0, "y_mm": e[1], "z_mm": e[2],
                   "words": "the eye 500 mm in front of the front edge, 350 mm above the counter, on the centre line"},
           "sticks": out_sticks, "lid": None}
    if lid:
        out["lid"] = _lid(g, products, P, e, occ)
    out["passed"] = all(s["pass"] for s in out_sticks) and (out["lid"] is None or out["lid"]["pass"])
    return out


def _lid(g: dict, products: dict, P: dict, e: tuple, occ: list) -> dict:
    """The front palette's lid above the sticks' tops, sampled every 5 mm across and every 1 mm up the lean."""
    t = g["t"]
    pal, lip, balm = products["palette"], products["lipstick"], products["balm"]
    place = _insert_place(g, P)
    n, u = place["n"], place["u"]
    idx, _idy = P["slot insert"]
    p0y, p0z = place["p0"]
    stick_top = t + max(lip["height_mm"], balm["height_mm"])
    hw, px = pal["width_mm"] / 2, idx + P["palettes_x"]
    xs = [-hw + px + 5.0 * k for k in range(int(round(pal["width_mm"] / 5.0)) + 1)]
    b_start = max(0.0, (stick_top - p0z) / u[1])
    bs = [b_start + k for k in range(int(math.floor(pal["height_mm"] - b_start)) + 1)]
    lid_hidden, lid_total, lid_vis = {}, 0, 0
    whole_vis = whole_total = 0
    for x in xs:
        for b in range(int(pal["height_mm"]) + 1):
            pt = (x, p0y + b * u[0] - 1e-6 * n[0], p0z + b * u[1] - 1e-6 * n[1])
            hit = _first_hit(e, pt, occ, "front palette")
            whole_total += 1
            whole_vis += hit is None
        for b in bs:
            pt = (x, p0y + b * u[0] - 1e-6 * n[0], p0z + b * u[1] - 1e-6 * n[1])
            hit = _first_hit(e, pt, occ, "front palette")
            lid_total += 1
            if hit is None:
                lid_vis += 1
            else:
                lid_hidden[hit] = lid_hidden.get(hit, 0) + 1
    lid_rays = {}
    for label, b in (("centre", pal["height_mm"] / 2), ("top", pal["height_mm"])):
        pt = (px, p0y + b * u[0] - 1e-6 * n[0], p0z + b * u[1] - 1e-6 * n[1])
        hit = _first_hit(e, pt, occ, "front palette")
        lid_rays[label] = {"y_mm": _r(pt[1], 2), "z_mm": _r(pt[2], 2), "visible": hit is None, "occluder": hit}
    lid_frac = lid_vis / lid_total if lid_total else 0.0
    return {"item": "front palette lid above the sticks' tops",
            "region": {"x_mm": [_r(-hw + px, 2), _r(hw + px, 2)], "x_step_mm": 5.0,
                       "along_lean_mm": [_r(b_start, 3), _r(pal["height_mm"], 3)], "along_step_mm": 1.0,
                       "z_from_mm": _r(stick_top, 2), "z_to_mm": _r(p0z + pal["height_mm"] * u[1], 2),
                       "words": "the lid face (the front palette's front face) sampled every 5 mm across and every "
                                "1 mm up the lean, from where it rises above the tallest stick's top to its top edge"},
            "samples": lid_total, "visible_fraction": _r(lid_frac, 4), "pass": lid_frac >= 1.0 - 1e-12,
            "limiting_occluders": sorted(lid_hidden, key=lambda k: (-lid_hidden[k], k)), "rays": lid_rays,
            "whole_lid_visible_fraction": _r(whole_vis / whole_total, 4)}


def _play(g: dict, products: dict, own: dict) -> dict:
    lock = LOCK_PLAY_MM / 2
    return {"key_mm": lock,
            "balm_in_hole_mm": _r((g["balm_hole"] - products["balm"]["diameter_mm"]) / 2),
            "lipstick_in_hole_mm": _r((g["lip_hole"] - products["lipstick"]["diameter_mm"]) / 2),
            "slot_insert_mm": lock,
            "palettes_across_slot_mm": _r((float(own["slot_width_mm"]) - products["palette"]["width_mm"]) / 2),
            "fold_each_mm": _r(g["fold_each"])}


def _tol_pose(pl: dict, sxf, syf, sxb, syb, ix=0, iy=0, px=0, row_x=None) -> dict:
    """A pose at the play's corners: the front row (platform + balms) by sxf/syf, the back row by sxb/syb, the slot
    insert by ix/iy, the palettes by px (each −1, 0 or +1). Backward (+1) a hole row also takes its one fold's
    allowance behind its keyed front leg, and the slot insert its junction's (``fold_each_mm``); forward a fold adds
    nothing. ``row_x`` overrides each row's whole x shift (mm, the platform taking its key's play and the stick the
    rest) for the margin search."""
    lock, fe = pl["key_mm"], pl.get("fold_each_mm", 0.0)
    hb, hl = pl["balm_in_hole_mm"], pl["lipstick_in_hole_mm"]
    fx, bx = (sxf * (lock + hb), sxb * (lock + hl)) if row_x is None else (sxf * row_x, sxb * row_x)
    return {"front platform": (sxf * lock, syf * lock), "balm": (fx - sxf * lock, syf * hb + (fe if syf > 0 else 0)),
            "back platform": (sxb * lock, syb * lock), "lipstick": (bx - sxb * lock, syb * hl + (fe if syb > 0 else 0)),
            "slot insert": (ix * lock, iy * lock + (fe if iy > 0 else 0)),
            "palettes_x": px * pl["palettes_across_slot_mm"]}


def sight_tolerance(g: dict, products: dict, own: dict, *, limit_mm: float = 8.0, depth_limit_mm: float = 20.0) -> dict:
    """The sightline with every keyed part at its locked place ± its key's play and every stick ± its own play in its
    hole, worst case both ways: every corner of that play evaluated, then each worst direction pushed beyond the play
    (bisected to 0.01 mm) to give the margin."""
    pl = _play(g, products, own)
    corners = list(itertools.product((-1, 1), repeat=6))
    worst = {}
    for sxf, syf, sxb, syb, ix, iy in corners:
        pose = _tol_pose(pl, sxf, syf, sxb, syb, ix, iy)
        for s in _sight(g, products, own, pose, lid=False)["sticks"]:
            w = worst.get(s["item"])
            if w is None or s["visible_fraction"] < w["min_visible_fraction"]:
                worst[s["item"]] = {"item": s["item"], "min_visible_fraction": s["visible_fraction"],
                                    "at": {"front_row": [sxf, syf], "back_row": [sxb, syb], "slot_insert": [ix, iy]},
                                    "limiting_occluders": s["limiting_occluders"]}
    lid_min, lid_n = 1.0, 0
    for ix, iy, px in itertools.product((-1, 1), repeat=3):
        res = _sight(g, products, own, _tol_pose(pl, 0, 0, 0, 0, ix, iy, px), sticks=False)
        lid_min, lid_n = min(lid_min, res["lid"]["visible_fraction"]), lid_n + 1
    row = pl["key_mm"] + max(pl["balm_in_hole_mm"], pl["lipstick_in_hole_mm"])

    def first_fail(pose_at, limit=limit_mm):
        """The least whole shift s in [row, limit] (bisected to 0.01) at which a stick's band loses a sample."""
        def bad(s):
            res = _sight(g, products, own, pose_at(s), lid=False)
            failing = [x["item"] for x in res["sticks"] if not x["pass"]]
            return failing
        if bad(row):
            return row, bad(row)
        if not bad(limit):
            return None, []
        lo, hi = row, limit
        while hi - lo > 0.01:
            mid = (lo + hi) / 2
            if bad(mid):
                hi = mid
            else:
                lo = mid
        return hi, bad(hi)
    def worst_of(tries, words, limit=limit_mm):
        """The least limit over the tried directions (None: no sample lost up to ``limit`` in any of them)."""
        hit = [x for x in tries if x["limit_mm"] is not None]
        w = min(hit, key=lambda x: x["limit_mm"]) if hit else None
        return {"rows": words, "tried": tries, "limit_mm": w["limit_mm"] if w else None, "allowed_mm": _r(row, 2),
                "margin_mm": _r(w["limit_mm"] - row, 2) if w else None,
                "worst": {k: w[k] for k in ("front_row", "back_row", "first_to_fail")} if w else None,
                "words": ("first lost at %.2f mm each row, %.2f past the play" % (w["limit_mm"], w["limit_mm"] - row)
                          if w else "no sample lost up to %.2f mm in any direction tried" % limit)}
    apart = []
    for sign, words in ((1, "rows apart across: balms toward +x (the shopper's right), lipsticks toward −x; each row "
                            "at each corner of its depth play"),
                        (-1, "rows apart across: balms toward −x, lipsticks toward +x; each row at each corner of its "
                             "depth play")):
        tries = []
        for syf, syb in itertools.product((-1, 1), repeat=2):
            lim, items = first_fail(lambda s, syf=syf, syb=syb: _tol_pose(pl, sign, syf, -sign, syb, row_x=s))
            tries.append({"front_row": "back" if syf > 0 else "forward", "back_row": "back" if syb > 0 else "forward",
                          "limit_mm": None if lim is None else _r(lim, 2), "first_to_fail": items})
        apart.append(worst_of(tries, words))
    depth = []
    for sign in (1, -1):
        tries = []
        for syf, syb in itertools.product((-1, 1), repeat=2):
            def pose_y(s, sign=sign, syf=syf, syb=syb):
                p = _tol_pose(pl, sign, syf, -sign, syb)
                lock = pl["key_mm"]
                p.update({"balm": (p["balm"][0], syf * (s - lock)), "lipstick": (p["lipstick"][0], syb * (s - lock))})
                return p
            lim, items = first_fail(pose_y, depth_limit_mm)
            tries.append({"front_row": "back" if syf > 0 else "forward", "back_row": "back" if syb > 0 else "forward",
                          "limit_mm": None if lim is None else _r(lim, 2), "first_to_fail": items})
        # searched to depth_limit_mm (20): past a platform's racked drift (fold check: racking), not only its play
        depth.append(worst_of(tries, "rows moved in depth, each way; across at the play's corner (balms %s, "
                                     "lipsticks %s)" % (("+x", "−x") if sign > 0 else ("−x", "+x")), depth_limit_mm))
    # yaw: the translation search and the corners hold each part square; its keys still let it turn a little — at
    # most the key play over the span of its TIGHT leg's outer tab ends (the back leg is free in depth over the fold
    # allowance, so only the front leg holds the turn). Bound what that moves a stick by.
    yaw = []
    for part, xs_, row_y in (("front platform", g["balm_x"], g["balm_y"]), ("back platform", g["lip_x"], g["lip_y"])):
        legs_ = g["legs"][part]
        spans = []
        for leg in legs_:
            if leg != TIGHT_LEG:
                continue
            ks = [k for k in g["keys"] if k["part"] == part and k["leg"] == leg]
            spans.append(max(k["x_mm"] + k["width_mm"] / 2 for k in ks) - min(k["x_mm"] - k["width_mm"] / 2
                                                                              for k in ks))
        rad = LOCK_PLAY_MM / max(spans)
        # the turn's pivot lies anywhere between the legs (the back leg up to the fold allowance behind its drawn
        # place): bound the row's arm by its farthest leg face
        faces = [v for leg, (y0, y1) in legs_.items() for v in (y0, y1 + (0.0 if leg == TIGHT_LEG else g["allowance"]))]
        arm = max(abs(row_y - v) for v in faces)
        yaw.append({"part": part, "outer_tab_span_mm": _r(max(spans), 2), "yaw_max_rad": _r(rad, 5),
                    "stick_depth_shift_max_mm": _r(rad * max(abs(x) for x in xs_), 3),
                    "row_arm_mm": _r(arm, 2), "stick_across_shift_max_mm": _r(rad * arm + 1e-9, 3)})
    least_across = min([m["margin_mm"] for m in apart if m["margin_mm"] is not None] or [math.inf])
    depth_lims = [m["limit_mm"] for m in depth if m["limit_mm"] is not None]
    yaw_ok = all(y["stick_across_shift_max_mm"] < least_across and
                 (not depth_lims or y["stick_depth_shift_max_mm"] < min(depth_lims) - row) for y in yaw)
    sticks = [worst[k] for k in sorted(worst, key=lambda n: (n.split()[0], int(n.split()[1])))]
    passed = (all(s["min_visible_fraction"] >= 1.0 - 1e-12 for s in sticks) and lid_min >= 1.0 - 1e-12 and yaw_ok)
    return {"play": dict(pl, row_total_mm=_r(row)),
            "words": ("each platform at its keyed place ± %.2f mm each way (slot = tab + 0.5), each stick ± its own "
                      "%.2f mm in its hole on top of that (hole = product + 1), each hole row backward also its one "
                      "fold's allowance (0 … %.2f), the slot insert ± %.2f (backward + its fold's %.2f), the palettes "
                      "± %.2f across the slot: every corner of the rows' and the insert's play evaluated (%d poses) "
                      "for the sticks, every corner of the insert's and the palettes' (%d poses) for the lid; the "
                      "margins push each worst direction past the play until a sample is lost (bisected to "
                      "0.01 mm)" % (pl["key_mm"], pl["balm_in_hole_mm"], pl["fold_each_mm"], pl["slot_insert_mm"],
                                    pl["fold_each_mm"], pl["palettes_across_slot_mm"], len(corners), lid_n)),
            "stick_poses": len(corners), "lid_poses": lid_n, "sticks": sticks,
            "yaw": {"parts": yaw, "within_margins": yaw_ok,
                    "words": "a keyed platform may still turn by at most the key play over its front (tight) leg's "
                             "outer tab span (its back leg is free in depth over the fold allowance); about a pivot "
                             "anywhere between its legs that moves a stick by the shifts listed (the row's arm to its "
                             "farthest leg face), inside the across margin and the depth margin "
                             "(none lost to %.2f mm), so the corners above stay the worst case" % depth_limit_mm},
            "lid_min_visible_fraction": _r(lid_min, 4), "passed": passed,
            "margins": {"rows_apart_across": apart, "rows_in_depth": depth,
                        "least_margin_mm": min([m["margin_mm"] for m in apart + depth
                                                if m["margin_mm"] is not None] or [None])}}


def sight_at_sway(g: dict, products: dict, own: dict) -> dict:
    """The sightline at the slot insert's lean limits (D-D13-2; fold-check.json racking.slot_insert): the insert at
    each seat (drawn; rearmost: its key's play + one fold's allowance behind), its closed tube leaned to each end of
    what its fit permits (−max, +max), the palettes across the slot at −, 0 and + their play — every stick's band and
    the lid above the sticks' tops."""
    m = _frame_measure(g, build_die(g))
    pal_play = (float(own["slot_width_mm"]) - products["palette"]["width_mm"]) / 2
    poses = []
    for s in m["seats"]:
        for lean in (-m["lean_max"], m["lean_max"]):
            for px in (-1, 0, 1):
                res = _sight(g, products, own, {"slot insert": (0.0, s["behind"]), "insert_lean_deg": lean,
                                                "palettes_x": px * pal_play})
                poses.append({"seat": s["seat"], "insert_behind_drawn_mm": _r(s["behind"], 2),
                              "front_leg_lean_deg": _r(lean, 2), "palettes_x_mm": _r(px * pal_play, 2),
                              "sticks_passing": sum(1 for x in res["sticks"] if x["pass"]),
                              "sticks": len(res["sticks"]),
                              "lid_visible_fraction": res["lid"]["visible_fraction"],
                              "whole_lid_visible_fraction": res["lid"]["whole_lid_visible_fraction"],
                              "lid_limiting_occluders": res["lid"]["limiting_occluders"], "passed": res["passed"]})
    return {"words": "the slot insert at each seat, its closed tube leaned to each end of the lean its fit permits "
                     "(D-D13-2; fold-check.json racking.slot_insert), the palettes across the slot at each end of "
                     "their play and centred: every stick's top 25 mm and the lid above the sticks' tops",
            "poses": poses, "passed": all(p["passed"] for p in poses),
            "lid_min_visible_fraction": min(p["lid_visible_fraction"] for p in poses),
            "whole_lid_min_visible_fraction": min(p["whole_lid_visible_fraction"] for p in poses)}


def sightlines(record: dict, *, max_raise_mm: int = 120) -> dict:
    """The owner's sightline check for this form, and — if it fails — the least whole-mm raise of the slot or of the
    back platform that passes (searched, listed, re-run). When it passes at the drawn places, it is run again with the
    keys' and the holes' play (``sight_tolerance``)."""
    if record.get("schema") in (PRODUCT_GRID_SCHEMA, "counter_tray_header/product-grid-2"):
        return product_tray_sightlines(record)
    products = {name: {k: f["value"] for k, f in vals.items()} for name, vals in record["products"].items()}
    own = {k: f["value"] for k, f in record["owner_provisional"].items()}
    g = _geometry(products, own)
    first = _sight(g, products, own)
    out = {"schema": SIGHT_SCHEMA, "template": "%s/%s" % (TEMPLATE_ID, VERSION), "method": (
        "true 3-D segments from the eye: vertical cylinders for the sticks (caps and bodies at their record heights), "
        "oriented slabs for the two leaning palettes and the slot's bed, backrest and wings, convex prisms for the "
        "tray's doubled walls (the sides tapering), boxes for the back wall + return flap + header and the platform "
        "plates and legs; a sample is visible when no occluder other than its own product crosses the segment"),
        "pass_rule": "the top %g mm of every stick's front face (its centreline, sampled every 1 mm) and the front "
                     "palette's lid above the sticks' tops visible" % float(own["visible_band_mm"]),
        "result": first, "passed": first["passed"], "remedy": None, "tolerance": None, "insert_sway": None}
    if first["passed"]:
        tol = sight_tolerance(g, products, own)
        out["tolerance"] = tol
        sway = sight_at_sway(g, products, own)
        out["insert_sway"] = sway
        out["passed"] = first["passed"] and tol["passed"] and sway["passed"]
    if not first["passed"]:
        tried = []
        for k in range(1, max_raise_mm + 1):
            for what, key in (("slot", "slot_floor_mm"), ("back platform", "back_plate_mm")):
                own2 = dict(own, **{key: own[key] + k})
                res = _sight(_geometry(products, own2), products, own2)
                if res["passed"]:
                    tried.append({"raise": what, "by_mm": k})
            if tried:
                break
        if tried:
            key = "slot_floor_mm" if tried[0]["raise"] == "slot" else "back_plate_mm"
            own2 = dict(own, **{key: own[key] + tried[0]["by_mm"]})
            rerun = _sight(_geometry(products, own2), products, own2)
            out["remedy"] = {"searched_mm": [1, max_raise_mm], "found": tried[0], "listed": tried,
                             "rerun_passed": rerun["passed"]}
        else:
            out["remedy"] = {"searched_mm": [1, max_raise_mm], "found": None,
                             "words": "no whole-mm raise of the slot or of the back platform up to %d mm passes; "
                                      "raising the back platform cannot lift a stick that stands on the floor" %
                                      max_raise_mm}
    return out


# =====================================================================================================================
# the reference die (ES3083) — measured only
# =====================================================================================================================

PRODUCT_GRID_SCHEMA = "counter_tray_header/product-grid-1"


def solve_product_tray(*, product_width_mm, product_depth_mm, product_height_mm,
                       rows, columns, count, width_mm, depth_mm, height_mm,
                       header_height_mm, front_height_mm, board_mm=1.5,
                       hole_shape="square", clearance_mm=0.5, top_edge="square", row_seat_z_mm=None):
    """Single-product tray: an arbitrary counted grid, a holder, and a doubled header.

    This branch uses its own product inputs. It does not substitute a bottle for
    any historical palette, lipstick or balm. Dimensions are provisional until
    a folded sample is checked; visibility reports never alter the row seats.
    """
    _validate_hole_shape(hole_shape)
    if top_edge != "square":
        raise ValueError("This tray branch requires the declared square header edge")
    if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0
           for value in (rows, columns, count)) or rows * columns != count or count > 100:
        raise ValueError("The observed tray count must equal rows times columns (at most 100)")
    values = dict(product_width_mm=product_width_mm, product_depth_mm=product_depth_mm,
                  product_height_mm=product_height_mm, width_mm=width_mm, depth_mm=depth_mm,
                  height_mm=height_mm, header_height_mm=header_height_mm,
                  front_height_mm=front_height_mm, board_mm=board_mm, clearance_mm=clearance_mm)
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= 5000:
            raise ValueError("%s must be a finite positive millimetre measurement" % name)
    values = {name: float(value) for name, value in values.items()}
    t, W, D, H = (values[name] for name in ("board_mm", "width_mm", "depth_mm", "height_mm"))
    if row_seat_z_mm is not None:
        if (not isinstance(row_seat_z_mm, (list, tuple)) or len(row_seat_z_mm) != rows
                or any(isinstance(z, bool) or not isinstance(z, (int, float)) or not math.isfinite(z)
                       or z < t or z >= H or (z != t and z < 5 * t) for z in row_seat_z_mm)):
            raise ValueError("Each measured seat must be on the floor or leave room for a closed two-board support")
        values["row_seat_z_mm"] = list(map(float, row_seat_z_mm))
    front, header = values["front_height_mm"] - t, values["header_height_mm"]
    back = H - t - header
    fw, fd = W - 2 * t, D - 2 * t
    side = max(values["product_width_mm"], values["product_depth_mm"]) + values["clearance_mm"]
    if min(front, back, fw, fd) <= t or back < front:
        raise ValueError("The tray dimensions leave no usable floor, walls or header")
    fit = max(t, 1.0)
    pw, pd = fw - 2 * fit, fd - 2 * fit
    if min(pw, pd) <= 0:
        raise ValueError("The tray dimensions leave no usable holder plate")
    # The minimum web follows the existing engine's three-board rule. Centres
    # spread over the usable plate, retaining this edge margin on all four sides.
    edge = 3 * t
    def centres(span, number):
        if number == 1:
            return [span / 2]
        start = edge + side / 2
        return [start + index * (span - 2 * start) / (number - 1) for index in range(number)]
    xs, ys = centres(pw, columns), centres(pd, rows)
    row_platforms = []
    if row_seat_z_mm is not None:
        row_depth = pd / rows
        ys = [(row + .5) * row_depth for row in range(rows)]
        for row, seat in enumerate(row_seat_z_mm, 1):
            row_platforms.append({"row": row, "depth_mm": row_depth, "y0_mm": (row - 1) * row_depth,
                "seat_z_mm": float(seat), "seat_part": "seat row %d" % row if seat > t else None,
                "seat_wall_height_mm": float(seat) - 3 * t if seat > t else None,
                "collar_part": "holder row %d" % row, "collar_top_z_mm": float(seat) + 4 * t,
                "collar_leg_mm": 2 * t, "collar_foot_mm": 3 * t})
    leg = min(front, values["product_height_mm"] * 0.2)
    flap = min(12.0, front * 0.75, back * 0.75, fd / 4)
    foot = min(10.0, pd / 4)
    holes = [{"index": r * columns + c + 1, "row": r + 1, "column": c + 1,
              "centre_mm": [_r(x), _r(y)], "shape": hole_shape, "size_mm": _r(side),
              "product_centre_mm": [_r(t + fit + x), _r(t + fit + y)],
              "seat_z_mm": _r(row_seat_z_mm[r] if row_seat_z_mm is not None else t)}
             for r, y in enumerate(ys) for c, x in enumerate(xs)]
    result = {"schema": PRODUCT_GRID_SCHEMA,
            "template": {"id": TEMPLATE_ID, "version": VERSION, "branch": "single_product_grid",
                         "provisional": True, "production_ready": False},
            "inputs": values, "layout": {"rows": rows, "columns": columns, "count": count},
            "hole_shape": hole_shape, "top_edge": top_edge, "holes": holes,
            "geometry": {"floor_mm": [fw, fd], "front_panel_height_mm": front,
                         "back_panel_height_mm": back, "header_height_mm": header,
                         "holder_mm": [pw, pd], "holder_height_mm": leg, "holder_inset_mm": fit,
                         "corner_glue_flap_mm": flap, "holder_foot_flap_mm": foot,
                         "minimum_web_mm": edge, "opening_size_mm": side},
            "assembly": "Fold the tray walls and glue the corner flaps inside the sides. Fold the header double. "
                        "Fold the holder legs down and glue their feet to the tray floor. Products stand on the floor.",
            "provisional": True,
            "authority": {"layout": "picked-picture inspection", "product": "product brief measurements",
                          "dimensions": "brief and picked-picture panel proportions; provisional",
                          "clearance": "execution specification, total across the opening",
                          "top_edge": "owner-authorized square header edge"}}
    if row_platforms:
        result["geometry"]["row_platforms"] = row_platforms
        result["assembly"] = ("Fold and glue the tray. Fold each row seat into a closed box and glue its bottom to the tray floor. "
            "Fold each square-hole collar's end legs down and glue its feet onto that row's seat. "
            "Bottles rest on the solid seats, not through a hole onto the tray floor. Fold the header double.")
        result["authority"]["seats"] = "source bottle-height scale, paired cap tops and observed front-base clearance"
        result["authority"]["collar"] = ("provisional construction: four-board engagement, two-board end legs, "
                                            "three-board glue feet; no front wall across printed bottle labels")
    return result


def _product_row_parts(record, row):
    """A closed seat box carries weight; its low, end-supported collar locates bottles."""
    width = record["geometry"]["holder_mm"][0]
    depth = row["depth_mm"]
    parts = []
    if row["seat_part"]:
        wall = row["seat_wall_height_mm"]
        flap = min(3 * record["inputs"]["board_mm"], wall / 2, depth / 4)
        seat = Part(row["seat_part"], "ROW %d SEAT — closed box; glue bottom to tray floor" % row["row"])
        seat.faces = [("seat", _rect(0, 0, width, depth), False),
            ("front wall", _rect(0, -wall, width, 0), False),
            ("bottom", _rect(0, -wall - depth, width, -wall), False),
            ("back wall", _rect(0, depth, width, depth + wall), False),
            ("closure flap", _rect(0, depth + wall, width, depth + wall + flap), False),
            ("left wall", _rect(-wall, 0, 0, depth), False),
            ("right wall", _rect(width, 0, width + wall, depth), False)]
        seat.creases = [("seat / front", _seg(0, 0, width, 0)),
            ("front / bottom", _seg(0, -wall, width, -wall)),
            ("seat / back", _seg(0, depth, width, depth)),
            ("back / closure", _seg(0, depth + wall, width, depth + wall)),
            ("seat / left", _seg(0, 0, 0, depth)), ("seat / right", _seg(width, 0, width, depth))]
        for end, y0, y1 in (("front", -wall, 0), ("back", depth, depth + wall)):
            for side, x0, x1, hinge in (("left", -flap, 0, 0), ("right", width, width + flap, width)):
                seat.faces.append((end + " " + side + " glue flap", _rect(x0, y0, x1, y1), False))
                seat.creases.append((end + " " + side + " glue fold", _seg(hinge, y0, hinge, y1)))
        parts.append(seat)
    leg, foot = row["collar_leg_mm"], row["collar_foot_mm"]
    holder = Part(row["collar_part"], "ROW %d COLLAR — glue end feet to its solid seat" % row["row"],
                  hole_shape=record["hole_shape"])
    holder.faces = [("plate", _rect(0, 0, width, depth), False),
        ("left leg", _rect(-leg, 0, 0, depth), False),
        ("left foot", _rect(-leg-foot, 0, -leg, depth), False),
        ("right leg", _rect(width, 0, width + leg, depth), False),
        ("right foot", _rect(width + leg, 0, width + leg + foot, depth), False)]
    holder.creases = [("left foot / leg", _seg(-leg, 0, -leg, depth)),
        ("left leg / plate", _seg(0, 0, 0, depth)), ("plate / right leg", _seg(width, 0, width, depth)),
        ("right leg / foot", _seg(width + leg, 0, width + leg, depth))]
    holder.holes = [("opening %d" % hole["index"],
                     (hole["centre_mm"][0], hole["centre_mm"][1] - row["y0_mm"]), hole["size_mm"] / 2)
                    for hole in record["holes"] if hole["row"] == row["row"]]
    parts.append(holder)
    return parts


def build_product_tray_die(record):
    """Draw the generic branch with the same Part/Die geometry and exporters."""
    g = record["geometry"]
    fw, fd = g["floor_mm"]
    front, back, header = (g[key] for key in ("front_panel_height_mm", "back_panel_height_mm", "header_height_mm"))
    flap = g["corner_glue_flap_mm"]
    tray = Part("tray", "TRAY — fold walls; glue corner flaps inside")
    tray.faces = [("floor", _rect(0, 0, fw, fd), False),
                  ("front panel", _rect(0, -front, fw, 0), True),
                  ("left side", Polygon([(0, 0), (0, fd), (-back, fd), (-front, 0)]), True),
                  ("right side", Polygon([(fw, 0), (fw + front, 0), (fw + back, fd), (fw, fd)]), True),
                  ("back panel", _rect(0, fd, fw, fd + back), True),
                  ("header front", _rect(0, fd + back, fw, fd + back + header), True),
                  ("header back", _rect(0, fd + back + header, fw, fd + back + 2 * header), False)]
    tray.creases = [("floor / front", _seg(0, 0, fw, 0)), ("floor / back", _seg(0, fd, fw, fd)),
                    ("floor / left", _seg(0, 0, 0, fd)), ("floor / right", _seg(fw, 0, fw, fd)),
                    ("back / header", _seg(0, fd + back, fw, fd + back)),
                    ("header fold", _seg(0, fd + back + header, fw, fd + back + header))]
    for end, y0, y1 in (("front", -front, 0), ("back", fd, fd + back)):
        for side_name, x0, x1, hinge in (("left", -flap, 0, 0), ("right", fw, fw + flap, fw)):
            tray.faces.append((end + " " + side_name + " glue flap", _rect(x0, y0, x1, y1), False))
            tray.creases.append((end + " " + side_name + " glue fold", _seg(hinge, y0, hinge, y1)))
    pw, pd = g["holder_mm"]
    leg, foot = g["holder_height_mm"], g["holder_foot_flap_mm"]
    holder = Part("holder", "HOLDER — fold legs down; glue feet to floor", hole_shape=record["hole_shape"])
    holder.faces = [("front foot", _rect(0, 0, pw, foot), False),
                    ("front leg", _rect(0, foot, pw, foot + leg), False),
                    ("plate", _rect(0, foot + leg, pw, foot + leg + pd), True),
                    ("back leg", _rect(0, foot + leg + pd, pw, foot + 2 * leg + pd), False),
                    ("back foot", _rect(0, foot + 2 * leg + pd, pw, 2 * foot + 2 * leg + pd), False)]
    holder.creases = [("holder fold %d" % i, _seg(0, y, pw, y)) for i, y in enumerate(
        (foot, foot + leg, foot + leg + pd, foot + 2 * leg + pd), 1)]
    holder.holes = [("opening %d" % hole["index"],
                     (hole["centre_mm"][0], foot + leg + hole["centre_mm"][1]), hole["size_mm"] / 2)
                    for hole in record["holes"]]
    raw_parts = [tray, holder]
    if g.get("row_platforms"):
        raw_parts = [tray] + [part for row in g["row_platforms"] for part in _product_row_parts(record, row)]
    placed, x = [], SHEET_MARGIN_MM
    row_y, row_bottom = SHEET_MARGIN_MM + LABEL_MM + 4, 0.0
    packing_width = tray.outline().bounds[2] - tray.outline().bounds[0]
    for part in raw_parts:
        minx, miny, maxx, maxy = part.outline().bounds
        if g.get("row_platforms") and x > SHEET_MARGIN_MM and x + maxx - minx > SHEET_MARGIN_MM + packing_width:
            x, row_y = SHEET_MARGIN_MM, row_bottom + PART_GAP_MM + LABEL_MM + 4
        moved = part.moved(x - minx, row_y - miny)
        placed.append(moved)
        row_bottom = max(row_bottom, moved.outline().bounds[3])
        x = moved.outline().bounds[2] + PART_GAP_MM
    bounds = unary_union([part.outline() for part in placed]).bounds
    width, height = math.ceil(bounds[2] + SHEET_MARGIN_MM), math.ceil(bounds[3] + SHEET_MARGIN_MM + 20)
    labels = [(part.label, (part.outline().bounds[0], part.outline().bounds[1] - DIE_BLEED_MM - 3), LABEL_MM)
              for part in placed]
    return Die(placed, width, height, labels, (SHEET_MARGIN_MM, height - 18.0, 50.0),
               "Single-product counter tray — provisional — flat die at 100 %")


def product_tray_fold_check(record, die=None):
    """Measure the drawn parts and openings, reporting failed fits without altering them."""
    die = die or build_product_tray_die(record)
    g, v = record["geometry"], record["inputs"]
    parts = {part.name: part for part in die.parts}
    tray = parts["tray"]
    holders = [part for part in die.parts if part.name == "holder" or part.name.startswith("holder row ")]
    floor = _face(tray, "floor")
    t = v["board_mm"]
    checks = []
    def check(key, measured, expected, ok):
        checks.append({"id": key, "measured": measured, "expected": expected, "ok": bool(ok)})
    closed = []
    for axis, key in ((0, "width_mm"), (1, "depth_mm")):
        value = _span(floor, axis) + 2 * t
        closed.append(value)
        check("closed_" + key, value, v[key], abs(value - v[key]) <= TOL_MM)
    height = _span(_face(tray, "back panel"), 1) + _span(_face(tray, "header front"), 1) + t
    check("closed_height_mm", height, v["height_mm"], abs(height - v["height_mm"]) <= TOL_MM)
    holes = [hole for holder in holders for hole in holder.holes]
    check("opening_count", len(holes), record["layout"]["count"], len(holes) == record["layout"]["count"])
    shapes = [holder.hole_shape for holder in holders]
    check("opening_shape", shapes, record["hole_shape"], bool(shapes) and all(shape == record["hole_shape"] for shape in shapes))
    sizes = [2 * half for _name, _centre, half in holes]
    expected = max(v["product_width_mm"], v["product_depth_mm"]) + v["clearance_mm"]
    check("opening_clearance_mm", [size - max(v["product_width_mm"], v["product_depth_mm"]) for size in sizes],
          v["clearance_mm"], bool(sizes) and all(abs(size - expected) <= TOL_MM for size in sizes))
    margins, webs = [], []
    for holder in holders:
        plate = _face(holder, "plate")
        openings = [polygon for _name, polygon in holder.hole_polygons()]
        margins.extend(polygon.distance(plate.boundary) if plate.covers(polygon) else -1.0 for polygon in openings)
        webs.extend(a.distance(b) for i, a in enumerate(openings) for b in openings[i + 1:])
        platform = next((row for row in g.get("row_platforms", []) if row["collar_part"] == holder.name), None)
        expected_positions = {"opening %d" % hole["index"]:
            [hole["centre_mm"][0], hole["centre_mm"][1] - (platform["y0_mm"] if platform else 0)]
            for hole in record["holes"] if platform is None or hole["row"] == platform["row"]}
        actual_positions = {name: [centre[0] - plate.bounds[0], centre[1] - plate.bounds[1]]
                            for name, centre, _half in holder.holes}
        check("opening_positions:" + holder.name, actual_positions, expected_positions,
              set(actual_positions) == set(expected_positions) and all(
                  math.dist(actual_positions[name], expected_positions[name]) <= TOL_MM for name in expected_positions))
    margin = min(margins, default=-1.0)
    check("opening_edge_margin_mm", margin, g["minimum_web_mm"], margin >= g["minimum_web_mm"] - TOL_MM)
    web = min(webs, default=None)
    check("opening_web_mm", web, g["minimum_web_mm"], web is None or web >= g["minimum_web_mm"] - TOL_MM)
    widths = [_span(_face(holder, "plate"), 0) for holder in holders]
    depths = [_span(_face(holder, "plate"), 1) for holder in holders]
    check("holder_width_fit_mm", widths, _span(floor, 0), bool(widths) and all(0 < width < _span(floor, 0) for width in widths))
    check("holder_depth_fit_mm", sum(depths), _span(floor, 1), bool(depths) and 0 < sum(depths) < _span(floor, 1))
    measured_platforms = []
    if g.get("row_platforms"):
        for row in g["row_platforms"]:
            prefix = "row_%d:" % row["row"]
            seat_z = t
            if row["seat_part"]:
                seat = parts[row["seat_part"]]
                wall_heights = [_span(_face(seat, name), axis) for name, axis in (
                    ("front wall", 1), ("back wall", 1), ("left wall", 0), ("right wall", 0))]
                seat_z = 3 * t + wall_heights[0]
                check(prefix + "seat_walls_mm", wall_heights, row["seat_wall_height_mm"],
                      all(abs(value - row["seat_wall_height_mm"]) <= TOL_MM for value in wall_heights))
                top, bottom = _face(seat, "seat"), _face(seat, "bottom")
                check(prefix + "closed_support", [_span(bottom, 0), _span(bottom, 1)],
                      [_span(top, 0), _span(top, 1)], all(abs(_span(top, axis) - _span(bottom, axis)) <= TOL_MM for axis in (0, 1)))
            check(prefix + "seat_height_mm", seat_z, row["seat_z_mm"], abs(seat_z - row["seat_z_mm"]) <= TOL_MM)
            holder = parts[row["collar_part"]]
            collar_plate = _face(holder, "plate")
            if row["seat_part"]:
                check(prefix + "support_vs_collar_mm", [_span(top, axis) for axis in (0, 1)],
                      [_span(collar_plate, axis) for axis in (0, 1)],
                      all(abs(_span(top, axis) - _span(collar_plate, axis)) <= TOL_MM for axis in (0, 1)))
            legs = [_span(_face(holder, name), 0) for name in ("left leg", "right leg")]
            collar_z = seat_z + 2 * t + legs[0]
            check(prefix + "collar_legs_mm", legs, row["collar_leg_mm"],
                  all(abs(value - row["collar_leg_mm"]) <= TOL_MM for value in legs))
            check(prefix + "collar_height_mm", collar_z, row["collar_top_z_mm"], abs(collar_z - row["collar_top_z_mm"]) <= TOL_MM)
            feet = [_span(_face(holder, name), 0) for name in ("left foot", "right foot")]
            check(prefix + "collar_feet_mm", feet, row["collar_foot_mm"],
                  all(abs(value - row["collar_foot_mm"]) <= TOL_MM for value in feet))
            check(prefix + "collar_below_product_mm", collar_z - seat_z, v["product_height_mm"],
                  0 < collar_z - seat_z < v["product_height_mm"])
            check(prefix + "seat_matches_bottles", [hole["seat_z_mm"] for hole in record["holes"] if hole["row"] == row["row"]],
                  seat_z, all(abs(hole["seat_z_mm"] - seat_z) <= TOL_MM for hole in record["holes"] if hole["row"] == row["row"]))
            measured_platforms.append({"row": row["row"], "seat_z_mm": seat_z, "collar_top_z_mm": collar_z,
                                       "support_part": row["seat_part"], "collar_part": row["collar_part"]})
    else:
        check("holder_below_product_mm", g["holder_height_mm"], v["product_height_mm"],
              0 < g["holder_height_mm"] < v["product_height_mm"])
    for part in die.parts:
        outline = part.outline()
        check("connected:" + part.name, outline.geom_type, "Polygon", outline.geom_type == "Polygon" and outline.is_valid)
        overlap = max((a.intersection(b).area for i, (_an, a, _ap) in enumerate(part.faces)
                       for _bn, b, _bp in part.faces[i + 1:]), default=0.0)
        check("flat_overlap:" + part.name, overlap, 0.0, overlap < 1e-6)
        for name, crease in part.creases:
            faces = sum(face.boundary.buffer(1e-6).contains(crease) for _n, face, _p in part.faces)
            check("hinge:" + part.name + ":" + name, faces, 2, faces == 2)
    passed = all(row["ok"] for row in checks)
    return {"schema": "counter_tray_header/product-grid-fold-1", "passed": passed, "valid": passed,
            "findings": checks, "failed": [row["id"] for row in checks if not row["ok"]],
            "closed_mm": closed + [height],
            "measured_row_platforms": measured_platforms,
            "construction_measurement": "Folded heights include tray, support-bottom, seat and collar board thickness; bend radius and glue compression require a physical sample",
            "physical_sample_required": True, "provisional": True}


def _product_plate_hit(eye, point, data):
    """Intersect a ray with the actual perforated plate extruded through its board thickness."""
    material, z0, z1 = data
    dz = point[2] - eye[2]
    lo, hi = 1e-9, 1 - 1e-7
    if abs(dz) < 1e-15:
        if not z0 <= eye[2] <= z1:
            return False
    else:
        a, b = (z0 - eye[2]) / dz, (z1 - eye[2]) / dz
        lo, hi = max(lo, min(a, b)), min(hi, max(a, b))
    if hi - lo <= 1e-9:
        return False
    ends = [(eye[0] + (point[0] - eye[0]) * s, eye[1] + (point[1] - eye[1]) * s) for s in (lo, hi)]
    if math.dist(*ends) < 1e-9:
        return material.contains(Point(ends[0]))
    return material.intersection(LineString(ends)).length > 1e-9


def _product_first_hit(eye, point, occluders, skip):
    for name, kind, data in occluders:
        if name == skip:
            continue
        hit = _product_plate_hit(eye, point, data) if kind == "plate" else _first_hit(eye, point, [(name, kind, data)], skip)
        if hit:
            return name
    return None


def product_tray_platform_fronts(record):
    """Orthographic front faces of the actual, unprinted row support parts.

    Boxes are x/y-down millimetres from the stand's upper-left corner. Depth is
    the front-face y plane in the same physical coordinates as product centres;
    render deeper objects first, then these faces and the front tray panel.
    """
    v, g = record["inputs"], record["geometry"]
    if "row_platforms" not in g:
        return []
    H, t = v["height_mm"], v["board_mm"]
    x0 = t + g["holder_inset_mm"]
    x1 = x0 + g["holder_mm"][0]
    faces = []
    for row in g["row_platforms"]:
        seat, top = row["seat_z_mm"], row["collar_top_z_mm"]
        depth = t + g["holder_inset_mm"] + row["y0_mm"]
        def face(kind, part, left, bottom, right, upper):
            faces.append({"id": "row_%d_%s" % (row["row"], kind), "kind": kind,
                          "part": part, "row": row["row"], "depth_mm": depth,
                          "box_mm": [left, H - upper, right, H - bottom],
                          "material": "unprinted board", "printed": False})
        if row["seat_part"]:
            # The closed front silhouette includes its top and bottom board edges.
            face("support_front", row["seat_part"], x0, t, x1, seat)
        face("collar_front_edge", row["collar_part"], x0, top - t, x1, top)
        for side, left, right in (("left", x0, x0 + t), ("right", x1 - t, x1)):
            face("collar_%s_leg" % side, row["collar_part"], left, seat + t, right, top - t)
        foot = row["collar_foot_mm"]
        for side, left, right in (("left", x0, x0 + foot), ("right", x1 - foot, x1)):
            face("collar_%s_foot" % side, row["collar_part"], left, seat, right, seat + t)
    return faces


def product_tray_enclosure_elevations(record):
    """Expose the existing folded tray walls without inventing perspective.

    The back panel fills the space between the header and floor. A true front
    view shows only the board-thickness silhouettes of the sloping side walls;
    their full, measured slopes belong in the separate side elevation.
    Materials and print finishes are deliberately not assigned by geometry.
    """
    v, g = record["inputs"], record["geometry"]
    W, D, H, t = (v[key] for key in ("width_mm", "depth_mm", "height_mm", "board_mm"))
    header = g["header_height_mm"]
    front, back = (g[key] + t for key in ("front_panel_height_mm", "back_panel_height_mm"))
    faces = []
    for kind, name, depth, bounds, projection in (
            ("back_interior", "back panel", D - t, [t, header, W - t, H - t], "planar front face"),
            ("left_side_edge", "left side", 0., [0., header, t, H - t], "board-thickness orthographic silhouette"),
            ("right_side_edge", "right side", 0., [W - t, header, W, H - t], "board-thickness orthographic silhouette")):
        left, top, right, bottom = bounds
        faces.append({"id": "tray_" + kind, "kind": kind, "part": "tray", "face": name,
                      "depth_mm": depth, "box_mm": bounds, "projection": projection,
                      "polygon_mm": [[left, top], [right, top], [right, bottom], [left, bottom]]})
    side = {"width_mm": D, "height_mm": H,
            "coordinate_system": "Depth from front to back on x; height down from the stand top on y",
            "wall_polygon_mm": [[t, H - t], [t, H - front], [D - t, H - back], [D - t, H - t]],
            "front_wall_top_mm": H - front, "back_wall_top_mm": H - back,
            "board_mm": t, "source": "Existing tray side faces folded about the engine floor edges"}
    return {"front_faces": faces, "side_elevation": side,
            "projection_note": "True front elevation: side walls retain board thickness; their slope is shown only in the side elevation"}


def product_tray_raise_rear(record):
    """Owner-selected construction change: pass the unchanged 25 mm sightline test."""
    if record['inputs']['product_height_mm'] < 25:
        raise ValueError('A 25 mm visible top band needs a product at least 25 mm high')
    initial = product_tray_sightlines(record)
    original = [next(hole['seat_z_mm'] for hole in record['holes'] if hole['row'] == row)
                for row in range(1, record['layout']['rows'] + 1)]
    seats = list(original)
    base_height, board = record['inputs']['height_mm'], record['inputs']['board_mm']
    def candidate(values):
        inputs = dict(record['inputs'], **record['layout'], hole_shape=record['hole_shape'],
                      top_edge=record['top_edge'], row_seat_z_mm=list(values),
                      height_mm=base_height + max(a - b for a, b in zip(values, original)))
        return solve_product_tray(**inputs)
    current = record
    for index in range(1, len(seats)):
        def passes(trial):
            return all(row['passed'] for row in product_tray_sightlines(trial)['products'] if row['row'] == index + 1)
        if passes(current):
            continue
        start = max(seats[index], 5 * board)
        low, high = start, start
        trial = list(seats)
        while True:
            trial[index] = high
            trial_record = candidate(trial)
            if passes(trial_record):
                break
            low = high
            high += max(1., high - start)
            if high - original[index] > record['inputs']['product_height_mm']:
                raise ValueError('The rear top band cannot be exposed within one product height of additional support')
        while high - low > .05:
            middle = (low + high) / 2
            trial[index] = middle
            if passes(candidate(trial)):
                high = middle
            else:
                low = middle
        seats[index] = math.ceil(high * 10) / 10
        current = candidate(seats)
        if not passes(current):
            raise ValueError('The rounded rear support does not pass the unchanged sightline check')
    final = product_tray_sightlines(current)
    if not final['passed']:
        raise ValueError('The existing 25 mm sightline check still has an occluded product')
    current['authority']['rear_visibility'] = 'Explicit owner-selected rise until the existing 25 mm top-band check passes'
    return {'record': current, 'initial_sightlines': initial, 'final_sightlines': final,
            'original_seats_mm': original, 'final_seats_mm': seats,
            'added_rise_mm': [a - b for a, b in zip(seats, original)],
            'original_height_mm': base_height, 'final_height_mm': current['inputs']['height_mm'],
            'visible_band_mm': 25., 'seat_precision_mm': .1,
            'method': 'Raise rear rows front-to-back; bounded search using the unchanged engine eye and samples; rebuild closed seats and raise the header by the largest added rise',
            'allowed_difference': 'Rear platform rise and corresponding provisional back-wall height',
            'physical_sample_required': True}


def product_tray_sightlines(record):
    """Report visibility at the engine's 500/350 mm eye; keep every pictured seat."""
    v, g = record["inputs"], record["geometry"]
    W, D, H, t = (v[key] for key in ("width_mm", "depth_mm", "height_mm", "board_mm"))
    pw, pd, ph = (v[key] for key in ("product_width_mm", "product_depth_mm", "product_height_mm"))
    eye = (W / 2, -500.0, 350.0)
    back = g["back_panel_height_mm"] + t
    front = g["front_panel_height_mm"] + t
    occ = [("front wall", "box", _halfspaces_box(0, W, 0, t, 0, front)),
           ("back wall and header", "box", _halfspaces_box(0, W, D - t, D, 0, H))]
    slope = (back - front) / D
    for name, x0, x1 in (("left wall", 0, t), ("right wall", W - t, W)):
        occ.append((name, "box", _halfspaces_box(x0, x1, 0, D, 0, back) + [((0, -slope, 1), front)]))
    for row in g.get("row_platforms", []):
        x0, y0 = t + g["holder_inset_mm"], t + g["holder_inset_mm"] + row["y0_mm"]
        x1, y1 = x0 + g["holder_mm"][0], y0 + row["depth_mm"]
        seat, top = row["seat_z_mm"], row["collar_top_z_mm"]
        if seat > t:
            occ.append(("row %d seat" % row["row"], "box", _halfspaces_box(x0, x1, y0, y1, t, seat)))
        holes = []
        for hole in record["holes"]:
            if hole["row"] != row["row"]:
                continue
            x, y = hole["product_centre_mm"]
            half = hole["size_mm"] / 2
            holes.append(_rect(x-half, y-half, x+half, y+half) if record["hole_shape"] == "square"
                         else Point(x, y).buffer(half, 64))
        material = _rect(x0, y0, x1, y1).difference(unary_union(holes))
        occ.append(("row %d collar" % row["row"], "plate", (material, top-t, top)))
        for side, a, b in (("left", x0, x0+t), ("right", x1-t, x1)):
            occ.append(("row %d %s collar leg" % (row["row"], side), "box",
                        _halfspaces_box(a, b, y0, y1, seat+t, top-t)))
        for side, a, b in (("left", x0, x0+row["collar_foot_mm"]), ("right", x1-row["collar_foot_mm"], x1)):
            occ.append(("row %d %s collar foot" % (row["row"], side), "box",
                        _halfspaces_box(a, b, y0, y1, seat, seat+t)))
    for hole in record["holes"]:
        x, y = hole["product_centre_mm"]
        seat = hole["seat_z_mm"]
        shape = ("cyl", (x, y, pw / 2, seat, seat + ph)) if record["hole_shape"] == "circle" else (
            "box", _halfspaces_box(x - pw / 2, x + pw / 2, y - pd / 2, y + pd / 2, seat, seat + ph))
        occ.append(("product %d" % hole["index"], *shape))
    rows = []
    band = min(25.0, ph)
    samples = max(1, math.ceil(band))
    for hole in record["holes"]:
        x, y = hole["product_centre_mm"]
        name = "product %d" % hole["index"]
        seat = hole["seat_z_mm"]
        results = [_product_first_hit(eye, (x, y - pd / 2, seat + ph - band + band * index / samples), occ, name)
                   for index in range(samples + 1)]
        visible = sum(hit is None for hit in results)
        rows.append({"index": hole["index"], "row": hole["row"], "column": hole["column"],
                     "seat_z_mm": hole["seat_z_mm"], "visible_fraction": visible / len(results),
                     "visible_samples": visible, "samples": len(results), "passed": visible == len(results),
                     "front_elevation_exposed_top_mm": max(0, min(ph, seat + ph - max(
                         [other["seat_z_mm"] + ph for other in record["holes"]
                          if other["column"] == hole["column"] and other["row"] < hole["row"]] or [seat]))),
                     "occluders": sorted({hit for hit in results if hit is not None})})
    return {"schema": "counter_tray_header/product-grid-sightlines-1", "eye_mm": list(eye),
            "method": "3-D segments to each product's front centreline, sampled at most 1 mm apart in its top band",
            "visible_band_mm": band, "products": rows, "passed": all(row["passed"] for row in rows),
            "design_gate": False, "seats_changed": False,
            "includes_measured_row_supports": bool(g.get("row_platforms")),
            "note": "Measured report for the designer's eye. Covered bands do not change the picked row heights."}


REFERENCE_PATH = "materials/house-designs/ES3083吸塑 展盒刀线.ai"
REFERENCE_SHA256 = "6a13d2d45197d26d82bc21800a031a6a427e81a7258eeadb3ca7129c2635ed8b"
CUT_RGB = (0.006, 0.005, 0.006)
CUT_STROKE_PT = 0.709
CREASE_RGB = (0.904, 0.105, 0.104)


def measure_reference_die(path) -> dict:
    """Walk the reference's vectors (PyMuPDF ``get_drawings``) and return NUMBERS only: every crease path (its id,
    its end points in mm at 2 dp, its length; the shaped one by its box and segment count), every cut path counted,
    and every other stroke excluded by colour with its reason. Nothing of the file is copied."""
    import fitz
    with open(path, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    doc = fitz.open(path)
    page = doc[0]
    creases, cuts, excluded = [], [], {}
    for d in page.get_drawings():
        rgb = d.get("color")
        stroke_pt = round(float(d.get("width") or 0.0), 3)
        key = tuple(round(v, 3) for v in rgb) if rgb else None
        box_pt = tuple(d["rect"])
        box_mm = [round(c_pt * MM_PER_PT, 2) for c_pt in box_pt]
        segs = []
        for it in d["items"]:
            if it[0] == "l":
                a_pt, b_pt = tuple(it[1]), tuple(it[2])
            elif it[0] == "c":
                a_pt, b_pt = tuple(it[1]), tuple(it[4])
            else:
                continue
            segs.append(([round(c_pt * MM_PER_PT, 2) for c_pt in a_pt],
                         [round(c_pt * MM_PER_PT, 2) for c_pt in b_pt], it[0]))
        if key == CREASE_RGB:
            creases.append({"box_mm": box_mm, "segments": segs})
        elif key == CUT_RGB and stroke_pt == CUT_STROKE_PT:
            cuts.append({"box_mm": box_mm, "segments": segs})
        else:
            label = "%s @ %s pt" % (list(key) if key else None, stroke_pt)
            slot = excluded.setdefault(label, {"paths": 0, "box_mm": None})
            slot["paths"] += 1
            b = slot["box_mm"]
            slot["box_mm"] = box_mm if b is None else [min(b[0], box_mm[0]), min(b[1], box_mm[1]),
                                                        max(b[2], box_mm[2]), max(b[3], box_mm[3])]
    return {"sha256": sha, "page_mm": [round(c_pt * MM_PER_PT, 2) for c_pt in tuple(page.rect)],
            "creases": creases, "cuts": cuts, "excluded": excluded}


def _walk_creases(walk: dict) -> list:
    out = []
    for i, c in enumerate(walk["creases"]):
        segs = c["segments"]
        cid = "C%02d" % (i + 1)
        if len(segs) == 1:
            a, b, _k = segs[0]
            dx, dy = b[0] - a[0], b[1] - a[1]
            kind = "horizontal" if abs(dy) < 0.01 else "vertical" if abs(dx) < 0.01 else "slanted"
            if (kind == "horizontal" and a[0] > b[0]) or (kind != "horizontal" and a[1] > b[1]):
                a, b = b, a
            out.append({"id": cid, "kind": kind, "a": list(a), "b": list(b), "length_mm": _r(math.dist(a, b), 2)})
        else:
            out.append({"id": cid, "kind": "shaped", "box_mm": c["box_mm"], "segments": len(segs),
                        "length_mm": None})
    return out


def _near(a, b, tol=0.06):
    return abs(a - b) <= tol


def reference_measures(walk: dict) -> dict:
    """The ES3083 die's structure, measured from the walk: every crease given its role, every cut path its feature,
    and the panel measures computed from those coordinates (mm, 2 dp)."""
    cr = _walk_creases(walk)
    hz = [c for c in cr if c["kind"] == "horizontal"]
    longest = max(hz, key=lambda c: c["length_mm"])
    X0, X1 = longest["a"][0], longest["b"][0]
    Xc = (X0 + X1) / 2
    inside = lambda c: c["a"][0] >= X0 - 0.06 and c["b"][0] <= X1 + 0.06   # noqa: E731
    ys = sorted({c["a"][1] for c in hz if inside(c)})
    by_y = {y: [c for c in hz if inside(c) and _near(c["a"][1], y, 0.01)] for y in ys}
    counts = [len(by_y[y]) for y in ys]
    if counts != [1, 1, 3, 1, 1, 2, 1]:
        raise ValueError("ES3083's inside horizontal creases are not the structure read: %r" % counts)
    y_liner, y_skin, y_front, y_back, y_head, y_fold, y_ret = ys
    out_h = [c for c in hz if not inside(c)]
    vt = [c for c in cr if c["kind"] == "vertical"]
    sl = [c for c in cr if c["kind"] == "slanted"]
    sh = [c for c in cr if c["kind"] == "shaped"]
    roles = {}

    def put(role, items):
        for c in items:
            roles[c["id"]] = role
    put("front spine / front liner", by_y[y_liner])
    put("front skin / front spine", by_y[y_skin])
    put("floor / front skin", by_y[y_front])
    put("floor / back wall", by_y[y_back])
    put("back wall / header rear leaf", by_y[y_head])
    put("header top fold (straight part)", by_y[y_fold])
    put("header front leaf / return flap", by_y[y_ret])
    corner = [c for c in out_h if _near(c["a"][1], y_front + 1.5, 0.2)]
    lockh = [c for c in out_h if _near(c["a"][1], y_back, 0.01)]
    put("side skin / corner flap", corner)
    put("side skin / lock tab", lockh)
    side = [c for c in vt if _near(c["a"][0], X0) or _near(c["a"][0], X1)]
    flap = [c for c in vt if c not in side]
    put("floor / side skin", side)
    put("back wall / back flap", flap)
    for sgn in (-1, 1):
        pair = sorted([c for c in sl if (c["a"][0] - Xc) * sgn > 0],
                      key=lambda c: abs(c["a"][0] - (X1 if sgn > 0 else X0)))
        put("side skin / side spine", pair[:1])
        put("side spine / side liner", pair[1:])
    put("header top fold (shaped crest)", sh)
    if len(roles) != len(cr):
        raise ValueError("unassigned creases: %r" % sorted(set(c["id"] for c in cr) - set(roles)))

    # -- the cut paths, each to its feature (left folded onto right) ----------------------------------------------------
    fold = lambda x: Xc + abs(x - Xc)                                       # noqa: E731
    side_start = min(c["a"][1] for c in side)
    xin = max(c["a"][0] for c in flap)                                      # the back flap crease, right
    groups = [
        ("front liner free edge and its two tabs", lambda b, k, fl, fh: 28.8 <= b[1] and b[3] <= y_liner - 22.9 and
         X0 + 5.4 <= b[0] and b[2] <= X1 - 5.4, 9),
        ("front liner sides", lambda b, k, fl, fh: _near(b[0], b[2]) and _near(fh, X1 - 5.5) and
         _near(b[3], y_liner), 2),
        ("front spine ends (chamfers)", lambda b, k, fl, fh: _near(b[1], y_liner) and _near(b[3], y_skin), 2),
        ("front skin sides", lambda b, k, fl, fh: _near(b[0], b[2]) and _near(fh, X1) and _near(b[1], y_skin)
         and b[3] < y_front, 2),
        ("front corner relief arcs", lambda b, k, fl, fh: k == "c" and b[1] >= y_front - 0.6 and b[3] <= side_start + 0.06
         and fh >= X1 - 0.06, 2),
        ("corner flaps", lambda b, k, fl, fh: fl >= X1 + 3.9 and fh <= X1 + 23.1 and
         b[3] <= side_start + 0.06 and b[1] >= 38.3, 6),
        ("corner flap to side liner joins", lambda b, k, fl, fh: b[3] - b[1] < 3 and _near(b[1], side_start) and
         fh > X1 + 22, 2),
        ("side liners' stepped free edges (four lock tabs)", lambda b, k, fl, fh: fl >= X1 + 31 and
         b[1] >= 78 and b[3] <= y_back - 3.7, 22),
        ("side liners' back ends", lambda b, k, fl, fh: _near(b[3], y_back) and b[1] > y_back - 4 and
         abs(b[2] - b[0]) < 5 and fh > X1 + 70, 2),
        ("side skins' back edges", lambda b, k, fl, fh: _near(b[1], y_back) and _near(b[3], y_back), 4),
        ("lock tabs (arrow)", lambda b, k, fl, fh: fl >= X1 + 23.9 and fh <=
         X1 + 53.1 and b[1] >= y_back - 0.06 and b[3] <= y_back + 15.06, 14),
        ("lock tabs' relief slits", lambda b, k, fl, fh: _near(b[0], b[2]) and _near(b[3], y_back) and
         _near(b[1], y_back - 2), 4),
        ("floor side slots", lambda b, k, fl, fh: fl >= X1 - 4.56 and fh <= X1 + 0.06
         and b[1] > side_start + 1 and b[3] < y_back - 1, 16),
        ("front floor slots", lambda b, k, fl, fh: b[1] >= y_front - 0.06 and b[3] <= y_front + 4.56 and
         fl > Xc + 60, 8),
        ("lock slots", lambda b, k, fl, fh: fl >= xin - 0.56 and fh <= xin + 4.06 and
         b[1] >= y_back + 24 and b[3] <= y_head - 24, 8),
        ("back flaps' outlines", lambda b, k, fl, fh: fh >= xin - 0.06 and b[1] >= y_back - 0.06 and
         b[3] <= y_head + 0.06 and fl >= xin - 0.06, 12),
        ("header sides", lambda b, k, fl, fh: _near(b[0], b[2]) and _near(b[1], y_head) and _near(b[3], y_ret), 2),
        ("return flap outline", lambda b, k, fl, fh: b[1] >= y_ret - 0.06, 7),
    ]
    assigned = {g[0]: [] for g in groups}
    unassigned = []
    for i, path in enumerate(walk["cuts"]):
        b = path["box_mm"]
        k = "c" if all(sg[2] == "c" for sg in path["segments"]) else "l"
        fl, fh = sorted((fold(b[0]), fold(b[2])))
        if b[0] < Xc < b[2]:
            fl, fh = Xc, max(fold(b[0]), fold(b[2]))
        for name, pred, _n in groups:
            if pred(b, k, fl, fh):
                assigned[name].append(i)
                break
        else:
            unassigned.append(i)
    cut_groups = [{"feature": name, "paths": len(assigned[name]), "expected": n} for name, _p, n in groups]

    # -- the measures ------------------------------------------------------------------------------------------------
    seg_cuts = [(a, b2) for path in walk["cuts"] for a, b2, _k in path["segments"]]

    def find_cut(pred):
        hits = [(a, b2) for a, b2 in seg_cuts if pred(a, b2)]
        if not hits:
            raise ValueError("a cut segment the structure needs is missing")
        return hits[0]
    right_side = sorted([c for c in side if _near(c["a"][0], X1)], key=lambda c: c["a"][1])
    gaps = [(p["b"][1], q["a"][1]) for p, q in zip(right_side, right_side[1:])]
    front_segs = sorted(by_y[y_front], key=lambda c: c["a"][0])
    fgaps = [(p["b"][0], q["a"][0]) for p, q in zip(front_segs, front_segs[1:])]
    inner_r = [c for c in sl if roles[c["id"]] == "side skin / side spine" and c["a"][0] > Xc][0]
    outer_r = [c for c in sl if roles[c["id"]] == "side spine / side liner" and c["a"][0] > Xc][0]

    def x_on(c, y):
        (ax, ay), (bx, by_) = c["a"], c["b"]
        return ax + (bx - ax) * (y - ay) / (by_ - ay)

    def perp(c, p):
        (ax, ay), (bx, by_) = c["a"], c["b"]
        L = math.dist(c["a"], c["b"])
        return abs((bx - ax) * (ay - p[1]) - (ax - p[0]) * (by_ - ay)) / L
    liner_edge = find_cut(lambda a, b2: _near(a[1], b2[1]) and _near(a[1], y_liner - 23.0, 0.2))
    tab_tip = find_cut(lambda a, b2: _near(a[1], b2[1]) and a[1] < liner_edge[0][1] - 1 and
                       min(a[0], b2[0]) > Xc)
    cflap_out = find_cut(lambda a, b2: _near(a[0], b2[0]) and a[0] > X1 + 10 and min(a[1], b2[1]) < y_front - 30)
    bflap_out = find_cut(lambda a, b2: _near(a[0], b2[0]) and a[0] > xin + 50 and min(a[1], b2[1]) > y_back)
    # the right side lock tab (arrow), from its own cut paths: its head is its widest pair of vertices
    arrow = [walk["cuts"][i] for i in assigned["lock tabs (arrow)"] if walk["cuts"][i]["box_mm"][0] > Xc]
    arrow_pts = [p for path in arrow for a, b2, _k in path["segments"] for p in (a, b2)]
    head_pts = [p for p in arrow_pts if _near(p[0], max(q[0] for q in arrow_pts), 0.02) or
                _near(p[0], min(q[0] for q in arrow_pts), 0.02)]
    if len({round(p[1], 2) for p in head_pts}) != 1:
        raise ValueError("ES3083's lock tab head is not one level: %r" % head_pts)
    shoulder = [p for p in arrow_pts if p[0] > X1 + 20 and y_back + 11 < p[1] < y_back + 12]
    curves = [path["box_mm"] for path in arrow if all(sg[2] == "c" for sg in path["segments"])]
    # the relief arcs: half circles (box 2R × R) at the front corners and at the back flaps' hinge foot
    relief_boxes = [walk["cuts"][i]["box_mm"] for i in assigned["front corner relief arcs"]]
    relief_boxes += [walk["cuts"][i]["box_mm"] for i in assigned["back flaps' outlines"]
                     if all(sg[2] == "c" for sg in walk["cuts"][i]["segments"])]
    relief_r = sorted({_r(min(b[2] - b[0], b[3] - b[1]), 2) for b in relief_boxes})
    if len(relief_r) != 1 or any(abs(max(b[2] - b[0], b[3] - b[1]) - 2 * relief_r[0]) > 0.02 for b in relief_boxes):
        raise ValueError("ES3083's relief arcs are not one half-circle size: %r" % relief_boxes)
    # the right side liner's free edge, reflected back across its spine onto the skin: its distance from the floor
    # crease at the free edge's front and back ends (its tab tips lie a tab's height beyond the edge)
    refl_back, _nrm = _reflector(((inner_r["a"][0] + outer_r["a"][0]) / 2, (inner_r["a"][1] + outer_r["a"][1]) / 2),
                                 (inner_r["b"][0] - inner_r["a"][0], inner_r["b"][1] - inner_r["a"][1]))
    crease_ends = [tuple(outer_r["a"]), tuple(outer_r["b"])]
    liner_pts = {tuple(p) for i in assigned["side liners' stepped free edges (four lock tabs)"]
                 if walk["cuts"][i]["box_mm"][0] > Xc for a, b2, _k in walk["cuts"][i]["segments"] for p in (a, b2)}
    liner_pts = sorted((refl_back(p) for p in liner_pts if all(math.dist(p, q) > 0.06 for q in crease_ends)),
                       key=lambda q: q[1])
    (fx, fy_), (bx_, by2) = liner_pts[0], liner_pts[-1]
    on_line = lambda q: fx + (bx_ - fx) * (q[1] - fy_) / (by2 - fy_)  # noqa: E731
    base_dev = [q[0] - on_line(q) for q in liner_pts]
    tab_h = HOUSE["tab_height_mm"][0]
    if any(min(abs(d), abs(d + tab_h)) > 0.15 for d in base_dev):
        raise ValueError("ES3083's side liner edge is not one straight edge with its tabs: %r" % base_dev)
    tip = find_cut(lambda a, b2: _near(a[1], b2[1]) and a[1] > y_back + 14 and a[1] < y_back + 16 and
                   min(a[0], b2[0]) > X1)
    relief = find_cut(lambda a, b2: _near(a[0], b2[0]) and _near(max(a[1], b2[1]), y_back) and
                      _near(min(a[1], b2[1]), y_back - 2.0) and a[0] > X1)
    lock_slot = [(a, b2) for a, b2 in seg_cuts if _near(a[0], b2[0]) and xin - 1 < a[0] < xin + 5 and
                 y_back + 20 < min(a[1], b2[1]) < y_head - 20]
    ret_bottom = find_cut(lambda a, b2: _near(a[1], b2[1]) and a[1] > y_ret + 10)
    ret_side = find_cut(lambda a, b2: _near(a[0], b2[0]) and a[0] > Xc and min(a[1], b2[1]) > y_ret)
    ret_chamfer = find_cut(lambda a, b2: _near(max(a[0], b2[0]), X1) and _near(min(a[1], b2[1]), y_ret) and
                           max(a[1], b2[1]) < y_ret + 5)
    flap_r = sorted([c for c in flap if c["a"][0] > Xc], key=lambda c: c["a"][1])
    lock_r = [c for c in lockh if c["a"][0] > Xc][0]
    corner_r = [c for c in corner if c["a"][0] > Xc][0]
    crest = sh[0]
    fold_l = sorted(by_y[y_fold], key=lambda c: c["a"][0])
    side_front_h = x_on(inner_r, side_start) - X1
    m = {
        "principal_width_mm": X1 - X0,
        "floor_depth_mm": y_back - y_front,
        "side_run_mm": right_side[-1]["b"][1] - right_side[0]["a"][1],
        "side_start_mm": side_start - y_front,
        "side_crease_segments_mm": [c["length_mm"] for c in right_side],
        "side_slot_lengths_mm": [b2 - a for a, b2 in gaps],
        "side_slot_centre_1_mm": (gaps[0][0] + gaps[0][1]) / 2 - side_start,
        "side_slot_centre_2_mm": (gaps[1][0] + gaps[1][1]) / 2 - side_start,
        "slot_depth_mm": X1 - min(a[0] for a, b2 in seg_cuts if _near(a[0], b2[0]) and X1 - 5 < a[0] < X1 - 4),
        "front_skin_mm": y_front - y_skin,
        "spine_mm": y_skin - y_liner,
        "front_liner_mm": y_liner - liner_edge[0][1],
        "front_liner_width_mm": by_y[y_liner][0]["length_mm"],
        "liner_inset_mm": (X1 - X0 - by_y[y_liner][0]["length_mm"]) / 2,
        "liner_short_mm": (y_front - y_skin) - (y_liner - liner_edge[0][1]),
        "tab_height_mm": liner_edge[0][1] - tab_tip[0][1],
        "tab_tip_mm": abs(tab_tip[1][0] - tab_tip[0][0]),
        "tab_base_mm": fgaps[0][1] - fgaps[0][0],
        "front_crease_segments_mm": [c["length_mm"] for c in front_segs],
        "front_slot_offset_mm": abs((fgaps[1][0] + fgaps[1][1]) / 2 - Xc),
        "side_front_height_mm": side_front_h,
        "side_back_height_mm": x_on(inner_r, y_back) - X1,
        "side_spine_mm": [perp(inner_r, outer_r["a"]), perp(inner_r, outer_r["b"])],
        "inner_slant_crease_mm": inner_r["length_mm"], "outer_slant_crease_mm": outer_r["length_mm"],
        "corner_flap_width_mm": corner_r["length_mm"],
        "corner_flap_inset_mm": corner_r["a"][0] - X1,
        "corner_flap_top_gap_mm": side_front_h - (corner_r["b"][0] - X1),
        "corner_flap_length_mm": abs(cflap_out[1][1] - cflap_out[0][1]),
        "back_wall_mm": y_head - y_back,
        "back_body_mm": xin - min(c["a"][0] for c in flap),
        "back_inset_mm": X1 - xin,
        "back_flap_depth_mm": bflap_out[0][0] - xin,
        "back_flap_bottom_mm": min(bflap_out[0][1], bflap_out[1][1]) - y_back,
        "back_flap_outer_top_mm": max(bflap_out[0][1], bflap_out[1][1]) - y_back,
        "back_flap_hinge_mm": [flap_r[0]["a"][1] - y_back, flap_r[-1]["b"][1] - y_back],
        "lock_slot_length_mm": flap_r[1]["a"][1] - flap_r[0]["b"][1],
        "lock_slot_width_mm": max(a[0] for a, b2 in lock_slot) - min(a[0] for a, b2 in lock_slot),
        "lock_slot_into_body_mm": xin - min(a[0] for a, b2 in lock_slot),
        "lock_slot_centre_mm": (flap_r[1]["a"][1] + flap_r[0]["b"][1]) / 2 - y_back,
        "lock_neck_mm": lock_r["length_mm"],
        "lock_neck_centre_mm": (lock_r["a"][0] + lock_r["b"][0]) / 2 - X1,
        "lock_head_mm": max(p[0] for p in head_pts) - min(p[0] for p in head_pts),
        "lock_head_at_mm": head_pts[0][1] - y_back,
        "lock_shoulder_curves": len(curves),
        "lock_shoulder_curve_w_mm": max(b[2] - b[0] for b in curves),
        "lock_shoulder_curve_h_mm": max(b[3] - b[1] for b in curves),
        "relief_arcs": len(relief_boxes),
        "relief_arc_radius_mm": relief_r[0],
        "side_liner_short_front_mm": fx - X1,
        "side_liner_short_back_mm": bx_ - X1,
        "side_liner_edge_points": len(liner_pts),
        "side_liner_edge_straight_mm": max(min(abs(d), abs(d + tab_h)) for d in base_dev),
        "lock_shoulder_mm": max(p[0] for p in shoulder) - min(p[0] for p in shoulder),
        "lock_shoulder_at_mm": shoulder[0][1] - y_back,
        "lock_tip_mm": abs(tip[1][0] - tip[0][0]),
        "lock_length_mm": tip[0][1] - y_back,
        "lock_relief_mm": abs(relief[1][1] - relief[0][1]),
        "header_mm": y_ret - y_head,
        "header_fold_mm": y_fold - y_head,
        "header_fold_straight_mm": [c["length_mm"] for c in fold_l],
        "crest_segments": crest["segments"],
        "crest_width_mm": crest["box_mm"][2] - crest["box_mm"][0],
        "crest_depth_mm": crest["box_mm"][3] - crest["box_mm"][1],
        "return_mm": ret_bottom[0][1] - y_ret,
        "return_short_mm": (y_head - y_back) - (ret_bottom[0][1] - y_ret),
        "return_inset_mm": X1 - ret_side[0][0],
        "return_width_mm": 2 * (ret_side[0][0] - Xc),
        "return_bottom_mm": abs(ret_bottom[1][0] - ret_bottom[0][0]),
        "return_corner_radius_mm": ret_side[0][0] - max(ret_bottom[0][0], ret_bottom[1][0]),
        "return_chamfer_y_mm": max(ret_chamfer[0][1], ret_chamfer[1][1]) - y_ret,
        "clearance_mm": flap_r[0]["a"][1] - y_back,
        "floor_back_crease_mm": by_y[y_back][0]["length_mm"],
    }
    rnd = lambda v: [_r(x, 2) for x in v] if isinstance(v, list) else (_r(v, 2) if isinstance(v, float) else v)  # noqa
    return {"frame": {"X0_mm": X0, "X1_mm": X1, "centre_mm": _r(Xc, 2),
                      "y_mm": {"front spine / liner": y_liner, "front skin / spine": y_skin, "floor front": y_front,
                               "side start": side_start, "floor back": y_back, "header": y_head,
                               "header fold": y_fold, "return": y_ret}},
            "creases": [dict(c, role=roles[c["id"]]) for c in cr], "cut_groups": cut_groups,
            "cut_paths": len(walk["cuts"]), "cut_unassigned": unassigned,
            "measures": {k: rnd(v) for k, v in m.items()}}


#: HOUSE key -> the reference_measures key it must equal (the runner's check)
HOUSE_FROM_WALK = {
    "principal_width_mm": "principal_width_mm", "floor_depth_mm": "floor_depth_mm", "side_run_mm": "side_run_mm",
    "side_start_mm": "side_start_mm", "spine_mm": "spine_mm", "liner_short_mm": "liner_short_mm",
    "liner_inset_mm": "liner_inset_mm", "tab_base_mm": "tab_base_mm", "tab_tip_mm": "tab_tip_mm",
    "tab_height_mm": "tab_height_mm", "slot_depth_mm": "slot_depth_mm", "front_slot_offset_mm": "front_slot_offset_mm",
    "side_slot_centre_1_mm": "side_slot_centre_1_mm", "side_slot_centre_2_mm": "side_slot_centre_2_mm",
    "corner_flap_inset_mm": "corner_flap_inset_mm", "corner_flap_top_gap_mm": "corner_flap_top_gap_mm",
    "corner_flap_length_mm": "corner_flap_length_mm", "back_inset_mm": "back_inset_mm",
    "back_wall_mm": "back_wall_mm", "back_flap_depth_mm": "back_flap_depth_mm",
    "back_flap_bottom_mm": "back_flap_bottom_mm", "lock_neck_mm": "lock_neck_mm", "lock_head_mm": "lock_head_mm",
    "lock_head_at_mm": "lock_head_at_mm", "lock_shoulder_mm": "lock_shoulder_mm",
    "lock_shoulder_at_mm": "lock_shoulder_at_mm", "lock_tip_mm": "lock_tip_mm", "lock_length_mm": "lock_length_mm",
    "lock_relief_mm": "lock_relief_mm", "lock_slot_width_mm": "lock_slot_width_mm",
    "lock_slot_into_body_mm": "lock_slot_into_body_mm", "lock_slot_length_mm": "lock_slot_length_mm",
    "relief_arc_radius_mm": "relief_arc_radius_mm", "lock_shoulder_curve_w_mm": "lock_shoulder_curve_w_mm",
    "lock_shoulder_curve_h_mm": "lock_shoulder_curve_h_mm", "side_liner_short_front_mm": "side_liner_short_front_mm",
    "side_liner_short_back_mm": "side_liner_short_back_mm",
    "header_mm": "header_mm", "header_fold_mm": "header_fold_mm", "return_mm": "return_mm",
    "return_short_mm": "return_short_mm", "return_inset_mm": "return_inset_mm",
    "return_chamfer_y_mm": "return_chamfer_y_mm", "return_corner_radius_mm": "return_corner_radius_mm",
    "clearance_mm": "clearance_mm",
}


def house_against_walk(measures: dict) -> list:
    """Every HOUSE value against the walk's measure: ``[{"house", "value", "walk", "ok"}]``."""
    out = []
    for k, mk in HOUSE_FROM_WALK.items():
        got = measures["measures"][mk]
        out.append({"house": k, "value": HOUSE[k][0], "walk": got,
                    "ok": got is not None and abs(float(got) - HOUSE[k][0]) <= 0.011})
    return out


def reference_mapping(measures: dict, record: dict, die: Die, *, sha256: str, tier: str) -> dict:
    """reference-mapping.json (schema reference_mapping/1.0): every ES3083 panel, fold, cut feature, slot and tab →
    this template's part, with the walk's measure and the re-solved value."""
    g = _g_from_record(record)
    m = measures["measures"]
    tray = next(p for p in die.parts if p.name == "tray")
    cl = {n: c.length for n, c in tray.creases}

    def cre(prefix):
        return [_r(v, 2) for n, v in sorted(cl.items()) if n.startswith(prefix)]
    ids = {}
    for c in measures["creases"]:
        ids.setdefault(c["role"], []).append(c["id"])
    rows = []

    def row(part, kind, measured, our, resolved, rule, note="", role=None):
        rows.append({"es3083_part": part, "kind": kind, "measured_mm": measured, "our_part": our,
                     "resolved_mm": resolved, "rule": rule, "note": note,
                     "crease_ids": ids.get(role, []) if role else []})
    t = g["t"]
    run = g["skin_y1"] - g["skin_y0"]
    # -- panels ------------------------------------------------------------------------------------------------------
    row("floor (side creases x 491.94 → 766.94; front crease → back crease)", "panel",
        [m["principal_width_mm"], m["floor_depth_mm"]], "tray: floor",
        [_r(g["floor_w"], 2), _r(g["floor_d"], 2)],
        "scaled to the owner's footprint 250 × 160: crease to crease = outer − 2 × board")
    row("front wall, outer skin", "panel", m["front_skin_mm"], "tray: front skin", _r(g["front_skin_h"], 2),
        "the owner's front wall 20 mm (outer, over the counter) − board")
    row("front wall spine (doubled wall's top)", "panel", m["spine_mm"], "tray: front spine", g["spine"],
        "kept from the house")
    row("front wall inner liner", "panel", [m["front_liner_width_mm"], m["front_liner_mm"]], "tray: front liner",
        [_r(g["floor_w"] - 2 * house("liner_inset_mm"), 2), _r(g["front_skin_h"] - house("liner_short_mm"), 2)],
        "kept from the house: inset 5.50 a side, 2.00 shorter than its skin")
    tab_rule = ("base and tip kept from the house; height re-solved: the liner's %.2f short + the %.2f board = %.2f, "
                "so the tip stops flush with the floor's underside (the house's %.2f would reach %.2f below it) — "
                "departures: liner_tabs_flush" % (house("liner_short_mm"), t, g["liner_tab_h"], house("tab_height_mm"),
                                                  house("tab_height_mm") - g["liner_tab_h"]))
    row("front liner lock tabs (2)", "tab", [m["tab_base_mm"], m["tab_tip_mm"], m["tab_height_mm"]],
        "tray: front liner tab L / R", [house("tab_base_mm"), house("tab_tip_mm"), _r(g["liner_tab_h"], 2)], tab_rule)
    row("side walls, outer skins (2), tapered", "panel",
        [m["side_front_height_mm"], m["side_back_height_mm"], m["side_run_mm"]], "tray: side skin L / R",
        [_r(g["front_skin_h"], 2), _r(g["back_wall_h"], 2), _r(run, 2)],
        "solved: from the front wall's height to the back wall's (the owner's taper); run = floor depth − the "
        "house's 1.50 front offset", "ES3083 stands +0.42 over its front wall and 6.00 under its back wall; not "
        "carried")
    row("side spines (2)", "panel", m["side_spine_mm"], "tray: side spine L / R", g["spine"], "kept from the house",
        "measured perpendicular between the double creases at both ends")
    row("side liners (2), free edge short of the floor (reflected back across the spine: front end, back end)",
        "panel", [m["side_liner_short_front_mm"], m["side_liner_short_back_mm"]], "tray: side liner L / R",
        [house("liner_short_mm"), house("liner_short_mm")],
        "re-solved: the liner is its skin reflected across the spine, its free edge a constant %.2f short of the floor "
        "(the front liner's measured short), its back end %.2f clear of the return flap" % (
            house("liner_short_mm"), g["clearance"]),
        "ES3083's edge (straight within %.2f, its tabs %.2f beyond it) is NOT the floor line reflected: it runs from "
        "%.2f short of the floor at the front to %.2f past it at the back — departures: side_liner_edge" % (
            m["side_liner_edge_straight_mm"], house("tab_height_mm"), m["side_liner_short_front_mm"],
            -m["side_liner_short_back_mm"]))
    row("side liner lock tabs (4)", "tab", [m["tab_base_mm"], m["tab_tip_mm"], m["tab_height_mm"]],
        "tray: side liner tab L1 L2 R1 R2", [house("tab_base_mm"), house("tab_tip_mm"), _r(g["liner_tab_h"], 2)],
        tab_rule + "; positions scaled to the side run (centres %.2f, %.2f of %.2f)" % (
            house("side_slot_centre_1_mm") * run / house("side_run_mm"),
            house("side_slot_centre_2_mm") * run / house("side_run_mm"), run))
    row("corner flaps (2)", "flap", [m["corner_flap_width_mm"], m["corner_flap_length_mm"]],
        "tray: corner flap L / R", [_r(g["front_skin_h"] - house("corner_flap_inset_mm") -
                                       house("corner_flap_top_gap_mm"), 2), house("corner_flap_length_mm")],
        "re-solved: insets kept (4.00 from the floor crease, 2.42 under the side's top), length kept")
    row("back wall", "panel", [m["back_body_mm"], m["back_wall_mm"]], "tray: back wall",
        [_r(g["floor_w"] - 2 * house("back_inset_mm"), 2), _r(g["back_wall_h"], 2)],
        "width: the house's 1.50 inset a side; height SOLVED from the slot (the leaning stack's top)",
        "the owner's 'about 245' is not built — die.json departures[0]")
    row("back wall side flaps (2), trapezoid", "flap",
        [m["back_flap_depth_mm"], m["back_flap_bottom_mm"], m["back_flap_outer_top_mm"]], "tray: back flap L / R",
        [_r(g["back_flap_depth"], 2), house("back_flap_bottom_mm"),
         _r(skin_height(g, g["skin_y1"] - g["back_flap_depth"]) - g["clearance"], 2)],
        "depth scaled to the side run; bottom kept; top follows the side's taper 2.00 under it",
        "sandwiched between each side's skin and liner, as ES3083's")
    row("side skin lock tabs (2), arrow", "tab",
        [m["lock_neck_mm"], m["lock_head_mm"], m["lock_shoulder_mm"], m["lock_tip_mm"], m["lock_length_mm"]],
        "tray: side lock tab L / R", [house("lock_neck_mm"), house("lock_head_mm"), house("lock_shoulder_mm"),
                                      house("lock_tip_mm"), house("lock_length_mm")],
        "kept from the house; at mid-height of the side's back edge (ES3083 %.2f of %.2f; ours %.2f of %.2f)" % (
            m["lock_neck_centre_mm"], m["side_back_height_mm"], g["lock_h"], g["back_wall_h"]),
        "ES3083's %d shoulder-to-tip edges are curves (box %.2f × %.2f); ours are the straight chords between the same "
        "end points — departures: lock_shoulder_curves" % (m["lock_shoulder_curves"], m["lock_shoulder_curve_w_mm"],
                                                          m["lock_shoulder_curve_h_mm"]))
    row("header, rear leaf (back wall up to the top fold)", "panel", m["header_fold_mm"], "tray: header rear leaf",
        g["header_h"], "the owner's header 110")
    row("header, front leaf (top fold down to the return)", "panel", _r(m["header_mm"] - m["header_fold_mm"], 2),
        "tray: header front leaf", g["header_h"], "the owner's header 110 (doubled as ES3083's 197 = 2 × 98.50)")
    row("return flap", "flap", [m["return_width_mm"], m["return_mm"]], "tray: return flap",
        [_r(g["header_w"] - 2 * house("return_inset_mm"), 2), _r(g["return_mm"], 2)],
        "length = back wall − 3.00 (kept: ES3083 83.00 − 80.00); width = header − 2 × 5.00 (kept)")
    # -- folds ---------------------------------------------------------------------------------------------------------
    row("floor / front skin crease (3 segments around 2 slots)", "crease", m["front_crease_segments_mm"],
        "tray: floor / front skin 1–3", cre("floor / front skin"), "slots re-placed at ±%.2f (±85.00 × %.0f / 275)" % (
            house("front_slot_offset_mm") * g["floor_w"] / house("principal_width_mm"), g["floor_w"]),
        role="floor / front skin")
    row("front skin / front spine crease", "crease", by_role(measures, "front skin / front spine"),
        "tray: front skin / front spine", cre("front skin / front spine"), "= floor width", role="front skin / "
                                                                                                    "front spine")
    row("front spine / front liner crease", "crease", by_role(measures, "front spine / front liner"),
        "tray: front spine / front liner", cre("front spine / front liner"), "floor width − 2 × 5.50",
        role="front spine / front liner")
    row("floor / side skin creases (2 × 3 segments around 2 slots each)", "crease", m["side_crease_segments_mm"],
        "tray: floor / side skin L1–3, R1–3", cre("floor / side skin R"), "slots at the scaled centres, 35.50 long",
        "the findings doc's 'front stack 43 / 35 / 50 / 35 / 33.5' IS this run (crease, slot, crease, slot, crease "
        "from the back) — see correction", role="floor / side skin")
    row("side skin / side spine creases (2, slanted)", "crease", m["inner_slant_crease_mm"],
        "tray: side skin / side spine L / R", cre("side skin / side spine R"), "the taper's top edge",
        role="side skin / side spine")
    row("side spine / side liner creases (2, slanted)", "crease", m["outer_slant_crease_mm"],
        "tray: side spine / side liner L / R", cre("side spine / side liner R"), "the spine's far edge, to the liner's "
        "back end", role="side spine / side liner")
    row("side skin / corner flap creases (2)", "crease", m["corner_flap_width_mm"],
        "tray: side skin / corner flap L / R", cre("side skin / corner flap R"), "the corner flap's width",
        role="side skin / corner flap")
    row("floor / back wall crease", "crease", m["floor_back_crease_mm"], "tray: floor / back wall",
        cre("floor / back wall"), "the back wall's width", "ES3083's runs 1.50 short at its left end (273.50)",
        role="floor / back wall")
    row("back wall / back flap creases (2 × 2 around the lock slot)", "crease",
        by_role(measures, "back wall / back flap"), "tray: back wall / back flap L1–2, R1–2",
        cre("back wall / back flap R"), "from the flap's bottom (4.00) to 2.00 under the top, around the lock slot",
        role="back wall / back flap")
    row("side skin / lock tab creases (2)", "crease", m["lock_neck_mm"], "tray: side skin / lock tab L / R",
        cre("side skin / lock tab R"), "kept", role="side skin / lock tab")
    row("back wall / header crease", "crease", by_role(measures, "back wall / header rear leaf"),
        "tray: back wall / header rear leaf", cre("back wall / header"), "the back wall's width",
        role="back wall / header rear leaf")
    row("header top fold, straight parts (2)", "crease", m["header_fold_straight_mm"], "tray: header top fold",
        cre("header top fold"), "one straight fold across the header (250)", role="header top fold (straight part)")
    row("header top fold, shaped crest (61 segments)", "crease",
        {"width": m["crest_width_mm"], "depth": m["crest_depth_mm"], "segments": m["crest_segments"]},
        "not carried", None,
        "not carried: the crest's outline belongs to ES3083's artwork; the owner's header is a 250 × 110 rectangle",
        "its box and segment count only — the outline itself is never copied", role="header top fold (shaped crest)")
    row("header front leaf / return flap crease", "crease", by_role(measures, "header front leaf / return flap"),
        "tray: header front leaf / return flap", cre("header front leaf / return"), "the header's width",
        role="header front leaf / return flap")
    # -- slots, cuts ---------------------------------------------------------------------------------------------------
    row("front floor slots (2)", "slot", [m["tab_base_mm"], m["slot_depth_mm"]], "tray: front slot L / R",
        [house("tab_base_mm") + 0.5, house("slot_depth_mm")], "tab + 0.5 (the lead's rule); depth kept",
        "ES3083: slot = tab (+0.00)")
    row("floor side slots (4)", "slot", [m["side_slot_lengths_mm"], m["slot_depth_mm"]],
        "tray: side slot L1 L2 R1 R2", [house("tab_base_mm") + 0.5, house("slot_depth_mm")],
        "tab + 0.5; depth kept", "ES3083: slot = tab (+0.00)")
    row("back flap lock slots (2)", "slot", [m["lock_slot_length_mm"], m["lock_slot_width_mm"]],
        "tray: lock slot L / R", [house("lock_head_mm") + 0.5, house("lock_slot_width_mm")],
        "head + 0.5 (the lead's rule); width and 0.50 into the body kept", "ES3083: 33.00 for a 29.00 head (+4.00)")
    row("lock tab relief slits (4)", "cut", m["lock_relief_mm"], "tray: lock relief L a/b, R a/b",
        house("lock_relief_mm"), "kept")
    row("front corner relief arcs (2) and back flap relief arcs (2): half circles, radius", "cut",
        m["relief_arc_radius_mm"], "not carried", None,
        "not carried: a cutting detail (R %.2f, %d arcs measured); the clearances they make are kept" % (
            m["relief_arc_radius_mm"], m["relief_arcs"]), "departures: relief_arcs")
    row("return flap corners R 10 and chamfers", "cut", [m["return_corner_radius_mm"], m["return_chamfer_y_mm"]],
        "tray: return flap", [house("return_corner_radius_mm"), house("return_chamfer_y_mm")], "kept")
    # -- parts ES3083 does not have ----------------------------------------------------------------------------------
    extra = [{"our_part": "slot insert", "source": "D-D12-2: one slot 194 × 30, floor 60 up, leaning 15°",
              "note": "ES3083 holds its palettes in a separate PET blister (the findings doc); the slot is the "
                      "owner's, drawn as a closed tube with wings"},
             {"our_part": "front platform, back platform", "source": "D-D12-2: raised hole platforms 20 / 30 mm",
              "note": "the house's E-flute insert with a hole (house 020's die) in kind; every number the owner's or "
                      "solved"},
             {"our_part": "floor keys (tray floor slots; key tabs on the platforms' and the slot insert's legs)",
              "source": "builder_provisional.floor_keys (the reviewer's M1)",
              "note": "tab widths the house's: %.2f (ES3083's front liner tab base) and %.2f (its lock tab neck); "
                      "slot = tab + 0.5 by board + 0.5 on a front leg, by board + %d × board + 0.5 on a platform's "
                      "back leg (the fold allowance); positions the builder's" % (
                          house("tab_base_mm"), house("lock_neck_mm"), FOLD_ALLOWANCE_BOARDS)}]
    found = sorted(c["id"] for c in measures["creases"])
    mapped = sorted({i for r in rows for i in r["crease_ids"]})
    panel_rows = [r for r in rows if r["kind"] in ("panel", "flap", "tab")]
    instances = {"floor": 1, "front skin": 1, "front spine": 1, "front liner": 1, "front liner tabs": 2,
                 "side skins": 2, "side spines": 2, "side liners": 2, "side liner tabs": 4, "corner flaps": 2,
                 "back wall": 1, "back flaps": 2, "lock tabs": 2, "header rear leaf": 1, "header front leaf": 1,
                 "return flap": 1}
    tray_faces = len(tray.faces)
    return {
        "schema": "reference_mapping/1.0",
        "template": "%s/%s" % (TEMPLATE_ID, VERSION),
        "source": {"path": REFERENCE_PATH, "sha256": sha256, "tier": tier, "use": "measured only, never placed",
                   "owner_named_path": "materials/unknown/unclassified/6a13d2d45197d26d/ (exists, empty)"},
        "method": ("PyMuPDF page.get_drawings() over the one page; strokes of colour (0.006, 0.005, 0.006) at "
                   "0.709 pt = CUT, of colour (0.904, 0.105, 0.104) = CREASE; mm = pt × 25.4 / 72, 2 dp; Bézier "
                   "items taken by their end points; every other stroke excluded by colour (listed). Only numbers "
                   "leave the walk: no path, outline or byte of the file is copied, traced or embedded."),
        "frame": measures["frame"],
        "creases_found": [_crease_entry(c, measures["frame"]) for c in measures["creases"]],
        "cut_paths": {"found": measures["cut_paths"], "groups": measures["cut_groups"],
                      "unassigned": measures["cut_unassigned"]},
        "rows": rows,
        "parts_not_in_es3083": extra,
        "correction": ("The findings doc (docs/archive/es3083/ES3083_DIMENSION_FINDINGS.md) lists the 'front panel "
                       "stack 43.00 / 35.00 / 50.00 / 35.00 / 33.50 mm' as consecutive fold spacings, each 275 wide. "
                       "The walk shows otherwise: they are the floor's side crease run, %s mm crease segments "
                       "interrupted by two %s mm lock slots (33.50 crease, 35.00 slot, 50.00 crease, 35.00 slot, "
                       "43.00 crease from the front; 196.50 in all), on both side creases (x 491.94 and 766.94). "
                       "The fold spacings down the principal column are 5.00 (spine) / 25.00 (front skin) / 198.00 "
                       "(floor) / 83.00 (back wall) / 98.50 + 98.50 (header) / 80.00 (return). The doc's 'largest "
                       "panel 275.00 × 197.00 mm' is not one panel either: %.2f is the doubled header, two %.2f leaves "
                       "across its top fold (y %.2f → %.2f → %.2f, between %.2f-long creases); the largest single "
                       "panel is the floor, %.2f × %.2f crease to crease (y %.2f → %.2f)." % (
                           " / ".join("%.2f" % v for v in m["side_crease_segments_mm"]),
                           " / ".join("%.2f" % v for v in m["side_slot_lengths_mm"]),
                           m["header_mm"], m["header_fold_mm"], measures["frame"]["y_mm"]["header"],
                           measures["frame"]["y_mm"]["header fold"], measures["frame"]["y_mm"]["return"],
                           m["principal_width_mm"], m["principal_width_mm"], m["floor_depth_mm"],
                           measures["frame"]["y_mm"]["floor front"], measures["frame"]["y_mm"]["floor back"])),
        "completeness": {
            "creases_found": len(found), "creases_mapped": len(mapped), "creases_unmapped": sorted(set(found) -
                                                                                                   set(mapped)),
            "cut_paths_found": measures["cut_paths"],
            "cut_paths_assigned": measures["cut_paths"] - len(measures["cut_unassigned"]),
            "cut_groups_as_expected": all(gr["paths"] == gr["expected"] for gr in measures["cut_groups"]),
            "panel_instances_read": sum(instances.values()), "panel_instances": instances,
            "panel_rows": len(panel_rows), "tray_faces_drawn": tray_faces,
            "words": "every crease of the walk carries a role and sits in a row; every cut path is attributed to a "
                     "feature (left folded onto right); the panel inventory is read from the crease topology "
                     "(26 instances) and equals the tray's 26 drawn faces",
        },
    }


def _crease_entry(c: dict, frame: dict) -> dict:
    """One crease of the walk as a measure: id, kind, role, length and ONE position relative to the floor's frame —
    never its end points, so the reference's fold layer cannot be redrawn from this file."""
    out = {"id": c["id"], "kind": c["kind"], "role": c["role"], "length_mm": c["length_mm"]}
    front, centre = frame["y_mm"]["floor front"], frame["centre_mm"]
    if c["kind"] == "horizontal":
        out["behind_floor_front_crease_mm"] = _r(c["a"][1] - front, 2)
    elif c["kind"] == "vertical":
        out["from_centre_line_mm"] = _r(abs(c["a"][0] - centre), 2)
    elif c["kind"] == "slanted":
        out["angle_from_depth_axis_deg"] = _r(math.degrees(math.atan2(abs(c["b"][0] - c["a"][0]),
                                                                      c["b"][1] - c["a"][1])), 2)
    else:
        box = c["box_mm"]
        out.update(width_mm=_r(box[2] - box[0], 2), depth_mm=_r(box[3] - box[1], 2), segments=c["segments"])
    return out


def by_role(measures: dict, role: str) -> list:
    return [c["length_mm"] for c in measures["creases"] if c["role"] == role]


# =====================================================================================================================
# the template's declaration: registered (D-D13-3)
# =====================================================================================================================


def template_definition():
    """The registry entry this template carries: apps/dielines/registry.py's COUNTER_TRAY_HEADER (D-D13-3: registered
    with the registry-agreement test the other templates carry; 0.1 ⟪PROVISIONAL⟫, never production — ``REGISTRATION``).
    The registry declares it (one source of truth); this returns it."""
    from apps.dielines import registry as R
    return R.resolve(TEMPLATE_ID, VERSION)


__all__ = ["solve", "full_record", "build_die", "fold_check", "sightlines", "sight_tolerance", "measure_reference_die",
           "stood_keys", "floor_key_slots", "key_fits", "turned_round", "print_side_in", "seats_at", "seat_range",
           "platform_racking", "insert_sway", "insert_linkage", "sway_pose", "frame_pose", "frame_lean_limit",
           "frame_leans", "frame_reserve", "frame_fold_corners", "insert_gussets", "back_wall_ruling",
           "floor_keys", "mark_box", "die_word_boxes",
           "template_definition", "record_bytes", "alternative_board", "default_products", "default_provisional",
           "HOUSE", "PT_PER_MM", "MM_PER_PT"]
