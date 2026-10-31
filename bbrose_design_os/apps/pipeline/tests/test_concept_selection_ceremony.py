"""pipeline_container_concept_selection/1.0 — chain-grade RECORD of the
human Gate-1 concept selection (2C-2D-CORR-2 §3).

The event grants nothing, recreates nothing, and duplicates nothing: it
records the EXISTING GateDecision + hashed metadata record + visual
contract, idempotently, signed under the active epoch."""
from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.utils import timezone

from apps.accounts import authz_policy as authz
from apps.accounts import bootstrap_registry as reg
from apps.accounts.decision_chain import (
    event_integrity_state,
    verify_chain,
    verify_event,
)
from apps.accounts.models import DecisionEvent
from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignProject,
    DesignTask,
    GateDecision,
    GeneratedImage,
)
from apps.pipeline.services import concept_selection_ceremony as ceremony
from apps.pipeline.services import selected_concept_contract as scc

pytestmark = pytest.mark.django_db
User = get_user_model()

_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")

RATIONALE = {"selected_because": ["frosted dusty-rose bottle"],
             "unselected_because": {"A": "too heavy", "C": "too masculine"}}


@pytest.fixture()
def chain_world(settings):
    settings.DECISION_EVENT_HMAC_KEYS = {"epoch-test": "e" * 32}
    settings.DECISION_EVENT_ACTIVE_KEY_ID = "epoch-test"
    settings.BOOTSTRAP_ENABLED = True
    settings.BOOTSTRAP_SINGLE_OPERATOR_ENABLED = True
    settings.DEBUG = True
    settings.ENVIRONMENT = "LOCAL_DEVELOPMENT"
    settings.LOCAL_DEVELOPMENT_DATABASES = [
        settings.DATABASES["default"]["NAME"]]
    from apps.accounts.security import signing
    signing.reset_registry()
    yield settings
    signing.reset_registry()


@pytest.fixture()
def world(chain_world):
    brand = Brand.objects.create(name="BBROSE", master_brief="x")
    product = Product.objects.create(
        brand=brand, product_id="BBR-SK-201", name="Rose Damascena",
        category="SK", year=2026, product_type="carton",
        width_mm=40, depth_mm=40, height_mm=110)
    actor = User.objects.create_superuser("ceremop", password="x")
    project = DesignProject.objects.create(
        brand=brand, product=product, brief="b",
        design_target="complete_product", status="container")
    task = DesignTask.objects.create(
        brand=brand, product=product, task_text="dropper bottle",
        design_target="product_container", stage="container",
        project=project, status="awaiting_container_profile",
        created_by=actor)
    images = []
    for n, vid in enumerate(["A_AMBER_NOCTURNE", "B_ROSE_SMOKE",
                             "C_NOCTURNE_APOTHECARY"], start=1):
        img = GeneratedImage.objects.create(
            task=task, direction_name="Damascena Nocturne",
            prompt_used="p", variation_number=n,
            reference_provenance={"variation_identity": vid})
        img.image_file.save(f"c{n}.png", ContentFile(_PNG), save=True)
        images.append(img)
    selected, unselected = images[1], [images[0], images[2]]
    selected.is_approved = True
    selected.save(update_fields=["is_approved"])
    gd = GateDecision.objects.create(
        task=task, gate="gate_1", decision="approve", decided_by=actor,
        notes="human selection")
    contract = scc.build_visual_contract(
        selected, measurements=[], human_rationale=RATIONALE)
    scc.persist_visual_contract(project, contract)
    scc.record_selection_decision(
        project, selected_image=selected, unselected_images=unselected,
        rationale=RATIONALE, actor=actor,
        contract_hash=contract["contract_hash"],
        now_iso=timezone.now().isoformat())
    return {"actor": actor, "project": project, "task": task, "gd": gd,
            "selected": selected, "unselected": unselected,
            "contract": contract}


