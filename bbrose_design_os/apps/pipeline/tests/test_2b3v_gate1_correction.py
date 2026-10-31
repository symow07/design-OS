"""Phase 2B-3V Gate-1 correction — the authorization + variation-contract fix.

Task #51's Gate-1 set was rejected because the initial render fed the provider
four UNAPPROVED house references while the four the user approved never
shipped, and because the three prompts abandoned the required A/B/C variation
contract. These tests pin the correction end to end:

  §2  the canonical resolver never returns house-index files;
  §3  pre-spend blocks a changed approval set / missing file / unapproved file;
  §4/§5/§6  the container variation contract (named identities, seven-axis
       diversity, per-variation reference subsets) is enforced before any
       image call — generic names fail, a non-distinct set fails, both make
       zero image calls;
  §7  the rejected set stays but is unselectable;
  §8  provider latency + request id are recorded (honestly when absent).

No test makes a real provider call.
"""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import base64
import copy
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.models import Brand, DesignReference, Product
from apps.pipeline.models import (
    ConceptInfluencePlan,
    ConceptReference,
    CreativeBrief,
    DesignTask,
    GeneratedImage,
)


def _b64_response():
    data = MagicMock()
    data.url = None
    data.b64_json = base64.b64encode(b"fake png").decode()
    resp = MagicMock()
    resp.data = [data]
    resp._request_id = "req_test_123"
    resp.id = "resp_test_456"
    return resp


def _claude(payload):
    import json
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    resp = MagicMock()
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=10, output_tokens=10)
    resp.id, resp._request_id = "msg_1", "req_1"
    return resp


class _ContainerTaskMixin(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-410", name="Rosé Nectar Lip Gloss",
            category="CO", year=2026, product_type="lip gloss")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="lip gloss",
            status="running", design_target="product_container")

    def _approve(self, count=2):
        rows = []
        for i in range(count):
            (Path(self.media) / f"c{i}.png").write_bytes(b"\x89PNG c")
            rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:{i}", title=f"ref {i}",
                image_root="media", image_path=f"c{i}.png",
                permission_status=ConceptReference.PERMISSION_APPROVED))
        plan = {"schema_version": "material_influence_plan/1.0",
                "references": [{"reference_id": r.pk,
                                "permitted_analysis": ["palette"],
                                "prohibited_from_copying": ["copy the layout"]}
                               for r in rows]}
        ConceptInfluencePlan.objects.create(
            task=self.task, schema_version="material_influence_plan/1.0",
            plan=plan, plan_hash="planhash123")
        return rows

    def _house_reference(self):
        (Path(self.media) / "house.png").write_bytes(b"\x89PNG house")
        return DesignReference.objects.create(
            name="YB-1039", image_path="house.png", category="CO",
            product_type="lip gloss", tags=["gloss"], summary="house ref")


# --- §2 resolver ------------------------------------------------------------

class ResolverTests(_ContainerTaskMixin):
    def test_house_index_never_returns_an_image_file(self):
        # §2: an unapproved product-matched house reference must not appear as
        # a provider file — even when it is the only "reference" available.
        self._house_reference()
        with override_settings(MEDIA_ROOT=self.media):
            from apps.pipeline.services.visual_reference_resolver import (
                resolve_visual_references)
            bundle = resolve_visual_references(self.task)
        assert bundle.concept_references == []
        assert bundle.reference_file_paths() == []
        assert bundle.approved_reference_ids == []

    def test_only_approved_files_are_returned(self):
        rows = self._house_reference(), self._approve(2)
        _, approved = rows
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            from apps.pipeline.services.visual_reference_resolver import (
                resolve_visual_references)
            bundle = resolve_visual_references(self.task)
        assert sorted(bundle.approved_reference_ids) == sorted(r.pk for r in approved)
        names = {Path(p).name for p in bundle.reference_file_paths()}
        assert names == {"c0.png", "c1.png"}          # never house.png
        assert bundle.influence_plan_hash == "planhash123"


# --- §3 pre-spend -----------------------------------------------------------

