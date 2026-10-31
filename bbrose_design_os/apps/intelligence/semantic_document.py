"""Bounded semantic source document — DIP-1C-1 (`intelligence_semantic_document/1.0`).

This is the ONLY representation of a corpus item that may ever be sent to an external
embedding provider. It is a strict allow-list: only bounded, non-secret metadata is
included, and the builder is written so that adding a field is a deliberate act, not an
accident. Everything an embedding could leak — binaries, absolute or relative filesystem
paths, source-location observations, secrets, HMAC material, DecisionEvent payloads,
authorization snapshots, reviewer usernames, licence-document text, unrestricted raw
values, legacy authority signals — is excluded by construction and asserted absent before
transmission.

Machine-generated labels and verified human assertions are both included but remain
clearly distinguishable in the document, so an encoder can never quietly launder a machine
guess into a human conclusion.

The document is deterministic and hashed: the same corpus state always yields the same
document and the same hash, which is what makes an index rebuild idempotent.
"""
from __future__ import annotations

import hashlib
import json
import re

from .models import (
    MachineClassification, ObservedFact, ReviewCandidate,
)
from .projection_reader import read_published_assertions
from .review_campaign import CampaignScopeError, campaign_entry_for
from .review_readiness import assess_readiness

# --- schema 1.0: FROZEN. Preserved so historical generations remain describable and so
# tests can pin its meaning. It is never emitted by the builder any more; 1.1 supersedes it.
DOCUMENT_SCHEMA_V1_0 = "intelligence_semantic_document/1.0"
INCLUDED_FIELDS_V1_0 = (
    "external_key", "item_kind", "display_label", "dataset_identifier",
    "product_family_label", "style_labels", "font_metadata",
    "observed_fact_labels", "observed_fact_values",
    "machine_classification_labels", "human_assertion_labels",
    "readiness_state", "blocker_codes",
)

# --- schema 1.1: the active schema (DIP-1C-3A) ----------------------------------
# Changes, and why the version advances rather than mutating 1.0:
#   * `display_label` is now OPTIONAL — an unsafe optional title is omitted instead of
#     excluding the whole item, so items whose only title is a source filename stay
#     indexable via their safe fields.
#   * `machine_product_family_labels` — bounded, explicitly machine-derived.
#   * `observed_script_coverage` — bounded technical font observation.
# A 1.1 document therefore hashes differently from 1.0 and needs a new generation.
DOCUMENT_SCHEMA_V1_1 = "intelligence_semantic_document/1.1"
DOCUMENT_SCHEMA = DOCUMENT_SCHEMA_V1_1

# the fields this schema is permitted to carry — the external boundary is this list.
# It is an ALLOW-list, not a required-list: an optional field may be omitted.
# NB: 1.0's `product_family_label` is REMOVED in 1.1, not merely supplemented. It was a raw
# unbounded passthrough of a machine string — an unvalidated leak vector (a path-shaped
# machine label would have been transmitted verbatim). It is superseded by
# `machine_product_family_labels`, which is normalized through an explicit vocabulary,
# refuses path-like values, and names itself machine-derived.
INCLUDED_FIELDS = (
    "external_key", "item_kind", "display_label", "dataset_identifier",
    "machine_product_family_labels", "style_labels",
    "font_metadata", "observed_script_coverage",
    "observed_fact_labels", "observed_fact_values",
    "machine_classification_labels", "human_assertion_labels",
    "readiness_state", "blocker_codes",
)

# --- bounded product-family vocabulary (machine observations only) ----------------
# Sourced ONLY from HistoricalDesignProfile.product_family_machine_label and
# MachineClassification(classification_type=HISTORICAL_PRODUCT_FAMILY). Never inferred
# from a filename, directory, or title.
PRODUCT_FAMILY_VOCABULARY = {
    "makeup-compact": "MAKEUP_COMPACT",
    "complexion": "COMPLEXION",
    "lip-colour": "LIP_COLOUR",
    "lip-color": "LIP_COLOUR",
    "primer-skincare": "PRIMER_SKINCARE",
    "eye-colour": "EYE_COLOUR",
    "eye-color": "EYE_COLOUR",
    "concealer": "CONCEALER",
}
PRODUCT_FAMILY_OTHER = "OTHER"
PRODUCT_FAMILY_CONFLICT = "MACHINE_LABELS_CONFLICT"
PRODUCT_FAMILY_CLASSIFICATION_TYPE = "HISTORICAL_PRODUCT_FAMILY"

