"""VQR-1 — the owner-accepted M3 structural backbone in production.

The owner rejected the reconstruction's coarse parametric geometry while the
ACCEPTED VQ-1 M3 fit (identity PNG sha256 4ecc8e9df1d1…, frozen fit sha256
a407ef38…) sat unused in ``docs/visual_quality/vq1_master``. This module
wires that frozen fit into ``reconstruct_container`` for the standard
Bottle + dropper profile:

* the GLASS component becomes the body silhouette;
* the COLLAR and DARK_CLOSURE components become the real dropper assembly
  (collar band + bulb) — no generic cap block;
* geometry is emitted as TRUE cubic curves transformed from the fit, never
  re-derived, never densified into polylines.

The fit is a HALF-WIDTH profile in source-image pixels (x = distance from
the centerline at row y). It maps into the confirmed profile's local mm box
with an anisotropic linear transform: the confirmed ``width_mm`` /
``height_mm`` are the human-confirmed reconstruction controls (2C dimension
amendments made them owner-authoritative), so the accepted CURVE CHARACTER
carries over while the confirmed dimensions govern extent. The transform is
linear, so cubic control points map exactly.

Fail-closed rules:

* the frozen fit is hash-verified on every load — drift raises
  ``M3GeometryDrift`` (VQR1_M3_GEOMETRY_DRIFT) and the reconstruction fails
  honestly instead of silently regenerating different geometry;
* only Bottle + dropper uses M3 (that is the accepted archetype); every
  other archetype/closure keeps the parametric builder — no false claim of
  accepted geometry where none exists;
* [no rollback: the switch ``settings.CONTAINER_STRUCTURAL_BACKBONE = "parametric"``,
  which sent the dropper back to the parametric builder, was removed on the
  owner's word of 2026-10-03 (his Q8) — M3 is the dropper's one engine.]

M3 remains CONCEPT_VISUAL_GEOMETRY_ONLY — not manufacturing geometry.
"""
from __future__ import annotations
from apps.pipeline.targets.container import archetypes as _declared

import hashlib
import json
from pathlib import Path

from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo

from .silhouettes import ContainerBackbone, ContainerProfile, build_backbone

M3_FIT_PATH = (Path(__file__).resolve().parents[4] / "docs"
               / "visual_quality" / "vq1_master" / "master_fit_m3.json")
M3_FIT_SHA256 = ("a407ef385d40a462712d5183ec7a4dabf3ea3c9b89719f37f3964cee"
                 "c1c27f41")
M3_IDENTITY_PNG = "4ecc8e9df1d1"
M3_SOURCE = "vq1_m3_master_fit"
VQR1_M3_GEOMETRY_DRIFT = "VQR1_M3_GEOMETRY_DRIFT"

# closure component names recorded in the design graph — the VQR-2A closure
# axis requires exactly this structural evidence for a dropper
DROPPER_COMPONENTS = ("collar", "bulb")


class M3GeometryDrift(ValueError):
    """The frozen M3 fit changed on disk. Never rebuild over drifted
    geometry — fail the reconstruction and surface the code."""

    code = VQR1_M3_GEOMETRY_DRIFT


_FIT_CACHE: dict = {}


def load_m3_fit() -> dict:
    """The frozen fit, hash-verified byte-for-byte on first load."""
    if "fit" not in _FIT_CACHE:
        raw = M3_FIT_PATH.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != M3_FIT_SHA256:
            raise M3GeometryDrift(
                f"{VQR1_M3_GEOMETRY_DRIFT}: master_fit_m3.json sha256 "
                f"{digest[:12]} != frozen {M3_FIT_SHA256[:12]}")
        _FIT_CACHE["fit"] = json.loads(raw)
    return _FIT_CACHE["fit"]


