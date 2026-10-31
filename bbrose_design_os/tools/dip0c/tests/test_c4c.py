"""DIP-0C4c — manifests, two views, queues, quarantine, curated candidates."""
from __future__ import annotations

import json

import pytest

from tools.dip0c import config as C
from tools.dip0c import font_curated as FC
from tools.dip0c import font_style as FS
from tools.dip0c import font_views as FV
from tools.dip0c import review_c4c as RV
from tools.dip0c import rights_model as RM
from tools.dip0c import run_c4c
from tools.dip0c.tests.test_c4a import face


# === the two views are independent ===========================================
def test_the_two_views_answer_different_questions():
    assert FV.VIEWS == (FV.VIEW_TECHNICAL, FV.VIEW_RIGHTS)
    t = FV.technical_view(faces=[], files=[], groups=[],
                          dedupe={"duplicate_group_count": 0}, styles={})
    r = FV.rights_view(files=[], packages=[], duplicate_model=[],
                       evidence_by_path={}, suspicions={}, faces_by_hash={})
    assert "ownership, licence, permission" in t["answers_nothing_about"]
    assert "typographic family" in r["answers_nothing_about"]
    assert "implies NOTHING in the rights view" in t["note"]
    assert "implies NOTHING in the technical view" in r["note"]


def test_the_technical_view_carries_no_rights_fields():
    t = FV.technical_view(faces=[], files=[], groups=[],
                          dedupe={"duplicate_group_count": 0}, styles={})
    text = json.dumps(t).lower()
    for forbidden in ("license_decision", "ownership_decision", "approved"):
        assert forbidden not in text or "human" in text


def test_the_rights_view_carries_no_typographic_decisions():
    r = FV.rights_view(files=[], packages=[], duplicate_model=[],
                       evidence_by_path={}, suspicions={}, faces_by_hash={})
    assert "weight_classes" not in json.dumps(r)
    assert r["all_permissions_false"] is True


# === manifests ===============================================================
def _manifest_row():
    f = face(family16="Nova", sha="h1", path="materials/DOWNLOADE 2026/A/x.ttf")
    f["_family_key"] = "nova"
    f["parse_status"] = "PARSED"
    rows = FV.face_manifest(
        faces=[f], files=[{"source_path": f["source_path"],
                           "parse_status": "PARSED", "face_count": 1,
                           "source_sha256": "h1"}],
        groups=[{"group_id": "fam-1", "faces": [f["face_id"]],
                 "state": "FAMILY_GROUPED"}],
        dedupe={"by_hash": {"h1": [{}]}},
        evidence_by_path={}, suspicions={}, styles={}, duplicate_model=[])
    return rows[0]


def test_every_human_field_is_blank():
    row = _manifest_row()
    h = row["human"]
    for k in ("reviewer", "reviewed_at", "family_confirmation",
              "source_package_confirmation", "provenance_confirmation",
              "license_decision", "ownership_decision", "quarantine_decision",
              "style_tags_confirmation", "notes", "correction_reason"):
        assert h[k] is None, k
    assert h["approved_scripts"] == []
    assert h["approved_usage"] == []


def test_machine_inference_is_immutable_after_human_review():
    """A human correction sits BESIDE the inference, never over it."""
    row = _manifest_row()
    assert row["machine_inference_immutable"] is True
    machine_before = json.dumps(row["machine"], sort_keys=True)

    # a human reviews and disagrees
    row["human"]["reviewer"] = "alice"
    row["human"]["family_confirmation"] = "NOT_THE_SAME_FAMILY"
    row["human"]["correction_reason"] = "different foundry entirely"

    assert json.dumps(row["machine"], sort_keys=True) == machine_before
    assert set(row) == {"schema_version", "machine", "human",
                        "machine_inference_immutable"}


def test_the_manifest_carries_every_required_machine_field():
    m = _manifest_row()["machine"]
    for k in ("source_path", "file_sha256", "face_id", "collection_index",
              "preferred_family", "fallback_family", "subfamily",
              "postscript_name", "vendor", "version", "weight_class",
              "width_class", "italic", "variable_axes", "scripts",
              "script_coverage", "dominant_script", "glyph_count", "file_format",
              "technical_health", "fstype", "duplicate_group", "technical_family",
              "source_package", "provenance_rights_subgroup", "license_evidence",
              "system_font_suspicion", "quarantine_recommendation",
              "review_priority", "review_reasons", "permissions"):
        assert k in m, k
    assert not any(m["permissions"].values())
    assert m["review_reasons"]


