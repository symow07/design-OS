"""Dieline generation agent — replaces the role Pacdora played after Gate 1.

Two-phase, matching the AI Dieline Contract (docs/ai_dieline_contract.md in the
dieline-generator project):

  Phase 1 (estimate):  run() produces a DimensionExtractionResult and a
                       DielineJob. Scenario A reads exact dimensions straight
                       from the Product (no AI). Scenario B asks Claude to
                       estimate, and never invents geometry.
  Phase 2 (generate):  after a human confirms the dimensions, generate() runs
                       the deterministic geometry engine + SVG/AI exporters.

Claude only ever estimates scalar dimensions; all geometry is produced by the
deterministic code in apps.dielines.geometry.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

from django.conf import settings

from apps.dielines.validators.schema import (
    DielineInputJSON,
    DimensionExtractionResult,
    FieldEstimate,
)
from apps.dielines.geometry.engine import calculate_straight_tuck_end
from apps.dielines.exporters.svg_exporter import export_svg
from apps.dielines.exporters.svg_validator import validate_svg
from apps.dielines.exporters.ai_exporter import export_ai
from apps.dielines.models import DielineJob, DielineTemplate

TEMPLATE_TYPE = "straight_tuck_end_carton"

# Fallback print/construction constants if no DielineTemplate is seeded.
_DEFAULT_BLEED_MM = 3.0
_DEFAULT_SAFE_MARGIN_MM = 4.0
_DEFAULT_GLUE_TAB_MM = 10.0

_BLOCKED_FIELD = FieldEstimate(value=None, confidence=0.0, source="manual", blocked=True)

_SYSTEM_PROMPT = """\
You are a packaging engineer AI. Your job is to estimate the physical dimensions
of a cosmetic product carton from the provided context.

Return ONLY valid JSON — no markdown, no preamble, no explanation.

The JSON must match this exact schema:
{
  "width_mm":       {"value": float|null, "confidence": float, "source": string},
  "depth_mm":       {"value": float|null, "confidence": float, "source": string},
  "height_mm":      {"value": float|null, "confidence": float, "source": string},
  "bleed_mm":       {"value": float|null, "confidence": float, "source": string},
  "safe_margin_mm": {"value": float|null, "confidence": float, "source": string},
  "glue_tab_mm":    {"value": float|null, "confidence": float, "source": string}
}

Rules:
- confidence is a float between 0.0 and 1.0
- If confidence < 0.85, value MUST be null
- Be conservative — null is safer than a wrong number
- source must be one of: "image", "text", "pdf", "db", "manual"

Cosmetic product reference ranges (mm):
  width_mm:        12–50  (slim cosmetics)
  depth_mm:        12–40
  height_mm:       60–180
  bleed_mm:        always 3.0, confidence 1.0, source "db"
  safe_margin_mm:  always 4.0, confidence 1.0, source "db"
  glue_tab_mm:     8–12, default 10.0
