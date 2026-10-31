"""Gate C — the CLOSED set of display-space measurement exemptions.

Eight-then-ten sites were individually justified in
docs/roadmap/palt_m6/display_frame_measurement_sweep.json. An exemption
mechanism is the escape hatch through which the display-frame defect
class returns, so the set is enumerable here and a test asserts that
the declared set is EXACTLY the set of modules carrying the
DISPLAY_SPACE_BY_DECLARATION constant — the same shape as the tracker
closure-record invariant and the TemplateType set-equality assertion.
A ninth site cannot appear without failing something.
"""
from __future__ import annotations

DISPLAY_SPACE_EXEMPT_MODULES = frozenset({
    "apps/pipeline/services/palette_m5_closeout.py",
    "apps/pipeline/services/palette_m5_evidence.py",
    "apps/pipeline/services/palette_m4b_b_gate.py",
    "apps/pipeline/services/palette_variant_visual_proof.py",
    "apps/pipeline/services/a3p_evidence_render.py",
    "apps/pipeline/services/geometry_validation_render.py",
    "apps/pipeline/services/image_checks.py",
    "apps/pipeline/services/visual_input_quality.py",
    "apps/pipeline/services/gate_a_corr1.py",
    "apps/ire/vq2_vectorize.py",
})
