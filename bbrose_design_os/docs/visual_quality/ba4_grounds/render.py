"""§BA-4 — the mark at TRUE SCALE on every ground it is actually composed on.

Sanctioned explicitly by the tranche brief: "a rendered comparison at true
scale ... is a legitimate deliverable of this tranche and it is not a §AE2(c)
decision to produce one."

WHY THIS SCRIPT IS IN THE REPOSITORY AND NOT IN /tmp. Without it the panels
are unfalsifiable claims about what the emitter produces. With it, anyone can
re-run the measurement and watch the printed grounds either match README.md's
table or contradict it. A picture that cannot be re-derived is a drawing.

Each panel is a CROP OF A REAL EMITTED .ai -- the same file the repository
would ship -- rasterised and cut around the mark plus one cap height. Nothing
is re-drawn for the picture, so a panel cannot flatter the artefact.

The one exception is the ``pure_white`` panel, and the exception is about the
DOCUMENT, not the file. ``panel1_pure_white_DECLARED.ai`` is a real emitted
file like the other three; what is synthetic is the document behind it, which
no composer produces. It is built by deleting every node except the mark from
a real document, so the mark's own bytes are identical across panels and the
ground is the only variable. The emitter is honest in all four cases; it is
the INPUT to it that panel 1 fabricates, on purpose, because the declaration
under audit describes a state nothing composes. (This paragraph said "has no
artefact" until 2026-08-22. That was false and the file on disk refutes it —
the README had already been corrected and this docstring had not, which is the
stale-body pattern this tranche kept finding in its own work.)

The four states come from the SAME fixture the §AU3 tests use, so the picture
and the test cannot silently disagree about what the composer emits. That is
a shared FIXTURE, not a shared vocabulary: this file has already drifted from
the test module's naming once (see ``crop_geometry``), so the guarantee is
narrower than "cannot drift apart" and is stated at its real width.

Usage:  venv/bin/python docs/visual_quality/ba4_grounds/render.py [outdir]
Requires PyMuPDF. The repo's own pdf_to_png uses sips, which rasterises at
72 dpi only and cannot produce a true-scale crop.
"""
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT = sys.argv[1] if len(sys.argv) > 1 else HERE
DPI = 600

