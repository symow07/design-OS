"""Heuristic style observations (DIP-0C4c).

**A review aid, and nothing more.** A style tag never touches licence state, ownership,
permission, or quarantine. It exists so a human scanning 2,832 families can find the
serif they need — not so a machine can decide anything.

**Nothing is derived from a filename.** The evidence is `OS/2.panose`, the subfamily name
(name IDs 2/17), weight/width class, the italic flag, glyph count and script coverage —
all of it metadata the font declares about itself.

**And most of this corpus declares nothing.** PANOSE is `[0,0,0,0,…]` — meaning *"any /
unset"* — on the majority of the indie and free fonts here. Sinkin Sans and Almarai both
zero it out; only the Microsoft fonts fill it in. So a large share of faces get **no style
tag at all**, and that is the correct answer: silence, not a guess. A confident tag on a
font that told us nothing would be worse than no tag.
"""
from __future__ import annotations

import warnings

from . import config as C

PARSER = f"{C.TOOL_NAME}.font_style/{C.TOOL_VERSION}"
SCHEMA_VERSION = "font_style/1.0"

try:
    from fontTools.ttLib import TTCollection, TTFont
except ImportError:                                   # pragma: no cover
    TTFont = TTCollection = None

# --- tags (all HEURISTIC) --------------------------------------------------------
SERIF = "serif"
SANS = "sans"
HANDWRITTEN = "handwritten"
DISPLAY = "display"
BODY_CANDIDATE = "body candidate"
CONDENSED = "condensed"
EXTENDED = "extended"
HIGH_CONTRAST = "high contrast"
GEOMETRIC = "geometric"
HUMANIST = "humanist"
MONOSPACE = "monospace"
LUXURY_CANDIDATE = "luxury candidate"
PLAYFUL_CANDIDATE = "playful candidate"
CLINICAL_CANDIDATE = "clinical candidate"
TAGS = (SERIF, SANS, HANDWRITTEN, DISPLAY, BODY_CANDIDATE, CONDENSED, EXTENDED,
        HIGH_CONTRAST, GEOMETRIC, HUMANIST, MONOSPACE, LUXURY_CANDIDATE,
        PLAYFUL_CANDIDATE, CLINICAL_CANDIDATE)

# Confidence is CAPPED. A style read from metadata is a hint, never a judgement.
CONF_PANOSE = 0.6            # the font told us, in a field designed to say it
CONF_METRICS = 0.4           # inferred from weight/width/glyph count
CONF_SUBFAMILY = 0.3         # the font's own subfamily string (metadata, not filename)
CONF_CAP = 0.6

# PANOSE family types (byte 0)
PAN_FAMILY = {2: "text", 3: "script", 4: "decorative", 5: "pictorial"}
# PANOSE serif style (byte 1): 11-15 are the sans-serif range
PAN_SANS_RANGE = range(11, 16)


def _panose(path: str, index: int) -> list[int] | None:
    """Read OS/2.panose for ONE face. Read-only; the file is never modified."""
    if TTFont is None:                                # pragma: no cover
        return None
    p = C.SOURCE_ROOT.parent / path
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if p.suffix.lower() in (".ttc", ".otc"):
                coll = TTCollection(str(p), lazy=True)
                f = coll.fonts[index]
                pan = getattr(f.get("OS/2"), "panose", None)
                out = _pan_list(pan)
                coll.close()
                return out
            f = TTFont(str(p), lazy=True, fontNumber=0)
            pan = getattr(f.get("OS/2"), "panose", None)
            out = _pan_list(pan)
            f.close()
            return out
    except Exception:                                 # noqa: BLE001
        return None


def _pan_list(pan) -> list[int] | None:
    if pan is None:
        return None
    return [getattr(pan, f"b{k}", 0) for k in
            ("FamilyType", "SerifStyle", "Weight", "Proportion", "Contrast",
             "StrokeVariation", "ArmStyle", "Letterform", "Midline", "XHeight")]


