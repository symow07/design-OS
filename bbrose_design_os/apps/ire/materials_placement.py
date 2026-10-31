"""§BH39(d): the placement record on the Image seam, the credit node, and the
refusals — REFERENCE assets can never be placed; a conditioned PRODUCTION asset
whose credit is not visible where its terms say resolves REFERENCE for that
output (§BH37). The seam is ``pdf_ai._draw_image``: the ONE point a raster
reaches an artefact; ``compose.py`` and ``compose_vector_art.py`` are its callers.
"""
from __future__ import annotations

import os
from pathlib import Path

SCHEMA = "materials_placement/1.0"
USAGE_SCHEMA = "placement_usage/1.0"
CREDIT_NODE_PREFIX = "credit-"
REPO_ROOT = Path(__file__).resolve().parents[3]

#: resolutions a placement receives
PLACED = "PLACED"                                      # a PRODUCTION row, its credit (if any) visible
RESOLVED_REFERENCE_NO_VISIBLE_CREDIT = "RESOLVED_REFERENCE_NO_VISIBLE_CREDIT"   # §BH37: conditioned, credit absent → REFERENCE for this output
REFUSED_REFERENCE_ASSET = "REFUSED_REFERENCE_ASSET"    # a REFERENCE row can never be placed
REFUSED_NO_TIER_ROW = "REFUSED_NO_TIER_ROW"            # a materials/ source with no row in the tier record
REFUSED_NO_PLACEMENT_RECORD = "REFUSED_NO_PLACEMENT_RECORD"  # a materials/ source with no record on the document
REFUSED_IDENTITY_MISMATCH = "REFUSED_IDENTITY_MISMATCH"


class PlacementRefused(RuntimeError):
    """Raised by the emitter ahead of every byte when a placement is refused."""

    def __init__(self, code: str, src: str):
        super().__init__(f"{code}: {src}")
        self.code = code
        self.src = src


def materials_relative(src: str) -> str | None:
    """``materials/…`` relative path of an absolute or relative source under
    the repo's materials root; None for any other source (media/, tmp, …)."""
    p = Path(src)
    try:
        rel = p.resolve().relative_to(REPO_ROOT.resolve()) if p.is_absolute() else Path(src)
    except ValueError:
        return None
    s = str(rel).replace(os.sep, "/")
    return s if s.startswith("materials/") else None


def placement_record(node, tier_row: dict, *, panel: str = "", credit_node_name: str | None = None) -> dict:
    """The record a composer attaches for ONE placed asset: the tier row (path,
    sha256, tier, evidence, condition, terms_class), the placement (node name,
    mm box, clip), and the credit's rendering (the node that carries it)."""
    return {
        "node": node.name, "src": node.src, "relative_path": tier_row.get("relative_path"),
        "sha256": tier_row.get("sha256"), "tier": tier_row.get("tier"), "tier_source": tier_row.get("tier_source"),
        "evidence": tier_row.get("evidence"), "terms_class": tier_row.get("terms_class"),
        "condition": tier_row.get("condition") or "", "panel": panel,
        "box_mm": [node.x, node.y, node.w, node.h], "clipped": node.clip is not None,
        "credit_node": credit_node_name,
    }


def credit_text(condition: str) -> str:
    """The verbatim PRINT form the terms state ('"Designed by … / Freepik"'):
    the part after ' | ' of the channel's condition (web anchor | print text)."""
    web, _, prn = (condition or "").partition(" | ")
    return (prn or web).strip().strip('"')


def credit_node(record_row: dict, *, x: float, y: float, size_pt: float, font: str = "regular", color=None):
    """A live TextRun carrying the verbatim credit, named ``credit-<node>`` so the
    record and the artefact name the same object."""
    from apps.ire.graph import Color, TextRun
    return TextRun(name=f"{CREDIT_NODE_PREFIX}{record_row['node']}", text=credit_text(record_row["condition"]),
                   x=x, y=y, font=font, size_pt=size_pt, color=color or Color.from_hex("#000000", cmyk=(0, 0, 0, 1)))


def records_of(doc) -> list[dict]:
    return list(((doc.metadata or {}).get(SCHEMA) or {}).get("placements") or [])


