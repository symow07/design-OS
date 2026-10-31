"""Capability-aware segmentation (DIP-0C2a).

Dispatches by the C1 file `kind` and produces `AssetCandidate` records, never
exceeding what each format actually supports:

* **PDF-backed `.ai` / `.pdf`** — reuse dip0b `segment_page` (true vector
  geometry). >1 cluster → `SEGMENTED`; exactly one → `WHOLE_FILE_SINGLE_ASSET`
  (natural); zero clusters → a whole-file **fallback** candidate (never zero
  candidates — the LOGO6 lesson).
* **native SVG** — safe element-tree grouping. Unsafe/malformed SVG is
  quarantined → `UNAVAILABLE`, not segmented.
* **raster** — deterministic connected-region segmentation on a downscaled mask;
  `AUTO_CONFIDENT` / `AUTO_LOW_CONFIDENCE` / `MANUAL_REVIEW_REQUIRED`.
* **EPS** — only a *usable* (PIL-decodable) TIFF preview yields
  `PREVIEW_DERIVED` regions (confidence-capped, explicitly not editable EPS
  objects). Otherwise `UNAVAILABLE` with a single header-only whole-file
  candidate (bbox from BoundingBox, no geometry/editability claim).

Every candidate carries deterministic-id + full provenance via `assetcandidate`.
"""
from __future__ import annotations

import dataclasses
import io
from pathlib import Path
from xml.parsers import expat

import numpy as np

from tools.dip0b import config as BC
from tools.dip0b.cluster import label_components
from tools.dip0b.limits import Budget
from tools.dip0b.regions import DEFAULT_THRESHOLDS, segment_page

from . import assetcandidate as AC
from . import config as C
from . import eps_header, svg

PARSER = f"{C.TOOL_NAME}.segment/{C.TOOL_VERSION}"

RASTER_LONG_EDGE = 512           # downscale target for the mask
RASTER_MIN_AREA_FRAC = 0.002     # a "big" component is >= 0.2% of the image
ALPHA_THRESH = 32
BG_DIFF_THRESH = 40
COVERAGE_FLOOR = 0.005           # below this, nothing separable
COVERAGE_CEIL = 0.92             # above this, no fg/bg separation
EPS_PREVIEW_CONF_CAP = 0.45      # preview-derived confidence is capped


def segment_file(source: dict, inv_rec: dict, override=None) -> dict:
    """`source` is the C1-style file dict {relative_path, sha256, format, kind}.
    Returns {file_status, candidates:[...], evidence:[...]}."""
    ext = (source.get("format") or Path(source["relative_path"]).suffix).lower()
    inventory_cat = inv_rec.get("category", {}).get("value", "UNKNOWN") \
        if inv_rec else "UNKNOWN"
    ctx = dict(source=source, inventory_category=inventory_cat, override=override)
    if ext in (".ai", ".pdf"):
        return _segment_vector_pdf(ctx)
    if ext == ".svg":
        return _segment_svg(ctx)
    if ext == ".eps":
        return _segment_eps(ctx)
    if ext in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".gif", ".bmp"):
        return _segment_raster(ctx)
    return {"file_status": C.SEG_STATUS_UNAVAILABLE, "candidates": [],
            "evidence": [f"unsupported format for segmentation: {ext}"]}


# --- vector (PDF-backed) ----------------------------------------------------
def _vector_fp() -> str:
    th = dataclasses.asdict(DEFAULT_THRESHOLDS)
    return AC.config_fingerprint({"segthresholds": th,
                                  "limits": BC.DEFAULT_LIMITS.__dict__
                                  if hasattr(BC.DEFAULT_LIMITS, "__dict__")
                                  else str(BC.DEFAULT_LIMITS)})


