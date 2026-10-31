"""[His goal for the pitch, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), B (5): "DESIGNER'S EYE: after every drawing, render
it beside its concept and have a vision model list every visible difference (missing parts, wrong colours, fonts,
order, shape, unreadable text). Fix and re-check; "PASS" means "matches the concept", never only "the files match each
other". Tell me the cost per design."]

The drawing, rendered as the design's own file prints it, is shown to the strongest vision model beside the concept
picture it was drawn from. It lists every visible difference by part — what the concept shows, what the drawing shows,
how much it matters — and, where the engine has a lever for it, the fix. The engine makes the fixes it has levers for
(a part's colour, redrawn in the concept's), draws the file again and looks again, up to ``ROUNDS`` looks. PASS is the
eye's own word that the drawing matches the concept: no blocking and no major difference. What it still sees is shown
beside Approve in its own words. Every look is a paid call on the design's ledger (operation ``OPERATION``), and the
record says what the eye cost.

What it cannot do, said so it is not assumed: it sees a raster of the drawing at ``EYE_DPI``, not the vectors; a
colour it names is its reading of a picture, so a recolour moves only a colour the drawing really prints near it
(``RECOLOUR_DE``); a difference with no lever is said, never "fixed".

[His goal after the pitch page, 2026-10-15, A (7): "DESIGNER'S EYE STRICTER: always check, explicitly, shape and
proportion, font classification, metallic finish, completeness and contrast; look twice and report what both looks
agree on. "Matches" only when none of these differ."] Every look answers each of the ``CHECKS`` by name, same or not,
and names the check each difference belongs to. The eye looks twice; where the two looks disagree on any check a third
look breaks the tie. A difference is reported where at least two looks name it (same check, the same part); a check
differs where at least two looks say so; "matches" only where no check differs and no agreed difference is blocking or
major."""
from __future__ import annotations

import base64
import io
import json
import re

SCHEMA = "designers_eye/1.0"
OPERATION = "designers_eye"
#: how many times the eye looks at one drawing — the first look, and one after each round of fixes
ROUNDS = 3
#: the drawing rendered for the eye at this many dots per inch, and either picture sent at most this long a side
EYE_DPI = 200
MAX_SIDE = 1568
#: a colour the eye names is the drawing's own where one it prints stands within this ΔE (CIEDE2000) of it
RECOLOUR_DE = 14.0
SEVERITIES = ("blocking", "major", "minor")
#: [his goal after the pitch page, A (7)] what every look checks, explicitly and by name
#: [his last goal before the pitch, 2026-10-16, Step 2: "The designer's eye must fail a drawing that misses any of these"
#: — the hero never lost (caps and closures, illustrations, every text line), proportions from the concept, no duplicate
#: or ghost text, text inside the panel and readable, fonts, metals and colours, no empty or grey blocks, no broken
#: motifs] each of his checklist's points named under the check that answers for it
CHECKS = {"shape": "shape and proportion — the product's outline and aspect ratio (a squat drawing of a tall concept, "
                   "shoulders that flare where the concept is a straight block), and each part's shape: cap and "
                   "closure (never missing), dropper bulb and collar, lid, pump, frame",
          "font": "font classification of every line of type — serif / sans / script / condensed / display, its "
                  "weight, its letter-spacing and its case; the lines of one name in one face",
          "metal": "metallic finish — gold, chrome or silver parts drawn as metal with highlights and shadows, never "
                   "flat tan, brown or grey",
          "completeness": "completeness — every element of the concept's design drawn: the hero illustration, motifs, "
                          "frames, rules, highlights, every line of type the concept shows (its size line too); no "
                          "duplicate or ghost text; no empty or grey block; no broken or garbled motif",
          "contrast": "contrast — the logo and every small line of type readable against what lies behind it, never "
                      "washed out, and every line of text inside its frame, its panel and the product's own outline"}
#: how many looks agree before a difference is reported, and how many the eye takes at most each round
AGREE = 2
MAX_LOOKS = 3
KINDS = ("missing part", "extra part", "colour", "font", "text order", "wrong text", "unreadable text",
         "text over the hero", "shape", "size or position", "detail lost")

