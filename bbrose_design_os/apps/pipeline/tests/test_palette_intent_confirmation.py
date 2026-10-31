"""PALT-M4C M4C-4 — human confirmation contract and the review surface."""
import pytest
from django.test import SimpleTestCase
from django.urls import reverse

from apps.pipeline.services import palette_design_intent as di
from apps.pipeline.services import palette_intent_confirmation as pc
from apps.pipeline.services.palette_es3083_intent import build_es3083_intent


def _rec(intent):
    return pc.ConfirmationRecord(concept_reference=intent.concept_reference,
                                 draft_identity=intent.identity())


class PanelTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.intent = build_es3083_intent()
        cls.panel = pc.panel(cls.intent)

    def test_the_panel_states_what_it_is(self):
        self.assertEqual(
            self.panel["title"],
            "WHAT THE ENGINE UNDERSTOOD FROM THE SELECTED DESIGN")
        self.assertIn("ES3083", self.panel["concept_reference"])

    def test_every_required_row_is_present(self):
        fields = {r["field"] for r in self.panel["rows"]}
        for required in pc.REQUIRED_PANEL_ROWS:
            self.assertIn(required, fields, required)

    def test_each_row_carries_confidence_and_level(self):
        for r in self.panel["rows"]:
            if r["field"] == "selected_source_image":
                continue
            self.assertIn("confidence", r)
            self.assertIn("level", r)
            self.assertIn("state", r)

    def test_undetected_fields_are_marked_unresolved(self):
        row = next(r for r in self.panel["rows"]
                   if r["field"] == "relative_pan_sizes")
        self.assertEqual(row["state"], pc.UNRESOLVED)
        self.assertIsNone(row["understood"])

    def test_approximate_readings_stay_provisional(self):
        for name in ("pan_count", "rows", "columns"):
            row = next(r for r in self.panel["rows"] if r["field"] == name)
            self.assertEqual(row["state"], pc.PROVISIONAL)
            self.assertLess(row["confidence"], 0.7)

    def test_the_visible_pan_shape_is_a_provisional_visible_constraint(self):
        row = next(r for r in self.panel["rows"]
                   if r["field"] == "pan_shapes")
        self.assertEqual(row["understood"], "RECTANGULAR")
        self.assertEqual(row["state"], pc.PROVISIONAL_VISIBLE)

    def test_the_panel_never_claims_approval(self):
        self.assertFalse(self.panel["owner_approved"])
        self.assertEqual(self.panel["state"], di.DRAFT)
        self.assertIn("only", self.panel["warning"])

    def test_all_owner_actions_are_offered(self):
        for a in (pc.CONFIRM, pc.CORRECT, pc.DELETE, pc.ADD,
                  pc.RECLASSIFY, pc.MARK_UNRESOLVED, pc.NOTE):
            self.assertIn(a, self.panel["available_actions"])
        self.assertEqual(self.panel["available_levels"],
                         list(di.CONSTRAINT_LEVELS))


