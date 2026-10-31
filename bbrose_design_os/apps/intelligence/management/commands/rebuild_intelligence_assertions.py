import json

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ...projection import ProjectionError, rebuild_assertion_projections


class Command(BaseCommand):
    help = ("Verify and rebuild deterministic human-assertion projections "
            "(write-free dry run by default).")
    # Verification of a genesis chain and projection maintenance do not sign events.
    # Non-empty chains still fail closed in verify_chain if a referenced key is absent.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="Build and atomically publish; default is a write-free dry run.")
        parser.add_argument(
            "--json", action="store_true", help="Emit a JSON report.")
        parser.add_argument(
            "--evaluation-timestamp",
            help="Aware ISO-8601 evaluation time for deterministic testing.")
        parser.add_argument(
            "--expected-chain-head",
            help="Expected lowercase SHA-256 head hash, or GENESIS.")

    def handle(self, *args, **options):
        evaluation_at = None
        if options["evaluation_timestamp"]:
            evaluation_at = parse_datetime(options["evaluation_timestamp"])
            if evaluation_at is None or not timezone.is_aware(evaluation_at):
                raise CommandError("EVALUATION_TIMESTAMP_MUST_BE_AWARE")
        try:
            report = rebuild_assertion_projections(
                apply=options["apply"], evaluation_at=evaluation_at,
                expected_chain_head=options["expected_chain_head"])
        except ProjectionError as exc:
            raise CommandError(exc.code) from exc
        if options["json"]:
            self.stdout.write(json.dumps(report, sort_keys=True, indent=2))
            return
        for key in sorted(report):
            self.stdout.write(f"{key}: {report[key]}")
