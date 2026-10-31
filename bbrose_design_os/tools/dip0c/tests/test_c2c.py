"""DIP-0C2c tests — duplicates, perceptual similarity, families, canonical.

The pilot contains no true visual duplicate CANDIDATE pair, so every relationship
path is proven here with synthetic fixtures, plus false-positive controls. The
load-bearing invariants: information content overrides hash distance, transform
matches are explicit, candidate equivalence is never inferred from source facts,
weak bridges split components, family membership propagates nothing, and canonical
assets are nominated but never selected.
"""
from __future__ import annotations

import io
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from tools.dip0c import canonical, config as C, families, phash
from tools.dip0c import relationships as R
from tools.dip0c import run_c2c


# --- image fixtures ---------------------------------------------------------
def _art(n=256, color="red", seed=0):
    """Structured artwork with real information content."""
    im = Image.new("RGB", (n, n), "white")
    d = ImageDraw.Draw(im)
    rng = np.random.default_rng(seed)
    for i in range(12):
        x, y = rng.integers(10, n - 60, 2)
        d.ellipse([int(x), int(y), int(x) + 50, int(y) + 40], fill=color)
        d.rectangle([int(x) - 5, int(y) + 30, int(x) + 20, int(y) + 55],
                    fill="black")
    return im


def _blank(n=256, shade=200):
    return Image.new("RGB", (n, n), (shade, shade, shade))


def _logo_rgba(n=256):
    # colours are distinct from BOTH white and black backgrounds. (A logo element
    # that matches the background colour genuinely vanishes from the silhouette —
    # a real limitation, recorded in c2c_known_limitations.md, not a fixture to
    # paper over here.)
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([60, 60, 200, 200], fill=(220, 30, 30, 255))
    d.rectangle([100, 100, 160, 190], fill=(100, 150, 230, 255))
    return im


def _logo_on(bg, n=256):
    base = Image.new("RGBA", (n, n), bg)
    base.alpha_composite(_logo_rgba(n))
    return base.convert("RGB")


def _recompress(im, quality=35):
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality)
    buf.seek(0)
    return Image.open(buf)


def _cand(cid, im, *, fmt=".png", folder="pkg", stem="a.png", sha="sha1"):
    return {
        "candidate_id": cid,
        "source_path": f"{folder}/{stem}",
        "source_sha256": sha,
        "source_format": fmt,
        "source_folder": folder,
        "filename_stem": stem,
        "hash": phash.hash_image(im) if im is not None else None,
        "color_sig": phash.color_signature(im) if im is not None else None,
        "readiness": C.READY_TECHNICALLY_READY,
        "isolation": 0.5,
        "jpeg_shell": False,
        "collection": None,
    }


def _rels(edge):
    return {h["relationship"] for h in edge["hypotheses"]} if edge else set()


# --- exact SHA duplicate (source level) -------------------------------------
def test_exact_sha_duplicate_source_edge():
    srcs = [{"relative_path": "a/x.eps", "sha256": "S", "format": ".eps",
             "folder": "a", "filename": "x.eps", "hash": None},
            {"relative_path": "b/x.eps", "sha256": "S", "format": ".eps",
             "folder": "b", "filename": "x.eps", "hash": None}]
    edges = families.source_edges(srcs)
    exact = [e for e in edges
             if any(h["relationship"] == C.SRC_EXACT_FILE_DUPLICATE
                    for h in e["hypotheses"])]
    assert len(exact) == 1 and exact[0]["confidence"] == 1.0


def test_cross_format_is_never_an_exact_duplicate():
    """An .ai, .eps and .jpg may look alike; they are never exact duplicates."""
    srcs = [{"relative_path": "p/x.ai", "sha256": "A", "format": ".ai",
             "folder": "p", "filename": "x.ai", "hash": None},
            {"relative_path": "p/x.jpg", "sha256": "B", "format": ".jpg",
             "folder": "p", "filename": "x.jpg", "hash": None}]
    edges = families.source_edges(srcs)
    rels = {h["relationship"] for e in edges for h in e["hypotheses"]}
    assert C.SRC_EXACT_FILE_DUPLICATE not in rels
    assert C.SRC_ALTERNATE_FORMAT_SOURCE in rels