class PreSpendTests(_ContainerTaskMixin):
    def _bundle(self):
        from apps.pipeline.services.visual_reference_resolver import (
            resolve_visual_references)
        return resolve_visual_references(self.task)

    def test_changed_approval_set_blocks(self):
        self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            bundle = self._bundle()
            pf, hl = bundle.provider_files()
            # a reference is approved AFTER the bundle was built → drift
            (Path(self.media) / "c2.png").write_bytes(b"\x89PNG c")
            ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id="design_reference:2", title="late",
                image_root="media", image_path="c2.png",
                permission_status=ConceptReference.PERMISSION_APPROVED)
            from apps.pipeline.services.provider_prespend import (
                validate_image_prespend)
            res = validate_image_prespend(
                self.task, bundle, opened_files=pf, has_logo=hl)
        assert not res.ok
        assert "REFERENCE_APPROVAL_SET_CHANGED" in res.codes

    def test_unauthorised_opened_file_blocks(self):
        self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            bundle = self._bundle()
            from apps.pipeline.services.provider_prespend import (
                validate_image_prespend)
            res = validate_image_prespend(
                self.task, bundle,
                opened_files=["/etc/passwd"], has_logo=False)
        assert not res.ok
        assert "UNAPPROVED_VISUAL_REFERENCE_USED" in res.codes

    def test_require_visual_with_no_references_blocks(self):
        # §2/§6: no silent fallback — a workflow that requires visual grounding
        # fails closed when nothing is authorised.
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            bundle = self._bundle()
            from apps.pipeline.services.provider_prespend import (
                validate_image_prespend)
            res = validate_image_prespend(
                self.task, bundle, opened_files=[], has_logo=False,
                require_visual=True)
        assert not res.ok
        assert "APPROVED_VISUAL_REFERENCES_REQUIRED" in res.codes

    def test_clean_set_passes_and_production_use_stays_false(self):
        self._approve(2)
        with override_settings(MEDIA_ROOT=self.media, BRAND_LOGO_PATH=""):
            bundle = self._bundle()
            pf, hl = bundle.provider_files()
            from apps.pipeline.services.provider_prespend import (
                validate_image_prespend)
            res = validate_image_prespend(
                self.task, bundle, opened_files=pf, has_logo=hl,
                require_visual=True)
        assert res.ok and res.codes == []
        assert res.detail["production_use_allowed"] is False


# --- §4/§5/§6 container variation contract ----------------------------------

def _container_payload(distinct=True, generic_names=False, force_all_refs=False):
    from apps.pipeline.services import container_gate1 as cg1
    ids = (["variation_1", "variation_2", "variation_3"] if generic_names
           else list(cg1.CONTAINER_VARIATION_IDENTITIES))
    base = {
        "typography_signature": "condensed serif, centred",
        "composition_signature": "centred column",
        "motif_signature": "petal window, 8 droplets",
        "cap_body_signature": "rose-gold cap on blush body",
        "decoration_zone_signature": "centred front window",
        "color_field_signature": "blush to ivory gradient",
        "finish_signature": "spot-UV on petals",
        "native_reconstruction_plan": "live serif + Bézier petals + gradient fills",
        "prompt": " ".join(["a tall slim lip-gloss tube with a rose-gold cap and"
                            " a native-vector petal window design"] * 4),
        "reference_ids": [1, 2] if force_all_refs else [1],
    }
    variations = []
    for n, vid in enumerate(ids):
        v = copy.deepcopy(base)
        v["variation_id"] = vid
        v["title"] = vid
        if distinct:
            # make every signature axis differ across the three
            for f in ("typography_signature", "composition_signature",
                      "motif_signature", "cap_body_signature",
                      "decoration_zone_signature", "color_field_signature",
                      "finish_signature"):
                v[f] = f"{v[f]} variant {n}"
        v["reference_ids"] = [1] if n == 0 else [2] if not force_all_refs else [1, 2]
        variations.append(v)
    return {"schema_version": cg1.CONTAINER_GATE1_SCHEMA,
            "approved_reference_ids": [1, 2],
            "influence_plan_hash": "planhash123",
            "variations": variations}


