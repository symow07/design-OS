"""Editable human-review manifest (DIP-0B2, safeguard 5 + decision 8).

The review path is **mandatory**, not optional. This is a validated, editable
JSON document — not a UI. A reviewer may:

  accept · relabel · split_by_bbox · merge · exclude ·
  identify_primary_artwork · identify_dieline ·
  include_workspace / exclude_workspace · mark_manual · note

Machine inference is **preserved verbatim** after any human correction: an
operation writes into the `human` block and appends to `review_operations`; it
never mutates `candidate_type`, `bbox_pt`, `path_count` or any other machine
field. Applying a review therefore never destroys what the machine said.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from . import config as C

REVIEW_VERSION = "b2-review-1"

OPERATIONS = (
    "accept",
    "relabel",
    "split_by_bbox",
    "merge",
    "exclude",
    "identify_primary_artwork",
    "identify_dieline",
    "include_workspace",
    "exclude_workspace",
    "mark_manual",
    "note",
)

DISPOSITIONS = ("pending", "accepted", "relabelled", "split", "merged",
                "excluded", "manual")


class ReviewError(ValueError):
    """An invalid review operation. Nothing is applied."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def build_review(seg: dict) -> dict:
    """A blank, editable review document for one page."""
    def entry(c: dict) -> dict:
        return {
            "unit_id": c["unit_id"],
            "off_canvas": c["off_canvas"],
            # --- machine inference (never written by a reviewer) -----------
            "machine": {
                "candidate_type": c["candidate_type"]["value"],
                "confidence": c["candidate_type"]["confidence"],
                "evidence": c["candidate_type"]["evidence"],
                "tier": c["candidate_type"]["tier"],
                "bbox_pt": c["bbox_pt"],
                "path_count": c["path_count"],
                "raster_count": c["raster_count"],
                "structural_count": c["structural_count"],
                "repeat_evidence": c.get("repeat_evidence", []),
                "contained_by": c.get("contained_by"),
            },
            # --- human curation (never pre-filled as a confirmed fact) -----
            "human": {
                "confirmed_type": None,
                "is_primary_artwork": None,
                "is_dieline": None,
                "include_in_historical_memory": None,
                "disposition": "pending",
                "correction_reason": None,
                "notes": "",
            },
        }

    return {
        "review_version": REVIEW_VERSION,
        "file": seg["file"],
        "page": seg["page"],
        "artbox_pt": seg["artbox_pt"],
        "reviewer": None,
        "reviewed_at": None,
        "page_disposition": "pending",
        "segmentation": {
            "machine_status": seg["segmentation"]["status"],
            "failure_indicators": seg["segmentation"]["failure_indicators"],
            "human_status": None,          # MANUAL_RESOLVED is set by a person
        },
        "provenance": seg["provenance"],
        "candidates": [entry(c) for c in seg["candidates"]],
        "workspace_candidates": [entry(c) for c in seg["workspace_candidates"]],
        "review_operations": [],
        "operations_supported": list(OPERATIONS),
        "policy": ("machine fields are immutable; human fields start empty; "
                   "off-canvas workspace candidates are never auto-included in "
                   "Historical Design Memory"),
    }


def _find(review: dict, unit_id: str) -> dict:
    for key in ("candidates", "workspace_candidates"):
        for c in review[key]:
            if c["unit_id"] == unit_id:
                return c
    raise ReviewError(f"unknown unit_id: {unit_id}")


def _validate_bbox(b) -> list[float]:
    if not (isinstance(b, (list, tuple)) and len(b) == 4):
        raise ReviewError(f"bbox must be [x0,y0,x1,y1], got {b!r}")
    x0, y0, x1, y1 = (float(v) for v in b)
    if x1 <= x0 or y1 <= y0:
        raise ReviewError(f"degenerate bbox: {b!r}")
    return [x0, y0, x1, y1]


