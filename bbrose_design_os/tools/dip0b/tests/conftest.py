"""Synthetic PDFs for DIP-0B1. The real library is never written to, and the
pilot-regression tests below only ever READ it."""
from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

REAL_REPO = Path(__file__).resolve().parents[4]
REAL_PILOT = REAL_REPO / "docs" / "design_intelligence" / "dip0a" / "pilot_manifest.json"


def _page_with_boxes(doc, w=400, h=300, artbox=(20, 30, 380, 260)):
    page = doc.new_page(width=w, height=h)
    # PDF boxes are y-up, bottom-left origin
    doc.xref_set_key(page.xref, "ArtBox", f"[{artbox[0]} {artbox[1]} {artbox[2]} {artbox[3]}]")
    doc.xref_set_key(page.xref, "TrimBox", f"[0 0 {w} {h}]")
    doc.xref_set_key(page.xref, "BleedBox", f"[0 0 {w} {h}]")
    return page


@pytest.fixture
def simple_pdf(tmp_path):
    """One page, ArtBox inset, a thin no-fill stroke, a big fill, a glyph-scale
    fill, and one object placed OFF-CANVAS (outside the ArtBox)."""
    doc = fitz.open()
    page = _page_with_boxes(doc)
    page.draw_rect(fitz.Rect(30, 40, 370, 250), color=None, fill=(0.9, 0.8, 0.8))
    page.draw_rect(fitz.Rect(50, 60, 200, 180), color=(0, 0, 0), width=0.7)  # thin stroke
    page.draw_rect(fitz.Rect(60, 70, 70, 80), color=None, fill=(0, 0, 0))    # glyph-scale
    page.draw_rect(fitz.Rect(0, 0, 12, 12), color=None, fill=(1, 0, 0))      # off-canvas
    p = tmp_path / "simple.pdf"
    doc.save(p)
    doc.close()
    return p


@pytest.fixture
def multipage_pdf(tmp_path):
    doc = fitz.open()
    _page_with_boxes(doc, 400, 300)
    _page_with_boxes(doc, 600, 500, artbox=(0, 0, 600, 500))   # second page larger
    p = tmp_path / "multi.pdf"
    doc.save(p)
    doc.close()
    return p


@pytest.fixture
def empty_pdf(tmp_path):
    doc = fitz.open()
    doc.new_page(width=200, height=200)
    p = tmp_path / "empty.pdf"
    doc.save(p)
    doc.close()
    return p


@pytest.fixture
def dense_pdf(tmp_path):
    """Enough paths to trip a low max_paths_detailed guard."""
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    for i in range(300):
        x = (i % 20) * 24 + 2
        y = (i // 20) * 30 + 2
        page.draw_rect(fitz.Rect(x, y, x + 8, y + 8), color=None, fill=(0, 0, 0))
    p = tmp_path / "dense.pdf"
    doc.save(p)
    doc.close()
    return p


@pytest.fixture
def out_dirs(tmp_path, monkeypatch):
    """Redirect every dip0b output root into tmp; assert nothing escapes."""
    from tools.dip0b import config as C

    root = tmp_path / "var" / "dip0b"
    monkeypatch.setattr(C, "OUTPUT_ROOT", root)
    monkeypatch.setattr(C, "OUT_TECHNICAL", root / "technical")
    monkeypatch.setattr(C, "OUT_PREVIEWS", root / "previews")
    monkeypatch.setattr(C, "OUT_REPORTS", root / "reports")
    monkeypatch.setattr(C, "OUT_TEMP", root / "temporary")
    monkeypatch.setattr(C, "DOCS_ROOT", tmp_path / "docs" / "dip0b")
    return root


# --- real-pilot regression access (READ-ONLY) -------------------------------

def _pilot_entries():
    if not REAL_PILOT.exists():
        return []
    return json.loads(REAL_PILOT.read_text())["historical_designs"]


@pytest.fixture(scope="session")
def pilot_entries():
    entries = _pilot_entries()
    if not entries:
        pytest.skip("DIP-0A pilot manifest not present")
    return entries


def pilot_path(entry) -> Path:
    # Day 6 migration: the recorded pilot path is the identity; the bytes may live at the manifest's new path.
    from tools.dip0 import config as C0
    return C0.physical_path(entry["relative_path"], REAL_REPO)
