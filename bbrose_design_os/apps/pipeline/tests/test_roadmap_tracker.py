"""Roadmap rebase 2026-08-03 — tracker schema + consistency tests (§21).

The tracker is documentation, but documentation that LIES about progress is
how a rejected reconstruction got reported as MEASURED_PASS. These tests
keep the tracker honest: valid statuses, summing weights, bounded
percentages, evidence for validated claims, rejection/acceptance coherence,
one active milestone, and cached rollups that can never drift from the
leaf data.
"""
import copy
import json
from io import StringIO
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import SimpleTestCase

from apps.pipeline.management.commands.roadmap_status import (
    ACCEPTANCE_EVIDENCE_GRANDFATHERED, PERCENT_FIELDS, TRACKER_PATH,
    VALID_STATUSES, acceptance_evidence_claims, component_review_coverage,
    load_tracker, program_percent, rollup, validate_tracker,
    verify_acceptance_evidence)


class TrackerFileTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tracker = load_tracker()
        cls.nodes = cls.tracker["nodes"]

    def test_tracker_exists_with_expected_schema(self):
        # 3.1 -> 3.2 on 2026-08-24: nodes claiming owner acceptance gained
        # `owner_acceptance_evidence`. The node SHAPE changed, so the version
        # moves with it — a field added under an unchanged version number is
        # how two readers come to disagree about what a record means.
        assert self.tracker["schema"] == "bbrose_progress_tracker/3.2"
        assert Path(TRACKER_PATH).name == "progress_tracker.json"

    def test_tracker_is_fully_valid(self):
        assert validate_tracker(self.tracker) == []

    def test_ids_unique_and_statuses_legal(self):
        ids = [n["id"] for n in self.nodes]
        assert len(ids) == len(set(ids))
        assert {n["status"] for n in self.nodes} <= VALID_STATUSES

    def test_weights_sum_within_every_parent(self):
        parents = {n["id"] for n in self.nodes}
        for pid in parents:
            kids = [n for n in self.nodes if n.get("parent_id") == pid]
            if kids:
                assert abs(sum(k["weight"] for k in kids) - 1.0) < 1e-6, pid

    def test_percentages_bounded(self):
        for n in self.nodes:
            for f in PERCENT_FIELDS:
                v = n.get(f)
                assert v is None or 0 <= v <= 100, (n["id"], f)

    def test_rejection_consistency_is_structural(self):
        # the active program rejection can never be reported as accepted
        by_id = {n["id"]: n for n in self.nodes}
        pc_acc = by_id["pc.acceptance_outcome"]
        assert pc_acc["status"] == "REJECTED"
        assert pc_acc["owner_acceptance_percent"] == 0
        assert pc_acc["visual_quality_percent"] == 0
        assert pc_acc["production_readiness_percent"] == 0
        state = self.tracker["meta"]["program_state"]
        assert state["PRODUCT_CONTAINER_END_TO_END_ACCEPTANCE"] == \
            "REJECTED"
        assert state["PRODUCT_CONTAINER_OWNER_ACCEPTANCE_READINESS"] == 0
        assert state["GATE_2"] == "BLOCKED"

    def test_quality_weight_dominates_administrative_weight(self):
        # §10: quality-critical milestones carry meaningful weight — the
        # five design-quality nodes outweigh the mechanics nodes
        by_id = {n["id"]: n for n in self.nodes}
        quality = sum(by_id[i]["weight"] for i in (
            "pc.current_structural_output", "pc.current_concept_fidelity",
            "pc.current_artwork_output", "pc.current_typography_output",
            "pc.vqr1_m3_integration", "pc.vqr2b_concept_analysis",
            "pc.vqr2b_reconstruction_measurement",
            "pc.vqr3_artwork_composition", "pc.vqr4_typography_quality",
            "pc.design_adjustment_studio", "pc.vqr5_materials",
            "pc.acceptance_outcome"))
        mechanics = sum(by_id[i]["weight"] for i in (
            "pc.workflow_mechanics", "pc.reference_system",
            "pc.profile_workflow", "pc.reconstruction_infra",
            "pc.retry_recovery", "pc.acceptance_workflow"))
        assert quality > mechanics

    def test_rollup_formula_and_cached_views_agree(self):
        # cached views carry the GATED owner-acceptance numbers (§3), so
        # the comparison goes through program_percent, not the raw rollup
        for view_id, stored in self.tracker["computed_views"].items():
            for f in PERCENT_FIELDS:
                computed = program_percent(self.tracker, view_id, f)
                if stored[f] is None:
                    assert computed is None, (view_id, f)
                else:
                    assert abs(stored[f] - computed) <= 0.51, (view_id, f)
            if "component_review_coverage_percent" in stored:
                coverage = component_review_coverage(self.tracker, view_id)
                assert abs(stored["component_review_coverage_percent"]
                           - coverage) <= 0.51, view_id

    def test_visual_quality_cannot_be_hidden_by_implementation(self):
        # §9: the model must be able to say "implemented but visually
        # unready" — Product Container demonstrates it
        impl = rollup(self.nodes, "pc", "implementation_percent")
        vq = rollup(self.nodes, "pc", "visual_quality_percent")
        assert impl > 45
        assert vq < 20
        # §3: end-to-end rejection gates the TOP-LEVEL rollup to exactly 0
        assert program_percent(self.tracker, "pc",
                               "owner_acceptance_percent") == 0.0
        assert program_percent(self.tracker, "design_os",
                               "owner_acceptance_percent") == 0.0

    def test_no_dependency_names_a_node_that_does_not_exist(self):
        """§V3(a). A dependency that cannot resolve cannot gate — it reads
        as a constraint and enforces nothing. Seven such edges existed
        undetected; this is the guard that prevents the eighth, landed
        BEFORE the repoint so the order is the mechanism rather than the
        intention."""
        ids = {n["id"] for n in self.nodes}
        dangling = sorted(
            (n["id"], dep) for n in self.nodes
            for dep in (n.get("dependencies") or []) if dep not in ids)
        assert dangling == [], (
            "these dependencies name nodes absent from the tracker, so they "
            "gate nothing. Repoint them at the intended node or remove them "
            "and record why — do NOT invent a node to satisfy an edge "
            f"(§V3b): {dangling}")

    def test_active_and_next_milestones_point_to_open_work(self):
        by_id = {n["id"]: n for n in self.nodes}
        meta = self.tracker["meta"]
        active = by_id[meta["active_milestone"]]
        assert active["status"] not in ("VALIDATED", "OWNER_ACCEPTED",
                                        "PRODUCTION_AUTHORIZED")
        assert len(meta["primary_active_milestones"]) == 1
        for m in meta["next_milestones"]:
            assert by_id[m]["status"] not in ("VALIDATED", "OWNER_ACCEPTED",
                                              "PRODUCTION_AUTHORIZED"), m


