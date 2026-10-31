"""ARIA Visual Inspector — input quality gate (VQ-VISUALIZER-CORR-2).

The IT5 inspection returned a confident "flat-topped cylinder" verdict on a
dome that was 27 pixels high in the submitted image. The model was not at
fault; it was starved of pixels. This module makes that impossible: no
multimodal call may run until the target component clears a legibility
floor measured in the ACTUAL bytes that will be sent.

Two rules the gate exists to enforce:

* fail closed. When the target is below floor, clipped, unverifiable or
  the evidence packet is incomplete, the result is
  ``INSPECTION_NOT_PERFORMED_INPUT_QUALITY_FAILED`` — never
  ``VISUALLY_REJECTED``. An invalid packet cannot produce a verdict
  against the geometry.
* upscaling buys legibility, never evidence. Enlarged crops are for
  qualitative multimodal judgment only; topology, coordinates, ratios and
  symmetry are always measured on the original image.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

QUALITY_SCHEMA = "visual_inspector_input_quality/1.0"
MANIFEST_SCHEMA = "visual_inspector_input_manifest/1.0"

INSPECTION_NOT_PERFORMED = "INSPECTION_NOT_PERFORMED_INPUT_QUALITY_FAILED"
PASSED, FAILED = "PASSED", "FAILED"

# §2 / §9 stable findings
VQ_TARGET_COMPONENT_TOO_SMALL = "VQ_VISUALIZER_TARGET_COMPONENT_TOO_SMALL"
VQ_COMPONENT_LEGIBILITY_FAILED = "VQ_VISUALIZER_COMPONENT_LEGIBILITY_FAILED"
VQ_EVIDENCE_PACKET_INCOMPLETE = "VQ_VISUALIZER_EVIDENCE_PACKET_INCOMPLETE"
VQ_VERDICT_NOT_ACTIONABLE = "VQ_VISUALIZER_VERDICT_NOT_ACTIONABLE"
VQ_INPUT_QUALITY_GATE_MISSING = "VQ_VISUALIZER_INPUT_QUALITY_GATE_MISSING"
VQ_INPUT_RESOLUTION_INSUFFICIENT = \
    "VQ_VISUALIZER_INPUT_RESOLUTION_INSUFFICIENT"
VQ_TARGET_CLIPPED = "VQ_VISUALIZER_TARGET_CLIPPED"
VQ_SCALE_MISMATCH = "VQ_VISUALIZER_REFERENCE_CANDIDATE_SCALE_MISMATCH"
VQ_REQUIRED_CROP_MISSING = "VQ_VISUALIZER_REQUIRED_CROP_MISSING"
VQ_INPUT_HASH_MISMATCH = "VQ_VISUALIZER_INPUT_HASH_MISMATCH"

#: §4 model-input legibility floors in PIXELS. These are not production
#: dimensions and carry no geometric authority.
LEGIBILITY_FLOORS = {
    "FULL_ASSEMBLY": {"min_height_px": 512, "min_width_px": 180},
    "CLOSURE": {"min_height_px": 420, "min_width_px": 180},
    "DARK_CLOSURE": {"min_height_px": 300, "min_width_px": 100},
    "DOME_APEX": {"min_height_px": 120, "min_width_px": 60,
                  "min_distinguishable_top_rows": 20},
    "COLLAR": {"min_height_px": 160, "min_width_px": 180},
    "NECK_VISIBLE": {"min_height_px": 80, "min_width_px": 60},
    "SHOULDER": {"min_height_px": 80, "min_width_px": 300},
}

#: §4 normalized y-bands used to locate a component inside an assembly
#: silhouette. Mirrors the concept envelope's own banding.
COMPONENT_Y_BANDS = {
    "FULL_ASSEMBLY": (0.0, 1.0),
    "CLOSURE": (0.0, 0.36),
    "DARK_CLOSURE": (0.0, 0.1875),
    "DOME_APEX": (0.0, 0.055),
    "COLLAR": (0.1875, 0.356),
    "NECK_VISIBLE": (0.356, 0.377),
    "SHOULDER": (0.377, 0.415),
    "BODY_BASE": (0.415, 1.0),
}

#: §5 crops a structural comparison may need
SUGGESTED_CROPS = ("FULL_ASSEMBLY", "CLOSURE", "DARK_CLOSURE", "DOME_APEX",
                   "COLLAR", "NECK_VISIBLE", "SHOULDER", "BODY_BASE")

#: §7 evidence a structural comparison call must carry
REQUIRED_EVIDENCE = ("full_reference", "reference_component_crop",
                     "full_candidate", "candidate_component_crop")
COMPARATIVE_EVIDENCE = ("previous_candidate", "equal_scale_overlay")

#: §10 authority hierarchy — persisted so it cannot drift
VERDICT_AUTHORITY = {
    "deterministic_output_pixel_analysis_governs": [
        "apex topology", "contour coordinates", "pixel width",
        "pixel height", "numeric ratios", "clipping", "symmetry",
        "component bounds"],
    "multimodal_inspection_governs": [
        "semantic resemblance", "perceived form",
        "qualitative proportional balance",
        "generic-versus-reference character",
        "visual improvement or regression"],
    "human_governs": ["final structural acceptance", "semantic approval",
                      "whether another correction is authorized"],
    "multimodal_may_override_deterministic_pixel_topology": False,
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def sha256(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# --- measurement on the ACTUAL bytes -----------------------------------------

def measure_component(path: str, component: str, *,
                      bands: dict | None = None) -> dict:
    """Locate a component in the real pixels of ``path`` and report its
    size. Never uses pre-render vector data."""
    import numpy as np
    from PIL import Image

    band = (bands or COMPONENT_Y_BANDS).get(component)
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(float)
    bg = np.median(np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]]), axis=0)
    mask = np.sqrt(((a - bg) ** 2).sum(axis=2)) > 10
    rows = [y for y in range(mask.shape[0]) if mask[y].any()]
    if not rows:
        return {"component": component, "found": False,
                "image_size": list(im.size), "width_px": 0, "height_px": 0}
    top, bot = rows[0], rows[-1]
    span = max(bot - top, 1)
    if band is None:
        y0, y1 = top, bot
    else:
        y0 = int(top + span * band[0])
        y1 = max(y0 + 1, int(top + span * band[1]))
    seg = [y for y in range(y0, min(y1 + 1, mask.shape[0])) if mask[y].any()]
    if not seg:
        return {"component": component, "found": False,
                "image_size": list(im.size), "width_px": 0, "height_px": 0}
    xs = [int(np.flatnonzero(mask[y])[0]) for y in seg]
    xe = [int(np.flatnonzero(mask[y])[-1]) for y in seg]
    left, right = min(xs), max(xe)
    h, w = im.size[1], im.size[0]
    # a component crop legitimately continues past its BOTTOM edge (the
    # rest of the assembly is below it). Truncation that actually hides
    # the component is horizontal, or off the top.
    truncated_sides = left <= 0 or right >= w - 1
    truncated_top = min(seg) <= 0
    continues_below = max(seg) >= h - 1
    touches = truncated_sides or truncated_top
    area = (right - left + 1) * (max(seg) - min(seg) + 1)
    return {"component": component, "found": True,
            "image_size": [w, h],
            "bbox": [left, min(seg), right, max(seg)],
            "width_px": right - left + 1,
            "height_px": max(seg) - min(seg) + 1,
            "percent_of_image": round(100.0 * area / (w * h), 3),
            "touches_image_edge": bool(touches),
            "truncated_sides": bool(truncated_sides),
            "truncated_top": bool(truncated_top),
            "continues_below_frame": bool(continues_below),
            "assembly_top_px": top, "assembly_bottom_px": bot}


def _sharpness(path: str) -> float:
    import numpy as np
    from PIL import Image
    g = np.asarray(Image.open(path).convert("L")).astype(float)
    gx = np.abs(np.diff(g, axis=1)).mean()
    gy = np.abs(np.diff(g, axis=0)).mean()
    return round(float(gx + gy), 4)


def _contrast(path: str) -> float:
    import numpy as np
    from PIL import Image
    g = np.asarray(Image.open(path).convert("L")).astype(float)
    return round(float(g.max() - g.min()), 2)


# --- §3 the gate ---------------------------------------------------------------

def evaluate_input_quality(*, component: str, candidate_path: str,
                           reference_path: str | None = None,
                           evidence: dict | None = None,
                           expected_hashes: dict | None = None,
                           floors: dict | None = None,
                           override_record: dict | None = None) -> dict:
    """§3 — run BEFORE any multimodal call. Fails closed."""
    ev = dict(evidence or {})
    floor = dict((floors or LEGIBILITY_FLOORS).get(component, {}))
    if override_record:
        # §4 an override is only honoured through an explicit reviewed
        # record; thresholds are never lowered silently
        if override_record.get("reviewed") and override_record.get("reason"):
            floor.update(override_record.get("floors", {}))
    m = measure_component(candidate_path, component)
    findings, checks = [], {}

    checks["target_found"] = m.get("found", False)
    checks["meets_min_height"] = (
        m.get("height_px", 0) >= floor.get("min_height_px", 0))
    checks["meets_min_width"] = (
        m.get("width_px", 0) >= floor.get("min_width_px", 0))
    if not (checks["meets_min_height"] and checks["meets_min_width"]):
        findings += [VQ_TARGET_COMPONENT_TOO_SMALL,
                     VQ_COMPONENT_LEGIBILITY_FAILED,
                     VQ_INPUT_RESOLUTION_INSUFFICIENT]
    checks["not_clipped"] = not m.get("touches_image_edge", True)
    if not checks["not_clipped"]:
        findings.append(VQ_TARGET_CLIPPED)

    checks["sharp_enough"] = _sharpness(candidate_path) > 0.5
    checks["contrast_sufficient"] = _contrast(candidate_path) > 40
    checks["aspect_preserved"] = bool(
        ev.get("aspect_preserved", True))

    for key in REQUIRED_EVIDENCE:
        present = bool(ev.get(key))
        checks[f"evidence_{key}"] = present
        if not present:
            findings.append(VQ_REQUIRED_CROP_MISSING
                            if "crop" in key else
                            VQ_EVIDENCE_PACKET_INCOMPLETE)
    if ev.get("comparative_judgment_requested"):
        for key in COMPARATIVE_EVIDENCE:
            checks[f"evidence_{key}"] = bool(ev.get(key))
            if not ev.get(key):
                findings.append(VQ_EVIDENCE_PACKET_INCOMPLETE)

    ok_hash = True
    for label, expected in (expected_hashes or {}).items():
        actual = ev.get(label)
        if actual and os.path.exists(actual):
            if sha256(actual) != expected:
                ok_hash = False
    checks["labels_match_bytes"] = ok_hash
    if not ok_hash:
        findings.append(VQ_INPUT_HASH_MISMATCH)

    if reference_path and os.path.exists(reference_path):
        rm = measure_component(reference_path, "FULL_ASSEMBLY")
        cand_h = m.get("height_px", 1) or 1
        ratio = (rm.get("height_px", 1) or 1) / cand_h
        checks["reference_candidate_scale_compatible"] = 0.2 <= ratio <= 5.0
        if not checks["reference_candidate_scale_compatible"]:
            findings.append(VQ_SCALE_MISMATCH)

    passed = all(checks.values())
    return {
        "schema_version": QUALITY_SCHEMA, "evaluated_at": _now(),
        "component_under_review": component,
        "candidate_path": candidate_path,
        "candidate_sha256": sha256(candidate_path)
        if os.path.exists(candidate_path) else None,
        "measurement": m, "floors_applied": floor,
        "override_record": override_record,
        "checks": checks, "findings": sorted(set(findings)),
        "quality_gate": PASSED if passed else FAILED,
        "verdict_if_failed": None if passed else INSPECTION_NOT_PERFORMED,
        "note": "these are model-input legibility floors, not production "
                "dimensions; they carry no geometric authority",
    }


# --- §5/§6 crop generation -----------------------------------------------------

def generate_component_crop(path: str, component: str, out_dir: str, *,
                            context: float = 0.15,
                            target_height: int | None = None,
                            bands: dict | None = None) -> dict:
    """Lossless component crop from the candidate itself, optionally
    enlarged for legibility. Records full SHA lineage and the exact
    scaling applied. No generative upscaling, ever."""
    from PIL import Image

    os.makedirs(out_dir, exist_ok=True)
    m = measure_component(path, component, bands=bands)
    if not m.get("found"):
        return {"component": component, "created": False,
                "reason": VQ_REQUIRED_CROP_MISSING}
    im = Image.open(path).convert("RGB")
    x0, y0, x1, y1 = m["bbox"]
    pad_x = int((x1 - x0 + 1) * context)
    pad_y = int((y1 - y0 + 1) * context)
    box = (max(0, x0 - pad_x), max(0, y0 - pad_y),
           min(im.width, x1 + 1 + pad_x), min(im.height, y1 + 1 + pad_y))
    crop = im.crop(box)
    floor = LEGIBILITY_FLOORS.get(component, {})
    want = target_height or floor.get("min_height_px", 0)
    scale = 1.0
    if want and crop.height < want:
        scale = want / crop.height
        crop = crop.resize((max(1, int(crop.width * scale)),
                            max(1, int(crop.height * scale))),
                           Image.LANCZOS)
    name = f"{os.path.splitext(os.path.basename(path))[0]}_{component.lower()}.png"
    out = os.path.join(out_dir, name)
    crop.save(out)
    return {
        "component": component, "created": True, "path": out,
        "source_path": path, "source_sha256": sha256(path),
        "crop_sha256": sha256(out),
        "original_dimensions": [im.width, im.height],
        "component_bbox": m["bbox"],
        "crop_bounds": list(box),
        "crop_dimensions_before_scaling": [box[2] - box[0], box[3] - box[1]],
        "scale_factor": round(scale, 4),
        "scaling_algorithm": "LANCZOS" if scale != 1.0 else "NONE",
        "output_dimensions": [crop.width, crop.height],
        "aspect_preserved": True,
        "generative_upscaling": False,
        "clipped": m.get("touches_image_edge", False),
        "evidence_status": "LEGIBILITY_ONLY_NOT_NEW_GEOMETRIC_EVIDENCE",
        "topology_authority": "the ORIGINAL image governs topology, "
                              "coordinates, ratios and symmetry",
    }


def build_manifest(*, inspection_id: str, purpose: str, component: str,
                   images: list, quality: dict, model: str,
                   prompt_version: str, semantic_state: str,
                   human_findings=(), response_id: str = "") -> dict:
    """§8 — no call is permitted unless quality_gate == PASSED."""
    return {
        "schema_version": MANIFEST_SCHEMA, "created_at": _now(),
        "inspection_identity": inspection_id, "purpose": purpose,
        "component_under_review": component,
        "images": images,
        "image_order": [i.get("label") for i in images],
        "semantic_state": semantic_state,
        "human_findings": list(human_findings),
        "prompt_version": prompt_version, "model": model,
        "quality_gate": quality["quality_gate"],
        "quality_findings": quality["findings"],
        "response_identity": response_id,
        "call_permitted": quality["quality_gate"] == PASSED,
        "verdict_authority": VERDICT_AUTHORITY,
        "credentials_persisted": False,
    }


def gated_inspection(*, component: str, candidate_path: str,
                     reference_path: str, evidence: dict,
                     run_fn, inspection_id: str = "",
                     model: str = "", prompt_version: str = "",
                     semantic_state: str = "", human_findings=(),
                     expected_hashes: dict | None = None,
                     override_record: dict | None = None) -> dict:
    """Run ``run_fn`` ONLY behind a passing quality gate. On failure the
    result is INSPECTION_NOT_PERFORMED_INPUT_QUALITY_FAILED with no model
    call — an invalid packet must never yield VISUALLY_REJECTED."""
    q = evaluate_input_quality(
        component=component, candidate_path=candidate_path,
        reference_path=reference_path, evidence=evidence,
        expected_hashes=expected_hashes, override_record=override_record)
    images = [{"label": k, "path": v,
               "sha256": sha256(v) if isinstance(v, str)
               and os.path.exists(v) else None}
              for k, v in evidence.items() if isinstance(v, str)]
    manifest = build_manifest(
        inspection_id=inspection_id, purpose="structural comparison",
        component=component, images=images, quality=q, model=model,
        prompt_version=prompt_version, semantic_state=semantic_state,
        human_findings=human_findings)
    if q["quality_gate"] != PASSED:
        return {"verdict": INSPECTION_NOT_PERFORMED,
                "model_called": False, "result": None,
                "input_quality": q, "manifest": manifest,
                "findings": q["findings"] + [VQ_VERDICT_NOT_ACTIONABLE],
                "note": "no multimodal call was made; an invalid input "
                        "packet cannot produce a verdict against the "
                        "geometry"}
    result = run_fn()
    return {"verdict": None, "model_called": True, "result": result,
            "input_quality": q, "manifest": manifest, "findings": []}


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("input QC of inherently 8-bit sources — the display frame is the authentic artifact")
