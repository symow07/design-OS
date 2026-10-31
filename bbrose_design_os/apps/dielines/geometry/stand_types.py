"""What the engine knows about every kind of stand (owner's part 2, 2026-10-31): one rules file per type in
docs/research/stands/rules, written from the research and read here. A type is a record: what it is for, which products and
counts it suits, its construction rules, and whether a working die template stands behind it."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parents[4] / "docs/research/stands/rules"


@lru_cache(maxsize=1)
def common():
    return json.loads((RULES_DIR / "_common.json").read_text(encoding="utf8"))


@lru_cache(maxsize=None)
def record(type_id):
    path = RULES_DIR / (type_id + ".json")
    if not path.exists():
        raise ValueError("The engine has no record of a stand type called %s" % type_id)
    return json.loads(path.read_text(encoding="utf8"))


def all_types():
    """Every type's record, the working templates first, in the owner's order."""
    rows = [json.loads(path.read_text(encoding="utf8")) for path in sorted(RULES_DIR.glob("*.json")) if not path.name.startswith("_")]
    return sorted(rows, key=lambda row: (row.get("build_order") or 99, row["id"]))


def label(type_id):
    return record(type_id)["label"]


def version(type_id):
    return record(type_id)["version"]


def provisional_notes(type_id):
    return list(record(type_id).get("provisional", []))


def buildable():
    return [row for row in all_types() if row.get("status") == "working"]


def suggest(*, count, rows=None, product_height_mm=None, testers=False, ships_filled=False):
    """The engine's suggestion among the working templates, by each type's own ``suits``, with its reason in words. Rule-based
    and deterministic: a tester goes to the tester unit; a stand that ships filled to the lid-converts tray; many rows of a tall
    product to the stepped display; few rows of a tall product to the slanted one; otherwise the tray with a header."""
    working = {row["id"]: row for row in buildable()}
    tall = bool(product_height_mm and product_height_mm >= 60)
    if testers and rows and rows > 1 and "flat_tray_testers" in working:
        pick, why = "flat_tray_testers", "sealed rows with a tester at the front of each column: the house's flat tray"
    elif testers and "tester_unit" in working:
        pick, why = "tester_unit", "testers want their own open deck, wipeable, with room to put them back"
    elif ships_filled and "lid_header_tray" in working:
        pick, why = "lid_header_tray", "it ships filled and closed, and its lid becomes the header"
    elif rows and rows >= 3 and tall and count >= 12 and "stepped_tiered" in working and (count > 12 or rows > 3):
        pick, why = "stepped_tiered", "more rows of a tall product than a tray can show"
    elif rows and rows <= 2 and tall and "slanted_front" in working:
        pick, why = "slanted_front", "one or two rows of a tall product read best leaned back toward the eye"
    else:
        pick, why = "flat_tray_testers", "the house's most-used counter form: %d products at one height, a tester showing each shade" % count
    return {"type": pick, "why": why}
