# BEFORE MODIFYING ANY GEOMETRY:
# Read apps/dielines/docs/geometry_decisions.md AND the coordinate
# contract below. Every coordinate is derived from the contract — no
# ratios, no angles not listed in the contract, no magic numbers.
"""ECMA A20.20.01.01 straight-tuck-end — customer-grade archetype (2A-9).

``ecma_a20_20_01_01_ste_carton/0.1`` — OPEN_SOURCE_FORMULA_ADAPTED_
PROVISIONAL. The closed-form geometry is adapted, with attribution, from
the MIT-licensed DDR68/Rhino_Packaging_Toolkit generator (see
FORMULA_PROVENANCE below and THIRD_PARTY_NOTICES.md). This module is an
independent internal implementation: no Rhino runtime code or dependency
is imported; the emission targets the platform's own
:class:`DielineCoordinates` contract (Shapely + primitives), and bleed,
safe area, collision checks and inner/manufacturing/outer conversion are
BBROSE additions absent from the source.

Nothing in the historical STE engine (``engine.py``, versions 1.0/1.1) is
modified: this archetype registers its own template id and version.

STATUS: PROVISIONAL — PHYSICAL_SAMPLE_VALIDATION_REQUIRED. The template
cannot pass Gate 2, and only a recorded physical FIT_PASS may promote it
past 0.1 (apps.dielines.services.physical_validation). A customer- or
manufacturer-supplied vector dieline automatically outranks it.

COORDINATE CONTRACT (t = board thickness; the supplied width/depth/height
are INNER dimensions for THIS template — the task-50 authority facts are
inner 90 x 32 x 92 at t = 0.5):

    L = W_inner + 2t        external main span   (DDR68 input convention)
    P = D_inner + 2t        external side span
    A = H_inner + 2t        external height
    body_h = A - 2t = H_inner   (body height between the main creases)

    x0 = 0                  glue-flap free edge
    x1 = G                  crease: glue flap | back   (G = glue_tab_mm)
    x2 = x1 + L - t         crease: back | side_left   (back = L - t)
    x3 = x2 + P - t         relief-cut start           (side column = P - t)
    x3b = x3 + t            crease: side_left | front  (t-wide relief strip)
    x4 = x3b + L            crease: front | side_right (front = L)
    x5 = x4 + P - t         cut: right free edge       (side_right = P - t)

    y (internal, y-up; flipped to the engine's y-down on emission):
    y_bot = 0, y_top = body_h                    body creases (sides/front)
    y_bot_t = -t, y_top_t = body_h + t           back-panel creases
                                                 (compensated: the back
                                                 wraps the closure faces)
    y_inc_* = body creases inset by t            glue crease shortened
    crd_off = t*2t/(2t + taper)                  back crease start where the
                                                 glue-diagonal cut meets it

    closure (per end, from the back-panel crease):
    ear  = crease -/+ P                          closure-face outer edge
    fold = ear +/- 2t                            tuck fold (2t lock ears)
    tip  = fold -/+ hook                         tuck-hook tip
    closure face depth = P - 2t = D_inner        (the folded face spans the
                                                 inner depth exactly)

    dust flap depth = min((P + hook - t)/2, L/2)
    entry slits: at each tuck-fold end, slit_l cut along the ear line +
    slit_d cut across the fold; the fold crease spans only the middle
    (crease shortening around cut interruptions).

COMPENSATION ASSUMPTIONS (every one is reported in ``derived``):
  * external = inner + 2t on every axis (DDR68 convention). Pacdora's
    published manufacturing numbers (~90.6 x 32.6 x 93.1) use a different
    allowance convention (deltas <= 0.6 mm); only a physical sample or a
    supplied manufacturer die resolves which convention the converter uses.
  * glue width, hook length, chamfer, taper, slit sizes and the shoulder
    control factor are published template parameters, not customer facts.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .coordinates import DielineCoordinates, DimensionSet
from .panels import Panel
from .primitives import CubicSeg, LineSeg, Primitive, sample_path

#: §2 provenance record — persisted with every structure built from this
#: archetype (structure_presentation and the preview parameter table).
FORMULA_PROVENANCE = {
    "source_repository": "https://github.com/DDR68/Rhino_Packaging_Toolkit",
    "commit_reviewed": "e062327c0f309a0bb3a374fb9a210713d97a13ca",
    "source_license": "MIT",
    "license_notice": "MIT License, Copyright (c) 2026 DDR68 — see "
                      "THIRD_PARTY_NOTICES.md; no endorsement of BBROSE "
                      "Design OS is implied",
    "source_file": "packaging/ECMA_A20_20_01_01.py",
    "source_functions": ["main()", "linea()", "nurbs2()"],
    "formulas_adapted": [
        "panel boundaries glue | L-t | P-t | [t relief] | L | P-t",
        "body height A - 2t with back-panel creases offset by t",
        "glue crease shortened t; diagonal crease-start t*2t/(2t+taper)",
        "closure: ear at crease -/+ P, fold 2t inside, hook past the fold",
        "quadratic Bezier tuck shoulders (control factor 0.635)",
        "entry slits slit_l x slit_d with the fold crease shortened",
        "dust flap depth (P + hook - t)/2 capped at L/2, chamfer + taper",
    ],
    "bbrose_changes": [
        "Rhino document emission replaced by DielineCoordinates "
        "(Shapely polygons + LineSeg/CubicSeg primitives, y-down)",
        "quadratic shoulders emitted as exact cubic Beziers "
        "(c1=(q0+2*qc)/3, c2=(q2+2*qc)/3)",
        "inner-dimension input convention (external = inner + 2t derived)",
        "full-contour bleed, safe area, collision checks, deterministic "
        "content hashes, parameter validation — all absent upstream",
        "interactive Rhino prompts replaced by the platform input schema",
    ],
    "internal_geometry_version": "ecma_a20_20_01_01_ste_carton/0.1",
}

TEMPLATE_ID = "ecma_a20_20_01_01_ste_carton"
TEMPLATE_VERSION = "0.1"


class EcmaSteGeometryError(ValueError):
    """Raised when the supplied parameters cannot fold as this archetype."""


@dataclass(frozen=True)
class EcmaSteSpec:
    """Frozen parameter set for one published archetype version."""
    template: str = TEMPLATE_ID
    version: str = TEMPLATE_VERSION
    hook_mm: float = 18.0          # tuck-hook reach past the fold
    chamfer_mm: float = 3.0        # dust-flap / glue-flap corner chamfer
    taper_mm: float = 2.0          # dust-flap inner-edge taper
    entry_slit_len_mm: float = 7.0     # slit along the ear line, per end
    entry_slit_depth_mm: float = 2.5   # slit across the fold, per end
    shoulder_control_k: float = 0.635  # Bezier control position ear->tip
    assumptions: tuple[str, ...] = (
        "external dimensions = inner + 2t on every axis (DDR68 convention); "
        "Pacdora's published allowances differ by <= 0.6 mm — the physical "
        "sample decides the convention",
        "tuck hook 18 mm, chamfer 3 mm, taper 2 mm, entry slits 7 x 2.5 mm, "
        "shoulder control factor 0.635: published template parameters from "
        "the adapted MIT source, not customer dimensions",
        "glue flap width is a template parameter (default 12 mm), not a "
        "customer dimension",
    )


ECMA_A20_20_01_01_STE_CARTON_V0_1 = EcmaSteSpec()

_SPECS: dict[str, EcmaSteSpec] = {
    ECMA_A20_20_01_01_STE_CARTON_V0_1.template:
        ECMA_A20_20_01_01_STE_CARTON_V0_1,
}


def spec_for_template(template: str) -> EcmaSteSpec | None:
    return _SPECS.get(template)


def _quad_to_cubic(q0, qc, q2) -> CubicSeg:
    """Exact degree elevation of a quadratic Bezier to a cubic."""
    c1 = ((q0[0] + 2.0 * qc[0]) / 3.0, (q0[1] + 2.0 * qc[1]) / 3.0)
    c2 = ((q2[0] + 2.0 * qc[0]) / 3.0, (q2[1] + 2.0 * qc[1]) / 3.0)
    return CubicSeg(q0, c1, c2, q2)


def paths_content_hash(paths: list[list[tuple[float, float]]]) -> str:
    """Deterministic sha256 of rounded path coordinates (2 dp)."""
    payload = json.dumps(
        [[[round(v, 2) for v in pt] for pt in path] for path in paths],
        separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def calculate_ecma_ste(params, spec: EcmaSteSpec) -> DielineCoordinates:
    """Build the archetype die. ``params`` is a validated DielineInputJSON
    whose width/depth/height are INNER dimensions for this template."""
    d = params.dimensions
    pset = params.print_settings
    c = params.construction

    Wi, Di, Hi = d.width_mm, d.depth_mm, d.height_mm
    t = c.board_thickness_mm
    G = c.glue_tab_mm
    bleed_mm = pset.bleed_mm
    safe_mm = pset.safe_margin_mm
    hook = spec.hook_mm
    chamf = spec.chamfer_mm
    taper = spec.taper_mm
    slit_l = spec.entry_slit_len_mm
    slit_d = spec.entry_slit_depth_mm
    k = spec.shoulder_control_k

    if t <= 0.0:
        raise EcmaSteGeometryError(
            "board_thickness_mm must be > 0 for this archetype: every "
            "compensation in the contract is derived from t")

    L, P, A = Wi + 2 * t, Di + 2 * t, Hi + 2 * t
    body_h = A - 2 * t                      # == Hi by construction
    ear = 2 * t

    if P < G + 3.0:
        raise EcmaSteGeometryError(
            f"side span P = {P:g} mm must be >= glue flap + 3 mm "
            f"({G + 3.0:g} mm) or the glue joint overlaps the side fold")
    if P - t - 2 * chamf - taper <= 0:
        raise EcmaSteGeometryError(
            f"side span P = {P:g} mm leaves no dust-flap base after "
            f"chamfer {chamf:g} + taper {taper:g}")
    if hook <= ear:
        raise EcmaSteGeometryError("tuck hook must reach past the 2t ear")
    if (L - t) - 2 * (slit_l + ear) <= 0:
        raise EcmaSteGeometryError(
            "back panel too narrow for the entry slits and lock ears")

    # ---- contract X ----
    x0 = 0.0
    x1 = G
    x2 = x1 + L - t
    x3 = x2 + P - t
    x3b = x3 + t
    x4 = x3b + L
    x5 = x4 + P - t

    # ---- contract Y (internal y-up) ----
    y_bot, y_top = 0.0, body_h
    y_bot_t, y_top_t = -t, body_h + t
    y_inc_bot, y_inc_top = y_bot + t, y_top - t
    dust_d = min((P + hook - t) / 2.0, L / 2.0)
    ear_b, ear_t = y_bot_t - P, y_top_t + P
    fold_b, fold_t = ear_b + ear, ear_t - ear
    tip_b, tip_t = fold_b - hook, fold_t + hook
    xl = x1 - t                              # tuck left edge (x2 is right)
    crd_off = t * 2 * t / (2 * t + taper)
    crd_x = x1 - crd_off

    flat_w = x5
    flat_h = tip_t - tip_b

    def Y(y_up: float) -> float:            # flip to the engine's y-down
        return round(tip_t - y_up, 6)

    def ring(points_up: list[tuple[float, float]]) -> Polygon:
        return Polygon([(round(px, 6), Y(py)) for px, py in points_up])

    # ---- components (y-up rings, flipped inside ring()) ----
    glue_poly = ring([
        (x1, y_inc_bot), (x0, y_inc_bot + chamf),
        (x0, y_inc_top - chamf), (x1, y_inc_top),
    ])
    back_poly = ring([
        (x1, y_inc_bot), (crd_x, y_bot_t), (x2, y_bot_t),
        (x2, y_top_t), (crd_x, y_top_t), (x1, y_inc_top),
    ])
    slab_poly = ring([
        (x2, y_bot), (x5, y_bot), (x5, y_top), (x2, y_top),
    ])
    body_poly = unary_union([back_poly, slab_poly])

    def _tuck_primitives(sign: int) -> list[Primitive]:
        """Closed tuck outline. sign -1 = bottom closure, +1 = top."""
        hinge = y_bot_t if sign < 0 else y_top_t
        e = ear_b if sign < 0 else ear_t
        tp = tip_b if sign < 0 else tip_t
        ctrl_y = e + (tp - e) * k
        tip_l, tip_r = xl + slit_l + ear, x2 - slit_l - ear
        pts = {
            "hinge_l": (crd_x, Y(hinge)),
            "diag": (xl, Y(hinge + sign * taper)),
            "ear_l": (xl, Y(e)),
            "tip_l": (tip_l, Y(tp)),
            "tip_r": (tip_r, Y(tp)),
            "ear_r": (x2, Y(e)),
            "hinge_r": (x2, Y(hinge)),
        }
        ctrl_l, ctrl_r = (xl, Y(ctrl_y)), (x2, Y(ctrl_y))
        return [
            LineSeg(pts["hinge_l"], pts["diag"]),
            LineSeg(pts["diag"], pts["ear_l"]),
            _quad_to_cubic(pts["ear_l"], ctrl_l, pts["tip_l"]),
            LineSeg(pts["tip_l"], pts["tip_r"]),
            _quad_to_cubic(pts["tip_r"], ctrl_r, pts["ear_r"]),
            LineSeg(pts["ear_r"], pts["hinge_r"]),
            LineSeg(pts["hinge_r"], pts["hinge_l"]),
        ]

    tuck_bot_prims = _tuck_primitives(-1)
    tuck_top_prims = _tuck_primitives(+1)
    tuck_bot_poly = Polygon(sample_path(tuck_bot_prims))
    tuck_top_poly = Polygon(sample_path(tuck_top_prims))

    def _dust(x_in: float, x_out: float, sign: int, shift: float) -> Polygon:
        """Dust flap. ``x_in`` = tapered inner edge, ``x_out`` = chamfered
        outer edge; ``shift`` = t on the P4 outer edge (DDR68 compensated
        chamfer), 0 on P2. sign -1 = bottom, +1 = top."""
        base = y_bot if sign < 0 else y_top
        tab = base + sign * dust_d
        inner_first = x_in < x_out
        pts_inner = [
            (x_in, base),
            (x_in, base + sign * (chamf + taper)),
            (x_in + (chamf if inner_first else -chamf),
             base + sign * (2 * chamf + taper)),
            (x_in + ((chamf + taper) if inner_first else -(chamf + taper)),
             tab),
        ]
        pts_outer = [
            (x_out + (-chamf + shift if inner_first else chamf - shift), tab),
            (x_out + (-chamf + shift if inner_first else chamf - shift),
             base + sign * chamf),
            (x_out, base),
        ]
        return ring(pts_inner + pts_outer)

    dust_p2_bot = _dust(x3, x2, -1, 0.0)
    dust_p2_top = _dust(x3, x2, +1, 0.0)
    dust_p4_bot = _dust(x4 + t, x5, -1, t)
    dust_p4_top = _dust(x4 + t, x5, +1, t)

    parts = [glue_poly, body_poly, tuck_bot_poly, tuck_top_poly,
             dust_p2_bot, dust_p2_top, dust_p4_bot, dust_p4_top]
    cut_polygon = unary_union(parts)
    if cut_polygon.geom_type != "Polygon":
        raise EcmaSteGeometryError(
            "cut contour is not a single closed region — components are "
            f"disconnected ({cut_polygon.geom_type})")
    bleed_polygon = cut_polygon.buffer(bleed_mm, join_style=1, quad_segs=16)
    safe_polygon = box(x1 + safe_mm, Y(y_top) + safe_mm,
                       x5 - safe_mm, Y(y_bot) - safe_mm)

    # ---- creases (y-down 4-tuples) ----
    def seg(xa, ya, xb, yb):
        return (round(xa, 6), Y(ya), round(xb, 6), Y(yb))

    fold_lines = [
        seg(x1, y_inc_bot, x1, y_inc_top),        # glue crease (shortened t)
        seg(x2, y_bot, x2, y_top),                # back | side_left
        seg(x3b, y_bot, x3b, y_top),              # side_left | front
        seg(x4, y_bot, x4, y_top),                # front | side_right
        seg(crd_x, y_bot_t, x2, y_bot_t),         # back bottom (compensated)
        seg(crd_x, y_top_t, x2, y_top_t),         # back top (compensated)
        seg(x2, y_bot, x3, y_bot),                # P2 bottom dust hinge
        seg(x2, y_top, x3, y_top),                # P2 top dust hinge
        seg(x4 + t, y_bot, x5, y_bot),            # P4 bottom dust hinge
        seg(x4 + t, y_top, x5, y_top),            # P4 top dust hinge
        # tuck folds, shortened around the entry slits
        seg(xl + slit_l, fold_b, x2 - slit_l, fold_b),
        seg(xl + slit_l, fold_t, x2 - slit_l, fold_t),
    ]

    # ---- entry slits (cut interruptions at the tuck folds) ----
    slit_lines = []
    for e, sign in ((ear_b, +1), (ear_t, -1)):
        slit_lines += [
            seg(xl, e, xl + slit_l, e),
            seg(xl + slit_l, e, xl + slit_l, e + sign * slit_d),
            seg(x2, e, x2 - slit_l, e),
            seg(x2 - slit_l, e, x2 - slit_l, e + sign * slit_d),
        ]

    panels = [
        Panel("glue_tab", x0, Y(y_inc_top), x1 - x0, body_h - 2 * t),
        Panel("back", x1, Y(y_top_t), x2 - x1, body_h + 2 * t),
        Panel("side_left", x2, Y(y_top), x3b - x2, body_h),
        Panel("front", x3b, Y(y_top), x4 - x3b, body_h),
        Panel("side_right", x4, Y(y_top), x5 - x4, body_h),
    ]

    parameters = {
        "inner_mm": [Wi, Di, Hi],
        "board_thickness_mm": t,
        "glue_tab_mm": G,
        "hook_mm": hook, "chamfer_mm": chamf, "taper_mm": taper,
        "entry_slit_len_mm": slit_l, "entry_slit_depth_mm": slit_d,
        "shoulder_control_k": k,
        "bleed_mm": bleed_mm, "safe_margin_mm": safe_mm,
    }
    compensation_report = [
        f"external = inner + 2t: L={L:g}, P={P:g}, A={A:g} (t={t:g})",
        f"back panel L - t = {L - t:g} mm; front L = {L:g} mm; "
        f"sides P - t = {P - t:g} mm each; relief strip t = {t:g} mm",
        f"back creases offset +/-{t:g} mm (body {body_h:g} mm between "
        "the side/front creases)",
        f"glue crease shortened {t:g} mm each end; crease start "
        f"compensated {crd_off:.3f} mm at the glue diagonal",
        f"closure face depth P - 2t = {P - 2 * t:g} mm (= inner depth)",
        f"tuck lock ears 2t = {ear:g} mm; entry slits {slit_l:g} x "
        f"{slit_d:g} mm cross the fold by {slit_d - ear:g} mm",
        f"dust flap depth (P + hook - t)/2 = {dust_d:g} mm (cap L/2 = "
        f"{L / 2:g} mm)",
    ]

    coords = DielineCoordinates(
        flat_width_mm=round(flat_w, 4),
        flat_height_mm=round(flat_h, 4),
        panels=panels,
        fold_lines=fold_lines,
        cut_polygon=cut_polygon,
        bleed_polygon=bleed_polygon,
        safe_polygon=safe_polygon,
        tuck_flap_polygons=[tuck_top_poly, tuck_bot_poly],
        dust_flap_polygons=[dust_p2_top, dust_p4_top,
                            dust_p2_bot, dust_p4_bot],
        glue_tab_polygon=glue_poly,
        body_polygon=body_poly,
        slit_lines=slit_lines,
        components=[
            ("main-body", body_poly),
            ("glue-tab", glue_poly),
            ("top-back-tuck", tuck_top_poly),
            ("bottom-back-tuck", tuck_bot_poly),
            ("top-left-dust", dust_p2_top),
            ("top-right-dust", dust_p4_top),
            ("bottom-left-dust", dust_p2_bot),
            ("bottom-right-dust", dust_p4_bot),
        ],
        component_paths={
            "top-back-tuck": tuck_top_prims,
            "bottom-back-tuck": tuck_bot_prims,
        },
        stadium_cutouts=[],
        dimensions=DimensionSet(
            manufacture=(round(L, 4), round(P, 4), round(A, 4)),
            inner=(round(Wi, 4), round(Di, 4), round(Hi, 4)),
            outer=(round(L + 2 * t, 4), round(P + 2 * t, 4),
                   round(A + 2 * t, 4)),
        ),
        board_thickness_mm=t,
        body_top_y=Y(y_top),
        body_bottom_y=Y(y_bot),
        derived={
            "structure_type": spec.template,
            "template_version": spec.version,
            "archetype": TEMPLATE_ID,
            "structure_status": "OPEN_SOURCE_FORMULA_ADAPTED_PROVISIONAL",
            "physical_validation": "PHYSICAL_SAMPLE_VALIDATION_REQUIRED",
            "provisional": True,
            "per_hinge_creases": True,
            "thickness_compensation": True,
            "x0": x0, "x1": x1, "x2": x2, "x3": x3, "x3b": x3b,
            "x4": x4, "x5": x5,
            "top_tuck_panel": "back", "bottom_tuck_panel": "back",
            "bottom_mode": "tuck",
            "tuck_flap_height_mm": round(P - 2 * t + hook, 4),
            "top_tuck_lip_mm": hook,
            "tuck_inset_mm": round(slit_l + ear, 4),
            "tuck_curve_h_mm": round(hook - ear, 4),
            "tuck_lock_ear_mm": ear,
            "dust_flap_height_mm": round(dust_d, 4),
            "entry_slit_mm": slit_l,
            "entry_slit_depth_mm": slit_d,
            "glue_tab_corner_cut_mm": chamf,
            "slit_web_mm": round(((L - t) - 2 * slit_l) / 2.0, 4),
            "panel_allowance_back_mm": 0.0,
            "panel_allowance_side_mm": 0.0,
            "kerf_mm": c.kerf_mm,
            "parameters": parameters,
            "compensation_report": compensation_report,
            "assumptions": list(spec.assumptions),
            "formula_provenance": FORMULA_PROVENANCE,
            "notes": [
                "PROVISIONAL STRUCTURE — PHYSICAL SAMPLE REQUIRED — "
                "NOT APPROVED FOR MASS PRODUCTION",
                "geometry adapted from the MIT-licensed "
                "DDR68/Rhino_Packaging_Toolkit ECMA A20.20.01.01 generator "
                "(attribution in THIRD_PARTY_NOTICES.md)",
                "a customer- or manufacturer-supplied vector dieline "
                "automatically outranks this archetype",
            ],
        },
    )
    coords.validate()
    return coords


def geometry_content_hashes(coords: DielineCoordinates) -> dict:
    """Deterministic content hashes of the emitted cut/crease/bleed paths."""
    cut_paths = [list(coords.cut_polygon.exterior.coords)]
    cut_paths += [[(a, b), (cx, dy)] for (a, b, cx, dy) in coords.slit_lines]
    crease_paths = [[(a, b), (cx, dy)]
                    for (a, b, cx, dy) in coords.fold_lines]
    bleed_paths = [list(coords.bleed_polygon.exterior.coords)]
    return {
        "cut_path_hash": paths_content_hash(cut_paths),
        "crease_path_hash": paths_content_hash(crease_paths),
        "bleed_path_hash": paths_content_hash(bleed_paths),
    }


def collision_report(coords: DielineCoordinates) -> dict:
    """§3 archetype-specific collision/overlap checks (flat + folded)."""
    d = coords.derived
    L, P, A = coords.dimensions.manufacture
    t = coords.board_thickness_mm
    dust_d = d["dust_flap_height_mm"]
    hook = d["top_tuck_lip_mm"]
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("dust_flaps_opposing_clearance", L - 2 * dust_d > 0,
        f"folded dust flaps leave {L - 2 * dust_d:.2f} mm across the "
        f"{L:g} mm opening")
    add("dust_flap_depth_cap", dust_d <= L / 2,
        f"dust depth {dust_d:g} <= L/2 = {L / 2:g}")
    add("tuck_hook_vs_body", hook + 2 * t < A - 2 * t,
        f"hook {hook:g} mm folds inside the {A - 2 * t:g} mm body")
    add("closure_face_equals_inner_depth",
        abs((P - 2 * t) - coords.dimensions.inner[1]) < 1e-6,
        f"closure face {P - 2 * t:g} mm == inner depth "
        f"{coords.dimensions.inner[1]:g} mm")
    add("glue_flap_vs_side_panel",
        P >= d["parameters"]["glue_tab_mm"] + 3.0,
        f"side span {P:g} mm clears the glue flap by "
        f"{P - d['parameters']['glue_tab_mm']:g} mm")

    # flat-layout: no two components may overlap by area (shared hinge
    # edges contribute zero area)
    comps = coords.components
    worst = 0.0
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            worst = max(worst, comps[i][1].intersection(comps[j][1]).area)
    add("component_area_overlap", worst < 1e-6,
        f"largest pairwise component overlap {worst:.8f} mm^2")

    add("cut_contour_closed_valid",
        coords.cut_polygon.is_valid
        and coords.cut_polygon.geom_type == "Polygon",
        "cut contour is one valid closed region")
    cb, bb = coords.cut_polygon.bounds, coords.bleed_polygon.bounds
    grow = min(cb[0] - bb[0], cb[1] - bb[1], bb[2] - cb[2], bb[3] - cb[3])
    add("bleed_contour_complete", grow > 0,
        f"bleed offset outward on every side (min growth {grow:.3f} mm)")

    return {"checks": checks, "all_ok": all(c["ok"] for c in checks)}


__all__ = [
    "EcmaSteSpec", "EcmaSteGeometryError",
    "ECMA_A20_20_01_01_STE_CARTON_V0_1",
    "FORMULA_PROVENANCE", "TEMPLATE_ID", "TEMPLATE_VERSION",
    "spec_for_template", "calculate_ecma_ste",
    "geometry_content_hashes", "collision_report", "paths_content_hash",
]
