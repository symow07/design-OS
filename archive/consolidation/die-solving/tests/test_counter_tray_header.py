"""counter_tray_header 0.1 — D-D12-2's family counter display: the solve, the die, the fold check, the sightlines,
the sheets and the ES3083 reference mapping. Pure: no database, no network, no paid call.

[The owner's decision, CURRENT_DECISIONS.md "Day 12", D-D12-2: "the engine solves from the three product records
(palette 190 × 120 × 12; lipstick 80 × Ø 20; balm 70 × Ø 18), never from a picture ... a fold check that outputs the
closed dimensions and every clearance against the three product records ... The sightline check, defined for this
form ... pass = the top 25 mm of every stick's front face, and the front palette's lid above the sticks' tops,
visible."]
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from apps.dielines.exporters import counter_display_files as L
from apps.dielines.geometry import counter_tray_header as C

# Day 13, D-D13-2: the die is rebuilt; Day 12's record is kept as it was
OUT = Path(__file__).resolve().parents[4] / "docs/audit/day-13/display/die"
DAY12 = Path(__file__).resolve().parents[4] / "docs/audit/day-12/display/die"
SIN, COS = math.sin(math.radians(15)), math.cos(math.radians(15))


@pytest.fixture(scope="module")
def record():
    return C.full_record()


@pytest.fixture(scope="module")
def die(record):
    return C.build_die(record)


def _v(fact):
    return fact["value"]


# --- the solve against hand arithmetic ---------------------------------------------------------------------------------

def test_the_back_wall_is_solved_from_the_slot_not_taken_from_the_estimate(record):
    stack_top = 60 + 24 * SIN + 120 * COS                      # 182.1228 mm over the tray floor
    assert abs(_v(record["tray"]["back_wall_panel_mm"]) - stack_top) < 1e-3
    assert abs(_v(record["tray"]["back_wall_outer_mm"]) - (stack_top + 1.5)) < 1e-3
    assert abs(_v(record["tray"]["header_top_mm"]) - (stack_top + 1.5 + 110)) < 1e-3
    # Day 13, D-D13-1: "182.12 mm above the tray floor (183.62 mm over the counter) ... Not a departure; the record is
    # corrected" — his ruling beside the solved height, the 245 estimate and its departure gone
    ruling = record["tray"]["back_wall_ruling"]
    assert _v(ruling["panel_mm"]) == 182.12 and _v(ruling["outer_mm"]) == 183.62 and ruling["agrees"] is True
    assert round(stack_top, 2) == 182.12 and round(stack_top + 1.5, 2) == 183.62
    assert ruling["words"] == C.BACK_WALL_RULING and "Not a departure; the record is corrected." in ruling["words"]
    assert ruling["panel_mm"]["source"].startswith("D-D13-1 (CURRENT_DECISIONS.md, Day 13)")
    assert _v(record["owner_provisional"]["back_wall_mm"]) == 182.12
    assert "back_wall_owner_estimate_mm" not in record["owner_provisional"]
    assert "back_wall_owner_estimate_mm" not in record["tray"]
    assert "back_wall_245" not in {d["id"] for d in record["departures"]}
    # the ruling is his words as typed in CURRENT_DECISIONS.md's Day 13 block
    decisions = (Path(__file__).resolve().parents[4] / "CURRENT_DECISIONS.md").read_text(encoding="utf-8")
    assert "182.12 mm above the tray floor (183.62 mm over the counter)" in decisions
    assert "Not a departure; the record is corrected." in decisions
    fc = C.fold_check(record)
    ruled = next(f for f in fc["findings"] if f["id"] == "back_wall_vs_owner_ruling")
    assert ruled["ok"] and ruled["expected"] == {"panel_mm": 182.12, "outer_mm": 183.62}
    # planted control: the slot floor 1 mm higher solves a back wall 1 mm taller — no longer the height he ruled
    raised = C.solve(provisional={"slot_floor_mm": 61.0})
    assert "back_wall_vs_owner_ruling" in C.fold_check(raised)["failed"]
    assert raised["tray"]["back_wall_ruling"]["agrees"] is False


def test_the_tray_and_the_slot_against_hand_arithmetic(record):
    t = 1.5
    assert [_v(f) for f in record["tray"]["floor_crease_to_crease_mm"]] == [250 - 2 * t, 160 - 2 * t]
    assert _v(record["tray"]["front_skin_panel_mm"]) == 20 - t
    assert _v(record["tray"]["back_inner_face_y_mm"]) == 160 - 3 * t
    # set forward by one fold's allowance (1.5 × board) + the key's play 0.25 (MJ-1) — and, Day 13, D-D13-2: + the
    # stack corner's move back at the closed tube's most lean (4.4316), so 119.9417 → 115.5101
    reserve = C._g_from_record(record)["frame"]["reserve"]
    assert 4.43 < reserve < 4.44
    junction = 160 - 3 * t - 2.0 - 120 * SIN - (1.5 * t + 0.25) - reserve
    assert abs(_v(record["slot"]["junction_y_mm"]) - junction) < 1e-3
    assert abs(_v(record["slot"]["junction_y_mm"]) - 115.5101) < 1e-4
    # Day 13, D-D13-2: the stack's top-back corner as drawn 8.93 from the back (2.5 + the lean's 4.43 + 2.00)
    assert abs(_v(record["slot"]["stack_rear_y_mm"]) - (160 - 3 * t - 2.0 - 2.5 - reserve)) < 1e-3
    assert abs(_v(record["slot"]["stack_rear_y_rearmost_mm"]) - (160 - 3 * t - 2.0 - reserve)) < 1e-3
    assert abs(_v(record["slot"]["stack_rear_y_rearmost_leaned_mm"]) - (160 - 3 * t - 2.0)) < 1e-3
    assert abs(_v(record["slot"]["front_lid_bottom"]["h_mm"]) - (60 + 24 * SIN)) < 1e-3
    assert abs(_v(record["slot"]["bed_front_edge"]["y_mm"]) - (junction - 30 * COS)) < 1e-3
    assert _v(record["slot"]["width_mm"]) == 194.0 and _v(record["slot"]["palettes"]) == 2
    assert _v(record["slot"]["stack_mm"]) == 24.0


def test_the_platforms_and_rows_against_hand_arithmetic(record):
    gap = 3 * 1.5 + 2 * 0.25 + 0.5                              # fold allowance + both keys' play + 0.5 = 5.5
    edge = (35 - (19 + 21) / 2 - gap) / 2                       # 4.75, still >= 3 × board
    pf, pb = record["platforms"]["front"], record["platforms"]["back"]
    assert _v(record["platforms"]["gap_between_mm"]) == gap and _v(record["platforms"]["edge_mm"]) == edge
    assert _v(pf["plate_depth_mm"]) == 19 + 2 * edge and _v(pb["plate_depth_mm"]) == 21 + 2 * edge
    assert [_v(f) for f in pf["plate_y_mm"]] == [5.0 + 2.0, 5.0 + 2.0 + 28.5]
    assert [_v(f) for f in pb["plate_y_mm"]] == [41.0, 71.5]
    assert _v(pf["row_y_mm"]) == 21.25 and _v(pb["row_y_mm"]) == 56.25
    assert _v(pb["row_y_mm"]) - _v(pf["row_y_mm"]) == 35.0
    assert _v(pf["length_mm"]) == 250 - 2 * 5.0 - 2 * 2.0


def test_the_platform_heights_are_the_owners(record, die):
    assert _v(record["platforms"]["front"]["plate_top_h_mm"]) == 20.0
    assert _v(record["platforms"]["back"]["plate_top_h_mm"]) == 30.0
    parts = {p.name: p for p in die.parts}
    for name, leg in (("front platform", 20.0), ("back platform", 30.0)):
        face = dict((n, f) for n, f, _p in parts[name].faces)["front leg"]
        assert abs((face.bounds[3] - face.bounds[1]) - leg) < 1e-9


def test_hole_and_slot_counts_against_the_product_records(record, die):
    holes = record["holes"]
    assert len([h for h in holes if h["product"] == "balm"]) == 6
    assert len([h for h in holes if h["product"] == "lipstick"]) == 6
    assert {h["diameter_mm"] for h in holes if h["product"] == "balm"} == {18 + 1.0}
    assert {h["diameter_mm"] for h in holes if h["product"] == "lipstick"} == {20 + 1.0}
    assert [h["x_mm"] for h in holes if h["row"] == "front"] == [-88.0, -56.0, -24.0, 8.0, 40.0, 72.0]
    assert [h["x_mm"] for h in holes if h["row"] == "back"] == [-72.0, -40.0, -8.0, 24.0, 56.0, 88.0]
    parts = {p.name: p for p in die.parts}
    assert [len(parts[n].holes) for n in ("front platform", "back platform")] == [6, 6]
    assert sorted({round(2 * r, 6) for _n, _c, r in parts["front platform"].holes}) == [19.0]
    assert sorted({round(2 * r, 6) for _n, _c, r in parts["back platform"].holes}) == [21.0]
    assert [p.name for p in die.parts].count("slot insert") == 1


# --- the fold check ---------------------------------------------------------------------------------------------------

def test_the_fold_check_passes_on_the_solved_die(record, die):
    fc = C.fold_check(record, die)
    assert fc["passed"], fc["failed"]
    assert fc["closed"]["outer_width_mm"] == 250.0 and fc["closed"]["outer_depth_mm"] == 160.0
    assert fc["closed"]["slot_width_mm"] == 194.0 and fc["closed"]["front_wall_mm"] == 20.0
    ids = {f["id"] for f in fc["findings"]}
    for must in ("slot_width_vs_palette", "slot_bed_vs_stack", "stack_top_vs_back_wall", "hole_vs_balm",
                 "hole_vs_lipstick", "web_balm", "web_lipstick", "lipstick_body_visible", "balm_body_visible",
                 "front_wall_vs_front_row", "words_outside_cut", "no_part_overlap"):
        assert must in ids
    for p in ("tray", "slot insert", "front platform", "back platform"):
        for rule in ("one_outline", "no_face_overlap", "creases_inside", "creases_hinge"):
            assert any(f["id"] == "%s:%s" % (rule, p) and f["ok"] for f in fc["findings"])
    tabs = [f for f in fc["findings"] if f["id"].startswith("tab_slot:")]
    # the tray's own 2 + 4 + 2, and the floor keys: 4 per platform, 2 on the slot insert
    assert len(tabs) == 2 + 4 + 2 + (4 + 4 + 2) and all(f["ok"] for f in tabs)
    keys = [f for f in fc["findings"] if f["id"].startswith("tab_slot:key tab")]
    # a front leg's slot board + 0.5 across; a platform's back leg's board + 3 × board (the fold allowance) + 0.5
    assert {(f["measured"]["slot_length_mm"] - f["measured"]["tab_width_mm"], f["measured"]["slot_width_mm"])
            for f in keys} == {(0.5, 2.0), (0.5, 6.5)}
    assert sorted(f["measured"]["slot_width_mm"] for f in keys) == [2.0] * 6 + [6.5] * 4
    assert [r["id"] for r in fc["removed"]] == ["stack_top_vs_header"] and "stack_top_vs_header" not in ids


def test_every_tab_lands_on_its_slot_and_a_moved_slot_fails(record):
    fc = C.fold_check(record, C.build_die(record))
    lands = [f for f in fc["findings"] if f["id"].startswith("tab_lands:")]
    assert len(lands) == 8 and all(f["ok"] for f in lands)
    from shapely import affinity
    moved = C.build_die(record)
    tray = next(p for p in moved.parts if p.name == "tray")
    slot = next(sl for sl in tray.slots if sl["id"] == "side slot R2")
    slot["polygon"] = affinity.translate(slot["polygon"], 0, 3.0)
    fc2 = C.fold_check(record, moved)
    assert "tab_lands:side liner tab R2" in fc2["failed"] and not fc2["passed"]
    assert "tab_lands:side liner tab R1" not in fc2["failed"]


def test_a_189_mm_slot_fails_the_fold_check():
    rec = C.solve(provisional={"slot_width_mm": 189.0})
    fc = C.fold_check(rec)
    assert not fc["passed"]
    assert "slot_width_vs_palette" in fc["failed"]


def test_a_20_mm_hole_for_the_lipstick_fails_the_fold_check():
    rec = C.solve(provisional={"lipstick_hole_mm": 20.0})
    fc = C.fold_check(rec)
    assert not fc["passed"]
    assert "hole_vs_lipstick" in fc["failed"]


def test_a_25_mm_hole_for_the_lipstick_fails_the_fold_check_too():
    """The owner's rule is hole = product + 1 exactly (within 0.01): a hole 5 mm too big fails (MINOR 4's control)."""
    rec = C.solve(provisional={"lipstick_hole_mm": 25.0})
    fc = C.fold_check(rec)
    assert "hole_vs_lipstick" in fc["failed"] and "hole_vs_balm" not in fc["failed"]
    hv = next(f for f in fc["findings"] if f["id"] == "hole_vs_lipstick")
    assert hv["measured"] == 5.0 and hv["expected"] == 1.0


# --- the floor keys (the reviewer's M1) and the face the die is drawn from (MINOR 1) --------------------------------

def _stood_holes(die, g, part_name):
    """The drawn holes of a platform, stood the way it erects and moved to where its keys seat it."""
    stood = C.stood_keys(die, g)
    boxes = C.key_fits(stood[part_name], C.floor_key_slots(die, g))
    assert len(boxes) == 1
    dx = (boxes[0][0] + boxes[0][1]) / 2
    part = next(p for p in die.parts if p.name == part_name)
    plate = dict((n, f) for n, f, _p in part.faces)["plate"]
    xc = (plate.bounds[0] + plate.bounds[2]) / 2
    return sorted(xc - c[0] + dx for _n, c, _r in part.holes)


def test_the_platform_holes_are_drawn_mirrored_by_hand_arithmetic(record):
    """Drawn print side up, the plate is seen from above with its front leg at the top of the sheet: the shopper's
    x = L/2 − X. Balm 1 (x −88) is drawn 118 + 88 = 206 mm from the plate's left end; lipstick 1 (x −72) at 190."""
    g = C._g_from_record(record)
    assert g["plate_len"] == 236.0
    fp, bp = C._platform(g, "front"), C._platform(g, "back")
    assert fp.holes[0][1][0] == 206.0 and bp.holes[0][1][0] == 190.0
    assert fp.holes[-1][1][0] == 118.0 - 72.0 and bp.holes[-1][1][0] == 118.0 - 88.0
    assert [h["flat_x_from_plate_centre_mm"] for h in record["holes"]][:2] == [88.0, 56.0]
    assert "print side" in record["datums"]["die_face"] and "PRINT SIDE" in C.build_die(record).title