class ConfirmationActionTests(SimpleTestCase):
    def setUp(self):
        self.intent = build_es3083_intent()

    def test_confirm_promotes_to_design_authority(self):
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("pan_shapes", pc.CONFIRM, route="PANEL_ACTION"))
        out = pc.apply_confirmations(self.intent, rec)
        self.assertTrue(out.get("pan_shapes").is_design_authority)

    def test_correct_changes_the_value_and_records_it(self):
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("pan_count", pc.CORRECT, new_value=12,
                                  note="counted on the tray", route="PANEL_ACTION"))
        out = pc.apply_confirmations(self.intent, rec)
        f = out.get("pan_count")
        self.assertEqual(f.value, 12)
        self.assertEqual(f.confirmation_state, di.CORRECTED)
        self.assertIn("counted on the tray", f.note)

    def test_reclassify_changes_the_constraint_level(self):
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("pan_count", pc.RECLASSIFY,
                                  new_level=di.HARD, route="PANEL_ACTION"))
        out = pc.apply_confirmations(self.intent, rec)
        self.assertEqual(out.get("pan_count").constraint_level, di.HARD)

    def test_delete_removes_the_field(self):
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("ornament", pc.DELETE, route="PANEL_ACTION"))
        out = pc.apply_confirmations(self.intent, rec)
        self.assertIsNone(out.get("ornament"))

    def test_add_creates_an_owner_stated_field(self):
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("applicator_zone", pc.ADD,
                                  new_value="NONE", new_level=di.HARD, route="PANEL_ACTION"))
        out = pc.apply_confirmations(self.intent, rec)
        f = out.get("applicator_zone")
        self.assertEqual(f.extraction_method, "OWNER_STATED")
        self.assertTrue(f.is_design_authority)

    def test_mark_unresolved_keeps_it_pending(self):
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("mirror_presence", pc.MARK_UNRESOLVED,
                                  note="lid interior not visible", route="PANEL_ACTION"))
        out = pc.apply_confirmations(self.intent, rec)
        f = out.get("mirror_presence")
        self.assertEqual(f.confirmation_state, di.PENDING)
        self.assertIn("UNRESOLVED", f.note)

    def test_the_draft_is_never_mutated(self):
        before = self.intent.identity()
        rec = _rec(self.intent).apply(
            pc.ConfirmationAction("pan_count", pc.CORRECT, new_value=12, route="PANEL_ACTION"))
        pc.apply_confirmations(self.intent, rec)
        self.assertEqual(self.intent.identity(), before)
        self.assertEqual(self.intent.get("pan_count").constraint_level,
                         di.SOFT)

    def test_unknown_action_and_bad_reclassify_fail_closed(self):
        with self.assertRaises(pc.ConfirmationError):
            pc.ConfirmationAction("pan_count", "MADE_UP", route="PANEL_ACTION")
        with self.assertRaises(pc.ConfirmationError):
            pc.ConfirmationAction("pan_count", pc.RECLASSIFY, route="PANEL_ACTION")
        with self.assertRaises(pc.ConfirmationError):
            pc.ConfirmationAction("not_a_field", pc.ADD, route="PANEL_ACTION")

    def test_status_never_reports_owner_approved(self):
        s = pc.confirmation_status(self.intent)
        self.assertFalse(s["owner_approved"])
        self.assertEqual(s["manufacturing_authority"], "NOT_ESTABLISHED")
        self.assertFalse(s["fully_confirmed"])

    def test_the_record_has_a_stable_identity(self):
        a = _rec(self.intent).apply(
            pc.ConfirmationAction("pan_shapes", pc.CONFIRM, route="PANEL_ACTION"))
        b = _rec(self.intent).apply(
            pc.ConfirmationAction("pan_shapes", pc.CONFIRM, route="PANEL_ACTION"))
        self.assertEqual(a.identity(), b.identity())


@pytest.mark.django_db
class TestTheConfirmationPageIsServed:
    def test_the_dashboard_serves_it(self, client, django_user_model):
        u = django_user_model.objects.create_user("m4c4ui", password="x")
        client.force_login(u)
        r = client.get(reverse("dashboard:palette_intent_confirmation"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "WHAT THE ENGINE UNDERSTOOD" in html
        assert "ES3083" in html
        assert "RECTANGULAR" in html
        assert "PROVISIONAL_PENDING_CONFIRMATION" in html
        assert "GATE_2: BLOCKED" in html
        for action in ("CONFIRM", "RECLASSIFY", "MARK_UNRESOLVED"):
            assert action in html

    def test_it_is_in_the_one_shell_and_says_the_reading_in_words(self, client, django_user_model):
        # [the owner's answer to the UI directions of 2026-09-25: "One clean visual system", "Plain words everywhere.
        # No engine codes on screen." — each code the form posts or the record keeps stays, folded or in the form]
        import re
        client.force_login(django_user_model.objects.create_user("m4c4words", password="x"))
        html = client.get(reverse("dashboard:palette_intent_confirmation")).content.decode()
        assert 'class="bar"' in html and ' style="' not in html and "<style" not in html
        shown = re.sub(r"<[^>]+>", " ", re.sub(r'<details class="tech">.*?</details>', "", html, flags=re.S))
        for code in ("PROVISIONAL_PENDING_CONFIRMATION", "HARD_VISIBLE_CONSTRAINT", "IMAGE_COUNTED", "GATE_2",
                     "WHAT THE ENGINE UNDERSTOOD", "MARK_UNRESOLVED"):
            assert code not in shown, code
        for words in ("Read — not yet confirmed", "Must be seen", "counted on the picture", "Mark it unresolved"):
            assert words in shown, words

    def test_it_requires_login(self, client):
        r = client.get(reverse("dashboard:palette_intent_confirmation"))
        assert r.status_code in (302, 403)