def resolve_placements(doc) -> dict:
    """placement_usage/1.0: every Image node of the document resolved —
    PLACED, RESOLVED_REFERENCE_NO_VISIBLE_CREDIT, or a refusal. Read-only over
    the document; the emitter acts on it (skips a REFERENCE-resolved image,
    raises on a refusal) and the counter is reconciled against the artefact's
    embedded images (``reconcile_images``)."""
    from apps.ire.graph import Image, TextRun
    recs = {r["node"]: r for r in records_of(doc)}
    text_nodes = {n.name: n for n, _ in doc.walk() if isinstance(n, TextRun)}
    rows = []
    for node, _parent in doc.walk():
        if not isinstance(node, Image):
            continue
        rel = materials_relative(node.src)
        if rel is None:
            rows.append({"node": node.name, "src": node.src, "resolution": PLACED, "governed": False})
            continue
        rec = recs.get(node.name)
        if rec is None:
            rows.append({"node": node.name, "src": node.src, "resolution": REFUSED_NO_PLACEMENT_RECORD, "governed": True})
            continue
        from apps.ire.materials_paths import migration_row, original_material_key, MaterialPathError
        mapped = migration_row(node.src, repo_root=REPO_ROOT)
        if mapped:
            try:
                actual = original_material_key(node.src, mapped['sha256'], repo_root=REPO_ROOT)
                recorded = original_material_key(rec.get('relative_path') or '', rec.get('sha256'), repo_root=REPO_ROOT)
                matches = actual == recorded
            except MaterialPathError:
                matches = False
            if not matches:
                rows.append({'node': node.name, 'src': node.src, 'resolution': REFUSED_IDENTITY_MISMATCH, 'governed': True})
                continue
        if not rec.get("tier"):
            rows.append({"node": node.name, "src": node.src, "resolution": REFUSED_NO_TIER_ROW, "governed": True})
            continue
        if rec["tier"] != "PRODUCTION":
            rows.append({"node": node.name, "src": node.src, "resolution": REFUSED_REFERENCE_ASSET, "governed": True, "tier": rec["tier"]})
            continue
        if rec.get("condition"):
            cn = text_nodes.get(rec.get("credit_node") or f"{CREDIT_NODE_PREFIX}{node.name}")
            visible = cn is not None and credit_text(rec["condition"]) in (cn.text or "")
            if not visible:
                rows.append({"node": node.name, "src": node.src, "resolution": RESOLVED_REFERENCE_NO_VISIBLE_CREDIT,
                             "governed": True, "tier": "PRODUCTION", "condition": rec["condition"]})
                continue
        rows.append({"node": node.name, "src": node.src, "resolution": PLACED, "governed": True, "tier": "PRODUCTION",
                     "evidence": rec.get("evidence"), "condition": rec.get("condition") or ""})
    counter = {}
    for r in rows:
        counter[r["resolution"]] = counter.get(r["resolution"], 0) + 1
    return {"schema_version": USAGE_SCHEMA, "rows": rows, "counter": counter,
            "placed": sum(1 for r in rows if r["resolution"] == PLACED)}


def refuse_or_skip(doc) -> tuple[set[str], dict]:
    """Ahead of every byte the emitter writes: raise on a refusal; return the
    names of the Image nodes to SKIP (resolved REFERENCE for this output) and
    the placement_usage/1.0 record the emitter carries into ``usage_out``."""
    usage = resolve_placements(doc)
    for r in usage["rows"]:
        if r["resolution"] in (REFUSED_REFERENCE_ASSET, REFUSED_NO_TIER_ROW, REFUSED_NO_PLACEMENT_RECORD, REFUSED_IDENTITY_MISMATCH):
            raise PlacementRefused(r["resolution"], r["src"])
    return {r["node"] for r in usage["rows"] if r["resolution"] == RESOLVED_REFERENCE_NO_VISIBLE_CREDIT}, usage


def reconcile_images(pdf_path: str, usage: dict) -> dict:
    """The per-run placement counter against the artefact's embedded image
    XObjects (PyMuPDF). Disagreement is a defect (§BH39(f)); when PyMuPDF is
    absent the record says so rather than pretending agreement."""
    try:
        import fitz
    except ImportError:
        return {"embedded_images": None, "placed": usage.get("placed", 0), "agree": None,
                "note": "not reconciled: PyMuPDF absent"}
    embedded = 0
    with fitz.open(pdf_path) as pdf:
        for page in pdf:
            embedded += len(page.get_images())
    placed = usage.get("placed", 0)
    surplus = embedded - placed            # zero when the counter and the artefact agree (no dimensioned comparison)
    return {"embedded_images": embedded, "placed": placed, "surplus": surplus, "agree": not surplus}


__all__ = ["SCHEMA", "USAGE_SCHEMA", "CREDIT_NODE_PREFIX", "PLACED", "RESOLVED_REFERENCE_NO_VISIBLE_CREDIT",
           "REFUSED_REFERENCE_ASSET", "REFUSED_NO_TIER_ROW", "REFUSED_NO_PLACEMENT_RECORD", "PlacementRefused",
           "materials_relative", "placement_record", "credit_text", "credit_node", "records_of",
           "resolve_placements", "refuse_or_skip", "reconcile_images"]