# --- near-duplicates --------------------------------------------------------
def test_resized_image_is_near_duplicate():
    im = _art()
    e = R.compare_candidates(_cand("a", im),
                             _cand("b", im.resize((128, 128)), stem="b.png"))
    assert C.CAND_LIKELY_NEAR_DUPLICATE in _rels(e) or \
        C.CAND_EXACT_VISUAL_DUPLICATE in _rels(e)


def test_recompressed_image_is_near_duplicate():
    im = _art()
    e = R.compare_candidates(_cand("a", im),
                             _cand("b", _recompress(im), stem="b.jpg"))
    assert C.CAND_LIKELY_NEAR_DUPLICATE in _rels(e) or \
        C.CAND_EXACT_VISUAL_DUPLICATE in _rels(e)


def test_identical_image_is_exact_visual_duplicate():
    im = _art()
    e = R.compare_candidates(_cand("a", im), _cand("b", im.copy(), stem="b.png"))
    assert C.CAND_EXACT_VISUAL_DUPLICATE in _rels(e)


# --- false-positive control -------------------------------------------------
def test_unrelated_images_produce_no_edge():
    a, b = _art(seed=1, color="red"), _art(seed=99, color="blue")
    e = R.compare_candidates(_cand("a", a), _cand("b", b, folder="other",
                                                  stem="b.png", sha="sha2"))
    assert e is None or C.CAND_LIKELY_NEAR_DUPLICATE not in _rels(e)


# --- information-content guards OVERRIDE hash distance ----------------------
def test_blank_images_never_become_confident_near_duplicates():
    """Two blanks have IDENTICAL hashes — the guard must still refuse."""
    a, b = _blank(shade=200), _blank(shade=201)
    ha, hb = phash.hash_image(a), phash.hash_image(b)
    assert phash.hamming(ha["dhash"], hb["dhash"]) <= C.HAMMING_STRONG
    assert ha["information"]["weak_evidence"] is True
    e = R.compare_candidates(_cand("a", a), _cand("b", b, stem="b.png"))
    assert C.CAND_LIKELY_NEAR_DUPLICATE not in _rels(e)
    assert C.CAND_EXACT_VISUAL_DUPLICATE not in _rels(e)
    assert e["weak_visual_evidence"] is True
    assert e["confidence"] <= C.WEAK_EVIDENCE_CONFIDENCE_CAP


def test_mostly_transparent_image_is_weak_evidence():
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([120, 120, 136, 136], fill=(255, 0, 0, 255))
    h = phash.hash_image(im)
    assert h["information"]["weak_evidence"] is True
    assert h["information"]["confidence_cap"] == C.WEAK_EVIDENCE_CONFIDENCE_CAP


def test_transparent_png_with_real_content_is_strong_evidence():
    h = phash.hash_image(_logo_rgba())
    assert h["has_alpha"] is True
    assert h["information"]["weak_evidence"] is False
    assert h["silhouette_informative"] is True


# --- transforms are explicit, never silent ----------------------------------
def test_mirrored_match_is_reported_as_transform_evidence():
    im = _art(seed=3)
    mirrored = im.transpose(Image.FLIP_LEFT_RIGHT)
    e = R.compare_candidates(_cand("a", im), _cand("b", mirrored, stem="b.png"))
    assert e is not None
    assert e["best_transform"] == C.XF_MIRRORED
    assert e["transform_only_match"] is True
    assert any("MIRRORED" in x for x in e["evidence"])


