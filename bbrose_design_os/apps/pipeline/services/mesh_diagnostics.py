"""RBV-2B §12 — deterministic mesh diagnostics (pure NumPy).

Stable error codes; serious defects are recorded, never silently repaired.
"""
from __future__ import annotations

import numpy as np

MESH_NON_MANIFOLD = "MESH_NON_MANIFOLD"
MESH_NORMALS_INVERTED = "MESH_NORMALS_INVERTED"
MESH_DEGENERATE_FACE = "MESH_DEGENERATE_FACE"
MESH_DEGENERATE_EDGE = "MESH_DEGENERATE_EDGE"
MESH_DUPLICATE_VERTICES = "MESH_DUPLICATE_VERTICES"
MESH_COMPONENT_DISCONNECTED = "MESH_COMPONENT_DISCONNECTED"
CLOSURE_ALIGNMENT_INVALID = "CLOSURE_ALIGNMENT_INVALID"

PARAMS = {
    "version": "mesh_diagnostics_params/1.0",
    "duplicate_epsilon": 1e-6,
    "zero_area_epsilon": 1e-9,
    "zero_edge_epsilon": 1e-9,
    "closure_center_tolerance_ratio": 0.02,   # vs body width
    "closure_gap_tolerance_mm": 1.0,
}


def _edges(faces: np.ndarray) -> np.ndarray:
    e = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                        faces[:, [2, 0]]])
    return np.sort(e, axis=1)


def diagnose_mesh(vertices: np.ndarray, faces: np.ndarray) -> dict:
    """§12 diagnostics for one mesh. Returns metrics + stable codes."""
    codes: list[str] = []
    v = np.asarray(vertices, dtype=float)
    f = np.asarray(faces, dtype=np.int64)

    # duplicate vertices
    rounded = np.round(v / PARAMS["duplicate_epsilon"]).astype(np.int64)
    unique = np.unique(rounded, axis=0)
    duplicates = len(v) - len(unique)
    if duplicates > 2:            # loft caps legitimately share 2 centroids
        codes.append(MESH_DUPLICATE_VERTICES)

    # degenerate faces / edges
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    areas = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    if (areas < PARAMS["zero_area_epsilon"]).any():
        codes.append(MESH_DEGENERATE_FACE)
    edges = _edges(f)
    lengths = np.linalg.norm(v[edges[:, 0]] - v[edges[:, 1]], axis=1)
    if (lengths < PARAMS["zero_edge_epsilon"]).any():
        codes.append(MESH_DEGENERATE_EDGE)

    # manifold: every undirected edge shared by exactly two faces
    uniq_edges, counts = np.unique(edges, axis=0, return_counts=True)
    non_manifold = int((counts != 2).sum())
    if non_manifold:
        codes.append(MESH_NON_MANIFOLD)

    # connectivity over the face graph (union-find on shared vertices)
    parent = np.arange(len(v))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for tri in f:
        r0, r1, r2 = find(tri[0]), find(tri[1]), find(tri[2])
        parent[r1] = r0
        parent[find(r2)] = r0
    used = np.unique(f)
    components = len({find(int(i)) for i in used})
    if components != 1:
        codes.append(MESH_COMPONENT_DISCONNECTED)

    # normals orientation via signed volume (positive = outward for CCW)
    signed_volume = float(np.einsum("ij,ij->i", a,
                                    np.cross(b, c)).sum() / 6.0)
    if signed_volume < 0:
        codes.append(MESH_NORMALS_INVERTED)

    return {
        "params_version": PARAMS["version"],
        "vertex_count": int(len(v)),
        "edge_count": int(len(uniq_edges)),
        "face_count": int(len(f)),
        "duplicate_vertices": int(duplicates),
        "zero_area_faces": int((areas < PARAMS["zero_area_epsilon"]).sum()),
        "non_manifold_edges": non_manifold,
        "components": components,
        "signed_volume_mm3": round(signed_volume, 3),
        "codes": codes,
    }


def diagnose_assembly(body: dict, collar: dict | None,
                      bulb: dict | None) -> dict:
    """Closure/body relation checks for the M3 assembly (visible scope
    only — no invented internals)."""
    codes: list[str] = []
    facts: dict = {}

    def _bounds(mesh):
        v = mesh["vertices"]
        return {"z_min": float(v[:, 2].min()), "z_max": float(v[:, 2].max()),
                "cx": float((v[:, 0].min() + v[:, 0].max()) / 2),
                "cy": float((v[:, 1].min() + v[:, 1].max()) / 2),
                "width": float(v[:, 0].max() - v[:, 0].min())}

    bb = _bounds(body)
    facts["body"] = bb
    tol_gap = PARAMS["closure_gap_tolerance_mm"]
    for name, mesh, below in (("collar", collar, "body"),
                              ("bulb", bulb, "collar")):
        if mesh is None:
            continue
        mb = _bounds(mesh)
        facts[name] = mb
        # centered over the body
        if abs(mb["cx"] - bb["cx"]) > \
                PARAMS["closure_center_tolerance_ratio"] * bb["width"]:
            codes.append(CLOSURE_ALIGNMENT_INVALID)
        # sits above (small overlap allowed, gap bounded)
        ref = facts.get(below) or bb
        if mb["z_min"] > ref["z_max"] + tol_gap or \
                mb["z_max"] < ref["z_max"] - tol_gap:
            if CLOSURE_ALIGNMENT_INVALID not in codes:
                codes.append(CLOSURE_ALIGNMENT_INVALID)
    return {"facts": facts, "codes": sorted(set(codes))}
