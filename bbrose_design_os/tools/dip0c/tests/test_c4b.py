"""DIP-0C4b — system-font suspicion, packages, licence evidence, quarantine, queues."""
from __future__ import annotations

import json

import pytest

from tools.dip0c import config as C
from tools.dip0c import font_packages as FP
from tools.dip0c import font_provenance as FPV
from tools.dip0c import font_rights as FR
from tools.dip0c import review_c4 as RV
from tools.dip0c import rights_model as RM
from tools.dip0c.tests.test_c4a import face


def ms_face(**kw):
    kw.setdefault("vendor", "MS")
    f = face(**kw)
    f["names"]["copyright"] = "© 2018 Microsoft Corporation. All rights reserved."
    return f


# === suspicion comes from the NAME TABLE, never the filename ==================
def test_suspicion_comes_from_vendor_and_copyright_not_the_filename():
    s = FPV.assess(ms_face(path="materials/Fonts/3333/consola.ttf"))
    assert s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY
    assert s["foundries"] == ["Microsoft"]
    assert s["filename_used"] is False
    codes = {e["code"] for e in s["evidence"]}
    assert FPV.EV_OS_VENDOR_ID in codes
    assert FPV.EV_OS_COPYRIGHT in codes


def test_a_misleading_filename_does_not_trigger_suspicion():
    """My own first probe 'found' system fonts in 'Barista Script' and 'ALLOVER
    MODERN DEMO' by substring. Nothing here reads a filename."""
    for name in ("Barista Script.otf", "ALLOVER MODERN DEMO.otf",
                 "RemachineScript_Personal_Use.ttf", "microsoft-lookalike.ttf",
                 "arial-clone.ttf"):
        f = face(path=f"materials/Fonts/3333/{name}", vendor="ACME")
        s = FPV.assess(f)
        assert s["outcome"] == FPV.NO_SYSTEM_FONT_EVIDENCE, name
        assert s["confidence"] == 0.0
        assert s["filename_used"] is False


def test_folder_location_carries_zero_weight_and_changes_no_outcome():
    """A weight of 0.0 is not enough: mere PRESENCE in the evidence list must not
    push a face out of NO_SYSTEM_FONT_EVIDENCE. Location is context, and it moves
    nothing — 2,972 faces were briefly flagged for living in the wrong directory."""
    clean = face(vendor="ACME", path="materials/Fonts/3333/x.ttf")
    a = FPV.assess(clean, in_dump_folder=False)
    b = FPV.assess(clean, in_dump_folder=True)
    assert a["outcome"] == b["outcome"] == FPV.NO_SYSTEM_FONT_EVIDENCE
    assert a["confidence"] == b["confidence"] == 0.0
    assert FPV.WEIGHTS[FPV.EV_DUMP_FOLDER] == 0.0
    # ...but the context IS shown to the reviewer
    assert any(e["code"] == FPV.EV_DUMP_FOLDER for e in b["evidence"])


def test_microsoft_metadata_triggers_suspicion_but_never_legal_guilt():
    s = FPV.assess(ms_face())
    assert s["outcome"] == FPV.SUSPECTED_SYSTEM_FONT_COPY
    assert s["legal_conclusion"] is None
    assert s["human_confirmation"] is None
    assert "does NOT state that the font was copied illegally" in s["note"]
    assert s["confidence"] <= FPV.CONFIDENCE_CAP < 1.0     # never certainty


def test_a_vendor_id_alone_is_evidence_but_below_the_suspicion_threshold():
    f = face(vendor="MONO")                                # no copyright string
    s = FPV.assess(f)
    assert s["outcome"] == FPV.SYSTEM_FONT_EVIDENCE_PRESENT
    assert s["foundries"] == ["Monotype"]
    assert s["confidence"] < FPV.SUSPECT_THRESHOLD


def test_an_exact_duplicate_of_a_suspect_inherits_the_question_not_the_answer():
    f = face(vendor="ACME")
    s = FPV.assess(f, duplicate_of_suspect=True)
    assert s["outcome"] == FPV.SYSTEM_FONT_STATUS_UNCERTAIN
    assert any(e["code"] == FPV.EV_DUPLICATE_OF_SUSPECT for e in s["evidence"])


