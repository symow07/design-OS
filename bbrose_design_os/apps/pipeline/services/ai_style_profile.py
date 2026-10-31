"""Native .ai design-library intelligence (2A-6E-CORR-8 §6/§7).

§6: task-scoped candidate retrieval over the DIP inventory's native `.ai`
sources (historical production designs first), so the user can approve 2–3
files for CONCEPT ANALYSIS — the same narrow permission as image references:
composition, density, typography zones, color relationships, line weights,
finish conventions. Never: copying paths or artwork, embedding sources,
production use, rights changes.

§7: for APPROVED references only, a bounded feature extraction from the
native structure via PyMuPDF — ai_reference_style_profile/1.0. Derived
DESCRIPTORS only (scales, ratios, counts, colors, zones); no source path
data is ever persisted, and extraction refuses unapproved rows.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from django.conf import settings

AI_STYLE_SCHEMA = "ai_reference_style_profile/1.0"
SOURCE_AI_LIBRARY = "AI_DESIGN_LIBRARY"

#: Product-vocabulary aliases for the house SKU naming.
_PRODUCT_ALIASES = {
    "face powder": ("fb", "bp", "粉饼", "powder", "pressed"),
    "blush": ("bl", "blush", "腮红"),
    "foundation": ("fd", "foundation", "粉底"),
    "complexion": ("fb", "bp", "bl", "hl"),
}


def _dip_inventory_path() -> Path:
    from apps.pipeline.services.concept_references import _dip_inventory_path
    return _dip_inventory_path()


#: [His goal of 2026-10-06, item 13.] The words a brief names each family's products with — a family is searched for
#: only when the brief names it; the house's codes (fb, bl …) are the files' names, never a brief's words
_FAMILY_WORDS = {"face powder": ("powder", "pressed"), "blush": ("blush",), "foundation": ("foundation",)}


def product_family(task) -> str | None:
    """The family of the house's .ai files the brief's own product words name, or None (``_FAMILY_WORDS``)."""
    from apps.pipeline.targets.container import brief_text, product_words, without_choice
    words = set(re.findall(r"[a-z]+", product_words(without_choice(brief_text(task))).lower()))
    return next((family for family, said in _FAMILY_WORDS.items() if words & set(said)), None)


def ai_design_candidates(task, product_type: str | None = None,
                         limit: int = 8) -> list[dict]:
    """Scored native-.ai candidates from the design library (read-only) — [his goal of 2026-10-06, item 13] of the
    family the brief's product is (``product_family``), and none where its brief names none: every design was offered
    the face powders (this read ``product_type="face powder"`` for every call)."""
    inventory = _dip_inventory_path()
    if not inventory.exists():
        return []
    product_type = product_type or product_family(task)
    if not product_type or product_type.lower() not in _PRODUCT_ALIASES:
        return []
    aliases = _PRODUCT_ALIASES[product_type.lower()]
    rows = []
    with open(inventory, encoding="utf-8") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            category = record.get("category")
            if isinstance(category, dict):
                category = category.get("value")
            if category not in ("HISTORICAL_DESIGN", "PRODUCT_REFERENCE"):
                continue
            if (record.get("extension") or "").lower() != ".ai":
                continue
            relative = record.get("relative_path") or ""
            stem = Path(relative).stem.lower()
            score = 2.0 if category == "HISTORICAL_DESIGN" else 1.0
            hits = [alias for alias in aliases
                    if re.search(rf"(^|[^a-z]){re.escape(alias)}", stem)
                    or alias in stem]
            score += 3.0 * len(hits)
            if not hits:
                continue      # only offer relevant sources, never padding
            ownership = record.get("ownership_status")
            if isinstance(ownership, dict):
                ownership = ownership.get("value")
            license_status = record.get("license_status")
            if isinstance(license_status, dict):
                license_status = license_status.get("value")
            rows.append({
                "source_type": SOURCE_AI_LIBRARY,
                "library_item_id":
                    f"ai:{record.get('sha256', relative)[:64]}",
                "title": Path(relative).stem[:200],
                "description": f"{category} native .ai source"[:500],
                "relevance_reason": ("matches product vocabulary "
                                     + "/".join(hits))[:300],
                "retrieval_score": score,
                "ownership_status": (
                    "HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED"
                    if category == "HISTORICAL_DESIGN"
                    else (ownership or "UNKNOWN"))[:60],
                "rights_status": (license_status or "RIGHTS_UNREVIEWED")[:60],
                "is_vector": True,
                "image_root": "materials",
                "image_path": relative[:500],
            })
    rows.sort(key=lambda r: (-r["retrieval_score"], r["library_item_id"]))
    return rows[:limit]


def render_ai_thumbnail(path: Path, cache_key: str) -> Path | None:
    """A PNG preview of a native .ai (PDF-compatible) file, cached under
    MEDIA_ROOT/concept_thumbs/. Read-only on the source."""
    import fitz

    cache_dir = Path(settings.MEDIA_ROOT) / "concept_thumbs"
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{cache_key}.png"
    if out.exists():
        return out
    try:
        with fitz.open(str(path)) as doc:
            page = doc[0]
            zoom = min(1.0, 640.0 / max(page.rect.width, 1.0))
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            pix.save(str(out))
        return out
    except Exception:  # noqa: BLE001 — a preview is best-effort
        return None


def quick_ai_stats(path: Path) -> dict:
    """Lightweight native structure stats for the candidate card."""
    import fitz

    try:
        with fitz.open(str(path)) as doc:
            page = doc[0]
            drawings = page.get_drawings()
            text = page.get_text("dict")
            return {
                "pages": doc.page_count,
                "vector_object_count": len(drawings),
                "text_block_count": len(text.get("blocks", [])),
                "page_mm": [round(page.rect.width * 25.4 / 72, 1),
                            round(page.rect.height * 25.4 / 72, 1)],
            }
    except Exception:  # noqa: BLE001
        return {}


def extract_style_profile(reference) -> dict:
    """ai_reference_style_profile/1.0 for a USER-APPROVED .ai reference.

    Refuses unapproved rows. Derived descriptors only — no path
    coordinates, no glyph outlines, no reusable artwork data."""
    from apps.pipeline.models import ConceptReference
    from apps.pipeline.services.concept_references import reference_file_path

    if reference.permission_status != ConceptReference.PERMISSION_APPROVED:
        raise PermissionError(
            "style extraction requires USER_APPROVED_FOR_CONCEPT_REFERENCE")
    import fitz

    path = reference_file_path(reference)
    with fitz.open(str(path)) as doc:
        page = doc[0]
        page_w, page_h = page.rect.width, page.rect.height
        page_area = max(1.0, page_w * page_h)
        text = page.get_text("dict")
        text_boxes = []
        max_text_h = 0.0
        for block in text.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    x0, y0, x1, y1 = span["bbox"]
                    height = y1 - y0
                    max_text_h = max(max_text_h, height)
                    text_boxes.append({
                        "x": round(x0 / page_w, 3),
                        "y": round(y0 / page_h, 3),
                        "w": round((x1 - x0) / page_w, 3),
                        "h": round(height / page_h, 3),
                        "size_rel": round(height / page_h, 4),
                    })
        drawings = page.get_drawings()
        stroke_widths = [d.get("width") or 0.0 for d in drawings
                         if d.get("width")]
        fills = {}
        covered = 0.0
        min_x = min_y = 1.0
        max_x = max_y = 0.0
        for d in drawings:
            rect = d.get("rect")
            if rect:
                covered += rect.width * rect.height
                min_x = min(min_x, rect.x0 / page_w)
                min_y = min(min_y, rect.y0 / page_h)
                max_x = max(max_x, rect.x1 / page_w)
                max_y = max(max_y, rect.y1 / page_h)
            fill = d.get("fill")
            if fill:
                key = "#%02X%02X%02X" % tuple(
                    int(max(0, min(1, c)) * 255) for c in fill[:3])
                fills[key] = fills.get(key, 0) + 1
        dominant = sorted(fills.items(), key=lambda kv: -kv[1])[:8]
        return {
            "schema_version": AI_STYLE_SCHEMA,
            "reference_id": reference.pk,
            "permission": reference.permission_status,
            "page_mm": [round(page_w * 25.4 / 72, 1),
                        round(page_h * 25.4 / 72, 1)],
            "text_block_count": len(text_boxes),
            "headline_to_page_scale": round(max_text_h / page_h, 4),
            "text_zones": sorted(text_boxes,
                                 key=lambda b: -b["size_rel"])[:12],
            "path_density_per_100cm2": round(
                len(drawings) / (page_area * (25.4 / 72) ** 2 / 10000.0), 1),
            "vector_object_count": len(drawings),
            "stroke_width_range_pt": ([round(min(stroke_widths), 2),
                                       round(max(stroke_widths), 2)]
                                      if stroke_widths else None),
            "dominant_swatches": [{"hex": color, "count": count}
                                  for color, count in dominant],
            "drawing_coverage_fraction": round(
                min(1.0, covered / page_area), 4),
            "motif_bounding": {"x": round(min_x, 3), "y": round(min_y, 3),
                               "w": round(max(0.0, max_x - min_x), 3),
                               "h": round(max(0.0, max_y - min_y), 3)},
            "whitespace_fraction": round(
                max(0.0, 1.0 - covered / page_area), 4),
            "note": "derived descriptors only — no source paths persisted",
        }


__all__ = ["ai_design_candidates", "render_ai_thumbnail", "quick_ai_stats",
           "extract_style_profile", "AI_STYLE_SCHEMA", "SOURCE_AI_LIBRARY"]
