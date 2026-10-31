"""Phase 2A-1 — the `design_intent/1.0` contract.

The contract is the boundary every later slice builds to (generator, DIP adapter, UI), so
these tests pin its refusals as much as its accept path: unknown fields, missing fields,
non-distinct directions and unlabelled DIP references must all fail loudly now, not
surprise a later slice.
"""
from __future__ import annotations

import pytest

from apps.pipeline.design_intent import (
    DESIGN_INTENT_SCHEMA, DESIGN_TARGETS, DIRECTION_COUNT, REFERENCE_LABEL,
    DesignIntentError, build_design_brief, build_design_intent, build_dip_reference,
    build_direction, production_input_references, validate_directions_distinct,
)

from .direction_fixtures import valid_directions, valid_intent


def _brief(**changes):
    brief = {
        "brand": "BBROSE",
        "product_name": "Hyaluronic Dew Serum",
        "product_category": "skincare serum",
        "design_target": "packaging",
        "audience": "premium skincare buyers 25-40",
        "market": "CN + EU",
        "required_copy": ["BBROSE", "Hyaluronic Dew Serum", "30 ml"],
        "preferred_colors": ["soft pink", "glass clear"],
        "prohibited_motifs": ["cartoon characters"],
    }
    brief.update(changes)
    return brief


def _direction(n, **changes):
    direction = valid_directions()[n]
    direction.update(changes)
    return direction


def _directions():
    return valid_directions()


def _intent(**changes):
    intent = valid_intent()
    intent.update(changes)
    return intent


# === brief =======================================================================

def test_brief_validates_and_normalizes():
    brief = build_design_brief(_brief(brand="  BBROSE  "))
    assert brief["brand"] == "BBROSE"
    assert brief["design_target"] == "packaging"
    assert brief["required_copy"] == ["BBROSE", "Hyaluronic Dew Serum", "30 ml"]
    assert brief["prohibited_colors"] == []          # optional list defaults empty


def test_brief_refuses_unknown_missing_and_unsupported_target():
    with pytest.raises(DesignIntentError) as unknown:
        build_design_brief(_brief(reasoning="let me think step by step..."))
    assert unknown.value.code == "UNSUPPORTED_FIELD"
    with pytest.raises(DesignIntentError) as missing:
        build_design_brief(_brief(product_name=""))
    assert missing.value.code == "FIELD_REQUIRED"
    with pytest.raises(DesignIntentError) as target:
        build_design_brief(_brief(design_target="billboard"))
    assert target.value.code == "UNSUPPORTED_TARGET"


def test_design_targets_mirror_the_pipeline_target_choices():
    """The contract mirrors DesignTarget as literals to stay Django-free; this pins the
    mirror so it cannot drift silently."""
    from apps.pipeline.targets.base import DesignTarget
    assert set(DESIGN_TARGETS) == set(DesignTarget.values)


# === directions ==================================================================

def test_exactly_three_structurally_distinct_directions_are_required():
    validate_directions_distinct([build_direction(d) for d in _directions()])
    with pytest.raises(DesignIntentError) as count:
        validate_directions_distinct([build_direction(_direction(0))])
    assert count.value.code == "DIRECTION_COUNT_INVALID"


def test_three_colorways_of_one_layout_are_refused():
    shared = _direction(0)["layout_structure"]
    clones = [_direction(n, layout_structure=shared) for n in range(3)]
    with pytest.raises(DesignIntentError) as exc:
        validate_directions_distinct([build_direction(d) for d in clones])
    assert exc.value.code == "DUPLICATE_LAYOUT_STRUCTURE"


def test_duplicate_axes_and_names_are_refused_case_insensitively():
    dupes = _directions()
    dupes[1]["design_axis"] = "  TYPOGRAPHY-LED "
    with pytest.raises(DesignIntentError):
        validate_directions_distinct([build_direction(d) for d in dupes])


def test_direction_refuses_unknown_fields_and_requires_every_text_field():
    with pytest.raises(DesignIntentError) as unknown:
        build_direction(_direction(0, chain_of_thought="hidden reasoning"))
    assert unknown.value.code == "UNSUPPORTED_FIELD"
    with pytest.raises(DesignIntentError) as missing:
        build_direction(_direction(0, prompt_seed=""))
    assert missing.value.code == "FIELD_REQUIRED"
    with pytest.raises(DesignIntentError) as refusals:
        build_direction(_direction(0, prohibited_choices=[]))
    assert refusals.value.code == "FIELD_REQUIRED"


# === DIP references ==============================================================

