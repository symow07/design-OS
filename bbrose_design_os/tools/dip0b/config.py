"""DIP-0B configuration: pilot scope, capability tiers, resource limits.

Reuses the DIP-0A read-only invariants rather than re-implementing them. The
14 pilot files are the ONLY permitted inputs; anything else is refused.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tools.dip0.config import (  # noqa: F401 — re-exported invariants
    REPO_ROOT,
    SOURCE_ROOT,
    assert_output_safe,
    relpath,
    physical_path,
)

TOOL_NAME = "dip0b"
TOOL_VERSION = "0.1.0"

OUTPUT_ROOT = REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0b"
OUT_TECHNICAL = OUTPUT_ROOT / "technical"
OUT_PREVIEWS = OUTPUT_ROOT / "previews"
OUT_REPORTS = OUTPUT_ROOT / "reports"
OUT_TEMP = OUTPUT_ROOT / "temporary"
# B2
OUT_UNITS = OUTPUT_ROOT / "units"
OUT_OVERLAYS = OUTPUT_ROOT / "overlays"
OUT_CROPS = OUTPUT_ROOT / "crops"
OUT_REVIEW = OUTPUT_ROOT / "regions_review"

DOCS_ROOT = REPO_ROOT / "docs" / "design_intelligence" / "dip0b"
PILOT_MANIFEST = REPO_ROOT / "docs" / "design_intelligence" / "dip0a" / "pilot_manifest.json"

# The one branch historical production designs may come from (DIP-0A truth).
HISTORICAL_DIR = "materials/historical AI production designs"


# --- capability tiers (safeguard: every value declares what it really is) ----
TIER_DIRECT = "DIRECT"                            # read from the PDF structure
TIER_HEURISTIC = "HEURISTIC"                      # inferred by rule
TIER_REQUIRES_ILLUSTRATOR = "REQUIRES_ILLUSTRATOR"  # locked in /AIPrivateData
TIER_REQUIRES_HUMAN = "REQUIRES_HUMAN"            # only a designer can settle it
TIERS = (TIER_DIRECT, TIER_HEURISTIC, TIER_REQUIRES_ILLUSTRATOR, TIER_REQUIRES_HUMAN)

# Capabilities that live inside the opaque Illustrator private payload. DIP-0B
# records that they exist and are unreachable. It never parses the payload.
ILLUSTRATOR_ONLY_CAPABILITIES = (
    "original_layer_names_and_nesting",
    "live_text_objects_and_fonts",
    "symbols_and_instances",
    "appearance_attributes",
    "live_effects",
    "artboard_names",
    "swatch_library",
)


@dataclass(frozen=True)
class Limits:
    """Hard operational guards (safeguard 3).

    Reaching a limit is never fatal and never silent: the record gets
    `truncated=true`, the exact limit, what was skipped, and a reduced
    confidence. `YB-1025(LP5870)...ai` (77,322 xrefs, 9,630 transparency
    groups) is the file these exist for.
    """

    max_xref_scan: int = 20_000
    max_paths_detailed: int = 500        # bounded sample; aggregates cover the rest
    max_clips_enumerated: int = 2_000
    max_groups_enumerated: int = 2_000
    max_render_px: int = 2_000           # long edge (previews / overlays)
    max_crop_px: int = 800               # candidate crops are review thumbnails
    max_page_seconds: float = 60.0
    max_mask_pixels: int = 4_000_000
    max_crops_per_page: int = 200        # reserved for B2

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_LIMITS = Limits()


def ensure_output_dirs() -> None:
    for d in (OUT_TECHNICAL, OUT_PREVIEWS, OUT_REPORTS, OUT_TEMP,
              OUT_UNITS, OUT_OVERLAYS, OUT_CROPS, OUT_REVIEW):
        assert_output_safe(d)
        d.mkdir(parents=True, exist_ok=True)


# --- pilot scope guard ------------------------------------------------------

class PilotScopeError(RuntimeError):
    """Raised when an input is not an approved historical-design pilot file."""


def load_pilot(manifest: Path | None = None) -> list[dict]:
    """The 14 approved HISTORICAL_DESIGN files, re-verified.

    DIP-0B must never touch stock vectors, reusable assets, brand masters,
    logos, downloaded illustrations, or the 135 scattered non-production `.ai`
    files. Every entry is re-checked against the historical branch and `.ai`
    extension — the manifest is trusted, but verified.
    """
    manifest = Path(manifest or PILOT_MANIFEST)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    entries = data.get("historical_designs") or []
    if not entries:
        raise PilotScopeError(f"no historical_designs[] in {manifest}")

    out = []
    for e in entries:
        rel = e["relative_path"]
        verify_pilot_path(rel)
        out.append(e)
    return out


def verify_pilot_path(rel: str) -> None:
    if not rel.startswith(HISTORICAL_DIR + "/"):
        raise PilotScopeError(
            f"refusing non-historical input (DIP-0B is pilot-only): {rel}")
    if not rel.lower().endswith(".ai"):
        raise PilotScopeError(f"refusing non-.ai input: {rel}")
    if "/" in rel[len(HISTORICAL_DIR) + 1:]:
        raise PilotScopeError(f"unexpected nesting under historical branch: {rel}")
