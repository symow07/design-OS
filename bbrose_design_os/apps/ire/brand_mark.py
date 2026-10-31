"""THE HOUSE MARK FROM AN APPROVED VECTOR MASTER — the switch, BUILT now and THROWN later by one data-only act.

THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I start
testing"), bug 3: "When I approve the logo trace, switch the mark to it so gold foil can print." The executor's
reading, transcribed at :23856: the mark is drawn from a vector master when an approved one is on file, and foil may
print on it; without one the mark stays the PNG and foil stays refused by name; built and proved with a test master,
and his trace goes on file only on his word. He has not approved the trace. Nothing here places it.

WHERE AN APPROVED MASTER LIVES. ``docs/brand/mark/bbrose-logo.svg`` beside ``docs/brand/mark/approval.json``, under
BASE_DIR and TRACKED — never ``media/``, which ``.gitignore:33`` ignores wholesale. The approval record carries the
master's sha256, his words verbatim with the register line and the date, the source PNG and its sha256, the tracer and
its settings, and the emitter-vs-MuPDF match score; ``tools/brand_mark_place.py`` writes both files from the SVG he
approves and his quoted words (a REHEARSAL outside the repository by default; ``--place`` for the live folder).

PLACING TAKES EFFECT IN EVERY RUNNING PROCESS AT ONCE. ``approved_master`` reads those two files afresh on every call
— every composition, in the web server, every worker and every exploration — so the moment they are written into
``docs/brand/mark/`` every running process draws the vector mark at its next composition. No restart and no commit is
needed for that; the data-only commit records it, and removing the two files undoes it at once in the same way. The
VQ2 record under ``docs/visual_quality/vq2/`` (053d54e, a different drawing) is not an approval of this master and
nothing here reads it.

THE STATES — one draws the vector, and every other draws exactly what was drawn before this module existed:
  * NO_APPROVAL_ON_FILE: the PNG; the lockup's foil stays REFUSED_NO_VECTOR_MASTER by name; every output
    byte-identical, because no composer is handed a master and nothing below touches a document without one.
  * APPROVAL_ON_FILE_REFUSED: the PNG, plus the named code(s) in ``codes`` — the record UNREADABLE (it does not read
    or parse; the OS error named), INCOMPLETE (the fields it lacks named), its MATCH_FAILED, the master MISSING (not
    found — nothing else is called missing) or UNREADABLE (its OS error named), its SHA_MISMATCH, or a grammar the
    approval did not cover (REFUSED, by the grammar's own name).
  * APPROVED_VECTOR_MASTER: the mark is placed as an ``AssetRef`` named as the raster it replaces, in the box the
    raster would get with the height read from the MASTER's ink bounds; ``expand`` turns it into the master's own
    outlines, filled by the nonzero winding rule, when the emitter draws it — page 1 and every plate — and when a
    handoff graph is serialised. Every instrument keeps reading the box, and the mark's own outlines never stand in
    its own clear space.
  * UPLOADED_LOGO_STAYS_RASTER: a task's uploaded logo is its own raster and stays one.
  * APPROVAL_LOOKUP_OFF: the test suite (config/settings.py, conftest.py) — a test is never changed by the owner's
    file being placed; a test that wants the vector mark hands a composer a master of its own.

THE GRAMMAR THE APPROVAL COVERS, and nothing else — checked on the RAW BYTES first (UTF-8; at most potrace's own XML
declaration and SVG 1.0 DOCTYPE; no other processing instruction, comment, CDATA or DTD declaration), then on the
parsed tree: potrace's (at most ONE ``<g transform="translate(x,y) scale(sx,sy)">`` of flat-filled paths, relative
m/l/c/z with repeated arguments — both real traces hold exactly one) and the ® redraw's (absolute M/L/C/Z paths with
``fill-rule="nonzero"`` beside the group), every number ASCII, finite and within ten million. Anything the approval
did not cover is refused BY NAME: an image, a link, text, a stroke, a second fill colour, a second group, any other
transform, element, attribute or path command, a number out of range.

Pure: no ORM, no network; Django's settings are read at call time only (``lookup_enabled``, ``approved_master``).
"""
from __future__ import annotations

import datetime
import errno
import hashlib
import json
import math
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

SCHEMA = "brand_mark_selection/1.0"
APPROVAL_SCHEMA = "brand_mark_approval/1.0"
RULING = ('THE OWNER\'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803, the block headed "Before I '
          'start testing"): "When I approve the logo trace, switch the mark to it so gold foil can print."')

#: where the approved master and its approval record live, under BASE_DIR
MARK_DIR = ("docs", "brand", "mark")
MASTER_FILE = "bbrose-logo.svg"
APPROVAL_FILE = "approval.json"
#: an AssetRef naming an approved master: ``brand-mark:<sha256 of the master file's bytes>``
ASSET_PREFIX = "brand-mark:"
#: the zone label a composer records for the mark drawn from its master (the raster's is "front-controlled-fallback")
ZONE_USED = "front-approved-vector-master"
#: the flag a vector-art mark carries in its name where the raster carries BRAND_LOGO_RASTER_FALLBACK
VECTOR_MASTER_FLAG = "BRAND_MARK_VECTOR_MASTER"

# the states of the switch
NO_APPROVAL = "NO_APPROVAL_ON_FILE"
LOOKUP_OFF = "APPROVAL_LOOKUP_OFF"
UPLOADED = "UPLOADED_LOGO_STAYS_RASTER"
APPROVED = "APPROVED_VECTOR_MASTER"
REFUSED = "APPROVAL_ON_FILE_REFUSED"

