"""Emit fb3093_lid_C1.ai + fb3093_lid_C3.ai from the locked §M finals.

Authorized act: OWNER_BLOCKER_CLEARANCE.md §M via ../owner_pick_ingestion
.json — the A2/§J emission pattern: the proven emitter converts the LOCKED
final SVGs (it never edits), validates its own output, and each emission is
appended to m7_ai_emission_record.json with owner_approved false awaiting
the §I/§K acceptance pattern (§N). Run AFTER the vocabulary-growth commit
whose regression proved every locked emission byte-identical.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

from apps.pipeline.services import palette_m7_ai_emitter as AI  # noqa: E402

DUALS = (
    ("fb3093_lid_C1.ai", "fb3093_lid_C1_final.svg",
     "c1_finalisation_record.json"),
    ("fb3093_lid_C3.ai", "fb3093_lid_C3_final.svg",
     "c3_finalisation_record.json"),
)
FRAME = (72.0, 72.0)  # the brief's PRIOR frame — calipers re-flow by re-run


def assert_source_committed(svg: Path):
    """The §N incident's process fix: the C1 emission consumed an
    externally-modified working-tree SVG that differed from HEAD (and was
    later reverted, losing the bytes). Emission now REFUSES any source
    whose working-tree bytes differ from the committed state."""
    import subprocess
    rel = svg.resolve().relative_to(ROOT)
    head = subprocess.run(
        ["git", "show", f"HEAD:bbrose_design_os/{rel}"],
        capture_output=True, cwd=ROOT.parent)
    if head.returncode != 0:
        raise AI.AiEmitterError(f"{rel}: not present at HEAD — commit the "
                                "final before emitting")
    if hashlib.sha256(head.stdout).hexdigest() != hashlib.sha256(
            svg.read_bytes()).hexdigest():
        raise AI.AiEmitterError(
            f"{rel}: working tree differs from HEAD — refusing to emit an "
            "uncommitted source (the §N C1 incident's admission path)")


def main():
    face = AI.SetFace(AI.MATERIALS_FONT)
    rec_path = AI.OUT_DIR / "m7_ai_emission_record.json"
    record = json.loads(rec_path.read_text())
    existing = {e["ai"] for e in record["emissions"]}
    for ai_name, svg_name, fin_rec in DUALS:
        assert ai_name not in existing, f"{ai_name} already emitted"
        svg = HERE / svg_name
        assert_source_committed(svg)
        rec = AI.emit(svg, AI.OUT_DIR / ai_name, face)
        assert rec["artboard_mm"] == list(FRAME), rec["artboard_mm"]
        v = AI.validate(AI.OUT_DIR / ai_name, FRAME,
                        rec["live_text_blocks"], rec["spot_separations"])
        if v["verdict"] != "PASS":
            raise AI.AiEmitterError(f"{ai_name}: {v['findings']}")
        rec.update({
            "authorized_by": "OWNER_BLOCKER_CLEARANCE.md §M (dual pick "
                             "'c1 & c3') via owner_pick_ingestion.json "
                             "(H2 request fb3093_compact_02)",
            "h2_request": "docs/roadmap/palt_h2/fb3093_compact_02",
            "finalisation_record": "docs/roadmap/palt_h2/fb3093_compact_02"
                                   f"/final/{fin_rec}",
            "frame_tier": "PRIOR (72x72mm supplier-listing web measurement "
                          "— owner calipers supersede in place; the final "
                          "re-flows by re-run and re-emits)",
            "owner_approved": False,
        })
        record["emissions"].append(rec)
        record["validations"].append(v)
        print(f"{ai_name}: {rec['bytes']}b sha256 {rec['ai_sha256'][:16]} "
              f"spots={rec['spot_separations']} "
              f"live={len(rec['live_text_blocks'])} -> PASS")
    record["acceptance_scope_note"] = (
        "The top-level owner_approved and owner_acceptance block cover the "
        "FIRST THREE emissions only (the §I-accepted 2026-08-15 set). "
        "Later emissions carry their own owner_approved flag: "
        "es3083_lid_A2.ai ACCEPTED per §K (2026-08-15); fb3093_lid_C1.ai "
        "and fb3093_lid_C3.ai AWAIT acceptance per the §I/§K pattern "
        "(verdicts land as §N).")
    rec_path.write_text(json.dumps(record, indent=1) + "\n")
    print("record appended:", rec_path.name)


if __name__ == "__main__":
    main()
