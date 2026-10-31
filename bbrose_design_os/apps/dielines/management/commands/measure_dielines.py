"""Measure factory dieline geometry across a folder of .ai files (WS1).

    manage.py measure_dielines ../design_models --out report.json
    manage.py measure_dielines ../design_models --census
    manage.py measure_dielines ../design_models --only EP2508

Dev tooling (requires PyMuPDF from requirements-dev.txt). Produces a
human-review report; it NEVER changes engine constants — that is the
separate, deliberate regen_engine_reference step.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Measure dieline geometry ratios from factory .ai files (report only)"

    def add_arguments(self, parser):
        parser.add_argument("directory", help="Folder with .ai/.pdf files")
        parser.add_argument("--out", help="Write the full JSON report here")
        parser.add_argument("--census", action="store_true",
                            help="Print per-file stroke color/dash census only")
        parser.add_argument("--only", default="",
                            help="Only files whose name contains this substring")

    def handle(self, *args, **opts):
        src = Path(opts["directory"]).expanduser().resolve()
        if not src.is_dir():
            raise CommandError(f"not a directory: {src}")

        from apps.dielines.analysis.measure import (
            aggregate,
            census_strokes,
            extract_vector_drawing,
            measure_file,
        )

        files = sorted(
            p for p in src.iterdir()
            if p.suffix.lower() in (".ai", ".pdf")
            and (not opts["only"] or opts["only"].lower() in p.name.lower())
        )
        if not files:
            raise CommandError("no .ai/.pdf files matched")

        if opts["census"]:
            for f in files:
                raw = extract_vector_drawing(str(f))
                if raw is None:
                    self.stdout.write(f"{f.name}: unreadable")
                    continue
                self.stdout.write(f"{f.name}: {json.dumps(census_strokes(raw))}")
            return

        reports = []
        for f in files:
            r = measure_file(str(f))
            reports.append(r)
            if r["ok"]:
                m = r["measurements"]
                self.stdout.write(
                    f"  ok   {f.name}: W={m.get('W_mm')} D={m.get('D_mm')} "
                    f"tuck/W={m.get('tuck_total_over_W')} "
                    f"dust/D={m.get('dust_over_D')} "
                    f"(confidence {r['confidence']})"
                )
            else:
                self.stdout.write(f"  skip {f.name}: {r['skip_reason']}")

        summary = aggregate(reports)
        self.stdout.write(self.style.SUCCESS(
            f"\nmeasured {summary['files_measured']}/{summary['files_total']} "
            f"files (coverage {summary['coverage']:.0%})"
        ))
        adoptable = 0
        for key, s in summary["ratios"].items():
            verdict = ("ADOPTABLE" if s["consistent"]
                       else "inconsistent — do not adopt")
            adoptable += int(s["consistent"])
            self.stdout.write(
                f"  {key}: median {s['median']} (MAD {s['mad']}, n={s['n']}) "
                f"vs engine {s['engine_current']} [{verdict}]"
            )
        if not adoptable:
            self.stdout.write(self.style.WARNING(
                "no ratio measured consistently across >=5 files — the "
                "measured flats are not a matching template family; keep "
                "the engine constants as they are (Phase B not applicable)"
            ))

        if opts["out"]:
            out = Path(opts["out"]).expanduser().resolve()
            out.write_text(json.dumps(
                {"summary": summary, "files": reports}, indent=2))
            self.stdout.write(f"report written: {out}")