# the codes a record that does not hold carries — the PNG is drawn and the lockup's foil stays refused. Each names
# only what was measured (§BH58(e): a handler may not assert a cause it did not measure)
#: approval.json does not read (its OS error named) or does not parse as a JSON object
CODE_APPROVAL_UNREADABLE = "BRAND_MARK_APPROVAL_UNREADABLE"
#: approval.json parses and lacks, or malforms, fields it must carry — each named
CODE_APPROVAL_INCOMPLETE = "BRAND_MARK_APPROVAL_INCOMPLETE"
#: approval.json records its emitter-vs-MuPDF match as not passed
CODE_APPROVAL_MATCH_FAILED = "BRAND_MARK_APPROVAL_MATCH_FAILED"
#: the master file is not found (FileNotFoundError, and nothing else)
CODE_MASTER_MISSING = "BRAND_MARK_MASTER_MISSING"
#: the master file is there and does not read — its OS error named
CODE_MASTER_UNREADABLE = "BRAND_MARK_MASTER_UNREADABLE"
CODE_SHA_MISMATCH = "BRAND_MARK_MASTER_SHA_MISMATCH"
CODE_MASTER_REFUSED = "BRAND_MARK_MASTER_REFUSED"
#: an AssetRef naming a master neither in hand nor approved on file: refused at the emitter, never drawn as nothing
CODE_UNRESOLVED = "BRAND_MARK_UNRESOLVED"

# the grammar's refusals, by name
NOT_SVG = "NOT_SVG"
NOT_UTF8 = "NOT_UTF8"
BYTE_ORDER_MARK = "BYTE_ORDER_MARK"
PROCESSING_INSTRUCTION = "PROCESSING_INSTRUCTION"
COMMENT = "COMMENT"
CDATA = "CDATA"
DOCTYPE = "DOCTYPE"
ENTITY = "ENTITY"
NUMBER = "NUMBER"
IMAGE = "IMAGE"
LINK = "LINK"
TEXT = "TEXT"
STROKE = "STROKE"
SECOND_FILL_COLOUR = "SECOND_FILL_COLOUR"
FILL = "FILL"
FILL_RULE = "FILL_RULE"
TRANSFORM = "TRANSFORM"
ELEMENT = "ELEMENT"
ATTRIBUTE = "ATTRIBUTE"
PATH_COMMAND = "PATH_COMMAND"
PATH_DATA = "PATH_DATA"
NO_INK = "NO_INK"

#: the cap band is measured on the master rasterised at this many pixels of INK height — the live mark's own raster
#: height (media/brand/logo.png is 1439 x 300), so the two bands are read at one scale
CAP_BAND_RASTER_PX = 300
#: straight pieces a cubic is cut into for the cap-band raster (the drawn mark is never flattened)
_FLATTEN_STEPS = 16


class MarkRefused(ValueError):
    """A master the approval does not cover — or a mark no master resolves — refused BY NAME: ``reason`` is one of
    the names above, ``detail`` says where."""

    def __init__(self, reason: str, detail: str):
        super().__init__(f"{reason}: {detail}")
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True, eq=False)
class Master:
    """A vector master, read. ``subpaths`` hold the master's outlines in its own user space (y down, the ``<g>``
    transform applied), each a tuple of ops — ``("M", x, y)``, ``("L", x, y)``, ``("C", x1, y1, x2, y2, x, y)``,
    ``("Z",)`` — in the file's order and direction. ``bounds`` is the INK: the outlines' own extent, curve extrema
    solved exactly, never a control hull and never the viewBox."""
    sha256: str
    path: str
    fill: str
    subpaths: tuple
    bounds: tuple
    census: dict = field(default_factory=dict)

    @property
    def asset_id(self) -> str:
        return ASSET_PREFIX + self.sha256

    @property
    def aspect(self) -> float:
        """``height / width`` of the INK — the placed box's aspect. A padded viewBox is not the mark: potrace's
        viewBox is the traced PNG's whole canvas, 1397 x 305 with ~8 px of air, while the ink is 1381 x 289."""
        x0, y0, x1, y1 = self.bounds
        return (y1 - y0) / (x1 - x0)


#: every master read or placed in this process, by the sha256 of its bytes — how ``expand`` finds the master a mark
#: names. ONE rule, ``_register``: the master most recently read or placed is the entry (same bytes, same outlines).
_REGISTRY: dict = {}
#: the cap band of every master measured in this process, by sha256
_BANDS: dict = {}


# ---------------------------------------------------------------------------------------------------------------------
# READING — the strict grammar check and the outlines
# ---------------------------------------------------------------------------------------------------------------------

_SVG_NS = "{http://www.w3.org/2000/svg}"
#: every pattern is ASCII-only (``re.ASCII``): a Unicode digit or space — which ``\d``/``\s`` otherwise match, and which
#: ``float`` would read — is refused, never read as a number
_NUM = r"[-+]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][-+]?[0-9]+)?"
_TRANSFORM_RE = re.compile(r"^\s*translate\(\s*(%s)\s*[,\s]\s*(%s)\s*\)\s*scale\(\s*(%s)\s*(?:[,\s]\s*(%s)\s*)?\)\s*$"
                           % (_NUM, _NUM, _NUM, _NUM), re.ASCII)
_TOKEN_RE = re.compile(r"[\s,]*(?:([A-Za-z])|(%s))" % _NUM, re.ASCII)
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$", re.ASCII)
#: no number past this magnitude is read — potrace's own integers for the 1397 px wordmark reach 111,760
_MAX_MAGNITUDE = 1e7
#: the only XML declaration covered: potrace's own (UTF-8 the only encoding it may name), at the file's first byte
_XML_DECL_RE = re.compile(r'<\?xml\s+version="1\.0"(?:\s+encoding="(?:UTF-8|utf-8)")?(?:\s+standalone="(?:yes|no)")?\s*\?>',
                          re.ASCII)
#: the only DOCTYPE covered: potrace's SVG 1.0 public DTD, whitespace aside — no internal subset, no other identifier
_POTRACE_DOCTYPE = ('<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 20010904//EN" '
                    '"http://www.w3.org/TR/2001/REC-SVG-20010904/DTD/svg10.dtd">')
