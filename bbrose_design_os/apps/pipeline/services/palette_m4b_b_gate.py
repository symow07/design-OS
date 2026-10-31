"""M4B-B §11 — the exit gate.

Every condition is CHECKED, not asserted. The gate refuses by default:
anything it cannot verify counts as unmet, so a missing check reads as a
failure rather than as a pass.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DOCS = REPO / "docs" / "roadmap" / "palt_m4b_b"

SCHEMA = "palette_m4b_b_exit_gate/1.0"


def subject_separation(path):
    """(coverage, contrast) of a render against its own backdrop.

    The backdrop is the modal luminance OF THE BORDER RING. Taking the
    mode of the whole image identifies the subject as the background once
    the subject fills the frame, which reported a legible close-up of a
    pocket as having no contrast. In an orthographic technical render the
    frame edge is backdrop by construction, so it is the honest place to
    measure it from.

    Contrast is the 90th percentile of the subject against that backdrop,
    so a lit surface has to stand clear rather than a bright speck
    carrying the image.
    """
    import numpy as np
    from PIL import Image
    arr = np.asarray(Image.open(path).convert("RGB"))
    lum = arr.astype(int).mean(axis=2).round().astype(int)
    h, w = lum.shape
    band = max(2, int(min(h, w) * 0.05))
    border = np.concatenate([lum[:band].ravel(), lum[-band:].ravel(),
                             lum[:, :band].ravel(), lum[:, -band:].ravel()])
    bg = int(np.bincount(border, minlength=256).argmax())
    subject = np.abs(lum - bg) > 8
    if not subject.any():
        return 0.0, 0.0
    return (float(subject.mean()),
            float(np.percentile(lum[subject], 90) - bg))


def _mesh_diagnostics(components):
    from apps.pipeline.services import palette_moulded_validators as mv
    bad = []
    for name, comp in components.items():
        d = mv.validate_mesh(name, comp,
                             check_self_intersection=False)["diagnostics"]
        if (d["boundary_edges"] or d["non_manifold_edges"]
                or d["inconsistent_half_edges"]
                or d["euler_characteristic"] != 2):
            bad.append(name)
    return bad


def evaluate() -> dict:
    from apps.pipeline.services import palette_es3083_owner_confirmation \
        as OC
    from apps.pipeline.services import palette_moulded_geometry as MG
    from apps.pipeline.services import palette_moulded_rect as MR
    from apps.pipeline.services import palette_rect_pan as RP

    comps_b, dims_b = MR.build_rect_components(OC.confirmed_intent())
    comps_a, _dims_a = MG.build_moulded_components()
    checks = []

    def check(name, ok, detail):
        checks.append({"condition": name,
                       "verdict": "PASS" if ok else "FAIL",
                       "detail": detail})

    # pans seated with the contract clearance
    from apps.pipeline.services import palette_rect_tray_geometry as RT
    z = RT.POCKET_DATUM_SOLUTION["seating_datum_z_mm"]
    sec = RT.functional_section(dims_b["tray"], z)
    c = RP.contract_values()
    clr = (sec["width_mm"] - c["pan_width_mm"]) / 2
    check("pans are correctly seated",
          abs(clr - c["pocket_tolerance_mm"]) < 1e-6,
          f"{clr:.6f} mm per side at the seating datum")

    check("the tray is moulded credibly",
          dims_b["tray"]["draft"]["release_direction"] == "UPWARD"
          and dims_b["tray"]["weld_count"] == 0,
          "drafted, releases upward, no tolerance welding")

    lid = comps_b["lid_outer_shell"]["vertices"]
    check("the lid is credibly moulded",
          "lid_structural_rim" in comps_b
          and (lid[:, 2].max() - lid[:, 2].min()) > 3.0,
          "hollow shell with a structural rim, cavity opening down")

    knuckles = [n for n in comps_b if n.startswith("hinge_knuckle_")]
    check("the hinge is understandable",
          len(knuckles) == MR.HINGE["knuckle_count"]
          and "hinge_pin" in comps_b
          and "hinge_pin_cap_1" in comps_b,
          f"{len(knuckles)} alternating knuckles, pin, retention caps")

    check("the clasp is understandable",
          all(k in comps_b for k in
              ("clasp_hook", "clasp_hook_lip", "clasp_detent",
               "clasp_flex_zone", "clasp_finger_notch")),
          "hook, lip, detent, flex region and opening affordance")

    for fam, expected in (("p1a", 11), ("p1b", 10)):
        path = DOCS / f"{fam}_sections.json"
        rec = json.loads(path.read_text()) if path.exists() else {}
        check(f"true sections pass ({fam.upper()})",
              rec.get("produced_count") == expected
              and rec.get("method") == "TRUE_PLANE_CUT_NOT_CLIPPED_RENDER",
              f"{rec.get('produced_count')} of 11"
              + (" — mirror_stack has no mirror to cut"
                 if fam == "p1b" else ""))

    try:
        for state in MR.STATES:
            MR.compose_rect_state(comps_b, dims_b, state)
        ok, detail = True, f"{len(MR.STATES)} states compose"
    except Exception as exc:                                # noqa: BLE001
        ok, detail = False, str(exc)[:120]
    check("open/closed articulation passes", ok, detail)

    pin = DOCS.parent / "palt_m4b" / "p1a_moulded_identity_pin.json"
    from apps.pipeline.services import palette_identity as PI
    pinned = json.loads(pin.read_text())
    now = {n: PI.mesh_geometry_identity(c) for n, c in comps_a.items()}
    check("P1A remains regression-stable",
          now == pinned["components"],
          f"{len(now)} components match the pin")

    check("P1B reflects ES3083 design intent",
          dims_b["tray"]["grid"]["columns"] == 4
          and dims_b["tray"]["grid"]["rows"] == 3
          and dims_b["tray"]["pocket_shape"] == "RECTANGULAR"
          and dims_b["provenance"]["case_width_mm"] == MR.VISIBLE,
          "12 rectangular pans in 4 x 3, case footprint from the "
          "confirmed pan field")

    bad = _mesh_diagnostics(comps_b)
    check("all meshes pass diagnostics", not bad,
          f"{len(comps_b)} components, {len(bad)} non-conforming")

    # Completeness against the 23 REQUIRED views, not a count against a
    # threshold. The three section views come from §8 and are mapped in by
    # evidence_manifest; a threshold would clear while they were absent.
    from apps.pipeline.services import palette_m4b_b_evidence as EVB
    rec_path = DOCS / "review_records.json"
    recs = json.loads(rec_path.read_text()) if rec_path.exists() else []
    sections = {}
    for fam, fname in (("P1A", "p1a_sections.json"),
                       ("P1B", "p1b_sections.json")):
        fp = DOCS / fname
        sections[fam] = json.loads(fp.read_text()) if fp.exists() else {}
    manifest = EVB.evidence_manifest(recs, sections)
    #: the one declared exception, with its reason recorded in the record
    ALLOWED_MISSING = {"P1A": set(), "P1B": {"mirror_stack_view"}}
    unexplained = {
        fam: sorted(set(info["missing"]) - ALLOWED_MISSING.get(fam, set()))
        for fam, info in manifest["families"].items()}
    check("evidence manifest passes",
          bool(manifest["families"])
          and not any(unexplained.values()),
          "; ".join(f"{fam} {info['produced_count']}/"
                    f"{manifest['required_count']}"
                    + (f" missing {unexplained[fam]}"
                       if unexplained[fam] else "")
                    for fam, info in sorted(manifest["families"].items())))

    # §10 sets a legibility bar: "sufficient edge definition", "do not use
    # white-on-white evidence". Eight renders currently fail it — the
    # medium-grey clay part sits on a medium-grey backdrop, so a flat
    # elevation barely separates from it. That is the grey-on-grey form of
    # the defect the directive names, so the gate reports it.
    from apps.pipeline.services import palette_render_contract as RC
    illegible = []
    for rec in recs:
        for key in rec["produced"]:
            if key == "dimension_overlay":
                continue                      # a drawing, not a render
            fp = os.path.join(rec["out_dir"], f"{key}.png")
            if not os.path.exists(fp):
                continue
            cov, con = subject_separation(fp)
            fails_coverage = (
                cov <= RC.MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE)
            fails_contrast = (
                cov < RC.CONTRAST_APPLIES_BELOW_COVERAGE
                and con < RC.MINIMUM_LUMINANCE_CONTRAST)
            if fails_coverage or fails_contrast:
                illegible.append(
                    f"{rec['family']}/{key} (coverage {cov:.3f}, "
                    f"contrast {con:.0f})")
    check("review evidence is legible", not illegible,
          f"{len(illegible)} render(s) below the predeclared bars "
          f"(coverage {RC.MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE}, "
          f"contrast {RC.MINIMUM_LUMINANCE_CONTRAST:.0f}): "
          f"{sorted(illegible)}"
          if illegible else
          f"every render clears coverage "
          f"{RC.MINIMUM_MODAL_BACKGROUND_SUBJECT_COVERAGE} and contrast "
          f"{RC.MINIMUM_LUMINANCE_CONTRAST:.0f} against its backdrop")

    bridge = DOCS / "m4c9_visual_variant_proof_full.json"
    bdata = json.loads(bridge.read_text()) if bridge.exists() else {}
    check("design-intent bridge passes",
          bdata.get("DESIGN_INTENT_BRIDGE") == "PASS"
          and bdata.get("all_required_views_exist") is True,
          f"{bdata.get('produced_count')} of 10 views, "
          f"{bdata.get('differences_judged')} differences judged")

    failed = [c["condition"] for c in checks if c["verdict"] == "FAIL"]
    return {
        "record_type": SCHEMA,
        "checks": checks,
        "evidence_manifest": manifest,
        "failed": failed,
        "M4B_B_EXIT_GATE": "PASS" if not failed else "FAIL",
        "not_checked_here": [
            "full canonical pytest — run separately and recorded with the "
            "checkpoint, because a suite cannot verify itself from inside",
        ],
        "owner_approved": False,
        "manufacturing_authority": "NOT_ESTABLISHED",
        "PALT_P1_FINAL_DIMENSIONS": "NOT_APPROVED",
        "GATE_2": "BLOCKED",
    }


#: Gate C exemption — this module feeds verdicts from display-encoded
#: frames BY DECLARATION. The registry test asserts the exemption set
#: is closed: a new site cannot appear without failing it.
DISPLAY_SPACE_BY_DECLARATION = ("M4B-B evidence legibility: subject separation is a property of the review image itself")