def test_the_drawn_holes_stood_as_keyed_give_the_owners_stagger(record, die):
    g = C._g_from_record(record)
    balms, lips = _stood_holes(die, g, "front platform"), _stood_holes(die, g, "back platform")
    want_b = [h["x_mm"] for h in record["holes"] if h["product"] == "balm"]
    want_l = [h["x_mm"] for h in record["holes"] if h["product"] == "lipstick"]
    assert all(abs(a - b) < 0.01 for a, b in zip(balms, want_b)) and len(balms) == 6
    assert all(abs(a - b) < 0.01 for a, b in zip(lips, want_l)) and len(lips) == 6
    both = sorted([(x, "b") for x in balms] + [(x, "l") for x in lips])
    assert [k for _x, k in both] == ["b", "l"] * 6                     # alternating: offset half a pitch
    assert all(abs((b[0] - a[0]) - 16.0) < 0.01 for a, b in zip(both, both[1:]))


def test_every_key_lands_and_each_part_fits_one_way_round_at_one_place(record, die):
    fc = C.fold_check(record, die)
    lands = [f for f in fc["findings"] if f["id"].startswith("key_lands:")]
    assert len(lands) == 10 and all(f["ok"] for f in lands)
    for f in lands:
        pm = f["measured"]["play_mm"]
        assert pm["left"] == pm["right"] == pm["front"] == 0.25
        assert pm["behind"] == (4.75 if " back leg " in f["id"] else 0.25), f["id"]
    for part in ("front platform", "back platform", "slot insert"):
        one = next(f for f in fc["findings"] if f["id"] == "key_one_place:" + part)
        assert one["ok"] and one["measured"]["places"] == 1
        assert one["measured"]["boxes_mm"] == [[-0.25, 0.25, -0.25, 0.25]]
        assert next(f for f in fc["findings"] if f["id"] == "key_rejects_turned_round:" + part)["ok"]
    for part in ("front platform", "back platform"):
        assert next(f for f in fc["findings"] if f["id"] == "key_rejects_swap:" + part)["ok"]
    for must in ("key_slots_web", "key_slots_clear_of_sticks_and_feet", "clearances_with_key_play",
                 "orientation_mark:front platform", "orientation_mark:back platform", "orientation_mark:slot insert",
                 "words_outside_cut", "key_seats_across_allowance:front platform",
                 "key_seats_across_allowance:back platform", "key_rejects_print_side_in:front platform",
                 "key_rejects_print_side_in:back platform", "key_rejects_print_side_in:slot insert",
                 "insert_glue_flap_vs_front_leg", "stack_rear_vs_back_wall"):
        assert next(f for f in fc["findings"] if f["id"] == must)["ok"], must
    widths = {k["kind"]: k["tab_width_mm"]["value"] for k in record["keys"]}
    assert widths == {"wide": 35.0, "narrow": 21.0}                    # the house's liner tab and lock neck


def test_a_symmetric_key_is_caught_turned_round(record):
    """Planted control: the front platform's keys made symmetric (both narrow, ±30) — turned round, it fits."""
    g = C._g_from_record(record)
    layout = dict(C.KEY_LAYOUT, **{"front platform": {"front leg": ((-30.0, "narrow"), (30.0, "narrow")),
                                                      "back leg": ((-30.0, "narrow"), (30.0, "narrow"))}})
    g["keys"] = C.floor_keys(g["legs"], g["t"], layout)
    fc = C.fold_check(record, C.build_die(g))
    assert "key_rejects_turned_round:front platform" in fc["failed"]
    assert "key_rejects_turned_round:back platform" not in fc["failed"]
    assert not any(f.startswith("key_lands:") for f in fc["failed"])


