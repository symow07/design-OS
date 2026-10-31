"""One authoritative object/colour model for the AI8/EPS source and its proofs.

Gate A failed because every visible object in ``vq2_a2_r2_final.ai`` was emitted
as ``0.0000 0.0000 0.0000 Xa``, so Illustrator opened a black silhouette.

The root cause is visible in the accepted artefacts themselves. The PDF proof
committed alongside that source carries the correct colours — ``.85098 .741176
.709804 rg`` and the other three — while the ``.ai`` carries a constant zero
triple for all forty objects. Two separate writers produced the two files from
the same artwork, and only one of them was ever looked at. No emitter for the
``.ai`` exists in the repository at all: it was written by a throwaway script,
which is why nothing tested it and why the divergence survived review.

So this module is deliberately arranged so that class of bug cannot recur:

* geometry is carried as the **raw source text lines**, byte for byte. Nothing
  re-formats a coordinate, so "geometry drift = 0" is true by construction
  rather than by after-the-fact comparison.
* the AI, the PDF and the PNG are all produced from this one model. AI8 path
  operators map 1:1 onto PDF operators, so the PDF carries the identical
  numbers, and the PNG is a raster of that same PDF. There is no second colour
  implementation left to drift.
* a visible object with no assigned colour raises. It is never a black default.
* the emitted bytes are checked by *executing* them (:func:`ps_resolve`), not by
  scanning them, so an operator whose operands are consumed in the wrong order
  cannot pass. That is the specific mistake that turns #D9BDB5 into #B5BDD9.

The authoritative values below are not restatements of the brief; they are read
back out of the accepted PDF proof, which is the artefact the owner approved.
"""
import re

FLAT_COLORS = {
    "BODY": (0xD9, 0xBD, 0xB5),
    "COLLAR": (0x70, 0x52, 0x42),
    "CLOSURE": (0x49, 0x30, 0x34),
    "ARTWORK": (0x50, 0x25, 0x25),
}

LAYER_ROLE = {
    "01_STRUCTURE_BODY": "BODY",
    "02_STRUCTURE_COLLAR": "COLLAR",
    "03_STRUCTURE_CLOSURE": "CLOSURE",
    "04_APPROVED_BBROSE_LOGO": "ARTWORK",
    "05_DIVIDER": "ARTWORK",
    "06_ROSE_LETTERING": "ARTWORK",
    "07_DAMASCENA_LETTERING": "ARTWORK",
    "08_SUPPORTING_COPY": "ARTWORK",
}

# Read out of the accepted proof's content stream, not chosen here. The AI
# declared no stroke width at all and would therefore have drawn the divider at
# the PostScript default of 1 pt — nearly three times the accepted weight. That
# is a second, quieter source/proof divergence in the same file.
#
# §W4: this is the COLOUR SHEET's divider, measured in the context it was
# measured in. It is NOT the container's front rule and neither number moves
# to meet the other — see ire/container_line_weight.py for all three elements.
DIVIDER_WIDTH_PT = 0.362384

# The accepted proof fills every object with `f*`, and the rule is load
# bearing: rendering these glyphs under nonzero winding closes counters that
# even-odd keeps open (H loses both, R and A lose two each). So even-odd is
# declared explicitly in three places rather than left to any default — `1 XR`
# in the AI setup, `eofill` in the prolog, and `f*` in the PDF.
EVEN_ODD = True

# the accepted clean proof's raster size
PROOF_WIDTH_PX = 576
PROOF_HEIGHT_PX = 1371
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)

EXPECTED_GROUPS = {
    "01_STRUCTURE_BODY": 1,
    "02_STRUCTURE_COLLAR": 1,
    "03_STRUCTURE_CLOSURE": 1,
    "04_APPROVED_BBROSE_LOGO": 9,
    "05_DIVIDER": 1,
    "06_ROSE_LETTERING": 4,
    "07_DAMASCENA_LETTERING": 9,
    "08_SUPPORTING_COPY": 14,
}


def hexs(rgb):
    return "#%02X%02X%02X" % tuple(rgb)


def _norm(rgb):
    """Round, never truncate. The proof PNG shipped #D8BCB5 for #D9BDB5 once."""
    return tuple(round(c / 255.0, 6) for c in rgb)


def _rgb255(norm):
    return tuple(round(float(v) * 255) for v in norm)


class Obj:
    """A visible drawing object: its identity, its geometry, its paint."""

    def __init__(self, layer, name, role=None, rgb=None):
        self.layer = layer
        self.name = name
        self._rgb = rgb           # fixtures paint outside the accepted palette
        self.geometry = []        # raw source lines, byte-identical
        self.color_op = None      # 'Xa' (fill) or 'XA' (stroke)
        self.emitted_rgb = None   # what the SOURCE bytes said
        self.paint_op = None      # 'f' or 'S'
        self.width = None         # stroke width, when the source declares one
        self._role = role         # set directly by the capability fixture

    @property
    def role(self):
        return self._role or LAYER_ROLE.get(self.layer)

    @property
    def expected_rgb(self):
        if self._rgb is not None:
            return self._rgb
        role = self.role
        return FLAT_COLORS[role] if role else None

    def subpaths(self):
        """Flatten the raw geometry into (op, coords) for rendering."""
        out = []
        for ln in self.geometry:
            if ln == "h":
                out.append(("h", []))
                continue
            m = re.match(r"^([-0-9. ]+)([mLC])$", ln)
            if m:
                nums = [float(v) for v in m.group(1).split()]
                out.append((m.group(2), nums))
        return out