class TestCeremony:
    def test_exactly_one_verified_event_with_full_lineage(self, world):
        result = ceremony.record_concept_selection_event(
            task=world["task"], actor=world["actor"])
        assert result.status == "PERFORMED"
        events = DecisionEvent.objects.filter(
            action=reg.PIPELINE_CONTAINER_CONCEPT_SELECT)
        assert events.count() == 1
        event = events.get()
        p = event.payload
        assert p["decision_code"] == "SELECT_CONTAINER_CONCEPT"
        assert p["selected_image_id"] == world["selected"].pk
        assert p["selected_variation_identity"] == "B_ROSE_SMOKE"
        assert p["gate_decision_id"] == world["gd"].pk
        assert [u["image_id"] for u in p["unselected"]] == \
            [i.pk for i in world["unselected"]]
        assert p["visual_contract_hash"] == \
            world["contract"]["contract_hash"]
        record = world["project"].metadata[scc.SELECTION_META_KEY]
        assert p["metadata_decision_record_hash"] == record["record_hash"]
        assert p["signing_epoch"] == "epoch-test" == event.signing_key_id
        assert "does not recreate or alter it" in p["statements"][0]
        # verified: envelope + ceremony semantics + whole chain
        assert verify_event(event) == (True, ())
        assert event_integrity_state(event) == "VERIFIED"
        chain = verify_chain()
        assert chain.ok, chain.problems
        # lineage persisted, original record untouched
        world["project"].refresh_from_db()
        lineage = world["project"].metadata[ceremony.EVENT_META_KEY]
        assert lineage["event_id"] == event.event_id
        assert f"GateDecision #{world['gd'].pk}" in lineage["lineage"]
        assert world["project"].metadata[scc.SELECTION_META_KEY] == record

    def test_gate_decision_is_untouched_and_not_duplicated(self, world):
        gd_before = GateDecision.objects.get(pk=world["gd"].pk)
        snapshot = (gd_before.gate, gd_before.decision, gd_before.notes,
                    gd_before.decided_by_id, gd_before.decided_at)
        ceremony.record_concept_selection_event(
            task=world["task"], actor=world["actor"])
        gd_after = GateDecision.objects.get(pk=world["gd"].pk)
        assert (gd_after.gate, gd_after.decision, gd_after.notes,
                gd_after.decided_by_id, gd_after.decided_at) == snapshot
        assert GateDecision.objects.filter(task=world["task"]).count() == 1

    def test_second_call_is_idempotent(self, world):
        first = ceremony.record_concept_selection_event(
            task=world["task"], actor=world["actor"])
        second = ceremony.record_concept_selection_event(
            task=world["task"], actor=world["actor"])
        assert second.status == "ALREADY_RECORDED"
        assert second.event_id == first.event_id
        assert DecisionEvent.objects.filter(
            action=reg.PIPELINE_CONTAINER_CONCEPT_SELECT).count() == 1

    def test_event_cannot_authorize_anything(self, world):
        ceremony.record_concept_selection_event(
            task=world["task"], actor=world["actor"])
        event = DecisionEvent.objects.get(
            action=reg.PIPELINE_CONTAINER_CONCEPT_SELECT)
        # the action is chain-recordable but NEVER role-authorizable
        assert reg.PIPELINE_CONTAINER_CONCEPT_SELECT not in authz.ACTIONS
        assert reg.PIPELINE_CONTAINER_CONCEPT_SELECT not in authz.POLICY
        assert event.role_used == reg.BOOTSTRAP_OPERATOR
        assert tuple(event.payload["non_authorizations"]) == \
            reg.CONCEPT_SELECT_NON_AUTHORIZATIONS
        for blocked in ("profile_confirmation", "zone_confirmation",
                        "native_reconstruction", "gate_2",
                        "packaging_creation", "production_authority"):
            assert blocked in event.payload["non_authorizations"]
        # nothing about the task/profile state changed
        world["task"].refresh_from_db()
        assert world["task"].status == "awaiting_container_profile"

    def test_tampered_contract_hash_fails_verification(self, world):
        ceremony.record_concept_selection_event(
            task=world["task"], actor=world["actor"])
        event = DecisionEvent.objects.get(
            action=reg.PIPELINE_CONTAINER_CONCEPT_SELECT)
        # simulate a later metadata swap: verification must flag disagreement
        meta = dict(world["project"].metadata)
        contract = dict(meta[scc.META_KEY])
        contract["contract_hash"] = "0" * 64
        meta[scc.META_KEY] = contract
        world["project"].metadata = meta
        world["project"].save(update_fields=["metadata"])
        from apps.accounts.bootstrap_verification import verify_bootstrap_event
        problems = verify_bootstrap_event(event)
        assert any("visual contract hash" in p for p in problems)

    def test_missing_records_fail_closed(self, world):
        meta = dict(world["project"].metadata)
        meta.pop(scc.SELECTION_META_KEY)
        world["project"].metadata = meta
        world["project"].save(update_fields=["metadata"])
        with pytest.raises(ceremony.ConceptSelectionCeremonyError) as e:
            ceremony.record_concept_selection_event(
                task=world["task"], actor=world["actor"])
        assert e.value.code == "SELECTION_RECORDS_MISSING"
        assert DecisionEvent.objects.count() == 0