def observe(face: dict, *, panose: list[int] | None = None) -> dict:
    """Style observations for ONE face. Silent when the font says nothing."""
    if panose is None:
        panose = _panose(face["source_path"], face.get("collection_index", 0))

    tags: dict[str, dict] = {}
    declared = bool(panose and any(panose))

    def add(tag, conf, source, evidence):
        prev = tags.get(tag)
        if not prev or conf > prev["confidence"]:
            tags[tag] = {"tag": tag, "confidence": min(conf, CONF_CAP),
                         "source": source, "evidence": evidence}

    # --- 1. PANOSE — the field the font uses to describe itself -----------------
    if declared:
        fam, serif_style, _w, prop, contrast, _sv, _arm, letterform = panose[:8]
        if fam == 2:                                   # text family
            if serif_style in PAN_SANS_RANGE:
                add(SANS, CONF_PANOSE, "OS/2.panose",
                    f"familyType=2 serifStyle={serif_style} (sans range)")
            elif serif_style >= 2:
                add(SERIF, CONF_PANOSE, "OS/2.panose",
                    f"familyType=2 serifStyle={serif_style}")
        elif fam == 3:
            add(HANDWRITTEN, CONF_PANOSE, "OS/2.panose", "familyType=3 (script)")
        elif fam == 4:
            add(DISPLAY, CONF_PANOSE, "OS/2.panose", "familyType=4 (decorative)")
        if prop == 9:
            add(MONOSPACE, CONF_PANOSE, "OS/2.panose", "proportion=9 (monospaced)")
        if contrast >= 7:
            add(HIGH_CONTRAST, CONF_PANOSE, "OS/2.panose", f"contrast={contrast}")
        if letterform in (2, 3, 4):
            add(HUMANIST, CONF_PANOSE - 0.2, "OS/2.panose",
                f"letterform={letterform}")
        elif letterform in (8, 9):
            add(GEOMETRIC, CONF_PANOSE - 0.2, "OS/2.panose",
                f"letterform={letterform}")

    # --- 2. width / weight / glyph metrics --------------------------------------
    width = face.get("width_class")
    if width in ("CONDENSED", "SEMI_CONDENSED", "EXTRA_CONDENSED",
                 "ULTRA_CONDENSED"):
        add(CONDENSED, CONF_METRICS, "OS/2.usWidthClass", width)
    elif width in ("EXPANDED", "SEMI_EXPANDED", "EXTRA_EXPANDED",
                   "ULTRA_EXPANDED"):
        add(EXTENDED, CONF_METRICS, "OS/2.usWidthClass", width)

    glyphs = face.get("glyph_count") or 0
    scripts = face.get("scripts") or []
    if glyphs and glyphs < 150:
        add(DISPLAY, CONF_METRICS, "maxp.numGlyphs",
            f"{glyphs} glyphs — too few for body text")
    elif glyphs >= 300 and len(scripts) >= 2 and not face.get("italic"):
        add(BODY_CANDIDATE, CONF_METRICS, "maxp.numGlyphs + cmap",
            f"{glyphs} glyphs across {len(scripts)} scripts")

    # --- 3. the font's own subfamily string (metadata, NOT a filename) -----------
    sub = " ".join(filter(None, [
        (face.get("names") or {}).get("subfamily_typographic"),
        (face.get("names") or {}).get("subfamily_legacy")])).lower()
    for word, tag in (("condensed", CONDENSED), ("extended", EXTENDED),
                      ("expanded", EXTENDED), ("display", DISPLAY),
                      ("mono", MONOSPACE)):
        if word in sub:
            add(tag, CONF_SUBFAMILY, "name.subfamily", sub[:40])

    out = sorted(tags.values(), key=lambda t: (-t["confidence"], t["tag"]))
    return {
        "schema_version": SCHEMA_VERSION,
        "face_id": face["face_id"],
        "tags": out,
        "tag_names": [t["tag"] for t in out],
        "panose_declared": declared,
        "panose": panose,
        "filename_used": False,
        "affects_license_or_permission": False,
        "note": ("HEURISTIC review aid only. Style never touches licence, ownership, "
                 "permission or quarantine. Most of this corpus leaves PANOSE unset, "
                 "so many faces carry NO tag — silence is the correct answer when the "
                 "font declares nothing."),
        "human_confirmation": None,          # human only
        "parser": PARSER,
    }