class Doc:
    def __init__(self):
        self.header = []
        self.layers = []          # [(lb_line, layer_name, [Obj])]
        self.trailer = []
        self.bbox = None
        self.hires_bbox = None

    def objects(self):
        for _, _, objs in self.layers:
            yield from objs

    @property
    def size(self):
        return self.hires_bbox[2], self.hires_bbox[3]


def parse_ai8(text):
    """Parse an AI8/EPS source into the object model."""
    doc = Doc()
    lines = text.splitlines()
    i, n = 0, len(lines)

    while i < n and not lines[i].startswith("%AI5_BeginLayer"):
        if lines[i].startswith("%%BoundingBox:"):
            doc.bbox = [float(v) for v in lines[i].split(":")[1].split()]
        if lines[i].startswith("%%HiResBoundingBox:"):
            doc.hires_bbox = [float(v) for v in lines[i].split(":")[1].split()]
        doc.header.append(lines[i])
        i += 1

    while i < n and lines[i].startswith("%AI5_BeginLayer"):
        i += 1
        lb_line = lines[i]
        layer_name = re.search(r"\(([^)]*)\)\s*Lb\s*$", lb_line).group(1)
        i += 1
        objs, cur = [], None
        while i < n and lines[i] != "LB":
            ln = lines[i]
            m = re.match(r"^%%Note: object (.+)$", ln)
            if m:
                cur = Obj(layer_name, m.group(1))
                objs.append(cur)
                i += 1
                continue
            m = re.match(r"^([-0-9.]+) ([-0-9.]+) ([-0-9.]+) (Xa|XA)$", ln)
            if m and cur is not None:
                cur.color_op = m.group(4)
                cur.emitted_rgb = _rgb255(m.group(k) for k in (1, 2, 3))
                i += 1
                continue
            if ln in ("f", "S") and cur is not None:
                cur.paint_op = ln
                i += 1
                continue
            m = re.match(r"^([-0-9.]+) w$", ln)
            if m and cur is not None:
                cur.width = float(m.group(1))
                i += 1
                continue
            if cur is not None and ln.strip() and not ln.startswith("%"):
                cur.geometry.append(ln)
            i += 1
        i += 1                                    # consume 'LB'
        if i < n and lines[i].startswith("%AI5_EndLayer"):
            i += 1
        doc.layers.append((lb_line, layer_name, objs))

    doc.trailer = lines[i:]
    return doc


def resolve_visible_colors(text):
    """Every visible object's effective colour, as the SOURCE bytes declare it."""
    return [(o.layer, o.name, o.emitted_rgb) for o in parse_ai8(text).objects()]


def all_black(text):
    """The regression probe. The defective source resolves all 40 to black."""
    cols = [c for _, _, c in resolve_visible_colors(text)]
    return bool(cols) and all(c == BLACK for c in cols)


def document_colors(text):
    """The document-level colour declarations, as written in the header."""
    out = {"process": None, "rgb": [], "usage": None}
    for ln in text.splitlines():
        if ln.startswith("%%DocumentProcessColors:"):
            out["process"] = ln.split(":", 1)[1].strip()
        elif ln.startswith("%%DocumentRGBColors:"):
            out["rgb"] = ln.split(":", 1)[1].split()
        elif ln.startswith("%%ColorUsage:"):
            out["usage"] = ln.split(":", 1)[1].strip()
        elif ln.startswith("%AI5_BeginLayer"):
            break
    return out


# --------------------------------------------------------------------------
# A restricted PostScript evaluator
# --------------------------------------------------------------------------
# The point is not to render. The point is to resolve each object's colour by
# *executing* the emitted bytes through the prolog the file itself ships, so
# that a prolog which consumed `r g b` in the wrong order would be caught. A
# byte scan cannot catch that; this can.

_NUM = re.compile(r"^-?\d*\.?\d+$")


def _tokenize(text):
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == "%":
            j = text.find("\n", i)
            i = n if j < 0 else j + 1
        elif c == "(":                       # strings: only ever layer names
            depth, j = 1, i + 1
            while j < n and depth:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            toks.append(("str", text[i + 1:j - 1]))
            i = j
        elif c in "{}":
            toks.append(("punct", c))
            i += 1
        elif c == "/":
            j = i + 1
            while j < n and text[j] not in " \t\r\n{}/()%":
                j += 1
            toks.append(("lit", text[i + 1:j]))
            i = j
        else:
            j = i
            while j < n and text[j] not in " \t\r\n{}/()%":
                j += 1
            w = text[i:j]
            toks.append(("num", float(w)) if _NUM.match(w) else ("exec", w))
            i = j
    return toks