def test_identical_platforms_are_caught_swapped():
    """Planted control: both platforms the same depth (lipstick holes 19) and the same keys — swapped, they fit."""
    rec = C.solve(provisional={"lipstick_hole_mm": 19.0})
    g = C._g_from_record(rec)
    assert g["front_plate_d"] == g["back_plate_d"]
    same = {"front leg": ((-30.0, "wide"), (30.0, "narrow")), "back leg": ((-30.0, "wide"), (30.0, "narrow"))}
    layout = dict(C.KEY_LAYOUT, **{"front platform": same, "back platform": same})
    g["keys"] = C.floor_keys(g["legs"], g["t"], layout)
    fc = C.fold_check(rec, C.build_die(g))
    assert "key_rejects_swap:front platform" in fc["failed"] and "key_rejects_swap:back platform" in fc["failed"]
    assert "key_one_place:front platform" in fc["failed"]


def test_a_platform_drawn_unmirrored_does_not_land(record):
    """Planted control: the front platform drawn the old way (holes and keys at L/2 + x): its keys miss their slots
    and its holes would stand at −x."""
    from shapely import affinity
    die = C.build_die(record)
    g = C._g_from_record(record)
    p = next(q for q in die.parts if q.name == "front platform")
    plate = dict((n, f) for n, f, _p in p.faces)["plate"]
    xc = (plate.bounds[0] + plate.bounds[2]) / 2
    mir = lambda geom: affinity.scale(geom, xfact=-1, yfact=1, origin=(xc, 0))  # noqa: E731
    p.faces = [(n, mir(f), pr) for n, f, pr in p.faces]
    p.tabs = [dict(tb, polygon=mir(tb["polygon"]), base=mir(tb["base"])) for tb in p.tabs]
    p.holes = [(n, (2 * xc - c[0], c[1]), r) for n, c, r in p.holes]
    fc = C.fold_check(record, die)
    assert "key_lands:key tab front platform front leg wide" in fc["failed"]
    assert "key_one_place:front platform" in fc["failed"]
    assert not C.key_fits(C.stood_keys(die, g)["front platform"], C.floor_key_slots(die, g))


def test_a_plate_drawn_2_mm_deeper_puts_its_back_keys_off_their_slots(record):
    """Planted control: the back platform drawn with a plate 2 mm deeper than solved (the tray's slots unchanged) —
    its back leg, stood where the drawn plate puts it, is off its drawn place in its slot, and the 2 mm eat the fold
    allowance: folded more than 2.5 mm over drawn it no longer seats; its front leg still lands."""
    die = C.build_die(record)
    g = C._g_from_record(record)
    i = next(n for n, q in enumerate(die.parts) if q.name == "back platform")
    deeper = C._platform(dict(g, back_plate_d=g["back_plate_d"] + 2.0), "back")
    b0, b1 = die.parts[i].outline().bounds, deeper.outline().bounds
    die.parts[i] = deeper.moved(b0[0] - b1[0], b0[1] - b1[1])
    fc = C.fold_check(record, die)
    assert {"key_lands:key tab back platform back leg wide", "key_lands:key tab back platform back leg narrow",
            "key_seats_across_allowance:back platform"} <= set(fc["failed"])
    assert "key_lands:key tab back platform front leg wide" not in fc["failed"]
    seat = next(f for f in fc["findings"] if f["id"] == "key_seats_across_allowance:back platform")
    assert seat["measured"]["seat_range_mm"] == [-2.5, 3.0]


def test_a_key_slot_moved_1_mm_fails(record):
    from shapely import affinity
    die = C.build_die(record)
    tray = next(p for p in die.parts if p.name == "tray")
    sl = next(s for s in tray.slots if s["id"] == "key slot back platform back leg narrow")
    sl["polygon"] = affinity.translate(sl["polygon"], 1.0, 0)
    fc = C.fold_check(record, die)
    assert "key_lands:key tab back platform back leg narrow" in fc["failed"]
    assert "key_lands:key tab back platform back leg wide" not in fc["failed"]


# --- the fold allowance (the reviewer's MJ-1), print side in (MINOR 1) -------------------------------------------------

def test_each_platform_seats_across_the_whole_fold_allowance_and_not_outside_it(record, die):
    """Front leg keyed tight, back leg's slots 3 × board deeper behind it (x held): every folded leg spacing from the
    drawn to drawn + 4.5 seats at the drawn place, the keys' ±0.25 at either end; a spacing outside it does not."""
    g = C._g_from_record(record)
    for part in ("front platform", "back platform"):
        assert C.seat_range(die, g, part) == (-0.5, 5.0), part
        for a in (0.0, 1.5, 2.25, 3.0, 4.5):                       # the verifier's +1.5 and +3.0 among them
            boxes = C.key_fits(C.stood_keys(die, g, a)[part], C.floor_key_slots(die, g))
            assert boxes == [(-0.25, 0.25, -0.25, 0.25)], (part, a, boxes)
        for a in (-0.75, 5.25, 6.0):                               # controls: outside the allowance
            assert not C.seats_at(die, g, part, a), (part, a)
    fc = C.fold_check(record, die)
    seat = next(f for f in fc["findings"] if f["id"] == "key_seats_across_allowance:front platform")
    assert seat["ok"] and all(seat["measured"]["seats_at_each"]) and seat["measured"]["controls_refused"] == [True,
                                                                                                             True]


def test_tight_back_slots_reproduce_the_verifiers_zero_places(record):
    """Planted control (the die before MJ-1's fix): every key slot board + 0.5 across — a back leg folded 1.5 or
    3.0 mm deeper than drawn seats nowhere, and the sweep fails."""
    g = C._g_from_record(record)
    g["keys"] = [dict(k, room_mm=0.0, slot_y_mm=(k["y_mm"][0] - 0.25, k["y_mm"][1] + 0.25)) for k in g["keys"]]
    die = C.build_die(g)
    for part in ("front platform", "back platform"):
        assert C.seats_at(die, g, part, 0.0) and C.seats_at(die, g, part, 0.5)
        assert not C.seats_at(die, g, part, 1.5) and not C.seats_at(die, g, part, 3.0)
        assert C.seat_range(die, g, part) == (-0.5, 0.5)
    fc = C.fold_check(record, die)
    assert "key_seats_across_allowance:front platform" in fc["failed"]


def test_a_platform_folded_print_side_in_fits_nowhere(record, die):
    """MINOR 1: print side in, a platform is its own mirror image — across (x → −x) or front to back (y → −y, its legs
    swapped). With unlike legs (±30 / ±40; ±75 / ±60) neither seats, at either end of the fold allowance."""
    g = C._g_from_record(record)
    slots = C.floor_key_slots(die, g)
    for part in ("front platform", "back platform"):
        for a in (0.0, 4.5):
            tabs = C.stood_keys(die, g, a)[part]
            assert C.key_fits(tabs, slots)
            assert not C.key_fits(C.print_side_in(tabs), slots) and not C.key_fits(C.print_side_in(tabs, True), slots)
    fc = C.fold_check(record, die)
    for part in ("front platform", "back platform"):
        f = next(x for x in fc["findings"] if x["id"] == "key_rejects_print_side_in:" + part)
        assert f["ok"] and f["measured"]["mirrored_front_to_back_places"] == 0


def test_like_legs_would_seat_print_side_in_turned(record):
    """Planted control: the old layout (back leg keyed as its front leg) — print side in and turned, it seats."""
    g = C._g_from_record(record)
    like = dict(C.KEY_LAYOUT, **{"front platform": {"front leg": ((-30.0, "wide"), (30.0, "narrow")),
                                                    "back leg": ((-30.0, "wide"), (30.0, "narrow"))}})
    g["keys"] = C.floor_keys(g["legs"], g["t"], like)
    die = C.build_die(g)
    tabs = C.stood_keys(die, g)["front platform"]
    assert C.key_fits(C.print_side_in(tabs, True), C.floor_key_slots(die, g))
    fc = C.fold_check(record, die)
    assert "key_rejects_print_side_in:front platform" in fc["failed"]
    assert "key_rejects_print_side_in:back platform" not in fc["failed"]


def test_the_slot_insert_print_side_in_is_refused_by_its_footprint_a_listed_departure(record, die):
    """The insert is keyed on one leg (its back leg's foot is creased to the base): mirrored front to back its one row
    of keys is the same row and seats — refused only because its base would then lie over the back platform."""
    fc = C.fold_check(record, die)
    f = next(x for x in fc["findings"] if x["id"] == "key_rejects_print_side_in:slot insert")
    assert f["ok"] and f["measured"]["mirrored_across_places"] == 0
    assert f["measured"]["mirrored_front_to_back_places"] == 1 and f["measured"]["blocked_by_footprint"] == [True,
                                                                                                             True]
    assert "insert_print_side_in" in {d["id"] for d in record["departures"]}


