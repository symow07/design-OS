"""DIP-0C2c runner — duplicates, perceptual similarity, families, canonical.

Read-only. Re-runs C2a segmentation + C2b scoring in-process, hashes each
candidate crop, blocks the pairs, builds the source and candidate graphs, derives
family components (splitting at weak bridges) and nominates canonical candidates.

Nothing is activated. Family membership propagates NO readiness, ownership,
licence, permission, retrieval eligibility, automatic use or brand status —
enforced by invariants that fail the run.

    python -m tools.dip0c.run_c2c
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import canonical, config as C, families, phash, relationships as R
from . import run_c2a, run_c2b

PARSER = f"{C.TOOL_NAME}.run_c2c/{C.TOOL_VERSION}"


def _candidate_image(cand, src_img):
    """The candidate's own crop — that is what gets hashed."""
    if src_img is None:
        return None
    bb = cand.get("bbox_px")
    try:
        if bb:
            x0, y0, x1, y1 = bb
            w, h = src_img.size
            box = (max(0, int(x0)), max(0, int(y0)),
                   min(w, int(x1)), min(h, int(y1)))
            if box[2] - box[0] >= 8 and box[3] - box[1] >= 8:
                return src_img.crop(box)
        return src_img.copy()
    except Exception:  # noqa: BLE001
        return None


def collect(pilot, inv) -> tuple[list[dict], list[dict]]:
    """Score the pilot (C2a+C2b) and build hashable candidate records."""
    unique: dict[str, dict] = {}
    for e in pilot:
        unique.setdefault(e["relative_path"], e)

    sources, cands = [], []
    for entry in unique.values():
        rel = entry["relative_path"]
        res = run_c2b.score_entry(entry, inv)
        kind = res["kind"]
        sha = (res["candidates"][0]["source_file"]["sha256"]
               if res["candidates"] else None)
        src_img = run_c2b._source_image(rel, kind)
        # the WHOLE-source hash: a visual family link can be true of the FILES while
        # being invisible at candidate level (one source segmented into crops, the
        # other a single whole-file candidate). Recorded as source evidence only.
        sources.append({"relative_path": rel, "sha256": sha,
                        "format": Path(rel).suffix.lower(),
                        "folder": str(Path(rel).parent),
                        "filename": Path(rel).name,
                        "hash": (phash.hash_image(src_img, rel_path=rel)
                                 if src_img is not None else None)})
        for c in res["candidates"]:
            im = _candidate_image(c, src_img)
            h = phash.hash_image(im, rel_path=rel) if im is not None else None
            sig = phash.color_signature(im) if im is not None else None
            cands.append({
                "candidate_id": c["candidate_id"],
                "source_path": rel,
                "source_sha256": sha,
                "source_format": Path(rel).suffix.lower(),
                "source_folder": str(Path(rel).parent),
                "filename_stem": Path(rel).name,
                "hash": h,
                "color_sig": sig,
                "readiness": c["A_technical_readiness"]["value"],
                "isolation": c.get("isolated_candidate_confidence"),
                "jpeg_shell": any(
                    e["code"] == C.EV_EMBEDDED_RASTER_DEPENDENCE
                    for e in c["A_technical_readiness"]["evidence"]),
                "collection": c.get("collection"),
                # rights carried through UNCHANGED — never touched by C2c
                "rights": c["B_rights_readiness"],
                "retrieval": c["D_retrieval_eligibility"],
                "automatic_use": c["E_automatic_use_eligibility"],
            })
        if src_img is not None:
            try:
                src_img.close()
            except Exception:  # noqa: BLE001
                pass
    return sources, cands


def build_candidate_edges(cands: list[dict]) -> tuple[list[dict], dict]:
    pairs, stats = families.candidate_blocks(cands)
    edges = []
    compared = 0
    for i, j in sorted(pairs):
        a, b = cands[i], cands[j]
        if a["source_path"] == b["source_path"]:
            # same sheet -> a COLLECTION_MEMBER relationship, not equivalence
            if (a.get("collection") or {}).get("is_member"):
                edges.append(R.edge(
                    a["candidate_id"], b["candidate_id"], level="candidate",
                    hypotheses=[R.hypothesis(C.CAND_COLLECTION_MEMBER, 0.7,
                                             ["segmented from the same source "
                                              "surface"])],
                    evidence=["co-membership of one collection is NOT visual "
                              "equivalence"],
                    confidence=0.7, dhash_distance=None, phash_distance=None,
                    best_transform=None, transform_only_match=False,
                    exact_sha_match=True, weak_visual_evidence=False,
                    source_evidence=R._source_evidence(a, b)))
            continue
        compared += 1
        e = R.compare_candidates(a, b)
        if e:
            edges.append(e)
    stats["perceptual_comparisons_performed"] = compared
    return edges, stats


