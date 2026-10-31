"""THE ONE ACT THAT THROWS THE SWITCH — the owner's approved logo trace placed on file with its approval record.

THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
testing"): "When I approve the logo trace, switch the mark to it so gold foil can print." The switch is built
(``apps/ire/brand_mark.py``); this tool writes the two files it reads — ``bbrose-logo.svg`` and ``approval.json`` —
from the SVG he approves and his own words, and nothing else.

PLACING IS LIVE THE MOMENT THE FILES ARE WRITTEN. ``brand_mark.approved_master`` reads ``docs/brand/mark/`` afresh on
EVERY composition, in EVERY process — the web server, every worker, every exploration — so the instant this tool
writes into the repository's ``docs/brand/mark/``, every running process draws the vector mark at its next
composition. No restart and no commit is needed for that to happen: the data-only commit only records it, and
removing the two files undoes it. Hence two modes:

  REHEARSAL (the default): every step below, the files written into ``--out`` — which must lie OUTSIDE the git root
  and outside any ``media/`` folder, where nothing live reads them.

      venv/bin/python tools/brand_mark_place.py --out <a folder outside the repository> --svg <the SVG he approved> \\
          --words "<his words, verbatim>" --register OWNER_BLOCKER_CLEARANCE.md:<line> --date YYYY-MM-DD \\
          --source-png media/brand/bbrose-logo.png --tracer "potrace 1.16" --tracer-settings "<as recorded>"

  PLACE: ``--place`` instead of ``--out`` writes into the live ``docs/brand/mark/``. Refused by name while a master or
  an approval record is already on file there, unless ``--replace <sha256 of the master on file>`` names exactly it.

WHICH FILE IS HIS TO NAME. Two traces are on record (the trace, and the trace with the ® redrawn as a circle); the tool
takes the one he approves and chooses nothing.

IN ORDER, refusing BY NAME — writing nothing — at the first step that does not hold:
  1. the arguments: his words must stand VERBATIM (line wrapping, runs of spaces and blockquote markers aside) in the
     register paragraph that starts at ``--register FILE:LINE``; ``--date`` a real calendar date written YYYY-MM-DD;
     a tracer named; the SVG and the source PNG readable;
  2. the SVG through the SAME strict grammar the switch reads it with (``brand_mark.read_master``);
  3. the crop to its INK bounds, rewriting ONLY the root element's viewBox, width and height — every path's bytes
     identical — found by PARSING the root's start tag; the crop is read again and must give the same outlines, and
     its new viewBox must BE the ink;
  4. the match, through the real path — and the bar is THIS TOOL'S OWN, stated as such: the mark as the emitter draws
     it (``emit_pdf_ai``, which expands it) rendered by MuPDF, against MuPDF's own rendering of the same SVG, at the
     source PNG's pixel size — both rasters of the same size and no pixel disagreeing by more than half. Its FORM is
     rule 2 of the trace's SELECTION_RULE.txt (sealed 2026-09-25), which holds the TRACE against the PNG; here it
     holds the EMITTER against MuPDF, so it proves the switch draws what he approved. The master against the source
     PNG is measured and recorded beside it and is not a bar: the drawing he approves, not the PNG, is the mark (a ®
     redrawn as a circle at his word differs from the PNG's by design);
  5. the two files are written.

MuPDF (PyMuPDF) is a development dependency (requirements-dev.txt), as this tool is a development tool: the switch
itself reads the record and never needs it.
"""
from __future__ import annotations

import argparse
import datetime
import errno
import hashlib
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from xml.parsers import expat

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CRITERION = ("THE TOOL'S OWN BAR: the mark as the emitter draws it (emit_pdf_ai, rendered by MuPDF) against MuPDF's "
             "rendering of the same SVG, at the source PNG's pixel size, both rasters the same size and no pixel "
             "disagreeing by more than half. Its form is the last clause of rule 2 of the trace's SELECTION_RULE.txt "
             "(sealed 2026-09-25: no pixel at the PNG's own size disagreeing with the PNG's coverage by more than "
             "half), which holds the TRACE against the PNG; this holds the EMITTER against MuPDF")
PLACED_BY = "tools/brand_mark_place.py"
_NUM = r"[-+]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)"


