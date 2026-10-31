"""M4B-B §11 — the exit gate."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services import palette_m4b_b_evidence as EVB
from apps.pipeline.services import palette_m4b_b_gate as G

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs" / "roadmap" / "palt_m4b_b"


class ExitGateTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.result = G.evaluate()

    def test_every_condition_the_directive_names_is_checked(self):
        conditions = {c["condition"] for c in self.result["checks"]}
        for want in ("pans are correctly seated",
                     "the tray is moulded credibly",
                     "the lid is credibly moulded",
                     "the hinge is understandable",
                     "the clasp is understandable",
                     "open/closed articulation passes",
                     "P1A remains regression-stable",
                     "P1B reflects ES3083 design intent",
                     "all meshes pass diagnostics",
                     "evidence manifest passes",
                     "design-intent bridge passes"):
            self.assertIn(want, conditions)
        self.assertTrue(any("true sections pass" in c for c in conditions))

    def test_the_gate_passes(self):
        """Every condition, re-run after the legibility correction — not
        only the condition that had failed."""
        self.assertEqual(self.result["failed"], [])
        self.assertEqual(self.result["M4B_B_EXIT_GATE"], "PASS")

    def test_every_condition_passes(self):
        passing = [c["condition"] for c in self.result["checks"]
                   if c["verdict"] == "PASS"]
        self.assertEqual(len(passing), len(self.result["checks"]))

    def test_it_says_what_it_does_not_check(self):
        """A suite cannot verify itself from inside."""
        self.assertTrue(any("canonical pytest" in s
                            for s in self.result["not_checked_here"]))

    def test_it_claims_no_authority(self):
        self.assertFalse(self.result["owner_approved"])
        self.assertEqual(self.result["manufacturing_authority"],
                         "NOT_ESTABLISHED")
        self.assertEqual(self.result["PALT_P1_FINAL_DIMENSIONS"],
                         "NOT_APPROVED")
        self.assertEqual(self.result["GATE_2"], "BLOCKED")


class EvidenceCompletenessTests(SimpleTestCase):
    """The manifest check must be completeness, not a threshold."""

    def _records(self):
        return json.loads((DOCS / "review_records.json").read_text())

    def _sections(self):
        return {"P1A": json.loads((DOCS / "p1a_sections.json").read_text()),
                "P1B": json.loads((DOCS / "p1b_sections.json").read_text())}

    def test_the_full_set_is_complete(self):
        m = EVB.evidence_manifest(self._records(), self._sections())
        self.assertEqual(m["required_count"], 23)
        self.assertEqual(m["families"]["P1A"]["missing"], [])
        self.assertEqual(m["families"]["P1B"]["missing"],
                         ["mirror_stack_view"])

    def test_the_section_views_are_mapped_in_not_assumed(self):
        """hinge_section, clasp_section and true_stack_section come from
        §8. A count threshold would clear while they were absent."""
        m = EVB.evidence_manifest(self._records(), self._sections())
        for key in ("hinge_section", "clasp_section",
                    "true_stack_section"):
            self.assertIn(key, m["families"]["P1A"]["produced"])
            self.assertIn(key, m["families"]["P1B"]["produced"])

    def test_a_truncated_record_reports_missing_views(self):
        """The negative control: without it this is a completeness check
        nobody has seen fail."""
        recs = self._records()
        recs[0]["produced"] = recs[0]["produced"][:3]
        m = EVB.evidence_manifest(recs, {})
        self.assertTrue(m["families"][recs[0]["family"]]["missing"])
        self.assertGreater(
            len(m["families"][recs[0]["family"]]["missing"]), 15)

    def test_dropping_the_sections_reports_them_missing(self):
        m = EVB.evidence_manifest(self._records(), {})
        for fam in ("P1A", "P1B"):
            for key in ("hinge_section", "clasp_section",
                        "true_stack_section"):
                self.assertIn(key, m["families"][fam]["missing"])


class BridgeRecordTests(SimpleTestCase):
    def test_the_bridge_record_is_present_and_passing(self):
        """The record is committed, so absence is a failure, not a skip."""
        path = DOCS / "m4c9_visual_variant_proof_full.json"
        self.assertTrue(path.exists(), str(path))
        data = json.loads(path.read_text())
        self.assertTrue(data["all_required_views_exist"])
        self.assertEqual(data["produced_count"], 10)
        self.assertEqual(data["DESIGN_INTENT_BRIDGE"], "PASS")
        self.assertEqual(data["differences_not_visible"], [])
        self.assertEqual(data["differences_judged"], 11)