def _component_outline(comp: dict, *, cx: float, sx: float, sy: float,
                       y0: float) -> list:
    """A closed, symmetric outline for one half-width component.

    Right side follows the fitted cubics top→bottom; a straight base edge
    crosses to the mirrored left side, which retraces the cubics
    bottom→top with negated half-widths; a straight top edge closes.
    Control points transform linearly — the accepted curves survive
    exactly.
    """
    def R(hw, y):                     # right-side map
        return (cx + hw * sx, (y - y0) * sy)

    def L(hw, y):                     # mirrored left-side map
        return (cx - hw * sx, (y - y0) * sy)

    start = comp["start"]
    segs = comp["segments"]
    sx0, sy0 = R(*start)
    out = [MoveTo(x=sx0, y=sy0)]
    prev = start
    for c1, c2, p3 in segs:
        (c1x, c1y), (c2x, c2y), (ex, ey) = R(*c1), R(*c2), R(*p3)
        out.append(CubicTo(x1=c1x, y1=c1y, x2=c2x, y2=c2y, x=ex, y=ey))
        prev = p3
    # base edge to the mirrored side
    mx, my = L(*prev)
    out.append(LineTo(x=mx, y=my))
    # left side retraces the cubics in reverse
    points = [start] + [s[2] for s in segs]
    for i in range(len(segs) - 1, -1, -1):
        c1, c2, _ = segs[i]
        (c2x, c2y), (c1x, c1y), (tx, ty) = L(*c2), L(*c1), L(*points[i])
        out.append(CubicTo(x1=c2x, y1=c2y, x2=c1x, y2=c1y, x=tx, y=ty))
    out.append(ClosePath())
    return out


def build_m3_dropper_backbone(p: ContainerProfile) -> ContainerBackbone:
    """The accepted M3 assembly in the profile's local mm box (y-down,
    0..width_mm × 0..height_mm) behind the standard ContainerBackbone
    interface — the composer needs no new vocabulary."""
    fit = load_m3_fit()
    W, H = p.width_mm, p.height_mm
    cx = W / 2.0
    span0, span1 = fit["assembly_span_px"]
    sy = H / float(span1 - span0)
    glass = fit["fits"]["GLASS"]
    # normalize so the emitted BODY spans exactly the confirmed width
    max_hw = max(
        [glass["start"][0]] + [pt[0] for seg in glass["segments"]
                               for pt in seg])
    sx = (W / 2.0) / float(max_hw)

    kw = dict(cx=cx, sx=sx, sy=sy, y0=span0)
    silhouette = _component_outline(glass, **kw)
    collar = _component_outline(fit["fits"]["COLLAR"], **kw)
    bulb = _component_outline(fit["fits"]["DARK_CLOSURE"], **kw)

    # body band (mm) from the GLASS band — label/anchors use the same
    # fractions as the parametric dropper builder so artwork placement
    # stays byte-comparable in character
    y_body = (glass["band_px"][0] - span0) * sy
    body_h = H - y_body
    g = p.closure_geometry or {}
    base_t = float(g.get("base_thickness", 0.05 * H))
    lw, lh = W * 0.67, body_h * 0.59
    label = p.label_zone or (cx - lw / 2, y_body + body_h * 0.15, lw, lh)
    lx, ly, _lw, _lh = label
    return ContainerBackbone(
        "bottle", W, H, silhouette, collar, label, p.decoration_zone,
        anchors={"logo": (cx, ly + lh * 0.12),
                 "product_name": (cx, ly + lh * 0.44)},
        collar_region=collar, bulb_region=bulb,
        base_band_mm=base_t)


def _uses_m3(profile: ContainerProfile) -> bool:
    # his Q8 of 2026-10-03: no rollback switch — a Bottle + dropper is drawn on M3, always
    return ((profile.archetype or "").lower() == "bottle"
            and (profile.cap_style or "").lower() == "dropper")


def build_container_backbone(profile: ContainerProfile):
    """(backbone, structure_record) — the ONE production selector.

    Bottle + dropper → the accepted M3 assembly, always (its rollback flag
    was removed, 2026-10-03, his Q8). Everything else → the legacy parametric builder,
    with an honest record that NO accepted structural geometry backs it
    (the VQR-2A closure axis then stays UNMEASURED rather than passing a
    generic block).
    """
    if _uses_m3(profile) and profile.outline is not None and profile.outline.get("kind") == "profile":
        # [his goal for the pitch, 2026-10-15, B (9): "Shapes from the concept, not crude templates (126's bottle)"] a
        # dropper whose concept was traced is drawn in its concept's own outline — its bottle, its collar and its
        # bulb as the picture shows them (silhouettes._traced_elevation); M3 where no trace reached it
        return build_backbone(profile), {
            "backbone_source": "concept_trace",
            "geometry_authority": "CONCEPT_VISUAL_GEOMETRY_ONLY",
            "closure_assembly": {"family": "dropper", "components": ["collar", "bulb"],
                                 "source": "the concept's own traced outline",
                                 "assembly_scope": "VISIBLE_DROPPER_FROM_CONCEPT"},
        }
    if _uses_m3(profile):
        backbone = build_m3_dropper_backbone(profile)
        record = {
            "backbone_source": M3_SOURCE,
            "fit_sha256": M3_FIT_SHA256[:16],
            "identity_sha256_png": M3_IDENTITY_PNG,
            "geometry_authority": "CONCEPT_VISUAL_GEOMETRY_ONLY",
            "closure_assembly": {
                "family": "dropper",
                "components": list(DROPPER_COMPONENTS),
                "source": M3_SOURCE,
                # owner correction (2026-08-03): honest scope language —
                # this is the VISIBLE assembly the accepted fixture
                # contains, never a fully decomposed technical dropper
                "assembly_scope": "M3_VISIBLE_DROPPER_ASSEMBLY",
                "scope_notes": [
                    "no internal pipette exists in the accepted M3 fixture",
                    "shoulder and neck are contained within the GLASS "
                    "contour, not separate editable objects",
                    "this is not a fully decomposed engineering dropper "
                    "assembly — visible structural geometry only",
                ],
            },
        }
        return backbone, record
    return build_backbone(profile), {
        "backbone_source": "parametric",
        "closure_assembly": None,
    }