# --- bounded script vocabulary (technical observation only) -----------------------
SCRIPT_VOCABULARY = {
    "latin": "LATIN",
    "arabic": "ARABIC",
    "arabic_presentation_a": "ARABIC",
    "arabic_presentation_b": "ARABIC",
    "cyrillic": "CYRILLIC",
    "greek": "GREEK",
    "hebrew": "HEBREW",
    "cjk": "CJK",
    "cjk_ext_a": "CJK",
    "cjk_ext_b": "CJK",
    "hangul": "HANGUL",
    "devanagari": "DEVANAGARI",
    "thai": "THAI",
}
SCRIPT_OTHER = "OTHER"
SCRIPT_UNKNOWN = "UNKNOWN"
# `numerals` is a character class, not a script. Mapping it to OTHER would put 33 of 34
# fonts in OTHER and destroy the field's discriminating value, so it is excluded from
# script coverage deliberately and explicitly — not silently dropped.
NON_SCRIPT_TOKENS = frozenset({"numerals", "punctuation", "symbols"})

# diagnostics recorded LOCALLY and never transmitted
OPTIONAL_DISPLAY_LABEL_OMITTED_SOURCE_FILENAME = (
    "OPTIONAL_DISPLAY_LABEL_OMITTED_SOURCE_FILENAME")

# fields that must NEVER appear in a semantic document — asserted absent before any send
PROHIBITED_FIELDS = (
    "source_binary", "image", "illustrator_file", "font_file", "archive_contents",
    "absolute_path", "relative_path", "path", "source_location", "source_locations",
    "secret", "api_key", "hmac", "decision_event_payload", "authorization_snapshot",
    "username", "reviewer", "licence_text", "license_text", "acquisition_document",
    "raw_value", "evidence_locator", "legacy_approval", "legacy_signal", "vector",
)

_MAX_LABELS = 32
_MAX_LABEL_LEN = 100
_MAX_VALUE_LEN = 120


class SemanticDocumentError(ValueError):
    """A document that cannot be built within the boundary is refused, never trimmed
    silently into something that leaks. `code` is a bounded reason code."""

    def __init__(self, message, code=""):
        super().__init__(message)
        self.code = code


def _bounded(text, limit=_MAX_LABEL_LEN):
    return (str(text) if text is not None else "")[:limit]


def _labels(values, limit=_MAX_LABELS):
    seen, out = set(), []
    for value in values:
        label = _bounded(value)
        if label and label not in seen:
            seen.add(label)
            out.append(label)
        if len(out) >= limit:
            break
    return sorted(out)


def _raw_display_label(item):
    for attr, field in (("historical_design_profile", "display_title"),
                        ("font_face_profile", "family_name"),
                        ("design_asset_profile", "candidate_source_key")):
        profile = getattr(item, attr, None)
        if profile is not None:
            return _bounded(getattr(profile, field) or "")
    brand = getattr(item, "brand_candidate_profile", None)
    if brand is not None:
        return _bounded(brand.observed_brand_label or brand.get_candidate_kind_display())
    return ""


def _display_label(item):
    """Back-compat helper: the safe label only (may be empty)."""
    return _safe_display_label(item)[0]


def _safe_display_label(item):
    """Deterministic precedence for a SAFE display label → (label, omission_reason).

    1. a verified human display/classification label, when one exists;
    2. a safe imported descriptive title;
    3. a safe bounded non-filename label;
    4. omit.

    It never falls back to a source filename, path, archive member, absolute location, or
    a directory-derived phrase. The stable external key stays available as identity
    metadata but is NOT promoted into natural-language semantic content.

    An unsafe optional title is OMITTED, never sanitized: stripping `.ai` off
    `LG5505唇彩.ai` and presenting the remainder as a reviewed title would manufacture
    semantic metadata that no human ever approved.
    """
    # 1. a verified human label, if any exists
    assertions = read_published_assertions(item)
    for current in (assertions.current_by_domain or {}).values():
        if isinstance(current, dict):
            human = _bounded(current.get("label", ""))
            if human and not _classify_value(human):
                return human, ""
    # 2-3. a safe imported/bounded label
    raw = _raw_display_label(item)
    if not raw:
        return "", ""
    code = _classify_value(raw)
    if code:
        # 4. omit — record the reason locally; the value itself is never transmitted
        return "", OPTIONAL_DISPLAY_LABEL_OMITTED_SOURCE_FILENAME
    return raw, ""


