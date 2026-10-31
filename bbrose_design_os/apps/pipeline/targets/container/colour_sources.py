"""WHICH RECORD EACH CONTAINER COLOUR COMES FROM — §BH65(b)2.

The owner: "The lid takes the detailing colour as its field colour. Fix it, and say which record each colour
should come from."

WHAT ACTUALLY HAPPENED, MEASURED ON EVERY CONTAINER OUTPUT IN THE TABLE. The lid colour was the first `#RRGGBB`
found in the concept's `cap_color` sentence, and when that sentence held NO hex the lid took
`_DEFAULT_CAP_HEX = "#C9A24B"` — a flat gold. Six of the nine container outputs were painted with that constant
(tasks 53, 54, 55, 56, 57 and 89), and task 88's concept — "Deep rose-plum gloss cap" — would have been the
seventh. Task 89's concept said "Lid in matte soft-touch warm cream with rose-gold foil detailing", and its own
ground sentence said "Warm Cream #FAF3EC ground across the full lid face". The lid was painted gold.

HIS DIAGNOSIS IS EXACT AT THE LEVEL OF THE BRAND'S OWN RECORD. The gold is not arbitrary: it is the flat stand-in
for the brand ColorSystem's Metallic swatch — Rose Gold, "Metallic 10122 C", whose usage the brand wrote as
"Caps, closures, foil detail". On a BOTTLE the cap is a closure, and that is the brand's own rule. On a COMPACT
the "cap" in this colour model is the LID FACE — the whole top surface, the one the drawing shows in plan and the
one the artwork sits on — and the brand's rule for that surface is the Ground: Warm Cream, "Base packaging,
backgrounds". The lid face took the closure-and-foil-detail colour as its field colour. That is his sentence.

THE RECORD EACH COLOUR COMES FROM, IN ORDER — the answer he asked for, and it is written into every spec as
`container_colour_sources/1.0` so it is on the record for every run and not only in a report:

  LID FACE (a form drawn in PLAN — the compact)
    1. the concept's own LID sentence (`cap_color`): its first FIELD colour — a hex, or a brand palette name
    2. the concept's own GROUND sentence (`body_base_color`): its first FIELD colour — a compact's concept says
       its ground covers "the full lid face"
    3. the brand ColorSystem's Ground swatch — "Base packaging, backgrounds"
    never the Metallic swatch, which the brand reserves for "Caps, closures, foil detail"

  CLOSURE CAP (a form drawn in ELEVATION — bottle, jar, tube) — UNCHANGED BY THIS COMMIT
    1. the first hex in the concept's `cap_color`
    2. the brand Metallic swatch, flat stand-in `#C9A24B` because 10122 C carries no hex — the brand's own rule
       for caps and closures, now named instead of anonymous

  BODY     the colour MEASURED from the approved concept image (unchanged)
  PRODUCT  the first hex in the concept's `body_base_color`, else the cap's (unchanged)

A FIELD COLOUR VERSUS A DETAIL COLOUR, as a rule and not a guess. Every colour the sentence names — a hex, or a
name from the brand's own palette record — is a MENTION. A detail word (foil, detailing, accent, type, band,
seam, trim, emboss, print …) belongs to the nearest mention BEFORE it, and a mention that owns one is a DETAIL
colour, as is any swatch the brand classes Metallic. The field colour is the first mention that is neither. So
"warm cream with rose-gold foil detailing" reads warm cream as the field and rose-gold as the detail, and
"rose-gold #B76E79 foil border on a Warm Cream #FAF3EC lid" reads #FAF3EC, never the foil.

Pure: no Django, no ORM. The palette is handed in by the caller.
"""
from __future__ import annotations

import re

SCHEMA = "container_colour_sources/1.0"

_HEX = re.compile(r"#[0-9A-Fa-f]{6}")

#: A detail word attaches to the nearest colour mentioned BEFORE it.
DETAIL_WORDS = frozenset("""
    foil foils detail details detailing accent accents trim trims band bands stamp stamping stamped
    emboss embossed embossing deboss debossed print printed printing type typography logo logos
    lettering line lines linework seam seams edge edging keyline keylines hairline hairlines rule rules
""".split())

