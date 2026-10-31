"""Permanent governance rules — each derived from a defect that shipped.

Every rule here is tested with a negative control, because rule A is that
a check without one is not evidence. The tests apply the rules to the
REAL modules, not to toy fixtures, so a regression in the production code
fails here.
"""
import datetime as dt

from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignTask, PaletteIntentConfirmation
from apps.pipeline.services import palette_confirmation_flow as flow
from apps.pipeline.services import palette_design_fidelity as fid
from apps.pipeline.services import palette_design_graph as dg
from apps.pipeline.services import palette_es3083_intent as es
from apps.pipeline.services import palette_es3083_owner_confirmation as OC
from apps.pipeline.services import palette_governance as gov
from apps.pipeline.services import palette_rect_tray_geometry as rt
from apps.pipeline.services import palette_variant_visual_proof as VP


class RuleAFalsifiabilityTests(SimpleTestCase):
    def test_a_check_that_accepts_its_negative_control_is_rejected(self):
        control = gov.NegativeControl("always true", True, False)
        with self.assertRaises(gov.GovernanceViolation) as ctx:
            gov.assert_falsifiable(lambda _x: True, control)
        self.assertIn("cannot fail", str(ctx.exception))

    def test_a_check_that_rejects_its_passing_case_is_rejected(self):
        control = gov.NegativeControl("always false", True, False)
        with self.assertRaises(gov.GovernanceViolation):
            gov.assert_falsifiable(lambda _x: False, control)

    def test_a_real_check_passes(self):
        gov.assert_falsifiable(
            bool, gov.NegativeControl("truthiness", 1, 0))

    def test_the_fidelity_engine_is_falsifiable_on_the_real_build(self):
        """The metric set must reject a build that contradicts the
        confirmed design."""
        intent = OC.confirmed_intent()
        graph = dg.build_palette_design_graph(
            intent, rt.build_rect_recessed_tray())

        def check(tray):
            r = fid.score_palette_fidelity(intent, tray, graph=graph)
            return not r["discriminating_metrics_failed"]

        gov.assert_falsifiable(check, gov.NegativeControl(
            "ES3083 fidelity",
            rt.build_rect_recessed_tray(),
            rt.build_rect_recessed_tray({"cells_x": 3, "cells_y": 3,
                                         "tray_width_mm": 90.0,
                                         "tray_depth_mm": 70.0})))

    def test_the_variant_proof_is_falsifiable(self):
        a, b = VP._variants()
        graph = dg.build_palette_design_graph(
            OC.confirmed_intent(), rt.build_rect_recessed_tray())

        def check(pair):
            diffs = VP.measured_differences(pair[0], pair[1], graph_a=None,
                                            graph_b=graph)
            return all(d["visible"] for d in diffs
                       if not d["excluded_from_verdict"])

        gov.assert_falsifiable(check, gov.NegativeControl(
            "design intent bridge", (a, b), (b, b)))

    def test_a_metric_that_cannot_fail_is_classified_and_excluded(self):
        self.assertEqual(gov.classify_metric(can_fail_for_a_valid_build=False),
                         gov.NON_DISCRIMINATING)
        score = gov.owner_facing_score([
            {"metric": "REAL", "discriminating_power": gov.DISCRIMINATING,
             "verdict": "PASS"},
            {"metric": "BY_CONSTRUCTION",
             "discriminating_power": gov.NON_DISCRIMINATING,
             "verdict": "PASS"}])
        self.assertEqual(score["discriminating_passed"], ["REAL"])
        self.assertEqual(score["excluded_from_score"], ["BY_CONSTRUCTION"])
        self.assertEqual(score["score"], 1.0)

    def test_the_shipped_fidelity_report_excludes_non_discriminating(self):
        intent = OC.confirmed_intent()
        tray = rt.build_rect_recessed_tray()
        report = fid.score_palette_fidelity(
            intent, tray, graph=dg.build_palette_design_graph(intent, tray))
        self.assertIn("OUTER_MARGIN_FIDELITY",
                      report["passes_by_construction"])
        self.assertNotIn("OUTER_MARGIN_FIDELITY",
                         report["discriminating_metrics_passed"])


