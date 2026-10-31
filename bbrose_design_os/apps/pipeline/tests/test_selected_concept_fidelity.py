"""Selected-concept fidelity (2A-6E-CORR-7).

Task #50's production artwork replaced the approved Powder Constellation
concept with generic diagonal stripes and a small centered label: the
composer derived its language from the DIRECTION's "hairline rule"
vocabulary and never consulted the SELECTED variation. These pin the whole
corrected chain: the variation identity survives the structure gate into
reconstruction; the constellation maps to native vector primitives; the
stripe fallback can never replace an unsupported selected motif (fail
closed); typography hierarchy, vertical Spanish copy and panel roles are
preserved and validated; decorative rasters stay zero.
"""
from __future__ import annotations

from django.test import TestCase

from apps.ire.compose_vector_art import VectorArtStyle
from apps.ire.concept_fidelity import (
    ConceptFidelityError,
    validate_concept_fidelity,
)
from apps.ire.design_language import (
    POWDER_CONSTELLATION_SWATCHES,
    LanguageParameters,
    VectorReconstructionReviewRequired,
    get_language,
    resolve_language,
)
from apps.pipeline.services.selected_concept import (
    extract_copy_lines,
    reconstruction_spec,
)

#: Trimmed replica of the ACTUAL C_POWDER_CONSTELLATION record the user
#: approved (job 2 payload, prompt-verified against image 89).
SELECTED_VARIATION = {
    "variation_id": "C_POWDER_CONSTELLATION",
    "title": "Powder Constellation",
    "composition_signature": (
        "Left-asymmetric editorial type hierarchy with BBROSE upper-left "
        "anchored by partial open rectangle frame; powder-particle "
        "constellation massing at lower-right dispersing diagonally; "
        "vertical Spanish copy on right edge"),
    "color_field_signature": (
        "Warm ivory ground with a faint soft-mint atmospheric wash at "
        "lower-left; rose-gold constellation and frame as the accent field"),
    "motif_signature": (
        "Forty-to-sixty vector powder particles — mixed fine dots, slim "
        "ellipses and cross-tick hairlines in rose-gold — forming a "
        "dispersing constellation from lower-right corner toward mid-panel"),
    "logo_zone": ("Upper left of front face, rose-gold Pantone with light "
                  "emboss, partially enclosed by an open double-hairline "
                  "rose-gold rectangle frame on bottom and right sides only"),
    "product_name_zone": ("Upper central area left-aligned to a one-third "
                          "axis: BAKED in large blush-rose condensed "
                          "uppercase above POWDER in ivory"),
    "decorative_coverage_pct": 17,
    "prompt": ("A compact face-powder carton... the word BAKED in large "
               "condensed uppercase above POWDER... POLVO HORNEADO runs "
               "vertically along the right edge in warm grey letterspaced "
               "capitals, rotated to read bottom-to-top... beneath the "
               "product name sits LUMINOSIDAD SUAVE in small warm-grey "
               "tracking... particles scatter and sparkle toward the "
               "lower-right corner"),
    "verified": True,
}


def _spec():
    return reconstruction_spec(SELECTED_VARIATION,
                               product_name="Baked Powder",
                               direction={"direction_id": "d1"})