SYSTEM = """You are a senior packaging designer with a merciless eye. You are shown TWO pictures of one product design:
IMAGE 1 is the CONCEPT — a photographic render the client approved. IMAGE 2 is the DRAWING — flat, print-ready vector
artwork that must reproduce the concept's printed design faithfully (it may also show the product's outline, its back
or other faces beside the front; judge the face that matches the concept).

List EVERY visible difference a client would notice between the concept's printed design and the drawing: a missing or
extra part (motif, illustration, band, rule, frame, logo, line of type), a wrong colour, a wrong typeface character
(serif/sans/script, weight, width, case, spacing), text in a different order or with different words, a different
shape or silhouette of the product or of a part, a part clearly moved or resized, detail lost (an illustration
simplified, gradients flattened to bands, texture gone), text that is hard to read against what lies behind it, text
printed over the hero illustration.

THE BRAND MARK (the BBROSE wordmark with a small rose inside its O, and its ®) is placed as its approved artwork: never
list a difference in the mark's own drawing — its ®, its letterforms or the rose in its O — only its colour, size or
place.

IGNORE what a flat drawing cannot and should not copy: the photo's lighting, shading, shine, reflections and shadows,
the 3-D curvature and perspective, the backdrop behind the product, and the slight softness of a photograph. On a
carton's flat die-line, its printer's marks are not the design: the cut lines (magenta or red), fold lines (dashed),
bleed and safe-area guides, and the tuck's thumb-notch cut — judge the front panel's printed design inside them.

Severity: "blocking" — the hero element or the product name missing, wrong or unreadable, or the design no longer
recognisably the concept; "major" — a clearly wrong colour on a large area, a wrong typeface character, a missing
secondary element, a wrong shape, an illustration visibly simplified; "minor" — small offsets, small details a client
would barely notice.

For a colour difference give the drawing's colour and the concept's as hex (your best reading of the flat colour, never
a shadow or a highlight) in "fix": {"lever": "recolour", "drawing_hex": "#RRGGBB", "concept_hex": "#RRGGBB"}; for a line
of type whose letters are clearly heavier in the concept "fix": {"lever": "weight", "to": "bold"} (or "to": "regular"
where the drawing's are clearly heavier), and name that line by its words in "part"; for any other difference
"fix": {"lever": "none"}.

ALWAYS CHECK THESE FIVE, EXPLICITLY, ONE BY ONE, and say for each whether the drawing is the same as the concept:
 "shape": %(shape)s;
 "font": %(font)s;
 "metal": %(metal)s;
 "completeness": %(completeness)s;
 "contrast": %(contrast)s.
Look closely at each before you answer: a sans line where the concept sets a serif, a block where the concept shows a
dropper's bulb and collar, a landscape drawing of a portrait concept, a flat tan lid where the concept shows gold — each
is a "major" difference. The photo's lighting is ignored, but a metal part's highlights and shadows are its finish.

Return ONLY JSON:
{"checks": {"shape": {"same": true|false, "note": "..."}, "font": {...}, "metal": {...}, "completeness": {...},
            "contrast": {...}},
 "matches": true|false, "summary": "one sentence a designer would say",
 "differences": [{"check": "shape|font|metal|completeness|contrast|colour|other", "kind": "...",
                  "part": "a few plain words", "concept": "what the concept shows",
                  "drawing": "what the drawing shows", "severity": "blocking|major|minor", "fix": {...}}]}
A check that is not the same has at least one difference under it. "matches" is true only when all five checks are the
same and no difference is blocking or major. Be specific and exhaustive; never invent a difference.""" % CHECKS


def _png_b64(data: bytes) -> str:
    """The picture as PNG, its longest side at most MAX_SIDE, base64."""
    from PIL import Image
    with Image.open(io.BytesIO(data)) as im:
        img = im.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        out = io.BytesIO()
        img.save(out, format="PNG", optimize=True)
    return base64.standard_b64encode(out.getvalue()).decode("ascii")


#: [his goal after the pitch page, A (7)] the share of a picture's height, from the top of what it shows, shown to the eye
#: again enlarged — where a closure and the shoulders stand (it passed 128's grey-block dropper on the whole picture)
TOP_SHARE = 0.4