def _validate_container(payload):
    from apps.pipeline.services import container_gate1 as cg1
    from apps.pipeline.services.gate1_prompts import validate_regeneration_payload
    return validate_regeneration_payload(
        payload, cg1.CONTAINER_VARIATION_IDENTITIES, [1, 2], "planhash123",
        schema_version=cg1.CONTAINER_GATE1_SCHEMA,
        required_fields=cg1.CONTAINER_REQUIRED_FIELDS,
        diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS,
        min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
        schema_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        empty_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        not_distinct_code=cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT,
        identity_code=cg1.CONTAINER_VARIATION_IDENTITY_MISSING,
        require_per_variation_reference_ids=True)


def _validate_slots(payload):
    """§BH67(c)4: the contract with no person's identities — three SLOTS the variations name themselves."""
    from apps.pipeline.services import container_gate1 as cg1
    from apps.pipeline.services.gate1_prompts import validate_regeneration_payload
    return validate_regeneration_payload(
        payload, (), [1, 2], "planhash123",
        schema_version=cg1.CONTAINER_GATE1_SCHEMA,
        required_fields=cg1.CONTAINER_REQUIRED_FIELDS,
        diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS,
        min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
        schema_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        empty_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
        not_distinct_code=cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT,
        identity_code=cg1.CONTAINER_VARIATION_IDENTITY_MISSING,
        require_per_variation_reference_ids=True,
        identity_slots=cg1.CONTAINER_VARIATION_SLOTS)


def _named(ids):
    payload = _container_payload()
    for v, vid in zip(payload["variations"], ids):
        v["variation_id"] = v["title"] = vid
    return payload


def test_bh67c4_the_variations_name_themselves_and_no_house_name_is_required():
    """§BH67(c)4, 2026-09-24: "A house instruction is not a design decision. All three variations come from the
    directions." Three names of the concepts' own pass; the July names still name their slots, so the records of
    tasks 51-91 revalidate."""
    assert _validate_slots(_named(["A_ORCHARD_HOUR", "B_SILK_TIDE", "C_LANTERN_ROW"])) == []
    assert _validate_slots(_container_payload()) == []


def test_bh67c4_a_generic_or_misplaced_name_is_refused_by_its_slot():
    from apps.pipeline.services import container_gate1 as cg1
    for bad in (["variation_1", "variation_2", "variation_3"],          # the legacy form, read as no record
                ["A_VARIATION_1", "B_SILK_TIDE", "C_LANTERN_ROW"],       # a generic word is not a name
                ["B_SILK_TIDE", "A_ORCHARD_HOUR", "C_LANTERN_ROW"],      # out of slot order
                ["A_orchard", "B_SILK_TIDE", "C_LANTERN_ROW"]):          # not capitals and underscores
        codes = _validate_slots(_named(bad))
        assert any(cg1.CONTAINER_VARIATION_IDENTITY_MISSING in c for c in codes), bad


def test_bh67c4_the_brief_forces_no_house_motif_onto_a_slot():
    """The July slot briefs are gone from both texts the Prompt Engineer reads; the house motifs are offered as
    options, and no July identity is named as one the model must produce."""
    from apps.pipeline.services import container_gate1 as cg1
    text = cg1.CONTAINER_GATE1_DIRECTIVES
    assert "VARIATION A —" not in text and "VARIATION B —" not in text and "VARIATION C —" not in text
    assert "HOUSE MOTIFS — OPTIONS, NEVER DEFAULTS" in text
    for vid in cg1.CONTAINER_VARIATION_IDENTITIES:
        assert vid not in text and vid not in cg1.CONTAINER_SYSTEM


class ContainerVariationContractTests(TestCase):
    def test_valid_named_distinct_set_passes(self):
        assert _validate_container(_container_payload()) == []

    def test_generic_variation_names_fail(self):
        from apps.pipeline.services import container_gate1 as cg1
        codes = _validate_container(_container_payload(generic_names=True))
        assert any(cg1.CONTAINER_VARIATION_IDENTITY_MISSING in c for c in codes)

    def test_non_distinct_set_fails_seven_axis_gate(self):
        from apps.pipeline.services import container_gate1 as cg1
        codes = _validate_container(_container_payload(distinct=False))
        assert any(cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT in c for c in codes)

    def test_missing_signature_field_fails_contract(self):
        from apps.pipeline.services import container_gate1 as cg1
        payload = _container_payload()
        del payload["variations"][0]["finish_signature"]
        codes = _validate_container(payload)
        assert any(cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED in c
                   and "finish_signature" in c for c in codes)

    def test_per_variation_reference_subset_enforced(self):
        from apps.pipeline.services import container_gate1 as cg1
        payload = _container_payload()
        payload["variations"][0]["reference_ids"] = [1, 2, 99]   # 99 not approved
        codes = _validate_container(payload)
        assert any(cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED in c
                   and "reference_ids" in c for c in codes)


