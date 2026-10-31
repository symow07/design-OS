"""VQR-2B-A — deterministic, reconstruction-independent concept analysis.

``product_container_concept_analysis/1.0`` describes the SELECTED concept's
visible product structure from local pixel evidence only: mask extraction,
mask-quality validation, image-space/normalized measurements, and an
analyzability classification that feeds the future Concept Quality Gate.

Hard boundaries (VQR-2B-A brief):

* reconstruction-independent — this module never reads reconstructed AI/PNG,
  the Design Graph, reconstruction status or production geometry; it has no
  imports from those modules and takes plain PIL images;
* deterministic local analysis only — Pillow + NumPy; no provider vision,
  no OCR, no semantic segmentation, no generative tooling;
* fail-closed — a mask that cannot be defended is UNMEASURABLE and produces
  NO measurements; a low-quality threshold mask is never labeled accurate;
* image-space / normalized measurements only — never millimetres, capacity,
  materials or manufacturing facts;
* the SELECTED_CONCEPT_SILHOUETTE_FIDELITY axis stays
  UNMEASURED_PENDING_VQR_2B_B — comparison against reconstruction is
  VQR-2B-B's job, not this module's.

Contour representation: a fixed-count width-at-height profile sampled inside
the mask bounding box (plus left/right edge profiles). It is translation-
invariant (bbox-relative) and scale-normalized (divided by bbox extent).
LIMITATIONS (recorded, §12): designed for front-facing standard containers
on resolvable backgrounds; it does NOT support perspective concepts,
multi-product scenes or occluded silhouettes — those classify PARTIAL or
UNMEASURABLE instead of pretending.
"""
from __future__ import annotations

from collections import deque

import numpy as np
from PIL import Image
from apps.pipeline.services import palette_firing_trace as FT

SCHEMA = "product_container_concept_analysis/1.0"

MEASURED = "MEASURED"
PARTIAL = "PARTIAL"
UNMEASURABLE = "UNMEASURABLE"

READY = "CONCEPT_ANALYSIS_READY"
PARTIAL_CLASS = "CONCEPT_ANALYSIS_PARTIAL"
UNMEASURABLE_CLASS = "CONCEPT_ANALYSIS_UNMEASURABLE"

ALPHA = "ALPHA"
BACKGROUND_SEGMENTATION = "BACKGROUND_SEGMENTATION"
OWNER_GOLDEN_MASK = "OWNER_GOLDEN_MASK"

# §1 owner correction (2026-08-03): MASK AUTHORITY is reported separately
# from the extraction method — an outline-fill result is DERIVED evidence
# and never upgrades to HIGH confidence merely for being deterministic
MASK_AUTHORITY_OWNER_GOLDEN = "OWNER_GOLDEN"
MASK_AUTHORITY_DIRECT = "DIRECT_PIXEL_EVIDENCE"
MASK_AUTHORITY_OUTLINE_FILL = "OUTLINE_FILL_DERIVED"

# §8 stable reason codes
CONCEPT_PRODUCT_CROPPED = "CONCEPT_PRODUCT_CROPPED"
CONCEPT_CLOSURE_HIDDEN = "CONCEPT_CLOSURE_HIDDEN"
CONCEPT_MULTIPLE_PRODUCTS = "CONCEPT_MULTIPLE_PRODUCTS"
CONCEPT_EXCESSIVE_PERSPECTIVE = "CONCEPT_EXCESSIVE_PERSPECTIVE"
CONCEPT_BACKGROUND_UNRESOLVED = "CONCEPT_BACKGROUND_UNRESOLVED"
CONCEPT_MASK_FRAGMENTED = "CONCEPT_MASK_FRAGMENTED"
CONCEPT_FRAME_CONTACT = "CONCEPT_FRAME_CONTACT"
CONCEPT_PRODUCT_TOO_SMALL = "CONCEPT_PRODUCT_TOO_SMALL"
CONCEPT_HEAVY_SHADOW_INTERFERENCE = "CONCEPT_HEAVY_SHADOW_INTERFERENCE"
CONCEPT_SILHOUETTE_AMBIGUOUS = "CONCEPT_SILHOUETTE_AMBIGUOUS"
CONCEPT_MASK_EMPTY = "CONCEPT_MASK_EMPTY"
CONCEPT_MASK_FRAME_FILLING = "CONCEPT_MASK_FRAME_FILLING"