def _top(data: bytes) -> bytes:
    """The top TOP_SHARE of what a picture shows (its ground trimmed), as PNG."""
    from PIL import Image, ImageChops
    with Image.open(io.BytesIO(data)) as im:
        img = im.convert("RGB")
    ground = Image.new("RGB", img.size, img.getpixel((0, 0)))
    box = ImageChops.difference(img, ground).convert("L").point([0] * 25 + [255] * 231).getbbox()
    if box:
        img = img.crop(box)
    img = img.crop((0, 0, img.width, max(1, int(img.height * TOP_SHARE))))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def render(ai_path: str, box_mm=None, dpi: int = EYE_DPI) -> bytes:
    """The drawing's first page as the file prints it, at ``dpi`` — cut to ``box_mm`` (x0, y0, x1, y1, page mm) where it
    is given (the design itself, ``views_of``'s "The design"), else the whole page."""
    import fitz
    with fitz.open(ai_path) as pdf:
        page = pdf[0]
        clip = None
        if box_mm:
            k = 72.0 / 25.4
            pad = 1.0
            clip = fitz.Rect((box_mm[0] - pad) * k, (box_mm[1] - pad) * k, (box_mm[2] + pad) * k,
                             (box_mm[3] + pad) * k) & page.rect
        pix = page.get_pixmap(dpi=dpi, clip=clip, alpha=False)
        return pix.tobytes("png")


def design_box(views: dict):
    """The design itself on the drawing's first page (``views_of``'s record), or None."""
    for section in (views or {}).get("sections") or []:
        on_first = "page" not in section or section["page"] == 1
        if section.get("words") in ("The design", "The front") and on_first:
            return section.get("box_mm")
    return None


def _said(row, key) -> str:
    """``row[key]`` as text — "" where it is not there."""
    value = row[key] if key in row else None
    return str(value) if value is not None else ""


def _child(obj, name):
    """``obj.name``, or None where it has none."""
    try:
        return getattr(obj, name)
    except AttributeError:
        return None


def _roots(doc) -> list:
    """The drawing's artboards: its outside, and its inside where it has one."""
    inside = _child(doc, "inside")
    return [doc.root] + ([inside] if inside is not None else [])


def look(concept: bytes, drawing: bytes, *, call=None, model=None, top=False) -> dict:
    """One look: ``{"matches", "summary", "differences", "model"}`` — the concept and the drawing shown side by side to
    the vision model, its answer read; the call on the design's ledger (operation OPERATION)."""
    from django.conf import settings
    if not model:
        model = settings.DESIGNERS_EYE_MODEL if settings.DESIGNERS_EYE_MODEL else settings.CLAUDE_MODEL_HEAVY
    content = [{"type": "text", "text": "IMAGE 1 — the CONCEPT:"},
               {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _png_b64(concept)}},
               {"type": "text", "text": "IMAGE 2 — the DRAWING:"},
               {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _png_b64(drawing)}}]
    if top:
        # [his goal after the pitch page, A (7)] a standing product's closure and shoulders, enlarged
        content += [{"type": "text", "text": "IMAGE 3 — the CONCEPT's top (its closure and shoulders), enlarged:"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": _png_b64(_top(concept))}},
                    {"type": "text", "text": "IMAGE 4 — the DRAWING's top, enlarged:"},
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                 "data": _png_b64(_top(drawing))}},
                    {"type": "text", "text": "Judge the closure (cap, dropper bulb and collar, lid, pump) and the "
                                             "shoulders on images 3 and 4: their outline, proportions and finish."}]
    content.append({"type": "text", "text": "List every visible difference, as the system prompt asks. JSON only."})
    if call is None:
        from apps.pipeline.services.claude_service import call_claude, extract_text
        text = extract_text(call_claude(SYSTEM, content, max_tokens=6000, model=model, operation=OPERATION))
    else:
        text = call(SYSTEM, content)
    from apps.pipeline.services.claude_service import loads_tolerant
    raw = loads_tolerant(text)
    diffs = []
    for d in raw.get("differences") or []:
        if not isinstance(d, dict):
            continue
        sev = _said(d, "severity").lower()
        check = _said(d, "check").lower()
        diffs.append({"check": check if check in CHECKS else _check_of(_said(d, "kind")),
                      "kind": _said(d, "kind"), "part": _said(d, "part"),
                      "concept": _said(d, "concept"), "drawing": _said(d, "drawing"),
                      "severity": sev if sev in SEVERITIES else "minor",
                      "fix": d.get("fix") if isinstance(d.get("fix"), dict) else {"lever": "none"}})
    checks = _checks_of(raw, diffs)
    # a check said to differ with no difference under it is a difference of its own, in the eye's words
    for name, row in checks.items():
        if not row["same"] and not any(d["check"] == name for d in diffs):
            diffs.append({"check": name, "kind": name, "part": name, "concept": "", "drawing": row["note"],
                          "severity": "major", "fix": {"lever": "none"}})
    # the mark's own drawing is its approved artwork (his §AE2 brand lockup): a difference in its ®, its letters or the
    # rose in its O is never a difference of the design — its colour, its size and its place are
    diffs = [d for d in diffs if not _mark_drawing(d)]
    serious = [d for d in diffs if d["severity"] in ("blocking", "major")]
    # PASS is the eye's word AND no serious difference listed — an answer that says it matches while listing a
    # blocking difference is read by what it lists
    same = all(row["same"] for row in checks.values())
    return {"matches": bool(raw.get("matches")) and not serious and same, "summary": _said(raw, "summary"),
            "checks": checks, "differences": diffs, "model": model}


