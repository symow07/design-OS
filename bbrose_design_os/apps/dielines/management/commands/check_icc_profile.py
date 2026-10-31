"""Validate a candidate print-shop ICC profile (Phase 2A-6B §9).

    manage.py check_icc_profile /path/to/printer-supplied.icc

Reports exactly what the production-readiness record will carry — runtime
path, SHA-256, description, colour space, device class, version — and states
whether the profile would satisfy the output intent. Nothing is installed,
copied into the repository, or configured as a side effect: the operator
sets PRODUCTION_ICC_PROFILE_PATH deliberately after reading this.

The profile must come from the print shop and match the agreed printing
condition, board stock, coating, press standard and ink limit. Those are
commercial facts this command cannot verify — it verifies only that the FILE
is a valid CMYK output profile.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError
from django.test import override_settings


class Command(BaseCommand):
    help = "Validate a candidate CMYK ICC profile for the PDF/X output intent"

    def add_arguments(self, parser):
        parser.add_argument("path", help="path to the printer-supplied .icc")
        parser.add_argument("--json", action="store_true",
                            help="emit the identity record as JSON")

    def handle(self, *args, **opts):
        from apps.dielines.exporters.output_intent import describe_profile

        with override_settings(PRODUCTION_ICC_PROFILE_PATH=opts["path"]):
            identity = describe_profile()

        if opts["json"]:
            self.stdout.write(json.dumps(identity.to_dict(), indent=2))
        else:
            self.stdout.write("ICC PROFILE IDENTITY")
            for label, key in (
                ("runtime path", "path"),
                ("file name", "filename"),
                ("SHA-256", "sha256"),
                ("size (bytes)", "size_bytes"),
                ("description", "description"),
                ("colour space", "colour_space"),
                ("components", "components"),
                ("device class", "device_class"),
                ("profile version", "profile_version"),
                ("validation", "validation_result"),
                ("detail", "detail"),
            ):
                self.stdout.write(f"  {label:16s}: {identity.to_dict()[key]}")

        if not identity.valid:
            raise CommandError(
                f"NOT USABLE as a production output intent: "
                f"{identity.validation_result} — {identity.detail}")

        self.stdout.write(self.style.SUCCESS(
            "\nValid CMYK output profile. To use it:\n"
            f"  1. keep the file OUTSIDE source control (licence and "
            f"redistribution rights are the print shop's);\n"
            f"  2. set PRODUCTION_ICC_PROFILE_PATH={identity.path}\n"
            f"  3. set PRODUCTION_OUTPUT_CONDITION to the agreed printing "
            f"condition (currently {identity.output_condition!r});\n"
            "  4. re-run the production export — the PDF/X OutputIntent is\n"
            "     attached and MISSING_OUTPUT_INTENT clears;\n"
            "  5. confirm with the print shop that the profile matches the\n"
            "     board stock, coating, press standard and ink limit — this\n"
            "     command validates the FILE, not the commercial agreement."))
