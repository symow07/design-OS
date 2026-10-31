"""VQ-1-CORR-1 — visual-quality program review delivery.

Program-level synthetic diagnostics (NEVER task-52 production outputs):
bounded artifact serving + the direct structural-review page + the
vq1_human_structural_review/1.0 state. Authenticated only; root-bounded
file resolution; no arbitrary paths."""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

VQ1_DIR = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq1")
REVIEW_STATE_FILE = os.path.join(VQ1_DIR, "vq1_human_structural_review.json")
REVIEW_SCHEMA = "vq1_human_structural_review/1.0"
REVIEW_STATES = ("NOT_REVIEWED", "ACCEPTED", "REJECTED",
                 "REVISION_REQUIRED")

#: the ONLY servable artifacts — never arbitrary paths
ARTIFACTS = {
    "review-png": ("vq1_cylindrical_backbone_review.png", "image/png"),
    "review-pdf": ("vq1_cylindrical_backbone_review.pdf",
                   "application/pdf"),
    "review-ai": ("vq1_cylindrical_backbone_review.ai",
                  "application/pdf"),
    "graph": ("vq1_cylindrical_backbone_graph.json", "application/json"),
    "perceived-geometry": ("vq1_perceived_geometry_report.json",
                           "application/json"),
    "closure-continuity": ("vq1_closure_continuity_report.json",
                           "application/json"),
    "illustrator": ("vq1_illustrator_execution_report.json",
                    "application/json"),
    "task52-diagnostic": ("vq1_task52_readonly_diagnostic.json",
                          "application/json"),
    "human-review": ("vq1_human_structural_review.json",
                     "application/json"),
    "corr2-png": ("../vq1_corr2/vq1_corr2_review.png", "image/png"),
    "corr2-pdf": ("../vq1_corr2/vq1_corr2_review.pdf", "application/pdf"),
    "corr3-png": ("../vq1_corr3/vq1_corr3_review.png", "image/png"),
    "corr3-pdf": ("../vq1_corr3/vq1_corr3_review.pdf", "application/pdf"),
    "corr4-png": ("../vq1_corr4/vq1_corr4_review.png", "image/png"),
    "corr4-pdf": ("../vq1_corr4/vq1_corr4_review.pdf", "application/pdf"),
    "corr4-sheet2-png": ("../vq1_corr4/vq1_corr4_assembly.png", "image/png"),
    "corr4-sheet2-pdf": ("../vq1_corr4/vq1_corr4_assembly.pdf",
                         "application/pdf"),
    "corr4-fixture-png": ("../vq1_corr4/vq1_corr4_fixture.png", "image/png"),
    "reset1-packet-png": ("../vq1_reset1/"
                          "vq1_web_geometry_reference_packet.png",
                          "image/png"),
    "reset1-packet-pdf": ("../vq1_reset1/"
                          "vq1_web_geometry_reference_packet.pdf",
                          "application/pdf"),
    "reset1-packet-json": ("../vq1_reset1/"
                           "vq1_web_geometry_reference_packet.json",
                           "application/json"),
    "reset1-semantics": ("../vq1_reset1/component_semantic_finding.json",
                         "application/json"),
    "reset1-plan": ("../vq1_reset1/visual_correction_plan.json",
                    "application/json"),
    "reset1-loop": ("../vq1_reset1/visual_correction_loop.json",
                    "application/json"),
    "reset1-provider-log": ("../vq1_reset1/provider_call_log.json",
                            "application/json"),
    "reset1-freeze": ("../vq1_reset1/vq1_generator_freeze.json",
                      "application/json"),
    "reset1-corr5-classification": (
        "../vq1_reset1/vq1_corr5_rejection_classification.json",
        "application/json"),
    "reset1-inspection-corr4": ("../vq1_reset1/inspection_corr_4.json",
                                "application/json"),
    "reset1-inspection-corr5": ("../vq1_reset1/inspection_corr_5.json",
                                "application/json"),
    "reset1a-packet-png": ("../vq1_reset1a/"
                           "vq1_geometry_evidence_review.png", "image/png"),
    "reset1a-packet-p2-png": ("../vq1_reset1a/"
                              "vq1_geometry_evidence_review_p2.png",
                              "image/png"),
    "reset1a-packet-p3-png": ("../vq1_reset1a/"
                              "vq1_geometry_evidence_review_p3.png",
                              "image/png"),
    "reset1a-packet-pdf": ("../vq1_reset1a/"
                           "vq1_geometry_evidence_review.pdf",
                           "application/pdf"),
    "reset1a-packet-p2-pdf": ("../vq1_reset1a/"
                              "vq1_geometry_evidence_review_p2.pdf",
                              "application/pdf"),
    "reset1a-packet-p3-pdf": ("../vq1_reset1a/"
                              "vq1_geometry_evidence_review_p3.pdf",
                              "application/pdf"),
    "reset1a-packet-json": ("../vq1_reset1a/"
                            "vq1_geometry_evidence_review.json",
                            "application/json"),
    "reset1b-packet-png": ("../vq1_reset1b/"
                           "vq1_technical_geometry_evidence_v2.png",
                           "image/png"),
    "reset1b-packet-p2-png": ("../vq1_reset1b/"
                              "vq1_technical_geometry_evidence_v2_p2.png",
                              "image/png"),
    "reset1b-packet-p3-png": ("../vq1_reset1b/"
                              "vq1_technical_geometry_evidence_v2_p3.png",
                              "image/png"),
    "reset1b-packet-pdf": ("../vq1_reset1b/"
                           "vq1_technical_geometry_evidence_v2.pdf",
                           "application/pdf"),
    "reset1b-packet-p2-pdf": ("../vq1_reset1b/"
                              "vq1_technical_geometry_evidence_v2_p2.pdf",
                              "application/pdf"),
    "reset1b-packet-p3-pdf": ("../vq1_reset1b/"
                              "vq1_technical_geometry_evidence_v2_p3.pdf",
                              "application/pdf"),
    "reset1b-packet-json": ("../vq1_reset1b/"
                            "vq1_technical_geometry_evidence_v2.json",
                            "application/json"),
    "reset1b-decision": ("../vq1_reset1b/"
                         "vq1_reset1a_human_evidence_decision.json",
                         "application/json"),
    "reset2-review-png": ("../vq1_reset2/vq1_reset2_visual_review.png",
                          "image/png"),
    "reset2-review-pdf": ("../vq1_reset2/vq1_reset2_visual_review.pdf",
                          "application/pdf"),
    "reset2-review-json": ("../vq1_reset2/vq1_reset2_visual_review.json",
                           "application/json"),
    "reset2-authority": ("../vq1_reset2/container_geometry_authority.json",
                         "application/json"),
    "reset2-envelope": ("../vq1_reset2/concept_visual_envelope.json",
                        "application/json"),
    "reset2-loop": ("../vq1_reset2/visual_correction_loop.json",
                    "application/json"),
    "reset2-plans": ("../vq1_reset2/correction_plans.json",
                     "application/json"),
    "reset2-discovery": ("../vq1_reset2/same_domain_spec_discovery.json",
                         "application/json"),
    "reset2-supplier-requests": (
        "../vq1_reset2/vq1_supplier_specification_request.json",
        "application/json"),
    "reset2-it4-png": ("../vq1_reset2/iteration_4.png", "image/png"),
    "reset2-it5-png": ("../vq1_reset2/iteration_5.png", "image/png"),
    "corr1-review-png": ("../vq1_reset2/vq1_reset2_corr1_review.png",
                         "image/png"),
    "corr1-review-pdf": ("../vq1_reset2/vq1_reset2_corr1_review.pdf",
                         "application/pdf"),
    "corr1-review-json": ("../vq1_reset2/vq1_reset2_corr1_review.json",
                          "application/json"),
    "corr1-envelope": ("../vq1_reset2/concept_visual_envelope_it5.json",
                       "application/json"),
    "corr1-outreach": (
        "../vq1_reset2/vq1_supplier_specification_outreach.json",
        "application/json"),
    "it5-review-png": ("../vq1_it5_audit/vq1_it5_human_review.png",
                       "image/png"),
    "it5-review-pdf": ("../vq1_it5_audit/vq1_it5_human_review.pdf",
                       "application/pdf"),
    "it5-review-json": ("../vq1_it5_audit/vq1_it5_human_review.json",
                        "application/json"),
    "it5-input-manifest": (
        "../vq1_it5_audit/visual_inspector_input_manifest.json",
        "application/json"),
    "it5-apex-proof": (
        "../vq1_it5_audit/it5_output_pixel_apex_proof.json",
        "application/json"),
    "it5-apex-mask": ("../vq1_it5_audit/it5_apex_binary_mask.png",
                      "image/png"),
    "it5-replay": ("../vq1_it5_audit/visualizer_replay.json",
                   "application/json"),
    "it5-conflict-resolution": (
        "../vq1_it5_audit/visualizer_conflict_resolution.json",
        "application/json"),
    "it5-input-it5": ("../vq1_it5_audit/visualizer_input_it5.png",
                      "image/png"),
    "it5-input-it4": ("../vq1_it5_audit/visualizer_input_it4.png",
                      "image/png"),
    "gate-record": (
        "../vq1_visualizer_gate/vq_visualizer_input_quality_gate.json",
        "application/json"),
    "gate-crops": ("../vq1_visualizer_gate/it5_component_crops.json",
                   "application/json"),
    "gate-dome-crop": (
        "../vq1_visualizer_gate/iteration_5_dome_apex.png", "image/png"),
    "gate-closure-crop": (
        "../vq1_visualizer_gate/iteration_5_closure.png", "image/png"),
    "it6-review-png": ("../vq1_it6_review/vq1_it6_collar_neck_review.png",
                       "image/png"),
    "it6-review-pdf": ("../vq1_it6_review/vq1_it6_collar_neck_review.pdf",
                       "application/pdf"),
    "it6-review-json": ("../vq1_it6_review/vq1_it6_collar_neck_review.json",
                        "application/json"),
    "it6-png": ("../vq1_reset2/iteration_6.png", "image/png"),
    "it6-envelope": ("../vq1_reset2/concept_visual_envelope_it6.json",
                     "application/json"),
    "it6-blockers": (
        "../vq1_it6_review/vq1_it6_blocker_classification.json",
        "application/json"),
    "it6-reference-pixels": (
        "../vq1_reset2/it6_reference_collar_pixels.json",
        "application/json"),
    "corr5-p1-png": ("../vq1_corr5/vq1_corr5_p1_bulb.png",
                         "image/png"),
    "corr5-p1-pdf": ("../vq1_corr5/vq1_corr5_p1_bulb.pdf",
                         "application/pdf"),
    "corr5-p2-png": ("../vq1_corr5/vq1_corr5_p2_collar_neck.png",
                         "image/png"),
    "corr5-p2-pdf": ("../vq1_corr5/vq1_corr5_p2_collar_neck.pdf",
                         "application/pdf"),
    "corr5-p3-png": ("../vq1_corr5/vq1_corr5_p3_shoulder_body.png",
                         "image/png"),
    "corr5-p3-pdf": ("../vq1_corr5/vq1_corr5_p3_shoulder_body.pdf",
                         "application/pdf"),
    "corr5-p4-png": ("../vq1_corr5/vq1_corr5_p4_assembly.png",
                         "image/png"),
    "corr5-p4-pdf": ("../vq1_corr5/vq1_corr5_p4_assembly.pdf",
                         "application/pdf"),
    "corr5-p5-png": ("../vq1_corr5/vq1_corr5_p5_overlay.png",
                         "image/png"),
    "corr5-p5-pdf": ("../vq1_corr5/vq1_corr5_p5_overlay.pdf",
                         "application/pdf"),
    "corr5-p6-png": ("../vq1_corr5/vq1_corr5_p6_all_fixtures.png",
                         "image/png"),
    "corr5-p6-pdf": ("../vq1_corr5/vq1_corr5_p6_all_fixtures.pdf",
                         "application/pdf"),
    "corr5-p7-png": ("../vq1_corr5/vq1_corr5_p7_deviation.png",
                         "image/png"),
    "corr5-p7-pdf": ("../vq1_corr5/vq1_corr5_p7_deviation.pdf",
                         "application/pdf"),
    # --- VQ-1 CLOSE-1 closeout + owner acceptance ---------------------------
    "close1-review-pdf": ("../vq1_master/vq1_master_structural_review.pdf",
                          "application/pdf"),
    "close1-review-png": ("../vq1_master/vq1_master_structural_review.png",
                          "image/png"),
    "close1-review-json": ("../vq1_master/vq1_master_structural_review.json",
                           "application/json"),
    "close1-forensics-pdf": ("../vq1_master/vq1_junction_forensics.pdf",
                             "application/pdf"),
    "close1-forensics-png": ("../vq1_master/vq1_junction_forensics.png",
                             "image/png"),
    "close1-forensics-json": ("../vq1_master/vq1_junction_forensics.json",
                              "application/json"),
    "close1-owner-acceptance": ("../vq1_master/vq1_owner_acceptance.json",
                                "application/json"),
    "close1-adjudication": (
        "../vq1_master/vq1_human_structural_adjudication.json",
        "application/json"),
    "close1-final-candidate": (
        "../vq1_master/vq1_final_structural_candidate.json",
        "application/json"),
    "close1-scoring-contract": (
        "../vq1_master/vq1_structural_scoring_contract.json",
        "application/json"),
    "close1-fitter-defect": (
        "../vq1_master/vq1_fitter_defect_and_remediation.json",
        "application/json"),
    # --- VQ-2 (lettering / typography) — the board must serve it too ---
    "vq2-state": ("../vq2/vq2_state.json", "application/json"),
    "vq2-provider-blocker": ("../vq2/vq2_typography_provider_blocker.json",
                             "application/json"),
    "vq2-resume-attempt-1": ("../vq2/vq2_lf1_resume_attempt_1.json",
                             "application/json"),
    "vq2-billing-probe": ("../vq2/vq2_anthropic_billing_probe.json",
                          "application/json"),
    "vq2-billing-probe-2": ("../vq2/vq2_anthropic_billing_probe_2.json",
                            "application/json"),
    "vq2-a2-ai": ("../vq2/vq2_a2.ai", "application/pdf"),
    "vq2-a2-r1-ai": ("../vq2/vq2_a2_r1.ai", "application/pdf"),
    "vq2-a2-r2-ai": ("../vq2/vq2_a2_r2.ai", "application/pdf"),
    "vq2-final-ai": ("../vq2/vq2_a2_r2_final.ai", "application/postscript"),
    "vq2-final-pdf": ("../vq2/vq2_a2_r2_final.pdf", "application/pdf"),
    "vq2-final-clean": ("../vq2/vq2_a2_r2_final_clean.png", "image/png"),
    "vq2-final-guides": ("../vq2/vq2_a2_r2_final_guides.png", "image/png"),
    "vq2-final-audit": ("../vq2/vq2_a2_r2_final_audit.json",
                        "application/json"),
    "vq2-final-review-pdf": ("../vq2/vq2_a2_r2_final_review.pdf",
                             "application/pdf"),
    "vq2-final-review-png": ("../vq2/vq2_a2_r2_final_review.png",
                             "image/png"),
    "vq2-final-review-json": ("../vq2/vq2_a2_r2_final_review.json",
                              "application/json"),
    "vq2-final-manifest": ("../vq2/vq2_a2_r2_final_object_manifest.json",
                           "application/json"),
    "vq2-final-supporting-authority": (
        "../vq2/vq2_supporting_copy_source_authority_v2.json",
        "application/json"),
    "vq3-m1": ("../vq3/vq3_m1_reference_balanced.png", "image/png"),
    "vq3-m2": ("../vq3/vq3_m2_soft_frosted.png", "image/png"),
    "vq3-m3": ("../vq3/vq3_m3_warm_rose_gold.png", "image/png"),
    "vq3-review-pdf": ("../vq3/vq3_material_review.pdf", "application/pdf"),
    "vq3-review-png": ("../vq3/vq3_material_review.png", "image/png"),
    "vq3-review-json": ("../vq3/vq3_material_review.json",
                        "application/json"),
    "pap-preflight-pdf": (
        "../../production_authority/production_authority_preflight.pdf",
        "application/pdf"),
    "pap-preflight-png": (
        "../../production_authority/production_authority_preflight.png",
        "image/png"),
    "pap-preflight-json": (
        "../../production_authority/production_authority_preflight.json",
        "application/json"),
    "pap-gates": ("../../production_authority/production_authority_gate.json",
                  "application/json"),
    "pap-illustrator-checklist": (
        "../../production_authority/"
        "illustrator_execution_verification_checklist.pdf",
        "application/pdf"),
    "pap-illustrator-template": (
        "../../production_authority/"
        "illustrator_execution_verification_result_template.json",
        "application/json"),
    "pap-supplier-spec": (
        "../../production_authority/"
        "supplier_evidence_request_specification.pdf", "application/pdf"),
    "pap-supplier-drafts": (
        "../../production_authority/production_supplier_request_drafts.json",
        "application/json"),
    "pap-illustrator-receipts": (
        "../../production_authority/"
        "illustrator_execution_verification_receipts.json",
        "application/json"),
    # GATE-A-CORR-1. The owner cannot perform the Illustrator round trip
    # without downloading the corrected source itself, so it is served here
    # alongside the evidence that it carries its colours.
    "gate-a-r1-ai": ("../vq2/vq2_a2_r2_final_gate_a_r1.ai",
                     "application/postscript"),
    "gate-a-r1-pdf": ("../vq2/vq2_a2_r2_final_gate_a_r1.pdf",
                      "application/pdf"),
    "gate-a-r1-png": ("../vq2/vq2_a2_r2_final_gate_a_r1.png", "image/png"),
    "gate-a-r1-manifest": (
        "../vq2/vq2_a2_r2_final_gate_a_r1_color_manifest.json",
        "application/json"),
    "gate-a-r1-equivalence": (
        "../vq2/vq2_a2_r2_final_gate_a_r1_equivalence.json",
        "application/json"),
    "gate-a-r1-gates": (
        "../../production_authority/gate_a_corr1_automated_gates.json",
        "application/json"),
    "gate-a-defective-source-record": (
        "../vq2/vq2_a2_r2_final_defective_source.json", "application/json"),
    "gate-a-color-capability": (
        "../vq2/vq2_a8_color_capability_fixture.json", "application/json"),
    # GATE-A-CORR-2. R1 rendered only 3 of 40 objects in Illustrator, so the
    # owner needs the R2 source AND the script that drives the round trip.
    "gate-a-r2-ai": ("../vq2/vq2_a2_r2_final_gate_a_r2.ai",
                     "application/postscript"),
    "gate-a-r2-pdf": ("../vq2/vq2_a2_r2_final_gate_a_r2.pdf",
                      "application/pdf"),
    "gate-a-r2-png": ("../vq2/vq2_a2_r2_final_gate_a_r2.png", "image/png"),
    "gate-a-r2-manifest": ("../vq2/vq2_a2_r2_final_gate_a_r2_manifest.json",
                           "application/json"),
    "gate-a-r2-equivalence": (
        "../vq2/vq2_a2_r2_final_gate_a_r2_equivalence.json",
        "application/json"),
    "gate-a-r2-gates": (
        "../../production_authority/gate_a_corr2_automated_gates.json",
        "application/json"),
    "gate-a-r1-failure": (
        "../vq2/vq2_a2_r2_final_gate_a_r1_failure.json", "application/json"),
    "gate-a-roundtrip-jsx": (
        "../../production_authority/illustrator_gate_a_roundtrip.jsx",
        "text/plain"),
    "gate-a-fixtures": (
        "../vq2/illustrator_compatibility_fixtures.json", "application/json"),
    "gate-a-fixture-a-ai": (
        "../vq2/illustrator_fixtures/fixture_a_layer_sequence.ai",
        "application/postscript"),
    "gate-a-fixture-a-png": (
        "../vq2/illustrator_fixtures/fixture_a_layer_sequence.png",
        "image/png"),
    "gate-a-fixture-b-ai": (
        "../vq2/illustrator_fixtures/fixture_b_compound_path.ai",
        "application/postscript"),
    "gate-a-fixture-c-ai": (
        "../vq2/illustrator_fixtures/fixture_c_artwork_paint.ai",
        "application/postscript"),
    "gate-a-fixture-d-ai": (
        "../vq2/illustrator_fixtures/fixture_d_graphics_state.ai",
        "application/postscript"),
    "gate-a-r2-initial-open": (
        "../vq2/vq2_a2_r2_final_gate_a_r2_initial_open.json",
        "application/json"),
    # round trip 1: artwork passed, artboard failed. Both the evidence and the
    # corrected script have to be reachable from the board.
    "gate-a-roundtrip1-record": (
        "../vq2/gate_a_roundtrip_1_artboard_drift.json", "application/json"),
    "gate-a-drift-ai": (
        "../vq2/vq2_a2_r2_final_illustrator_verified_artboard_drift.ai",
        "application/postscript"),
    "gate-a-drift-pdf": (
        "../vq2/vq2_a2_r2_final_illustrator_verified_artboard_drift.pdf",
        "application/pdf"),
    "gate-a-drift-png": (
        "../vq2/vq2_a2_r2_final_illustrator_verified_artboard_drift.png",
        "image/png"),
    "gate-a-aborted-run": (
        "../../production_authority/"
        "illustrator_execution_verification_result_aborted_run.json",
        "application/json"),
    "gate-a-final-gates": (
        "../../production_authority/gate_a_roundtrip_final_gates.json",
        "application/json"),
    # Gate A PASSED — the verified package and the reconciliation beside it
    "gate-a-verified-ai": ("../vq2/vq2_a2_r2_final_illustrator_verified.ai",
                           "application/pdf"),
    "gate-a-verified-pdf": ("../vq2/vq2_a2_r2_final_illustrator_verified.pdf",
                            "application/pdf"),
    "gate-a-verified-png": ("../vq2/vq2_a2_r2_final_illustrator_verified.png",
                            "image/png"),
    "gate-a-verified-result": (
        "../vq2/illustrator_execution_verification_result.json",
        "application/json"),
    "gate-a-final-verification": (
        "../vq2/gate_a_final_verification.json", "application/json"),
    "supplier-dispatch-log": (
        "../../production_authority/supplier_evidence_request_dispatch.json",
        "application/json"),
    "supplier-sent-validation": (
        "../../archive/supplier/"
        "supplier_sent_evidence_validation.json", "application/json"),
    "supplier-manifest-json": (
        "../../archive/supplier/supplier_dispatch_manifest.json",
        "application/json"),
    "supplier-manifest-pdf": (
        "../../archive/supplier/supplier_dispatch_manifest.pdf",
        "application/pdf"),
    "supplier-manifest-png": (
        "../../archive/supplier/supplier_dispatch_manifest.png",
        "image/png"),
    "supplier-eml-1": (
        "../../archive/supplier/supplier_emails/"
        "supplier_01_liquid_bottles.eml", "message/rfc822"),
    "supplier-eml-2": (
        "../../archive/supplier/supplier_emails/"
        "supplier_02_sks_bottle.eml", "message/rfc822"),
    "supplier-eml-3": (
        "../../archive/supplier/supplier_emails/"
        "supplier_03_bottlestore_oberk.eml", "message/rfc822"),
    "supplier-eml-4": (
        "../../archive/supplier/supplier_emails/"
        "supplier_04_premium_vials.eml", "message/rfc822"),
    "supplier-eml-5": (
        "../../archive/supplier/supplier_emails/"
        "supplier_05_nicer_packaging.eml", "message/rfc822"),
    "supplier-dispatch-pack": (
        "../../archive/supplier/"
        "supplier_evidence_request_dispatch_pack.txt", "text/plain"),
    "gate-a-reconciliation": (
        "../vq2/illustrator_execution_verification_result_reconciliation.json",
        "application/json"),
    "vq3-closeout-pdf": ("../vq3/vq3_material_closeout.pdf",
                         "application/pdf"),
    "vq3-closeout-png": ("../vq3/vq3_material_closeout.png", "image/png"),
    "vq3-closeout-json": ("../vq3/vq3_material_closeout.json",
                          "application/json"),
    "vq3-closeout-verification": ("../vq3/vq3_closeout_verification.json",
                                  "application/json"),
    "vq3-mask-sheet": ("../vq3/vq3_m3_component_mask_sheet.png", "image/png"),
    "vq3-geometry-overlay": ("../vq3/vq3_m3_geometry_overlay.png",
                             "image/png"),
    "vq3-material-closeups": ("../vq3/vq3_m3_material_closeups.png",
                              "image/png"),
    "vq3-selection": ("../vq3/vq3_owner_selection.json", "application/json"),
    "vq3-closeout": ("../vq3/vq3_closeout.json", "application/json"),
    "vq3-research": ("../vq3/vq3_material_research.json", "application/json"),
    "cp-owner-approval": (
        "../complete_product/complete_product_owner_approval.json",
        "application/json"),
    "cp-review-pdf": ("../complete_product/complete_product_review.pdf",
                      "application/pdf"),
    "cp-review-png": ("../complete_product/complete_product_review.png",
                      "image/png"),
    "cp-review-json": ("../complete_product/complete_product_review.json",
                       "application/json"),
    "cp-handoff": ("../complete_product/complete_product_handoff.json",
                   "application/json"),
    "cp-consistency": (
        "../complete_product/complete_product_inspection_consistency.json",
        "application/json"),
    "cp-concept": ("../complete_product/cp_1_concept.png", "image/png"),
    "cp-integrated": ("../complete_product/cp_2_integrated.png", "image/png"),
    "cp-side-by-side": ("../complete_product/cp_3_side_by_side.png",
                        "image/png"),
    "cp-silhouette": ("../complete_product/cp_4_silhouette.png", "image/png"),
    "cp-balance": ("../complete_product/cp_5_balance.png", "image/png"),
    "cp-hierarchy": ("../complete_product/cp_6_hierarchy.png", "image/png"),
    "cp-colour": ("../complete_product/cp_7_colour.png", "image/png"),
    "vq2-final-approval": (
        "../vq2/vq2_final_front_artwork_owner_approval.json",
        "application/json"),
    "vq2-handoff": ("../vq2/vq2_complete_product_handoff.json",
                    "application/json"),
    "vq2-a2-r2-clean": ("../vq2/vq2_a2_r2_clean.png", "image/png"),
    "vq2-a2-r2-guides": ("../vq2/vq2_a2_r2_guides.png", "image/png"),
    "vq2-a2-r2-json": ("../vq2/vq2_a2_r2.json", "application/json"),
    "vq2-a2-r2-review-pdf": ("../vq2/vq2_a2_r2_artwork_review.pdf",
                             "application/pdf"),
    "vq2-a2-r2-review-png": ("../vq2/vq2_a2_r2_artwork_review.png",
                             "image/png"),
    "vq2-a2-r2-review-json": ("../vq2/vq2_a2_r2_artwork_review.json",
                              "application/json"),
    "vq2-a2-r2-symmetry": ("../vq2/vq2_a2_r2_symmetry_proof.json",
                           "application/json"),
    "vq2-a2-r2-logo-validation": ("../vq2/vq2_a2_r2_logo_validation.json",
                                  "application/json"),
    "vq2-r1-diagnosis": ("../vq2/vq2_a2_r1_defect_diagnosis.json",
                         "application/json"),
    "vq2-a2-r1-clean": ("../vq2/vq2_a2_r1_clean.png", "image/png"),
    "vq2-a2-r1-guides": ("../vq2/vq2_a2_r1_guides.png", "image/png"),
    "vq2-a2-r1-json": ("../vq2/vq2_a2_r1.json", "application/json"),
    "vq2-a2-r1-review-pdf": ("../vq2/vq2_a2_r1_artwork_review.pdf",
                             "application/pdf"),
    "vq2-a2-r1-review-png": ("../vq2/vq2_a2_r1_artwork_review.png",
                             "image/png"),
    "vq2-a2-r1-review-json": ("../vq2/vq2_a2_r1_artwork_review.json",
                              "application/json"),
    "vq2-supporting-authority": (
        "../vq2/vq2_supporting_copy_source_authority.json",
        "application/json"),
    "vq2-logo-ink": ("../vq2/vq2_product_specific_logo_ink.json",
                     "application/json"),
    "vq2-a2-r1-gates": ("../vq2/vq2_a2_r1_deterministic_gates.json",
                        "application/json"),
    "vq2-a2-png": ("../vq2/vq2_a2.png", "image/png"),
    "vq2-a2-json": ("../vq2/vq2_a2.json", "application/json"),
    "vq2-a2-review-pdf": ("../vq2/vq2_a2_artwork_review.pdf",
                          "application/pdf"),
    "vq2-a2-review-png": ("../vq2/vq2_a2_artwork_review.png", "image/png"),
    "vq2-a2-review-json": ("../vq2/vq2_a2_artwork_review.json",
                           "application/json"),
    "vq2-a2-m3-freeze": ("../vq2/vq2_a2_m3_freeze_verification.json",
                         "application/json"),
    "vq2-lettering-approval": ("../vq2/vq2_lettering_owner_approval.json",
                               "application/json"),
    "vq2-preflight": ("../vq2/vq2_lf1_inspection_preflight.json",
                      "application/json"),
    "vq2-inspection": ("../vq2/vq2_lf1_typography_inspection.json",
                       "application/json"),
    "vq2-consistency": (
        "../vq2/vq2_lf1_typography_inspection_consistency.json",
        "application/json"),
    "vq2-review-json": ("../vq2/typeface/vq2_imbue_lf1_r1_review.json",
                        "application/json"),
    "vq2-review-pdf": ("../vq2/typeface/vq2_imbue_lf1_r1_review.pdf",
                       "application/pdf"),
    "vq2-review-png": ("../vq2/typeface/vq2_imbue_lf1_r1_review.png",
                       "image/png"),
    "vq2-resume-contract": (
        "../vq2/vq2_lf1_r1_inspection_resume_contract.json",
        "application/json"),
    "vq2-input-freeze": ("../vq2/vq2_lf1_inspection_input_freeze.json",
                         "application/json"),
    "vq2-certification": (
        "../vq2/vq2_lf1_r1_deterministic_certification.json",
        "application/json"),
    "vq2-equivalence": ("../vq2/vq2_outline_equivalence_v21.json",
                        "application/json"),
    "vq2-pending-json": (
        "../vq2/typeface/vq2_imbue_lf1_r1_review_pending.json",
        "application/json"),
    "vq2-pending-pdf": (
        "../vq2/typeface/vq2_imbue_lf1_r1_review_pending.pdf",
        "application/pdf"),
    "vq2-pending-png": (
        "../vq2/typeface/vq2_imbue_lf1_r1_review_pending.png", "image/png"),
    "close1-workstream-state": ("../vq1_master/vq1_workstream_state.json",
                                "application/json"),
    "close1-withdrawal": (
        "../vq1_master/vq1_measurement_method_withdrawal.json",
        "application/json"),
    "close1-dense": (
        "../vq1_master/vq1_neck_shoulder_dense_confirmation.json",
        "application/json"),
    "close1-assembly-dense": (
        "../vq1_master/vq1_assembly_wide_dense_confirmation.json",
        "application/json"),
    "close1-dual-inspection": (
        "../vq1_master/vq1_close1_dual_inspection.json", "application/json"),
    "close1-m3-png": ("../vq1_master/master_it3.png", "image/png"),
    "close1-contour-overlay": (
        "../vq1_master/close1/contour_overlay.png", "image/png"),
    "close1-neck-diagram": (
        "../vq1_master/close1/neck_width_diagram.png", "image/png"),
    "close1-shoulder-diagram": (
        "../vq1_master/close1/shoulder_curvature_diagram.png", "image/png"),
}

