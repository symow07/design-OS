"""M7 .AI EMITTER — the declared PDF-compatible .ai stream, executable.

Approach per m7_ai_emitter_declaration.json (declared before this was
built): each deliverable becomes a single-artboard PDF 1.6 document
written directly here — vector operators only, LIVE text under the
embedded SET_FACE (Crimson Text, OFL/fsType 0), OCG layers (Ground /
Keylines / Type), Separation spots PANTONE 621 C / 627 C with the
measured-Lab-derived sRGB alternates from the substrate record — saved
with the .ai extension. Illustrator opens the file as editable vector
artwork; that visual-fidelity step is the OWNER'S acceptance and is
recorded as such, never claimed here.

The three committed SVGs are the byte authority (C3 final and T1 are
LOCKED): this module CONVERTS, it never edits. The artwork's own anchor
convention is reproduced, not re-derived: the committed anchors sit at
centre - letter_spacing/2 because the artwork's renderer includes the
trailing letter-space in the advance; PDF's Tc has the same
include-trailing model, so centring on width = sum(advances) + n*Tc at
the SVG's own anchor lands the ink exactly where the locked artwork put
it.

Everything refuses loudly: an SVG tag or attribute outside the three
files' closed vocabulary, a character without a WinAnsi mapping, a
missing glyph, a colour not in the recorded map — all raise. No silent
defaults (the composed-gate discipline).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

REPO = Path(__file__).resolve().parents[3]
from apps.ire.materials_paths import resolve_material_file as _physical_material
MATERIALS_FONT = _physical_material(REPO.parent / "materials" / "Fonts" / "CrimsonText-Regular.ttf", repo_root=REPO.parent)   # Day 6 migration: identity kept, bytes located by the manifest
M7 = REPO / "docs" / "roadmap" / "palt_m7"
OUT_DIR = M7 / "ai_emission"

MM_TO_PT = 72.0 / 25.4

#: the recorded colour authorities (substrate record; no value invented)
SPOT_BY_RGB = {
    (207, 224, 216): {"name": "PANTONE 621 C",
                      "lab": [87.8431, -7.0, 2.0]},
    (17, 50, 44): {"name": "PANTONE 627 C",
                   "lab": [18.0392, -14.0, 0.0]},
}

#: WinAnsi code points beyond ASCII actually used by the artwork
#: ("·" added for the H2 A2 combined bilingual line, §J emission)
WINANSI_EXTRAS = {"—": 0x97, "·": 0xB7}

#: the closed element/attribute vocabulary of the committed SVGs
#: ("path" added for the H2 A2 rosette rings, §J emission: stroked
#: single-subpath absolute M/L[/Z] keylines; FILLED closed plate paths
#: added for the §M dual finals — fills OR strokes, never both; no
#: curves, and deliberately NO disc/circle/ellipse: neither picked
#: final uses them, and a new shape class means the artwork changed)
ALLOWED_ATTRS = {
    "svg": {"width", "height", "viewBox", "xmlns"},
    "rect": {"x", "y", "width", "height", "fill", "stroke",
             "stroke-width", "stroke-dasharray"},
    "line": {"x1", "y1", "x2", "y2", "stroke", "stroke-width"},
    "path": {"d", "fill", "stroke", "stroke-width", "stroke-linecap",
             "stroke-linejoin"},
    "text": {"x", "y", "font-family", "font-size", "letter-spacing",
             "text-anchor", "fill"},
}

DELIVERABLES = (
    ("es3083_lid_C3.ai",
     "lid_artwork/es3083_lid_C3_final.svg", (65.0, 65.0)),
    ("es3083_label_sheet_T1.ai",
     "label_sheet/es3083_label_sheet_T1_centred_black.svg",
     (263.0, 190.0)),
    ("es3083_back_label_DRAFT.ai",
     "back_label/es3083_back_label_DRAFT.svg", (55.0, 55.0)),
)


class AiEmitterError(RuntimeError):
    """Refuses rather than emitting a plausible file."""


# ---------------------------------------------------------------- parsing

def _mm(value):
    v = value.strip()
    if v.endswith("mm"):
        v = v[:-2]
    return float(v)


def _rgb(value):
    v = value.strip()
    if v == "none":
        return None
    if v == "white":
        return (255, 255, 255)
    if v.startswith("rgb(") and v.endswith(")"):
        parts = [int(p) for p in v[4:-1].split(",")]
        return tuple(parts)
    if v.startswith("#") and len(v) == 7:
        return (int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16))
    raise AiEmitterError(f"colour {value!r} outside the recorded "
                         "vocabulary — refusing")


def parse_svg(path) -> dict:
    root = ElementTree.parse(str(path)).getroot()
    tag = root.tag.split("}")[-1]
    if tag != "svg":
        raise AiEmitterError(f"root element {tag!r} is not svg")
    width_mm = _mm(root.attrib["width"])
    height_mm = _mm(root.attrib["height"])
    vb = [float(p) for p in root.attrib["viewBox"].split()]
    if vb != [0.0, 0.0, width_mm, height_mm]:
        raise AiEmitterError(
            f"viewBox {vb} does not equal the mm frame — the artwork's "
            "user unit must be the millimetre")
    elements = []
    for el in root:
        t = el.tag.split("}")[-1]
        if t not in ("rect", "line", "path", "text"):
            raise AiEmitterError(
                f"element {t!r} outside the closed vocabulary — the "
                "emitter converts the committed artwork only")
        extra = set(el.attrib) - ALLOWED_ATTRS[t]
        if extra:
            raise AiEmitterError(f"{t} carries unknown attributes "
                                 f"{sorted(extra)} — refusing")
        elements.append((t, dict(el.attrib),
                         el.text if el.text is not None else ""))
    return {"width_mm": width_mm, "height_mm": height_mm,
            "elements": elements}


# ------------------------------------------------------------- font layer

class SetFace:
    """The SET_FACE, loaded once: advances, metrics, raw bytes."""

    def __init__(self, font_path):
        from fontTools.ttLib import TTFont
        p = Path(font_path)
        if not p.exists():
            raise AiEmitterError(f"SET_FACE missing at {p}")
        self.bytes = p.read_bytes()
        tt = TTFont(str(p))
        self.upm = tt["head"].unitsPerEm
        self.ascent = tt["hhea"].ascent
        self.descent = tt["hhea"].descent
        self.cap_height = tt["OS/2"].sCapHeight
        self.bbox = (tt["head"].xMin, tt["head"].yMin,
                     tt["head"].xMax, tt["head"].yMax)
        if tt["OS/2"].fsType != 0:
            raise AiEmitterError(
                f"fsType {tt['OS/2'].fsType} — embedding permission "
                "changed since the typeface spec; refusing")
        self.cmap = tt.getBestCmap()
        hmtx = tt["hmtx"]
        self.adv = {}
        for ch, glyph_name in self.cmap.items():
            self.adv[ch] = hmtx[glyph_name][0]

    def advance_units(self, ch):
        cp = ord(ch)
        if cp not in self.adv:
            raise AiEmitterError(
                f"character {ch!r} has no glyph in the SET_FACE — "
                "the per-block outline path would be the remedy, and it "
                "was proven unnecessary for the committed artwork; a new "
                "character means the artwork changed")
        return self.adv[cp]

    def encode_winansi(self, s) -> bytes:
        out = bytearray()
        for ch in s:
            cp = ord(ch)
            if 32 <= cp <= 126:
                out.append(cp)
            elif ch in WINANSI_EXTRAS:
                out.append(WINANSI_EXTRAS[ch])
            else:
                raise AiEmitterError(
                    f"character {ch!r} has no WinAnsi mapping — "
                    "refusing to emit a wrong byte")
        return bytes(out)


# ---------------------------------------------------------- PDF assembly

def _esc(b: bytes) -> bytes:
    return (b.replace(b"\\", b"\\\\").replace(b"(", b"\\(")
            .replace(b")", b"\\)"))


def _num(x) -> str:
    s = f"{x:.4f}".rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s


class _Pdf:
    """A minimal deterministic PDF writer: numbered objects, one xref."""

    def __init__(self):
        self.objects = []

    def add(self, body: bytes) -> int:
        self.objects.append(body)
        return len(self.objects)

    def render(self) -> bytes:
        head = b"%PDF-1.6\n%\xe2\xe3\xcf\xd3\n"
        out = bytearray(head)
        offsets = []
        for i, body in enumerate(self.objects, start=1):
            offsets.append(len(out))
            out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
        xref_at = len(out)
        n = len(self.objects) + 1
        out += f"xref\n0 {n}\n".encode()
        out += b"0000000000 65535 f \n"
        for off in offsets:
            out += f"{off:010d} 00000 n \n".encode()
        out += (f"trailer\n<< /Size {n} /Root 1 0 R >>\n"
                f"startxref\n{xref_at}\n%%EOF\n").encode()
        return bytes(out)


def _path_ops(d_attr):
    """Absolute single-subpath M/L[/Z] only — the A2 ring grammar. Any
    other command (curves, relative moves, second subpath) refuses."""
    tokens = d_attr.replace(",", " ").split()
    ops = []
    closed = False
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in ("M", "L"):
            if t == "M" and ops:
                raise AiEmitterError(
                    "path with a second subpath — outside the A2 ring "
                    "grammar; refusing")
            try:
                x, y = float(tokens[i + 1]), float(tokens[i + 2])
            except (IndexError, ValueError):
                raise AiEmitterError(
                    f"path command {t} without a numeric coordinate "
                    "pair — refusing")
            ops.append(("m" if t == "M" else "l", x, y))
            i += 3
        elif t == "Z":
            closed = True
            i += 1
            if i != len(tokens):
                raise AiEmitterError("path content after Z — refusing")
        else:
            raise AiEmitterError(
                f"path command {t!r} outside the closed vocabulary "
                "(absolute M/L/Z only) — refusing")
    if not ops or ops[0][0] != "m":
        raise AiEmitterError("path does not begin with M — refusing")
    return ops, closed


def _stratum_of(kind, attrs):
    if kind == "text":
        return "Type"
    if kind == "line":
        return "Keylines"
    if kind == "path":
        # filled plate paths (the §M dual-final grammar) are Ground;
        # every locked emission's path carries fill="none" -> Keylines,
        # so locked bytes are untouched by this rule
        if attrs.get("fill", "none") != "none":
            return "Ground"
        return "Keylines"
    fill = _rgb(attrs["fill"]) if "fill" in attrs else None
    if fill is not None:
        return "Ground"
    return "Keylines"


def _fill_operators(rgb, spot_names):
    """Colour selection: recorded spots go through their Separation
    space; everything else is the recorded DeviceRGB value."""
    if rgb in SPOT_BY_RGB:
        name = SPOT_BY_RGB[rgb]["name"]
        idx = spot_names.index(name)
        return f"/CS{idx} cs 1 scn\n"
    r, g, b = (c / 255.0 for c in rgb)
    return f"{_num(r)} {_num(g)} {_num(b)} rg\n"


def _stroke_operators(rgb, spot_names):
    if rgb in SPOT_BY_RGB:
        name = SPOT_BY_RGB[rgb]["name"]
        idx = spot_names.index(name)
        return f"/CS{idx} CS 1 SCN\n"
    r, g, b = (c / 255.0 for c in rgb)
    return f"{_num(r)} {_num(g)} {_num(b)} RG\n"


def emit(svg_path, out_path, face) -> dict:
    """Convert one committed SVG into one single-artboard .ai file."""
    art = parse_svg(svg_path)
    W = art["width_mm"] * MM_TO_PT
    H = art["height_mm"] * MM_TO_PT

    spots_used = []
    for kind, attrs, text in art["elements"]:
        for key in ("fill", "stroke"):
            if key in attrs:
                rgb = _rgb(attrs[key])
                if rgb in SPOT_BY_RGB:
                    name = SPOT_BY_RGB[rgb]["name"]
                    if name not in spots_used:
                        spots_used.append(name)

    used_chars = set()
    for kind, attrs, text in art["elements"]:
        if kind == "text":
            used_chars.update(text)
    for ch in sorted(used_chars):
        face.advance_units(ch)   # glyph presence proven before writing
        face.encode_winansi(ch)  # encodability proven before writing

    strata = ("Ground", "Keylines", "Type")
    content = bytearray()
    live_blocks = []
    for kind, attrs, text in art["elements"]:
        stratum = _stratum_of(kind, attrs)
        oc = strata.index(stratum)
        content += f"/OC /oc{oc} BDC\n".encode()
        if kind == "rect":
            if "x" in attrs:
                x = _mm(attrs["x"])
            else:
                x = 0.0
            if "y" in attrs:
                y = _mm(attrs["y"])
            else:
                y = 0.0
            w = _mm(attrs["width"])
            h = _mm(attrs["height"])
            px, py = x * MM_TO_PT, H - (y + h) * MM_TO_PT
            rect_op = (f"{_num(px)} {_num(py)} {_num(w * MM_TO_PT)} "
                       f"{_num(h * MM_TO_PT)} re\n")
            fill = _rgb(attrs["fill"]) if "fill" in attrs else None
            stroke = _rgb(attrs["stroke"]) if "stroke" in attrs else None
            if fill is not None:
                content += _fill_operators(fill, spots_used).encode()
                content += rect_op.encode() + b"f\n"
            if stroke is not None:
                content += _stroke_operators(stroke, spots_used).encode()
                sw = _mm(attrs["stroke-width"]) * MM_TO_PT
                content += f"{_num(sw)} w\n".encode()
                if "stroke-dasharray" in attrs:
                    dashes = [
                        _num(_mm(p) * MM_TO_PT) for p in
                        attrs["stroke-dasharray"].replace(",", " ")
                        .split()]
                    content += (f"[{' '.join(dashes)}] 0 d\n").encode()
                content += rect_op.encode() + b"S\n"
                if "stroke-dasharray" in attrs:
                    content += b"[] 0 d\n"
        elif kind == "line":
            x1, y1 = _mm(attrs["x1"]), _mm(attrs["y1"])
            x2, y2 = _mm(attrs["x2"]), _mm(attrs["y2"])
            stroke = _rgb(attrs["stroke"])
            content += _stroke_operators(stroke, spots_used).encode()
            sw = _mm(attrs["stroke-width"]) * MM_TO_PT
            content += f"{_num(sw)} w\n".encode()
            content += (
                f"{_num(x1 * MM_TO_PT)} {_num(H - y1 * MM_TO_PT)} m "
                f"{_num(x2 * MM_TO_PT)} {_num(H - y2 * MM_TO_PT)} l "
                f"S\n").encode()
        elif kind == "path":
            if "fill" not in attrs:
                raise AiEmitterError(
                    "path without a fill attribute — outside the closed "
                    "vocabulary; refusing")
            if attrs["fill"] != "none":
                # FILLED PLATE grammar (§M dual finals: cartouche, boss
                # and medallion plates): closed single-subpath fill, no
                # stroke attributes — anything mixed refuses
                stroke_attrs = {"stroke", "stroke-width",
                                "stroke-linecap", "stroke-linejoin"} \
                    & set(attrs)
                if stroke_attrs:
                    raise AiEmitterError(
                        f"filled path carries stroke attributes "
                        f"{sorted(stroke_attrs)} — the plate grammar "
                        "fills OR strokes, never both; refusing")
                ops, closed = _path_ops(attrs["d"])
                if not closed:
                    raise AiEmitterError(
                        "filled path without Z — a plate must close; "
                        "refusing")
                fill = _rgb(attrs["fill"])
                content += _fill_operators(fill, spots_used).encode()
                for op, x, y in ops:
                    content += (f"{_num(x * MM_TO_PT)} "
                                f"{_num(H - y * MM_TO_PT)} {op}\n").encode()
                content += b"h f\n"
            else:
                for cap_attr in ("stroke-linecap", "stroke-linejoin"):
                    if cap_attr in attrs and attrs[cap_attr] != "round":
                        raise AiEmitterError(
                            f"{cap_attr} {attrs[cap_attr]!r} outside the "
                            "committed artwork's vocabulary — refusing")
                stroke = _rgb(attrs["stroke"])
                content += _stroke_operators(stroke, spots_used).encode()
                sw = _mm(attrs["stroke-width"]) * MM_TO_PT
                content += f"{_num(sw)} w\n1 J\n1 j\n".encode()
                ops, closed = _path_ops(attrs["d"])
                for op, x, y in ops:
                    content += (f"{_num(x * MM_TO_PT)} "
                                f"{_num(H - y * MM_TO_PT)} {op}\n").encode()
                content += b"h S\n" if closed else b"S\n"
                content += b"0 J\n0 j\n"
        else:
            if attrs["font-family"] != "Crimson Text":
                raise AiEmitterError(
                    f"font-family {attrs['font-family']!r} is not the "
                    "SET_FACE — the artwork changed; refusing")
            anchor = attrs["text-anchor"] if "text-anchor" in attrs \
                else "start"
            if anchor not in ("middle", "start"):
                raise AiEmitterError(
                    f"text-anchor {anchor!r} unsupported — the "
                    "committed artworks anchor middle or start only")
            size_pt = _mm(attrs["font-size"]) * MM_TO_PT
            if "letter-spacing" in attrs:
                spacing_mm = _mm(attrs["letter-spacing"])
            else:
                spacing_mm = 0.0
            tc_pt = spacing_mm * MM_TO_PT
            adv_pt = sum(face.advance_units(ch) / face.upm * size_pt
                         for ch in text)
            width_pt = adv_pt + len(text) * tc_pt
            ax = _mm(attrs["x"]) * MM_TO_PT
            ay = H - _mm(attrs["y"]) * MM_TO_PT
            if anchor == "middle":
                tx = ax - width_pt / 2.0
            else:
                tx = ax
            fill = _rgb(attrs["fill"])
            content += _fill_operators(fill, spots_used).encode()
            content += b"BT\n"
            content += f"/F1 {_num(size_pt)} Tf\n".encode()
            content += f"{_num(tc_pt)} Tc\n".encode()
            content += f"{_num(tx)} {_num(ay)} Td\n".encode()
            content += b"(" + _esc(face.encode_winansi(text)) + b") Tj\n"
            content += b"ET\n"
            live_blocks.append(text)
        content += b"EMC\n"

    pdf = _Pdf()
    # object numbering plan: 1 catalog, 2 pages, 3 page, 4 contents,
    # 5 font, 6 descriptor, 7 fontfile, 8.. OCGs, then separations
    ocg_first = 8
    sep_first = ocg_first + len(strata)
    catalog = (
        "<< /Type /Catalog /Pages 2 0 R /OCProperties << /OCGs ["
        + " ".join(f"{ocg_first + i} 0 R" for i in range(len(strata)))
        + "] /D << /Order ["
        + " ".join(f"{ocg_first + i} 0 R" for i in range(len(strata)))
        + "] /ON ["
        + " ".join(f"{ocg_first + i} 0 R" for i in range(len(strata)))
        + "] >> >> >>")
    pdf.add(catalog.encode())
    pdf.add(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    props = " ".join(f"/oc{i} {ocg_first + i} 0 R"
                     for i in range(len(strata)))
    csres = " ".join(f"/CS{i} {sep_first + i} 0 R"
                     for i in range(len(spots_used)))
    page = (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_num(W)} "
            f"{_num(H)}] /Contents 4 0 R /Resources << /Font << /F1 "
            f"5 0 R >> /Properties << {props} >> /ColorSpace << {csres} "
            f">> >> >>")
    pdf.add(page.encode())
    stream = bytes(content)
    pdf.add(b"<< /Length " + str(len(stream)).encode()
            + b" >>\nstream\n" + stream + b"\nendstream")

    # LastChar is usage-derived with 0x97 as the floor: the three locked
    # emissions use at most the em-dash, so their bytes are UNCHANGED by
    # this rule (proven by the re-emission regression test); an artwork
    # using a higher WinAnsi extra (the A2 middot, 0xB7) widens its own
    # table only.
    first_char = 32
    last_char = max([0x97] + [WINANSI_EXTRAS[ch] for ch in used_chars
                              if ch in WINANSI_EXTRAS])
    widths = []
    inv_extras = {v: k for k, v in WINANSI_EXTRAS.items()}
    for code in range(first_char, last_char + 1):
        if 32 <= code <= 126:
            ch = chr(code)
        elif code in inv_extras:
            ch = inv_extras[code]
        else:
            widths.append(0)
            continue
        if ord(ch) in face.adv:
            widths.append(round(face.adv[ord(ch)] * 1000.0 / face.upm))
        else:
            widths.append(0)
    scale = 1000.0 / face.upm
    font = (f"<< /Type /Font /Subtype /TrueType /BaseFont "
            f"/CrimsonText-Regular /FirstChar {first_char} /LastChar "
            f"{last_char} /Widths [{' '.join(str(w) for w in widths)}] "
            f"/Encoding /WinAnsiEncoding /FontDescriptor 6 0 R >>")
    pdf.add(font.encode())
    bx = [round(v * scale) for v in face.bbox]
    desc = (f"<< /Type /FontDescriptor /FontName /CrimsonText-Regular "
            f"/Flags 32 /FontBBox [{bx[0]} {bx[1]} {bx[2]} {bx[3]}] "
            f"/ItalicAngle 0 /Ascent {round(face.ascent * scale)} "
            f"/Descent {round(face.descent * scale)} /CapHeight "
            f"{round(face.cap_height * scale)} /StemV 80 /FontFile2 "
            f"7 0 R >>")
    pdf.add(desc.encode())
    pdf.add(b"<< /Length " + str(len(face.bytes)).encode()
            + b" /Length1 " + str(len(face.bytes)).encode()
            + b" >>\nstream\n" + face.bytes + b"\nendstream")
    for name in strata:
        pdf.add(f"<< /Type /OCG /Name ({name}) >>".encode())
    for name in spots_used:
        alt = None
        for rgb, spec in SPOT_BY_RGB.items():
            if spec["name"] == name:
                alt = rgb
        r, g, b = (c / 255.0 for c in alt)
        pdf_name = "/" + name.replace(" ", "#20")
        sep = (f"[ /Separation {pdf_name} /DeviceRGB << /FunctionType 2 "
               f"/Domain [0 1] /C0 [1 1 1] /C1 [{_num(r)} {_num(g)} "
               f"{_num(b)}] /N 1 >> ]")
        pdf.add(sep.encode())

    data = pdf.render()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    src = Path(svg_path).resolve()
    if src.is_relative_to(REPO):
        src_recorded = str(src.relative_to(REPO))
    else:
        src_recorded = str(src)
    return {
        "ai": out_path.name,
        "source_svg": src_recorded,
        "source_sha256": hashlib.sha256(
            Path(svg_path).read_bytes()).hexdigest(),
        "ai_sha256": hashlib.sha256(data).hexdigest(),
        "artboard_mm": [art["width_mm"], art["height_mm"]],
        "layers": list(strata),
        "spot_separations": list(spots_used),
        "live_text_blocks": live_blocks,
        "outlined_text_blocks": [],
        "bytes": len(data),
    }


# ------------------------------------------------------------ validation

def validate(ai_path, expect_mm, expect_texts, expect_spots) -> dict:
    """The declared programmatic assertions — what parsing CAN prove."""
    import fitz
    doc = fitz.open(str(ai_path))
    findings = []
    if doc.page_count != 1:
        findings.append(f"page_count {doc.page_count} != 1")
    page = doc[0]
    w_mm = page.rect.width / MM_TO_PT
    h_mm = page.rect.height / MM_TO_PT
    if abs(w_mm - expect_mm[0]) > 0.01 or abs(h_mm - expect_mm[1]) > 0.01:
        findings.append(f"artboard {w_mm:.3f}x{h_mm:.3f} != {expect_mm}")
    fonts = page.get_fonts(full=True)
    embedded = [f for f in fonts if "CrimsonText" in f[3]]
    if not embedded:
        findings.append("SET_FACE not present in page fonts")
    else:
        extracted = doc.extract_font(embedded[0][0])
        if len(extracted[3]) == 0:
            findings.append("font present but NOT embedded")
    if page.get_images():
        findings.append("raster image object present — not vector-only")
    # wide letter-spacing makes extractors insert word breaks between
    # glyphs, so liveness is proven two ways: the glyph SEQUENCE
    # extracts (whitespace-insensitive), and the exact WinAnsi string
    # bytes sit in the (uncompressed) content stream as a Tj operand.
    squashed = "".join(page.get_text().split())
    raw = Path(ai_path).read_bytes()
    face_for_bytes = SetFace(MATERIALS_FONT)
    for s in expect_texts:
        if "".join(s.split()) not in squashed:
            findings.append(f"live text {s!r} did not extract")
        operand = b"(" + _esc(face_for_bytes.encode_winansi(s)) + b") Tj"
        if operand not in raw:
            findings.append(f"Tj operand for {s!r} absent from the "
                            "content stream")
    for name in expect_spots:
        if name.replace(" ", "#20").encode() not in raw:
            findings.append(f"separation {name!r} absent")
    if b"/OCProperties" not in raw:
        findings.append("no OCG layer table")
    doc.close()
    return {"path": str(ai_path), "findings": findings,
            "verdict": "PASS" if not findings else "FAIL"}


def emit_all() -> dict:
    face = SetFace(MATERIALS_FONT)
    emissions, validations = [], []
    for ai_name, rel_svg, mm in DELIVERABLES:
        svg = M7 / rel_svg
        out = OUT_DIR / ai_name
        rec = emit(svg, out, face)
        if rec["artboard_mm"] != [mm[0], mm[1]]:
            raise AiEmitterError(
                f"{ai_name}: artboard {rec['artboard_mm']} != declared "
                f"{mm} — the artwork and the declaration disagree")
        v = validate(out, mm, rec["live_text_blocks"],
                     rec["spot_separations"])
        if v["verdict"] != "PASS":
            raise AiEmitterError(
                f"{ai_name} failed its own validation: {v['findings']}")
        emissions.append(rec)
        validations.append(v)
    record = {
        "record_type": "m7_ai_emission/1.0",
        "emitted": "2026-08-15",
        "declaration": "m7_ai_emitter_declaration.json",
        "set_face": {
            "file": "materials/Fonts/CrimsonText-Regular.ttf",
            "sha256": hashlib.sha256(face.bytes).hexdigest(),
            "licence": "OFL, fsType 0 — embedding permitted",
            "embedded_live": True,
        },
        "emissions": emissions,
        "validations": validations,
        "validation_cannot_prove": (
            "visual fidelity inside Adobe Illustrator — layer mapping, "
            "spot-swatch panel, practical editability. That is the "
            "OWNER'S acceptance step: open each file in Illustrator."),
        "owner_approved": False,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "m7_ai_emission_record.json").write_text(
        json.dumps(record, indent=1) + "\n")
    return record


if __name__ == "__main__":
    rec = emit_all()
    for e in rec["emissions"]:
        print(f"{e['ai']}: {e['artboard_mm'][0]}x{e['artboard_mm'][1]}mm "
              f"{e['bytes']}b sha256 {e['ai_sha256'][:16]} "
              f"spots={e['spot_separations']} "
              f"live={len(e['live_text_blocks'])}")
    print("ALL VALIDATIONS PASS — Illustrator fidelity remains the "
          "owner's acceptance step")
