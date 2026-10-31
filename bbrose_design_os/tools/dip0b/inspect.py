"""DIP-0B1 — technical inspection of one pilot `.ai` file.

Reads the PDF-compatible layer of an Illustrator file and records what is
DIRECTLY present, what is HEURISTIC, and what is locked behind native
Illustrator. Read-only: opens files, never writes to them.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import fitz

from tools.dip0.provenance import Inferred

from . import config as C
from .boxes import build_boxes, classify_off_canvas, pt_to_mm
from .limits import Budget
from .separation import build_separation_table, collect_separation, is_devicen

PARSER = f"{C.TOOL_NAME}.inspect/{C.TOOL_VERSION}+pymupdf"

# A fill small enough to plausibly be an outlined glyph. Evidence only — such a
# path may equally be an icon, ornament, motif or decorative linework, so this
# NEVER asserts that the geometry is text.
GLYPH_SCALE_MAX_AREA_PT2 = 900.0
GLYPH_SCALE_MIN_AREA_PT2 = 1.0

# Structural-stroke evidence for B3 (dieline candidates). Not a claim.
STRUCTURAL_MAX_WIDTH_PT = 1.2

_AI_PRIVATE = re.compile(r"/AIPrivateData\d*|/AIMetaData")
_OPS = re.compile(rb"(?<![A-Za-z])(cs|CS|scn|SCN|sh|gs|Do|BDC|EMC)(?![A-Za-z])")


def _inf(value, tier, source, evidence, confidence, penalty=1.0) -> dict:
    d = Inferred(value=value, source=source, evidence=list(evidence),
                 confidence=round(confidence * penalty, 3), parser=PARSER).to_dict()
    d["tier"] = tier
    return d


def _hist(values, buckets=None):
    c = Counter(values)
    return {str(k): v for k, v in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))[:20]}


def scan_xrefs(doc, budget: Budget) -> dict:
    """ONE bounded sweep of the xref table feeding every consumer.

    Separations, the XObject census and the Illustrator-private census used to
    walk the table independently — triple the cost, and the skip count was
    recorded three times over (86,951 objects reported as 200,853 skipped).
    """
    raw_seps: dict[int, tuple[str, int, str]] = {}
    devicen = shadings = patterns = smasks = tgroups = 0
    ai_objects = ai_bytes = 0
    ai_keys: set[str] = set()

    for x in budget.xref_scan_range(doc.xref_length()):
        try:
            s = doc.xref_object(x, compressed=True)
        except Exception:  # noqa: BLE001
            continue

        sep = collect_separation(s)
        if sep:
            raw_seps[x] = (sep[0], sep[1], s)
        if is_devicen(s):
            devicen += 1
        if "/ShadingType" in s:
            shadings += 1
        if "/PatternType" in s:
            patterns += 1
        if "/SMask" in s:
            smasks += 1
        if "/S/Transparency" in s or "/S /Transparency" in s:
            tgroups += 1

        found = _AI_PRIVATE.findall(s)
        if found:
            ai_objects += 1
            ai_keys.update(found)
            m = re.search(r"/Length\s+(\d+)", s)
            if m:
                ai_bytes += int(m.group(1))

    return {
        "raw_separations": raw_seps,
        "devicen": devicen,
        "xobjects": {"shadings": shadings, "patterns": patterns,
                     "smasks": smasks, "transparency_groups": tgroups},
        "ai": {"objects": ai_objects, "bytes": ai_bytes, "keys": sorted(ai_keys)},
    }


def inspect_ai_private(scan: dict) -> dict:
    """Report the native Illustrator payload — presence and size ONLY.

    Safeguard 2: record presence, object count, total size and structural
    evidence. Never parse it, never reverse-engineer it, never infer layer
    names, text, symbols, effects or appearances from it. The audit identifies
    the boundary; it does not cross it.
    """
    objects = scan["ai"]["objects"]
    total_bytes = scan["ai"]["bytes"]
    keys = set(scan["ai"]["keys"])

    present = objects > 0
    return {
        "present": present,
        "container_objects": objects,
        "declared_key_names": sorted(keys)[:12],
        "approx_declared_bytes": total_bytes,
        "parsed": False,
        "policy": ("presence, size and structural evidence only; the payload is "
                   "opaque, undocumented and deliberately NOT parsed"),
        "unavailable_capabilities": [
            _inf(None, C.TIER_REQUIRES_ILLUSTRATOR, "ai_private_data_present",
                 [f"capability lives in {sorted(keys)[:1] or ['/AIPrivateData*']}",
                  "requires native Adobe Illustrator"], 0.0)
            | {"capability": cap}
            for cap in C.ILLUSTRATOR_ONLY_CAPABILITIES
        ] if present else [],
    }


def _content_operators(page, budget: Budget) -> dict:
    try:
        raw = page.read_contents()
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}
    ops = Counter(m.decode() for m in _OPS.findall(raw))
    return {"stream_bytes": len(raw), "operators": dict(sorted(ops.items()))}


def inspect_page(doc, page, page_index: int, budget: Budget) -> dict:
    raw_page = doc.xref_object(page.xref, compressed=False)
    boxes = build_boxes(page, raw_page)
    surface = boxes["design_surface_pt"]

    # --- paths -------------------------------------------------------------
    extended = page.get_drawings(extended=True)
    drawings = [d for d in extended if d["type"] in ("f", "s", "fs")]
    clips = [d for d in extended if d["type"] == "clip"]
    groups = [d for d in extended if d["type"] == "group"]

    if budget.out_of_time():
        pass  # recorded; we still emit what we have

    by_type = Counter(d["type"] for d in drawings)
    widths, dashes, caps, joins = [], [], [], []
    fill_op, stroke_op = [], []
    glyph_scale = structural = 0
    rects = []
    for d in drawings:
        r = fitz.Rect(d["rect"])
        rects.append(r)
        w = d.get("width")
        if w:
            widths.append(round(w, 2))
        dashes.append(d.get("dashes") or "[] 0")
        caps.append(str(d.get("lineCap")))
        joins.append(str(d.get("lineJoin")))
        if d.get("fill_opacity") is not None:
            fill_op.append(round(d["fill_opacity"], 2))
        if d.get("stroke_opacity") is not None:
            stroke_op.append(round(d["stroke_opacity"], 2))
        area = r.get_area()
        if d["type"] == "f" and GLYPH_SCALE_MIN_AREA_PT2 < area < GLYPH_SCALE_MAX_AREA_PT2:
            glyph_scale += 1
        if (d["type"] == "s" and d.get("fill") is None
                and w and 0 < w <= STRUCTURAL_MAX_WIDTH_PT):
            structural += 1

    n = len(drawings)
    pen = budget.confidence_penalty()

    # bounded sample of full path records; aggregates above cover every path
    sample = budget.sample(drawings, budget.limits.max_paths_detailed,
                           "max_paths_detailed", "detailed_paths")
    path_sample = [{
        "type": d["type"],
        "rect_pt": [round(v, 2) for v in d["rect"]],
        "width": d.get("width"),
        "dashes": d.get("dashes"),
        "even_odd": d.get("even_odd"),
        "closePath": d.get("closePath"),
        "fill_rgb": d.get("fill"),
        "stroke_rgb": d.get("color"),
        "fill_opacity": d.get("fill_opacity"),
        "stroke_opacity": d.get("stroke_opacity"),
        "seqno": d.get("seqno"),
        "layer": d.get("layer"),
    } for d in sample]

    # clips/groups totals above are exact; only the enumerated detail is bounded
    capped_clips = budget.sample(clips, budget.limits.max_clips_enumerated,
                                 "max_clips_enumerated", "clips")
    capped_groups = budget.sample(groups, budget.limits.max_groups_enumerated,
                                  "max_groups_enumerated", "groups")

    # --- rasters -----------------------------------------------------------
    images = []
    for im in page.get_images(full=True):
        rec = {"xref": im[0], "width_px": im[2], "height_px": im[3],
               "bpc": im[4], "colorspace": im[5], "filter": im[8], "bbox_pt": None}
        try:
            bb = page.get_image_bbox(im)
            rec["bbox_pt"] = [round(v, 2) for v in bb]
            rec["bbox_mm"] = [round(pt_to_mm(v), 2) for v in bb]
        except Exception as e:  # noqa: BLE001
            rec["bbox_error"] = type(e).__name__
        images.append(rec)

    # --- live text (measured: zero across the whole pilot) -----------------
    td = page.get_text("dict")
    spans = sum(len(line["spans"]) for b in td["blocks"] if b["type"] == 0
                for line in b["lines"])
    fonts = doc.get_page_fonts(page_index)

    off_canvas = classify_off_canvas(rects + [fitz.Rect(i["bbox_pt"]) for i in images
                                              if i.get("bbox_pt")], surface)

    return {
        "page_index": page_index,
        "boxes": boxes,
        "off_canvas": off_canvas,
        "paths": {
            "total": n,
            "by_type": dict(by_type),
            "clips_total": len(clips),
            "groups_total": len(groups),
            "clips_enumerated": len(capped_clips),
            "groups_enumerated": len(capped_groups),
            "width_histogram": _hist(widths),
            "dash_histogram": _hist(dashes),
            "line_cap_histogram": _hist(caps),
            "line_join_histogram": _hist(joins),
            "fill_opacity_histogram": _hist(fill_op),
            "stroke_opacity_histogram": _hist(stroke_op),
            "sample": path_sample,
            "sample_note": ("bounded sample; aggregate statistics above describe "
                            "all paths"),
        },
        "rasters": {"count": len(images), "images": images},
        "live_text": {
            "span_count": _inf(spans, C.TIER_DIRECT, "pymupdf_get_text",
                               [f"{spans} spans on page {page_index}"], 1.0),
            "embedded_font_count": _inf(len(fonts), C.TIER_DIRECT,
                                        "pymupdf_get_page_fonts",
                                        [f"{len(fonts)} fonts"], 1.0),
            "all_typography_outlined": _inf(
                spans == 0 and len(fonts) == 0, C.TIER_DIRECT, "pymupdf",
                ["0 live text spans and 0 embedded fonts"
                 if spans == 0 and len(fonts) == 0 else "live text present"], 1.0),
        },
        "text_like_geometry": {
            # NOT a claim that this geometry is text. Glyph-scale fills also
            # cover icons, ornaments, motifs and decorative linework.
            "glyph_scale_fill_count": glyph_scale,
            "glyph_scale_fill_ratio": _inf(
                round(glyph_scale / n, 4) if n else 0.0, C.TIER_HEURISTIC,
                "path_area_threshold",
                [f"{glyph_scale}/{n} fills in "
                 f"({GLYPH_SCALE_MIN_AREA_PT2}, {GLYPH_SCALE_MAX_AREA_PT2}) pt²",
                 "may be outlined type OR icons/ornaments/motifs/linework"],
                0.5, pen),
            "candidate_label": "TEXT_LIKE_GEOMETRY_CANDIDATE",
        },
        "structural_strokes": {
            "thin_nofill_stroke_count": structural,
            "evidence_for": "B3 dieline candidate detection (not a dieline claim)",
            "criterion": f"type=s, fill=None, 0 < width <= {STRUCTURAL_MAX_WIDTH_PT} pt",
        },
        "content_stream": _content_operators(page, budget),
    }


def inspect_file(rel_path: str, limits: C.Limits | None = None) -> dict:
    """Full technical record for one pilot `.ai` file (all pages)."""
    C.verify_pilot_path(rel_path)          # pilot-only guard
    limits = limits or C.DEFAULT_LIMITS
    full = C.physical_path(rel_path, C.REPO_ROOT)

    doc = fitz.open(full)
    budget = Budget(limits)
    try:
        meta = dict(doc.metadata or {})
        # Capture before touching pages: get_drawings/get_pixmap can grow the table.
        xref_length = doc.xref_length()
        try:
            ocgs = doc.get_ocgs()
            layers = {"count": len(ocgs),
                      "names": [v.get("name") for v in ocgs.values()]}
        except Exception as e:  # noqa: BLE001
            layers = {"count": None, "error": type(e).__name__}

        scan = scan_xrefs(doc, budget)     # ONE sweep, feeding every consumer

        pages = []
        for i in range(doc.page_count):
            pages.append(inspect_page(doc, doc[i], i, budget))
            if budget.out_of_time():
                budget.hit("max_page_seconds", limits.max_page_seconds,
                           skipped_kind="pages", skipped_count=doc.page_count - i - 1)
                break

        record = {
            "relative_path": rel_path,
            "filename": full.name,
            "size_bytes": full.stat().st_size,
            "document": {
                "page_count": _inf(doc.page_count, C.TIER_DIRECT, "pymupdf",
                                   [f"{doc.page_count} pages/artboards"], 1.0),
                "pdf_format": meta.get("format"),
                "creator": meta.get("creator"),
                "producer": meta.get("producer"),
                "encrypted": doc.is_encrypted,
                "has_xmp": bool(doc.get_xml_metadata()),
                "xref_length": xref_length,
            },
            "ocg_layers": _inf(layers, C.TIER_DIRECT, "pymupdf_get_ocgs",
                               ["PDF optional-content groups; Illustrator's own "
                                "layer tree is not exposed here"], 1.0),
            "separations": build_separation_table(
                doc, budget, scan["raw_separations"], scan["devicen"]),
            "xobjects": scan["xobjects"],
            "ai_private_data": inspect_ai_private(scan),
            "requires_human": {
                "exact_wording": _inf(None, C.TIER_REQUIRES_HUMAN, "no_live_text",
                                      ["all typography outlined"], 0.0)
                | {"status": "unavailable / requires OCR"},
                "language": _inf(None, C.TIER_REQUIRES_HUMAN, "no_live_text",
                                 ["all typography outlined"], 0.0)
                | {"status": "unavailable / requires OCR or human confirmation"},
                "font_family": _inf(None, C.TIER_REQUIRES_ILLUSTRATOR,
                                    "no_embedded_fonts",
                                    ["0 embedded fonts; never inferred from "
                                     "visual resemblance"], 0.0)
                | {"status": "unavailable"},
                "type_style": _inf(None, C.TIER_REQUIRES_HUMAN, "no_live_text",
                                   ["outlined geometry only"], 0.0)
                | {"status": "uncertain"},
            },
            "pages": pages,
            "limits": budget.to_dict(),
        }
        return record
    finally:
        doc.close()
