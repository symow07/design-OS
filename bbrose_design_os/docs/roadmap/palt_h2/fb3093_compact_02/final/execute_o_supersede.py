"""§O SUPERSEDE execution — replace the as-picked C1 emission with the
canonical finalised emission.

Authorized act: OWNER_BLOCKER_CLEARANCE.md §O (O1, verbatim "Supersede",
2026-08-17): the canonical emission (4fb3541d…, committed source, rosette at
the measured channel centre) REPLACES the §N-accepted as-picked file
(9bebb28b…); acceptance transfers PENDING re-verification (owner_approved
false); incident → CLOSED_SUPERSEDED with its full residue preserved.

Every step asserts: committed-source guard, exact expected hashes on both
the outgoing and incoming bytes, validation PASS, record consistency.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path.insert(0, str(ROOT))

from apps.pipeline.services import palette_m7_ai_emitter as AI  # noqa: E402
from emit_duals import assert_source_committed  # noqa: E402

SUPERSEDED_AI = "9bebb28bc4156c0322c792e351cfcdc9f896f9a0225794818d774025ef582afc"
CANONICAL_SRC = "363b34e1834f7fd44516aa0a7274f441206f68accb15caffb8ba2cec5cba5944"
CANONICAL_AI = "4fb3541d52acf6c317ba4aeaa6f2117778ca087e9318ffc3609b02ef4b228513"


def main():
    svg = HERE / "fb3093_lid_C1_final.svg"
    ai_path = AI.OUT_DIR / "fb3093_lid_C1.ai"
    assert hashlib.sha256(svg.read_bytes()).hexdigest() == CANONICAL_SRC
    assert hashlib.sha256(ai_path.read_bytes()).hexdigest() == SUPERSEDED_AI
    assert_source_committed(svg)  # the incident's own guard, exercised

    face = AI.SetFace(AI.MATERIALS_FONT)
    rec = AI.emit(svg, ai_path, face)
    assert rec["ai_sha256"] == CANONICAL_AI, rec["ai_sha256"]
    v = AI.validate(ai_path, (72.0, 72.0), rec["live_text_blocks"],
                    rec["spot_separations"])
    assert v["verdict"] == "PASS", v["findings"]

    rec_path = AI.OUT_DIR / "m7_ai_emission_record.json"
    record = json.loads(rec_path.read_text())
    c1 = next(e for e in record["emissions"] if e["ai"] == "fb3093_lid_C1.ai")
    assert c1["source_binding_incident"]["status"] == \
        "OPEN_AWAITING_OWNER_RULING"

    c1["source_sha256"] = rec["source_sha256"]
    c1["ai_sha256"] = rec["ai_sha256"]
    c1["bytes"] = rec["bytes"]
    c1["superseded_acceptance"] = {
        "what": "the §N acceptance covered the as-picked emission "
                "9bebb28b… (949,655 b); §O ruled SUPERSEDE — that "
                "acceptance transfers to THIS finalised file PENDING "
                "re-verification by the usual basis (render + sha256)",
        "acceptance_as_given": c1.pop("owner_acceptance"),
    }
    c1["owner_approved"] = False
    inc = c1["source_binding_incident"]
    inc["status"] = "CLOSED_SUPERSEDED"
    inc["ruling"] = ("OWNER_BLOCKER_CLEARANCE.md §O (O1), verbatim "
                     "'Supersede', SIGNED: BBrose (PROJECT_OWNER, via "
                     "Cowork question session), DATE: 2026-08-17 — "
                     "executed this session: canonical emission "
                     "4fb3541d… now on disk; as-picked bytes remain "
                     "reconstructible from the recipe above")
    record["acceptance_scope_note"] = (
        "The top-level owner_approved and owner_acceptance block cover the "
        "FIRST THREE emissions only (the §I-accepted 2026-08-15 set). "
        "Later emissions carry their own owner_approved flag: "
        "es3083_lid_A2.ai ACCEPTED per §K; fb3093_lid_C3.ai ACCEPTED per "
        "§N; fb3093_lid_C1.ai SUPERSEDED per §O (finalised emission, "
        "owner_approved false pending re-verification — verdict lands "
        "next round).")
    rec_path.write_text(json.dumps(record, indent=1, ensure_ascii=False)
                        + "\n")
    print(f"superseded: {ai_path.name} now {rec['bytes']}b "
          f"sha256 {rec['ai_sha256'][:16]} — validation PASS, "
          "incident CLOSED_SUPERSEDED")


if __name__ == "__main__":
    main()