#: §BH48(b) / §BH49(a): THE ONE MILLIMETRE ANCHOR — the ruling's 31.5 mm on the GLASS body's full width, the one
#: isotropic scale `m3_profile_geometry` derives the profile from. It lived in container_profile_fit.py (the REFIT
#: fitter) until the clean-up of 2026-10-04 removed REFIT on the owner's word; it moved here first, its value
#: unchanged — §BH49's hard stop "the anchor moving" stands (pinned: test_container_confirmation_2c2e.py).
ANCHOR_MM = 31.5
#: §BH48(b)(ii): the record the M3-drawn reconstruction carries
DRAWING_SOURCE_SCHEMA = "container_drawing_source/1.0"
DRAWING_PARAMETRIC = "PARAMETRIC"        # the typed numbers through `_bottle_group` — by declaration only (§BH49(a))
DRAWING_M3_FIT = "M3_FIT"                # the accepted fit's own outlines — the product's source by construction
#: REFIT (§BH49(a)(i), the fitter's proposal drawn through the parametric group) left the tree with its fitter in
#: the clean-up of 2026-10-04 (git history keeps both); a record still declaring it is refused by name below
DRAWING_SOURCES = (DRAWING_M3_FIT, DRAWING_PARAMETRIC)
DRAWING_SOURCE_UNKNOWN = "CONTAINER_DRAWING_SOURCE_UNKNOWN"
#: §BH49(b) staged the five geometry rules the M3 drawing refused on and held such a reconstruction at
#: REFUSED_PENDING_RULING until the owner ruled. §BH50(a) is that ruling: the five are re-ruled to the M3
#: render's measured values (apps/ire/container_concept_fidelity.py, RE_RULED_GEOMETRY_CODES), so the
#: pending status and its code list are retired; a render the re-ruled rules refuse is BLOCKED like any other.


def drawing_source_of(spec: dict) -> str:
    """§BH49(a): M3_FIT BY CONSTRUCTION — the product path draws from the accepted fit unless the
    task's record DECLARES another source. PARAMETRIC (the typed numbers) is reachable only by that
    declaration; a declaration naming anything else is refused by name rather than read as one of
    them — REFIT too, since the clean-up of 2026-10-04 removed it. Nothing is inferred."""
    rec = spec.get(DRAWING_SOURCE_SCHEMA)
    if not isinstance(rec, dict) or "source" not in rec:
        return DRAWING_M3_FIT
    source = rec.get("source")
    if source in DRAWING_SOURCES:
        return source
    raise ValueError(f"{DRAWING_SOURCE_UNKNOWN}: {source!r} is not one of {DRAWING_SOURCES}")


def _max_half_width(comp: dict) -> float:
    return max([comp["start"][0]] + [pt[0] for seg in comp["segments"] for pt in seg])