#: The brand's own role for the swatch reserved to closures and foil detail.
METALLIC_ROLE = "Metallic"
GROUND_ROLE = "Ground"


def _flat(text: str) -> str:
    """Same LENGTH as the input, so positions carry across: lower-case, and a hyphen or underscore read as a
    space so `rose-gold` meets `Rose Gold`."""
    return text.lower().replace("-", " ").replace("_", " ")


def _swatches(palette):
    """(role, name, hex-or-None) from the brand's ColorSystem swatches; a swatch whose `hex` is not a real
    `#RRGGBB` (Rose Gold is `Metallic 10122 C`) keeps its name and role and carries no hex."""
    out = []
    for sw in palette or []:
        if not isinstance(sw, dict) or not sw.get("name"):
            continue
        raw = str(sw.get("hex") or "")
        out.append((str(sw.get("role") or ""), str(sw["name"]),
                    raw.upper() if _HEX.fullmatch(raw) else None))
    return out


def mentions(text: str, palette) -> list[dict]:
    """Every colour the sentence names, in order: `{start, end, hex, name, role}`."""
    text = text or ""
    flat = _flat(text)
    found = [{"start": m.start(), "end": m.end(), "hex": m.group(0).upper(), "name": None, "role": "hex"}
             for m in _HEX.finditer(text)]
    for role, name, hx in sorted(_swatches(palette), key=lambda s: -len(s[1])):
        pat = re.compile(r"(?<![a-z])" + re.escape(_flat(name)) + r"(?![a-z])")
        for m in pat.finditer(flat):
            if any(not (m.end() <= f["start"] or m.start() >= f["end"]) for f in found):
                continue
            found.append({"start": m.start(), "end": m.end(), "hex": hx, "name": name, "role": role})
    found.sort(key=lambda f: f["start"])
    merged: list[dict] = []
    for f in found:
        # "Warm Cream #FAF3EC", "Ivory (#FAF3EC)": a name immediately followed by a hex is ONE mention
        if (merged and merged[-1]["role"] != "hex" and f["role"] == "hex"
                and not text[merged[-1]["end"]:f["start"]].strip(" (")):
            merged[-1]["hex"], merged[-1]["end"] = f["hex"], f["end"]
            continue
        merged.append(dict(f))
    return merged


#: [his test day finding 3, 2026-09-30: "Hot pink (#E91E8C)", "soft pink (#F7B8D4)" — a colour's own words with the
#: hex a sentence writes beside them]
_NAMED_HEX = re.compile(r"([A-Za-z][A-Za-z\- ]{1,40}?)\s*\(\s*(#[0-9A-Fa-f]{6})\s*\)")


def named_hexes(text: str) -> dict:
    """``{colour words: hex}`` for every colour a sentence names beside its hex, the words lower-cased — "Hot pink
    (#E91E8C) solid upper two-thirds / soft pink (#F7B8D4)" gives {"hot pink": "#E91E8C", "soft pink": "#F7B8D4"}."""
    out = {}
    for m in _NAMED_HEX.finditer(text or ""):
        out.setdefault(" ".join(m.group(1).lower().split()), m.group(2).upper())
    return out


def cap_colour(cap_words: str, body_words: str, palette) -> tuple[str | None, str | None]:
    """A closure cap's colour from its concept's own words — ``(hex, what named it)`` or ``(None, None)``. [His test day
    finding 3, 2026-09-30, design 117: its cap words said "Flip-top cap in matching full-gloss hot pink" and named no
    hex, so the drawing took the stand-in gold #C9A24B — "invented a colour".] The cap's own hex; else a brand swatch
    its words name, with a hex; else the colour its words name as the body sentence gives it a hex — the longest run of
    that colour's words the cap's words hold, "hot pink" before "pink"."""
    text = cap_words or ""
    for m in mentions(text, palette):
        if m["hex"] and m["hex"].startswith("#"):
            return m["hex"], ("its own hex" if m["role"] == "hex" else "the brand's %s, which its words name" % m["name"])
    flat = " ".join(text.lower().split())
    best = None
    for words, hx in named_hexes(body_words).items():
        parts = words.split()
        for k in range(len(parts), 0, -1):
            phrase = " ".join(parts[-k:])
            if re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", flat):
                if best is None or k > best[0]:
                    best = (k, phrase, hx)
                break
    if best is not None:
        return best[2], "the colour its words name — \"%s\" — as the concept's body sentence gives it" % best[1]
    return None, None


