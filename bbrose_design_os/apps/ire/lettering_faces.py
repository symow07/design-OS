"""[His goal after the pitch page, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A (1): "TYPOGRAPHY: every drawing falls back
to a plain sans. Classify the concept's lettering (serif / sans / script / condensed / display, weight, letter-spacing,
case, colour) and set each line in the closest granted face with the same weight, spacing, size and colour. Grant
suitable OFL faces from google/fonts where none fit (licence recorded), so every common style has a match."]

The granted face closest to a line of type as its concept letters it. The design map reads each line's style
(``concept_design_map.TYPE_STYLE_WORDS``: class, kind of serif, weight, italic, width, case, spacing); this module turns
that reading into a face of the granted set (``font_roles.catalogue``) and a weight — a variable face at exactly that
weight, a static one the nearest of its family's — and the font the line names (``font_roles.line_face_key``), which
the layer verifies and every emitter draws. A display or script line the picture letters is matched by its outline
first (``concept_design_map.set_display``); an Arabic line keeps its own role; a line with no reading keeps the role
it had. Every choice is a table below — the executor's, his to change."""
from __future__ import annotations

#: the weight each word of the read stands for (CSS / OpenType wght)
# [his last goal before the pitch, 2026-10-16, Step 2: "text ... readable (... washed-out lines)" — 128's "TIDE GLASS"
# set at 100, hairlines that wash out on its aqua] a line read thin is set at a light weight, the thinnest that prints
WEIGHTS = {"thin": 300.0, "light": 300.0, "regular": 400.0, "medium": 500.0, "semibold": 600.0, "bold": 700.0,
           "black": 900.0}
#: the faces of each style of lettering, closest first: ``(stem, weight, italic)`` — a variable face's weight None (it
#: draws at the weight asked, inside its own axis), a static face its own weight
FAMILIES = {
    # a fashion didone: thin hairlines, high stroke contrast
    "didone": (("PlayfairDisplay[wght]", None, False), ("PlayfairDisplay-Italic[wght]", None, True),
               ("Italiana-Regular", 200.0, False), ("DMSerifDisplay-Regular", 650.0, False),
               ("DMSerifDisplay-Italic", 650.0, True), ("AbrilFatface-Regular", 900.0, False)),
    # a soft garamond
    "old-style": (("CormorantGaramond[wght]", None, False), ("CormorantGaramond-Italic[wght]", None, True)),
    # a baskerville; a slab serif has no face of its own in the set and takes this, its nearest
    "transitional": (("LibreBaskerville[wght]", None, False), ("LibreBaskerville-Italic[wght]", None, True)),
    # a glyphic, chiselled roman — and its capitals, wide spaced
    "flared": (("Marcellus-Regular", 400.0, False), ("Cinzel[wght]", None, False)),
    "roman-capitals": (("Cinzel[wght]", None, False), ("Marcellus-Regular", 400.0, False)),
    # a clean geometric sans — and a wide one
    "sans": (("Jost[wght]", None, False), ("Jost-Italic[wght]", None, True)),
    "wide-sans": (("Montserrat[wght]", None, False), ("Montserrat-Italic[wght]", None, True)),
    # a tall condensed serif — [his review of 127, 130, 131 and 132, 2026-10-15, C (6): "130 and 132 a tall condensed
    # serif"]
    "condensed-serif": (("InstrumentSerif-Regular", 400.0, False), ("InstrumentSerif-Italic", 400.0, True),
                        ("Gloock-Regular", 650.0, False)),
    # a typewriter slab — [his goal after the pitch page, B (10): the lotion tube's "with colloidal oat"]
    "slab": (("CourierPrime-Regular", 400.0, False), ("CourierPrime-Bold", 700.0, False)),
    # a condensed sans
    "condensed": (("BarlowCondensed-Light", 300.0, False), ("BarlowCondensed-Regular", 400.0, False),
                  ("BarlowCondensed-Medium", 500.0, False), ("BarlowCondensed-SemiBold", 600.0, False),
                  ("BarlowCondensed-Bold", 700.0, False), ("BarlowCondensed-ExtraBold", 800.0, False),
                  ("Oswald[wght]", None, False)),
    # a script set live (one the picture letters as a name is matched by its outline first)
    "script": (("GreatVibes-Regular", 400.0, False), ("DancingScript[wght]", None, False)),
}
#: the family a serif's kind names; a serif read with no kind is a didone — the beauty house's serif
SERIF_FAMILY = {"high-contrast": "didone", "old-style": "old-style", "transitional": "transitional",
                "slab": "transitional", "flared": "flared", "none": "didone"}