def test_rotated_match_is_reported_as_transform_evidence():
    im = _art(seed=4)
    rot = im.transpose(Image.ROTATE_180)
    e = R.compare_candidates(_cand("a", im), _cand("b", rot, stem="b.png"))
    assert e is not None
    assert e["best_transform"] == C.XF_ROT180
    assert e["transform_only_match"] is True
    assert any("ROTATED" in x for x in e["evidence"])


# --- logo on different backgrounds ------------------------------------------
def test_same_logo_on_different_backgrounds_is_linked_by_silhouette():
    white, black = _logo_on((255, 255, 255, 255)), _logo_on((0, 0, 0, 255))
    ha, hb = phash.hash_image(white), phash.hash_image(black)
    # the grayscale hashes are NOT close (the background inverted) ...
    assert phash.hamming(ha["phash"], hb["phash"]) > C.HAMMING_STRONG
    # ... but the silhouettes are identical, which is what rescues the link
    assert phash.hamming(ha["shape"], hb["shape"]) <= C.SILHOUETTE_SIMILAR_MAX
    e = R.compare_candidates(_cand("a", white), _cand("b", black, stem="b.png"))
    assert e is not None, "a shape match must keep the pair on the graph"


# --- colorway / crop / format / scale hypotheses ----------------------------
def test_true_colorway_is_proposed():
    a, b = _art(seed=7, color="red"), _art(seed=7, color="blue")
    e = R.compare_candidates(_cand("a", a), _cand("b", b, stem="b.png"))
    assert e is not None
    assert C.CAND_POSSIBLE_COLORWAY in _rels(e)


def test_colorway_needs_more_than_visual_similarity():
    """Same geometry AND same palette -> a duplicate, NOT a colorway."""
    im = _art(seed=7, color="red")
    e = R.compare_candidates(_cand("a", im), _cand("b", im.copy(), stem="b.png"))
    assert C.CAND_POSSIBLE_COLORWAY not in _rels(e)


def test_scale_variant_is_proposed():
    im = _art(seed=8)
    big = im.resize((640, 640))
    e = R.compare_candidates(_cand("a", im), _cand("b", big, stem="b.png"))
    assert C.CAND_POSSIBLE_SCALE_VARIANT in _rels(e)


def test_format_variant_is_proposed_across_formats():
    im = _art(seed=10)
    e = R.compare_candidates(_cand("a", im, fmt=".ai"),
                             _cand("b", _recompress(im), fmt=".jpg",
                                   stem="b.jpg"))
    assert C.CAND_POSSIBLE_FORMAT_VARIANT in _rels(e)
    hyp = next(h for h in e["hypotheses"]
               if h["relationship"] == C.CAND_POSSIBLE_FORMAT_VARIANT)
    assert any("readiness is NOT shared" in x for x in hyp["evidence"])


# --- EPS: no perceptual comparison ------------------------------------------
def test_eps_comparison_is_source_evidence_only():
    eps_a = _cand("a", None, fmt=".eps", folder="p", stem="x.eps", sha="S")
    eps_b = _cand("b", None, fmt=".eps", folder="q", stem="x.eps", sha="S")
    e = R.compare_candidates(eps_a, eps_b)
    assert e is not None
    assert _rels(e) == {C.CAND_UNKNOWN_RELATIONSHIP}
    assert e["perceptual_comparison"] == "UNAVAILABLE_REQUIRES_TOOL"
    assert e["dhash_distance"] is None


def test_unrelated_images_in_the_SAME_folder_get_no_crop_claim():
    """The path the pilot actually hits, and the one that produced 3 false
    'crop variants': two UNRELATED images, different aspect ratios, SAME folder.

    Shared folder + differing aspect is NOT visual evidence. A crop claim requires
    positive containment; without it, no crop hypothesis may be emitted.
    """
    a = _art(seed=21, color="red")
    b = _art(seed=88, color="green").crop((0, 0, 256, 110))   # different aspect
    e = R.compare_candidates(
        _cand("a", a, folder="samepkg", stem="a.png", sha="S1"),
        _cand("b", b, folder="samepkg", stem="b.png", sha="S2"))
    assert C.CAND_POSSIBLE_CROP_VARIANT not in _rels(e)
    assert C.CAND_LIKELY_NEAR_DUPLICATE not in _rels(e)
    assert C.CAND_EXACT_VISUAL_DUPLICATE not in _rels(e)


