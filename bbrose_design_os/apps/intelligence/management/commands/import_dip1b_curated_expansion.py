import json

from django.core.management.base import BaseCommand, CommandError

from ...curated_expansion import CuratedExpansionError
from ...curated_expansion_import import (
    CuratedExpansionImportError, run_curated_expansion_import,
)


class Command(BaseCommand):
    help = "Dry-run or apply the bounded DIP-1B-5A curated expansion."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        try:
            report = run_curated_expansion_import(apply=options["apply"])
        except (CuratedExpansionError, CuratedExpansionImportError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, indent=2, sort_keys=True))
