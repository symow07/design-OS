"""Reference-library indexing & product-aware selection (2026-07-06).

With 90+ production files in the library, the Creative Director must study
the references RELEVANT to the task's product, not the newest few. Two
halves:

  tag_reference(ref)     — one-time vision call per imported file: what
                           product type it is, its motifs/finishes/palette,
                           a one-line summary. ~$0.01/file on the fast model.
  select_references(task, limit)
                         — scores active references against the task's
                           product (category, type, name) + task text and
                           returns the best PNG paths; falls back to newest.
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_TAG_SYSTEM = """You are indexing a cosmetics packaging design reference library.
You will see ONE production artwork/dieline file (flattened image). Identify what
it is and describe it for retrieval. Respond ONLY with valid JSON:
{
  "category": "SK" | "HC" | "CO" | "",        // SKincare, Hair Care, COsmetics
  "product_type": "short type, e.g. 'eyeshadow palette', 'lip gloss', 'eyebrow powder'",
  "motifs": ["list", "of", "visual", "motifs"],
  "finishes": ["foil", "emboss", "matte", ...],
  "palette": ["dominant", "color", "words"],
  "summary": "one sentence: what this design is and its visual character"
}"""


def tag_reference(ref, log=None) -> bool:
    """Vision-tag one DesignReference row in place. Returns True on success."""
    log = log or (lambda msg: None)
    if not settings.ANTHROPIC_API_KEY:
        return False
    png = Path(settings.MEDIA_ROOT) / ref.image_path
    if not png.exists():
        return False
    try:
        from apps.pipeline.services.claude_service import (
            call_claude,
            extract_json,
            image_block_from_file,
        )
        content = [
            image_block_from_file(str(png)),
            {"type": "text",
             "text": f"Source filename (may hint at the product): {ref.source_file}"},
        ]
        response = call_claude(
            _TAG_SYSTEM, content, max_tokens=500,
            model=settings.CLAUDE_MODEL_FAST, operation="reference_tagging",
        )
        data = extract_json(response)
        ref.category = data.get("category") or ""
        if ref.category not in ("SK", "HC", "CO"):
            ref.category = ""
        ref.product_type = str(data.get("product_type") or "")[:120]
        tags = []
        for key in ("motifs", "finishes", "palette"):
            values = data.get(key) or []
            if isinstance(values, list):
                tags += [str(v).lower() for v in values if v]
        ref.tags = tags[:40]
        ref.summary = str(data.get("summary") or "")[:500]
        ref.save(update_fields=["category", "product_type", "tags", "summary"])
        log(f"tagged {ref.name}: {ref.product_type or '?'} [{ref.category or '-'}]")
        return True
    except Exception as exc:  # noqa: BLE001 — per-file, tagging is best-effort
        logger.warning("reference tagging failed for %s: %s", ref.name, exc)
        return False


_ANATOMY_SYSTEM = """You are performing a DEEP part-by-part study of one real
production packaging file for a beauty brand's design library. Study every
element one by one — layout, type, motifs, color, finishes, back panel — and
record it as structured, retrieval-ready data. Respond ONLY with valid JSON:
{
  "layout": {
    "logo_position": "e.g. 'upper third, centered'",
    "logo_scale": "e.g. 'about 60% of panel width'",
    "title_treatment": "how the product name is set and placed",
    "composition_grid": "how the front face is organized (1-2 sentences)"
  },
  "typography": {
    "case": "UPPERCASE / Title Case / mixed",
    "weights": ["light", "bold", ...],
    "serif_sans": "serif | sans | mixed",
    "hierarchy": "1 sentence: what reads first, second, third"
  },
  "motifs": [
    {"element": "e.g. 'line-engraved rose'",
     "placement": "e.g. 'corner clusters framing the wordmark'",
     "style": "rendering technique, e.g. 'single-weight etching, gold leaf accents'"}
  ],
  "palette_hex": ["#RRGGBB", ...],
  "finishes": ["foil", "emboss", ...],
  "back_panel": {
    "sticker_frame": true/false,
    "trilingual": true/false,
    "barcode_placement": "e.g. 'bottom left with batch box'",
    "blocks": ["order of content blocks top to bottom"]
  }
}"""


def analyze_reference_anatomy(ref, log=None) -> bool:
    """Deep vision study of one reference; saves ref.anatomy. Best-effort."""
    log = log or (lambda msg: None)
    if not settings.ANTHROPIC_API_KEY:
        return False
    png = Path(settings.MEDIA_ROOT) / ref.image_path
    if not png.exists():
        return False
    try:
        from apps.pipeline.services.claude_service import (
            call_claude,
            extract_json,
            image_block_from_file,
        )
        content = [
            image_block_from_file(str(png)),
            {"type": "text",
             "text": f"Source filename (may hint at the product): {ref.source_file}"},
        ]
        response = call_claude(
            _ANATOMY_SYSTEM, content, max_tokens=1200,
            model=settings.CLAUDE_MODEL_FAST, operation="reference_anatomy",
        )
        data = extract_json(response)
        if not isinstance(data, dict) or not data:
            return False
        ref.anatomy = data
        ref.save(update_fields=["anatomy"])
        log(f"anatomy: {ref.name} studied "
            f"({len(data.get('motifs') or [])} motif(s))")
        return True
    except Exception as exc:  # noqa: BLE001 — per-file, analysis is best-effort
        logger.warning("reference anatomy failed for %s: %s", ref.name, exc)
        return False


def anatomy_digest(refs, max_refs: int = 4, max_chars: int = 2000, names=()) -> str:
    """Compact per-reference anatomy JSON for prompt injection.

    Numbered to correspond to the attached-image order (reference 1 = first
    attached reference image). Hard character cap keeps the token budget sane.
    """
    import json

    lines = []
    for i, ref in enumerate(refs[:max_refs], start=1):
        if not getattr(ref, "anatomy", None):
            continue
        # [his test findings on design 121, 2026-10-07, item 4: "Earlier designs may inform style only, never names."]
        # a past design's anatomy without its names and its copy — 'Lip Oil', 'Subtle Gloss' reached 121's planner so —
        # and named by its kind, never by its file
        # — each of its words cleaned where it stands, the anatomy's own shape kept
        from apps.pipeline.services.other_designs import style_only_in
        blob = json.dumps(style_only_in(ref.anatomy, names), ensure_ascii=False, separators=(",", ":"))
        per_ref = max_chars // max(1, min(len(refs), max_refs))
        kind = ref.product_type if ref.product_type else "a past BBROSE design"
        lines.append(f"reference {i} ({kind}): {blob[:per_ref]}")
    return "\n".join(lines)


def _query_tokens(task, profile=None) -> set[str]:
    parts = [getattr(task, "task_text", "") or ""]
    product = getattr(task, "product", None)
    if product is not None:
        parts += [product.name or "", product.product_type or "",
                  product.get_category_display() or "", product.notes or ""]
    if profile:
        parts += [profile.get("name") or "", profile.get("product_type") or ""]
    text = " ".join(parts).lower()
    return {w for w in "".join(
        ch if ch.isalnum() else " " for ch in text
    ).split() if len(w) > 2}


def select_reference_records(task, limit: int, profile=None) -> list:
    """The most relevant DesignReference ROWS for this task (scored).

    ``profile`` (resolve_product_profile) supplies the identified category and
    product type when the task has no Product record, so an inferred
    "eyeshadow palette [CO]" still gets the category bonus. Rows whose PNG is
    missing on disk are dropped.
    """
    from apps.core.models import DesignReference
    from apps.pipeline.services.concept_references import withheld_reference_ids

    # §BH60(b), OWNER RULED: a reproduction run "DOES NOT GET THE ORIGINAL ARTWORK, in any form, at any stage."
    # THIS IS THE CHANNEL THE §BH60 WITHHOLDING NEVER REACHED, found on the §BH65(d) re-run (2026-09-23): the Creative
    # Director attaches the rows chosen here as IMAGES with their anatomy digest to the call that writes the
    # directions, and ARIA hands the closest one's anatomy to the Prompt Engineer. On task 89's run and task 90's,
    # DesignReference 15 — the original itself — was the first of four. A reference the task's project withholds is
    # never chosen here, so it reaches none of them.
    withheld = withheld_reference_ids(task)
    refs = [r for r in DesignReference.objects.filter(active=True) if r.id not in withheld]
    if not refs:
        return []
    tokens = _query_tokens(task, profile)
    product = getattr(task, "product", None)
    category = getattr(product, "category", "") if product else ""
    if not category and profile:
        category = profile.get("category") or ""

    def score(ref):
        s = 0
        if category and ref.category == category:
            s += 3
        type_words = set((ref.product_type or "").lower().split())
        s += 2 * len(tokens & type_words)
        hay = set(ref.tags or []) | set((ref.summary or "").lower().split())
        s += len(tokens & hay)
        return s

    scored = sorted(refs, key=lambda r: (-score(r), -r.id))
    top = [r for r in scored[:limit] if score(r) > 0]
    chosen = top if top else scored[:limit]   # nothing matched → newest
    media = Path(settings.MEDIA_ROOT)
    return [r for r in chosen if (media / r.image_path).exists()]


def select_references(task, limit: int, profile=None) -> list[str]:
    """Absolute PNG paths of the most relevant references (path wrapper)."""
    media = Path(settings.MEDIA_ROOT)
    return [str(media / r.image_path)
            for r in select_reference_records(task, limit, profile)]
