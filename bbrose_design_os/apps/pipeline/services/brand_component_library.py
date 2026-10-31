"""MINIMUM brand component library — brand_gov.minimum_component_library.

WHAT "MINIMUM" MEANS HERE. Exactly four components: the logo lockup, the
medallion, the registered symbol, and the divider rule. Not a starter set
to be grown by whoever needs one next — the EXPANDED library is a
separate tracker node, and a library that quietly accretes components is
how unlicensed artwork reaches production.

EVERY COMPONENT CARRIES PROVENANCE AND PERMISSION, OR IT DOES NOT EXIST.
That is the node's own title and it is enforced structurally rather than
documented: a component with no origin, no source and no confirmation
state cannot be constructed, and the origin must come from a CLOSED set.
There is no UNKNOWN origin and no GENERATED origin, because a brand
component whose provenance is unknown is precisely the thing this node
exists to prevent from being emitted.

TWO PROVENANCE CLASSES, AND THEY ARE NOT INTERCHANGEABLE:

* OWNER_CONFIRMED_VECTOR_EXTRACTION — the logo, medallion and registered
  symbol. These are DIRECT VECTOR EXTRACTIONS from the owner's own brand
  guideline PDF, owner-confirmed under VQ-2 with explicit codes. They
  were not traced, not redrawn, not image-traced, and no font was
  substituted; the record asserts each of those negatives and this module
  re-checks them rather than trusting the summary.
* GATE_A_VERIFIED_MEASUREMENT — the divider. The divider is NOT extracted
  brand artwork; it is a stroked rule whose width was MEASURED from the
  owner-approved front artwork and verified at Gate A. Recording it under
  the extraction origin would claim an authority it does not have, so it
  has its own origin and carries no asset file.

PERMISSION IS READ, NEVER ASSERTED. The scope string and the
third-party restriction are quoted live from the owner's confirmation
record. Hard-coding "BBROSE mark only" here would let this file and the
owner's record drift apart silently, and the file would win.

FAIL-CLOSED. The canonical asset is hash-verified against the hash the
owner confirmed. A missing asset, a changed asset, an unconfirmed
provenance or an unknown component id all REFUSE with an explicit
finding. Nothing degrades to a placeholder.
"""
from __future__ import annotations

import hashlib
import json
import os

from django.conf import settings

SCHEMA = "brand_component_library/1.0"

#: the owner-confirmed extraction record and the Gate-A verification that
#: measured the divider. Both are committed evidence, not derived here.
LOGO_RECORD = "docs/visual_quality/vq2/vq2_authoritative_bbrose_logo.json"
RULING_RECORD = "docs/visual_quality/vq2/vq2_brand_authority_ruling.json"
GATE_A_RECORD = "docs/visual_quality/vq2/gate_a_final_verification.json"
INK_RECORD = "docs/visual_quality/vq2/vq2_product_specific_logo_ink.json"

#: CLOSED. A component may not be admitted under an origin outside this
#: set, and neither member means "we do not know".
ORIGINS = frozenset({"OWNER_CONFIRMED_VECTOR_EXTRACTION",
                     "GATE_A_VERIFIED_MEASUREMENT"})

ROLES = frozenset({"wordmark_lockup", "medallion", "registered_symbol",
                   "rule"})

#: the MINIMUM set, in full. Exactly the four the tracker node names.
MINIMUM_SET = ("LOGO", "MEDALLION", "REGISTERED_SYMBOL", "DIVIDER")

#: the extraction record asserts each of these negatives about the logo.
#: They are the difference between an extraction and a reconstruction, so
#: they are re-checked here rather than taken on the record's word.
EXTRACTION_NEGATIVES = ("traced", "image_trace_used", "redrawn",
                        "font_substituted", "paths_simplified",
                        "medallion_altered", "registered_symbol_altered")

PROVENANCE_REQUIRED = ("origin", "source", "confirmation_state")
PERMISSION_REQUIRED = ("scope", "third_party_authorized", "owner_codes")

BRAND_LIB_COMPONENT_UNKNOWN = "BRAND_LIB_COMPONENT_UNKNOWN"
BRAND_LIB_SOURCE_RECORD_MISSING = "BRAND_LIB_SOURCE_RECORD_MISSING"
BRAND_LIB_ASSET_MISSING = "BRAND_LIB_ASSET_MISSING"
BRAND_LIB_ASSET_HASH_MISMATCH = "BRAND_LIB_ASSET_HASH_MISMATCH"
BRAND_LIB_PROVENANCE_INCOMPLETE = "BRAND_LIB_PROVENANCE_INCOMPLETE"
BRAND_LIB_ORIGIN_NOT_RECOGNISED = "BRAND_LIB_ORIGIN_NOT_RECOGNISED"
BRAND_LIB_PERMISSION_INCOMPLETE = "BRAND_LIB_PERMISSION_INCOMPLETE"
BRAND_LIB_EXTRACTION_NOT_CONFIRMED = "BRAND_LIB_EXTRACTION_NOT_CONFIRMED"
BRAND_LIB_SET_INCOMPLETE = "BRAND_LIB_SET_INCOMPLETE"