_CHECK_WORDS = (("shape", re.compile(r"shape|proportion|aspect|outline|silhouette|landscape|portrait", re.I)),
                ("font", re.compile(r"font|typeface|serif|sans|script|weight|letter|tracking|spacing|case", re.I)),
                ("metal", re.compile(r"metal|gold|chrome|silver|foil|finish", re.I)),
                ("completeness", re.compile(r"missing|absent|detail|simplif|extra", re.I)),
                ("contrast", re.compile(r"read|contrast|legib|overflow|outside|over the hero", re.I)))


def _check_of(kind: str) -> str:
    """The check a difference belongs to, from its kind where the eye named none — "colour" or "other" else."""
    for name, words in _CHECK_WORDS:
        if words.search(kind):
            return name
    return "colour" if re.search(r"colou?r", kind, re.I) else "other"


def _checks_of(raw, diffs) -> dict:
    """Each of CHECKS as the look answered it — ``{name: {"same", "note"}}``; a check it left unanswered is the same
    unless a difference it listed falls under it (never a pass given by silence over a listed difference)."""
    given = raw.get("checks") if isinstance(raw.get("checks"), dict) else {}
    out = {}
    for name in CHECKS:
        row = given.get(name) if isinstance(given.get(name), dict) else {}
        listed = any(d["check"] == name and d["severity"] in ("blocking", "major") for d in diffs)
        said_same = row.get("same") if isinstance(row.get("same"), bool) else not listed
        out[name] = {"same": bool(said_same) and not listed, "note": _said(row, "note")}
    return out


def _words(part: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]{3,}", part.lower())} - _STOP_WORDS


def _same_difference(a, b) -> bool:
    """Whether two looks name one difference: the same check and the same part (a word of its name in common, or the
    check's only serious difference in both)."""
    if a["check"] != b["check"]:
        return False
    return bool(_words(a["part"]) & _words(b["part"])) or (not _words(a["part"]) and not _words(b["part"]))


