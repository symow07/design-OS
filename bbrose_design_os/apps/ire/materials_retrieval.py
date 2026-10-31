"""§BH39(d): the retrieval CONTRACT for REFERENCE (and PRODUCTION) materials —
``materials_retrieval/1.0`` — an interface the BRAIN front (§BH34 front 3)
implements. A row carries captions, palette, layout metadata and the tier; NO
bytes of the asset and NO locator a composer could place. This module holds
the contract and its validation only; there is no server here.
"""
from __future__ import annotations

import re as _re

SCHEMA = "materials_retrieval/1.0"
_HEX = _re.compile(r"#[0-9A-Fa-f]{6}")

#: what a query may ask for
WANTED = ("palette", "composition", "motif", "texture", "finish")
#: a row's fields — exactly these; a locator is absent BY SCHEMA
ROW_FIELDS = ("sha256", "tier", "category", "pack", "caption", "palette", "layout_metadata", "evidence",
              "condition", "prohibited")
#: fields a row may NEVER carry (the design_context leak discipline, §2A-6E)
FORBIDDEN_FIELDS = ("path", "relative_path", "src", "locator", "url", "bytes", "image", "data")

PROHIBITED_FROM_COPYING = (
    "copy the same layout", "reproduce the same pattern", "trace the artwork",
    "recreate the same logo placement", "reproduce unique illustrations",
    "imitate a competitor package closely",
)


class RetrievalContractError(ValueError):
    pass


def validate_query(query: dict) -> dict:
    q = dict(query or {})
    wanted = tuple(q.get("wanted") or ())
    bad = [w for w in wanted if w not in WANTED]
    if bad:
        raise RetrievalContractError(f"wanted outside the contract: {bad}")
    k = int(q.get("k") or 0)
    if k <= 0:
        raise RetrievalContractError("k must be a positive count")
    return {"task_tokens": list(q.get("task_tokens") or []), "product_category": q.get("product_category") or "",
            "wanted": list(wanted), "k": k}


def validate_row(row: dict) -> dict:
    missing = [f for f in ROW_FIELDS if f not in row]
    if missing:
        raise RetrievalContractError(f"row lacks {missing}")
    leak = [f for f in FORBIDDEN_FIELDS if f in row]
    if leak:
        raise RetrievalContractError(f"row carries a locator or bytes: {leak}")
    if row["tier"] not in ("REFERENCE", "PRODUCTION"):
        raise RetrievalContractError(f"tier {row['tier']!r} outside the two tiers")
    if tuple(row.get("prohibited") or ()) != PROHIBITED_FROM_COPYING:
        raise RetrievalContractError("a row must carry the copy prohibitions verbatim")
    for h in row.get("palette") or ():
        if not (isinstance(h, str) and _HEX.fullmatch(h)):
            raise RetrievalContractError(f"palette entry {h!r} is not a #RRGGBB hex")
    return row


class MaterialsRetrieval:
    """The interface. ``query`` is implemented by the BRAIN; here it refuses."""

    schema_version = SCHEMA

    def query(self, query: dict) -> list[dict]:
        validate_query(query)
        raise NotImplementedError("materials_retrieval/1.0 is a contract; the BRAIN front implements it")


__all__ = ["SCHEMA", "WANTED", "ROW_FIELDS", "FORBIDDEN_FIELDS", "PROHIBITED_FROM_COPYING", "RetrievalContractError",
           "validate_query", "validate_row", "MaterialsRetrieval"]