# === licence evidence: proximity is not relevance =============================
def test_a_stock_asset_licence_beside_a_font_does_not_govern_the_font():
    """`License free.txt` says 'this license only applies if you downloaded this
    VECTOR' — it is a stock-asset licence sitting next to a font."""
    text = ("IMPORTANT NOTICE: This license only applies if you downloaded this "
            "vector as an unsubscribed user. Premium user subscription applies.")
    cls = FP.classify_text("License free.txt", text)
    assert cls["license_type"] == FP.LIC_STOCK_ASSET
    assert cls["mentions_fonts"] is False
    assert cls["mentions_stock_assets"] is True
    assert FP.W_MAY_NOT_COVER_FONTS in cls["warnings"]


def test_evidence_that_never_mentions_fonts_has_its_confidence_cut():
    ev = [{"path": "materials/pkg/License free.txt", "filename": "License free.txt",
           "strength": "strong", "scope": "same_dir", "distance": 0}]
    rows = FP.associate({"relative_path": "materials/pkg/x.ttf"}, ev)
    r = rows[0]
    assert r["association_method"] == FP.ASSOC_SAME_DIR
    assert r["dip0a_strength"] == "strong"            # DIP-0A said strong...
    assert r["association_confidence"] < FP.CONF_SAME_DIR   # ...C4b disagrees


def test_an_ofl_is_recognised_and_still_grants_nothing():
    text = ("This Font Software is licensed under the SIL Open Font License, "
            "Version 1.1.")
    cls = FP.classify_text("OFL.txt", text)
    assert cls["license_type"] == FP.LIC_OFL
    assert cls["mentions_fonts"] is True

    ev = [{"path": "materials/pkg/OFL.txt", "filename": "OFL.txt",
           "strength": "strong", "scope": "same_dir", "distance": 0}]
    r = FP.associate({"relative_path": "materials/pkg/x.ttf"}, ev)[0]
    assert r["grants_permission"] is False
    assert r["review_status"] == "NOT_REVIEWED"
    assert "does NOT set LICENSE_APPROVED" in r["note"]


def test_restrictive_terms_are_detected():
    cls = FP.classify_text("readme.txt",
                           "This font is for personal use only. Not for commercial "
                           "use. A demo version.")
    assert cls["restrictions"]
    assert FP.W_RESTRICTIVE in cls["warnings"]


def test_unreadable_evidence_fails_closed():
    cls = FP.classify_text("x.txt", None)
    assert cls["license_type"] == FP.LIC_UNREADABLE
    assert FP.W_UNREADABLE in cls["warnings"]


# === packages ================================================================
def test_the_two_dump_folders_are_one_package_not_two():
    assert FP.classify_package("materials/Fonts") == FP.PKG_SUSPECTED_DUMP
    assert FP.classify_package("materials/Fonts/3333") == FP.PKG_SUSPECTED_DUMP
    files = [{"relative_path": "materials/Fonts/a.ttf", "sha256": "h1",
              "extension": ".ttf"},
             {"relative_path": "materials/Fonts/3333/a.ttf", "sha256": "h1",
              "extension": ".ttf"}]
    pkgs = FP.build_packages(files, {}, {})
    assert len(pkgs) == 1
    p = pkgs[0]
    assert p["package_kind"] == FP.PKG_SUSPECTED_DUMP
    assert p["is_credible_rights_batch"] is False
    assert sorted(p["package_roots"]) == ["materials/Fonts", "materials/Fonts/3333"]
    assert "NEITHER folder's evidence clears the other" in p["note"]


def test_one_packages_evidence_does_not_clear_another():
    files = [{"relative_path": "materials/DOWNLOADE 2026/A/a.ttf", "sha256": "h1",
              "extension": ".ttf"},
             {"relative_path": "materials/DOWNLOADE 2026/B/b.ttf", "sha256": "h2",
              "extension": ".ttf"}]
    ev = {"materials/DOWNLOADE 2026/A/a.ttf": [
        {"evidence_file": "materials/DOWNLOADE 2026/A/OFL.txt",
         "license_type": FP.LIC_OFL, "mentions_fonts": True,
         "restrictions_detected": [], "warnings": []}]}
    pkgs = {p["package_key"]: p for p in FP.build_packages(files, {}, ev)}
    a = pkgs["materials/DOWNLOADE 2026/A"]
    b = pkgs["materials/DOWNLOADE 2026/B"]
    assert a["has_license_evidence"] is True
    assert b["has_license_evidence"] is False          # B is NOT cleared by A
    assert b["license_evidence_files"] == []


