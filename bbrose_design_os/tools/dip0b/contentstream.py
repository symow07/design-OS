"""Content-stream graphics state: which colourspace painted which path (DIP-0B3).

`get_drawings()` hands back RGB-converted colour with no colourspace, so a path
cannot be mapped to `/Separation /All` from it. This module walks the content
stream (recursing into Form XObjects, honouring `q`/`Q`) and records the fill and
stroke colourspace active at every painting operator, in paint order.

**Alignment is proven, never assumed.** Only when the number of painting
operators equals the number of drawings can a path be mapped to a colourspace by
index. Measured on the pilot, that equality does NOT hold (LP-2018: 7,180
painting operators vs 49,904 drawings), so path-level association is reported as
*unavailable* there and no thin stroke inherits `/All` certainty.

What remains DIRECT in every case is a document/page-level fact: registration ink
exists, and N painting operations used it.
"""
from __future__ import annotations

import re

from . import config as C
from .separation import unescape_pdf_name

# Path-painting operators. `n` paints nothing (clip-only), so it is excluded.
PAINT_OPS = frozenset({"S", "s", "f", "F", "f*", "B", "B*", "b", "b*"})

_TOK = re.compile(rb"/[^\s/\[\]<>(){}%]*|[-+]?\d*\.?\d+|<<|>>|\[|\]|[A-Za-z*'\"]+")
_SEP_NAME = re.compile(r"/Separation\s*/([^\s/\[\]<>()]+)")

REGISTRATION = "All"
MAX_FORM_DEPTH = 8


class _Res:
    """Resource dictionary of a page or a Form XObject.

    Resources are usually an inline dict, so the lookup key is the nested path
    `Resources/ColorSpace/CS0`, not the bare name.
    """

    def __init__(self, doc, xref: int, prefix: str = "Resources"):
        self.doc, self.xref, self.prefix = doc, xref, prefix

    def get(self, path: str):
        key = f"{self.prefix}/{path}" if self.prefix else path
        try:
            return self.doc.xref_get_key(self.xref, key)
        except Exception:  # noqa: BLE001
            return None


def _child_res(doc, xref: int) -> _Res:
    e = doc.xref_get_key(xref, "Resources")
    if e and e[0] == "xref":
        return _Res(doc, int(e[1].split()[0]), "")
    return _Res(doc, xref, "Resources")


def _resolve_colorspace(doc, res: _Res, name: str) -> tuple[str, str] | None:
    """`/CS0` → ('separation', 'All') | ('devicen', …) | ('device', …) | ('other', …)."""
    if name in ("/DeviceRGB", "/DeviceGray", "/DeviceCMYK", "/Pattern"):
        return ("device", name[1:])
    e = res.get(f"ColorSpace/{name[1:]}")
    if not e:
        return None
    if e[0] == "xref":
        try:
            src = doc.xref_object(int(e[1].split()[0]), compressed=True)
        except Exception:  # noqa: BLE001
            return None
    elif e[0] == "array":
        src = e[1]
    else:
        return ("other", str(e[1])[:32])

    m = _SEP_NAME.search(src)
    if m:
        return ("separation", unescape_pdf_name(m.group(1)))
    if "/DeviceN" in src:
        return ("devicen", "DeviceN")
    return ("other", src[:32])


