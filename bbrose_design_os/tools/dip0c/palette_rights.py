"""Palette naming, ownership and usage rights (DIP-0C3c).

**The filename proves nothing.** `Pantone_3519C.ase` sits in a folder called "general
models from the internet". Neither the name nor the location establishes that BBROSE
owns it, that it is an official BBROSE palette, or that anyone may redistribute it.

And the bytes say something sharper than the filename does: this file's colour type is
**GLOBAL**, not SPOT. It carries no spot identity, no CMYK, no Lab, no ICC profile.
"Pantone" exists **only inside a name string** — it is third-party *naming evidence*,
not an authoritative Pantone definition. There is nothing here to convert *from*, so
nothing may be inferred about what ink this would be on press.

A palette may parse perfectly and still be unusable, because parsing is a technical
fact and ownership is a legal one. They never collapse into one score.
"""
from __future__ import annotations

import re

from . import config as C

PARSER = f"{C.TOOL_NAME}.palette_rights/{C.TOOL_VERSION}"

# --- machine-allowed palette states -------------------------------------------
TECHNICALLY_PARSED = "TECHNICALLY_PARSED"
PARTIAL_PARSE = "PARTIAL_PARSE"
REFERENCE_ONLY = "REFERENCE_ONLY"
OWNERSHIP_UNCONFIRMED = "OWNERSHIP_UNCONFIRMED"
LICENSE_UNVERIFIED = "LICENSE_UNVERIFIED"
REQUIRES_HUMAN = "REQUIRES_HUMAN"
MACHINE_ALLOWED = (TECHNICALLY_PARSED, PARTIAL_PARSE, REFERENCE_ONLY,
                   OWNERSHIP_UNCONFIRMED, LICENSE_UNVERIFIED, REQUIRES_HUMAN)

# --- states no machine may ever produce ---------------------------------------
APPROVED_BRAND_PALETTE = "APPROVED_BRAND_PALETTE"
APPROVED_REUSABLE = "APPROVED_REUSABLE"
LICENSE_APPROVED = "LICENSE_APPROVED"
BBROSE_OWNED_CONFIRMED = "BBROSE_OWNED_CONFIRMED"
HUMAN_ONLY = (APPROVED_BRAND_PALETTE, APPROVED_REUSABLE, LICENSE_APPROVED,
              BBROSE_OWNED_CONFIRMED)

# --- third-party naming systems, recognised as NAMES, never as definitions -----
NAMING_SYSTEMS = {
    "PANTONE": re.compile(r"\bpantone\b|\bpms\b", re.I),
    "RAL": re.compile(r"\bral\s*\d{3,4}\b", re.I),
    "NCS": re.compile(r"\bncs\b", re.I),
    "HKS": re.compile(r"\bhks\b", re.I),
    "TOYO": re.compile(r"\btoyo\b", re.I),
    "DIC": re.compile(r"\bdic\s*\d+\b", re.I),
}
TRADEMARKED = ("PANTONE", "RAL", "NCS", "HKS", "TOYO", "DIC")


def machine_palette_state(value: str | None) -> str | None:
    """Guard. Machine code may only ever produce a QUESTION, never an approval."""
    if value is None:
        return None
    if value in HUMAN_ONLY:
        raise C.HumanOnlyStateViolation(
            f"{value!r} is a HUMAN decision about a palette. Machine code may only "
            f"emit one of {list(MACHINE_ALLOWED)}. Parsing a colour is a technical "
            "fact; approving it is a legal and brand one.")
    if value not in MACHINE_ALLOWED:
        raise ValueError(f"{value!r} is not a known palette state")
    return value


def detect_naming(text: str) -> list[dict]:
    """Which third-party naming systems does this string mention?"""
    out = []
    for system, rx in NAMING_SYSTEMS.items():
        m = rx.search(text or "")
        if m:
            out.append({
                "system": system,
                "matched": m.group(0),
                "trademarked_third_party": system in TRADEMARKED,
                "note": f"{system} is a THIRD-PARTY naming system. A name is "
                        "evidence about naming — not a colour definition, not "
                        "ownership, and not permission to redistribute.",
            })
    return sorted(out, key=lambda r: r["system"])