def _parse_procs(toks):
    """Fold {...} into nested procedure objects."""
    out, stack = [], []
    for kind, val in toks:
        target = stack[-1] if stack else out
        if (kind, val) == ("punct", "{"):
            proc = []
            target.append(("proc", proc))
            stack.append(proc)
        elif (kind, val) == ("punct", "}"):
            stack.pop()
        else:
            target.append((kind, val))
    return out


class PSError(Exception):
    pass


class _PS:
    """Just enough PostScript to execute what we emit."""

    def __init__(self):
        self.st = []
        self.dict = {}
        self.paints = []          # (rgb255, kind, detail) in emission order
        self.path_pts = 0
        self.rgb = BLACK

    def run(self, prog):
        for kind, val in prog:
            if kind in ("num", "str"):
                self.st.append(val)
            elif kind == "lit":
                self.st.append(("name", val))
            elif kind == "proc":
                self.st.append(("proc", val))
            elif kind == "exec":
                self._op(val)

    def _pop(self):
        if not self.st:
            raise PSError("stack underflow")
        return self.st.pop()

    def _num(self):
        v = self._pop()
        if not isinstance(v, (int, float)):
            raise PSError(f"expected number, got {v!r}")
        return v

    def _op(self, w):
        d, st = self.dict, self.st
        if w in d:
            body = d[w]
            if isinstance(body, tuple) and body[0] == "proc":
                self.run(body[1])
            else:
                st.append(body)
            return
        if w == "def":
            v = self._pop()
            k = self._pop()
            if not (isinstance(k, tuple) and k[0] == "name"):
                raise PSError("def without a name")
            d[k[1]] = v
        elif w == "bind":
            pass
        elif w == "exch":
            a, b = self._pop(), self._pop()
            st += [a, b]
        elif w == "dup":
            v = self._pop()
            st += [v, v]
        elif w == "pop":
            self._pop()
        elif w == "repeat":
            proc = self._pop()
            cnt = int(self._num())
            for _ in range(cnt):
                self.run(proc[1])
        elif w == "if":
            proc, cond = self._pop(), self._pop()
            if cond:
                self.run(proc[1])
        elif w == "ifelse":
            b, a, cond = self._pop(), self._pop(), self._pop()
            self.run((a if cond else b)[1])
        elif w == "eq":
            st.append(self._pop() == self._pop())
        elif w == "ne":
            st.append(self._pop() != self._pop())
        elif w == "true":
            st.append(True)
        elif w == "false":
            st.append(False)
        elif w == "setrgbcolor":
            b, g, r = self._num(), self._num(), self._num()
            self.rgb = _rgb255((r, g, b))
        elif w == "setlinewidth":
            self.lw = self._num()
        elif w == "moveto" or w == "lineto":
            self._num(), self._num()
            self.path_pts += 1
        elif w == "curveto":
            for _ in range(6):
                self._num()
            self.path_pts += 1
        elif w in ("closepath", "newpath"):
            pass
        elif w == "fill":
            self.paints.append((self.rgb, "fill", "nonzero"))
        elif w == "eofill":
            self.paints.append((self.rgb, "fill", "evenodd"))
        elif w == "stroke":
            self.paints.append((self.rgb, "stroke", getattr(self, "lw", None)))
        elif w in ("gsave", "grestore", "showpage"):
            pass
        else:
            raise PSError(f"unknown operator {w!r}")


def ps_resolve(text):
    """Execute the emitted bytes; return every paint in emission order.

    Returns ``[(rgb255, kind, detail), ...]`` where kind is 'fill' or 'stroke'
    and detail is the winding rule or the stroke width. Raises
    :class:`PSError` if the file is not executable PostScript.
    """
    ps = _PS()
    body = "\n".join(
        ln for ln in text.splitlines()
        if not ln.startswith(("%!", "%%", "%AI")))
    ps.run(_parse_procs(_tokenize(body)))
    return ps.paints


def ps_resolve_in_order(text):
    """Per-object executed colour, paired back to the object list.

    One paint per object, in order, so this gives an execution-derived colour
    for every object without trusting the byte scan that produced it.
    """
    objs = list(parse_ai8(text).objects())
    paints = ps_resolve(text)
    if len(paints) != len(objs):
        raise PSError(f"{len(paints)} paints for {len(objs)} objects")
    return [(o.layer, o.name, c, kind, detail)
            for o, (c, kind, detail) in zip(objs, paints)]


# --------------------------------------------------------------------------
# AI8/EPS emission
# --------------------------------------------------------------------------

