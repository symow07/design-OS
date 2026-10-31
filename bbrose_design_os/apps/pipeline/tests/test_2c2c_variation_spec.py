"""2C-2C — project-mandated Gate-1 variation specification.

A composite-project container task may carry human-mandated variation
identities, contract directives and a strict prompt-attempt cap in
project.metadata['gate1_variation_spec']; every task without a project or
spec keeps the 2B-3V module constants byte-for-byte (task #51 regressions)."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignProject, DesignTask
from apps.pipeline.services import container_gate1 as cg1
from apps.pipeline.targets import get_target

pytestmark = pytest.mark.django_db
User = get_user_model()

SPEC_IDS = ["A_AMBER_NOCTURNE", "B_ROSE_SMOKE", "C_NOCTURNE_APOTHECARY"]


class _AriaStub:
    def __init__(self, task):
        self.task = task

    def _product_profile(self):
        return {}

    def _log_for(self, agent):
        return lambda *a, **k: None


def _world(with_spec):
    brand = Brand.objects.create(name="BBROSE", master_brief="x")
    product = Product.objects.create(
        brand=brand, product_id="BBR-SK-201", name="Rose Damascena Night "
        "Repair Oil", category="SK", year=2026, product_type="carton")
    project = None
    if with_spec is not None:
        project = DesignProject.objects.create(
            brand=brand, product=product, brief="b",
            design_target="complete_product", status="container",
            metadata=({"gate1_variation_spec": with_spec} if with_spec
                      else {}))
    task = DesignTask.objects.create(
        brand=brand, product=product, task_text="b",
        design_target="product_container", status="queued", project=project)
    return task


def _captured_kwargs(task):
    target = get_target("product_container")
    with patch("apps.pipeline.services.gate1_prompts."
               "build_regeneration_prompts") as brp:
        brp.return_value = "SENTINEL"
        result = target.gate1_variation_plan(
            _AriaStub(task), {"direction_id": "d1", "name": "n"})
    assert result == "SENTINEL"
    return brp.call_args.kwargs


def test_project_spec_overrides_identities_directives_and_attempts():
    spec = {"variation_identities": SPEC_IDS,
            "richness_directives": "VARIATION A — AMBER NOCTURNE: ...",
            "max_prompt_attempts": 1}
    kwargs = _captured_kwargs(_world(spec))
    assert kwargs["variation_identities"] == SPEC_IDS
    assert kwargs["identity_slots"] is None          # §BH67(c)4: a person's own identities are enforced exactly
    assert kwargs["richness_directives"].startswith("VARIATION A — AMBER")
    assert kwargs["max_attempts"] == 1


def test_no_project_keeps_2b3v_constants():
    # §BH67(c)4, 2026-09-24: "The July petal-window directive stops being forced onto variation 1." With no person's
    # identities the three are SLOTS the variations name themselves — the July identities are no longer the default
    kwargs = _captured_kwargs(_world(None))
    assert kwargs["variation_identities"] == ()
    assert kwargs["identity_slots"] == cg1.CONTAINER_VARIATION_SLOTS == ("A", "B", "C")
    assert kwargs["richness_directives"] == cg1.CONTAINER_GATE1_DIRECTIVES
    assert kwargs["max_attempts"] is None


def test_project_without_spec_keeps_constants():
    kwargs = _captured_kwargs(_world({}))
    assert kwargs["variation_identities"] == ()                                # §BH67(c)4: slots, as above
    assert kwargs["identity_slots"] == cg1.CONTAINER_VARIATION_SLOTS
    assert kwargs["max_attempts"] is None


def test_his_answer_the_briefs_colours_reach_the_container_concepts_making():
    """His answer 1 of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6badb27): "the brief's colours go into the
    step that MAKES the concept picture, not only the drawing." A container's Gate-1 pictures are made from the variation
    contract's prompts: the product block they are written from carries the brief's colours under his ruling's heading;
    with a brief that names none it carries nothing new."""
    from apps.pipeline.services.product_profile import BRIEF_COLOURS_HEADING

    class _Coloured(_AriaStub):
        def _product_profile(self):
            return {"preferred_colors": ["hot pink", "soft pink", "cream"], "prohibited_colors": ["black"]}
    task = _world(None)
    target = get_target("product_container")
    with patch("apps.pipeline.services.gate1_prompts.build_regeneration_prompts") as brp:
        brp.return_value = "SENTINEL"
        target.gate1_variation_plan(_Coloured(task), {"direction_id": "d1", "name": "n"})
    block = brp.call_args.kwargs["product_block"]
    assert BRIEF_COLOURS_HEADING in block and "Colours: hot pink; soft pink; cream" in block
    assert "Never a dominant colour: black" in block
    assert BRIEF_COLOURS_HEADING not in _captured_kwargs(task)["product_block"]