def naming_evidence(parsed: dict) -> dict:
    """Naming findings across the filename AND the swatch names."""
    path = parsed.get("source") or ""
    filename = path.rsplit("/", 1)[-1]
    folder = path.rsplit("/", 1)[0] if "/" in path else ""
    swatch_names = [s["name"] for s in parsed["swatches"]]

    from_filename = detect_naming(filename)
    from_swatches = sorted(
        ({"swatch": s["name"], **d} for s in parsed["swatches"]
         for d in detect_naming(s["name"])),
        key=lambda r: (r["swatch"], r["system"]))

    # Does anything in the FILE actually define a spot colour?
    has_spot = any(s["color_type"] == "SPOT" for s in parsed["swatches"])
    models = sorted({s["model"] for s in parsed["swatches"]})

    return {
        "source_filename": filename,
        "source_folder": folder,
        "swatch_names": swatch_names,
        "naming_from_filename": from_filename,
        "naming_from_swatch_names": from_swatches,
        "detected_naming_systems": sorted(
            {d["system"] for d in from_filename}
            | {d["system"] for d in from_swatches}),
        "third_party_naming_present": bool(from_filename or from_swatches),
        "contains_spot_identity": has_spot,
        "color_models_present": models,
        "authoritative_definition_present": has_spot and models != ["RGB"],
        "findings": _findings(from_filename, from_swatches, has_spot, models),
        "filename_proves_nothing": (
            "The filename and folder are NOT evidence of ownership, of brand "
            "association, or of permission. They never have been."),
        "parser": PARSER,
    }


def _findings(from_filename, from_swatches, has_spot, models) -> list[str]:
    out: list[str] = []
    systems = sorted({d["system"] for d in from_filename}
                     | {d["system"] for d in from_swatches})
    if not systems:
        return ["no third-party naming system was detected"]
    for s in systems:
        out.append(f"{s} naming detected — third-party, trademarked")
    if not has_spot:
        out.append(
            "the file declares NO spot colour: every swatch is GLOBAL or NORMAL. "
            "It therefore contains no authoritative spot definition, whatever its "
            "name says.")
    if models == ["RGB"]:
        out.append(
            "the file carries RGB only — no CMYK, no LAB, no ICC profile. There is "
            "nothing here from which a print-accurate or licensed conversion could "
            "be derived, and none may be fabricated from a generic formula.")
    if systems and not has_spot:
        out.append(
            f"CONCLUSION: {'/'.join(systems)} exists only in a NAME STRING. This is "
            "third-party naming evidence, not a colour definition and not a licence.")
    return out


def rights_record(parsed: dict, naming: dict) -> dict:
    """Ownership, licence and usage. Everything defaults to unconfirmed and false."""
    return {
        "ownership_status": machine_palette_state(OWNERSHIP_UNCONFIRMED),
        "license_status": machine_palette_state(LICENSE_UNVERIFIED),
        "brand_association": machine_palette_state(REQUIRES_HUMAN),
        "reuse_posture": machine_palette_state(REFERENCE_ONLY),
        "third_party_naming_present": naming["third_party_naming_present"],
        "detected_naming_systems": naming["detected_naming_systems"],
        # every permission is FALSE, and only a human may change that
        "permissions": {
            "retrieval_allowed": False,
            "automatic_use_allowed": False,
            "production_use_allowed": False,
            "modification_allowed": False,
            "embedding_allowed": False,
            "redistribution_allowed": False,
            "public_export_allowed": False,
            "approved_for_bbrose": False,
            "approved_for_other_brands": False,
        },
        "restrictions": [
            "no proprietary colour library may be bundled or redistributed",
            "only the single source file supplied in materials/ has been audited",
            "third-party naming does not grant any right to expose or export "
            "third-party reference data",
            "no commercial approval is implied by the presence of this file",
        ],
        "human_review_required": True,
        "why_unusable": (
            "The palette may be technically readable and still be unusable. Parsing a "
            "colour is a TECHNICAL fact; owning it, licensing it, and calling it the "
            "brand's are LEGAL and BRAND facts. None of the latter has been "
            "established, so every permission stays false."),
        "parser": PARSER,
    }


# --- the approval contract (defined here, exercised by nobody in C3c) ----------
APPROVAL_CHECKLIST = (
    "brand_association_confirmed",
    "ownership_or_permitted_use_confirmed",
    "intended_product_families",
    "intended_markets",
    "intended_print_or_digital_use",
    "source_color_model_confirmed",
    "approved_conversion_behavior",
    "spot_or_process_interpretation_confirmed",
    "official_swatch_names_confirmed",
    "version_or_date_recorded",
    "review_expiry_or_no_expiry_reason",
    "restrictions_recorded",
)


def blank_approval() -> dict:
    """The contract a human must satisfy. `None` is NOT a pass — it blocks.

    This mirrors the C3b3 canonical checklist deliberately: a palette approval will
    ride the SAME dual-control, ledger and permission machinery rather than growing a
    parallel one. C3c defines the contract; it approves nothing.
    """
    return {item: {"result": None, "confirmed_by": None, "confirmed_at": None,
                   "notes": ""} for item in APPROVAL_CHECKLIST}
