"""Authored-master acceptance: exact assets/copy, immutable files and closed gates."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import fitz
import pytest
from PIL import Image
from django.core import signing
from django.urls import reverse

from apps.pipeline.services.design_spec import DEFAULT_COPY, digest, make_spec, validate_spec
from apps.pipeline.services.hybrid_bottle_output import compile_bundle


@pytest.fixture(autouse=True)
def hybrid_environment(settings, tmp_path):
    settings.BRAND_MARK_APPROVAL_LOOKUP = True
    settings.HYBRID_BOTTLE_ENABLED = True
    settings.MEDIA_ROOT = tmp_path / "media"


def test_owner_dimensions_do_not_become_supplier_measurements():
    spec = make_spec()
    assert (spec.stock.diameter_mm, spec.stock.height_mm, spec.stock.capacity_ml) == (29, 108, 30)
    assert spec.stock.height_datum == "unresolved"
    assert not spec.stock.supplier_verified and not spec.surface.supplier_verified
    assert spec.surface.method == "unresolved" and spec.surface.seam_exclusion_mm is None
    assert spec.model_dump()["copy"] == DEFAULT_COPY


@pytest.mark.parametrize("change", [
    lambda d: d.update(schema_version="design_spec/99"),
    lambda d: d.update(surprise="silent field"),
    lambda d: d.update(brief="different brief"),
    lambda d: d["stock"].update(diameter_mm=35.0),
    lambda d: d["stock"].update(supplier_verified=True),
    lambda d: d["surface"].update(width_mm=float("nan")),
    lambda d: d["surface"].update(seam_exclusion_mm=0),
    lambda d: d["surface"].update(method="foil"),
    lambda d: d["type_tokens"][0].update(size_pt=35.0),
    lambda d: d["assets"][0].update(sha256="0" * 64),
    lambda d: d["illustration"].update(x_mm=39.0),
    lambda d: d["palette"].update(secondary=d["palette"]["dominant"]),
    lambda d: d.update(creative_acceptance="accepted"),
])
def test_corrupt_or_unsupported_spec_is_refused(change):
    data = make_spec().model_dump()
    change(data)
    with pytest.raises(ValueError):
        validate_spec(data)


def test_single_line_copy_and_whitespace_are_never_silently_removed():
    for key, value in [("descriptor", "SERUM\nSPF"), ("benefit", "  Care"), ("arabic", "سيروم\nصن")]:
        with pytest.raises(ValueError):
            make_spec(copy=dict(DEFAULT_COPY, **{key: value}))


def test_overflow_is_refused_instead_of_shrinking_or_dropping_copy(tmp_path):
    spec = make_spec(copy=dict(DEFAULT_COPY, name="SUPER REJUVENATING COMPLEX SERUM"))
    with pytest.raises(ValueError, match="lines|needs"):
        compile_bundle(spec.model_dump(), tmp_path / "refused")
    assert not (tmp_path / "refused/artwork.pdf").exists()


def test_missing_or_changed_required_bitmap_refuses(monkeypatch, tmp_path):
    from apps.pipeline.services import design_spec as ds
    spec = make_spec().model_dump()
    altered = tmp_path / "altered.png"
    Image.new("RGB", (1024, 1536), "red").save(altered)
    monkeypatch.setitem(ds.ASSET_FILES, "solar-gesture-v1", (altered, "illustration"))
    with pytest.raises(ValueError, match="missing or changed"):
        validate_spec(spec)


def test_unsupported_glyph_cannot_be_hidden_behind_logical_copy(tmp_path):
    spec = make_spec(copy=dict(DEFAULT_COPY, descriptor="SERUM🚀"))
    with pytest.raises(ValueError, match="cannot draw every character"):
        compile_bundle(spec.model_dump(), tmp_path / "refused-glyph")
    assert not (tmp_path / "refused-glyph/artwork.pdf").exists()


def test_real_compiler_preserves_pixels_fonts_copy_and_dimensions_without_legacy(monkeypatch, tmp_path):
    from apps.pipeline.targets import container
    for name in ("_infer_profile", "_read_design_map", "ensure_flat_motifs", "reconstruct_container"):
        monkeypatch.setattr(container, name, Mock(side_effect=AssertionError("Legacy reconstruction called")))
    from apps.pipeline.services import claude_service
    monkeypatch.setattr(claude_service, "call_claude", Mock(side_effect=AssertionError("Provider called")))
    spec = make_spec()
    original = next(a.sha256 for a in spec.assets if a.role == "illustration")
    root = tmp_path / "master"
    result = compile_bundle(spec.model_dump(), root, expected_hash=digest(spec.model_dump()))
    report = result["preflight"]
    assert report["original_raster_pixels_preserved"]
    assert report["effective_ppi"] == pytest.approx([812.8, 812.8])
    assert report["page_mm"] == pytest.approx([32, 60], abs=.001)
    assert report["live_copy"] == DEFAULT_COPY
    assert report["source_asset_sha256"] == original
    assert report["creative_acceptance"] == "review_pending" and not report["production_ready"]
    assert len(report["embedded_fonts"]) == 3 and report["logical_text_in_pdf"]
    assert (root / "artwork.pdf").read_bytes() == (root / "artwork-pdf-compatible.ai").read_bytes()
    svg = (root / "artwork.svg").read_text()
    assert 'data-symbol="℮"' in (root / "artwork-back.svg").read_text() and DEFAULT_COPY["arabic"] in svg
    assert 'clip-path="url(#illustration-crop)"' in svg
    assert [row["surface_id"] for row in report["surfaces"]] == ["body.front", "body.back"]
    assert "data:image/png;base64," in svg and svg.count("data:font/ttf;base64,") == 3
    with fitz.open(root / "comparison-at-100-percent.pdf") as proof:
        assert [proof[0].rect.width * 25.4 / 72, proof[0].rect.height * 25.4 / 72] == pytest.approx([297, 210], abs=.001)
        assert "50 mm calibration bar" in proof[0].get_text()
    with fitz.open(root / "artwork.pdf") as pdf:
        assert [o["name"] for o in pdf.get_ocgs().values()] == ["ARTWORK"]
        assert len(pdf) == 2
        for page in pdf:
            assert [page.rect.width * 25.4 / 72, page.rect.height * 25.4 / 72] == pytest.approx([32, 60], abs=.001)
            assert len(page.get_drawings()) > 1  # field and approved vector mark, on both pages
        assert "SUN" in pdf[0].get_text() and "Revive" not in pdf[0].get_text()
        assert "Revive" in pdf[1].get_text() and "SUN" not in pdf[1].get_text()
    assert (root / "artwork-back.png").is_file()


@pytest.fixture
def author(db, client):
    from django.contrib.auth.models import User
    from apps.core.models import Brand
    user = User.objects.create_superuser("day2-author", password="test-only")
    Brand.objects.create(name="BBROSE")
    client.force_login(user)
    return user


def test_height_datum_is_carried_into_proof(tmp_path):
    root = tmp_path / "overall"
    result = compile_bundle(make_spec(height_datum="overall").model_dump(), root)
    assert result["preflight"]["prototype_height_convention"] == "108 mm overall, owner-provided"
    with fitz.open(root / "comparison-at-100-percent.pdf") as pdf:
        assert "108 mm overall height is owner-provided" in pdf[0].get_text()
        assert "108 mm overall height is owner-provided" in pdf[1].get_text()


def test_native_surface_names_and_back_mark_are_preserved():
    from apps.ire.compose_hybrid_bottle import compose
    from apps.ire.emitters import native_ai
    doc, _ = compose(make_spec())
    data = native_ai.tree(doc)
    assert [b['name'] for b in data['boards']] == ['BODY FRONT', 'BODY BACK']
    assert not data['skipped']
    for board in data['boards']:
        assert 'Approved BBROSE vector mark' in json.dumps(board)
    for invalid in ('AB', [], ['ONLY'], ['', 'BACK'], None):
        doc.metadata['surface_names'] = invalid
        with pytest.raises(ValueError, match='artboards'):
            native_ai.tree(doc)


def test_logical_pdf_copy_metadata_does_not_change_artwork_pixels(tmp_path):
    from apps.ire.compose_hybrid_bottle import compose
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    doc, _ = compose(make_spec())
    enabled = tmp_path / 'logical.pdf'
    emit_pdf_ai(doc, str(enabled))
    del doc.metadata['logical_text/1.0']
    plain = tmp_path / 'plain.pdf'
    emit_pdf_ai(doc, str(plain))
    with fitz.open(enabled) as a, fitz.open(plain) as b:
        for i in (0, 1):
            assert a[i].get_pixmap(dpi=300).samples == b[i].get_pixmap(dpi=300).samples
        assert DEFAULT_COPY['arabic'].encode('utf-16-be').hex().upper().encode() in a[0].read_contents().upper()
        assert '30 ml ℮ 1.0 fl oz'.encode('utf-16-be').hex().upper().encode() in a[1].read_contents().upper()