def field_colour(text: str, palette) -> tuple[str | None, str | None]:
    """The first FIELD colour the sentence names — `(hex, what named it)` — or `(None, None)`."""
    text = text or ""
    ms = mentions(text, palette)
    for i, m in enumerate(ms):
        stop = ms[i + 1]["start"] if i + 1 < len(ms) else len(text)
        window = text[m["end"]:stop].split(";")[0]
        detail = bool(set(re.findall(r"[a-z]+", window.lower())) & DETAIL_WORDS)
        if detail or m["role"] == METALLIC_ROLE or not m["hex"]:
            continue
        return m["hex"], (m["name"] or "an explicit hex")
    return None, None


def ground_swatch(palette) -> str | None:
    for role, _name, hx in _swatches(palette):
        if role == GROUND_ROLE and hx:
            return hx
    return None


def metallic_hex(palette, stand_in: str) -> tuple[str, str]:
    """§BH65(c)2 — the colour a METAL finish depicts in on page 1: the brand's own Metallic swatch — "Caps,
    closures, foil detail" — when it carries a hex, else ``stand_in``, the flat stand-in this module already names
    for it. A depiction, never a plate."""
    for role, name, hx in _swatches(palette):
        if role == METALLIC_ROLE and hx:
            return hx, "the brand ColorSystem's Metallic swatch — %s" % name
    return stand_in, ("the brand Metallic swatch's flat stand-in %s — the record carries no hex (10122 C)"
                      % stand_in)


def lid_face_colour(fields: dict, palette) -> tuple[str | None, str]:
    """§BH65(b)2 — the colour of a lid FACE (a form drawn in plan), and the record it came from."""
    def _text(name):
        return str(((fields or {}).get(name) or {}).get("value") or "")
    for field in ("cap_color", "body_base_color"):
        hx, what = field_colour(_text(field), palette)
        if hx:
            return hx, "the concept's own `%s` sentence — %s" % (field, what)
    hx = ground_swatch(palette)
    if hx:
        return hx, "the brand ColorSystem's Ground swatch — \"Base packaging, backgrounds\""
    return None, "no concept sentence and no brand Ground swatch names a colour"


# ---------------------------------------------------------------------------------------------------------------
# §BH67 HARD STOP — "a finish or colour applied that nothing specified". Measured on task 91's drawn lid: the name
# and its Arabic line printed in `#5A2C3A`, a constant the composer carried from the dropper's palette (TYPE_WINE,
# "authority UNVERIFIED", kept for task 52 by §BH50(f)(9)) while the concept says "in Deep Rose" and the brand's own
# record gives Deep Rose the usage "Typography, fine detail lines"; the motif printed `#F7EFE4`, `#D9B49A` and
# `#B76E79`, the design language's DEFAULT_SWATCHES, which neither the concept nor the brand record names. Every
# colour the composer PRINTS now comes from one of three records, and the run says which:
#   the concept's own words (a hex, or a name from the brand's palette record) · a measurement of the approved
#   concept image · the brand ColorSystem swatch whose ROLE or USAGE the brand wrote for that job.
# ---------------------------------------------------------------------------------------------------------------

