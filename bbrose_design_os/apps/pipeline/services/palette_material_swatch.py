"""M5 §3/§4/§6 — the standardized material characterization fixture.

The three-quarter palette view could not separate MATTE from SATIN
because a largely flat palette presents almost no surface at the grazing
angle where a soft lobe narrows. That is a property of the VIEW, not
proof that the two materials are the same, so this fixture exists to
measure the materials themselves.

It is an ENGINEERING_MATERIAL_CHARACTERIZATION_FIXTURE. It is not product
geometry, not a client presentation and not an owner design, and it never
replaces the real palette evidence — §9 still requires the same two
contracts to show a visible difference on actual P1B geometry.

One swatch shape for every material family. A different shape per
material would let the shape carry the difference.

The pass law and every threshold in this module were fixed BEFORE any
pair was measured against them.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

SCHEMA = "palette_material_swatch/1.0"
VERSION = 1

# --------------------------------------------------------------------------
# §6 — the pass law, declared before measurement
# --------------------------------------------------------------------------

#: Independent physical discriminators. Each is measured in SCENE-LINEAR
#: data where highlights would otherwise clip.
DISCRIMINATOR_AXES = (
    "HIGHLIGHT_FWHM",
    "HIGHLIGHT_PEAK",
    "SPECULAR_TO_DIFFUSE_RATIO",
    "GRAZING_RESPONSE",
    "SHEEN_REGION_RESPONSE",
    "EDGE_HIGHLIGHT_RESPONSE",
)

#: Relative effect size required on an axis for it to count as
#: discriminating: the two materials must differ by at least this fraction
#: of their mean on that axis. Predeclared.
MINIMUM_RELATIVE_EFFECT = 0.25

#: How many independent axes must clear that effect size. Predeclared.
#: Not every axis is expected to separate every pair — a matte and a satin
#: share a diffuse base — so requiring all six would be a bar no plausible
#: cosmetic material could meet.
REQUIRED_DISCRIMINATING_AXES = 2

PASS_LAW = {
    "statement": (
        f"a material pair is distinguishable when at least "
        f"{REQUIRED_DISCRIMINATING_AXES} of the "
        f"{len(DISCRIMINATOR_AXES)} independent axes differ by at least "
        f"{MINIMUM_RELATIVE_EFFECT:.0%} relative effect size, AND the "
        "negative controls fail"),
    "axes": list(DISCRIMINATOR_AXES),
    "minimum_relative_effect": MINIMUM_RELATIVE_EFFECT,
    "required_axes": REQUIRED_DISCRIMINATING_AXES,
    "declared_before_measurement": True,
    "measured_in": "SCENE_LINEAR",
    "why_not_all_axes": "a matte and a satin share a diffuse base, so "
                        "requiring every axis would be a bar no plausible "
                        "moulded cosmetic material could meet",
}


class SwatchError(ValueError):
    """Raised when the fixture cannot be built exactly."""


# --------------------------------------------------------------------------
# §3 — the fixture geometry
# --------------------------------------------------------------------------

SWATCH = {
    "plate_w": 40.0, "plate_d": 26.0, "plate_h": 3.0,
    "shallow_radius": 90.0, "shallow_w": 40.0, "shallow_d": 16.0,
    "quarter_radius": 7.0, "quarter_len": 40.0,
    "bevel": 1.6,
    "grazing_deg": 74.0, "grazing_w": 40.0, "grazing_len": 18.0,
    "segments": 96,
    "gap": 4.0,
}

#: Named regions, so a measurement can say which surface it came from.
REGIONS = ("PLANAR", "SHALLOW_CURVE", "QUARTER_CYLINDER", "BEVEL",
           "GRAZING")


def _quad(verts, faces, a, b, c, d):
    faces.append((a, b, c))
    faces.append((a, c, d))


def _strip(verts, faces, row_a, row_b):
    for i in range(len(row_a) - 1):
        _quad(verts, faces, row_a[i], row_b[i], row_b[i + 1], row_a[i + 1])


def build_swatch() -> dict:
    """One deterministic swatch carrying every required surface type.

    The same object is used for every material family, so a difference
    between two renders can only come from the material.
    """
    s = SWATCH
    n = s["segments"]
    verts: list = []
    faces: list = []
    region_of_face: list = []

    def add(x, y, z):
        verts.append([float(x), float(y), float(z)])
        return len(verts) - 1

    def row(pts):
        return [add(*p) for p in pts]

    def mark(region, start):
        region_of_face.extend([region] * (len(faces) - start))

    x0 = -s["plate_w"] / 2.0
    y = 0.0

    # --- planar face -----------------------------------------------------
    start = len(faces)
    a = row([(x0, y, 0.0), (x0 + s["plate_w"], y, 0.0)])
    b = row([(x0, y + s["plate_d"], 0.0),
             (x0 + s["plate_w"], y + s["plate_d"], 0.0)])
    _strip(verts, faces, a, b)
    mark("PLANAR", start)
    y += s["plate_d"] + s["gap"]

    # --- shallow curve ---------------------------------------------------
    start = len(faces)
    R = s["shallow_radius"]
    half = s["shallow_d"] / 2.0
    prev = None
    for j in range(n + 1):
        t = -half + 2 * half * j / n
        z = R - math.sqrt(max(R * R - t * t, 0.0))
        cur = row([(x0, y + half + t, -z),
                   (x0 + s["shallow_w"], y + half + t, -z)])
        if prev is not None:
            _strip(verts, faces, prev, cur)
        prev = cur
    mark("SHALLOW_CURVE", start)
    y += s["shallow_d"] + s["gap"]

    # --- convex quarter cylinder ----------------------------------------
    start = len(faces)
    r = s["quarter_radius"]
    prev = None
    for j in range(n + 1):
        ang = (math.pi / 2) * j / n
        dy, dz = r * math.sin(ang), r * (1.0 - math.cos(ang))
        cur = row([(x0, y + dy, -dz),
                   (x0 + s["quarter_len"], y + dy, -dz)])
        if prev is not None:
            _strip(verts, faces, prev, cur)
        prev = cur
    mark("QUARTER_CYLINDER", start)
    y += r + s["gap"]

    # --- bevelled edge ---------------------------------------------------
    start = len(faces)
    bv = s["bevel"]
    prev = None
    for j in range(9):
        ang = (math.pi / 2) * j / 8
        dy, dz = bv * math.sin(ang), bv * (1.0 - math.cos(ang))
        cur = row([(x0, y + dy, -dz), (x0 + s["plate_w"], y + dy, -dz)])
        if prev is not None:
            _strip(verts, faces, prev, cur)
        prev = cur
    mark("BEVEL", start)
    y += bv + s["gap"]

    # --- grazing-angle ramp ---------------------------------------------
    start = len(faces)
    th = math.radians(s["grazing_deg"])
    ln = s["grazing_len"]
    a = row([(x0, y, 0.0), (x0 + s["grazing_w"], y, 0.0)])
    b = row([(x0, y + ln * math.cos(th), -ln * math.sin(th)),
             (x0 + s["grazing_w"], y + ln * math.cos(th),
              -ln * math.sin(th))])
    _strip(verts, faces, a, b)
    mark("GRAZING", start)

    v = np.asarray(verts, float)
    f = np.asarray(faces, np.int64)
    return {
        "name": "material_characterization_swatch",
        "schema": SCHEMA, "version": VERSION,
        "vertices": v, "faces": f,
        "region_of_face": region_of_face,
        "regions": list(REGIONS),
        "role": "ENGINEERING_MATERIAL_CHARACTERIZATION_FIXTURE",
        "is_product_geometry": False,
        "is_client_presentation": False,
        "is_owner_design": False,
        "identical_for_every_material": True,
        "swatch_geometry_identity": hashlib.sha256(
            np.round(v, 6).tobytes() + f.tobytes()
            + repr(sorted(SWATCH.items())).encode()).hexdigest()[:16],
    }


def swatch_bounds():
    sw = build_swatch()
    v = sw["vertices"]
    return v.min(axis=0), v.max(axis=0)


#: Distinct emission colours for the region mask. Rendered once from the
#: same geometry and camera, so a measurement can say which surface it
#: came from instead of guessing at image rows.
REGION_COLOURS = {
    "PLANAR": [1.0, 0.0, 0.0],
    "SHALLOW_CURVE": [0.0, 1.0, 0.0],
    "QUARTER_CYLINDER": [0.0, 0.0, 1.0],
    "BEVEL": [1.0, 1.0, 0.0],
    "GRAZING": [1.0, 0.0, 1.0],
}


def build_swatch_regions() -> dict:
    """The same swatch, split into one mesh per named region.

    Splitting is what makes the mask exact: each region carries its own
    emission colour in the mask pass and the identical material in every
    measurement pass.
    """
    sw = build_swatch()
    v, f = sw["vertices"], sw["faces"]
    out = {}
    for region in REGIONS:
        idx = [i for i, r in enumerate(sw["region_of_face"])
               if r == region]
        if not idx:
            continue
        sub = f[idx]
        used = np.unique(sub)
        remap = {int(o): i for i, o in enumerate(used)}
        out[region] = {
            "name": region,
            "vertices": v[used],
            "faces": np.asarray(
                [[remap[int(a)] for a in tri] for tri in sub], np.int64),
        }
    if set(out) != set(REGIONS):
        raise SwatchError(
            f"region split lost {sorted(set(REGIONS) - set(out))}")
    return out


def build_transmission_plates(thickness=2.0) -> dict:
    """Closed thin PLATES for the transmission rig.

    The main swatch's regions are open zero-thickness sheets — right for
    reading a reflection lobe, physically wrong for transmission: a
    single refracting surface BENDS a ray permanently, where a real plate
    (a palette lid, a window) offsets it slightly and lets the scene
    behind stay recognisable. Measuring transmission through an open
    sheet therefore measures an artefact.

    One plate fixture is used for every material in the transmission
    comparison, so the §3 rule stands: the shape never differs between
    the materials being compared.
    """
    s = SWATCH
    out = {}
    specs = {
        "PLANAR": {"w": s["plate_w"], "d": s["plate_d"], "tilt": 0.0,
                   "y": 0.0},
        "GRAZING": {"w": s["grazing_w"], "d": s["grazing_len"],
                    "tilt": s["grazing_deg"],
                    "y": s["plate_d"] + s["gap"]},
    }
    for region, sp in specs.items():
        w, d, t = sp["w"], sp["d"], thickness
        th = math.radians(sp["tilt"])
        x0 = -w / 2.0
        # local frame: u along width, v along the (possibly tilted) face,
        # n the face normal
        verts = []
        for dv in (0.0, d):
            vy = sp["y"] + dv * math.cos(th)
            vz = -dv * math.sin(th)
            for dn in (0.0, -t):
                ny = dn * math.sin(th)
                nz = dn * math.cos(th)
                for du in (0.0, w):
                    verts.append([x0 + du, vy + ny, vz - nz])
        # 8 corners: (v,n,u) order — build the 6 faces of the slab
        idx = lambda v, n, u: v * 4 + n * 2 + u              # noqa: E731
        quads = [
            (idx(0, 0, 0), idx(0, 0, 1), idx(1, 0, 1), idx(1, 0, 0)),
            (idx(0, 1, 1), idx(0, 1, 0), idx(1, 1, 0), idx(1, 1, 1)),
            (idx(0, 0, 0), idx(1, 0, 0), idx(1, 1, 0), idx(0, 1, 0)),
            (idx(0, 0, 1), idx(0, 1, 1), idx(1, 1, 1), idx(1, 0, 1)),
            (idx(0, 0, 0), idx(0, 1, 0), idx(0, 1, 1), idx(0, 0, 1)),
            (idx(1, 0, 0), idx(1, 0, 1), idx(1, 1, 1), idx(1, 1, 0)),
        ]
        faces = []
        for a, b, c, dd in quads:
            faces.append([a, b, c])
            faces.append([a, c, dd])
        v = np.asarray(verts, float)
        f = np.asarray(faces, np.int64)
        a = v[f[:, 0]]
        signed = float(np.einsum("ij,ij->i", a,
                                 np.cross(v[f[:, 1]] - a,
                                          v[f[:, 2]] - a)).sum() / 6.0)
        if signed < 0:
            f = f[:, [0, 2, 1]]
        out[region] = {"name": region, "vertices": v, "faces": f}
    return out
