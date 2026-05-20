from __future__ import annotations

import json
import logging
from typing import Literal

import anthropic
from django.apps import apps

from apps.dielines.validators.schema import (
    DimensionExtractionResult,
    FieldEstimate,
)

logger = logging.getLogger(__name__)

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


def _make_blocked_result(scenario: Literal["A", "B"]) -> DimensionExtractionResult:
    b = _BLOCKED_FIELD
    return DimensionExtractionResult(
        width_mm=b, depth_mm=b, height_mm=b,
        bleed_mm=b, safe_margin_mm=b, glue_tab_mm=b,
        scenario=scenario,
        can_proceed=False,
    )


def _db_field(value: float, confidence: float = 1.0) -> FieldEstimate:
    return FieldEstimate(value=value, confidence=confidence, source="db", blocked=False)


class DielineAgent:
    def __init__(self, task_id: str) -> None:
        DesignTask = apps.get_model("pipeline", "DesignTask")
        self.task = DesignTask.objects.select_related("product").get(pk=task_id)
        self.product = getattr(self.task, "product", None)
        AgentLog = apps.get_model("pipeline", "AgentLog")
        self.agent_logs = list(AgentLog.objects.filter(task=self.task).order_by("created_at"))

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def run(self) -> DimensionExtractionResult:
        scenario = self.determine_scenario()
        self.log(f"DielineAgent: scenario {scenario} determined")

        if scenario == "A":
            result = self.extract_dimensions_from_db()
        else:
            result = self.extract_dimensions_from_context()

        self.log(f"DielineAgent: extraction complete, can_proceed={result.can_proceed}")
        self._save_job(result, scenario)
        return result

    def determine_scenario(self) -> Literal["A", "B"]:
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

    def extract_dimensions_from_db(self) -> DimensionExtractionResult:
        p = self.product
        tpl = self._load_template()

        return DimensionExtractionResult(
            width_mm=_db_field(float(p.width_mm)),
            depth_mm=_db_field(float(p.depth_mm)),
            height_mm=_db_field(float(p.height_mm)),
            bleed_mm=_db_field(float(tpl.default_bleed_mm), confidence=0.90),
            safe_margin_mm=_db_field(float(tpl.default_safe_margin_mm), confidence=0.90),
            glue_tab_mm=_db_field(float(tpl.default_glue_tab_mm), confidence=0.90),
            scenario="A",
            can_proceed=True,
        )

    def extract_dimensions_from_context(self) -> DimensionExtractionResult:
        context = self._build_context()
        try:
            raw = self._call_claude(context)
            result = self._parse_claude_response(raw)
        except Exception as exc:
            logger.error("DielineAgent: extraction failed — %s", exc)
            self.log(f"DielineAgent: extraction failed — {exc}")
            return _make_blocked_result("B")
        return result

    def log(self, message: str) -> None:
        AgentLog = apps.get_model("pipeline", "AgentLog")
        AgentLog.objects.create(
            task=self.task,
            agent_name="DielineAgent",
            action=message,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_template(self):
        DielineTemplate = apps.get_model("dielines", "DielineTemplate")
        return DielineTemplate.objects.get(template_type="straight_tuck_end_carton")

    def _build_context(self) -> str:
        parts = [
            f"Task ID: {self.task.pk}",
            f"Description: {getattr(self.task, 'description', '')}",
        ]
        file_refs = getattr(self.task, "uploaded_file_refs", None)
        if file_refs:
            parts.append(f"Uploaded files: {file_refs}")
        if self.agent_logs:
            log_lines = "\n".join(
                f"  [{log.created_at}] {log.agent_name}: {log.action}"
                for log in self.agent_logs
            )
            parts.append(f"Agent log history:\n{log_lines}")
        return "\n".join(parts)

    def _call_claude(self, context: str) -> str:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context}],
        )
        return response.content[0].text

    def _parse_claude_response(self, raw: str) -> DimensionExtractionResult:
        data = json.loads(raw)

        def _field(key: str) -> FieldEstimate:
            entry = data[key]
            confidence = float(entry["confidence"])
            value = entry.get("value")
            if value is not None:
                value = float(value)
            blocked = confidence < 0.85 or value is None
            # Enforce schema contract
            if blocked:
                value = None
            return FieldEstimate(
                value=value,
                confidence=confidence,
                source=entry["source"],
                blocked=blocked,
            )

        fields = {k: _field(k) for k in (
            "width_mm", "depth_mm", "height_mm",
            "bleed_mm", "safe_margin_mm", "glue_tab_mm",
        )}
        can_proceed = not any(f.blocked for f in fields.values())

        return DimensionExtractionResult(
            **fields,
            scenario="B",
            can_proceed=can_proceed,
        )

    def _save_job(self, result: DimensionExtractionResult, scenario: Literal["A", "B"]) -> None:
        DielineJob = apps.get_model("dielines", "DielineJob")
        DielineJob.objects.create(
            product=self.product,
            template_type="straight_tuck_end_carton",
            scenario=scenario,
            input_json={},
            extraction_result=result.model_dump(),
            validation_status="pending",
        )
