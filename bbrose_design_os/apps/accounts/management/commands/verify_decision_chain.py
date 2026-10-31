"""`manage.py verify_decision_chain` — read-only verification of the signed chain (1A-5C).

Verifies head signature, event count, terminal sequence/hash, sequence continuity,
previous-event linkage, schema/signed-field/serialization, content hashes, HMAC signatures,
key ids, signature algorithms, supersession references, actor/role/action validity, the
signed authorization snapshot's consistency with its envelope, historical role assignment,
policy version, attestation binding, lifecycle invalidation, and subject consistency.

Modes: full (default) or bounded (`--from-seq`/`--limit`, diagnostic only). Output: text
(default) or `--format json`. **Never writes, repairs, re-signs, or updates anything.**
Exits non-zero on any FATAL (cryptographic / chain-integrity / authorization-integrity)
finding; warnings are reported and qualified but do not, by themselves, fail the command.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand

from ...chain_verification import genesis_head_summary, verify_decision_chain


class Command(BaseCommand):
    help = "Verify the signed decision-event chain (read-only)."

    def add_arguments(self, parser):
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--from-seq", type=int, default=None,
                            help="Bounded diagnostic: start at this sequence number.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Bounded diagnostic: inspect at most N events.")

    def handle(self, *args, **opts):
        report = verify_decision_chain(from_seq=opts["from_seq"], limit=opts["limit"])
        head = genesis_head_summary()

        if opts["format"] == "json":
            self.stdout.write(json.dumps(
                {"report": report.as_dict(), "head": head}, indent=2))
        else:
            self._text(report, head)

        # non-zero ONLY on fatal findings; a diagnostic (bounded) run with no fatals is 0
        # but never claims full-chain validity.
        if not report.ok:
            self.stderr.write(self.style.ERROR(
                f"FAILED: {len(report.fatal)} fatal finding(s)."))
            raise SystemExit(1)

    def _text(self, report, head):
        w = self.stdout.write
        w(f"decision-chain verification — status: {report.status}")
        w(f"  mode: {report.mode}  head_checked: {report.head_checked}")
        w(f"  verified {report.verified_events} of {report.total_events} event(s)")
        w(f"  head: {head}")
        if report.mode == "bounded":
            w(self.style.WARNING(
                "  NOTE: bounded/diagnostic run — whole-chain linkage and head "
                "reconciliation are NOT established by a slice."))
        if report.fatal:
            w(self.style.ERROR(f"  FATAL ({len(report.fatal)}):"))
            for f in report.fatal:
                w(f"    [{f.code}] seq={f.sequence_number} {f.event_id}: {f.detail}")
        if report.warnings:
            w(self.style.WARNING(f"  WARNINGS ({len(report.warnings)}):"))
            for f in report.warnings:
                w(f"    [{f.code}] seq={f.sequence_number} {f.event_id}: {f.detail}")
        if not report.fatal and not report.warnings:
            w(self.style.SUCCESS("  no findings."))
