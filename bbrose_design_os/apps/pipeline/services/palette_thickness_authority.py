"""PALT-M4B-A3R — wall-thickness measurement authority.

A3 reported a 0.663 mm minimum from a single plane-sampling method whose
result moved with sampling density. That is diagnostic evidence, not
approval evidence. This module establishes three INDEPENDENT methods and
requires two of them to agree before any region is classified.

Geometry is frozen. Nothing here mutates a mesh.

§8 thickness semantics — these are NOT interchangeable:

``LOCAL_NORMAL_THICKNESS``
    distance from a surface point along its own inward normal to the first
    opposing surface. What a moulder means by "wall".
``MINIMUM_MATERIAL_LIGAMENT``
    diameter of the largest inscribed circle/sphere at a point — the
    narrowest material bridge, which can be smaller than the normal
    thickness where two surfaces converge obliquely.
``SECTION_HORIZONTAL_THICKNESS`` / ``SECTION_VERTICAL_THICKNESS``
    the material interval along a section axis. Direction-dependent and
    always >= the normal thickness.
``ANALYTICAL_NOMINAL_THICKNESS``
    closed-form thickness where the surfaces are known offsets.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "palette_thickness_authority/1.0"

THICKNESS_DEFINITIONS = {
    "LOCAL_NORMAL_THICKNESS": "surface point -> first opposing surface "
                              "along the inward surface normal",
    "MINIMUM_MATERIAL_LIGAMENT": "diameter of the largest inscribed circle "
                                 "at the point",
    "SECTION_HORIZONTAL_THICKNESS": "material interval along the section "
                                    "horizontal axis",
    "SECTION_VERTICAL_THICKNESS": "material interval along the section "
                                  "vertical axis",
    "ANALYTICAL_NOMINAL_THICKNESS": "closed form from the construction",
}

# which definition each moulding policy is measured against (§8)
POLICY_CONTROLLING_DEFINITION = {
    "MINIMUM_LOCAL_WALL": "LOCAL_NORMAL_THICKNESS",
    "POCKET_WALL": "LOCAL_NORMAL_THICKNESS",
    "DECK_LIGAMENT": "SECTION_HORIZONTAL_THICKNESS",
    "BASE_SKIN": "ANALYTICAL_NOMINAL_THICKNESS",
    "POCKET_FLOOR": "ANALYTICAL_NOMINAL_THICKNESS",
    "MAXIMUM_THICKNESS_RATIO": "MINIMUM_MATERIAL_LIGAMENT",
}

RAY_PARAMS = {
    "version": "normal_ray_thickness/1.0",
    "sample_pattern": "FACE_CENTROID_PLUS_FIXED_BARYCENTRIC",
    "barycentric": [[1 / 3, 1 / 3, 1 / 3],
                    [0.6, 0.2, 0.2], [0.2, 0.6, 0.2], [0.2, 0.2, 0.6]],
    "normal_method": "FACE_WINDING_CROSS_PRODUCT_UNIT",
    "ray_epsilon_mm": 1e-6,
    "max_ray_distance_mm": 12.0,
    "adjacency_exclusion_depth": 1,      # source face + any vertex-sharing
    # the ray EXITS the material through the opposing face, so that
    # face's outward normal points ALONG the ray, not against it
    "opposing_face_cos": 0.20,
    "intersection_ordering": "ASCENDING_T_THEN_ASCENDING_FACE_INDEX",
    "ambiguity_relative_tolerance": 0.02,
    "coordinate_quantization": 1e-6,
    "acceleration": "UNIFORM_BUCKET_GRID/1.0",
    "bucket_mm": 3.0,
    "ambiguity_policy": "REPORT_AS_SURFACE_PAIRING_AMBIGUITY_NOT_A_VALUE",
}

CONVERGENCE = {
    "version": "thickness_convergence/1.0",
    "levels_planes_per_family": [5, 9, 13, 21, 33, 49],
    "levels_ray_samples_per_face": [1, 2, 4],
    # declared BEFORE any result is observed
    "minimum_tolerance_mm": 0.02,
    "coordinate_tolerance_mm": 0.50,
    "stable_levels_required": 3,
}

FEATURE_CLASSES = (
    "POCKET_WALL", "POCKET_FLOOR", "RIM_FILLET", "FLOOR_FILLET",
    "DECK_SKIN", "OUTER_WALL", "BASE_SKIN", "CORE_TRANSITION",
    "CORNER_TRANSITION", "SURFACE_PAIRING_AMBIGUITY", "SAMPLING_ARTIFACT",
    "UNKNOWN")

MAX_CLASSIFICATIONS = (
    "CONFIRMED_PHYSICAL_THICK_REGION", "INCORRECT_OPPOSING_SURFACE_PAIR",
    "LONG_PATH_NOT_LOCAL_WALL_THICKNESS",
    "RAY_MISSED_INTENDED_OPPOSING_SURFACE",
    "CORNER_OR_PERIMETER_SOLID_MASS", "CORE_TRANSITION_THICK_REGION",
    "SECTION_DEGENERACY_ARTIFACT", "UNRESOLVED")

# §7: the maximum policy controls MAXIMUM_LOCAL_WALL_THICKNESS and must NOT
# be driven by LONGEST_MATERIAL_PATH. A normal ray can run a long way
# through a THIN sheet when it happens to start on a surface whose normal
# lies in the plane of the sheet — the two faces are genuinely antiparallel
# but they are not the two boundaries of one wall. The discriminator is the
# inscribed sphere at the ray MIDPOINT: inside a real slab of thickness t
# the midpoint sits t/2 from the surface; inside a thin sheet crossed
# lengthwise it sits a fraction of that.
LOCAL_WALL_MIDPOINT_RATIO = 0.60


def midpoint_inscribed_diameter(mesh, a, b, *, cell=3.0):
    """Twice the distance from the segment midpoint to the nearest face."""
    v = np.asarray(mesh["vertices"], float)
    f = np.asarray(mesh["faces"], np.int64)
    mid = (np.asarray(a, float) + np.asarray(b, float)) / 2.0
    tri = v[f]
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    near = np.all((lo <= mid + 8.0) & (hi >= mid - 8.0), axis=1)
    idx = np.nonzero(near)[0]
    if not len(idx):
        idx = np.arange(len(f))
    best = np.inf
    for fi in idx:
        p0, p1, p2 = v[f[fi]]
        e0, e1 = p1 - p0, p2 - p0
        n = np.cross(e0, e1)
        ln = np.linalg.norm(n)
        if ln < 1e-14:
            continue
        n = n / ln
        d = abs(float((mid - p0) @ n))
        proj = mid - ((mid - p0) @ n) * n
        # barycentric containment, else fall back to the vertices
        d00, d01, d11 = e0 @ e0, e0 @ e1, e1 @ e1
        w = proj - p0
        d20, d21 = w @ e0, w @ e1
        den = d00 * d11 - d01 * d01
        if abs(den) > 1e-14:
            u = (d11 * d20 - d01 * d21) / den
            vv = (d00 * d21 - d01 * d20) / den
            if u >= -1e-9 and vv >= -1e-9 and u + vv <= 1 + 1e-9:
                best = min(best, d)
                continue
        best = min(best, float(np.linalg.norm(v[f[fi]] - mid, axis=1).min()))
    return 2.0 * best


def classify_maximum(mesh, sample) -> dict:
    """Is a large normal-ray value a real wall, or a long path?"""
    a = np.asarray(sample["point"], float)
    d = -np.asarray(sample["source_normal"], float)
    b = a + d * sample["thickness_mm"]
    inscribed = midpoint_inscribed_diameter(mesh, a, b)
    ratio = inscribed / sample["thickness_mm"] if sample["thickness_mm"] \
        else FT.traced_zero("palette_thickness_authority.py:classify_maximum", "guard")
    local = ratio >= LOCAL_WALL_MIDPOINT_RATIO
    return {
        "ray_length_mm": sample["thickness_mm"],
        "midpoint_inscribed_diameter_mm": round(float(inscribed), 6),
        "midpoint_ratio": round(float(ratio), 6),
        "threshold": LOCAL_WALL_MIDPOINT_RATIO,
        "definition": "MAXIMUM_LOCAL_WALL_THICKNESS" if local
                      else "LONGEST_MATERIAL_PATH",
        "classification": "CONFIRMED_PHYSICAL_THICK_REGION" if local
                          else "LONG_PATH_NOT_LOCAL_WALL_THICKNESS",
        "counts_toward_maximum_policy": bool(local),
    }


def authoritative_maximum(mesh, ray_report) -> dict:
    """Largest LOCAL WALL thickness, long paths excluded and reported."""
    kept, rejected = [], []
    for s in sorted(ray_report["samples"],
                    key=lambda r: -r["thickness_mm"]):
        got = classify_maximum(mesh, s)
        (kept if got["counts_toward_maximum_policy"] else rejected).append(
            {**s, **got})
        if len(kept) >= 1 and len(rejected) >= 40:
            break
    return {"record_type": "authoritative_maximum/1.0",
            "definition": "MAXIMUM_LOCAL_WALL_THICKNESS",
            "excluded_definition": "LONGEST_MATERIAL_PATH",
            "maximum_local_wall_mm": kept[0]["thickness_mm"] if kept
            else None,
            "maximum_sample": kept[0] if kept else None,
            "longest_material_path_mm": ray_report["maximum_mm"],
            "rejected_long_paths": rejected[:10],
            "rejected_count": len(rejected)}


CLASSIFICATIONS = (
    "CONFIRMED_PHYSICAL_THIN_REGION", "NUMERICAL_SAMPLING_ARTIFACT",
    "INCORRECT_OPPOSING_SURFACE_PAIR", "SECTION_DEGENERACY_ARTIFACT",
    "FILLET_OR_TANGENCY_SINGULARITY", "UNRESOLVED")


class ThicknessAuthorityError(ValueError):
    """Raised when a measurement cannot be made unambiguously."""


# ---------------------------------------------------------------------------
# Method A — analytical


def analytical_offset_wall(offset_mm, arc_centre_r, arc_centre_z, arc_radius,
                           z):
    """Normal thickness of a RADIALLY offset wall against a fillet arc.

    A cup profile generated as ``r_cavity(z) + w`` is offset in RADIUS, not
    along the surface normal. On an arc the two differ by the cosine of the
    angle between the radial direction and the surface normal, so the true
    wall is ``w * cos(theta)`` and collapses to zero where the arc becomes
    horizontal.
    """
    dz = z - arc_centre_z
    if abs(dz) > arc_radius + 1e-9:
        return None
    dr = math.sqrt(max(arc_radius * arc_radius - dz * dz, 0.0))
    cos_theta = dr / arc_radius
    return {"definition": "ANALYTICAL_NOMINAL_THICKNESS",
            "cavity_radius_mm": round(arc_centre_r + dr, 9),
            "radial_offset_mm": offset_mm,
            "normal_thickness_mm": round(offset_mm * cos_theta, 9),
            "obliquity_deg": round(math.degrees(math.acos(
                min(1.0, max(-1.0, cos_theta)))), 6)}


def analytical_slab(a, b):
    return {"definition": "ANALYTICAL_NOMINAL_THICKNESS",
            "normal_thickness_mm": round(abs(b - a), 9)}


def analytical_tray(tray) -> dict:
    """Closed-form thickness of every region defined by known offsets."""
    e = tray["elevations_mm"]
    p = tray["pockets"][0]
    wall = tray["core"]["cup_wall_mm"]
    floor_fillet = tray["fillets_mm"]["floor"]
    # floor-fillet arc centre, from the pocket construction
    th = math.radians(tray["draft"]["pocket_draft_deg"])
    c_z = e["pocket_floor"] + floor_fillet
    c_r = p["flat_floor_radius_mm"]
    scan = []
    z = e["pocket_floor"]
    while z <= c_z + 1e-9:
        got = analytical_offset_wall(wall, c_r, c_z, floor_fillet, z)
        if got:
            scan.append({"z_mm": round(z, 6), **got})
        z += 0.025
    worst = min(scan, key=lambda r: r["normal_thickness_mm"]) if scan else None
    return {
        "record_type": "analytical_thickness/1.0",
        "method": "A_ANALYTICAL",
        "regions": {
            "base_skin_pocket_floor": analytical_slab(e["underside"],
                                                      e["pocket_floor"]),
            "deck_skin": analytical_slab(e["core_ceiling"], e["deck"]),
            "straight_pocket_wall": {
                "definition": "ANALYTICAL_NOMINAL_THICKNESS",
                "normal_thickness_mm": round(wall * math.cos(th), 9),
                "note": "the straight drafted run is offset radially too, "
                        "so its true normal wall is w*cos(draft)"},
            "outer_perimeter_wall": {
                "definition": "ANALYTICAL_NOMINAL_THICKNESS",
                "normal_thickness_mm": tray["core"]["perimeter_wall_mm"]},
        },
        "floor_fillet_scan": scan,
        "worst_floor_fillet": worst,
        "analytical_minimum_mm": worst["normal_thickness_mm"] if worst
        else None,
        "cause": (
            "the cup profile is generated by offsetting the pocket profile "
            "in RADIUS. On the floor fillet the surface normal turns away "
            "from radial, so the delivered wall is w*cos(obliquity) and "
            "falls below the nominal w."),
    }


# ---------------------------------------------------------------------------
# Method B — surface-normal ray thickness


def _face_normals(v, f):
    a = v[f[:, 0]]
    n = np.cross(v[f[:, 1]] - a, v[f[:, 2]] - a)
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 1e-14
    n[ok] /= ln[ok][:, None]
    return n, ln / 2.0


def _buckets(v, f, cell):
    tri = v[f]
    lo = np.floor(tri.min(axis=1) / cell).astype(np.int64)
    hi = np.floor(tri.max(axis=1) / cell).astype(np.int64)
    table = {}
    for i in range(len(f)):
        for x in range(lo[i, 0], hi[i, 0] + 1):
            for y in range(lo[i, 1], hi[i, 1] + 1):
                for z in range(lo[i, 2], hi[i, 2] + 1):
                    table.setdefault((x, y, z), []).append(i)
    return table


def _ray_faces(orig, direction, v, f, cand, params):
    """Möller-Trumbore over candidate faces; returns sorted (t, face)."""
    if not len(cand):
        return []
    tri = v[f[cand]]
    e1 = tri[:, 1] - tri[:, 0]
    e2 = tri[:, 2] - tri[:, 0]
    pv = np.cross(direction, e2)
    det = np.einsum("ij,ij->i", e1, pv)
    ok = np.abs(det) > 1e-14
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tvec = orig - tri[:, 0]
    u = np.einsum("ij,ij->i", tvec, pv) * inv
    qv = np.cross(tvec, e1)
    w = (qv @ direction) * inv
    t = np.einsum("ij,ij->i", e2, qv) * inv
    eps = params["ray_epsilon_mm"]
    hit = (ok & (u >= -1e-9) & (w >= -1e-9) & (u + w <= 1 + 1e-9)
           & (t > eps) & (t <= params["max_ray_distance_mm"]))
    out = [(float(t[i]), int(cand[i])) for i in np.nonzero(hit)[0]]
    out.sort(key=lambda r: (round(r[0], 9), r[1]))   # deterministic order
    return out


def normal_ray_thickness(mesh, *, samples_per_face=1, params=None,
                         face_filter=None) -> dict:
    """LOCAL_NORMAL_THICKNESS at deterministic surface samples."""
    prm = dict(RAY_PARAMS)
    prm.update(params or {})
    v = np.asarray(mesh["vertices"], float)
    f = np.asarray(mesh["faces"], np.int64)
    n, area = _face_normals(v, f)
    cell = prm["bucket_mm"]
    table = _buckets(v, f, cell)
    bary = prm["barycentric"][:max(1, samples_per_face)]
    idx = np.arange(len(f)) if face_filter is None else np.asarray(face_filter)

    results = []
    ambiguous = 0
    for fi in idx:
        if area[fi] < 1e-12:
            continue
        nrm = n[fi]
        share = set(f[fi].tolist())
        for bc in bary:
            p = (bc[0] * v[f[fi, 0]] + bc[1] * v[f[fi, 1]]
                 + bc[2] * v[f[fi, 2]])
            d = -nrm                      # inward
            key = tuple(np.floor(p / cell).astype(np.int64))
            cand = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        cand.update(table.get((key[0] + dx, key[1] + dy,
                                               key[2] + dz), ()))
            # walk the ray a few buckets deeper
            for step in range(1, 5):
                q = p + d * (step * cell)
                k2 = tuple(np.floor(q / cell).astype(np.int64))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            cand.update(table.get((k2[0] + dx, k2[1] + dy,
                                                   k2[2] + dz), ()))
            cand.discard(int(fi))
            cand = [c for c in cand if not (share & set(f[c].tolist()))]
            hits = _ray_faces(p, d, v, f, np.asarray(sorted(cand),
                                                     dtype=np.int64), prm)
            opposing = [(t, c) for t, c in hits
                        if float(n[c] @ d) > prm["opposing_face_cos"]]
            if not opposing:
                continue
            t0, c0 = opposing[0]
            amb = False
            if len(opposing) > 1:
                t1 = opposing[1][0]
                if abs(t1 - t0) <= prm["ambiguity_relative_tolerance"] * t0:
                    amb = True
                    ambiguous += 1
            results.append({"point": [round(float(x), 6) for x in p],
                            "source_face": int(fi), "opposing_face": c0,
                            "thickness_mm": round(t0, 6),
                            "source_normal": [round(float(x), 6)
                                              for x in nrm],
                            "opposing_normal": [round(float(x), 6)
                                                for x in n[c0]],
                            "ambiguous": amb})
    if not results:
        raise ThicknessAuthorityError("no opposing surface found for any "
                                      "sample — the mesh may be open")
    vals = np.array([r["thickness_mm"] for r in results])
    best = min(results, key=lambda r: (r["thickness_mm"], r["source_face"]))
    payload = "|".join(f"{r['source_face']}:{r['opposing_face']}:"
                       f"{r['thickness_mm']:.6f}" for r in results)
    return {
        "record_type": "normal_ray_thickness/1.0", "method": "B_NORMAL_RAY",
        "definition": "LOCAL_NORMAL_THICKNESS",
        "params": prm, "samples_per_face": samples_per_face,
        "sample_count": len(results), "ambiguous_count": ambiguous,
        "minimum_mm": round(float(vals.min()), 6),
        "maximum_mm": round(float(vals.max()), 6),
        "median_mm": round(float(np.median(vals)), 6),
        "minimum_sample": best,
        "identity": hashlib.sha256(payload.encode()).hexdigest()[:16],
        "samples": results,
    }


# ---------------------------------------------------------------------------
# Method C — local cross-section at a point


def section_interval_at(mesh, point, axis, *, sections=None):
    """SECTION_* thickness: the material interval through ``point``."""
    from apps.pipeline.services import palette_mesh_section as ms
    ai = {"x": 0, "y": 1, "z": 2}[axis]
    sec = ms.section_assembly({"m": mesh}, axis, float(point[ai]), cap=False)
    loops = [lp for c in sec["components"].values() for lp in c["loops"]]
    if not loops:
        raise ThicknessAuthorityError(f"no section at {axis}={point[ai]}")
    u, w = ms.PLANE_BASIS[axis]
    px, pz = point[u], point[w]
    best = None
    for lp in loops:
        pts = np.asarray(lp["points_2d"], float)
        seg_a, seg_b = pts, np.roll(pts, -1, axis=0)
        for direction, label in (((1.0, 0.0), "SECTION_HORIZONTAL_THICKNESS"),
                                 ((0.0, 1.0), "SECTION_VERTICAL_THICKNESS")):
            ts = []
            for a, b in zip(seg_a, seg_b):
                e = b - a
                den = e[0] * direction[1] - e[1] * direction[0]
                if abs(den) < 1e-14:
                    continue
                wv = np.array([px - a[0], pz - a[1]])
                t = (e[0] * wv[1] - e[1] * wv[0]) / den
                s = (direction[0] * wv[1] - direction[1] * wv[0]) / den
                if -1e-9 <= s <= 1 + 1e-9:
                    ts.append(t)
            ts = sorted(ts)
            neg = [t for t in ts if t < 0]
            pos = [t for t in ts if t > 0]
            if neg and pos:
                span = pos[0] - neg[-1]
                if best is None or span < best["thickness_mm"]:
                    best = {"definition": label, "axis": axis,
                            "thickness_mm": round(float(span), 6),
                            "at": [round(float(x), 6) for x in point]}
    if best is None:
        raise ThicknessAuthorityError("point is not inside the section")
    return best


# ---------------------------------------------------------------------------
# classification


def classify_region(analytical, ray_sample, section_value, *,
                    tolerance_mm=0.15) -> dict:
    """Two independent methods must agree before anything is classified."""
    vals = {"A_ANALYTICAL": analytical, "B_NORMAL_RAY": ray_sample,
            "C_SECTION": section_value}
    present = {k: v for k, v in vals.items() if v is not None}
    below = {k: v for k, v in present.items() if v < 1.0}
    agree = [k for k, a in present.items()
             for j, b in present.items()
             if k < j and abs(a - b) <= tolerance_mm]
    if len(below) >= 2:
        status = "CONFIRMED_PHYSICAL_THIN_REGION"
    elif len(present) >= 2 and not below:
        status = "NUMERICAL_SAMPLING_ARTIFACT"
    else:
        status = "UNRESOLVED"
    return {"methods": present, "methods_below_policy": sorted(below),
            "methods_in_agreement": sorted(set(agree)),
            "classification": status,
            "requires_two_methods": True,
            "note": "a larger value from one method does NOT discard a "
                    "smaller one; they measure different definitions"}


def validate_long_path_threshold(cases, *, threshold=None) -> dict:
    """§5A — measure the long-path classifier against labelled fixtures.

    ``cases`` is a list of ``(mesh, sample, expected_is_local_wall)``.
    The threshold is a DESIGN_DEFAULT: it is not an industry standard and
    is not manufacturer confirmed. Reporting sensitivity alongside the
    confusion matrix is what makes it auditable rather than asserted.
    """
    thr = LOCAL_WALL_MIDPOINT_RATIO if threshold is None else threshold
    tp = tn = fp = fn = 0
    ambiguous = []
    rows = []
    for mesh, sample, expect_local in cases:
        got = classify_maximum(mesh, sample)
        ratio = got["midpoint_ratio"]
        predicted = ratio >= thr
        if abs(ratio - thr) <= 0.05:
            ambiguous.append({"ratio": ratio, "expected": expect_local})
        if predicted and expect_local:
            tp += 1
        elif not predicted and not expect_local:
            tn += 1
        elif predicted and not expect_local:
            fp += 1
        else:
            fn += 1
        rows.append({"ratio": ratio, "predicted_local_wall": predicted,
                     "expected_local_wall": expect_local,
                     "correct": predicted == expect_local})
    total = tp + tn + fp + fn
    sensitivity = tp / (tp + fn) if (tp + fn) else None
    specificity = tn / (tn + fp) if (tn + fp) else None
    return {
        "record_type": "long_path_classifier_validation/1.0",
        "threshold": thr,
        "threshold_authority": ["DESIGN_DEFAULT", "NOT_INDUSTRY_STANDARD",
                                "NOT_MANUFACTURER_CONFIRMED"],
        "true_positives": tp, "true_negatives": tn,
        "false_positives": fp, "false_negatives": fn,
        "total": total,
        "accuracy": round((tp + tn) / total, 6) if total else None,
        "sensitivity": round(sensitivity, 6) if sensitivity is not None
        else None,
        "specificity": round(specificity, 6) if specificity is not None
        else None,
        "ambiguous_count": len(ambiguous),
        "ambiguity_rate": round(len(ambiguous) / total, 6) if total else None,
        "ambiguous_cases": ambiguous,
        "cases": rows,
        "note": "a case within 0.05 of the threshold is flagged ambiguous "
                "and must not be relied on for a policy verdict",
    }


def threshold_sensitivity(cases, *, candidates=(0.3, 0.4, 0.5, 0.6, 0.7,
                                                0.8)) -> dict:
    """How the verdict moves with the threshold — so the 0.60 choice is
    visibly a plateau rather than a knife edge."""
    sweep = []
    for t in candidates:
        got = validate_long_path_threshold(cases, threshold=t)
        sweep.append({"threshold": t, "accuracy": got["accuracy"],
                      "false_positives": got["false_positives"],
                      "false_negatives": got["false_negatives"]})
    perfect = [s["threshold"] for s in sweep if s["accuracy"] == 1.0]
    return {"record_type": "long_path_threshold_sensitivity/1.0",
            "sweep": sweep, "thresholds_with_perfect_accuracy": perfect,
            "selected": LOCAL_WALL_MIDPOINT_RATIO,
            "selected_is_inside_the_plateau":
                LOCAL_WALL_MIDPOINT_RATIO in perfect}