class PlacementRefused(ValueError):
    """Nothing was written: ``reason`` names the step that did not hold."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _errno_name(exc: OSError) -> str:
    return errno.errorcode.get(exc.errno, str(exc.errno)) if exc.errno is not None else type(exc).__name__


def git_root(start: str = _HERE) -> str:
    """The repository's root: the nearest folder at or above ``start`` holding ``.git`` (a worktree's is a file). With
    none above it, the folder above ``start`` — the project's own parent, so a rehearsal still lands outside it."""
    here = os.path.realpath(start)
    while True:
        if os.path.exists(os.path.join(here, ".git")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            return os.path.dirname(os.path.realpath(start))
        here = parent


def _inside(path: str, root: str) -> bool:
    path, root = os.path.realpath(path), os.path.realpath(root)
    return os.path.commonpath([path, root]) == root


def _read(path: str, what: str) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError as exc:
        raise PlacementRefused(f"{what}_NOT_FOUND", path) from exc
    except OSError as exc:
        raise PlacementRefused(f"{what}_UNREADABLE", f"{path}: {_errno_name(exc)}") from exc


# ---------------------------------------------------------------------------------------------------------------------
# his words, in the register
# ---------------------------------------------------------------------------------------------------------------------

def register_block(register: str, register_root: str) -> str:
    """The paragraph of the register that starts at ``FILE:LINE`` — its lines up to the first blank one, a line that
    is blank once its blockquote markers are off (a quoted paragraph break, ``>``) counting as blank — with each line's
    blockquote markers taken off and every run of whitespace made one space."""
    m = re.fullmatch(r"(.+\.md):([0-9]+)", register.strip(), re.ASCII)
    if m is None:
        raise PlacementRefused("NO_REGISTER_LINE", f"--register {register!r} is not FILE.md:LINE")
    path = m.group(1) if os.path.isabs(m.group(1)) else os.path.join(register_root, m.group(1))
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError as exc:
        raise PlacementRefused("REGISTER_NOT_FOUND", path) from exc
    except UnicodeDecodeError as exc:
        raise PlacementRefused("REGISTER_UNREADABLE", f"{path} is not UTF-8 ({exc.reason})") from exc
    except OSError as exc:
        raise PlacementRefused("REGISTER_UNREADABLE", f"{path}: {_errno_name(exc)}") from exc
    first = int(m.group(2))

    def unquoted(text):
        return re.sub(r"^\s*(?:>\s?)+", "", text)

    if first < 1 or first > len(lines) or not unquoted(lines[first - 1]).strip():
        raise PlacementRefused("REGISTER_LINE_NOT_FOUND",
                               f"{register}: the register has {len(lines)} lines and no paragraph starts there")
    block = []
    for text in lines[first - 1:]:
        if not unquoted(text).strip():
            break
        block.append(unquoted(text))
    return " ".join(" ".join(block).split())


def check_words(words: str, register: str, register_root: str) -> None:
    if words is None or not words.strip():
        raise PlacementRefused("NO_OWNER_WORDS", "--words is his approval, verbatim, and it is empty")
    if register is None:
        raise PlacementRefused("NO_REGISTER_LINE", "--register FILE.md:LINE is where his words are transcribed")
    if " ".join(words.split()) not in register_block(register, register_root):
        raise PlacementRefused("WORDS_NOT_IN_REGISTER",
                               f"the words given do not stand verbatim in the paragraph at {register}")


def check_date(date: str) -> str:
    if date is None or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date.strip(), re.ASCII):
        raise PlacementRefused("BAD_DATE", f"--date {date!r} is not written YYYY-MM-DD")
    try:
        datetime.date.fromisoformat(date.strip())
    except ValueError as exc:
        raise PlacementRefused("BAD_DATE", f"--date {date!r} is not a calendar date ({exc})") from exc
    return date.strip()


# ---------------------------------------------------------------------------------------------------------------------
# the SVG's root element, parsed
# ---------------------------------------------------------------------------------------------------------------------

