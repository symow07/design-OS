"""§BH26(a) — the owner-grant channel, measured.

The channel is NOT the seam: these tests prove the grant confers on exactly
the two sha256-named faces, that both fail-closed legs actually close, and
that the machine ceilings did not move to make any of it possible.
"""
from __future__ import annotations

import copy

import pytest

from apps.ire import container_font_authority as cfa
from apps.ire import container_font_owner_grant as cfg
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _doc():
    bb = build_backbone(ContainerProfile(archetype="bottle", height_mm=110,
                                         width_mm=40))
    zones = cc.propose_zones(cc.build_inferred_profile("bottle"))
    return compose_container_graph(bb, product_name="Rose Nectar",
                                   name_lines=["Rose Nectar"], zones=zones,
                                   native=True)


def _legacy_doc():
    """§BH48(a): the untagged copy of the composition — the surface is lifted and draws the theme's
    Poppins pair, so the §BH26 channel's two Noto faces draw only where a document resolves as at
    41604ac: an untagged one, or the chains' last fallback. The channel's mechanics are proved here."""
    from apps.ire.font_roles import SURFACE_KEY
    doc = _doc()
    doc.metadata = {k: v for k, v in (doc.metadata or {}).items() if k != SURFACE_KEY}
    return doc


def test_on_the_lifted_container_surface_the_theme_faces_draw_and_carry_their_own_grants():
    """§BH48(a): the live composition is no longer the Noto pair's surface — the theme's Poppins
    Light and Regular draw, their states come from their own §BH30 grants, and the §BH26 grant
    names two faces that do not draw here and confers nothing on these."""
    auth = cfg.apply_owner_grant(cfa.build_font_authority(_doc()))
    shas = {f["sha256"] for f in auth["faces"]}
    assert shas == {"650ba57fa99d12ec40c31ccfb680be656be4497fbe14164617d67e32ffe9cd46",   # Poppins-Light
                    "7e65201e9b79159e2300267cc885e16c8dcef2424cdfa09a29bfb0980a94a7ba"}   # Poppins-Regular
    assert not shas & set(cfg.OWNER_GRANT_BH26["face_sha256s"])
    for f in auth["faces"]:
        assert f["verification"] == cfa.VERIFIED_FOR_PRODUCTION
        assert f["source"] == cfa.SOURCE_USER_CONFIRMED
        assert f["approved_by"] == "BBrose"
    assert auth["all_production_verified"] is True


def test_the_grant_confers_on_exactly_the_two_named_faces():
    auth = cfa.build_font_authority(_legacy_doc())
    before = copy.deepcopy(auth)
    granted = cfg.apply_owner_grant(auth)
    # the input is never mutated
    assert auth == before
    faces = granted["faces"]
    assert faces and {f["sha256"] for f in faces} == set(
        cfg.OWNER_GRANT_BH26["face_sha256s"])
    for f in faces:
        assert f["verification"] == cfa.VERIFIED_FOR_PRODUCTION
        assert f["source"] == cfa.SOURCE_USER_CONFIRMED
        assert f["is_fallback"] is False
        assert f["licence_id"] == "OFL-1.1"
        assert f["licence_evidence"].endswith(
            "sha256:" + cfg.OWNER_GRANT_BH26["licence_evidence_sha256"])
        assert "static/fonts/OFL.txt" in f["licence_evidence"]
        assert f["redistribution_status"] == "GRANTED"
        assert f["production_use_status"] == "GRANTED"
        assert f["approved_by"] == "BBrose"
        assert f["approved_at"] == "2026-09-01"
    # the gate clears for these faces — and the flag is measured, not forced
    codes = cfa.font_confirmation_gate(granted)
    assert "CONTAINER_FONT_CONFIRMATION_REQUIRED" not in codes
    assert "CONTAINER_FONT_LICENSE_REVIEW_REQUIRED" not in codes
    assert "CONTAINER_FONT_FALLBACK_DETECTED" not in codes
    assert granted["all_production_verified"] is True


def test_evidence_hash_mismatch_voids_the_grant_never_an_error_shaped_pass():
    auth = cfa.build_font_authority(_legacy_doc())
    bad = dict(cfg.OWNER_GRANT_BH26, licence_evidence_sha256="0" * 64)
    granted = cfg.apply_owner_grant(auth, grant=bad)   # no exception
    for f in granted["faces"]:
        assert f["verification"] == cfa.LICENCE_REVIEW_REQUIRED
        # nothing conferred on the VOID path: no claim, no source flip
        assert f["source"] != cfa.SOURCE_USER_CONFIRMED
        assert f["licence_id"] == ""
        assert f["licence_evidence"] == ""
        assert f["is_fallback"] is True
    codes = cfa.font_confirmation_gate(granted)
    assert "CONTAINER_FONT_LICENSE_REVIEW_REQUIRED" in codes
    assert granted["all_production_verified"] is False


