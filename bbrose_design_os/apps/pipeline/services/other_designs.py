"""[His test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md), item 4: "A new design never takes names, words
or ideas from another design's brief. Earlier designs may inform style only, never names."] What a new design's planner
may be told of other designs: their style — never their names, their words or their stories.

MEASURED on 121's planner inputs: no other design's brief reached it (the house library draws only on BBROSE's past
production files and the materials library; the directions' "Rebel" stood in 121's own brief — its Product line, its
Arabic name and its front copy). Three inputs did carry other designs' names and words to it: the "Similar BBROSE
products" (each product's name, its id and its story — "dusk to dawn, a rose that opens in the dark"), the house library's
lines (each past design's file name, and its description's product names — 'Juicy Lips', 'OMG Lip Honey', BBROSE
Colorete, BBROSE SPF 90 Protector Solar, BBRose Solid Blush) and the reference anatomy (each past design's copy — 'Lip Oil',
'Subtle Gloss'). Each now passes through ``style_only``.
"""
from __future__ import annotations

import re

#: what a similar product may lend a new design: its kind and its finish — never its name, its id, its year or its story
SIMILAR_STYLE_FIELDS = ("category", "product_type", "finish_notes")

#: a name or a line of copy quoted in a description
_QUOTED = re.compile(r"'[^'\n]{1,60}'|\"[^\"\n]{1,60}\"|‘[^’\n]{1,60}’|“[^”\n]{1,60}”")
#: a BBROSE product named after the house's name: "BBROSE Colorete", "BBRose Solid Blush", "BBROSE SPF 90 Protector Solar"
_HOUSE_NAMED = re.compile(r"\b(?i:bb ?rose)\b(?:[ \t]+[A-Z0-9][\w'’&.-]*)+")
#: a product's code: "(FS5817)", "BL-2050", "YB-1039"
_CODE = re.compile(r"\(\s*[A-Z]{1,4}-?\d{3,}[A-Z0-9_-]*\s*\)|\b[A-Z]{1,4}-?\d{3,}[A-Z0-9_-]*\b")

#: told to the planner beside them
#: [his goal for the pitch, 2026-10-15, A (3): "never repeat a main motif used in my recent designs"] their craft, never
#: their motifs
RULE = ("Earlier designs and other BBROSE products inform STYLE ONLY — finish, craft level, type discipline and "
        "composition. Never take a name, a line of copy, a story, an idea or a main motif from them: this design's "
        "names come from its own brief alone, and its motif is its own.")


def names_of_other_designs(task=None) -> list:
    """Every other product's name on record — the task's own product's left out."""
    from apps.core.models import Product
    own = task.product_id if task is not None and hasattr(task, "product_id") else None
    names = Product.objects.exclude(pk=own).values_list("name", flat=True) if own else \
        Product.objects.values_list("name", flat=True)
    return sorted({str(n).strip() for n in names if n and len(str(n).strip()) > 2}, key=len, reverse=True)


def style_only(text, names=()) -> str:
    """``text`` with other designs' names and words taken out — quoted names and copy, a product named after the house's
    name, products' codes and every name in ``names`` — its style words kept."""
    out = _QUOTED.sub(" ", str(text) if text else "")
    out = _HOUSE_NAMED.sub(" ", out)
    out = _CODE.sub(" ", out)
    for name in names or ():
        out = re.sub(r"(?i)\b%s\b" % re.escape(name), " ", out)
    out = re.sub(r"\(\s*\)", " ", out)
    out = re.sub(r"\b(?:for|of|by|from)\s*(?=[,.;:)])", "", out)      # "a dieline for, featuring" — its name gone
    out = re.sub(r"\s+([,.;:)])", r"\1", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip()


def style_only_in(node, names=()):
    """``style_only`` on every word of a record — each string where it stands, its keys and its shape kept (a past
    design's anatomy: its layout, type and motif words lent, its copy and names taken out)."""
    if isinstance(node, str):
        return style_only(node, names)
    if isinstance(node, dict):
        return {key: style_only_in(value, names) for key, value in node.items()}
    if isinstance(node, list):
        return [style_only_in(value, names) for value in node]
    return node


def similar_style(similar, names=()) -> list:
    """The similar products as style: their kind and finish, never their names, ids, years or stories."""
    out = []
    for product in similar or ():
        style = {k: (style_only(product.get(k), names) if k == "finish_notes" else product.get(k))
                 for k in SIMILAR_STYLE_FIELDS if product.get(k)}
        if style and style not in out:
            out.append(style)
    return out