def agreed(looks: list) -> dict:
    """[his goal after the pitch page, A (7)] what the looks agree on: each difference named by at least AGREE looks
    (the first look's words, the milder severity two agree on), each check differing where AGREE looks say so, and
    "matches" only where no check differs and no agreed difference is blocking or major."""
    sev_rank = {s: i for i, s in enumerate(SEVERITIES)}
    out, used = [], [set() for _ in looks]
    for i, look_i in enumerate(looks):
        for di, d in enumerate(look_i["differences"]):
            if di in used[i]:
                continue
            found, worst = [], []
            for j in range(i + 1, len(looks)):
                for dj, e in enumerate(looks[j]["differences"]):
                    if dj not in used[j] and _same_difference(d, e):
                        found.append((j, dj))
                        worst.append(e["severity"])
                        break
            if 1 + len(found) < AGREE:
                continue
            used[i].add(di)
            for j, dj in found:
                used[j].add(dj)
            sevs = sorted([d["severity"]] + worst, key=lambda s: sev_rank[s])
            out.append(dict(d, severity=sevs[AGREE - 1], seen_by=1 + len(found)))
    checks = {name: {"same": sum(1 for lk in looks if not lk["checks"][name]["same"]) < AGREE,
                     "notes": [lk["checks"][name]["note"] for lk in looks if not lk["checks"][name]["same"]]}
              for name in CHECKS}
    serious = [d for d in out if d["severity"] in ("blocking", "major")]
    return {"matches": not serious and all(c["same"] for c in checks.values()), "differences": out, "checks": checks,
            "summary": looks[0]["summary"], "looks": len(looks), "model": looks[0]["model"]}


def _disagree(a, b) -> bool:
    """Whether two looks differ on any check or on whether the drawing matches."""
    return a["matches"] != b["matches"] or any(a["checks"][n]["same"] != b["checks"][n]["same"] for n in CHECKS)


_MARK_DRAWING = re.compile(r"®|registered|inside (?:the|its) o\b|in the o\b|letterform|rose icon|rose inside|bean|"
                           r"symbol", re.I)
_MARK_KEPT = re.compile(r"colou?r|size|scale|position|placement|placed|moved|missing|absent|legib|read", re.I)


def _mark_drawing(d) -> bool:
    """Whether a difference is about the brand mark's own drawing — never one the design can or may change."""
    words = set(re.findall(r"[a-z]+", d["part"].lower()))
    said = " ".join((d["part"], d["concept"], d["drawing"], d["kind"]))
    return bool(words & _MARK_WORDS) and bool(_MARK_DRAWING.search(said)) and not _MARK_KEPT.search(d["kind"])


def _hex_ok(value) -> bool:
    s = value if isinstance(value, str) else ""
    return len(s) == 7 and s.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in s[1:])


def drawn_colours(doc) -> set:
    """Every solid colour the drawing prints — fills, strokes, gradient stops, type."""
    found = set()
    for root in _roots(doc):
        stack = [root]
        while stack:
            node = stack.pop()
            for attr in ("fill", "stroke"):
                paint = _child(node, attr)
                if paint is None:
                    continue
                c = _child(paint, "color")
                if c is not None:
                    found.add(c.to_hex().upper())
                for stop in _child(paint, "stops") or []:
                    found.add(stop.color.to_hex().upper())
            c = _child(node, "color")
            if c is not None and hasattr(c, "to_hex"):
                found.add(c.to_hex().upper())
            stack.extend(_child(node, "children") or [])
    return found


#: a line of type is the part the eye names where at least this share of its own words are in the part's words
LINE_WORDS_SHARE = 0.6


def _is_line_of(text: str, words: set) -> bool:
    """True where ``text``'s own words are mostly ``words`` (LINE_WORDS_SHARE of them) — that line, never a sentence."""
    own = _words(text)
    return bool(own) and len(own & words) >= LINE_WORDS_SHARE * len(own)


