"""PALT-M4B-A3P §5B — fail-closed manifest for the palette visual evidence.

Three milestones in a row recorded that their evidence images were never
produced, and each recorded it only as free text inside a validation
report. Free text does not stop anything: a downstream consumer can read
"A3F_RESULT: PASS" and proceed without ever learning that the visual
evidence behind it does not exist.

This module makes the gap structural. Evidence is REQUESTED by name, and
a request for evidence that was never produced raises. The default answer
is refusal, so a missing render can no longer pass as silence.

The individual image names were specified in the owner directives, not
persisted to this repository. Inventing 41 plausible filenames would
manufacture a manifest that looks complete and is not, so the counts are
recorded as stated by each milestone and the names are marked
NOT_ENUMERATED_IN_REPOSITORY. That is a smaller claim than the directive
asked for, and it is the true one.
"""
from __future__ import annotations

SCHEMA = "palette_evidence_manifest/1.0"

PRODUCED = "PRODUCED"
NOT_PRODUCED = "NOT_PRODUCED"
NOT_ENUMERATED = "NOT_ENUMERATED_IN_REPOSITORY"

#: What each milestone recorded about its own visual evidence, quoted from
#: its validation report rather than restated.
MILESTONES = {
    "A3R": {
        "deferred_image_count": 13,
        "named_diagnostics_total": 19,
        "produced": 1,
        "state": NOT_PRODUCED,
        "quoted": "no evidence images were produced in A3R — 18 of the 19 "
                  "named diagnostics are missing.",
        "source": "docs/roadmap/palt_m4b_a3r/a3r_validation_report.json",
    },
    "A3F": {
        "deferred_image_count": 16,
        "state": NOT_PRODUCED,
        "quoted": "no A3F evidence images and none of the 13 deferred A3R "
                  "images were produced",
        "source": "docs/roadmap/palt_m4b_a3f/a3f_validation_report.json",
    },
    "A3M": {
        "deferred_image_count": 12,
        "state": NOT_PRODUCED,
        "quoted": "no A3R, A3F or A3M evidence images were produced; the "
                  "gap is now three milestones deep",
        "source": "docs/roadmap/palt_m4b_a3m/a3m_validation_report.json",
    },
}

TOTAL_DEFERRED = sum(m["deferred_image_count"] for m in MILESTONES.values())

#: Numerical findings that DO have durable evidence, so the manifest does
#: not imply the milestones proved nothing.
PRODUCED_EVIDENCE = {
    "A3R_thickness_convergence":
        "docs/roadmap/palt_m4b_a3r/thickness_convergence_table.json",
    "A3R_method_comparison":
        "docs/roadmap/palt_m4b_a3r/thickness_method_comparison.json",
    "A3R_minimum_region":
        "docs/roadmap/palt_m4b_a3r/minimum_region_manifest.json",
    "A3M_identity_migration":
        "docs/roadmap/palt_m4b_a3m/identity_migration_map.json",
    "A3P_cup_wall_proof":
        "docs/roadmap/palt_m4b_a3p/a3p_cup_wall_proof.json",
    "A3P_classifier_validation":
        "docs/roadmap/palt_m4b_a3p/a3p_classifier_validation.json",
}

#: A3M §6 was recorded unresolved and was later closed by A3P. Superseding
#: is recorded, never silently dropped.
SUPERSEDED = {
    "A3M_SECTION_6_CUP_WALL_UNPROVEN": {
        "superseded_by": "A3P build-time FaceLog provenance",
        "evidence": PRODUCED_EVIDENCE["A3P_cup_wall_proof"],
        "why": "z-band classification put deck-skin faces inside the "
               "cup-wall band; provenance replaces inference",
    },
}


class EvidenceNotProduced(RuntimeError):
    """Raised when evidence is requested that does not exist."""


def require_evidence(name: str) -> str:
    """Return the path to produced evidence, or refuse.

    The default answer is refusal: anything not positively recorded as
    produced raises rather than returning None, so a caller cannot treat
    absent evidence as an empty-but-valid result.
    """
    if name in PRODUCED_EVIDENCE:
        return PRODUCED_EVIDENCE[name]
    if name in MILESTONES:
        m = MILESTONES[name]
        raise EvidenceNotProduced(
            f"{name} visual evidence was never produced "
            f"({m['deferred_image_count']} images outstanding): "
            f"{m['quoted']}")
    raise EvidenceNotProduced(
        f"no evidence named {name!r} is recorded as produced; the manifest "
        "refuses by default rather than implying it exists")


def visual_evidence_state() -> dict:
    """The whole gap, machine-readable."""
    return {
        "record_type": SCHEMA,
        "total_deferred_images": TOTAL_DEFERRED,
        "milestones": {k: dict(v) for k, v in MILESTONES.items()},
        "image_names": NOT_ENUMERATED,
        "why_names_absent": "the individual diagnostic names were specified "
                            "in the owner directives and never persisted "
                            "here; inventing 41 filenames would produce a "
                            "manifest that looks complete and is not",
        "produced_numerical_evidence": dict(PRODUCED_EVIDENCE),
        "superseded_findings": {k: dict(v) for k, v in SUPERSEDED.items()},
        "blocks": [
            "PALT_M5 pilot evidence package",
            "any claim that A3R/A3F/A3M were VISUALLY verified",
        ],
        "does_not_block": [
            "the numerical thickness authority, which has durable evidence",
            "geometry construction, which is deterministic and tested",
        ],
        "requires": "the pinned Blender 4.5.12 LTS render runtime, in its "
                    "VISUALIZATION_AND_RENDERING_ONLY role",
        "visual_verification_claimed": False,
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
    }
