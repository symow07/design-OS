"""Controlled DIP-1B-2 correction from 48 C2 records to 47 semantic assets."""
from __future__ import annotations

import collections

from django.db import transaction

from apps.accounts.models import DecisionEvent

from .identity import (
    ASSET_IDENTITY_VERSION, C2_DATASET_ID, IDENTITY_ALIAS_PROVENANCE,
    CandidateIdentityError, asset_classification_identity_hash,
    asset_fact_identity_hash, evidence_identity_hash, semantic_asset_external_key,
)
from .import_services import finalize_import_batch, record_import_attempt
from .manifest import (
    IMPORTER_VERSION, PreparedManifest, canonical_hash, prepare_manifest,
)
from .models import (
    CorpusItem, DesignAssetProfile, EvidenceReference, ImportBatch, ImportRecord,
    MachineClassification, ObservedFact, OperationalPermissionProjection,
    ProvenanceRecord,
)

RECONCILER_IDENTIFIER = "bbrose.intelligence.reconcile_dip1b2_asset_identity"


def _manifest_origins(prepared: PreparedManifest):
    origins = collections.defaultdict(list)
    source_hashes = collections.defaultdict(set)
    for entry, candidate, _record_hash, candidate_index in prepared.domain_records["assets"]:
        key = str(candidate["candidate_id"])
        origins[key].append({
            "stable_source_key": entry.declaration["stable_source_key"],
            "source_path": entry.declaration["source"]["path"],
            "source_hash": entry.declaration["source"]["sha256"],
            "record_locator": {
                "path": entry.declaration["data_source"]["source"]["path"],
                "segments": (
                    entry.declaration["data_source"]["locator"]["value"]["segments"]
                    + [candidate_index]
                ),
            },
        })
        source_hashes[key].add(entry.declaration["source"]["sha256"])
    return origins, source_hashes


def _build_plan(prepared):
    origins, source_hashes = _manifest_origins(prepared)
    profiles = list(DesignAssetProfile.objects.select_related(
        "corpus_item", "primary_source_artifact",
    ).filter(dataset_identifier=C2_DATASET_ID))
    persisted = collections.defaultdict(list)
    for profile in profiles:
        persisted[profile.candidate_source_key].append(profile)
    if set(persisted) != set(origins):
        raise CandidateIdentityError(
            "persisted C2 candidate keys do not match the frozen bounded manifest"
        )

    groups = []
    for candidate_key in sorted(origins):
        expected_origins = sorted(
            origins[candidate_key], key=lambda row: (
                row["stable_source_key"], row["record_locator"]["path"],
                tuple(row["record_locator"]["segments"]),
            ),
        )
        candidates = sorted(
            persisted[candidate_key],
            key=lambda profile: (profile.source_manifest_entry_key,
                                 str(profile.corpus_item_id)),
        )
        if not 1 <= len(candidates) <= len(expected_origins):
            raise CandidateIdentityError(
                f"candidate {candidate_key!r} has an unexpected persisted subject count"
            )
        if any(profile.primary_source_artifact.sha256 not in source_hashes[candidate_key]
               for profile in candidates):
            raise CandidateIdentityError(
                f"candidate {candidate_key!r} is linked to an unexpected source identity"
            )
        canonical_source_key = expected_origins[0]["stable_source_key"]
        winner = next(
            (profile for profile in candidates
             if profile.source_manifest_entry_key == canonical_source_key),
            candidates[0],
        )
        groups.append({
            "candidate_key": candidate_key,
            "origins": expected_origins,
            "canonical_source_key": canonical_source_key,
            "winner": winner,
            "losers": [profile for profile in candidates if profile.pk != winner.pk],
            "semantic_external_key": semantic_asset_external_key(
                C2_DATASET_ID, candidate_key),
        })
    return groups


def _result(prepared, groups, *, mode, batch=None, before_profiles=None,
            normalized_external_keys=None):
    losers = [profile for group in groups for profile in group["losers"]]
    duplicate_records = {
        group["candidate_key"]: len(group["origins"])
        for group in groups if len(group["origins"]) > 1
    }
    return {
        "mode": mode,
        "identity_version": ASSET_IDENTITY_VERSION,
        "manifest_hash": prepared.manifest_hash,
        "frozen_candidate_records": prepared.actual_counts["asset_candidates"],
        "semantic_candidates": prepared.actual_counts["semantic_asset_candidates"],
        "physical_source_artifacts": prepared.actual_counts["c2_content_identities"],
        "duplicate_record_groups": duplicate_records,
        "profiles_before": (before_profiles if before_profiles is not None
                            else DesignAssetProfile.objects.filter(
                                dataset_identifier=C2_DATASET_ID).count()),
        "profiles_after": DesignAssetProfile.objects.filter(
            dataset_identifier=C2_DATASET_ID).count() if mode == "apply" else (
                DesignAssetProfile.objects.filter(
                    dataset_identifier=C2_DATASET_ID).count() - len(losers)),
        "subjects_merged": len(losers),
        "external_keys_normalized": (normalized_external_keys
                                     if normalized_external_keys is not None else sum(
            group["winner"].corpus_item.external_key != group["semantic_external_key"]
            for group in groups
        )),
        "legacy_url_aliases": len(losers),
        "batch_id": str(batch.pk) if batch else None,
    }