# The defective source shipped an EMPTY %%BeginProlog, so `Xa`, `m`, `C`, `f`
# and the layer operators had no PostScript definition at all — as EPS it could
# not render anywhere, and its colour could never be checked outside
# Illustrator. Defining them costs nothing Illustrator reads (it parses the AI
# operators with its own reader) and makes the bytes verifiable by execution.
#
# `Xa`/`XA` are the documented Illustrator RGB fill/stroke operators, and here
# they are *also* real PostScript that ends in `setrgbcolor`. Whichever reader
# Illustrator uses, the same numbers produce the same colour — the choice is
# not a bet on one parser.
PROLOG = """%%BeginProlog
/_fr 0 def /_fg 0 def /_fb 0 def
/_sr 0 def /_sg 0 def /_sb 0 def
/_eo true def
/Xa { /_fb exch def /_fg exch def /_fr exch def } bind def
/XA { /_sb exch def /_sg exch def /_sr exch def } bind def
/XR { 1 eq /_eo exch def } bind def
/m { moveto } bind def
/L { lineto } bind def
/C { curveto } bind def
/h { closepath } bind def
/f { _fr _fg _fb setrgbcolor _eo { eofill } { fill } ifelse } bind def
/S { _sr _sg _sb setrgbcolor stroke } bind def
/w { setlinewidth } bind def
/Lb { 17 { pop } repeat } bind def
/LB { } bind def
%%EndProlog"""


def serialize_ai8(doc, title="VQ2-A2-R2-FINAL-GATE-A-R1"):
    """Emit AI8/EPS with every visible object carrying its authoritative colour.

    Colour is written at emission time from the object's role, so an object
    cannot reach the file with an unassigned or defaulted colour.
    """
    rgb_list = " ".join(sorted({hexs(c) for c in FLAT_COLORS.values()}))
    out = []
    for ln in doc.header:
        if ln.startswith("%%DocumentProcessColors:"):
            # The document contains no CMYK process ink. Declaring "Black" here
            # while emitting RGB is exactly the false declaration that let the
            # all-black emission look plausible.
            continue
        if ln.startswith("%%Title:"):
            out.append(f"%%Title: ({title})")
            continue
        if ln.startswith("%%ColorUsage:"):
            out.append("%%ColorUsage: Color")
            # An informational inventory of the four flat colours, not a claim
            # of DSC conformance: hex is not a DSC numeric convention and no
            # Adobe-authored AI8 EPS was available here to check the key's
            # spelling against. Comments are skipped by every consumer, and the
            # authoritative colour lives in the per-object Xa/XA operators.
            out.append(f"%%DocumentRGBColors: {rgb_list}")
            # ASCII only. This is the one file whose Illustrator compatibility
            # is the whole point of Gate A; DSC comments are conventionally
            # 7-bit and an em-dash here buys nothing.
            out.append("%%Note: colour model sRGB concept artwork - not CMYK, "
                       "not Pantone, not spot, no supplier ink authority")
            continue
        if ln == "%%BeginProlog":
            out.append(PROLOG)
            continue
        if ln == "%%EndProlog":
            continue
        if ln == "%%BeginSetup":
            out.append("%%BeginSetup")
            out.append(f"{1 if EVEN_ODD else 0} XR")
            continue
        out.append(ln)

    for lb_line, layer_name, objs in doc.layers:
        out.append("%AI5_BeginLayer")
        out.append(lb_line)
        out.append(f"%%Note: layer {layer_name}")
        for o in objs:
            rgb = o.expected_rgb
            if rgb is None:
                raise ValueError(
                    f"visible object {o.layer}/{o.name} has no assigned colour "
                    "— refusing to emit a black default")
            r, g, b = _norm(rgb)
            out.append(f"%%Note: object {o.name}")
            out.append(f"%%Note: color {hexs(rgb)} role {o.role}")
            out.append(f"{r:.6f} {g:.6f} {b:.6f} {o.color_op}")
            if o.paint_op == "S":
                out.append(f"{DIVIDER_WIDTH_PT:.6f} w")
            out.extend(o.geometry)
            out.append(o.paint_op)
        out.append("LB")
        out.append("%AI5_EndLayer--")

    out.extend(doc.trailer)
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# R2 emission — flat, standard PostScript, no AI operator vocabulary
# --------------------------------------------------------------------------
# R1 opened in Illustrator with its three structure objects painted correctly
# and all 37 artwork objects absent from the visible result. Two explanations
# fit that equally well and this environment cannot separate them: either the
# body ends up stacked above the artwork, or Illustrator dropped everything
# after the third %AI5_BeginLayer block. R2 does not need the answer, because
# it removes the thing both explanations depend on.
#
# There are no layer blocks, so there is no inter-layer stacking to invert and
# no layer boundary to drop. There is one flat paint sequence in the approved
# order, and every object carries its own complete graphics state, so nothing
# inherits colour, line width, clip or transform from the object before it.
#
# The AI operator vocabulary is gone with it. `Xa`, `Lb` and the sixteen-number
# layer line were copied verbatim out of the defective source — which was
# written by the untested throwaway script — so their behaviour in Illustrator
# was never established. R2 uses only operators that have meant the same thing
# since PostScript Level 1.

