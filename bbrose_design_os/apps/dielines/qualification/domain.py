"""Supported dimensional domain (2A-9B §2) — derived, never guessed.

Every constraint is derived from the closure geometry, the material
compensation, the slit/ear construction, flap collision or a minimum
manufacturing feature — the derivation is stated next to each formula.
Combinations outside the domain fail with
``DIMENSION_COMBINATION_UNSUPPORTED`` naming the EXACT violated
constraint; distorted geometry is never generated.

Symbols: W/D/H = inner width/depth/height, t = board, G = glue width,
L = W + 2t, P = D + 2t (externals), hook = 18, chamfer = 3, taper = 2,
slit_l = 7, slit_d = 2.5, ear = 2t (all constants from the version-0.1
parameter contract).
"""
from __future__ import annotations

from dataclasses import dataclass

from .contract import OPPOSED_TUCK_CONTRACT

DIMENSION_COMBINATION_UNSUPPORTED = "DIMENSION_COMBINATION_UNSUPPORTED"

_C = {e.name: e.value for e in OPPOSED_TUCK_CONTRACT.entries
      if e.value is not None}
_HOOK = 18.0
_CHAMF = 3.0
_TAPER = 2.0
_SLIT_L = 7.0
_SLIT_D = 2.5
_MIN_CLEAR = _C["flap_clearance_mm"]          # 2.0
_MIN_HINGE = _C["min_fold_hinge_mm"]          # 10.0
_MIN_DUST_BASE = _C["min_dust_base_mm"]       # 2.0
_MIN_TIP = _C["min_tuck_tip_mm"]              # 4.0
_MIN_ENGAGE = _C["min_ear_engagement_mm"]     # 0.5


@dataclass(frozen=True)
class DomainConstraint:
    name: str
    formula: str
    derivation: str

    def violation(self, p: dict) -> str | None:
        raise NotImplementedError


class _Constraint(DomainConstraint):
    def __init__(self, name, formula, derivation, check):
        super().__init__(name, formula, derivation)
        object.__setattr__(self, "_check", check)

    def violation(self, p: dict) -> str | None:
        return self._check(p)


def _rng(name, lo, hi, label, why):
    def check(p):
        v = p[name]
        if not (lo <= v <= hi):
            return (f"{label}: {name} = {v:g} mm is outside "
                    f"[{lo:g}, {hi:g}] mm")
        return None
    return _Constraint(label, f"{lo:g} <= {name} <= {hi:g}", why, check)


def _cx(label, formula, why, predicate, message):
    def check(p):
        return None if predicate(p) else message(p)
    return _Constraint(label, formula, why, check)


