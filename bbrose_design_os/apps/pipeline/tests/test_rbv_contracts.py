"""RBV architecture slice — proposal contracts stay honest and machine-
checkable. No renderer exists yet; these tests pin the PROPOSED status,
the authority rules, and the tracker's RBV critical-path insertion."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.management.commands.roadmap_status import load_tracker

RBV = Path(__file__).resolve().parents[3] / "docs" / "visual_quality" / "rbv"


class RbvContractTests(SimpleTestCase):
    def _load(self, name):
        return json.loads((RBV / name).read_text())

    def test_approved_standards_are_active_and_carry_owner_provenance(self):
        """§R2 (2026-08-17) moved the two capture standards to ACTIVE. An
        ACTIVE authority state with no recorded owner authority behind it
        is the failure mode this repo has caught before, so the provenance
        is pinned alongside the status."""
        for name, schema in (
                ("camera_standard_proposal.json",
                 "real_bottle_camera_standard/1.0"),
                ("lighting_standard_proposal.json",
                 "real_bottle_lighting_standard/1.0")):
            data = self._load(name)
            assert data["schema"] == schema, name
            assert data["status"] == "ACTIVE", name
            prov = data["approval_provenance"]
            assert "§R2" in prov, name
            assert "2026-08-17" in prov, name
            # the approval must not be readable as more than it is
            assert "approves no RENDER" in prov, name
            assert "ABSENT_BLOCKED" in prov, name
            assert data["superseded_status"].startswith("PROPOSED"), name

    def test_unapproved_contracts_are_still_proposed_not_active(self):
        """§R2c: the comparison and review contracts were NOT approved by
        that ruling and must still be quoted as PROPOSED."""
        for name, schema in (
                ("real_bottle_comparison_contract.json",
                 "real_bottle_visual_comparison/1.0"),
                ("claude_visual_review_contract.json",
                 "claude_visual_review/1.0")):
            data = self._load(name)
            assert data["schema"] == schema, name
            assert "PROPOSED" in data["status"], name

    def test_camera_contract_forbids_misleading_zoom(self):
        cam = self._load("camera_standard_proposal.json")
        assert "identical camera" in cam["shared"]["comparison_rule"]
        assert "never differing zoom" in cam["shared"]["comparison_rule"]
        for view in ("FRONT_ORTHOGRAPHIC", "SIDE_ORTHOGRAPHIC",
                     "TOP_ORTHOGRAPHIC", "CLOSURE_DETAIL"):
            assert cam["cameras"][view]["projection"] == "orthographic"

    def test_comparison_contract_never_collapses_domains(self):
        comp = self._load("real_bottle_comparison_contract.json")
        assert set(comp["domains"]) == {"GEOMETRY", "ARTWORK",
                                        "TYPOGRAPHY", "MATERIAL"}
        assert "never collapsed" in comp["no_single_score_rule"]
        assert "blocking" in comp["no_single_score_rule"]

    def test_review_records_its_own_non_determinism(self):
        """Two live passes over an identical package returned different
        severity counts while agreeing on substance. That is recorded as a
        measured PROPERTY of the review so no consumer treats a finding
        count as a measurement."""
        rev = self._load("claude_visual_review_contract.json")
        prop = rev["observed_properties"]["classification_is_not_deterministic"]
        assert "IDENTICAL package" in prop["statement"]
        # the evidence must name real ledgered calls, not assert a claim
        assert prop["evidence"].count("req_") >= 2
        assert "never be a gate input" in prop["consequence_for_consumers"]

    def test_claude_review_never_self_approves(self):
        rev = self._load("claude_visual_review_contract.json")
        assert rev["classification"] == ["BLOCKING", "MAJOR", "MINOR",
                                         "VISUAL_POLISH"]
        assert any("must not self-approve" in r
                   for r in rev["authority_rules"])
        assert any("OWNER remains final authority" in r
                   for r in rev["authority_rules"])

    def test_inventory_concludes_no_usable_reference(self):
        inv = self._load("real_bottle_reference_inventory.json")
        assert inv["conclusion"] == \
            "NO_USABLE_REAL_BOTTLE_REFERENCE_IN_REPOSITORY"
        assert all(c["usable"] is False for c in inv["candidates"])

    def test_tracker_inserts_rbv_before_vqr2bb_without_vq_inflation(self):
        tracker = load_tracker()
        path = tracker["meta"]["critical_path_nodes"]
        rbv = [n for n in path if n.startswith("quality.rbv")]
        assert rbv == ["quality.rbv1_reference_standard",
                       "quality.rbv2_visualization_renderer",
                       "quality.rbv3_review_package",
                       "quality.rbv4_claude_review",
                       "quality.rbv5_comparison_gate"]
        assert path.index(rbv[-1]) < path.index(
            "pc.vqr2b_reconstruction_measurement")
        by_id = {n["id"]: n for n in tracker["nodes"]}
        for nid in rbv:
            node = by_id[nid]
            # milestones progress through NOT_STARTED → IN_PROGRESS →
            # VALIDATED as slices land — but NO rbv node may claim
            # visual-quality readiness before owner review of real
            # pilot output (the no-inflation rule)
            assert node["status"] in ("NOT_STARTED", "IN_PROGRESS",
                                      "VALIDATED")
            assert (node["visual_quality_percent"] or 0) == 0
        fixtures = by_id["quality.golden_concept_fixtures"]
        assert "ENGINEERING_REGRESSION_FIXTURES" in fixtures["title"]
        assert by_id["quality.real_bottle_golden_references"][
            "status"] == "NOT_STARTED"
