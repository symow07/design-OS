"""[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (6): "SEE THE DESIGN ON THE PAGE: show each drawing (outside,
inside, lid, tray, back label, plates) large, with click-to-enlarge, zoom and pan, so I never need to open the file to
see it."] The design's drawings for the page's viewer (static/js/viewer.js), for every kind of design: each page of its
drawing — the outside, the inside, each finish plate, each artwork piece — and each named part of its first page
(``apps.ire.views_of``), rendered from the drawing itself at the size asked, sharp enough to zoom into, kept once made."""
from __future__ import annotations

import hashlib
import os
import re
import threading

#: PyMuPDF reads one drawing at a time in a process: its own documentation does not support it on several threads at
#: once, and the site answers on several — so the views are made with the drawing (``prepare``, in the pipeline's own
#: thread) and the page only reads what was made; a view made on request (a design drawn before) waits its turn here
_ONE_AT_A_TIME = threading.Lock()

#: the widths a view is rendered at: beside the page, large on it, and enlarged for zooming
THUMB_PX, MAIN_PX, LARGE_PX = 320, 1600, 3600
#: a plate's page says so in its own label (apps/ire/emitters/pdf_ai.py ``_draw_finish_plates``)
PLATE = re.compile(r"FINISH PLATE (\S+) - (\S+)")


def drawing_file(output):
    """The drawing's own file (a PDF): the design .ai (PDF-compatible) where it was made, else its print PDF."""
    for field in ("design_preview_ai", "production_pdf"):
        f = getattr(output, field, None)
        if f and f.name and os.path.exists(f.path):
            return f.path
    return None


def page_words(output, n: int, text: str) -> str:
    """What page ``n`` of the drawing is, in words."""
    m = PLATE.search(text or "")
    if m:
        return "The %s plate (%s)" % (m.group(1).replace("_", " ").lower(), m.group(2).lower())
    spec = output.spec_sheet or {}
    if spec.get("backend") == "artwork":
        formats = (spec.get("artwork_record/1.0") or {}).get("formats") or []
        return "The presentation sheet" if n == 1 else (formats[n - 2].get("label") if n - 2 < len(formats)
                                                        and formats[n - 2].get("label") else "Piece %d" % (n - 1))
    if n == 1:
        return "The outside" if not spec.get("container_reconstruction") else "The design"
    if n == 2 and spec.get("inside_print/1.0"):
        return "The inside"
    return "Page %d" % n


def _fingerprint(path: str) -> str:
    """The drawing's own file named by its path, size and time — never read whole to name it."""
    st = os.stat(path)
    return hashlib.sha256(repr((path, st.st_size, st.st_mtime_ns)).encode()).hexdigest()[:16]


def _listed(output, path: str) -> list:
    """``[(key, words, page, box)]`` — every page of the drawing and each named part of its first, read from the drawing
    itself (PyMuPDF, one at a time); [] where its bytes do not open."""
    with _ONE_AT_A_TIME:
        pdf = _opened(path)
        if pdf is None:
            return []
        out = []
        with pdf:
            for n in range(1, len(pdf) + 1):
                out.append(("page-%d" % n, page_words(output, n, pdf[n - 1].get_text()), n, None))
                if n == 1:
                    for sec in ((output.spec_sheet or {}).get("drawing_views/1.0") or {}).get("sections") or []:
                        out.append((sec["key"], sec["words"], sec.get("page", 1), sec["box_mm"]))
        return out


def prepare(task, output) -> None:
    """[His goal of 2026-10-13, (6).] The drawing's views made with the drawing, in the pipeline's own thread: the list
    kept on its record (``drawing_views/1.0`` "views", with the drawing's fingerprint) and every view's picture at each
    size the page asks — so the page only reads files, never the drawing itself. Nothing where there is no drawing."""
    path = drawing_file(output)
    if path is None:
        return
    listed = _listed(output, path)
    for _key, _words, page, box in listed:
        for width in (THUMB_PX, MAIN_PX):           # the enlarged one is made when he first enlarges it
            picture(task, page, width, box, output=output)
    spec = dict(output.spec_sheet or {})
    record = dict(spec.get("drawing_views/1.0") or {"schema": "drawing_views/1.0", "sections": []})
    record.update(views=[{"key": k, "words": w, "page": p, "box_mm": b} for k, w, p, b in listed],
                  drawing=_fingerprint(path))
    spec["drawing_views/1.0"] = record
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])


def views_for(task) -> list:
    """``[{"key", "words", "url", "thumb", "large"}]`` — every page of the drawing and each named part of its first: as
    made with the drawing (``prepare``), else read from it now (a design drawn before)."""
    output = task.current_output()
    if output is None:
        return []
    path = drawing_file(output)
    if path is None:
        return []
    base = "/api/tasks/%d/drawing/" % task.pk
    record = (output.spec_sheet or {}).get("drawing_views/1.0") or {}
    if record.get("views") is not None and record.get("drawing") == _fingerprint(path):
        listed = [(v["key"], v["words"], v["page"], v["box_mm"]) for v in record["views"]]
    else:
        listed = _listed(output, path)       # a drawing that does not open shows nothing here; its files still say it
    return [_view(base, key, words, page, box) for key, words, page, box in listed]


def _opened(path: str):
    """The drawing opened as a PDF, or None where its bytes are not one (a file still being written, a stand-in)."""
    import fitz
    try:
        pdf = fitz.open(path, filetype="pdf")
    except (fitz.FileDataError, RuntimeError, ValueError):
        return None
    if pdf.page_count < 1:
        pdf.close()
        return None
    return pdf


def _view(base, key, words, page, box):
    q = ("&box=" + ",".join("%.2f" % v for v in box)) if box else ""
    url = "%s%d.png?w=%%d%s" % (base, page, q)
    return {"key": key, "words": words, "url": url % MAIN_PX, "thumb": url % THUMB_PX, "large": url % LARGE_PX}


def picture(task, page: int, width: int, box=None, output=None) -> str | None:
    """The path of page ``page`` of the drawing — or the part of it in ``box`` (mm) — rendered ``width`` px wide, made
    once and kept beside the drawing (``prepare`` makes them with it); None where the design has no drawing or no such
    page."""
    from django.conf import settings
    output = output if output is not None else task.current_output()
    path = drawing_file(output) if output is not None else None
    if path is None:
        return None
    width = max(64, min(int(width), 6000))
    tag = hashlib.sha256(repr((int(page), width, list(box) if box else None)).encode()).hexdigest()[:12]
    folder = os.path.join(settings.MEDIA_ROOT, "drawing_views")
    os.makedirs(folder, exist_ok=True)
    kept = os.path.join(folder, "task_%d_%s_%s.png" % (task.pk, _fingerprint(path), tag))
    if os.path.exists(kept):
        return kept
    with _ONE_AT_A_TIME:
        return _render(path, int(page), width, box, kept)


def _render(path: str, page: int, width: int, box, kept: str) -> str | None:
    import fitz
    if os.path.exists(kept):
        return kept
    pdf = _opened(path)
    if pdf is None:
        return None
    with pdf:
        if not 1 <= page <= len(pdf):
            return None
        pg = pdf[page - 1]
        k = 72.0 / 25.4
        clip = fitz.Rect(box[0] * k, box[1] * k, box[2] * k, box[3] * k) & pg.rect if box else pg.rect
        if clip.is_empty:
            return None
        zoom = width / clip.width
        pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False).save(kept)
    return kept
