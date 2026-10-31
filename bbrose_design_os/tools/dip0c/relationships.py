"""Relationship edges (DIP-0C2c).

An edge is **evidence, not a verdict**. A pair may carry SEVERAL hypotheses at
once (a colorway is also a format variant, etc.), each with its own evidence and
confidence, and the human field is always blank.

Two rules the whole slice rests on:

1. **A candidate edge is never created from a source edge alone.** Shared filename,
   folder, package, visual style or family membership are *evidence* recorded on an
   edge — they never, by themselves, make two candidates equivalent. Perceptual or
   exact evidence is required to propose visual equivalence.
2. **Information content overrides hash distance.** A blank or near-uniform image
   collides with every other blank image; such pairs are capped at
   `REVIEW_REQUIRED` no matter how small the Hamming distance is.
"""
from __future__ import annotations

from . import config as C
from . import phash

PARSER = f"{C.TOOL_NAME}.relationships/{C.TOOL_VERSION}"


def edge(a_id: str, b_id: str, *, level: str, hypotheses: list[dict],
         evidence: list[str], confidence: float, **extra) -> dict:
    return {
        "level": level,                      # "source" | "candidate"
        "a": a_id,
        "b": b_id,
        "hypotheses": hypotheses,            # may be MORE THAN ONE
        "primary": (max(hypotheses, key=lambda h: h["confidence"])["relationship"]
                    if hypotheses else C.CAND_UNKNOWN_RELATIONSHIP),
        "evidence": list(evidence),
        "confidence": round(float(confidence), 3),
        "human_confirmed_relationship": None,   # never machine-set
        "parser": PARSER,
        "config_fingerprint": phash.CONFIG_FP,
        **extra,
    }


def hypothesis(rel: str, confidence: float, evidence: list[str]) -> dict:
    if rel not in C.CANDIDATE_RELATIONSHIPS and rel not in C.SOURCE_RELATIONSHIPS:
        raise ValueError(f"unknown relationship: {rel!r}")
    return {"relationship": rel, "confidence": round(float(confidence), 3),
            "evidence": list(evidence)}


def _best_transform(ha: dict, hb: dict) -> tuple[str, int, int]:
    """Compare A's stored orientation against every transform of B.
    Returns (transform, dhash_distance, phash_distance) for the best match."""
    best = (C.XF_IDENTITY, 64, 64)
    for xf, v in hb["variants"].items():
        dd = phash.hamming(ha["dhash"], v["dhash"])
        dp = phash.hamming(ha["phash"], v["phash"])
        if max(dd, dp) < max(best[1], best[2]):
            best = (xf, dd, dp)
    return best


