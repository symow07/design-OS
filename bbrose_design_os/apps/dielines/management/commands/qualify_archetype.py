"""Regenerate an archetype's committed qualification reports (2A-9C).

    python manage.py qualify_archetype reference_opposed_tuck_carton

Writes parameter_schema.json, supported_domain.json, qualification_matrix
.json and property_test_report.json into
``docs/qualification/<template>_<version>/`` so every archetype's report
regenerates identically. Markdown narratives and render thinning stay a
reviewed, committed responsibility — the command never deletes anything.
"""
from __future__ import annotations

import json
import os

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Regenerate committed qualification reports for an archetype"

    def add_arguments(self, parser):
        parser.add_argument("template_id")
        parser.add_argument("--outdir", default="")
        parser.add_argument("--renders", action="store_true",
                            help="also render preview SVGs + folded "
                                 "diagnostics for supported fixtures")

    def handle(self, *args, **options):
        from apps.dielines.qualification.contract import contract_for
        from apps.dielines.qualification.domain import (
            domain_report,
            effective_bounds,
        )
        from apps.dielines.qualification.runner import (
            adapter_for,
            fixtures_for,
            qualification_matrix,
            seeded_property_sweep,
            sweep_seed_for,
        )

        template_id = options["template_id"]
        adapter = adapter_for(template_id)
        if adapter is None:
            raise CommandError(
                f"{template_id!r} has no qualification adapter; registered: "
                f"{__import__('apps.dielines.qualification.runner', fromlist=['registered_adapters']).registered_adapters()}")
        fixtures = fixtures_for(template_id)
        if not fixtures:
            raise CommandError(f"{template_id!r} has no frozen fixture set")
        outdir = options["outdir"] or os.path.join(
            "docs", "qualification",
            f"{adapter.template}_{adapter.version.replace('.', '_')}")
        os.makedirs(outdir, exist_ok=True)

        seed = sweep_seed_for(template_id)
        rows = qualification_matrix(
            fixtures, adapter,
            render_dir=os.path.join(outdir, "renders")
            if options["renders"] else None)
        sweep = seeded_property_sweep(adapter, seed=seed,
                                      n_in_domain=150, n_random=250)

        contract = contract_for(adapter.key)
        if contract is not None:
            with open(os.path.join(outdir, "parameter_schema.json"),
                      "w") as fh:
                json.dump(contract.to_dict(), fh, indent=2)
        with open(os.path.join(outdir, "supported_domain.json"), "w") as fh:
            json.dump({"schema": "dieline_supported_domain/1.0",
                       "template_key": adapter.key,
                       "closure": adapter.closure.to_dict(),
                       "constraints": domain_report(
                           adapter.domain_constraints),
                       "envelope_at_t05_glue12":
                           effective_bounds(0.5, 12.0)}, fh, indent=2)
        with open(os.path.join(outdir, "qualification_matrix.json"),
                  "w") as fh:
            json.dump({"schema": "dieline_qualification_matrix/1.0",
                       "template_key": adapter.key, "rows": rows},
                      fh, indent=2, default=str)
        with open(os.path.join(outdir, "property_test_report.json"),
                  "w") as fh:
            json.dump({"schema": "dieline_property_sweep/1.0",
                       "template_key": adapter.key,
                       "summary": {k: v for k, v in sweep.items()
                                   if k != "failures"},
                       "failures": sweep["failures"]}, fh, indent=2)

        supported = sum(1 for r in rows if r["outcome"] == "SUPPORTED")
        self.stdout.write(self.style.SUCCESS(
            f"{adapter.key}: {supported}/{len(rows)} fixtures supported; "
            f"sweep seed {seed}: {len(sweep['failures'])} failures; "
            f"reports in {outdir}"))
        if sweep["failures"]:
            raise CommandError(
                "property sweep produced failures — see "
                "property_test_report.json (reproduce with the seed)")