AI_TO_PS = {"m": "moveto", "L": "lineto", "C": "curveto", "h": "closepath"}

# Operators that would let one object affect the next. R2 emits none of them,
# which is what makes "no leak" checkable rather than asserted.
FORBIDDEN_OPS = ("clip", "eoclip", "initclip", "concat", "translate", "scale",
                 "rotate", "setmatrix", "initmatrix", "showpage", "def",
                 "Xa", "XA", "XR", "Lb", "LB")


def ps_path_lines(obj):
    """The object's geometry with AI operator names spelled out.

    Only the operator token changes. Every coordinate is copied through as the
    accepted source wrote it, so geometry cannot drift here.
    """
    out = []
    for ln in obj.geometry:
        if ln == "h":
            out.append("closepath")
            continue
        m = re.match(r"^([-0-9. ]+)([mLC])$", ln)
        if not m:
            raise ValueError(f"ungrammatical geometry line {ln!r}")
        out.append(f"{m.group(1).rstrip()} {AI_TO_PS[m.group(2)]}")
    return out


def serialize_eps_r2(doc, title="VQ2-A2-R2-FINAL-GATE-A-R2"):
    """Emit a flat, self-contained EPS. One object, one complete state."""
    w, h = doc.size
    bw, bh = doc.bbox[2], doc.bbox[3]
    rgb_list = " ".join(sorted({hexs(c) for c in FLAT_COLORS.values()}))
    out = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        # R1 claimed to be Adobe Illustrator 8.0. It was not, and that claim
        # plausibly routed the file into Illustrator's AI reader, whose layer
        # semantics could never be verified here. Say what actually wrote it.
        "%%Creator: BBROSE Design OS gate_a_corr2 (not Adobe Illustrator)",
        f"%%Title: ({title})",
        f"%%BoundingBox: 0 0 {bw:.0f} {bh:.0f}",
        f"%%HiResBoundingBox: 0 0 {w:.4f} {h:.4f}",
        "%%LanguageLevel: 2",
        "%%DocumentData: Clean7Bit",
        "%%ColorUsage: Color",
        f"%%DocumentRGBColors: {rgb_list}",
        "%%Note: colour model sRGB concept artwork - not CMYK, not Pantone, "
        "not spot, no supplier ink authority",
        "%%Note: flat paint sequence in approved back-to-front order; every "
        "object sets its own colour and restores its own state",
        "%%EndComments",
        "%%BeginProlog",
        "%%EndProlog",
        "%%BeginSetup",
        "%%EndSetup",
    ]
    for _, layer_name, objs in doc.layers:
        out.append(f"%%Note: group {layer_name}")
        for o in objs:
            rgb = o.expected_rgb
            if rgb is None:
                raise ValueError(
                    f"visible object {o.layer}/{o.name} has no assigned colour "
                    "- refusing to emit a black default")
            r, g, b = _norm(rgb)
            out.append(f"%%Note: object {o.name}")
            out.append(f"%%Note: color {hexs(rgb)} role {o.role}")
            out.append("gsave")
            out.append(f"{r:.6f} {g:.6f} {b:.6f} setrgbcolor")
            if o.paint_op == "S":
                out.append(f"{DIVIDER_WIDTH_PT:.6f} setlinewidth")
            out.append("newpath")
            out.extend(ps_path_lines(o))
            out.append("stroke" if o.paint_op == "S"
                       else ("eofill" if EVEN_ODD else "fill"))
            out.append("grestore")
    out += ["%%PageTrailer", "%%Trailer", "%%EOF"]
    return "\n".join(out) + "\n"


def parse_eps_r2(text):
    """Read an R2 source back into the object model, from its own bytes."""
    doc = Doc()
    lines = text.splitlines()
    layer, objs_by_layer, order = None, {}, []
    cur = None
    for i, ln in enumerate(lines):
        if ln.startswith("%%BoundingBox:"):
            doc.bbox = [float(v) for v in ln.split(":")[1].split()]
        elif ln.startswith("%%HiResBoundingBox:"):
            doc.hires_bbox = [float(v) for v in ln.split(":")[1].split()]
        m = re.match(r"^%%Note: group (.+)$", ln)
        if m:
            layer = m.group(1)
            objs_by_layer.setdefault(layer, [])
            order.append(layer)
            continue
        m = re.match(r"^%%Note: object (.+)$", ln)
        if m:
            cur = Obj(layer, m.group(1))
            objs_by_layer[layer].append(cur)
            continue
        if cur is None:
            continue
        m = re.match(r"^([-0-9.]+) ([-0-9.]+) ([-0-9.]+) setrgbcolor$", ln)
        if m:
            cur.emitted_rgb = _rgb255(m.group(k) for k in (1, 2, 3))
            continue
        m = re.match(r"^([-0-9.]+) setlinewidth$", ln)
        if m:
            cur.width = float(m.group(1))
            continue
        if ln in ("eofill", "fill"):
            cur.paint_op = "f"
            continue
        if ln == "stroke":
            cur.paint_op = "S"
            continue
        m = re.match(r"^(.*?)\s*(moveto|lineto|curveto)$", ln)
        if m:
            back = {"moveto": "m", "lineto": "L", "curveto": "C"}[m.group(2)]
            cur.geometry.append(f"{m.group(1)} {back}")
            continue
        if ln == "closepath":
            cur.geometry.append("h")
    doc.layers = [(None, name, objs_by_layer[name]) for name in order]
    return doc