def root_tag_span(data: bytes) -> tuple:
    """``(start, end)`` byte offsets of the root element's START TAG, found by PARSING the file (expat's byte index of
    the first start-element event) — never the first ``<svg`` the raw bytes happen to hold."""
    parser = expat.ParserCreate()
    found: list = []

    def start(_name, _attrs):
        if not found:
            found.append(parser.CurrentByteIndex)

    parser.StartElementHandler = start
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise PlacementRefused("NOT_SVG", f"the file does not parse ({exc})") from exc
    if not found:
        raise PlacementRefused("NOT_SVG", "no root element")
    quote = None
    for i in range(found[0], len(data)):
        ch = data[i:i + 1]
        if quote is not None:
            if ch == quote:
                quote = None
        elif ch in (b'"', b"'"):
            quote = ch
        elif ch == b">":
            return found[0], i + 1
    raise PlacementRefused("NOT_SVG", "the root's start tag does not close")


def _root_attrs(data: bytes) -> dict:
    try:
        return dict(ET.fromstring(data).attrib)
    except ET.ParseError as exc:
        raise PlacementRefused("NOT_SVG", f"the file does not parse ({exc})") from exc


def viewbox(data: bytes) -> tuple:
    """The root's viewBox, read from the parsed root, as four finite floats with a positive width and height."""
    value = _root_attrs(data).get("viewBox")
    if value is None:
        raise PlacementRefused("NO_VIEWBOX", "the root carries no viewBox")
    parts = re.split(r"[\s,]+", value.strip(), flags=re.ASCII)
    if len(parts) != 4 or not all(re.fullmatch(_NUM, p, re.ASCII) for p in parts):
        raise PlacementRefused("NO_VIEWBOX", f"viewBox={value!r}")
    vx, vy, vw, vh = (float(p) for p in parts)
    if vw <= 0 or vh <= 0:
        raise PlacementRefused("NO_VIEWBOX", f"viewBox={value!r} encloses nothing")
    return vx, vy, vw, vh


def _set_attr(tag: bytes, name: bytes, value: str) -> bytes:
    pattern = re.compile(rb"(\s" + name + rb"\s*=\s*)([\"'])(.*?)\2", re.S)
    if pattern.search(tag) is None:
        closing = b"/>" if tag.endswith(b"/>") else b">"
        return tag[:-len(closing)] + b" " + name + b'="' + value.encode("ascii") + b'"' + closing
    return pattern.sub(lambda m: m.group(1) + m.group(2) + value.encode("ascii") + m.group(2), tag, count=1)


def crop_to_ink(data: bytes, bounds: tuple) -> bytes:
    """``data`` with ONLY the root's viewBox, width and height rewritten to the ink ``bounds``: width and height keep
    their unit and their scale to the viewBox; every other byte is the input's."""
    start, end = root_tag_span(data)
    tag = data[start:end]
    attrs = _root_attrs(data)
    _vx, _vy, vw, vh = viewbox(data)
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    new = _set_attr(tag, b"viewBox", "%.6f %.6f %.6f %.6f" % (x0, y0, w, h))
    for name, extent, span in (("width", w, vw), ("height", h, vh)):
        value = attrs.get(name)
        if value is None:
            continue
        num = re.fullmatch(r"\s*(" + _NUM + r")\s*([a-z%]*)\s*", value, re.ASCII)
        if num is None:
            raise PlacementRefused("UNREADABLE_SIZE", f"{name}={value!r}")
        new = _set_attr(new, name.encode("ascii"), "%.6f%s" % (extent * float(num.group(1)) / span, num.group(2)))
    return data[:start] + new + data[end:]


# ---------------------------------------------------------------------------------------------------------------------
# the match
# ---------------------------------------------------------------------------------------------------------------------

def _coverage_of_pdf(pdf_path: str, zoom: float):
    import fitz
    import numpy as np
    with fitz.open(pdf_path) as pdf:
        pix = pdf[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        return arr[..., pix.n - 1].astype(float) / 255.0


def _svg_page_pt(svg: bytes) -> tuple:
    """The page MuPDF lays the SVG on, in points — its own reading of width, height and their units."""
    import fitz
    with fitz.open(stream=svg, filetype="svg") as svg_doc:
        return svg_doc[0].rect.width, svg_doc[0].rect.height


def _coverage_of_svg(svg: bytes, zoom: float):
    import fitz
    import numpy as np
    with fitz.open(stream=svg, filetype="svg") as svg_doc:
        pix = svg_doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=True)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        return arr[..., pix.n - 1].astype(float) / 255.0