PRINTED_SCHEMA = "container_printed_colours/1.0"
UNSOURCED_CODE = "CONTAINER_COLOUR_UNSOURCED"
#: [his test blocker on design 124, 2026-10-11, (3)] the lid's art, drawn whole (``targets.container.lid_art``), and
#: where every colour it prints comes from
LID_ART_GROUP = "LID ART"
LID_ART_SOURCE = ("the lid's flat redraw, traced in colour — its sky's gradients and its illustration's regions, every "
                  "colour read from the redraw's own pixels")

#: the words that mark a colour mention as the TYPE's in a colour sentence ("Deep Rose type", "cocoa lettering")
_TYPE_WORDS = frozenset("type typography lettering name names wordmark text copy".split())


def _usage_swatch(palette, word: str) -> tuple[str | None, str | None]:
    """The first swatch whose USAGE the brand wrote names ``word`` — `(hex, what named it)`."""
    for sw in palette or []:
        if not isinstance(sw, dict):
            continue
        raw = str(sw.get("hex") or "")
        if word in str(sw.get("usage") or "").lower() and _HEX.fullmatch(raw):
            return raw.upper(), "the brand ColorSystem's %s swatch %s — its usage \"%s\"" % (
                sw.get("role"), sw.get("name"), sw.get("usage"))
    return None, None


def type_ink(structured: dict | None, palette) -> tuple[str | None, str]:
    """The colour the product's TYPE prints in, and the record it came from: 1. the concept's own typography
    sentence — the first colour it names that is not the Metallic ("… set above the petal window in Deep Rose");
    2. a colour the colour-field sentence gives the type ("Deep Rose type"); 3. the brand's swatch whose usage is
    "Typography" (Deep Rose, "Typography, fine detail lines"). None only when all three are silent."""
    structured = structured or {}
    typo = str(structured.get("typography_signature") or "")
    for m in mentions(typo, palette):
        if m["hex"] and m["role"] != METALLIC_ROLE:
            return m["hex"], "the concept's own `typography_signature` — %s" % (m["name"] or "an explicit hex")
    field = str(structured.get("color_field_signature") or "")
    ms = mentions(field, palette)
    for i, m in enumerate(ms):
        stop = ms[i + 1]["start"] if i + 1 < len(ms) else len(field)
        window = set(re.findall(r"[a-z]+", field[m["end"]:stop].split(";")[0].lower()))
        if m["hex"] and m["role"] != METALLIC_ROLE and window & _TYPE_WORDS:
            return m["hex"], "the concept's own `color_field_signature` — %s, named for the type" % (
                m["name"] or "an explicit hex")
    hx, what = _usage_swatch(palette, "typograph")
    if hx:
        return hx, what
    return None, "no concept sentence and no brand swatch names a colour for type"


def motif_colours(structured: dict | None, palette, *, ground_hex: str | None) -> list[tuple[str, str]]:
    """The colours the product's MOTIF prints in, in the order the concept names them, each with its record: every
    colour the motif sentence and then the colour-field sentence name that is neither the ground (the surface the
    motif sits on) nor the Metallic (a metal is a FINISH, plated and depicted, §BH65(c)2). When the concept names
    none, the brand's own Primary, Secondary and Accent swatches, in that order."""
    structured = structured or {}
    out: list[tuple[str, str]] = []
    for field in ("motif_signature", "color_field_signature"):
        for m in mentions(str(structured.get(field) or ""), palette):
            hx = m["hex"]
            if (hx and m["role"] != METALLIC_ROLE and hx.upper() != (ground_hex or "").upper()
                    and hx not in [h for h, _ in out]):
                out.append((hx, "the concept's own `%s` — %s" % (field, m["name"] or "an explicit hex")))
    if out:
        return out
    for role in ("Primary", "Secondary", "Accent"):
        for sw_role, name, hx in _swatches(palette):
            if sw_role == role and hx and hx not in [h for h, _ in out]:
                out.append((hx, "the brand ColorSystem's %s swatch %s — the concept names no motif colour"
                            % (role, name)))
                break
    return out


#: [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines."] the word the brand wrote into the usage of the swatch
#: a face's fine LINES print in when the concept's own words give them no colour — Deep Rose, "Typography, fine detail
#: lines" on this brand's record
LINE_USAGE_WORD = "fine detail"


