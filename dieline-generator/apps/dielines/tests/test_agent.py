"""
Unit tests for DielineAgent.

All Django ORM calls and the Anthropic client are mocked — no live DB or
API key required.  The tests cover the agent's decision logic and the shape
of the data it produces; integration with the real DB is covered by the
broader test suite.
"""
from __future__ import annotations

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

from apps.dielines.validators.schema import DimensionExtractionResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_product(width=20.0, depth=20.0, height=130.0):
    p = MagicMock()
    p.width_mm = Decimal(str(width)) if width is not None else None
    p.depth_mm = Decimal(str(depth)) if depth is not None else None
    p.height_mm = Decimal(str(height)) if height is not None else None
    return p


def _make_template(bleed=3.0, safe=4.0, glue=10.0):
    t = MagicMock()
    t.default_bleed_mm = Decimal(str(bleed))
    t.default_safe_margin_mm = Decimal(str(safe))
    t.default_glue_tab_mm = Decimal(str(glue))
    return t


def _make_task(task_id="task-1", description="eyeliner", product=None):
    task = MagicMock()
    task.pk = task_id
    task.description = description
    task.product = product
    task.uploaded_file_refs = None
    return task


def _make_agent(task, template, logs=None):
    """
    Build a DielineAgent with all Django/Anthropic calls patched out.
    Returns the agent instance and a dict of the key mocks.
    """
    from apps.pipeline.agents.dieline_agent import DielineAgent

    AgentLog = MagicMock()
    AgentLog.objects.filter.return_value.order_by.return_value = logs or []

    DesignTask = MagicMock()
    DesignTask.objects.select_related.return_value.get.return_value = task

    DielineTemplate = MagicMock()
    DielineTemplate.objects.get.return_value = template

    DielineJob = MagicMock()

    def get_model(app_label, model_name):
        return {
            ("pipeline", "DesignTask"): DesignTask,
            ("pipeline", "AgentLog"): AgentLog,
            ("dielines", "DielineTemplate"): DielineTemplate,
            ("dielines", "DielineJob"): DielineJob,
        }[(app_label, model_name)]

    patcher = patch("apps.pipeline.agents.dieline_agent.apps.get_model", side_effect=get_model)
    patcher.start()

    agent = DielineAgent.__new__(DielineAgent)
    agent.task = task
    agent.product = task.product
    agent.agent_logs = logs or []

    # Attach mocks so tests can inspect them
    agent._mock_get_model = get_model
    agent._mock_AgentLog = AgentLog
    agent._mock_DielineJob = DielineJob
    agent._mock_DielineTemplate = DielineTemplate
    agent._patcher = patcher  # keep alive; call agent._patcher.stop() if needed

    return agent


# ---------------------------------------------------------------------------
# determine_scenario
# ---------------------------------------------------------------------------

class TestDetermineScenario:
    def test_scenario_a_when_product_has_all_dimensions(self):
        product = _make_product(20, 20, 130)
        task = _make_task(product=product)
        agent = _make_agent(task, _make_template())
        assert agent.determine_scenario() == "A"

    def test_scenario_b_when_product_is_none(self):
        task = _make_task(product=None)
        agent = _make_agent(task, _make_template())
        assert agent.determine_scenario() == "B"

    def test_scenario_b_when_width_is_zero(self):
        product = _make_product(width=0, depth=20, height=130)
        task = _make_task(product=product)
        agent = _make_agent(task, _make_template())
        assert agent.determine_scenario() == "B"

    def test_scenario_b_when_height_is_missing(self):
        product = _make_product(width=20, depth=20, height=None)
        task = _make_task(product=product)
        agent = _make_agent(task, _make_template())
        assert agent.determine_scenario() == "B"


# ---------------------------------------------------------------------------
# extract_dimensions_from_db  (Scenario A)
# ---------------------------------------------------------------------------

class TestScenarioA:
    def setup_method(self):
        self.product = _make_product(20.0, 20.0, 130.0)
        task = _make_task(product=self.product)
        self.agent = _make_agent(task, _make_template(bleed=3.0, safe=4.0, glue=10.0))
        self.result = self.agent.extract_dimensions_from_db()

    def test_returns_extraction_result(self):
        assert isinstance(self.result, DimensionExtractionResult)

    def test_scenario_is_a(self):
        assert self.result.scenario == "A"

    def test_can_proceed_is_true(self):
        assert self.result.can_proceed is True

    def test_all_fields_source_db(self):
        fields = [
            self.result.width_mm, self.result.depth_mm, self.result.height_mm,
            self.result.bleed_mm, self.result.safe_margin_mm, self.result.glue_tab_mm,
        ]
        for f in fields:
            assert f.source == "db", f"Expected source='db', got '{f.source}'"

    def test_dimension_values_match_product(self):
        assert self.result.width_mm.value == 20.0
        assert self.result.depth_mm.value == 20.0
        assert self.result.height_mm.value == 130.0

    def test_dimension_fields_confidence_1(self):
        assert self.result.width_mm.confidence == 1.0
        assert self.result.depth_mm.confidence == 1.0
        assert self.result.height_mm.confidence == 1.0

    def test_template_defaults_applied(self):
        assert self.result.bleed_mm.value == 3.0
        assert self.result.safe_margin_mm.value == 4.0
        assert self.result.glue_tab_mm.value == 10.0

    def test_no_blocked_fields(self):
        fields = [
            self.result.width_mm, self.result.depth_mm, self.result.height_mm,
            self.result.bleed_mm, self.result.safe_margin_mm, self.result.glue_tab_mm,
        ]
        for f in fields:
            assert f.blocked is False


