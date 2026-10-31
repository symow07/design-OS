"""Real text metrics from the ACTUAL registered faces (2A-6E-CORR-10).

The composer sized and the validator measured type with a fixed 0.52 em/char
estimate, so the report claimed a 67%-wide name group while quoting the
placeholder's guess — and the embedded BarlowCondensed-Bold was never asked.
Every width here comes from reportlab's stringWidth on the SAME registered
face the emitter draws with, and every visual height from the face's real
cap height (fontTools OS/2 sCapHeight), so sizing, measurement, and the
emitted PDF agree by construction.

TWO READERS PER METRIC, on purpose (VQR-3):

* the LENIENT pair (``text_width_mm``, ``cap_height_em``) substitutes a
  constant when the face cannot be asked. A composer needs *a* number to lay
  out with, and a layout computed from a slightly wrong em is a visible
  defect the measurement side is supposed to catch.
* the STRICT pair (``*_measured``) returns None instead. A measurement caller
  must never receive the layout fallback: a guessed extent handed back as a
  float is an estimate wearing a measurement's name, and downstream it reads
  as fact. This mirrors ``container_logo_metrics``, where an unreadable asset
  yields NO record rather than a plausible zero.

``resolve_metric_font`` previously returned ``(name, None)`` on its own
fallback branch while the registrar it delegates to had just loaded the face
from a path. Container callers therefore measured WIDTHS from the real face
and took the CAP HEIGHT from the 0.72 constant — half measured, half assumed,
described by one tuple. The path now comes back from the face reportlab
actually registered, so both metrics are read from the SAME file or neither
is.
"""
from __future__ import annotations

import os
from functools import lru_cache

_FALLBACK_ADVANCE_EM = 0.52
_FALLBACK_CAP_EM = 0.72


def register_font(name: str, path: str | None) -> bool:
    """Idempotently register a TTF/OTF with reportlab; False on failure."""
    if not name:
        return False
    from reportlab.pdfbase import pdfmetrics
    try:
        pdfmetrics.getFont(name)
        return True
    except KeyError:
        pass
    if not path or not os.path.exists(path):
        return False
    try:
        from reportlab.pdfbase.ttfonts import TTFont
        pdfmetrics.registerFont(TTFont(name, path))
        return True
    except Exception:  # noqa: BLE001 — metrics degrade to the fallback
        return False


def registered_font_path(font_name: str | None) -> str | None:
    """The FILE reportlab registered for ``font_name``, or None.

    Deliberately asked of reportlab rather than recomputed from the repo font
    directory: whichever face answered for the advance widths is the face
    whose cap height must be read. Guessing the path would let widths come
    from one file and heights from another. A built-in Type1 (Helvetica) has
    no file at all, and None is then the true answer.
    """
    if not font_name:
        return None
    from reportlab.pdfbase import pdfmetrics
    try:
        face = pdfmetrics.getFont(font_name).face
    except KeyError:
        return None
    path = getattr(face, "filename", None)
    return path if path and os.path.exists(path) else None


def text_width_mm(text: str, size_mm: float, font_name: str | None) -> float:
    """The emitted advance width of ``text`` at ``size_mm`` em size, falling
    back to a char-count estimate. LAYOUT callers only — a measurement caller
    wants ``text_width_mm_measured``."""
    measured = text_width_mm_measured(text, size_mm, font_name)
    if measured is not None:
        return measured
    return len(text) * size_mm * _FALLBACK_ADVANCE_EM


def text_width_mm_measured(text: str, size_mm: float,
                           font_name: str | None) -> float | None:
    """The EXACT emitted advance width, or None when the face is not
    registered and no width was measured at all."""
    if not font_name:
        return None
    from reportlab.pdfbase import pdfmetrics
    try:
        if "℮" in text:
            # [his goal of 2026-10-12, (5)] each ℮ in the room the files draw a 3 mm sign in (``size_mm`` is in mm)
            from apps.ire.estimated_sign import width
            return width(text, font_name, size_mm, per_mm=1.0)
        return pdfmetrics.stringWidth(text, font_name, size_mm)
    except KeyError:
        return None


