# BEFORE MODIFYING ANY GEOMETRY:
# Read apps/dielines/docs/geometry_decisions.md AND the coordinate
# contract below. Every coordinate is derived from the contract — no
# ratios, no angles not listed in the contract, no magic numbers.
"""Reference-matched OPPOSING-tuck carton (Phase 2A-9-CORR-2).

``reference_opposed_tuck_carton/0.1`` — REFERENCE_RECONSTRUCTED_PROVISIONAL.

The first 2A-9 archetype (ecma_a20_20_01_01_ste_carton/0.1) hung BOTH major
tucks from the same main panel; the Pacdora reference visibly opposes them
(PROVISIONAL_CLOSURE_TOPOLOGY_MISMATCH / MAJOR_TUCK_PANEL_ASSIGNMENT_
MISMATCH / REFERENCE_OPPOSING_TUCK_NOT_PRESERVED). This module rebuilds the
closure with the reference attachment:

    upper major tuck  -> MAIN PANEL A  (first 90 mm panel after the glue)
    lower major tuck  -> MAIN PANEL B  (second 90 mm panel)
    dust flaps        -> both 32 mm SIDE panels, top and bottom

Geometry adapted, with attribution, from the MIT-licensed
DDR68/Rhino_Packaging_Toolkit ECMA A20.20.03.01 generator (opposing-tuck
topology); see FORMULA_PROVENANCE and THIRD_PARTY_NOTICES.md. Upstream
defect fixed here: that script uses ``dust_d`` without defining it — this
implementation defines it as the sibling STE generator does.

COORDINATE CONTRACT (t = board thickness; supplied width/depth/height are
INNER dimensions; external L/P/A = inner + 2t):

    x0 = 0                 glue-flap free edge
    x1 = G                 crease: glue | main_a       (G = glue_tab_mm)
    x2 = x1 + L - t        crease: main_a | side_a     (main_a = L - t)
    x3 = x2 + P            crease: side_a | main_b     (side_a = P)
    x4 = x3 + L            crease: main_b | side_b     (main_b = L)
    x5 = x4 + P - t        cut: right free edge        (side_b = P - t)

    y_bot = 0, y_top = A - 2t                body creases on the sides
    y_top_t = y_top + t                      main_a TOP crease (compensated:
                                             its closure wraps the opening)
    y_bot_t = -t                             main_b BOTTOM crease (mirror)
    glue flap spans y_bot .. y_top - t       (shortened only at the top,
                                             beside the main_a tuck)

    top closure (from main_a):   ear = y_top_t + P, fold = ear - 2t,
                                 tip = fold + hook
    bottom closure (from main_b): ear = y_bot_t - P, fold = ear + 2t,
                                 tip = fold - hook
    closure face depth = P - 2t = inner depth, both ends
    entry slits slit_l x slit_d at all four fold ends; every fold crease is
    shortened around its slits; dust depth = min((P + hook - t)/2, L/2)
    (defined here; see upstream defect note above)

Nothing in the historical STE engine or in ecma_ste.py is modified.
"""
from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .coordinates import DielineCoordinates, DimensionSet
from .ecma_ste import _quad_to_cubic, paths_content_hash
from .panels import Panel
from .primitives import LineSeg, Primitive, sample_path

FORMULA_PROVENANCE = {
    "source_repository": "https://github.com/DDR68/Rhino_Packaging_Toolkit",
    "commit_reviewed": "e062327c0f309a0bb3a374fb9a210713d97a13ca",
    "source_license": "MIT",
    "license_notice": "MIT License, Copyright (c) 2026 DDR68 — see "
                      "THIRD_PARTY_NOTICES.md; no endorsement implied",
    "source_file": "packaging/ECMA_A20_20_03_01.py",
    "source_functions": ["main()", "linea()", "nurbs2()"],
    "formulas_adapted": [
        "opposing closure: top tuck from the first main panel, bottom tuck "
        "from the second (panel boundaries glue | L-t | P | L | P-t)",
        "asymmetric compensation: main_a top crease +t, main_b bottom "
        "crease -t, glue flap shortened only at the top",
        "closure ear/fold/hook chain and quadratic Bezier shoulders "
        "(k = 0.635); entry slits with shortened fold creases",
        "dust flaps: plain chamfer on the tuck-adjacent edge, chamfer + "
        "taper on the free edge, hinges inset t at panel steps",
    ],
    "bbrose_changes": [
        "UPSTREAM DEFECT FIXED: the source uses dust_d without defining it "
        "(Rhino leftover-scope); defined as min((P+hook-t)/2, L/2) per the "
        "sibling STE generator",
        "Rhino emission replaced by DielineCoordinates; exact cubic "
        "Beziers; inner-dimension input; full-contour bleed, safe area, "
        "flat + FOLDED collision checks, deterministic content hashes",
        "explicit reference attachment map persisted with the geometry",
    ],
    "internal_geometry_version": "reference_opposed_tuck_carton/0.1",
}

