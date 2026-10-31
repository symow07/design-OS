"""DIP-0C2b tests — technical readiness, pattern, raster quality, watermark.

Axis A is scored here and NOTHING else. The load-bearing invariants: the readiness
vocabulary is canonical, EPS is never technically ready, unsafe SVG stays
quarantined, DPI metadata never rejects a high-resolution file, low resolution
alone never proves a watermark, a filename never decides a repeat verdict,
seamlessness confidence is capped, source and candidate verdicts stay independent
except for safety/tool blockers, results are deterministic, rights/retrieval stay
disabled, and materials are unchanged.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tools.dip0c import config as C
from tools.dip0c import pattern, quality, readiness, run_c2b, watermark


# --- tile fixtures ----------------------------------------------------------
def _seamless_tile(n=256):
    """Sinusoids with integer periods wrap exactly in both axes."""
    y, x = np.mgrid[0:n, 0:n]
    a = (128 + 60 * np.sin(2 * np.pi * 4 * x / n)
         + 60 * np.sin(2 * np.pi * 3 * y / n))
    return Image.fromarray(a.astype(np.uint8), "L").convert("RGB")


def _visible_seam_tile(n=256):
    """A left-to-right ramp: the left edge (0) cannot meet the right edge (255)."""
    y, x = np.mgrid[0:n, 0:n]
    a = (255 * x / (n - 1)) + 20 * np.sin(2 * np.pi * 5 * y / n)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L").convert("RGB")


def _half_drop_tile(n=256):
    """Sheared stripes: traversing the full width shifts phase by half a tile, so
    the wrap fails straight but succeeds when the neighbour is offset by 1/2."""
    y, x = np.mgrid[0:n, 0:n]
    phase = (y - (n / 2) * x / (n - 1)) % n
    a = 128 + 100 * np.sin(2 * np.pi * phase / n)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L").convert("RGB")


def _flat_margin_art(n=256):
    """Artwork floating in white space — its borders trivially 'wrap'."""
    im = Image.new("RGB", (n, n), "white")
    ImageDraw.Draw(im).ellipse([80, 80, 176, 176], fill="red")
    return im


# --- pattern ----------------------------------------------------------------
def test_seamless_tile_is_seamless_likely_and_capped():
    v = pattern.analyse(rel_path="tile.png", image=_seamless_tile())
    assert v["value"] == C.PAT_SEAMLESS_LIKELY
    assert v["confidence"] <= C.SEAMLESS_CONFIDENCE_CAP
    assert v["human_confirmed"] is None


def test_visible_seam_tile_is_non_seamless():
    v = pattern.analyse(rel_path="ramp.png", image=_visible_seam_tile())
    assert v["value"] == C.PAT_NON_SEAMLESS_LIKELY


def test_half_drop_is_repeat_type_uncertain():
    v = pattern.analyse(rel_path="brick.png", image=_half_drop_tile())
    assert v["value"] == C.PAT_REPEAT_TYPE_UNCERTAIN
    assert any("half-drop" in e or "1/2 offset" in e for e in v["evidence"])


def test_filename_never_decides_the_verdict():
    # named "seamless" but visibly seamed -> still NON_SEAMLESS_LIKELY
    v = pattern.analyse(rel_path="seamless-pattern-tile.jpg",
                        image=_visible_seam_tile())
    assert v["value"] == C.PAT_NON_SEAMLESS_LIKELY
    assert v["filename_hint"] is True
    assert v["filename_hint_is_decisive"] is False


def test_flat_margin_art_is_not_called_seamless():
    v = pattern.analyse(rel_path="logo.png", image=_flat_margin_art())
    assert v["value"] != C.PAT_SEAMLESS_LIKELY
    assert v["value"] == C.PAT_REPEAT_TYPE_UNCERTAIN


def test_eps_pattern_is_requires_tool():
    v = pattern.analyse(rel_path="a.eps", image=None, is_eps=True)
    assert v["value"] == C.PAT_REQUIRES_TOOL


def test_crop_from_sheet_is_not_given_a_tile_verdict():
    v = pattern.analyse(rel_path="sheet.jpg", image=_seamless_tile(), is_tile=False)
    assert v["value"] == C.PAT_REQUIRES_HUMAN


def test_transparent_edges_are_uncertain():
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([60, 60, 196, 196], fill=(255, 0, 0, 255))
    v = pattern.analyse(rel_path="cutout.png", image=im)
    assert v["value"] == C.PAT_REPEAT_TYPE_UNCERTAIN


# --- raster quality ---------------------------------------------------------
def test_high_res_with_absent_dpi_is_not_rejected():
    """THE rule: low/absent DPI metadata must never reject a high-res file."""
    q = quality.assess_raster(bbox_px=[0, 0, 8333, 8333],
                              source_facts={"dpi": None, "alpha": False})
    assert q["resolution_band"] == C.RES_HIGH_RES_CANDIDATE
    assert q["dpi_is_decisive"] is False
    assert "NOT used to judge quality" in q["dpi_note"]
    assert q["low_resolution_risk"] is False


def test_high_res_with_low_dpi_is_not_rejected():
    q = quality.assess_raster(bbox_px=[0, 0, 4000, 3000],
                              source_facts={"dpi": 72, "alpha": False})
    assert q["resolution_band"] == C.RES_HIGH_RES_CANDIDATE
    assert q["low_resolution_risk"] is False


def test_nothing_is_print_ready_from_pixels_alone():
    q = quality.assess_raster(bbox_px=[0, 0, 8333, 8333],
                              source_facts={"dpi": 300, "alpha": False})
    assert q["print_suitability"] == C.PRINT_SUITABILITY_UNDETERMINED
    assert "PRINT_READY" not in q["resolution_band"]


def test_low_resolution_raster_band():
    q = quality.assess_raster(bbox_px=[0, 0, 300, 300], source_facts={"dpi": 300})
    assert q["resolution_band"] == C.RES_TOO_LOW
    assert q["low_resolution_risk"] is True


def test_effective_resolution_uses_the_candidate_crop():
    # a small sticker cropped from a huge sheet is judged on the CROP
    q = quality.assess_raster(bbox_px=[100, 100, 450, 450],
                              source_facts={"dimensions": {"w": 8000, "h": 8000}})
    assert q["effective_resolution"]["long_edge"] == 350
    assert q["resolution_band"] == C.RES_TOO_LOW


def test_transparent_png_role_and_alpha():
    q = quality.assess_raster(bbox_px=[0, 0, 1500, 1500],
                              source_facts={"alpha": True})
    assert q["alpha"] is True
    assert q["role_guess"]["value"] == C.ROLE_ILLUSTRATION


# --- watermark --------------------------------------------------------------
def test_low_resolution_alone_is_never_a_watermark():
    """FALSE-WATERMARK case: small, clean, no stock signals -> NOT suspected."""
    im = Image.new("RGB", (300, 300), "white")
    ImageDraw.Draw(im).ellipse([100, 100, 200, 200], fill="blue")
    w = watermark.assess(rel_path="assets/my-logo.png", image=im, long_edge=300)
    assert w["value"] is False
    assert w["state"] == "NOT_SUSPECTED"
    assert any("contributes NOTHING" in e for e in w["evidence"])


def test_stock_provider_name_raises_suspicion():
    im = Image.new("RGB", (400, 400), "white")
    w = watermark.assess(rel_path="downloads/shutterstock_12345_preview.jpg",
                         image=im, long_edge=400)
    assert w["value"] is True
    assert w["state"] == "WATERMARK_SUSPECTED"
    assert w["human_confirmed"] is None          # machine never confirms
    assert w["tier"] == C.TIER_HEURISTIC


def test_watermark_is_never_stated_as_fact():
    im = Image.new("RGB", (400, 400), "white")
    w = watermark.assess(rel_path="istock_sample.jpg", image=im, long_edge=400)
    assert w["confidence"] < 1.0
    assert "never a statement of fact" in w["note"]


def test_clean_high_res_file_is_not_suspected():
    im = Image.new("RGB", (2400, 2400), "white")
    ImageDraw.Draw(im).rectangle([200, 200, 2200, 2200], fill="green")
    w = watermark.assess(rel_path="brand/hero.png", image=im, long_edge=2400)
    assert w["value"] is False


# --- readiness model --------------------------------------------------------
def _ev(code, blocking=False, tier=C.TIER_DIRECT, signal=None):
    return readiness.evidence(code, "detail", tier=tier, signal=signal,
                              blocking=blocking)


def test_clean_vector_candidate_is_technically_ready():
    a = readiness.assess([_ev(C.EV_EDITABLE_COLORS), _ev(C.EV_PATH_CLEANLINESS)])
    assert a["value"] == C.READY_TECHNICALLY_READY
    assert a["axis"] == "A_technical_only"


def test_high_complexity_vector_gets_caveats():
    a = readiness.assess([_ev(C.EV_EDITABLE_COLORS),
                          _ev(C.EV_COMPLEXITY, signal="caveat")])
    assert a["value"] == C.READY_TECHNICALLY_USABLE_WITH_CAVEATS


def test_jpeg_shell_candidate_needs_reconstruction():
    a = readiness.assess([_ev(C.EV_EMBEDDED_RASTER_DEPENDENCE, blocking=True)])
    assert a["value"] == C.READY_NEEDS_VECTOR_RECONSTRUCTION


def test_vector_with_embedded_raster_needs_cleanup():
    a = readiness.assess([_ev(C.EV_VECTOR_RASTER_BALANCE, blocking=True)])
    assert a["value"] == C.READY_NEEDS_CLEANUP


def test_low_resolution_raster_is_reference_only():
    a = readiness.assess([_ev(C.EV_RASTER_RESOLUTION, blocking=True)])
    assert a["value"] == C.READY_REFERENCE_ONLY


def test_watermark_suspicion_is_reference_only():
    a = readiness.assess([_ev(C.EV_WATERMARK_SUSPICION, blocking=True,
                              tier=C.TIER_HEURISTIC)])
    assert a["value"] == C.READY_REFERENCE_ONLY


def test_unsafe_svg_is_quarantined():
    a = readiness.assess([_ev(C.EV_UNSAFE_SVG, blocking=True)])
    assert a["value"] == C.READY_QUARANTINE


def test_corruption_is_rejected():
    a = readiness.assess([_ev(C.EV_CORRUPTION, blocking=True)])
    assert a["value"] == C.READY_REJECT_CANDIDATE


def test_eps_is_requires_tool_or_header_only_never_ready():
    blocked = readiness.assess(
        [_ev(C.EV_EPS_TOOL_LIMITATION, blocking=True, tier=C.TIER_REQUIRES_TOOL)])
    assert blocked["value"] == C.READY_REQUIRES_TOOL
    assert blocked["blocked_by_tool"] is True
    partial = readiness.assess(
        [_ev(C.EV_EPS_TOOL_LIMITATION, blocking=True, tier=C.TIER_REQUIRES_TOOL)],
        header_facts=True)
    assert partial["value"] == C.READY_HEADER_ONLY_PARTIAL
    for a in (blocked, partial):
        assert a["value"] != C.READY_TECHNICALLY_READY


def test_readiness_is_deterministic():
    ev = [_ev(C.EV_EDITABLE_COLORS), _ev(C.EV_COMPLEXITY, signal="caveat")]
    a, b = readiness.assess(list(ev)), readiness.assess(list(ev))
    assert a["value"] == b["value"]
    assert a["config_fingerprint"] == b["config_fingerprint"]


def test_readiness_never_emits_retired_vocabulary():
    a = readiness.assess([_ev(C.EV_EDITABLE_COLORS)])
    assert a["value"] in C.TECHNICAL_READINESS
    assert "READY_AFTER_RIGHTS_REVIEW" not in json.dumps(a)


# --- source vs candidate independence ---------------------------------------
def test_safety_and_tool_blockers_propagate_to_the_candidate():
    src = readiness.assess([_ev(C.EV_UNSAFE_SVG, blocking=True)])
    cand_ev = [_ev(C.EV_EDITABLE_COLORS)]
    cand = readiness.assess(cand_ev)
    assert cand["value"] == C.READY_TECHNICALLY_READY      # clean on its own
    merged = readiness.merge_source_blockers(cand, src, cand_ev)
    assert merged["value"] == C.READY_QUARANTINE           # but parent is unsafe


def test_a_poor_parent_does_not_invalidate_a_clean_candidate():
    # parent needs cleanup (a QUALITY judgment) -> must NOT propagate
    src = readiness.assess([_ev(C.EV_VECTOR_RASTER_BALANCE, blocking=True)])
    assert src["value"] == C.READY_NEEDS_CLEANUP
    cand_ev = [_ev(C.EV_EDITABLE_COLORS)]
    cand = readiness.assess(cand_ev)
    merged = readiness.merge_source_blockers(cand, src, cand_ev)
    assert merged["value"] == C.READY_TECHNICALLY_READY


def test_a_clean_parent_does_not_rescue_a_poor_candidate():
    src = readiness.assess([_ev(C.EV_EDITABLE_COLORS)])
    assert src["value"] == C.READY_TECHNICALLY_READY
    cand_ev = [_ev(C.EV_RASTER_RESOLUTION, blocking=True)]
    cand = readiness.assess(cand_ev)
    merged = readiness.merge_source_blockers(cand, src, cand_ev)
    assert merged["value"] == C.READY_REFERENCE_ONLY


# --- independence through the REAL pipeline (not just the helper) -----------
@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "REPO_ROOT", tmp_path, raising=False)
    return tmp_path


def _raster_heavy_multicluster_pdf(root, name="heavy.pdf"):
    """A page that IS raster-heavy (coverage >= 0.60) but has >60 vector paths in
    two clusters well away from the image — so it is NOT a JPEG-shell, and the
    clusters are clean pure vector."""
    import fitz
    Image.new("RGB", (300, 300), "orange").save(root / "im.png")
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_image(fitz.Rect(0, 0, 400, 320), filename=str(root / "im.png"))
    for i in range(40):
        page.draw_rect(fitz.Rect(10 + (i % 8) * 4, 340 + (i // 8) * 4,
                                 12 + (i % 8) * 4, 342 + (i // 8) * 4),
                       fill=(0, 0, 1))
    for i in range(40):
        page.draw_rect(fitz.Rect(330 + (i % 8) * 4, 340 + (i // 8) * 4,
                                 332 + (i % 8) * 4, 342 + (i // 8) * 4),
                       fill=(0, 1, 0))
    doc.save(root / name)
    doc.close()
    return name


def test_real_pipeline_poor_parent_does_not_invalidate_clean_subcandidates(repo):
    """Drives run_c2b.score_entry, NOT merge_source_blockers directly.

    The page-level judgment "raster covers 70% of the SURFACE" describes the whole
    page. It must not block a clean pure-vector cluster cut out of that page.
    """
    name = _raster_heavy_multicluster_pdf(repo)
    res = run_c2b.score_entry({"relative_path": name, "format": ".pdf",
                               "c2_test_role": "probe"}, {})
    src = res["source_technical_readiness"]
    assert src["value"] == C.READY_NEEDS_CLEANUP           # the PAGE is raster-heavy
    assert src["caused_by"] == C.EV_VECTOR_RASTER_BALANCE
    subs = [c for c in res["candidates"]
            if c["segmentation"]["method"] == C.SEG_METHOD_VECTOR]
    assert subs, "expected vector sub-candidates"
    for c in subs:
        a = c["A_technical_readiness"]
        assert a["value"] in (C.READY_TECHNICALLY_READY,
                              C.READY_TECHNICALLY_USABLE_WITH_CAVEATS)
        assert a["caused_by"] != C.EV_VECTOR_RASTER_BALANCE
        # the parent's verdict is still visible, just not binding
        assert c["source_technical_readiness"]["value"] == C.READY_NEEDS_CLEANUP


def test_real_pipeline_whole_surface_candidate_does_inherit_its_own_page(repo):
    """The other half of the rule: when the candidate IS the whole surface, the
    page-level judgment genuinely describes it — a JPEG-shell must still come back
    NEEDS_VECTOR_RECONSTRUCTION through the real pipeline."""
    Image.new("RGB", (300, 300), "red").save(repo / "img.png")
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_image(page.rect, filename=str(repo / "img.png"))
    doc.save(repo / "shell.pdf")
    doc.close()
    res = run_c2b.score_entry({"relative_path": "shell.pdf", "format": ".pdf",
                               "c2_test_role": "shell"}, {})
    assert len(res["candidates"]) == 1
    a = res["candidates"][0]["A_technical_readiness"]
    assert a["value"] == C.READY_NEEDS_VECTOR_RECONSTRUCTION
    assert a["caused_by"] == C.EV_EMBEDDED_RASTER_DEPENDENCE


# --- integration: real pilot, read-only --------------------------------------
@pytest.fixture(scope="module")
def recon():
    assert run_c2b.main() == 0
    return json.loads((C.OUT_REPORTS / "c2b_reconciliation.json")
                      .read_text(encoding="utf-8"))


def test_pilot_invariants_and_integrity(recon):
    assert all(recon["invariants"].values())
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["integrity"]["no_output_under_source"]["ok"] is True


def test_pilot_eps_never_technically_ready(recon):
    assert recon["invariants"]["eps_never_technically_ready"] is True
    assert recon["blocked_by_tooling"] >= 5          # the 5 real EPS candidates


def test_pilot_rights_and_retrieval_stay_disabled(recon):
    assert recon["invariants"]["no_rights_granted"] is True
    assert recon["invariants"]["retrieval_and_auto_use_all_false"] is True
    assert recon["invariants"]["no_approved_reusable"] is True


def test_pilot_readiness_vocabulary_is_canonical(recon):
    assert recon["invariants"]["readiness_vocabulary_canonical"] is True
    assert recon["invariants"]["no_retired_readiness_vocabulary"] is True
    for value in recon["candidates_by_technical_readiness"]:
        assert value in C.TECHNICAL_READINESS


def test_pilot_jpeg_shell_reported(recon):
    assert "5955567.ai" in recon["embedded_raster_or_jpeg_shell_sources"]
    assert recon["requiring_reconstruction"] >= 1


def test_pilot_run_is_deterministic():
    a = json.loads((C.OUT_REPORTS / "c2b_reconciliation.json")
                   .read_text(encoding="utf-8"))
    assert run_c2b.main() == 0
    b = json.loads((C.OUT_REPORTS / "c2b_reconciliation.json")
                   .read_text(encoding="utf-8"))
    assert a["candidates_by_technical_readiness"] == \
        b["candidates_by_technical_readiness"]
    assert a["pattern_verdict_totals_per_source"] == \
        b["pattern_verdict_totals_per_source"]
    assert a["raster_quality_bands"] == b["raster_quality_bands"]