def line_colour(structured: dict | None, palette, *, element: str, stand_in: str) -> tuple[str | None, str]:
    """[the owner's second answer of 2026-09-25 — and §BH67's hard stop over it: "a finish or colour applied that
    nothing specified".] The colour one of a face's own LINES prints in — ``element`` "rule" [or "ring": task 110's
    "Deep Rose (#8B3A52) for all name type and rim rule"] — and the record it came from, in order:
      1. the colour the concept's own words give that line: in each clause that names it
         (``concept_front.lines``), the colour mentioned NEAREST BEFORE it — this module's own rule for a detail word
         — the colour-field sentence read first. A METAL there ("Rose Gold hot-foil on BBROSE lockup and hairline
         rule") is a finish and not an ink: the line prints in the metal's depiction (``metallic_hex`` — the brand
         Metallic swatch, or its flat stand-in ``stand_in`` when the record carries no hex) and the finish reader
         plates it;
      2. the brand ColorSystem swatch whose USAGE names fine detail lines (``LINE_USAGE_WORD``).
    Never the type ink by accident: the type's colour is ``type_ink``'s, read for the type. None only when both are
    silent, and the audit then refuses the stand-in the composer prints by name."""
    from apps.ire.concept_front import lines
    said = lines(structured).get(element)
    hits = sorted(said if said is not None else [], key=lambda h: h["field"] != "color_field_signature")
    for hit in hits:
        before = [m for m in mentions(hit["clause"], palette) if m["end"] <= hit["at"]]
        if not before:
            continue
        m = before[-1]
        if m["role"] == METALLIC_ROLE:
            hx, what = metallic_hex(palette, stand_in)
            return hx, ("the concept's own `%s` — %s, a metal, named for its %s (%r): it prints in the metal's "
                        "depiction, %s" % (hit["field"], m["name"], element, hit["words"], what))
        if m["hex"]:
            return m["hex"], "the concept's own `%s` — %s, named for its %s (%r)" % (
                hit["field"], m["name"] or "an explicit hex", element, hit["words"])
    hx, what = _usage_swatch(palette, LINE_USAGE_WORD)
    if hx:
        return hx, "%s — the concept's own words give its %s no colour" % (what, element)
    return None, "no concept sentence and no brand swatch names a colour for a %s" % element


def body_colour(structured: dict | None, palette) -> tuple[str | None, str | None]:
    """The BODY's colour from the concept's own words, when its cap/body sentence gives the base or body one ("Lid
    and base both in matte soft-touch Warm Cream"). A measurement of the concept image is the fallback, not the
    first record: measured on task 91 it read `#958879`, the shadowed sidewall, where the words say Warm Cream."""
    text = str((structured or {}).get("cap_body_signature") or "")
    for clause in re.split(r"[;\n]", text):
        body = re.search(r"(?<![a-z])(base|body|case)(?![a-z])", clause.lower())
        if not body:
            continue
        # the colour named AFTER the body word is the body's: "Deep rose-plum gloss cap … with the body's upper
        # blush-rose gradient field" gives the cap Deep Rose and the body Blush (task 88, measured)
        ms = mentions(clause, palette)
        for i, m in enumerate(ms):
            if m["start"] < body.end() or not m["hex"] or m["role"] == METALLIC_ROLE:
                continue
            stop = ms[i + 1]["start"] if i + 1 < len(ms) else len(clause)
            if set(re.findall(r"[a-z]+", clause[m["end"]:stop].lower())) & DETAIL_WORDS:
                continue
            return m["hex"], "the concept's own `cap_body_signature` — %s" % (m["name"] or "an explicit hex")
    return None, None


#: [his test day finding 3, 2026-09-30] the words that place a colour field on the body, at its top or at its foot
_FIELD_PLACE = re.compile(r"(?<![a-z])(upper|top|lower|bottom)(?![a-z])")