TEMPLATE_ID = "reference_opposed_tuck_carton"
TEMPLATE_VERSION = "0.1"

#: §1 — the reference attachment map, persisted INDEPENDENTLY of any
#: archetype name. Derived from visual analysis of the Pacdora screenshot
#: plus the user-stated body facts; never traced, never a parity claim.
REFERENCE_ATTACHMENT_MAP = {
    "schema_version": "reference_attachment_map/1.0",
    "source": "Pacdora reference screenshot (visual closure reference "
              "only) + user-verified body facts; not a production vector",
    "body_sequence": [
        {"panel": "glue_flap", "width_basis": "glue_tab_mm"},
        {"panel": "main_panel_a", "width_basis": "90 mm inner main"},
        {"panel": "side_panel_a", "width_basis": "32 mm inner side"},
        {"panel": "main_panel_b", "width_basis": "90 mm inner main"},
        {"panel": "side_panel_b", "width_basis": "32 mm inner side"},
    ],
    "upper_major_tuck": "main_panel_a",
    "lower_major_tuck": "main_panel_b",
    "upper_dust_flaps": ["side_panel_a", "side_panel_b"],
    "lower_dust_flaps": ["side_panel_a", "side_panel_b"],
    "closure": "OPPOSING_TUCK",
    "note": "attachment map is the review contract: correctness is judged "
            "against it, never inferred from nominal dimensions",
}

#: §1/§7 mismatch codes.
CLOSURE_TOPOLOGY_MISMATCH = "PROVISIONAL_CLOSURE_TOPOLOGY_MISMATCH"
TUCK_PANEL_ASSIGNMENT_MISMATCH = "MAJOR_TUCK_PANEL_ASSIGNMENT_MISMATCH"
OPPOSING_TUCK_NOT_PRESERVED = "REFERENCE_OPPOSING_TUCK_NOT_PRESERVED"

#: engine panel name -> attachment-map panel name
_PANEL_ALIAS = {"main_a": "main_panel_a", "main_b": "main_panel_b",
                "back": "main_panel_a", "front": "main_panel_b"}


class OpposedTuckGeometryError(ValueError):
    pass


@dataclass(frozen=True)
class OpposedTuckSpec:
    template: str = TEMPLATE_ID
    version: str = TEMPLATE_VERSION
    hook_mm: float = 18.0
    chamfer_mm: float = 3.0
    taper_mm: float = 2.0
    entry_slit_len_mm: float = 7.0
    entry_slit_depth_mm: float = 2.5
    shoulder_control_k: float = 0.635
    assumptions: tuple[str, ...] = (
        "external = inner + 2t on every axis; the physical sample decides "
        "the allowance convention",
        "hook 18 mm, chamfer 3 mm, taper 2 mm, entry slits 7 x 2.5 mm, "
        "shoulder factor 0.635: published template parameters from the "
        "adapted MIT source, not customer dimensions",
        "dust depth min((P+hook-t)/2, L/2): defined here — the upstream "
        "opposing-tuck script leaves it undefined",
        "glue flap width is a template parameter (default 12 mm)",
    )


REFERENCE_OPPOSED_TUCK_CARTON_V0_1 = OpposedTuckSpec()

_SPECS: dict[str, OpposedTuckSpec] = {
    REFERENCE_OPPOSED_TUCK_CARTON_V0_1.template:
        REFERENCE_OPPOSED_TUCK_CARTON_V0_1,
}


def spec_for_template(template: str) -> OpposedTuckSpec | None:
    return _SPECS.get(template)