def test_the_glue_flap_sits_inside_the_front_leg_and_the_stack_keeps_2_mm(record, die):
    """MJ-1, the insert: the base is the footprint less the front leg's board, so the glue flap rises against the front
    leg's inner face and the front leg stands on the floor in its keys; set forward by one fold's allowance + the
    key's play, the stack's top-back corner is still 2.00 from the back at the insert's rearmost seat."""
    g = C._g_from_record(record)
    assert abs(g["insert"]["base_mm"] - (g["r_y"] - g["f_y"] - 1.5)) < 1e-9
    fc = C.fold_check(record, die)
    flap = next(x for x in fc["findings"] if x["id"] == "insert_glue_flap_vs_front_leg")
    assert flap["ok"] and flap["measured"]["glue_flap_y_mm"][0] == flap["measured"]["front_leg_y_mm"][1]
    stack = next(x for x in fc["findings"] if x["id"] == "stack_rear_vs_back_wall")
    # Day 13, D-D13-2: 8.93 clear square at the drawn seat; 2.00 still the least, now at every lean the closed tube
    # permits (4.50 at the drawn seat at its most lean, 2.00 at the rearmost)
    assert stack["ok"] and stack["measured"] == 2.0 and "8.93 mm clear square" in stack["words"]
    assert "the least clearance is 4.50 at the drawn seat and 2.00 at the rearmost" in stack["words"]
    # planted control: the old base (the whole footprint) puts the glue flap in the front leg's board
    old = C._insert(dict(g, insert=dict(g["insert"], base_mm=g["insert"]["base_mm"] + 1.5)))
    i = next(n for n, q in enumerate(die.parts) if q.name == "slot insert")
    planted = C.Die(list(die.parts), die.sheet_w, die.sheet_h, die.labels, die.bar, die.title)
    b0, b1 = die.parts[i].outline().bounds, old.outline().bounds
    planted.parts[i] = old.moved(b0[0] - b1[0], b0[1] - b1[1])
    assert "insert_glue_flap_vs_front_leg" in C.fold_check(record, planted)["failed"]


def test_the_platforms_clear_at_the_full_fold_allowance(record, die):
    """The front platform's back leg 4.5 behind its drawn place and both keys at their worst: still 0.5 from the back
    platform; a stick, its row a fold (2.25) back, still 0.5 from the back leg's open slot."""
    fc = C.fold_check(record, die)
    near = next(x for x in fc["findings"] if x["id"] == "clearances_with_key_play")
    assert near["ok"] and near["measured"] == 0.5
    assert "the front platform's back leg at the full fold allowance 0.50" in near["words"]
    feet = next(x for x in fc["findings"] if x["id"] == "key_slots_clear_of_sticks_and_feet")
    assert feet["ok"] and feet["measured"] == 0.5


def test_racking_is_a_named_measured_dependency_and_the_sightline_reaches_past_it(record, sight):
    """The verifier's "an open-ended channel can rack": not held by the die — measured (the key tab binds at 25.53°,
    the plates 8.62 / 12.93 mm off their feet), listed, and the sightline searched to 20 mm in depth loses nothing."""
    fc = C.fold_check(record)
    rk = fc["racking"]
    assert rk["lean_max_deg"] == 25.53
    assert [(p["part"], p["plate_drift_max_mm"], p["stick_foot_to_back_slot_mm"]) for p in rk["parts"]] == [
        ("front platform", 8.62, 2.75), ("back platform", 12.93, 2.75)]
    assert "platform_racking" in {d["id"] for d in record["departures"]}
    depth = sight["tolerance"]["margins"]["rows_in_depth"]
    assert all(m["limit_mm"] is None and "up to 20.00 mm" in m["words"] for m in depth)
    assert max(p["plate_drift_max_mm"] for p in rk["parts"]) < 20.0


# --- the die's words (MINOR 2, MINOR 5) --------------------------------------------------------------------------------


def test_the_folders_mark_is_on_the_front_legs_reverse_face(die):
    for p in die.parts:
        if p.name not in C.KEY_LAYOUT:
            continue
        (mark,) = p.marks
        assert mark[3] == "front leg" and mark[4] == "reverse"
        front_leg = dict((n, f) for n, f, _p in p.faces)["front leg"]
        assert C.mark_box(mark).within(front_leg.buffer(-1.0))


def test_the_labels_stand_clear_of_the_bleed_and_a_label_on_it_is_caught(record, die):
    """MINOR 5: every part label, the title and the bar's words outside every bleed outline; a label put back where
    it was (4 mm above its part's top) crosses the bleed and fails."""
    fc = C.fold_check(record, die)
    w = next(x for x in fc["findings"] if x["id"] == "words_outside_cut")
    assert w["ok"] and "bleed" in w["rule"]
    old = [(text, (x, y + C.DIE_BLEED_MM + 1.0 + 0.3 * size - 4.0), size) for text, (x, y), size in die.labels]
    planted = C.Die(die.parts, die.sheet_w, die.sheet_h, old, die.bar, die.title)
    assert "words_outside_cut" in C.fold_check(record, planted)["failed"]


# --- the sightlines ---------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sight(record):
    return C.sightlines(record)


def test_the_sightline_passes_for_every_stick_and_the_lid(sight):
    sl = sight
    res = sl["result"]
    assert sl["passed"] and sl["remedy"] is None
    assert len(res["sticks"]) == 12 and all(s["pass"] and s["samples"] == 26 for s in res["sticks"])
    assert res["lid"]["pass"] and res["lid"]["visible_fraction"] == 1.0
    assert res["eye"]["y_mm"] == -500.0 and res["eye"]["z_mm"] == 350.0


def test_the_sightline_holds_with_the_keys_and_holes_play_and_records_its_margins(sight):
    tol = sight["tolerance"]
    assert tol["passed"] and tol["stick_poses"] == 64 and tol["lid_poses"] == 8
    assert tol["yaw"]["within_margins"] and all(y["stick_across_shift_max_mm"] < 0.55 for y in tol["yaw"]["parts"])
    # only the front (tight) leg holds the turn: the front platform's 88 mm tab span, the back's 178
    assert [y["outer_tab_span_mm"] for y in tol["yaw"]["parts"]] == [88.0, 178.0]
    assert tol["play"] == {"key_mm": 0.25, "balm_in_hole_mm": 0.5, "lipstick_in_hole_mm": 0.5, "slot_insert_mm": 0.25,
                           "palettes_across_slot_mm": 2.0, "fold_each_mm": 2.25, "row_total_mm": 0.75}
    assert all(s["min_visible_fraction"] == 1.0 for s in tol["sticks"]) and tol["lid_min_visible_fraction"] == 1.0
    apart = tol["margins"]["rows_apart_across"]
    assert [m["limit_mm"] for m in apart] == [1.3, 1.72] and [m["margin_mm"] for m in apart] == [0.55, 0.97]
    assert apart[0]["worst"]["first_to_fail"] == ["lipstick 6"] and apart[1]["worst"]["first_to_fail"] == ["lipstick 1"]
    # the worst corner is now the back row at its fold's allowance behind (2.25 back), the front row forward
    assert apart[0]["worst"]["front_row"] == "forward" and apart[0]["worst"]["back_row"] == "back"
    # the reviewer's own readings (1.47 one way, 1.86 the other) are the both-rows-forward corner, which a fold never
    # moves (a fold only adds depth behind a keyed leg)
    ff = [next(t for t in m["tried"] if t["front_row"] == t["back_row"] == "forward") for m in apart]
    assert [t["limit_mm"] for t in ff] == [1.47, 1.86]
    assert tol["margins"]["least_margin_mm"] == 0.55
    assert all(m["limit_mm"] is None for m in tol["margins"]["rows_in_depth"])          # none lost to 8 mm


def test_a_front_wall_raised_to_120_mm_fails_the_sightline():
    rec = C.solve(provisional={"front_wall_mm": 120.0})
    sl = C.sightlines(rec, max_raise_mm=2)
    assert not sl["passed"]
    balms = [s for s in sl["result"]["sticks"] if s["item"].startswith("balm")]
    assert all(not s["pass"] and "front wall" in s["limiting_occluders"] for s in balms)
    assert sl["remedy"]["found"] is None


# --- the sheets -------------------------------------------------------------------------------------------------------


# --- the reference mapping and the record on disk ---------------------------------------------------------------------

def test_the_reference_mapping_maps_every_es3083_crease():
    m = json.loads((OUT / "reference-mapping.json").read_text(encoding="utf-8"))
    assert m["schema"] == "reference_mapping/1.0"
    assert m["source"]["sha256"] == C.REFERENCE_SHA256 and m["source"]["tier"] == "NOT_IN_TIER_RECORD"
    assert m["source"]["use"] == "measured only, never placed"
    found = {c["id"] for c in m["creases_found"]}
    mapped = {i for r in m["rows"] for i in r["crease_ids"]}
    assert len(found) == 29 and found == mapped
    comp = m["completeness"]
    assert comp["creases_found"] == comp["creases_mapped"] == 29 and comp["creases_unmapped"] == []
    assert comp["cut_paths_found"] == comp["cut_paths_assigned"] == 124 and comp["cut_groups_as_expected"]
    assert comp["panel_instances_read"] == comp["tray_faces_drawn"]
    assert all(h["ok"] for h in m["house_values_checked"])
    assert "43.00 / 35.00 / 50.00 / 35.00 / 33.50" in m["correction"]
    for r in m["rows"]:
        assert set(r) >= {"es3083_part", "kind", "measured_mm", "our_part", "resolved_mm", "rule", "note"}