#: the attributes each covered element may carry; everything else is refused by name
_ATTRIBUTES = {"svg": {"version", "width", "height", "viewBox", "preserveAspectRatio"},
               "metadata": set(),
               "g": {"transform", "fill", "stroke"},
               "path": {"d", "fill", "fill-rule", "stroke"}}
_ARGS = {"M": 2, "L": 2, "C": 6}


def _local(el) -> str:
    tag = el.tag if isinstance(el.tag, str) else ""
    if not tag.startswith(_SVG_NS):
        raise MarkRefused(ELEMENT, f"<{tag}> is not an SVG element")
    return tag[len(_SVG_NS):]


def _check_attributes(el, name: str) -> None:
    for key, value in el.attrib.items():
        if key == "href" or key.endswith("}href"):
            raise MarkRefused(LINK, f"<{name}> carries a link ({key}={value!r})")
        if key.startswith("{"):
            raise MarkRefused(ATTRIBUTE, f"<{name}> carries {key}")
        if key.startswith("stroke"):
            if key == "stroke" and value.strip() == "none" and name in ("g", "path"):
                continue
            raise MarkRefused(STROKE, f"<{name}> {key}={value!r}")
        if key == "transform" and name != "g":
            raise MarkRefused(TRANSFORM, f"<{name}> transform={value!r}")
        if key == "fill-rule" and value.strip() != "nonzero":
            raise MarkRefused(FILL_RULE, f"<{name}> fill-rule={value!r} (the approval covers nonzero)")
        if key == "preserveAspectRatio" and value.strip() != "xMidYMid meet":
            raise MarkRefused(ATTRIBUTE, f"<{name}> preserveAspectRatio={value!r}")
        if key not in _ATTRIBUTES[name]:
            raise MarkRefused(ATTRIBUTE, f"<{name}> {key}={value!r}")


def _check_no_text(el, name: str) -> None:
    for chunk in (el.text, el.tail):
        if chunk is not None and chunk.strip():
            raise MarkRefused(TEXT, f"character data in or after <{name}>: {chunk.strip()[:40]!r}")


def _number(text: str) -> float:
    """A number the grammar read (ASCII already), refused BY NAME when it is not finite or past ``_MAX_MAGNITUDE``."""
    value = float(text)
    if not math.isfinite(value) or abs(value) > _MAX_MAGNITUDE:
        raise MarkRefused(NUMBER, f"{text!r} is not a finite number within {_MAX_MAGNITUDE:g}")
    return value


def _transform(value):
    """``(tx, ty, sx, sy)`` of the one transform the approval covers — ``translate(tx,ty) scale(sx[,sy])``."""
    if value is None:
        return (0.0, 0.0, 1.0, 1.0)
    m = _TRANSFORM_RE.match(value)
    if m is None:
        raise MarkRefused(TRANSFORM, f"transform={value!r} (the approval covers translate(x,y) scale(sx,sy))")
    tx, ty, sx, sy = m.groups()
    out = (_number(tx), _number(ty), _number(sx), _number(sx if sy is None else sy))
    if out[2] == 0.0 or out[3] == 0.0:
        raise MarkRefused(TRANSFORM, f"transform={value!r} scales to nothing")
    return out


def _fill_of(value, inherited: str) -> str:
    if value is None:
        return inherited
    if not _HEX_RE.match(value.strip()):
        raise MarkRefused(FILL, f"fill={value!r} (the approval covers one flat #RRGGBB fill)")
    return value.strip().upper()


def _tokens(d: str) -> list:
    out, pos = [], 0
    d = d.rstrip(" \t\r\n,")
    while pos < len(d):
        m = _TOKEN_RE.match(d, pos)
        if m is None or m.end() == pos:
            raise MarkRefused(PATH_DATA, f"unreadable path data at {pos}: {d[pos:pos + 20]!r}")
        out.append(m.group(1) if m.group(1) is not None else _number(m.group(2)))
        pos = m.end()
    return out


def _parse_d(d: str, xform) -> tuple[list, int, int]:
    """The subpaths of one ``d`` in user space, and its curve and line counts. SVG's own rules: pairs after a moveto
    are linetos; a command's arguments repeat; after a closepath the current point is the subpath's start, and a
    drawing command there starts a new subpath from it."""
    tx, ty, sx, sy = xform

    def at(x, y):
        return (tx + sx * x, ty + sy * y)

    subpaths, cur = [], None
    cx = cy = start_x = start_y = 0.0
    closed, cmd, pending, curves, lines = False, None, False, 0, 0
    tokens, i = _tokens(d), 0
    while i < len(tokens):
        tok = tokens[i]
        if isinstance(tok, str):
            if pending:
                raise MarkRefused(PATH_DATA, f"{cmd!r} carries no arguments")
            if tok.upper() not in "MLCZ":
                raise MarkRefused(PATH_COMMAND, f"{tok!r} (the approval covers M, L, C and Z, absolute or relative)")
            cmd, i = tok, i + 1
            if cmd in "Zz":
                if cur is None:
                    raise MarkRefused(PATH_DATA, "a closepath with no subpath")
                cur.append(("Z",))
                cx, cy, closed = start_x, start_y, True
            else:
                pending = True
            continue
        if cmd is None or cmd in "Zz":
            raise MarkRefused(PATH_DATA, f"a number with no command to take it ({tok})")
        n = _ARGS[cmd.upper()]
        args = tokens[i:i + n]
        if len(args) < n or any(isinstance(a, str) for a in args):
            raise MarkRefused(PATH_DATA, f"{cmd!r} needs {n} numbers")
        i, pending = i + n, False
        rel = cmd.islower()
        if cmd in "Mm":
            x, y = args
            if rel:
                x, y = x + cx, y + cy
            cur = [("M",) + at(x, y)]
            subpaths.append(cur)
            cx, cy = start_x, start_y = x, y
            closed = False
            cmd = "l" if rel else "L"            # further pairs after a moveto are linetos
            continue
        if cur is None:
            raise MarkRefused(PATH_DATA, f"{cmd!r} draws before any moveto")
        if closed:                               # a drawing command after a closepath starts from the subpath's start
            cur = [("M",) + at(cx, cy)]
            subpaths.append(cur)
            closed = False
        if cmd in "Ll":
            x, y = args
            if rel:
                x, y = x + cx, y + cy
            cur.append(("L",) + at(x, y))
            cx, cy = x, y
            lines += 1
        else:
            x1, y1, x2, y2, x, y = args
            if rel:
                x1, y1, x2, y2, x, y = x1 + cx, y1 + cy, x2 + cx, y2 + cy, x + cx, y + cy
            cur.append(("C",) + at(x1, y1) + at(x2, y2) + at(x, y))
            cx, cy = x, y
            curves += 1
    if pending:
        raise MarkRefused(PATH_DATA, f"{cmd!r} carries no arguments")
    return subpaths, curves, lines