# --- §4/§5/§6 + §3 end-to-end through _render_variations --------------------

class ContainerRenderTests(_ContainerTaskMixin):
    def _brief(self, direction_id="d1"):
        return CreativeBrief.objects.create(
            task=self.task,
            design_intent={"schema_version": "structured_director/2.3",
                           "confidence": "high"},
            directions=[{"direction_id": direction_id, "name": "Liquid Petal Veil",
                         "design_axis": "vector"}],
            selected_direction_id=direction_id)

    @patch("apps.pipeline.agents.creative_director.call_claude")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.image_producer.openai.images.edit")
    def test_named_identities_persist_and_no_house_ref_ships(
            self, mock_edit, mock_gen, mock_pe, mock_cd):
        import json

        from apps.pipeline.agents.aria import ARIAAgent
        self._brief()
        rows = self._approve(2)
        self._house_reference()
        payload = _container_payload()
        payload["approved_reference_ids"] = sorted(r.pk for r in rows)
        payload["influence_plan_hash"] = "planhash123"
        for v in payload["variations"]:
            v["reference_ids"] = [rows[0].pk]
        mock_pe.return_value = _claude(payload)
        mock_edit.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL="gpt-image-1",
                               BRAND_LOGO_PATH="", MAX_REVISION_PASSES=0):
            with patch("apps.pipeline.agents.qa_reviewer.call_claude",
                       return_value=_claude(critique(8))):
                aria = ARIAAgent(self.task.pk)
                aria._render_variations(
                    {"direction_id": "d1", "name": "Liquid Petal Veil"})
        mock_cd.assert_not_called()               # §15: no Creative Director
        mock_gen.assert_not_called()
        images = GeneratedImage.objects.filter(task=self.task)
        assert images.count() == 3
        identities = {i.reference_provenance.get("variation_identity")
                      for i in images}
        from apps.pipeline.services import container_gate1 as cg1
        assert identities == set(cg1.CONTAINER_VARIATION_IDENTITIES)
        for i in images:                          # §2/§3: only approved shipped
            prov = i.reference_provenance
            files = prov["visual_files_passed"]
            assert not any("house" in f for f in files)
            assert prov["concept_reference_ids"]
            # §4/§6: the structured per-variation record persists
            contract = prov["container_variation_contract"]
            assert contract["typography_signature"]
            assert contract["native_reconstruction_plan"]
            assert prov["assigned_reference_ids"]        # per-variation subset

    @patch("apps.pipeline.agents.creative_director.call_claude")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.image_producer.openai.images.edit")
    def test_non_distinct_contract_is_drawn_after_its_one_retry_with_a_note(
            self, mock_edit, mock_gen, mock_pe, mock_cd):
        """[Re-pinned by his test blocker on design 123, 2026-10-09 (transcribed at ea2b98b), (2): "Every "not distinct"
        check: it never stops a design. On failure it retries once with the reason; if it still fails, it shows me the
        three anyway with a note, and I choose."] Three too alike, twice: drawn, the step's record carrying its codes
        for the note; a contract refused on anything else still draws nothing (below)."""
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
        from apps.pipeline.models import AgentLog
        from apps.pipeline.services import container_gate1 as cg1
        self._brief()
        rows = self._approve(2)
        payload = _container_payload(distinct=False)
        payload["approved_reference_ids"] = sorted(r.pk for r in rows)
        payload["influence_plan_hash"] = "planhash123"
        for v in payload["variations"]:
            v["reference_ids"] = [rows[0].pk]
        mock_pe.return_value = _claude(payload)
        mock_edit.return_value = _b64_response()
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL="gpt-image-1",
                               BRAND_LOGO_PATH="", MAX_REVISION_PASSES=0):
            with patch("apps.pipeline.agents.qa_reviewer.call_claude",
                       return_value=_claude(critique(8))):
                aria = ARIAAgent(self.task.pk)
                aria._render_variations(
                    {"direction_id": "d1", "name": "Liquid Petal Veil"})
        assert mock_pe.call_count == 2                    # retried once with the reason
        mock_cd.assert_not_called()               # §15
        assert GeneratedImage.objects.filter(task=self.task).count() == 3
        note = AgentLog.objects.filter(task=self.task, action__startswith="Gate-1 variation contract result"
                                       ).latest("timestamp").payload[SHOWN_ALIKE_KEY]
        assert note["codes"] and all(c.startswith(cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT) for c in note["codes"])
        assert note["alike_attempts"] == [1, 2]

    @patch("apps.pipeline.agents.creative_director.call_claude")
    @patch("apps.pipeline.services.claude_service.call_claude")
    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.image_producer.openai.images.edit")
    def test_a_contract_refused_on_another_check_makes_zero_image_calls(
            self, mock_edit, mock_gen, mock_pe, mock_cd):
        """The fail-closed guard the test above held, on a refusal that is not "not distinct": a variation with no
        native-reconstruction plan, twice — zero image calls, until [Re-pinned by his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 1: "NO planner check ever stops a design (not only "not distinct"): on failure it retries once with the reason; if it still fails, it shows me the three directions with a plain note, and I choose. Apply this to every planner and concept check."] Now drawn, its refusal
        the note beside the three."""
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.direction_signature import SHOWN_ALIKE_KEY
        from apps.pipeline.models import AgentLog
        self._brief()
        rows = self._approve(2)
        payload = _container_payload()
        payload["approved_reference_ids"] = sorted(r.pk for r in rows)
        payload["influence_plan_hash"] = "planhash123"
        for v in payload["variations"]:
            v["reference_ids"] = [rows[0].pk]
            del v["native_reconstruction_plan"]
        mock_pe.return_value = _claude(payload)
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL="gpt-image-1",
                               BRAND_LOGO_PATH=""):
            aria = ARIAAgent(self.task.pk)
            out = aria._render_variations(
                {"direction_id": "d1", "name": "Liquid Petal Veil"})
        assert out != (None, None)
        mock_cd.assert_not_called()               # §15
        assert GeneratedImage.objects.filter(task=self.task).count() == 3
        note = AgentLog.objects.filter(task=self.task, action__startswith="Gate-1 variation contract result"
                                       ).latest("timestamp").payload[SHOWN_ALIKE_KEY]
        assert note["codes"] and note["alike_attempts"] == [1, 2]