def _machine_product_family_labels(item):
    """Bounded, explicitly MACHINE-derived product-family labels.

    Sourced only from existing machine observations — the profile's machine label and
    HISTORICAL_PRODUCT_FAMILY classifications. Never inferred from a filename or directory.
    Disagreeing machine observations are BOTH kept plus an explicit conflict marker, rather
    than one being chosen silently.
    """
    raw = set()
    profile = getattr(item, "historical_design_profile", None)
    if profile is not None and (profile.product_family_machine_label or "").strip():
        raw.add(profile.product_family_machine_label.strip().lower())
    for label in MachineClassification.objects.filter(
            corpus_item=item,
            classification_type=PRODUCT_FAMILY_CLASSIFICATION_TYPE).values_list(
            "label", flat=True):
        if (label or "").strip():
            raw.add(label.strip().lower())

    normalized = set()
    for value in raw:
        if _classify_value(value):
            continue                      # a path-like value can never become a family
        mapped = PRODUCT_FAMILY_VOCABULARY.get(value)
        if mapped:
            normalized.add(mapped)
        elif value not in ("", "unknown", "none"):
            normalized.add(PRODUCT_FAMILY_OTHER)
    if not normalized:
        return []
    labels = sorted(normalized)
    if len(labels) > 1:
        labels.append(PRODUCT_FAMILY_CONFLICT)   # visible disagreement, never a silent pick
    return labels


def _observed_script_coverage(item):
    """Bounded technical script observation for a font face.

    A technical observation only: NOT a font recommendation, NOT licence evidence, NOT
    permission to use the face. Presence of a script means glyphs were observed in it — it
    is not a guarantee of coverage depth (the DIP-0C4 lesson: presence is not coverage).
    Emits bounded vocabulary names only — never raw ranges, paths, or filenames.
    """
    profile = getattr(item, "font_face_profile", None)
    if profile is None:
        return []
    coverage = profile.script_coverage
    tokens = []
    if isinstance(coverage, dict):
        tokens = list(coverage.keys())
    elif isinstance(coverage, (list, tuple)):
        tokens = list(coverage)
    if not tokens:
        return []
    scripts = set()
    for token in tokens:
        key = str(token).strip().lower()
        if not key or key in NON_SCRIPT_TOKENS:
            continue
        scripts.add(SCRIPT_VOCABULARY.get(key, SCRIPT_OTHER))
    return sorted(scripts)


def _dataset_identifier(item):
    profile = getattr(item, "design_asset_profile", None)
    return profile.dataset_identifier if profile is not None else ""


def _product_family_label(item):
    profile = getattr(item, "historical_design_profile", None)
    # a MACHINE label — included for matching, but the document marks it machine-generated
    return _bounded(profile.product_family_machine_label) if profile is not None else ""


def _font_metadata(item):
    profile = getattr(item, "font_face_profile", None)
    if profile is None:
        return {}
    # bounded technical font metadata only — never the font binary
    return {
        "family_name": _bounded(getattr(profile, "family_name", "")),
        "technical_suitability_state": _bounded(
            getattr(profile, "technical_suitability_state", "")),
    }


def _style_labels(item):
    """Bounded style/kind labels only.

    `DesignAssetProfile.collection_family_label` is deliberately NOT included. It was
    assumed to be a collection/style name, but it is operationally contaminated with source
    paths (34 of 100 asset rows hold values like
    `materials/DOWNLOADE 2026/DOWNLOADS 12-2025/9993170.ai`), so it cannot be trusted as
    semantic design metadata and must never be transmitted. The stored values are left
    untouched for provenance; they are simply not part of the external document. A
    human-reviewed collection label may arrive later via a separately defined safe field or
    a signed human assertion — never by sanitizing this one.
    """
    labels = []
    asset = getattr(item, "design_asset_profile", None)
    if asset is not None:
        labels.append(asset.candidate_asset_kind)
    brand = getattr(item, "brand_candidate_profile", None)
    if brand is not None:
        labels.append(brand.candidate_kind)
    return _labels(label for label in labels if label)