def test_unreadable_evidence_is_the_same_void(tmp_path):
    auth = cfa.build_font_authority(_legacy_doc())
    gone = dict(cfg.OWNER_GRANT_BH26,
                licence_evidence_path=str(tmp_path / "no-such-licence.txt"))
    granted = cfg.apply_owner_grant(auth, grant=gone)
    assert all(f["verification"] == cfa.LICENCE_REVIEW_REQUIRED
               for f in granted["faces"])
    assert granted["all_production_verified"] is False


def test_a_third_sha256_gets_nothing_from_the_channel():
    third = {"role": "regular", "sha256": "ab" * 32,
             "verification": cfa.UNVERIFIED,
             "source": cfa.SOURCE_PLACEHOLDER_FALLBACK,
             "is_fallback": True, "licence_id": "", "licence_evidence": ""}
    auth = {"schema_version": cfa.SCHEMA, "faces": [dict(third)],
            "outlined_text_present": False, "all_production_verified": False}
    granted = cfg.apply_owner_grant(auth)
    assert granted["faces"] == [third]          # untouched, field for field
    assert granted["all_production_verified"] is False
    # and on the VOID path too: a third sha stays a third sha
    bad = dict(cfg.OWNER_GRANT_BH26, licence_evidence_sha256="0" * 64)
    voided = cfg.apply_owner_grant(auth, grant=bad)
    assert voided["faces"] == [third]


def test_a_malformed_grant_applies_to_nothing():
    auth = cfa.build_font_authority(_doc())
    for missing in cfg._REQUIRED_FIELDS:
        broken = {k: v for k, v in cfg.OWNER_GRANT_BH26.items()
                  if k != missing}
        granted = cfg.apply_owner_grant(auth, grant=broken)
        assert granted["faces"] == auth["faces"]


def test_the_machine_guards_still_refuse_and_the_seam_is_not_the_channel():
    """§BH26 hard stop 1, measured as a pin: honoring the grant required NO
    change to either guard's refusal behavior and no ceiling move."""
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa.machine_writable_verification(cfa.VERIFIED_FOR_PRODUCTION)
    with pytest.raises(cfa.FontStateAboveCeiling):
        cfa.machine_writable_source(cfa.SOURCE_USER_CONFIRMED)
    # the seam still refuses a typed-in production claim
    assert cfa.VERIFIED_FOR_PRODUCTION in cfa.SEAM_REFUSED_VERIFICATIONS


# ---- §BH30(d): the open-set grants. Every assertion below measures the corpus bytes;
# nothing is asserted from memory.

def _brand_faces():
    from pathlib import Path
    import json
    root = Path(cfg.__file__).resolve().parents[2] / "static" / "fonts" / "brand2026"
    prov = json.loads((root / "PROVENANCE.json").read_text())
    for folder, e in prov["families"].items():
        for f in e["files"]:
            if f["file"].endswith((".ttf", ".otf")):
                yield root / folder / f["file"], f["sha256"], root / folder / f["licence_file"]


def test_every_bh30_grant_row_describes_bytes_that_exist_and_hash_as_pinned():
    import hashlib
    from pathlib import Path
    seen = set()
    # [2026-10-02: the font set he granted, its own tuple of rows like §BH30's] every grant tuple of brand faces is read
    # [his goal after the pitch page, 2026-10-15, A (1)] and the serif, condensed and geometric faces granted then
    for g in (cfg.OWNER_GRANTS_BH30 + cfg.OWNER_GRANTS_2026_10_02 + cfg.OWNER_GRANTS_2026_10_15
              + cfg.OWNER_GRANTS_2026_10_15_CONDENSED + cfg.OWNER_GRANTS_2026_10_16_SLAB):
        for k in cfg._REQUIRED_FIELDS:
            assert g.get(k)
        p = Path(g["licence_evidence_path"])
        assert p.exists()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == g["licence_evidence_sha256"]
        assert g["licence_id"] in ("SIL Open Font License, Version 1.1", "Apache License, Version 2.0")
        assert len(g["face_sha256s"]) == 1  # §BH30(d): one grant row per face keyed by sha256
        for sha in g["face_sha256s"]:
            assert sha not in seen          # no sha256 appears in two grants
            seen.add(sha)
    on_disk = {sha for _, sha, _ in _brand_faces()}
    assert seen == on_disk                  # the grants name exactly the corpus faces, all of them


def test_no_bh30_grant_names_the_noto_pair_and_the_noto_grant_is_untouched():
    noto = set(cfg.OWNER_GRANT_BH26["face_sha256s"])
    for g in (cfg.OWNER_GRANTS_BH30 + cfg.OWNER_GRANTS_2026_10_02 + cfg.OWNER_GRANTS_2026_10_15
              + cfg.OWNER_GRANTS_2026_10_15_CONDENSED + cfg.OWNER_GRANTS_2026_10_16_SLAB):
        assert not (noto & set(g["face_sha256s"]))
    assert cfg.OWNER_GRANTS[0] is cfg.OWNER_GRANT_BH26
    assert cfg.OWNER_GRANT_BH26["granted_at"] == "2026-09-01"