def test_dip_references_must_be_labelled_descriptive_only():
    reference = build_dip_reference({
        "corpus_item_id": "8656cdaa-fe9a-453a-9761-1f5b13ad58f9",
        "label": REFERENCE_LABEL, "source": "MACHINE_DERIVED"})
    assert reference["blocked"] is False
    for bad in ({"label": "APPROVED_FOR_REUSE"}, {"label": ""},
                {"source": "TRUST_ME"}, {"source": ""}):
        raw = {"corpus_item_id": "x" * 8, "label": REFERENCE_LABEL,
               "source": "MACHINE_DERIVED"}
        raw.update(bad)
        with pytest.raises(DesignIntentError):
            build_dip_reference(raw)


def test_blocked_references_survive_as_blocked_and_never_become_inputs():
    direction = build_direction(_direction(0, dip_references=[{
        "corpus_item_id": "abc123", "label": REFERENCE_LABEL,
        "source": "MACHINE_DERIVED", "blocked": True,
        "note": "historical display; evidence integrity unresolved"}]))
    assert direction["dip_references"][0]["blocked"] is True
    document = build_design_intent(
        brief=_brief(), intent=_intent(),
        directions=[_direction(0, dip_references=[{
            "corpus_item_id": "abc123", "label": REFERENCE_LABEL,
            "source": "MACHINE_DERIVED", "blocked": True}]),
            _direction(1), _direction(2)])
    assert production_input_references(document) == []


# === the whole document ==========================================================

def test_full_document_assembles_deterministically():
    document = build_design_intent(
        brief=_brief(), intent=_intent(), directions=_directions())
    assert document["schema_version"] == DESIGN_INTENT_SCHEMA
    assert document["brief"]["brand"] == "BBROSE"
    assert len(document["directions"]) == DIRECTION_COUNT
    assert document["confidence"] == "MEDIUM"
    again = build_design_intent(
        brief=_brief(), intent=_intent(), directions=_directions())
    assert document == again


def test_intent_refuses_unknown_fields_and_invalid_confidence():
    with pytest.raises(DesignIntentError) as unknown:
        build_design_intent(brief=_brief(),
                            intent=_intent(internal_notes="scratchpad"),
                            directions=_directions())
    assert unknown.value.code == "UNSUPPORTED_FIELD"
    with pytest.raises(DesignIntentError) as confidence:
        build_design_intent(brief=_brief(), intent=_intent(confidence="CERTAIN"),
                            directions=_directions())
    assert confidence.value.code == "CONFIDENCE_INVALID"


