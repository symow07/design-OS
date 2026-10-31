"""web_reference_visual_review_packet/1.0 — the human contact sheet for
session #3's shortlisted sources.

Two responsibilities, both governed:

* `acquire_representative_visual` — at most ONE representative image per
  page-based shortlisted source, located on the source's OWN page (its
  declared og:image / primary product image) and pulled through the same
  access-policy pipeline as every other fetch (SSRF, robots, MIME, redirect,
  byte caps, quarantine). Failure is honest: VISUAL EVIDENCE UNAVAILABLE,
  never a substitute from another domain.
* `build_visual_review_packet` — large-card PDF + PNG contact sheet + JSON
  decision template, validated (§12) before it is offered, changing NO
  permission state.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

from django.utils import timezone

from apps.pipeline.services import web_research as wr

PACKET_SCHEMA = "web_reference_visual_review_packet/1.0"
PACKET_SCHEMA_V11 = "web_reference_visual_review_packet/1.1"
PARTIALLY_COMPLETE = "VISUAL_REVIEW_PACKET_PARTIALLY_COMPLETE"

#: section config: letter -> (title, allowed classifications or None,
#: image-exempt). Image-exempt sections (warning/appendix) don't require the
#: styling line; appendix sections must stay TEXT-ONLY.
SECTIONS_V10 = {
    "A": ("A. PRIMARY PHYSICAL ANALOGS", ("analog", "image"), False),
    "B": ("B. ALTERNATE PHYSICAL ANALOGS", ("analog", "image"), False),
    "C": ("C. PRIMARY VISUAL INSPIRATIONS", ("inspiration", "image"), False),
    "D": ("D. ALTERNATE VISUAL INSPIRATIONS", ("inspiration", "image"),
          False),
    "E": ("E. BRAND-IDENTITY VERIFICATION ISSUE", None, True),
}
SECTIONS_V11 = {
    "A": ("A. VISUALLY REVIEWABLE PHYSICAL ANALOGS", ("analog", "image"),
          False),
    "B": ("B. VISUALLY REVIEWABLE INSPIRATIONS", ("inspiration", "image"),
          False),
    "C": ("C. BRAND-IDENTITY WARNING", None, True),
    "D": ("D. TEXT-ONLY / VISUAL EVIDENCE UNAVAILABLE APPENDIX",
          ("analog", "inspiration", "image"), True),
}
#: appendix letters per config — text-only, never counted as reviewable
APPENDIX = {"V10": (), "V11": ("D",)}
UNAVAILABLE = "VISUAL EVIDENCE UNAVAILABLE"
STYLING_LABEL = "PHOTOGRAPHIC STYLING — NOT PRINTED ARTWORK"
REFERENCE_ONLY_LABEL = "REFERENCE ONLY — DO NOT COPY ARTWORK"
NOT_EXACT_LABEL = "NOT THE EXACT BBR-SK-201 PRODUCT"

# §12 stable failure codes
VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH = "VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH"
VISUAL_REVIEW_EVIDENCE_UNAVAILABLE = "VISUAL_REVIEW_EVIDENCE_UNAVAILABLE"
VISUAL_REVIEW_CLASSIFICATION_MIXED = "VISUAL_REVIEW_CLASSIFICATION_MIXED"
VISUAL_REVIEW_PROVENANCE_MISSING = "VISUAL_REVIEW_PROVENANCE_MISSING"
PHOTOGRAPHIC_STYLING_MISCLASSIFIED = "PHOTOGRAPHIC_STYLING_MISCLASSIFIED"
UNAUTHORIZED_PERMISSION_CHANGE = "UNAUTHORIZED_PERMISSION_CHANGE"


class VisualReviewError(Exception):
    def __init__(self, code, detail=""):
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


# --- §2 representative-image acquisition -------------------------------------------

_OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']'
    r'[^>]+content=["\']([^"\']+)["\']', re.IGNORECASE)
_OG_RE_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+'
    r'(?:property|name)=["\'](?:og:image|twitter:image)["\']', re.IGNORECASE)
_IMG_RE = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)


def _candidate_image_urls(page_url: str, html: str) -> list[str]:
    """The page's OWN declared representative images, og/twitter first."""
    urls = []
    for rx in (_OG_RE, _OG_RE_REV):
        urls += [m.group(1) for m in rx.finditer(html)]
    urls += [m.group(1) for m in _IMG_RE.finditer(html)
             if not m.group(1).startswith("data:")][:10]
    out, seen = [], set()
    for u in urls:
        absolute = urljoin(page_url, u.strip())
        if absolute not in seen and urlparse(absolute).scheme in ("http",
                                                                  "https"):
            seen.add(absolute)
            out.append(absolute)
    return out