def _walk(doc, data: bytes, res: _Res, out: list, depth: int, seen: frozenset,
          forms_expanded: list) -> None:
    if depth > MAX_FORM_DEPTH:
        return
    fill_cs: tuple | None = None
    stroke_cs: tuple | None = None
    stack: list = []
    operands: list[str] = []

    for m in _TOK.finditer(data):
        tok = m.group().decode("latin-1")
        if not (tok[0].isalpha() or tok[0] in "*'\""):
            operands.append(tok)
            continue

        op = tok
        if op == "q":
            stack.append((fill_cs, stroke_cs))
        elif op == "Q":
            if stack:
                fill_cs, stroke_cs = stack.pop()
        elif op == "cs" and operands:
            fill_cs = _resolve_colorspace(doc, res, operands[-1])
        elif op == "CS" and operands:
            stroke_cs = _resolve_colorspace(doc, res, operands[-1])
        elif op in PAINT_OPS:
            out.append({"op": op, "fill_cs": fill_cs, "stroke_cs": stroke_cs,
                        "depth": depth})
        elif op == "Do" and operands:
            e = res.get(f"XObject/{operands[-1][1:]}")
            if e and e[0] == "xref":
                x = int(e[1].split()[0])
                st = doc.xref_get_key(x, "Subtype")
                if st and st[1] == "/Form" and x not in seen:
                    try:
                        sub = doc.xref_stream(x)
                    except Exception:  # noqa: BLE001
                        sub = None
                    if sub:
                        forms_expanded.append(x)
                        _walk(doc, sub, _child_res(doc, x), out, depth + 1,
                              seen | {x}, forms_expanded)
        operands = []


def _uses(rec: dict, name: str) -> bool:
    for k in ("fill_cs", "stroke_cs"):
        cs = rec[k]
        if cs and cs[0] == "separation" and cs[1] == name:
            return True
    return False


def analyse_page(doc, page, drawing_count: int) -> dict:
    """Colourspace usage per painting operator, plus an explicit alignment verdict.

    `drawing_count` is `len(get_drawings())` for the same page.
    """
    painted: list[dict] = []
    forms: list[int] = []
    try:
        _walk(doc, page.read_contents(), _Res(doc, page.xref), painted, 0,
              frozenset(), forms)
        error = None
    except Exception as e:  # noqa: BLE001 — never fatal
        error = f"{type(e).__name__}: {e}"

    aligned = (error is None and len(painted) == drawing_count
               and drawing_count > 0)

    sep_ops = [r for r in painted
               if (r["fill_cs"] and r["fill_cs"][0] == "separation")
               or (r["stroke_cs"] and r["stroke_cs"][0] == "separation")]
    reg_ops = [r for r in painted if _uses(r, REGISTRATION)]

    names: dict[str, int] = {}
    for r in sep_ops:
        for k in ("fill_cs", "stroke_cs"):
            cs = r[k]
            if cs and cs[0] == "separation":
                names[cs[1]] = names.get(cs[1], 0) + 1

    # Index -> colourspace, ONLY when alignment is proven.
    index_map = None
    if aligned:
        index_map = [
            {"fill_separation": (r["fill_cs"][1]
                                 if r["fill_cs"] and r["fill_cs"][0] == "separation"
                                 else None),
             "stroke_separation": (r["stroke_cs"][1]
                                   if r["stroke_cs"] and r["stroke_cs"][0] == "separation"
                                   else None)}
            for r in painted
        ]

    return {
        "painting_operators": len(painted),
        "drawing_count": drawing_count,
        "form_xobjects_expanded": len(forms),
        "alignment_proven": aligned,
        "alignment_reason": (
            "painting-operator count equals drawing count" if aligned
            else (error or f"counts differ ({len(painted)} ops vs "
                           f"{drawing_count} drawings); MuPDF flattens geometry "
                           "this walker does not reproduce")),
        # DIRECT document/page-level facts, independent of alignment:
        "separation_painting_ops": len(sep_ops),
        "separation_ops_by_ink": dict(sorted(names.items())),
        "registration_painting_ops": len(reg_ops),
        "registration_ink_used_on_page": bool(reg_ops),
        # Path-level association, only when proven:
        "path_association": ("DIRECT" if aligned else "UNAVAILABLE"),
        "path_index_map": index_map,
        "policy": (
            "Presence of /Separation /All proves registration ink exists in the "
            "document; it never proves that any particular thin stroke is a "
            "registration mark. Path-level association is claimed only when the "
            "painting-operator sequence provably aligns with the drawing list."),
        "tier_document_level": C.TIER_DIRECT,
        "tier_path_level": C.TIER_DIRECT if aligned else C.TIER_HEURISTIC,
    }
