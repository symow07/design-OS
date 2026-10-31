"""Phase 2B-2 slice 1 — selected-variation identity + visual graph.

Deterministic, no-provider derivation: identity is verified against the
persisted image/prompt record and fails closed when it cannot be; the visual
graph is three-state honest (VERIFIED only from the structured record,
INFERRED from local analysis, MISSING for what needs vision) and reproducible.
"""
from __future__ import annotations

import base64
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignTask,
    Gate1RegenerationJob,
    GeneratedImage,
    PackagingOutput,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_visual_graph as cvg
from apps.pipeline.targets import DesignTarget

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")


class _Base(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-1", name="Rose Nectar",
            category="CO", year=2026, product_type="bottle")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="a bottle",
            status="awaiting_container_profile",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)

    def _image(self, *, prompt="A luxe rose bottle, ROSE NECTAR",
               provenance=None):
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used=prompt,
            variation_number=1, reference_provenance=provenance or {})
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        return img

    def _output(self, img):
        return PackagingOutput.objects.create(
            task=self.task, approved_image=img,
            spec_sheet={"backend": "container", "product_name": "Rose Nectar",
                        cc.PROFILE_SCHEMA: cc.build_inferred_profile("bottle")})


class IdentityTests(_Base):
    def test_first_pass_is_verified_without_structured_record(self):
        out = self._output(self._image())
        resolved = cvg.resolve_selected_variation_identity(self.task, out)
        ident = resolved["identity"]
        assert ident["verified"] is True
        assert ident["structured_record_present"] is False
        assert resolved["structured"] is None
        assert ident["approved_prompt_hash"]      # verifiable prompt
        assert ident["source_hash"]

    def test_missing_approved_image_fails_closed(self):
        img = self._image()
        out = self._output(img)
        out.approved_image = None
        with pytest.raises(cvg.SelectedVariationIdentityError) as exc:
            cvg.resolve_selected_variation_identity(self.task, out)
        assert exc.value.code == "SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED"

    def test_empty_prompt_fails_closed(self):
        out = self._output(self._image(prompt=""))
        with pytest.raises(cvg.SelectedVariationIdentityError):
            cvg.resolve_selected_variation_identity(self.task, out)

    def test_unverifiable_regenerated_record_fails_closed(self):
        # a structured identity whose record cannot be matched must NOT fall
        # back to the direction/first concept
        img = self._image(provenance={"variation_identity": "v_abc"})
        out = self._output(img)
        with pytest.raises(cvg.SelectedVariationIdentityError):
            cvg.resolve_selected_variation_identity(self.task, out)

    def test_verified_regenerated_record_is_loaded(self):
        prompt = "ROSE NECTAR bottle with a scattered powder constellation"
        img = self._image(prompt=prompt,
                          provenance={"variation_identity": "v_abc"})
        Gate1RegenerationJob.objects.create(
            task=self.task, direction_id="d1",
            status=Gate1RegenerationJob.STATUS_COMPLETED,
            prompts_payload={"variations": [{
                "variation_id": "v_abc", "title": "Powder",
                "prompt": prompt,
                "motif_signature": "scattered powder constellation",
                "logo_zone": "upper left",
                "product_name_zone": "centered",
                "decorative_coverage_pct": 18}]})
        out = self._output(img)
        resolved = cvg.resolve_selected_variation_identity(self.task, out)
        assert resolved["identity"]["structured_record_present"] is True
        assert resolved["identity"]["variation_title"] == "Powder"
        assert resolved["identity"]["regeneration_job_id"]
        assert resolved["structured"]["verified"] is True


class VisualGraphTests(_Base):
    def _graph(self, structured=None):
        out = self._output(self._image())
        return cvg.build_visual_graph(
            self.task, out, out.spec_sheet[cc.PROFILE_SCHEMA], structured,
            out.approved_image.image_file.path)

    def test_schema_and_every_field_carries_four_axes(self):
        g = self._graph()
        assert g["schema_version"] == "container_selected_concept_visual_graph/1.0"
        for f in g["fields"].values():
            assert set(f) >= {"value", "confidence", "source", "verification"}

    def test_vision_only_fields_are_missing_never_faked(self):
        g = self._graph()
        for key in ("front_back_visual_relationship", "wrap_continuation_direction",
                    "label_edge_relationship", "dominant_alignment_axes"):
            assert g["fields"][key]["verification"] == cc.MISSING
            assert g["fields"][key]["value"] is None

    def test_structured_fields_verified_only_with_record(self):
        # no record → logo/name zones + motif family are MISSING
        g0 = self._graph(structured=None)
        assert g0["fields"]["logo_zone"]["verification"] == cc.MISSING
        assert g0["fields"]["motif_family"]["verification"] == cc.MISSING
        # with a verified record → those become VERIFIED from the record
        structured = {"verified": True, "variation_id": "v_abc",
                      "logo_zone": "upper left", "product_name_zone": "centered",
                      "motif_signature": "powder constellation scatter",
                      "decorative_coverage_pct": 18}
        g1 = self._graph(structured=structured)
        assert g1["fields"]["logo_zone"]["verification"] == cc.VERIFIED
        assert g1["fields"]["logo_zone"]["source"] == cvg.SRC_VARIATION_RECORD
        assert g1["fields"]["motif_family"]["value"] == "powder_constellation"
        assert g1["fields"]["decoration_coverage"]["verification"] == cc.VERIFIED

    def test_local_fields_are_inferred(self):
        g = self._graph()
        bc = g["fields"]["body_base_color"]
        assert bc["source"] == cvg.SRC_LOCAL_IMAGE
        assert bc["verification"] == cc.INFERRED

    def test_bh70_a_compact_pictured_from_above_keeps_no_cap_colour_and_faces_no_front(self):
        """§BH70(1), item 11 of the list the owner was sent: the record read a cap colour from the top quarter of every
        concept picture and said every product faced front — on a compact, pictured from above, that quarter is
        background. A form drawn in plan keeps no cap colour, says why, and is seen from above; a bottle is unchanged."""
        out = self._output(self._image())
        path = out.approved_image.image_file.path
        compact = cvg.build_visual_graph(self.task, out, {"archetype": "compact"}, None, path)["fields"]
        coord = compact["body_cap_color_coordination"]
        assert coord["value"] is None and coord["verification"] == cc.MISSING
        assert coord["note"] == cvg.PLAN_HAS_NO_CAP_AT_THE_TOP
        assert compact["front_orientation"]["value"] == "seen_from_above"
        bottle = cvg.build_visual_graph(self.task, out, {"archetype": "bottle"}, None, path)["fields"]
        assert bottle["body_cap_color_coordination"]["value"]["cap_region"].startswith("#")
        assert "note" not in bottle["body_cap_color_coordination"]
        assert bottle["front_orientation"]["value"] == "front_facing"

    def test_graph_is_deterministic(self):
        out = self._output(self._image())
        path = out.approved_image.image_file.path
        prof = out.spec_sheet[cc.PROFILE_SCHEMA]
        h1 = cvg.build_visual_graph(self.task, out, prof, None, path)["visual_graph_hash"]
        h2 = cvg.build_visual_graph(self.task, out, prof, None, path)["visual_graph_hash"]
        assert h1 == h2 and h1

    @patch("apps.pipeline.services.claude_service.call_claude")
    def test_no_provider_call(self, mock_claude):
        self._graph()
        cvg.resolve_selected_variation_identity(
            self.task, self._output(self._image()))
        mock_claude.assert_not_called()