def test_the_reference_mapping_measures_what_was_typed_before():
    """MINOR 6: the side liner, the relief arcs and the lock head are measured from the walk, not typed."""
    m = json.loads((OUT / "reference-mapping.json").read_text(encoding="utf-8"))
    rows = {r["es3083_part"].split(" (")[0].split(",")[0]: r for r in m["rows"]}
    liner = next(r for r in m["rows"] if r["es3083_part"].startswith("side liners (2)"))
    assert liner["measured_mm"] == [1.96, -1.84] and liner["resolved_mm"] == [2.0, 2.0]
    arcs = next(r for r in m["rows"] if r["es3083_part"].startswith("front corner relief arcs"))
    assert arcs["measured_mm"] == 2.0 == C.HOUSE["relief_arc_radius_mm"][0]
    checked = {h["house"]: h for h in m["house_values_checked"]}
    for k in ("lock_head_at_mm", "lock_head_mm", "relief_arc_radius_mm", "lock_shoulder_curve_w_mm",
              "lock_shoulder_curve_h_mm", "side_liner_short_front_mm", "side_liner_short_back_mm"):
        assert checked[k]["ok"] and checked[k]["walk"] == C.HOUSE[k][0], k
    assert len(checked) == len(C.HOUSE_FROM_WALK) == 45 and rows


def test_builder_choices_carry_their_values_and_are_labelled_as_builders(record):
    """MINOR 3: no builder value labelled solved, no builder fact with a null value."""
    bp = record["builder_provisional"]
    assert all(f["value"] is not None and f["authority"] == C.BUILDER for f in bp.values())
    assert bp["backrest_mm"]["value"] == 60.0 and bp["glue_flap_mm"]["value"] == 12.0
    assert bp["minimum_web_mm"]["value"] == 4.5 and bp["platform_gap_mm"]["value"] == 5.5
    assert bp["fold_allowance_mm"]["value"]["leg_spacing_mm"] == [0.0, 4.5]
    assert bp["fold_allowance_mm"]["value"]["each_fold_mm"] == [0.0, 2.25]
    # Day 13, D-D13-2: one fold 2.25 + the key 0.25 + the closed tube's lean 4.4316 (was 2.5)
    assert bp["insert_set_forward_mm"]["value"] == 6.9316
    assert bp["insert_gusset_mm"]["value"] == {"up_the_back_leg_mm": 60.0, "along_the_base_mm": 30.0,
                                               "glue_flap_mm": 12.0, "per_end": 1, "printed": False}
    assert bp["liner_tab_height_mm"]["value"] == 2.0 + 1.5                # the liner's short + the board
    assert bp["lock_slot_rule"]["value"]["slot_minus_tab_mm"] == 0.5
    panels = record["slot"]["insert_panels_mm"]
    # Day 13, D-D13-2: the gussets' three sizes are the builder's too
    assert {k for k, f in panels.items() if f["authority"] == C.BUILDER} == {
        "backrest_mm", "glue_flap_mm", "wing_mm", "gusset_up_mm", "gusset_along_mm", "gusset_flap_mm"}
    assert panels["bed_mm"]["authority"] == C.OWNER
    assert record["platforms"]["gap_between_mm"]["authority"] == C.BUILDER

    def solved_quoting_a_builder(node):
        if isinstance(node, dict):
            if node.get("authority") == C.SOLVED and node.get("source") in C.BUILDER_CHOICES.values():
                yield node
            for v in node.values():
                yield from solved_quoting_a_builder(v)
        elif isinstance(node, list):
            for v in node:
                yield from solved_quoting_a_builder(v)
    assert not list(solved_quoting_a_builder(record))
    ids = {d["id"] for d in record["departures"]}
    assert {"floor_keys", "die_face", "lock_shoulder_curves", "side_liner_edge", "relief_arcs", "insert_allowances",
            "insert_glue_flap", "insert_print_side_in", "die_words_layer", "insert_sway", "liner_tabs_flush"} <= ids
    # MINOR 4: the front plate's place is the builder's rows_forward, labelled so
    y0 = record["platforms"]["front"]["plate_y_mm"][0]
    assert y0["authority"] == C.BUILDER and y0["source"] == C.BUILDER_CHOICES["rows_forward"] and y0["value"] == 7.0


def test_two_solves_give_identical_die_json_bytes_and_match_the_record_on_disk():
    a, b = C.record_bytes(C.full_record()), C.record_bytes(C.full_record())
    assert a == b
    assert (OUT / "die.json").read_bytes() == a


def test_square_hole_parameter_is_optional_and_preserved_on_record_rebuild():
    assert C.record_bytes(C.full_record(hole_shape='circle')) == (OUT / 'die.json').read_bytes()
    record = C.solve(hole_shape='square')
    assert all(row['shape'] == 'square' and 'side_mm' in row and 'diameter_mm' not in row for row in record['holes'])
    die = C.build_die(record)
    assert {part.hole_shape for part in die.parts if part.holes} == {'square'}
    assert C.fold_check(record, die)['passed']
    with pytest.raises(ValueError, match='circle or square'):
        C.solve(hole_shape='rounded_guess')


def _product_grid_fixture(rows=3, columns=4):
    return {'product_width_mm': 15.0, 'product_depth_mm': 15.0, 'product_height_mm': 100.0,
            'rows': rows, 'columns': columns, 'count': rows * columns, 'width_mm': 110.0,
            'depth_mm': 85.0, 'height_mm': 160.0, 'header_height_mm': 53.5,
            'front_height_mm': 20.0, 'board_mm': 1.5, 'clearance_mm': 0.5,
            'hole_shape': 'square', 'top_edge': 'square'}


@pytest.mark.parametrize('rows,columns', [(1, 1), (2, 3), (3, 4)])
def test_single_product_tray_solves_actual_count_and_square_15_5_mm_openings(rows, columns):
    record = C.solve(product_grid=_product_grid_fixture(rows, columns))
    assert 'palette' not in str(record) and 'balm' not in str(record) and 'lipstick' not in str(record)
    assert record['layout'] == {'rows': rows, 'columns': columns, 'count': rows * columns}
    assert len(record['holes']) == rows * columns and {hole['size_mm'] for hole in record['holes']} == {15.5}
    die = C.build_die(record)
    fold = C.fold_check(record, die)
    assert fold['passed'], fold['failed']
    assert fold['closed_mm'] == [110.0, 85.0, 160.0]
    assert record['top_edge'] == 'square'
    front = C._face(next(part for part in die.parts if part.name == 'tray'), 'header front')
    assert len(front.exterior.coords) == 5 and front.equals(C._rect(*front.bounds))
    holder = next(part for part in die.parts if part.name == 'holder')
    assert holder.hole_cut_length() == rows * columns * 62


def test_single_product_fold_check_reads_the_drawn_holes_and_header():
    from shapely import affinity
    record = C.solve(product_grid=_product_grid_fixture())
    die = C.build_die(record)
    holder = next(part for part in die.parts if part.name == 'holder')
    name, centre, half = holder.holes[0]
    holder.holes[0] = (name, centre, half + 0.5)
    assert 'opening_clearance_mm' in C.fold_check(record, die)['failed']
    holder.holes[0] = (name, (0, 0), half)
    assert 'opening_edge_margin_mm' in C.fold_check(record, die)['failed']
    die = C.build_die(record)
    tray = next(part for part in die.parts if part.name == 'tray')
    tray.faces = [(name, affinity.scale(face, yfact=1.1, origin='center') if name == 'header front' else face, printed)
                  for name, face, printed in tray.faces]
    assert 'closed_height_mm' in C.fold_check(record, die)['failed']


def test_single_product_sightline_reports_covered_back_rows_without_raising_them():
    record = C.solve(product_grid=_product_grid_fixture())
    before = C.record_bytes(record)
    result = C.sightlines(record)
    assert not result['passed'] and not result['design_gate'] and not result['seats_changed']
    assert len(result['products']) == 12 and all(row['seat_z_mm'] == 1.5 for row in result['products'])
    assert any(row['occluders'] for row in result['products'] if row['row'] > 1)
    assert C.record_bytes(record) == before