def _cubic_extrema(p0, p1, p2, p3) -> list:
    """Every value the cubic takes at an interior extremum along one axis — solved, not sampled."""
    a = -p0 + 3 * p1 - 3 * p2 + p3
    b = 2 * (p0 - 2 * p1 + p2)
    c = p1 - p0
    roots = []
    if abs(a) < 1e-12:
        if abs(b) > 1e-12:
            roots.append(-c / b)
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            sq = math.sqrt(disc)
            roots += [(-b + sq) / (2 * a), (-b - sq) / (2 * a)]
    out = []
    for t in roots:
        if 0.0 < t < 1.0:
            u = 1.0 - t
            out.append(u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3)
    return out


def ink_bounds(subpaths) -> tuple:
    """``(x0, y0, x1, y1)`` the outlines actually ink: every on-curve point and every curve's interior extrema."""
    xs, ys = [], []
    for sub in subpaths:
        px = py = None
        for op in sub:
            if op[0] in ("M", "L"):
                px, py = op[1], op[2]
                xs.append(px)
                ys.append(py)
            elif op[0] == "C":
                _o, x1, y1, x2, y2, x, y = op
                if px is not None:
                    xs.extend(_cubic_extrema(px, x1, x2, x))
                    ys.extend(_cubic_extrema(py, y1, y2, y))
                px, py = x, y
                xs.append(x)
                ys.append(y)
            elif sub and sub[0][0] == "M":
                px, py = sub[0][1], sub[0][2]
    if not xs:
        raise MarkRefused(NO_INK, "no outline to draw")
    return (min(xs), min(ys), max(xs), max(ys))


