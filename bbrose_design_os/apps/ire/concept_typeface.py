"""§BH67(c)5 — the face a concept names, read against the owner's granted set.

OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "TYPEFACE: where the concept names a face that sits inside
my granted set — the 35 plus the Noto trio — the concept's face leads. Outside that set, the role layer decides. No
face outside the set is ever drawn."

``read`` finds every face the concept's ``typography_signature`` NAMES — a family of the layer's own catalogue
(``font_roles.catalogue``: the 35 activated faces re-hashed against PROVENANCE.json, and the Noto trio), with the
weight and italic words that travel with it — and says, for the product name, which catalogue file leads. It reads
names, never styles: "a high-contrast old-style serif" names no face, and the role layer decides as it always has.

What cannot lead is REFUSED BY NAME and the role layer decides:
- a face outside the set (``OUTSIDE_THE_SET``) — recorded when it is one the reader knows by name; a face it does not
  know is simply not a granted face, and is never drawn either way;
- a weight the set does not hold for that family (``WEIGHT_NOT_GRANTED``) — "Lato Light" when only Lato Black is
  granted: the named file is outside the set;
- a variable face at a role with no pinned instance (``VARIABLE_UNPINNED``) — §BH33(2): "A role with no pinned weight
  never receives a variable face". The container's name is the DISPLAY role, which pins none, so Playfair Display and
  Quicksand (variable only) cannot print a container's name until a display instance is pinned; that pin is the
  owner's, and the reader names the refusal rather than choosing one; [§BH68(c), 2026-09-24: HE PINNED IT — "THE
  DISPLAY ROLE TAKES THE HEADING PIN — weight 700 for a variable face — unless the face declares its own display
  instance." The name's lead records the weight the layer DRAWS (``font_roles.pinned_weight``'s rule), and the weight
  the concept named beside it where the two differ. The refusal stands for a role that pins none.]
- a face that cannot set the element's script (``WRONG_SCRIPT``) — a Latin name in Noto Naskh Arabic.

Pure: reads words and the catalogue; draws nothing. The composer hands the lead to the layer
(``font_roles.CONCEPT_NAME``), which verifies it through the seam like every other face.
"""
from __future__ import annotations

import re

SCHEMA = "container_concept_typeface/1.0"
GOVERNED_BY = "§BH67(c)5"
LEADS, REFUSED, AGREES = "LEADS", "REFUSED", "AGREES"
OUTSIDE_THE_SET = "CONCEPT_TYPEFACE_OUTSIDE_THE_GRANTED_SET"
WEIGHT_NOT_GRANTED = "CONCEPT_TYPEFACE_WEIGHT_NOT_GRANTED"
VARIABLE_UNPINNED = "CONCEPT_TYPEFACE_VARIABLE_UNPINNED"
WRONG_SCRIPT = "CONCEPT_TYPEFACE_WRONG_SCRIPT"

#: weight words as the concept writes them -> the OpenType weight class
WEIGHT_WORDS = (
    (r"extra[\s-]?light|ultra[\s-]?light", 200), (r"semi[\s-]?bold|demi[\s-]?bold", 600),
    (r"extra[\s-]?bold|ultra[\s-]?bold|heavy", 800), (r"thin|hairline", 100), (r"light", 300),
    (r"regular|book|normal", 400), (r"medium", 500), (r"bold", 700), (r"black", 900),
)
#: a static stem's style suffix -> (weight class, italic)
_STEM_STYLE = {"thin": 100, "extralight": 200, "light": 300, "regular": 400, "": 400, "medium": 500,
               "semibold": 600, "bold": 700, "extrabold": 800, "black": 900}

#: faces a concept may name that the set does NOT hold — recorded by name when named, so the refusal reads as one;
#: not a list of what may be drawn (the catalogue is that), and a face missing here is refused all the same
KNOWN_OUTSIDE = ("didot", "bodoni", "garamond", "cormorant", "baskerville", "caslon", "canela", "optima", "trajan",
                 "cinzel", "copperplate", "futura", "helvetica", "avenir", "gotham", "gill sans", "proxima nova",
                 "inter", "roboto", "lora", "libre baskerville", "dm serif", "bembo", "times new roman",
                 "freight", "ogg", "tiempos", "sackers", "brandon grotesque", "century gothic", "neue haas",
                 "amiri", "dubai", "tajawal", "kufi")