"""


@contextmanager
def _in_export_dir():
    """The exporters write to a relative 'exports/' path; pin CWD to BASE_DIR
    so files always land in DIELINE_EXPORT_DIR regardless of how the process
    was launched."""
    prev = os.getcwd()
    os.chdir(settings.BASE_DIR)
    try:
        yield
    finally:
        os.chdir(prev)


def _db_field(value, confidence=1.0):
    return FieldEstimate(value=float(value), confidence=confidence, source="db", blocked=False)


class DielineAgent:
    def __init__(self, task, log_fn=None):
        self.task = task
        self.product = getattr(task, "product", None)
        self.log = log_fn or (lambda msg, data=None, level="info": None)

    # ------------------------------------------------------------------
    # Phase 1 — dimension estimation
    # ------------------------------------------------------------------

    def run(self):
        """Estimate dimensions and persist a DielineJob. Returns (result, job)."""
        scenario = self._determine_scenario()
        self.log(f"Dieline: scenario {scenario} determined")

        if scenario == "A":
            result = self._extract_from_db()
            self.log("Dieline: dimensions read from product record (no AI needed)")
        else:
            result = self._extract_from_context()
            self.log(
                "Dieline: dimensions estimated from context"
                if result.can_proceed
                else "Dieline: some dimensions need manual entry",
                level="info" if result.can_proceed else "warning",
            )

        job = DielineJob.objects.create(
            product=self.product,
            template_type=TEMPLATE_TYPE,
            scenario=scenario,
            input_json={},
            extraction_result=result.model_dump(),
            validation_status="pending",
        )
        self.log(f"Dieline: job {job.id} created, awaiting dimension confirmation")
        return result, job

    def _determine_scenario(self):
        p = self.product
        if (
            p is not None
            and getattr(p, "width_mm", None)
            and getattr(p, "depth_mm", None)
            and getattr(p, "height_mm", None)
            and p.width_mm > 0
            and p.depth_mm > 0
            and p.height_mm > 0
        ):
            return "A"
        return "B"

    def _extract_from_db(self):
        p = self.product
        tpl = self._load_template()
        bleed = float(tpl.default_bleed_mm) if tpl else _DEFAULT_BLEED_MM
        safe = float(tpl.default_safe_margin_mm) if tpl else _DEFAULT_SAFE_MARGIN_MM
        glue = float(tpl.default_glue_tab_mm) if tpl else _DEFAULT_GLUE_TAB_MM
        return DimensionExtractionResult(
            width_mm=_db_field(p.width_mm),
            depth_mm=_db_field(p.depth_mm),
            height_mm=_db_field(p.height_mm),
            bleed_mm=_db_field(bleed, confidence=0.90),
            safe_margin_mm=_db_field(safe, confidence=0.90),
            glue_tab_mm=_db_field(glue, confidence=0.90),
            scenario="A",
            can_proceed=True,
        )

    def _extract_from_context(self):
        try:
            raw = self._call_claude(self._build_context())
            return self._parse_claude_response(raw)
        except Exception as exc:
            self.log(f"Dieline: AI estimation failed — {exc}", level="warning")
            return self._blocked_result("B")

    def _blocked_result(self, scenario):
        b = _BLOCKED_FIELD
        return DimensionExtractionResult(
            width_mm=b, depth_mm=b, height_mm=b,
            bleed_mm=b, safe_margin_mm=b, glue_tab_mm=b,
            scenario=scenario, can_proceed=False,
        )

    def _build_context(self):
        parts = [
            f"Task ID: {self.task.pk}",
            f"Description: {getattr(self.task, 'task_text', '')}",
        ]
        p = self.product
        if p is not None:
            parts.append(f"Product: {p.name}")
            if getattr(p, "product_type", ""):
                parts.append(f"Product type: {p.product_type}")
            if getattr(p, "dimensions", ""):
                parts.append(f"Recorded dimensions (free text): {p.dimensions}")
        return "\n".join(parts)

    def _call_claude(self, context):
        import anthropic
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY or None)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        return response.content[0].text

    def _parse_claude_response(self, raw):
        data = json.loads(raw)

        def _field(key):
            entry = data[key]
            confidence = float(entry["confidence"])
            value = entry.get("value")
            blocked = confidence < 0.85 or value is None
            return FieldEstimate(
                value=None if blocked else float(value),
                confidence=confidence,
                source=entry["source"],
                blocked=blocked,
            )

        fields = {
            k: _field(k)
            for k in ("width_mm", "depth_mm", "height_mm",
                      "bleed_mm", "safe_margin_mm", "glue_tab_mm")
        }
        return DimensionExtractionResult(
            **fields,
            scenario="B",
            can_proceed=not any(f.blocked for f in fields.values()),
        )

    def _load_template(self):
        return DielineTemplate.objects.filter(template_type=TEMPLATE_TYPE).first()

    # ------------------------------------------------------------------
    # Phase 2 — deterministic geometry + export
    # ------------------------------------------------------------------

    def generate(self, job, confirmed_dims, metadata=None):
        """Run geometry + exporters for confirmed dimensions.

        Returns a dict with the SVG string, the .ai path (or None), the geometry
        summary and any warnings. Raises ValueError on invalid input/geometry so
        the caller can surface it to the user.
        """
        metadata = metadata or {}
        params = DielineInputJSON(
            template=TEMPLATE_TYPE,
            unit="mm",
            dimensions={
                "width_mm": confirmed_dims["width_mm"],
                "depth_mm": confirmed_dims["depth_mm"],
                "height_mm": confirmed_dims["height_mm"],
            },
            print_settings={
                "bleed_mm": confirmed_dims.get("bleed_mm", _DEFAULT_BLEED_MM),
                "safe_margin_mm": confirmed_dims.get("safe_margin_mm", _DEFAULT_SAFE_MARGIN_MM),
            },
            construction={
                "glue_tab_mm": confirmed_dims.get("glue_tab_mm", _DEFAULT_GLUE_TAB_MM),
            },
            metadata={
                "product_name": metadata.get("product_name", ""),
                "product_type": metadata.get("product_type", ""),
                "notes": metadata.get("notes", ""),
            },
        )

        self.log("Dieline: running geometry engine")
        coords = calculate_straight_tuck_end(params)

        job_id = str(job.id)
        with _in_export_dir():
            svg_string = export_svg(coords, job_id)

            svg_errors = validate_svg(svg_string, coords)
            if svg_errors:
                job.input_json = params.model_dump()
                job.validation_status = "invalid"
                job.warnings = svg_errors
                job.save(update_fields=["input_json", "validation_status", "warnings"])
                self.log(f"Dieline: SVG validation failed — {svg_errors}", level="error")
                raise ValueError(f"SVG validation failed: {svg_errors}")

            # Illustrator .ai export is best-effort (needs cairo/svglib).
            ai_path = None
            try:
                ai_rel = export_ai(svg_string, job_id)
                ai_path = os.path.join(settings.BASE_DIR, ai_rel)
                if not os.path.exists(ai_path):
                    ai_path = None
            except Exception as exc:
                self.log(f"Dieline: .ai export skipped — {exc}", level="warning")
                ai_path = None

        job.input_json = params.model_dump()
        job.validation_status = "valid"
        job.svg_output_path = f"exports/{job_id}.svg"
        job.ai_output_path = f"exports/{job_id}.ai" if ai_path else ""
        job.save(update_fields=[
            "input_json", "validation_status", "svg_output_path", "ai_output_path",
        ])
        self.log("Dieline: SVG generated and validated")

        return {
            "svg_string": svg_string,
            "ai_path": ai_path,
            "flat_width_mm": coords.flat_width_mm,
            "flat_height_mm": coords.flat_height_mm,
            "panel_count": len(coords.panels),
            "warnings": list(job.warnings) if job.warnings else [],
        }
