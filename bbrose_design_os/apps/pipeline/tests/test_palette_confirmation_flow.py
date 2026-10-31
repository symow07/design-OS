"""PALT-M4C-4 §2 — the confirmation flow, end to end.

A route existing is not proof. These exercise the whole production path:
the state a task waits in, the governed record a confirmation creates, the
versioning, the refusal to let a draft drive geometry, permissions, and
the Review Board link.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.core.models import Brand, Product
from apps.pipeline.models import (
    DesignTask, GateDecision, PaletteIntentConfirmation)
from apps.pipeline.services import palette_confirmation_flow as flow
from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_es3083_intent as es
from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_intent_confirmation as pic


def _task():
    brand = Brand.objects.create(name="BBROSE", master_brief="x")
    product = Product.objects.create(
        brand=brand, product_id="ES-3083", name="Outer Glow",
        category="EY", year=2026, product_type="eyeshadow palette")
    return DesignTask.objects.create(
        brand=brand, product=product, task_text="ES3083 palette",
        status="running", design_target="palette")


class ConfirmationFlowTests(TestCase):
    def setUp(self):
        self.task = _task()
        self.draft = es.build_es3083_intent()

    def test_opening_the_flow_parks_the_task_in_its_own_state(self):
        panel = flow.open_confirmation(self.task, self.draft)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, flow.AWAITING)
        self.assertEqual(panel["title"],
                         "WHAT THE ENGINE UNDERSTOOD FROM THE SELECTED "
                         "DESIGN")

    def test_a_confirmation_creates_a_governed_record(self):
        flow.open_confirmation(self.task, self.draft)
        row = flow.save_confirmation(self.task, self.draft,
                                     OC.confirmation_record())
        self.assertEqual(row.version, 1)
        self.assertIsNotNone(row.gate_decision)
        self.assertEqual(row.gate_decision.gate, "design_intent")
        self.assertEqual(row.gate_decision.decision, "approve")
        self.assertEqual(GateDecision.objects.filter(
            task=self.task, gate="design_intent").count(), 1)

    def test_the_confirmation_is_not_gate_1_or_gate_2(self):
        """It approves a READING. Nothing keyed off a real gate may
        advance because of it."""
        flow.open_confirmation(self.task, self.draft)
        flow.save_confirmation(self.task, self.draft,
                               OC.confirmation_record())
        self.assertFalse(GateDecision.objects.filter(
            task=self.task, gate__in=["gate_1", "gate_2"]).exists())
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, flow.CONFIRMED)
        self.assertNotIn(self.task.status,
                         ("gate_1_approved", "gate_2_approved"))
        self.assertFalse(flow.flow_state(self.task)["grants_gate_approval"])

    def test_it_refuses_a_confirmation_from_the_wrong_state(self):
        self.task.status = "queued"
        self.task.save()
        with self.assertRaises(flow.ConfirmationFlowError):
            flow.save_confirmation(self.task, self.draft,
                                   OC.confirmation_record())

    def test_a_revision_supersedes_rather_than_overwrites(self):
        flow.open_confirmation(self.task, self.draft)
        first = flow.save_confirmation(self.task, self.draft,
                                       OC.confirmation_record())
        flow.open_confirmation(self.task, self.draft)
        second_record = OC.confirmation_record()
        second_record.apply(pic.ConfirmationAction(
            field_name="mirror_presence", action=pic.CORRECT,
            new_value=True, note="owner saw a mirror", route="PANEL_ACTION"))
        second = flow.save_confirmation(self.task, self.draft,
                                        second_record)
        first.refresh_from_db()
        self.assertEqual(second.version, 2)
        self.assertEqual(first.superseded_by_id, second.pk)
        self.assertFalse(first.is_current)
        self.assertTrue(second.is_current)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 2)
        self.assertNotEqual(first.confirmed_intent_identity,
                            second.confirmed_intent_identity)

    def test_history_keeps_every_version_oldest_first(self):
        for _ in range(3):
            flow.open_confirmation(self.task, self.draft)
            flow.save_confirmation(self.task, self.draft,
                                   OC.confirmation_record())
        versions = [r.version for r in flow.revision_history(self.task)]
        self.assertEqual(versions, [1, 2, 3])
        self.assertEqual(flow.current_confirmation(self.task).version, 3)

    def test_the_confirmed_intent_rehydrates(self):
        flow.open_confirmation(self.task, self.draft)
        row = flow.save_confirmation(self.task, self.draft,
                                     OC.confirmation_record())
        back = flow.rehydrate(row)
        self.assertEqual(back.identity(), row.confirmed_intent_identity)
        self.assertEqual(back.get("pan_count").value, 12)
        self.assertEqual(back.get("pan_shapes").constraint_level, di.HARD)

    def test_a_draft_cannot_drive_geometry(self):
        """This refusal is why the confirmation state exists."""
        with self.assertRaises(flow.UnconfirmedIntentError) as ctx:
            flow.map_confirmed_intent(self.draft)
        self.assertIn("HUMAN_CONFIRMED_DESIGN_INTENT", str(ctx.exception))

    def test_a_partly_confirmed_intent_is_still_refused_by_name(self):
        """The §1 confirmation covers visible composition, so HARD fields
        it did not touch remain drafts and must still block geometry."""
        flow.open_confirmation(self.task, self.draft)
        row = flow.save_confirmation(self.task, self.draft,
                                     OC.confirmation_record())
        with self.assertRaises(flow.UnconfirmedIntentError) as ctx:
            flow.map_confirmed_intent(row)
        msg = str(ctx.exception)
        self.assertIn("opening_direction", msg)
        self.assertIn("regulatory_zones", msg)

    def test_a_fully_confirmed_intent_maps_to_the_engineering_contract(self):
        """The whole path: confirmed intent -> mapper -> contract."""
        flow.open_confirmation(self.task, self.draft)
        record = OC.confirmation_record()
        for name in ("opening_direction", "regulatory_zones"):
            record.apply(pic.ConfirmationAction(
                field_name=name, action=pic.CONFIRM,
                note="confirmed alongside the visible composition", route="PANEL_ACTION"))
        row = flow.save_confirmation(self.task, self.draft, record)
        contract = flow.map_confirmed_intent(row)
        self.assertTrue(contract)
        resolved = contract["resolved"]
        self.assertEqual(resolved["pan.shape"]["value"], "RECTANGULAR")
        self.assertEqual(resolved["pan.count"]["value"], 12)
        self.assertNotEqual(resolved["pan.shape"]["origin"],
                            resolved["tray.width_mm"]["origin"])

    def test_flow_state_links_the_review_board_to_the_record(self):
        flow.open_confirmation(self.task, self.draft)
        flow.save_confirmation(self.task, self.draft,
                               OC.confirmation_record())
        state = flow.flow_state(self.task)
        self.assertEqual(state["current_version"], 1)
        self.assertEqual(state["gate"], "design_intent")
        self.assertIn(str(self.task.pk), state["review_board_url"])
        self.assertEqual(state["scope"], "VISIBLE_COMPOSITION_ONLY")
        self.assertFalse(state["owner_approved"])
        self.assertEqual(state["manufacturing_authority"],
                         "NOT_ESTABLISHED")


class ConfirmationPageTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user("owner", password="pw")
        self.editor = User.objects.create_user("editor", password="pw")
        self.editor.user_permissions.add(
            Permission.objects.get(codename="change_designtask"))
        self.task = _task()

    def test_the_page_requires_login(self):
        url = reverse("dashboard:palette_intent_confirmation")
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_it_shows_what_the_engine_understood(self):
        self.client.force_login(self.user)
        r = self.client.get(
            reverse("dashboard:palette_intent_confirmation"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "WHAT THE ENGINE UNDERSTOOD")
        self.assertContains(r, "es3083_understanding.png")
        self.assertContains(r, "not registered onto the source image")
        self.assertContains(r, "No Image Trace was used")

    def test_it_shows_the_confirmed_grid_and_the_scope_limits(self):
        self.client.force_login(self.user)
        r = self.client.get(
            reverse("dashboard:palette_intent_confirmation"))
        self.assertContains(r, "VISIBLE_COMPOSITION_ONLY")
        self.assertContains(r, "manufacturing feasibility")
        self.assertContains(r, "hinge construction")

    def test_a_task_page_shows_the_flow_state(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.get(reverse(
            "dashboard:palette_intent_confirmation_task",
            args=[self.task.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, flow.AWAITING)
        self.assertContains(r, "Save these corrections and confirm")
        # the per-field action affordance must be present, not just a
        # single blanket confirm button
        self.assertContains(r, "action_pan_shapes")
        self.assertContains(r, "RECLASSIFY")

    def test_a_user_without_permission_cannot_confirm(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.user)
        r = self.client.post(reverse(
            "dashboard:palette_intent_confirmation_task",
            args=[self.task.pk]))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 0)

    def test_a_permitted_user_records_a_versioned_confirmation(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]), {"notes": "looks right"})
        self.assertEqual(r.status_code, 302)
        row = PaletteIntentConfirmation.objects.get()
        self.assertEqual(row.version, 1)
        self.assertEqual(row.confirmed_by, self.editor)
        self.assertIn("looks right", row.gate_decision.notes)

    def test_a_per_field_correction_is_saved(self):
        """The owner's corrections must reach the record, not just a
        blanket confirmation."""
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_mirror_presence": "CORRECT",
             "value_mirror_presence": "yes",
             "notes": "there is a mirror"})
        row = PaletteIntentConfirmation.objects.get()
        applied = [a for a in row.actions
                   if a["field_name"] == "mirror_presence"
                   and a["action"] == "CORRECT"]
        self.assertTrue(applied)
        # the draft holds a bool here, so the form string is coerced
        self.assertIs(applied[-1]["new_value"], True)
        self.assertIs(flow.rehydrate(row).get("mirror_presence").value,
                      True)

    def test_a_nonsense_value_for_a_yes_no_field_is_refused(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_mirror_presence": "CORRECT",
             "value_mirror_presence": "MIRROR_PRESENT"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 0)

    def test_an_integer_correction_round_trips_as_an_integer(self):
        """Form values arrive as strings; storing "12" where the draft
        holds 12 would break every downstream comparison."""
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_pan_count": "CORRECT", "value_pan_count": "15"})
        row = PaletteIntentConfirmation.objects.get()
        value = flow.rehydrate(row).get("pan_count").value
        self.assertIsInstance(value, int)
        self.assertEqual(value, 15)

    def test_a_list_correction_round_trips_as_a_list(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_colour_zones": "CORRECT",
             "value_colour_zones": "PANTONE 621 C, PANTONE 700 C"})
        row = PaletteIntentConfirmation.objects.get()
        self.assertEqual(flow.rehydrate(row).get("colour_zones").value,
                         ["PANTONE 621 C", "PANTONE 700 C"])

    def test_a_non_numeric_correction_to_a_number_is_refused(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_pan_count": "CORRECT", "value_pan_count": "twelve"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 0)

    def test_an_empty_correction_is_refused_rather_than_erasing(self):
        """Applying an empty CORRECT would erase the reading and record
        the loss as an owner decision."""
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_pan_shapes": "CORRECT", "value_pan_shapes": "   "})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 0)

    def test_a_malformed_action_is_refused(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_pan_shapes": "NOT_AN_ACTION"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 0)

    def test_posting_without_a_task_is_refused(self):
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation"))
        self.assertEqual(r.status_code, 400)

    def test_a_revision_can_be_driven_entirely_through_the_ui(self):
        """§2 requires retry and revision history to work. Every earlier
        revision test called open_confirmation in Python, so the UI path
        was never exercised."""
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        url = reverse("dashboard:palette_intent_confirmation_task",
                      args=[self.task.pk])
        self.client.post(url, {"action_pan_shapes": "CONFIRM"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, flow.CONFIRMED)

        page = self.client.get(url)
        self.assertContains(page, "Revise this confirmation")
        self.client.post(url, {"reopen": "1"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, flow.AWAITING)

        self.client.post(url, {"action_pan_count": "CORRECT",
                               "value_pan_count": "9"})
        rows = flow.revision_history(self.task)
        self.assertEqual([r.version for r in rows], [1, 2])
        self.assertFalse(rows[0].is_current)
        self.assertTrue(rows[1].is_current)
        self.assertEqual(flow.rehydrate(rows[1]).get("pan_count").value, 9)

    def test_reopening_an_unconfirmed_task_is_refused(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        r = self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]), {"reopen": "1"})
        self.assertEqual(r.status_code, 400)

    def test_a_post_stores_only_the_actions_it_carried(self):
        """Replaying the canonical §1 record on every post would attribute
        a dozen decisions the poster never made to the poster."""
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"action_pan_shapes": "CONFIRM"})
        row = PaletteIntentConfirmation.objects.get()
        self.assertEqual(len(row.actions), 1)
        self.assertEqual(row.actions[0]["field_name"], "pan_shapes")
        self.assertEqual(row.actions[0]["action"], "CONFIRM")

    def test_the_es3083_baseline_is_applied_only_when_asked(self):
        flow.open_confirmation(self.task, es.build_es3083_intent())
        self.client.force_login(self.editor)
        self.client.post(
            reverse("dashboard:palette_intent_confirmation_task",
                    args=[self.task.pk]),
            {"apply_es3083_baseline": "1"})
        row = PaletteIntentConfirmation.objects.get()
        self.assertGreater(len(row.actions), 5)
        self.assertEqual(flow.rehydrate(row).get("pan_count").value, 12)

    def test_the_history_is_shown_after_a_second_confirmation(self):
        draft = es.build_es3083_intent()
        for _ in range(2):
            flow.open_confirmation(self.task, draft)
            flow.save_confirmation(self.task, draft,
                                   OC.confirmation_record(),
                                   user=self.editor)
        self.client.force_login(self.editor)
        r = self.client.get(reverse(
            "dashboard:palette_intent_confirmation_task",
            args=[self.task.pk]))
        self.assertContains(r, "Revision history")
        self.assertContains(r, "superseded")
