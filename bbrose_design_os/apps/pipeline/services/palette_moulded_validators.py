"""PALT-M4B-A — strict fail-closed validators for the moulded tray.

Nothing here repairs geometry. A failing tray is reported with numbers,
never resized: the owner's standing rule is that dimensions are not
altered to make validation pass.

"Do not accept a mesh merely because Blender can display it" — so the
topology checks are real: edge incidence, orientability, T-junctions and
triangle-triangle self-intersection are all computed, the last two with
spatial bucketing so they stay affordable at ~15k faces.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

VALIDATOR_VERSION = "palette_moulded_validators/1.0"

# --- topology codes --------------------------------------------------------
NON_MANIFOLD_EDGE = "NON_MANIFOLD_EDGE"
NOT_WATERTIGHT = "NOT_WATERTIGHT"
BOUNDARY_EDGE_PRESENT = "BOUNDARY_EDGE_PRESENT"
DISCONNECTED_COMPONENTS = "DISCONNECTED_COMPONENTS"
INCONSISTENT_WINDING = "INCONSISTENT_WINDING"
INVERTED_NORMALS = "INVERTED_NORMALS"
NON_POSITIVE_VOLUME = "NON_POSITIVE_VOLUME"
SELF_INTERSECTION = "SELF_INTERSECTION"
ZERO_AREA_FACE = "ZERO_AREA_FACE"
DUPLICATE_FACE = "DUPLICATE_FACE"
DUPLICATE_VERTEX = "DUPLICATE_VERTEX"
T_JUNCTION = "T_JUNCTION"
DEGENERATE_EULER_CHARACTERISTIC = "DEGENERATE_EULER_CHARACTERISTIC"

# --- contract codes --------------------------------------------------------
POCKET_COUNT_MISMATCH = "POCKET_COUNT_MISMATCH"
POCKET_CENTRE_MISPLACED = "POCKET_CENTRE_MISPLACED"
POCKET_DEPTH_MISMATCH = "POCKET_DEPTH_MISMATCH"
POCKET_DRAFT_MISMATCH = "POCKET_DRAFT_MISMATCH"
TRAY_DRAFT_MISMATCH = "TRAY_DRAFT_MISMATCH"
FLOOR_THICKNESS_MISMATCH = "FLOOR_THICKNESS_MISMATCH"
POCKET_BREAKTHROUGH = "POCKET_BREAKTHROUGH"
DECK_NOT_CONTINUOUS = "DECK_NOT_CONTINUOUS"

# --- pan codes -------------------------------------------------------------
PAN_NOT_SEATED = "PAN_NOT_SEATED"
PAN_FLOATS = "PAN_FLOATS"
PAN_POCKET_INTERSECTION = "PAN_POCKET_INTERSECTION"
PAN_RECESS_MISMATCH = "PAN_RECESS_MISMATCH"
POWDER_LID_CLEARANCE = "POWDER_LID_CLEARANCE"

# --- section codes ---------------------------------------------------------
SECTION_LOOP_OPEN = "SECTION_LOOP_OPEN"
SECTION_LAYER_MISSING = "SECTION_LAYER_MISSING"

# --- declared scope boundaries (not defects — owner rulings) ---------------
UNMODELLED_CONTRACT_FEATURE = "UNMODELLED_CONTRACT_FEATURE"
CONTRACT_VALUE_DIVERGENCE = "CONTRACT_VALUE_DIVERGENCE"
SECTION_THICKNESS_RISK = "SECTION_THICKNESS_RISK"

TOL = 1e-6


def _findings():
    out = []

    def add(code, message, severity="FAIL", **extra):
        out.append({"code": code, "message": message,
                    "severity": severity, **extra})
    return out, add


# ---------------------------------------------------------------------------
# mesh topology


def _edges(faces):
    he = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                         faces[:, [2, 0]]])
    return he, np.unique(np.sort(he, axis=1), axis=0)


def _grid_key(p, cell):
    return tuple(np.floor(p / cell).astype(np.int64))


def find_t_junctions(vertices, faces, *, tol=1e-7, cell=4.0):
    """A vertex lying strictly inside an edge it does not belong to."""
    _, edges = _edges(faces)
    p0, p1 = vertices[edges[:, 0]], vertices[edges[:, 1]]
    d = p1 - p0
    length2 = np.einsum("ij,ij->i", d, d)
    buckets = defaultdict(list)
    lo = np.minimum(p0, p1)
    hi = np.maximum(p0, p1)
    for e in range(len(edges)):
        a = np.floor(lo[e] / cell).astype(np.int64)
        b = np.floor(hi[e] / cell).astype(np.int64)
        for i in range(a[0], b[0] + 1):
            for j in range(a[1], b[1] + 1):
                for k in range(a[2], b[2] + 1):
                    buckets[(i, j, k)].append(e)
    hits = []
    for vi, p in enumerate(vertices):
        cand = buckets.get(_grid_key(p, cell))
        if not cand:
            continue
        idx = np.asarray(cand)
        idx = idx[(edges[idx, 0] != vi) & (edges[idx, 1] != vi)]
        if not len(idx):
            continue
        w = p - p0[idx]
        t = np.einsum("ij,ij->i", w, d[idx]) / length2[idx]
        inside = (t > tol) & (t < 1.0 - tol)
        if not inside.any():
            continue
        sel = idx[inside]
        ts = t[inside]
        proj = p0[sel] + d[sel] * ts[:, None]
        near = np.linalg.norm(p - proj, axis=1) < tol
        for e in sel[near]:
            hits.append((int(vi), int(edges[e, 0]), int(edges[e, 1])))
    return hits


def _seg_tri_hits(orig, dest, tv0, tv1, tv2):
    """Vectorised Moller-Trumbore restricted to the segment span."""
    d = dest - orig
    e1, e2 = tv1 - tv0, tv2 - tv0
    pv = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, pv)
    ok = np.abs(det) > 1e-12
    inv = np.zeros_like(det)
    inv[ok] = 1.0 / det[ok]
    tvec = orig - tv0
    u = np.einsum("ij,ij->i", tvec, pv) * inv
    qv = np.cross(tvec, e1)
    v = np.einsum("ij,ij->i", d, qv) * inv
    t = np.einsum("ij,ij->i", e2, qv) * inv
    eps = 1e-9
    return (ok & (u > eps) & (v > eps) & (u + v < 1.0 - eps)
            & (t > eps) & (t < 1.0 - eps))


def find_self_intersections(vertices, faces, *, cell=6.0, limit=64):
    """Proper triangle-triangle intersections, spatially bucketed.

    Triangles sharing any vertex are skipped: they meet legitimately.
    """
    tri = vertices[faces]
    lo, hi = tri.min(axis=1), tri.max(axis=1)
    buckets = defaultdict(list)
    for fi in range(len(faces)):
        a = np.floor(lo[fi] / cell).astype(np.int64)
        b = np.floor(hi[fi] / cell).astype(np.int64)
        for i in range(a[0], b[0] + 1):
            for j in range(a[1], b[1] + 1):
                for k in range(a[2], b[2] + 1):
                    buckets[(i, j, k)].append(fi)
    seen = set()
    hits = []
    for cand in buckets.values():
        if len(cand) < 2:
            continue
        arr = np.asarray(sorted(cand))
        for n, fi in enumerate(arr[:-1]):
            other = arr[n + 1:]
            shared = np.isin(faces[other], faces[fi]).any(axis=1)
            other = other[~shared]
            if not len(other):
                continue
            # AABB reject
            keep = ~((hi[fi] < lo[other] - 1e-12).any(axis=1)
                     | (lo[fi] > hi[other] + 1e-12).any(axis=1))
            other = other[keep]
            if not len(other):
                continue
            a0, a1, a2 = tri[fi]
            b0, b1, b2 = tri[other, 0], tri[other, 1], tri[other, 2]
            bad = np.zeros(len(other), dtype=bool)
            for s, e in ((a0, a1), (a1, a2), (a2, a0)):
                bad |= _seg_tri_hits(np.broadcast_to(s, (len(other), 3)),
                                     np.broadcast_to(e, (len(other), 3)),
                                     b0, b1, b2)
            oa = np.broadcast_to(a0, (len(other), 3))
            ob = np.broadcast_to(a1, (len(other), 3))
            oc = np.broadcast_to(a2, (len(other), 3))
            for s, e in ((0, 1), (1, 2), (2, 0)):
                bad |= _seg_tri_hits(tri[other, s], tri[other, e], oa, ob, oc)
            for fj in other[bad]:
                pair = (int(fi), int(fj))
                if pair not in seen:
                    seen.add(pair)
                    hits.append(pair)
                    if len(hits) >= limit:
                        return hits
    return hits


def validate_mesh(name, mesh, *, expect_components=1,
                  check_self_intersection=True) -> dict:
    """Topology validation for one closed manifold solid."""
    findings, add = _findings()
    v = np.asarray(mesh["vertices"], dtype=float)
    f = np.asarray(mesh["faces"], dtype=np.int64)
    he, edges = _edges(f)

    counts = defaultdict(int)
    for a, b in np.sort(he, axis=1):
        counts[(int(a), int(b))] += 1
    boundary = [e for e, c in counts.items() if c == 1]
    excess = [e for e, c in counts.items() if c > 2]
    if boundary:
        add(BOUNDARY_EDGE_PRESENT,
            f"{name}: {len(boundary)} boundary edge(s) — the mesh is not "
            "watertight", count=len(boundary))
        add(NOT_WATERTIGHT, f"{name}: open surface", count=len(boundary))
    if excess:
        add(NON_MANIFOLD_EDGE,
            f"{name}: {len(excess)} edge(s) with more than two incident "
            "faces", count=len(excess))

    directed = set(map(tuple, he))
    unpaired = [(int(a), int(b)) for a, b in map(tuple, he)
                if (b, a) not in directed]
    if unpaired:
        add(INCONSISTENT_WINDING,
            f"{name}: {len(unpaired)} half-edge(s) are not traversed in "
            "both directions — the surface is not consistently oriented",
            count=len(unpaired))

    a = v[f[:, 0]]
    cr = np.cross(v[f[:, 1]] - a, v[f[:, 2]] - a)
    areas = 0.5 * np.linalg.norm(cr, axis=1)
    volume = float(np.einsum("ij,ij->i", a, cr).sum() / 6.0)
    if volume <= 0.0:
        add(NON_POSITIVE_VOLUME,
            f"{name}: signed volume {volume:.4f} mm3 is not positive — "
            "normals point inward", volume_mm3=volume)
        add(INVERTED_NORMALS, f"{name}: inward-facing normals")
    zero = int((areas < 1e-9).sum())
    if zero:
        add(ZERO_AREA_FACE, f"{name}: {zero} zero-area face(s)", count=zero)

    _, fc = np.unique(np.sort(f, axis=1), axis=0, return_counts=True)
    dup_f = int((fc > 1).sum())
    if dup_f:
        add(DUPLICATE_FACE, f"{name}: {dup_f} duplicated face(s)",
            count=dup_f)
    _, vc = np.unique(np.round(v, 6), axis=0, return_counts=True)
    dup_v = int((vc > 1).sum())
    if dup_v:
        add(DUPLICATE_VERTEX, f"{name}: {dup_v} coincident vertex "
            "position(s)", count=dup_v)

    # connected components over the face-adjacency graph
    parent = list(range(len(v)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for e0, e1 in edges:
        r0, r1 = find(int(e0)), find(int(e1))
        if r0 != r1:
            parent[r1] = r0
    used = {find(int(i)) for i in np.unique(f)}
    if len(used) != expect_components:
        add(DISCONNECTED_COMPONENTS,
            f"{name}: {len(used)} connected component(s), expected "
            f"{expect_components}", count=len(used))

    tj = find_t_junctions(v, f)
    if tj:
        add(T_JUNCTION, f"{name}: {len(tj)} T-junction incidence(s)",
            count=len(tj), sample=tj[:5])

    si = find_self_intersections(v, f) if check_self_intersection else []
    if si:
        add(SELF_INTERSECTION,
            f"{name}: {len(si)} self-intersecting face pair(s)",
            count=len(si), sample=si[:5])

    euler = len(v) - len(edges) + len(f)
    if euler != 2:
        add(DEGENERATE_EULER_CHARACTERISTIC,
            f"{name}: Euler characteristic {euler} (expected 2 for a closed "
            "genus-0 solid)", euler=euler)

    return {"validator": VALIDATOR_VERSION, "target": name,
            "valid": not findings, "findings": findings,
            "finding_count": len(findings),
            "diagnostics": {
                "vertices": int(len(v)), "edges": int(len(edges)),
                "faces": int(len(f)), "euler_characteristic": int(euler),
                "signed_volume_mm3": round(volume, 6),
                "surface_area_mm2": round(float(areas.sum()), 6),
                "boundary_edges": len(boundary),
                "non_manifold_edges": len(excess),
                "inconsistent_half_edges": len(unpaired),
                "zero_area_faces": zero, "duplicate_faces": dup_f,
                "duplicate_vertices": dup_v,
                "connected_components": len(used),
                "t_junctions": len(tj),
                "self_intersecting_pairs": len(si),
                "self_intersection_checked": bool(check_self_intersection)}}


# ---------------------------------------------------------------------------
# contract conformance


def _profile_radius(rings, z):
    for (r0, z0), (r1, z1) in zip(rings, rings[1:]):
        if z1 - 1e-9 <= z <= z0 + 1e-9:
            if abs(z0 - z1) < 1e-12:
                return max(r0, r1)
            t = (z0 - z) / (z0 - z1)
            return r0 + (r1 - r0) * t
    return None


def validate_recessed_tray(tray, contract) -> dict:
    """Tray geometry against the M4B-A contract values."""
    findings, add = _findings()
    ex = contract["expected"]
    pockets = tray["pockets"]

    if len(pockets) != ex["pocket_count"]:
        add(POCKET_COUNT_MISMATCH,
            f"{len(pockets)} pockets, expected {ex['pocket_count']}",
            count=len(pockets))

    pitch = ex["pitch_mm"]
    want = {(round((c - 1) * pitch, 6), round((r - 1) * pitch, 6))
            for r in range(3) for c in range(3)}
    got = {(round(p["centre_mm"][0], 6), round(p["centre_mm"][1], 6))
           for p in pockets}
    if want != got:
        add(POCKET_CENTRE_MISPLACED,
            f"pocket centres do not match a {pitch} mm 3x3 lattice",
            missing=sorted(want - got), unexpected=sorted(got - want))

    for p in pockets:
        if abs(p["depth_mm"] - ex["pocket_depth_mm"]) > 1e-6:
            add(POCKET_DEPTH_MISMATCH,
                f"pocket ({p['row']},{p['col']}) depth {p['depth_mm']} mm "
                f"!= {ex['pocket_depth_mm']} mm")

    got_pd = tray["draft"]["pocket_draft_deg"]
    if abs(got_pd - ex["pocket_draft_deg"]) > 1e-9:
        add(POCKET_DRAFT_MISMATCH,
            f"pocket draft {got_pd} != {ex['pocket_draft_deg']} deg")
    got_td = tray["draft"]["tray_draft_deg"]
    if abs(got_td - ex["tray_draft_deg"]) > 1e-9:
        add(TRAY_DRAFT_MISMATCH,
            f"tray draft {got_td} != {ex['tray_draft_deg']} deg")

    # measured draft, straight from the mesh: the wall run between the two
    # fillet tangents over its rise
    rings = tray["pocket_profile_rings"]
    k = tray["topology"]["fillet_arc_samples"]
    (r_top, z_top), (r_bot, z_bot) = rings[k], rings[k + 1]
    measured = math.degrees(math.atan2(r_top - r_bot, z_top - z_bot))
    if abs(measured - ex["pocket_draft_deg"]) > 1e-6:
        add(POCKET_DRAFT_MISMATCH,
            f"measured pocket wall draft {measured:.6f} deg differs from "
            f"the contract {ex['pocket_draft_deg']} deg",
            measured_deg=round(measured, 6))

    floor_t = tray["pocket_floor_thickness_mm"]
    if abs(floor_t - ex["pocket_floor_thickness_mm"]) > 1e-6:
        add(FLOOR_THICKNESS_MISMATCH,
            f"pocket floor thickness {floor_t} mm != "
            f"{ex['pocket_floor_thickness_mm']} mm")
    if floor_t <= 0.0:
        add(POCKET_BREAKTHROUGH,
            f"pocket floors break through the underside (thickness "
            f"{floor_t} mm)")

    # the deck must be one continuous surface at a single elevation
    v = np.asarray(tray["vertices"])
    deck_z = tray["elevations_mm"]["deck"]
    if not np.isclose(v[:, 2].max(), deck_z, atol=1e-9):
        add(DECK_NOT_CONTINUOUS,
            f"highest vertex {v[:, 2].max():.6f} is not the deck {deck_z}")

    return {"validator": VALIDATOR_VERSION,
            # distinct from the mesh-topology report's target, which is the
            # component name — merge_reports keys by target
            "target": "recessed_tray_contract",
            "valid": not findings, "findings": findings,
            "finding_count": len(findings),
            "measured": {"pocket_wall_draft_deg": round(measured, 6),
                         "flat_floor_radius_mm": rings[-1][0],
                         "opening_radius_mm": rings[0][0],
                         "pocket_floor_thickness_mm": floor_t}}


def validate_pan_seating(tray, contract, *, samples=400) -> dict:
    """Pan-in-pocket relationships, measured against the real profile.

    The tightest point is the pan BASE, not the rim: draft narrows the
    pocket downward and the floor fillet narrows it further. Checking the
    rim alone would miss the interference entirely.
    """
    findings, add = _findings()
    pan = contract["pan"]
    rings = tray["pocket_profile_rings"]
    pan_r = pan["pan_outside_diameter_mm"] / 2.0
    z0 = pan["pan_seating_z_mm"]
    z1 = pan["pan_top_z_mm"]
    deck_z = tray["elevations_mm"]["deck"]
    floor_z = tray["elevations_mm"]["pocket_floor"]

    if abs((z1 - z0) - pan["pan_depth_mm"]) > 1e-9:
        add(PAN_NOT_SEATED,
            f"pan span {z1 - z0} mm != pan depth {pan['pan_depth_mm']} mm")

    gap = z0 - floor_z
    if gap < -1e-9:
        add(PAN_NOT_SEATED,
            f"pan base {z0} lies below the pocket floor {floor_z}")
    elif abs(gap - pan["adhesive_allowance_mm"]) > 1e-9:
        add(PAN_FLOATS,
            f"pan base sits {gap:.4f} mm above the pocket floor, but the "
            f"adhesive allowance is {pan['adhesive_allowance_mm']} mm",
            gap_mm=round(gap, 6))

    recess = deck_z - z1
    if abs(recess - pan["pan_recess_mm"]) > 1e-9:
        add(PAN_RECESS_MISMATCH,
            f"pan recess below deck {recess:.4f} mm != "
            f"{pan['pan_recess_mm']} mm", recess_mm=round(recess, 6))

    zs = np.linspace(z0, z1, samples)
    clear = np.array([_profile_radius(rings, float(z)) - pan_r for z in zs])
    imin = int(np.argmin(clear))
    min_clear = float(clear[imin])
    if min_clear < 0.0:
        add(PAN_POCKET_INTERSECTION,
            f"the pan intersects the pocket wall by {-min_clear:.4f} mm at "
            f"z {zs[imin]:.4f} — the {tray['fillets_mm']['floor']} mm floor "
            f"fillet reaches radius "
            f"{_profile_radius(rings, float(zs[imin])):.4f} where the pan "
            f"needs {pan_r}",
            interference_mm=round(-min_clear, 6),
            at_z_mm=round(float(zs[imin]), 6))

    powder_top = z1 + pan.get("powder_crown_mm", 0.0)
    lid_z = pan.get("lid_inner_z_mm")
    if lid_z is not None:
        head = lid_z - powder_top
        if head < pan.get("powder_to_lid_clearance_mm", 0.0) - 1e-9:
            add(POWDER_LID_CLEARANCE,
                f"powder crown to lid {head:.4f} mm is below the "
                f"{pan['powder_to_lid_clearance_mm']} mm requirement",
                clearance_mm=round(head, 6))

    return {"validator": VALIDATOR_VERSION, "target": "pan_seating",
            "valid": not findings, "findings": findings,
            "finding_count": len(findings),
            "measured": {
                "min_radial_clearance_mm": round(min_clear, 6),
                "min_clearance_z_mm": round(float(zs[imin]), 6),
                "clearance_at_pan_base_mm": round(float(clear[0]), 6),
                "clearance_at_pan_top_mm": round(float(clear[-1]), 6),
                "pan_recess_mm": round(recess, 6),
                "adhesive_gap_mm": round(gap, 6)}}


def max_floor_fillet_for_pan(pocket_r, deck_z, floor_z, draft_deg, pan_r,
                             pan_z, *, hi=2.0, iterations=80):
    """Largest floor fillet that still lets the pan seat — the number the
    owner needs to rule on the interference, solved rather than guessed."""
    from apps.pipeline.services.palette_recessed_tray_geometry import (
        RecessedTrayError, _pocket_profile)

    def clears(b):
        try:
            rings, _, _ = _pocket_profile(pocket_r, deck_z, floor_z,
                                          draft_deg, 0.6, b, 5)
        except RecessedTrayError:
            return False
        r = _profile_radius(rings, pan_z)
        return r is not None and r >= pan_r

    lo = 1e-4
    if not clears(lo):
        return 0.0
    if clears(hi):
        return hi
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if clears(mid):
            lo = mid
        else:
            hi = mid
    return round(lo, 4)


def min_pocket_diameter_for_pan(floor_fillet, deck_z, floor_z, draft_deg,
                                pan_r, pan_z, *, iterations=80):
    """Smallest sharp-corner pocket diameter that seats the pan at a given
    floor fillet."""
    from apps.pipeline.services.palette_recessed_tray_geometry import (
        RecessedTrayError, _pocket_profile)

    def clears(pr):
        try:
            rings, _, _ = _pocket_profile(pr, deck_z, floor_z, draft_deg,
                                          0.6, floor_fillet, 5)
        except RecessedTrayError:
            return False
        r = _profile_radius(rings, pan_z)
        return r is not None and r >= pan_r

    lo, hi = pan_r, pan_r + 4.0
    if not clears(hi):
        return None
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if clears(mid):
            hi = mid
        else:
            lo = mid
    return round(hi * 2.0, 4)


# ---------------------------------------------------------------------------
# section


def validate_section(section, required_layers) -> dict:
    """Every loop closed, and the section actually exposes the layers the
    owner listed."""
    findings, add = _findings()
    if section.get("open_loop_count", 0):
        add(SECTION_LOOP_OPEN,
            f"{section['open_loop_count']} open section loop(s)")
    for name, joined in section["components"].items():
        for loop in joined["loops"]:
            if not loop.get("closed"):
                add(SECTION_LOOP_OPEN, f"{name}: open loop")
            if abs(loop["signed_area_mm2"]) < 1e-9:
                add(SECTION_LOOP_OPEN,
                    f"{name}: degenerate zero-area loop")
    exposed = {k for k, present in required_layers.items() if present}
    missing = sorted(set(required_layers) - exposed)
    if missing:
        add(SECTION_LAYER_MISSING,
            f"the section does not expose: {', '.join(missing)}",
            missing=missing)
    return {"validator": VALIDATOR_VERSION, "target": "centre_section",
            "valid": not findings, "findings": findings,
            "finding_count": len(findings),
            "exposed_layers": sorted(exposed), "missing_layers": missing}


def merge_reports(*reports) -> dict:
    findings = [dict(f, source=r.get("target", "?"))
                for r in reports for f in r["findings"]]
    fails = [f for f in findings if f.get("severity") == "FAIL"]
    return {"validator": VALIDATOR_VERSION,
            "valid": not fails,
            "findings": findings,
            "finding_count": len(findings),
            "failure_count": len(fails),
            "declared_count": len(findings) - len(fails),
            "reports": {r.get("target", "?"): r for r in reports}}
