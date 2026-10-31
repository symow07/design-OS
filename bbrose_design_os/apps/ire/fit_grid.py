"""N units in a grid, and the tray that holds them (§BH55 Phase 2, 2026-09-19) — a counter display's tray today; the
insert a gift set holds its pieces in, next.

GEOMETRY, AND PROVISIONAL: a converter's die governs every production structure, and nothing here is one. Every number
is a PROPOSAL a person confirms at the design's gate, recorded with where it came from. What is measured is the unit (its
size, from the record it came from) and the arrangement's own arithmetic; what is chosen is said as chosen, beside it.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass

# ONE MODEL, TWO READERS: a structure not proven by a physical sample is named in the dieline registry's own words —
# its status, and the code that holds such a structure at Gate 2 ("the structure cannot pass Gate 2 while this code
# stands", apps/dielines/registry.py) — never in a new vocabulary beside it
# [§BH70(3): the code is said as INFORMATION since — "a colleague test-fits; that is not the system's job" — never a hold]
from apps.dielines.registry import (PHYSICAL_SAMPLE_INFORMATION, PHYSICAL_SAMPLE_VALIDATION_REQUIRED,
                                    STRUCTURE_PROVISIONAL)

#: CHOSEN, and said as chosen: the space around each unit in the tray; the board a counter display is folded from (a
#: single-wall E-flute is commonly about this thick); the counter tray's width-to-depth, wider than deep so its front
#: shows more of what it holds; the lip's and the back wall's heights as shares of the unit's height (the unit stands
#: and shows above the lip), never below the floors; and the header card's height as a share of the tray's width
CLEARANCE_MM = 2.0
BOARD_MM = 3.0
TRAY_ASPECT = 1.6
LIP_SHARE, LIP_FLOOR_MM = 0.30, 25.0
BACK_SHARE, BACK_FLOOR_MM = 0.60, 40.0
HEADER_SHARE, HEADER_FLOOR_MM = 0.55, 120.0
FLAP_MM = 15.0

#: the sentence the registry prints on its provisional cartons, and the converter's die that governs this one
#: [§BH70(3): kept word for word — it is the converter's note on the drawing, the registry's own sentence (ONE MODEL,
#: TWO READERS, above), and the colleague who test-fits reads it; it holds no design since]
STRUCTURE_STATE = ("PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — NOT APPROVED FOR MASS PRODUCTION. "
                   "A converter's die governs.")


@dataclass(frozen=True)
class Unit:
    """One of the things the tray holds, as it stands: its footprint and its height, with where the size came from."""
    width_mm: float
    depth_mm: float
    height_mm: float
    source: str


def arrangements(n: int, unit: Unit, *, clearance_mm: float = CLEARANCE_MM) -> list[dict]:
    """Every columns × rows that holds ``n`` units — its inner tray, and how many places it leaves empty."""
    out = []
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        inner_w_mm = cols * unit.width_mm + (cols + 1) * clearance_mm
        inner_d_mm = rows * unit.depth_mm + (rows + 1) * clearance_mm
        out.append({"columns": cols, "rows": rows, "empty_places": cols * rows - n,
                    "inner_w_mm": round(inner_w_mm, 2), "inner_d_mm": round(inner_d_mm, 2),
                    "aspect": round(inner_w_mm / inner_d_mm, 4)})
    return out


def choose(arrs: list[dict], *, target_aspect: float = TRAY_ASPECT) -> tuple[dict, list[dict]]:
    """The arrangement with the fewest empty places, then the one whose tray is nearest the target width-to-depth —
    and the three it was chosen over, so the record says what was rejected."""
    ranked = sorted(arrs, key=lambda a: (a["empty_places"], abs(math.log(a["aspect"] / target_aspect)), a["columns"]))
    return ranked[0], ranked[1:4]


def tray_for(n: int, unit: Unit) -> dict:
    """The counter tray and its header card, proposed for ``n`` units: the chosen arrangement, the alternatives it beat,
    and every dimension in millimetres with the rule that made it."""
    chosen, beaten = choose(arrangements(n, unit))
    lip_h = max(LIP_FLOOR_MM, unit.height_mm * LIP_SHARE)
    back_h = max(lip_h, BACK_FLOOR_MM, unit.height_mm * BACK_SHARE)
    outer_w = chosen["inner_w_mm"] + 2 * BOARD_MM
    outer_d = chosen["inner_d_mm"] + 2 * BOARD_MM
    header_h = max(HEADER_FLOOR_MM, outer_w * HEADER_SHARE)
    return {
        "units": n, "unit": asdict(unit), "arrangement": chosen, "alternatives": beaten,
        "chosen_by": f"fewest empty places, then the tray nearest {TRAY_ASPECT} wide to deep (CHOSEN)",
        "clearance_mm": CLEARANCE_MM, "board_mm": BOARD_MM,
        "tray": {"inner_w_mm": chosen["inner_w_mm"], "inner_d_mm": chosen["inner_d_mm"],
                 "outer_w_mm": round(outer_w, 2), "outer_d_mm": round(outer_d, 2),
                 "lip_h_mm": round(lip_h, 2), "back_h_mm": round(back_h, 2)},
        "header": {"w_mm": round(outer_w, 2), "h_mm": round(header_h, 2)},
        "rules": {"lip": f"{LIP_SHARE} of the unit's height, never below {LIP_FLOOR_MM} mm (CHOSEN)",
                  "back": f"{BACK_SHARE} of the unit's height, never below the lip or {BACK_FLOOR_MM} mm (CHOSEN)",
                  "header": f"{HEADER_SHARE} of the tray's outer width, never below {HEADER_FLOOR_MM} mm (CHOSEN)",
                  "board": f"{BOARD_MM} mm (CHOSEN — the converter's board governs)"},
        "structure_state": STRUCTURE_STATE, "structure_status": STRUCTURE_PROVISIONAL,
        # §BH70(3) (§BH70 LIVE): "A physical sample is never required to finish a design … Remove that condition from
        # Display Stand." The sample code held every stand at Gate 2; it is information now, never a hold
        "codes": [],
        "information": [{"code": PHYSICAL_SAMPLE_VALIDATION_REQUIRED, "words": PHYSICAL_SAMPLE_INFORMATION}],
    }


def blank_outline(tray: dict) -> dict:
    """The tray's flat blank, y-down, from its own dimensions: the cut outline (base, back wall, lip, the two tapered
    side walls, four glue flaps) as one closed polygon, and the folds. The base is the tray's inner footprint."""
    t = tray["tray"]
    w, d, lip, back, f = t["inner_w_mm"], t["inner_d_mm"], t["lip_h_mm"], t["back_h_mm"], FLAP_MM
    sx, sy = back, back                                    # the base's top-left: the side walls unfold to its left and right
    cut = [
        (sx, sy - back), (sx + w, sy - back),                                  # the back wall's top edge
        (sx + w + f, sy - back + f / 3), (sx + w + f, sy - f / 3), (sx + w, sy),  # its right glue flap
        (sx + w + back, sy), (sx + w + lip, sy + d), (sx + w, sy + d),         # the right side wall, tapering to the lip
        (sx + w + f, sy + d + f / 3), (sx + w + f, sy + d + lip - f / 3),      # the lip's right glue flap
        (sx + w, sy + d + lip), (sx, sy + d + lip),                            # the lip's bottom edge
        (sx - f, sy + d + lip - f / 3), (sx - f, sy + d + f / 3), (sx, sy + d),  # the lip's left glue flap
        (sx - lip, sy + d), (sx - back, sy), (sx, sy),                         # the left side wall
        (sx - f, sy - f / 3), (sx - f, sy - back + f / 3),                     # the back wall's left glue flap
    ]
    folds = [((sx, sy), (sx + w, sy)), ((sx, sy + d), (sx + w, sy + d)),    # the base's back and front edges
             ((sx, sy), (sx, sy + d)), ((sx + w, sy), (sx + w, sy + d)),    # its left and right edges
             ((sx + w, sy - back), (sx + w, sy)), ((sx, sy - back), (sx, sy)),  # the back wall's flaps
             ((sx + w, sy + d), (sx + w, sy + d + lip)), ((sx, sy + d), (sx, sy + d + lip))]  # the lip's flaps
    xs, ys = [p[0] for p in cut], [p[1] for p in cut]
    return {"cut": cut, "folds": folds, "bbox": (min(xs), min(ys), max(xs), max(ys)),
            "base": (sx, sy, w, d)}