class ReconstructionSpecTests(TestCase):
    def test_variation_resolves_to_the_constellation_language(self):
        lang = resolve_language(None, variation=SELECTED_VARIATION)
        assert lang.name == "powder_constellation"

    def test_direction_vocabulary_no_longer_decides(self):
        """The task-#50 defect: the direction's 'hairline rule' vocabulary
        must not choose the language when a variation exists."""
        stripe_direction = {
            "name": "Editorial Soft Radiance",
            "graphic_elements": "one fine hairline rule; a thin vertical "
                                "rule; linear rules",
        }
        lang = resolve_language(stripe_direction,
                                variation=SELECTED_VARIATION)
        assert lang.name == "powder_constellation"

    def test_unsupported_variation_fails_closed_never_substitutes(self):
        alien = {"variation_id": "X", "title": "Holographic Chrome",
                 "motif_signature": "iridescent holographic chrome shards",
                 "composition_signature": "chrome", "prompt": "chrome"}
        with self.assertRaises(VectorReconstructionReviewRequired) as ctx:
            VectorArtStyle.for_variation(alien)
        assert ctx.exception.code == "VECTOR_RECONSTRUCTION_REVIEW_REQUIRED"

    def test_copy_extraction_is_verbatim_and_flags_vertical(self):
        lines = extract_copy_lines(SELECTED_VARIATION, "Baked Powder")
        assert "POLVO HORNEADO" in lines["secondary"]
        assert "LUMINOSIDAD SUAVE" in lines["secondary"]
        assert lines["vertical"] == "POLVO HORNEADO"
        spec = _spec()
        assert spec["name_lines"] == ["BAKED", "POWDER"]

    def test_constellation_builds_native_editable_primitives(self):
        lang = get_language("powder_constellation")
        from dataclasses import replace
        params = replace(lang.defaults, seed=50)
        groups = lang.build((0, 0, 90, 92), params, "front",
                            lambda x: x, lambda y: y)
        names = [g.name for g in groups]
        assert "constellation-core" in names
        assert "constellation-drift" in names
        particles = [c for g in groups for c in g.children]
        # §4: the front carries 90-150 meaningful particles
        assert 90 <= len(particles) <= 150
        assert all(p.type == "path" for p in particles)     # native vectors
        assert all(p.name.startswith("particle-") for p in particles)
        # side-panel continuation is a REDUCED field, not a repeat
        side = lang.build((0, 0, 25, 92),
                          params.for_surface("side_right"), "side_right",
                          lambda x: x, lambda y: y)
        side_particles = [c for g in side for c in g.children]
        assert 0 < len(side_particles) < len(particles)

    def test_swatches_carry_the_mandated_names(self):
        names = set(POWDER_CONSTELLATION_SWATCHES.to_dict())
        assert {"WARM_IVORY_BASE", "BLUSH_PINK", "DUSTY_PINK_TYPE",
                "ROSE_GOLD_PLACEHOLDER", "SOFT_PEACH_PARTICLES",
                "WARM_GREY_SUPPORTING_TEXT"} <= names


class VariationLoaderTests(TestCase):
    """The selected variation identity survives the structure gate into
    reconstruction — loaded from the job's persisted payload and verified
    against the approved image's own prompt."""

    def setUp(self):
        from django.contrib.auth.models import User
        from apps.core.models import Brand
        from apps.pipeline.models import (DesignTask, Gate1RegenerationJob,
                                          GeneratedImage)
        self.user = User.objects.create_superuser("vc", "v@v.com", "pw")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=brand, task_text="x", status="awaiting_gate_2",
            created_by=self.user)
        Gate1RegenerationJob.objects.create(
            task=self.task, direction_id="d1", status="completed",
            approved_reference_ids=[2, 7], influence_plan_hash="h" * 64,
            variation_identities=["C_POWDER_CONSTELLATION"],
            prompts_payload={"variations": [SELECTED_VARIATION]},
            created_by=self.user)
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="Editorial Soft Radiance",
            prompt_used=SELECTED_VARIATION["prompt"], variation_number=3,
            reference_provenance={
                "variation_identity": "C_POWDER_CONSTELLATION"})

    def test_identity_survives_into_a_verified_record(self):
        from apps.pipeline.services.selected_concept import (
            load_selected_variation)
        record = load_selected_variation(self.task, self.image)
        assert record["verified"] is True
        assert record["variation_id"] == "C_POWDER_CONSTELLATION"
        assert record["motif_signature"] == \
            SELECTED_VARIATION["motif_signature"]

    def test_prompt_mismatch_fails_verification(self):
        from apps.pipeline.services.selected_concept import (
            load_selected_variation)
        self.image.prompt_used = "a completely different prompt"
        self.image.save()
        record = load_selected_variation(self.task, self.image)
        assert record["verified"] is False

    def test_legacy_image_without_identity_returns_none(self):
        from apps.pipeline.services.selected_concept import (
            load_selected_variation)
        self.image.reference_provenance = {}
        self.image.save()
        assert load_selected_variation(self.task, self.image) is None


