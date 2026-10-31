"""First real human metadata pilot scope — DIP-1C-5C
(`dip1c_semantic_metadata_pilot/1.0`).

A deterministic 12-item subset of the accepted 55-item DIP-1C-5B review scope, sized so one
reviewer can complete it in a single sitting with genuine attention per item. Selecting is a
pure read: it creates no `CorpusItem`, no `ReviewCandidate`, no `DecisionEvent`, and grants
nothing.

Composition (4 historical · 2 C2 assets · 2 curated assets · 2 fonts · 2 brand/palette) is
chosen for **type diversity against current document sparsity**: schema 1.2 renders 176
documents into only 63 distinct texts, and the duplicate collapse is concentrated in exactly
these segments. Each entry carries the descriptor domains a reviewer can honestly answer for
that item type, and the conclusions that are prohibited for it.

The scope is a subset **by construction** — it is drawn from `semantic_metadata_scope`, so an
item can never be in the pilot but outside the recording scope the service enforces.

**Readiness is a selection criterion, not a warning.** An item whose evidence integrity
blocks evidence-dependent claims would be refused by the projector, so it is excluded here
rather than handed to a reviewer who would waste the effort. That has a real consequence
today: 21 of 22 brand candidates are blocked by the unresolved `dip0c3_brand_candidates/1.0`
source version, so the brand/palette segment can supply only the Pantone palette item. The
document records the shortfall in `unfilled_segments` instead of padding the count.

Because readiness is part of the criteria, the pilot hash moves if evidence integrity is
repaired. That is correct: a different set of reviewable items IS a different pilot.
"""
from __future__ import annotations

import hashlib
import json

from .evidence_integrity import EvidenceIntegrityResolver
from .models import EvidenceReference, ReviewCandidate
from .semantic_metadata_scope import SCOPE_SCHEMA as REVIEW_SCOPE_SCHEMA
from .semantic_metadata_scope import select_scope_items

PILOT_SCHEMA = "dip1c_semantic_metadata_pilot/1.0"

TARGET = {
    "historical": 4,
    "c2_assets": 2,
    "curated_assets": 2,
    "fonts": 2,
    "brand_palette": 2,
}
TARGET_TOTAL = sum(TARGET.values())

# What a reviewer can honestly answer, per item type. A domain absent here is not "optional"
# — it is one the evidence for that type does not support, so offering it invites invention.
EXPECTED_DOMAINS = {
    "historical": (
        "product_families", "design_styles", "motifs", "visual_moods",
        "color_characteristics", "layout_or_format_types", "search_synonyms"),
    "c2_assets": (
        "design_styles", "motifs", "visual_moods", "color_characteristics",
        "layout_or_format_types", "asset_categories", "search_synonyms"),
    "curated_assets": (
        "design_styles", "motifs", "visual_moods", "color_characteristics",
        "layout_or_format_types", "asset_categories", "search_synonyms"),
    "fonts": (
        "font_styles", "script_suitability", "layout_or_format_types",
        "search_synonyms"),
    "brand_palette": (
        "brand_observations", "color_characteristics", "layout_or_format_types"),
}

REQUIRED_ROLE = {
    "historical": "DESIGN_REVIEWER",
    "c2_assets": "DESIGN_REVIEWER",
    "curated_assets": "DESIGN_REVIEWER",
    "fonts": "DESIGN_REVIEWER",
    # brand/palette triage is descriptive too, but BRAND_ADMIN is the role that routinely
    # looks at brand evidence. Either role is authorized; this records the preference.
    "brand_palette": "BRAND_ADMIN",
}

SELECTION_REASON = {
    "historical": (
        "Historical designs dominate the corpus and carry the least topical text; product "
        "family, style and motif are visible in the artwork and recorded nowhere."),
    "c2_assets": (
        "Original C2 assets whose machine asset kind is UNKNOWN, so schema 1.2 renders no "
        "asset-category phrase at all."),
    "curated_assets": (
        "Curated-expansion assets, to test whether the vocabulary behaves the same across "
        "two datasets with different provenance."),
    "fonts": (
        "Fonts carry family name and script coverage but no style judgement; font_styles is "
        "exactly the human-only channel."),
    "brand_palette": (
        "Brand and palette candidates are where descriptive review is most likely to drift "
        "into ownership language — the pilot must test that boundary deliberately."),
}