def test_crop_requires_positive_containment_evidence():
    """A REAL crop (a sub-region of the same artwork) is corroborated by matching
    one of the parent's region hashes."""
    im = _art(seed=9)
    top = im.crop((0, 0, 256, 128))            # exactly the parent's 'top' region
    e = R.compare_candidates(_cand("a", im), _cand("b", top, stem="b.png"))
    assert e is not None
    assert C.CAND_POSSIBLE_CROP_VARIANT in _rels(e)
    hyp = next(h for h in e["hypotheses"]
               if h["relationship"] == C.CAND_POSSIBLE_CROP_VARIANT)
    assert any("containment" in x for x in hyp["evidence"])
    assert any("never from shared folder/package" in x for x in hyp["evidence"])


def test_candidate_equivalence_is_never_inferred_from_source_facts():
    """Same folder + same stem, but visually UNRELATED -> no equivalence."""
    a, b = _art(seed=11, color="red"), _art(seed=77, color="green")
    e = R.compare_candidates(
        _cand("a", a, folder="pkg", stem="x.png", sha="S"),
        _cand("b", b, folder="pkg", stem="x.png", sha="S"))
    assert C.CAND_LIKELY_NEAR_DUPLICATE not in _rels(e)
    assert C.CAND_EXACT_VISUAL_DUPLICATE not in _rels(e)


# --- weak bridges split components ------------------------------------------
def test_weak_bridge_splits_the_component():
    """A~B (strong), B~C (strong), and a WEAK sole connector C~D must not fuse D
    into the family."""
    def e(a, b, conf):
        return R.edge(a, b, level="candidate",
                      hypotheses=[R.hypothesis(C.CAND_LIKELY_NEAR_DUPLICATE, conf,
                                               ["synthetic"])],
                      evidence=["synthetic"], confidence=conf)
    edges = [e("A", "B", 0.9), e("B", "C", 0.9), e("C", "D", 0.62)]
    res = families.build_components(["A", "B", "C", "D"], edges)
    assert len(res["weak_bridges"]) == 1
    assert res["weak_bridges"][0]["action"] == "COMPONENT_SPLIT"
    comps = {frozenset(c) for c in res["components"]}
    assert frozenset({"A", "B", "C"}) in comps
    assert not any("D" in c and "A" in c for c in res["components"])


def test_strong_chain_is_not_split():
    def e(a, b, conf):
        return R.edge(a, b, level="candidate",
                      hypotheses=[R.hypothesis(C.CAND_LIKELY_NEAR_DUPLICATE, conf,
                                               ["synthetic"])],
                      evidence=["synthetic"], confidence=conf)
    res = families.build_components(["A", "B", "C"],
                                    [e("A", "B", 0.9), e("B", "C", 0.9)])
    assert res["weak_bridges"] == []
    assert sorted(res["components"][0]) == ["A", "B", "C"]


# --- determinism ------------------------------------------------------------
def test_hashes_are_deterministic():
    im = _art(seed=12)
    a, b = phash.hash_image(im), phash.hash_image(im.copy())
    assert a["dhash"] == b["dhash"] and a["phash"] == b["phash"]
    assert a["shape"] == b["shape"]
    assert a["config_fingerprint"] == b["config_fingerprint"] == phash.CONFIG_FP


