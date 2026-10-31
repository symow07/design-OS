"""Vector design-language library + panel roles (Phase 2A-6 §7–8).

The contract: a bounded set of reconstructable primitives, editable
parameters, per-panel-role variation — and a hard stop instead of a raster
when a direction is outside the library.
"""
from __future__ import annotations

import pytest

from apps.dielines.geometry.engine import calculate_dieline
from apps.dielines.validators.schema import DielineInputJSON
from apps.ire.compose_vector_art import (
    NATIVE_VECTOR_RECONSTRUCTION,
    TEMPORARY_VISUAL_REFERENCE_ONLY,
    VectorArtStyle,
    compose_vector_art_graph,
)
from apps.ire.design_language import (
    DEFAULT_EMPHASIS,
    LanguageParameters,
    ROLE_BACK,
    ROLE_FRONT,
    ROLE_GLUE_FLAP,
    Swatch,
    VectorReconstructionReviewRequired,
    get_language,
    panel_role,
    resolve_language,
    supported_languages,
)
from apps.ire.graph import Group, Path

LIQUID_DIRECTION = {
    "name": "Liquid Veil",
    "design_axis": "image/texture-led",
    "concept_statement": "a full-panel engraved liquid pour",
    "graphic_elements": "flowing fluid linework, silk drape, gradient veil",
}
STRATA_DIRECTION = {
    "name": "Skin Strata",
    "design_axis": "material-led",
    "concept_statement": "three horizontal strata bands",
    "graphic_elements": "geometric material band stack, architectural blocks",
}
UNSUPPORTED_DIRECTION = {
    "name": "Hand-painted Portrait",
    "design_axis": "illustration-led",
    "concept_statement": "a photorealistic oil portrait of a model",
    "graphic_elements": "brushwork, human face, painterly chiaroscuro",
}