def audit_graphics_state(text):
    """Prove no object can affect the next one, by reading the emitted bytes.

    Every claim §10 makes about leaking state is answered here from the file
    rather than from the code that wrote it.
    """
    lines = [ln for ln in text.splitlines() if not ln.startswith("%")]
    depth, max_depth, errors = 0, 0, []
    objects, colour_set, painted, path_open = 0, 0, 0, False
    has_colour = False
    for ln in lines:
        if ln == "gsave":
            depth += 1
            max_depth = max(max_depth, depth)
            objects += 1
            has_colour = False
        elif ln == "grestore":
            if not has_colour:
                errors.append("object restored without setting a colour")
            if path_open:
                errors.append("object restored with an unpainted path")
            depth -= 1
            if depth < 0:
                errors.append("grestore without gsave")
        elif ln.endswith("setrgbcolor"):
            if depth == 0:
                errors.append("colour set outside a saved state")
            has_colour = True
            colour_set += 1
        elif ln == "newpath":
            path_open = True
        elif ln in ("eofill", "fill", "stroke"):
            if not has_colour:
                errors.append("painted without setting a colour")
            painted += 1
            path_open = False
    for op in FORBIDDEN_OPS:
        if re.search(rf"(?m)(^|\s){re.escape(op)}(\s|$)", "\n".join(lines)):
            errors.append(f"state-affecting operator present: {op}")
    return {
        "objects": objects,
        "colour_set_count": colour_set,
        "paint_count": painted,
        "gsave_grestore_balanced": depth == 0,
        "max_nesting_depth": max_depth,
        "every_object_sets_own_colour": colour_set == objects,
        "every_object_painted": painted == objects,
        "forbidden_operators_present": [e for e in errors if "operator" in e],
        "errors": errors,
        "passed": not errors and depth == 0 and colour_set == objects
        and painted == objects,
    }


# --------------------------------------------------------------------------
# PDF emission from the SAME model — AI8 ops map 1:1 onto PDF ops
# --------------------------------------------------------------------------

AI_TO_PDF = {"m": "m", "L": "l", "C": "c", "h": "h"}
FILL_OP = "f*" if EVEN_ODD else "f"


def content_stream(doc, only=None, skip=None):
    ops = []
    for o in doc.objects():
        if only is not None and o is not only:
            continue
        if skip is not None and o is skip:
            continue
        r, g, b = _norm(o.expected_rgb)
        if o.paint_op == "S":
            ops.append(f"{r:.6f} {g:.6f} {b:.6f} RG")
            ops.append(f"{DIVIDER_WIDTH_PT:.6f} w")
        else:
            ops.append(f"{r:.6f} {g:.6f} {b:.6f} rg")
        for op, nums in o.subpaths():
            if op == "h":
                ops.append("h")
            else:
                ops.append(" ".join(f"{v:.4f}" for v in nums)
                           + " " + AI_TO_PDF[op])
        ops.append(FILL_OP if o.paint_op == "f" else "S")
    return "\n".join(ops)


def pdf_bytes(stream, width, height, mediabox=None):
    """A minimal one-page PDF carrying the model's exact numbers.

    ``mediabox`` overrides the page box, which is how a single object can be
    rastered cropped to itself without moving any coordinate.
    """
    box = mediabox or (0, 0, width, height)
    data = stream.encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (f"<< /Type /Page /Parent 2 0 R /MediaBox "
         f"[{box[0]:.6f} {box[1]:.6f} {box[2]:.6f} {box[3]:.6f}] "
         f"/Contents 4 0 R /Resources << >> >>").encode("latin-1"),
        b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data
        + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


def build_pdf(doc, path):
    w, h = doc.size
    data = pdf_bytes(content_stream(doc), w, h)
    with open(path, "wb") as fh:
        fh.write(data)
    return len(data)


def render_png(pdf_path, png_path, height_px=PROOF_HEIGHT_PX):
    """Raster the PDF itself, so the PNG cannot carry a different colour.

    The zoom is driven by height so the raster lands on the accepted proof's
    exact 576x1371. Deriving it from width instead rounds the height up to
    1372 — a uniform scale either way, but one of them matches the approved
    artefact and the other invites a needless question.
    """
    import fitz
    doc = fitz.open(pdf_path)
    page = doc[0]
    zoom = height_px / page.rect.height
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    pix.save(png_path)
    size = (pix.width, pix.height)
    doc.close()
    return size