def recolour(doc, differences, mine=()) -> list:
    """The fixes the engine has a lever for: each colour difference's drawn colour — the drawing's own colour nearest
    the one the eye read, within RECOLOUR_DE — redrawn in the concept's on the part's own nodes (their names carry the
    part's words), never wholesale; a colour his brief set (``mine``) is never moved. One sentence each fix; [] where
    nothing could be moved."""
    from apps.ire.graph import Color
    from apps.pipeline.services.flat_motif import delta_e
    keep = {str(h).upper() for h in mine}
    nodes = _painted(doc)
    plan, said = [], []
    for d in differences:
        fix = d.get("fix") or {}
        if fix.get("lever") != "recolour" or not (_hex_ok(fix.get("drawing_hex")) and _hex_ok(fix.get("concept_hex"))):
            continue
        if d["severity"] == "minor":
            continue
        new = str(fix["concept_hex"]).upper()
        words = _words(d["part"])
        if words & _MARK_WORDS:
            words |= {"logo", "mark"}                   # the brand mark, as the drawing names it
        for said_word, drawn_words in _PART_WORDS.items():
            if said_word in words:
                words |= drawn_words                    # the part as the drawing names it
        # a line of type the eye names by its own words is that line, whatever colour the eye read it in
        # [his goal after the pitch page, B (9): 138's "upper 'MIDNIGHT FIG' and 'eau de parfum'" recoloured every back
        # line holding "and" or "de" cream on its white] a line is the part's only where most of its own words are the
        # part's — never a sentence sharing one common word with it
        typed = [(n, c) for n, c, h in nodes if _child(n.node, "type") == "text" and h not in keep
                 and _is_line_of(str(_child(n.node, "text")), words)]
        if typed:
            plan.append((typed, new))
            said.append("the %s redrawn in the concept's %s, as the designer's eye saw it" % (d["part"], new))
            continue
        near = sorted({(delta_e(h, fix["drawing_hex"]), h) for _n, _c, h in nodes if h not in keep})
        if not near or near[0][0] > RECOLOUR_DE:
            continue
        old = near[0][1]
        if delta_e(old, new) < 3.0:
            continue
        # only the part's own nodes, found by its words in their names; a colour printed elsewhere too is never moved
        # wholesale — the eye's fix would recolour what it never named
        mine_nodes = [(n, c) for n, c, h in nodes if h == old and any(w in _name(n) for w in words)]
        if not mine_nodes:
            said.append("the %s: its colour is not moved — %s also prints where the eye named nothing" % (d["part"], old))
            continue
        plan.append((mine_nodes, new))
        said.append("the %s redrawn from %s in the concept's %s, as the designer's eye saw it" % (d["part"], old, new))
    said += _reweigh(nodes, differences)
    if not plan:
        return [line for line in said if " set " in line]
    for found, new in plan:
        nc = Color.from_hex(new)
        for _node, color in found:
            color.r, color.g, color.b, color.cmyk = nc.r, nc.g, nc.b, None
    return [line for line in said if " redrawn " in line or " set " in line]


#: [his goal for the pitch, B (5)] the weight lever: the granted role a line of type is set in to read heavier or lighter
#: (``ire.font_roles.CHAINS`` — heading is Montserrat at 700, body Poppins Regular)
WEIGHT_ROLES = {"bold": "heading", "regular": "body"}


def _reweigh(nodes, differences) -> list:
    """Each line of type the eye names heavier (or lighter) in the concept, found by its words, set in the granted role
    that weighs so — one sentence each."""
    said, done = [], set()
    for d in differences:
        fix = d.get("fix") or {}
        wanted = _said(fix, "to").lower()
        role = WEIGHT_ROLES[wanted] if fix.get("lever") == "weight" and wanted in WEIGHT_ROLES else None
        if role is None or d["severity"] == "minor":
            continue
        words = {w for w in re.findall(r"[a-z]{3,}", d["part"].lower())} - _STOP_WORDS
        for named, _colour, _hex in nodes:
            node = named.node
            if id(node) in done or _child(node, "type") != "text" or not words:
                continue
            text = str(_child(node, "text")).lower()
            to = _reweighed(_child(node, "font"), wanted, role)
            if any(w in text for w in words) and _child(node, "font") != to:
                node.font = to
                done.add(id(node))
                said.append("the line %r set heavier (%s), as the designer's eye saw the concept's" % (
                    str(_child(node, "text"))[:40], role) if role == "heading" else
                    "the line %r set lighter (%s), as the designer's eye saw the concept's" % (
                        str(_child(node, "text"))[:40], role))
    return said


def _reweighed(font, wanted: str, role: str) -> str:
    """[His goal after the pitch page, A (1)] the font a line set heavier or lighter names: a line set in its concept's
    own face (``font_roles.LINE_FACE_PREFIX``) keeps its family at the weight wanted; any other line the granted role
    that weighs so."""
    from apps.ire import lettering_faces as lf
    from apps.ire.font_roles import line_face_key, parse_line_face
    parsed = parse_line_face(font)
    if parsed is None:
        return role
    stem = parsed[0]
    for family, faces in lf.FAMILIES.items():
        italic = next((slanted for s, _w, slanted in faces if s == stem), None)
        if italic is None:
            continue
        picked = lf.pick(family, lf.WEIGHTS[wanted], italic)
        if picked is not None:
            return line_face_key(*picked)
    return role