def test_round_files_stand_adapter_uses_vision_count_and_engine_surfaces(tmp_path):
    from apps.pipeline.services.round_files_stand import build_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    inspection = {'image_size_px': [1536, 1024], 'stand': {'rows': 2, 'columns': 3, 'count': 6},
                  'panels': {'stand_header': {'crop_px': [100, 100, 500, 300]},
                             'stand_base': {'crop_px': [100, 500, 500, 560]}}}
    result = build_stand(gloss_brief(), inspection, tmp_path)
    assert result['count'] == 6 and result['valid'] and result['provisional']
    assert result['surfaces']['stand_header']['size_mm'] == [107.0, 53.5]
    assert result['surfaces']['stand_base']['size_mm'][1] == pytest.approx(16.05)
    assert result['die']['cut'] and result['die']['fold'] and result['guides']['safe']
    front = result['front_elevation']
    assert front['height_mm'] == 160 and front['header_box_mm'][3] == 53.5
    assert len(front['product_slots']) == 6 and {slot['row'] for slot in front['product_slots']} == {1, 2}
    assert json.loads((tmp_path / 'stand-fold-check.json').read_text())['passed']
    assert json.loads((tmp_path / 'stand-sightlines.json').read_text())['design_gate'] is False


def test_single_product_tray_refuses_malformed_count_and_reports_a_tight_grid():
    with pytest.raises(ValueError, match='rows times columns'):
        C.solve(product_grid=dict(_product_grid_fixture(), count=11))
    with pytest.raises(ValueError, match='finite positive'):
        C.solve(product_grid=dict(_product_grid_fixture(), product_width_mm=float('nan')))
    record = C.solve(product_grid=dict(_product_grid_fixture(), width_mm=60.0))
    assert not C.fold_check(record)['passed']


def test_round_files_stand_grows_provisional_brief_for_fourteen_observed_bottles():
    from apps.pipeline.services.round_files_stand import solve_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    brief = gloss_brief()
    assert brief['stand']['count'] == 12 and brief['stand']['dimensions_mm']['width'] == 110
    inspection = {'stand': {'rows': 2, 'columns': 7, 'count': 14},
                  'panels': {'stand_header': {'crop_px': [100, 100, 500, 300]},
                             'stand_base': {'crop_px': [100, 500, 500, 560]}}}
    result = solve_stand(brief, inspection)
    assert result['valid'] and result['count'] == len(result['record']['holes']) == 14
    assert result['dimensions_mm']['width'] == 150.5
    assert all(hole['shape'] == 'square' and hole['size_mm'] == 15.5 for hole in result['record']['holes'])
    assert result['dimension_adjustments'] == [{'dimension': 'width', 'from_mm': 110.0, 'to_mm': 150.5,
        'reason': 'Fit the observed count with product clearance and three-board webs'}]
    assert brief['stand']['dimensions_mm']['width'] == 110
    brief['stand']['provisional'] = False
    fixed = solve_stand(brief, inspection)
    assert not fixed['valid'] and fixed['dimensions_mm']['width'] == 110 and not fixed['dimension_adjustments']


def _observed_row_fixture():
    return {'image_size_px': [800, 800], 'stand': {'rows': 2, 'columns': 3, 'count': 6,
        'bottles': [{'row': row, 'column': column,
                     'box_px': [100 + 30*column, 200 if row == 0 else 184,
                                120 + 30*column, 600 if row == 0 else 204]}
                    for row in range(2) for column in range(3)]},
        'panels': {'stand_header': {'crop_px': [80, 100, 220, 184]},
                   'stand_base': {'crop_px': [80, 612, 220, 642]}}}


def test_single_product_raised_seat_report_measures_the_drawn_support_and_collar():
    from shapely import affinity
    record = C.solve(product_grid=dict(_product_grid_fixture(2, 3), row_seat_z_mm=[22., 27.]))
    die = C.build_die(record)
    seat = next(part for part in die.parts if part.name == 'seat row 2')
    seat.faces = [(name, affinity.scale(face, yfact=1.1, origin='center') if name == 'front wall' else face, printed)
                  for name, face, printed in seat.faces]
    assert 'row_2:seat_height_mm' in C.fold_check(record, die)['failed']
    die = C.build_die(record)
    collar = next(part for part in die.parts if part.name == 'holder row 1')
    collar.faces = [(name, affinity.scale(face, xfact=2, origin='center') if name == 'left leg' else face, printed)
                    for name, face, printed in collar.faces]
    assert 'row_1:collar_height_mm' in C.fold_check(record, die)['failed']
    die = C.build_die(record)
    collar = next(part for part in die.parts if part.name == 'holder row 1')
    name, centre, half = collar.holes[1]
    collar.holes[1] = name, (centre[0] + .1, centre[1]), half
    assert 'opening_positions:holder row 1' in C.fold_check(record, die)['failed']


@pytest.mark.parametrize('product_height', [80, 100, 120])
def test_round_files_stand_measures_row_rises_front_clearance_and_header_gap(product_height):
    from apps.pipeline.services.round_files_stand import solve_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    brief, inspection = gloss_brief(), _observed_row_fixture()
    brief['dimensions_mm']['height'] = product_height
    before = json.dumps(inspection, sort_keys=True)
    result = solve_stand(brief, inspection)
    assert result['valid'], result['fold_check']['failed']
    placement = result['observed_row_placement']
    assert placement['applied'] and placement['provisional']
    assert placement['front_clearance_above_base_mm'] == pytest.approx(12 / 400 * product_height)
    seats = placement['row_seat_z_mm']
    assert seats[1] - seats[0] == pytest.approx(16 / 400 * product_height)
    assert len(result['record']['holes']) == 6
    elevation = result['front_elevation']
    front, rear = elevation['product_slots'][0], elevation['product_slots'][3]
    assert elevation['base_box_mm'][1] - front['box_mm'][3] == pytest.approx(12 / 400 * product_height, abs=.001)
    assert front['box_mm'][1] - rear['box_mm'][1] == pytest.approx(16 / 400 * product_height, abs=.001)
    assert rear['box_mm'][1] == pytest.approx(elevation['header_box_mm'][3], abs=.001)
    platforms = elevation['platform_fronts']
    assert len(platforms) == 12 and len({face['id'] for face in platforms}) == 12
    for measured in result['fold_check']['measured_row_platforms']:
        row_faces = {face['kind']: face for face in platforms if face['row'] == measured['row']}
        slot = next(slot for slot in elevation['product_slots'] if slot['row'] == measured['row'])
        support, collar = row_faces['support_front'], row_faces['collar_front_edge']
        assert support['part'] == measured['support_part'] and collar['part'] == measured['collar_part']
        assert support['box_mm'][1] == pytest.approx(elevation['height_mm'] - measured['seat_z_mm'])
        assert collar['box_mm'][1] == pytest.approx(elevation['height_mm'] - measured['collar_top_z_mm'])
        assert collar['box_mm'][3] - collar['box_mm'][1] == pytest.approx(1.5)
        assert all(face['depth_mm'] < slot['depth_mm'] for face in row_faces.values())
        assert all(not face['printed'] and face['material'] == 'unprinted board' for face in row_faces.values())
        assert all(0 <= face['box_mm'][0] < face['box_mm'][2] <= elevation['width_mm']
                   and 0 <= face['box_mm'][1] < face['box_mm'][3] <= elevation['height_mm'] for face in row_faces.values())
    assert result['sightlines']['includes_measured_row_supports']
    assert not result['sightlines']['seats_changed'] and not result['sightlines']['design_gate']
    assert all(row['front_elevation_exposed_top_mm'] == pytest.approx(16 / 400 * product_height, abs=.001)
               for row in result['sightlines']['products'] if row['row'] == 2)
    assert json.dumps(inspection, sort_keys=True) == before


@pytest.mark.parametrize('missing', ['bottle', 'base', 'full_front', 'consistent_cap_tops'])
def test_round_files_stand_reports_insufficient_seat_evidence_without_inventing_rises(missing):
    from apps.pipeline.services.round_files_stand import solve_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    inspection = _observed_row_fixture()
    if missing == 'bottle':
        inspection['stand']['bottles'].pop()
    elif missing == 'base':
        inspection['panels']['stand_base'].pop('crop_px')
    elif missing == 'full_front':
        inspection['stand']['bottles'][0]['box_px'][3] = 620
    else:
        inspection['stand']['bottles'][3]['box_px'][1] = 202
    result = solve_stand(gloss_brief(), inspection)
    assert not result['observed_row_placement']['applied']
    assert result['observed_row_placement']['reason']
    assert 'row_platforms' not in result['record']['geometry']
    assert result['front_elevation']['platform_fronts'] == []
    assert all(hole['seat_z_mm'] == 1.5 for hole in result['record']['holes'])