class ComposedDocumentTests(TestCase):
    """Full composition on a real STE 1.1 geometry — the corrected artwork."""

    def _compose(self, concept=True):
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose_vector_art import compose_vector_art_graph
        params = DielineInputJSON(
            template="straight_tuck_end_carton", unit="mm",
            dimensions={"width_mm": 90.0, "depth_mm": 25.0,
                        "height_mm": 92.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.35,
                          "thickness_compensation": True},
            metadata={"product_name": "Baked Powder",
                      "product_type": "face powder"})
        coords = calculate_dieline(params)
        style = VectorArtStyle.for_variation(SELECTED_VARIATION, seed=50)
        return compose_vector_art_graph(
            coords, style=style, product_name="Baked Powder",
            subtitle="face powder",
            concept_spec=_spec() if concept else None)

    def test_corrected_composition_passes_fidelity(self):
        doc = self._compose()
        assert validate_concept_fidelity(doc, _spec()) == []

    def test_front_hierarchy_and_vertical_copy_are_live_text(self):
        doc = self._compose()
        runs = {n.name: n for n, _ in doc.walk() if n.type == "text"}
        assert runs["product-name-line-1"].text == "BAKED"
        assert runs["product-name-line-2"].text == "POWDER"
        assert runs["product-name-line-1"].align == "left"
        assert runs["product-name-line-1"].size_pt >= 16.0
        assert runs["vertical-copy"].text == "POLVO HORNEADO"
        assert abs(runs["vertical-copy"].rotation_deg) == 90.0
        assert runs["tagline"].text == "LUMINOSIDAD SUAVE"
        assert doc.metadata["logo_zone_used"] == "upper-left"

    def test_finish_layers_are_separable_named_groups(self):
        doc = self._compose()
        groups = {n.name for n, _ in doc.walk() if n.type == "group"}
        assert {"SPOT_UV", "EMBOSS", "DEBOSS", "ROSE_GOLD_FOIL"} <= groups

    def test_decorative_rasters_remain_zero(self):
        doc = self._compose()
        inventory = doc.metadata["inventory"]
        assert inventory["decorative_raster_count"] == 0

    def test_back_panel_stays_quiet(self):
        doc = self._compose()
        for node, _ in doc.walk():
            if node.type == "group" and node.role == "decoration" \
                    and node.name.endswith("-back"):
                raise AssertionError("decoration composed on the back panel")

    def test_stripe_substitution_fails_the_fidelity_gate(self):
        """The exact task-#50 defect, now impossible to export: a ruled
        stripe composition presented against the constellation concept."""
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose_vector_art import compose_vector_art_graph
        params = DielineInputJSON(
            template="straight_tuck_end_carton", unit="mm",
            dimensions={"width_mm": 90.0, "depth_mm": 25.0,
                        "height_mm": 92.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.35,
                          "thickness_compensation": True},
            metadata={"product_name": "Baked Powder",
                      "product_type": "face powder"})
        coords = calculate_dieline(params)
        stripes = VectorArtStyle(language="ruled_field")
        doc = compose_vector_art_graph(
            coords, style=stripes, product_name="Baked Powder",
            subtitle="face powder")     # legacy composition, no concept
        failures = validate_concept_fidelity(doc, _spec())
        joined = " ".join(failures)
        assert "principal motif family changed" in joined
        assert "constellation is absent" in joined
        assert "stacked hierarchy" in joined or "small label" in joined
        assert "POLVO HORNEADO" in joined
        with self.assertRaises(ConceptFidelityError):
            from apps.ire.concept_fidelity import assert_concept_fidelity
            assert_concept_fidelity(doc, _spec())


