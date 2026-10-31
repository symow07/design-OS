"""M5 §2-§9 — rendered variant evidence for the material engine.

Every variant renders through ``palt_p1_m4b_evidence.render`` and
``palette_csg_views.py`` — the same production path M4B-B uses. There is
no demonstration renderer: a material engine proven by a bypass would not
be proven at all.

All six variants share one mesh, one camera, one lighting rig, one
assembly state and one frame. Only the material specification changes, so
a difference between two images can only come from the material.

Discrimination is MEASURED from the images. A material family is not
distinct because its JSON differs — two shaders can carry different
numbers and render identically, and that is exactly the failure §5 names.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np
from PIL import Image, ImageDraw

from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_identity as PI
from apps.pipeline.services import palette_material_engine as ME
from apps.pipeline.services import palette_moulded_rect as MR
from apps.pipeline.services import palette_render_contract as RC
from apps.pipeline.services import palt_p1_m4b_evidence as EV
from apps.pipeline.services.palette_review_fonts import font

SCHEMA = "palette_m5_evidence/1.0"

#: §3 — the six required variants, in the order the board presents them.
VARIANT_FILES = (
    ("NEUTRAL_ABS_MATTE", "neutral_abs_matte.png",
     "neutral ABS, matte, opaque"),
    ("DARK_GLOSSY_ABS", "dark_abs_glossy.png",
     "dark ABS, glossy, opaque"),
    ("LIGHT_SATIN_ABS", "light_abs_satin.png",
     "light ABS, satin, opaque"),
    ("METALLIC_ACCENT", "metallic_accent.png",
     "metallic lid, hinge and clasp over a satin base"),
    ("ES3083_SYMBOLIC_ZONES", "es3083_colour_zone_proxy.png",
     "ES3083 zones — PANTONE 621 C / 627 C shown as labelled proxies"),
    ("OWNER_SUBSTITUTED_COLOUR", "arbitrary_colour_substitution.png",
     "an arbitrary owner-selected colour on a different base material"),
)

#: §5 — the pairwise discriminations, each rendered on the same geometry.
PAIRWISE = (
    ("matte_vs_glossy_detail.png", ME.MATTE, ME.GLOSSY, ME.ABS, ME.ABS),
    ("matte_vs_satin_detail.png", ME.MATTE, ME.SATIN, ME.ABS, ME.ABS),
    ("glossy_vs_metallic_detail.png", ME.GLOSSY, ME.METALLIC, ME.ABS,
     ME.METAL),
    ("opaque_vs_transparent_detail.png", ME.MATTE, ME.TRANSPARENT, ME.ABS,
     ME.ACRYLIC),
    ("opaque_vs_translucent_detail.png", ME.MATTE, ME.TRANSLUCENT, ME.ABS,
     ME.ACRYLIC),
)

#: Predeclared. Two renders are distinguishable when they differ by at
#: least this much on at least one measured axis. Fixed before any pair
#: was measured.
MINIMUM_DISCRIMINATION = {
    "mean_luminance": 6.0,
    "highlight_fraction": 0.010,
    "highlight_p99": 10.0,
    "specular_spread": 4.0,
}

PAPER = (250, 249, 246)
INK = (28, 28, 32)
GREY = (110, 110, 118)
RED = (198, 48, 42)


class M5EvidenceError(RuntimeError):
    """Raised when M5 evidence cannot be produced honestly."""


# --------------------------------------------------------------------------
# rendering through the production path
# --------------------------------------------------------------------------

def _fixture():
    """PALT-P1B ES3083 — the M5 visual fixture, unchanged."""
    comps, dims = MR.build_rect_components(OC.confirmed_intent())
    state = MR.compose_rect_state(comps, dims, "OPEN_REVIEW_ANGLE")
    pts = np.concatenate([c["vertices"] for c in state.values()])
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    return {
        "components": comps, "dims": dims, "state": state,
        "centre": tuple(((lo + hi) / 2.0).tolist()),
        "ortho_scale": float(max(hi - lo)) * RC.FRAME_MARGIN,
        "geometry_identity": assembly_identity(comps),
    }


def assembly_identity(components) -> str:
    """One identity for the whole assembly, so 'same geometry' is a
    statement about every component rather than a sampled one."""
    ids = {n: PI.mesh_geometry_identity(c)
           for n, c in sorted(components.items())}
    return hashlib.sha256(
        repr(sorted(ids.items())).encode()).hexdigest()[:16]


def render_variant(fixture, contract, out_path, *, samples=40) -> dict:
    """One variant through the real render path."""
    resolved = contract.resolve(fixture["state"].keys())
    EV.render(fixture["state"],
              {"three_quarter": os.path.basename(out_path)},
              os.path.dirname(out_path),
              centre=fixture["centre"],
              ortho_scale=fixture["ortho_scale"],
              samples=samples,
              distance=max(520.0, fixture["ortho_scale"] * 4.0),
              materials=resolved,
              light_policy=RC.m5_material_config())
    if not os.path.exists(out_path):
        raise M5EvidenceError(f"{out_path} was not written")
    return {
        "path": out_path,
        "mesh_geometry_identity": fixture["geometry_identity"],
        "material_contract_identity": contract.identity(),
        "evidence_package_identity": ME.evidence_identity(
            fixture["geometry_identity"], contract),
        "renderer": "palette_csg_views.py (the production path)",
        "camera": "three_quarter",
        "state": "OPEN_REVIEW_ANGLE",
        "ortho_scale": fixture["ortho_scale"],
    }


# --------------------------------------------------------------------------
# §5 — measured visual discrimination
# --------------------------------------------------------------------------

def optical_signature(path) -> dict:
    """Measurable optical behaviour of a rendered material.

    Highlight width and intensity, the diffuse/specular split and the
    spread of bright pixels are what actually separate a matte from a
    gloss on screen. They are read from the subject only, so the backdrop
    cannot carry a difference.
    """
    arr = np.asarray(Image.open(path).convert("RGB")).astype(float)
    lum = arr.mean(axis=2)
    h, w = lum.shape
    band = max(2, int(min(h, w) * 0.05))
    border = np.concatenate([lum[:band].ravel(), lum[-band:].ravel(),
                             lum[:, :band].ravel(), lum[:, -band:].ravel()])
    bg = float(np.median(border))
    subject = np.abs(lum - bg) > 8
    if subject.sum() < 100:
        raise M5EvidenceError(f"{path}: no subject to measure")
    vals = lum[subject]
    p99 = float(np.percentile(vals, 99))
    hi = vals > (float(np.percentile(vals, 50)) + 0.45 * (p99 - float(
        np.percentile(vals, 50))))
    return {
        "mean_luminance": round(float(vals.mean()), 4),
        "median_luminance": round(float(np.median(vals)), 4),
        "highlight_p99": round(p99, 4),
        "highlight_fraction": round(float(hi.mean()), 6),
        "specular_spread": round(float(vals.std()), 4),
        "subject_fraction": round(float(subject.mean()), 6),
        "saturation_mean": round(
            float((arr.max(axis=2) - arr.min(axis=2))[subject].mean()), 4),
    }


def discriminate(sig_a, sig_b, label_a, label_b) -> dict:
    """Do two renders actually look different?"""
    axes = {}
    passed = []
    for axis, bar in MINIMUM_DISCRIMINATION.items():
        delta = abs(sig_a[axis] - sig_b[axis])
        axes[axis] = {"a": sig_a[axis], "b": sig_b[axis],
                      "delta": round(delta, 6), "bar": bar,
                      "clears": bool(delta >= bar)}
        if delta >= bar:
            passed.append(axis)
    return {
        "a": label_a, "b": label_b, "axes": axes,
        "axes_clearing_the_bar": passed,
        "verdict": "PASS" if passed else "FAIL",
        "why": "two renders are distinguishable when they differ by at "
               "least the predeclared bar on at least one measured axis; "
               "differing JSON is not evidence",
    }


def _pair_contract(finish_a, finish_b, material_a, material_b):
    """Two contracts differing only in material and finish."""
    grey = ME.Colour(rgb=(0.62, 0.62, 0.63))
    pan = ME.MaterialAssignment("metal_pan_", ME.METAL, ME.SATIN,
                                ME.Colour(rgb=(0.72, 0.73, 0.75)))
    powder = ME.MaterialAssignment("powder_", ME.ABS, ME.MATTE,
                                   ME.Colour(rgb=(0.36, 0.30, 0.28)))
    a = ME.MaterialContract(
        f"{material_a}_{finish_a}",
        [ME.MaterialAssignment("*", material_a, finish_a, grey), pan,
         powder])
    b = ME.MaterialContract(
        f"{material_b}_{finish_b}",
        [ME.MaterialAssignment("*", material_b, finish_b, grey), pan,
         powder])
    return a, b


# --------------------------------------------------------------------------
# boards
# --------------------------------------------------------------------------

def _label(img, title, subtitle, note="", note_colour=RED):
    w = img.width
    head = 150 if note else 118
    out = Image.new("RGB", (w, img.height + head), PAPER)
    out.paste(img, (0, head))
    d = ImageDraw.Draw(out)
    d.text((26, 22), title, font=font(34), fill=INK)
    d.text((26, 66), subtitle, font=font(22), fill=GREY)
    if note:
        d.text((26, 104), note, font=font(21), fill=note_colour)
    return out


def variant_board(records, out_png, out_pdf, *, geometry_identity):
    """§8 — the six variants on one board."""
    tiles = []
    for name, filename, means in VARIANT_FILES:
        rec = records[name]
        img = Image.open(rec["path"]).convert("RGB").resize((760, 760))
        note = ""
        if rec.get("proxy_tokens"):
            note = ("PROVISIONAL_VISUAL_PROXY — "
                    + ", ".join(rec["proxy_tokens"])
                    + " shown VISUALIZATION_ONLY; no colour accuracy "
                      "claimed")
        tiles.append(_label(img, name.replace("_", " "), means, note))
    cols, tw, th = 3, tiles[0].width, max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    board = Image.new("RGB", (cols * tw + 60, rows * th + 260), PAPER)
    d = ImageDraw.Draw(board)
    d.text((30, 34), "M5 — MATERIAL VARIANT BOARD", font=font(52),
           fill=INK)
    d.text((30, 100),
           "one mesh, one camera, one lighting rig, one frame — only the "
           "material specification changes", font=font(26), fill=GREY)
    d.text((30, 140), f"MESH_GEOMETRY_IDENTITY {geometry_identity} — "
                      "identical for every tile", font=font(24), fill=INK)
    for i, tile in enumerate(tiles):
        board.paste(tile, (30 + (i % cols) * tw, 200 + (i // cols) * th))
    d.text((30, board.height - 56),
           "PALT_P1_FINAL_DIMENSIONS: NOT_APPROVED · "
           "PALT_P1_MANUFACTURING_AUTHORITY: NOT_ESTABLISHED · "
           "Pantone tokens remain the colour authority",
           font=font(22), fill=GREY)
    board.save(out_png)
    board.convert("RGB").save(out_pdf, "PDF", resolution=150.0)
    return out_png, out_pdf


def pair_board(path_a, path_b, out_path, title, subtitle, report):
    """A side-by-side pair with its measured deltas printed on it."""
    a = Image.open(path_a).convert("RGB").resize((900, 900))
    b = Image.open(path_b).convert("RGB").resize((900, 900))
    out = Image.new("RGB", (a.width + b.width + 60, 900 + 420), PAPER)
    out.paste(a, (20, 190))
    out.paste(b, (a.width + 40, 190))
    d = ImageDraw.Draw(out)
    d.text((26, 34), title, font=font(46), fill=INK)
    d.text((26, 96), subtitle, font=font(26), fill=GREY)
    d.text((26, 134), f"verdict: {report['verdict']}", font=font(28),
           fill=(44, 150, 92) if report["verdict"] == "PASS" else RED)
    d.text((26, 1100), report["a"], font=font(26), fill=INK)
    d.text((a.width + 40, 1100), report["b"], font=font(26), fill=INK)
    y = 1150
    for axis, row in report["axes"].items():
        mark = "clears" if row["clears"] else "below bar"
        d.text((26, y), f"{axis}: {row['a']} vs {row['b']}  "
                        f"delta {row['delta']}  bar {row['bar']}  "
                        f"[{mark}]",
               font=font(23),
               fill=INK if row["clears"] else GREY)
        y += 32
    out.save(out_path)
    return out_path


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

def build_m5_evidence(out_dir, *, samples=40) -> dict:
    """Render every variant and every pair, then measure them."""
    os.makedirs(out_dir, exist_ok=True)
    fixture = _fixture()
    gid = fixture["geometry_identity"]
    contracts = ME.variant_contracts()

    records, signatures = {}, {}
    for name, filename, _means in VARIANT_FILES:
        contract = contracts[name]
        rec = render_variant(fixture, contract,
                             os.path.join(out_dir, filename),
                             samples=samples)
        rec["proxy_tokens"] = sorted({
            a.colour.name for a in contract.assignments
            if a.colour.kind == ME.SYMBOLIC})
        records[name] = rec
        signatures[name] = optical_signature(rec["path"])

    board_png, board_pdf = variant_board(
        records, os.path.join(out_dir, "m5_material_variant_board.png"),
        os.path.join(out_dir, "m5_material_variant_board.pdf"),
        geometry_identity=gid)

    pairs = []
    for filename, fa, fb, ma, mb in PAIRWISE:
        ca, cb = _pair_contract(fa, fb, ma, mb)
        pa = os.path.join(out_dir, f"_pair_{fa}_{ma}.png")
        pb = os.path.join(out_dir, f"_pair_{fb}_{mb}.png")
        for contract, path in ((ca, pa), (cb, pb)):
            if not os.path.exists(path):
                render_variant(fixture, contract, path, samples=samples)
        report = discriminate(optical_signature(pa), optical_signature(pb),
                              f"{ma} {fa}", f"{mb} {fb}")
        report["image"] = pair_board(
            pa, pb, os.path.join(out_dir, filename),
            filename.replace("_detail.png", "").replace("_", " ").upper(),
            "same mesh, same camera, same light — only the material "
            "differs", report)
        report["pair"] = filename
        pairs.append(report)

    # the negative control: a material compared with ITSELF must fail
    control_path = os.path.join(out_dir, "_pair_MATTE_ABS.png")
    control = discriminate(optical_signature(control_path),
                           optical_signature(control_path),
                           "ABS MATTE", "ABS MATTE (same render)")
    control["pair"] = "NEGATIVE_CONTROL_SELF_COMPARISON"

    failed = [p["pair"] for p in pairs if p["verdict"] == "FAIL"]
    meshes = {r["mesh_geometry_identity"] for r in records.values()}
    materials = {r["material_contract_identity"] for r in records.values()}
    evidence = {r["evidence_package_identity"] for r in records.values()}

    manifest = {
        "record_type": "material_identity_manifest/1.0",
        "fixture": "PALT-P1B ES3083",
        "mesh_geometry_identity": gid,
        "distinct_mesh_identities": len(meshes),
        "distinct_material_identities": len(materials),
        "distinct_evidence_identities": len(evidence),
        "variants": {k: {kk: vv for kk, vv in v.items() if kk != "path"}
                     for k, v in records.items()},
        "optical_signatures": signatures,
        "render_contract_identity": RC.contract_identity(),
        "renderer": "palette_csg_views.py (the production path)",
        "separate_demonstration_renderer": False,
    }
    discrimination = {
        "record_type": "material_discrimination_report/1.0",
        "predeclared_bars": dict(MINIMUM_DISCRIMINATION),
        "bars_predeclared_before_measurement": True,
        "pairs": pairs,
        "negative_control": control,
        "negative_control_verdict_must_be": "FAIL",
        "negative_control_behaved": control["verdict"] == "FAIL",
        "failed_pairs": failed,
        "MATERIAL_DIFFERENTIATION":
            "PASS" if not failed and control["verdict"] == "FAIL"
            else "FAIL",
    }
    return {
        "record_type": SCHEMA, "out_dir": out_dir,
        "board_png": board_png, "board_pdf": board_pdf,
        "identity_manifest": manifest,
        "discrimination_report": discrimination,
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("M5 §5 visual legibility: a human-view property, declared on the review frame")