sys.path.insert(0, ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django  # noqa: E402

django.setup()

import fitz  # noqa: E402

sys.path.insert(0, os.path.join(ROOT, "apps/ire/tests"))
from apps.ire.container_brand_usage import (  # noqa: E402
    _contains, _ink_box, evaluate_brand_usage,
)
from apps.ire.emitters.pdf_ai import emit_pdf_ai  # noqa: E402
from apps.ire.graph import Document, Group  # noqa: E402
from test_au3_brand_usage import (  # noqa: E402
    LIVE_FRONT_GROUND, _ground_node, _live_front,
)

os.makedirs(OUT, exist_ok=True)


def crop_geometry():
    """The mark's box and cap height, taken from THE GATE'S OWN RECORD.

    Not measured here and not hard-coded here. The crop is the mark plus ONE
    cap height on every side, which is also §AU3's clear-space rule -- so the
    panel shows exactly the region the rule is about.

    The ``background`` argument is INERT here -- only ``placed_mm`` and
    ``logo_cap_height_mm`` are read and neither depends on it. It said
    ``"motif_field"`` until the §AE6(a) audit found it, which is the spelling
    the test module repudiates in bold at its own definition of
    ``LIVE_FRONT_GROUND``. Inert or not, a shipped script that reproduces the
    deliverable may not use the vocabulary the deliverable exists to retire.
    """
    rec = evaluate_brand_usage(_live_front(motif=True),
                               background=LIVE_FRONT_GROUND)
    place = rec["placements"][0]
    mark = tuple(place["placed_mm"])
    cap = place["logo_cap_height_mm"]
    return mark, cap, (mark[0] - cap, mark[1] - cap,
                       mark[2] + 2 * cap, mark[3] + 2 * cap)


MARK, CAP, (CX0, CY0, CW, CH) = crop_geometry()


def hexof(node):
    fill = getattr(node, "fill", None)
    color = getattr(fill, "color", None) if fill is not None else None
    if color is None:
        return None
    return "#%02X%02X%02X" % (round(color.r * 255), round(color.g * 255),
                              round(color.b * 255))


def ground_of(doc):
    """The last opaque filled node in document order, before the mark, whose
    box contains the mark's. The flat emitter paints in document order, so
    that is the colour the mark's ink lands on.

    CORRECTED 2026-08-22 BY THE §AE6(a) AUDIT, AND THE CLAIM IS NOW TRUE
    RATHER THAN DELETED. This docstring said the function was "deliberately a
    second implementation: if they ever disagree, one of them is wrong and the
    disagreement is visible rather than assumed away." It was a line-for-line
    copy of ``_ground_node`` with a single local renamed, and NOTHING COMPARED
    THEM -- so no disagreement could ever have surfaced. A cross-check that
    cannot fire is worse than none: it spends the reader's trust and returns
    nothing, which is the §AA failure in miniature.

    The local walk is kept, and its answer is now actually checked against
    ``_ground_node``'s on every call. A disagreement RAISES, here, in the
    script that draws the picture -- rather than being settled silently in
    favour of whichever implementation happened to run last.
    """
    order = [n for n, _ in doc.walk()]
    logo = next(n for n in order if str(getattr(n, "name", "")) == "logo")
    lbox = _ink_box(logo)
    under = None
    for node in order:
        if node is logo:
            break
        fill = getattr(node, "fill", None)
        if fill is None or getattr(fill, "opacity", 1.0) < 1.0:
            continue
        box = _ink_box(node)
        if box is not None and _contains(box, lbox):
            under = node
    theirs = _ground_node(doc)
    if under is not theirs:
        raise AssertionError(
            "GROUND_DISAGREEMENT: render.py and test_au3_brand_usage.py"
            "::_ground_node do not agree about what the mark is printed on. "
            "render.py says %r, _ground_node says %r. One of them is wrong "
            "and the picture must not be drawn until it is known which."
            % (getattr(under, "name", under), getattr(theirs, "name", theirs)))
    return under


def mark_only(doc):
    """The same document with everything but the mark deleted -- the state
    ``background="pure_white"`` declares, which no composer emits."""
    order = [n for n, _ in doc.walk()]
    logo = next(n for n in order if str(getattr(n, "name", "")) == "logo")
    return Document(page_w=doc.page_w, page_h=doc.page_h, title="pure_white",
                    root=Group(name="Artwork", role="artwork",
                               children=[logo]))


def crop(doc, stem):
    ai = os.path.join(OUT, stem + ".ai")
    emit_pdf_ai(doc, ai)
    doc_pdf = fitz.open(ai)
    page = doc_pdf[0]
    zoom = DPI / 72.0
    # mm -> points; the emitter's page is doc.page_w/h mm with the graph's
    # y-DOWN origin at top-left, which is fitz's convention too.
    rect = fitz.Rect(CX0 / 25.4 * 72, CY0 / 25.4 * 72,
                     (CX0 + CW) / 25.4 * 72, (CY0 + CH) / 25.4 * 72)
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect,
                          alpha=False)
    png = os.path.join(OUT, stem + ".png")
    pix.save(png)
    doc_pdf.close()
    return png


PANELS = []


def add(slug, label, doc, note=""):
    node = ground_of(doc)
    gname = str(getattr(node, "name", "-")) if node is not None else "NOTHING"
    ghex = hexof(node) if node is not None else "-"
    try:
        png = crop(doc, slug)
    except Exception as exc:  # a REFUSAL is a result, not a crash
        PANELS.append((label, gname, ghex, None,
                       f"{type(exc).__name__}: {exc}"))
        return
    PANELS.append((label, gname, ghex, png, note))


live = _live_front(motif=True)
bare = _live_front(motif=False)
direct = _live_front(hierarchy=[{"text": "PLACEHOLDER-BRAND", "rel": 1.0,
                                 "kind": "product_name"}], motif=False)