def test_a_download_package_is_a_credible_rights_batch():
    assert FP.classify_package("materials/DOWNLOADE 2026/sinkin-sans") \
        == FP.PKG_DOWNLOAD_PACKAGE


def test_package_grouping_is_deterministic():
    files = [{"relative_path": f"materials/DOWNLOADE 2026/P/{n}.ttf",
              "sha256": f"h{n}", "extension": ".ttf"} for n in "abc"]
    assert FP.build_packages(files, {}, {}) == \
        FP.build_packages(list(reversed(files)), {}, {})


def test_the_dump_overlap_is_measured_not_assumed():
    files = ([{"relative_path": f"materials/Fonts/3333/{i}.ttf", "sha256": f"h{i}"}
              for i in range(10)]
             + [{"relative_path": f"materials/Fonts/{i}.ttf", "sha256": f"h{i}"}
                for i in range(9)])
    o = FP.dump_overlap(files)
    assert o["shared_hashes"] == 9
    assert o["overlap_pct_of_fonts"] == 100.0
    assert o["neither_clears_the_other"] is True


# === rights: machine may never approve =======================================
@pytest.mark.parametrize("state", FR.HUMAN_ONLY)
def test_a_machine_can_never_approve_clear_or_reject_a_font(state):
    with pytest.raises(C.HumanOnlyStateViolation):
        FR.machine_font_state(state)


def test_the_machine_allowed_states_are_all_questions():
    for s in FR.MACHINE_ALLOWED:
        assert FR.machine_font_state(s) == s
    assert "LICENSE_APPROVED" not in FR.MACHINE_ALLOWED
    assert "PERMANENTLY_REJECTED" not in FR.MACHINE_ALLOWED


def test_every_permission_is_false_and_the_count_is_not_hardcoded():
    p = FR.permissions()
    assert set(p) == set(RM.PERMISSION_FLAGS)
    assert not any(p.values())
    assert len(p) == len(RM.PERMISSION_FLAGS)


def test_a_suspected_system_batch_becomes_a_quarantine_candidate():
    f = ms_face()
    sus = {f["face_id"]: FPV.assess(f)}
    b = FR.assess_batch(batch_id="materials/Fonts[+3333]",
                        kind=FP.PKG_SUSPECTED_DUMP, faces=[f], files=[{}],
                        package=None, suspicions=sus)
    assert b["reuse_posture"] == FR.QUARANTINE_CANDIDATE
    assert b["ownership_status"] == "OWNERSHIP_UNCONFIRMED"
    assert b["license_status"] == "LICENSE_UNVERIFIED"
    assert not any(b["permissions"].values())
    assert b["machine_may_delete_or_reject"] is False
    assert b["source_files_moved_or_deleted"] == 0
    assert set(b["permitted_human_outcomes"]) == set(FR.PERMITTED_HUMAN_OUTCOMES)
    assert b["human_confirmation"] is None


def test_an_ofl_package_is_evidence_present_unreviewed_not_approved():
    f = face(vendor="pyrs")
    pkg = {"license_evidence": [
        {"evidence_file": "OFL.txt", "license_type": FP.LIC_OFL,
         "mentions_fonts": True, "restrictions_detected": [], "warnings": []}]}
    b = FR.assess_batch(batch_id="pkg", kind=FP.PKG_DOWNLOAD_PACKAGE,
                        faces=[f], files=[{}], package=pkg,
                        suspicions={f["face_id"]: FPV.assess(f)})
    assert b["reuse_posture"] == FR.EVIDENCE_PRESENT_UNREVIEWED
    assert not any(b["permissions"].values())         # STILL nothing granted
    assert b["license_status"] == "LICENSE_UNVERIFIED"