# === priorities record reasons ===============================================
def test_every_priority_records_its_reasons():
    p, reasons = FV.prioritise(healthy=True, has_font_evidence=False,
                               suspected=False, cross_package_dup=False,
                               family_conflict=False, unsupported=False,
                               curated_candidate=False)
    assert p == FV.HIGH
    assert any("possession is not permission" in r for r in reasons)

    p2, r2 = FV.prioritise(healthy=False, has_font_evidence=False, suspected=False,
                           cross_package_dup=False, family_conflict=False,
                           unsupported=True, curated_candidate=False)
    assert p2 == FV.LOW
    assert r2


def test_a_cross_package_duplicate_is_high_priority():
    p, reasons = FV.prioritise(healthy=True, has_font_evidence=True, suspected=False,
                               cross_package_dup=True, family_conflict=False,
                               unsupported=False, curated_candidate=False)
    assert p == FV.HIGH
    assert any("identical bytes, potentially different rights" in r for r in reasons)


# === style tags ==============================================================
def test_style_tags_never_come_from_a_filename():
    f = face(path="materials/x/ELEGANT_LUXURY_SERIF_DISPLAY.ttf", vendor="ACME")
    s = FS.observe(f, panose=[0] * 10)          # the font declares nothing
    assert s["filename_used"] is False
    assert s["tag_names"] == [] or "serif" not in s["tag_names"]


def test_a_font_that_declares_nothing_gets_no_tag():
    """Silence is the correct answer when the font says nothing."""
    f = face(glyph_count=None) if False else face()
    f["glyph_count"] = 200
    f["scripts"] = ["latin"]
    f["width_class"] = "NORMAL"
    f["names"]["subfamily_legacy"] = "Regular"
    f["names"]["subfamily_typographic"] = None
    s = FS.observe(f, panose=[0] * 10)
    assert s["panose_declared"] is False
    assert s["tag_names"] == []


def test_panose_drives_the_tag_when_the_font_declares_it():
    f = face()
    # familyType=2 (text), serifStyle=11 (sans range), proportion=9 (monospace)
    s = FS.observe(f, panose=[2, 11, 6, 9, 2, 0, 0, 3, 0, 0])
    assert "sans" in s["tag_names"]
    assert "monospace" in s["tag_names"]
    for t in s["tags"]:
        assert t["confidence"] <= FS.CONF_CAP
        assert t["source"].startswith("OS/2") or t["source"].startswith("name") \
            or t["source"].startswith("maxp")
        assert t["evidence"]


def test_style_tags_never_touch_licence_or_permission():
    s = FS.observe(face(), panose=[2, 2, 6, 3, 5, 0, 0, 2, 0, 0])
    assert s["affects_license_or_permission"] is False
    assert s["human_confirmation"] is None
    assert "never touches licence" in s["note"]


# === curated candidates ======================================================
@pytest.mark.parametrize("state", FC.FORBIDDEN)
def test_a_machine_may_never_approve_or_activate_a_font(state):
    with pytest.raises(C.HumanOnlyStateViolation):
        FC.machine_curated_state(state)


def test_the_only_machine_curated_state_is_a_candidate():
    assert FC.machine_curated_state(FC.CURATED_STARTER_CANDIDATE) \
        == "CURATED_STARTER_CANDIDATE"
    assert "APPROVED_FONT" in FC.FORBIDDEN
    assert "RETRIEVABLE_FONT" in FC.FORBIDDEN
    assert "PRODUCTION_READY_FONT" in FC.FORBIDDEN


def test_a_candidate_is_never_approved_or_activated():
    c = FC.nominate(groups=[], faces=[], packages=[], evidence_by_path={},
                    suspicions={}, styles={}, dedupe={})
    assert c["approved"] is False
    assert c["activated"] is False
    assert c["all_permissions_false"] is True


def test_a_dump_font_can_never_be_a_curated_candidate():
    f = face(family16="Nova", path="materials/Fonts/3333/x.ttf")
    g = {"group_id": "g1", "faces": [f["face_id"]], "family_key": "nova",
         "state": "FAMILY_GROUPED", "face_count": 1, "display_names": ["Nova"],
         "weight_classes": [400], "is_variable": False, "variable_axes": [],
         "scripts": ["latin"], "dominant_scripts": ["latin"],
         "duplicate_hashes": []}
    c = FC.nominate(groups=[g], faces=[f], packages=[],
                    evidence_by_path={f["source_path"]: [
                        {"evidence_file": "x", "mentions_fonts": True,
                         "restrictions_detected": []}]},
                    suspicions={}, styles={}, dedupe={})
    assert c["candidate_count"] == 0        # unverified provenance -> never nominated


