"""The products, and their sizes (§BH55 Phase 3, 2026-09-20).

OWNER STANDING ORDER §BH55, PHASE 3: "Every capability the engine has is reachable and labelled in words a designer
understands." A product's width, depth and height decide how a carton for it is sized: all three on record, and the
size step reads them (no estimate, no spend — dieline_agent._determine_scenario); any one missing, and the size is
ESTIMATED from the concept by a paid model call (_extract_from_context → _call_claude) for the designer to confirm.
They were set only in the admin. The products are listed here with what a design reads from them, and a designer sets
a product's size and its type. A product's carton STRUCTURE is shown and not set: it is an approved association on the
brand's structure record that outranks the size step's recommendation (template_selection._gather_evidence), recorded
in the admin; each design still chooses or confirms its structure at its size step.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

SIZE_FIELDS = (("width_mm", "Width"), ("depth_mm", "Depth"), ("height_mm", "Height"))
#: the fields' own limits (max_digits=6, decimal_places=2): under 10,000 mm, at most two decimals
SIZE_LIMIT = Decimal("10000")
NO_SIZE_WORDS = ("No size on record — a carton for it is sized by a paid estimate from its concept, which you then "
                 "confirm")


def size_words(product) -> str:
    whd = [getattr(product, f) for f, _ in SIZE_FIELDS]
    if all(v is not None and v > 0 for v in whd):
        return "%s × %s × %s mm" % tuple(f"{v.normalize():f}" for v in whd)
    return ""


def test_records(products) -> set:
    """The products made only for the system's own tests, kept apart from the brand's (C's Library, his pick of
    2026-09-25): a product whose every design is folded away — his fold, "They are tests, not my work" (a691f56), or a
    planning probe. A product with no design is his."""
    from apps.dashboard import board
    from apps.pipeline.models import DesignTask
    designs: dict = {}
    for t in DesignTask.objects.filter(product__in=products).select_related("project"):
        designs.setdefault(t.product_id, []).append(t)
    return {pk for pk, tasks in designs.items() if all(board.fold_of(t) for t in tasks)}


def listing(brand) -> list[dict]:
    from apps.core.models import Product
    if brand is None:
        return []
    rows = []
    products = list(Product.objects.filter(brand=brand).select_related("packaging_structure").order_by("product_id"))
    tests = test_records(products)
    for p in products:
        s = p.packaging_structure
        rows.append({
            "p": p, "size": size_words(p), "category": p.get_category_display() if p.category else "",
            "test": p.pk in tests,
            "structure": (f"{s.name} ({s.structure_type.replace('_', ' ')})" if s else ""),
            "printed": [(label, value) for label, value in (
                ("Net content", p.net_weight), ("Item number", p.item_no), ("Barcode", p.barcode_ean),
                ("Description", p.description), ("Ingredients", p.ingredients), ("How to use", p.how_to_use),
                ("Warnings", p.warnings_text)) if value],
        })
    return rows


def parse_size(data) -> tuple[dict, list[str]]:
    """A size as typed: all three blank clears it (the carton's size is then estimated); otherwise each a number of
    millimetres above 0 and under 10,000, with at most two decimals — the record's own limits. The words of every
    fault, never a guess."""
    raw = {f: (data.get(f) or "").strip() for f, _ in SIZE_FIELDS}
    if not any(raw.values()):
        return {f: None for f, _ in SIZE_FIELDS}, []
    values, errors = {}, []
    for field, label in SIZE_FIELDS:
        try:
            value = Decimal(raw[field])
        except InvalidOperation:
            errors.append(f"{label}: “{raw[field] or 'blank'}” is not a number of millimetres")
            continue
        if not value.is_finite() or value <= 0:
            errors.append(f"{label} must be more than 0 mm")
        elif value >= SIZE_LIMIT:
            errors.append(f"{label} must be under 10,000 mm")
        elif value.as_tuple().exponent < -2:
            errors.append(f"{label} takes at most two decimals")
        else:
            values[field] = value
    return values, errors