def representative_visual(source) -> dict | None:
    """The already-recorded representative visual for a source, if any."""
    if source.classification == "image" and source.quarantine_path and \
            source.mime_type.startswith("image/"):
        return {"quarantine_path": source.quarantine_path,
                "image_url": source.original_url,
                "provenance": "retained session image (source itself)"}
    for w in source.extraction_warnings:
        if isinstance(w, dict) and w.get("kind") == "representative_visual":
            return w
    return None


def acquire_representative_visual(session, source, *, http_get=None,
                                  robots=None) -> dict | None:
    """Fetch at most ONE representative image from the source's own page.
    Governed end to end; idempotent; None on any policy-compliant failure
    (the card then shows VISUAL EVIDENCE UNAVAILABLE)."""
    from apps.pipeline.models import WebAccessRecord

    existing = representative_visual(source)
    if existing is not None:
        return existing
    config = wr.gateway_config()
    robots_files: dict = {}

    def _verdict(url: str) -> str:
        """§BH71 PART 2: this url's robots verdict — its authority's file read once, matched to its own path."""
        if robots is not None:                    # an injected checker, asked per url
            read = robots(url, config["user_agent"])
            if isinstance(read, dict):
                return read["verdict"]
            return read
        origin = wr.robots_origin(url)
        if origin not in robots_files:
            robots_files[origin] = wr.robots_file(url, config["user_agent"])
        return wr.robots_verdict(robots_files[origin], config["user_agent"], url)["verdict"]

    try:
        wr.check_url_policy(source.original_url)
        verdict = _verdict(source.original_url)
        if verdict != "allowed":
            # [§BH71 PART 2: only 'allowed' allows here too — an unreadable robots.txt is a refusal (RFC 9309
            # §2.3.1.4); it refused 'disallowed' alone]
            outcome = wr.WEB_ROBOTS_DISALLOWED
            if verdict != "disallowed":
                outcome = wr.WEB_ROBOTS_UNREADABLE
            WebAccessRecord.objects.create(
                session=session, kind="policy_block",
                url=source.original_url, domain=source.domain,
                outcome=outcome,
                detail="visual-review page fetch — robots respected")
            return None
        page = wr.governed_fetch(source.original_url, config,
                                 http_get=http_get, robots=_verdict)
        WebAccessRecord.objects.create(
            session=session, kind="page_fetch", url=source.original_url,
            domain=source.domain, outcome="ok",
            http_status=page["http_status"], byte_count=page["byte_count"],
            detail="visual-review representative-image location")
        if page["mime_type"] != "text/html":
            return None
        html = page["body"].decode("utf-8", errors="replace")
        for image_url in _candidate_image_urls(source.original_url,
                                               html)[:5]:
            try:
                wr.check_url_policy(image_url)
                # [§BH71 PART 2: the image's own url asked of its host's robots.txt — it was fetched unasked]
                image_verdict = _verdict(image_url)
                if image_verdict != "allowed":
                    outcome = wr.WEB_ROBOTS_DISALLOWED
                    if image_verdict != "disallowed":
                        outcome = wr.WEB_ROBOTS_UNREADABLE
                    WebAccessRecord.objects.create(
                        session=session, kind="policy_block", url=image_url,
                        domain=urlparse(image_url).netloc, outcome=outcome,
                        detail="visual-review image fetch — robots respected")
                    continue
                fetched = wr.governed_fetch(image_url, config,
                                            http_get=http_get, robots=_verdict)
                if not fetched["mime_type"].startswith("image/"):
                    continue
                if fetched["byte_count"] < 4096:
                    continue                    # tracking pixels / favicons
                name = (f"visual_{source.id}_"
                        f"{Path(urlparse(image_url).path).name or 'image'}")
                path = wr.quarantine_write(config["quarantine_root"],
                                           session.id, name,
                                           fetched["body"])
                WebAccessRecord.objects.create(
                    session=session, kind="image_fetch", url=image_url,
                    domain=urlparse(image_url).hostname or "",
                    outcome="ok", http_status=fetched["http_status"],
                    byte_count=fetched["byte_count"],
                    detail=f"visual-review representative image for "
                           f"source {source.id}")
                record = {"kind": "representative_visual",
                          "image_url": image_url,
                          "declared_by_page": source.original_url,
                          "quarantine_path": path,
                          "content_sha256": fetched["content_sha256"],
                          "acquired_at": timezone.now().isoformat(),
                          "provenance": "og/primary image declared by the "
                                        "source's own page"}
                source.extraction_warnings.append(record)
                source.save(update_fields=["extraction_warnings"])
                return record                    # exactly ONE image
            except wr.WebPolicyError as exc:
                WebAccessRecord.objects.create(
                    session=session, kind="image_fetch", url=image_url,
                    domain=urlparse(image_url).hostname or "",
                    outcome=exc.code, detail=str(exc)[:300])
                continue
        return None
    except wr.WebPolicyError as exc:
        WebAccessRecord.objects.create(
            session=session, kind="page_fetch", url=source.original_url,
            domain=source.domain, outcome=exc.code,
            detail=f"visual-review: {exc}"[:300])
        return None
    except Exception as exc:  # noqa: BLE001 — network faults stay honest
        WebAccessRecord.objects.create(
            session=session, kind="page_fetch", url=source.original_url,
            domain=source.domain, outcome="NETWORK_ERROR",
            detail=str(exc)[:300])
        return None


