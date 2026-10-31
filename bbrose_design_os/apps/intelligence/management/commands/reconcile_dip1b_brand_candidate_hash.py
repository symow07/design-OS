import json

from django.core.management.base import BaseCommand

from ...evidence_integrity import reconcile_brand_candidate_integrity


class Command(BaseCommand):
    help = "Read-only reconciliation for DIP-1B-DATA-CORR-1 brand evidence integrity."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", dest="as_json")

    def handle(self, *args, **options):
        report = reconcile_brand_candidate_integrity()
        if options["as_json"]:
            self.stdout.write(json.dumps(report, sort_keys=True))
            return
        integrity = report["integrity"]
        self.stdout.write(
            f"{report['correction_id']}: {integrity['status']} "
            f"({','.join(integrity['reason_codes'])})")
        observed = report["root_of_trust"]["observed_source_sha256"] or "UNAVAILABLE"
        self.stdout.write(
            f"expected={report['root_of_trust']['expected_source_sha256']} "
            f"observed={observed}")
        self.stdout.write(
            f"affected_candidates={report['database']['affected_candidate_items']} "
            f"decisions={report['authority']['affected_decision_events']} "
            f"allowed={report['authority']['affected_allowed_permissions']} "
            f"database_changed={report['database_changed']}")
