import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...brand_evidence import (
    ACCEPTED_IMPORT_MANIFEST_SHA256,
    DATASET_ID,
    DEFAULT_DATASET_PATH,
    DEFAULT_MANIFEST_PATH,
    ORIGIN_DATASET_ID,
    BrandEvidenceError,
    build_default_bundle,
)
from ...models import ImportRecord


def _preserved_import_records():
    rows = ImportRecord.objects.filter(
        import_batch__source_manifest_hash=ACCEPTED_IMPORT_MANIFEST_SHA256,
        reconciliation_details__dataset_id=ORIGIN_DATASET_ID,
        stable_source_record_key__startswith="brand-candidate:",
        corpus_item__isnull=False,
    ).order_by("stable_source_record_key")
    return [{
        "stable_source_key": row.stable_source_record_key.removeprefix(
            "brand-candidate:"),
        "dataset_id": row.reconciliation_details.get("dataset_id"),
        "source_record_hash": row.source_record_hash,
    } for row in rows]


class Command(BaseCommand):
    help = "Build or verify the deterministic DIP-1B brand-evidence successor."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--write", action="store_true",
            help="Write the canonical dataset and binding manifest; default is dry-run.")

    def handle(self, *args, **options):
        try:
            bundle = build_default_bundle(_preserved_import_records())
        except BrandEvidenceError as exc:
            raise CommandError(str(exc)) from exc
        dataset_path = Path(DEFAULT_DATASET_PATH)
        manifest_path = Path(DEFAULT_MANIFEST_PATH)
        report = {
            "mode": "write" if options["write"] else "dry-run",
            "dataset_id": DATASET_ID,
            "dataset_path": str(dataset_path),
            "dataset_sha256": bundle.dataset_sha256,
            "dataset_byte_size": len(bundle.dataset_bytes),
            "manifest_path": str(manifest_path),
            "manifest_sha256": bundle.manifest_sha256,
            "record_count": bundle.dataset_document["record_count"],
            "source_input_count": bundle.manifest_document["source_input_count"],
            "physical_content_identity_count": bundle.manifest_document[
                "physical_content_identity_count"],
            "dataset_matches_existing": (
                dataset_path.is_file() and dataset_path.read_bytes() == bundle.dataset_bytes),
            "manifest_matches_existing": (
                manifest_path.is_file() and manifest_path.read_bytes() == bundle.manifest_bytes),
        }
        if options["write"]:
            dataset_path.parent.mkdir(parents=True, exist_ok=True)
            dataset_path.write_bytes(bundle.dataset_bytes)
            manifest_path.write_bytes(bundle.manifest_bytes)
            report["written"] = True
        else:
            report["written"] = False
        self.stdout.write(json.dumps(report, sort_keys=True, indent=2))