# ---------------------------------------------------------------------------
# deterministic analysis constants — versioned, documented, testable
PARAMS = {
    "version": "concept_analysis_params/1.0",
    "alpha_threshold": 128,          # alpha >= threshold → product
    "alpha_min_transparent_ratio": 0.02,   # else the channel is decorative
    "bg_distance_threshold": 30.0,   # L2 RGB distance from border colour
    # background resolution is MEDIAN-based so a product touching the frame
    # does not poison the estimate: at least this fraction of border pixels
    # must agree with the median border colour, else UNRESOLVED
    "border_agreement_min": 0.70,
    "min_coverage": 0.005,
    "max_coverage": 0.90,            # beyond → frame-filling, not a product
    "min_product_px": 24,            # bbox side floor (task-57's 1px fails)
    "component_scale_max": 512,      # labeling runs on a bounded downscale
    "largest_component_min_ratio": 0.85,
    "major_component_ratio": 0.10,   # second component ≥ this → multiple
    "noise_ratio_max": 0.06,
    "edge_contact_report_px": 2,     # mask pixels on the frame → contact
    "profile_samples": 64,
    "closure_narrow_ratio": 0.72,    # sustained top narrowing → closure zone
    # §6 hole suppression: interior regions unreachable from the border are
    # filled (a line-drawn concept yields an outline ring; the PRODUCT is
    # the enclosed region). A large filled fraction is reported honestly.
    "hole_fill_report_ratio": 0.25,
    "closure_min_band": 0.04,        # ≥ this height fraction to be a zone
    "symmetry_warn": 0.06,           # mean |left+right| asymmetry warning
}


# ---------------------------------------------------------------------------
# mask extraction (§5) — preferred order: golden, alpha, background, none


def _as_rgba(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("RGBA"), dtype=np.uint8)


def extract_mask(img: Image.Image, *, golden_mask: Image.Image | None = None):
    """(mask bool array | None, method, confidence, warnings)."""
    warnings: list[str] = []
    if golden_mask is not None:
        gm = np.asarray(golden_mask.convert("L"), dtype=np.uint8)
        if gm.shape[:2] != (img.height, img.width):
            return None, OWNER_GOLDEN_MASK, "LOW", \
                ["golden mask dimensions do not match the source image"]
        return gm >= 128, OWNER_GOLDEN_MASK, "HIGH", warnings

    arr = _as_rgba(img)
    alpha = arr[..., 3]
    transparent_ratio = float((alpha < PARAMS["alpha_threshold"]).mean())
    if transparent_ratio >= PARAMS["alpha_min_transparent_ratio"]:
        return alpha >= PARAMS["alpha_threshold"], ALPHA, "HIGH", warnings

    rgb = arr[..., :3].astype(np.float64)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    med = np.median(border, axis=0)
    border_dist = np.sqrt(((border - med) ** 2).sum(axis=-1))
    agreeing = border_dist <= PARAMS["bg_distance_threshold"]
    if float(agreeing.mean()) < PARAMS["border_agreement_min"]:
        return None, BACKGROUND_SEGMENTATION, "LOW", \
            [CONCEPT_BACKGROUND_UNRESOLVED]
    bg = border[agreeing].mean(axis=0)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=-1))
    mask = dist > PARAMS["bg_distance_threshold"]
    return mask, BACKGROUND_SEGMENTATION, "MEDIUM", warnings


# ---------------------------------------------------------------------------
# component labeling — BFS on a bounded deterministic downscale (no scipy)


def _label_scale(mask: np.ndarray):
    h, w = mask.shape
    cap = PARAMS["component_scale_max"]
    if max(h, w) <= cap:
        return mask
    factor = max(h, w) / cap
    img = Image.fromarray((mask * 255).astype(np.uint8))
    small = img.resize((max(1, int(round(w / factor))),
                        max(1, int(round(h / factor)))), Image.NEAREST)
    return np.asarray(small) >= 128


def _components(mask: np.ndarray):
    """Deterministic 4-connected component sizes, largest first."""
    work = _label_scale(mask)
    h, w = work.shape
    seen = np.zeros_like(work, dtype=bool)
    sizes = []
    for sy in range(h):
        for sx in range(w):
            if work[sy, sx] and not seen[sy, sx]:
                q = deque([(sy, sx)])
                seen[sy, sx] = True
                size = 0
                while q:
                    y, x = q.popleft()
                    size += 1
                    for ny, nx in ((y - 1, x), (y + 1, x),
                                   (y, x - 1), (y, x + 1)):
                        if 0 <= ny < h and 0 <= nx < w and work[ny, nx] \
                                and not seen[ny, nx]:
                            seen[ny, nx] = True
                            q.append((ny, nx))
                sizes.append(size)
    sizes.sort(reverse=True)
    return sizes