def _segment_vector_pdf(ctx: dict) -> dict:
    import fitz
    fp = _vector_fp()
    full = C.physical_path(ctx["source"]["relative_path"], C.REPO_ROOT)
    doc = fitz.open(full)
    cands, evidence = [], []
    try:
        idx = 0
        for pno in range(doc.page_count):
            page = doc[pno]
            surface = _page_surface_pt(page)
            if _is_jpeg_shell(page, surface):
                # a full-page embedded raster with few vector paths (the C1
                # JPEG-shell trap): ONE embedded-raster asset, never split into
                # fake vector fragments.
                cands.append(_vec_candidate(
                    ctx, C.SEG_METHOD_VECTOR_WHOLE_NATURAL, C.SEG_STATUS_WHOLE_FILE,
                    surface, fp, idx, pno,
                    ["JPEG-shell: embedded raster covers the page with few vector "
                     "paths; treated as ONE embedded-raster asset, not split"],
                    0.5, tier=C.TIER_HEURISTIC))
                idx += 1
                evidence.append(f"page {pno}: JPEG-shell -> single embedded raster")
                continue
            res = segment_page(doc, page, pno, ctx["source"]["relative_path"],
                               Budget(BC.DEFAULT_LIMITS))
            page_cands = res.get("candidates", [])
            if not page_cands:
                # whole-file fallback — never zero candidates
                cands.append(_vec_candidate(
                    ctx, C.SEG_METHOD_VECTOR_WHOLE_FALLBACK, C.SEG_STATUS_WHOLE_FILE,
                    surface, fp, idx, pno,
                    ["segment_page produced 0 clusters (below dieline thresholds); "
                     "whole-page fallback so the asset is never lost"], 0.4))
                idx += 1
                evidence.append(f"page {pno}: 0 clusters -> whole-file fallback")
                continue
            method = (C.SEG_METHOD_VECTOR if len(page_cands) > 1
                      else C.SEG_METHOD_VECTOR_WHOLE_NATURAL)
            status = (C.SEG_STATUS_SEGMENTED if len(page_cands) > 1
                      else C.SEG_STATUS_WHOLE_FILE)
            surf_area = max((surface[2] - surface[0]) * (surface[3] - surface[1]),
                            1e-6)
            for c in page_cands:
                bb = c["bbox_pt"]
                iso = round(min(1.0, ((bb[2] - bb[0]) * (bb[3] - bb[1]))
                                / surf_area), 3)
                cands.append(_vec_candidate(
                    ctx, method, status, bb, fp, idx, pno,
                    [f"vector cluster {c.get('unit_id')}",
                     f"{c.get('path_count', c.get('n_paths', '?'))} member paths"],
                    0.7 if len(page_cands) > 1 else 0.6,
                    collection=_collection(ctx, len(page_cands), idx, pno),
                    isolated=iso))
                idx += 1
            evidence.append(f"page {pno}: {len(page_cands)} candidate(s)")
        # a file that produced more than one candidate is SEGMENTED, whether the
        # split came from one artboard (a sheet) or several artboards.
        file_status = (C.SEG_STATUS_SEGMENTED if len(cands) > 1
                       else C.SEG_STATUS_WHOLE_FILE)
        return {"file_status": file_status, "candidates": cands,
                "evidence": evidence}
    finally:
        doc.close()


def _page_surface_pt(page):
    r = page.rect
    return [r.x0, r.y0, r.x1, r.y1]


JPEG_SHELL_COVERAGE = 0.85       # same threshold as C1 pdf_vector
JPEG_SHELL_MAX_PATHS = 60


def _is_jpeg_shell(page, surface) -> bool:
    """Full-page embedded raster + few vector paths (mirrors C1's detector)."""
    surface_area = max((surface[2] - surface[0]) * (surface[3] - surface[1]), 1e-6)
    img_area = 0.0
    for im in page.get_images(full=True):
        try:
            bb = page.get_image_bbox(im)
            img_area += abs(bb.width * bb.height)
        except Exception:  # noqa: BLE001
            pass
    coverage = img_area / surface_area
    paths = sum(1 for d in page.get_drawings(extended=True)
                if d["type"] in ("f", "s", "fs"))
    return coverage >= JPEG_SHELL_COVERAGE and paths <= JPEG_SHELL_MAX_PATHS


def _vec_candidate(ctx, method, status, bbox_pt, fp, idx, pno, evidence, conf,
                   collection=None, tier=C.TIER_DIRECT, isolated=None):
    return AC.build_candidate(
        source=ctx["source"], method=method, status=status, bbox_pt=bbox_pt,
        preview_source="none", capability_tier=tier, confidence=conf,
        evidence=evidence, parser=PARSER, config_fp=fp, index=idx,
        inventory_category=ctx["inventory_category"], override=ctx["override"],
        collection=collection, isolated_confidence=isolated, page=pno)


def _collection(ctx, n_on_page, idx, pno):
    if n_on_page <= 1:
        return None
    return {"is_member": True,
            "parent_source": ctx["source"]["relative_path"],
            "parent_page": pno,
            "sibling_count_on_page": n_on_page,
            "manual_actions_allowed": ["split", "merge", "relabel", "exclude"]}


