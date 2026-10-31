"""Fallback-class gate registration helper (§R4 / §S1).

Answers one question: WHICH fallback-class occurrences in
``apps/pipeline/services`` are not yet in
``docs/roadmap/palt_m6/enforcement_closure/gate_baseline.json``, and what
does their source actually say?

It exists because the registration this repo owes is per-occurrence and
judged, not bulk. RBV-4 added 24 occurrences to a gate that was already
red and nobody noticed, precisely because there was no cheap way to see
the delta a commit introduces. This makes the delta cheap to see.

  python tools/gate_registration.py            # summary
  python tools/gate_registration.py --json     # machine-readable inventory

It NEVER writes the baseline. Registration is a judgment an author makes
and justifies; a tool that could register for you would be the bulk
registration §R4b forbids.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from apps.pipeline.tests.test_palette_statistics import (  # noqa: E402
    SERVICES,
    _symbol_of,
    composed_gate,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = os.path.join(
    REPO, "docs", "roadmap", "palt_m6", "enforcement_closure",
    "gate_baseline.json")


def baseline_keys() -> set:
    return set(map(tuple, json.load(open(BASELINE))["keys"]))


def unregistered() -> dict:
    """Every occurrence not in the baseline, grouped by key, with the
    source line so the judgment can be made on the code rather than on
    the shape name."""
    base = baseline_keys()
    inventory: dict = {}
    for path in sorted(SERVICES.rglob("*.py")):
        src = path.read_text()
        lines = src.splitlines()
        for shape, line in composed_gate(src):
            key = (path.name, _symbol_of(src, line), shape)
            if key in base:
                continue
            entry = inventory.setdefault("|".join(key), {
                "file": key[0], "symbol": key[1], "shape": key[2],
                "path": os.path.relpath(path, REPO), "occurrences": [],
            })
            entry["occurrences"].append(
                {"line": line, "code": lines[line - 1].strip()[:200]})
    return inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    inv = unregistered()
    if args.json:
        print(json.dumps(inv, indent=1))
        return 0

    total = sum(len(v["occurrences"]) for v in inv.values())
    print(f"unregistered keys: {len(inv)}   occurrences: {total}")
    if not inv:
        print("gate is GREEN — every occurrence is registered")
        return 0
    print()
    for file, count in Counter(v["file"] for v in inv.values()).most_common():
        occ = sum(len(v["occurrences"]) for v in inv.values()
                  if v["file"] == file)
        print(f"  {count:3d} keys / {occ:4d} occurrences   {file}")
    print()
    print("Register each key with a justification naming the concrete")
    print("downstream consequence of the default. Bulk registration and")
    print("wildcards are forbidden (§R4b).")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