def fill_holes(mask: np.ndarray) -> tuple[np.ndarray, float]:
    """Deterministically fill enclosed interior regions (flood the
    background from the frame; anything unreachable is product interior).
    Returns (filled mask, filled_fraction_of_result)."""
    from PIL import ImageDraw as _ImageDraw
    h, w = mask.shape
    # pad so the flood always starts on background
    bg = Image.new("L", (w + 2, h + 2), 0)
    bg.paste(Image.fromarray((mask * 255).astype(np.uint8)), (1, 1))
    _ImageDraw.floodfill(bg, (0, 0), 128)
    arr = np.asarray(bg)[1:-1, 1:-1]
    filled = arr != 128                      # product + enclosed interior
    before = int(mask.sum())
    after = int(filled.sum())
    ratio = 0.0 if after == 0 else (after - before) / after
    return filled, round(ratio, 4)


def mask_quality(mask: np.ndarray) -> dict:
    """§6 quality metrics + failure reason codes."""
    h, w = mask.shape
    total = int(mask.sum())
    failures: list[str] = []
    coverage = total / float(h * w)
    if total == 0:
        return {"failures": [CONCEPT_MASK_EMPTY], "coverage": 0.0,
                "component_count": 0, "largest_component_ratio": 0.0,
                "edge_contact_px": 0, "noise_ratio": 0.0}
    if coverage > PARAMS["max_coverage"]:
        failures.append(CONCEPT_MASK_FRAME_FILLING)
    if coverage < PARAMS["min_coverage"]:
        failures.append(CONCEPT_PRODUCT_TOO_SMALL)

    sizes = _components(mask)
    largest_ratio = sizes[0] / float(sum(sizes)) if sizes else FT.traced_zero("concept_analysis.py:mask_quality", "guard")
    majors = [s for s in sizes
              if s >= PARAMS["major_component_ratio"] * sum(sizes)]
    noise_ratio = 1.0 - largest_ratio
    if len(majors) > 1:
        failures.append(CONCEPT_MULTIPLE_PRODUCTS)
    elif largest_ratio < PARAMS["largest_component_min_ratio"]:
        failures.append(CONCEPT_MASK_FRAGMENTED)
    elif noise_ratio > PARAMS["noise_ratio_max"]:
        failures.append(CONCEPT_MASK_FRAGMENTED)

    edge = int(mask[0].sum() + mask[-1].sum()
               + mask[:, 0].sum() + mask[:, -1].sum())

    ys, xs = np.nonzero(mask)
    bw = int(xs.max() - xs.min() + 1)
    bh = int(ys.max() - ys.min() + 1)
    if min(bw, bh) < PARAMS["min_product_px"]:
        if CONCEPT_PRODUCT_TOO_SMALL not in failures:
            failures.append(CONCEPT_PRODUCT_TOO_SMALL)

    return {"failures": failures, "coverage": round(coverage, 5),
            "component_count": len(sizes),
            "largest_component_ratio": round(largest_ratio, 4),
            "edge_contact_px": edge,
            "noise_ratio": round(noise_ratio, 4)}


# ---------------------------------------------------------------------------
# measurements (§7) + contour representation (§12)