#: the lettering word of an older read, where its line carries no style
CLASS_OF_LETTERING = {"serif": "serif", "sans": "sans", "script": "script", "display": "display"}
#: letter-spacing in ems for each spacing word of the read — the least a line so spaced is tracked
SPACING_EM = {"tight": 0.0, "normal": 0.0, "wide": 0.12, "very wide": 0.25}
#: a script line heavier than this draws in the family's weighted face (Dancing Script), lighter in Great Vibes
SCRIPT_HEAVY_FROM = 500.0


def family_of(style: dict, lettering: str | None) -> str | None:
    """The family of ``FAMILIES`` a line's style names, or None — a display line (matched by its outline), an Arabic
    line, or a line read with no style and no lettering."""
    cls = style.get("class") if style.get("class") else CLASS_OF_LETTERING.get(lettering or "")
    if cls is None or cls == "display" or lettering == "arabic":
        return None
    if (cls == "serif" and style.get("width") == "condensed") or (
            cls == "condensed" and style.get("serif") in SERIF_FAMILY and style.get("serif") != "none"):
        return "condensed-serif"
    if cls == "serif" and style.get("serif") == "slab":
        return "slab"
    if cls == "serif":
        kind = style.get("serif") if style.get("serif") in SERIF_FAMILY else "none"
        if kind == "none" and style.get("case") == "upper" and style.get("spacing") in ("wide", "very wide"):
            return "roman-capitals"
        return SERIF_FAMILY[kind]
    if cls == "condensed" or (cls == "sans" and style.get("width") == "condensed"):
        return "condensed"
    if cls == "sans":
        return "wide-sans" if style.get("width") == "wide" else "sans"
    if cls == "script":
        return "script"
    return None


def weight_of(style: dict, measured: str | None) -> float:
    """The weight a line is read in: its style's word, else its letters' measured weight (``trace_type``), else
    regular."""
    if style.get("weight") in WEIGHTS:
        return WEIGHTS[style["weight"]]
    return WEIGHTS["bold"] if measured == "bold" else WEIGHTS["regular"]


def faces_of(family: str) -> tuple:
    """[D-D7-1, 2026-10-19] the faces of a lettering family: the brand faces of ``FAMILIES`` first, closest first as before,
    then the GRANTED pool's faces of that family (``font_pool.chain``: a class read from each face's names and OS/2 width, a
    heuristic the record states), alphabetical — the enlarged candidate set of row 12."""
    from apps.ire import font_pool
    return tuple(FAMILIES.get(family, ())) + font_pool.chain(family)


def pick(family: str, weight: float, italic: bool) -> tuple[str, float] | None:
    """``(stem, weight)``: the face of ``family`` closest to ``weight`` and ``italic`` that sits in the granted set — a
    variable face at the weight asked, inside its axis; a static face at its own. None where no face of it is granted."""
    from apps.ire.font_roles import catalogue
    cat = catalogue()
    best = None
    for stem, own, slanted in faces_of(family):
        entry = cat.get(stem)
        if entry is None:
            continue
        if own is None:
            axis = (entry.get("axes") or {}).get("wght")
            if axis is None:
                continue
            at = min(max(weight, axis[0]), axis[2])
        else:
            at = own
        if family == "script" and own is not None and weight >= SCRIPT_HEAVY_FROM:
            at = own + 1000.0                      # a heavy script line: the weighted face first
        cost = (0 if slanted == italic else 1000) + abs(at - weight)
        if best is None or cost < best[0]:
            best = (cost, stem, own if own is not None else at)
    return (best[1], best[2]) if best else None


