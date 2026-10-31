"""Print-data entry/review screen + recovery report (Phase 2A-6B §1, §5, §6)."""
from __future__ import annotations

import json

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.permissions import ROLE_DESIGNER, ROLE_REVIEWER
from apps.pipeline.services.print_data_recovery import (
    entry_screen,
    recovery_report,
    save_print_data,
)

REAL_RECORD = {
    "brand_display_name": "BBROSE",
    "product_name": "Skynte Foundation",
    "product_type": "Fundación facial",
    "ingredients": "AQUA, GLYCERIN, TITANIUM DIOXIDE",
    "how_to_use": "Shake well before use.",
    "warnings": "For external use only.",
    "net_weight": "30 ml / 1.0 fl. oz.",
    "manufacturer": "YIWU YIBIN TRADING COMPANY",
    "country_of_origin": "Made in China",
}


def _user(name, role):
    u = User.objects.create_user(name, f"{name}@t.com", "pw")
    g, _ = Group.objects.get_or_create(name=role)
    u.groups.add(g)
    return u


class EntryScreenTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="awaiting_gate_2", brand=self.brand)
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=self.image,
            spec_sheet={"panel_info": {},
                        "panel_info_incident": {
                            "incident_id": "PRINT-DATA-47",
                            "fields_lost": ["ingredients", "warnings"]}})

    def test_every_contract_field_is_offered(self):
        screen = entry_screen(self.task)
        keys = {f.key for f in screen.fields}
        for expected in ("brand_display_name", "product_name", "product_type",
                         "description", "ingredients", "how_to_use",
                         "warnings", "net_weight", "shade", "item_no",
                         "barcode_ean", "qr_url", "batch_code", "manufacturer",
                         "marketer", "importer", "country_of_origin"):
            self.assertIn(expected, keys)

    def test_states_are_shown_for_every_field(self):
        for entry in entry_screen(self.task).fields:
            self.assertIn(entry.state, {"VERIFIED", "UNVERIFIED", "MISSING",
                                        "PLACEHOLDER", "NOT_APPLICABLE"})

    def test_legal_and_formula_fields_are_never_prefilled(self):
        """Even when a Product record could supply them."""
        product = Product.objects.create(
            brand=self.brand, product_id="P-1", name="Other Product",
            category="CO", year=2026,
            ingredients="SOMEONE ELSE'S INCI",
            warnings_text="Someone else's warning.",
            net_weight="99 ml")
        self.task.product = product
        self.task.save()
        screen = entry_screen(self.task)
        by_key = {f.key: f for f in screen.fields}
        for legal in ("ingredients", "warnings", "net_weight", "manufacturer",
                      "country_of_origin"):
            self.assertEqual(by_key[legal].value, "",
                             f"{legal} was prefilled from another record")
            self.assertFalse(by_key[legal].from_default)

    def test_non_legal_defaults_are_offered_but_flagged(self):
        product = Product.objects.create(
            brand=self.brand, product_id="P-2", name="Skynte Foundation",
            category="CO", year=2026, description="From the product record.")
        self.task.product = product
        self.task.save()
        by_key = {f.key: f for f in entry_screen(self.task).fields}
        self.assertEqual(by_key["product_name"].value, "Skynte Foundation")
        self.assertTrue(by_key["product_name"].from_default)

    def test_outstanding_lists_required_gaps(self):
        screen = entry_screen(self.task)
        self.assertFalse(screen.complete)
        for required in ("ingredients", "warnings", "net_weight"):
            self.assertIn(required, screen.outstanding)

    def test_incident_is_surfaced(self):
        screen = entry_screen(self.task)
        self.assertEqual(screen.incident["incident_id"], "PRINT-DATA-47")

    def test_rendered_artifact_values_are_not_treated_as_verified(self):
        """The screen reads the STRUCTURED record only. An intact rendered
        artifact does not make a field verified."""
        screen = entry_screen(self.task)
        by_key = {f.key: f for f in screen.fields}
        self.assertEqual(by_key["ingredients"].state, "MISSING")


class SaveAndSnapshotTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="awaiting_gate_2", brand=self.brand)
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=self.image, spec_sheet={})

    def test_saving_stores_only_contract_fields(self):
        save_print_data(self.task, {**REAL_RECORD,
                                    "task_text": "internal brief",
                                    "prompt_used": "a photo of"})
        self.output.refresh_from_db()
        stored = self.output.spec_sheet["panel_info"]
        self.assertNotIn("task_text", stored)
        self.assertNotIn("prompt_used", stored)
        self.assertEqual(stored["ingredients"], REAL_RECORD["ingredients"])

    def test_saving_returns_a_deterministic_snapshot_hash(self):
        first = save_print_data(self.task, dict(REAL_RECORD))
        second = save_print_data(self.task, dict(REAL_RECORD))
        self.assertEqual(first["snapshot_hash"], second["snapshot_hash"])
        self.assertEqual(len(first["snapshot_hash"]), 64)

    def test_translations_are_stored_and_snapshotted(self):
        saved = save_print_data(
            self.task, dict(REAL_RECORD),
            translations={"es": {"warnings": "Solo para uso externo."}})
        self.output.refresh_from_db()
        self.assertIn("es", self.output.spec_sheet["panel_info"]["translations"])
        self.assertIn("es", saved["snapshot"]["translations"])

    def test_saved_record_becomes_complete(self):
        save_print_data(self.task, dict(REAL_RECORD))
        self.assertTrue(entry_screen(self.task).complete)


class RecoveryReportTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="awaiting_gate_2", brand=self.brand)
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=self.image,
            spec_sheet={"panel_info": {}, "panel_info_incident": {
                "incident_id": "PRINT-DATA-47-2026-07-20",
                "fields_lost": ["ingredients", "warnings", "translations"],
                "restoration_source": "AWAITING_USER_ENTRY"}})

    def test_report_carries_the_required_sections(self):
        report = recovery_report(self.task)
        for key in ("incident_id", "task_id", "fields_lost",
                    "restoration_source", "restored_snapshot_hash",
                    "replay_snapshot_hash", "differences", "result"):
            self.assertIn(key, report)
        self.assertEqual(report["result"], "AWAITING_USER_ENTRY")

    def test_report_reflects_a_restored_record(self):
        save_print_data(self.task, dict(REAL_RECORD))
        report = recovery_report(self.task)
        self.assertEqual(report["result"], "RECORD_PRESENT_REPLAY_PENDING")
        self.assertTrue(report["restored_snapshot_hash"])

    def test_report_states_replay_differences(self):
        from apps.pipeline.services.print_data_snapshot import (
            snapshot_from_panel_info,
        )
        before = snapshot_from_panel_info(self.task.pk, dict(REAL_RECORD))
        lossy = {k: v for k, v in REAL_RECORD.items() if k != "warnings"}
        after = snapshot_from_panel_info(self.task.pk, lossy)
        report = recovery_report(self.task, before=before, after=after)
        self.assertEqual(report["result"], "REPLAY_DIFFERENCES_FOUND")
        self.assertTrue(report["differences"])

    def test_identical_replay_is_reported_as_such(self):
        from apps.pipeline.services.print_data_snapshot import (
            snapshot_from_panel_info,
        )
        snap = snapshot_from_panel_info(self.task.pk, dict(REAL_RECORD))
        report = recovery_report(self.task, before=snap, after=snap)
        self.assertEqual(report["result"], "REPLAY_IDENTICAL")
        self.assertEqual(report["differences"], [])

    def test_no_decision_event_is_created(self):
        from apps.accounts.models import DecisionEvent
        before = DecisionEvent.objects.count()
        save_print_data(self.task, dict(REAL_RECORD))
        recovery_report(self.task)
        self.assertEqual(DecisionEvent.objects.count(), before)


class PrintDataEndpointTests(TestCase):
    def setUp(self):
        self.reviewer = _user("rev-pd", ROLE_REVIEWER)
        self.designer = _user("des-pd", ROLE_DESIGNER)
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="awaiting_gate_2", brand=self.brand)
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u")
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=self.image, spec_sheet={})

    def test_reviewer_can_read_the_screen(self):
        self.client.force_login(self.reviewer)
        res = self.client.get(f"/api/tasks/{self.task.id}/print_data/")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("entry", body)
        self.assertIn("recovery", body)
        self.assertFalse(body["entry"]["complete"])

    def test_reviewer_can_save_and_gets_a_hash(self):
        self.client.force_login(self.reviewer)
        res = self.client.post(
            f"/api/tasks/{self.task.id}/print_data/",
            data=json.dumps({"values": REAL_RECORD}),
            content_type="application/json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["snapshot_hash"]), 64)
        self.assertTrue(res.json()["entry"]["complete"])

    def test_designer_cannot_write(self):
        self.client.force_login(self.designer)
        res = self.client.post(
            f"/api/tasks/{self.task.id}/print_data/",
            data=json.dumps({"values": REAL_RECORD}),
            content_type="application/json")
        self.assertEqual(res.status_code, 403)

    def test_malformed_payload_is_refused(self):
        self.client.force_login(self.reviewer)
        res = self.client.post(
            f"/api/tasks/{self.task.id}/print_data/",
            data=json.dumps({"values": "not an object"}),
            content_type="application/json")
        self.assertEqual(res.status_code, 400)