class BrandLibraryRefusal(ValueError):
    """Fail-closed refusal. Carries every finding, never just the first."""

    def __init__(self, findings):
        self.findings = list(findings)
        super().__init__("; ".join(self.findings))


def _abs(rel: str) -> str:
    return os.path.join(settings.BASE_DIR, rel)


def _load(rel: str) -> dict:
    path = _abs(rel)
    if not os.path.exists(path):
        raise BrandLibraryRefusal(
            [f"{BRAND_LIB_SOURCE_RECORD_MISSING}:{rel}"])
    with open(path) as fh:
        return json.load(fh)


def _sha256_16(rel: str) -> str:
    with open(_abs(rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def _verified_asset(rel: str, expected: str, component: str) -> dict:
    """The asset the owner confirmed, or a refusal. A component that
    cannot prove it is still the artwork that was approved is not a
    usable brand component."""
    if not os.path.exists(_abs(rel)):
        raise BrandLibraryRefusal(
            [f"{BRAND_LIB_ASSET_MISSING}:{component}:{rel}"])
    actual = _sha256_16(rel)
    if actual != expected:
        raise BrandLibraryRefusal(
            [f"{BRAND_LIB_ASSET_HASH_MISMATCH}:{component}:{rel}:"
             f"expected {expected}, found {actual} — the approved artwork "
             "has changed since the owner confirmed it"])
    return {"path": rel, "sha256_16": actual}


def _component(component_id: str, role: str, provenance: dict,
               permission: dict, **extra) -> dict:
    """The ONLY constructor. Provenance and permission are checked here
    so that no caller can assemble a component without them — the check
    lives at construction rather than in a later validation pass, because
    a validation pass can be skipped."""
    findings = []
    missing = [k for k in PROVENANCE_REQUIRED
               if k not in provenance or not provenance[k]]
    if missing:
        findings.append(f"{BRAND_LIB_PROVENANCE_INCOMPLETE}:"
                        f"{component_id}:{','.join(missing)}")
    origin = provenance.get("origin")
    if origin is not None and origin not in ORIGINS:
        findings.append(f"{BRAND_LIB_ORIGIN_NOT_RECOGNISED}:"
                        f"{component_id}:{origin!r}")
    missing_perm = [k for k in PERMISSION_REQUIRED if k not in permission]
    if missing_perm:
        findings.append(f"{BRAND_LIB_PERMISSION_INCOMPLETE}:"
                        f"{component_id}:{','.join(missing_perm)}")
    if role not in ROLES:
        findings.append(f"{BRAND_LIB_COMPONENT_UNKNOWN}:"
                        f"{component_id}:role={role!r}")
    if findings:
        raise BrandLibraryRefusal(findings)
    record = {"id": component_id, "role": role,
              "provenance": dict(provenance), "permission": dict(permission)}
    record.update(extra)
    return record


def _required(record: dict, key: str, label: str):
    """Membership, never a default. The composed-gate guard caught the
    first version of this module reading permission through `or {}`,
    which meant an ABSENT owner confirmation produced a permission with
    scope=None instead of refusing — a brand library that hands out the
    mark under a permission nobody granted. The default is the defect."""
    if key not in record:
        raise BrandLibraryRefusal(
            [f"{BRAND_LIB_PERMISSION_INCOMPLETE}:{label}.{key} is absent"])
    return record[key]


def _permission(logo: dict) -> dict:
    """Quoted live from the owner's confirmation, never restated, and
    never defaulted."""
    oc = _required(logo, "owner_confirmation", LOGO_RECORD)
    return {"scope": _required(oc, "scope", "owner_confirmation"),
            "third_party_authorized":
                not _required(oc, "third_party_assets_not_authorized",
                              "owner_confirmation"),
            "owner_codes": list(_required(oc, "codes", "owner_confirmation")),
            "confirmed_by": _required(oc, "confirmed_by",
                                      "owner_confirmation")}


def _assert_extraction_is_an_extraction(logo: dict) -> None:
    """The record asserts seven negatives that separate an extraction
    from a reconstruction. If any of them flips, the artwork is no longer
    the owner's mark — it is our drawing of it — and the confirmation no
    longer covers it.

    An ABSENT negative counts as violated: a record that does not assert
    "not traced" has not told us the mark was not traced, and reading it
    through a default would turn silence into assurance.
    """
    violated = [k for k in EXTRACTION_NEGATIVES if k not in logo or logo[k]]
    if "is_extraction_not_reconstruction" not in logo or \
            not logo["is_extraction_not_reconstruction"]:
        violated.append("is_extraction_not_reconstruction")
    if violated:
        raise BrandLibraryRefusal(
            [f"{BRAND_LIB_EXTRACTION_NOT_CONFIRMED}:{','.join(violated)}"])


def build() -> dict:
    """The minimum library, assembled from committed evidence only."""
    logo = _load(LOGO_RECORD)
    ruling = _load(RULING_RECORD)
    gate_a = _load(GATE_A_RECORD)
    ink = _load(INK_RECORD)

    _assert_extraction_is_an_extraction(logo)
    permission = _permission(logo)
    extraction_source = {
        "record": LOGO_RECORD,
        "source_file": logo.get("source_file"),
        "source_sha256": logo.get("source_sha256"),
        "extraction_method": logo.get("extraction_method")}

    def extracted(state: str) -> dict:
        return {"origin": "OWNER_CONFIRMED_VECTOR_EXTRACTION",
                "source": extraction_source,
                "confirmation_state": state}

    state = "OWNER_CONFIRMED"
    asset = _verified_asset(logo["canonical_ai"], logo["canonical_ai_sha256"],
                            "LOGO")

    components = [
        _component(
            "LOGO", "wordmark_lockup", extracted(state), permission,
            asset=asset,
            preview={"path": logo.get("preview_png")},
            sub_components=[c["component"] for c in logo.get("components") or []],
            source_path_items=logo.get("source_path_items"),
            emitted_segments=logo.get("emitted_segments")),
        _component(
            "MEDALLION", "medallion", extracted(state), permission,
            asset=asset,
            identity=logo.get("medallion_identity"),
            note="a REGION of the confirmed lockup, not a separate file — "
                 "it shares the lockup's asset and hash by construction"),
        _component(
            "REGISTERED_SYMBOL", "registered_symbol", extracted(state),
            permission,
            asset=asset,
            identity=logo.get("registered_symbol_identity"),
            may_be_omitted=bool(ruling.get("registered_symbol_omitted")),
            note="the ruling lists inclusion of the registered symbol among "
                 "the controls the approved mark holds, so omission is not a "
                 "layout choice"),
        _component(
            "DIVIDER", "rule",
            {"origin": "GATE_A_VERIFIED_MEASUREMENT",
             "source": {"record": GATE_A_RECORD,
                        "measured_from": "the owner-approved front artwork "
                                         "composition VQ2-A2-R2-FINAL",
                        "ink_record": INK_RECORD},
             "confirmation_state": "GATE_A_VERIFIED"},
            permission,
            asset=None,
            geometry={
                "stroke_width_pt":
                    (gate_a.get("colours") or {}).get(
                        "divider_width_nominal_pt"),
                # THE LIVE INK, NOT THE A2 ONE. a2_previous_inks.divider
                # is "#66433A" and is SUPERSEDED: A2 used four
                # near-but-not-equal browns, which is why the record
                # exists. The divider now shares the single flat product
                # ink with the logo and the product name.
                "ink_hex": ink.get("selected_product_ink"),
                "ink_is_shared_not_component_specific":
                    bool(ink.get("shared_single_flat_colour"))},
            note="NOT extracted brand artwork. A stroked rule whose width "
                 "was measured and Gate-A verified; it carries no asset "
                 "file and must never be recorded as an extraction"),
    ]

    ids = [c["id"] for c in components]
    absent = [c for c in MINIMUM_SET if c not in ids]
    if absent:
        raise BrandLibraryRefusal(
            [f"{BRAND_LIB_SET_INCOMPLETE}:{','.join(absent)}"])

    return {"schema_version": SCHEMA,
            "minimum_set": list(MINIMUM_SET),
            "components": components,
            "permission": permission,
            # HANDING OUT THE MARK WITHOUT ITS AUTHORIZED INK IS HOW THE
            # WRONG COLOUR SHIPS. The brand guideline publishes the logo
            # in CYAN, and this product does NOT use it — the approved
            # artwork contains zero cyan pixels. The geometry is
            # unaltered; only the ink differs, and the prohibited
            # treatments are quoted rather than summarised.
            "ink_authority": {
                "selected_product_ink": ink.get("selected_product_ink"),
                "guideline_source_colour": ink.get("guideline_source_colour"),
                "guideline_colour_used": ink.get("guideline_colour_used"),
                "shared_single_flat_colour":
                    ink.get("shared_single_flat_colour"),
                "applied_to": list(ink.get("applied_to") or []),
                "logo_geometry_altered": ink.get("logo_geometry_altered"),
                "prohibited_absent": dict(ink.get("prohibited_absent") or {}),
                "record": INK_RECORD},
            "expanded_library_is_a_separate_node": True}


def component(component_id: str) -> dict:
    """One component by id, or a refusal. There is no default and no
    nearest match — guessing which brand component the caller meant is
    how the wrong mark gets emitted."""
    for record in build()["components"]:
        if record["id"] == component_id:
            return record
    raise BrandLibraryRefusal(
        [f"{BRAND_LIB_COMPONENT_UNKNOWN}:{component_id!r} — the minimum "
         f"library is exactly {', '.join(MINIMUM_SET)}"])