# --- §3-§9 the contact sheet ---------------------------------------------------------

CARD_W, CARD_H = 1400, 1960
IMG_H = 900
MARGIN = 46


def _font(size):
    from PIL import ImageFont
    for path in ("/System/Library/Fonts/Helvetica.ttc",
                 "/System/Library/Fonts/Supplemental/Arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    from PIL import ImageFont as F
    return F.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, line = str(text).split(), [], ""
    for w in words:
        probe = f"{line} {w}".strip()
        if draw.textlength(probe, font=font) <= max_w:
            line = probe
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def _draw_card(entry) -> "object":
    """One large review card: image on top, labelled facts below."""
    from PIL import Image, ImageDraw

    card = Image.new("RGB", (CARD_W, CARD_H), (250, 249, 246))
    d = ImageDraw.Draw(card)
    f_head = _font(52)
    f_label = _font(38)
    f_body = _font(30)
    f_small = _font(26)

    accent = entry.get("accent") or {
        "A": (26, 82, 118), "B": (26, 82, 118), "C": (120, 66, 18),
        "D": (120, 66, 18), "E": (140, 20, 20)}.get(entry["section"],
                                                    (26, 82, 118))
    d.rectangle([0, 0, CARD_W, 12], fill=accent)

    # image area
    box = [MARGIN, 90, CARD_W - MARGIN, 90 + IMG_H]
    path = entry.get("quarantine_path")
    if path and Path(path).is_file():
        img = Image.open(path).convert("RGB")
        img.thumbnail((box[2] - box[0], box[3] - box[1]))
        ox = box[0] + (box[2] - box[0] - img.width) // 2
        oy = box[1] + (box[3] - box[1] - img.height) // 2
        card.paste(img, (ox, oy))
    else:
        d.rectangle(box, outline=(150, 150, 150), width=3)
        d.text((CARD_W // 2, (box[1] + box[3]) // 2), UNAVAILABLE,
               font=f_head, fill=(120, 30, 30), anchor="mm")

    d.text((MARGIN, 24), f"SOURCE {entry['source_id']}  ·  {entry['domain']}",
           font=f_head, fill=(20, 20, 20))

    y = 90 + IMG_H + 18
    for banner, colour in entry.get("banners", []):
        d.rectangle([MARGIN, y, CARD_W - MARGIN, y + 54], fill=colour)
        d.text((CARD_W // 2, y + 27), banner, font=f_label,
               fill=(255, 255, 255), anchor="mm")
        y += 66

    for label, value in entry.get("fields", []):
        lines = _wrap(d, value, f_body, CARD_W - 2 * MARGIN - 340)
        d.text((MARGIN, y), label, font=f_body, fill=accent)
        for ln in lines:
            d.text((MARGIN + 340, y), ln, font=f_body, fill=(35, 35, 35))
            y += 40
        y += 6
        if y > CARD_H - 140:
            break

    for note in entry.get("footnotes", []):
        for ln in _wrap(d, note, f_small, CARD_W - 2 * MARGIN):
            if y > CARD_H - 40:
                break
            d.text((MARGIN, y), ln, font=f_small, fill=(90, 90, 90))
            y += 34
    return card


def _title_page(title, lines):
    from PIL import Image, ImageDraw
    page = Image.new("RGB", (CARD_W, CARD_H), (250, 249, 246))
    d = ImageDraw.Draw(page)
    d.text((MARGIN, 120), title, font=_font(64), fill=(20, 20, 20))
    y = 260
    for text in lines:
        for ln in _wrap(d, text, _font(34), CARD_W - 2 * MARGIN):
            d.text((MARGIN, y), ln, font=_font(34), fill=(45, 45, 45))
            y += 48
        y += 24
    return page


def build_visual_review_packet(session, entries, archetype_lines,
                               decision_lines, out_dir, *,
                               section_config=None, appendix=(),
                               schema_version=PACKET_SCHEMA,
                               file_prefix="session_3_visual_review") -> dict:
    """Compose, validate (§12) and write the PDF + PNG + JSON. Returns the
    manifest. Changes no permission state — verified by the caller."""
    from PIL import Image

    section_config = section_config or SECTIONS_V10
    validate_entries(session, entries, section_config=section_config,
                     appendix=appendix)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    sections = {k: v[0] for k, v in section_config.items()}
    pages = [_title_page(
        "SESSION #3 — WEB REFERENCE VISUAL REVIEW",
        [f"{schema_version} · "
         f"generated {timezone.now().date()}",
         "Every analog is NOT the exact BBR-SK-201 product. Every "
         "inspiration is REFERENCE ONLY — artwork is never copied.",
         "Reference-view is the ONLY enabled permission. Provider input, "
         "artwork reuse, fact-source and Design Memory all remain false "
         "until decided source-by-source.",
         "Sections: " + " · ".join(sections.values())])]
    current = None
    for e in entries:
        if e["section"] != current:
            current = e["section"]
        pages.append(_draw_card(e))
    pages.append(_title_page("ARCHETYPE COMPARISON — evidence only, "
                             "NO selection made", archetype_lines))
    pages.append(_title_page("HUMAN DECISION FORM", decision_lines))

    pdf_path = out / f"{file_prefix}.pdf"
    pages[0].save(pdf_path, save_all=True, append_images=pages[1:],
                  format="PDF", resolution=150)

    cols = 4
    thumb_w = 700
    thumb_h = int(CARD_H * thumb_w / CARD_W)
    rows = (len(pages) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (thumb_w + 20) + 20,
                              rows * (thumb_h + 20) + 20), (235, 233, 228))
    for i, page in enumerate(pages):
        t = page.copy()
        t.thumbnail((thumb_w, thumb_h))
        sheet.paste(t, (20 + (i % cols) * (thumb_w + 20),
                        20 + (i // cols) * (thumb_h + 20)))
    png_path = out / f"{file_prefix}.png"
    sheet.save(png_path, "PNG")

    warning_letters = {k for k, v in section_config.items() if v[1] is None}
    non_decidable = warning_letters | set(appendix)
    template = {
        "schema_version": schema_version,
        "session_id": session.id,
        "decisions": {str(e["source_id"]): {
            "options": e["decision_options"], "decision": None}
            for e in entries if e["section"] not in non_decidable},
        "source_44": {"options": ["NEEDS_VERIFICATION (keep)", "REJECT"],
                      "decision": None,
                      "note": "BRAND IDENTITY VERIFICATION REQUIRED — "
                              "EXCLUDED FROM PILOT INPUT"},
        "archetype_choice": {
            "options": ["DROPPER BOTTLE", "TREATMENT PUMP",
                        "SCREW-CAP TREATMENT BOTTLE",
                        "NONE — RESEARCH AGAIN"],
            "decision": None},
    }
    json_path = out / f"{file_prefix}.json"
    json_path.write_text(json.dumps(template, indent=1) + "\n",
                         encoding="utf-8")

    candidate = [e for e in entries if e["section"] not in non_decidable]
    usable = [e for e in candidate if e.get("quarantine_path")]
    counts = {
        "requested_candidates": len(candidate),
        "visually_reviewable_analogs": sum(
            1 for e in usable
            if "ANALOG" in " ".join(e.get("decision_options", []))),
        "visually_reviewable_inspirations": sum(
            1 for e in usable
            if "INSPIRATION" in " ".join(e.get("decision_options", []))),
        "usable_pilot_candidate_visuals": len(usable),
        "excluded_warning_visuals": sum(
            1 for e in entries if e["section"] in warning_letters
            and e.get("quarantine_path")),
        "text_only_sources": sum(1 for e in entries
                                 if e["section"] in appendix),
        "missing_visual_evidence": len(candidate) - len(usable),
    }
    manifest = {
        "schema_version": schema_version,
        "generated_at": timezone.now().isoformat(),
        "status": (PARTIALLY_COMPLETE if counts["missing_visual_evidence"]
                   else "VISUAL_REVIEW_PACKET_COMPLETE"),
        "counts": counts,
        "pdf": str(pdf_path), "png": str(png_path), "json": str(json_path),
        "pdf_sha256": hashlib.sha256(pdf_path.read_bytes()).hexdigest(),
        "png_sha256": hashlib.sha256(png_path.read_bytes()).hexdigest(),
        "pages": len(pages),
        "represented_source_ids": [e["source_id"] for e in entries
                                   if e.get("quarantine_path")],
        "missing_visual_source_ids": [e["source_id"] for e in candidate
                                      if not e.get("quarantine_path")],
        "text_only_source_ids": [e["source_id"] for e in entries
                                 if e["section"] in appendix],
        "sections": {s: [e["source_id"] for e in entries
                         if e["section"] == s] for s in sections},
    }
    return manifest


def validate_entries(session, entries, *, section_config=None,
                     appendix=()) -> None:
    """§12 — refuse a malformed packet with a stable code."""
    section_config = section_config or SECTIONS_V10
    ids = [e["source_id"] for e in entries]
    if len(ids) != len(set(ids)):
        raise VisualReviewError(VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH,
                                "a source appears more than once")
    by_id = {s.id: s for s in session.sources.filter(id__in=ids)}
    for e in entries:
        src = by_id.get(e["source_id"])
        if src is None:
            raise VisualReviewError(VISUAL_REVIEW_PROVENANCE_MISSING,
                                    f"source {e['source_id']} not in session")
        section = e["section"]
        if section not in section_config:
            raise VisualReviewError(VISUAL_REVIEW_CLASSIFICATION_MIXED,
                                    f"unknown section {section!r}")
        title, allowed_classes, image_exempt = section_config[section]
        if src.human_review_state == "REJECTED" and section not in appendix \
                and allowed_classes is not None:
            raise VisualReviewError(
                VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH,
                f"rejected source {src.id} may not appear as a candidate")
        if allowed_classes is not None and \
                src.classification not in allowed_classes:
            raise VisualReviewError(
                VISUAL_REVIEW_CLASSIFICATION_MIXED,
                f"source {src.id} ({src.classification}) does not belong "
                f"in section {section}")
        path = e.get("quarantine_path")
        if section in appendix and path:
            # the appendix is TEXT-ONLY: an image here means a replacement
            # visual was attached to a historical empty source
            raise VisualReviewError(
                VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH,
                f"appendix source {src.id} must remain text-only")
        if path:
            visual = representative_visual(src)
            if visual is None or visual.get("quarantine_path") != path:
                raise VisualReviewError(
                    VISUAL_REVIEW_PROVENANCE_MISSING,
                    f"source {src.id} image has no recorded provenance")
            if not Path(path).is_file():
                raise VisualReviewError(
                    VISUAL_REVIEW_EVIDENCE_UNAVAILABLE,
                    f"source {src.id} quarantined image missing")
        if not image_exempt and not any(
                STYLING_LABEL in str(v) for _, v in e.get("fields", [])):
            raise VisualReviewError(
                PHOTOGRAPHIC_STYLING_MISCLASSIFIED,
                f"source {e['source_id']} card lacks the styling "
                "classification")


def permission_snapshot(session) -> dict:
    return {s.id: (s.human_review_state, s.reference_view_permission,
                   s.fact_source_permission, s.provider_input_permission,
                   s.artwork_reuse_permission, s.design_memory_permission)
            for s in session.sources.all()}


__all__ = [
    "PACKET_SCHEMA", "PACKET_SCHEMA_V11", "PARTIALLY_COMPLETE",
    "SECTIONS_V10", "SECTIONS_V11",
    "UNAVAILABLE", "STYLING_LABEL", "REFERENCE_ONLY_LABEL",
    "NOT_EXACT_LABEL", "VisualReviewError", "representative_visual",
    "acquire_representative_visual", "build_visual_review_packet",
    "validate_entries", "permission_snapshot",
    "VISUAL_REVIEW_SOURCE_IMAGE_MISMATCH",
    "VISUAL_REVIEW_EVIDENCE_UNAVAILABLE",
    "VISUAL_REVIEW_CLASSIFICATION_MIXED",
    "VISUAL_REVIEW_PROVENANCE_MISSING",
    "PHOTOGRAPHIC_STYLING_MISCLASSIFIED",
    "UNAUTHORIZED_PERMISSION_CHANGE",
]