def test_a_brand_face_record_is_conferred_through_the_channel_and_pinned_to_its_licence():
    path, sha, lic = next(_brand_faces())
    rec = cfa._face_record(role="regular", name="x", path=str(path), confirmed=None)
    out = cfg.apply_owner_grant({"schema_version": cfa.SCHEMA, "faces": [rec], "outlined_text_present": False, "all_production_verified": False})
    f = out["faces"][0]
    assert f["verification"] == cfa.VERIFIED_FOR_PRODUCTION
    assert f["source"] == cfa.SOURCE_USER_CONFIRMED
    assert f["is_fallback"] is False
    assert f["approved_by"] == "BBrose"
    assert f["licence_evidence"].startswith(str(lic))
    assert out["all_production_verified"] is True


def test_a_void_bh30_grant_voids_only_its_own_faces_and_confers_nothing():
    path, sha, lic = next(_brand_faces())
    rec = cfa._face_record(role="regular", name="x", path=str(path), confirmed=None)
    grants = tuple(dict(g, licence_evidence_sha256="0" * 64) if sha in g["face_sha256s"] else g
                   for g in cfg.OWNER_GRANTS)
    out = cfg.apply_owner_grant({"schema_version": cfa.SCHEMA, "faces": [rec], "outlined_text_present": False, "all_production_verified": False}, grants=grants)
    f = out["faces"][0]
    assert f["verification"] == cfa.LICENCE_REVIEW_REQUIRED   # the VOID path, a machine value
    assert f["source"] != cfa.SOURCE_USER_CONFIRMED
    assert f["licence_id"] == ""
    # the Noto pair, whose grant was not voided, still confers
    noto = cfg.apply_owner_grant(cfa.build_font_authority(_legacy_doc()), grants=grants)
    assert {x["sha256"] for x in noto["faces"]} == set(cfg.OWNER_GRANT_BH26["face_sha256s"])  # the harness resolved the pair
    assert all(x["verification"] == cfa.VERIFIED_FOR_PRODUCTION for x in noto["faces"])


def test_an_unknown_sha256_gets_nothing_from_any_bh30_grant():
    rec = cfa._face_record(role="regular", name="x", path=__file__, confirmed=None)  # a real file, not a face
    out = cfg.apply_owner_grant({"schema_version": cfa.SCHEMA, "faces": [rec], "outlined_text_present": False, "all_production_verified": False})
    assert out["faces"][0] == rec


# ---- §BH32(c): the Noto Naskh Arabic grant — the sticker path's Arabic face enters governance.

def test_the_naskh_grant_names_exactly_the_sticker_arabic_face_and_pins_the_read_licence():
    import hashlib
    from pathlib import Path
    g = cfg.OWNER_GRANT_NASKH
    for k in cfg._REQUIRED_FIELDS:
        assert g.get(k)
    assert g["licence_id"] == "OFL-1.1"
    root = Path(cfg.__file__).resolve().parents[2] / "static" / "fonts"
    face = root / "NotoNaskhArabic-Regular.ttf"
    assert face.exists()
    assert g["face_sha256s"] == (hashlib.sha256(face.read_bytes()).hexdigest(),)
    evidence = Path(g["licence_evidence_path"])
    assert evidence == root / "OFL.txt"                       # the file the owner read at §BH25
    assert hashlib.sha256(evidence.read_bytes()).hexdigest() == g["licence_evidence_sha256"]
    assert g["licence_evidence_sha256"] == cfg.OWNER_GRANT_BH26["licence_evidence_sha256"]
    # the face is named by this grant alone
    others = [x for x in cfg.OWNER_GRANTS if x is not g]
    assert all(g["face_sha256s"][0] not in x["face_sha256s"] for x in others)
    assert cfg.OWNER_GRANTS[0] is cfg.OWNER_GRANT_BH26 and cfg.OWNER_GRANTS[1] is g


def test_the_naskh_face_is_conferred_through_the_channel():
    from pathlib import Path
    face = Path(cfg.__file__).resolve().parents[2] / "static" / "fonts" / "NotoNaskhArabic-Regular.ttf"
    rec = cfa._face_record(role="arabic", name="NotoNaskhArabic", path=str(face), confirmed=None)
    out = cfg.apply_owner_grant({"schema_version": cfa.SCHEMA, "faces": [rec], "outlined_text_present": False, "all_production_verified": False})
    f = out["faces"][0]
    assert f["verification"] == cfa.VERIFIED_FOR_PRODUCTION
    assert f["source"] == cfa.SOURCE_USER_CONFIRMED
    assert f["is_fallback"] is False
    assert f["approved_by"] == "BBrose"
    assert f["licence_evidence"].startswith(str(face.parent / "OFL.txt"))
    assert out["all_production_verified"] is True