_CLAUSE_SPLIT = re.compile(r";|\s—\s|\.\s")
#: the element a clause is about: the fixed lockup, the supporting copy, or — by default — the product name
_MARK_ELEMENT = re.compile(r"bbrose|lockup|\blogo\b|brand mark")
_OTHER_ELEMENT = re.compile(r"claims?|descriptor|supporting|category|side band|secondary|net content|\bcopy\b")
_NAME_WORDS = re.compile(r"\bname|\bproduct\b|'[^']+'|\(en\)|display type|headline")


def _families(catalogue: dict) -> dict[str, list[tuple[str, dict]]]:
    """``{family words (lower): [(stem, entry), ...]}`` from the catalogue. [D-D7-1, Day 7 §4] the GRANTED pool of the
    materials library extends the families the house does not hold; where the house holds a family, its own files lead
    (a pool copy of Playfair Display never displaces the brand's variable face and its declared display instance)."""
    from apps.ire import font_pool
    out: dict[str, list] = {}
    for stem, entry in catalogue.items():
        out.setdefault(str(entry.get("family") or stem).lower(), []).append((stem, entry))
    for family, members in out.items():
        house = [m for m in members if m[1].get("origin") != font_pool.ORIGIN]
        if house:
            out[family] = house
    return out


def _family_re(family: str) -> re.Pattern:
    words = family.split()
    return re.compile(r"(?<![a-z])" + r"[\s-]*".join(map(re.escape, words)) + r"(?![a-z])")


def _style_of(stem: str) -> tuple[int, bool]:
    tail = stem.split("-", 1)[1] if "-" in stem else ""
    tail = tail.split("[", 1)[0].lower()
    italic = tail.endswith("italic")
    base = tail[:-len("italic")] if italic else tail
    return _STEM_STYLE.get(base, 400), italic


def _weight_after(text: str, end: int) -> tuple[int | None, bool, str]:
    """The weight and italic words that follow a family name, within the same few words."""
    window = text[end:end + 28]
    stop = re.search(r"[,;(]|\s(?:for|on|in|with|set|and|over|above|below|at)\s", window)
    window = window[:stop.start()] if stop else window
    weight, said = None, []
    for rx, w in WEIGHT_WORDS:
        m = re.search(r"(?<![a-z])(%s)(?![a-z])" % rx, window)
        if m:
            weight = w
            said.append(m.group(1))
            break
    italic = bool(re.search(r"(?<![a-z])italic(?![a-z])", window))
    if italic:
        said.append("italic")
    return weight, italic, " ".join(said)


def read(structured: dict | None, catalogue: dict, *, name_role_pin: float | None = None) -> dict:
    """``container_concept_typeface/1.0``: every face the concept names, and the NAME's lead or its refusal.

    ``name_role_pin`` is the instance weight the layer role the name prints in pins (§BH33(2)) — None where it pins
    none; the container's name is DISPLAY, pinned at 700 since §BH68(c)."""
    out = {"schema_version": SCHEMA, "governed_by": GOVERNED_BY, "named": [], "name": None,
           "state": "NO_STRUCTURED_RECORD"}
    if not structured:
        return out
    text = " ".join(str(structured.get("typography_signature") or "").lower().split())
    out["state"] = "READ"
    families = _families(catalogue)
    found = []
    for family in sorted(families, key=len, reverse=True):
        for m in _family_re(family).finditer(text):
            if any(a <= m.start() < b for a, b, *_ in found):
                continue
            found.append((m.start(), m.end(), "GRANTED", family))
    for outside in KNOWN_OUTSIDE:
        for m in _family_re(outside).finditer(text):
            if not any(a <= m.start() < b for a, b, *_ in found):
                found.append((m.start(), m.end(), "OUTSIDE", outside))
    bounds, pos = [], 0
    for m in _CLAUSE_SPLIT.finditer(text):
        bounds.append((pos, m.start()))
        pos = m.end()
    bounds.append((pos, len(text)))
    for start, end, kind, family in sorted(found):
        a, b = next(((a, b) for a, b in bounds if a <= start < b), (0, len(text)))
        clause = text[a:b]
        members = families.get(family, [])
        if _MARK_ELEMENT.search(clause) and not _NAME_WORDS.search(clause):
            element = "mark"            # the lockup is fixed artwork: a face named for it is recorded, never drawn
        elif _OTHER_ELEMENT.search(clause) and not _NAME_WORDS.search(clause):
            element = "other"
        elif kind == "GRANTED" and members and not any(e.get("latin") for _s, e in members):
            element = "name_ar"
        else:
            element = "name"
        weight, italic, said = _weight_after(text, end)
        row = {"words": (text[start:end] + (" " + said if said else "")).strip(), "family": family,
               "element": element, "weight": weight, "italic": italic, "clause": clause.strip()[:160]}
        if kind == "OUTSIDE":
            row.update(verdict=REFUSED, code=OUTSIDE_THE_SET,
                       why="named by the concept and not in the granted set — never drawn; the role layer decides")
        elif element == "name_ar":
            row.update(verdict=AGREES, why="an Arabic face of the set: the Arabic chain is Noto Naskh Arabic alone "
                                           "(§BH33(1)), and it is what the Arabic line prints in")
        else:
            row.update(_lead(members, weight, italic, pin=name_role_pin))
        out["named"].append(row)
    out["name"] = next((r for r in out["named"] if r["element"] == "name"), None)
    return out