# --------------------------------------------------------------------------
# Rendering helpers used to sample real pixels
# --------------------------------------------------------------------------

def _raster(pdf_data, width_px=PROOF_WIDTH_PX):
    import fitz
    d = fitz.open(stream=pdf_data, filetype="pdf")
    page = d[0]
    zoom = width_px / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    out = (bytes(pix.samples), pix.width, pix.height, pix.n)
    d.close()
    return out


def _pixel_histogram(samples, n):
    hist = {}
    for i in range(0, len(samples), n):
        px = tuple(samples[i:i + 3])
        hist[px] = hist.get(px, 0) + 1
    return hist


def object_bbox(obj):
    """The extent of an object's own coordinates, control points included."""
    xs, ys = [], []
    for _, nums in obj.subpaths():
        for i in range(0, len(nums), 2):
            xs.append(nums[i])
            ys.append(nums[i + 1])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def render_object(doc, obj, target_px=240, pad=2.0):
    """Raster one object alone, cropped to itself, at a chosen resolution.

    Cropping matters: at page scale a 4 pt glyph is a handful of antialiased
    pixels and never reaches its own flat colour, which says nothing about the
    colour it was given.
    """
    bb = object_bbox(obj)
    if bb is None:
        return {}, 0.0
    x0, y0 = bb[0] - pad, bb[1] - pad
    x1, y1 = bb[2] + pad, bb[3] + pad
    span = max(x1 - x0, y1 - y0)
    zoom = target_px / span
    data = pdf_bytes(content_stream(doc, only=obj), x1 - x0, y1 - y0,
                     mediabox=(x0, y0, x1, y1))
    samples, pw, ph, n = _raster(data, max(1, round((x1 - x0) * zoom)))
    hist = _pixel_histogram(samples, n)
    hist.pop(WHITE, None)
    return hist, zoom


def blend_residual(px, expected, bg=WHITE):
    """Distance from the bg->expected blend line, in 8-bit steps.

    Every antialiased pixel of a flat-filled object must be a mix of the
    background and that object's colour. A pixel off that line came from some
    other colour — which is exactly what a black default looks like.
    """
    ts, spread = [], 0
    for c, e, b in zip(px, expected, bg):
        if b == e:
            continue
        ts.append((b - c) / (b - e))
    if not ts:
        return 0
    t = sum(ts) / len(ts)
    for c, e, b in zip(px, expected, bg):
        spread = max(spread, abs(c - (b + t * (e - b))))
    return spread


def sample_object_color(doc, obj, target_px=240, tolerance=None):
    """What this object actually rasterises to, and whether that is its colour.

    Returns the modal non-background pixel, the pixel count, the worst
    departure from the blend line, and the flat colour if the raster reaches
    it. Escalating resolution is what lets a 4 pt glyph prove its own fill.
    """
    if tolerance is None:
        tolerance = RASTER_QUANTISATION_TOLERANCE
    expected = obj.expected_rgb
    hist, zoom = render_object(doc, obj, target_px)
    if not hist:
        return {"modal": None, "pixels": 0, "blend_residual": None,
                "realised": None, "zoom": zoom}
    modal = max(hist.items(), key=lambda kv: kv[1])[0]
    worst = max(blend_residual(px, expected) for px in hist)

    realised, used = None, zoom
    for tp in (target_px, target_px * 4, target_px * 16):
        h2, z2 = render_object(doc, obj, tp)
        hit = [px for px in h2
               if all(0 <= e - c <= tolerance for c, e in zip(px, expected))]
        if hit:
            realised, used = hit[0], z2
            break
    return {"modal": modal, "pixels": sum(hist.values()),
            "blend_residual": round(worst, 2), "realised": realised,
            "zoom": round(used, 3)}


def composite_raster(doc, width_px=PROOF_WIDTH_PX):
    w, h = doc.size
    return _raster(pdf_bytes(content_stream(doc), w, h), width_px)[0]


def contributes_to_composite(doc, obj, full=None, width_px=PROOF_WIDTH_PX):
    """Does removing this object change the rendered page?

    A same-colour object hidden entirely under another would make no
    difference, and asking the question this way needs no assumption about
    which pixel the object owns.
    """
    w, h = doc.size
    if full is None:
        full = composite_raster(doc, width_px)
    less = _raster(pdf_bytes(content_stream(doc, skip=obj), w, h),
                   width_px)[0]
    if full == less:
        return False, 0
    return True, sum(1 for a, b in zip(full, less) if a != b)


# --------------------------------------------------------------------------
# Colour-capability fixture
# --------------------------------------------------------------------------