def choose(line: dict) -> dict | None:
    """The face a traced line (``concept_design_map.trace_type``'s record) is set in: ``{"font", "stem", "weight",
    "family", "label", "path", "tracking_em", "upper", "why"}`` — None where its line was read with no style, its style
    names no family of the set (``family_of``), or no face of it verifies (the line keeps the role it had)."""
    style = line.get("style") if isinstance(line.get("style"), dict) else {}
    if not style:
        return None                    # a line read before its style was asked keeps the face it had
    family = family_of(style, line.get("lettering"))
    if family is None:
        return None
    weight = weight_of(style, line.get("weight"))
    picked = pick(family, weight, bool(style.get("italic")))
    if picked is None:
        return None
    return _face_of(line, style, family, picked)


def _face_of(line: dict, style: dict, family: str, picked: tuple) -> dict | None:
    """``choose``'s face for ``picked`` (``(stem, weight)``), verified through the seam — None where it does not."""
    from apps.ire.font_roles import line_face_key, resolve_line_face
    r = resolve_line_face(*picked)
    if r.get("refused"):
        return None
    spacing = style.get("spacing") if style.get("spacing") in SPACING_EM else line.get("spacing")
    return {"font": line_face_key(*picked), "stem": picked[0], "weight": picked[1], "family": family,
            "label": r["label"], "path": r["path"], "tracking_em": SPACING_EM[spacing] if spacing in SPACING_EM else 0.0,
            "upper": style.get("case") in ("upper", "small-caps"),
            "why": "%s, %s%s, as the concept letters it" % (family, ("%g" % picked[1]),
                                                           " italic" if style.get("italic") else "")}


def by_proportion(line: dict, face: dict | None, along_per_across: float, ink_em: float) -> dict | None:
    """[His fixes to 142 (Cherry Kiss), 2026-10-17, (1): "set vertically in a matching script face"] a script line the
    picture stands on end, its letters too small for a tracer, is set in the granted script whose letters run closest to
    the picture's own — the length of its words for their height (``ink_em`` of a size) nearest the box's length for its
    width, ``along_per_across`` — at the weight its read names, inside each face's own axis; ``face`` (``choose``'s) for
    any other line, or where none measures."""
    import math

    from apps.ire.compose_container import _INK_MM_PER_PT
    from apps.ire.font_roles import catalogue
    if face is None or face["family"] != "script" or along_per_across <= 0.0:
        return face
    style = line.get("style") if isinstance(line.get("style"), dict) else {}
    weight = weight_of(style, line.get("weight"))
    cat = catalogue()
    best = None
    for stem, own, _slanted in faces_of("script"):
        entry = cat.get(stem)
        if entry is None:
            continue
        if own is None:
            axis = (entry.get("axes") or {}).get("wght")
            if axis is None:
                continue
            at = min(max(weight, axis[0]), axis[2])
        else:
            at = own
        got = _face_of(line, style, "script", (stem, at))
        length = width_mm(got, line["words"], 1.0, got["tracking_em"]) if got is not None else None
        if not length:
            continue
        miss = abs(math.log(length / (ink_em * _INK_MM_PER_PT) / along_per_across))
        if best is None or miss < best[0]:
            best = (miss, got)
    if best is None:
        return face
    return dict(best[1], why=best[1]["why"] + "; of the granted scripts, the one whose letters run closest to the "
                                              "picture's own for their height")


def width_mm(face: dict, text: str, size_pt: float, tracking_em: float = 0.0) -> float | None:
    """``text``'s drawn width in ``face`` at ``size_pt``, tracking included — the emitter's own measure
    (``text_metrics.drawn_width_mm``); None where the face cannot measure it."""
    from apps.ire.compose_container import _INK_MM_PER_PT
    from apps.ire.text_metrics import drawn_width_mm
    size_mm = size_pt * _INK_MM_PER_PT
    drawn = drawn_width_mm(text, size_mm, face["label"])
    if drawn is None:
        return None
    return drawn + tracking_em * size_mm * max(len(text) - 1, 0)


def cap_em(face: dict) -> float:
    """The face's capital height in ems, read from its file."""
    from apps.ire.text_metrics import cap_height_em
    return cap_height_em(face["path"])