# Stated per entry so the prohibition travels with the item, not only with the doctrine.
PROHIBITED_CONCLUSIONS = (
    "OWNERSHIP", "OFFICIAL_BRAND_IDENTITY", "CANONICAL_MASTER", "LICENCE_VALIDITY",
    "RIGHTS_CLEARANCE", "OPERATIONAL_PERMISSION", "APPROVAL",
)
BRAND_PALETTE_NOTE = (
    "Observational only: record what is visible (a wordmark, a lockup, a palette-like "
    "graphic). Never assert that it IS the BBROSE mark, is owned, or is approved.")


def _candidate_ids(items):
    """Review-candidate UUIDs where they exist. Metadata recording does not require a
    candidate — this is context for the reviewer, not a dependency."""
    rows = ReviewCandidate.objects.filter(
        corpus_item__in=items).values_list("corpus_item_id", "id")
    return {str(item_id): str(candidate_id) for item_id, candidate_id in rows}


def _reviewable(items):
    """Items a reviewer can actually complete: evidence present, integrity not blocking, and
    reachable in the protected UI.

    UI reachability is a real constraint, not a nicety — metadata is submitted from the
    review-candidate detail page, so an item with no `ReviewCandidate` has no route a human
    can use. Including one would hand the reviewer an item they cannot review.

    One resolver, two bulk queries — no per-item fan-out.
    """
    resolver = EvidenceIntegrityResolver()
    with_evidence = set(EvidenceReference.objects.filter(
        corpus_item__in=items, is_test_only=False).values_list(
        "corpus_item_id", flat=True))
    with_candidate = set(ReviewCandidate.objects.filter(
        corpus_item__in=items).values_list("corpus_item_id", flat=True))
    return [item for item in items
            if item.pk in with_evidence and item.pk in with_candidate
            and not resolver.evaluate(item).blocks_evidence_dependent_claims]


def select_pilot_items():
    """The first N *reviewable* items of each segment of the accepted review scope, in its
    deterministic `external_key` order. A pure subset — never a separate selection."""
    segments = select_scope_items()
    return {segment: _reviewable(segments[segment])[:count]
            for segment, count in TARGET.items()}


def build_pilot_document():
    """Deterministic pilot document (no timestamp), hash-stable."""
    segments = select_pilot_items()
    every_item = [item for items in segments.values() for item in items]
    candidates = _candidate_ids(every_item)
    entries = []
    for segment, items in segments.items():
        for item in items:
            entry = {
                "corpus_item_id": str(item.pk),
                "review_candidate_id": candidates.get(str(item.pk), ""),
                "external_key": item.external_key,
                "item_kind": item.item_kind,
                "segment": segment,
                "selection_reason": SELECTION_REASON[segment],
                "required_reviewer_role": REQUIRED_ROLE[segment],
                "expected_descriptor_domains": list(EXPECTED_DOMAINS[segment]),
                "evidence_requirement": (
                    "At least one non-test EvidenceReference belonging to this item must be "
                    "cited; the reviewer must have looked at it."),
                "prohibited_conclusions": list(PROHIBITED_CONCLUSIONS),
            }
            if segment == "brand_palette":
                entry["observational_only_note"] = BRAND_PALETTE_NOTE
            entries.append(entry)
    entries.sort(key=lambda entry: entry["corpus_item_id"])
    return {
        "schema_version": PILOT_SCHEMA,
        "parent_review_scope": REVIEW_SCOPE_SCHEMA,
        "target": dict(TARGET),
        "target_total": TARGET_TOTAL,
        "segment_counts": {s: len(items) for s, items in segments.items()},
        # a segment that cannot supply its target is reported, never padded from elsewhere
        "unfilled_segments": {
            s: TARGET[s] - len(items) for s, items in segments.items()
            if len(items) < TARGET[s]},
        "actual_total": len(entries),
        "entries": entries,
    }


def _canonical_bytes(document) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def pilot_hash(document=None) -> str:
    return hashlib.sha256(
        _canonical_bytes(document or build_pilot_document())).hexdigest()


def pilot_item_ids():
    return {entry["corpus_item_id"] for entry in build_pilot_document()["entries"]}


def is_in_pilot(corpus_item) -> bool:
    return str(corpus_item.pk) in pilot_item_ids()