def _check_raw(data: bytes) -> None:
    """What the parsed tree cannot show, read off the RAW BYTES: UTF-8 without a byte-order mark; at most potrace's
    own XML declaration, first; at most potrace's own SVG 1.0 DOCTYPE; no other processing instruction, no comment,
    no CDATA section and no other DTD declaration (an ENTITY above all)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MarkRefused(NOT_UTF8, f"the file is not UTF-8 ({exc.reason} at byte {exc.start})") from exc
    if text.startswith("\ufeff"):
        raise MarkRefused(BYTE_ORDER_MARK, "the file begins with a byte-order mark the approval did not cover")
    declaration = _XML_DECL_RE.match(text)
    rest = text if declaration is None else text[declaration.end():]
    if "<?" in rest:
        at = rest.index("<?")
        raise MarkRefused(PROCESSING_INSTRUCTION, f"{rest[at:at + 40]!r} (the approval covers potrace's own XML "
                                                  "declaration, first, and nothing else)")
    if "<!--" in text:
        raise MarkRefused(COMMENT, "the file holds a comment")
    if "<![CDATA[" in text:
        raise MarkRefused(CDATA, "the file holds a CDATA section")
    if re.search(r"<!ENTITY|<!ELEMENT|<!ATTLIST|<!NOTATION", text):
        raise MarkRefused(ENTITY, "the file declares an ENTITY or another DTD component")
    doctypes = [m.start() for m in re.finditer(r"<!DOCTYPE", text)]
    others = [m.start() for m in re.finditer(r"<!(?!DOCTYPE)", text)]
    if others:
        raise MarkRefused(DOCTYPE, f"{text[others[0]:others[0] + 40]!r} is a declaration the approval did not cover")
    if len(doctypes) > 1:
        raise MarkRefused(DOCTYPE, "the file holds more than one DOCTYPE")
    if doctypes:
        end = text.find(">", doctypes[0])
        found = " ".join(text[doctypes[0]:end + 1].split()) if end != -1 else text[doctypes[0]:doctypes[0] + 60]
        if found != _POTRACE_DOCTYPE:
            raise MarkRefused(DOCTYPE, f"{found[:120]!r} (the approval covers potrace's SVG 1.0 DOCTYPE only)")


def _register(master) -> None:
    """The ONE registry rule, for ``read_master`` and ``mark_node`` alike: the master most recently read or placed is
    the entry for its sha256."""
    _REGISTRY[master.sha256] = master


def read_master(data: bytes, *, path: str = "") -> Master:
    """The master in ``data``, checked against the grammar the approval covers — its raw bytes first, then its parsed
    tree — and read into outlines; refused BY NAME (``MarkRefused``) for anything else. Registered, so a mark that
    names it is drawn from it."""
    _check_raw(data)
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise MarkRefused(NOT_SVG, f"the file does not parse as XML ({exc})") from exc
    if _local(root) != "svg":
        raise MarkRefused(NOT_SVG, f"the root element is <{_local(root)}>, not <svg>")
    _check_attributes(root, "svg")
    _check_no_text(root, "svg")
    fills: set = set()
    subpaths: list = []
    census = {"paths": 0, "subpaths": 0, "curves": 0, "lines": 0}

    def take(path_el, xform, inherited):
        _check_attributes(path_el, "path")
        _check_no_text(path_el, "path")
        if len(path_el):
            raise MarkRefused(ELEMENT, f"<path> holds <{_local(path_el[0])}>")
        fill = _fill_of(path_el.get("fill"), inherited)
        d = path_el.get("d")
        if d is None:
            raise MarkRefused(PATH_DATA, "a <path> with no d")
        subs, curves, lines = _parse_d(d, xform)
        fills.add(fill)
        subpaths.extend(subs)
        census["paths"] += 1
        census["subpaths"] += len(subs)
        census["curves"] += curves
        census["lines"] += lines

    groups = 0
    for child in root:
        name = _local(child)
        if name == "metadata":
            _check_attributes(child, "metadata")
            if len(child):
                raise MarkRefused(ELEMENT, f"<metadata> holds <{_local(child[0])}>")
            if child.tail is not None and child.tail.strip():
                raise MarkRefused(TEXT, f"character data after <metadata>: {child.tail.strip()[:40]!r}")
        elif name == "g":
            groups += 1
            if groups > 1:
                raise MarkRefused(ELEMENT, "a second <g> (the approval covers potrace's one group)")
            _check_attributes(child, "g")
            _check_no_text(child, "g")
            xform = _transform(child.get("transform"))
            inherited = _fill_of(child.get("fill"), "#000000")      # SVG's initial fill value is black
            for leaf in child:
                leaf_name = _local(leaf)
                if leaf_name != "path":
                    raise MarkRefused(_named_refusal(leaf_name), f"<g> holds <{leaf_name}>")
                take(leaf, xform, inherited)
        elif name == "path":
            take(child, (0.0, 0.0, 1.0, 1.0), "#000000")
        else:
            raise MarkRefused(_named_refusal(name), f"<svg> holds <{name}>")
    if len(fills) > 1:
        raise MarkRefused(SECOND_FILL_COLOUR, "the paths fill in %s" % ", ".join(sorted(fills)))
    if not subpaths:
        raise MarkRefused(NO_INK, "no path")
    bounds = ink_bounds(subpaths)
    if not (bounds[2] > bounds[0] and bounds[3] > bounds[1]):
        raise MarkRefused(NO_INK, f"the outlines enclose no area ({bounds})")
    master = Master(sha256=hashlib.sha256(data).hexdigest(), path=path, fill=fills.pop(),
                    subpaths=tuple(tuple(s) for s in subpaths), bounds=bounds, census=census)
    _register(master)
    return master


def _named_refusal(name: str) -> str:
    if name == "image":
        return IMAGE
    if name in ("a", "use"):
        return LINK
    if name in ("text", "tspan", "textPath"):
        return TEXT
    return ELEMENT


# ---------------------------------------------------------------------------------------------------------------------
# THE APPROVAL ON FILE, and the house mark a composer is handed
# ---------------------------------------------------------------------------------------------------------------------

def lookup_enabled() -> bool:
    """False for the test suite (config/settings.py under pytest, and conftest.py for a runner that set Django up
    first): no test changes when the owner's approved master is placed."""
    from django.conf import settings
    return bool(getattr(settings, "BRAND_MARK_APPROVAL_LOOKUP", True))


def approval_problems(record) -> list:
    """Why an approval record is not honoured, each as ``(code, what)`` naming only what was measured: INCOMPLETE for
    every field missing or malformed (each named), MATCH_FAILED when the record says its emitter-vs-MuPDF match did
    not pass. Empty: the record is complete. A record that is not a JSON object is UNREADABLE."""
    if not isinstance(record, dict):
        return [(CODE_APPROVAL_UNREADABLE, "the record is not a JSON object")]
    incomplete = []

    def text(key):
        value = record.get(key)
        return value if isinstance(value, str) and value.strip() else None

    def sha(value):
        return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value, re.ASCII) is not None

    if record.get("schema_version") != APPROVAL_SCHEMA:
        incomplete.append(f"schema_version is {record.get('schema_version')!r}, not {APPROVAL_SCHEMA!r}")
    if record.get("master") != MASTER_FILE:
        incomplete.append(f"master is {record.get('master')!r}, not {MASTER_FILE!r}")
    if not sha(record.get("master_sha256")):
        incomplete.append("master_sha256 is not a sha256")
    if text("owner_words") is None:
        incomplete.append("the owner's words are missing")
    if text("register") is None:
        incomplete.append("the register line is missing")
    date = record.get("date")
    if not (isinstance(date, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date, re.ASCII)):
        incomplete.append("the date is not YYYY-MM-DD")
    else:
        try:
            datetime.date.fromisoformat(date)
        except ValueError:
            incomplete.append(f"the date {date} is not a calendar date")
    source = record.get("source_png")
    if not (isinstance(source, dict) and sha(source.get("sha256"))):
        incomplete.append("the source PNG and its sha256 are missing")
    tracer = record.get("tracer")
    if not (isinstance(tracer, dict) and isinstance(tracer.get("name"), str) and tracer["name"].strip()):
        incomplete.append("the tracer is missing")
    match = record.get("match")
    bar = match.get("emitter_vs_mupdf") if isinstance(match, dict) else None
    problems = [(CODE_APPROVAL_INCOMPLETE, what) for what in incomplete]
    if not isinstance(bar, dict) or "passed" not in bar:
        problems.append((CODE_APPROVAL_INCOMPLETE, "the emitter-vs-MuPDF match is not recorded"))
    elif bar["passed"] is not True:
        problems.append((CODE_APPROVAL_MATCH_FAILED, "the recorded emitter-vs-MuPDF match did not pass (%s px "
                         "disagreeing by more than half)" % bar.get("px_disagreeing_over_half")))
    return problems