def compare_candidates(a: dict, b: dict) -> dict | None:
    """`a`/`b` are candidate records carrying `hash` (from phash.hash_image),
    `color_sig`, dimensions, source format and collection info.

    Returns an edge, or None when the pair is unrelated by every signal.
    """
    ha, hb = a.get("hash"), b.get("hash")

    # --- EPS (and anything unhashable): source evidence only ------------------
    if ha is None or hb is None:
        return _unhashable_edge(a, b)

    xf, dd, dp = _best_transform(ha, hb)
    agree = max(dd, dp)                       # BOTH must agree for "strong"
    ev = [f"dHash distance {dd}, pHash distance {dp} (best transform: {xf})",
          f"thresholds: strong <= {C.HAMMING_STRONG}, "
          f"review <= {C.HAMMING_REVIEW}"]

    # --- information guards OVERRIDE distance --------------------------------
    weak = ha["information"]["weak_evidence"] or hb["information"]["weak_evidence"]
    cap = min(ha["information"]["confidence_cap"], hb["information"]["confidence_cap"])
    if weak:
        ev.append("WEAK VISUAL EVIDENCE — hash distance is not trustworthy here: "
                  + "; ".join(ha["information"]["reasons"]
                              + hb["information"]["reasons"]))

    # Perceptual hashes are NOT crop-invariant: a genuine crop legitimately fails
    # the distance test. So a far-apart pair is dropped only when there is also no
    # silhouette match and no source evidence to justify a *hypothesis*. Source
    # evidence can support a CROP/SCALE hypothesis for review — it can never, on
    # its own, produce a near-duplicate or visual-equivalence claim (guarded below,
    # where `strong` requires the hashes).
    src_ev = _source_evidence(a, b)
    has_source_evidence = (src_ev["same_folder_or_package"]
                           or src_ev["same_filename_stem"])
    if (agree > C.HAMMING_REVIEW and not _shape_match(ha, hb)
            and not has_source_evidence):
        return None                            # unrelated by every signal

    # --- transform-only matches are explicit, never silent -------------------
    transform_only = xf != C.XF_IDENTITY and agree <= C.HAMMING_REVIEW
    if transform_only:
        kind = "MIRRORED" if xf == C.XF_MIRRORED else "ROTATED"
        ev.append(f"{kind}: the pair matches ONLY under transform {xf} — reported "
                  "as an explicit transform relationship, not a silent duplicate")

    hyps: list[dict] = []
    strong = (dd <= C.HAMMING_STRONG and dp <= C.HAMMING_STRONG) and not weak
    shape_ok = _shape_match(ha, hb)
    if shape_ok:
        ev.append(f"silhouette match (shape Hamming "
                  f"{phash.hamming(ha['shape'], hb['shape'])} <= "
                  f"{C.SILHOUETTE_SIMILAR_MAX})")

    if strong and dd == 0 and dp == 0 and xf == C.XF_IDENTITY:
        hyps.append(hypothesis(C.CAND_EXACT_VISUAL_DUPLICATE, 0.9,
                               ["dHash and pHash both identical"]))
    elif strong:
        conf = 0.75 if not transform_only else 0.6
        hyps.append(hypothesis(C.CAND_LIKELY_NEAR_DUPLICATE, conf,
                               [f"both hashes agree within {C.HAMMING_STRONG}"]
                               + ([f"under transform {xf}"] if transform_only
                                  else [])))
    elif shape_ok and agree > C.HAMMING_REVIEW:
        # the silhouettes agree while the grayscale hashes do not: consistent with
        # the SAME artwork over a different background. Kept on the graph for
        # review — never promoted to a duplicate, because the pixels do differ.
        hyps.append(hypothesis(
            C.CAND_UNKNOWN_RELATIONSHIP, min(0.4, cap),
            [f"{C.REL_REVIEW_REQUIRED}: silhouettes match but grayscale hashes "
             f"differ (dHash {dd}, pHash {dp}) — consistent with the same artwork "
             "on a different background"]))
    elif agree <= C.HAMMING_REVIEW or weak:
        hyps.append(hypothesis(C.CAND_UNKNOWN_RELATIONSHIP,
                               min(0.35, cap),
                               [f"{C.REL_REVIEW_REQUIRED}: hashes are close but "
                                "not conclusive" if not weak
                                else f"{C.REL_REVIEW_REQUIRED}: weak visual "
                                     "evidence overrides hash distance"]))

    # --- independent hypotheses (a pair may carry several) -------------------
    hyps += _variant_hypotheses(a, b, ha, hb, dd, dp, weak)

    if not hyps:
        return None
    confidence = min(max(h["confidence"] for h in hyps), cap)
    return edge(a["candidate_id"], b["candidate_id"], level="candidate",
                hypotheses=hyps, evidence=ev, confidence=confidence,
                dhash_distance=dd, phash_distance=dp, best_transform=xf,
                transform_only_match=transform_only,
                exact_sha_match=(a["source_sha256"] == b["source_sha256"]
                                 and a["source_sha256"] is not None),
                weak_visual_evidence=weak,
                source_evidence=src_ev)


def _containment(ha: dict, hb: dict) -> dict | None:
    """Does one image appear as a SUB-REGION of the other?

    A crop of an image is approximately one of the parent's regions, so the crop's
    whole-image hash should match one of the parent's region hashes. This is the
    only positive visual evidence a crop can have — the whole-image distance cannot
    provide it, because perceptual hashes are not crop-invariant.

    Containment is a WEAKER signal than a whole-image match, so it demands STRONGER
    agreement: both dHash and pHash must fall within `HAMMING_STRONG`. A single
    lenient dHash is not enough — on flat-background artwork most gradient bits are
    zero, and two unrelated white-ish regions collided at Hamming 8.
    """
    best = None
    for parent, child, direction in ((ha, hb, "b_in_a"), (hb, ha, "a_in_b")):
        for name, rh in (parent.get("regions") or {}).items():
            dd = phash.hamming(child["dhash"], rh["d"])
            dp = phash.hamming(child["phash"], rh["p"])
            agree = max(dd, dp)
            if agree <= C.HAMMING_STRONG and (best is None
                                              or agree < best["agree"]):
                best = {"region": name, "distance": dd, "phash_distance": dp,
                        "agree": agree, "direction": direction}
    return best


def _shape_match(ha: dict, hb: dict) -> bool:
    """Same silhouette → the 'same logo on white vs on black' case, whose grayscale
    hashes are nearly inverted. Only trusted when BOTH silhouettes carry actual
    shape information (an all-on or all-off mask matches everything)."""
    if not (ha.get("silhouette_informative") and hb.get("silhouette_informative")):
        return False
    return phash.hamming(ha["shape"], hb["shape"]) <= C.SILHOUETTE_SIMILAR_MAX