def test_evidence_that_does_not_mention_fonts_does_not_count_as_licence_evidence():
    f = face(vendor="ACME")
    pkg = {"license_evidence": [
        {"evidence_file": "License free.txt", "license_type": FP.LIC_STOCK_ASSET,
         "mentions_fonts": False, "restrictions_detected": [],
         "warnings": [FP.W_MAY_NOT_COVER_FONTS]}]}
    b = FR.assess_batch(batch_id="pkg", kind=FP.PKG_DOWNLOAD_PACKAGE,
                        faces=[f], files=[{}], package=pkg,
                        suspicions={f["face_id"]: FPV.assess(f)})
    assert b["reuse_posture"] != FR.EVIDENCE_PRESENT_UNREVIEWED
    assert b["license_evidence_mentioning_fonts"] == []
    assert any("NONE of it mentions fonts" in r for r in b["reasons"])


# === EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS ===============================
def _dedupe(groups: dict):
    return {"duplicate_groups": {h: [{"relative_path": p} for p in ps]
                                 for h, ps in groups.items()},
            "files_unique": 0, "files_in_duplicate_groups": 0,
            "duplicate_group_count": len(groups)}


OFL_EV = [{"evidence_file": "materials/DOWNLOADE 2026/A/OFL.txt",
           "mentions_fonts": True}]


def test_exact_duplicates_share_technical_metadata():
    dd = _dedupe({"h1": ["materials/DOWNLOADE 2026/A/x.ttf",
                         "materials/Fonts/3333/x.ttf"]})
    m = FR.duplicate_review_model(dd, {}, {"h1": [face(sha="h1")]})[0]
    t = m["technical_identity_group"]
    assert t["safe_as_one_decision"] is True
    assert t["scope"] == "TECHNICAL IDENTITY ONLY — not rights"
    assert "identical glyph structure" in t["shared_safely"]
    assert "identical fsType data" in t["shared_safely"]
    assert t["face_count"] == 1


def test_exact_duplicates_do_not_automatically_share_rights_status():
    """The same TTF bought under licence and scraped from elsewhere is byte-identical
    and legally nothing alike."""
    dd = _dedupe({"h1": ["materials/DOWNLOADE 2026/A/x.ttf",
                         "materials/Fonts/3333/x.ttf"]})
    m = FR.duplicate_review_model(
        dd, {"materials/DOWNLOADE 2026/A/x.ttf": OFL_EV})[0]
    assert m["rights_batchable"] is False
    assert m["rights_subgroup_count"] == 2
    assert "NOT identical rights" in m["rights_batch_reason"]
    assert "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS" in m["note"]


def test_cross_package_duplicates_remain_separate_rights_units():
    dd = _dedupe({"h1": ["materials/DOWNLOADE 2026/A/x.ttf",
                         "materials/DOWNLOADE 2026/B/x.ttf"]})
    m = FR.duplicate_review_model(
        dd, {"materials/DOWNLOADE 2026/A/x.ttf": OFL_EV})[0]
    assert m["rights_batchable"] is False
    kinds = {s["provenance_kind"] for s in m["provenance_rights_subgroups"]}
    assert kinds == {FR.PROV_KNOWN_PACKAGE, FR.PROV_KNOWN_NO_EVIDENCE}
    # package A has evidence; package B does NOT inherit it
    b = next(s for s in m["provenance_rights_subgroups"]
             if s["source_package"].endswith("/B"))
    assert b["license_evidence_mentioning_fonts"] == []
    assert b["rights_posture"] == FR.RIGHTS_REVIEW_REQUIRED


def test_same_package_duplicates_with_shared_evidence_may_be_batched():
    dd = _dedupe({"h1": ["materials/DOWNLOADE 2026/A/x.ttf",
                         "materials/DOWNLOADE 2026/A/y.ttf"]})
    ev = {"materials/DOWNLOADE 2026/A/x.ttf": OFL_EV,
          "materials/DOWNLOADE 2026/A/y.ttf": OFL_EV}
    m = FR.duplicate_review_model(dd, ev)[0]
    assert m["rights_batchable"] is True
    assert m["rights_subgroup_count"] == 1
    assert m["provenance_rights_subgroups"][0]["provenance_kind"] \
        == FR.PROV_KNOWN_PACKAGE
    assert "ONE credible package" in m["rights_batch_reason"]