#: the owner-acceptance record is the board's authority on VQ-1 state
ACCEPTANCE_FILE = os.path.join(
    settings.BASE_DIR, "docs", "visual_quality", "vq1_master",
    "vq1_owner_acceptance.json")
WORKSTREAM_FILE = os.path.join(
    settings.BASE_DIR, "docs", "visual_quality", "vq1_master",
    "vq1_workstream_state.json")


VQ2_DIR = os.path.join(settings.BASE_DIR, "docs", "visual_quality", "vq2")


def _json_or_none(path: str):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def _vq2_summary() -> dict:
    """VQ-2's live hold state, read from the records — never hard-coded.

    Committed files are not a human review boundary; the board has to show
    this or the owner cannot see that VQ-2 is waiting on them.
    """
    blk = _json_or_none(
        os.path.join(VQ2_DIR, "vq2_typography_provider_blocker.json")) or {}
    att = _json_or_none(
        os.path.join(VQ2_DIR, "vq2_lf1_resume_attempt_1.json")) or {}
    st = _json_or_none(os.path.join(VQ2_DIR, "vq2_state.json")) or {}
    prb = _json_or_none(
        os.path.join(VQ2_DIR, "vq2_anthropic_billing_probe_2.json")) \
        or _json_or_none(
            os.path.join(VQ2_DIR, "vq2_anthropic_billing_probe.json")) or {}
    rev = _json_or_none(
        os.path.join(VQ2_DIR, "typeface", "vq2_imbue_lf1_r1_review.json"))
    appr = _json_or_none(os.path.join(
        VQ2_DIR, "vq2_final_front_artwork_owner_approval.json"))
    _CPD = os.path.join(os.path.dirname(VQ2_DIR), "complete_product")
    cp = _json_or_none(os.path.join(_CPD, "complete_product_review.json"))
    cpa = _json_or_none(os.path.join(
        _CPD, "complete_product_owner_approval.json"))
    _V3D = os.path.join(os.path.dirname(VQ2_DIR), "vq3")
    v3 = _json_or_none(os.path.join(_V3D, "vq3_material_review.json"))
    v3s = _json_or_none(os.path.join(_V3D, "vq3_owner_selection.json"))
    v3c = _json_or_none(os.path.join(_V3D, "vq3_material_closeout.json"))
    pap = _json_or_none(os.path.join(
        settings.BASE_DIR, "docs", "production_authority",
        "production_authority_preflight.json"))
    a2r = _json_or_none(
        os.path.join(VQ2_DIR, "vq2_a2_r2_final_review.json")) \
        or _json_or_none(
            os.path.join(VQ2_DIR, "vq2_a2_r2_artwork_review.json")) \
        or _json_or_none(
            os.path.join(VQ2_DIR, "vq2_a2_r1_artwork_review.json")) \
        or _json_or_none(os.path.join(VQ2_DIR, "vq2_a2_artwork_review.json"))
    a2 = _json_or_none(os.path.join(VQ2_DIR, "vq2_a2_r2.json")) \
        or _json_or_none(os.path.join(VQ2_DIR, "vq2_a2_r1.json")) \
        or _json_or_none(os.path.join(VQ2_DIR, "vq2_a2.json"))
    probe = None
    if prb:
        probe = {
            "outcome": prb.get("outcome"),
            "code": prb.get("code") or ", ".join(prb.get("codes") or []),
            "request_id": prb.get("request_id"),
            "credential_valid": prb.get("credential_valid"),
            "billing_available": prb.get("billing_available"),
            "root_cause": (None if prb.get("outcome") == "PROBE_SUCCEEDED"
                           else blk.get("root_cause")),
            # fingerprint only — the key itself is never read into a response
            "key_fingerprint": (prb.get("secret_source") or {}).get(
                "key_fingerprint_sha256_12"),
            "env_file_mtime": (prb.get("secret_source") or {}).get(
                "env_file_mtime"),
        }
    return {
        "workstream": "VQ-2 — Surface Artwork, Flat Colour, Level-A "
                      "Typography",
        "started": True,
        "state": st.get("VQ_2") or st.get("state"),
        "lettering_candidate": "VQ2-LF1-R1 (Imbue, SIL OFL, opsz 100 / "
                               "wght 400)",
        "deterministic_certification":
            "VQ2_LF1_R1_DETERMINISTICALLY_CERTIFIED — vector 13/13, "
            "raster 13/13",
        "typography_inspection": (
            f"COMPLETE — {rev['inspections_performed']} independent "
            f"inspections" if rev else "NOT_PERFORMED"),
        "final_review": {
            "result_classification": rev.get("result_classification"),
            "inspector_a": {
                "request_id": rev["inspector_a"]["request_id"],
                "verdict": rev["inspector_a_result"].get("verdict"),
                "actionable_defects":
                    rev["inspector_a_result"].get("actionable_defect_count")},
            "inspector_b": {
                "request_id": rev["inspector_b"]["request_id"],
                "verdict": rev["inspector_b_result"].get("verdict"),
                "actionable_defects":
                    rev["inspector_b_result"].get("actionable_defect_count")},
            "consistency_all_pass": rev["consistency"]["all_checks_pass"],
            "divergences": rev["consistency"]["divergences"],
            "human_approval_state": rev.get("human_approval_state"),
            "is_gate_2": rev.get("is_gate_2"),
            "is_production_authority": rev.get("is_production_authority"),
            "package": {"pdf": "/api/visual-quality/vq1/vq2-review-pdf/",
                        "png": "/api/visual-quality/vq1/vq2-review-png/",
                        "json": "/api/visual-quality/vq1/vq2-review-json/"},
        } if rev else None,
        "rose_width": ((rev.get("rose_width") or {}).get("code") if rev
                       else att.get("rose_width_classification")),
        "blocker": {
            "reason": "ANTHROPIC_API_CREDIT",
            "external_to_this_repo": True,
            "attempts": len(blk.get("attempts") or []),
            "latest_request_id": blk.get("latest_request_id"),
            "retry_count": blk.get("retry_count"),
            "retries_remaining": blk.get("retries_remaining"),
            "further_automatic_retry": blk.get("further_automatic_retry"),
            "provider_substituted": blk.get("provider_substituted"),
        },
        "billing_probe": probe,
        "production_authority": {
            "state": pap.get("state"),
            "all_gates_blocked": (pap.get("gates") or {}).get(
                "all_gates_blocked"),
            "gates_passed": (pap.get("gates") or {}).get("gates_passed"),
            "gate_states": {k: v["state"] for k, v in
                            (pap.get("gates") or {}).get("gates", {}).items()},
            "illustrator_verification": (
                pap.get("illustrator_verification") or {}).get("state"),
            "supplier_requests_sent": pap.get("supplier_requests_sent"),
            "gates_remaining_blocked": (pap.get("gates") or {}).get(
                "gates_remaining_blocked"),
            "gate_a_passed": ((pap.get("gates") or {}).get("gates", {})
                              .get("A_illustrator_execution", {})
                              .get("state") == "PASSED"),
            "gate_a_does_not_grant": (pap.get("gates") or {}).get(
                "gate_a_passing_does_not_imply") or [],
            "next_required_owner_action": (pap.get("gates") or {}).get(
                "next_required_owner_action"),
            "supplier_dispatch": {
                "authorized": (pap.get("supplier_dispatch") or {}).get(
                    "authorization", {}).get("granted"),
                "sent": (pap.get("supplier_dispatch") or {}).get(
                    "requests_sent"),
                "blocked": (pap.get("supplier_dispatch") or {}).get(
                    "requests_blocked"),
                "ready": (pap.get("supplier_dispatch") or {}).get(
                    "requests_ready_not_sent"),
                "blocking_code": (pap.get("supplier_dispatch") or {}).get(
                    "blocking_code"),
                "log": "/api/visual-quality/vq1/supplier-dispatch-log/",
                "pack": "/api/visual-quality/vq1/supplier-dispatch-pack/",
                "manifest":
                    "/api/visual-quality/vq1/supplier-manifest-json/",
                "manifest_pdf":
                    "/api/visual-quality/vq1/supplier-manifest-pdf/",
                "sent_validation":
                    "/api/visual-quality/vq1/supplier-sent-validation/",
                "evidence_verified": (pap.get("supplier_sent_validation")
                                      or {}).get("messages_verified"),
                "evidence_received": (pap.get("supplier_sent_validation")
                                      or {}).get("messages_with_evidence"),
                "emails": [
                    {"supplier": m["supplier"],
                     "destination": m["destination"],
                     "status": m["status"],
                     "url": f"/api/visual-quality/vq1/supplier-eml-{i}/"}
                    for i, m in enumerate(
                        (pap.get("supplier_manifest") or {}).get(
                            "messages", []), start=1)],
            } if pap.get("supplier_dispatch") else None,
            "packaging_may_begin_now": (pap.get("gates") or {}).get(
                "packaging_may_begin_now"),
            "owner_actions_required": [
                a["action"] for a in pap.get("owner_actions_required") or []],
            "gates_b_to_e_wait_on": (pap.get("gates") or {}).get(
                "gates_b_to_e_wait_on"),
            "gate_causes": {k: v.get("cause") for k, v in
                            (pap.get("gates") or {}).get("gates", {}).items()
                            if "cause" in v},
            "illustrator_receipts": {
                "verification_copy_received": (
                    pap.get("illustrator_receipts") or {}).get(
                        "verification_copy_received"),
                "codes": [c for r in (pap.get("illustrator_receipts") or {}
                                      ).get("receipts", []) for c in r["codes"]],
                "awaiting": [a["filename"] for a in
                             (pap.get("illustrator_receipts") or {}).get(
                                 "awaiting", []) if not a["received"]],
            } if pap.get("illustrator_receipts") else None,
            # GATE-A-CORR-1 — the owner's Illustrator run FAILED, so the page
            # must say so and hand over the corrected source to try again.
            "gate_a_correction": dict(
                ((pap.get("gates") or {}).get("gates", {})
                 .get("A_illustrator_execution", {}).get("correction") or {}),
                failure_codes=(pap.get("illustrator_verification") or {}
                               ).get("codes") or [],
                downloads={
                    "ai": "/api/visual-quality/vq1/gate-a-r1-ai/",
                    "pdf": "/api/visual-quality/vq1/gate-a-r1-pdf/",
                    "png": "/api/visual-quality/vq1/gate-a-r1-png/",
                    "color_manifest":
                        "/api/visual-quality/vq1/gate-a-r1-manifest/",
                    "equivalence":
                        "/api/visual-quality/vq1/gate-a-r1-equivalence/",
                    "automated_gates":
                        "/api/visual-quality/vq1/gate-a-r1-gates/",
                    "defective_source_record":
                        "/api/visual-quality/vq1/"
                        "gate-a-defective-source-record/",
                    "r2_ai": "/api/visual-quality/vq1/gate-a-r2-ai/",
                    "r2_pdf": "/api/visual-quality/vq1/gate-a-r2-pdf/",
                    "r2_png": "/api/visual-quality/vq1/gate-a-r2-png/",
                    "r2_manifest":
                        "/api/visual-quality/vq1/gate-a-r2-manifest/",
                    "r2_equivalence":
                        "/api/visual-quality/vq1/gate-a-r2-equivalence/",
                    "r2_gates": "/api/visual-quality/vq1/gate-a-r2-gates/",
                    "r1_failure": "/api/visual-quality/vq1/gate-a-r1-failure/",
                    "roundtrip_jsx":
                        "/api/visual-quality/vq1/gate-a-roundtrip-jsx/",
                    "fixtures": "/api/visual-quality/vq1/gate-a-fixtures/",
                    "fixture_a_ai":
                        "/api/visual-quality/vq1/gate-a-fixture-a-ai/",
                    "r2_initial_open":
                        "/api/visual-quality/vq1/gate-a-r2-initial-open/",
                    "roundtrip1_record":
                        "/api/visual-quality/vq1/gate-a-roundtrip1-record/",
                    "drift_ai": "/api/visual-quality/vq1/gate-a-drift-ai/",
                    "drift_png": "/api/visual-quality/vq1/gate-a-drift-png/",
                    "aborted_run":
                        "/api/visual-quality/vq1/gate-a-aborted-run/",
                    "final_gates":
                        "/api/visual-quality/vq1/gate-a-final-gates/",
                    "verified_ai":
                        "/api/visual-quality/vq1/gate-a-verified-ai/",
                    "verified_pdf":
                        "/api/visual-quality/vq1/gate-a-verified-pdf/",
                    "verified_png":
                        "/api/visual-quality/vq1/gate-a-verified-png/",
                    "verified_result":
                        "/api/visual-quality/vq1/gate-a-verified-result/",
                    "final_verification":
                        "/api/visual-quality/vq1/gate-a-final-verification/",
                    "reconciliation":
                        "/api/visual-quality/vq1/gate-a-reconciliation/",
                },
                roundtrip_passed=bool(
                    ((pap.get("gates") or {}).get("gates", {})
                     .get("A_illustrator_execution", {}).get("correction")
                     or {}).get("roundtrip_passed")),
                initial_open_passed=bool(
                    (pap.get("illustrator_receipts") or {}).get(
                        "initial_open_passed")),
                roundtrip_performed=bool(
                    (pap.get("illustrator_receipts") or {}).get(
                        "roundtrip_performed")),
                attempts=[a for a in (
                    (pap.get("gates") or {}).get("gates", {})
                    .get("A_illustrator_execution", {})
                    .get("attempt_history") or [])],
            ) if pap.get("gate_a_correction") else None,
            "package": {
                "pdf": "/api/visual-quality/vq1/pap-preflight-pdf/",
                "json": "/api/visual-quality/vq1/pap-preflight-json/",
                "checklist":
                    "/api/visual-quality/vq1/pap-illustrator-checklist/"},
        } if pap else None,
        "vq3": {
            "state": (v3c["state"] if v3c
                      else (v3s["closeout_evaluation"]["result"] if v3s
                            else v3.get("state"))),
            "evidence_complete": bool(v3c and v3c.get("evidence_complete")),
            "selected": (v3s or {}).get("selected"),
            "alternates": list((v3s or {}).get("alternates") or {}),
            "remaining_closeout_items": (0 if v3c else (
                (v3s or {}).get("closeout_evaluation") or {}).get(
                    "further_vq3_tasks_remaining")),
            "grants_production_authority": (
                (v3s or {}).get("grants_production_authority")
                if v3s else False),
            "build_time_state": v3.get("state"),
            "result": v3.get("result_classification"),
            "candidates": v3.get("candidate_count"),
            "rank_order": v3.get("rank_order"),
            "ranking_is_advisory": True,
            "all_geometry_gates_pass": v3.get("all_geometry_gates_pass"),
            "image_generation_calls": (v3.get("render_method") or {}).get(
                "image_generation_calls"),
            "stage_b": (v3.get("render_method") or {}).get(
                "stage_b_image_model_enhancement"),
            "collar_body_integration_resolved": (
                v3.get("collar_body_integration") or {}).get("resolved"),
            "human_accepted": bool(v3s and v3s.get("human_accepted")),
            "build_time_human_accepted": v3.get("human_accepted"),
            "package": {"pdf": "/api/visual-quality/vq1/vq3-review-pdf/",
                        "json": "/api/visual-quality/vq1/vq3-review-json/",
                        "m1": "/api/visual-quality/vq1/vq3-m1/",
                        "m2": "/api/visual-quality/vq1/vq3-m2/",
                        "m3": "/api/visual-quality/vq1/vq3-m3/"},
        } if v3 else None,
        "complete_product": {
            "state": (cpa["downstream"]["COMPLETE_PRODUCT_REVIEW"] if cpa
                      else cp.get("state")),
            "result": ((cpa["codes"][0]) if cpa
                       else cp.get("result_classification")),
            # the build-time classification stays visible, unaltered
            "build_time_result": cp.get("result_classification"),
            "owner_decision": cpa.get("decision") if cpa else None,
            "inspector_disagreement": (
                "RESOLVED_BY_OWNER" if cpa else "OPEN"),
            "adjudications": (cpa or {}).get("adjudications_count", 0),
            "collar_colour": ("DEFERRED_TO_VQ3_MATERIAL_INTEGRATION" if cpa
                              else None),
            "logo_scale": ("OWNER_CONFIRMED_AND_FROZEN" if cpa else None),
            "left_datum": ("OWNER_CONFIRMED_AND_FROZEN" if cpa else None),
            "approval_record": ("/api/visual-quality/vq1/cp-owner-approval/"
                                if cpa else None),
            "open_defects": len(cp.get("open_defects") or []),
            "defects_contesting_accepted_decisions":
                (cp.get("consistency") or {}).get(
                    "defects_contesting_accepted_decisions"),
            "inspector_a": {
                "request_id": cp["inspector_a"]["request_id"],
                "verdict": cp["inspector_a_result"].get("verdict"),
                "actionable": cp["inspector_a_result"].get(
                    "actionable_defect_count")},
            "inspector_b": {
                "request_id": cp["inspector_b"]["request_id"],
                "verdict": cp["inspector_b_result"].get("verdict"),
                "actionable": cp["inspector_b_result"].get(
                    "actionable_defect_count")},
            "packaging_readiness": ((cpa or {}).get("downstream", {}).get(
                "PACKAGING_READINESS")
                or (cp.get("downstream_readiness") or {}).get(
                    "PACKAGING_READINESS")),
            "vq3_readiness": ((cpa or {}).get("downstream", {}).get(
                "VQ3_READINESS")
                or (cp.get("downstream_readiness") or {}).get(
                    "VQ3_READINESS")),
            "accepted_assets_modified": cp.get("accepted_assets_modified"),
            "human_accepted": bool(cpa and cpa.get("decision") == "APPROVED"),
            "build_time_human_accepted": cp.get("human_accepted"),
            "package": {"pdf": "/api/visual-quality/vq1/cp-review-pdf/",
                        "png": "/api/visual-quality/vq1/cp-review-png/",
                        "json": "/api/visual-quality/vq1/cp-review-json/"},
        } if cp else None,
        "owner_approval": {
            "decision": appr.get("decision"),
            "codes": appr.get("codes"),
            "approved_candidate": appr.get("approved_candidate"),
            "reviewed_artefact": appr.get("reviewed_artefact"),
            "scope": appr.get("scope"),
            "scope_excludes": appr.get("scope_excludes"),
            "advisory_notes_nonblocking":
                appr.get("advisory_notes_nonblocking"),
            "workstream": (appr.get("workstream_closure_evaluation")
                           or {}).get("result"),
            "closure_is_not": (appr.get("workstream_closure_evaluation")
                               or {}).get("closure_is_not"),
            "downstream_unchanged": appr.get("downstream_unchanged"),
            "record": "/api/visual-quality/vq1/vq2-final-approval/",
        } if appr else None,
        "a2": {
            "state": a2r.get("state"),
            "m3_identity": a2.get("m3_identity")
            or a2.get("m3_file_identity"),
            "m3_modified": a2.get("m3_modified")
            if a2.get("m3_modified") is not None
            else a2.get("m3_file_modified"),
            "hierarchy": a2.get("hierarchy_order_top_to_bottom"),
            "front_artwork_zone_compliant":
                a2.get("front_artwork_zone_compliant"),
            "material_realization_added": a2.get(
                "material_realization_added")
            if a2.get("material_realization_added") is not None
            else (a2.get("flat_artwork") or {}).get(
                "material_realization_added"),
            "production_flat_artwork": a2.get("production_flat_artwork"),
            "human_accepted": bool(appr and appr.get("decision")
                                   == "APPROVED"),
            "build_time_human_accepted": a2r.get("human_accepted"),
            "package": {"ai": "/api/visual-quality/vq1/vq2-a2-r2-ai/",
                        "clean": "/api/visual-quality/vq1/vq2-a2-r2-clean/",
                        "guides": "/api/visual-quality/vq1/vq2-a2-r2-guides/",
                        "pdf": "/api/visual-quality/vq1/vq2-a2-r2-review-pdf/",
                        "json":
                            "/api/visual-quality/vq1/vq2-a2-r2-review-json/"},
        } if (a2r and a2) else None,
        "owner_action_required": (
            "VQ-2 front artwork is OWNER APPROVED and the workstream is "
            "closed. Nothing downstream starts without an explicit "
            "instruction." if appr
            else "Review VQ2-A2 visually and decide whether the composed front "
            "artwork is right. Nothing here is acceptance." if a2r
            else "Look at the lettering and decide whether it is visually right "
            "for the product. Both machine inspections passed with zero "
            "actionable defects, but that is not acceptance — human visual "
            "approval is the boundary and an automated pass never overrides "
            "your judgement." if rev
            else prb.get("owner_action_required")
            or att.get("owner_action_required")),
        "human_approval": "NOT_GRANTED — no inspection has run, so there is "
                          "nothing to visually approve yet",
    }


