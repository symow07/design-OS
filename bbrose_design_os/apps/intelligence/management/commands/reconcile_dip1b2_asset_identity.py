import json

from django.core.management.base import BaseCommand, CommandError

from ...asset_identity_reconciliation import reconcile_asset_identity
from ...identity import CandidateIdentityError
from ...manifest import ManifestError


class Command(BaseCommand):
    help = "Reconcile the bounded C2 duplicate origin records to semantic identity."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument(
            "--apply", action="store_true",
            help="Persist the controlled correction; default is a read-only plan.",
        )

    def handle(self, *args, **options):
        try:
            result = reconcile_asset_identity(
                options["manifest"], apply=options["apply"])
        except (ManifestError, CandidateIdentityError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result, sort_keys=True, indent=2))