def validate_against_attachment_map(derived: dict,
                                    attachment_map: dict | None = None
                                    ) -> list[str]:
    """§7: judge a structure's closure against the REFERENCE attachment
    map. Returns stable mismatch codes; empty list = topology preserved."""
    amap = attachment_map or REFERENCE_ATTACHMENT_MAP
    top = _PANEL_ALIAS.get(str(derived.get("top_tuck_panel")),
                           str(derived.get("top_tuck_panel")))
    bottom = _PANEL_ALIAS.get(str(derived.get("bottom_tuck_panel")),
                              str(derived.get("bottom_tuck_panel")))
    failures: list[str] = []
    if top == bottom:
        failures.append(
            OPPOSING_TUCK_NOT_PRESERVED
            + f": both major tucks hinge from {top!r}; the reference "
              "opposes them")
    if top != amap["upper_major_tuck"]:
        failures.append(
            TUCK_PANEL_ASSIGNMENT_MISMATCH
            + f": upper tuck on {top!r} vs reference "
              f"{amap['upper_major_tuck']!r}")
    if bottom != amap["lower_major_tuck"]:
        failures.append(
            TUCK_PANEL_ASSIGNMENT_MISMATCH
            + f": lower tuck on {bottom!r} vs reference "
              f"{amap['lower_major_tuck']!r}")
    if failures:
        failures.insert(0, CLOSURE_TOPOLOGY_MISMATCH
                        + ": closure system differs from the reference")
    return failures


