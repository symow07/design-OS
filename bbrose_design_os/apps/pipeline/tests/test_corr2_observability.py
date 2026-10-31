"""Rejected-payload observability (Phase 2A-6D-CORR-2 §7).

AgentLog 806 captured the retry's rejected DIRECTIONS but not its design
intent — the field that fired UNCONFIRMED_STRUCTURE_ASSUMED was
unrecoverable and the whole set had to be regenerated. A failed generation
now preserves the complete bounded result: intent + directions of EVERY
attempt (initial and repair distinguishable), the validator's input brief,
the classification and content matrices, structured coverage values and the
code revision — enough for deterministic offline revalidation with zero
provider calls. Never credentials, provider transport or worker state.
"""
from __future__ import annotations

import json

from apps.pipeline.design_direction_generator import generate_design_directions
from apps.pipeline.tests.direction_fixtures import valid_document

BRIEF = {
    "brand": "BBROSE",
    "product_name": "Baked Powder",
    "product_category": "face powder",
    "design_target": "packaging",
    "required_copy": ["BBROSE", "BAKED POWDER"],
    "production_constraints": ["decorative coverage no more than 20%"],
}


def _collapsed_document():
    """A structurally valid document that fails semantic distinctness:
    three copies of one direction, renamed."""
    document = valid_document()
    base = document["directions"][0]
    document["directions"] = []
    for index in range(3):
        clone = dict(base)
        clone["direction_id"] = f"d{index + 1}"
        clone["name"] = f"Same Idea {index + 1}"
        clone["design_axis"] = f"{base['design_axis']} (variant {index + 1})"
        clone["layout_structure"] = (f"{base['layout_structure']} "
                                     f"Variant {index + 1}.")
        clone["color_system"] = f"{base['color_system']} Accent {index + 1}."
        document["directions"].append(clone)
    return document


def _failing_call_model():
    calls = []

    def call(system, content):
        calls.append(content)
        return json.dumps(_collapsed_document()), "test:model"
    return call, calls


class TestFailureCapture:
    """[Re-pinned by his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 1: "NO planner check ever stops a design (not only "not distinct"): on failure it retries once with the reason; if it still fails, it shows me the three directions with a plain note, and I choose."]
    A set refused twice is shown with its note now, not failed: the capture is kept for it as for a failure — every
    attempt, the validator's own evidence — and the set itself is the document shown."""

    def _failed_result(self):
        call, _ = _failing_call_model()
        result = generate_design_directions(brief=BRIEF, call_model=call)
        assert result.ok and result.alike                  # refused twice: shown with its note
        return result

    def test_rejected_document_contains_intent_and_directions(self):
        result = self._failed_result()
        assert result.rejected_document is None            # nothing was rejected: the set is shown
        assert result.document.get("target_structural_guidance")
        assert len(result.document["directions"]) == 3

    def test_initial_and_repair_attempts_remain_distinguishable(self):
        result = self._failed_result()
        assert [entry["attempt"] for entry in result.attempt_history] == [1, 2]
        for entry in result.attempt_history:
            assert entry["codes"]
            assert len(entry["directions"]) == 3
            assert isinstance(entry["design_intent"], dict)

    def test_diagnostics_support_offline_revalidation(self):
        result = self._failed_result()
        diagnostics = result.rejected_diagnostics
        assert diagnostics is not None
        assert diagnostics["validator_input_brief"]["product_name"] == \
            "Baked Powder"
        assert len(diagnostics["classification_matrix"]) == 3
        assert all("typography_family" in row
                   for row in diagnostics["classification_matrix"])
        assert isinstance(diagnostics["content_codes"], list)
        findings = diagnostics["coverage_findings"]
        assert [f["direction"] for f in findings] == [0, 1, 2]
        assert all(f["cap"] == 20 for f in findings)

    def test_no_sensitive_data_in_the_capture(self):
        result = self._failed_result()
        captured = json.dumps({
            "document": result.rejected_document,
            "history": list(result.attempt_history),
            "diagnostics": result.rejected_diagnostics,
        }).lower()
        for secret_marker in ("api_key", "authorization", "secret",
                              "bearer ", "sk-ant"):
            assert secret_marker not in captured

    def test_successful_run_carries_no_rejected_payload(self):
        def call(system, content):
            return json.dumps(valid_document()), "test:model"
        # no content constraints: the shared fixture legitimately uses
        # full-bleed language and its own copy, which a constrained brief
        # now (correctly) rejects
        unconstrained = {k: v for k, v in BRIEF.items()
                         if k not in ("production_constraints",
                                      "required_copy")}
        result = generate_design_directions(brief=unconstrained,
                                            call_model=call)
        assert result.ok
        assert result.rejected_document is None
        assert result.rejected_directions == ()
        assert result.rejected_diagnostics is None
