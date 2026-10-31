"""DIP-0C2a tests — capability-aware segmentation + the AssetCandidate schema.

Hermetic where possible (synthetic fixtures under a temp REPO_ROOT), plus a
read-only integration pass over the frozen C2 pilot. The load-bearing invariants:
capability-aware routing, collection-sheet splitting vs single-asset wholeness
(natural + 0-cluster fallback), JPEG-shell = one embedded raster, SVG safe/unsafe
handling, raster confidence states, EPS preview-derived-vs-unavailable with NO
geometry claims, deterministic ids, the five independent axes, no machine
APPROVED_REUSABLE, blank human blocks, and materials integrity.
"""
from __future__ import annotations

import io
import json
import struct

import fitz
import pytest
from PIL import Image, ImageDraw

from tools.dip0c import (
    assetcandidate as AC,
    config as C,
    run_c2a,
    segment,
)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "REPO_ROOT", tmp_path, raising=False)
    return tmp_path


def _write(root, name, data: bytes):
    (root / name).write_bytes(data)
    return name


def _src(rel, fmt, kind, sha="deadbeef"):
    return {"relative_path": rel, "sha256": sha, "format": fmt, "kind": kind}


# --- synthetic fixtures -----------------------------------------------------
def _jpeg_shell_pdf(root, name="shell.pdf"):
    Image.new("RGB", (300, 300), "orange").save(root / "_img.png")
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_image(page.rect, filename=str(root / "_img.png"))
    doc.save(root / name)
    doc.close()
    return name


def _empty_vector_pdf(root, name="empty.pdf"):
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_line((10, 10), (12, 12))          # one tiny path, no real cluster
    doc.save(root / name)
    doc.close()
    return name


def _clean_svg():
    return (b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" '
            b'viewBox="0 0 100 100"><g><path d="M0 0 L5 5"/></g></svg>')


def _multi_group_svg():
    return (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
            b'<g><rect width="5" height="5"/></g>'
            b'<g><circle r="3"/></g>'
            b'<g><path d="M1 1 L2 2"/></g></svg>')


def _script_svg():
    return (b'<svg xmlns="http://www.w3.org/2000/svg"><script>x()</script>'
            b'<rect onclick="y()"/></svg>')


