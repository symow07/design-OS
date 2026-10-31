import json

from django.core.management.base import BaseCommand, CommandError

from ...brand_evidence import BrandEvidenceError
from ...brand_evidence_import import BrandEvidenceImportError, run_brand_evidence_import


class Command(BaseCommand):
    help = "Dry-run or apply the bounded deterministic brand-evidence import."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Persist the validated append-only import; default is dry-run.")

    def handle(self, *args, **options):
        try:
            report = run_brand_evidence_import(apply=options["apply"])
        except (BrandEvidenceError, BrandEvidenceImportError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(report, sort_keys=True, indent=2))