def _refused(codes, reason: str) -> dict:
    return {"state": REFUSED, "master": None, "codes": sorted(set(codes)), "reason": reason}


def _errno_name(exc: OSError) -> str:
    """The OS error a read failed with, by its errno name (EACCES, EISDIR, ...) — the only cause a handler may state."""
    return errno.errorcode.get(exc.errno, str(exc.errno)) if exc.errno is not None else type(exc).__name__


def mark_root():
    """Where ``docs/brand/mark/`` is looked for: ``settings.BRAND_MARK_ROOT`` when it is set (a test's temp root),
    else BASE_DIR. Read at call time, like the lookup switch."""
    from django.conf import settings
    configured = getattr(settings, "BRAND_MARK_ROOT", None)
    return str(settings.BASE_DIR) if configured is None else str(configured)


def approved_master(*, root=None) -> dict:
    """The approved master on file, or the state that says why there is none: ``{"state", "master", "codes",
    "reason"}`` (and ``"approval"``, the record's own fields, when APPROVED). ``root`` defaults to ``mark_root()``.
    Read afresh on EVERY call — placing or removing the files takes effect at the next composition, in every
    process."""
    if not lookup_enabled():
        return {"state": LOOKUP_OFF, "master": None, "codes": [],
                "reason": "the approval lookup is off (the test suite: config/settings.py, conftest.py)"}
    folder = os.path.join(mark_root() if root is None else str(root), *MARK_DIR)
    record_path = os.path.join(folder, APPROVAL_FILE)
    if not os.path.lexists(record_path):                     # a dangling link IS something on file: it does not read
        return {"state": NO_APPROVAL, "master": None, "codes": [],
                "reason": "no approval record at %s" % "/".join(MARK_DIR + (APPROVAL_FILE,))}
    try:
        with open(record_path, encoding="utf-8") as fh:
            record = json.load(fh)
    except OSError as exc:
        return _refused([CODE_APPROVAL_UNREADABLE], f"{record_path} does not read: {_errno_name(exc)}")
    except ValueError as exc:
        return _refused([CODE_APPROVAL_UNREADABLE], f"{record_path} does not parse as JSON: {exc}")
    problems = approval_problems(record)
    if problems:
        return _refused([code for code, _what in problems], "; ".join(what for _code, what in problems))
    master_path = os.path.join(folder, MASTER_FILE)
    try:
        with open(master_path, "rb") as fh:
            data = fh.read()
    except FileNotFoundError:
        return _refused([CODE_MASTER_MISSING], f"{master_path} is not found")
    except OSError as exc:
        return _refused([CODE_MASTER_UNREADABLE], f"{master_path} does not read: {_errno_name(exc)}")
    sha = hashlib.sha256(data).hexdigest()
    if sha != record["master_sha256"]:
        return _refused([CODE_SHA_MISMATCH], "the master on file hashes %s, the approval names %s"
                        % (sha, record["master_sha256"]))
    try:
        master = read_master(data, path=master_path)
    except MarkRefused as exc:
        return _refused([CODE_MASTER_REFUSED], str(exc))
    return {"state": APPROVED, "master": master, "codes": [], "reason": "the approval on file holds",
            "approval": {k: record.get(k) for k in ("owner_words", "register", "date", "source_png", "tracer",
                                                    "match", "master_sha256")}}


def house_mark(uploads=None, *, root=None) -> dict:
    """What a composer draws the house mark from: ``png`` — exactly the raster the callers picked before this module
    (an uploaded logo when there is one, else ``settings.BRAND_LOGO_PATH``, either only if it exists) — and
    ``master``, the approved vector master or None, with the state and codes that say why."""
    from django.conf import settings
    uploaded = None if uploads is None else uploads.get("logo")
    if uploaded:
        return {"schema_version": SCHEMA, "state": UPLOADED, "master": None, "codes": [],
                "png": uploaded if os.path.exists(uploaded) else None,
                "reason": "an uploaded logo is the task's own raster and stays one"}
    png = getattr(settings, "BRAND_LOGO_PATH", None)
    return dict(approved_master(root=root), schema_version=SCHEMA,
                png=png if (png is not None and png != "" and os.path.exists(png)) else None)


def selection_record(house: dict) -> dict:
    """``brand_mark_selection/1.0`` — the house mark's state for the task's record, JSON-able."""
    master = house.get("master")
    return {"schema_version": SCHEMA, "ruling": RULING, "state": house.get("state"), "codes": list(house["codes"]),
            "reason": house.get("reason"), "png": house.get("png"),
            "master": None if master is None else {
                "sha256": master.sha256, "path": master.path, "fill": master.fill,
                "ink_bounds": [round(v, 4) for v in master.bounds], "ink_aspect": round(master.aspect, 6),
                "census": dict(master.census)},
            **({"approval": house["approval"]} if house.get("approval") is not None else {})}


def confirmed_assets(*, root=None) -> list:
    """The approved master's path when the approval on file holds; nothing otherwise."""
    selected = approved_master(root=root)
    return [selected["master"].path] if selected["state"] == APPROVED else []


# ---------------------------------------------------------------------------------------------------------------------
# PLACING AND DRAWING
# ---------------------------------------------------------------------------------------------------------------------

def master_kwargs(master) -> dict:
    """``{"logo_master": master}`` — or NOTHING when there is no master, so every call a caller makes without one is,
    keyword for keyword, the call it made before the switch existed (a test's double of a composer or a helper sees
    the same shape it always saw)."""
    return {} if master is None else {"logo_master": master}


def is_mark(node) -> bool:
    """An AssetRef naming a brand-mark master."""
    asset_id = getattr(node, "asset_id", None)
    return (getattr(node, "type", None) == "asset_ref" and asset_id is not None
            and str(asset_id).startswith(ASSET_PREFIX))