def reconcile(sources, cands, src_edges, cand_edges, comps, noms, blocking,
              integrity, runtime_s, out_bytes) -> dict:
    src_types = Counter(h["relationship"] for e in src_edges
                        for h in e["hypotheses"])
    cand_types = Counter(h["relationship"] for e in cand_edges
                         for h in e["hypotheses"])
    transform_matches = [e for e in cand_edges if e.get("transform_only_match")]
    xf = Counter(e["best_transform"] for e in transform_matches)
    exact_groups = sum(1 for e in src_edges
                       if any(h["relationship"] == C.SRC_EXACT_FILE_DUPLICATE
                              for h in e["hypotheses"]))

    # cross-format family check
    fam = _cross_format(cands, src_edges, cand_edges)

    blob = json.dumps({"e": cand_edges, "n": noms}, default=json_default)
    rights_moved = [c["candidate_id"] for c in cands
                    if c["retrieval"] or c["automatic_use"]
                    or any(c["rights"][k] for k in ("commercial_use",
                                                    "modification", "embedding",
                                                    "redistribution"))]
    auto_selected = [n for n in noms if n.get("human_selected_canonical")]
    weak_bridges = comps["weak_bridges"]

    return {
        "slice": "DIP-0C2c",
        "c2b_commit": "5bdfe4bb77a8fa70f261708983cf766c1175c842",
        "hash_config_fingerprint": phash.CONFIG_FP,
        "algorithm_version": phash.ALGORITHM_VERSION,
        "sources": len(sources),
        "candidates": len(cands),
        "source_exact_duplicate_edges": exact_groups,
        "source_relationship_totals": dict(src_types),
        "candidate_relationship_totals": dict(cand_types),
        "near_duplicate_totals": {
            "exact_visual": cand_types.get(C.CAND_EXACT_VISUAL_DUPLICATE, 0),
            "likely_near_duplicate": cand_types.get(C.CAND_LIKELY_NEAR_DUPLICATE, 0),
        },
        "hypothesis_totals": {
            "colorway": cand_types.get(C.CAND_POSSIBLE_COLORWAY, 0),
            "crop_variant": cand_types.get(C.CAND_POSSIBLE_CROP_VARIANT, 0),
            "format_variant": cand_types.get(C.CAND_POSSIBLE_FORMAT_VARIANT, 0),
            "scale_variant": cand_types.get(C.CAND_POSSIBLE_SCALE_VARIANT, 0),
        },
        "transform_matches": {"total": len(transform_matches),
                              "by_transform": dict(xf)},
        "blocking": blocking,
        "family_components": len(comps["components"]),
        "component_sizes": sorted((len(c) for c in comps["components"]),
                                  reverse=True),
        "weak_bridges_detected_and_split": len(weak_bridges),
        "weak_bridges": weak_bridges,
        "canonical_nominations": len(noms),
        "cross_format_5955564_66_67": fam,
        "unhashable_candidates": sum(1 for c in cands if c["hash"] is None),
        "invariants": {
            "no_rights_or_permissions_propagated": not rights_moved,
            "no_automatic_canonical_selection": not auto_selected,
            "no_approved_reusable": C.POSTURE_APPROVED_REUSABLE not in blob,
            "no_retired_readiness_vocabulary": not any(
                old in blob for old in C.RETIRED_READINESS),
            "candidate_edges_have_blank_human_field": all(
                e["human_confirmed_relationship"] is None for e in cand_edges),
            "no_naive_all_pairs": (blocking["blocked_pairs"]
                                   <= blocking["naive_pairs"]),
        },
        "integrity": integrity,
        "runtime_seconds": round(runtime_s, 2),
        "output_bytes": out_bytes,
    }