def test_contract_is_pure_and_creates_no_authority():
    """No Django model import, no DecisionEvent, no permission — a data contract only."""
    import ast
    import inspect

    import apps.pipeline.design_intent as module
    tree = ast.parse(inspect.getsource(module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "django" not in imported
    assert "apps" not in imported          # no model, service or agent dependency


# === 2A-2-CORR-1: version freeze ==================================================

def _frozen_v1_0_document():
    """A literal design_intent/1.0 document in the exact Phase 2A-1 shape (62e22a4).
    Frozen: if this ever fails 1.0 validation, the freeze itself has been broken."""
    intent_fields = {
        "visual_objective": "Express hydration as suspended water.",
        "hierarchy": "product name first, brand mark second",
        "focal_point": "a single suspended droplet",
        "composition": "vertical thirds",
        "typography_strategy": "expressive serif display against quiet sans",
        "color_strategy": "porcelain neutrals with one accent",
        "motif_strategy": "one water motif per direction",
        "imagery_strategy": "no photography",
        "material_finish_direction": "soft-touch matte",
        "target_structural_guidance": "tall slim carton; front face is hero",
        "originality_constraints": ["no reuse of prior artwork"],
        "forbidden_choices": ["logo centered on a plain colored box"],
        "unresolved_questions": [],
        "source_references": ["brand context brief"],
        "confidence": "MEDIUM",
    }
    def direction(n, axis, layout, colors):
        return {
            "name": f"Direction {n}",
            "concept_statement": f"Concept {n} for the serum's water story.",
            "design_axis": axis,
            "layout_structure": layout,
            "color_system": colors,
            "typography": "modern serif for the name",
            "graphic_elements": "single droplet motif",
            "product_target_fit": "tall slim serum carton",
            "image_prompt": f"A tall slim carton, composition {n}...",
            "risks": "foil budget",
            "originality_notes": "evolved from house conventions",
        }
    return {
        "schema_version": "design_intent/1.0",
        "brief": build_design_brief({
            "brand": "BBROSE", "product_name": "Hyaluronic Dew Serum",
            "product_category": "skincare serum", "design_target": "packaging"}),
        **intent_fields,
        "directions": [
            direction(1, "typography-led", "oversized serif name fills the front",
                      "porcelain white with rose-gold type"),
            direction(2, "pattern-led", "engraved botanical pattern wraps all faces",
                      "deep botanical green with blush accents"),
            direction(3, "material-led", "full-bleed blind-embossed droplet relief",
                      "monochrome nude with a gloss droplet"),
        ],
    }


def test_v1_0_is_frozen_and_historical_documents_stay_valid():
    from apps.pipeline.design_intent import (
        DESIGN_INTENT_SCHEMA_V1_0, validate_design_intent_document,
    )
    document = _frozen_v1_0_document()
    assert validate_design_intent_document(document) == DESIGN_INTENT_SCHEMA_V1_0
    assert DESIGN_INTENT_SCHEMA_V1_0 == "design_intent/1.0"
    assert DESIGN_INTENT_SCHEMA == "design_intent/1.2"


def test_v1_1_documents_validate_and_declare_1_1():
    """§BH68(a): 1.1 is FROZEN — a plan written before the declared hierarchy family validates exactly as it did,
    because the resume path and direction selection re-validate a persisted plan against its own version."""
    from apps.pipeline.design_intent import DESIGN_INTENT_SCHEMA_V1_1, validate_design_intent_document
    legacy = [{k: v for k, v in d.items() if k != "hierarchy_family"} for d in _directions()]
    document = build_design_intent(
        brief=_brief(), intent=_intent(), directions=legacy, version=DESIGN_INTENT_SCHEMA_V1_1)
    assert document["schema_version"] == "design_intent/1.1"
    assert validate_design_intent_document(document) == "design_intent/1.1"


def test_bh68a_v1_2_documents_declare_the_hierarchy_family_and_the_versions_never_interchange():
    """§BH68(a): 1.2 carries each direction's DECLARED hierarchy family; a 1.1 plan declaring 1.2 is refused for the
    missing declaration, and a 1.2 plan declaring 1.1 for the field 1.1 never had."""
    from apps.pipeline.design_intent import (HIERARCHY_FAMILY_NOT_DECLARED, DesignIntentError,
                                             validate_design_intent_document)
    document = build_design_intent(brief=_brief(), intent=_intent(), directions=_directions())
    assert document["schema_version"] == "design_intent/1.2"
    assert [d["hierarchy_family"] for d in document["directions"]] == ["NAME_FIRST", "MOTIF_FIRST", "MATERIAL_FIRST"]
    assert validate_design_intent_document(document) == "design_intent/1.2"
    as_1_1 = dict(document, schema_version="design_intent/1.1")
    with pytest.raises(DesignIntentError) as down:
        validate_design_intent_document(as_1_1)
    assert down.value.code == "UNSUPPORTED_FIELD"
    stripped = dict(document, directions=[{k: v for k, v in d.items() if k != "hierarchy_family"}
                                          for d in document["directions"]])
    with pytest.raises(DesignIntentError) as up:
        validate_design_intent_document(stripped)
    assert up.value.code == HIERARCHY_FAMILY_NOT_DECLARED


def test_schema_declarations_cannot_be_interchanged():
    from apps.pipeline.design_intent import validate_design_intent_document
    # a 1.1 payload declaring 1.0: the frozen validator refuses the new fields
    rich = build_design_intent(brief=_brief(), intent=_intent(),
                               directions=_directions())
    rich["schema_version"] = "design_intent/1.0"
    with pytest.raises(DesignIntentError) as down:
        validate_design_intent_document(rich)
    assert down.value.code in ("UNSUPPORTED_FIELD", "FIELD_REQUIRED")
    # a 1.0 payload declaring 1.1: the current validator refuses the missing fields
    old = _frozen_v1_0_document()
    old["schema_version"] = "design_intent/1.1"
    with pytest.raises(DesignIntentError):
        validate_design_intent_document(old)
    # an unknown version is refused outright
    old["schema_version"] = "design_intent/2.0"
    with pytest.raises(DesignIntentError) as unknown:
        validate_design_intent_document(old)
    assert unknown.value.code == "UNSUPPORTED_SCHEMA_VERSION"


def test_generator_result_pins_the_output_schema_and_projection_works_from_1_1():
    from apps.pipeline.design_direction_generator import (
        GENERATOR_SCHEMA, generate_design_directions, to_legacy_direction,
    )
    from .direction_fixtures import valid_document

    class OneShot:
        def __call__(self, system, content):
            import json as _json
            return _json.dumps(valid_document()), "fake:model"

    assert GENERATOR_SCHEMA == "design_direction_generator/1.2"
    result = generate_design_directions(
        brief={"brand": "BBROSE", "product_name": "X", "product_category": "serum",
               "design_target": "packaging"}, call_model=OneShot())
    assert result.ok
    assert result.output_schema == "design_intent/1.2"
    legacy = to_legacy_direction(result.document["directions"][0])
    assert set(legacy) == {"name", "rationale", "palette", "material",
                           "finish_combination", "connected_to", "design_axis",
                           "subject_story", "prompt_seed"}
