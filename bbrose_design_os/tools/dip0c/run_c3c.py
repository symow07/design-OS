"""DIP-0C3c runner — the ASE palette audit.

Read-only. The source file is never modified, never moved, never rewritten. The audit
reports what the bytes say and refuses to say anything else.

    python -m tools.dip0c.run_c3c
"""
from __future__ import annotations

import sys
import time

from tools.dip0.integrity import compare, snapshot
from tools.dip0.provenance import human_block

from . import ase
from . import config as C
from . import palette as PAL
from . import palette_rights as PR
from . import run_c3b2

PARSER = f"{C.TOOL_NAME}.run_c3c/{C.TOOL_VERSION}"

ASE_PATH = C.physical_path("materials/DOWNLOADE 2026/نماذج عامة من  01الانترنيت/Pantone_3519C.ase", C.REPO_ROOT)   # Day 6 migration: identity kept, bytes located by the manifest
OUT = C.OUTPUT_ROOT / "c3c"


def audit(path=ASE_PATH) -> dict:
    parsed = ase.parse_file(path)
    parsed["source"] = C.relpath(path)
    rec = PAL.palette_record(parsed)
    naming = PR.naming_evidence(parsed)
    rights = PR.rights_record(parsed, naming)
    return {"parsed": parsed, "palette": rec, "naming": naming, "rights": rights}


def review_item(a: dict) -> dict:
    """One human-review item. Machine fields populated; HUMAN fields blank."""
    rec, naming, rights = a["palette"], a["naming"], a["rights"]
    p = rec["palette"]
    return {
        "schema_version": "c3c_review_item/1.0",
        "queue": "K",
        "title": "colour palette awaiting ownership and brand review",
        "priority": "HIGH",
        "required_reviewer_roles": ["LEGAL_REVIEWER", "BRAND_ADMIN"],
        "batch_review_allowed": False,
        # --- what the machine found ---
        "machine": {
            "source_filename": naming["source_filename"],
            "source_folder": naming["source_folder"],
            "source_sha256": rec["source_file"]["sha256"],
            "parse_status": p["parse_status"],
            "capability": p["capability"],
            "layout": p["layouts_seen"],
            "fallback_used": p["fallback_used"],
            "parser_warnings": p["parser_warnings"],
            "parser_confidence": min(
                [s["normalized"]["confidence"] for s in rec["swatches"]] or [0.0]),
            "groups": p["group_count"],
            "swatches": p["swatch_count"],
            "color_models": p["color_models"],
            "color_types": p["color_types"],
            "swatch_summary": [
                {"name": s["raw"]["name"], "model": s["raw"]["model"],
                 "raw_channels": s["raw"]["channels"],
                 "color_type": s["raw"]["color_type"],
                 "srgb_preview_8bit": s["normalized"]["srgb_8bit_preview"],
                 "preview_is_derivative": True,
                 "conversion_method": s["normalized"]["conversion_method"]}
                for s in rec["swatches"]],
            "third_party_naming": naming["detected_naming_systems"],
            "naming_findings": naming["findings"],
            "ownership_status": rights["ownership_status"],
            "license_status": rights["license_status"],
            "brand_association": rights["brand_association"],
            "restrictions": rights["restrictions"],
            "conversion_warnings": rec["conversion_warnings"],
        },
        "required_human_action": (
            "Confirm (or deny) BBROSE ownership or permitted use, confirm brand "
            "association, and decide whether this palette may be retrieved at all. "
            "Until then every permission stays false."),
        # --- what only a human may fill in ---
        "human": {
            **human_block(),
            "ownership_confirmation": None,
            "brand_association": None,
            "palette_approval": None,
            "approved_brands": [],
            "approved_products": [],
            "approved_markets": [],
            "allowed_uses": [],
            "restrictions": [],
            "review_expiry": None,
        },
        "approval_contract": PR.blank_approval(),
        "parser": PARSER,
    }