def _raster_multi(root, name="multi.png"):
    im = Image.new("RGB", (400, 400), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([20, 20, 120, 120], fill="red")
    d.rectangle([260, 30, 360, 130], fill="blue")
    d.rectangle([150, 260, 250, 360], fill="green")
    im.save(root / name)
    return name


def _raster_full_bleed(root, name="fill.png"):
    # interior fills almost the whole frame and differs from the thin border, so
    # foreground coverage ~99% -> no usable fg/bg separation -> manual review
    im = Image.new("RGB", (300, 300), (200, 40, 40))
    ImageDraw.Draw(im).rectangle([0, 0, 299, 299], outline=(20, 200, 20), width=1)
    im.save(root / name)
    return name


def _eps_no_preview(root, name="np.eps"):
    ps = (b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 50 50\n"
          b"%%EndComments\nshowpage\n")
    _write(root, name, ps)
    return name


def _eps_decodable_preview(root, name="dp.eps"):
    buf = io.BytesIO()
    im = Image.new("RGB", (60, 60), "white")
    ImageDraw.Draw(im).rectangle([20, 20, 40, 40], fill="red")
    im.save(buf, "TIFF", compression="raw")     # uncompressed -> PIL-decodable
    tiff = buf.getvalue()
    ps = b"%!PS-Adobe-3.0 EPSF-3.0\n%%BoundingBox: 0 0 60 60\n%%EndComments\n"
    ps_off = 30
    tiff_off = ps_off + len(ps)
    hdr = (b"\xc5\xd0\xd3\xc6"
           + struct.pack("<IIIIII", ps_off, len(ps), 0, 0, tiff_off, len(tiff))
           + b"\xff\xff")
    _write(root, name, hdr + ps + tiff)
    return name


# --- routing ----------------------------------------------------------------
def test_routing_by_format(repo):
    _write(repo, "a.svg", _clean_svg())
    _eps_no_preview(repo, "a.eps")
    _raster_multi(repo, "a.png")
    _empty_vector_pdf(repo, "a.pdf")
    assert segment.segment_file(_src("a.svg", ".svg", "svg"), {})["candidates"]
    assert segment.segment_file(_src("a.eps", ".eps", "eps"), {})["candidates"]
    assert segment.segment_file(_src("a.png", ".png", "raster"), {})["candidates"]
    assert segment.segment_file(_src("a.pdf", ".pdf", "pdf_backed"), {})["candidates"]


# --- vector -----------------------------------------------------------------
def test_jpeg_shell_single_asset(repo):
    name = _jpeg_shell_pdf(repo)
    res = segment.segment_file(_src(name, ".pdf", "pdf_backed"), {})
    assert res["file_status"] == C.SEG_STATUS_WHOLE_FILE
    assert len(res["candidates"]) == 1
    c = res["candidates"][0]
    assert c["segmentation"]["method"] == C.SEG_METHOD_VECTOR_WHOLE_NATURAL
    assert "JPEG-shell" in " ".join(c["segmentation"]["evidence"])


def test_zero_cluster_whole_file_fallback(repo):
    name = _empty_vector_pdf(repo)
    res = segment.segment_file(_src(name, ".pdf", "pdf_backed"), {})
    assert len(res["candidates"]) == 1
    assert res["candidates"][0]["segmentation"]["method"] \
        == C.SEG_METHOD_VECTOR_WHOLE_FALLBACK
    assert res["file_status"] == C.SEG_STATUS_WHOLE_FILE


# --- SVG --------------------------------------------------------------------
def test_svg_multi_group_segments(repo):
    _write(repo, "m.svg", _multi_group_svg())
    res = segment.segment_file(_src("m.svg", ".svg", "svg"), {})
    assert res["file_status"] == C.SEG_STATUS_SEGMENTED
    assert len(res["candidates"]) == 3
    assert all(c["segmentation"]["method"] == C.SEG_METHOD_SVG
               for c in res["candidates"])


def test_svg_single_group_whole_file(repo):
    _write(repo, "s.svg", _clean_svg())
    res = segment.segment_file(_src("s.svg", ".svg", "svg"), {})
    assert res["file_status"] == C.SEG_STATUS_WHOLE_FILE
    assert len(res["candidates"]) == 1


def test_svg_unsafe_quarantined_not_segmented(repo):
    _write(repo, "evil.svg", _script_svg())
    res = segment.segment_file(_src("evil.svg", ".svg", "svg"), {})
    assert res["file_status"] == C.SEG_STATUS_UNAVAILABLE
    assert res["candidates"] == []


# --- raster -----------------------------------------------------------------
def test_raster_multi_region_is_low_confidence(repo):
    # multiple raster regions are only a PROPOSAL (could be one composition) ->
    # AUTO_LOW_CONFIDENCE, never a confident split
    name = _raster_multi(repo)
    res = segment.segment_file(_src(name, ".png", "raster"), {})
    assert res["file_status"] == C.SEG_STATUS_AUTO_LOW_CONF
    assert len(res["candidates"]) == 3
    assert all(c["segmentation"]["method"] == C.SEG_METHOD_RASTER
               for c in res["candidates"])


def test_raster_single_region_is_confident(repo):
    # one dominant subject on a clear background -> AUTO_CONFIDENT (the other
    # side of the boundary the slice draws)
    im = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(im).ellipse([120, 120, 280, 280], fill="red")
    im.save(repo / "one.png")
    res = segment.segment_file(_src("one.png", ".png", "raster"), {})
    assert res["file_status"] == C.SEG_STATUS_AUTO_CONFIDENT
    assert len(res["candidates"]) == 1


def test_raster_full_bleed_manual(repo):
    name = _raster_full_bleed(repo)
    res = segment.segment_file(_src(name, ".png", "raster"), {})
    assert res["file_status"] == C.SEG_STATUS_MANUAL
    assert res["candidates"][0]["segmentation"]["status"] == C.SEG_STATUS_MANUAL


# --- EPS --------------------------------------------------------------------
def test_eps_no_preview_unavailable_no_geometry(repo):
    name = _eps_no_preview(repo)
    res = segment.segment_file(_src(name, ".eps", "eps"), {})
    assert res["file_status"] == C.SEG_STATUS_UNAVAILABLE
    c = res["candidates"][0]
    assert c["segmentation"]["method"] == C.SEG_METHOD_NONE
    # NO geometry/editability claims anywhere on an EPS candidate
    forbidden = {"editability", "editability_score", "path_count",
                 "path_cleanliness", "anchor_count", "clip_structure",
                 "vector_raster_balance", "recolorability"}
    assert not (forbidden & set(c))
    assert not (forbidden & set(c.get("segmentation_detail", {})))


def test_eps_decodable_preview_is_preview_derived(repo):
    name = _eps_decodable_preview(repo)
    res = segment.segment_file(_src(name, ".eps", "eps"), {})
    assert res["file_status"] == C.SEG_STATUS_PREVIEW_DERIVED
    c = res["candidates"][0]
    assert c["segmentation"]["method"] == C.SEG_METHOD_EPS_PREVIEW
    assert c["segmentation"]["confidence"] <= segment.EPS_PREVIEW_CONF_CAP
    assert any("DO NOT correspond to editable EPS objects" in e
               for e in c["segmentation"]["evidence"])


# --- schema: deterministic ids + five axes ----------------------------------
def test_candidate_id_deterministic_bytes_and_config(repo):
    _raster_multi(repo, "det.png")
    r1 = segment.segment_file(_src("det.png", ".png", "raster", sha="abc"), {})
    r2 = segment.segment_file(_src("det.png", ".png", "raster", sha="abc"), {})
    ids1 = [c["candidate_id"] for c in r1["candidates"]]
    ids2 = [c["candidate_id"] for c in r2["candidates"]]
    assert ids1 == ids2                      # identical bytes + config -> identical
    assert len(set(ids1)) == len(ids1)       # unique within the file


def test_candidate_id_changes_with_config():
    a = AC.candidate_id("sha", C.SEG_METHOD_VECTOR, [0, 0, 10, 10], "cfgAAA", 0)
    b = AC.candidate_id("sha", C.SEG_METHOD_VECTOR, [0, 0, 10, 10], "cfgBBB", 0)
    assert a != b                            # config fingerprint folded into id


def test_five_axes_present_and_independent(repo):
    _write(repo, "x.svg", _clean_svg())
    c = segment.segment_file(_src("x.svg", ".svg", "svg"), {})["candidates"][0]
    assert c["A_technical_readiness"]["status"] == C.READY_UNSCORED
    assert c["A_technical_readiness"]["value"] is None
    b = c["B_rights_readiness"]
    assert b["ownership"] == "unconfirmed" and b["license"] == "unverified"
    assert not any(b[k] for k in ("commercial_use", "modification", "embedding",
                                  "redistribution"))
    assert c["C_reuse_posture_candidate"]["value"] is None
    assert c["D_retrieval_eligibility"] is False
    assert c["E_automatic_use_eligibility"] is False
    assert c["production_use"] is False


def test_no_approved_reusable_in_record(repo):
    _write(repo, "x.svg", _clean_svg())
    c = segment.segment_file(_src("x.svg", ".svg", "svg"), {})["candidates"][0]
    assert C.POSTURE_APPROVED_REUSABLE not in json.dumps(c)


def test_human_block_blank(repo):
    _write(repo, "x.svg", _clean_svg())
    c = segment.segment_file(_src("x.svg", ".svg", "svg"), {})["candidates"][0]
    assert c["human"]["category"] is None and c["human"]["reviewed_by"] is None


def test_collection_membership_has_manual_actions(repo):
    name = _raster_multi(repo)
    res = segment.segment_file(_src(name, ".png", "raster"), {})
    coll = res["candidates"][0]["collection"]
    assert coll and coll["is_member"]
    assert set(coll["manual_actions_allowed"]) == {"split", "merge", "relabel",
                                                   "exclude"}


# --- manifest determinism ---------------------------------------------------
def test_frozen_manifest_loads_deterministically():
    a = C.load_c2_pilot()
    b = C.load_c2_pilot()
    assert a == b and len(a) == 20
    req = {"relative_path", "inventory_category_original", "c1_participation",
           "c2_test_role", "format", "difficulty",
           "expected_segmentation_capability", "expected_family_relationship",
           "ownership_licensing_risk", "selection_rationale"}
    for e in a:
        assert req <= set(e)


def test_review_manifest_shape_and_caveats(repo):
    # the human-facing review JSON: a vector sheet is a confident split; a
    # multi-region raster lands in the low-confidence bucket WITH a caveat and is
    # never presented as a confirmed collection.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    for cx in (60, 200, 340):
        for cy in (60, 200, 340):
            page.draw_rect(fitz.Rect(cx - 20, cy - 20, cx + 20, cy + 20),
                           fill=(0.1, 0.2, 0.9))
    doc.save(repo / "sheet.pdf")
    doc.close()
    _raster_multi(repo, "rmulti.png")
    r_vec = run_c2a.segment_entry(
        {"relative_path": "sheet.pdf", "format": ".pdf",
         "c2_test_role": "vec_sheet"}, {})
    r_ras = run_c2a.segment_entry(
        {"relative_path": "rmulti.png", "format": ".png",
         "c2_test_role": "ras_multi"}, {})
    rev = run_c2a.build_review_manifest([r_vec, r_ras])
    ras = [s for s in rev["low_confidence_multi_region"]
           if s["parent_source"] == "rmulti.png"]
    assert ras and "caveat" in ras[0]
    # a low-confidence raster is NOT in the confident bucket
    assert all(s["parent_source"] != "rmulti.png"
               for s in rev["confident_collection_splits"])
    assert all(s["human_decision"] is None
               for s in rev["confident_collection_splits"]
               + rev["low_confidence_multi_region"])


# --- integration: real pilot, read-only -------------------------------------
def test_full_pilot_runs_and_materials_unchanged():
    rc = run_c2a.main()
    assert rc == 0
    recon = json.loads((C.OUT_REPORTS / "c2a_reconciliation.json")
                       .read_text(encoding="utf-8"))
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["integrity"]["no_output_under_source"]["ok"] is True
    assert all(recon["invariants"].values())
    # every frozen expectation matches the actual run
    assert recon["expected_vs_actual"]["all_match"] is True
    # confident collections are VECTOR splits (true geometry); the vector sticker
    # sheet is one
    assert recon["confident_collection_splits"].get("9347862.ai", 0) > 1
    # raster multi-region is only a proposal -> low confidence, NOT a confident
    # collection: neither the fluid background nor the rendered raster sheet is
    # presented as a confirmed sticker sheet
    assert "SL-041222-49680-07.jpg" not in recon["confident_collection_splits"]
    assert "5955566.jpg" not in recon["confident_collection_splits"]
    # multi-artboard file is tracked separately, not as a collection sheet
    assert "344195-PC2FZA-950.ai" in recon["multi_artboard_files"]
    # every real EPS preview is undecodable here -> UNAVAILABLE, none preview-derived
    assert recon["eps_preview_derived"] == 0
    assert recon["eps_unavailable"] >= 4
