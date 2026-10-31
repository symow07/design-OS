"""Explicit, deterministic DIP-1B-5A curated-expansion manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from django.conf import settings

from .dataset_identifiers import DIP1B_CURATED_ASSET_EXPANSION_DATASET
from .locator_schemas import normalize_relative_path

MANIFEST_ID = "dip1b_curated_expansion_manifest/1.0"
MANIFEST_SCHEMA = MANIFEST_ID
HISTORICAL_DATASET_ID = "dip1b_curated_historical_expansion/1.0"
GENERATOR_IDENTIFIER = "bbrose.intelligence.curated_expansion_manifest"
GENERATOR_VERSION = "1.0"
DEFAULT_MANIFEST_PATH = (
    Path(settings.BASE_DIR).parent
    / "docs/design_intelligence/dip1/dip1b_curated_expansion_manifest_1_0.json")

HISTORICAL_SELECTIONS = (
    ("BL-2055 FB-2056.ai", "makeup-compact", "decorative", "mixed-product-packaging"),
    ("FL-2025.ai", "complexion", "minimal", "carton"),
    ("LG5505唇彩.ai", "lip-colour", "decorative", "primary-packaging"),
    ("PM5520妆前乳.ai", "primer-skincare", "minimal", "primary-packaging"),
    ("YB-1059(ES6009).END.ai", "eye-colour", "decorative", "carton"),
    ("ZYG5528遮瑕膏.ai", "concealer", "minimal", "primary-packaging"),
)

ASSET_SELECTIONS = (
    ("DOWNLOADS 12-2025/4-point-stars-background/4_point_stars_background.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/abstract-background-with-gradient-blur-design/abstract_background_with_a_gradient_blur_design_2705.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/bear-polar-seamless-pattern-flower-daisy-paw-footprint-cartoon-character/bear_polar_seamless_pattern_flower_daisy_paw_footprint_cartoon_character.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/black-white-seamless-pattern-background/684.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/candy-pattern-ice-background-design-template/oq4.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/carrot-line-icons-seamless-pattern/e99707d0-7618-42d1-a3fb-36f49d043290.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/cooking-hands-line-seamless-pattern-vector-background/f76b109a-8499-4376-9a75-3609d0feb8a8.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/cosmetic-icon-seamless-pattern-pink-vector-wallpaper/Cosmetic_patterns_pink1.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/cute-hand-drawn-valentine-s-day-pattern/56.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/cute-teddy-bear-brown-seamless-pattern-kawaii-wallpaper/29087547-91e5-4ca9-ab1d-a3ae011b4ba5.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/dark-pattern-orange-waves/4487.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/diagonal-leaves-pattern-background-vector/diagonal_leaves_pattern_background_vector.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/flat-design-purple-striped-pattern-design/7689241.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/floral-print-seamless-texture/172.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/geometric-flowers-with-seamless-pattern-red-background-repeating-brown-floral-vector-illustration/442Z_Dance_26.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/geometric-seamless-texture/td4-s-inv-14.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/gift-boxes-vector-seamless-pattern-white-simple-line-elements-red-background/8612c434-3235-48c6-a413-511d1c3cb8c0.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/glitter-background-valentine/4925.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/glitter-heart-square-frame-valentines-day/84a05810-e04d-42de-9f27-aa4345062042.eps", "MOTIF"),
    ("DOWNLOADS 12-2025/gold-glitter-heart-frame-luxury-shimmer-heart-shape-border/cb072975-e986-418d-98f4-7671b239c4a9.eps", "MOTIF"),
    ("DOWNLOADS 12-2025/hand-drawn-candies-pattern/4866.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/hand-drawn-christmas-season-pattern-design-with-presents/9707607.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/hand-drawn-colorless-fruit-vegetable-background/2258766.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/hand-drawn-picnic-food-pattern/55838-O8JMCR-917.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/honey-thin-line-vector-seamless-pattern/56.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/intertwined-flowing-line-art-pattern/c55db16d-4d1e-483b-adf0-46e0a59f5335.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/isolated-gardenia-flower-line-art-with-leaves-element/11_okt_8.eps", "ILLUSTRATION"),
    ("DOWNLOADS 12-2025/luxury-pattern-design-seamless-textile-printing-digital-printing-banner-poster-background-vector/pattern_design_2551796.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/modern-geometric-luxury-background-with-golden-hexagons-honeycomb-yellow/180c381c-0f52-47e1-ad71-6d2ee9c3d54a.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/realistic-silver-stars-background/8251341.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/red-rose-flower-vector-illustration(1)/4d45b476-92c9-475e-ab94-ce281349c1e4.eps", "ILLUSTRATION"),
    ("DOWNLOADS 12-2025/red-rose-flower-vector-illustration/bbf846e7-3542-4e7b-8f55-716d06f4a0ec.eps", "ILLUSTRATION"),
    ("DOWNLOADS 12-2025/romantic-doodle-ornaments/05.eps", "MOTIF"),
    ("DOWNLOADS 12-2025/seamless-background-theme-restaurant-menu/menu_07.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/seamless-decorative-background-decorative-lacy-element-texture-design/pale_geom.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/seamless-pattern-with-flat-cosmetics-icon/237.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/seamless-pattern-with-hand-drawn-gift-box/b84ed2ad-2dad-48ae-94a4-8ec592224f45.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/vector-christmas-gift-background-wallpaper/81020623-fad8-4179-9427-6f48e3f62269.eps", "BACKGROUND"),
    ("DOWNLOADS 12-2025/vector-pattern-with-cosmetics-perfumes-gray-background-cartoon-style-doodle/06b444a5-c193-4d52-b985-0721ea6eb992.eps", "PATTERN"),
    ("DOWNLOADS 12-2025/white-beige-vector-seamless-check-pattern-allover-pattern-ink-grunge-grid-hand-drawn-seamless-check-(1)/tdw6-28.eps", "PATTERN"),
    ("abstract-circles-pattern-design/OCVD5Q1.eps", "PATTERN"),
    ("abstract-retro-pattern-design-background/abstract_retro_pattern_design_background_2504.eps", "BACKGROUND"),
    ("botanical-floral-illustration/76269.eps", "ILLUSTRATION"),
    ("butterfly-silhouettes-pattern/04_27_butterflies.eps", "PATTERN"),
    ("celestial-constellations-astrological-golden-seamless-pattern-dark-background/9Z_cell.eps", "PATTERN"),
    ("circle-halftone-dotted-background/d5886001-bb75-45d3-922b-837dbcfb06f5.eps", "BACKGROUND"),
    ("colorful-background-with-different-stains/309710-P950PP-904.eps", "BACKGROUND"),
    ("cute-baby-bear-pattern-style-flat-lines/59.eps", "PATTERN"),
    ("cute-bear-face-cartoon-doodle-pattern/248.eps", "PATTERN"),
    ("cute-hand-drawn-ribbons/08.eps", "MOTIF"),
    ("cute-pastel-galaxy-space-pattern-design-vector-seamless-design-illustration/celestial_pattern_07.eps", "PATTERN"),
    ("damask-seamless-3d-paper-art-cross-ribbon-flower/1340.eps", "PATTERN"),
    ("doodle-bows-pattern-transparent-background-festive-pattern-packaging-design/231118valentinespattern2.eps", "PATTERN"),
)


class CuratedExpansionError(ValueError):
    pass


def _sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def _physical(root, relative):
    """The committed path is the record's identity; the Day 6 migration manifest says where the bytes live now."""
    from apps.ire.materials_paths import resolve_material_file, MaterialPathError
    try:
        return resolve_material_file((root / relative).resolve(), repo_root=root)
    except MaterialPathError as exc:
        raise CuratedExpansionError(f"curated source migration invalid: {relative}") from exc