def build_semantic_document(item, *, with_diagnostics=False):
    """Build the bounded `intelligence_semantic_document/1.1` for one item. Read-only.

    Optional fields that would carry an unsafe value are OMITTED (with a locally recorded,
    never-transmitted diagnostic) so the item stays indexable via its safe fields. Required
    identity fields still fail closed. The fully assembled document is validated at the end
    — no document passes because its fields were checked individually earlier.
    """
    facts = list(ObservedFact.objects.filter(corpus_item=item)
                 .values_list("fact_type", "normalized_value")[:_MAX_LABELS])
    machine_labels = list(MachineClassification.objects.filter(
        corpus_item=item).values_list("label", flat=True)[:_MAX_LABELS])
    assertions = read_published_assertions(item)
    human_labels = [c.get("label", "") for c in
                    (assertions.current_by_domain or {}).values()
                    if isinstance(c, dict)]

    candidate = ReviewCandidate.objects.filter(
        corpus_item=item).order_by("created_at").first()
    readiness_state, blocker_codes = "", []
    if candidate is not None:
        try:
            entry = campaign_entry_for(candidate)
            readiness = assess_readiness(
                candidate, wave=entry["wave"] if entry else None)
            readiness_state = readiness.overall
            blocker_codes = list(readiness.blocker_codes)
        except CampaignScopeError:
            readiness_state, blocker_codes = "", []

    diagnostics = []
    safe_label, omission = _safe_display_label(item)
    if omission:
        diagnostics.append({"field": "display_label", "reason_code": omission})

    document = {
        "schema_version": DOCUMENT_SCHEMA,
        "external_key": _bounded(item.external_key),
        "item_kind": item.item_kind,
        "dataset_identifier": _dataset_identifier(item),
        # explicitly MACHINE-derived — never presented as verified product family
        "machine_product_family_labels": _machine_product_family_labels(item),
        "style_labels": _style_labels(item),
        "font_metadata": _font_metadata(item),
        # technical observation only — not a recommendation, licence, or permission
        "observed_script_coverage": _observed_script_coverage(item),
        "observed_fact_labels": _labels(f[0] for f in facts),
        # normalized bounded values only — never the unrestricted raw_value
        "observed_fact_values": _labels(
            (_bounded(f[1], _MAX_VALUE_LEN) for f in facts if isinstance(f[1], str))),
        # machine vs human kept distinguishable, by key name
        "machine_classification_labels": _labels(machine_labels),
        "human_assertion_labels": _labels(human_labels),
        "readiness_state": readiness_state,
        "blocker_codes": sorted(blocker_codes),
    }
    # optional field: present only when safe. Omitted entirely otherwise — the unsafe
    # value never reaches the document, its bytes, its hash, or the preview.
    if safe_label:
        document["display_label"] = safe_label

    # final gate on the COMPLETE assembled document — nothing passes on the strength of
    # an earlier per-field check
    _assert_within_boundary(document)
    if with_diagnostics:
        return document, diagnostics
    return document


# --- value-boundary reason codes -------------------------------------------------
PROHIBITED_FIELD_NAME = "PROHIBITED_FIELD_NAME"
ABSOLUTE_PATH_VALUE = "ABSOLUTE_PATH_VALUE"
RELATIVE_PATH_VALUE = "RELATIVE_PATH_VALUE"
MATERIALS_PATH_VALUE = "MATERIALS_PATH_VALUE"
FILE_URI_VALUE = "FILE_URI_VALUE"
SOURCE_FILENAME_VALUE = "SOURCE_FILENAME_VALUE"
PROHIBITED_FILE_REFERENCE = "PROHIBITED_FILE_REFERENCE"

# source-artifact extensions, matched only when the value actually looks like a file
# reference — never merely because a phrase contains a period
SOURCE_EXTENSIONS = (
    ".ai", ".eps", ".pdf", ".psd", ".svg", ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    ".zip", ".otf", ".ttf", ".ttc", ".ase",
)

_ABSOLUTE_POSIX = re.compile(r"(^|\s)/(Users|home|private|tmp|var|opt|etc|mnt|media)/",
                             re.IGNORECASE)
_WINDOWS_DRIVE = re.compile(r"(^|\s)[A-Za-z]:[\\/]")
_FILE_URI = re.compile(r"file://", re.IGNORECASE)
_TRAVERSAL = re.compile(r"\.\.[\\/]")
# the boundary set includes ':' so an embedded key like "asset:materials/x.ai" is
# classified as a materials path rather than falling through to a vaguer code
_MATERIALS = re.compile(r"(^|[\s\"'(:/\\])materials[\\/]", re.IGNORECASE)
_SEPARATOR = re.compile(r"[\\/]")
# a bare filename like "9993170.ai" or "logo.psd": token + source extension, no spaces
_BARE_FILENAME = re.compile(
    r"(^|\s)[\w.\-]+(" + "|".join(re.escape(e) for e in SOURCE_EXTENSIONS) + r")(\s|$)",
    re.IGNORECASE)