def _coords():
    return calculate_dieline(DielineInputJSON(
        template="skynte_foundation_tuck_carton", unit="mm",
        dimensions={"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0},
        print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        construction={"glue_tab_mm": 10.0, "board_thickness_mm": 0.30,
                      "thickness_compensation": True},
        metadata={"product_name": "P", "product_type": "t"},
    ))


class TestLanguageResolution:
    def test_liquid_direction_resolves_to_liquid_veil(self):
        assert resolve_language(LIQUID_DIRECTION).name == "liquid_veil"

    def test_strata_direction_resolves_to_strata_field(self):
        assert resolve_language(STRATA_DIRECTION).name == "strata_field"

    def test_unsupported_direction_fails_closed(self):
        with pytest.raises(VectorReconstructionReviewRequired) as exc:
            resolve_language(UNSUPPORTED_DIRECTION)
        assert exc.value.code == "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"
        assert exc.value.supported          # tells the designer what IS supported
        assert "must NOT be printed" in str(exc.value)

    def test_empty_direction_fails_closed(self):
        with pytest.raises(VectorReconstructionReviewRequired):
            resolve_language({})

    def test_explicit_language_overrides_matching(self):
        assert resolve_language(UNSUPPORTED_DIRECTION,
                                explicit="ruled_field").name == "ruled_field"

    def test_unknown_explicit_language_fails_closed(self):
        with pytest.raises(VectorReconstructionReviewRequired):
            get_language("photoreal_airbrush")

    def test_resolution_is_deterministic(self):
        assert {resolve_language(LIQUID_DIRECTION).name for _ in range(5)} == {
            "liquid_veil"}

    def test_style_for_direction_never_rasterizes(self):
        with pytest.raises(VectorReconstructionReviewRequired):
            VectorArtStyle.for_direction(UNSUPPORTED_DIRECTION)
        style = VectorArtStyle.for_direction(LIQUID_DIRECTION, seed=47)
        assert style.mode == NATIVE_VECTOR_RECONSTRUCTION
        assert style.seed == 47


class TestPrimitives:
    @pytest.mark.parametrize("lang", [lg.name for lg in supported_languages()])
    def test_every_language_builds_native_paths(self, lang):
        params = LanguageParameters(seed=1)
        nodes = get_language(lang).build(
            (0.0, 0.0, 42.0, 140.0), params, ROLE_FRONT,
            lambda v: v, lambda v: v)
        # native paths, possibly organized in named editable groups
        # (2A-6E-CORR-7: powder_constellation groups its particles so a
        # designer can thin/recolor/delete whole regions)
        from apps.ire.graph import Group

        def _flat(items):
            for item in items:
                if isinstance(item, Group):
                    yield from _flat(item.children)
                else:
                    yield item
        flattened = list(_flat(nodes))
        assert flattened or lang == "quiet_ground"   # gradient-only language
        assert all(isinstance(n, Path) for n in flattened)
        assert all(n.fill or n.stroke for n in flattened)
        if lang != "quiet_ground":
            assert nodes, f"{lang} produced nothing"

    def test_parameters_are_editable_and_effective(self):
        lang = get_language("liquid_veil")
        box = (0.0, 0.0, 42.0, 140.0)
        sparse = lang.build(box, LanguageParameters(seed=1, density=0.5),
                            ROLE_FRONT, lambda v: v, lambda v: v)
        dense = lang.build(box, LanguageParameters(seed=1, density=3.0),
                           ROLE_FRONT, lambda v: v, lambda v: v)
        assert len(dense) > len(sparse)

    def test_swatch_recolor_updates_artwork(self):
        from apps.ire.design_language import DEFAULT_SWATCHES
        import dataclasses
        recolored = dataclasses.replace(
            DEFAULT_SWATCHES,
            line_light=Swatch("LINE_LIGHT", "#123456", (0.9, 0.7, 0.2, 0.1)))
        params = LanguageParameters(seed=1, swatches=recolored)
        nodes = get_language("liquid_veil").build(
            (0.0, 0.0, 42.0, 140.0), params, ROLE_FRONT,
            lambda v: v, lambda v: v)
        hexes = {n.stroke.color.to_hex() for n in nodes if n.stroke}
        assert "#123456" in hexes

    def test_every_swatch_carries_cmyk(self):
        for sw in LanguageParameters().swatches.all():
            assert sw.color().cmyk is not None

    def test_radial_lines_draw_rays_from_one_centre_in_the_motifs_own_colour_only(self):
        """[the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start
        testing"): "The lid is missing the concept's rule, ring and radial lines."] Rays from the region's centre, each
        a straight cubic beginning where the rays stop touching (n·w/2π), each ending in its node where the words say
        so, their reach tapering; drawn in ``line_light`` ONLY — task 110's sourced motif palette puts the motif's
        Blush there and the colour field's Deep Rose in ``line_deep``, and no ray or node takes the Deep Rose. A
        near-quiet surface carries no rays."""
        import math
        from apps.ire.compose_container import _motif_swatches
        from apps.ire.design_language import RADIAL_NODE_DIAMETER_MM, gen_radial_lines
        swatches = _motif_swatches({"motif": ["#F2C4CE", "#8B3A52"], "ink": "#8B3A52"})
        assert (swatches.line_light.hex, swatches.line_deep.hex) == ("#F2C4CE", "#8B3A52")
        params = LanguageParameters(seed=1, swatches=swatches)
        import random
        radial = {"rays": 72, "nodes": True, "taper": True, "opacity": 0.5}
        nodes = gen_radial_lines((0.0, 0.0, 90.0, 70.0), params, random.Random(3), lambda v: v, lambda v: v,
                                 radial=radial)
        rays = [n for n in nodes if n.name.startswith("radial-ray-")]
        dots = [n for n in nodes if n.name.startswith("radial-node-")]
        assert len(rays) == len(dots) == 72
        assert {n.stroke.color.to_hex() for n in rays} | {n.fill.color.to_hex() for n in dots} == {"#F2C4CE"}
        assert {n.stroke.opacity for n in rays} | {n.fill.opacity for n in dots} == {0.5}
        inner = 72 * params.stroke_min_mm / (2.0 * math.pi)
        reach = []
        for ray in rays:
            (x0, y0), (x1, y1) = (ray.segments[0].x, ray.segments[0].y), (ray.segments[-1].x, ray.segments[-1].y)
            assert abs(math.hypot(x0 - 45.0, y0 - 35.0) - inner) < 1e-9          # from one centre, not a blot
            assert abs((x1 - 45.0) * (y0 - 35.0) - (y1 - 35.0) * (x0 - 45.0)) < 1e-6   # straight out along its line
            reach.append(math.hypot(x1 - 45.0, y1 - 35.0))
        assert max(reach) - min(reach) > 10.0                                   # "density tapering toward the rim"
        assert all(abs(_d_w - RADIAL_NODE_DIAMETER_MM) < 1e-9 for _d_w in
                   (max(p.x for p in d.segments if hasattr(p, "x")) - min(p.x for p in d.segments if hasattr(p, "x"))
                    for d in dots))
        quiet = gen_radial_lines((0.0, 0.0, 90.0, 70.0), LanguageParameters(density=0.02, swatches=swatches),
                                 random.Random(3), lambda v: v, lambda v: v, radial=radial)
        assert quiet == []


class TestPanelRoles:
    def test_role_mapping(self):
        assert panel_role("front") == ROLE_FRONT
        assert panel_role("back") == ROLE_BACK
        assert panel_role("glue_tab") == ROLE_GLUE_FLAP
        assert panel_role("top-left-dust") == "dust_flap"
        assert panel_role("top-back-tuck") == "top_flap"
        assert panel_role("bottom-front-tuck") == "bottom_flap"

    def test_front_is_strongest_back_is_quiet(self):
        assert DEFAULT_EMPHASIS[ROLE_FRONT] == 1.0
        assert DEFAULT_EMPHASIS[ROLE_BACK] == 0.0
        assert DEFAULT_EMPHASIS["side_left"] < DEFAULT_EMPHASIS[ROLE_FRONT]
        assert DEFAULT_EMPHASIS[ROLE_GLUE_FLAP] < DEFAULT_EMPHASIS["side_left"]

    def test_panels_are_not_the_same_artwork_tiled(self):
        """Each surface generates with its own seed — side_left and
        side_right must not be identical groups (§8)."""
        doc = compose_vector_art_graph(
            _coords(), style=VectorArtStyle(), product_name="P")
        groups = {g.name: g for g in doc.find_role("decoration")
                  if isinstance(g, Group)}
        left = groups.get("liquid_veil-side_left")
        right = groups.get("liquid_veil-side_right")
        assert left is not None and right is not None
        assert left.model_dump_json() != right.model_dump_json()

    def test_emphasis_thins_flaps_relative_to_front(self):
        doc = compose_vector_art_graph(
            _coords(), style=VectorArtStyle(), product_name="P")
        groups = {g.name: len(g.children) for g in doc.find_role("decoration")
                  if isinstance(g, Group)}
        front = groups.get("liquid_veil-front", 0)
        glue = groups.get("liquid_veil-glue_tab", 0)
        assert front > glue

    def test_document_declares_the_reference_only_role(self):
        doc = compose_vector_art_graph(
            _coords(), style=VectorArtStyle(), product_name="P")
        assert doc.metadata["artwork_mode"] == NATIVE_VECTOR_RECONSTRUCTION
        assert doc.metadata["concept_render_role"] == TEMPORARY_VISUAL_REFERENCE_ONLY


class TestEditabilityMetrics:
    def test_inventory_reports_editability_evidence(self):
        doc = compose_vector_art_graph(
            _coords(), style=VectorArtStyle(), product_name="P",
            subtitle="s", panel_info={"net_weight": "30 ml"})
        inv = doc.metadata["inventory"]
        for key in ("vector_object_count", "raster_count", "raster_area_mm2",
                    "raster_area_fraction", "decorative_vector_count",
                    "live_text_count", "outlined_text_count",
                    "clip_mask_count", "gradient_count", "swatches",
                    "layer_groups", "panel_roles"):
            assert key in inv, f"missing editability metric: {key}"
        assert inv["gradient_count"] >= 1
        assert inv["clip_mask_count"] >= 1
        assert inv["raster_area_fraction"] == 0.0     # no rasters at all
        assert len(inv["swatches"]) == 6