def drawn_width_mm(text: str, size_mm: float, font_name: str | None) -> float | None:
    """[His goal of 2026-10-06, item 8: "measure with the real font outlines so it never crosses. A warning is not a
    fix."] The width ``text`` covers when drawn from its origin: its advances (as ``text_width_mm_measured``, the
    emitter's own) widened by any ink its glyphs' OUTLINES put before the origin or past the last advance — read from
    the very file the face is registered from. None where the face is not registered or a character has no glyph."""
    advance = text_width_mm_measured(text, size_mm, font_name)
    if advance is None:
        return None
    span = ink_span_em(text, registered_font_path(font_name))
    if span is None:
        return advance
    left, right = span
    return max(advance, right * size_mm) - min(0.0, left * size_mm)


@lru_cache(maxsize=2048)
def ink_span_em(text: str, font_path: str | None) -> tuple[float, float] | None:
    """The string's ink along its baseline, from its origin, in ems: ``(left, right)`` — each glyph's outline bounds
    placed at its advance (hmtx, no kerning — what reportlab draws). None where there is nothing to read."""
    if not font_path or not text:
        return None
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTLibError
    try:
        font = _font_file(font_path)
        cmap = font.getBestCmap()
        glyphs = font.getGlyphSet()
        hmtx = font["hmtx"]
        upm = float(font["head"].unitsPerEm)
    except (OSError, KeyError, TTLibError):
        return None
    x, left, right = 0.0, None, None
    for ch in text:
        glyph = cmap.get(ord(ch))
        if glyph is None:
            return None
        if not ch.isspace():
            pen = BoundsPen(glyphs)
            glyphs[glyph].draw(pen)
            if pen.bounds is not None:
                x0, _y0, x1, _y1 = pen.bounds
                left = x + x0 if left is None else min(left, x + x0)
                right = x + x1 if right is None else max(right, x + x1)
        x += hmtx[glyph][0]
    if left is None:
        return None
    return left / upm, right / upm


def cap_height_em(font_path: str | None) -> float:
    """The face's cap height as a fraction of the em, falling back to a
    constant. LAYOUT callers only — a measurement caller wants
    ``cap_height_em_measured``."""
    measured = cap_height_em_measured(font_path)
    return _FALLBACK_CAP_EM if measured is None else measured


@lru_cache(maxsize=16)
def cap_height_em_measured(font_path: str | None) -> float | None:
    """The face's REAL cap height (OS/2 sCapHeight / unitsPerEm), or None when
    the file is absent, undecodable, or states no cap height.

    None rather than the constant: 0.72 and NotoSans' true 0.714 differ by
    under 1%, so a caller handed the constant cannot tell a read face from an
    unread one by looking at the value.
    """
    if not (font_path and os.path.exists(font_path)):
        return None
    try:
        from fontTools.ttLib import TTFont as FTFont
        with FTFont(font_path, lazy=True) as font:
            upm = font["head"].unitsPerEm or 1000
            os2 = font.get("OS/2")
            cap = getattr(os2, "sCapHeight", 0) if os2 else 0
            if cap:
                return cap / upm
    except Exception:  # noqa: BLE001
        pass
    return None


@lru_cache(maxsize=16)
def _font_file(font_path: str):
    from fontTools.ttLib import TTFont
    return TTFont(font_path, lazy=True)