# --- §7 rejected set preserved but unselectable -----------------------------

class Gate1SetRejectionTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="x", status="awaiting_gate_1")
        self.images = [GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p",
            variation_number=n + 1) for n in range(3)]

    def test_marked_set_is_preserved_but_unselectable(self):
        from apps.pipeline.services.gate1_review import (
            UNAPPROVED_REFERENCE_GROUNDING, VARIATION_CONTRACT_NOT_PRESERVED,
            gate1_set_status, image_is_selectable, mark_set_rejected)
        ids = mark_set_rejected(
            self.task,
            [UNAPPROVED_REFERENCE_GROUNDING, VARIATION_CONTRACT_NOT_PRESERVED])
        assert sorted(ids) == sorted(i.id for i in self.images)
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"       # never globally failed
        for i in self.images:
            i.refresh_from_db()
            assert i.pk and not image_is_selectable(i)     # preserved, locked
        status = gate1_set_status(self.task)
        assert status["status"] == "GATE1_SET_REJECTED"
        assert UNAPPROVED_REFERENCE_GROUNDING in status["codes"]

    def test_gate1_approve_refuses_a_rejected_image(self):
        from django.contrib.auth.models import User
        from rest_framework.test import APIRequestFactory, force_authenticate

        from apps.pipeline.services.gate1_review import mark_set_rejected
        from apps.pipeline.views import Gate1ApproveView
        mark_set_rejected(self.task, ["UNAPPROVED_REFERENCE_GROUNDING"])
        reviewer = User.objects.create_superuser("rev", "r@r.com", "x")
        req = APIRequestFactory().post(
            f"/api/tasks/{self.task.id}/gate1_approve/",
            {"image_id": self.images[0].id}, format="json")
        force_authenticate(req, user=reviewer)
        resp = Gate1ApproveView.as_view()(req, task_id=self.task.id)
        assert resp.status_code == 409
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"       # not approved