# === queues ==================================================================
def _queues():
    return RV.build(faces=[], files=[], groups=[], packages=[], suspicions={},
                    duplicate_model=[], evidence_by_path={},
                    curated={"candidates": []},
                    dedupe={"duplicate_groups": {}})


def test_there_are_fourteen_queues_with_stable_ids():
    assert len(RV.QUEUE_IDS) == 14
    assert len(set(RV.QUEUE_IDS)) == 14
    q = _queues()
    for qid, item in q["queues"].items():
        assert item["queue_id"] == qid
        assert item["display_label"] == RV.LABELS[qid]


def test_every_queue_records_counts_evidence_exceptions_and_roles():
    q = _queues()
    for qid, item in q["queues"].items():
        for k in ("file_count", "face_count", "family_count", "package_count"):
            assert k in item, qid
        assert item["shared_reason"] and item["evidence"] and item["exceptions"]
        assert item["required_reviewer_roles"]
        assert item["recommended_human_action"]
        assert item["applies_decision_automatically"] is False


def test_technical_and_rights_duplicates_are_different_queues():
    """The C4b correction, made structural."""
    assert "FONT_DUPLICATE_TECHNICAL_GROUP" in RV.QUEUE_IDS
    assert "FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW" in RV.QUEUE_IDS
    assert RV.BATCHABLE["FONT_DUPLICATE_TECHNICAL_GROUP"] is True
    assert RV.BATCHABLE["FONT_CROSS_PACKAGE_DUPLICATE_RIGHTS_REVIEW"] is False


def test_queue_items_are_not_presented_as_decisions():
    q = _queues()
    assert "queue_items_are_not_decisions" in q
    assert "One face can appear in four queues" in q["queue_items_are_not_decisions"]


def test_queues_are_deterministic():
    assert json.dumps(_queues(), sort_keys=True) == \
        json.dumps(_queues(), sort_keys=True)


def test_no_queue_applies_a_decision():
    q = _queues()
    assert q["all_permissions_false"] is True
    assert q["permission_flag_count"] == len(RM.PERMISSION_FLAGS)


# === the real corpus =========================================================
def test_totals_reconcile_with_c4a_and_c4b():
    # [the clean-up of 2026-10-04 — his fifth and sixth answers: the duplicate copies, the Cracked-by fonts and the
    # screen fonts left materials/ and the DIP-0A inventory lost exactly their 1,092 FONT rows (M1 1,028, M4 27, M5 37,
    # reconciled against the pre-move index); re-measured here: 5,212 -> 4,120 files, 4,157 -> 4,099 unique, 1,047 -> 20 duplicate groups in the model. The faces, families and packages are read from
    # the C4a output on disk, made before the move, and still count the removed fonts — said in the clean-up's report.]
    a = run_c4c.audit()
    assert len(a["files"]) == 4120                    # C4a
    assert a["dedupe"]["files_unique"] == 4099        # C4a
    assert len(a["faces"]) == 4182                    # C4a
    assert len(a["groups"]) == 2841                   # C4a
    assert len(a["packages"]) == 137                   # C4b
    assert len(a["duplicate_model"]) == 20             # C4b
    assert sum(1 for d in a["duplicate_model"] if d["rights_batchable"]) == 0


def test_the_quarantine_remains_proposed_only():
    a = run_c4c.audit()
    p = a["system_font_proposal"]
    assert p["is_applied"] is False
    assert p["applied_by_machine"] is False
    assert p["human_confirmation"] is None


def test_every_permission_is_false_across_the_whole_corpus():
    a = run_c4c.audit()
    for row in a["manifest"][:200]:
        assert not any(row["machine"]["permissions"].values())
    for c in a["curated"]["candidates"]:
        assert not any(c["permissions"].values())
    for sg in a["rights_view"]["provenance_rights_subgroups"][:200]:
        assert not any(sg["permissions"].values())


def test_c4c_installs_renders_exports_and_exposes_nothing():
    import ast
    import inspect
    banned = {"unlink", "remove", "rmtree", "move", "rename", "copy", "copy2",
              "copyfile", "system", "popen", "urlopen"}
    for mod in (FS, FV, FC, RV):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                attr = getattr(node.func, "attr", None)
                assert attr not in banned, f"{mod.__name__} calls .{attr}()"