class GeometryGateTests(TestCase):
    """2A-6E-CORR-8 §9: declared presence can never pass when the EMITTED
    geometry is wrong — the first gate's exact blind spot."""

    def _compose(self, style=None, spec=None, concept=True):
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose_vector_art import compose_vector_art_graph
        params = DielineInputJSON(
            template="straight_tuck_end_carton", unit="mm",
            dimensions={"width_mm": 90.0, "depth_mm": 25.0,
                        "height_mm": 92.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.35,
                          "thickness_compensation": True},
            metadata={"product_name": "Baked Powder",
                      "product_type": "face powder"})
        coords = calculate_dieline(params)
        style = style or VectorArtStyle.for_variation(SELECTED_VARIATION,
                                                      seed=50)
        doc = compose_vector_art_graph(
            coords, style=style, product_name="Baked Powder",
            subtitle="face powder",
            concept_spec=(spec or _spec()) if concept else None)
        front = {p.name: p for p in coords.panels}["front"]
        min_x, min_y, _, _ = coords.bleed_polygon.bounds
        bounds = (front.x - (min_x - 10), front.y - (min_y - 10),
                  front.width, front.height)
        return doc, bounds

    BARLOW = {"name": "BarlowCondensed-Bold",
              "path": "/Users/symow/Desktop/bbrose-systemOS/materials/"
                      "Fonts/3333/BarlowCondensed-Bold.ttf"}

    def _confirmed_spec(self):
        # the REAL approved face: sizing and measurement share its metrics
        return {**_spec(), "confirmed_font": dict(self.BARLOW)}

    def test_correct_geometry_passes(self):
        from apps.ire.concept_fidelity import validate_concept_geometry
        spec = self._confirmed_spec()
        doc, bounds = self._compose(spec=spec)
        assert validate_concept_geometry(doc, spec, bounds) == []

    def test_unconfirmed_font_blocks_with_a_stable_code(self):
        from apps.ire.concept_fidelity import validate_concept_geometry
        doc, bounds = self._compose()
        codes = validate_concept_geometry(doc, _spec(), bounds)
        assert codes and all("FONT_CONFIRMATION_REQUIRED" in c
                             for c in codes)

    def test_small_name_and_sparse_field_fail_by_measurement(self):
        """A legacy small-label + stripes composition against the same
        spec — every §9 defect is caught from GEOMETRY, with the elements
        nominally 'present' being irrelevant."""
        from apps.ire.concept_fidelity import validate_concept_geometry
        doc, bounds = self._compose(
            style=VectorArtStyle(language="ruled_field"), concept=False)
        joined = " ".join(validate_concept_geometry(
            doc, self._confirmed_spec(), bounds))
        assert "PRODUCT_NAME_TOO_SMALL" in joined
        assert "CONSTELLATION_TOO_SPARSE" in joined
        assert "LOGO_FRAME_TOO_SMALL" in joined
        assert "VERTICAL_COPY_ZONE_MISMATCH" in joined

    def test_wrong_centroid_and_missing_continuation_fail(self):
        from apps.ire.concept_fidelity import validate_concept_geometry
        from apps.ire.graph import Group
        spec = self._confirmed_spec()
        doc, bounds = self._compose(spec=spec)
        fx, fy, fw, fh = bounds

        def _shift(node):
            for group in getattr(node, "children", []) or []:
                _shift(group)
            if node.type == "path" and node.name.startswith("particle-"):
                for seg in node.segments:
                    for attr in ("x", "x1", "x2"):
                        if getattr(seg, attr, None) is not None:
                            setattr(seg, attr,
                                    fx + (getattr(seg, attr) - fx) * 0.3)
                    for attr in ("y", "y1", "y2"):
                        if getattr(seg, attr, None) is not None:
                            setattr(seg, attr,
                                    fy + (getattr(seg, attr) - fy) * 0.3)
        _shift(doc.root)
        joined = " ".join(validate_concept_geometry(doc, spec, bounds))
        assert "CONSTELLATION_ZONE_MISMATCH" in joined

    def test_missing_side_continuation_fails(self):
        from apps.ire.concept_fidelity import validate_concept_geometry
        spec = self._confirmed_spec()
        doc, bounds = self._compose(spec=spec)

        def _drop_side(node):
            kept = []
            for child in getattr(node, "children", []) or []:
                _drop_side(child)
                name = str(getattr(child, "name", ""))
                if name.startswith("powder_constellation-") and \
                        name != "powder_constellation-front":
                    continue
                kept.append(child)
            if hasattr(node, "children"):
                node.children = kept
        _drop_side(doc.root)
        joined = " ".join(validate_concept_geometry(doc, spec, bounds))
        assert "SIDE_CONTINUATION_MISSING" in joined


class AiLibraryTests(TestCase):
    """§6/§7: the .ai design library feeds candidates; unapproved sources
    are never analyzed; descriptors carry no reusable paths."""

    def test_candidates_come_from_the_design_library(self):
        import json as jsonlib
        import shutil
        import tempfile
        from pathlib import Path
        from django.test import override_settings
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask
        from apps.pipeline.services.ai_style_profile import (
            ai_design_candidates)
        materials = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, materials, True)
        inventory = Path(materials) / "inventory.jsonl"
        inventory.write_text("\n".join(jsonlib.dumps(record) for record in [
            {"relative_path": "materials/designs/FB-9999.ai",
             "extension": ".ai", "sha256": "a" * 64,
             "category": "HISTORICAL_DESIGN",
             "ownership_status": {"value": "UNKNOWN"},
             "license_status": {"value": "UNVERIFIED"}},
            {"relative_path": "materials/designs/unrelated-poster.ai",
             "extension": ".ai", "sha256": "b" * 64,
             "category": "HISTORICAL_DESIGN",
             "ownership_status": {"value": "UNKNOWN"},
             "license_status": {"value": "UNVERIFIED"}},
        ]))
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x",
                                         status="awaiting_gate_2")
        with override_settings(DIP_INVENTORY_PATH=str(inventory),
                               MATERIALS_ROOT=materials):
            rows = ai_design_candidates(task, "face powder")
        titles = [r["title"] for r in rows]
        assert "FB-9999" in titles
        assert "unrelated-poster" not in titles
        assert all(r["is_vector"] for r in rows)

    def test_unapproved_ai_reference_is_never_analyzed(self):
        from django.contrib.auth.models import User
        from apps.core.models import Brand
        from apps.pipeline.models import ConceptReference, DesignTask
        from apps.pipeline.services.ai_style_profile import (
            extract_style_profile)
        User.objects.create_superuser("ai", "a@a.com", "pw")
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        task = DesignTask.objects.create(brand=brand, task_text="x",
                                         status="awaiting_gate_2")
        row = ConceptReference.objects.create(
            task=task, source_type="AI_DESIGN_LIBRARY",
            library_item_id="ai:" + "c" * 60, title="FB-9999",
            image_root="materials", image_path="materials/FB-9999.ai")
        with self.assertRaises(PermissionError):
            extract_style_profile(row)

    def test_descriptors_contain_no_source_paths(self):
        """The profile schema is descriptor-only by construction: assert the
        published field set carries no path/segment data."""
        import inspect
        from apps.pipeline.services import ai_style_profile as module
        source = inspect.getsource(module.extract_style_profile)
        assert "get_drawings" in source
        # the profile dict keys are ratios/counts/zones — never path items
        for forbidden in ("\"items\"", "'items'", "d[\"items\"]",
                          "seg", "path_points"):
            assert forbidden not in source


