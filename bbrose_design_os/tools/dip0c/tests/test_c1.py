"""DIP-0C1 tests — hermetic where possible (synthetic fixtures under a temp
REPO_ROOT), plus a read-only integration pass over the real pilot.

The invariants under test are the ones the plan makes load-bearing: routing by
format, the JPEG-shell detector, SVG security rejection, EPS header parsing +
TIFF-preview detection, the blocked Ghostscript adapter, classification overrides
that never rewrite the DIP-0A original, the absolute ban on machine-emitted
APPROVED_REUSABLE, and the strict separation of technical readiness (axis A) from
rights/retrieval (axis B).
"""
from __future__ import annotations

import json
import struct

import fitz
import pytest
from PIL import Image

from tools.dip0c import (
    classify_override as co,
    config as C,
    eps_ghostscript,
    eps_header,
    raster,
    run_c1,
    svg,
)


# --- fixtures ---------------------------------------------------------------
@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Point every module's REPO_ROOT at a temp tree so fixtures resolve there."""
    for mod in (svg, raster, eps_header, eps_ghostscript, run_c1.pdf_vector):
        monkeypatch.setattr(mod.C, "REPO_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(C, "REPO_ROOT", tmp_path, raising=False)
    return tmp_path


def _write(root, name, data: bytes):
    p = root / name
    p.write_bytes(data)
    return name


def _clean_svg():
    return (b'<?xml version="1.0"?>'
            b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
            b'<path d="M0 0 L5 5" fill="red"/><circle r="2"/></svg>')


def _script_svg():
    return (b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<script>alert(1)</script>'
            b'<rect onclick="x()" fill="blue"/>'
            b'<image href="https://evil.example/a.png"/></svg>')


def _entity_svg():
    return (b'<?xml version="1.0"?>'
            b'<!DOCTYPE svg [<!ENTITY lol "aa"><!ENTITY lol2 "&lol;&lol;">]>'
            b'<svg xmlns="http://www.w3.org/2000/svg"><text>&lol2;</text></svg>')


def _binary_eps_with_tiff():
    ps = (b"%!PS-Adobe-3.0 EPSF-3.0\n"
          b"%%BoundingBox: 0 0 100 200\n"
          b"%%HiResBoundingBox: 0 0 100.5 200.5\n"
          b"%%DocumentCustomColors: (PANTONE 185 C)\n"
          b"%%DocumentProcessColors: Cyan Magenta Yellow Black\n"
          b"%%DocumentFonts: Helvetica\n"
          b"%%Creator: Adobe Illustrator(R) 28.0\n"
          b"%%EndComments\nshowpage\n")
    tiff = b"II*\x00" + b"\x00" * 40
    ps_off = 30
    tiff_off = ps_off + len(ps)
    hdr = (b"\xc5\xd0\xd3\xc6"
           + struct.pack("<IIIIII", ps_off, len(ps), 0, 0, tiff_off, len(tiff))
           + b"\xff\xff")
    assert len(hdr) == 30
    return hdr + ps + tiff


def _ascii_eps():
    return (b"%!PS-Adobe-3.0 EPSF-3.0\n"
            b"%%BoundingBox: 0 0 50 60\n"
            b"%%DocumentProcessColors: Cyan Magenta\n"
            b"%%EndComments\nshowpage\n")


def _psd_header(w=1200, h=800, channels=5, mode=3, depth=8):
    return (b"8BPS" + struct.pack(">H", 1) + b"\x00" * 6
            + struct.pack(">H", channels) + struct.pack(">I", h)
            + struct.pack(">I", w) + struct.pack(">H", depth)
            + struct.pack(">H", mode))


# --- routing ----------------------------------------------------------------
def test_routing_by_format(repo):
    _write(repo, "a.svg", _clean_svg())
    _write(repo, "a.eps", _ascii_eps())
    Image.new("RGB", (1200, 1200)).save(repo / "a.png")
    doc = fitz.open()
    doc.new_page()
    doc.save(repo / "a.pdf")
    doc.close()
    assert run_c1.route("a.svg")[0] == "svg"
    assert run_c1.route("a.eps")[0] == "eps"
    assert run_c1.route("a.png")[0] == "raster"
    assert run_c1.route("a.pdf")[0] == "pdf_backed"
    assert run_c1.route("a.otf")[0] == "deferred"
    assert run_c1.route("a.xyz")[0] == "unsupported"


# --- JPEG-shell detector ----------------------------------------------------
def test_jpeg_shell_detected(repo):
    Image.new("RGB", (400, 400), "red").save(repo / "img.png")
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.insert_image(page.rect, filename=str(repo / "img.png"))  # full-page raster
    doc.save(repo / "shell.pdf")
    doc.close()
    a = run_c1.route("shell.pdf")[1]
    assert a["raster"]["jpeg_shell"]["value"] is True
    assert a["technical_readiness"]["value"] == C.READY_NEEDS_VECTOR_RECONSTRUCTION


def test_clean_vector_not_shell(repo):
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    for i in range(0, 200, 5):
        page.draw_line((0, i), (200, i))
    doc.save(repo / "vec.pdf")
    doc.close()
    a = run_c1.route("vec.pdf")[1]
    assert a["raster"]["jpeg_shell"]["value"] is False
    assert a["path_count"]["value"] > 0


def test_pdf_vector_surfaces_plan_fields(repo):
    # gradients/masks/transparency, off-canvas and AI-private must be present
    # (they are the near-free fields the plan enumerates for PDF-backed audit).
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_rect(fitz.Rect(10, 10, 50, 50), fill=(1, 0, 0))
    doc.save(repo / "fields.pdf")
    doc.close()
    a = run_c1.route("fields.pdf")[1]
    gmt = a["gradients_masks_transparency"]["value"]
    assert set(gmt) == {"shadings", "soft_masks", "transparency_groups",
                        "tiling_patterns"}
    assert "total" in a["off_canvas"]["value"]
    assert a["ai_private_present"]["tier"] == C.TIER_REQUIRES_ILLUSTRATOR


# --- SVG security -----------------------------------------------------------
def test_svg_clean_parses_safe(repo):
    _write(repo, "clean.svg", _clean_svg())
    a = svg.audit("clean.svg")
    assert a["parse_status"] == "PARSED"
    assert a["security"]["safe_to_ingest"]["value"] is True
    assert a["vector_paths"]["value"] >= 2


def test_svg_script_and_remote_rejected(repo):
    _write(repo, "evil.svg", _script_svg())
    a = svg.audit("evil.svg")
    assert a["security"]["safe_to_ingest"]["value"] is False
    assert a["technical_readiness"]["value"] == C.READY_QUARANTINE
    joined = " ".join(a["security"]["findings"])
    assert "script" in joined and "remote" in joined and "event-handler" in joined


def test_svg_internal_entity_rejected(repo):
    _write(repo, "bomb.svg", _entity_svg())
    a = svg.audit("bomb.svg")
    assert a["parse_status"] == "REJECTED_UNSAFE_XML"
    assert a["security"]["safe_to_ingest"]["value"] is False


def test_svg_never_fetches_network(repo):
    # remote href must be recorded as a finding, never resolved
    _write(repo, "remote.svg",
           b'<svg xmlns="http://www.w3.org/2000/svg">'
           b'<image href="http://10.255.255.1/x.png"/></svg>')
    a = svg.audit("remote.svg")
    assert a["security"]["network_access"] == "blocked"
    assert a["raster"]["remote_or_external"] >= 1


# --- raster / PSD -----------------------------------------------------------
def test_raster_dims_alpha(repo):
    Image.new("RGBA", (2048, 1024)).save(repo / "big.png")
    a = raster.audit("big.png")
    assert a["dimensions"]["value"] == {"w": 2048, "h": 1024}
    assert a["alpha"]["value"] is True
    assert a["technical_readiness"]["value"] == C.READY_TECHNICALLY_USABLE_WITH_CAVEATS


def test_raster_low_res_reference_only(repo):
    Image.new("RGB", (300, 300)).save(repo / "small.png")
    a = raster.audit("small.png")
    assert a["technical_readiness"]["value"] == C.READY_REFERENCE_ONLY


def test_psd_header_channels(repo):
    _write(repo, "art.psd", _psd_header(channels=5, mode=3))
    a = raster.audit("art.psd")
    assert a["parse_status"] == "PARSED"
    assert a["dimensions"]["value"] == {"w": 1200, "h": 800}
    assert a["extra_channels"] == 2      # 5 channels - 3 base rgb
    assert a["color_mode"]["value"] == "rgb"


def test_watermark_is_heuristic_never_fact(repo):
    Image.new("RGB", (500, 500)).save(repo / "shutterstock_preview.png")
    a = raster.audit("shutterstock_preview.png")
    wm = a["watermark_suspected"]
    assert wm["tier"] == C.TIER_HEURISTIC
    assert wm["value"] is True and wm["confidence"] < 1.0


# --- EPS C1A header ---------------------------------------------------------
def test_eps_binary_header_and_tiff(repo):
    _write(repo, "bin.eps", _binary_eps_with_tiff())
    a = eps_header.audit("bin.eps")
    assert a["binary_dos_eps"] is True
    assert a["eps_capability_state"] == C.EPS_HEADER_AUDITED
    assert a["bounding_box"]["value"] == [0, 0, 100, 200]
    assert a["spot_colors"]["value"] == ["PANTONE 185 C"]
    assert a["tiff_preview"]["present"] is True
    assert a["tiff_preview"]["magic_valid"] is True
    # header pass must NEVER claim it has geometry
    assert a["vector_geometry"]["tier"] == C.TIER_REQUIRES_TOOL
    assert a["vector_geometry"]["value"] is None


def test_eps_ascii_header(repo):
    _write(repo, "asc.eps", _ascii_eps())
    a = eps_header.audit("asc.eps")
    assert a["binary_dos_eps"] is False
    assert a["bounding_box"]["value"] == [0, 0, 50, 60]
    assert a["tiff_preview"]["present"] is False


def test_eps_dsc_multiline_continuation(repo):
    # custom colours declared across several %%+ continuation lines must all be
    # captured, not just the first (regression: single-line capture bug).
    eps = (b"%!PS-Adobe-3.0 EPSF-3.0\n"
           b"%%BoundingBox: 0 0 10 10\n"
           b"%%DocumentCustomColors: (PANTONE 185 C)\n"
           b"%%+ (PANTONE 032 C)\n"
           b"%%+ (PANTONE Reflex Blue C)\n"
           b"%%EndComments\nshowpage\n")
    _write(repo, "multi.eps", eps)
    a = eps_header.audit("multi.eps")
    assert a["spot_colors"]["value"] == [
        "PANTONE 185 C", "PANTONE 032 C", "PANTONE Reflex Blue C"]


def test_eps_truncated_binary_header_no_crash(repo):
    # DOS-EPS magic but fewer than 30 header bytes must degrade, not raise.
    _write(repo, "trunc.eps", b"\xc5\xd0\xd3\xc6\x00\x00")
    a = eps_header.audit("trunc.eps")
    assert a["eps_capability_state"] == C.EPS_HEADER_ONLY_PARTIAL
    assert any("truncated" in w for w in a["warnings"])


# --- Ghostscript adapter blocked --------------------------------------------
# §BH44(a)(1). This pair replaces one test that asserted a fact about THE HOST:
# `eps_capability_state == GHOSTSCRIPT_NOT_INSTALLED` held only while no gs binary
# was on PATH, so installing Ghostscript refused the gate on a machine change rather
# than a code change. The adapter has two blocked states and both are now pinned
# deterministically by patching detection, so this file reads the same on a machine
# with Ghostscript and on one without. The four invariants below are asserted in BOTH
# branches, unchanged: one accidental branch became two deliberate ones.
def _assert_blocked_invariants(a):
    """What holds whatever this machine has installed: the adapter is blocked, it
    converts nothing, it installs nothing, and the geometry still requires a tool."""
    assert a["adapter_status"] == C.GHOSTSCRIPT_ADAPTER_BLOCKED
    assert a["conversion"]["attempted"] is False
    assert a["ghostscript"]["auto_install"] is False
    assert a["derived_geometry"]["tier"] == C.TIER_REQUIRES_TOOL


def test_ghostscript_adapter_blocked_when_gs_absent(monkeypatch, repo):
    monkeypatch.setattr(eps_ghostscript, "detect_ghostscript",
                        lambda: {"present": False, "binary": None, "path": None})
    _write(repo, "x.eps", _ascii_eps())
    a = eps_ghostscript.audit("x.eps")
    _assert_blocked_invariants(a)
    assert a["eps_capability_state"] == C.EPS_GHOSTSCRIPT_NOT_INSTALLED


def test_ghostscript_adapter_blocked_when_gs_present(monkeypatch, repo):
    monkeypatch.setattr(eps_ghostscript, "detect_ghostscript",
                        lambda: {"present": True, "binary": "gs", "path": "/opt/homebrew/bin/gs"})
    _write(repo, "x.eps", _ascii_eps())
    a = eps_ghostscript.audit("x.eps")
    _assert_blocked_invariants(a)
    assert a["eps_capability_state"] == C.EPS_GHOSTSCRIPT_PILOT_PENDING


def test_ghostscript_never_autoinstalls(monkeypatch, repo):
    # even if a gs binary were present, C1 must not convert inline
    monkeypatch.setattr(eps_ghostscript, "detect_ghostscript",
                        lambda: {"present": True, "binary": "gs", "path": "/x/gs"})
    _write(repo, "y.eps", _ascii_eps())
    a = eps_ghostscript.audit("y.eps", enable=True)
    assert a["conversion"]["attempted"] is False
    assert a["adapter_status"] == C.GHOSTSCRIPT_ADAPTER_BLOCKED


# --- classification overrides -----------------------------------------------
def test_override_eula_is_license_evidence():
    ov = co.classify_pdf("EULA Cartoon 2 US.pdf", page_count=1,
                         first_page_text="End User License Agreement",
                         original_category="REUSABLE_VECTOR_ASSET",
                         third_party=False)
    assert ov["audit_category_override"] == "LICENSE_EVIDENCE"
    # original is preserved, human decision stays blank
    assert ov["inventory_category_original"] == "REUSABLE_VECTOR_ASSET"
    assert ov["human_confirmed_category"] is None


def test_override_presentation_deck():
    ov = co.classify_pdf("ATC PRESENTATION-1.pdf", page_count=12,
                         first_page_text="", original_category="REUSABLE_VECTOR_ASSET",
                         third_party=True)
    assert ov["audit_category_override"] == "THIRD_PARTY_RESTRICTED"
    assert ov["inventory_category_original"] == "REUSABLE_VECTOR_ASSET"


def test_override_absent_leaves_original():
    ov = co.classify_pdf("flower-motif.pdf", page_count=1, first_page_text="",
                         original_category="MOTIF", third_party=False)
    assert ov["audit_category_override"] is None
    assert ov["inventory_category_original"] == "MOTIF"


# --- APPROVED_REUSABLE is human-only ----------------------------------------
def test_machine_posture_rejects_approved_reusable():
    with pytest.raises(C.ReusePostureViolation):
        C.machine_posture(C.POSTURE_APPROVED_REUSABLE)


def test_posture_hint_never_approved():
    for cat in co.OVERRIDE_CATEGORIES:
        ov = co.override_record("X", cat, "r", [], 0.5)
        hint = co.posture_hint(ov)
        assert hint["value"] != C.POSTURE_APPROVED_REUSABLE
        assert hint["value"] in C.MACHINE_ALLOWED_POSTURES


def test_no_approved_reusable_in_any_record(repo):
    _write(repo, "clean.svg", _clean_svg())
    entry = {"relative_path": "clean.svg", "format": ".svg",
             "test_role": "svg", "inventory_category_original": "REUSABLE_VECTOR_ASSET"}
    rec = run_c1.audit_entry(entry, {})
    assert C.POSTURE_APPROVED_REUSABLE not in json.dumps(rec)


# --- technical readiness is NOT rights readiness ----------------------------
def test_tech_axis_never_grants_rights(repo):
    # a technically clean SVG still has all rights false + retrieval off
    _write(repo, "clean.svg", _clean_svg())
    entry = {"relative_path": "clean.svg", "format": ".svg",
             "test_role": "svg", "inventory_category_original": "PATTERN"}
    rec = run_c1.audit_entry(entry, {})
    assert rec["technical_readiness"]["value"] == C.READY_TECHNICALLY_USABLE_WITH_CAVEATS
    r = rec["rights"]
    assert r["commercial_use"] is False and r["modification"] is False
    assert r["embedding"] is False and r["redistribution"] is False
    assert r["ownership_status"] == "unverified"
    g = rec["retrieval_gate"]
    assert not any(g[k] for k in ("retrieval", "automatic_use", "embedding",
                                  "production_use"))


def test_human_block_present_and_blank(repo):
    _write(repo, "clean.svg", _clean_svg())
    entry = {"relative_path": "clean.svg", "format": ".svg",
             "test_role": "svg", "inventory_category_original": "PATTERN"}
    rec = run_c1.audit_entry(entry, {})
    assert rec["human"]["category"] is None
    assert rec["human"]["reviewed_by"] is None


# --- integration: real pilot, read-only -------------------------------------
def test_full_pilot_runs_and_materials_unchanged():
    rc = run_c1.main()
    assert rc == 0
    recon = json.loads((C.OUT_REPORTS / "c1_reconciliation.json")
                       .read_text(encoding="utf-8"))
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["integrity"]["no_output_under_source"]["ok"] is True
    assert recon["invariants"]["no_approved_reusable_in_machine_output"] is True
    assert recon["invariants"]["retrieval_gate_all_off"] is True
    assert recon["pilot_count"] == 24
    assert "5955567.ai" in recon["jpeg_shell_files"]
