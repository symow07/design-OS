import json

from django.core.management.base import BaseCommand, CommandError

from ...manifest import ManifestError
from ...mvp_import import run_import


class Command(BaseCommand):
    help = "Validate or apply the bounded DIP-0 MVP manifest (dry-run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--manifest", required=True)
        parser.add_argument("--apply", action="store_true",
                            help="Persist the import; without this flag no data is written.")

    def handle(self, *args, **options):
        try:
            result = run_import(options["manifest"], apply=options["apply"])
        except ManifestError as exc:
            raise CommandError(str(exc)) from exc
        serializable = dict(result)
        batch = serializable.pop("batch", None)
        if batch is not None:
            serializable["batch_id"] = str(batch.pk)
            serializable["batch_status"] = batch.status
        self.stdout.write(json.dumps(serializable, sort_keys=True, indent=2))
