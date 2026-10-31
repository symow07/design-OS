"""§BH50(f)(7), OWNER RULED 2026-09-13 — THE COUNTER READS EVERY PLACE COLOUR IS
APPLIED: fills, strokes and text. "A counter that reads fills alone is not a
counter, and the ink proved it."

The reader of the emitted artefact, operator by operator. reportlab is the only
writer of these bytes (pdf_ai.py), so its grammar is the one interpreted: a
q/Q graphics-state stack; the colour-set operators rg RG k K g G cs CS sc SC
scn SCN; the painting operators (f F f* B B* b b* for the fill colour, S s B B*
b b* for the stroke colour); text shows (Tj TJ ' ") under the render mode Tr —
0/2/4/6 apply the fill colour, 1/2/5/6 the stroke colour, 3/7 apply none — and
a show with no glyphs applies no colour; `sh` shadings, whose Type 2 / Type 3
functions carry the stops; `Do` XObjects branched on /Subtype (an Image is
colour applied to the page and is NOT colour-reconciled — placement_usage/1.0
governs it; a Form is walked in the graphics state in effect where it is
painted, with its own resources, or the painting stream's where it declares
none; any other XObject, or a name the resources do not hold, is unreadable). A colour is read in
the colour space it is DRAWN in: DeviceRGB by its hex, DeviceCMYK by its
components (matched against the counted rows' own cmyk, never through an ICC
conversion — the §BH39(f) instrument, PyMuPDF's get_drawings, hands back
ICC-converted RGB with no colour space, which on a jar's CMYK motif reads a
false disagreement; tools/dip0b/color.py:160 calls that route "HEURISTIC by
construction", and tools/dip0b/contentstream.py is this walker's precedent —
not reused, because it is not string-aware and records no colour value).

Pure: no Django, no ORM, no network, no PyMuPDF. Never raises to its caller —
``read_applications`` returns ``{"status": "UNREAD", ...}`` when the bytes
cannot be read, which the reconciler turns into a code and never into a pass.
"""
from __future__ import annotations

import base64
import re
import zlib

_WS = b" \t\r\n\f\x00"
_DELIM = b"()<>[]{}/%"


class _Name(str):
    pass


class _Ref(tuple):
    pass


class _Op(str):
    pass


_EI = re.compile(rb"[ \t\r\n\f\x00]EI(?=[ \t\r\n\f\x00]|$)")
_EI_A85 = re.compile(rb"~>[ \t\r\n\f\x00]*EI(?=[ \t\r\n\f\x00]|$)")   # an ASCII85 payload ends at its own ~>


def _tokenize(data: bytes):
    """PDF tokens. An inline image's payload (after ``ID``) is skipped to its ``EI`` by the tokenizer itself, so no
    payload byte is ever read as a string, a name or an operator (review finding R2: a ``(`` in an ASCII85 payload
    swallowed every operator after the image, and the reader reported READ over a shortened census). A literal
    string that reaches the end of the data unterminated raises — the census is cut, so the artefact is UNREAD,
    never READ short (R4)."""
    i, n = 0, len(data)
    bi_at = 0
    while i < n:
        ch = data[i:i + 1]
        if ch in (b" ", b"\t", b"\r", b"\n", b"\f", b"\x00"):
            i += 1
            continue
        if ch == b"%":
            while i < n and data[i:i + 1] not in (b"\r", b"\n"):
                i += 1
            continue
        if ch == b"/":
            j = i + 1
            while j < n and data[j:j + 1] not in _WS and data[j:j + 1] not in _DELIM:
                j += 1
            raw = re.sub(rb"#([0-9A-Fa-f]{2})",
                         lambda m: bytes([int(m.group(1), 16)]), data[i + 1:j])
            yield _Name(raw.decode("latin-1"))
            i = j
            continue
        if ch == b"(":
            depth, j, out = 1, i + 1, bytearray()
            while j < n and depth:
                c = data[j:j + 1]
                if c == b"\\":
                    nx = data[j + 1:j + 2]
                    esc = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b",
                           b"f": b"\f", b"(": b"(", b")": b")", b"\\": b"\\"}
                    if nx in esc:
                        out += esc[nx]
                        j += 2
                    elif nx.isdigit():
                        k = j + 1
                        while k < j + 4 and data[k:k + 1].isdigit():
                            k += 1
                        out.append(int(data[j + 1:k], 8) & 0xFF)
                        j = k
                    elif nx in (b"\r", b"\n"):
                        j += 2
                    else:
                        j += 1
                    continue
                if c == b"(":
                    depth += 1
                elif c == b")":
                    depth -= 1
                    if depth == 0:
                        j += 1
                        break
                out += c
                j += 1
            if depth:
                raise ValueError("unterminated literal string: the content stream is cut")
            yield bytes(out)
            i = j
            continue
        if ch == b"<":
            if data[i + 1:i + 2] == b"<":
                yield _Op("<<")
                i += 2
                continue
            j = data.index(b">", i)
            hx = re.sub(rb"\s", b"", data[i + 1:j])
            if len(hx) % 2:
                hx += b"0"
            yield bytes.fromhex(hx.decode())
            i = j + 1
            continue
        if ch == b">":
            if data[i + 1:i + 2] == b">":
                yield _Op(">>")
                i += 2
                continue
            i += 1
            continue
        if ch in (b"[", b"]", b"{", b"}"):
            yield _Op(ch.decode())
            i += 1
            continue
        j = i
        while j < n and data[j:j + 1] not in _WS and data[j:j + 1] not in _DELIM:
            j += 1
        word = data[i:j]
        if j == i:
            i += 1
            continue
        try:
            yield float(word) if (b"." in word) else int(word)
        except ValueError:
            yield _Op(word.decode("latin-1"))
            if word == b"BI":
                bi_at = i
            if word == b"ID":
                # a line of an ASCII85 payload may itself begin "EI "; when the image declares ASCII85 its payload
                # ends at "~>", so EI is looked for only after that marker
                head = data[bi_at:j]
                m = (_EI_A85 if (b"/A85" in head or b"ASCII85Decode" in head) else _EI).search(data, j)
                if m is None:
                    raise ValueError("inline image without EI: the content stream is cut")
                j = m.end()
                yield _Op("EI")
        i = j