def mark_node(name: str, master: Master, x: float, y: float, w: float, h: float):
    """The mark in the box ``(x, y, w, h)`` — a composer computes the box as it did for the raster, its height from
    ``master.aspect``. An AssetRef: every instrument reads its box as it read the raster's."""
    from apps.ire.graph import AssetRef
    _register(master)
    return AssetRef(name=name, asset_id=master.asset_id, x=x, y=y, w=w, h=h)


def resolve(asset_id, *, root=None):
    """The master a mark names: one read in this process, else the approved master on file when its sha256 is the
    one named; None when neither holds."""
    if asset_id is None or not str(asset_id).startswith(ASSET_PREFIX):
        return None
    asset_id = str(asset_id)
    sha = asset_id[len(ASSET_PREFIX):]
    master = _REGISTRY.get(sha)
    if master is not None:
        return master
    held = approved_master(root=root).get("master")
    return held if held is not None and held.sha256 == sha else None


def placed_segments(master: Master, x: float, y: float, w: float, h: float) -> list:
    """The master's outlines, in order and direction, mapped from its INK bounds onto the box — uniformly when the
    box's aspect is the master's."""
    from apps.ire.graph import ClosePath, CubicTo, LineTo, MoveTo
    x0, y0, x1, y1 = master.bounds
    kx, ky = w / (x1 - x0), h / (y1 - y0)

    def X(u):
        return x + (u - x0) * kx

    def Y(v):
        return y + (v - y0) * ky

    segments = []
    for sub in master.subpaths:
        for op in sub:
            if op[0] == "M":
                segments.append(MoveTo(x=X(op[1]), y=Y(op[2])))
            elif op[0] == "L":
                segments.append(LineTo(x=X(op[1]), y=Y(op[2])))
            elif op[0] == "C":
                segments.append(CubicTo(x1=X(op[1]), y1=Y(op[2]), x2=X(op[3]), y2=Y(op[4]), x=X(op[5]), y=Y(op[6])))
            else:
                segments.append(ClosePath())
    return segments


def expanded(node, *, root=None):
    """The mark ``node`` as the Path it draws: every outline of its master in ONE path, so a counter is cut by the
    winding rule; the master's own fill (or the node's explicit recolour); the node's name, opacity, finishes, blend
    mode and shadow carried. Refused by name when no master resolves — a mark is never drawn as nothing."""
    from apps.ire.graph import Color, Path, SolidFill
    master = resolve(node.asset_id, root=root)
    if master is None:
        raise MarkRefused(CODE_UNRESOLVED, "%s names %s, and no master read in this process nor approved on file has "
                                           "that sha256" % (node.name if node.name != "" else "a mark", node.asset_id))
    colour = node.recolor if node.recolor is not None else Color.from_hex(master.fill)
    return Path(name=node.name, segments=placed_segments(master, node.x, node.y, node.w, node.h),
                fill=SolidFill(color=colour), fill_rule="nonzero", opacity=node.opacity,
                finishes=list(node.finishes), blend_mode=node.blend_mode, shadow=node.shadow)


def expand(doc, *, root=None):
    """``doc`` with every mark expanded (``expanded``) — a deep copy, never the caller's document, which keeps the
    box every instrument reads. A document with no mark is returned AS IS: the same object, so nothing downstream of
    this call can move for it."""
    from apps.ire.graph import Group
    def has_mark(node):
        return is_mark(node) or (isinstance(node, Group) and any(has_mark(child) for child in node.children))

    if not any(has_mark(tree) for tree in (doc.root, doc.inside) if tree is not None):
        return doc
    out = doc.model_copy(deep=True)

    def rebuild(group):
        for i, child in enumerate(group.children):
            if is_mark(child):
                group.children[i] = expanded(child, root=root)
            elif isinstance(child, Group):
                rebuild(child)

    rebuild(out.root)
    if out.inside is not None:
        rebuild(out.inside)
    return out


# ---------------------------------------------------------------------------------------------------------------------
# WHAT THE INSTRUMENTS READ — the mark's nodes, its source, its aspect and its cap band
# ---------------------------------------------------------------------------------------------------------------------

def logo_nodes(doc) -> list:
    """The placed marks — the logo rasters and the marks drawn from a master — classified exactly as the v1.1 census
    classifies a logo raster (reference wins over logo), so every reader agrees which node is the mark. For a document
    with no master-drawn mark this is ``container_logo_metrics.logo_image_nodes``, node for node."""
    found = []
    for node, parent in doc.walk():
        if node.type != "image" and not is_mark(node):
            continue
        low = str(node.name).lower()                    # a node's name is a str, "" when unset (graph._NodeBase)
        if "reference" in low or (parent is not None and parent.name == "Reference"):
            continue
        if "logo" in low:
            found.append(node)
    return found


def source_of(node) -> str:
    """Where a placed mark comes from: a raster's ``src``; a master-drawn mark's master file (its asset id when the
    master is not resolvable here)."""
    if is_mark(node):
        master = resolve(node.asset_id)
        return str(node.asset_id) if master is None or master.path == "" else master.path
    src = getattr(node, "src", None)
    return "" if src is None else str(src)