def test_no_permission_propagates_through_a_hash_group():
    dd = _dedupe({"h1": ["materials/DOWNLOADE 2026/A/x.ttf",
                         "materials/Fonts/3333/x.ttf"]})
    m = FR.duplicate_review_model(
        dd, {"materials/DOWNLOADE 2026/A/x.ttf": OFL_EV})[0]
    for sg in m["provenance_rights_subgroups"]:
        assert not any(sg["permissions"].values())
        assert sg["human_confirmation"] is None
    # the dump copy is PROVENANCE_MISSING, not cleared by its licensed twin
    dump = next(s for s in m["provenance_rights_subgroups"]
                if s["provenance_kind"] == FR.PROV_UNVERIFIED_DUMP)
    assert dump["rights_posture"] == FR.PROVENANCE_MISSING
    assert dump["license_evidence_mentioning_fonts"] == []


def test_an_unverified_dump_copy_is_provenance_missing():
    dd = _dedupe({"h1": ["materials/Fonts/a.ttf", "materials/Fonts/3333/a.ttf"]})
    m = FR.duplicate_review_model(dd, {})[0]
    for sg in m["provenance_rights_subgroups"]:
        assert sg["provenance_kind"] == FR.PROV_UNVERIFIED_DUMP
        assert sg["rights_posture"] == FR.PROVENANCE_MISSING


# === fail-closed policy ======================================================
def test_the_fail_closed_policy_disables_every_axis():
    p = FR.FAIL_CLOSED_POLICY
    assert p["license_status"] == "LICENSE_UNVERIFIED"
    for k in ("retrieval_allowed", "automatic_use_allowed", "production_use_allowed",
              "embedding_allowed", "redistribution_allowed"):
        assert p[k] is False


def test_no_suspicion_is_never_read_as_safe():
    assert "not examined" in FR.NO_SUSPICION_IS_NOT_SAFETY
    assert "never 'cleared'" in FR.NO_SUSPICION_IS_NOT_SAFETY
    for s in (FR.RIGHTS_REVIEW_REQUIRED, FR.PROVENANCE_MISSING):
        assert FR.machine_font_state(s) == s          # both are machine-allowed


# === the system-font batch is a PROPOSAL =====================================
def test_the_system_font_batch_is_proposed_never_applied():
    f = ms_face()
    p = FR.system_font_batch_proposal(
        files=[{}, {}], faces=[f], suspicions={f["face_id"]: FPV.assess(f)},
        overlap={"shared_hashes": 933}, unparseable=[{}])
    assert p["is_applied"] is False
    assert p["applied_by_machine"] is False
    assert p["duplicate_overlap"]["shared_hashes"] == 933
    assert p["unsupported_fon_files"] == 1
    assert p["vendor_evidence"] and p["copyright_evidence"]
    assert p["known_exceptions"]
    assert "MATERIAL" in p["false_positive_risk"]
    assert not any(p["permissions"].values())
    assert p["human_confirmation"] is None


def test_the_curated_recommendation_does_not_activate_anything():
    r = FR.curated_library_recommendation(packages=[], evidence_fonts=72, faces=[])
    assert "CURATED" in r["strategy"]
    assert len(r["steps"]) == 6
    assert "not implemented" in r["activation_requires"]
    assert "must not become the active BBROSE font library" in r["archive_note"]


# === batch leverage ==========================================================
def test_the_only_safe_lever_is_scoped_to_TECHNICAL_identity():
    """The correction: duplicates are safe as ONE TECHNICAL decision, never as one
    RIGHTS decision."""
    lv = FR.batch_leverage(files=[], faces=[], groups=[], packages=[],
                           suspicions={},
                           dedupe={"files_unique": 0, "files_in_duplicate_groups": 0,
                                   "duplicate_group_count": 0})
    safe = [x for x in lv["levers"] if x["safe_as_one_decision"]]
    assert len(safe) == 1
    assert safe[0]["scope"] == "TECHNICAL IDENTITY ONLY"
    assert "TECHNICAL" in safe[0]["lever"]

    rights = next(x for x in lv["levers"] if x.get("scope") == "RIGHTS")
    assert rights["safe_as_one_decision"] is False
    assert "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS" in rights["exceptions"]
    assert "EXACT BYTES DO NOT PROVE IDENTICAL RIGHTS" in lv["note"]