def _source_root_fragments():
    """Configured source-root fragments (e.g. the repo's materials root), so a value that
    embeds the real source root is caught even if it is not literally 'materials/'."""
    fragments = set()
    try:
        from django.conf import settings
        for name in ("DIP_SOURCE_ROOT", "SOURCE_ROOT", "MATERIALS_ROOT", "BASE_DIR"):
            value = getattr(settings, name, None)
            if value:
                text = str(value).strip().strip("/")
                if text and len(text) > 3:
                    fragments.add(text.lower())
    except Exception:
        pass
    return fragments


def _classify_value(text: str) -> str:
    """Return a reason code if this string is a path/file reference, else ""."""
    if not text:
        return ""
    lowered = text.lower()
    if _FILE_URI.search(text):
        return FILE_URI_VALUE
    if _TRAVERSAL.search(text):
        return RELATIVE_PATH_VALUE
    if _MATERIALS.search(text):
        return MATERIALS_PATH_VALUE
    if _ABSOLUTE_POSIX.search(text) or text.startswith("/"):
        return ABSOLUTE_PATH_VALUE
    if _WINDOWS_DRIVE.search(text):
        return ABSOLUTE_PATH_VALUE
    for fragment in _source_root_fragments():
        if fragment in lowered:
            return MATERIALS_PATH_VALUE
    has_extension = any(lowered.endswith(e) or f"{e} " in f"{lowered} "
                        for e in SOURCE_EXTENSIONS)
    if has_extension:
        # a separator plus a source extension is a path; a bare filename is still a
        # source reference. A dotted phrase without either is fine.
        if _SEPARATOR.search(text):
            return RELATIVE_PATH_VALUE
        if _BARE_FILENAME.search(text):
            return SOURCE_FILENAME_VALUE
        return PROHIBITED_FILE_REFERENCE
    return ""


def _walk(value, path, findings):
    """Recursively inspect every nested value — a prohibited value must not pass merely
    because it sits inside an allowed field."""
    if isinstance(value, dict):
        for key, child in value.items():
            _walk(child, f"{path}.{key}" if path else str(key), findings)
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _walk(child, f"{path}[{index}]", findings)
    elif isinstance(value, str):
        code = _classify_value(value)
        if code:
            findings.append((path, code))
    # numbers, bools and None carry no path content


def _assert_within_boundary(document):
    """Fail closed on a prohibited field NAME or a prohibited VALUE anywhere inside.

    The original check inspected field names only, so a filesystem path embedded in an
    allowed field (`style_labels`) passed validation and would have been transmitted. Values
    are now walked recursively.
    """
    unexpected = set(document) - ({"schema_version"} | set(INCLUDED_FIELDS))
    if unexpected:
        raise SemanticDocumentError(
            f"semantic document has unexpected fields: {sorted(unexpected)}",
            code=PROHIBITED_FIELD_NAME)
    blob = json.dumps(document, sort_keys=True).lower()
    for prohibited in PROHIBITED_FIELDS:
        if f'"{prohibited}"' in blob:
            raise SemanticDocumentError(
                f"prohibited field {prohibited!r} present in semantic document",
                code=PROHIBITED_FIELD_NAME)

    findings = []
    _walk(document, "", findings)
    if findings:
        # identify WHERE, never log the prohibited value itself
        located = ", ".join(f"{field}={code}" for field, code in findings)
        raise SemanticDocumentError(
            f"prohibited value in semantic document at {located}",
            code=findings[0][1])


def document_hash(document) -> str:
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def semantic_text(document) -> str:
    """The flat text an encoder embeds. Deterministic, order-stable, labels only.

    `display_label` is optional in schema 1.1 and may be absent, so it is read with .get().
    """
    parts = [
        document.get("display_label", ""), document["item_kind"],
        document["dataset_identifier"],
        " ".join(document.get("machine_product_family_labels", [])),
        " ".join(document["style_labels"]),
        " ".join(document.get("observed_script_coverage", [])),
        " ".join(document["observed_fact_labels"]),
        " ".join(document["observed_fact_values"]),
        " ".join(document["machine_classification_labels"]),
        " ".join(document["human_assertion_labels"]),
        document["readiness_state"],
    ]
    font = document.get("font_metadata") or {}
    parts.extend(str(v) for v in font.values())
    return " ".join(p for p in parts if p).strip()