# --- native SVG -------------------------------------------------------------
def _segment_svg(ctx: dict) -> dict:
    rel = ctx["source"]["relative_path"]
    audit = svg.audit(rel)
    fp = AC.config_fingerprint({"svg_parser": svg.PARSER})
    if not audit["security"]["safe_to_ingest"]["value"] \
            or audit["parse_status"] != "PARSED":
        return {"file_status": C.SEG_STATUS_UNAVAILABLE, "candidates": [],
                "evidence": [f"SVG quarantined/not parsed "
                             f"({audit['parse_status']}); not segmented",
                             *audit["security"]["findings"]]}
    groups = _svg_top_level_groups(rel)
    vb = audit.get("view_box")
    bbox_px = _viewbox_bbox(vb)
    if len(groups) > 1:
        cands = []
        for i, g in enumerate(groups):
            cands.append(AC.build_candidate(
                source=ctx["source"], method=C.SEG_METHOD_SVG,
                status=C.SEG_STATUS_SEGMENTED, bbox_px=None,
                preview_source="none", capability_tier=C.TIER_HEURISTIC,
                confidence=0.55,
                evidence=[f"top-level element-tree group #{i} <{g}>",
                          "per-group bbox not computed natively in C2a"],
                parser=PARSER, config_fp=fp, index=i,
                inventory_category=ctx["inventory_category"],
                override=ctx["override"],
                collection={"is_member": True, "parent_source": rel,
                            "sibling_count_on_page": len(groups),
                            "manual_actions_allowed": ["split", "merge",
                                                       "relabel", "exclude"]},
                extra={"element_path": f"svg>g[{i}]"}))
        return {"file_status": C.SEG_STATUS_SEGMENTED, "candidates": cands,
                "evidence": [f"{len(groups)} top-level SVG groups"]}
    return {"file_status": C.SEG_STATUS_WHOLE_FILE,
            "candidates": [AC.build_candidate(
                source=ctx["source"], method=C.SEG_METHOD_SVG,
                status=C.SEG_STATUS_WHOLE_FILE, bbox_px=bbox_px,
                preview_source="none", capability_tier=C.TIER_HEURISTIC,
                confidence=0.55,
                evidence=[f"{len(groups)} top-level group(s); single SVG asset",
                          f"viewBox={vb}"],
                parser=PARSER, config_fp=fp, index=0,
                inventory_category=ctx["inventory_category"],
                override=ctx["override"], extra={"element_path": "svg"})],
            "evidence": ["single-asset SVG"]}


class _StopParse(Exception):
    pass


def _svg_top_level_groups(rel: str) -> list[str]:
    """Direct structural children of the root <svg>. Hardened: no DTD entities,
    no external-entity resolution (safety already asserted by svg.audit)."""
    data = C.physical_path(rel, C.REPO_ROOT).read_bytes()
    depth = [0]
    top = []
    p = expat.ParserCreate()
    p.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
    p.ExternalEntityRefHandler = lambda *a: 0

    def start(name, attrs):
        local = name.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()
        # Only real asset CONTAINERS count as top-level assets. A bare <text>
        # label, <defs>, gradients, <style>/<title>/<metadata> etc. are not
        # standalone reusable assets and must not force a split.
        if depth[0] == 1 and local in ("g", "symbol"):
            top.append(local)
        depth[0] += 1

    def end(name):
        depth[0] -= 1

    p.StartElementHandler = start
    p.EndElementHandler = end
    try:
        p.Parse(data, True)
    except expat.ExpatError:
        return top
    return top


def _viewbox_bbox(vb):
    if not vb:
        return None
    try:
        parts = [float(x) for x in vb.replace(",", " ").split()]
        if len(parts) == 4:
            x, y, w, h = parts
            return [int(x), int(y), int(x + w), int(y + h)]
    except ValueError:
        pass
    return None


# --- raster -----------------------------------------------------------------
def _raster_fp() -> str:
    return AC.config_fingerprint({
        "long_edge": RASTER_LONG_EDGE, "min_area_frac": RASTER_MIN_AREA_FRAC,
        "alpha_thresh": ALPHA_THRESH, "bg_diff_thresh": BG_DIFF_THRESH,
        "coverage_floor": COVERAGE_FLOOR, "coverage_ceil": COVERAGE_CEIL,
        "min_big_mass": MIN_BIG_MASS, "single_region_confident": True})