def test_every_lever_records_its_exceptions():
    lv = FR.batch_leverage(files=[], faces=[], groups=[], packages=[], suspicions={},
                           dedupe={"files_unique": 0, "files_in_duplicate_groups": 0,
                                   "duplicate_group_count": 0})
    for x in lv["levers"]:
        assert x["exceptions"]
        assert x["shared_evidence"]


def test_a_family_from_two_packages_is_two_rights_units():
    a = face(family16="Nova", sha="h1", path="materials/DOWNLOADE 2026/A/a.ttf")
    b = face(family16="Nova", sha="h2", path="materials/DOWNLOADE 2026/B/b.ttf")
    a["_family_key"], b["_family_key"] = "nova", "nova"
    lv = FR.batch_leverage(files=[], faces=[a, b], groups=[], packages=[],
                           suspicions={},
                           dedupe={"files_unique": 0, "files_in_duplicate_groups": 0,
                                   "duplicate_group_count": 0})
    assert "nova" in lv["families_split_across_packages"]
    assert len(lv["families_split_across_packages"]["nova"]) == 2


# === queues ==================================================================
def _queues():
    f = ms_face(path="materials/Fonts/3333/consola.ttf")
    f["_family_key"] = "consolas"
    sus = {f["face_id"]: FPV.assess(f)}
    return RV.build(faces=[f], files=[], groups=[], packages=[],
                    suspicions=sus, batches=[],
                    dedupe={"duplicate_groups": {}, "files_unique": 1,
                            "files_in_duplicate_groups": 0,
                            "duplicate_group_count": 0})


def test_queue_ids_are_identity_and_letters_are_labels():
    q = _queues()
    assert len(RV.QUEUE_IDS) == 10
    assert len(set(RV.QUEUE_IDS)) == 10
    for qid, item in q["queues"].items():
        assert item["queue_id"] == qid
        assert item["display_label"] == RV.LABELS[qid]


def test_every_queue_records_evidence_exceptions_and_counts():
    q = _queues()
    for qid, item in q["queues"].items():
        assert item["shared_reason"], qid
        assert item["evidence"], qid
        assert item["exceptions"], qid
        assert item["recommended_human_action"], qid
        assert item["priority"] in (RV.CRITICAL, RV.HIGH, RV.MEDIUM, RV.LOW)
        assert item["applies_decision_automatically"] is False
        for k in ("item_count", "file_count", "face_count", "family_count"):
            assert k in item


def test_queues_are_deterministic():
    assert json.dumps(_queues(), sort_keys=True) == \
        json.dumps(_queues(), sort_keys=True)


def test_no_queue_applies_a_decision():
    q = _queues()
    assert q["all_permissions_false"] is True
    assert q["permission_flag_count"] == len(RM.PERMISSION_FLAGS)
    for item in q["queues"].values():
        assert item["applies_decision_automatically"] is False


# === the real corpus =========================================================
def test_the_real_corpus_suspicion_totals_hold():
    from tools.dip0c import run_c4b
    a = run_c4b.audit()
    from collections import Counter
    outcomes = Counter(s["outcome"] for s in a["suspicions"].values())
    assert outcomes[FPV.SUSPECTED_SYSTEM_FONT_COPY] == 706
    assert outcomes[FPV.SYSTEM_FONT_EVIDENCE_PRESENT] == 130
    # every suspicion is evidenced, capped, and legally silent
    for s in a["suspicions"].values():
        assert s["confidence"] <= FPV.CONFIDENCE_CAP
        assert s["legal_conclusion"] is None
        assert s["filename_used"] is False
    # no batch grants anything
    for b in a["batches"]:
        assert not any(b["permissions"].values())
        assert b["source_files_moved_or_deleted"] == 0


def test_c4b_moves_or_deletes_nothing():
    import ast
    import inspect
    banned = {"unlink", "remove", "rmtree", "move", "rename", "copy", "copy2",
              "copyfile", "system", "popen", "run"}
    for mod in (FPV, FP, FR, RV):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                attr = getattr(node.func, "attr", None)
                assert attr not in banned, f"{mod.__name__} calls .{attr}()"