def main(argv=None) -> int:
    t0 = time.monotonic()
    before = snapshot()

    if not ASE_PATH.exists():
        print(f"ASE not found: {ASE_PATH}", file=sys.stderr)
        return 1

    a = audit()
    item = review_item(a)
    rec, naming, rights = a["palette"], a["naming"], a["rights"]
    p = rec["palette"]
    sw = rec["swatches"][0]["raw"] if rec["swatches"] else {}

    # heavy output -> var/ (git-ignored); lightweight -> docs/
    C.assert_output_safe(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    out_bytes = run_c3b2._write(OUT / "palette_full.json", a)

    summary = {
        "slice": "DIP-0C3c",
        "source": rec["source_file"],
        "palette": p,
        "groups": rec["groups"],
        "swatches": rec["swatches"],
        "naming": naming,
        "rights": rights,
        "conversion_warnings": rec["conversion_warnings"],
    }
    out_bytes += run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3c_palette_summary.json", summary)
    out_bytes += run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3c_review_item_sample.json", item)

    after = snapshot()
    recon = {
        "slice": "DIP-0C3c",
        "c3b4_commit": "263a912",
        "ase_version": p["version"],
        "declared_block_count": p["declared_block_count"],
        "parsed_block_count": p["parsed_block_count"],
        "group_count": p["group_count"],
        "swatch_count": p["swatch_count"],
        "color_models": p["color_models"],
        "color_types": p["color_types"],
        "raw_swatch_names": [s["raw"]["name"] for s in rec["swatches"]],
        "parse_status": p["parse_status"],
        "capability": p["capability"],
        "layout": p["layouts_seen"],
        "fallback_used": p["fallback_used"],
        "parser_warnings": p["parser_warnings"],
        "conversion_warnings": rec["conversion_warnings"],
        "trailing_bytes": p["trailing_bytes"],
        "standard_failure_reason": sw.get("standard_failure_reason"),
        "third_party_naming": naming["detected_naming_systems"],
        "contains_spot_identity": naming["contains_spot_identity"],
        "authoritative_definition_present":
            naming["authoritative_definition_present"],
        "ownership_status": rights["ownership_status"],
        "license_status": rights["license_status"],
        "brand_association": rights["brand_association"],
        "permissions": rights["permissions"],
        "policy_conformance": {
            "parse_status_is_partial": p["parse_status"] == ase.PARTIAL_PARSE,
            "capability_requires_human": p["capability"] == ase.CAP_REQUIRES_HUMAN,
            "layout_is_non_standard":
                p["layouts_seen"] == [ase.LAYOUT_NON_STANDARD],
            "warning_name_length_absent":
                ase.W_NAME_LENGTH_ABSENT in p["parser_warnings"],
            "fallback_used": p["fallback_used"] is True,
            "never_technically_parsed":
                p["parse_status"] != ase.TECHNICALLY_PARSED,
            "all_permissions_false":
                not any(rights["permissions"].values()),
            "no_spot_identity": naming["contains_spot_identity"] is False,
        },
        "integrity": {"materials": compare(before, after)},
        "runtime_seconds": round(time.monotonic() - t0, 2),
        "output_bytes": out_bytes,
    }
    run_c3b2._write(C.MILESTONE_OUTPUT_ROOT / "c3c_parser_reconciliation.json", recon)
    _print(recon, naming)

    ok = (all(recon["policy_conformance"].values())
          and recon["integrity"]["materials"]["unchanged"])
    if not ok:
        print("\nFAILED: a C3c invariant broke", file=sys.stderr)
        return 1
    return 0


def _print(r: dict, naming: dict) -> None:
    print("DIP-0C3c — ASE colour palette audit")
    print(f"  file:       Pantone_3519C.ase — ASE v{r['ase_version'][0]}."
          f"{r['ase_version'][1]}, {r['declared_block_count']} block, "
          f"{r['group_count']} groups, {r['swatch_count']} swatch")
    print(f"  swatch:     {r['raw_swatch_names']} | {r['color_models']} | "
          f"{r['color_types']}")
    print(f"  parse:      {r['parse_status']} / {r['capability']}")
    print(f"  layout:     {r['layout']} (fallback_used={r['fallback_used']})")
    print(f"  warnings:   {r['parser_warnings']}")
    print(f"  std failed: {(r['standard_failure_reason'] or '')[:66]}...")
    print("  THE FINDING:")
    for f in naming["findings"]:
        print(f"     - {f}")
    print(f"  rights:     ownership={r['ownership_status']} "
          f"license={r['license_status']} brand={r['brand_association']}")
    print(f"  permissions: all false = {not any(r['permissions'].values())}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s")


if __name__ == "__main__":
    raise SystemExit(main())