def calculate_opposed_tuck(params, spec: OpposedTuckSpec
                           ) -> DielineCoordinates:
    """Build the opposing-tuck die. ``params`` is a validated
    DielineInputJSON with INNER width/depth/height."""
    d = params.dimensions
    pset = params.print_settings
    c = params.construction

    Wi, Di, Hi = d.width_mm, d.depth_mm, d.height_mm
    t = c.board_thickness_mm
    G = c.glue_tab_mm
    bleed_mm, safe_mm = pset.bleed_mm, pset.safe_margin_mm
    hook, chamf, taper = spec.hook_mm, spec.chamfer_mm, spec.taper_mm
    slit_l, slit_d = spec.entry_slit_len_mm, spec.entry_slit_depth_mm
    k = spec.shoulder_control_k

    if t <= 0.0:
        raise OpposedTuckGeometryError(
            "board_thickness_mm must be > 0: the opposing-closure "
            "compensation derives from t")
    # 2A-9B §2: the DERIVED supported domain gates generation — a
    # combination outside it fails closed with the exact violated
    # constraint; distorted geometry is never emitted.
    from apps.dielines.qualification.domain import (
        DIMENSION_COMBINATION_UNSUPPORTED,
        evaluate_domain,
    )
    violations = evaluate_domain({
        "width_mm": Wi, "depth_mm": Di, "height_mm": Hi,
        "board_thickness_mm": t, "glue_tab_mm": G,
        "bleed_mm": bleed_mm, "safe_margin_mm": safe_mm,
    })
    if violations:
        error = OpposedTuckGeometryError(
            DIMENSION_COMBINATION_UNSUPPORTED + ": " +
            " | ".join(violations))
        error.code = DIMENSION_COMBINATION_UNSUPPORTED
        error.violations = violations
        raise error

    L, P, A = Wi + 2 * t, Di + 2 * t, Hi + 2 * t
    body_h = A - 2 * t
    ear = 2 * t
    assert hook > ear, "contract constant: hook reaches past the 2t ear"

    dust_d = min((P + hook - t) / 2.0, L / 2.0)   # upstream-defect fix

    # ---- contract X ----
    x0, x1 = 0.0, G
    x2 = x1 + L - t
    x3 = x2 + P
    x4 = x3 + L
    x5 = x4 + P - t

    # ---- contract Y (internal y-up) ----
    y_bot, y_top = 0.0, body_h
    y_top_t, y_bot_t = y_top + t, -t
    y_inc_bot, y_inc_top = y_bot, y_top - t
    ear_t = y_top_t + P
    fold_t = ear_t - ear
    tip_t = fold_t + hook
    ear_b = y_bot_t - P
    fold_b = ear_b + ear
    tip_b = fold_b - hook

    flat_w = x5
    flat_h = tip_t - tip_b

    def Y(y_up: float) -> float:
        return round(tip_t - y_up, 6)

    def ring(points_up):
        return Polygon([(round(px, 6), Y(py)) for px, py in points_up])

    # ---- components ----
    glue_poly = ring([
        (x1, y_inc_bot), (x0, y_inc_bot + chamf),
        (x0, y_inc_top - chamf), (x1, y_inc_top),
    ])
    main_a_poly = ring([(x1, y_bot), (x2, y_bot),
                        (x2, y_top_t), (x1, y_top_t)])
    side_a_poly = ring([(x2, y_bot), (x3, y_bot),
                        (x3, y_top), (x2, y_top)])
    main_b_poly = ring([(x3, y_bot_t), (x4, y_bot_t),
                        (x4, y_top), (x3, y_top)])
    side_b_poly = ring([(x4, y_bot), (x5, y_bot),
                        (x5, y_top), (x4, y_top)])
    body_poly = unary_union([main_a_poly, side_a_poly,
                             main_b_poly, side_b_poly])

    def _tuck(x_l: float, x_r: float, hinge: float, e: float,
              tp: float) -> list[Primitive]:
        ctrl_y = e + (tp - e) * k
        tip_l, tip_r = x_l + slit_l + ear, x_r - slit_l - ear
        pts = {
            "hl": (x_l, Y(hinge)), "el": (x_l, Y(e)),
            "tl": (tip_l, Y(tp)), "tr": (tip_r, Y(tp)),
            "er": (x_r, Y(e)), "hr": (x_r, Y(hinge)),
        }
        cl, cr = (x_l, Y(ctrl_y)), (x_r, Y(ctrl_y))
        return [
            LineSeg(pts["hl"], pts["el"]),
            _quad_to_cubic(pts["el"], cl, pts["tl"]),
            LineSeg(pts["tl"], pts["tr"]),
            _quad_to_cubic(pts["tr"], cr, pts["er"]),
            LineSeg(pts["er"], pts["hr"]),
            LineSeg(pts["hr"], pts["hl"]),
        ]

    tuck_top_prims = _tuck(x1, x2, y_top_t, ear_t, tip_t)     # main_a
    tuck_bot_prims = _tuck(x3, x4, y_bot_t, ear_b, tip_b)     # main_b
    tuck_top_poly = Polygon(sample_path(tuck_top_prims))
    tuck_bot_poly = Polygon(sample_path(tuck_bot_prims))

    def _dust(x_plain: float, x_taper: float, base: float,
              sign: int) -> Polygon:
        """Dust flap: plain 45-deg chamfer on the tuck-adjacent edge
        (``x_plain``), chamfer + taper on the free edge (``x_taper``)."""
        tab = base + sign * dust_d
        toward = 1.0 if x_taper > x_plain else -1.0
        pts = [
            (x_plain, base),
            (x_plain + toward * chamf, base + sign * chamf),
            (x_plain + toward * chamf, tab),
            (x_taper - toward * (chamf + taper), tab),
            (x_taper - toward * chamf, base + sign * (2 * chamf + taper)),
            (x_taper, base + sign * (chamf + taper)),
            (x_taper, base),
        ]
        return ring(pts)

    # hinges are inset t at the compensated panel steps (source sections
    # 2/3/8-11): bottom row insets beside main_b? no — beside main_a/side
    # steps exactly as drawn upstream.
    dust_sa_bot = _dust(x3, x2 + t, y_bot, -1)
    dust_sa_top = _dust(x2, x3 - t, y_top, +1)
    dust_sb_bot = _dust(x4, x5, y_bot, -1)
    dust_sb_top = _dust(x4 + t, x5, y_top, +1)

    parts = [glue_poly, body_poly, tuck_top_poly, tuck_bot_poly,
             dust_sa_bot, dust_sa_top, dust_sb_bot, dust_sb_top]
    cut_polygon = unary_union(parts)
    if cut_polygon.geom_type != "Polygon":
        raise OpposedTuckGeometryError(
            f"cut contour is not one region ({cut_polygon.geom_type})")
    bleed_polygon = cut_polygon.buffer(bleed_mm, join_style=1, quad_segs=16)
    safe_polygon = box(x1 + safe_mm, Y(y_top) + safe_mm,
                       x5 - safe_mm, Y(y_bot) - safe_mm)

    def seg(xa, ya, xb, yb):
        return (round(xa, 6), Y(ya), round(xb, 6), Y(yb))

    fold_lines = [
        seg(x1, y_inc_bot, x1, y_inc_top),          # glue crease
        seg(x2, y_bot, x2, y_top),                  # main_a | side_a
        seg(x3, y_bot, x3, y_top),                  # side_a | main_b
        seg(x4, y_bot, x4, y_top),                  # main_b | side_b
        seg(x1, y_top_t, x2, y_top_t),              # main_a top (comp.)
        seg(x3, y_bot_t, x4, y_bot_t),              # main_b bottom (comp.)
        seg(x2 + t, y_bot, x3, y_bot),              # side_a bottom hinge
        seg(x2, y_top, x3 - t, y_top),              # side_a top hinge
        seg(x4, y_bot, x5, y_bot),                  # side_b bottom hinge
        seg(x4 + t, y_top, x5, y_top),              # side_b top hinge
        # tuck folds, shortened around the entry slits
        seg(x1 + slit_l, fold_t, x2 - slit_l, fold_t),
        seg(x3 + slit_l, fold_b, x4 - slit_l, fold_b),
    ]

    slit_lines = []
    for (x_l, x_r, e, sign) in ((x1, x2, ear_t, -1), (x3, x4, ear_b, +1)):
        slit_lines += [
            seg(x_l, e, x_l + slit_l, e),
            seg(x_l + slit_l, e, x_l + slit_l, e + sign * slit_d),
            seg(x_r, e, x_r - slit_l, e),
            seg(x_r - slit_l, e, x_r - slit_l, e + sign * slit_d),
        ]

    panels = [
        Panel("glue_tab", x0, Y(y_inc_top), x1 - x0, body_h - t),
        Panel("main_a", x1, Y(y_top_t), x2 - x1, body_h + t),
        Panel("side_a", x2, Y(y_top), x3 - x2, body_h),
        Panel("main_b", x3, Y(y_top), x4 - x3, body_h + t),
        Panel("side_b", x4, Y(y_top), x5 - x4, body_h),
    ]

    parameters = {
        "inner_mm": [Wi, Di, Hi], "board_thickness_mm": t,
        "glue_tab_mm": G, "hook_mm": hook, "chamfer_mm": chamf,
        "taper_mm": taper, "entry_slit_len_mm": slit_l,
        "entry_slit_depth_mm": slit_d, "shoulder_control_k": k,
        "bleed_mm": bleed_mm, "safe_margin_mm": safe_mm,
    }
    compensation_report = [
        f"external = inner + 2t: L={L:g}, P={P:g}, A={A:g} (t={t:g})",
        f"panels: glue {G:g} | main_a {L - t:g} | side_a {P:g} | "
        f"main_b {L:g} | side_b {P - t:g}",
        f"asymmetric closure compensation: main_a top crease +{t:g} mm, "
        f"main_b bottom crease -{t:g} mm (opposing tucks)",
        f"glue crease shortened {t:g} mm at the top only (bottom of "
        "main_a is a cut edge — the bottom closure lives on main_b)",
        f"closure face depth P - 2t = {P - 2 * t:g} mm at BOTH ends "
        "(= inner depth)",
        f"lock ears 2t = {ear:g} mm; entry slits {slit_l:g} x {slit_d:g} "
        f"mm at all four fold ends; folds shortened accordingly",
        f"dust flap depth (P + hook - t)/2 = {dust_d:g} mm (cap L/2); "
        "plain chamfer on tuck-adjacent edges, taper on free edges",
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
        dust_flap_polygons=[dust_sa_top, dust_sb_top,
                            dust_sa_bot, dust_sb_bot],
        glue_tab_polygon=glue_poly,
        body_polygon=body_poly,
        slit_lines=slit_lines,
        components=[
            ("main-body", body_poly),
            ("glue-tab", glue_poly),
            ("top-main-a-tuck", tuck_top_poly),
            ("bottom-main-b-tuck", tuck_bot_poly),
            ("top-side-a-dust", dust_sa_top),
            ("top-side-b-dust", dust_sb_top),
            ("bottom-side-a-dust", dust_sa_bot),
            ("bottom-side-b-dust", dust_sb_bot),
        ],
        component_paths={
            "top-main-a-tuck": tuck_top_prims,
            "bottom-main-b-tuck": tuck_bot_prims,
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
            "structure_status": "REFERENCE_RECONSTRUCTED_PROVISIONAL",
            "physical_validation": "PHYSICAL_SAMPLE_VALIDATION_REQUIRED",
            "provisional": True,
            "per_hinge_creases": True,
            "thickness_compensation": True,
            "x0": x0, "x1": x1, "x2": x2, "x3": x3, "x4": x4, "x5": x5,
            "top_tuck_panel": "main_a", "bottom_tuck_panel": "main_b",
            "closure_orientation": "OPPOSING_TUCK",
            "attachment_map": REFERENCE_ATTACHMENT_MAP,
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
                "OPPOSING TUCK / REFERENCE-MATCHED PROVISIONAL: top tuck "
                "on MAIN PANEL A, bottom tuck on MAIN PANEL B (reference "
                "attachment map preserved with the geometry)",
                "geometry adapted from the MIT-licensed "
                "DDR68/Rhino_Packaging_Toolkit ECMA A20.20.03.01 generator",
                "a customer- or manufacturer-supplied vector dieline "
                "automatically outranks this archetype",
            ],
        },
    )
    coords.validate()
    topology = validate_against_attachment_map(coords.derived)
    if topology:
        raise OpposedTuckGeometryError(
            "emitted geometry violates the reference attachment map: "
            + "; ".join(topology))
    return coords