# --- §8 observability -------------------------------------------------------

class ObservabilityTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="x", status="running")

    def test_image_call_records_latency_and_request_id(self):
        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services.cost_ledger import record_image
        rec = record_image("gpt-image-2", operation="image:X", task=self.task,
                           metadata={"latency_ms": 1234,
                                     "provider_request_id": "req_abc",
                                     "prompt_hash": "h"})
        assert rec.metadata["latency_ms"] == 1234
        assert rec.metadata["provider_request_id"] == "req_abc"
        assert ApiCallRecord.objects.get(pk=rec.pk).metadata["prompt_hash"] == "h"

    def test_the_wiring_checks_w4_the_logo_sentence_names_the_product_never_a_carton(self):
        """The clean-up's wiring check, 2026-10-04 (its finding W4): the sentence that places the house logo, and the
        product's form, name the product — never "the carton", which every design was told, a bottle's too."""
        from apps.pipeline.agents.image_producer import ImageProducerAgent
        agent = ImageProducerAgent(self.task, [], log_fn=lambda *a, **k: None,
                                   product_profile={"physical_format": "pump bottle"})
        text = agent._grounded_prompt("a pump bottle, straight-on on a plain ground", True)
        assert "carton" not in text.lower(), text
        assert "on the product as the brand mark" in text and "the product is a pump bottle" in text, text

    def test_absent_request_id_is_reported_honestly(self):
        from apps.pipeline.services.cost_ledger import (
            PROVIDER_REQUEST_ID_NOT_RETURNED, provider_request_id)
        resp = MagicMock(spec=[])          # no _request_id attribute
        assert provider_request_id(resp) == PROVIDER_REQUEST_ID_NOT_RETURNED
        # and a real id is passed through
        resp2 = MagicMock()
        resp2._request_id = "req_xyz"
        assert provider_request_id(resp2) == "req_xyz"


# ---------------------------------------------------------------------------
# §BH57(a)3 — THE LOGO IS ACTUALLY ATTACHED, AND NO NEW LIE REPLACES THE OLD.
#
# §BH56 measured the defect: `provider_files()` returned nothing whenever there
# was no design reference, so a zero-reference run attached NO logo, took the
# plain `generate` branch, and sent a prompt the system had instructed to say
# "the official BBROSE logo placed <where>". Provenance:
# `official_logo_included: false`. The model was told a logo was attached, none
# was, and it drew the wordmark itself. The owner: "a lie to the model is worse
# than a limit."
# ---------------------------------------------------------------------------


class LoneLogoReachesTheProviderTests(TestCase):

    def _bundle(self, *, logo, refs):
        from apps.pipeline.services.visual_reference_resolver import VisualReferenceBundle
        return VisualReferenceBundle(task_id=0, concept_references=[], upload_paths=list(refs),
                                     logo_path=logo, logo_is_uploaded=False)

    def test_a_lone_logo_now_reaches_the_provider(self):
        files, has_logo = self._bundle(logo="/tmp/logo.png", refs=[]).provider_files()
        self.assertEqual(files, ["/tmp/logo.png"])
        self.assertTrue(has_logo, "the prompt claims a logo; it must actually be attached")

    def test_the_logo_still_leads_when_references_exist(self):
        files, has_logo = self._bundle(logo="/tmp/logo.png", refs=["/tmp/a.png"]).provider_files()
        self.assertEqual(files, ["/tmp/logo.png", "/tmp/a.png"])
        self.assertTrue(has_logo)

    def test_no_logo_and_no_references_still_takes_the_plain_generate_path(self):
        """The only case that keeps the old contract: nothing to attach, so nothing is attached."""
        files, has_logo = self._bundle(logo=None, refs=[]).provider_files()
        self.assertEqual(files, [])
        self.assertFalse(has_logo)

    def test_a_variation_with_no_assigned_reference_still_gets_the_logo(self):
        files, has_logo, opened = self._bundle(logo="/tmp/logo.png", refs=[]).provider_files_for([])
        self.assertEqual(files, ["/tmp/logo.png"])
        self.assertTrue(has_logo)
        self.assertEqual(opened, [])