def compare(a, b, what: str) -> dict:
    """``a`` against ``b``, two coverage rasters (0..1) of the SAME size — rasters of different sizes are refused by
    name, never cropped to a common size (that would compare two drawings at different scales and call it a match)."""
    if a.shape != b.shape:
        raise PlacementRefused("RASTER_SIZE_MISMATCH", "%s: %dx%d px against %dx%d px"
                               % (what, a.shape[1], a.shape[0], b.shape[1], b.shape[0]))
    diff = abs(a - b)
    inked_a, inked_b = a > 0.5, b > 0.5
    union = int((inked_a | inked_b).sum())
    return {"raster_px": [int(a.shape[1]), int(a.shape[0])], "px_disagreeing_over_half": int((diff > 0.5).sum()),
            "mean_coverage_diff": round(float(diff.mean()), 6),
            "iou": None if union == 0 else round(float((inked_a & inked_b).sum()) / union, 6)}


def match(master, svg: bytes, source_png: str) -> dict:
    """The emitter's drawing of ``master`` against MuPDF's rendering of ``svg`` — the bar — and against the source
    PNG — recorded. Both at the source PNG's pixel size."""
    import numpy as np
    from PIL import Image as PILImage
    from PIL import UnidentifiedImageError

    from apps.ire import brand_mark
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.graph import Document, Group

    try:
        with PILImage.open(source_png) as im:
            png = im.convert("RGBA")
    except FileNotFoundError as exc:
        raise PlacementRefused("SOURCE_PNG_NOT_FOUND", source_png) from exc
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise PlacementRefused("SOURCE_PNG_UNREADABLE", f"{source_png}: {type(exc).__name__}: {exc}") from exc
    png_w, _png_h = png.size
    png_cov = np.asarray(png.getchannel("A"), dtype=float) / 255.0
    vx, vy, vw, vh = viewbox(svg)
    page_w_pt, page_h_pt = _svg_page_pt(svg)                 # MuPDF's own page for the SVG, units read by it
    kx, ky = page_w_pt / vw, page_h_pt / vh                   # points per user unit
    if abs(kx - ky) > 1e-9 * max(kx, ky):
        raise PlacementRefused("VIEWBOX_ASPECT", "the SVG's page and its viewBox differ in aspect (%.6f / %.6f pt "
                               "per unit): the tool does not letterbox" % (kx, ky))
    zoom = png_w / page_w_pt                                   # pixels per point: the PNG's own size
    mm_per_pt = 25.4 / 72.0
    x0, y0, x1, y1 = master.bounds
    mark = brand_mark.mark_node("logo", master, (x0 - vx) * kx * mm_per_pt, (y0 - vy) * kx * mm_per_pt,
                                (x1 - x0) * kx * mm_per_pt, (y1 - y0) * kx * mm_per_pt)
    doc = Document(page_w=page_w_pt * mm_per_pt, page_h=page_h_pt * mm_per_pt, title="brand mark match",
                   root=Group(name="mark-match", children=[mark]))
    with tempfile.TemporaryDirectory(prefix="bbrose_brand_mark_place_") as tmp:
        pdf = emit_pdf_ai(doc, os.path.join(tmp, "mark.pdf"))
        emitter = _coverage_of_pdf(pdf, zoom)
    mupdf = _coverage_of_svg(svg, zoom)
    bar = compare(emitter, mupdf, "the emitter's drawing against MuPDF's rendering of the SVG")
    bar.update(passed=bar["px_disagreeing_over_half"] == 0, criterion=CRITERION,
               measured_by="emit_pdf_ai (the mark expanded by apps/ire/brand_mark.py) rendered by MuPDF, against "
                           "MuPDF's rendering of the SVG, both at the source PNG's pixel size")
    try:
        source = compare(emitter, png_cov, "the emitter's drawing against the source PNG")
    except PlacementRefused as exc:
        # recorded, never a bar — so a size mismatch here is SAID, and no number is made up by cropping
        source = {"compared": False, "reason": exc.reason, "detail": exc.detail}
    source.update(bar=None, note="recorded, never a bar: the approved drawing, not the PNG, is the mark")
    return {"emitter_vs_mupdf": bar, "master_vs_source_png": source, "zoom_px_per_pt": round(zoom, 6)}