def _fold_refs(items):
    out = []
    for it in items:
        if (isinstance(it, _Op) and it == "R" and len(out) >= 2
                and isinstance(out[-1], int) and isinstance(out[-2], int)):
            g = out.pop()
            num = out.pop()
            out.append(_Ref((num, g)))
        else:
            out.append(it)
    return out


def _parse(tokens):
    stack = [[]]
    for t in tokens:
        if isinstance(t, _Op) and t in ("[", "<<"):
            stack.append([t])
        elif isinstance(t, _Op) and t == "]":
            items = stack.pop()[1:]
            stack[-1].append(_fold_refs(items))
        elif isinstance(t, _Op) and t == ">>":
            items = _fold_refs(stack.pop()[1:])
            d = {}
            for k in range(0, len(items) - 1, 2):
                d[str(items[k])] = items[k + 1]
            stack[-1].append(d)
        else:
            stack[-1].append(t)
    return _fold_refs(stack[0])


class _PDF:
    def __init__(self, raw: bytes):
        self.raw = raw
        self.objs = {}
        for m in re.finditer(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", raw, re.S):
            self.objs[int(m.group(1))] = m.group(3)

    def obj(self, num):
        body = self.objs[num]
        sm = re.search(rb"\bstream\r?\n", body)
        if sm:
            val = _parse(_tokenize(body[:sm.start()]))[0]
            data = body[sm.end():body.rfind(b"endstream")]
            length = val.get("Length") if isinstance(val, dict) else None
            if isinstance(length, int) and length <= len(data):
                data = data[:length]
            return val, data
        return _parse(_tokenize(body))[0], None

    def resolve(self, v):
        while isinstance(v, _Ref):
            v = self.obj(v[0])[0]
        return v

    def stream(self, num):
        d, data = self.obj(num)
        filters = d.get("Filter")
        filters = [] if filters is None else (filters if isinstance(filters, list) else [filters])
        for f in filters:
            if f == "ASCII85Decode":
                s = data.strip()
                if s.startswith(b"<~"):
                    s = s[2:]
                if s.endswith(b"~>"):
                    s = s[:-2]
                data = base64.a85decode(re.sub(rb"\s", b"", s))
            elif f == "FlateDecode":
                data = zlib.decompress(data)
            else:
                raise ValueError(f"unsupported stream filter {f!r}")
        return d, data


def _hex_rgb(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, int(round(v * 255)))) for v in c[:3])


_CS_COMPS = {"DeviceRGB": 3, "DeviceCMYK": 4, "DeviceGray": 1}
_INIT = {"DeviceRGB": (0.0, 0.0, 0.0), "DeviceCMYK": (0.0, 0.0, 0.0, 1.0), "DeviceGray": (0.0,)}
_PAINT_FILL = {"f", "F", "f*", "B", "B*", "b", "b*"}
_PAINT_STROKE = {"S", "s", "B", "B*", "b", "b*"}
_SHOW = {"Tj", "TJ", "'", '"'}