def _rehash_and_rehome_evidence(group):
    winner_item = group["winner"].corpus_item
    item_ids = [winner_item.pk] + [profile.corpus_item_id for profile in group["losers"]]
    evidence_rows = list(EvidenceReference.objects.select_related(
        "source_artifact",
    ).filter(corpus_item_id__in=item_ids))
    for evidence in evidence_rows:
        evidence.corpus_item = winner_item
        evidence.evidence_hash = evidence_identity_hash(
            item_id=winner_item.pk,
            source_hash=evidence.source_artifact.sha256,
            kind=evidence.evidence_kind,
            schema=evidence.locator_schema_version,
            locator=evidence.locator,
            observed=evidence.observed_value,
        )
        evidence.save(update_fields=("corpus_item", "evidence_hash"))
    return {row.pk: row.evidence_hash for row in evidence_rows}


def _rehash_and_rehome_machine_output(group, evidence_hashes):
    winner_item = group["winner"].corpus_item
    item_ids = [winner_item.pk] + [profile.corpus_item_id for profile in group["losers"]]
    facts = list(ObservedFact.objects.filter(corpus_item_id__in=item_ids))
    for fact in facts:
        if fact.evidence_reference_id not in evidence_hashes:
            raise CandidateIdentityError("asset fact has no bounded origin evidence")
        fact.corpus_item = winner_item
        fact.fact_hash = asset_fact_identity_hash(
            fact_type=fact.fact_type,
            value=fact.normalized_value,
            evidence_hash=evidence_hashes[fact.evidence_reference_id],
        )
        fact.save(update_fields=("corpus_item", "fact_hash"))

    classifications = list(MachineClassification.objects.filter(
        corpus_item_id__in=item_ids))
    for classification in classifications:
        if classification.evidence_reference_id not in evidence_hashes:
            raise CandidateIdentityError(
                "asset classification has no bounded origin evidence")
        classification.corpus_item = winner_item
        classification.classification_hash = asset_classification_identity_hash(
            classification_type=classification.classification_type,
            label=classification.label,
            confidence=classification.confidence,
            explanation=classification.structured_explanation,
            evidence_hash=evidence_hashes[classification.evidence_reference_id],
        )
        classification.save(update_fields=("corpus_item", "classification_hash"))


def _merge_group(group):
    winner = group["winner"]
    winner_item = winner.corpus_item
    losers = group["losers"]
    all_item_ids = [winner_item.pk] + [profile.corpus_item_id for profile in losers]
    if DecisionEvent.objects.filter(
            subject_type="CorpusItem", subject_id__in=[str(value) for value in all_item_ids]
    ).exists():
        raise CandidateIdentityError(
            "cannot reconcile a candidate identity after signed decisions exist")
    if OperationalPermissionProjection.objects.filter(corpus_item_id__in=all_item_ids).exists():
        raise CandidateIdentityError(
            "cannot reconcile a candidate identity carrying permission projections")

    conflict = CorpusItem.objects.filter(
        item_kind=CorpusItem.Kind.DESIGN_ASSET,
        external_key=group["semantic_external_key"],
    ).exclude(pk=winner_item.pk).exists()
    if conflict:
        raise CandidateIdentityError("semantic external key is already assigned")

    evidence_hashes = _rehash_and_rehome_evidence(group)
    _rehash_and_rehome_machine_output(group, evidence_hashes)
    loser_ids = [profile.corpus_item_id for profile in losers]
    ProvenanceRecord.objects.filter(corpus_item_id__in=loser_ids).update(
        corpus_item=winner_item)
    ImportRecord.objects.filter(corpus_item_id__in=loser_ids).update(corpus_item=winner_item)

    winner.source_manifest_entry_key = group["canonical_source_key"]
    winner.save(update_fields=("source_manifest_entry_key",))
    winner_item.external_key = group["semantic_external_key"]
    winner_item.save(update_fields=("external_key", "updated_at"))

    for loser in losers:
        legacy_id = str(loser.corpus_item_id)
        source_artifact = loser.primary_source_artifact
        loser_item = loser.corpus_item
        loser.delete()
        ProvenanceRecord.objects.get_or_create(
            corpus_item=winner_item,
            source_artifact=source_artifact,
            provenance_type=IDENTITY_ALIAS_PROVENANCE,
            acquisition_reference=f"legacy-corpus-item:{legacy_id}",
            defaults={
                "source_package": C2_DATASET_ID,
                "normalized_machine_interpretation": {
                    "identity_version": ASSET_IDENTITY_VERSION,
                    "legacy_corpus_item_id": legacy_id,
                    "canonical_corpus_item_id": str(winner_item.pk),
                    "candidate_key": group["candidate_key"],
                    "browser_redirect_only": True,
                    "authority_inferred": False,
                },
            },
        )
        loser_item.delete()