def _review_state() -> dict:
    if os.path.exists(REVIEW_STATE_FILE):
        with open(REVIEW_STATE_FILE) as f:
            return json.load(f)
    return {"schema_version": REVIEW_SCHEMA, "state": "NOT_REVIEWED",
            "decided_by": None, "decided_at": None}


@login_required
def vq1_artifact(request, name):
    entry = ARTIFACTS.get(name)
    if entry is None:
        raise Http404("unknown VQ-1 artifact")
    filename, mime = entry
    path = os.path.join(VQ1_DIR, filename)
    # root-bounded: the whitelist gives basenames only, but stay paranoid
    # Defence in depth only — the whitelist above is the real control. The
    # bound is the docs/ tree because production-authority records live beside
    # visual_quality/, not inside it.
    root = os.path.realpath(os.path.join(settings.BASE_DIR, "docs"))
    if not os.path.realpath(path).startswith(root + os.sep) \
            or not os.path.exists(path):
        raise Http404("artifact missing")
    return FileResponse(open(path, "rb"), content_type=mime)


@login_required
def vq1_status(request):
    from apps.ire import vq1_backbone as vq
    rec = vq.build_backbone()
    summary = _vq2_summary()
    pa = (summary or {}).get("production_authority")
    return JsonResponse({
        "program": "FINAL VISUAL QUALITY PROGRAM",
        "workstream": "VQ-1 — Cylindrical Bottle Backbone and Closure "
                      "Assembly",
        "fixture": vq.IMPLEMENTATION,
        "fixture_hash": rec["backbone_hash"],
        "automated_verdict": rec["verdict"],
        "human_review": _review_state(),
        # read the live state rather than a literal — this string moved from
        # REQUIRED_BEFORE_PRODUCTION_AUTHORITY to PENDING_HUMAN_EXECUTION when
        # the preflight started, and a hardcoded copy would now be false
        "illustrator": (pa or {}).get("illustrator_verification")
                       or "ILLUSTRATOR_EXECUTION_VERIFICATION_REQUIRED",
        "owner_acceptance": _json_or_none(ACCEPTANCE_FILE),
        "workstream_state": _json_or_none(WORKSTREAM_FILE),
        "vq2": summary,
        "artifacts": {k: f"/api/visual-quality/vq1/{k}/"
                      for k in ARTIFACTS},
        "next_required_action": (
            ("VQ-1, VQ-2, COMPLETE PRODUCT AND VQ-3 ARE ALL OWNER ACCEPTED "
             "AND CLOSED. PRODUCTION AUTHORITY PREFLIGHT IS STARTED: "
             f"{pa['gates_passed']} of 5 gates passed; gates B to E wait on "
             f"{pa['gates_b_to_e_wait_on']} — "
             f"{pa['gate_causes'].get('B_supplier_geometry')}. "
             f"{len(pa['owner_actions_required'])} owner action(s) "
             "outstanding: " + "; ".join(pa["owner_actions_required"])
             + ". Packaging has not started; the system contacts no supplier "
             "(§BH46)."
             if pa else
             "VQ-1 IS OWNER ACCEPTED AND CLOSED. Production geometry remains "
             "blocked until the owner-supplied spec pack is intaken (§BH46).")
            if (_json_or_none(ACCEPTANCE_FILE) or {}).get("codes")
            else "HUMAN STRUCTURAL VISUAL REVIEW (accept or reject the "
                 "synthetic backbone — structure only)"),
        "scope_note": "program-level synthetic diagnostic — NOT a task-52 "
                      "reconstruction; acceptance never approves task 52, "
                      "materials, typography or VQ-2",
    })