def test_a_void_naskh_grant_voids_only_the_naskh_face_and_the_pair_still_confers():
    from pathlib import Path
    face = Path(cfg.__file__).resolve().parents[2] / "static" / "fonts" / "NotoNaskhArabic-Regular.ttf"
    rec = cfa._face_record(role="arabic", name="NotoNaskhArabic", path=str(face), confirmed=None)
    grants = tuple(dict(g, licence_evidence_sha256="0" * 64) if g is cfg.OWNER_GRANT_NASKH else g
                   for g in cfg.OWNER_GRANTS)
    out = cfg.apply_owner_grant({"schema_version": cfa.SCHEMA, "faces": [rec], "outlined_text_present": False, "all_production_verified": False}, grants=grants)
    f = out["faces"][0]
    assert f["verification"] == cfa.LICENCE_REVIEW_REQUIRED
    assert f["source"] != cfa.SOURCE_USER_CONFIRMED
    noto = cfg.apply_owner_grant(cfa.build_font_authority(_legacy_doc()), grants=grants)
    assert all(x["verification"] == cfa.VERIFIED_FOR_PRODUCTION for x in noto["faces"])


# ---- §BH37(1): the materials twin of the font ceiling — the two tiers, the guard, the channel.

def _tier_rows():
    return [{"relative_path": "materials/x/b.jpg", "sha256": "b" * 64},
            {"relative_path": "materials/x/a.jpg", "sha256": "a" * 64},
            {"relative_path": "materials/y/c.psd", "sha256": "c" * 64}]


def _material_grant(tmp_path, *, evidence_text=b"You are free to use this image\n", pinned_sha=None, shas=("a" * 64,), condition=""):
    import hashlib
    from apps.ire import materials_owner_grant as MG
    ev = tmp_path / "License free.txt"
    ev.write_bytes(evidence_text)
    return {"schema_version": MG.SCHEMA, "granted_by": "BBrose", "granted_at": "2026-09-05",
            "terms_class": "ATTRIBUTION-REQUIRED", "evidence_path": str(ev),
            "evidence_sha256": pinned_sha or hashlib.sha256(evidence_text).hexdigest(),
            "file_sha256s": tuple(shas), "condition": condition}


def test_materials_tiers_are_two_and_the_ceiling_partitions_them_by_substance():
    from apps.ire import materials_authority as MA
    assert MA.TIER_CEILING == {MA.TIER_PRODUCTION: MA.ABOVE_CEILING, MA.TIER_REFERENCE: MA.AT_OR_BELOW_CEILING}
    assert MA.MACHINE_WRITABLE_TIERS == (MA.TIER_REFERENCE,)
    assert MA.MACHINE_FORBIDDEN_TIERS == (MA.TIER_PRODUCTION,)
    # the two constants are flat strings that name themselves, the house idiom
    assert MA.TIER_REFERENCE == "REFERENCE" and MA.TIER_PRODUCTION == "PRODUCTION"


def test_the_machine_guard_refuses_production_and_an_unknown_tier_distinctly():
    import pytest
    from apps.ire import materials_authority as MA
    assert MA.machine_writable_tier(MA.TIER_REFERENCE) == MA.TIER_REFERENCE
    with pytest.raises(MA.MaterialTierAboveCeiling):        # a grant-shaped write
        MA.machine_writable_tier(MA.TIER_PRODUCTION)
    with pytest.raises(ValueError):                          # not a tier at all
        MA.machine_writable_tier("EMBEDDABLE")
    assert not issubclass(MA.MaterialTierAboveCeiling, ValueError)


def test_the_machine_record_is_reference_everywhere_ordered_by_path():
    from apps.ire import materials_authority as MA
    rec = MA.build_tier_record(_tier_rows())
    assert rec["schema_version"] == MA.SCHEMA
    assert [r["relative_path"] for r in rec["rows"]] == ["materials/x/a.jpg", "materials/x/b.jpg", "materials/y/c.psd"]
    assert {r["tier"] for r in rec["rows"]} == {MA.TIER_REFERENCE}
    assert {r["tier_source"] for r in rec["rows"]} == {MA.TIER_SOURCE_MACHINE}
    assert all(r["evidence"] == "" and r["condition"] == "" for r in rec["rows"])
    assert rec["all_machine_rows_reference"] is True
    assert MA.tier_counts(rec)["by_tier"] == {MA.TIER_REFERENCE: 3}


def test_the_channel_landed_empty_at_bh37_1_and_carries_the_bh37_4_grants():
    from apps.ire import materials_owner_grant as MG
    # (1) landed MATERIAL_GRANTS == () at 2463f29; (4) filled it as a single-use authority, spent on that landing
    assert isinstance(MG.MATERIAL_GRANTS, tuple) and MG.MATERIAL_GRANTS
    assert all(isinstance(g, dict) and all(g.get(k) for k in MG._REQUIRED_FIELDS) for g in MG.MATERIAL_GRANTS)