@lru_cache(maxsize=512)
def ink_extent_em(text: str, font_path: str | None) -> tuple[float, float] | None:
    """The string's INK above and below its baseline, as fractions of the em: the union of its own glyphs' outline
    bounds (yMax, yMin) in the very file the emitter draws it from — never a cap-height model. None where there is
    nothing to measure: no file, no ink, or a character the face has no glyph for (not measured, never guessed).
    Sideways placement does not matter to it: kerning and advances move glyphs along the baseline only.

    THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — the front-copy instrument's
    vertical axis reads this (compose_dropper._vertical_fit)."""
    if not font_path or not text or not text.strip():
        return None
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.ttLib import TTLibError
    try:
        font = _font_file(font_path)
        cmap = font.getBestCmap()
        glyphs = font.getGlyphSet()
        upm = float(font["head"].unitsPerEm)
    except (OSError, KeyError, TTLibError):
        return None
    top = bottom = None
    for ch in text:
        if ch.isspace():
            continue
        glyph = cmap.get(ord(ch))
        if glyph is None:
            return None
        pen = BoundsPen(glyphs)
        glyphs[glyph].draw(pen)
        if pen.bounds is None:
            continue
        _x0, y0, _x1, y1 = pen.bounds
        top = y1 if top is None else max(top, y1)
        bottom = y0 if bottom is None else min(bottom, y0)
    if top is None:
        return None
    return top / upm, bottom / upm


def resolve_metric_faces(doc_metadata: dict | None = None) -> dict:
    """``{logical role: (font_name, font_path)}`` — the SAME role→face map
    ``pdf_ai.emit_pdf_ai`` draws with.

    A run declares a logical role (``regular`` / ``bold`` / ``arabic``) and the
    emitter maps it to a real face. A measurer that asks ONE face about every
    run reports widths the emitted document will not have; a measurer that
    asks no face at all reports the char-count guess. Both were happening.

    Paths come from ``registered_font_path``, so a role's cap height is read
    from the very file its advance widths came from — including a confirmed
    face already registered under its name from elsewhere, where the claimed
    path and the loaded one can differ.
    """
    # §BH32(e) W3: the SAME resolution the emitter draws with — the role-based
    # selection layer, through the seam. The 2A-6E ``confirmed_font`` entry is
    # honoured for the bold/display role only when its bytes are in the layer's
    # catalogue (the 35 + the Noto trio).
    try:
        from apps.ire.font_roles import (is_exempt, legacy_metric_faces,
                                         legacy_role_map)
        # §BH32(h): an exempt surface — or an anonymous call, the way the ruled
        # surfaces' own measurers ask — resolves exactly as at 41604ac
        if is_exempt(doc_metadata):
            return legacy_metric_faces(doc_metadata)
        return dict(legacy_role_map(doc_metadata))
    except Exception:  # noqa: BLE001
        return {}


def resolve_role_metrics(faces: dict) -> dict:
    """``{role: (font_name, cap_height_em, cap_height_was_measured)}`` for an
    already-resolved role→face map.

    The cap height is the LENIENT read, because a caller measuring a box needs
    a number for every run; the third element is what stops that number being
    mistaken for a measurement.
    """
    return {role: (name, cap_height_em(path),
                   cap_height_em_measured(path) is not None)
            for role, (name, path) in faces.items()}


def metrics_provenance(role_metrics: dict) -> dict:
    """The per-role statement of WHICH extents were read from a file.

    Shared by every record that measures text, so two records built from the
    same document cannot describe their own honesty differently.
    """
    estimated = sorted(role for role, (name, _, measured) in
                       role_metrics.items() if not (name and measured))
    return {
        "faces_by_role": {role: {"font": name, "cap_height_em": cap,
                                 "cap_height_measured": measured}
                          for role, (name, cap, measured)
                          in sorted(role_metrics.items())},
        "roles_estimated": estimated,
        "all_roles_measured": not estimated,
    }


def resolve_metric_font(doc_metadata: dict | None) -> tuple[str | None,
                                                            str | None]:
    """(font_name, font_path) of the face the emitter will actually use for
    bold/product-name runs — the confirmed concept face when present and
    loadable, else the registered placeholder bold."""
    return resolve_metric_faces(doc_metadata).get("bold") or (None, None)


__all__ = ["register_font", "registered_font_path", "text_width_mm",
           "text_width_mm_measured", "cap_height_em",
           "cap_height_em_measured", "resolve_metric_faces",
           "resolve_role_metrics", "metrics_provenance",
           "resolve_metric_font"]
