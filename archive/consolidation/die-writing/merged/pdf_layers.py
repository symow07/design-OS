"""[His final goal, 2026-10-05 (transcribed at 32e9aaf), B2: "A PRINT-READY DIELINE ... The glue area marked; bleed and
safe-area lines; dimensions labelled. Each on its own named layer: CUT, CREASE, GLUE, BLEED, SAFE, ARTWORK. It must go to
a printer without being edited."] A drawn PDF's named layers: each part drawn inside its layer's marked content
(``begin`` / ``end``), and the file given its optional content groups after it is written (``apply``) — the guides
(GLUE, BLEED, SAFE, DIMENSIONS) seen on screen and never printed; CUT and CREASE their spot plates."""
from __future__ import annotations

import os

LAYERS = ("ARTWORK", "CUT", "CREASE", "GLUE", "BLEED", "SAFE", "DIMENSIONS")
NON_PRINTING = ("GLUE", "BLEED", "SAFE", "DIMENSIONS")
#: the spot plates the die is cut and creased from, and the screen tint each is shown in
SPOT_PLATES = {"CUT": ("CutContour", (0.0, 1.0, 0.0, 0.0)), "CREASE": ("Crease", (1.0, 0.0, 0.0, 0.0))}
#: the colour the guides are drawn in on screen
GUIDE_HEX = "#00A0E3"


def tag(layer: str) -> str:
    return "OC_" + layer


def begin(c, layer: str) -> None:
    """Open ``layer``'s marked content on the canvas."""
    c._code.append("/OC /%s BDC" % tag(layer))


def end(c) -> None:
    c._code.append("EMC")


def spot(layer: str):
    """The spot colour a die layer is drawn in (reportlab's separation), or None."""
    if layer not in SPOT_PLATES:
        return None
    from reportlab.lib.colors import CMYKColorSep
    name, (cy, ma, ye, k) = SPOT_PLATES[layer]
    return CMYKColorSep(cy, ma, ye, k, spotName=name, density=1.0)


def apply(path: str, layers, pages=None) -> list:
    """Give the written file at ``path`` an optional content group for each of ``layers`` (in LAYERS' order), each page
    in ``pages`` (all, when None) its /Properties for them; the guides never print. Returns the layers given."""
    import fitz
    order = [name for name in LAYERS if name in set(layers)]
    if not order:
        return []
    doc = fitz.open(path)
    xrefs = {name: doc.add_ocg(name, on=True) for name in order}
    for name in NON_PRINTING:
        if name in xrefs:
            doc.xref_set_key(xrefs[name], "Usage", "<</Print <</PrintState /OFF>> /View <</ViewState /ON>>>>")
    props = "<<%s>>" % " ".join("/%s %d 0 R" % (tag(n), x) for n, x in xrefs.items())
    for pno in range(doc.page_count) if pages is None else pages:
        doc.xref_set_key(doc[pno].xref, "Resources/Properties", props)
    guides = [xrefs[n] for n in NON_PRINTING if n in xrefs]
    if guides:
        doc.xref_set_key(doc.pdf_catalog(), "OCProperties/D/AS", "[<</Event /Print /OCGs [%s] /Category [/Print]>>]"
                         % " ".join("%d 0 R" % x for x in guides))
    tmp = path + ".layers"
    doc.save(tmp, garbage=0, deflate=True)
    doc.close()
    os.replace(tmp, path)
    return order


def layers_of(path: str) -> dict:
    """``{layer name: {"prints": bool}}`` as the written file declares them."""
    import fitz
    doc = fitz.open(path)
    out = {}
    for xref, info in doc.get_ocgs().items():
        usage = doc.xref_get_key(xref, "Usage")[1] or ""
        out[info["name"]] = {"prints": "/PrintState/OFF" not in usage.replace(" ", "")}
    return out