def test_a_grant_with_matching_evidence_raises_the_named_file_to_production_with_its_credit(tmp_path):
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    grant = _material_grant(tmp_path, condition='Designed by Freepik')
    before = MA.build_tier_record(_tier_rows())
    after = MG.apply_material_grants(before, grants=(grant,))
    by = {r["relative_path"]: r for r in after["rows"]}
    a = by["materials/x/a.jpg"]
    assert a["tier"] == MA.TIER_PRODUCTION and a["tier_source"] == MA.TIER_SOURCE_OWNER_GRANT
    assert a["condition"] == "Designed by Freepik"                 # verbatim, carried
    assert a["evidence"] == f'{grant["evidence_path"]} sha256:{grant["evidence_sha256"]}'
    assert a["terms_class"] == "ATTRIBUTION-REQUIRED" and a["granted_by"] == "BBrose"
    # the other rows are untouched REFERENCE; the input record was not mutated
    assert by["materials/x/b.jpg"]["tier"] == MA.TIER_REFERENCE and by["materials/y/c.psd"]["tier"] == MA.TIER_REFERENCE
    assert {r["tier"] for r in before["rows"]} == {MA.TIER_REFERENCE}
    assert [r["relative_path"] for r in MG.production_rows(after)] == ["materials/x/a.jpg"]


def test_negative_control_evidence_hash_mismatch_leaves_reference_and_records_the_void(tmp_path):
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    grant = _material_grant(tmp_path, pinned_sha="0" * 64)      # the text on disk does not hash to the pin
    after = MG.apply_material_grants(MA.build_tier_record(_tier_rows()), grants=(grant,))
    a = next(r for r in after["rows"] if r["relative_path"] == "materials/x/a.jpg")
    assert a["tier"] == MA.TIER_REFERENCE and a["tier_source"] == MA.TIER_SOURCE_MACHINE
    assert a["evidence"] == "" and a["condition"] == ""
    assert "grant_void" in a and "0" * 64 in a["grant_void"]      # visible, never silent
    assert MG.production_rows(after) == []


def test_negative_control_an_unknown_sha256_is_left_exactly_as_the_machine_wrote_it(tmp_path):
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    grant = _material_grant(tmp_path, shas=("f" * 64,))          # names a file that is not in the record
    before = MA.build_tier_record(_tier_rows())
    after = MG.apply_material_grants(before, grants=(grant,))
    assert after["rows"] == before["rows"]
    assert MG.production_rows(after) == []


def test_a_missing_evidence_file_and_a_malformed_grant_confer_nothing(tmp_path):
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    grant = _material_grant(tmp_path)
    (tmp_path / "License free.txt").unlink()                       # the evidence is gone
    after = MG.apply_material_grants(MA.build_tier_record(_tier_rows()), grants=(grant,))
    a = next(r for r in after["rows"] if r["relative_path"] == "materials/x/a.jpg")
    assert a["tier"] == MA.TIER_REFERENCE and "unreadable" in a["grant_void"]
    malformed = {k: v for k, v in _material_grant(tmp_path).items() if k != "evidence_sha256"}
    after2 = MG.apply_material_grants(MA.build_tier_record(_tier_rows()), grants=(malformed,))
    assert {r["tier"] for r in after2["rows"]} == {MA.TIER_REFERENCE}


def test_the_font_module_is_untouched_by_the_materials_twin():
    """§BH37(1): 'Protected regions of the font module untouched' — the materials
    modules import from nothing but materials_authority; the font ceiling's own
    partition is the one the font tests pin."""
    import apps.ire.materials_owner_grant as MG
    import apps.ire.materials_authority as MA
    from apps.ire import container_font_authority as cfa
    assert "container_font_authority" not in MG.__doc__.split("apps.ire.")[-1]
    assert cfa.MACHINE_FORBIDDEN_VERIFICATIONS == (cfa.VERIFIED_FOR_PRODUCTION, cfa.APPROVED_FOR_CONCEPT_ONLY)
    assert MA.MACHINE_FORBIDDEN_TIERS == (MA.TIER_PRODUCTION,)


# ---- §BH37(4): TIERS ASSIGNED — every admitted row REFERENCE by machine; the PRODUCTION grants through the channel.

import json as _json
import os as _os
from pathlib import Path as _Path

_OUTER = _Path(__file__).resolve().parents[4]
_SUMMARY = _OUTER / "docs" / "design_intelligence" / "dip0a" / "materials_tiers_summary.json"
_RECORD = _OUTER / "var" / "design_intelligence" / "audits" / "dip0" / "tiers" / "materials_tiers.jsonl"