def apply_operation(review: dict, op: dict, reviewer: str) -> dict:
    """Apply one operation, returning a NEW document. Machine data is untouched.

    Raises `ReviewError` on an invalid operation; the document is not modified.
    """
    kind = op.get("op")
    if kind not in OPERATIONS:
        raise ReviewError(f"unsupported operation: {kind!r}")

    r = copy.deepcopy(review)
    ts = _now()
    record = {"op": kind, "reviewer": reviewer, "at": ts,
              "review_version": REVIEW_VERSION,
              **{k: v for k, v in op.items() if k != "op"}}

    if kind == "mark_manual":
        r["segmentation"]["human_status"] = "MANUAL_RESOLVED" \
            if op.get("resolved") else "MANUAL_REQUIRED"
        r["page_disposition"] = "manual"

    elif kind == "note":
        c = _find(r, op["unit_id"]) if op.get("unit_id") else None
        if c:
            c["human"]["notes"] = op.get("text", "")
        else:
            r.setdefault("page_notes", "")
            r["page_notes"] = op.get("text", "")

    elif kind == "accept":
        c = _find(r, op["unit_id"])
        c["human"]["confirmed_type"] = c["machine"]["candidate_type"]
        c["human"]["disposition"] = "accepted"

    elif kind == "relabel":
        from .regions import CANDIDATE_TYPES
        t = op.get("candidate_type")
        if t not in CANDIDATE_TYPES:
            raise ReviewError(f"unknown candidate_type: {t!r}")
        c = _find(r, op["unit_id"])
        c["human"]["confirmed_type"] = t
        c["human"]["disposition"] = "relabelled"
        c["human"]["correction_reason"] = op.get("reason")

    elif kind == "exclude":
        c = _find(r, op["unit_id"])
        c["human"]["disposition"] = "excluded"
        c["human"]["include_in_historical_memory"] = False
        c["human"]["correction_reason"] = op.get("reason")

    elif kind == "identify_primary_artwork":
        c = _find(r, op["unit_id"])
        c["human"]["is_primary_artwork"] = True

    elif kind == "identify_dieline":
        c = _find(r, op["unit_id"])
        c["human"]["is_dieline"] = True

    elif kind in ("include_workspace", "exclude_workspace"):
        c = _find(r, op["unit_id"])
        if not c["off_canvas"]:
            raise ReviewError(f"{op['unit_id']} is not a workspace candidate")
        c["human"]["include_in_historical_memory"] = (kind == "include_workspace")

    elif kind == "split_by_bbox":
        c = _find(r, op["unit_id"])
        boxes = op.get("bboxes") or []
        if len(boxes) < 2:
            raise ReviewError("split_by_bbox needs at least two bboxes")
        parts = []
        for i, b in enumerate(boxes):
            parts.append({"child_unit_id": f"{c['unit_id']}.s{i:02d}",
                          "bbox_pt": _validate_bbox(b),
                          "confirmed_type": op.get("types", [None] * len(boxes))[i]})
        c["human"]["disposition"] = "split"
        c["human"]["split_into"] = parts     # machine bbox_pt preserved above
        c["human"]["correction_reason"] = op.get("reason")

    elif kind == "merge":
        ids = op.get("unit_ids") or []
        if len(ids) < 2:
            raise ReviewError("merge needs at least two unit_ids")
        members = [_find(r, i) for i in ids]
        if len({m["off_canvas"] for m in members}) > 1:
            raise ReviewError("cannot merge primary and workspace candidates")
        target = ids[0]
        for m in members:
            m["human"]["disposition"] = "merged"
            m["human"]["merged_into"] = target
            m["human"]["correction_reason"] = op.get("reason")

    r["review_operations"].append(record)
    r["reviewer"] = reviewer
    r["reviewed_at"] = ts
    return r


def validate_review(review: dict) -> list[str]:
    """Structural problems a reviewer's edit could introduce. Empty == valid."""
    problems = []
    if review.get("review_version") != REVIEW_VERSION:
        problems.append(f"review_version mismatch: {review.get('review_version')}")
    seen = set()
    for key in ("candidates", "workspace_candidates"):
        for c in review.get(key, []):
            if c["unit_id"] in seen:
                problems.append(f"duplicate unit_id {c['unit_id']}")
            seen.add(c["unit_id"])
            if set(c.get("machine", {})) < {"candidate_type", "bbox_pt"}:
                problems.append(f"{c['unit_id']}: machine block incomplete")
            d = c.get("human", {}).get("disposition")
            if d not in DISPOSITIONS:
                problems.append(f"{c['unit_id']}: bad disposition {d!r}")
            if key == "candidates" and c.get("off_canvas"):
                problems.append(f"{c['unit_id']}: off_canvas in primary list")
    return problems


def write_review(review: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or C.OUT_REVIEW)
    C.assert_output_safe(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(review["file"]).stem
    p = out_dir / f"{stem}-p{review['page']}.review.json"
    C.assert_output_safe(p)
    p.write_text(json.dumps(review, indent=1, ensure_ascii=False), encoding="utf-8")
    return p