def _colour(cs, comps) -> dict:
    """A colour AS DRAWN: its space and components, and its hex where the
    space is RGB or Gray. A CMYK colour carries no hex of its own — it is
    matched by components against the counted rows, never converted."""
    comps = tuple(float(x) for x in comps)
    if cs == "DeviceRGB" and len(comps) == 3:
        return {"space": cs, "components": comps, "hex": _hex_rgb(comps)}
    if cs == "DeviceGray" and len(comps) == 1:
        return {"space": cs, "components": comps, "hex": _hex_rgb((comps[0],) * 3)}
    if cs == "DeviceCMYK" and len(comps) == 4:
        return {"space": cs, "components": comps, "hex": None}
    return {"space": str(cs), "components": comps, "hex": None}


def _function_stops(pdf, fn):
    fn = pdf.resolve(fn)
    if isinstance(fn, list):
        return [None]
    t = fn.get("FunctionType") if isinstance(fn, dict) else None
    if t == 2:
        return [tuple(fn.get("C0", [0.0])), tuple(fn.get("C1", [1.0]))]
    if t == 3:
        out = []
        for sub in fn.get("Functions", []):
            out += _function_stops(pdf, sub)
        return out
    return [None]


def _mesh_stops(pdf, ref, sd: dict, cs: str) -> list:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (8) and (9): a glow and a gradient drawn as a smooth mesh.]
    The colour at every corner of a Coons (Type 6) or tensor (Type 7) patch mesh, read from the mesh's own stream: each
    patch its flag, its control points (12 or 16 for a new patch, 8 or 12 continuing one) and its corner colours (4, or
    2 continuing), unpacked at its BitsPerFlag, BitsPerCoordinate and BitsPerComponent and decoded by its Decode ranges;
    ``[None]`` where it cannot be read (no stream, bits not byte-aligned)."""
    if not isinstance(ref, _Ref):
        return [None]
    try:
        _d, data = pdf.stream(ref[0])
    except (ValueError, KeyError, zlib.error):
        return [None]
    n = _CS_COMPS.get(cs)
    bf, bc, bk = (int(sd.get(k, 0)) for k in ("BitsPerFlag", "BitsPerCoordinate", "BitsPerComponent"))
    decode = [float(v) for v in sd.get("Decode") or []]
    if n is None or bf % 8 or bc % 8 or bk % 8 or len(decode) < 4 + 2 * n:
        return [None]
    new_pts, more_pts = (12, 8) if sd.get("ShadingType") == 6 else (16, 12)
    out, at = [], 0
    while at < len(data):
        flag = int.from_bytes(data[at:at + bf // 8], "big")
        at += bf // 8
        at += (new_pts if flag == 0 else more_pts) * 2 * (bc // 8)
        for _corner in range(4 if flag == 0 else 2):
            comps = []
            for c in range(n):
                raw = int.from_bytes(data[at:at + bk // 8], "big")
                at += bk // 8
                lo, hi = decode[4 + 2 * c], decode[5 + 2 * c]
                comps.append(lo + raw * (hi - lo) / float((1 << bk) - 1))
            out.append(tuple(comps))
    return out if at == len(data) else [None]


def _interpret(pdf, content: bytes, resources, events: list, initial: dict | None = None, depth: int = 0):
    """Walk one content stream. ``initial`` is the graphics state in effect where a Form XObject is painted: a form
    INHERITS it (review finding R1 — reading a form from a fresh black state dropped every colour it inherits into
    process and passed an uncounted colour)."""
    if depth > 16:
        raise ValueError("Form XObjects nested deeper than 16: refusing to recurse")
    res = pdf.resolve(resources) or {}
    shadings = pdf.resolve(res.get("Shading")) or {}
    xobjs = pdf.resolve(res.get("XObject")) or {}
    gs = dict(initial) if initial else {"fcs": "DeviceGray", "fc": (0.0,), "scs": "DeviceGray", "sc": (0.0,), "Tr": 0}
    stack, ops = [], []
    toks = list(_tokenize(content))
    i = 0
    while i < len(toks):
        t = toks[i]
        i += 1
        if not isinstance(t, _Op) or t in ("[", "]", "<<", ">>"):
            ops.append(t)
            continue
        operands = _parse(ops)
        ops = []
        op = str(t)
        if op == "q":
            stack.append(dict(gs))
        elif op == "Q":
            gs = stack.pop() if stack else gs
        elif op in ("rg", "RG", "k", "K", "g", "G"):
            cs = {"rg": "DeviceRGB", "RG": "DeviceRGB", "k": "DeviceCMYK", "K": "DeviceCMYK",
                  "g": "DeviceGray", "G": "DeviceGray"}[op]
            comps = tuple(float(x) for x in operands[-_CS_COMPS[cs]:])
            if op.islower():
                gs["fcs"], gs["fc"] = cs, comps
            else:
                gs["scs"], gs["sc"] = cs, comps
        elif op in ("cs", "CS"):
            name = str(operands[-1])
            cs = name if name in _CS_COMPS else f"named:{name}"
            if op == "cs":
                gs["fcs"], gs["fc"] = cs, _INIT.get(cs, ())
            else:
                gs["scs"], gs["sc"] = cs, _INIT.get(cs, ())
        elif op in ("sc", "scn", "SC", "SCN"):
            nums = tuple(float(x) for x in operands if isinstance(x, (int, float)))
            if op in ("sc", "scn"):
                gs["fc"] = nums
            else:
                gs["sc"] = nums
        elif op in _PAINT_FILL or op in _PAINT_STROKE:
            if op in _PAINT_FILL:
                events.append(dict(kind="fill", **_colour(gs["fcs"], gs["fc"])))
            if op in _PAINT_STROKE:
                events.append(dict(kind="stroke", **_colour(gs["scs"], gs["sc"])))
        elif op == "Tr":
            gs["Tr"] = int(operands[-1])
        elif op in _SHOW:
            if op == "TJ":
                arr = operands[-1] if operands else []
                raw = b"".join(x for x in arr if isinstance(x, bytes)) if isinstance(arr, list) else b""
            else:
                raw = operands[-1] if operands and isinstance(operands[-1], bytes) else b""
            if not raw:
                continue                    # a show with no glyphs applies no colour
            mode = gs["Tr"]
            if mode in (0, 2, 4, 6):
                events.append(dict(kind="text", **_colour(gs["fcs"], gs["fc"])))
            if mode in (1, 2, 5, 6):
                events.append(dict(kind="text_stroke", **_colour(gs["scs"], gs["sc"])))
        elif op == "sh":
            name = str(operands[-1]) if operands else ""
            sd = pdf.resolve(shadings.get(name)) or {}
            cs = pdf.resolve(sd.get("ColorSpace"))
            cs = str(cs) if not isinstance(cs, list) else f"array:{cs[0]}"
            # [his goal of 2026-10-13, (8) and (9)] a mesh's colours are its patches' own corners, in its stream
            stops = (_mesh_stops(pdf, shadings.get(name), sd, cs) if sd.get("ShadingType") in (6, 7)
                     else _function_stops(pdf, sd.get("Function")))
            for s in stops:
                if s is None:
                    events.append({"kind": "stop", "space": cs, "components": (), "hex": None,
                                   "shading": name, "unreadable": True})
                else:
                    events.append(dict(kind="stop", shading=name, **_colour(cs, s)))
        elif op == "Do":
            name = str(operands[-1]) if operands else ""
            ref = xobjs.get(name)
            d = pdf.resolve(ref) or {}
            sub = d.get("Subtype") if isinstance(d, dict) else None
            if sub == "Image":
                events.append({"kind": "image", "xobject": name, "space": str(d.get("ColorSpace")),
                               "components": (), "hex": None})
            elif sub == "Form" and isinstance(ref, _Ref):
                fd, fdata = pdf.stream(ref[0])
                _interpret(pdf, fdata, fd.get("Resources") or res, events, initial=gs, depth=depth + 1)
            else:
                # R3: a name the resources do not hold, or a Subtype this reader does not know, cannot be read —
                # recorded as unreadable so the reconciler returns UNREAD, the way an unknown shading already does
                events.append({"kind": "xobject", "xobject": name, "space": "?", "components": (), "hex": None,
                               "unreadable": True})
        elif op == "EI":
            events.append({"kind": "image", "xobject": "inline", "space": "?", "components": (), "hex": None})
        elif op in ("BI", "ID"):
            continue                              # the image dictionary's operands are discarded with ``ops``
    return events


def read_applications(pdf_path: str) -> dict:
    """Every colour application in the artefact, by kind, as drawn. Status
    READ, or UNREAD with the reason when the bytes could not be interpreted —
    never a raise, never an empty census presented as a clean one."""
    try:
        pdf = _PDF(open(pdf_path, "rb").read())
        pages = [(num, pdf.obj(num)[0]) for num in sorted(pdf.objs)]
        pages = [(n, d) for n, d in pages if isinstance(d, dict) and d.get("Type") == "Page"]
        if not pages:
            return {"status": "UNREAD", "reason": "no page object found in the artefact",
                    "events": [], "pages": 0}
        events: list = []
        for _num, d in pages:
            contents = d.get("Contents")
            refs = contents if isinstance(contents, list) else [contents]
            data = b"".join(pdf.stream(r[0])[1] for r in refs if isinstance(r, _Ref))
            _interpret(pdf, data, d.get("Resources"), events)
        return {"status": "READ", "events": events, "pages": len(pages)}
    except Exception as exc:  # noqa: BLE001 — the reader's own failure is a finding, never a raise
        return {"status": "UNREAD", "reason": f"{type(exc).__name__}: {exc}", "events": [], "pages": 0}


__all__ = ["read_applications"]
