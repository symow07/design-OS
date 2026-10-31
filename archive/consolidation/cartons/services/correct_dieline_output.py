"""Regenerate a task's packaging deliverables with a corrected template
(DIP-2A-5-DIE-5, the task-#47 Gate-2 correction).

Two hard-ordered stages, per the correction contract:

  STAGE 1 — STRUCTURE, no graphics: new DielineJob, geometry, dimensional
  reconciliation against the customer's inner/outer triplets, structural
  comparison page + checklist. If the structure gate does not PASS, the
  command stops here — graphics are never placed on an unverified die.

  STAGE 2 — full regeneration: the shared export pipeline drawing the carton
  as every carton is drawn, its front from its concept's map [E5b, the owner's
  Q2, approved with the clean-up list at b5892f9: one engine for a carton —
  it drew the direction's style], the folded 3D mockup, and the
  PackagingOutput updated in place (spec_sheet gains required_template +
  production_validation: "strict" so Gate-2 approval is machine-gated).
  The defective DielineJob is kept for audit; the task status is NEVER
  touched — the task stays wherever the workflow holds it.

Finally the Gate-2 production-readiness report is printed. The command
regenerates deliverables; it does not approve anything.
"""
from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Regenerate a task's dieline/artwork deliverables with a corrected template"

    def add_arguments(self, parser):
        parser.add_argument("task_id", type=int)
        parser.add_argument("--template", required=True)
        parser.add_argument("--width", type=float, required=True,
                            help="manufacturing main-panel width W (mm)")
        parser.add_argument("--depth", type=float, required=True,
                            help="manufacturing side-panel width D (mm)")
        parser.add_argument("--height", type=float, required=True)
        parser.add_argument("--board", type=float, required=True,
                            help="board thickness t (mm)")
        parser.add_argument("--inner", required=True,
                            help="supplied inner dims 'W,D,H' (mm)")
        parser.add_argument("--outer", required=True,
                            help="supplied outer dims 'W,D,H' (mm)")
        parser.add_argument("--product-name", required=True)
        parser.add_argument("--subtitle", default="")
        parser.add_argument("--glue-tab", type=float, default=10.0)
        parser.add_argument("--structure-only", action="store_true",
                            help="stop after stage 1 (no graphics)")

    def handle(self, *args, **opts):
        from apps.dielines.analysis.reconciliation import reconcile_dimensions
        from apps.dielines.exporters.structural_comparison import (
            export_structural_comparison,
        )
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.models import DielineJob
        from apps.dielines.services.export_service import (
            generate_exports,
            job_export_dir,
        )
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.models import DesignTask, PackagingOutput

        task = DesignTask.objects.filter(pk=opts["task_id"]).first()
        if task is None:
            raise CommandError(f"task {opts['task_id']} not found")
        output = (PackagingOutput.objects
                  .filter(task=task).order_by("-created_at").first())
        if output is None:
            raise CommandError(f"task {task.pk} has no PackagingOutput")
        # [E5b] the carton redrawn from its concept's map, as the carton is drawn — never from the direction's
        # style; one with no map front on its record is refused here, before anything is drawn
        map_front = None
        if not opts["structure_only"]:
            from apps.pipeline.services.native_handoff import NO_MAP_FRONT_WORDS, carton_map_front
            map_front = carton_map_front(output)
            if map_front is None:
                raise CommandError(f"task {task.pk}: {NO_MAP_FRONT_WORDS}; nothing was redrawn")

        inner = tuple(float(v) for v in opts["inner"].split(","))
        outer = tuple(float(v) for v in opts["outer"].split(","))
        if len(inner) != 3 or len(outer) != 3:
            raise CommandError("--inner/--outer need exactly three values")

        old_spec = output.spec_sheet or {}
        panel_info = old_spec.get("panel_info") or {}
        # The regulatory sticker's product name must be the PRODUCT name,
        # never task/brief text.
        panel_info = {**panel_info, "product_name": opts["product_name"]}

        params = DielineInputJSON(
            template=opts["template"], unit="mm",
            dimensions={"width_mm": opts["width"], "depth_mm": opts["depth"],
                        "height_mm": opts["height"]},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": opts["glue_tab"],
                          "board_thickness_mm": opts["board"],
                          "thickness_compensation": True},
            metadata={"product_name": opts["product_name"],
                      "product_type": opts["subtitle"],
                      "notes": f"Gate-2 correction of task {task.pk}"},
        )

        # ------------------------- STAGE 1: structure ----------------------
        coords = calculate_dieline(params)
        rec = reconcile_dimensions(coords, inner, outer)

        job = DielineJob.objects.create(
            product=getattr(task, "product", None),
            template_type=opts["template"], scenario="B",
            input_json=params.model_dump(),
            extraction_result={}, validation_status="pending",
        )
        out_dir = str(job_export_dir(job.id))
        prev = {"template": old_spec.get("template", ""),
                "board_thickness_mm": ((output.dieline_job.input_json or {})
                                       .get("construction", {})
                                       .get("board_thickness_mm")
                                       if output.dieline_job else None)}
        cmp_pdf, cmp_json = export_structural_comparison(
            coords, rec, str(job.id), out_dir, previous_spec=prev)
        checklist = json.load(open(cmp_json, encoding="utf-8"))

        self.stdout.write(f"STAGE 1 — job {job.id}")
        self.stdout.write(f"  comparison: {cmp_pdf}")
        self.stdout.write(f"  reconciled: {rec.reconciled}")
        for a in rec.assumptions:
            self.stdout.write(f"  ASSUMPTION: {a}")
        for disc in rec.discrepancies:
            self.stdout.write(self.style.ERROR(f"  DISCREPANCY: {disc}"))

        if not checklist["structure_passed_before_graphics"]:
            job.validation_status = "invalid"
            job.save(update_fields=["validation_status"])
            raise CommandError(
                "structure gate NOT PASSED — graphics were not placed; "
                f"review {cmp_pdf}")
        self.stdout.write(self.style.SUCCESS(
            "  structure gate PASSED — graphics placement may proceed"))
        if opts["structure_only"]:
            return

        # ------------------------- STAGE 2: full regeneration --------------
        logs: list[str] = []
        gen = generate_exports(
            job, params,
            log=lambda msg, data=None, level="info": logs.append(msg),
            panel_info=panel_info,
            # [E5b] the front from its concept's map, on the map's own ground: the carton's one engine
            artwork_tint=map_front.get("ground"), map_front=map_front,
        )
        for msg in logs:
            self.stdout.write(f"  {msg}")

        mockup_path = None
        if gen.get("design_preview_png_path"):
            from apps.dielines.exporters.mockup_3d import export_folded_mockup
            import os
            mockup_out = os.path.join(out_dir, f"{job.id}_mockup_3d.png")
            mockup_path = export_folded_mockup(
                gen["coords"], gen["design_preview_png_path"], mockup_out)
            if mockup_path:
                self.stdout.write(f"  3D mockup: {mockup_path}")

        # --------- persist onto the PackagingOutput (files + spec) ----------
        tid = task.pk
        with open(gen["svg_path"], "rb") as f:
            from django.core.files import File
            output.dieline_file.save(
                f"dieline_task_{tid}_corrected.svg", File(f), save=False)
        if gen.get("ai_path"):
            with open(gen["ai_path"], "rb") as f:
                output.dieline_ai_file.save(
                    f"dieline_task_{tid}_corrected.ai", File(f), save=False)
        if gen.get("production_pdf_path"):
            with open(gen["production_pdf_path"], "rb") as f:
                output.production_pdf.save(
                    f"dieline_task_{tid}_corrected_production.pdf",
                    File(f), save=False)
        if gen.get("design_preview_png_path"):
            with open(gen["design_preview_png_path"], "rb") as f:
                output.design_preview.save(
                    f"design_preview_task_{tid}_corrected.png",
                    File(f), save=False)
        if gen.get("design_preview_ai_path"):
            with open(gen["design_preview_ai_path"], "rb") as f:
                output.design_preview_ai.save(
                    f"design_preview_task_{tid}_corrected.ai",
                    File(f), save=False)

        derived = gen["coords"].derived
        old_job_id = output.dieline_job_id
        output.dieline_job = job
        output.spec_sheet = {
            **old_spec,
            "backend": "dieline",
            "template": opts["template"],
            "template_version": derived.get("template_version"),
            "required_template": opts["template"],
            "production_validation": "strict",
            "panel_info": panel_info,
            "warnings": gen.get("warnings", []),
            "correction": {
                "replaced_job": str(old_job_id or ""),
                "reason": "Gate-2 correction: side-seam template, the carton "
                          "drawn from its concept's map (task stopped before "
                          "Gate 2)",
                "assumptions": derived.get("assumptions", []),
                "reconciled": rec.reconciled,
            },
        }
        output.save()

        # ------------------------- readiness report -------------------------
        from apps.dielines.validators.production_readiness import (
            evaluate_production_readiness,
        )
        from apps.pipeline.views import _forbidden_panel_texts
        output.refresh_from_db()
        report = evaluate_production_readiness(
            output, expected_template=opts["template"],
            forbidden_panel_texts=_forbidden_panel_texts(task))
        self.stdout.write("GATE-2 READINESS REPORT:")
        self.stdout.write(json.dumps(report.to_dict(), indent=2))
        self.stdout.write(self.style.SUCCESS(
            f"task {task.pk} status untouched: {task.status}"))