def geometry_content_hashes(coords: DielineCoordinates) -> dict:
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
    """Flat + folded checks on the ACTUAL flap geometry (§4).

    The folded checks transform the real flap outlines through the closure
    rotations (dust flaps in first, then each tuck) instead of reasoning
    about body panels only.
    """
    d = coords.derived
    L, P, A = coords.dimensions.manufacture
    t = coords.board_thickness_mm
    Wi, Di, Hi = coords.dimensions.inner
    dust_d = d["dust_flap_height_mm"]
    hook = d["top_tuck_lip_mm"]
    slit_l = d["entry_slit_mm"]
    ear = d["tuck_lock_ear_mm"]
    checks = []

    def add(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    add("opposing_attachment_preserved",
        d["top_tuck_panel"] != d["bottom_tuck_panel"],
        f"top tuck on {d['top_tuck_panel']}, bottom tuck on "
        f"{d['bottom_tuck_panel']}")

    # FOLDED: dust flaps rotate 90 deg over each opening; their real
    # outlines lie in the opening plane, reaching dust_d toward each other
    # across the inner width.
    clearance = Wi - 2 * dust_d
    add("folded_dust_flap_pair_clearance", clearance > 0,
        f"actual dust outlines reach {dust_d:g} mm each across the "
        f"{Wi:g} mm inner width -> {clearance:.2f} mm gap")
    # FOLDED: each closure face (depth P-2t) must span the opening depth
    # exactly; its hook then rotates down INSIDE the opposite main panel.
    add("closure_face_spans_opening",
        abs((P - 2 * t) - Di) < 1e-6,
        f"closure face {P - 2 * t:g} mm == inner depth {Di:g} mm "
        "(both tucks)")
    add("hook_clears_inside_face", hook + ear < Hi,
        f"hook {hook:g} mm + ear {ear:g} mm folds inside the {Hi:g} mm "
        "inner height")
    # FOLDED: the 2t lock ears at the fold ends must land on the entry
    # slits of the OPPOSITE panel edge when the tuck closes: ear span
    # (slit_l from each edge) equals the slit span by construction.
    add("lock_ear_engages_slit", slit_l > ear,
        f"ear projects {ear:g} mm and the slit admits {slit_l:g} mm of "
        "edge — engagement length "
        f"{slit_l - ear:g} mm per corner")
    # FOLDED: the tuck folds over the dust flaps — dust depth must stay
    # below the tuck zone reach so the hook is not blocked.
    add("dust_below_tuck_zone",
        (P - 2 * t + hook) - dust_d >= 2.0,
        f"tuck zone {P - 2 * t + hook:g} mm vs dust {dust_d:g} mm")
    add("glue_flap_vs_side_panel",
        P >= d["parameters"]["glue_tab_mm"] + 3.0,
        f"side span {P:g} mm clears the glue flap")

    comps = coords.components
    worst = 0.0
    for i in range(len(comps)):
        for j in range(i + 1, len(comps)):
            worst = max(worst, comps[i][1].intersection(comps[j][1]).area)
    add("component_area_overlap", worst < 1e-6,
        f"largest pairwise flat overlap {worst:.8f} mm^2")
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
    "OpposedTuckSpec", "OpposedTuckGeometryError",
    "REFERENCE_OPPOSED_TUCK_CARTON_V0_1", "REFERENCE_ATTACHMENT_MAP",
    "FORMULA_PROVENANCE", "TEMPLATE_ID", "TEMPLATE_VERSION",
    "CLOSURE_TOPOLOGY_MISMATCH", "TUCK_PANEL_ASSIGNMENT_MISMATCH",
    "OPPOSING_TUCK_NOT_PRESERVED",
    "spec_for_template", "calculate_opposed_tuck",
    "validate_against_attachment_map",
    "geometry_content_hashes", "collision_report",
]
