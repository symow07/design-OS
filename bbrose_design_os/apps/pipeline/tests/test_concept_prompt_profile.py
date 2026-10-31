"""concept_prompt_profile hook — parity-safe object-type directive (B3a).

The hook lets a target steer WHAT the concept depicts. It must be
byte-invisible for packaging (empty directive → the CD/PE user message is
identical to before) and inject a leading directive block only when a target
supplies one.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase

from apps.core.models import Brand
from apps.pipeline.agents.creative_director import CreativeDirectorAgent
from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
from apps.pipeline.models import DesignTask
from apps.pipeline.targets import get_target
from apps.pipeline.targets.base import DesignTarget


def _claude(json_data):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_data)
    resp = MagicMock()
    resp.content = [block]
    return resp


def _content_text(content):
    """CD/PE pass either a plain string or a list of blocks (vision + text);
    return the concatenated text either way."""
    if isinstance(content, str):
        return content
    return " ".join(b.get("text", "") for b in content if isinstance(b, dict))


class HookDefaultTests(TestCase):
    def test_packaging_directive_is_empty(self):
        # [his go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a carton] the
        # carton's directive is no longer empty: its concept is pictured so its design map can read its front, and this
        # test now pins that directive where it pinned the empty one (the prompt engineer's own parity tests below
        # still hold: an empty directive leaves a prompt byte-identical)
        from apps.pipeline.targets.packaging import CARTON_MAP_DIRECTIVE
        directive = get_target(DesignTarget.PACKAGING.value).concept_prompt_profile(None)
        assert directive == CARTON_MAP_DIRECTIVE and "FRONT panel square to the camera" in directive


class PromptEngineerDirectiveTests(TestCase):
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    def test_empty_directive_leaves_prompt_unchanged(self, mock_claude):
        mock_claude.return_value = _claude({"prompts": []})
        PromptEngineerAgent([{"name": "d"}], None).run()
        baseline = mock_claude.call_args.args[1]

        mock_claude.reset_mock()
        mock_claude.return_value = _claude({"prompts": []})
        PromptEngineerAgent([{"name": "d"}], None, target_directive="").run()
        assert mock_claude.call_args.args[1] == baseline          # byte-identical
        assert "Design target — READ FIRST" not in baseline

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    def test_directive_is_injected_when_set(self, mock_claude):
        mock_claude.return_value = _claude({"prompts": []})
        PromptEngineerAgent([{"name": "d"}], None,
                            target_directive="This is a BOTTLE, not a carton.").run()
        msg = mock_claude.call_args.args[1]
        assert "Design target — READ FIRST" in msg
        assert "This is a BOTTLE, not a carton." in msg


class CreativeDirectorDirectiveTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(brand=self.brand, task_text="a box")

    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_packaging_gets_explicit_target_guidance_without_a_directive(self, mock_claude):
        # Phase 2A-2 deliberately ended the B3 "empty directive → byte-identical" parity:
        # EVERY target now carries explicit guidance (no silent packaging default), so
        # packaging gets its TARGET_GUIDANCE line while the strategy directive stays absent.
        from apps.pipeline.design_direction_generator import TARGET_GUIDANCE
        mock_claude.return_value = _claude({"directions": []})
        CreativeDirectorAgent(self.task, self.brand.id).run()
        first_call = _content_text(mock_claude.call_args_list[0].args[1])
        assert "Design target — READ FIRST" in first_call
        assert TARGET_GUIDANCE["packaging"] in first_call
        assert "Design a JAR container." not in first_call

    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_directive_injected_when_set(self, mock_claude):
        mock_claude.return_value = _claude({"directions": []})
        CreativeDirectorAgent(self.task, self.brand.id,
                              target_directive="Design a JAR container.").run()
        # the FIRST call carries the brief; a repair retry deliberately does not restate it
        first_call = _content_text(mock_claude.call_args_list[0].args[1])
        assert "Design a JAR container." in first_call


class HisFindingOn119TheProductAloneTests(TestCase):
    """The owner's finding on design 119 (2026-10-03, OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "Concept
    pictures for drawing show the product alone: no props (no rose), straight-on, plain background. Styled shots are for
    mood only."."""

    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    def test_his_finding_on_119_a_concept_to_be_drawn_shows_the_product_alone(self, mock_claude):
        """Every concept the map draws from is asked for the product alone — a carton, a set's carton and every
        container form — and the prompt step's own brief, which asks for "one or two styling props", yields to it; a
        set's carton is no longer pictured "its front and one side visible"."""
        from apps.pipeline.agents.prompt_engineer import PROMPT_ENGINEER_SYSTEM
        from apps.pipeline.targets.container import MAP_ALONE, concept_directive
        from apps.pipeline.targets.packaging import CARTON_MAP_DIRECTIVE
        assert "no props" in MAP_ALONE and "for mood only" in MAP_ALONE
        assert MAP_ALONE in CARTON_MAP_DIRECTIVE
        assert all(MAP_ALONE in concept_directive(form, "") for form in ("bottle", "tube", "mascara", "compact"))
        assert MAP_ALONE in concept_directive(None, "a lovely thing")
        gift = get_target(DesignTarget.GIFT_SET.value).concept_prompt_profile(None)
        assert MAP_ALONE in gift and "one side visible" not in gift and "GIFT SET" in gift
        assert "pictured ALONE: then\n   NO props at all" in PROMPT_ENGINEER_SYSTEM
        mock_claude.return_value = _claude({"prompts": []})
        PromptEngineerAgent([{"name": "d"}], None, target_directive=CARTON_MAP_DIRECTIVE).run()
        system, message = mock_claude.call_args.args[0], _content_text(mock_claude.call_args.args[1])
        assert message.index(MAP_ALONE) < message.index("Product Profile") and "NO props at all" in system

    def test_his_finding_on_119_a_set_stopped_at_gate_one_writes_nothing_on_an_earlier_output(self):
        """A set's carton stopped at Gate 1 by its map makes no output, and its set's fit is not written on an output
        an earlier concept made."""
        from apps.pipeline.models import PackagingOutput
        from apps.pipeline.targets.gift_set import FIT_KEY, GiftSetTarget
        brand = Brand.objects.create(name="B", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="a set of three", status="gate_1_approved",
                                         design_target=DesignTarget.GIFT_SET.value)
        from apps.pipeline.models import GeneratedImage
        img = GeneratedImage.objects.create(task=task, direction_name="d", prompt_used="p", variation_number=1)
        earlier = PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet={"backend": "dieline"})
        aria = MagicMock()
        aria.task = task

        def stop(_self, aria_, _image):
            aria_.task.status = "awaiting_gate_1"
        with patch("apps.pipeline.targets.packaging.PackagingTarget.begin_output", stop):
            GiftSetTarget().begin_output(aria, MagicMock())
        earlier.refresh_from_db()
        assert FIT_KEY not in earlier.spec_sheet
