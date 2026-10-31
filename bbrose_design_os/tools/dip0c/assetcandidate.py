"""AssetCandidate schema (DIP-0C2a).

One record per reusable-unit candidate extracted from a source file. The record
keeps the **five axes strictly independent** and defaults every rights/eligibility
field to a non-grant:

  A technical readiness      — present but UNSCORED in C2a (scored in C2b)
  B rights readiness         — ownership unconfirmed, licence unverified, all
                               permission flags false
  C reuse-posture candidate  — pending; machine code can never emit
                               APPROVED_REUSABLE
  D retrieval eligibility     — false
  E automatic-use eligibility — false

Candidate IDs are deterministic for identical **source bytes AND configuration**:
the source sha256, the derivation method, the rounded bbox and a fingerprint of
the segmentation thresholds all feed the id. A whole-file candidate (bbox = design
surface, geometrically config-independent) still varies with the config
fingerprint, so different thresholds never collide on one id.

This module builds records only — it holds no segmentation logic and never writes
the human block.
"""
from __future__ import annotations

import hashlib
import json

from tools.dip0.provenance import human_block

from . import config as C

SCHEMA_VERSION = "assetcandidate/1.0"


def config_fingerprint(params: dict) -> str:
    """Stable short hash of the thresholds/config that produced a candidate."""
    blob = json.dumps(params, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


def candidate_id(source_sha256: str | None, method: str, bbox, config_fp: str,
                 index: int) -> str:
    """Deterministic for identical source bytes + method + bbox + config."""
    bb = "none" if not bbox else ",".join(f"{round(float(v), 2)}" for v in bbox)
    src = source_sha256 or "no_sha"
    key = f"{src}|{method}|{bb}|{config_fp}|{index}".encode("utf-8")
    return hashlib.sha256(key).hexdigest()[:16]


def technical_readiness_unscored() -> dict:
    """Axis A — present, deliberately not scored in C2a."""
    return {
        "value": None,
        "status": C.READY_UNSCORED,
        "evidence": ["technical-readiness scoring is DIP-0C2b, not C2a"],
        "confidence": 0.0,
    }


def rights_readiness() -> dict:
    """Axis B — nothing granted. Consistent with the C1 rights contract."""
    return {
        "ownership": "unconfirmed",
        "license": "unverified",
        "commercial_use": False,
        "modification": False,
        "embedding": False,
        "redistribution": False,
        "attribution_required": None,
        "reviewer": None,
        "evidence": [],
        "confidence": 0.0,
    }


def reuse_posture_candidate() -> dict:
    """Axis C — pending; APPROVED_REUSABLE is unreachable here by construction."""
    return {
        "value": None,
        "status": C.POSTURE_PENDING,
        "machine_allowed": list(C.MACHINE_ALLOWED_POSTURES),
        "note": "posture recommendation is a later slice; the fully-approved "
                "reusable posture is human-only and never machine-emitted",
    }


def build_candidate(*, source: dict, method: str, status: str, bbox_pt=None,
                    bbox_px=None, preview_source: str, capability_tier: str,
                    confidence: float, evidence: list[str], parser: str,
                    config_fp: str, index: int,
                    inventory_category: str, override: dict | None,
                    collection: dict | None = None,
                    isolated_confidence: float | None = None,
                    asset_type: str = C.ASSET_TYPE_UNKNOWN,
                    page: int | None = None, extra: dict | None = None) -> dict:
    if method not in C.SEG_METHODS:
        raise ValueError(f"unknown segmentation method: {method!r}")
    if status not in C.SEGMENTATION_STATUS:
        raise ValueError(f"unknown segmentation status: {status!r}")
    if asset_type not in C.ASSET_TYPES:
        raise ValueError(f"unknown asset type: {asset_type!r}")

    bbox = bbox_pt if bbox_pt is not None else bbox_px
    cid = candidate_id(source.get("sha256"), method, bbox, config_fp, index)
    rec = {
        "schema": SCHEMA_VERSION,
        "candidate_id": cid,
        "source_file": {
            "relative_path": source["relative_path"],
            "sha256": source.get("sha256"),
            "format": source.get("format"),
            "kind": source.get("kind"),
        },
        "page_or_artboard": page,
        "segmentation": {
            "method": method,
            "status": status,
            "capability_tier": capability_tier,
            "confidence": round(float(confidence), 3),
            "evidence": list(evidence),
            "config_fingerprint": config_fp,
        },
        "bbox_pt": [round(float(v), 2) for v in bbox_pt] if bbox_pt else None,
        "bbox_px": [int(v) for v in bbox_px] if bbox_px else None,
        "preview_source": preview_source,          # var/ path or "none"; never committed
        "asset_type": {"value": asset_type, "tier": C.TIER_HEURISTIC,
                       "note": "type inference deferred to a later slice"},
        "isolated_candidate_confidence": (round(float(isolated_confidence), 3)
                                          if isolated_confidence is not None
                                          else None),
        "collection": collection,                  # membership / parent, or None
        "parser": parser,
        # ---- classification provenance (never rewrites DIP-0A) ----
        "inventory_category_original": inventory_category,
        "classification_override": override,       # from C1's classify_override, or None
        # ---- FIVE INDEPENDENT AXES ----
        "A_technical_readiness": technical_readiness_unscored(),
        "B_rights_readiness": rights_readiness(),
        "C_reuse_posture_candidate": reuse_posture_candidate(),
        "D_retrieval_eligibility": False,
        "E_automatic_use_eligibility": False,
        "production_use": False,
        # ---- human curation (machine never writes) ----
        "human": human_block(),
    }
    if extra:
        rec["segmentation_detail"] = extra
    return rec