def _flatten(master: Master, width_px: int, height_px: int, margin: int) -> list:
    """The master's outlines as straight edges in raster pixels (the ink box onto ``width_px`` x ``height_px``)."""
    x0, y0, x1, y1 = master.bounds
    kx, ky = width_px / (x1 - x0), height_px / (y1 - y0)
    edges = []
    for sub in master.subpaths:
        start = cur = None
        for op in sub:
            if op[0] == "M":
                if cur is not None and start is not None and cur != start:
                    edges.append(cur + start)
                cur = start = (margin + (op[1] - x0) * kx, margin + (op[2] - y0) * ky)
            elif op[0] == "L":
                nxt = (margin + (op[1] - x0) * kx, margin + (op[2] - y0) * ky)
                edges.append(cur + nxt)
                cur = nxt
            elif op[0] == "C":
                p0 = cur
                p1 = (margin + (op[1] - x0) * kx, margin + (op[2] - y0) * ky)
                p2 = (margin + (op[3] - x0) * kx, margin + (op[4] - y0) * ky)
                p3 = (margin + (op[5] - x0) * kx, margin + (op[6] - y0) * ky)
                prev = p0
                for step in range(1, _FLATTEN_STEPS + 1):
                    t = step / _FLATTEN_STEPS
                    u = 1.0 - t
                    pt = (u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                          u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1])
                    edges.append(prev + pt)
                    prev = pt
                cur = p3
            else:
                if cur is not None and start is not None and cur != start:
                    edges.append(cur + start)
                cur = start
        if cur is not None and start is not None and cur != start:
            edges.append(cur + start)                      # an open subpath fills as if closed
    return edges


def coverage(master: Master, height_px: int, *, margin: int = 1):
    """The master rasterised by the NONZERO winding rule, sampled at pixel centres: a boolean array, ``height_px``
    rows of ink and ``margin`` empty pixels all round."""
    import numpy as np
    width_px = max(1, int(round(height_px / master.aspect)))
    rows, cols = height_px + 2 * margin, width_px + 2 * margin
    edges = np.array(_flatten(master, width_px, height_px, margin), dtype=float).reshape(-1, 4)
    xa, ya, xb, yb = edges[:, 0], edges[:, 1], edges[:, 2], edges[:, 3]
    keep = ya != yb
    xa, ya, xb, yb = xa[keep], ya[keep], xb[keep], yb[keep]
    direction = np.where(yb > ya, 1, -1)
    lo, hi = np.minimum(ya, yb), np.maximum(ya, yb)
    out = np.zeros((rows, cols), dtype=bool)
    for r in range(rows):
        yc = r + 0.5
        m = (lo <= yc) & (yc < hi)
        if not m.any():
            continue
        t = (yc - ya[m]) / (yb[m] - ya[m])
        xc = xa[m] + t * (xb[m] - xa[m])
        idx = np.clip(np.floor(xc - 0.5).astype(int) + 1, 0, cols)
        delta = np.zeros(cols + 1, dtype=int)
        np.add.at(delta, idx, direction[m])
        out[r] = np.cumsum(delta[:cols]) != 0
    return out


def cap_band(master: Master) -> dict | None:
    """The master's flat-capital band, measured by ``container_brand_usage.measure_cap_ratio`` — the instrument the
    raster's band is read with — on the master rasterised at CAP_BAND_RASTER_PX of ink height with one empty pixel
    round it (so the instrument reads its ground off a corner that is always empty), and stated against the INK
    height, which is the placed box's height. None when the instrument finds no band (§AW3: then UNMEASURED)."""
    if master.sha256 in _BANDS:
        return _BANDS[master.sha256]
    import tempfile

    import numpy as np
    from PIL import Image as PILImage

    from apps.ire.container_brand_usage import measure_cap_ratio
    ink = coverage(master, CAP_BAND_RASTER_PX)
    rgba = np.zeros(ink.shape + (4,), dtype=np.uint8)
    rgba[ink, 3] = 255
    with tempfile.TemporaryDirectory(prefix="bbrose_brand_mark_") as tmp:
        path = os.path.join(tmp, "mark.png")
        PILImage.fromarray(rgba, "RGBA").save(path)
        band = measure_cap_ratio(path)
    if band is not None:
        h, w = ink.shape[0] - 2, ink.shape[1] - 2
        band = dict(band, canvas_px=[int(w), int(h)], cap_line_px=band["cap_line_px"] - 1,
                    baseline_px=band["baseline_px"] - 1, cap_ratio=round(band["cap_band_px"] / h, 6),
                    measured_on=("the master %s rasterised at %d px of ink height (nonzero winding, pixel centres), "
                                 "one empty pixel round it; the ratio is of the ink height"
                                 % (master.sha256[:16], CAP_BAND_RASTER_PX)))
    _BANDS[master.sha256] = band
    return band


def band_of(node, src: str):
    """The cap band an instrument reads for a placed mark: the raster's by ``measure_cap_ratio`` on its file (exactly
    as before), a master-drawn mark's by ``cap_band``."""
    if is_mark(node):
        master = resolve(node.asset_id)
        return None if master is None else cap_band(master)
    from apps.ire.container_brand_usage import measure_cap_ratio
    return measure_cap_ratio(src) if src else None


__all__ = ["SCHEMA", "APPROVAL_SCHEMA", "RULING", "MARK_DIR", "MASTER_FILE", "APPROVAL_FILE", "ASSET_PREFIX",
           "ZONE_USED", "VECTOR_MASTER_FLAG", "NO_APPROVAL", "LOOKUP_OFF", "UPLOADED", "APPROVED", "REFUSED",
           "CODE_APPROVAL_UNREADABLE", "CODE_MASTER_MISSING", "CODE_SHA_MISMATCH", "CODE_MASTER_REFUSED",
           "CODE_UNRESOLVED", "CODE_APPROVAL_INCOMPLETE", "CODE_APPROVAL_MATCH_FAILED", "CODE_MASTER_UNREADABLE",
           "MarkRefused", "Master", "read_master", "ink_bounds", "mark_root",
           "lookup_enabled", "approval_problems", "approved_master", "house_mark", "selection_record",
           "confirmed_assets", "master_kwargs", "is_mark", "mark_node", "resolve", "placed_segments", "expanded", "expand",
           "logo_nodes", "source_of", "coverage", "cap_band", "band_of", "CAP_BAND_RASTER_PX"]