def m3_profile_geometry(anchor_mm: float, retained: dict, archetype: str
                        ) -> tuple[ContainerProfile, dict, dict]:
    """§BH61(b)(c): BOTTLE-ONLY, and it says so.

    Every input is a dropper bottle's — collar diameter, base thickness, shoulder radius, frost, translucency —
    and the ContainerProfile it returns is a dropper's. It used to mint `archetype="bottle"` from whatever it
    was called with; it now declares its scope and refuses another form by name at entry. Its three production
    callers (`targets/container/__init__.py:1319`, `apps/ire/compose_dropper.py`, `apps/dashboard/
    exploration_render.py`) are all on the dropper path and pass nothing else.
    [§BH70(1): and the form is NOT DEFAULTED. It read `archetype: str = "bottle"`, so a caller that passed none was
    let through as a bottle — the design loop called it so, and a record that said compact but carried a dropper's
    numbers was drawn as the dropper, with no refusal. Every caller now passes the form its record names.]
    """
    _declared.require_scope("m3_profile_geometry", archetype, serves=("bottle",))
    """§BH48(b)(ii) — M3 DRAWS: the parametric profile DERIVED from the accepted fit.

    One anchor, ``anchor_mm`` on the GLASS body's full width (the ruling's 31.5 mm); one
    isotropic scale from it; every height from the fit's component bands, every width from
    its half-widths, in the fit's own pixels. Nothing here is the human-typed extension
    number — those are the PARAMETRIC source's. ``retained`` supplies the values a silhouette
    does not hold (base thickness, frost, translucency) and the record says so per field.
    Returns (profile, geometry, derivation): the profile whose box the outlines fill
    isotropically, the geometry dict the sheet lays out from, and the derivation record.
    """
    fit = load_m3_fit()
    span0, span1 = fit["assembly_span_px"]
    glass, collar, bulb = fit["fits"]["GLASS"], fit["fits"]["COLLAR"], fit["fits"]["DARK_CLOSURE"]
    body_hw = _max_half_width(glass)
    scale = float(anchor_mm) / (2.0 * body_hw)                 # mm per px, the one anchor
    def mm(px): return round(float(px) * scale, 3)
    total_h = mm(span1 - span0)
    bulb_h = mm(bulb["band_px"][1] - bulb["band_px"][0])
    collar_h = mm(collar["band_px"][1] - collar["band_px"][0])
    # the glass begins inside the collar's band (the neck transition is hidden by the collar):
    # the visible neck is the glass above the collar's bottom edge, never negative
    hidden = collar["band_px"][1] - glass["band_px"][0]
    visible_neck = mm(max(0, -hidden))
    body_h = mm(span1 - collar["band_px"][1])
    geometry = {
        "total_height_mm": total_h, "body_height_mm": body_h, "body_diameter_mm": float(anchor_mm),
        "collar_height_mm": collar_h, "bulb_height_mm": bulb_h,
        "collar_diameter_mm": mm(2.0 * _max_half_width(collar)),
        "neck_diameter_mm": mm(2.0 * glass["start"][0]),
        "visible_neck_mm": visible_neck,
        "bulb_width_mm": mm(2.0 * _max_half_width(bulb)),
        "base_thickness_mm": float(retained["base_thickness_mm"]),
        "shoulder_radius_mm": float(retained["shoulder_radius_mm"]),
        "frost_intensity": float(retained["frost_intensity"]),
        "translucency": float(retained["translucency"]),
    }
    profile = ContainerProfile(archetype="bottle", variant="cylindrical", cap_style="dropper",
                               height_mm=total_h, width_mm=float(anchor_mm),
                               neck_ratio=round(glass["start"][0] / body_hw, 4),
                               closure_geometry={"collar_h": collar_h, "bulb_h": bulb_h,
                                                 "collar_w": geometry["collar_diameter_mm"],
                                                 "base_thickness": geometry["base_thickness_mm"],
                                                 "shoulder_radius": geometry["shoulder_radius_mm"]})
    derivation = {
        "schema_version": DRAWING_SOURCE_SCHEMA, "source": DRAWING_M3_FIT,
        "fit_sha256": M3_FIT_SHA256[:16], "identity_sha256_png": M3_IDENTITY_PNG,
        "anchor_mm": float(anchor_mm), "anchor_on": "the GLASS component's full width in the fit's pixels",
        "scale_mm_per_px": round(scale, 6), "isotropic": True,
        "bands_px": {"bulb": bulb["band_px"], "collar": collar["band_px"], "glass": glass["band_px"],
                     "span": [span0, span1], "hidden_neck_px": hidden},
        "field_sources": {k: ("RETAINED_FROM_CONFIRMED" if k in ("base_thickness_mm", "shoulder_radius_mm", "frost_intensity", "translucency")
                              else ("ANCHOR" if k == "body_diameter_mm" else "M3_FIT")) for k in geometry},
        "geometry": geometry,
    }
    return profile, geometry, derivation