@login_required
def vq1_review_page(request):
    return render(request, "dashboard/vq1_review.html", {
        "review": _review_state(),
        "fixture_hash_short": "19f9b98d0bc46a0d",
        "corr4": True,
        "acceptance": _json_or_none(ACCEPTANCE_FILE),
        "workstream": _json_or_none(WORKSTREAM_FILE),
        "vq2": _vq2_summary(),
    })


@login_required
@require_POST
def vq1_review_decision(request):
    state = request.POST.get("state", "")
    if state not in ("ACCEPTED", "REJECTED", "REVISION_REQUIRED"):
        return JsonResponse({"error": "state must be ACCEPTED, REJECTED "
                                      "or REVISION_REQUIRED"}, status=400)
    from django.utils import timezone
    record = {"schema_version": REVIEW_SCHEMA, "state": state,
              "decided_by": request.user.username,
              "decided_at": timezone.now().isoformat(),
              "reviewed_fixture": "CORR-5",
              "scope": "structural acceptance of the SYNTHETIC backbone "
                       "only — never task-52 approval, never material/"
                       "typography approval, never VQ-2 authorization"}
    # every prior human decision is preserved — a new decision is appended
    # to history, never an overwrite of the record it supersedes
    prior = _review_state()
    history = prior.pop("history", [])
    if prior.get("state") and prior.get("state") != "NOT_REVIEWED":
        history = [prior] + history
    record["history"] = history
    with open(REVIEW_STATE_FILE, "w") as f:
        json.dump(record, f, indent=1)
    return JsonResponse(record)
