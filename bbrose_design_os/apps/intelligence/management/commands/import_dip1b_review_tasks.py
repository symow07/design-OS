import json

from django.core.management.base import BaseCommand, CommandError

from ...review_manifest import (
    DEFAULT_MANIFEST, ReviewManifestError, import_review_candidates,
)


class Command(BaseCommand):
    help = "Validate or apply the bounded DIP-1B-3 review manifest (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
        parser.add_argument("--apply", action="store_true",
                            help="Persist review tasks; default is a write-free dry run.")

    def handle(self, *args, **options):
        try:
            result = import_review_candidates(
                options["manifest"], apply=options["apply"])
        except ReviewManifestError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, sort_keys=True, indent=2))