def build_curated_expansion_manifest(repository_root=None):
    root = Path(repository_root or Path(settings.BASE_DIR).parent).resolve()
    entries = []
    for index, (filename, family, language, packaging) in enumerate(
            HISTORICAL_SELECTIONS):
        relative = normalize_relative_path(
            f"materials/historical AI production designs/{filename}")
        path = _physical(root, relative)
        if not path.is_file():
            raise CuratedExpansionError(f"missing curated historical source: {relative}")
        entries.append({
            "stable_source_key": f"dip1b-exp-historical:{index:02d}",
            "record_type": "HISTORICAL_DESIGN",
            "dataset_id": HISTORICAL_DATASET_ID,
            "source": {"root": "repository", "path": relative,
                       "sha256": _sha(path), "source_type": "FILE",
                       "media_type": "application/pdf"},
            "evidence_locator": {"schema_version": "source_file/1.0",
                                 "value": {"path": relative}},
            "selection": {
                "product_family": family, "design_language": language,
                "packaging_format": packaging, "era": "2025-2026-production",
                "criteria": ["business_value", "format_coverage", "low_duplication",
                             "layout_and_typography_reference_value"],
            },
            "technical": {"format": "AI_PDF_COMPATIBLE", "page_count": 1,
                          "audit_status": "REVIEW_REQUIRED",
                          "machine_classification_confidence": 0.6},
            "reference_memory_policy": "REFERENCE_MEMORY_ONLY",
        })
    for index, (suffix, kind) in enumerate(ASSET_SELECTIONS):
        relative = normalize_relative_path(f"materials/DOWNLOADE 2026/{suffix}")
        path = _physical(root, relative)
        if not path.is_file():
            raise CuratedExpansionError(f"missing curated design asset: {relative}")
        entries.append({
            "stable_source_key": f"dip1b-exp-asset-source:{index:03d}",
            "record_type": "DESIGN_ASSET_CANDIDATE",
            "dataset_id": DIP1B_CURATED_ASSET_EXPANSION_DATASET,
            "candidate_key": f"dip1b-exp-asset:{index:03d}",
            "source": {"root": "repository", "path": relative,
                       "sha256": _sha(path), "source_type": "FILE",
                       "media_type": "application/postscript"},
            "evidence_locator": {"schema_version": "source_file/1.0",
                                 "value": {"path": relative}},
            "selection": {
                "asset_kind": kind,
                "criteria": ["brand_neutral_graphic", "design_language_diversity",
                             "vector_format", "review_value", "low_duplication"],
                "third_party_contamination": "NO_KNOWN_LOGO_DETECTED_BY_BOUNDED_SELECTION",
                "rights_warning": "THIRD_PARTY_RIGHTS_UNREVIEWED",
            },
            "technical": {
                "representation": "VECTOR",
                "readiness": "TECHNICALLY_USABLE_WITH_CAVEATS",
                "extraction_state": "WHOLE_SOURCE_ISOLATED",
                "parser_identifier": "bbrose.curated.vector_source",
                "parser_version": "1.0",
            },
        })
    document = {
        "schema_version": MANIFEST_SCHEMA, "manifest_id": MANIFEST_ID,
        "generator": {"identifier": GENERATOR_IDENTIFIER,
                      "version": GENERATOR_VERSION},
        "datasets": [HISTORICAL_DATASET_ID, DIP1B_CURATED_ASSET_EXPANSION_DATASET],
        "selection_scope": {
            "historical_designs_added": 6, "design_assets_added": 53,
            "fonts_added": 0, "brand_candidates_added": 0,
            "full_corpus_scan_authorized": False,
            "test_only_sources_authorized": False,
            "operational_permission_effect": "NONE",
        },
        "entries": entries,
    }
    raw = canonical_bytes(document)
    return document, raw, hashlib.sha256(raw).hexdigest()


def validate_curated_expansion_manifest(path=DEFAULT_MANIFEST_PATH):
    path = Path(path)
    try:
        raw = path.read_bytes()
        document = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CuratedExpansionError("curated expansion manifest is unavailable") from exc
    expected, expected_raw, expected_hash = build_curated_expansion_manifest()
    if raw != expected_raw or document != expected:
        raise CuratedExpansionError("curated expansion manifest is not deterministic")
    entries = document["entries"]
    historical = [row for row in entries if row["record_type"] == "HISTORICAL_DESIGN"]
    assets = [row for row in entries if row["record_type"] == "DESIGN_ASSET_CANDIDATE"]
    paths = [row["source"]["path"] for row in entries]
    if (len(entries) != 59 or len(historical) != 6 or len(assets) != 53
            or len(set(paths)) != 59
            or len({row["stable_source_key"] for row in entries}) != 59
            or any(any("test" in component.lower() for component in Path(path).parts)
                   for path in paths)
            or any("logo" in path.lower() for path in paths)):
        raise CuratedExpansionError("curated expansion exact scope is invalid")
    return {"document": document, "raw": raw, "sha256": expected_hash,
            "historical": historical, "assets": assets}
