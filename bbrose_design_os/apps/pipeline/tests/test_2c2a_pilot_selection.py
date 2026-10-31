"""Phase 2C-2A — pilot candidate selection (read-only, no provider)."""
from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignProject, DesignTask
from apps.pipeline.services import complete_product_pilot as cp


class SelectionTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.full = Product.objects.create(
            brand=self.brand, product_id="SK-1", name="Night Repair",
            category="SK", year=2026, product_type="serum bottle",
            width_mm=40, depth_mm=40, height_mm=110,
            description="d", ingredients="i", how_to_use="h", notes="n")
        self.empty = Product.objects.create(
            brand=self.brand, product_id="SK-0", name="Empty", category="SK",
            year=2026, product_type="carton")

    def test_scoring_is_deterministic_and_weighted(self):
        e = cp.candidate_evidence(self.full)
        r1 = cp.evaluate_candidate(e)
        r2 = cp.evaluate_candidate(cp.candidate_evidence(self.full))
        assert r1["scores"] == r2["scores"] and r1["total"] == r2["total"]
        assert sum(cp.WEIGHTS.values()) == 100
        for k, v in r1["scores"].items():
            assert 0 <= v <= cp.WEIGHTS[k], k

    def test_hard_exclusions(self):
        r = cp.evaluate_candidate(cp.candidate_evidence(self.empty))
        assert "PILOT_PRODUCT_COPY_INCOMPLETE" in r["hard_exclusions"]
        assert "PILOT_CONTAINER_DIMENSIONS_MISSING" in r["hard_exclusions"]
        assert not r["recommendable"]

    def test_human_rejection_and_authority_exclusions(self):
        e = cp.candidate_evidence(self.full)
        r = cp.evaluate_candidate(e, human_rejection_active=True,
                                  reference_authority_ok=False)
        assert "PILOT_HUMAN_REJECTION_ACTIVE" in r["hard_exclusions"]
        assert "PILOT_REFERENCE_AUTHORITY_INSUFFICIENT" in r["hard_exclusions"]

    def test_no_exact_reference_scores_zero_on_that_axis(self):
        r = cp.evaluate_candidate(cp.candidate_evidence(self.full))
        assert r["scores"]["exact_container_reference"] == 0

    def test_packet_defaults_pending_and_requires_five_decisions(self):
        e = cp.evaluate_candidate(cp.candidate_evidence(self.full))
        packet = cp.build_authorization_packet(
            e, e, e, preflight={"result": "READY_FOR_LIVE_PILOT",
                                "schema_version":
                                    "complete_product_preflight/1.0"},
            spend_plan={"max_calls": 32})
        assert packet["schema_version"] == cp.PACKET_SCHEMA
        assert packet["authorization_status"] == "PENDING_HUMAN_APPROVAL"
        assert len(packet["required_human_decisions"]) == 5

    def test_selection_creates_nothing_and_calls_no_provider(self):
        before_p = DesignProject.objects.count()
        before_t = DesignTask.objects.count()
        with patch("apps.pipeline.services.claude_service.call_claude") as pe, \
                patch("apps.pipeline.agents.image_producer.openai.images"
                      ".edit") as ie:
            e = cp.candidate_evidence(self.full)
            cp.evaluate_candidate(e)
        pe.assert_not_called()
        ie.assert_not_called()
        assert DesignProject.objects.count() == before_p
        assert DesignTask.objects.count() == before_t
        # product record unchanged (read-only)
        self.full.refresh_from_db()
        assert self.full.description == "d"

    def test_the_pilot_names_the_form_the_product_names(self):
        """§BH70(1): the pilot read "compact" as a JAR, "mascara" and "stick" as a TUBE and anything else as a BOTTLE.
        It reads the container's own form words now: a lipstick is a lipstick, a compact powder a compact, and a row
        that names no form — a carton — is unsupported by name, never a bottle."""
        def form_of(ptype):
            row = Product(brand=self.brand, product_id="X-" + ptype, name="X", category="CO", year=2026,
                          product_type=ptype)
            return cp.candidate_evidence(row)
        assert form_of("lipstick")["inferred_container_archetype"] == "lipstick"
        assert form_of("mascara")["inferred_container_archetype"] == "mascara"
        assert form_of("eyeliner pencil")["inferred_container_archetype"] == "pencil"
        assert form_of("compact powder")["inferred_container_archetype"] == "compact"
        assert form_of("serum bottle")["inferred_container_archetype"] == "bottle"
        carton = form_of("carton")
        assert carton["inferred_container_archetype"] is None and carton["supported_archetype"] is False
        assert "PILOT_UNSUPPORTED_CONTAINER_ARCHETYPE" in cp.evaluate_candidate(carton)["hard_exclusions"]