def colour_fields(structured: dict | None, palette) -> list[tuple[str, str]]:
    """[His test day finding 3, 2026-09-30, design 117: "the chosen pink is wrong" — his concept's body is two colours,
    "Hot pink (#E91E8C) solid upper two-thirds / soft pink (#F7B8D4) lower one-third", and the drawing painted one.]
    The body's two colour fields the concept's own `color_field_signature` names — ``[(upper hex, its words), (lower
    hex, its words)]`` — each part placed by its own word (upper or top; lower or bottom) and coloured by its own hex,
    else the brand swatch it names; [] unless both are named."""
    text = str((structured or {}).get("color_field_signature") or "")
    upper, lower = None, None
    for part in re.split(r"\s/\s|;", text):
        where = _FIELD_PLACE.search(part.lower())
        if where is None:
            continue
        hexes = list(named_hexes(part).values())
        if not hexes:
            hexes = [m["hex"] for m in mentions(part, palette) if m["hex"] and m["role"] != METALLIC_ROLE]
        if not hexes:
            continue
        field = (hexes[0].upper(), part.strip())
        if where.group(1) in ("upper", "top"):
            upper = upper or field
        else:
            lower = lower or field
    return [upper, lower] if upper and lower else []


def field_split(axis_colours: list, shares: list, upper_hex: str, lower_hex: str, *, closure_share,
                turned: bool) -> float | None:
    """[His test day finding 3, 2026-09-30] Where the upper colour field meets the lower, as a share of the drawing's
    height from its top — MEASURED ON THE CONCEPT PICTURE, which gives the proportions (§BH71 PART 1): the product's
    colour down its axis (``concept_outline``'s ``axis_colours`` at the heights ``shares``, read standing narrow end
    up; ``turned`` when the drawing stands it the other way), its closure's own heights left out, every other height
    given to the nearer of the two fields' colours, the split put where the fewest heights disagree with it — the upper
    field most of the heights above it and the lower most of those below. None when no split holds both."""
    from apps.ire.container_brand_usage import _delta_e_hex
    rows = []
    for t, hx in zip(shares, axis_colours):
        if hx is None or (closure_share is not None and float(t) < float(closure_share)):
            continue                                    # no pixel there, or the closure's own heights
        du, dl = _delta_e_hex(hx, upper_hex), _delta_e_hex(hx, lower_hex)
        if du is None or dl is None:
            continue
        rows.append((1.0 - float(t) if turned else float(t), du <= dl))
    rows.sort()
    best, at = None, None
    for k in range(1, len(rows)):
        above, below = rows[:k], rows[k:]
        ups_above = sum(1 for _d, up in above if up)
        ups_below = sum(1 for _d, up in below if up)
        if 2 * ups_above <= len(above) or 2 * (len(below) - ups_below) <= len(below):
            continue
        wrong = (len(above) - ups_above) + ups_below
        if best is None or wrong < best:
            best, at = wrong, (rows[k - 1][0] + rows[k][0]) / 2.0
    return round(at, 4) if at is not None else None


