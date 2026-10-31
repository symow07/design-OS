import json

from django.core.management.base import BaseCommand, CommandError

from ...curated_review import CuratedReviewError, import_curated_review_candidates


class Command(BaseCommand):
    help = "Dry-run or apply the bounded DIP-1B-5A review expansion."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            report = import_curated_review_candidates(apply=options["apply"])
        except CuratedReviewError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, sort_keys=True, indent=2))