OPPOSED_TUCK_DOMAIN: tuple[DomainConstraint, ...] = (
    _rng("board_thickness_mm", 0.3, 1.0, "BOARD_RANGE",
         "manufacturing caliper range for folding-carton board; every "
         "compensation in the contract derives from t"),
    _rng("width_mm", 12.0, 300.0, "WIDTH_RANGE",
         "print-shop sheet/die budget (schema Milestone 9.1)"),
    _rng("depth_mm", 12.0, 300.0, "DEPTH_RANGE",
         "print-shop sheet/die budget"),
    _rng("height_mm", 60.0, 600.0, "HEIGHT_RANGE",
         "print-shop sheet/die budget"),
    _rng("glue_tab_mm", 6.0, 15.0, "GLUE_RANGE",
         "adhesive-joint practice bounds"),
    _rng("bleed_mm", 2.0, 5.0, "BLEED_RANGE", "prepress practice bounds"),
    _rng("safe_margin_mm", 3.0, 8.0, "SAFE_RANGE",
         "prepress practice bounds"),
    _cx("HEIGHT_GT_WIDTH", "H > W",
        "tuck-carton proportion: the tuck closure needs the body taller "
        "than the opening span",
        lambda p: p["height_mm"] > p["width_mm"],
        lambda p: f"HEIGHT_GT_WIDTH: H = {p['height_mm']:g} must exceed "
                  f"W = {p['width_mm']:g}"),
    _cx("HEIGHT_GT_DEPTH", "H > D",
        "tuck-carton proportion",
        lambda p: p["height_mm"] > p["depth_mm"],
        lambda p: f"HEIGHT_GT_DEPTH: H = {p['height_mm']:g} must exceed "
                  f"D = {p['depth_mm']:g}"),
    _cx("GLUE_CLEARANCE", "D + 2t >= G + 3",
        "the glue flap laps inside the side span; less than 3 mm of "
        "clearance overlaps the side fold (adapted-source guard)",
        lambda p: p["depth_mm"] + 2 * p["board_thickness_mm"]
        >= p["glue_tab_mm"] + 3.0,
        lambda p: f"GLUE_CLEARANCE: side span D + 2t = "
                  f"{p['depth_mm'] + 2 * p['board_thickness_mm']:g} mm "
                  f"must be >= G + 3 = {p['glue_tab_mm'] + 3.0:g} mm"),
    _cx("DUST_BASE_MIN", "(D + t) - 2*chamfer - taper >= 2",
        "dust-flap base after the 3 mm chamfer and 2 mm taper must keep a "
        "2 mm manufacturable base (minimum feature)",
        lambda p: (p["depth_mm"] + p["board_thickness_mm"])
        - 2 * _CHAMF - _TAPER >= _MIN_DUST_BASE,
        lambda p: f"DUST_BASE_MIN: dust base = "
                  f"{(p['depth_mm'] + p['board_thickness_mm']) - 2 * _CHAMF - _TAPER:g} mm "
                  f"is below the {_MIN_DUST_BASE:g} mm minimum feature "
                  f"(D + t must be >= {_MIN_DUST_BASE + 2 * _CHAMF + _TAPER:g})"),
    _cx("FOLD_HINGE_MIN", "(W + t) - 2*slit_l >= 10",
        "the tuck-fold crease is shortened by a 7 mm entry slit at each "
        "end; below a 10 mm remaining span the fold has no functional "
        "hinge",
        lambda p: (p["width_mm"] + p["board_thickness_mm"])
        - 2 * _SLIT_L >= _MIN_HINGE,
        lambda p: f"FOLD_HINGE_MIN: remaining fold span = "
                  f"{(p['width_mm'] + p['board_thickness_mm']) - 2 * _SLIT_L:g} mm "
                  f"is below {_MIN_HINGE:g} mm"),
    _cx("TUCK_TIP_MIN", "(W + t) - 2*(slit_l + 2t) >= 4",
        "the flat tuck tip between the Bezier shoulders must keep a 4 mm "
        "span or the shoulders cross (self-intersection)",
        lambda p: (p["width_mm"] + p["board_thickness_mm"])
        - 2 * (_SLIT_L + 2 * p["board_thickness_mm"]) >= _MIN_TIP,
        lambda p: f"TUCK_TIP_MIN: tuck tip span = "
                  f"{(p['width_mm'] + p['board_thickness_mm']) - 2 * (_SLIT_L + 2 * p['board_thickness_mm']):g} mm "
                  f"is below {_MIN_TIP:g} mm"),
    _cx("DUST_PAIR_CLEARANCE", "W - (D + t + hook) >= 2",
        "FOLDED: opposing dust flaps (depth (P + hook - t)/2 each) meet "
        "across the inner width; W - 2*dust_d >= 2 mm or they collide "
        "(measured on the actual outlines by the folded checks)",
        lambda p: p["width_mm"] - (p["depth_mm"] + p["board_thickness_mm"]
                                   + _HOOK) >= _MIN_CLEAR,
        lambda p: f"DUST_PAIR_CLEARANCE: folded dust clearance = "
                  f"{p['width_mm'] - (p['depth_mm'] + p['board_thickness_mm'] + _HOOK):g} mm "
                  f"is below {_MIN_CLEAR:g} mm (needs W >= D + t + "
                  f"{_HOOK + _MIN_CLEAR:g})"),
    _cx("EAR_ENGAGEMENT", "slit_d - 2t >= 0.5",
        "the entry slit must cross the fold beyond the 2t locking ear by "
        ">= 0.5 mm or the ear cannot snap in",
        lambda p: _SLIT_D - 2 * p["board_thickness_mm"] >= _MIN_ENGAGE,
        lambda p: f"EAR_ENGAGEMENT: slit crossing = "
                  f"{_SLIT_D - 2 * p['board_thickness_mm']:g} mm is below "
                  f"{_MIN_ENGAGE:g} mm (t must be <= "
                  f"{(_SLIT_D - _MIN_ENGAGE) / 2:g})"),
    _cx("HOOK_VS_BODY", "H >= hook + 2t + 2",
        "FOLDED: the tuck hook folds down inside the opposite main face "
        "and must clear the body height",
        lambda p: p["height_mm"] >= _HOOK
        + 2 * p["board_thickness_mm"] + 2.0,
        lambda p: f"HOOK_VS_BODY: H = {p['height_mm']:g} mm must be >= "
                  f"{_HOOK + 2 * p['board_thickness_mm'] + 2.0:g} mm"),
)


def evaluate_domain(user_params: dict,
                    constraints=OPPOSED_TUCK_DOMAIN) -> list[str]:
    """All violated-constraint messages; empty = supported."""
    violations = []
    for constraint in constraints:
        message = constraint.violation(user_params)
        if message:
            violations.append(message)
    return violations


def domain_report(constraints=OPPOSED_TUCK_DOMAIN) -> list[dict]:
    return [{"name": c.name, "formula": c.formula,
             "derivation": c.derivation} for c in constraints]


def effective_bounds(t: float = 0.5, glue: float = 12.0) -> dict:
    """Human-readable envelope at a given board/glue (for the report)."""
    w_min = max(12.0, _MIN_HINGE + 2 * _SLIT_L - t,
                _MIN_TIP + 2 * _SLIT_L + 4 * t - t,
                12.0 + t + _HOOK + _MIN_CLEAR)   # with D at its 12 mm floor
    d_min = max(12.0, _MIN_DUST_BASE + 2 * _CHAMF + _TAPER - t,
                glue + 3.0 - 2 * t)
    return {
        "board_thickness_mm": [0.3, min(1.0, (_SLIT_D - _MIN_ENGAGE) / 2)],
        "width_mm_min_at_depth_floor": round(w_min, 2),
        "width_mm_max": 300.0,
        "depth_mm_min": round(d_min, 2),
        "depth_mm_max_given_W": f"W - t - {_HOOK + _MIN_CLEAR:g}",
        "height_mm": [60.0, 600.0],
        "height_rule": "H > W and H > D",
        "width_depth_rule": f"W >= D + t + {_HOOK + _MIN_CLEAR:g} "
                            "(folded dust clearance)",
    }


__all__ = ["DIMENSION_COMBINATION_UNSUPPORTED", "OPPOSED_TUCK_DOMAIN",
           "evaluate_domain", "domain_report", "effective_bounds",
           "DomainConstraint"]