def reconcile_asset_identity(manifest_path, *, apply=False):
    prepared = prepare_manifest(manifest_path)
    groups = _build_plan(prepared)
    if not apply:
        return _result(prepared, groups, mode="dry-run")

    with transaction.atomic():
        before_profiles = DesignAssetProfile.objects.filter(
            dataset_identifier=C2_DATASET_ID).count()
        before_decisions = DecisionEvent.objects.count()
        before_allowed = OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count()
        if before_allowed:
            raise CandidateIdentityError(
                "identity reconciliation requires zero ALLOWED permission projections")

        groups = _build_plan(prepared)
        normalized_external_keys = sum(
            group["winner"].corpus_item.external_key != group["semantic_external_key"]
            for group in groups
        )
        changes_required = any(
            group["losers"]
            or group["winner"].corpus_item.external_key != group["semantic_external_key"]
            or group["winner"].source_manifest_entry_key
            != group["canonical_source_key"]
            for group in groups
        )
        batch = None
        if changes_required:
            batch = ImportBatch.objects.create(
                importer_identifier=RECONCILER_IDENTIFIER,
                importer_version=IMPORTER_VERSION,
                configuration_hash=canonical_hash({
                    "identity_version": ASSET_IDENTITY_VERSION,
                    "mode": "bounded_case_a_reconciliation",
                }),
                source_manifest_hash=prepared.manifest_hash,
                scope={
                    "dataset_id": C2_DATASET_ID,
                    "frozen_candidate_records": prepared.actual_counts[
                        "asset_candidates"],
                    "semantic_candidates": prepared.actual_counts[
                        "semantic_asset_candidates"],
                    "physical_source_artifacts": prepared.actual_counts[
                        "c2_content_identities"],
                },
            )
            for group in groups:
                _merge_group(group)
            duplicate = next(group for group in groups if len(group["origins"]) > 1)
            record_import_attempt(
                import_batch=batch,
                stable_source_record_key=(
                    f"asset-identity:{C2_DATASET_ID}:{duplicate['candidate_key']}"),
                source_record_hash=canonical_hash({
                    "candidate_key": duplicate["candidate_key"],
                    "origins": duplicate["origins"],
                    "identity_version": ASSET_IDENTITY_VERSION,
                }),
                parser_version=IMPORTER_VERSION,
                source_schema_version=ASSET_IDENTITY_VERSION,
                disposition="CREATED",
                source_artifact=duplicate["winner"].primary_source_artifact,
                corpus_item=duplicate["winner"].corpus_item,
                reconciliation_details={
                    "case": "ONE_SEMANTIC_CANDIDATE_TWO_ORIGIN_RECORDS",
                    "origin_count": len(duplicate["origins"]),
                    "legacy_subjects_merged": len(duplicate["losers"]),
                    "decision_events_created": 0,
                    "allowed_permissions_created": 0,
                },
            )
            batch = finalize_import_batch(batch, status=ImportBatch.Status.COMPLETED,
                                          counts={
                                              "total_records": 1,
                                              "imported_records": 1,
                                              "unchanged_records": 0,
                                              "changed_records": 0,
                                              "skipped_records": 0,
                                              "quarantined_records": 0,
                                              "failed_records": 0,
                                          })
        after_decisions = DecisionEvent.objects.count()
        after_allowed = OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count()
        if (after_decisions != before_decisions or after_allowed != before_allowed):
            raise CandidateIdentityError("identity reconciliation changed authority state")
        result = _result(
            prepared, groups, mode="apply", batch=batch,
            before_profiles=before_profiles,
            normalized_external_keys=normalized_external_keys,
        )
        result.update({
            "decision_events_before": before_decisions,
            "decision_events_after": after_decisions,
            "allowed_before": before_allowed,
            "allowed_after": after_allowed,
        })
        return result