# ---------------------------------------------------------------------------
# extract_dimensions_from_context  (Scenario B)
# ---------------------------------------------------------------------------

_GOOD_CLAUDE_RESPONSE = json.dumps({
    "width_mm":       {"value": 18.0, "confidence": 0.91, "source": "image"},
    "depth_mm":       {"value": 18.0, "confidence": 0.91, "source": "image"},
    "height_mm":      {"value": 120.0, "confidence": 0.92, "source": "image"},
    "bleed_mm":       {"value": 3.0,  "confidence": 1.0,  "source": "db"},
    "safe_margin_mm": {"value": 4.0,  "confidence": 1.0,  "source": "db"},
    "glue_tab_mm":    {"value": 10.0, "confidence": 0.90, "source": "db"},
})

_LOW_CONFIDENCE_RESPONSE = json.dumps({
    "width_mm":       {"value": None,  "confidence": 0.40, "source": "image"},
    "depth_mm":       {"value": None,  "confidence": 0.40, "source": "image"},
    "height_mm":      {"value": None,  "confidence": 0.50, "source": "image"},
    "bleed_mm":       {"value": 3.0,   "confidence": 1.0,  "source": "db"},
    "safe_margin_mm": {"value": 4.0,   "confidence": 1.0,  "source": "db"},
    "glue_tab_mm":    {"value": 10.0,  "confidence": 0.90, "source": "db"},
})


def _agent_with_claude_response(response_text: str):
    task = _make_task(product=None, description="slim eyeliner pencil, approx 12cm tall")
    agent = _make_agent(task, _make_template())
    mock_content = MagicMock()
    mock_content.text = response_text
    mock_response = MagicMock()
    mock_response.content = [mock_content]
    agent._call_claude = MagicMock(return_value=response_text)
    return agent


class TestScenarioB:
    def test_calls_extract_context_when_no_product(self):
        task = _make_task(product=None)
        agent = _make_agent(task, _make_template())
        agent.extract_dimensions_from_context = MagicMock(
            return_value=_make_blocked_result_obj()
        )
        with patch.object(agent, "log"):
            with patch.object(agent, "_save_job"):
                agent.run()
        agent.extract_dimensions_from_context.assert_called_once()

    def test_good_claude_response_returns_can_proceed_true(self):
        agent = _agent_with_claude_response(_GOOD_CLAUDE_RESPONSE)
        result = agent.extract_dimensions_from_context()
        assert result.scenario == "B"
        assert result.can_proceed is True

    def test_good_claude_response_values(self):
        agent = _agent_with_claude_response(_GOOD_CLAUDE_RESPONSE)
        result = agent.extract_dimensions_from_context()
        assert result.width_mm.value == 18.0
        assert result.height_mm.value == 120.0

    def test_low_confidence_fields_are_blocked(self):
        agent = _agent_with_claude_response(_LOW_CONFIDENCE_RESPONSE)
        result = agent.extract_dimensions_from_context()
        assert result.width_mm.blocked is True
        assert result.width_mm.value is None

    def test_low_confidence_response_can_proceed_false(self):
        agent = _agent_with_claude_response(_LOW_CONFIDENCE_RESPONSE)
        result = agent.extract_dimensions_from_context()
        assert result.can_proceed is False

    def test_malformed_claude_response_returns_all_blocked(self):
        agent = _agent_with_claude_response("this is not json at all")
        result = agent.extract_dimensions_from_context()
        assert result.can_proceed is False
        assert result.width_mm.blocked is True


# ---------------------------------------------------------------------------
# run() — DielineJob creation
# ---------------------------------------------------------------------------

def _make_blocked_result_obj() -> DimensionExtractionResult:
    from apps.pipeline.agents.dieline_agent import _make_blocked_result
    return _make_blocked_result("B")


class TestRunCreatesJob:
    def _run_scenario_a(self):
        product = _make_product(20.0, 20.0, 130.0)
        task = _make_task(product=product)
        agent = _make_agent(task, _make_template())

        with patch("apps.pipeline.agents.dieline_agent.apps.get_model",
                   side_effect=agent._mock_get_model):
            with patch.object(agent, "log"):
                result = agent.run()

        return result, agent._mock_DielineJob

    def test_dieline_job_created_after_run(self):
        _, DielineJob = self._run_scenario_a()
        DielineJob.objects.create.assert_called_once()

    def test_dieline_job_has_extraction_result(self):
        result, DielineJob = self._run_scenario_a()
        call_kwargs = DielineJob.objects.create.call_args.kwargs
        assert "extraction_result" in call_kwargs
        assert call_kwargs["extraction_result"] is not None

    def test_dieline_job_scenario_matches(self):
        _, DielineJob = self._run_scenario_a()
        call_kwargs = DielineJob.objects.create.call_args.kwargs
        assert call_kwargs["scenario"] == "A"

    def test_dieline_job_template_type_set(self):
        _, DielineJob = self._run_scenario_a()
        call_kwargs = DielineJob.objects.create.call_args.kwargs
        assert call_kwargs["template_type"] == "straight_tuck_end_carton"

    def test_scenario_a_result_can_proceed(self):
        result, _ = self._run_scenario_a()
        assert result.can_proceed is True