# --- canonical: nominated, never selected -----------------------------------
def test_canonical_is_nominated_never_selected():
    by_id = {
        "v": {"candidate_id": "v", "readiness": C.READY_TECHNICALLY_READY,
              "source_format": ".ai", "isolation": 0.9, "source_sha256": "x",
              "jpeg_shell": False,
              "hash": {"source_dimensions": {"w": 3000, "h": 3000}}},
        "r": {"candidate_id": "r", "readiness": C.READY_REFERENCE_ONLY,
              "source_format": ".jpg", "isolation": 0.2, "source_sha256": "y",
              "jpeg_shell": False,
              "hash": {"source_dimensions": {"w": 300, "h": 300}}},
    }
    n = canonical.nominate(["v", "r"], by_id)
    assert n["nomination"] == C.POSTURE_CANONICAL_CANDIDATE
    assert n["nominated_candidate_id"] == "v"
    assert n["human_selected_canonical"] is None          # never machine-set
    assert n["score_breakdown"]["rights_contribution"] == 0
    assert n["rights_context"]["ownership"] == "unconfirmed"
    assert n["rights_context"]["retrieval"] is False


def test_rights_never_change_the_canonical_score():
    base = {"candidate_id": "x", "readiness": C.READY_TECHNICALLY_READY,
            "source_format": ".ai", "isolation": 0.5, "source_sha256": "s",
            "jpeg_shell": False,
            "hash": {"source_dimensions": {"w": 2500, "h": 2500}}}
    s1 = canonical._score(dict(base))
    s2 = canonical._score(dict(base, rights={"commercial_use": True},
                               license="APPROVED"))
    assert s1["total"] == s2["total"]      # rights are not an input, by design


# --- integration: the real pilot --------------------------------------------
@pytest.fixture(scope="module")
def recon():
    assert run_c2c.main() == 0
    return json.loads((C.OUT_REPORTS / "c2c_reconciliation.json")
                      .read_text(encoding="utf-8"))


def test_pilot_invariants_and_integrity(recon):
    assert all(recon["invariants"].values())
    assert recon["integrity"]["materials"]["unchanged"] is True
    assert recon["integrity"]["no_output_under_source"]["ok"] is True


def test_pilot_avoids_naive_all_pairs(recon):
    b = recon["blocking"]
    assert b["blocked_pairs"] < b["naive_pairs"]
    assert b["reduction"] > 0.0


def test_pilot_exact_duplicate_group_found(recon):
    assert recon["source_exact_duplicate_edges"] >= 1


def test_pilot_cross_format_family(recon):
    f = recon["cross_format_5955564_66_67"]
    assert set(f["members"]) == {"5955564.eps", "5955566.jpg", "5955567.ai"}
    # the .eps is not perceptually comparable
    assert f["members"]["5955564.eps"]["perceptually_hashable"] is False
    # the .ai and .jpg ARE visually near-identical at source level
    assert any(v["visually_near_identical"] for v in
               f["source_visual_corroboration"])
    # ...and readiness still did NOT propagate between members
    assert f["readiness_did_not_propagate"] is True
    assert f["readiness_per_member"]["5955567.ai"] == \
        ["NEEDS_VECTOR_RECONSTRUCTION"]
    assert f["readiness_per_member"]["5955564.eps"] == ["HEADER_ONLY_PARTIAL"]


def test_pilot_no_permission_propagation(recon):
    assert recon["invariants"]["no_rights_or_permissions_propagated"] is True
    assert recon["invariants"]["no_automatic_canonical_selection"] is True


def test_pilot_run_is_deterministic(recon):
    a = dict(recon)
    assert run_c2c.main() == 0
    b = json.loads((C.OUT_REPORTS / "c2c_reconciliation.json")
                   .read_text(encoding="utf-8"))
    for k in ("candidate_relationship_totals", "source_relationship_totals",
              "hypothesis_totals", "family_components", "component_sizes",
              "canonical_nominations", "weak_bridges_detected_and_split"):
        assert a[k] == b[k], f"{k} is not deterministic"