def measure_mask(mask: np.ndarray) -> dict:
    h, w = mask.shape
    ys, xs = np.nonzero(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    cx, cy = float(xs.mean()), float(ys.mean())
    n = PARAMS["profile_samples"]
    rows = np.linspace(y0, y1, n).round().astype(int)
    widths, lefts, rights = [], [], []
    for r in rows:
        row = np.nonzero(mask[r])[0]
        if row.size:
            left, right = int(row.min()), int(row.max())
            widths.append((right - left + 1) / bw)
            lefts.append((left - x0) / bw)
            rights.append((right - x0) / bw)
        else:
            widths.append(0.0)
            lefts.append(0.5)
            rights.append(0.5)
    widths_arr = np.array(widths)
    # symmetry: left inset vs mirrored right inset within the bbox
    sym_dev = float(np.mean(np.abs(np.array(lefts)
                                   - (1.0 - np.array(rights)))))

    # closure/body separation: a sustained narrow band from the top
    body_max = float(widths_arr[n // 3:].max()) if n >= 3 else 1.0
    closure_end = 0
    if body_max > 0:
        narrow = widths_arr < PARAMS["closure_narrow_ratio"] * body_max
        i = 0
        while i < n and narrow[i]:
            i += 1
        closure_end = i
    closure_sep = closure_end / n >= PARAMS["closure_min_band"] and \
        closure_end < n // 2
    closure_zone = None
    body_zone = None
    if closure_sep:
        split_row = int(rows[closure_end])
        closure_zone = {"y0_norm": 0.0,
                        "y1_norm": round(closure_end / n, 4),
                        "max_width_norm":
                            round(float(widths_arr[:closure_end].max()), 4)}
        body_zone = {"y0_norm": round(closure_end / n, 4), "y1_norm": 1.0,
                     "max_width_norm":
                         round(float(widths_arr[closure_end:].max()), 4)}
        del split_row

    return {
        "bounding_box_px": {"x": x0, "y": y0, "width": bw, "height": bh},
        "normalized_bounds": {"x": round(x0 / w, 4), "y": round(y0 / h, 4),
                              "width": round(bw / w, 4),
                              "height": round(bh / h, 4)},
        "centroid_normalized": {"x": round(cx / w, 4),
                                "y": round(cy / h, 4)},
        "aspect_h_over_w": round(bh / bw, 4),
        "pixel_count": int(mask.sum()),
        "coverage_ratio": round(float(mask.mean()), 5),
        "clearances_normalized": {"top": round(y0 / h, 4),
                                  "bottom": round((h - 1 - y1) / h, 4),
                                  "left": round(x0 / w, 4),
                                  "right": round((w - 1 - x1) / w, 4)},
        "frame_contacts": {"top": bool(mask[0].any()),
                           "bottom": bool(mask[-1].any()),
                           "left": bool(mask[:, 0].any()),
                           "right": bool(mask[:, -1].any())},
        "contour": {
            "representation": "width_at_height_profile/1.0",
            "samples": PARAMS["profile_samples"],
            "translation_invariant": True,
            "scale_normalized": True,
            "limitations": ("front-facing standard containers on "
                            "resolvable backgrounds only; no perspective, "
                            "multi-product or occlusion support"),
            "width_profile": [round(v, 4) for v in widths],
            "left_profile": [round(v, 4) for v in lefts],
            "right_profile": [round(v, 4) for v in rights],
        },
        "vertical_symmetry_deviation": round(sym_dev, 4),
        "closure_zone": closure_zone,
        "body_zone": body_zone,
        "closure_to_body_width_ratio": (
            round(closure_zone["max_width_norm"]
                  / body_zone["max_width_norm"], 4)
            if closure_zone and body_zone and body_zone["max_width_norm"]
            else None),
    }


# ---------------------------------------------------------------------------
# classification (§8)


def classify(quality: dict, measurements: dict | None,
             mask_confidence: str) -> tuple[str, list[str], list[str]]:
    reasons = list(quality.get("failures") or [])
    warnings: list[str] = []
    if measurements is None or CONCEPT_MASK_EMPTY in reasons \
            or CONCEPT_MASK_FRAME_FILLING in reasons \
            or CONCEPT_PRODUCT_TOO_SMALL in reasons \
            or CONCEPT_MULTIPLE_PRODUCTS in reasons \
            or CONCEPT_MASK_FRAGMENTED in reasons:
        return UNMEASURABLE_CLASS, reasons, warnings
    contacts = measurements["frame_contacts"]
    if any(contacts.values()):
        reasons.append(CONCEPT_FRAME_CONTACT)
        if contacts["bottom"] or contacts["top"]:
            reasons.append(CONCEPT_PRODUCT_CROPPED)
    if measurements["vertical_symmetry_deviation"] > PARAMS["symmetry_warn"]:
        warnings.append(CONCEPT_EXCESSIVE_PERSPECTIVE)
    if measurements["closure_zone"] is None:
        warnings.append(CONCEPT_CLOSURE_HIDDEN)
    if mask_confidence == "MEDIUM":
        warnings.append("mask from background segmentation — golden mask "
                        "recommended for calibration-grade evidence")
    if reasons:
        return PARTIAL_CLASS, reasons, warnings
    return READY, reasons, warnings


# ---------------------------------------------------------------------------
# top-level contract


def analyze_concept_image(img: Image.Image, *, safe_filename: str,
                          sha256: str, concept_id=None, task_id=None,
                          golden_mask: Image.Image | None = None) -> dict:
    """The full ``product_container_concept_analysis/1.0`` record. Pure:
    reads the given image only; writes nothing; no paths, no bytes, no
    provider. The source image object is never modified."""
    mask, method, confidence, warnings = extract_mask(
        img, golden_mask=golden_mask)
    arr_alpha = _as_rgba(img)[..., 3]
    record = {
        "schema": SCHEMA,
        "params_version": PARAMS["version"],
        "concept_id": concept_id,
        "task_id": task_id,
        "source_identity": {
            "safe_filename": safe_filename,
            "sha256": sha256,
            "width_px": img.width,
            "height_px": img.height,
            "has_alpha": bool((arr_alpha
                               < PARAMS["alpha_threshold"]).any()),
        },
        "mask_method": method,
        "mask_confidence": confidence if mask is not None else "LOW",
        "warnings": list(warnings),
    }
    if mask is None:
        record.update({
            "analysis_state": UNMEASURABLE,
            "classification": UNMEASURABLE_CLASS,
            "product_mask": {"available": False},
            "mask_quality": None,
            "measurements": None,
            "blocking_findings": list(warnings)
                                 or [CONCEPT_BACKGROUND_UNRESOLVED],
            "measurement_readiness": _readiness(False, False),
        })
        return record

    if mask.any():
        mask, hole_ratio = fill_holes(mask)
    else:
        hole_ratio = 0.0
    quality = mask_quality(mask)
    quality["holes_filled_ratio"] = hole_ratio
    mask_authority = (MASK_AUTHORITY_OWNER_GOLDEN
                      if method == OWNER_GOLDEN_MASK
                      else MASK_AUTHORITY_DIRECT)
    if hole_ratio >= PARAMS["hole_fill_report_ratio"]:
        mask_authority = MASK_AUTHORITY_OUTLINE_FILL
        # §1: outline-derived evidence caps at MEDIUM — determinism is
        # not authority
        if record["mask_confidence"] == "HIGH":
            record["mask_confidence"] = "MEDIUM"
        record["warnings"].append(
            "OUTLINE_SOURCE: the mask was substantially hole-filled "
            f"(filled fraction {hole_ratio}) — the source reads as a "
            "line-drawn concept with no solid product region; results "
            "are authoritative only for the measurements actually "
            "validated, and an owner-golden mask remains recommended")
    record["mask_authority"] = mask_authority
    fatal = {CONCEPT_MASK_EMPTY, CONCEPT_MASK_FRAME_FILLING,
             CONCEPT_PRODUCT_TOO_SMALL, CONCEPT_MULTIPLE_PRODUCTS,
             CONCEPT_MASK_FRAGMENTED}
    measurements = None
    if not (fatal & set(quality["failures"])):
        measurements = measure_mask(mask)
    classification, reasons, class_warnings = classify(
        quality, measurements, confidence)
    record["warnings"] += class_warnings
    state = (UNMEASURABLE if classification == UNMEASURABLE_CLASS
             else PARTIAL if classification == PARTIAL_CLASS else MEASURED)
    record.update({
        "analysis_state": state,
        "classification": classification,
        "product_mask": {"available": measurements is not None,
                         **({"pixel_count": measurements["pixel_count"],
                             "coverage_ratio":
                                 measurements["coverage_ratio"],
                             "bounding_box_px":
                                 measurements["bounding_box_px"],
                             "normalized_bounds":
                                 measurements["normalized_bounds"],
                             "centroid_normalized":
                                 measurements["centroid_normalized"],
                             "aspect_h_over_w":
                                 measurements["aspect_h_over_w"]}
                            if measurements else {})},
        "mask_quality": quality,
        "measurements": measurements,
        "blocking_findings": reasons,
        "measurement_readiness": _readiness(
            measurements is not None,
            bool(measurements and measurements["closure_zone"]),
            mask_authority=record.get("mask_authority"),
            mask_confidence=record.get("mask_confidence")),
    })
    return record


def _readiness(mask_ok: bool, closure_ok: bool, *, mask_authority=None,
               mask_confidence=None) -> dict:
    # §1 owner correction: readiness is reported PER ANALYSIS with the
    # mask authority beside it — one global READY never implies every
    # analysis is equally authoritative
    return {
        "SILHOUETTE_ANALYSIS_READY": mask_ok,
        "CLOSURE_ANALYSIS_READY": closure_ok,
        "COMPOSITION_ANALYSIS_READY": mask_ok,
        "MASK_AUTHORITY": mask_authority,
        "MASK_CONFIDENCE": mask_confidence,
        # legacy keys kept for existing consumers
        "silhouette_ready": mask_ok,
        "closure_ready": closure_ok,
        "composition_ready": mask_ok,
        # comparison readiness is a VQR-2B-B fact — concept-side analysis
        # alone can only say the CONCEPT side is prepared
        "reconstruction_comparison_ready": False,
        "reconstruction_comparison_note":
            "SELECTED_CONCEPT_SILHOUETTE_FIDELITY stays "
            "UNMEASURED_PENDING_VQR_2B_B",
    }