#: the words the eye names a product's parts by, and the drawing's names for them
_PART_WORDS = {"lid": {"cap"}, "closure": {"cap"}, "collar": {"cap"}, "dropper": {"cap", "bulb"},
               "bulb": {"bulb"}, "cap": {"cap"}}
#: the words the eye names the brand mark by
_MARK_WORDS = {"bbrose", "wordmark", "logotype", "logo", "lockup"}
#: words in a part's name that name no node
_STOP_WORDS = {"the", "and", "with", "its", "front", "back", "part", "colour", "color", "line", "text", "type"}


def _name(named) -> str:
    """A node's name and its parents' as the drawing writes them, lower case (``_painted``)."""
    return named.path


def _painted(doc) -> list:
    """``[(node, its colour object, hex)]`` — every solid colour each node prints, its group names carried down so a
    part's words find the colours drawn for it."""
    out = []
    for root in _roots(doc):
        stack = [(root, "")]
        while stack:
            node, path = stack.pop()
            own = _child(node, "name")
            words = _child(node, "text")
            # a line of type is found by the words it prints, as the eye names it
            here = "%s/%s%s" % (path, str(own).lower() if own else "", (" " + str(words).lower()) if words else "")
            colours = []
            for attr in ("fill", "stroke"):
                paint = _child(node, attr)
                if paint is None:
                    continue
                if _child(paint, "color") is not None:
                    colours.append(_child(paint, "color"))
                colours += [stop.color for stop in _child(paint, "stops") or []]
            c = _child(node, "color")
            if c is not None and hasattr(c, "to_hex"):
                colours.append(c)
            for colour in colours:
                out.append((_Named(node, here), colour, colour.to_hex().upper()))
            stack.extend((ch, here) for ch in _child(node, "children") or [])
    return out


class _Named:
    """A node seen with its path of names."""

    def __init__(self, node, path):
        self.node, self.path = node, path



def check(concept: bytes, draw, doc, *, mine=(), call=None, log=None, task=None, top=False) -> dict:
    """The eye's whole check of one drawing: ``draw()`` renders the drawing as its file prints it (PNG bytes) — called
    again after each round of fixes — looked at beside ``concept``, the fixes it has levers for made on ``doc``, up to
    ROUNDS looks. The record: each round's answer, the fixes made, PASS or not, what is left, and what it cost."""
    from decimal import Decimal
    rounds, fixed = [], []
    before = _spent(task)
    verdict = None
    for n in range(1, ROUNDS + 1):
        seen, error = _look_once(concept, draw, call, top)
        if seen is None:
            # the eye failing is said, never a PASS — and what it saw before stands
            rounds.append({"round": n, "error": error})
            break
        verdict = seen
        rounds.append({"round": n, **verdict})
        if log is not None:
            log("ARIA: the designer's eye, look %d: %s — %s" % (n, "vision comparison matches; contrast verification follows" if verdict["matches"]
                                                                else "%d difference(s)" % len(verdict["differences"]),
                                                                verdict["summary"]),
                payload={"differences": verdict["differences"]})
        if verdict["matches"] or n == ROUNDS or doc is None:
            break
        made = recolour(doc, verdict["differences"], list(mine) + _moved_to_read(doc))
        if not made:
            break
        fixed += made + _legible(doc)
    cost = _spent(task) - before if task is not None else Decimal("0")
    left = [d for d in (verdict or {}).get("differences") or [] if d["severity"] in ("blocking", "major")]
    if doc is not None:
        from apps.ire import legibility
        try:
            unresolved_contrast = legibility.remaining(doc)
        except Exception as exc:
            unresolved_contrast = [{'what': 'Contrast review unavailable: ' + str(exc)}]
        if doc.metadata.get('contrast_review_error'):
            unresolved_contrast.append({'what': 'Contrast repair could not be verified: ' + doc.metadata['contrast_review_error']})
        left += [{'kind': 'contrast', 'part': 'type and logo', 'severity': 'major',
                  'concept': 'readable required lettering', 'drawing': row['what']} for row in unresolved_contrast]
    return {"schema_version": SCHEMA, "state": ("PASS" if verdict and verdict["matches"] and not left else
                                                "NOT_LOOKED" if verdict is None else "DIFFERS"),
            "rounds": rounds, "fixed": fixed, "left": left,
            "minor": [d for d in (verdict or {}).get("differences") or [] if d["severity"] == "minor"],
            "checks": (verdict or {}).get("checks") or {},
            "summary": _said(verdict, "summary") if verdict else "", "cost_usd": str(cost), "dpi": EYE_DPI}