#: CHOSEN, and said as chosen: a gift set's insert — the space around each piece, and the headroom above them under the
#: carton's closure
SET_CLEARANCE_MM = 3.0
SET_HEADROOM_MM = 8.0
#: a set the dimension gate refuses in every arrangement carries this, with each refusal in the gate's own words
SET_CARTON_REFUSED = "GIFT_SET_CARTON_REFUSED"


def insert_for(n: int, unit: Unit, refusal) -> dict:
    """A gift set's insert and the carton that holds it. Of every columns × rows that holds ``n`` pieces, the SMALLEST
    carton the dimension gate accepts — then the fewest empty places, then the insert nearest the counter's width to
    depth (CHOSEN). ``refusal(w_mm, d_mm, h_mm)`` is the gate's own answer for a carton — its words when it refuses,
    else empty — ASKED, never restated. Where the gate refuses the height the pieces need, the carton is made the least
    whole millimetre taller at which it accepts (up to the pieces' own need again) and the insert raises the pieces by
    that much. With no arrangement accepted the set is refused, each arrangement with the gate's own words."""
    need_h_mm = unit.height_mm + SET_HEADROOM_MM
    accepted, refused = [], []
    for a in arrangements(n, unit, clearance_mm=SET_CLEARANCE_MM):
        words = ""
        for h_mm in [need_h_mm] + [float(h) for h in range(math.floor(need_h_mm) + 1, math.floor(2 * need_h_mm) + 1)]:
            words = refusal(a["inner_w_mm"], a["inner_d_mm"], h_mm)
            if not words:
                accepted.append({**a, "carton_h_mm": round(h_mm, 2), "raised_mm": round(h_mm - need_h_mm, 2)})
                break
        else:
            refused.append({**a, "refusal": words})
    base = {"units": n, "unit": asdict(unit), "clearance_mm": SET_CLEARANCE_MM, "headroom_mm": SET_HEADROOM_MM,
            "refused": refused}
    if not accepted:
        return {**base, "code": SET_CARTON_REFUSED, "arrangement": None, "alternatives": [], "carton_inner": None,
                "insert": None}
    ranked = sorted(accepted, key=lambda a: (a["inner_w_mm"] * a["inner_d_mm"] * a["carton_h_mm"], a["empty_places"],
                                             abs(math.log(a["aspect"] / TRAY_ASPECT)), a["columns"]))
    chosen = ranked[0]
    step_x, step_y = unit.width_mm + SET_CLEARANCE_MM, unit.depth_mm + SET_CLEARANCE_MM
    cutouts = [[round(SET_CLEARANCE_MM + c * step_x, 2), round(SET_CLEARANCE_MM + r * step_y, 2),
                unit.width_mm, unit.depth_mm]
               for r in range(chosen["rows"]) for c in range(chosen["columns"])][:n]
    return {
        **base, "code": "", "arrangement": chosen, "alternatives": ranked[1:4],
        "chosen_by": ("the smallest carton the dimension gate accepts, then the fewest empty places, then the insert "
                      f"nearest {TRAY_ASPECT} wide to deep (CHOSEN)"),
        "insert_raised_mm": chosen["raised_mm"],
        "carton_inner": {"w_mm": chosen["inner_w_mm"], "d_mm": chosen["inner_d_mm"], "h_mm": chosen["carton_h_mm"]},
        "insert": {"w_mm": chosen["inner_w_mm"], "d_mm": chosen["inner_d_mm"], "raised_mm": chosen["raised_mm"],
                   "cutouts_mm": cutouts},
    }