def _tier_rows_on_disk():
    import pytest
    if not _RECORD.exists():
        pytest.skip("materials tier record not present (var/ audit output)")
    return [_json.loads(l) for l in _RECORD.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_the_grant_rows_are_one_per_file_keyed_by_sha256_and_evidence_pinned():
    from apps.ire import materials_owner_grant as MG
    assert MG.MATERIAL_GRANTS                                   # §BH37(4): the authority spent
    pairs = [(s, p) for g in MG.MATERIAL_GRANTS for s, p in zip(g["file_sha256s"], g["paths"])]
    assert sorted(set(pairs)) == sorted(pairs)                  # no (sha256, path) pair named twice
    for g in MG.MATERIAL_GRANTS:
        if g["terms_class"] == "OWNER_DECLARATION":                                  # §BH39(c): the scope is the declared pack
            pack = "/".join(g["paths"][0].split("/")[:4]) + "/"                     # materials/<drop>/Telegram Desktop/<pack>/
            assert g["paths"] and all(p.startswith(pack) for p in g["paths"])
            continue
        assert g["paths"] and all(_os.path.dirname(p) == _os.path.dirname(g["evidence_path"]) or _os.path.dirname(p).startswith(_os.path.dirname(g["evidence_path"]) + "/") for p in g["paths"])   # the scope is the pack the text sits beside
    for g in MG.MATERIAL_GRANTS:
        assert g["terms_class"] in ("PERMISSIVE", "ATTRIBUTION-REQUIRED", "OWNER_DECLARATION")   # §BH39(c): the owner's declaration
        assert g["granted_by"] == "BBrose" and g["granted_at"] in ("2026-09-05", "2026-09-08")     # §BH37(4) / §BH39(c)
        assert MG._measured_evidence_sha256(g) == g["evidence_sha256"]     # the text beside the pack, re-hashed
        if g["terms_class"] == "ATTRIBUTION-REQUIRED":
            assert "Designed by" in g["condition"]                         # the credit, verbatim
        else:
            assert g["condition"] == ""


def test_the_tier_record_is_reference_by_machine_and_production_only_through_the_channel():
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    rows = _tier_rows_on_disk()
    summary = _json.loads(_SUMMARY.read_text(encoding="utf-8"))
    assert summary["rows"] == sum(1 for _ in rows)
    machine = [r for r in rows if r["tier_source"] == MA.TIER_SOURCE_MACHINE]
    assert {r["tier"] for r in machine} == {MA.TIER_REFERENCE}            # the machine wrote nothing above the ceiling
    prod = [r for r in rows if r["tier"] == MA.TIER_PRODUCTION]
    assert prod and all(r["tier_source"] == MA.TIER_SOURCE_OWNER_GRANT for r in prod)
    assert all(r["evidence"] and "sha256:" in r["evidence"] for r in prod)  # no PRODUCTION row without evidence
    granted = {(s, p) for g in MG.MATERIAL_GRANTS for s, p in zip(g["file_sha256s"], g["paths"])}
    assert {(r["sha256"], r["relative_path"]) for r in prod} <= granted        # in scope, by sha256 AND path
    # a byte-identical copy outside its pack (ADOBE STOCK's EDUME packs hold the same Freepik texts) stays REFERENCE
    same_sha_outside = [r for r in rows if r["tier"] == MA.TIER_REFERENCE and any(r["sha256"] == s for s, _ in granted) and (r["sha256"], r["relative_path"]) not in granted]
    assert same_sha_outside and all(r["tier_source"] == MA.TIER_SOURCE_MACHINE for r in same_sha_outside)
    assert summary["production_rows"] == sum(1 for _ in prod)
    assert summary["by_tier"] == {MA.TIER_REFERENCE: sum(1 for r in rows if r["tier"] == MA.TIER_REFERENCE), MA.TIER_PRODUCTION: sum(1 for _ in prod)}


def test_the_channel_scope_keeps_a_named_sha256_out_of_another_pack(tmp_path):
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    g = _material_grant(tmp_path, shas=("a" * 64,), condition="Designed by Freepik")
    g["paths"] = ("materials/x/a.jpg",)                                   # the pack the text sits beside
    rows = _tier_rows() + [{"relative_path": "materials/ADOBE STOCK/copy/a.jpg", "sha256": "a" * 64}]
    after = MG.apply_material_grants(MA.build_tier_record(rows), grants=(g,))
    by = {r["relative_path"]: r["tier"] for r in after["rows"]}
    assert by["materials/x/a.jpg"] == MA.TIER_PRODUCTION
    assert by["materials/ADOBE STOCK/copy/a.jpg"] == MA.TIER_REFERENCE     # same bytes, out of scope


def test_no_font_file_and_no_adobe_stock_row_is_production():
    from apps.ire import materials_authority as MA
    rows = _tier_rows_on_disk()
    assert all(r["tier"] == MA.TIER_REFERENCE for r in rows if r["relative_path"].startswith("materials/ADOBE STOCK/"))
    fonts = [r for r in rows if r["relative_path"].lower().endswith((".ttf", ".otf", ".ttc", ".woff", ".woff2", ".eot", ".pfb", ".pfa"))]
    assert fonts and all(r["tier"] == MA.TIER_REFERENCE for r in fonts)


def test_every_production_row_re_verifies_its_evidence_now():
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    rows = _tier_rows_on_disk()
    prod = [r for r in rows if r["tier"] == MA.TIER_PRODUCTION]
    for r in prod:
        path, _, pinned = r["evidence"].partition(" sha256:")
        assert MA.sha256_of_file(str(_OUTER / path)) == pinned
    # re-applying the channel to the machine record reproduces exactly these rows
    machine = MA.build_tier_record([{"relative_path": r["relative_path"], "sha256": r["sha256"]} for r in rows])
    again = MG.apply_material_grants(machine)
    assert sorted(r["relative_path"] for r in MG.production_rows(again)) == sorted(r["relative_path"] for r in prod)
    assert {r["condition"] for r in prod if r["condition"]} == {r["condition"] for r in MG.production_rows(again) if r["condition"]}


# ---- §BH38 riding ruling: the terms and read-me texts of the granted packs return to REFERENCE — evidence governs assets,
# ---- it is not an asset. One negative control; the (4) tests above stand unchanged.

def _inventory_category_by_path():
    inv = _OUTER / "var" / "design_intelligence" / "audits" / "dip0" / "inventory" / "inventory.jsonl"
    import pytest
    if not inv.exists():
        pytest.skip("DIP-0A inventory not present (var/ audit output)")
    out = {}
    for line in inv.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = _json.loads(line)
        c = r.get("category")
        out[r["relative_path"]] = c.get("value") if isinstance(c, dict) else c
        if r.get("original_source_path"):            # Day 6 migration: the tier record and grants name the original spelling
            out[r["original_source_path"]] = out[r["relative_path"]]
    return out


def test_no_terms_or_read_me_text_is_a_production_row_and_no_grant_names_one():
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    category = _inventory_category_by_path()
    rows = _tier_rows_on_disk()
    prod = [r for r in rows if r["tier"] == MA.TIER_PRODUCTION]
    assert prod
    assert all(category.get(r["relative_path"]) != "LICENSE_EVIDENCE" for r in prod)       # evidence is not an asset
    for g in MG.MATERIAL_GRANTS:
        assert g["paths"]                                                                   # a grant naming no file is nothing
        assert all(category.get(p) != "LICENSE_EVIDENCE" for p in g["paths"])
        if g["terms_class"] == "OWNER_DECLARATION":
            assert g["evidence_path"].startswith("docs/design_intelligence/dip0a/")            # §BH39(c): the declaration record
        else:
            assert category.get(g["evidence_path"]) in ("LICENSE_EVIDENCE", "PRODUCT_REFERENCE")   # the pin stays a text
    texts = [r for r in rows if category.get(r["relative_path"]) == "LICENSE_EVIDENCE"]
    assert texts and all(r["tier"] == MA.TIER_REFERENCE for r in texts)                     # every text REFERENCE by machine


# ---- §BH39(c): OWN WORK — PRODUCTION BY OWNER DECLARATION. The evidence is a tracked declaration record (path + sha256,
# ---- re-hashed on every application) quoting the §BH39 register line and carrying each pack's sha256 set.

_DECLARATION = _OUTER / "docs" / "design_intelligence" / "dip0a" / "own_work_declaration_bh39.json"


def test_every_owner_declaration_grant_pins_the_tracked_declaration_that_names_its_files():
    from apps.ire import materials_owner_grant as MG
    decl = _json.loads(_DECLARATION.read_text(encoding="utf-8"))
    assert decl["schema_version"] == "own_work_declaration/1.0"
    assert "I am the rights holder of my company's own work packs" in decl["register"]["line_verbatim"]
    assert decl["register"]["block"] == "§BH39" and decl["register"]["commit"]
    own = [g for g in MG.MATERIAL_GRANTS if g["terms_class"] == "OWNER_DECLARATION"]
    assert own
    by_pack = {p["pack"]: p for p in decl["packs"]}
    for g in own:
        assert g["evidence_path"] == "docs/design_intelligence/dip0a/own_work_declaration_bh39.json"
        assert MG._measured_evidence_sha256(g) == g["evidence_sha256"]                 # the record, re-hashed now
        assert g["condition"] == "" and g["granted_at"] == "2026-09-08"
        pack = next(p for p in by_pack if all(x.startswith(p + "/") for x in g["paths"]))
        named = {(f["path"], f["sha256"]) for f in by_pack[pack]["sha256_set"]}
        assert set(zip(g["paths"], g["file_sha256s"])) == named                         # one row per file, exactly the set
        for w in by_pack[pack]["withheld"]:
            assert w not in g["paths"]                                                  # the third-party-signalled file stays out


def test_own_work_rows_measure_production_with_the_declaration_as_evidence():
    from apps.ire import materials_authority as MA
    rows = _tier_rows_on_disk()
    own = [r for r in rows if r.get("terms_class") == "OWNER_DECLARATION"]
    assert own and all(r["tier"] == MA.TIER_PRODUCTION and r["tier_source"] == MA.TIER_SOURCE_OWNER_GRANT for r in own)
    assert all(r["evidence"].startswith("docs/design_intelligence/dip0a/own_work_declaration_bh39.json sha256:") for r in own)
    assert all(not r["condition"] for r in own)
    withheld = [r for r in rows if r["relative_path"].endswith("FACE WASH FOAM/بخاخ تيوب 2.psd")]
    assert withheld and withheld[0]["tier"] == MA.TIER_REFERENCE                        # Freepik's by its own XMP: not own work


# ---- §BH39(d): the evidence file itself is never a granted row — the Coolvetica EULA returned to REFERENCE.

def test_no_grant_names_its_own_evidence_file_and_no_production_row_is_an_evidence_file():
    from apps.ire import materials_authority as MA
    from apps.ire import materials_owner_grant as MG
    evidence = {g["evidence_path"] for g in MG.MATERIAL_GRANTS}
    for g in MG.MATERIAL_GRANTS:
        assert g["evidence_path"] not in g["paths"]
    rows = _tier_rows_on_disk()
    for r in rows:
        if r["relative_path"] in evidence:
            assert r["tier"] == MA.TIER_REFERENCE
    eula = [r for r in rows if r["relative_path"].endswith("Typodermic Desktop EULA 2023.pdf")]
    assert eula and eula[0]["tier"] == MA.TIER_REFERENCE


def test_his_goal_of_2026_10_06_item_6_the_naskh_bold_is_granted_from_google_fonts_with_its_licence_and_provenance():
    """His goal of 2026-10-06, item 6: "Approve Noto Naskh Arabic Bold (SIL OFL, from google/fonts, licence and
    provenance recorded) for Arabic headings; no outline bolding." The face is google/fonts' variable Naskh at its wght
    700 instance; its OFL is committed beside it and pinned by hash; its provenance record names the repository, the
    commit, the source file's hash and how the instance was made; his grant names exactly its bytes; it confers
    VERIFIED_FOR_PRODUCTION through the channel; the Arabic heading role reaches it first."""
    import hashlib
    import json
    from pathlib import Path

    from apps.ire.font_roles import CHAINS, resolve_role
    root = Path(cfg.__file__).resolve().parents[2]
    prov = json.loads((root / "docs" / "fonts" / "NotoNaskhArabic-Bold.provenance.json").read_text())
    face, licence = root / prov["file"], root / prov["licence"]["file"]
    g = cfg.OWNER_GRANT_NASKH_BOLD
    assert g in cfg.OWNER_GRANTS and g["granted_by"] == "BBrose" and g["granted_at"] == "2026-10-06"
    assert g["face_sha256s"] == (hashlib.sha256(face.read_bytes()).hexdigest(),) == (prov["file_sha256"],)
    assert Path(g["licence_evidence_path"]) == licence
    assert hashlib.sha256(licence.read_bytes()).hexdigest() == g["licence_evidence_sha256"] == prov["licence"]["sha256"]
    assert "SIL OPEN FONT LICENSE VERSION 1.1" in " ".join(licence.read_text().upper().split())
    assert prov["source"]["repository"] == "https://github.com/google/fonts"
    assert prov["source"]["path"] == "ofl/notonaskharabic/NotoNaskhArabic[wght].ttf" and len(prov["source"]["commit"]) == 40
    others = [x for x in cfg.OWNER_GRANTS if x is not g]
    assert all(g["face_sha256s"][0] not in x["face_sha256s"] for x in others)
    rec = cfa._face_record(role="arabic-heading", name="NotoNaskhArabic-Bold", path=str(face), confirmed=None)
    out = cfg.apply_owner_grant({"schema_version": cfa.SCHEMA, "faces": [rec], "outlined_text_present": False,
                                 "all_production_verified": False})
    assert out["faces"][0]["verification"] == cfa.VERIFIED_FOR_PRODUCTION and out["faces"][0]["approved_by"] == "BBrose"
    assert CHAINS["arabic-heading"][0] == "NotoNaskhArabic-Bold"
    assert resolve_role("arabic-heading")["stem"] == "NotoNaskhArabic-Bold"
    # it carries every presentation form the shaping path draws, as the Regular does
    from fontTools.ttLib import TTFont
    cmap = TTFont(str(face)).getBestCmap()
    regular = TTFont(str(root / "static" / "fonts" / "NotoNaskhArabic-Regular.ttf")).getBestCmap()
    forms = [c for c in range(0xFB50, 0xFF00) if c in regular]
    assert forms and all(c in cmap for c in forms)