def printed_colour_audit(doc, sourced: dict[str, str]) -> dict:
    """§BH67's hard stop, made a check the run cannot pass silently: every colour a PRINTED element of the product
    carries — the leaves of the product's decoration groups and of the sheet's surface panels: type, rule, ring,
    window, motif, field, their shadows — must be one ``sourced`` names (hex -> the record it came from). The
    material a container is made of (body, cap, glass, frost) is not print and is recorded in `colors`; a finish's
    depiction is painted by the emitter and plated on its own page; what names the drawing is not printed — a text run
    the composer itself declared a SHEET ANNOTATION (``print_scope``: a panel's label, its info placeholder) and a
    wrap panel's seam marker, the registration reference. Returns the record, with one CONTAINER_COLOUR_UNSOURCED code
    per colour no record names."""
    from apps.ire.graph import SHEET_ANNOTATION, GradientFill, Group, SolidFill, TextRun
    want = {h.upper(): src for h, src in (sourced or {}).items() if h}
    # [His goal after the pitch page, 2026-10-15, A (5): "logos and small text are always readable".] an ink the
    # drawing moved in lightness to read against what lies behind it (``ire.legibility``) is the colour it was chosen
    # in, moved: that colour's record is its record, and a colour no record names is named as it was chosen
    from apps.ire.legibility import MOVED_KEY
    moved = {str(k).upper(): str(v).upper() for k, v in ((doc.metadata or {}).get(MOVED_KEY) or {}).items()}
    for now, chosen in moved.items():
        if want.get(chosen) and now not in want:
            want[now] = "%s — its lightness moved from %s to read against what lies behind it" % (want[chosen], chosen)
    first_node: dict[str, str] = {}
    printed: dict[str, dict] = {}
    undeclared: list[str] = []          # §BH50(f)(1): a run with no declaration fails closed — read as print, named

    def colours(node):
        fill, stroke = getattr(node, "fill", None), getattr(node, "stroke", None)
        if isinstance(fill, SolidFill):
            yield fill.color
        elif isinstance(fill, GradientFill):
            yield from (st.color for st in fill.stops)
        if stroke is not None and getattr(stroke, "color", None) is not None:
            yield stroke.color
        if isinstance(node, TextRun) and getattr(node, "color", None) is not None:
            yield node.color
        shadow = getattr(node, "shadow", None)
        if shadow is not None:
            yield shadow.color

    lid_art: set = set()

    def art_colours(node):
        for c in colours(node):
            lid_art.add(c.to_hex().upper())
        for child in getattr(node, "children", ()) or ():
            art_colours(child)

    def walk(node, printed_branch):
        is_group = isinstance(node, Group)
        if is_group and node.name == LID_ART_GROUP:
            # [his test blocker on design 124, 2026-10-11, (3)] the lid's art: every colour its flat redraw's own, read
            # from it as it was traced — said once for them all, never one row each for its thousands of shades
            art_colours(node)
            return
        here = printed_branch or (is_group and (node.role == "decoration" or node.name == "Surfaces"))
        # the drawing's own furniture is never printed: a run the composer DECLARED a sheet annotation (a panel's
        # "BASE BOTTOM" label, its "INFO · INCI · CODE" placeholder), and a wrap panel's seam marker
        scope = getattr(getattr(node, "print_scope", None), "kind", None)
        if here and isinstance(node, TextRun) and scope is None:
            undeclared.append(node.name or "TextRun")
        if here and scope != SHEET_ANNOTATION and not (node.name or "").startswith("seam-"):
            for c in colours(node):
                hx = c.to_hex().upper()
                row = printed.setdefault(hx, {"source": want.get(hx), "nodes": []})
                first_node.setdefault(moved.get(hx, hx), node.name or type(node).__name__)
                if len(row["nodes"]) < 6:
                    row["nodes"].append(node.name or type(node).__name__)
        if is_group:
            for child in node.children:
                walk(child, here)

    for top in getattr(doc.root, "children", ()):
        if isinstance(top, Group) and (top.role == "product" or top.name == "Surfaces"):
            walk(top, top.name == "Surfaces")
    codes = sorted({"%s:%s:%s" % (UNSOURCED_CODE, moved.get(hx, hx), first_node[moved.get(hx, hx)])
                    for hx, row in printed.items() if not row["source"]})
    # READ, said on the record: an empty code list beside it is a clean product, never "the check did not run"
    return {"schema_version": PRINTED_SCHEMA, "state": "READ", "printed": printed, "sourced": want,
            "undeclared_read_as_print": undeclared, "codes": codes,
            **({"lid_art": {"colours": len(lid_art), "source": LID_ART_SOURCE}} if lid_art else {})}


__all__ = ["SCHEMA", "DETAIL_WORDS", "mentions", "field_colour", "ground_swatch", "metallic_hex",
           "lid_face_colour", "PRINTED_SCHEMA", "UNSOURCED_CODE", "type_ink", "motif_colours", "body_colour",
           "printed_colour_audit", "LINE_USAGE_WORD", "line_colour"]
