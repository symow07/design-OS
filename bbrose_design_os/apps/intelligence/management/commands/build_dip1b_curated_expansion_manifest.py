import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ...curated_expansion import (
    DEFAULT_MANIFEST_PATH, MANIFEST_ID, CuratedExpansionError,
    build_curated_expansion_manifest,
)


class Command(BaseCommand):
    help = "Build the explicit deterministic DIP-1B-5A expansion manifest."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--write", action="store_true")

    def handle(self, *args, **options):
        try:
            document, raw, manifest_hash = build_curated_expansion_manifest()
        except CuratedExpansionError as exc:
            raise CommandError(str(exc)) from exc
        path = Path(DEFAULT_MANIFEST_PATH)
        matches = path.is_file() and path.read_bytes() == raw
        if options["write"]:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        self.stdout.write(json.dumps({
            "mode": "write" if options["write"] else "dry-run",
            "manifest_id": MANIFEST_ID, "manifest_hash": manifest_hash,
            "manifest_entries": len(document["entries"]),
            "historical_designs": 6, "design_assets": 53, "fonts": 0,
            "matches_existing": matches, "written": bool(options["write"]),
        }, indent=2, sort_keys=True))