@pytest.mark.parametrize('columns', [3, 7])
def test_round_files_stand_enclosure_preserves_observed_cap_band_at_actual_scale(columns):
    from apps.pipeline.services.round_files_stand import solve_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    # The observed 484-pixel full bottle and 22-pixel cap step are intentionally
    # retained; translating the source crop and varying the count cannot change
    # their physical ratio or create a taller rear row merely for visibility.
    span = columns * 90 + 42
    inspection = {'image_size_px': [1200, 900], 'stand': {'rows': 2, 'columns': columns, 'count': 2 * columns,
        'bottles': [{'row': row, 'column': column, 'box_px': [100 + column * 90,
            112 if row == 0 else 90, 182 + column * 90, 596 if row == 0 else 116]}
            for row in range(2) for column in range(columns)]},
        'panels': {'stand_header': {'crop_px': [80, 10, 80 + span, 90]},
                   'stand_base': {'crop_px': [80, 609, 80 + span, 687]}}}
    before = json.dumps(inspection, sort_keys=True)
    brief = gloss_brief()
    original = solve_stand(brief, inspection)
    result = solve_stand(brief, inspection, include_enclosure=True)
    assert result['valid'] and result['record'] == original['record']
    for key in ('die', 'fold_check', 'sightlines', 'dimensions_mm', 'observed_row_placement'):
        assert result[key] == original[key]
    assert 'enclosure_faces' not in original['front_elevation'] and 'side_elevation' not in original
    front = result['front_elevation']
    first, rear = front['product_slots'][0], front['product_slots'][columns]
    step = first['box_mm'][1] - rear['box_mm'][1]
    assert step == pytest.approx(22 / 484 * 100, abs=.001)
    assert step * 6 > 27  # The current mechanical proof has a resolvable 27-pixel band.
    assert rear['box_mm'][1] == pytest.approx(front['header_box_mm'][3], abs=.001)
    faces = {face['kind']: face for face in front['enclosure_faces']}
    back = faces['back_interior']
    assert back['depth_mm'] > max(slot['depth_mm'] for slot in front['product_slots'])
    assert back['box_mm'][1] == front['header_box_mm'][3]
    assert back['box_mm'][3] == front['base_box_mm'][3]
    for kind in ('left_side_edge', 'right_side_edge'):
        face = faces[kind]
        assert face['box_mm'][2] - face['box_mm'][0] == pytest.approx(1.5)
        assert face['projection'] == 'board-thickness orthographic silhouette'
    side = result['side_elevation']
    assert side['front_wall_top_mm'] > side['back_wall_top_mm']
    assert side['back_wall_top_mm'] == pytest.approx(front['header_box_mm'][3])
    assert side['front_wall_top_mm'] == pytest.approx(front['base_box_mm'][1])
    assert {face['face'] for face in result['enclosure_surfaces']} == {'back panel', 'left side', 'right side', 'floor'}
    assert all(face['material'] is None for face in result['enclosure_surfaces'])
    assert json.dumps(inspection, sort_keys=True) == before


def test_round_files_stand_rounds_provisional_minimum_above_float_cancellation():
    from apps.pipeline.services.round_files_stand import solve_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    brief = gloss_brief()
    inspection = {'stand': {'rows': 3, 'columns': 4, 'count': 12},
                  'panels': {'stand_header': {'crop_px': [100, 20, 180, 115]},
                             'stand_base': {'crop_px': [100, 120, 180, 144]}}}
    result = solve_stand(brief, inspection, include_enclosure=True)
    assert result['valid'], result['fold_check']['failed']
    geometry = result['record']['geometry']
    assert geometry['header_height_mm'] == 127.0625
    assert geometry['front_panel_height_mm'] == 32.1
    assert geometry['back_panel_height_mm'] >= geometry['front_panel_height_mm']
    assert 0 < result['dimensions_mm']['height'] - 160.6625 < 1e-10
    assert result['dimension_adjustments'][-1]['dimension'] == 'height'
    brief['stand']['provisional'] = False
    with pytest.raises(ValueError, match='no usable floor, walls or header'):
        solve_stand(brief, inspection, include_enclosure=True)


@pytest.mark.parametrize('columns', [3, 7])
def test_round_files_stand_opt_in_raises_real_rear_supports_until_top_band_passes(columns):
    from apps.pipeline.services.round_files_stand import solve_stand
    from apps.pipeline.services.round_ideas_brief import gloss_brief
    inspection = _observed_row_fixture()
    inspection['stand'] = {'rows': 2, 'columns': columns, 'count': 2 * columns,
        'bottles': [{'row': row, 'column': column, 'box_px': [100 + column * 30,
                    200 if row == 0 else 178, 120 + column * 30, 684 if row == 0 else 204]}
                    for row in range(2) for column in range(columns)]}
    inspection['panels'] = {'stand_header': {'crop_px': [80, 80, 300, 178]},
                            'stand_base': {'crop_px': [80, 697, 300, 725]}}
    baseline = solve_stand(gloss_brief(), inspection, include_enclosure=True)
    result = solve_stand(gloss_brief(), inspection, include_enclosure=True, rear_visibility=True)
    adjustment = result['rear_visibility_adjustment']
    assert not baseline['sightlines']['passed'] and result['sightlines']['passed']
    assert result['sightlines']['visible_band_mm'] == 25
    assert result['sightlines']['eye_mm'] == baseline['sightlines']['eye_mm']
    assert all(row['visible_samples'] == row['samples'] == 26 for row in result['sightlines']['products'])
    assert adjustment['added_rise_mm'][0] == 0 and adjustment['added_rise_mm'][1] > 0
    assert result['dimensions_mm']['height'] - baseline['dimensions_mm']['height'] == pytest.approx(adjustment['added_rise_mm'][1])
    assert result['valid'] and len(result['record']['holes']) == 2 * columns
    assert result['fold_check']['measured_row_platforms'][1]['seat_z_mm'] == pytest.approx(adjustment['final_seats_mm'][1])
    assert result['die'] != baseline['die']
    assert solve_stand(gloss_brief(), inspection, include_enclosure=True) == baseline


def test_the_template_is_declared_provisional_and_never_production():
    defn = C.template_definition()
    assert defn.template_id == "counter_tray_header" and defn.version == "0.1"
    assert defn.provisional is True and defn.production_ready is False
    assert defn.geometry_module == "apps.dielines.geometry.counter_tray_header"
    assert any("D-D12-2" in note for note in defn.notes)


# --- the final pass (D-D12-8: no loop): the two verifiers' findings after the second fix ------------------------------

def test_the_slot_insert_sway_is_closed_by_its_gussets_and_the_2_mm_holds_at_every_lean(record, die):
    """Day 13, D-D13-2: the departure Day 12 named (a four-bar keyed at one foot) is closed by a glued diagonal gusset at
    each end: the back leg held square on the base, the tube leans only as its fit lets it (the base's two folds: the
    back leg 0 … 4.50 behind, ±3.85° of front-leg lean), and stack_rear_vs_back_wall is proven at every lean in that
    range, every 0.01°: at least 4.50 at the drawn seat and 2.00 at the rearmost. With the gussets left off the same
    tube still sways onto the back (the control)."""
    fc = C.fold_check(record, die)
    sw = fc["racking"]["slot_insert"]
    assert sw["status"] == "closed (D-D13-2)" and sw["choice"]["chosen"] == "a glued diagonal gusset at each end"
    assert sw["panels_from"] == "the drawn die's faces" and set(sw["closure_mm"].values()) == {0.0}
    assert sw["panels_mm"] == {"front leg": 67.765, "bed": 30.0, "backrest": 60.0, "back leg": 117.956,
                               "base": 43.007}
    assert [x["side"] for x in sw["gussets"]] == ["L", "R"]
    assert all(x["present"] and x["closes"] and x["corner_square"] and x["printed"] is False for x in sw["gussets"])
    lp = sw["lean_permitted"]
    assert lp["front_leg_lean_deg"] == [-3.85, 3.85] and lp["back_leg_moves_mm"] == 4.5
    proof = sw["proof"]
    assert proof["step_deg"] == 0.01 and proof["samples"] >= 2 * 3.85 / 0.01
    drawn, rear = proof["seats"]
    assert (drawn["least_clearance_mm"], rear["behind_drawn_mm"], rear["least_clearance_mm"]) == (4.5, 2.5, 2.0)
    assert all(s["house_clearance_kept"] and s["least_clearance_mm"] >= sw["house_clearance_mm"] == 2.0
               for s in (drawn, rear))
    assert proof["every_fold_corner"]["kept"] and proof["every_fold_corner"]["least_clearance_mm"] >= 2.0
    assert proof["set_forward_mm"]["total"] == 6.932
    # the control: the four-bar without its gussets touches the back at either seat
    four = sw["without_the_gussets"]
    assert all(s["stack_rear_vs_back_wall_mm"] == 0.0 for s in four["seats"])
    assert sw["choice"]["keys_at_both_feet"]["key_binds_at_deg"] == four["key_tab_binds_at_deg"] == 25.53
    stack = next(x for x in fc["findings"] if x["id"] == "stack_rear_vs_back_wall")
    assert stack["ok"] and stack["measured"] == 2.0 and "every lean" in stack["rule"]
    assert all(next(x for x in fc["findings"] if x["id"] == "insert_gusset:" + side)["ok"] for side in "LR")
    dep = {d["id"]: d for d in record["departures"]}
    assert dep["insert_sway"]["status"] == "closed — D-D13-2" and "platform_racking" in dep
    # re-read off the frame itself: drawn, it is the drawn tube; over every lean the corner moves back at most the
    # set-forward's lean reserve
    g = C._g_from_record(record)
    link = C.insert_linkage(g)
    p0 = C.frame_pose(link, 0.0)
    assert math.dist(p0["A"], link["A0"]) < 1e-9 and math.dist(p0["C"], link["C0"]) < 1e-9
    worst = max(C.frame_pose(link, a)["move"](link["K0"])[0] - link["K0"][0] for a in C.frame_leans(3.8549))
    assert worst <= proof["set_forward_mm"]["lean"] + 1e-3