def _segment_raster(ctx: dict) -> dict:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 300_000_000
    rel = ctx["source"]["relative_path"]
    fp = _raster_fp()
    try:
        im = Image.open(C.physical_path(rel, C.REPO_ROOT))
        full_w, full_h = im.size
        comps = _raster_components(im)
    except Exception as e:  # noqa: BLE001
        return {"file_status": C.SEG_STATUS_MANUAL, "candidates": [
            AC.build_candidate(
                source=ctx["source"], method=C.SEG_METHOD_NONE,
                status=C.SEG_STATUS_MANUAL, bbox_px=None, preview_source="none",
                capability_tier=C.TIER_REQUIRES_HUMAN, confidence=0.2,
                evidence=[f"raster unreadable: {type(e).__name__}"],
                parser=PARSER, config_fp=fp, index=0,
                inventory_category=ctx["inventory_category"],
                override=ctx["override"])],
            "evidence": [f"unreadable: {e}"]}
    return _raster_candidates(ctx, comps, full_w, full_h, fp, rel)


def _raster_components(im):
    """Downscaled mask + connected components. Returns dict of stats + boxes."""
    z = min(1.0, RASTER_LONG_EDGE / max(im.size))
    small = im.resize((max(1, int(im.size[0] * z)), max(1, int(im.size[1] * z))))
    if small.mode in ("RGBA", "LA") and "A" in small.getbands():
        a = np.asarray(small)
        mask = a[..., -1] > ALPHA_THRESH
        mask_kind = "alpha"
    else:
        rgb = np.asarray(small.convert("RGB")).astype(int)
        border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]) \
            .reshape(-1, 3)
        bg = np.median(border, axis=0)
        mask = np.abs(rgb - bg).sum(-1) > BG_DIFF_THRESH
        mask_kind = "bg_diff"
    labels, n = label_components(mask.astype(bool))
    sizes = np.bincount(labels.ravel())
    total_fg = int(mask.sum())
    minpx = RASTER_MIN_AREA_FRAC * mask.size
    big = [i for i in range(1, n + 1) if i < len(sizes) and sizes[i] >= minpx]
    big_mass = (sum(int(sizes[i]) for i in big) / total_fg) if total_fg else 0.0
    boxes = []
    for i in big:
        ys, xs = np.where(labels == i)
        boxes.append((int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
    return {"mask_kind": mask_kind, "raw_components": int(n),
            "big_components": len(big), "coverage": round(total_fg / mask.size, 4),
            "big_mass": round(big_mass, 3), "boxes": boxes,
            "scale": z, "small_size": small.size}


MIN_BIG_MASS = 0.30              # below this, big components don't represent content


def _raster_candidates(ctx, comps, full_w, full_h, fp, rel):
    cov, big, big_mass = comps["coverage"], comps["big_components"], comps["big_mass"]
    # No reliable segmentation: fills/empties the frame, no components, or the big
    # components carry too little of the foreground (a dense pattern / noise).
    if (cov >= COVERAGE_CEIL or cov <= COVERAGE_FLOOR or big == 0
            or big_mass < MIN_BIG_MASS):
        why = ("no components" if big == 0 else
               f"coverage {cov:.0%} leaves no fg/bg separation"
               if (cov >= COVERAGE_CEIL or cov <= COVERAGE_FLOOR)
               else f"big-component mass {big_mass:.0%} too low (dense/pattern)")
        ev = [f"{why}; segmentation unreliable -> manual review"]
        cands = [AC.build_candidate(
            source=ctx["source"], method=C.SEG_METHOD_RASTER,
            status=C.SEG_STATUS_MANUAL, bbox_px=[0, 0, full_w, full_h],
            preview_source=rel, capability_tier=C.TIER_REQUIRES_HUMAN,
            confidence=0.3, evidence=ev, parser=PARSER, config_fp=fp, index=0,
            inventory_category=ctx["inventory_category"], override=ctx["override"],
            extra={k: comps[k] for k in ("raw_components", "big_components",
                                         "coverage", "big_mass", "mask_kind")})]
        return {"file_status": C.SEG_STATUS_MANUAL, "candidates": cands,
                "evidence": ev}

    # A single dominant region is a reliable subject. But MULTIPLE raster regions
    # are only a PROPOSAL: connected components cannot tell whether the regions are
    # distinct reusable assets (a sticker sheet) or parts of one composition (a
    # fluid background) — a fluid bg (5 regions) and a sticker sheet (13) are
    # statistically indistinguishable here. So multi-region raster is
    # AUTO_LOW_CONFIDENCE and left for human confirmation.
    single = big == 1
    status = C.SEG_STATUS_AUTO_CONFIDENT if single else C.SEG_STATUS_AUTO_LOW_CONF
    inv_scale = 1.0 / comps["scale"] if comps["scale"] else 1.0
    cands = []
    n = len(comps["boxes"])
    for i, (x0, y0, x1, y1) in enumerate(comps["boxes"]):
        bbox = [int(x0 * inv_scale), int(y0 * inv_scale),
                int(x1 * inv_scale), int(y1 * inv_scale)]
        ev = [f"connected region {i + 1}/{n} ({comps['mask_kind']} mask)"]
        if single:
            ev.append("single dominant subject (reliable)")
        else:
            ev.append("one of several raster regions; whether these are distinct "
                      "assets or one composition needs human confirmation")
        cands.append(AC.build_candidate(
            source=ctx["source"], method=C.SEG_METHOD_RASTER, status=status,
            bbox_px=bbox, preview_source=rel, capability_tier=C.TIER_HEURISTIC,
            confidence=0.7 if single else 0.4, evidence=ev,
            parser=PARSER, config_fp=fp, index=i,
            inventory_category=ctx["inventory_category"], override=ctx["override"],
            isolated_confidence=big_mass,
            collection=({"is_member": True, "parent_source": rel,
                         "sibling_count_on_page": n,
                         "manual_actions_allowed": ["split", "merge", "relabel",
                                                    "exclude"]} if n > 1 else None)))
    return {"file_status": status, "candidates": cands,
            "evidence": [f"{n} region(s), coverage {cov:.0%}, "
                         f"big-mass {big_mass:.0%} -> {status}"]}


# --- EPS --------------------------------------------------------------------
def _segment_eps(ctx: dict) -> dict:
    rel = ctx["source"]["relative_path"]
    audit = eps_header.audit(rel)
    fp = AC.config_fingerprint({"eps_preview_decoder": "PIL",
                                "conf_cap": EPS_PREVIEW_CONF_CAP})
    preview = audit.get("tiff_preview", {})
    bbox = audit["bounding_box"]["value"] or audit["hires_bounding_box"]["value"]

    decoded = _try_decode_eps_preview(rel, preview) if preview.get("present") \
        else None
    if decoded is not None:
        comps = _raster_components(decoded)
        res = _raster_candidates(ctx, comps, *decoded.size, fp, rel)
        for c in res["candidates"]:
            c["segmentation"]["method"] = C.SEG_METHOD_EPS_PREVIEW
            c["segmentation"]["status"] = C.SEG_STATUS_PREVIEW_DERIVED
            # a heuristic segmentation of a RASTER preview — not native EPS geometry
            c["segmentation"]["capability_tier"] = C.TIER_HEURISTIC
            c["segmentation"]["confidence"] = min(c["segmentation"]["confidence"],
                                                  EPS_PREVIEW_CONF_CAP)
            c["segmentation"]["evidence"].append(
                "PREVIEW-DERIVED: regions come from the raster preview and DO NOT "
                "correspond to editable EPS objects; geometry needs Ghostscript")
        return {"file_status": C.SEG_STATUS_PREVIEW_DERIVED,
                "candidates": res["candidates"],
                "evidence": ["segmented the decodable TIFF preview (preview-derived)"]}

    # no usable preview -> UNAVAILABLE, single header-only whole-file candidate
    reason = ("TIFF preview present but not decodable by current toolchain (PIL) "
              "-> not a usable preview" if preview.get("present")
              else "no bitmap preview in EPS")
    cand = AC.build_candidate(
        source=ctx["source"], method=C.SEG_METHOD_NONE,
        status=C.SEG_STATUS_UNAVAILABLE,
        bbox_pt=bbox if bbox else None, preview_source="none",
        capability_tier=C.TIER_REQUIRES_TOOL, confidence=0.0,
        evidence=[reason,
                  "EPS contributes header/preview facts only; no geometry, "
                  "editability, path or clipping claims without Ghostscript"],
        parser=PARSER, config_fp=fp, index=0,
        inventory_category=ctx["inventory_category"], override=ctx["override"],
        extra={"bounding_box": bbox, "binary_dos_eps": audit["binary_dos_eps"],
               "tiff_preview_present": preview.get("present", False)})
    return {"file_status": C.SEG_STATUS_UNAVAILABLE, "candidates": [cand],
            "evidence": [reason]}


def _try_decode_eps_preview(rel: str, preview: dict):
    """Extract the declared TIFF-preview byte range and try PIL. Returns a PIL
    image on success, else None (fails closed — many Illustrator previews are a
    palette subset PIL cannot decode)."""
    if not preview.get("offset") or not preview.get("length"):
        return None
    from PIL import Image
    try:
        data = C.physical_path(rel, C.REPO_ROOT).read_bytes()
        blob = data[preview["offset"]:preview["offset"] + preview["length"]]
        im = Image.open(io.BytesIO(blob))
        im.load()
        return im
    except Exception:  # noqa: BLE001
        return None
