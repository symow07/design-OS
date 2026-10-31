"""Product-identification structural provenance (Phase 2A-6D-CORR-2 §1/§9).

The task-#50 retry failed UNCONFIRMED_STRUCTURE_ASSUMED because the
identification step INVENTED "small upright rectangular tuck-end carton"
for a brief that states no closure, dieline, dimensions or template — and
that guess flowed into the generation context as authoritative structure.
These tests pin the provenance contract: only EXPLICIT_USER_FACT or
VERIFIED_PRODUCT_RECORD structure reaches generation; inference is
quarantined in a diagnostic field; unknown structure is stated as UNKNOWN.
"""
from __future__ import annotations

from types import SimpleNamespace

from apps.pipeline.services.product_profile import (
    STRUCTURE_EXPLICIT_USER_FACT,
    STRUCTURE_INFERRED_NONAUTHORITATIVE,
    STRUCTURE_UNKNOWN,
    STRUCTURE_VERIFIED_PRODUCT_RECORD,
    UNKNOWN_STRUCTURE_TEXT,
    classify_structural_provenance,
    normalize_identified_profile,
    profile_text,
    resolve_product_profile,
)

#: Exactly what the identification model returned for task #50 (log 796),
#: minus provider transport — the deterministic boundary's real input.
TASK50_IDENTIFICATION = {
    "name": "Baked Powder",
    "category": "CO",
    "product_type": "face powder / baked powder",
    "physical_format": ("small upright rectangular tuck-end carton "
                        "(round baked powder compact inside)"),
    "required_copy": ["BBROSE", "BAKED POWDER", "POLVO HORNEADO",
                      "LUMINOSIDAD SUAVE"],
    "preferred_colors": ["light blush pink", "light sky blue", "light peach",
                         "soft mint", "ivory"],
    "prohibited_colors": ["black as dominant", "navy as dominant",
                          "dark brown as dominant"],
    "prohibited_motifs": ["powder spiral", "compact photograph"],
    "production_constraints": [
        "decorative coverage no more than 20%",
        "structure unconfirmed — no dimensions supplied"],
}

#: Trimmed replica of the actual Baked Powder brief: required copy, pastel
#: permissions, the 20% cap, prohibited motifs, finishes — and NO structural
#: facts (the real task_text contains no "tuck", no dimensions).
TASK50_BRIEF = """Create a new coordinated outer-packaging design for BBROSE Baked Powder.
Brand: BBROSE
Product name: BAKED POWDER
Spanish product name: POLVO HORNEADO
Tagline: LUMINOSIDAD SUAVE
Permitted pastel base colors: light blush pink, light sky blue, light peach, soft mint, ivory.
Black, navy or dark brown must never be dominant.
Decorative coverage no more than 20% of the visible area.
Prohibited motifs: powder spiral, compact photograph.
Finishes: restrained gold stamping, shallow embossing, selective spot UV.
The carton structure is not confirmed: no dimensions, no template, no closure
system has been decided. Do not assume one.
"""


def _stub_task(text=TASK50_BRIEF, product=None):
    return SimpleNamespace(product=product, campaign=None,
                           task_text=text, design_target="packaging")