def test_the_slot_insert_carries_its_gussets_on_the_drawn_die_and_in_its_files(die):
    """Day 13, D-D13-2: the closing is drawn, not only computed — the slot insert's two gussets and their glue flaps
    are faces of the drawn part, unprinted, hinged by creases on the back leg's side edges; the die's SVG carries their
    four creases and six cut edges over Day 12's die (both read from the files)."""
    ins = next(p for p in die.parts if p.name == "slot insert")
    faces = {n: printed for n, _poly, printed in ins.faces}
    creases = {n for n, _line in ins.creases}
    for side in "LR":
        assert faces["gusset " + side] is False and faces["gusset flap " + side] is False
        assert {"back leg / gusset " + side, "gusset / gusset flap " + side} <= creases

    def layer_counts(path):
        svg = path.read_text()
        out = {}
        for label in ("CUT", "CREASE"):
            at = svg.index('inkscape:label="%s"' % label)
            out[label] = len(re.findall(r"<(?:path|line|polyline|polygon)\b", svg[at:svg.index("</g>", at)]))
        return out
    day12 = OUT.parents[2] / "day-12" / "display" / "die" / "die.svg"
    now, before = layer_counts(OUT / "die.svg"), layer_counts(day12)
    assert now["CREASE"] - before["CREASE"] == 4 and now["CUT"] - before["CUT"] == 6


def test_the_template_is_registered_provisional_and_never_offered(record):
    """Day 13, D-D13-3: registered at 0.1 ⟪PROVISIONAL⟫ beside the TemplateType member the agreement test pins; never
    production — no production or new-task chooser offers it and the carton input schema refuses it — and the die's
    own record says so."""
    from pydantic import ValidationError

    from apps.dielines import registry
    from apps.dielines.models import TemplateType
    from apps.dielines.validators.schema import DielineInputJSON
    defn = registry.resolve("counter_tray_header")
    assert defn.key == "counter_tray_header/0.1" and defn is C.template_definition()
    assert defn.provisional is True and defn.production_ready is False
    assert defn.ineligibility_code == "PHYSICAL_SAMPLE_VALIDATION_REQUIRED"
    assert "counter_tray_header" in TemplateType.values
    assert "counter_tray_header" not in {d.template_id for d in registry.production_templates()}
    assert "counter_tray_header" not in {d["template_id"] for d in registry.new_selection_templates()}
    with pytest.raises(ValidationError):
        DielineInputJSON(template="counter_tray_header", unit="mm",
                         dimensions={"width_mm": 250.0, "depth_mm": 160.0, "height_mm": 183.62})
    t = record["template"]
    assert t["registered"] is True and t["version"] == "0.1" and t["status"] == "0.1 ⟪PROVISIONAL⟫ — never production"


def test_a_planted_looser_fit_or_panel_moves_the_proof(record, die):
    """Day 13, D-D13-2, planted controls: (1) the old full-footprint base (1.5 longer) — the panels are read off the die,
    so the closure shows it; (2) a looser fit (each fold 0.50 more than its allowance) lets the frame lean further than
    the insert's set-forward takes, and the rearmost seat's 2.00 fails."""
    g = C._g_from_record(record)
    old = C._insert(dict(g, insert=dict(g["insert"], base_mm=g["insert"]["base_mm"] + 1.5)))
    i = next(n for n, q in enumerate(die.parts) if q.name == "slot insert")
    planted = C.Die(list(die.parts), die.sheet_w, die.sheet_h, die.labels, die.bar, die.title)
    b0, b1 = die.parts[i].outline().bounds, old.outline().bounds
    planted.parts[i] = old.moved(b0[0] - b1[0], b0[1] - b1[1])
    sw = C.insert_sway(g, planted)
    assert sw["closure_mm"]["base_front_crease_vs_front_leg_inner_face"] == -1.5
    loose = C.insert_sway(dict(g, fold_each=g["fold_each"] + 0.5), die)
    assert loose["lean_permitted"]["front_leg_lean_deg"][1] > 3.85
    assert loose["proof"]["seats"][1]["house_clearance_kept"] is False
    assert loose["proof"]["seats"][1]["least_clearance_mm"] < 2.0


def test_the_sightline_holds_at_the_insert_lean_limits(sight):
    """Day 13, D-D13-2: recorded at each seat with the closed tube leaned to each end of the lean its fit permits, the
    palettes across the slot at each end of their play and centred: every stick's top 25 mm and the lid above the
    sticks' tops visible (the owner's pass); the whole lid's least share recorded beside it.
    D-D14-6 accepts the measured whole-lid 0.9841 for this prototype; the existing >= 0.98 bar and the
    above-stick 1.0 bar stay unchanged. No geometry or other threshold changes under that ruling."""
    sw = sight["insert_sway"]
    assert sw["passed"] and len(sw["poses"]) == 12 and sight["passed"]
    assert sw["lid_min_visible_fraction"] == 1.0 and sw["whole_lid_min_visible_fraction"] >= 0.98
    assert sw["whole_lid_min_visible_fraction"] == pytest.approx(0.9841, abs=0.00005)  # D-D14-6, accepted prototype
    assert {(p["seat"], p["front_leg_lean_deg"]) for p in sw["poses"]} == {
        ("drawn", -3.85), ("drawn", 3.85), ("rearmost", -3.85), ("rearmost", 3.85)}
    assert all(p["sticks_passing"] == p["sticks"] == 12 for p in sw["poses"])


def test_the_leaned_scene_moves_the_stack_by_the_frame(record):
    """Day 13, D-D13-2: the sightline's scene with the closed tube leaned: the palettes and the bed move by the frame
    (not by a translation) — back at a lean back, forward at a lean forward, turned by the frame's small stack turn."""
    g = C._g_from_record(record)
    P0, back, fwd = C._pose(None), C._pose({"insert_lean_deg": 3.85}), C._pose({"insert_lean_deg": -3.85})
    a, b, c = C._insert_place(g, P0), C._insert_place(g, back), C._insert_place(g, fwd)
    assert a["leg"] is None and b["leg"] is not None and c["leg"] is not None
    assert 4.0 < b["p0"][0] - a["p0"][0] < 4.6 and -4.6 < c["p0"][0] - a["p0"][0] < -4.0
    assert b["u"] != a["u"] and abs(b["u"][0] - a["u"][0]) < 0.01            # turned, by well under a degree


def test_the_wall_tabs_stop_flush_with_the_underside_and_the_old_5_mm_is_caught(record, die):
    """The geometry verifier's minor: the six liner tabs (ES3083's 5.00) reached 1.50 below the tray's underside.
    Now liner short + board = 3.50: every liner tab's tip, read off the drawn die and folded, at z 0.000; the lock
    tabs far above. Planted control: the house's 5.00 fails all six, at z −1.50 — and the two dies' printed faces,
    sheet and labels are the same (only the six unprinted tabs differ)."""
    fc = C.fold_check(record, die)
    tips = {f["id"].split(":")[1]: f for f in fc["findings"] if f["id"].startswith("tab_tip_vs_underside:")}
    assert len(tips) == 8 and all(f["ok"] for f in tips.values())
    liners = [k for k in tips if "liner" in k]
    assert len(liners) == 6 and all(tips[k]["measured"]["tip_z_mm"] == 0.0 for k in liners)
    assert all(tips[k]["measured"]["tip_z_mm"] > 70.0 for k in tips if "lock" in k)
    g = C._g_from_record(record)
    old = C.build_die(dict(g, liner_tab_h=5.0))
    fc_old = C.fold_check(record, old)
    assert sorted(f for f in fc_old["failed"]) == sorted("tab_tip_vs_underside:" + k for k in liners)
    assert all(f["measured"]["tip_z_mm"] == -1.5 for f in fc_old["findings"]
               if f["id"].startswith("tab_tip_vs_underside:") and "liner" in f["id"])
    assert (old.sheet_w, old.sheet_h, old.labels) == (die.sheet_w, die.sheet_h, die.labels)
    for p, q in zip(die.parts, old.parts):
        assert p.outline().bounds == q.outline().bounds
        for (n, f, pr), (n2, f2, pr2) in zip(p.faces, q.faces):
            assert n == n2 and (f.equals_exact(f2, 1e-12) or (not pr and "liner tab" in n)), n
    assert "liner_tabs_flush" in {d["id"] for d in record["departures"]}


def test_the_reference_mapping_reconciles_the_largest_panel():
    """The sheet verifier's minor: the findings doc's 'largest panel 275 × 197' is the doubled header, not a panel."""
    m = json.loads((OUT / "reference-mapping.json").read_text(encoding="utf-8"))
    assert "'largest panel 275.00 × 197.00 mm'" in m["correction"]
    assert "197.00 is the doubled header, two 98.50 leaves" in m["correction"]
    assert "the floor, 275.00 × 198.00 crease to crease" in m["correction"]
    tabs = [r for r in m["rows"] if "liner lock tabs" in r["es3083_part"]]
    assert len(tabs) == 2 and all(r["measured_mm"][2] == 5.0 and r["resolved_mm"][2] == 3.5 for r in tabs)