class RuleBEvidenceIdentityTests(SimpleTestCase):
    def _ref(self, **over):
        base = {"milestone": "A3M", "revision": 1, "purpose": "maximum",
                "geometry_identity": "7c0558062fde67a7",
                "contract_identity": "583a9d8a22e8ec6f",
                "evidence_identity": "abc123"}
        base.update(over)
        return base

    def test_a_complete_reference_resolves(self):
        self.assertTrue(gov.assert_evidence_resolvable(self._ref()))

    def test_geometry_identity_alone_is_refused(self):
        """A3F and A3M share geometry, so this is genuinely ambiguous."""
        with self.assertRaises(gov.GovernanceViolation):
            gov.assert_evidence_resolvable(
                {"geometry_identity": "7c0558062fde67a7"})

    def test_each_missing_field_is_caught(self):
        for field in gov.EVIDENCE_IDENTITY_FIELDS:
            with self.subTest(field=field):
                with self.assertRaises(gov.GovernanceViolation):
                    gov.assert_evidence_resolvable(self._ref(**{field: None}))


class RuleCConfirmationGovernanceTests(SimpleTestCase):
    def test_an_implicit_gate_promotion_is_refused(self):
        for status in gov.FORBIDDEN_IMPLICIT_STATUSES:
            with self.subTest(status=status):
                with self.assertRaises(gov.GovernanceViolation):
                    gov.assert_no_implicit_gate_approval(
                        "awaiting_design_intent_confirmation", status)

    def test_a_non_gate_completion_is_allowed(self):
        gov.assert_no_implicit_gate_approval(
            "awaiting_design_intent_confirmation",
            "design_intent_confirmed")

    def test_a_task_already_at_a_gate_is_not_flagged(self):
        gov.assert_no_implicit_gate_approval("gate_1_approved",
                                             "gate_1_approved")


class RuleDAuditTrailTests(SimpleTestCase):
    NOW = dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc).isoformat()

    def _delta(self, old, new):
        return gov.revision_delta(old, new, actor="owner",
                                  timestamp=self.NOW, source_revision=1,
                                  resulting_revision=2)

    def test_only_changed_fields_are_recorded(self):
        rows = self._delta({"pan_count": 12, "rows": 3},
                           {"pan_count": 9, "rows": 3})
        self.assertEqual([r["field"] for r in rows], ["pan_count"])
        self.assertEqual(rows[0]["old_value"], 12)
        self.assertEqual(rows[0]["new_value"], 9)

    def test_an_unchanged_field_is_never_recorded(self):
        self.assertEqual(self._delta({"a": 1}, {"a": 1}), [])

    def test_a_replayed_decision_is_refused(self):
        """The negative control: a record claiming a field changed when it
        did not is replayed history attributed to the current actor."""
        bad = [{"field": "pan_shapes", "old_value": "RECTANGULAR",
                "new_value": "RECTANGULAR", "actor": "owner",
                "timestamp": self.NOW, "source_revision": 1,
                "resulting_revision": 2}]
        with self.assertRaises(gov.GovernanceViolation) as ctx:
            gov.assert_revision_record_minimal(bad)
        self.assertIn("replayed history", str(ctx.exception))

    def test_extra_content_in_a_revision_record_is_refused(self):
        rows = self._delta({"a": 1}, {"a": 2})
        rows[0]["whole_prior_history"] = ["..."]
        with self.assertRaises(gov.GovernanceViolation):
            gov.assert_revision_record_minimal(rows)

    def test_a_real_delta_is_minimal(self):
        gov.assert_revision_record_minimal(self._delta({"a": 1}, {"a": 2}))


class RuleETypedIntentTests(SimpleTestCase):
    def test_each_semantic_type_survives(self):
        cases = [(12, "9", 9), (1.5, "2.25", 2.25), (True, "no", False),
                 (False, "yes", True), (["a"], "x, y", ["x", "y"]),
                 ("TEXT", "OTHER", "OTHER")]
        for current, raw, want in cases:
            with self.subTest(current=current, raw=raw):
                got = gov.coerce_to_type(current, raw)
                self.assertEqual(got, want)
                gov.assert_type_preserved(current, got)

    def test_an_integer_never_becomes_a_string(self):
        """pan_count = 12 must not persist as "12"."""
        got = gov.coerce_to_type(12, "12")
        self.assertIsInstance(got, int)
        self.assertNotIsInstance(got, str)

    def test_a_value_that_cannot_be_coerced_is_refused(self):
        for current, raw in ((12, "twelve"), (1.5, "big"),
                             (True, "maybe"), ({"a": 1}, "x")):
            with self.subTest(current=current):
                with self.assertRaises(gov.TypeCoercionError):
                    gov.coerce_to_type(current, raw)

    def test_a_type_change_is_caught(self):
        with self.assertRaises(gov.GovernanceViolation):
            gov.assert_type_preserved(12, "12")


