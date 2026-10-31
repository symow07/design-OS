import json
from pathlib import Path

from django.core.management.base import BaseCommand

from ...curated_review import (
    DEFAULT_MANIFEST_PATH, MANIFEST_ID, build_curated_review_manifest,
)


class Command(BaseCommand):
    help = "Build the deterministic bounded DIP-1B-5A review manifest."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--write", action="store_true")

    def handle(self, *args, **options):
        document, raw, manifest_hash = build_curated_review_manifest()
        path = Path(DEFAULT_MANIFEST_PATH)
        matches = path.is_file() and path.read_bytes() == raw
        if options["write"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.stdout.write(json.dumps({
            "mode": "write" if options["write"] else "dry-run",
            "manifest_id": MANIFEST_ID, "manifest_hash": manifest_hash,
            "manifest_entries": len(document["entries"]),
            "matches_existing": matches, "written": bool(options["write"]),
        }, sort_keys=True, indent=2))
