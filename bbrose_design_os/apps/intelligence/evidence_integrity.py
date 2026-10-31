"""General, read-only evidence-integrity evaluation and bounded reconciliation.

Content identity, not a pathname, is the root of trust.  The resolver joins immutable
import provenance to frozen manifest declarations and a versioned integrity-policy
registry.  It never imports, repairs, approves, or writes any record.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import DecisionEvent

from .locator_schemas import normalize_relative_path
from .manifest import SHA256_RE, canonical_hash
from .models import (
    BrandCandidateProfile, CorpusItem, EvidenceReference, HumanAssertionProjection,
    ImportBatch, ImportRecord, IntelligenceProjectionGeneration, MachineClassification,
    ObservedFact, OperationalPermissionProjection, ProjectionPublicationState,
    ReviewCandidate, SourceArtifact, SourceLocationObservation,
)

REGISTRY_SCHEMA = "dip1b_evidence_integrity_registry/1.0"
REGISTRY_ID = "dip1b_evidence_integrity_registry/1.0"
CORRECTION_ID = "dip1b_data_corr_1_brand_candidate_source_hash/1.0"
DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "docs/design_intelligence/dip1/dip1b_mvp_manifest_1_0.json"
)
DEFAULT_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "docs/design_intelligence/dip1/dip1b_evidence_integrity_registry_1_0.json"
)

VERIFIED = "VERIFIED"
HASH_MISMATCH = "HASH_MISMATCH"
STALE_GENERATED_OUTPUT = "STALE_GENERATED_OUTPUT"
UNVERIFIED_SOURCE_VERSION = "UNVERIFIED_SOURCE_VERSION"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

STALE_IGNORED_OUTPUT = "STALE_IGNORED_OUTPUT"
UNRESOLVED = "UNRESOLVED"


class EvidenceIntegrityConfigurationError(RuntimeError):
    """A versioned integrity declaration cannot be evaluated safely."""


@dataclasses.dataclass(frozen=True)
class SourceVersionEvaluation:
    version_id: str
    source_role: str
    dataset_id: str
    stable_source_keys: tuple[str, ...]
    status: str
    reason_codes: tuple[str, ...]
    expected_sha256: str
    observed_sha256: str | None
    byte_size: int | None
    source_artifact_ids: tuple[str, ...]
    manifest_id: str | None
    manifest_schema_version: str | None
    parser_identities: tuple[str, ...]
    locator: dict

    @property
    def locator_label(self) -> str:
        root = self.locator.get("root")
        path = self.locator.get("path")
        if root and path:
            return f"{root}-relative:{path}"
        return self.source_role


@dataclasses.dataclass(frozen=True)
class EvidenceIntegrityResult:
    status: str
    reason_codes: tuple[str, ...]
    classification: str
    affected_source_artifact_ids: tuple[str, ...]
    expected_hashes: tuple[str, ...]
    observed_hashes: tuple[str, ...]
    verified_source_versions: tuple[SourceVersionEvaluation, ...]
    unresolved_source_versions: tuple[SourceVersionEvaluation, ...]
    evaluation_timestamp: str
    grants_authority: bool = False

    @property
    def blocks_evidence_dependent_claims(self) -> bool:
        return self.status != VERIFIED

    @property
    def reason_code(self) -> str:
        return self.reason_codes[0] if self.reason_codes else "SOURCE_VERSION_VERIFIED"

    @property
    def state(self) -> str:
        return self.status

    @property
    def warning_message(self) -> str:
        if not self.blocks_evidence_dependent_claims:
            return ""
        return (
            "REVIEW REQUIRED: one or more evidence source versions are unresolved. "
            "Path equality is non-authoritative; machine classifications do not cure "
            "the mismatch, and operational permissions remain denied."
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp(value=None) -> str:
    value = value or timezone.now()
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.isoformat()
    return value.isoformat()


def _read_document(path: Path, label: str) -> tuple[dict, str]:
    try:
        raw = Path(path).read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceIntegrityConfigurationError(f"{label} is unavailable or invalid") from exc
    if not isinstance(document, dict):
        raise EvidenceIntegrityConfigurationError(f"{label} must be an object")
    return document, hashlib.sha256(raw).hexdigest()


def _load_registry(path: Path) -> tuple[dict, str]:
    document, raw_hash = _read_document(path, "integrity registry")
    if (document.get("schema_version") != REGISTRY_SCHEMA
            or document.get("registry_id") != REGISTRY_ID
            or not isinstance(document.get("policies"), list)):
        raise EvidenceIntegrityConfigurationError("integrity registry identity is invalid")
    correction_ids = set()
    for policy in document["policies"]:
        if (not isinstance(policy, dict)
                or policy.get("classification") not in {STALE_IGNORED_OUTPUT, UNRESOLVED}
                or policy.get("authority_effect") != "NONE"
                or not isinstance(policy.get("manifest_selector"), dict)
                or not isinstance(policy.get("root_of_trust"), dict)
                or not isinstance(policy.get("recognized_non_authoritative_versions"), list)):
            raise EvidenceIntegrityConfigurationError("integrity policy is invalid")
        selector = policy["manifest_selector"]
        root = policy["root_of_trust"]
        required_selector = {
            "manifest_id", "manifest_schema_version", "dataset_id", "record_type",
            "source_role", "expected_sha256",
        }
        correction_id = policy.get("correction_id")
        if (not isinstance(correction_id, str) or correction_id in correction_ids
                or set(selector) != required_selector
                or any(not isinstance(selector[key], str) or not selector[key]
                       for key in required_selector)
                or not SHA256_RE.fullmatch(selector["expected_sha256"])
                or any(not isinstance(root.get(key), str)
                       or not SHA256_RE.fullmatch(root[key]) for key in (
                           "current_frozen_manifest_sha256",
                           "accepted_import_manifest_sha256", "configuration_sha256"))):
            raise EvidenceIntegrityConfigurationError("integrity policy identity is invalid")
        recognized = policy["recognized_non_authoritative_versions"]
        hashes = [row.get("sha256") for row in recognized if isinstance(row, dict)]
        if (len(hashes) != len(recognized) or len(hashes) != len(set(hashes))
                or any(not isinstance(value, str) or not SHA256_RE.fullmatch(value)
                       for value in hashes)
                or any(not isinstance(row.get("byte_size"), int)
                       or row["byte_size"] < 0 for row in recognized)):
            raise EvidenceIntegrityConfigurationError(
                "recognized non-authoritative versions are invalid")
        correction_ids.add(correction_id)
    return document, raw_hash


def _record_matches_stable_key(record_key: str, stable_key: str) -> bool:
    """Match a manifest stable key without interpreting a domain-specific filename."""
    return (record_key == stable_key
            or record_key.endswith(f":{stable_key}")
            or f":{stable_key}:" in record_key)


def _configured_source(source: dict) -> Path:
    root_name = source.get("root")
    roots = getattr(settings, "INTELLIGENCE_SOURCE_ROOTS", {})
    if not isinstance(root_name, str) or root_name not in roots:
        raise EvidenceIntegrityConfigurationError("declared source root is not configured")
    try:
        relative = normalize_relative_path(source.get("path"))
    except (TypeError, ValidationError) as exc:
        raise EvidenceIntegrityConfigurationError("declared source path is invalid") from exc
    root = Path(roots[root_name]).resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise EvidenceIntegrityConfigurationError("declared source path escapes its root") from exc
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        path = resolve_material_file(path, repo_root=root)   # mapping only: the caller compares the declared hash
    except MaterialPathError as exc:
        raise EvidenceIntegrityConfigurationError('material migration invalid') from exc
    return path


class EvidenceIntegrityResolver:
    """Evaluate any corpus item against versioned manifest content identities."""

    def __init__(self, *, manifest_path=DEFAULT_MANIFEST, registry_path=DEFAULT_REGISTRY,
                 evaluated_at=None):
        self.manifest_path = Path(manifest_path)
        self.registry_path = Path(registry_path)
        self.evaluation_timestamp = _timestamp(evaluated_at)
        self._observations: dict[tuple[str, str], tuple[str | None, int | None]] = {}
        self.manifest_error = None
        self.registry_error = None
        try:
            self.manifest, self.manifest_sha256 = _read_document(
                self.manifest_path, "frozen manifest")
            if (not isinstance(self.manifest.get("entries"), list)
                    or not isinstance(self.manifest.get("manifest_id"), str)
                    or not isinstance(self.manifest.get("schema_version"), str)):
                raise EvidenceIntegrityConfigurationError("frozen manifest schema is invalid")
        except EvidenceIntegrityConfigurationError as exc:
            self.manifest, self.manifest_sha256 = {}, None
            self.manifest_error = str(exc)
        try:
            self.registry, self.registry_sha256 = _load_registry(self.registry_path)
        except EvidenceIntegrityConfigurationError as exc:
            self.registry, self.registry_sha256 = {}, None
            self.registry_error = str(exc)

    @property
    def policies(self) -> tuple[dict, ...]:
        return tuple(self.registry.get("policies") or ())

    def policy(self, correction_id: str) -> dict:
        rows = [row for row in self.policies if row.get("correction_id") == correction_id]
        if len(rows) != 1:
            raise EvidenceIntegrityConfigurationError(
                f"expected one integrity policy for {correction_id}")
        return rows[0]

    def _matching_entries(self, policy: dict) -> tuple[dict, ...]:
        selector = policy["manifest_selector"]
        if (self.manifest.get("manifest_id") != selector.get("manifest_id")
                or self.manifest.get("schema_version")
                != selector.get("manifest_schema_version")):
            return ()
        return tuple(entry for entry in self.manifest.get("entries", ()) if (
            entry.get("dataset_id") == selector.get("dataset_id")
            and entry.get("record_type") == selector.get("record_type")
            and isinstance(entry.get("data_source"), dict)
            and (entry.get("data_source") or {}).get("source", {}).get("sha256")
            == selector.get("expected_sha256")
        ))

    def _observe(self, source: dict) -> tuple[str | None, int | None]:
        key = (str(source.get("root")), str(source.get("path")))
        if key in self._observations:
            return self._observations[key]
        try:
            path = _configured_source(source)
            result = (_sha256(path), path.stat().st_size) if path.is_file() else (None, None)
        except (OSError, EvidenceIntegrityConfigurationError):
            result = (None, None)
        self._observations[key] = result
        return result

    def _declaration_version(self, policy: dict, entries: tuple[dict, ...],
                             source_artifact_ids=()) -> SourceVersionEvaluation:
        selector = policy["manifest_selector"]
        expected = selector["expected_sha256"]
        if not entries:
            return SourceVersionEvaluation(
                version_id=canonical_hash({"selector": selector, "unresolved": True}),
                source_role=selector["source_role"], dataset_id=selector["dataset_id"],
                stable_source_keys=(), status=UNVERIFIED_SOURCE_VERSION,
                reason_codes=("FROZEN_EVIDENCE_DECLARATION_UNRESOLVED",),
                expected_sha256=expected, observed_sha256=None, byte_size=None,
                source_artifact_ids=tuple(sorted(str(v) for v in source_artifact_ids)),
                manifest_id=selector.get("manifest_id"),
                manifest_schema_version=selector.get("manifest_schema_version"),
                parser_identities=(), locator={"source_role": selector["source_role"]},
            )
        sources = {(entry["data_source"]["source"]["root"],
                    entry["data_source"]["source"]["path"],
                    entry["data_source"]["source"]["sha256"])
                   for entry in entries}
        if len(sources) != 1:
            return SourceVersionEvaluation(
                version_id=canonical_hash({"selector": selector, "ambiguous": sorted(sources)}),
                source_role=selector["source_role"], dataset_id=selector["dataset_id"],
                stable_source_keys=tuple(sorted(entry["stable_source_key"] for entry in entries)),
                status=UNVERIFIED_SOURCE_VERSION,
                reason_codes=("FROZEN_EVIDENCE_DECLARATION_AMBIGUOUS",),
                expected_sha256=expected, observed_sha256=None, byte_size=None,
                source_artifact_ids=tuple(sorted(str(v) for v in source_artifact_ids)),
                manifest_id=self.manifest.get("manifest_id"),
                manifest_schema_version=self.manifest.get("schema_version"),
                parser_identities=(), locator={"source_role": selector["source_role"]},
            )
        root, relative, declared_hash = next(iter(sources))
        observed, byte_size = self._observe({"root": root, "path": relative})
        recognized = {
            row.get("sha256"): row
            for row in policy["recognized_non_authoritative_versions"]
            if isinstance(row, dict)
        }
        manifest_expected = policy["root_of_trust"].get("current_frozen_manifest_sha256")
        manifest_verified = self.manifest_sha256 == manifest_expected
        if not manifest_verified:
            status = UNVERIFIED_SOURCE_VERSION
            reasons = ("FROZEN_MANIFEST_VERSION_UNVERIFIED",)
        elif observed is None:
            status = UNVERIFIED_SOURCE_VERSION
            reasons = ("FROZEN_SOURCE_VERSION_UNAVAILABLE",)
        elif observed == declared_hash:
            status = VERIFIED
            reasons = ("FROZEN_SOURCE_HASH_VERIFIED",)
        elif observed in recognized and recognized[observed].get("byte_size") == byte_size:
            status = STALE_GENERATED_OUTPUT
            reasons = (
                "DECLARED_HASH_MISMATCH",
                "KNOWN_NON_AUTHORITATIVE_GENERATED_VERSION",
                "PATH_IDENTITY_NON_AUTHORITATIVE",
            )
        else:
            status = HASH_MISMATCH
            reasons = ("DECLARED_HASH_MISMATCH", "SOURCE_VERSION_UNRESOLVED")
        parser_ids = tuple(sorted({
            f"{entry.get('parser_identifier')}/{entry.get('parser_version')}"
            for entry in entries
        }))
        identity = {
            "manifest_id": self.manifest.get("manifest_id"),
            "dataset_id": selector["dataset_id"], "source_role": selector["source_role"],
            "expected_sha256": expected,
        }
        return SourceVersionEvaluation(
            version_id=canonical_hash(identity), source_role=selector["source_role"],
            dataset_id=selector["dataset_id"],
            stable_source_keys=tuple(sorted(entry["stable_source_key"] for entry in entries)),
            status=status, reason_codes=reasons, expected_sha256=expected,
            observed_sha256=observed, byte_size=byte_size,
            source_artifact_ids=tuple(sorted(str(v) for v in source_artifact_ids)),
            manifest_id=self.manifest.get("manifest_id"),
            manifest_schema_version=self.manifest.get("schema_version"),
            parser_identities=parser_ids, locator={"root": root, "path": relative},
        )

    def inspect_policy(self, correction_id: str) -> EvidenceIntegrityResult:
        try:
            policy = self.policy(correction_id)
            versions = (self._declaration_version(policy, self._matching_entries(policy)),)
        except EvidenceIntegrityConfigurationError:
            versions = ()
        return self._result((), versions, configuration_unresolved=not versions)

    def evaluate(self, corpus_item, evidence_refs=None) -> EvidenceIntegrityResult:
        if not isinstance(corpus_item, CorpusItem):
            raise TypeError("corpus_item must be a persisted CorpusItem")
        records = list(ImportRecord.objects.select_related(
            "import_batch", "source_artifact").filter(corpus_item=corpus_item))
        if evidence_refs is None:
            references = list(EvidenceReference.objects.select_related(
                "source_artifact").filter(corpus_item=corpus_item, is_test_only=False))
            invalid_reference_scope = False
        else:
            references = list(evidence_refs)
            invalid_reference_scope = any(
                row.corpus_item_id != corpus_item.pk or row.is_test_only for row in references)
        selected_artifact_ids = ({row.source_artifact_id for row in references}
                                 if evidence_refs is not None else None)

        verified = []
        for row in sorted(references, key=lambda value: str(value.pk)):
            artifact = row.source_artifact
            verified.append(SourceVersionEvaluation(
                version_id=f"source-artifact:{artifact.pk}:{artifact.sha256}",
                source_role="EVIDENCE_REFERENCE", dataset_id="",
                stable_source_keys=(), status=VERIFIED,
                reason_codes=("PERSISTED_CONTENT_IDENTITY_VERIFIED",),
                expected_sha256=artifact.sha256, observed_sha256=artifact.sha256,
                byte_size=artifact.byte_size,
                source_artifact_ids=(str(artifact.pk),), manifest_id=None,
                manifest_schema_version=None,
                parser_identities=(f"{artifact.parser_identifier}/{artifact.parser_version}",),
                locator={"evidence_reference_id": str(row.pk)},
            ))

        unresolved = []
        for policy in self.policies:
            selector = policy["manifest_selector"]
            policy_records = [row for row in records
                              if row.reconciliation_details.get("dataset_id")
                              == selector.get("dataset_id")]
            if selected_artifact_ids is not None:
                policy_records = [row for row in policy_records
                                  if row.source_artifact_id in selected_artifact_ids]
            if not policy_records:
                continue
            entries = self._matching_entries(policy)
            linked_entries = tuple(entry for entry in entries if any(
                _record_matches_stable_key(row.stable_source_record_key,
                                           entry.get("stable_source_key", ""))
                for row in policy_records))
            artifact_ids = {row.source_artifact_id for row in policy_records
                            if row.source_artifact_id and any(
                                _record_matches_stable_key(
                                    row.stable_source_record_key,
                                    entry.get("stable_source_key", ""))
                                for entry in linked_entries)}
            version = self._declaration_version(policy, linked_entries, artifact_ids)
            (verified if version.status == VERIFIED else unresolved).append(version)

        relevant_records = (records if selected_artifact_ids is None else [
            row for row in records if row.source_artifact_id in selected_artifact_ids])
        configuration_unresolved = bool(
            relevant_records and (self.manifest_error or self.registry_error))
        return self._result(
            tuple(verified), tuple(unresolved),
            configuration_unresolved=configuration_unresolved or invalid_reference_scope,
            extra_reason=("EVIDENCE_REFERENCE_SCOPE_INVALID"
                          if invalid_reference_scope else None),
        )

    def _result(self, verified, unresolved, *, configuration_unresolved=False,
                extra_reason=None):
        unresolved = list(unresolved)
        reasons = {code for version in unresolved for code in version.reason_codes}
        if configuration_unresolved:
            reasons.add(extra_reason or "EVIDENCE_INTEGRITY_CONFIGURATION_UNRESOLVED")
        blocked = bool(unresolved or configuration_unresolved)
        if not blocked:
            classification = VERIFIED
        elif (unresolved and not configuration_unresolved
              and all(row.status == STALE_GENERATED_OUTPUT for row in unresolved)):
            classification = STALE_IGNORED_OUTPUT
        else:
            classification = UNRESOLVED
        versions = tuple(verified) + tuple(unresolved)
        return EvidenceIntegrityResult(
            status=REVIEW_REQUIRED if blocked else VERIFIED,
            reason_codes=tuple(sorted(reasons)), classification=classification,
            affected_source_artifact_ids=tuple(sorted({artifact_id
                for version in unresolved for artifact_id in version.source_artifact_ids})),
            expected_hashes=tuple(sorted({row.expected_sha256 for row in versions})),
            observed_hashes=tuple(sorted({row.observed_sha256 for row in versions
                                          if row.observed_sha256})),
            verified_source_versions=tuple(verified),
            unresolved_source_versions=tuple(unresolved),
            evaluation_timestamp=self.evaluation_timestamp, grants_authority=False,
        )


def evaluate_evidence_integrity(corpus_item, evidence_refs=None, **resolver_options):
    """Public, general, write-free integrity gate used by UI and signed assertions."""
    return EvidenceIntegrityResolver(**resolver_options).evaluate(corpus_item, evidence_refs)


def _database_counts() -> dict:
    return {
        "source_artifacts": SourceArtifact.objects.count(),
        "source_location_observations": SourceLocationObservation.objects.count(),
        "import_batches": ImportBatch.objects.count(),
        "import_records": ImportRecord.objects.count(),
        "corpus_items": CorpusItem.objects.count(),
        "evidence_references": EvidenceReference.objects.count(),
        "observed_facts": ObservedFact.objects.count(),
        "machine_classifications": MachineClassification.objects.count(),
        "brand_candidate_profiles": BrandCandidateProfile.objects.count(),
        "review_candidates": ReviewCandidate.objects.count(),
        "decision_events": DecisionEvent.objects.count(),
        "human_assertion_projections": HumanAssertionProjection.objects.count(),
        "projection_generations": IntelligenceProjectionGeneration.objects.count(),
        "allowed_permissions": OperationalPermissionProjection.objects.filter(
            effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
    }


def _publication_snapshot() -> list[dict]:
    rows = list(ProjectionPublicationState.objects.order_by("pk").values(
        "id", "current_generation_id", "published_chain_head_hash",
        "published_terminal_sequence", "projector_identifier", "projector_version",
        "projection_schema_version", "published_at"))
    for row in rows:
        row["current_generation_id"] = str(row["current_generation_id"])
        row["published_at"] = row["published_at"].isoformat()
    return rows


def _dependency_trace(item: CorpusItem, integrity: EvidenceIntegrityResult,
                      supporting_imports=()) -> dict:
    item_imports = list(ImportRecord.objects.select_related(
        "import_batch", "source_artifact").filter(corpus_item=item).order_by(
            "stable_source_record_key", "created_at", "pk"))
    imports = sorted(
        item_imports + list(supporting_imports),
        key=lambda row: (row.stable_source_record_key, row.created_at, str(row.pk)),
    )
    evidence = list(EvidenceReference.objects.select_related("source_artifact").filter(
        corpus_item=item).order_by("pk"))
    facts = list(ObservedFact.objects.select_related(
        "source_artifact", "evidence_reference").filter(corpus_item=item).order_by("pk"))
    machines = list(MachineClassification.objects.select_related(
        "source_artifact", "evidence_reference").filter(corpus_item=item).order_by("pk"))
    artifact_ids = {row.source_artifact_id for row in imports if row.source_artifact_id}
    artifact_ids.update(row.source_artifact_id for row in evidence)
    artifact_ids.update(row.source_artifact_id for row in facts)
    artifact_ids.update(row.source_artifact_id for row in machines)
    profile = BrandCandidateProfile.objects.filter(corpus_item=item).first()
    if profile:
        artifact_ids.add(profile.primary_source_artifact_id)
    artifacts = SourceArtifact.objects.filter(pk__in=artifact_ids).order_by("sha256", "pk")
    locations = SourceLocationObservation.objects.filter(
        source_artifact_id__in=artifact_ids).order_by("source_artifact_id", "pk")
    reviews = ReviewCandidate.objects.filter(corpus_item=item).order_by("pk")
    decisions = DecisionEvent.objects.filter(
        subject_type="CorpusItem", subject_id=str(item.pk)).order_by(
            "sequence_number", "event_id")
    projections = HumanAssertionProjection.objects.filter(corpus_item=item).order_by(
        "projection_generation_id", "assertion_domain", "pk")
    batches = ImportBatch.objects.filter(
        pk__in={row.import_batch_id for row in imports}).order_by("started_at", "pk")
    return {
        "stable_identifier": item.external_key,
        "corpus_item_id": str(item.pk),
        "browser_visible": item.lifecycle_state == CorpusItem.Lifecycle.ACTIVE,
        "integrity": dataclasses.asdict(integrity),
        "source_artifacts": [{
            "id": str(row.pk), "stored_source_hash": row.sha256,
            "source_identifier": row.source_identifier,
            "parser_identity": f"{row.parser_identifier}/{row.parser_version}",
            "source_schema_version": row.source_schema_version,
        } for row in artifacts],
        "source_location_observations": [{
            "id": str(row.pk), "source_artifact_id": str(row.source_artifact_id),
            "observed_location": row.observed_location,
            "observed_by_import_record_id": (
                str(row.observed_by_import_record_id)
                if row.observed_by_import_record_id else None),
            "availability_state": row.availability_state,
        } for row in locations],
        "import_batches": [{
            "id": str(row.pk), "importer_identity": (
                f"{row.importer_identifier}/{row.importer_version}"),
            "configuration_hash": row.configuration_hash,
            "source_manifest_hash": row.source_manifest_hash,
        } for row in batches],
        "import_records": [{
            "id": str(row.pk), "stable_identifier": row.stable_source_record_key,
            "imported_record_hash": row.source_record_hash,
            "stored_source_hash": row.source_artifact.sha256 if row.source_artifact else None,
            "source_artifact_id": (str(row.source_artifact_id)
                                   if row.source_artifact_id else None),
            "import_batch_id": str(row.import_batch_id),
            "dataset_id": row.reconciliation_details.get("dataset_id"),
            "disposition": row.disposition,
        } for row in imports],
        "evidence_references": [{
            "id": str(row.pk), "evidence_hash": row.evidence_hash,
            "stored_source_hash": row.source_artifact.sha256,
            "source_artifact_id": str(row.source_artifact_id),
            "locator_schema_version": row.locator_schema_version,
            "evidence_locator": row.locator,
        } for row in evidence],
        "observed_facts": [{
            "id": str(row.pk), "stable_identifier": row.fact_type,
            "fact_hash": row.fact_hash, "stored_source_hash": row.source_artifact.sha256,
            "evidence_reference_id": (str(row.evidence_reference_id)
                                      if row.evidence_reference_id else None),
        } for row in facts],
        "machine_classifications": [{
            "id": str(row.pk), "stable_identifier": row.classification_type,
            "classification_hash": row.classification_hash,
            "stored_source_hash": row.source_artifact.sha256,
            "evidence_reference_id": (str(row.evidence_reference_id)
                                      if row.evidence_reference_id else None),
            "authoritative": False,
        } for row in machines],
        "brand_candidate_profile": ({
            "stable_identifier": item.external_key,
            "primary_source_artifact_id": str(profile.primary_source_artifact_id),
            "stored_source_hash": profile.primary_source_artifact.sha256,
            "candidate_status": profile.candidate_status,
            "warning_state": profile.warning_state,
        } if profile else None),
        "review_manifest_memberships": [{
            "review_candidate_id": str(row.pk),
            "review_manifest_id": row.review_manifest_id,
            "source_import_batch_id": (str(row.source_import_batch_id)
                                       if row.source_import_batch_id else None),
            "workflow_status": row.workflow_status,
        } for row in reviews],
        "signed_assertion_references": [{
            "event_id": str(row.event_id), "action": row.action,
            "content_hash": row.content_hash,
            "evidence_reference_ids": row.payload.get(
                "evidence_reference_ids", row.payload.get("evidence_references", [])),
        } for row in decisions],
        "human_assertion_projection_references": [{
            "id": str(row.pk), "projection_generation_id": str(
                row.projection_generation_id),
            "assertion_domain": row.assertion_domain,
            "effective_state": row.effective_state,
            "source_decision_event_id": (str(row.source_decision_event_id)
                                         if row.source_decision_event_id else None),
        } for row in projections],
    }


def reconcile_brand_candidate_integrity() -> dict:
    """Read-only, correction-scoped dependency report built on the general resolver."""
    registry_document, _ = _load_registry(DEFAULT_REGISTRY)
    resolver = EvidenceIntegrityResolver(evaluated_at=registry_document["evaluated_at"])
    policy = resolver.policy(CORRECTION_ID)
    selector = policy["manifest_selector"]
    entries = resolver._matching_entries(policy)
    stable_keys = tuple(sorted(entry["stable_source_key"] for entry in entries))
    before = _database_counts()
    publication_before = _publication_snapshot()

    dataset_records = list(ImportRecord.objects.select_related(
        "import_batch", "source_artifact", "corpus_item").filter(
            reconciliation_details__dataset_id=selector["dataset_id"]).order_by(
                "stable_source_record_key", "created_at", "pk"))
    domain_records = [row for row in dataset_records if row.corpus_item_id and any(
        _record_matches_stable_key(row.stable_source_record_key, key) for key in stable_keys)]
    source_declaration_records = [row for row in dataset_records
                                  if not row.corpus_item_id and any(
                                      row.stable_source_record_key == f"source:{key}"
                                      for key in stable_keys)]
    latest = {}
    for row in domain_records:
        latest[row.stable_source_record_key] = row
    items = list(CorpusItem.objects.filter(
        pk__in={row.corpus_item_id for row in domain_records}).order_by("external_key", "pk"))
    evaluations = {item.pk: resolver.evaluate(item) for item in items}
    affected = [item for item in items
                if evaluations[item.pk].blocks_evidence_dependent_claims]

    current_record_hashes = {}
    declaration = resolver._declaration_version(policy, entries)
    if declaration.observed_sha256 and entries:
        try:
            source_path = _configured_source(entries[0]["data_source"]["source"])
            rows = json.loads(source_path.read_text(encoding="utf-8"))
            for entry in entries:
                segments = entry["data_source"]["locator"]["value"]["segments"]
                value = rows
                for segment in segments:
                    value = value[segment]
                current_record_hashes[entry["stable_source_key"]] = canonical_hash(value)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError,
                IndexError, TypeError, EvidenceIntegrityConfigurationError):
            current_record_hashes = {}
    latest_matching_current = sum(
        row.source_record_hash == current_record_hashes.get(key)
        for record_key, row in latest.items() for key in stable_keys
        if _record_matches_stable_key(record_key, key))
    accepted_manifest_hash = policy["root_of_trust"]["accepted_import_manifest_sha256"]
    accepted_records = [row for row in domain_records
                        if row.import_batch.source_manifest_hash == accepted_manifest_hash]
    expected_hash = selector["expected_sha256"]
    observed_hash = declaration.observed_sha256
    affected_ids = {item.pk for item in affected}
    affected_subjects = [str(value) for value in affected_ids]
    dependency_trace = []
    for item in affected:
        item_records = [row for row in domain_records if row.corpus_item_id == item.pk]
        item_keys = {key for key in stable_keys if any(
            _record_matches_stable_key(row.stable_source_record_key, key)
            for row in item_records)}
        supporting = [row for row in source_declaration_records
                      if row.stable_source_record_key.removeprefix("source:") in item_keys]
        dependency_trace.append(
            _dependency_trace(item, evaluations[item.pk], supporting))
    publication_after = _publication_snapshot()
    after = _database_counts()
    report = {
        "correction_id": CORRECTION_ID,
        "mode": "read-only-reconciliation",
        "classification": declaration.status == STALE_GENERATED_OUTPUT
        and STALE_IGNORED_OUTPUT or UNRESOLVED,
        "integrity": dataclasses.asdict(resolver.inspect_policy(CORRECTION_ID)),
        "root_of_trust": {
            "manifest_id": resolver.manifest.get("manifest_id"),
            "manifest_schema_version": resolver.manifest.get("schema_version"),
            "current_manifest_sha256": resolver.manifest_sha256,
            "expected_source_sha256": expected_hash,
            "observed_source_sha256": observed_hash,
            "observed_source_byte_size": declaration.byte_size,
            **policy["root_of_trust"],
            "expected_bytes_recovered": False,
            "expected_hash_reproduced_from_preserved_import_provenance": True,
        },
        "database": {
            "linked_import_record_versions": (
                len(source_declaration_records) + len(domain_records)),
            "source_declaration_record_versions": len(source_declaration_records),
            "candidate_record_versions": len(domain_records),
            "latest_candidate_records": len(latest),
            "affected_candidate_items": len(affected_ids),
            "affected_review_candidates": ReviewCandidate.objects.filter(
                corpus_item_id__in=affected_ids).count(),
            "accepted_source_version_batches": len({row.import_batch_id
                                                     for row in accepted_records}),
            "accepted_candidate_records": len(accepted_records),
            "accepted_source_declaration_records": sum(
                row.import_batch.source_manifest_hash == accepted_manifest_hash
                for row in source_declaration_records),
            "latest_records_matching_current_output": latest_matching_current,
            "expected_json_source_artifacts": SourceArtifact.objects.filter(
                sha256=expected_hash).count(),
            "observed_json_source_artifacts": SourceArtifact.objects.filter(
                sha256=observed_hash).count() if observed_hash else 0,
            "physical_source_artifacts": len({row.source_artifact_id
                                              for row in domain_records
                                              if row.source_artifact_id}),
        },
        "authority": {
            "affected_decision_events": DecisionEvent.objects.filter(
                subject_type="CorpusItem", subject_id__in=affected_subjects).count(),
            "affected_human_assertion_projections": HumanAssertionProjection.objects.filter(
                corpus_item_id__in=affected_ids).count(),
            "affected_allowed_permissions": OperationalPermissionProjection.objects.filter(
                corpus_item_id__in=affected_ids,
                effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
            "global_decision_events": DecisionEvent.objects.count(),
            "global_human_assertion_projections": HumanAssertionProjection.objects.count(),
            "global_allowed_permissions": OperationalPermissionProjection.objects.filter(
                effective_state=OperationalPermissionProjection.State.ALLOWED).count(),
        },
        "dependencies": dependency_trace,
        "projection_publication_before": publication_before,
        "projection_publication_after": publication_after,
        "counts_before": before,
        "counts_after": after,
        "database_changed": before != after or publication_before != publication_after,
    }
    report["reconciliation_hash"] = canonical_hash(report)
    return report