class ConceptRenderQualityTests(TestCase):
    """2A-6E browser-verified defects pinned (finish placeholders painted as
    blocks; blush-dominant ground; confirmed font not reaching the emitter)."""

    def _doc(self):
        from apps.dielines.geometry.engine import calculate_dieline
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.ire.compose_vector_art import compose_vector_art_graph
        params = DielineInputJSON(
            template="straight_tuck_end_carton", unit="mm",
            dimensions={"width_mm": 90.0, "depth_mm": 25.0,
                        "height_mm": 92.0},
            print_settings={"bleed_mm": 3.0, "safe_margin_mm": 4.0},
            construction={"glue_tab_mm": 12.0, "board_thickness_mm": 0.35,
                          "thickness_compensation": True},
            metadata={"product_name": "Baked Powder",
                      "product_type": "face powder"})
        coords = calculate_dieline(params)
        return compose_vector_art_graph(
            coords, style=VectorArtStyle.for_variation(SELECTED_VARIATION,
                                                       seed=50),
            product_name="Baked Powder", subtitle="face powder",
            concept_spec=_spec())

    def test_finish_placeholders_are_outlines_never_painted_fills(self):
        doc = self._doc()
        for node, parent in doc.walk():
            name = str(getattr(node, "name", ""))
            if any(name.startswith(layer + "-") for layer in
                   ("SPOT_UV", "EMBOSS", "DEBOSS", "ROSE_GOLD_FOIL")):
                assert getattr(node, "fill", None) is None, name
                assert getattr(node, "stroke", None) is not None, name
                assert node.stroke.dash is not None, name

    def test_concept_ground_is_ivory_dominant(self):
        doc = self._doc()
        ground = next(node for node, _ in doc.walk()
                      if getattr(node, "name", "") == "ground-gradient")
        stops = ground.fill.stops
        assert len(stops) == 3
        assert stops[1].offset >= 0.7        # ivory holds ~3/4 of the sheet

    def test_soft_mint_wash_is_an_editable_gradient_object(self):
        doc = self._doc()
        wash = next((node for node, _ in doc.walk()
                     if getattr(node, "name", "") == "soft-mint-wash"), None)
        assert wash is not None
        assert wash.fill.kind == "linear"
        assert wash.opacity < 0.5            # atmospheric, never a block

    def test_confirmed_font_reaches_the_emitter_as_live_text(self):
        import shutil
        import tempfile
        from pathlib import Path as P
        from apps.ire.emitters.pdf_ai import emit_pdf_ai
        doc = self._doc()
        from apps.ire.materials_paths import resolve_material_file as _physical_material
        font_path = str(_physical_material("/Users/symow/Desktop/bbrose-systemOS/materials/Fonts/3333/BarlowCondensed-Bold.ttf"))   # Day 6 migration: identity kept, bytes located by the manifest
        doc.metadata["confirmed_font"] = {"name": "BarlowCondensed-Bold",
                                          "path": font_path}
        out = P(tempfile.mkdtemp()) / "t.ai"
        self.addCleanup(shutil.rmtree, out.parent, True)
        emit_pdf_ai(doc, str(out))
        raw = out.read_bytes()
        assert b"BarlowCondensed-Bold" in raw       # embedded live face
        inventory = doc.metadata["inventory"]
        assert inventory["outlined_text_count"] == 0