def _variant_hypotheses(a, b, ha, hb, dd, dp, weak) -> list[dict]:
    out: list[dict] = []
    pal = phash.palette_distance(a["color_sig"], b["color_sig"])
    # BOTH hashes must agree — the same rule as for a strong near-duplicate. Using
    # min() here let a single agreeing hash carry the pair while the other strongly
    # disagreed, which produced 24 spurious "colorways" between different stickers
    # on one sheet.
    geom_close = max(dd, dp) <= C.HAMMING_REVIEW
    ar_a, ar_b = ha["aspect_ratio"], hb["aspect_ratio"]
    aspect_close = (ar_a and ar_b
                    and abs(ar_a - ar_b) / max(ar_a, ar_b) <= C.ASPECT_SIMILAR_TOL)
    da, db = ha["source_dimensions"], hb["source_dimensions"]
    long_a, long_b = max(da["w"], da["h"]), max(db["w"], db["h"])
    ratio = (max(long_a, long_b) / max(min(long_a, long_b), 1))
    silhouette = _shape_match(ha, hb)
    same_pkg = _same_package(a, b)

    # COLORWAY: similar geometry AND materially different palette AND similar
    # silhouette AND similar dimensions AND package/naming evidence.
    if (geom_close and not weak and pal >= C.PALETTE_DIFFERENT_MIN
            and aspect_close and (silhouette or same_pkg)):
        out.append(hypothesis(
            C.CAND_POSSIBLE_COLORWAY, 0.5,
            [f"geometry is close (dHash {dd}/pHash {dp}) but the palette differs "
             f"materially (distance {pal:.2f} >= {C.PALETTE_DIFFERENT_MIN})",
             f"similar aspect ratio; silhouette_match={silhouette}, "
             f"same_package={same_pkg}"]))

    # SCALE VARIANT: same aspect, same content, materially different dimensions.
    if geom_close and aspect_close and ratio >= C.SCALE_VARIANT_MIN_RATIO:
        out.append(hypothesis(
            C.CAND_POSSIBLE_SCALE_VARIANT, 0.45,
            [f"same aspect ratio, long edge {long_a}px vs {long_b}px "
             f"(x{ratio:.2f})"]))

    # CROP VARIANT: requires POSITIVE visual containment — one image's whole-image
    # hash matching a sub-region hash of the other. Perceptual hashes are not
    # crop-invariant, so the whole-image distance is useless here; but a shared
    # folder plus a different aspect ratio is NOT visual evidence and must never
    # produce a crop claim (it would relate two unrelated images that merely sat in
    # the same download folder).
    cont = _containment(ha, hb)
    if cont:
        out.append(hypothesis(
            C.CAND_POSSIBLE_CROP_VARIANT, 0.45,
            [f"containment: one image matches the {cont['region']!r} region of the "
             f"other (dHash {cont['distance']})",
             "a crop is proposed ONLY from this positive visual containment "
             "signal, never from shared folder/package or aspect alone",
             f"aspect ratios {ar_a} vs {ar_b}"]))

    # FORMAT VARIANT: same artwork carried in different source formats.
    if geom_close and a["source_format"] != b["source_format"]:
        out.append(hypothesis(
            C.CAND_POSSIBLE_FORMAT_VARIANT, 0.5,
            [f"visually close across formats {a['source_format']} vs "
             f"{b['source_format']}",
             "formats differ in editability; readiness is NOT shared"]))

    return out


def _same_package(a, b) -> bool:
    return a["source_folder"] == b["source_folder"]


def _source_evidence(a, b) -> dict:
    """Recorded as CONTEXT on a candidate edge. It never, by itself, creates one."""
    return {
        "same_folder_or_package": _same_package(a, b),
        "same_filename_stem": a["filename_stem"] == b["filename_stem"],
        "same_source_file": a["source_path"] == b["source_path"],
        "note": "source-level facts are evidence only; they never establish "
                "candidate equivalence on their own",
    }


def _unhashable_edge(a, b) -> dict | None:
    """EPS (and anything else we cannot rasterise) has no perceptual hash, so a
    candidate relationship CANNOT be asserted. We record the pair only when there
    is real source evidence, and we keep it UNKNOWN."""
    src = _source_evidence(a, b)
    exact = (a["source_sha256"] == b["source_sha256"]
             and a["source_sha256"] is not None
             and a["source_path"] != b["source_path"])
    if not (exact or src["same_filename_stem"] or src["same_folder_or_package"]):
        return None
    ev = ["no perceptual hash available for at least one side (EPS previews are "
          "not decodable and would not represent editable objects anyway)",
          "relationship rests on source evidence ONLY and stays UNKNOWN at "
          "candidate level"]
    conf = 0.3 if exact else 0.2
    hyps = [hypothesis(C.CAND_UNKNOWN_RELATIONSHIP, conf,
                       ["source evidence only; visual equivalence not established"])]
    return edge(a["candidate_id"], b["candidate_id"], level="candidate",
                hypotheses=hyps, evidence=ev, confidence=conf,
                dhash_distance=None, phash_distance=None, best_transform=None,
                transform_only_match=False, exact_sha_match=exact,
                weak_visual_evidence=True, source_evidence=src,
                perceptual_comparison="UNAVAILABLE_REQUIRES_TOOL")