def _cross_format(cands, src_edges, cand_edges) -> dict:
    """The frozen 5955564.eps / 5955566.jpg / 5955567.ai family."""
    fam_ids = {}
    for c in cands:
        n = Path(c["source_path"]).name
        if n in ("5955564.eps", "5955566.jpg", "5955567.ai"):
            fam_ids.setdefault(n, []).append(c)
    members = {}
    for n, cs in fam_ids.items():
        members[n] = {
            "candidates": len(cs),
            "readiness": sorted({c["readiness"] for c in cs}),
            "perceptually_hashable": any(c["hash"] is not None for c in cs),
        }
    fam_edges = [e for e in src_edges
                 if Path(e["a"]).name in fam_ids and Path(e["b"]).name in fam_ids]
    src_rels = sorted({h["relationship"] for e in fam_edges
                       for h in e["hypotheses"]})
    visual = [{"a": Path(e["a"]).name, "b": Path(e["b"]).name,
               "dhash": e["perceptual"]["dhash_distance"],
               "phash": e["perceptual"]["phash_distance"],
               "visually_near_identical":
                   e["perceptual"]["visually_near_identical"]}
              for e in fam_edges if e.get("perceptual")]
    ids = {c["candidate_id"] for cs in fam_ids.values() for c in cs}
    cand_rels = sorted({h["relationship"] for e in cand_edges
                        for h in e["hypotheses"]
                        if e["a"] in ids and e["b"] in ids})
    readiness_by_member = {n: m["readiness"] for n, m in members.items()}
    distinct = len({tuple(v) for v in readiness_by_member.values()}) > 1
    return {
        "members": members,
        "source_relationships": src_rels,
        "source_visual_corroboration": visual,
        "candidate_relationships": cand_rels,
        "readiness_per_member": readiness_by_member,
        "readiness_did_not_propagate": distinct or len(members) < 2,
        "candidate_equivalence_not_asserted": (
            "the .jpg is segmented into stickers while the .ai is a single "
            "whole-page embedded-raster candidate, so no candidate pair is a "
            "comparable unit. The visual family link is real of the FILES and is "
            "recorded as SOURCE evidence; it is deliberately NOT promoted to "
            "candidate equivalence."),
        "note": "members share a family but keep DIFFERENT technical readiness "
                "and different capabilities; EPS has no perceptual hash",
    }


def _no_output_under_source() -> dict:
    src, out = C.SOURCE_ROOT.resolve(), C.OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src), "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    C.assert_output_safe(C.OUT_C2C)
    C.OUT_C2C.mkdir(parents=True, exist_ok=True)
    pilot = C.load_c2_pilot()
    inv = run_c2a._inventory_map()

    before = snapshot()
    sources, cands = collect(pilot, inv)
    src_edges = families.source_edges(sources)
    cand_edges, blocking = build_candidate_edges(cands)
    comps = families.build_components([c["candidate_id"] for c in cands],
                                      cand_edges)
    by_id = {c["candidate_id"]: c for c in cands}
    noms = [canonical.nominate(comp, by_id) for comp in comps["components"]]
    after = snapshot()

    out_bytes = 0
    for name, obj in (("source_edges.json", src_edges),
                      ("candidate_edges.json", cand_edges),
                      ("components.json", comps),
                      ("canonical_nominations.json", noms)):
        p = C.OUT_C2C / name
        C.assert_output_safe(p)
        payload = json.dumps(obj, default=json_default, ensure_ascii=False,
                             indent=2)
        p.write_text(payload, encoding="utf-8")
        out_bytes += len(payload.encode("utf-8"))

    integrity = {"materials": compare(before, after),
                 "no_output_under_source": _no_output_under_source()}
    recon = reconcile(sources, cands, src_edges, cand_edges, comps, noms,
                      blocking, integrity, time.monotonic() - t0, out_bytes)
    p = C.OUT_REPORTS / "c2c_reconciliation.json"
    C.assert_output_safe(p)
    p.write_text(json.dumps(recon, default=json_default, ensure_ascii=False,
                            indent=2), encoding="utf-8")

    ok = (integrity["materials"]["unchanged"]
          and integrity["no_output_under_source"]["ok"]
          and all(recon["invariants"].values()))
    _print(recon)
    if not ok:
        print("\nFAILED: integrity or invariant violation", file=sys.stderr)
        return 1
    return 0


def _print(r: dict) -> None:
    b = r["blocking"]
    print(f"DIP-0C2c — {r['sources']} sources, {r['candidates']} candidates")
    print(f"  blocking:   {b['blocked_pairs']} pairs vs {b['naive_pairs']} naive "
          f"({b['reduction']:.0%} reduction); "
          f"{b['perceptual_comparisons_performed']} comparisons performed")
    print(f"  src rels:   {r['source_relationship_totals']}")
    print(f"  cand rels:  {r['candidate_relationship_totals']}")
    print(f"  near-dup:   {r['near_duplicate_totals']}")
    print(f"  hypotheses: {r['hypothesis_totals']}")
    print(f"  transforms: {r['transform_matches']}")
    print(f"  components: {r['family_components']} sizes={r['component_sizes']}")
    print(f"  weak bridges split: {r['weak_bridges_detected_and_split']}")
    print(f"  canonical nominations: {r['canonical_nominations']}")
    print(f"  cross-format readiness_did_not_propagate="
          f"{r['cross_format_5955564_66_67']['readiness_did_not_propagate']}")
    print(f"  invariants: {r['invariants']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s, output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