def _moved_to_read(doc) -> list:
    """[His goal after the pitch page, 2026-10-15, A (5).] The inks the drawing moved to read against what lies behind
    them (``ire.legibility``) — never moved back by the eye's recolour, look after paid look."""
    from apps.ire.legibility import MOVED_KEY
    held = doc.metadata.get(MOVED_KEY) if doc is not None and doc.metadata else None
    return list(held) if held else []


def _legible(doc) -> list:
    """[His goal after the pitch page, 2026-10-15, A (5): "logos and small text are always readable against what's
    behind them."] The eye's recolour never undoes a mark's or a line's contrast: each read again against what lies
    beneath it and moved the least it must (``ire.legibility.repair``) — one sentence each."""
    from apps.ire import legibility
    try:
        return [f["what"] for f in legibility.repair(doc) if f["fixed"] is True]
    except Exception as exc:  # noqa: BLE001 — the eye goes on; that the contrast was not read again is said
        doc.metadata['contrast_review_error'] = str(exc)
        return []


def _look_once(concept, draw, call, top=False) -> tuple:
    """``(verdict, None)`` — the looks of one round agreed (``agreed``): two looks at the drawing as drawn, a third
    where they disagree on any check; ``(None, what failed)`` where the eye could not look twice (a spending cap is
    never caught: it stops the design as every cap does)."""
    from apps.pipeline.services.cost_ledger import BudgetExceededError
    try:
        drawing = draw()
        looks = [look(concept, drawing, call=call, top=top), look(concept, drawing, call=call, top=top)]
        if _disagree(looks[0], looks[1]) and MAX_LOOKS > 2:
            looks.append(look(concept, drawing, call=call, top=top))
        return agreed(looks), None
    except BudgetExceededError:
        raise
    except Exception as exc:  # noqa: BLE001 — said by type, beside Approve
        return None, "%s: %s" % (type(exc).__name__, str(exc)[:200])


def _spent(task):
    from decimal import Decimal
    if task is None:
        return Decimal("0")
    from apps.pipeline.models import ApiCallRecord
    return sum((r.cost_usd for r in ApiCallRecord.objects.filter(task=task, operation=OPERATION)), Decimal("0"))


def shown(record: dict) -> list:
    """What the eye still sees, as the drawing's own check shows it beside Approve — one line a difference."""
    if record.get("state") == "PASS":
        return []
    if record.get("state") == "NOT_LOOKED":
        errors = [r["error"] for r in record.get("rounds") or [] if r.get("error")]
        why = errors[0] if errors else "it could not look"
        return [{"kind": "designer's eye", "fixed": False,
                 "what": "the designer's eye could not compare the drawing with its concept (%s) — look at them side "
                         "by side before approving" % why}]
    rows = [{"kind": "designer's eye", "fixed": False,
             "what": "%s (%s): the concept shows %s; the drawing shows %s" % (d["part"] or d["kind"], d["severity"],
                                                                             d["concept"], d["drawing"])}
            for d in record.get("left") or []]
    named = {d["check"] for d in record.get("left") or [] if "check" in d}
    for name, row in (record.get("checks") or {}).items():
        if not row["same"] and name not in named:
            rows.append({"kind": "designer's eye", "fixed": False,
                         "what": "%s differs from the concept: %s" % (CHECKS[name].split(" — ")[0],
                                                                      "; ".join(n for n in row["notes"] if n)[:300])})
    return rows


def summary_json(record: dict) -> str:
    return json.dumps({k: record.get(k) for k in ("state", "cost_usd", "summary")})
