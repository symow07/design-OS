"""§BH50(f)(1) — the composer states what each text run is.

    "THE §W2 FLOOR IS PRODUCT COPY ONLY. 5.0 pt governs text printed on the
    product. The sheet's schematic annotations — labels, callouts, dimension
    text around the drawing — are not product copy and are out of §W2's
    scope; scope the rule by surface, not by page, and say in the rule what
    it covers."

``declare`` walks a composed document and sets ``TextRun.print_scope`` from
the composer's OWN structure: the groups it built for the product's printed
surfaces, the groups it built as schematic depictions, and the names it gave
its own furniture. It is called by the composer that built the document,
with that composer's names — it is the composer's statement, not a reader's
guess. A run that matches none of them stays UNDECLARED and is returned by
name, so a composer that forgot a run learns it from its own census and the
§W2 instruments judge that run by inference and disclose it (fail closed).
The annotation names are matched first, wherever the run sits: a panel's
caption drawn inside a schematic group is still the sheet's furniture.
"""
from __future__ import annotations

from apps.ire.graph import (DEPICTION_OF_PRODUCT_COPY, PRINTED_ON_PRODUCT,
                            SHEET_ANNOTATION, PrintScope)


def declare(doc, *, printed_groups: dict, depiction_groups: dict,
            annotation_names=(), annotation_prefixes=()) -> dict:
    """``printed_groups``: group name -> (surface, zone_id or None) for every
    group whose text prints on the product at the size it is set.
    ``depiction_groups``: group name -> (surface, zone_id or None) for every
    group that draws product copy as a schematic. ``annotation_names`` /
    ``annotation_prefixes``: the composer's own furniture. Returns
    ``{"declared": n, "undeclared": [names]}``."""
    parents = {id(node): parent for node, parent in doc.walk()}
    names = set(annotation_names or ())
    prefixes = tuple(annotation_prefixes or ())
    declared, undeclared = 0, []
    for node, _ in doc.walk():
        if getattr(node, "type", "") != "text":
            continue
        name = str(getattr(node, "name", "") or "")
        scope = None
        if name in names or (prefixes and name.startswith(prefixes)):
            scope = PrintScope(kind=SHEET_ANNOTATION)
        else:
            cur = parents.get(id(node))
            while cur is not None and scope is None:
                gname = str(getattr(cur, "name", "") or "")
                if gname in printed_groups:
                    surface, zone_id = printed_groups[gname]
                    scope = PrintScope(kind=PRINTED_ON_PRODUCT, surface=surface,
                                       zone_id=zone_id)
                elif gname in depiction_groups:
                    surface, zone_id = depiction_groups[gname]
                    scope = PrintScope(kind=DEPICTION_OF_PRODUCT_COPY,
                                       surface=surface, zone_id=zone_id)
                cur = parents.get(id(cur))
        if scope is None:
            undeclared.append(name)
            continue
        node.print_scope = scope
        declared += 1
    return {"declared": declared, "undeclared": undeclared}


def undeclared_runs(doc) -> list[str]:
    """The names of every text run carrying no declaration — the census a
    test reads to prove a composer declared every run it emitted."""
    return [str(getattr(n, "name", "") or "") for n, _ in doc.walk()
            if getattr(n, "type", "") == "text"
            and getattr(n, "print_scope", None) is None]


__all__ = ["declare", "undeclared_runs"]