future = _live_front(hierarchy=[
    {"text": "PLACEHOLDER-BRAND", "rel": 1.0, "kind": "product_name"},
    {"text": "⟪PROVISIONAL⟫ PLACEHOLDER-SUPPORT", "rel": 0.7,
     "kind": "descriptor"}], motif=True)

add("panel1_pure_white_DECLARED",
    "1  pure_white  — DECLARED, composed by nothing", mark_only(live),
    "what the declaration asserts")
add("panel2_now_no_motif", "2  NOW  — no motif", bare,
    "the fixture's state")
add("panel3_now_motif_LIVE", "3  NOW  — motif field, THE LIVE CALL SITE",
    live, "production, non-dropper branch")
add("panel4_future_direct_print", "4  FUTURE  — direct print, no motif",
    direct, "no decoration field emitted")
add("panel5_future_direct_print_motif",
    "5  FUTURE  — direct print + motif", future, "carries PROVISIONAL copy")

print(f"\ncrop = mark + 1.0 cap height = {CW:.4f} x {CH:.4f} mm  @ {DPI} dpi")
print(f"mark = {MARK[2]:.3f} x {MARK[3]:.3f} mm   cap = {CAP:.4f} mm")
print("=" * 74)
for label, gname, ghex, png, note in PANELS:
    state = "ok " if png else "REFUSED"
    print(f"{state} {label:46s} ground={gname:18s} {str(ghex):9s} {note}")

# ---- the true-scale sheet -------------------------------------------------
import reportlab.lib.pagesizes as ps  # noqa: E402
from reportlab.lib.units import mm as MM  # noqa: E402
from reportlab.pdfgen import canvas as rc  # noqa: E402

sheet = os.path.join(OUT, "mark_on_every_ground_TRUE_SCALE.pdf")
c = rc.Canvas(sheet, pagesize=ps.A4)
W, H = ps.A4
c.setFont("Helvetica-Bold", 10)
c.drawString(20 * MM, H - 20 * MM,
             "The mark at TRUE SCALE on every ground it is composed on")
c.setFont("Helvetica", 7)
c.drawString(20 * MM, H - 25 * MM,
             "Print at 100%%. Each panel is %.3f x %.3f mm: the mark "
             "(%.3f x %.3f mm) plus one cap height (%.4f mm)."
             % (CW, CH, MARK[2], MARK[3], CAP))
c.drawString(20 * MM, H - 29 * MM,
             "Panels are CROPS OF REAL EMITTED .ai FILES, not redrawings. "
             "Only panel 1 is synthetic - it is what the declaration claims.")
y = H - 45 * MM
for label, gname, ghex, png, note in PANELS:
    c.setFont("Helvetica-Bold", 8)
    c.drawString(20 * MM, y, label)
    c.setFont("Helvetica", 7)
    c.drawString(20 * MM, y - 4 * MM,
                 f"ground under the mark: {gname}   {ghex}")
    if png:
        c.drawImage(png, 20 * MM, y - 6 * MM - CH * MM,
                    width=CW * MM, height=CH * MM)
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.setLineWidth(0.2)
        c.rect(20 * MM, y - 6 * MM - CH * MM, CW * MM, CH * MM)
        c.setFont("Helvetica-Oblique", 6.5)
        c.drawString(20 * MM + CW * MM + 6 * MM, y - 6 * MM - CH / 2 * MM,
                     note)
        y -= (CH + 20) * MM
    else:
        c.setFont("Helvetica-Bold", 7)
        c.drawString(20 * MM, y - 8 * MM,
                     "NO PANEL — THE EMITTER REFUSED TO WRITE THIS ARTEFACT")
        c.setFont("Helvetica-Oblique", 6.5)
        yy = y - 12 * MM
        for chunk in textwrap.wrap(note, 118):
            c.drawString(20 * MM, yy, chunk)
            yy -= 3.4 * MM
        y = yy - 8 * MM
c.showPage()
c.save()
print("\nsheet ->", sheet)
