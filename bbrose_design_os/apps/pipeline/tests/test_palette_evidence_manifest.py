"""PALT-M4B-A3P §5B — the evidence gap must fail closed, not stay quiet."""
from django.test import SimpleTestCase

from apps.pipeline.services import palette_evidence_manifest as em


class EvidenceManifestTests(SimpleTestCase):
    def test_the_deferred_count_is_the_41_the_milestones_recorded(self):
        self.assertEqual(em.TOTAL_DEFERRED, 41)
        self.assertEqual(
            [em.MILESTONES[k]["deferred_image_count"]
             for k in ("A3R", "A3F", "A3M")], [13, 16, 12])

    def test_requesting_unproduced_evidence_raises(self):
        for milestone in ("A3R", "A3F", "A3M"):
            with self.subTest(milestone=milestone):
                with self.assertRaises(em.EvidenceNotProduced):
                    em.require_evidence(milestone)

    def test_an_unknown_name_is_refused_rather_than_assumed(self):
        with self.assertRaises(em.EvidenceNotProduced) as ctx:
            em.require_evidence("A3F_render_pass_01.png")
        self.assertIn("refuses by default", str(ctx.exception))

    def test_produced_numerical_evidence_is_returned(self):
        self.assertTrue(em.require_evidence("A3P_cup_wall_proof")
                        .endswith("a3p_cup_wall_proof.json"))

    def test_the_missing_names_are_declared_missing_not_invented(self):
        state = em.visual_evidence_state()
        self.assertEqual(state["image_names"], em.NOT_ENUMERATED)
        self.assertIn("would produce a manifest that looks complete and is "
                      "not", state["why_names_absent"])

    def test_it_never_claims_visual_verification(self):
        state = em.visual_evidence_state()
        self.assertFalse(state["visual_verification_claimed"])
        self.assertIn("any claim that A3R/A3F/A3M were VISUALLY verified",
                      state["blocks"])

    def test_it_does_not_overclaim_the_gap(self):
        """The numerical authority does have durable evidence; the manifest
        must not imply the milestones proved nothing."""
        state = em.visual_evidence_state()
        self.assertIn("the numerical thickness authority, which has durable "
                      "evidence", state["does_not_block"])
        self.assertGreaterEqual(len(state["produced_numerical_evidence"]), 6)

    def test_a_superseded_finding_is_recorded_not_dropped(self):
        s = em.visual_evidence_state()["superseded_findings"]
        self.assertIn("A3M_SECTION_6_CUP_WALL_UNPROVEN", s)
        self.assertEqual(s["A3M_SECTION_6_CUP_WALL_UNPROVEN"]
                         ["superseded_by"], "A3P build-time FaceLog "
                                            "provenance")