class RuleFRevisionReachabilityTests(SimpleTestCase):
    def test_history_without_an_action_is_refused(self):
        with self.assertRaises(gov.GovernanceViolation) as ctx:
            gov.assert_revision_reachable(action_exists=False,
                                          history_shown=True)
        self.assertIn("unreachable", str(ctx.exception))

    def test_history_with_an_action_is_allowed(self):
        gov.assert_revision_reachable(action_exists=True,
                                      history_shown=True)


class RuleGIsDeclaredAConventionTests(SimpleTestCase):
    def test_it_says_plainly_that_it_is_not_enforced(self):
        """Asserting an unobservable condition would be a check that
        cannot fail — which rule A forbids."""
        rule = gov.RULES["G_TEST_DATABASE_ISOLATION"]
        self.assertEqual(rule["kind"], "CONVENTION")
        self.assertIn("cannot fail", rule["why_not_enforced"])

    def test_every_other_rule_is_enforced_by_a_named_callable(self):
        for key, rule in gov.RULES.items():
            if key == "G_TEST_DATABASE_ISOLATION":
                continue
            with self.subTest(rule=key):
                self.assertEqual(rule["kind"], "ENFORCED")
                for name in rule["enforced_by"].split(" / "):
                    self.assertTrue(callable(getattr(gov, name, None)),
                                    f"{name} is not callable")


class GovernanceAppliedToTheLiveFlowTests(TestCase):
    """The rules applied to the shipped confirmation flow."""

    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(
            brand=brand, product_id="ES-3083G", name="Outer Glow",
            category="EY", year=2026, product_type="eyeshadow palette")
        self.task = DesignTask.objects.create(
            brand=brand, product=product, task_text="palette",
            status="running", design_target="palette")
        self.draft = es.build_es3083_intent()

    def test_rule_c_holds_for_the_real_confirmation(self):
        flow.open_confirmation(self.task, self.draft)
        before = self.task.status
        flow.save_confirmation(self.task, self.draft,
                               OC.confirmation_record())
        self.task.refresh_from_db()
        gov.assert_no_implicit_gate_approval(before, self.task.status)

    def test_rule_e_holds_through_persistence(self):
        flow.open_confirmation(self.task, self.draft)
        row = flow.save_confirmation(self.task, self.draft,
                                     OC.confirmation_record())
        value = flow.rehydrate(row).get("pan_count").value
        self.assertIsInstance(value, int)
        gov.assert_type_preserved(12, value)

    def test_rule_f_holds_for_the_real_page(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        user = get_user_model().objects.create_user("govuser",
                                                    password="x")
        user.user_permissions.add(
            Permission.objects.get(codename="change_designtask"))
        flow.open_confirmation(self.task, self.draft)
        self.client.force_login(user)
        url = reverse("dashboard:palette_intent_confirmation_task",
                      args=[self.task.pk])
        self.client.post(url, {"action_pan_shapes": "CONFIRM"})
        page = self.client.get(url)
        html = page.content.decode()
        gov.assert_revision_reachable(
            action_exists='name="reopen"' in html,
            history_shown="Revision history" in html)

    def test_rule_d_holds_for_a_real_revision(self):
        flow.open_confirmation(self.task, self.draft)
        first = flow.save_confirmation(self.task, self.draft,
                                       OC.confirmation_record())
        flow.open_confirmation(self.task, self.draft)
        import copy
        rec = copy.deepcopy(OC.confirmation_record())
        second = flow.save_confirmation(self.task, self.draft, rec)
        old = {f["name"]: f["value"]
               for f in first.confirmed_intent["fields"]}
        new = {f["name"]: f["value"]
               for f in second.confirmed_intent["fields"]}
        rows = gov.revision_delta(old, new, actor="owner",
                                  timestamp="2026-08-07T00:00:00Z",
                                  source_revision=first.version,
                                  resulting_revision=second.version)
        gov.assert_revision_record_minimal(rows)
        self.assertEqual(PaletteIntentConfirmation.objects.count(), 2)