def capability_fixture():
    """Four rectangles, one per accepted flat colour.

    The smallest thing that can answer "does a colour survive the whole
    pipeline" independently of the artwork.
    """
    doc = Doc()
    doc.bbox = [0.0, 0.0, 240.0, 60.0]
    doc.hires_bbox = [0.0, 0.0, 240.0, 60.0]
    doc.header = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        "%%Creator: Adobe Illustrator(R) 8.0",
        "%%AI8_CreatorVersion: 8.0",
        "%%Title: (AI8-COLOR-CAPABILITY-FIXTURE)",
        "%%BoundingBox: 0 0 240 60",
        "%%HiResBoundingBox: 0 0 240.0000 60.0000",
        "%%DocumentProcessColors: Black",
        "%%ColorUsage: Color",
        "%%EndComments",
        "%%BeginProlog",
        "%%EndProlog",
        "%%BeginSetup",
        "%%EndSetup",
    ]
    lb = ("1 1 1 1 0 0 0 79 128 255 0 0 0 0 0 0 (00_CAPABILITY_FIXTURE) Lb")
    objs = []
    for i, role in enumerate(["BODY", "COLLAR", "CLOSURE", "ARTWORK"]):
        x0, x1 = i * 60.0, i * 60.0 + 60.0
        o = Obj("00_CAPABILITY_FIXTURE", f"SWATCH_{role}", role=role)
        o.color_op, o.paint_op = "Xa", "f"
        o.geometry = [
            f"{x0:.4f} 0.0000 m",
            f"{x1:.4f} 0.0000 L",
            f"{x1:.4f} 60.0000 L",
            f"{x0:.4f} 60.0000 L",
            "h",
        ]
        objs.append(o)
    doc.layers = [(lb, "00_CAPABILITY_FIXTURE", objs)]
    doc.trailer = ["%%PageTrailer", "%%Trailer", "%%EOF"]
    return doc


# The rasteriser quantises a PDF colour component downwards by up to one 8-bit
# step: 0.850980 * 255 = 216.99999, which floors to 216 (#D8) rather than 217
# (#D9). This is not a serialization defect and it is not corrected here,
# because the ACCEPTED proof PNG carries exactly the same four quantised values
# — #D8BCB5, #705242, #492F34, #4F2424 — so those pixels are the approved
# appearance. The source bytes carry the exact accepted sRGB; the raster is
# allowed to sit one step below it, and only in that direction.
RASTER_QUANTISATION_TOLERANCE = 1
ACCEPTED_PROOF_PIXELS = {
    "BODY": (0xD8, 0xBC, 0xB5),
    "COLLAR": (0x70, 0x52, 0x42),
    "CLOSURE": (0x49, 0x2F, 0x34),
    "ARTWORK": (0x4F, 0x24, 0x24),
}


def capability_report(tolerance=RASTER_QUANTISATION_TOLERANCE):
    """Emit the fixture, execute it, raster it, compare all four readings."""
    doc = capability_fixture()
    text = serialize_ai8(doc, title="AI8-COLOR-CAPABILITY-FIXTURE")
    scanned = {name: rgb for _, name, rgb in resolve_visible_colors(text)}
    executed = {name: rgb for _, name, rgb, _, _ in ps_resolve_in_order(text)}
    rows, ok = [], True
    for o in doc.objects():
        s = sample_object_color(doc, o)
        rendered, px = s["modal"], s["pixels"]
        exp = o.expected_rgb
        row = {
            "object": o.name,
            "role": o.role,
            "expected": hexs(exp),
            "emitted_operator":
                "%.6f %.6f %.6f %s" % (_norm(exp) + (o.color_op,)),
            "emitted_numeric": list(_norm(exp)),
            "scanned_from_bytes": hexs(scanned[o.name]),
            "executed_postscript": hexs(executed[o.name]),
            "rendered_pixel": hexs(rendered) if rendered else None,
            "rendered_pixel_count": px,
            "accepted_proof_pixel": hexs(ACCEPTED_PROOF_PIXELS[o.role]),
            "matches_accepted_proof_pixel":
                rendered == ACCEPTED_PROOF_PIXELS[o.role],
            "tolerance": tolerance,
        }
        row["pass"] = (
            scanned[o.name] == exp
            and executed[o.name] == exp
            and rendered is not None
            # quantisation may only lose up to one step, never gain: a colour
            # rendering ABOVE its declared value is a real defect
            and all(0 <= e - r <= tolerance for r, e in zip(rendered, exp))
            and rendered == ACCEPTED_PROOF_PIXELS[o.role]
        )
        ok = ok and row["pass"]
        rows.append(row)
    return {
        "record_type": "ai8_color_capability_fixture/1.0",
        "purpose": "prove a colour survives emission, execution and raster "
                   "before trusting the artwork pipeline with it",
        "swatches": rows,
        "tolerance": tolerance,
        "passed": ok,
        "failure_codes": [] if ok else [
            "AI8_RGB_OPERATOR_NOT_PRESERVED",
            "AI8_OBJECT_COLOR_DEFAULTED_TO_BLACK",
            "AI8_COLOR_SERIALIZATION_VALUE_MISMATCH",
        ],
    }
