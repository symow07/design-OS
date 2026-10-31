"""Structure selection persistence (Phase 2A-6 §4).

The rules under test:
  * a persisted structure survives restart VERBATIM — no re-selection;
  * confirmation is idempotent for the same die and invalid for a changed one;
  * a structure record answers unconfirmed until it is confirmed, and again once it changes.

[The clean-up of 2026-10-04, his Q1 "remove the dormant packaging flow".] The confirmation ENDPOINT, the switch that
gated it and the flow that paused a design for it are gone, with their tests. What stays pinned is the record they
wrote on the dieline job, which task 50 still carries and the review board still reads.
"""
from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.dielines import registry
from apps.dielines.models import DielineJob
from apps.pipeline.permissions import ROLE_REVIEWER
from apps.pipeline.services import structure_selection as ss
from apps.pipeline.services.template_selection import select_template

PARAMS = {"width_mm": 42.0, "depth_mm": 32.0, "height_mm": 140.0,
          "bleed_mm": 3.0, "safe_margin_mm": 4.0, "glue_tab_mm": 10.0,
          "board_thickness_mm": 0.30, "thickness_compensation": True}


def _user(username, role):
    u = User.objects.create_user(username, f"{username}@t.com", "pw")
    g, _ = Group.objects.get_or_create(name=role)
    u.groups.add(g)
    return u


class StructureRecordTests(TestCase):
    def setUp(self):
        self.job = DielineJob.objects.create(
            template_type="skynte_foundation_tuck_carton", scenario="B",
            input_json={}, extraction_result={},
        )
        self.user = _user("rev-struct", ROLE_REVIEWER)

    def _record(self):
        sel = select_template(type("T", (), {"product": None})(),
                              user_template="skynte_foundation_tuck_carton",
                              dimensions=PARAMS)
        rec = ss.build_structure_record(
            sel, PARAMS, assumptions=["tuck lip 16 mm"],
            dimension_reconciliation={"reconciled": True})
        return ss.save_structure_record(self.job, rec)

    def test_record_persists_full_decision(self):
        rec = self._record()
        self.assertEqual(rec["template_id"], "skynte_foundation_tuck_carton")
        self.assertEqual(rec["template_version"], "1.0")
        self.assertEqual(rec["source"], "EXPLICIT_USER_CONFIRMATION")
        self.assertEqual(rec["confidence"], 1.0)
        self.assertEqual(rec["assumptions"], ["tuck lip 16 mm"])
        self.assertTrue(rec["geometry_hash"])
        self.assertEqual(rec["panel_sequence"][1], "side_left")
        self.job.refresh_from_db()
        self.assertEqual(self.job.template_type, "skynte_foundation_tuck_carton")

    def test_restart_reuses_the_identical_structure(self):
        rec = self._record()
        reloaded = ss.load_structure_record(
            DielineJob.objects.get(pk=self.job.pk))
        self.assertEqual(reloaded, rec)
        # and the reload is usable without re-selecting
        self.assertEqual(ss.assert_unchanged(self.job)["geometry_hash"],
                         rec["geometry_hash"])

    def test_unresolved_selection_cannot_be_persisted(self):
        sel = select_template(type("T", (), {"product": None})())
        with self.assertRaises(ss.StructureError) as ctx:
            ss.build_structure_record(sel, PARAMS)
        self.assertEqual(ctx.exception.code, ss.STRUCTURE_NOT_SELECTED)

    def test_confirmation_is_idempotent(self):
        self._record()
        first = ss.confirm_structure(self.job, self.user)
        second = ss.confirm_structure(
            DielineJob.objects.get(pk=self.job.pk), self.user)
        self.assertEqual(first["confirmed_at"], second["confirmed_at"])
        self.assertEqual(second["confirmed_by"], "rev-struct")

    def test_changed_parameters_invalidate_the_hash(self):
        rec = self._record()
        ss.confirm_structure(self.job, self.user)
        # someone edits parameters without re-hashing → hard stop
        rec = ss.load_structure_record(self.job)
        rec["parameters"]["height_mm"] = 150.0
        self.job.structure_selection = rec
        self.job.save(update_fields=["structure_selection"])
        with self.assertRaises(ss.StructureError) as ctx:
            ss.assert_confirmed(self.job)
        self.assertEqual(ctx.exception.code, ss.STRUCTURE_CHANGED)

    def test_changed_template_requires_new_confirmation(self):
        self._record()
        ss.confirm_structure(self.job, self.user)
        self.assertTrue(ss.is_confirmed(self.job))
        ss.invalidate_confirmation(self.job, "template changed")
        self.assertFalse(ss.is_confirmed(self.job))
        with self.assertRaises(ss.StructureError) as ctx:
            ss.assert_confirmed(self.job)
        self.assertEqual(ctx.exception.code, ss.STRUCTURE_NOT_CONFIRMED)

    def test_artwork_blocked_before_confirmation(self):
        self._record()
        with self.assertRaises(ss.StructureError) as ctx:
            ss.assert_confirmed(self.job)
        self.assertEqual(ctx.exception.code, ss.STRUCTURE_NOT_CONFIRMED)

    def test_confirming_a_different_die_is_refused(self):
        self._record()
        with self.assertRaises(ss.StructureError) as ctx:
            ss.confirm_structure(self.job, self.user,
                                 geometry_hash="not-the-hash")
        self.assertEqual(ctx.exception.code, ss.STRUCTURE_CHANGED)

    def test_presentation_carries_everything_the_reviewer_needs(self):
        self._record()
        pres = ss.structure_presentation(self.job)
        for key in ("panel_sequence", "closure_type", "glue_seam_position",
                    "board_compensation_model", "flap_capabilities",
                    "notch_capabilities", "assumptions", "geometry_hash",
                    "selection_source", "dimension_reconciliation"):
            self.assertIn(key, pres)
        self.assertEqual(pres["template_version"], "1.0")

    def test_legacy_job_has_no_structure_record(self):
        legacy = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="A",
            input_json={}, extraction_result={})
        self.assertEqual(ss.load_structure_record(legacy), {})
        self.assertFalse(ss.is_confirmed(legacy))


class MigrationShapeTests(TestCase):
    def test_structure_selection_defaults_to_empty_dict(self):
        job = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="A",
            input_json={}, extraction_result={})
        job.refresh_from_db()
        self.assertEqual(job.structure_selection, {})

    def test_new_status_registered(self):
        from apps.pipeline.models import TASK_STATUS
        self.assertIn("awaiting_structure_confirmation",
                      {c[0] for c in TASK_STATUS})

    def test_registry_versions_are_explicit(self):
        for defn in registry.all_templates():
            self.assertTrue(defn.version)
            self.assertIn("/", defn.key)