class ValidatorRuleTests(SimpleTestCase):
    """The validator itself must catch every §14 defect class."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = load_tracker()

    def _mutated(self, mutate):
        tracker = copy.deepcopy(self.base)
        mutate(tracker)
        return validate_tracker(tracker)

    def _node(self, tracker, nid):
        return next(n for n in tracker["nodes"] if n["id"] == nid)

    def test_duplicate_id_detected(self):
        def m(t):
            t["nodes"].append(dict(t["nodes"][-1]))
        assert any("duplicate" in f for f in self._mutated(m))

    def test_invalid_status_detected(self):
        def m(t):
            self._node(t, "pc.vqr5_materials")["status"] = "DONE"
        assert any("invalid status" in f for f in self._mutated(m))

    def test_weight_drift_detected(self):
        def m(t):
            self._node(t, "pc.vqr5_materials")["weight"] = 0.5
        assert any("weights sum" in f for f in self._mutated(m))

    def test_percentage_bounds_detected(self):
        def m(t):
            self._node(t, "pc.vqr5_materials")["implementation_percent"] = 150
        assert any("out of range" in f for f in self._mutated(m))

    def test_rejected_item_cannot_claim_owner_acceptance(self):
        def m(t):
            self._node(t, "pc.acceptance_outcome")[
                "owner_acceptance_percent"] = 100
        assert any("may not carry owner acceptance" in f
                   for f in self._mutated(m))

    def test_production_before_acceptance_detected(self):
        def m(t):
            node = self._node(t, "pkg.archetypes")
            node["status"] = "PRODUCTION_AUTHORIZED"
            node["owner_acceptance_percent"] = 50
        assert any("production authorized before owner acceptance" in f
                   for f in self._mutated(m))

    def test_validated_without_evidence_detected(self):
        def m(t):
            node = self._node(t, "pc.vqr5_materials")
            node["status"] = "VALIDATED"
            node["implementation_percent"] = 100
        assert any("requires evidence" in f for f in self._mutated(m))

    def test_completed_leaf_with_incomplete_implementation_detected(self):
        def m(t):
            node = self._node(t, "pc.retry_recovery")
            node["implementation_percent"] = 60
        assert any("implementation < 100" in f for f in self._mutated(m))

    def test_next_milestone_to_completed_item_detected(self):
        def m(t):
            t["meta"]["next_milestones"] = ["pc.reference_system"]
        assert any("completed item" in f for f in self._mutated(m))

    def test_closure_record_invariant_fires(self):
        """A milestone with a closure record on disk may not read
        NOT_STARTED — the invariant behind the 2026-08-07
        reconciliation, proven able to fire."""
        def m(t):
            node = self._node(t, "palettes.palt_m5_pilot_p1")
            node["status"] = "NOT_STARTED"
            node["owner_acceptance_percent"] = 0
        assert any("closure record" in f for f in self._mutated(m))

    def test_two_primary_active_milestones_detected(self):
        def m(t):
            t["meta"]["primary_active_milestones"] = [
                "pc.structural_geometry", "pc.concept_fidelity"]
        assert any("more than one primary" in f for f in self._mutated(m))

    def test_cached_view_drift_detected(self):
        def m(t):
            t["computed_views"]["pc"]["visual_quality_percent"] = 90.0
        assert any("drifted" in f for f in self._mutated(m))

    def test_deferred_item_counted_complete_detected(self):
        def m(t):
            self._node(t, "cp.creation_ux")["owner_acceptance_percent"] = 100
        assert any("may not carry owner acceptance" in f
                   for f in self._mutated(m))


class CommandTests(SimpleTestCase):
    def test_roadmap_status_runs_and_reports(self):
        out = StringIO()
        call_command("roadmap_status", stdout=out)
        text = out.getvalue()
        assert "tracker valid" in text
        # 2026-08-17 build-sprint reconciliation: the palette programme is
        # closed through H2; the recovery chain resumes at the RBV insertion
        assert "active milestone:          pc.vqr3_artwork_composition" in text
        assert "design_os" in text and "pc" in text
        assert "owner decisions required" in text

    def test_roadmap_status_json_view(self):
        out = StringIO()
        call_command("roadmap_status", "--json", stdout=out)
        payload = json.loads(out.getvalue().split("\n", 6)[6])
        assert "design_os" in payload and "pc" in payload
        assert payload["pc"]["visual_quality_percent"] < 20

    def test_command_fails_closed_on_invalid_tracker(self):
        import apps.pipeline.management.commands.roadmap_status as rs
        broken = copy.deepcopy(load_tracker())
        broken["nodes"][5]["status"] = "DONE"
        original = rs.load_tracker
        rs.load_tracker = lambda path=None: broken
        try:
            with self.assertRaises(CommandError):
                call_command("roadmap_status", stdout=StringIO(),
                             stderr=StringIO())
        finally:
            rs.load_tracker = original


class AmendmentTests(SimpleTestCase):
    """V3 amendment §10 — the owner's mandatory tracker corrections hold."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tracker = load_tracker()
        cls.nodes = cls.tracker["nodes"]
        cls.by_id = {n["id"]: n for n in cls.nodes}

    def test_rejected_capability_and_recovery_are_separate_nodes(self):
        pairs = [("pc.current_structural_output", "pc.vqr1_m3_integration"),
                 ("pc.current_concept_fidelity",
                  "pc.vqr2b_reconstruction_measurement"),
                 ("pc.current_artwork_output", "pc.vqr3_artwork_composition"),
                 ("pc.current_typography_output",
                  "pc.vqr4_typography_quality")]
        for current, recovery in pairs:
            assert self.by_id[current]["status"] == "REJECTED", current
            # recovery progress accrues ONLY on the recovery node: either
            # untouched (0%) or fully evidenced (VQR-1 is VALIDATED)
            rec = self.by_id[recovery]
            assert rec["status"] in ("NOT_STARTED", "VALIDATED",
                                     "OWNER_ACCEPTED"), recovery
            assert self.by_id[current]["evidence_commits"], current
            if rec["status"] == "NOT_STARTED":
                assert rec["implementation_percent"] == 0
            else:
                assert rec["evidence_tests"], recovery
            assert self.by_id[current]["owner_acceptance_percent"] == 0

    def test_top_level_owner_acceptance_gated_to_zero(self):
        assert program_percent(self.tracker, "pc",
                               "owner_acceptance_percent") == 0.0
        assert self.tracker["computed_views"]["pc"][
            "owner_acceptance_percent"] == 0.0

    def test_component_coverage_distinct_from_acceptance(self):
        coverage = component_review_coverage(self.tracker, "pc")
        assert coverage > 0
        cached = self.tracker["computed_views"]["pc"]
        assert cached["component_review_coverage_percent"] == \
            round(coverage, 1)
        assert cached["owner_acceptance_percent"] == 0.0

    def test_adjustment_studio_on_critical_path(self):
        path = self.tracker["meta"]["critical_path_nodes"]
        assert "pc.design_adjustment_studio" in path
        studio = self.by_id["pc.design_adjustment_studio"]
        assert set(studio["dependencies"]) >= {
            "pc.vqr3_artwork_composition", "pc.vqr4_typography_quality"}

    def test_minimum_component_library_is_vqr3_dependency(self):
        deps = self.by_id["pc.vqr3_artwork_composition"]["dependencies"]
        assert "brand_gov.minimum_component_library" in deps
        assert "ire.design_graph_v2" in deps
        assert "brand_gov.font_governance" in deps
        assert "pc.vqr2b_reconstruction_measurement" in deps
        assert self.by_id["brand_gov.minimum_component_library"] is not None

    def test_minimum_comparison_is_vqr2b_linked(self):
        deps = self.by_id["review_board.minimum_fidelity_comparison"][
            "dependencies"]
        assert "pc.vqr2b_concept_analysis" in deps
        assert "pc.vqr2b_reconstruction_measurement" in deps

    def test_vqr5_and_acceptance_dependencies(self):
        assert set(self.by_id["pc.vqr5_materials"]["dependencies"]) >= {
            "pc.vqr3_artwork_composition", "pc.vqr4_typography_quality",
            "pc.design_adjustment_studio"}
        assert set(self.by_id["pc.acceptance_outcome"]["dependencies"]) >= {
            "quality.concept_gate", "pc.vqr1_m3_integration",
            "pc.vqr2b_reconstruction_measurement",
            "pc.vqr3_artwork_composition", "pc.vqr4_typography_quality",
            "pc.design_adjustment_studio", "pc.vqr5_materials"}

    def test_partial_visual_estimates_are_medium_confidence(self):
        for nid in ("pc.current_structural_output",
                    "pc.current_concept_fidelity",
                    "pc.current_artwork_output",
                    "pc.current_typography_output"):
            assert self.by_id[nid]["confidence"] == "MEDIUM", nid
            assert self.by_id[nid]["confidence_basis"] == \
                "EVIDENCE_INFORMED_ESTIMATE", nid

    def test_future_target_parents_are_not_started(self):
        for did in ("gift_set", "display_stand", "marketing", "social",
                    "booth"):
            assert self.by_id[did]["status"] == "NOT_STARTED", did

    def test_every_critical_path_item_has_a_valid_ordered_node(self):
        assert validate_tracker(self.tracker) == []
        path = self.tracker["meta"]["critical_path_nodes"]
        for nid in path:
            assert nid in self.by_id, nid
        # break the ordering -> the validator objects
        broken = copy.deepcopy(self.tracker)
        broken["meta"]["critical_path_nodes"] = list(reversed(path))
        assert any("critical path order invalid" in f
                   for f in validate_tracker(broken))

    def test_gate_and_parent_activity_rules_fail_closed(self):
        broken = copy.deepcopy(self.tracker)
        broken["computed_views"]["pc"]["owner_acceptance_percent"] = 14.0
        assert any("must be 0 while gate" in f
                   for f in validate_tracker(broken))
        broken2 = copy.deepcopy(self.tracker)
        for n in broken2["nodes"]:
            if n["id"] == "gift_set":
                n["status"] = "IN_PROGRESS"
        assert any("no active or implemented descendant" in f
                   for f in validate_tracker(broken2))

    def test_vqr2a_is_owner_accepted(self):
        gate = self.by_id["quality.fail_closed_gate"]
        assert gate["status"] == "OWNER_ACCEPTED"
        assert gate["owner_acceptance_percent"] == 100
        assert self.tracker["meta"]["program_state"][
            "VQR_2A_FAIL_CLOSED_VISUAL_QUALITY_GATE"] == "OWNER_ACCEPTED"


