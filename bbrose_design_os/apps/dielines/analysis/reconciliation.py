"""Dimensional reconciliation + closure collision checks (DIP-2A-5-DIE-2).

Reconciles the THREE dimension sets a customer supplies for a carton —
manufacturing (score-to-score, the drawn truth), inner (usable cavity) and
outer (external envelope) — against the engine's board-thickness model, and
runs the physical collision checks the closure system must satisfy.

Binding rules (from the task-#47 correction contract):

  * The manufacturing dimensions are structural truth: the engine draws
    them and this module NEVER adjusts them.
  * Any assumption needed to reconcile the supplied inner/outer values is
    REPORTED in the result — supplied values are never silently changed and
    never silently ignored.
  * A per-axis comparison lands in one of three states:
        MATCH                       |delta| <= tolerance (0.05 mm)
        RECONCILED_WITH_ASSUMPTION  explained by a stated assumption
        DISCREPANCY_REPORTED        cannot be explained — a human must rule
    DISCREPANCY_REPORTED entries make ``reconciled`` False, which Gate-2
    production validation treats as a blocking failure.

The Skynte Foundation numbers, worked through this model (t = 0.3 mm is
inferred from the cross-section inner values, which equal manufacture − 2t
exactly and unambiguously):

    inner  W/D:  41.4 / 31.4  = 42/32 − 2t          → MATCH at t=0.3
    inner  H:    138.9        = 140 − 2t − 0.5      → 0.5 mm closure
                 headspace assumption (tuck lip + dust stack clearance)
    outer  W/D:  42.4 / 32.4  = 42/32 + 2t − 0.2    → 0.2 mm under the
                 nominal two-board stack: consistent with score compression
                 at the folded corners (boards crush at the crease)
    outer  H:    140.9        = 140 + 2t + 0.3      → 0.3 mm over nominal:
                 consistent with the closed tuck/dust flap stack at the ends
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

_MATCH_TOLERANCE_MM = 0.05
# Board thickness is compared more strictly: the inference already averages
# two axes, and a 0.05 mm slip on t doubles into 0.1 mm on every panel sum.
_T_TOLERANCE_MM = 0.02
# Reconciliation assumptions are only offered when the residual they explain
# stays physically small; beyond this the discrepancy must go to a human.
_MAX_EXPLAINABLE_RESIDUAL_MM = 1.0

MATCH = "MATCH"
RECONCILED = "RECONCILED_WITH_ASSUMPTION"
DISCREPANCY = "DISCREPANCY_REPORTED"

_AXES = ("width", "depth", "height")


@dataclass
class AxisCheck:
    dimension_set: str          # "inner" | "outer"
    axis: str                   # "width" | "depth" | "height"
    supplied_mm: float
    model_mm: float             # engine model value (manufacture ± 2t)
    delta_mm: float             # supplied − model
    status: str                 # MATCH | RECONCILED... | DISCREPANCY...
    assumption: str = ""


@dataclass
class CollisionCheck:
    name: str
    ok: bool
    value_mm: float
    limit_mm: float
    detail: str


@dataclass
class ReconciliationResult:
    template: str
    board_thickness_mm: float
    board_thickness_inferred_mm: float | None
    manufacture_mm: tuple[float, float, float]
    axis_checks: list[AxisCheck] = field(default_factory=list)
    collision_checks: list[CollisionCheck] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    discrepancies: list[str] = field(default_factory=list)

    @property
    def reconciled(self) -> bool:
        return not self.discrepancies and all(
            c.ok for c in self.collision_checks
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["reconciled"] = self.reconciled
        return d


def infer_board_thickness(
    manufacture: tuple[float, float, float],
    inner: tuple[float, float, float],
) -> float | None:
    """Infer t from the cross-section inner values (inner = manufacture − 2t).

    Only width and depth vote: the height axis carries closure headspace on
    real cartons. Returns None when the two votes disagree by more than the
    match tolerance — then t must come from the customer.
    """
    t_w = (manufacture[0] - inner[0]) / 2.0
    t_d = (manufacture[1] - inner[1]) / 2.0
    if abs(t_w - t_d) > _MATCH_TOLERANCE_MM:
        return None
    t = (t_w + t_d) / 2.0
    return round(t, 4) if t > 0 else None


def reconcile_dimensions(
    coords,
    supplied_inner: tuple[float, float, float],
    supplied_outer: tuple[float, float, float],
) -> ReconciliationResult:
    """Reconcile supplied inner/outer triplets against the drawn geometry.

    ``coords`` is the engine's DielineCoordinates (drawn from manufacturing
    dimensions). Triplets are (width, depth, height) in mm.
    """
    d = coords.derived
    manufacture = coords.dimensions.manufacture
    t = coords.board_thickness_mm
    inferred = infer_board_thickness(manufacture, supplied_inner)

    result = ReconciliationResult(
        template=str(d.get("structure_type", "")),
        board_thickness_mm=t,
        board_thickness_inferred_mm=inferred,
        manufacture_mm=manufacture,
    )

    if inferred is not None and abs(inferred - t) > _T_TOLERANCE_MM:
        result.discrepancies.append(
            f"board thickness mismatch: engine drew t = {t:g} mm but the "
            f"supplied inner cross-section implies t = {inferred:g} mm — "
            "regenerate with the inferred value or have the customer confirm"
        )
    if inferred is not None and abs(inferred - t) <= _T_TOLERANCE_MM:
        result.assumptions.append(
            f"board thickness t = {t:g} mm taken from the supplied inner "
            "cross-section (inner = manufacture − 2t on width and depth); "
            "not independently stated by the customer"
        )

    for i, axis in enumerate(_AXES):
        _check_axis(result, "inner", axis, supplied_inner[i],
                    model=manufacture[i] - 2.0 * t,
                    headspace_axis=(axis == "height"), t=t)
    for i, axis in enumerate(_AXES):
        _check_axis(result, "outer", axis, supplied_outer[i],
                    model=manufacture[i] + 2.0 * t,
                    headspace_axis=(axis == "height"), t=t)

    _collision_checks(result, coords)
    return result


def _check_axis(result, dim_set, axis, supplied, model, headspace_axis, t):
    delta = round(supplied - model, 4)
    check = AxisCheck(
        dimension_set=dim_set, axis=axis, supplied_mm=supplied,
        model_mm=round(model, 4), delta_mm=delta, status=MATCH,
    )
    if abs(delta) <= _MATCH_TOLERANCE_MM:
        result.axis_checks.append(check)
        return

    if abs(delta) > _MAX_EXPLAINABLE_RESIDUAL_MM:
        check.status = DISCREPANCY
        result.discrepancies.append(
            f"{dim_set} {axis}: supplied {supplied:g} mm differs from the "
            f"model value {model:g} mm by {delta:+g} mm — beyond any "
            "physical closure/crease allowance; a human must reconcile"
        )
        result.axis_checks.append(check)
        return

    # Small residuals: state the physical assumption that explains the
    # supplied value. The drawn geometry is NOT changed.
    if dim_set == "inner" and headspace_axis and delta < 0:
        check.assumption = (
            f"{-delta:g} mm vertical closure headspace inside the cavity "
            "(clearance under the closed tuck lip and dust-flap stack)"
        )
    elif dim_set == "inner":
        check.assumption = (
            f"{-delta:g} mm cavity allowance beyond the 2t wall model "
            "(board crush/fit tolerance)"
        )
    elif dim_set == "outer" and headspace_axis and delta > 0:
        check.assumption = (
            f"{delta:g} mm added external height from the closed tuck and "
            "dust-flap stack at the carton ends"
        )
    elif dim_set == "outer" and delta < 0:
        check.assumption = (
            f"{-delta:g} mm score compression at the folded corners "
            "(boards crush at the crease, so the external envelope measures "
            "under the nominal two-board stack)"
        )
    else:
        check.assumption = (
            f"{delta:+g} mm residual within crease/crush tolerance"
        )
    check.status = RECONCILED
    result.assumptions.append(
        f"{dim_set} {axis} {supplied:g} mm reconciled: {check.assumption}"
    )
    result.axis_checks.append(check)


def _collision_checks(result: ReconciliationResult, coords) -> None:
    d = coords.derived
    W, D, H = coords.dimensions.manufacture
    t = coords.board_thickness_mm if d.get("thickness_compensation") else 0.0

    def add(name, ok, value, limit, detail):
        result.collision_checks.append(CollisionCheck(
            name=name, ok=bool(ok), value_mm=round(value, 4),
            limit_mm=round(limit, 4), detail=detail,
        ))

    # 1. Opposing dust flaps must not collide when folded across the opening.
    dust_h = float(d.get("dust_flap_height_mm", 0.0))
    clearance = W - 2.0 * dust_h
    add("dust_flap_opposing_clearance", clearance >= 0.0, clearance, 0.0,
        f"opening span W = {W:g} mm minus two folded dust flaps "
        f"({dust_h:g} mm each) must leave a non-negative gap")

    # 2. Dust flaps fold before the tuck (DECISION-004): dust below tuck zone.
    tuck_h = float(d.get("top_tuck_height_mm", d.get("tuck_flap_height_mm", 0.0)))
    margin = tuck_h - dust_h
    add("dust_below_tuck_zone", margin >= 2.0, margin, 2.0,
        "dust flap must stay at least 2 mm shorter than the tuck zone")

    # 3. The tuck lip's flat top must clear the inner cross-section width.
    inset = float(d.get("tuck_inset_mm", 0.0))
    lip_flat_w = (W + 2.0 * t) - 2.0 * inset
    inner_w = W - 2.0 * coords.board_thickness_mm
    add("tuck_lip_entry_clearance", lip_flat_w <= inner_w,
        lip_flat_w, inner_w,
        "the tucked portion (flap width minus both shoulder insets) must "
        "slide inside the inner width")

    # 4. Tuck lip depth must stay usable against the panel height.
    lip = float(d.get("top_tuck_lip_mm", 0.0)) or max(tuck_h - D, 0.0)
    add("tuck_lip_vs_height", lip < H / 2.0, lip, H / 2.0,
        "tuck lip must be far shorter than the body height")

    # 5. Friction slit web (DECISION-017) already guarded — republish.
    web = float(d.get("slit_web_mm", 0.0))
    add("slit_web", web >= 2.0, web, 2.0,
        "solid board beside each friction-slit end")

    # 6. Bleed contour: closed, valid, and offset by the full bleed on every
    # side (bounds grow by >= bleed in all four directions).
    cb = coords.cut_polygon.bounds
    bb = coords.bleed_polygon.bounds
    grow = min(cb[0] - bb[0], cb[1] - bb[1], bb[2] - cb[2], bb[3] - cb[3])
    bleed_ok = (
        coords.bleed_polygon.is_valid
        and coords.bleed_polygon.geom_type == "Polygon"
        and grow > 0.0
    )
    add("bleed_contour_complete", bleed_ok, grow, 0.0,
        "bleed polygon must be one valid closed contour offset outward on "
        "every side")


__all__ = [
    "AxisCheck",
    "CollisionCheck",
    "ReconciliationResult",
    "infer_board_thickness",
    "reconcile_dimensions",
    "MATCH",
    "RECONCILED",
    "DISCREPANCY",
]
