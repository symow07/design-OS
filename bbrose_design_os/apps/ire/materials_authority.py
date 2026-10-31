"""Materials authority — the two tiers of §BH36(a), built at §BH37(1).

The materials twin of ``container_font_authority``: every governed material
carries a TIER. A machine may write REFERENCE — the engine may read, caption,
index and draw inspiration from the file; it is never embedded, traced or
reproduced in an output. PRODUCTION — embeddable in outputs — sits ABOVE THE
CEILING and enters only through the owner-grant channel
(``materials_owner_grant``), keyed by the file's sha256 and pinned to the
governing terms text by path AND sha256, re-hashed on every application;
an evidence mismatch or an unnamed sha256 leaves the row at REFERENCE. Absent
evidence is REFERENCE, never an error-shaped pass.

Discipline (the font module's, carried over):
* a tier is NEVER inferred from a filename, a folder name or a licence's name;
* a machine records the tier it may write and nothing that grants;
* the CONDITION field carries an attribution credit verbatim where a text
  requires one — the wiring front enforces it; this module only carries it.
"""
from __future__ import annotations

import hashlib

SCHEMA = "materials_tier/1.0"

# --- the two tiers (§BH36(a)) -------------------------------------------------
TIER_REFERENCE = "REFERENCE"
TIER_PRODUCTION = "PRODUCTION"

# --- the ceiling: which tier a MACHINE may write ------------------------------
# By substance, as in the font module (§BH14(a)): a tier is ABOVE the ceiling
# if it GRANTS. Reordering the constants cannot move the partition.
ABOVE_CEILING = "ABOVE_CEILING"
AT_OR_BELOW_CEILING = "AT_OR_BELOW_CEILING"
TIER_CEILING = {
    TIER_PRODUCTION: ABOVE_CEILING,       # embeddable — a grant
    TIER_REFERENCE: AT_OR_BELOW_CEILING,  # grants nothing
}
MACHINE_FORBIDDEN_TIERS = tuple(t for t, side in TIER_CEILING.items() if side == ABOVE_CEILING)
MACHINE_WRITABLE_TIERS = tuple(t for t, side in TIER_CEILING.items() if side == AT_OR_BELOW_CEILING)

# --- the tier's ORIGIN, under the same ceiling -------------------------------
TIER_SOURCE_MACHINE = "MACHINE"          # the machine's own write: REFERENCE
TIER_SOURCE_OWNER_GRANT = "OWNER_GRANT"  # conferred by the channel, evidence re-hashed


class MaterialTierAboveCeiling(RuntimeError):
    """A machine tried to write a tier that GRANTS.

    Deliberately NOT a ``ValueError``: an unrecognised tier raises ``ValueError``
    instead, so a cap test can prove WHICH refusal fired — the font module's own
    two-refusal discipline.
    """


def machine_writable_tier(value: str) -> str:
    """Guard. Returns ``value`` only if it sits at or below the ceiling."""
    if value not in TIER_CEILING:
        raise ValueError(
            f"{value!r} is not a materials tier. Known: {sorted(TIER_CEILING)}")
    if TIER_CEILING[value] == ABOVE_CEILING:
        raise MaterialTierAboveCeiling(
            f"{value!r} is above the ceiling: a machine writing it would confer "
            f"authority only the owner may confer. Writable: "
            f"{list(MACHINE_WRITABLE_TIERS)}")
    return value


def sha256_of_file(path: str) -> str | None:
    """The file's sha256, or None when it cannot be read. Never raises.

    A materials/ path recorded before the Day 6 migration is absent at its recorded spelling;
    the migration manifest maps it to the file's new place, and the identity (path, sha) is
    unchanged, so the recorded evidence still re-verifies."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except FileNotFoundError:
        from apps.ire.materials_paths import resolve_material_file, MaterialPathError
        try:
            moved = resolve_material_file(path)
        except MaterialPathError:
            return None
        return None if str(moved) == str(path) else sha256_of_file(str(moved))
    except OSError:
        return None


def tier_row(relative_path: str, sha256: str) -> dict:
    """One machine-written row: REFERENCE, the only tier a machine may write —
    passed through the guard so a future edit cannot slip a grant past it."""
    return {
        "relative_path": relative_path,
        "sha256": sha256,
        "tier": machine_writable_tier(TIER_REFERENCE),
        "tier_source": TIER_SOURCE_MACHINE,
        "evidence": "",            # the governing terms text: "<path> sha256:<hex>" when granted
        "condition": "",           # the verbatim attribution credit when the text requires one
        "granted_by": "",
        "granted_at": "",
    }


def build_tier_record(rows) -> dict:
    """``materials_tier/1.0`` — every row at REFERENCE by machine. ``rows`` are
    inventory-shaped mappings carrying ``relative_path`` and ``sha256``
    (DIP-0A's inventory rows or any subset). Deterministic order: by path."""
    out = []
    for r in sorted(rows, key=lambda r: str(r.get("relative_path") or "")):
        out.append(tier_row(str(r.get("relative_path") or ""), str(r.get("sha256") or "")))
    return {"schema_version": SCHEMA, "rows": out,
            "all_machine_rows_reference": all(x["tier"] == TIER_REFERENCE for x in out)}


def tier_counts(record: dict) -> dict:
    """Counts per tier and per source — the reconciliation the report prints."""
    by_tier: dict = {}; by_source: dict = {}
    for r in record.get("rows") or []:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
        by_source[r["tier_source"]] = by_source.get(r["tier_source"], 0) + 1
    return {"rows": len(record.get("rows") or []), "by_tier": by_tier, "by_source": by_source}


__all__ = ["SCHEMA", "TIER_REFERENCE", "TIER_PRODUCTION", "ABOVE_CEILING", "AT_OR_BELOW_CEILING",
           "TIER_CEILING", "MACHINE_FORBIDDEN_TIERS", "MACHINE_WRITABLE_TIERS",
           "TIER_SOURCE_MACHINE", "TIER_SOURCE_OWNER_GRANT", "MaterialTierAboveCeiling",
           "machine_writable_tier", "sha256_of_file", "tier_row", "build_tier_record", "tier_counts"]