# ---------------------------------------------------------------------------------------------------------------------
# the act
# ---------------------------------------------------------------------------------------------------------------------

def _on_file_sha(live: str, master_file: str, approval_file: str):
    """The sha256 of the master on file in ``live`` — its bytes, or, with no master but a record, the sha256 the record
    names — or None when neither file is there."""
    master_path, record_path = os.path.join(live, master_file), os.path.join(live, approval_file)
    if os.path.lexists(master_path):
        return _sha256(_read(master_path, "MASTER_ON_FILE"))
    if not os.path.lexists(record_path):
        return None
    try:
        with open(record_path, encoding="utf-8") as fh:
            record = json.load(fh)
    except OSError as exc:
        return f"an approval record that does not read ({_errno_name(exc)})"
    except ValueError:
        return "an approval record that does not parse as JSON"
    named = record.get("master_sha256") if isinstance(record, dict) else None
    return "an approval record naming no master" if named is None else str(named)


def place(svg_path: str, *, words: str, register: str, date: str, source_png: str, tracer: str,
          tracer_settings: str, out_dir: str | None = None, place: bool = False, replace: str | None = None,
          register_root: str | None = None, live_root: str | None = None) -> dict:
    """REHEARSE (``out_dir``) or PLACE (``place=True``: the live ``docs/brand/mark/``) the approved SVG and its approval
    record; return the record. Refused (``PlacementRefused``, nothing written) at the first step that does not hold —
    see the module's docstring. ``register_root`` (default: the git root) and ``live_root`` (default: BASE_DIR) exist so
    a test can hold both in a temp folder; the command line never moves them."""
    from apps.ire import brand_mark
    register_root = git_root() if register_root is None else register_root
    live_root = _HERE if live_root is None else live_root
    live = os.path.join(live_root, *brand_mark.MARK_DIR)
    # 0. where the files go
    if place:
        if out_dir is not None:
            raise PlacementRefused("OUT_WITH_PLACE", "--place writes the live docs/brand/mark/; --out is a rehearsal's")
        on_file = _on_file_sha(live, brand_mark.MASTER_FILE, brand_mark.APPROVAL_FILE)
        if on_file is not None and replace is None:
            raise PlacementRefused("ALREADY_PLACED", f"{live} holds {on_file}; --replace <that sha256> to replace it")
        if on_file is not None and replace != on_file:
            raise PlacementRefused("REPLACE_MISMATCH", f"--replace {replace} is not the master on file ({on_file})")
        target = live
    else:
        if replace is not None:
            raise PlacementRefused("REPLACE_WITHOUT_PLACE", "--replace names the master on file that --place replaces")
        if out_dir is None:
            raise PlacementRefused("NO_OUT", "a rehearsal writes into --out; --place writes the live docs/brand/mark/")
        if _inside(out_dir, git_root()):
            raise PlacementRefused("OUT_INSIDE_REPOSITORY", f"{out_dir}: a rehearsal is written outside the git root, "
                                                            "where nothing live reads it")
        target = out_dir
    # media/ — by the path as given, by the path it resolves to, and under the project's own media folder (a link
    # into another tree in a worktree): never written through
    media_link = os.path.join(_HERE, "media")
    if ("media" in os.path.abspath(target).split(os.sep) or "media" in os.path.realpath(target).split(os.sep)
            or (os.path.lexists(media_link) and _inside(target, media_link))):
        raise PlacementRefused("MEDIA_REFUSED", f"{target}: media/ is ignored wholesale (.gitignore:33); the approved "
                                                "master is tracked under docs/brand/mark/")
    # 1. the arguments
    check_words(words, register, register_root)
    date = check_date(date)
    if tracer is None or not tracer.strip():
        raise PlacementRefused("NO_TRACER", "--tracer names the tracer that made the SVG")
    approved = _read(svg_path, "SVG")
    png_sha = _sha256(_read(source_png, "SOURCE_PNG"))
    # 2. the grammar the approval covers
    try:
        master = brand_mark.read_master(approved, path=svg_path)
    except brand_mark.MarkRefused as exc:
        raise PlacementRefused("GRAMMAR", str(exc)) from exc
    # 3. the crop to the ink, read again
    cropped = crop_to_ink(approved, master.bounds)
    try:
        placed = brand_mark.read_master(cropped, path=os.path.join(target, brand_mark.MASTER_FILE))
    except brand_mark.MarkRefused as exc:
        raise PlacementRefused("CROP", str(exc)) from exc
    if placed.subpaths != master.subpaths or placed.bounds != master.bounds:
        raise PlacementRefused("CROP", "the cropped file does not give the approved file's outlines")
    cvx, cvy, cvw, cvh = viewbox(cropped)
    x0, y0, x1, y1 = master.bounds
    if max(abs(cvx - x0), abs(cvy - y0), abs(cvx + cvw - x1), abs(cvy + cvh - y1)) > 1e-5:
        raise PlacementRefused("CROP", f"the new viewBox ({cvx} {cvy} {cvw} {cvh}) is not the ink {master.bounds}")
    # 4. the match, through the real path
    measured = match(master, approved, source_png)
    if not measured["emitter_vs_mupdf"]["passed"]:
        raise PlacementRefused("MATCH", "the emitter's drawing disagrees with MuPDF's rendering of the SVG at %d px "
                               "(%s)" % (measured["emitter_vs_mupdf"]["px_disagreeing_over_half"], CRITERION))
    record = {
        "schema_version": brand_mark.APPROVAL_SCHEMA,
        "ruling": brand_mark.RULING,
        "owner_words": words,
        "register": register.strip(),
        "register_check": "the words stand verbatim in the register block that starts at that line",
        "date": date,
        "approved_file": {"name": os.path.basename(svg_path), "sha256": _sha256(approved), "bytes": len(approved),
                          "viewBox": " ".join("%g" % v for v in viewbox(approved))},
        "master": brand_mark.MASTER_FILE,
        "master_sha256": _sha256(cropped),
        "crop": {"viewBox": " ".join("%g" % v for v in (cvx, cvy, cvw, cvh)),
                 "rewritten": "the root's viewBox, width and height only — every path's data byte-identical"},
        "fill": master.fill,
        "fill_rule": "nonzero",
        "ink_bounds": [round(v, 6) for v in master.bounds],
        "ink_aspect": round((y1 - y0) / (x1 - x0), 6),
        "census": dict(master.census),
        "source_png": {"path": source_png, "sha256": png_sha},
        "tracer": {"name": tracer.strip(), "settings": "" if tracer_settings is None else tracer_settings.strip()},
        "match": measured,
        "placed_by": PLACED_BY,
        "written_as": "PLACED" if place else "REHEARSAL",
    }
    os.makedirs(target, exist_ok=True)
    with open(os.path.join(target, brand_mark.MASTER_FILE), "wb") as fh:
        fh.write(cropped)
    with open(os.path.join(target, brand_mark.APPROVAL_FILE), "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--svg", required=True, help="the SVG the owner approved")
    parser.add_argument("--words", required=True, help="his approval, verbatim, as the register transcribes it")
    parser.add_argument("--register", required=True, help="where his words are transcribed: FILE.md:LINE")
    parser.add_argument("--date", required=True, help="the date of his approval, YYYY-MM-DD")
    parser.add_argument("--source-png", required=True, help="the PNG the SVG was traced from")
    parser.add_argument("--tracer", required=True, help="the tracer that made the SVG")
    parser.add_argument("--tracer-settings", default=None, help="its settings, as recorded")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--out", default=None, help="REHEARSAL: a folder outside the repository")
    where.add_argument("--place", action="store_true", help="PLACE: the live docs/brand/mark/ — takes effect at once")
    parser.add_argument("--replace", default=None, help="with --place: the sha256 of the master on file")
    args = parser.parse_args(argv)
    try:
        record = place(args.svg, words=args.words, register=args.register, date=args.date,
                       source_png=args.source_png, tracer=args.tracer, tracer_settings=args.tracer_settings,
                       out_dir=args.out, place=args.place, replace=args.replace)
    except PlacementRefused as exc:
        print("BRAND_MARK_PLACEMENT_REFUSED %s" % exc)
        return 1
    print("BRAND_MARK_%s master_sha256=%s emitter_vs_mupdf=%s" % (
        record["written_as"], record["master_sha256"], json.dumps(record["match"]["emitter_vs_mupdf"])))
    return 0


if __name__ == "__main__":
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()
    sys.exit(main())
