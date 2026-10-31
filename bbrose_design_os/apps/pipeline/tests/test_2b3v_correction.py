"""Phase 2B-3V defect-correction regression tests.

Covers the run-1 failure mode and its fix: schema + content codes must
CO-SURFACE in one validation pass (so the single bounded repair can fix a
missing field AND a photographic direction together); a photographic printed
surface still fails (validator un-weakened); a concept-render photograph of the
physical product does not fail by itself; native_reconstruction_plan is
required; the repair guidance carries every code and demands full replacement;
and build_design_context restores grounding for an authorized reviewer without
leaking a path-like label.
"""
from __future__ import annotations

import copy

from apps.pipeline import design_direction_generator as gen
from apps.pipeline.tests.direction_fixtures import valid_document


def _brief():
    return {"brand": "BBROSE", "product_name": "Rosé Nectar Lip Gloss",
            "product_category": "CO", "design_target": "product_container"}


def _photographic(direction):
    direction["design_axis"] = (
        "Image-led — a full-bleed macro photograph is the entire printed surface")


# --- the difference-maker: schema + content co-surface ----------------------

def test_validate_cosurfaces_schema_and_raster_codes():
    doc = copy.deepcopy(valid_document())
    _photographic(doc["directions"][0])            # content defect
    del doc["directions"][0]["native_reconstruction_plan"]   # schema defect
    document, codes, _ = gen._validate(_brief(), doc)
    assert document is None
    joined = " ".join(codes)
    assert "FIELD_REQUIRED" in joined                          # schema code
    assert "native_reconstruction_plan" in joined
    assert any(c.startswith("PRODUCTION_RASTER_DEPENDENCY") for c in codes)  # content


def test_photographic_printed_surface_still_fails():
    doc = copy.deepcopy(valid_document())
    _photographic(doc["directions"][0])
    document, codes, _ = gen._validate(_brief(), doc)
    assert document is None
    assert any(c.startswith("PRODUCTION_RASTER_DEPENDENCY") for c in codes)


def test_liquid_glass_vector_language_does_not_imply_raster():
    # §7: "liquid-glass / shine / dew / petals" rendered as VECTOR primitives is
    # not a raster dependency. The un-weakened validator flags affirmative
    # PHOTOGRAPHIC terms in the printed-decoration fields, not sensory language;
    # the fix is generation-side (keep photo terms out of those fields), and a
    # vector direction with no photo terms passes.
    doc = copy.deepcopy(valid_document())
    d = doc["directions"][0]
    d["design_axis"] = "vector-illustration-led — a built liquid-glass field"
    d["graphic_elements"] = ("translucent vector gradients, liquid-veil Bézier "
                             "ribbons, radiance lines and abstract dew droplets")
    d["imagery_approach"] = "no photography on the printed surface; vector motifs only"
    d["native_reconstruction_plan"] = ("live serif type; liquid-veil ribbon motif; "
        "translucent gradient fields; front decoration surface; spot-UV dew mask; "
        "no concept-render-only elements; printed decoration needs zero decorative rasters")
    document, codes, _ = gen._validate(_brief(), doc)
    assert document is not None, codes            # vector-safe → passes
    assert codes == []


def test_native_reconstruction_plan_is_required():
    doc = copy.deepcopy(valid_document())
    del doc["directions"][1]["native_reconstruction_plan"]
    document, codes, _ = gen._validate(_brief(), doc)
    assert document is None
    assert any("FIELD_REQUIRED" in c and "native_reconstruction_plan" in c
               for c in codes)


def test_valid_vector_document_passes():
    document, codes, _ = gen._validate(_brief(), valid_document())
    assert document is not None and codes == []
    for d in document["directions"]:
        assert d["native_reconstruction_plan"]


# --- repair guidance --------------------------------------------------------

def test_repair_message_carries_all_codes_and_demands_replacement():
    codes = ["FIELD_REQUIRED: native_reconstruction_plan is required",
             "PRODUCTION_RASTER_DEPENDENCY:direction[0]"]
    msg = gen._repair_message(codes, raw_text="{}", directions=None)
    assert "native_reconstruction_plan" in msg
    assert "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in msg
    assert "REPLACE" in msg.upper()
    assert "vector" in msg.lower()
    # both layers named
    # [the owner's second answer of 2026-09-25: the raster layer's header names no photograph word — it read
    # "Photographic-decoration failures" until then]
    assert "Schema failures" in msg and "Raster-dependency failures" in msg


# --- generator: bounded repair + no other provider work ---------------------

def test_failed_planning_uses_two_calls_and_no_other_provider():
    calls = {"n": 0}

    def stub(system, content):
        calls["n"] += 1
        import json
        bad = copy.deepcopy(valid_document())
        _photographic(bad["directions"][0])
        del bad["directions"][0]["native_reconstruction_plan"]
        return json.dumps(bad), "anthropic:stub"

    result = gen.generate_design_directions(brief=_brief(), call_model=stub)
    assert result.ok is False
    assert result.attempts == 2                    # 1 + bounded repair, no more
    assert calls["n"] == 2                          # only the CD model, twice
    joined = " ".join(result.codes)
    assert "PRODUCTION_RASTER_DEPENDENCY" in joined  # content code surfaced


def test_safe_label_recovers_clean_label_from_path_like_value():
    # §5: a path-like display_label must not crash / empty the whole context —
    # it recovers a clean, non-path-like basename instead of leaking or dropping
    from apps.pipeline.design_context import _is_path_like, _safe_label
    label = _safe_label({"display_label": "references/ref_YB-1030.png",
                         "item_kind": "HISTORICAL_DESIGN"}, 80)
    assert label and not _is_path_like(label)
    assert ".png" not in label and "/" not in label
    # a clean label passes straight through
    assert _safe_label({"display_label": "Shine Misty Lip Gloss"}, 80) == \
        "Shine Misty Lip Gloss"
    # nothing usable → a bounded generic label, never empty
    assert _safe_label({"item_kind": "FONT"}, 80) == "unlabelled FONT"


def test_wording_only_photo_still_fails():
    # adding the word "vector" to a photographic surface does not pass
    doc = copy.deepcopy(valid_document())
    doc["directions"][0]["design_axis"] = (
        "vector-inspired but a full-bleed macro photograph is the printed surface")
    document, codes, _ = gen._validate(_brief(), doc)
    assert document is None
    assert any(c.startswith("PRODUCTION_RASTER_DEPENDENCY") for c in codes)