def _lead(members: list, weight: int | None, italic: bool, *, pin: float | None) -> dict:
    """Which of a granted family's files leads for a Latin name, or the refusal by name."""
    latin = [(s, e) for s, e in members if e.get("latin")]
    if not latin:
        return {"verdict": REFUSED, "code": WRONG_SCRIPT,
                "why": "the family carries no Latin letters; a Latin name cannot be set in it"}
    static = [(s, e) for s, e in latin if not e.get("variable")]
    want = weight if weight is not None else 400
    exact = [s for s, _e in static if _style_of(s) == (want, italic)]
    if exact:
        return {"verdict": LEADS, "stem": exact[0], "weight": want, "italic": italic,
                "why": "the concept's own face, a granted file at the weight it names"}
    if weight is None and not italic and len(static) == 1 and not [s for s, e in latin if e.get("variable")]:
        stem = static[0][0]
        return {"verdict": LEADS, "stem": stem, "weight": _style_of(stem)[0], "italic": _style_of(stem)[1],
                "why": "the concept's own face; the family's one granted file"}
    variable = [(s, e) for s, e in latin if e.get("variable") and ("italic" in s.lower()) == italic]
    if variable:
        stem, entry = variable[0]
        if pin is None:
            return {"verdict": REFUSED, "code": VARIABLE_UNPINNED, "stem": stem,
                    "why": "a granted variable face, and the name's role pins no instance weight — §BH33(2): \"A role "
                           "with no pinned weight never receives a variable face\"; the role layer decides"}
        # §BH68(c): the layer draws the face's own declared display instance, else the role's pin — never the named one
        declared = entry.get("display_instance")
        drawn = declared["wght"] if declared is not None else pin
        lo, _d, hi = (entry.get("axes") or {}).get("wght", (drawn, drawn, drawn))
        if not lo <= drawn <= hi:
            return {"verdict": REFUSED, "code": WEIGHT_NOT_GRANTED, "stem": stem,
                    "why": "the pinned weight %g lies outside the granted face's range %g-%g" % (drawn, lo, hi)}
        row = {"verdict": LEADS, "stem": stem, "weight": drawn, "italic": italic,
               "why": ("the concept's own face, the granted variable file at %s"
                       % ("its own declared display instance (%s)" % declared["name"] if declared is not None
                          else "the display role's pinned instance, %g (§BH68(c))" % drawn))}
        if weight is not None and weight != drawn:
            row["named_weight"] = weight           # what the concept's words said; the layer draws the pin (§BH68(c))
        return row
    return {"verdict": REFUSED, "code": WEIGHT_NOT_GRANTED,
            "why": "the family is granted, but not at the weight or style named (%s)"
                   % ", ".join(sorted(s for s, _e in latin))}


__all__ = ["SCHEMA", "GOVERNED_BY", "LEADS", "REFUSED", "AGREES", "OUTSIDE_THE_SET", "WEIGHT_NOT_GRANTED",
           "VARIABLE_UNPINNED", "WRONG_SCRIPT", "WEIGHT_WORDS", "KNOWN_OUTSIDE", "read"]