class OwnerAcceptanceEvidenceTests(SimpleTestCase):
    """§AE0(a) says `owner_acceptance` is UNTOUCHABLE and that no status
    containing OWNER_ACCEPTED is written by the executor for any node, EVER.
    Until 2026-08-24 that rule — the one the charter says must hold absolutely
    so the others can be relaxed — was enforced by nothing.

    MEASURED BEFORE THE FIELD EXISTED, both populations, caches refreshed each
    time as any editor of this file would refresh them: of the 56 nodes an
    executor could raise 0->100, ZERO were caught by any of the 39 tests here;
    of the 95 nodes not already accepted, 63 were caught but 58 of those were
    `test_tracker_is_fully_valid` and the critical-path test objecting to
    INCOMPLETE IMPLEMENTATION — an accident of where the node sat, not a
    refusal of self-approval — leaving 32 to flip in silence, one of them
    `cp.pilot_evidence`, whose status is REJECTED. AFTER: 56/56 and 95/95.

    What the field buys is FALSIFIABILITY, NOT UNFORGEABILITY. An executor can
    still write a locator. What changed is that a false acceptance must now be
    TOLD — naming a commit, quoting a sentence really in it — instead of being
    told by silence. The residue is stated in `verify_acceptance_evidence`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.base = load_tracker()

    def _node(self, tracker, nid):
        return next(n for n in tracker["nodes"] if n["id"] == nid)

    def _raised(self, nid, **extra):
        t = copy.deepcopy(self.base)
        n = self._node(t, nid)
        n["owner_acceptance_percent"] = 100
        n.update(extra)
        return validate_tracker(t)

    def test_raising_acceptance_without_evidence_is_refused(self):
        assert any("carries no owner_acceptance_evidence" in f
                   for f in self._raised("quality.rbv4_claude_review"))

    def test_flipping_status_to_owner_accepted_is_refused(self):
        # the REJECTED pilot record — the vivid case, silent before the field
        assert any("carries no owner_acceptance_evidence" in f
                   for f in self._raised("cp.pilot_evidence",
                                         status="OWNER_ACCEPTED"))

    def test_grandfather_clause_is_not_available_to_new_nodes(self):
        out = self._raised(
            "quality.rbv4_claude_review",
            owner_acceptance_evidence={"kind": "UNRECORDED_PREDATES_FIELD"})
        assert any("outside the frozen grandfather set" in f for f in out)

    def test_evidence_must_carry_locator_quote_and_date(self):
        out = self._raised(
            "quality.rbv4_claude_review",
            owner_acceptance_evidence={"kind": "OWNER_RULING_COMMIT",
                                       "locator": "", "quote": " "})
        for key in ("locator", "quote", "dated"):
            assert any(f"missing {key}" in f for f in out), key

    def test_unknown_evidence_kind_is_refused(self):
        out = self._raised(
            "quality.rbv4_claude_review",
            owner_acceptance_evidence={"kind": "EXECUTOR_SAYS_SO"})
        assert any("unknown acceptance evidence kind" in f for f in out)

    def test_evidence_cannot_be_staged_before_the_acceptance(self):
        """Pre-seeding evidence on an unaccepted node would let the two halves
        land in separate commits, so the diff that finally moves the number
        looks like a one-line edit."""
        t = copy.deepcopy(self.base)
        self._node(t, "quality.rbv4_claude_review")[
            "owner_acceptance_evidence"] = {"kind": "OWNER_RULING_COMMIT",
                                            "locator": "32cedf9",
                                            "quote": "VQ1_OWNER_ACCEPTED",
                                            "dated": "2026-07-28"}
        assert any("claims no owner acceptance" in f for f in validate_tracker(t))

    def test_every_accepting_node_carries_the_field(self):
        accepting = [n for n in self.base["nodes"]
                     if n["status"] == "OWNER_ACCEPTED"
                     or (n.get("owner_acceptance_percent") or 0) > 0]
        assert len(accepting) == 11
        assert all("owner_acceptance_evidence" in n for n in accepting)

    def test_the_grandfather_set_may_only_shrink(self):
        """Frozen 2026-08-24 at eight. Nothing may ever be ADDED: an
        acceptance made after that date has the field or is invalid. A
        grandfather clause that can grow is a loophole with a date on it."""
        assert ACCEPTANCE_EVIDENCE_GRANDFATHERED <= frozenset({
            "core_platform.front_half", "core_platform.target_selector",
            "pc.reference_system", "pc.reconstruction_infra", "pkg.archetypes",
            "ire.gate_a_roundtrip", "review_board.references",
            "quality.single_authority"})
        ids = {n["id"] for n in self.base["nodes"]}
        assert ACCEPTANCE_EVIDENCE_GRANDFATHERED <= ids

    def test_quoted_owner_words_really_are_in_the_named_commits(self):
        """The check that makes the locator more than decoration: three nodes
        name a commit, and each quote must resolve in real git history."""
        claims = acceptance_evidence_claims(self.base)
        assert {c[0] for c in claims} == {
            "ire.m3_backbone", "pc.vqr1_m3_integration",
            "quality.fail_closed_gate"}
        assert verify_acceptance_evidence(self.base) == []

    def test_a_fabricated_locator_does_not_resolve(self):
        t = copy.deepcopy(self.base)
        self._node(t, "ire.m3_backbone")["owner_acceptance_evidence"][
            "locator"] = "0000000"
        assert any("does not resolve" in f
                   for f in verify_acceptance_evidence(t))

    def test_a_real_commit_with_words_it_never_said_is_caught(self):
        t = copy.deepcopy(self.base)
        self._node(t, "ire.m3_backbone")["owner_acceptance_evidence"][
            "quote"] = "the owner accepted absolutely everything"
        assert any("are not in commit" in f
                   for f in verify_acceptance_evidence(t))
