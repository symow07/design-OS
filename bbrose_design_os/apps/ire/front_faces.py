"""[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 6: "FRONT TEXT: "Rose Blossom" in the granted face closest
to the concept's soft rounded sans (Quicksand or Montserrat), ONE colour, never two pinks or the heavy house bold; "Hand
Cream" in the same family, lighter; Arabic in a matching sans (Tajawal or Cairo), not Naskh."]

A carton's front drawn from its concept's map set its name in the house's bold (Noto Sans Bold, the drawing's own
"bold") and its Arabic in Noto Naskh, whatever the concept letters them in. Now, where the concept letters its name in a
sans, the front is set in the granted sans he names:

- THE NAME'S FACE (``choose``): the rounded one, Quicksand, where the design is soft — its brief's words or its chosen
  direction's type words say so (ROUNDED_WORDS: 123's "soft, romantic, girly") — else the crisp one, Montserrat; at
  NAME_WEIGHT, never the house's heavy bold. The executor's reading of "closest", his to veto: the concept picture's
  letters are not measured against the two faces — the map's reading of them, "sans", does not tell a rounded sans
  from a crisp one, and 123's picture is a photograph whose face box the letters cannot be cropped from reliably.
- ITS COPY in the same family, lighter (COPY_WEIGHT); THE ARABIC in Tajawal (ARABIC_STEM), a sans of the same build.
- Each a static instance of the granted file (``font_roles.instance_at``), carried to the files as the front's own three
  roles (ROLES) — the sticker keeps its ruled faces (§BH32(h)).
"""
from __future__ import annotations

import re

#: the two granted sans he names, by their catalogue stems: the rounded and the crisp
ROUNDED = ("Quicksand[wght]", "Quicksand")
CRISP = ("Montserrat[wght]", "Montserrat")
#: the words that make a design soft — its sans the rounded one
ROUNDED_WORDS = ("rounded", "round", "soft", "softly", "bubbly", "friendly", "girly", "playful", "cute", "gentle")
NAME_WEIGHT = 600.0
COPY_WEIGHT = 400.0
#: the Arabic's matching sans (granted, static)
ARABIC_STEM = "Tajawal-Medium"
NAME_ROLE, COPY_ROLE, ARABIC_ROLE = "front-name", "front-copy", "front-arabic"
ROLES = (NAME_ROLE, COPY_ROLE, ARABIC_ROLE)
#: kept on the front and the drawing's record
KEY = "front_faces"
#: the letterings a sans face may stand for — a script, a serif or a display lettering keeps its own way
SANS_LETTERING = ("sans", "sans-serif", "sans serif")


def soft_words(text: str) -> list:
    """The words in ``text`` that make a design soft (ROUNDED_WORDS), each once, in its order."""
    said = re.findall(r"[a-z]+", str(text or "").lower())
    return list(dict.fromkeys(w for w in said if w in ROUNDED_WORDS))


def choose(words: str) -> dict | None:
    """The front's faces for a name lettered in a sans: the rounded sans where ``words`` (its brief's and its chosen
    direction's type words) make the design soft, else the crisp one, its copy lighter and the Arabic's sans — ``{"family",
    "stem", "soft_words", "roles": {role: {"name", "path"}}, "why"}``; None where a face is not on file."""
    from apps.ire.font_roles import catalogue, instance_at
    soft = soft_words(words)
    stem, family = ROUNDED if soft else CRISP
    name, copy = instance_at(stem, NAME_WEIGHT), instance_at(stem, COPY_WEIGHT)
    arabic = catalogue().get(ARABIC_STEM)
    if name is None or copy is None or arabic is None:
        return None
    return {"family": family, "stem": stem, "name_weight": NAME_WEIGHT, "copy_weight": COPY_WEIGHT,
            "arabic": ARABIC_STEM, "soft_words": soft,
            "roles": {NAME_ROLE: {"name": name["postscript"], "path": name["path"]},
                      COPY_ROLE: {"name": copy["postscript"], "path": copy["path"]},
                      ARABIC_ROLE: {"name": ARABIC_STEM, "path": arabic["path"]}},
            "why": ("a soft design (%s): the rounded sans" % ", ".join(soft)) if soft else
                   "no word makes the design soft: the crisp sans"}


def for_front(types: list, product_name: str, words: str) -> dict | None:
    """The faces for a front's typed lines (its map's ``types``, their words given): where every line naming the
    product is lettered in a sans and set as type, ``choose`` by ``words``; None for a name lettered otherwise, set in a
    display face or traced, or none."""
    from apps.ire.compose_container import _name_parts, _name_start
    typed = [t for t in types if t.get("words")]
    parts = _name_parts(typed, product_name) or _name_start(typed, product_name)
    named = [t for t in typed if t["words"] == product_name or t["part"] in parts]
    if not named:
        return None
    for t in named:
        if t.get("lettering_set") or (t.get("outlines") and t.get("match") is not None and float(t["match"]) >= 1.0):
            return None
        if str(t.get("lettering") or "").lower() not in SANS_LETTERING:
            return None
    return choose(words)