class TestStructuralProvenance:
    def test_inferred_tuck_end_cannot_become_confirmed_structure(self):
        provenance, authoritative, quarantined = classify_structural_provenance(
            TASK50_IDENTIFICATION["physical_format"], TASK50_BRIEF)
        assert provenance == STRUCTURE_INFERRED_NONAUTHORITATIVE
        assert authoritative == ""
        assert "tuck-end" in quarantined

    def test_explicit_user_supplied_tuck_end_passes_through(self):
        task_text = TASK50_BRIEF + "\nThe carton is a tuck-end carton."
        provenance, authoritative, quarantined = classify_structural_provenance(
            "small upright tuck-end carton", task_text)
        assert provenance == STRUCTURE_EXPLICIT_USER_FACT
        assert "tuck-end" in authoritative
        assert quarantined == ""

    def test_dimensions_need_user_substantiation_too(self):
        provenance, authoritative, _ = classify_structural_provenance(
            "upright carton 100 mm tall", TASK50_BRIEF)
        assert provenance == STRUCTURE_INFERRED_NONAUTHORITATIVE
        assert authoritative == ""

    def test_nonstructural_form_guess_is_still_quarantined(self):
        provenance, authoritative, quarantined = classify_structural_provenance(
            "small square low carton", TASK50_BRIEF)
        assert provenance == STRUCTURE_INFERRED_NONAUTHORITATIVE
        assert authoritative == ""
        assert quarantined == "small square low carton"

    def test_unknown_structure_remains_unknown(self):
        assert classify_structural_provenance("", TASK50_BRIEF) == (
            STRUCTURE_UNKNOWN, "", "")

    def test_verified_product_record_passes_through(self):
        product = SimpleNamespace(name="Baked Powder", category="CO",
                                  product_type="face powder",
                                  dimensions="90 × 90 × 25 mm tuck-end carton")
        profile = resolve_product_profile(_stub_task(product=product))
        assert profile["structural_provenance"] == \
            STRUCTURE_VERIFIED_PRODUCT_RECORD
        assert profile["physical_format"] == product.dimensions
        assert "Carton form:" in profile_text(profile)

    def test_record_without_dimensions_is_unknown(self):
        product = SimpleNamespace(name="Baked Powder", category="CO",
                                  product_type="face powder", dimensions="")
        profile = resolve_product_profile(_stub_task(product=product))
        assert profile["structural_provenance"] == STRUCTURE_UNKNOWN
        assert UNKNOWN_STRUCTURE_TEXT in profile_text(profile)


class TestGenerationContextExclusion:
    def _task50_profile(self):
        return normalize_identified_profile(TASK50_IDENTIFICATION, TASK50_BRIEF)

    def test_profile_quarantines_the_inference(self):
        profile = self._task50_profile()
        assert profile["physical_format"] == ""
        assert profile["structural_provenance"] == \
            STRUCTURE_INFERRED_NONAUTHORITATIVE
        assert "tuck-end" in profile["inferred_non_authoritative_context"]

    def test_profile_text_states_unknown_and_never_the_inference(self):
        text = profile_text(self._task50_profile())
        assert "tuck" not in text.lower()
        assert "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED" in text
        for fact in ("width UNKNOWN", "depth UNKNOWN", "height UNKNOWN",
                     "template UNKNOWN", "panel sequence UNKNOWN",
                     "closure system UNKNOWN"):
            assert fact in text

    def test_product_context_excludes_the_inference(self):
        from apps.pipeline.services.brand_context import build_product_context
        context = build_product_context(_stub_task(), profile=self._task50_profile())
        assert "tuck" not in context.lower()
        assert "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED" in context

    def test_legacy_inferred_profile_without_provenance_is_quarantined(self):
        legacy = {"name": "Baked Powder", "source": "inferred",
                  "physical_format": "small upright tuck-end carton"}
        text = profile_text(legacy)
        assert "tuck" not in text.lower()
        assert UNKNOWN_STRUCTURE_TEXT in text

    def test_task50_generation_context_fixture(self):
        """§9: the original Baked Powder brief through the deterministic
        profile/context boundary only — no provider call. The assembled
        generation message must carry the brief's real constraints and no
        invented structure."""
        from apps.pipeline.agents.creative_director import CreativeDirectorAgent
        from apps.pipeline.design_intent import build_design_brief
        from apps.pipeline.design_direction_generator import _user_message
        from apps.pipeline.services.brand_context import build_product_context

        profile = self._task50_profile()
        task = _stub_task()
        agent = CreativeDirectorAgent(task, brand_id=0, product_profile=profile)
        brief = build_design_brief(agent._brief())
        message = _user_message(
            brief=brief, brand_context="",
            product_context=build_product_context(task, profile=profile),
            target_profile="", reference_summaries=[task.task_text],
            dip_context=[], revision_feedback="")

        low = message.lower()
        for required in ("bbrose", "baked powder", "polvo horneado",
                         "luminosidad suave", "light blush pink",
                         "light sky blue", "light peach", "soft mint",
                         "black as dominant",
                         "decorative coverage no more than 20%",
                         "powder spiral", "gold stamping"):
            assert required in low, f"missing from generation context: {required}"
        assert "structural_template_confirmation_required" in low
        assert "tuck" not in low
        assert "auto-lock" not in low
        import re
        assert not re.search(r"\b\d+(?:\.\d+)?\s*(?:mm|cm)\b", low)
        assert brief["dimensions"] == ""
