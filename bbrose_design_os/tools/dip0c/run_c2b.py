"""DIP-0C2b runner — technical readiness, pattern, raster quality, watermark.

Read-only. Re-runs C2a segmentation in-process (so results never depend on stale
`var/` artefacts), then scores **axis A only** on each AssetCandidate. Rights
(axis B), reuse posture (axis C) and retrieval / automatic use (D/E) are carried
through untouched and stay false/unconfirmed — verified by invariants.

    python -m tools.dip0c.run_c2b
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from tools.dip0.integrity import compare, snapshot
from tools.dip0.report import json_default

from . import config as C
from . import pattern, quality, readiness, run_c1, run_c2a, watermark

PARSER = f"{C.TOOL_NAME}.run_c2b/{C.TOOL_VERSION}"
RENDER_LONG_EDGE = 900          # bounded render for pattern/watermark measurement


# --- source-level assessment (axis A on the FILE) ---------------------------
def assess_source(rel: str, kind: str, audit: dict) -> tuple[dict, dict]:
    ev: list[dict] = []
    facts: dict = {"kind": kind}

    if kind == "eps":
        has_header = bool(audit["bounding_box"]["value"]
                          or audit["hires_bounding_box"]["value"])
        ev.append(readiness.evidence(
            C.EV_EPS_TOOL_LIMITATION,
            "EPS geometry needs Ghostscript; header-only audit",
            tier=C.TIER_REQUIRES_TOOL,
            signal="header_facts" if has_header else None, blocking=True))
        return readiness.assess(ev, header_facts=has_header), facts

    if kind == "svg":
        if not audit["security"]["safe_to_ingest"]["value"]:
            ev.append(readiness.evidence(
                C.EV_UNSAFE_SVG, "; ".join(audit["security"]["findings"]),
                tier=C.TIER_DIRECT, blocking=True))
        if audit["parse_status"] == "MALFORMED_XML":
            ev.append(readiness.evidence(C.EV_CORRUPTION, "SVG did not parse",
                                         tier=C.TIER_DIRECT, blocking=True))
        if audit.get("filters") or audit.get("element_counts", {}).get(
                "foreignobject"):
            ev.append(readiness.evidence(
                C.EV_UNSUPPORTED_FEATURES,
                "SVG filters/foreignObject present", tier=C.TIER_DIRECT,
                blocking=True))
        if audit["parse_status"] == "PARSED" and audit["vector_paths"]["value"]:
            ev.append(readiness.evidence(
                C.EV_EDITABLE_COLORS,
                f"{audit['vector_paths']['value']} native vector nodes",
                tier=C.TIER_DIRECT))
        return readiness.assess(ev), facts

    if kind == "pdf_backed":
        shell = audit["raster"]["jpeg_shell"]["value"]
        cov = audit["raster"]["coverage_fraction"]["value"]
        paths = audit["path_count"]["value"]
        band = audit["complexity"]["value"]
        facts.update({"jpeg_shell": shell, "raster_coverage": cov,
                      "paths": paths, "complexity": band,
                      "surface_mm": audit["boxes"].get("surface_mm")})
        if shell:
            ev.append(readiness.evidence(
                C.EV_EMBEDDED_RASTER_DEPENDENCE,
                f"embedded raster covers {cov:.0%} with only {paths} vector paths",
                tier=C.TIER_HEURISTIC, blocking=True))
        elif cov >= readiness.THRESHOLDS["raster_coverage_cleanup"]:
            ev.append(readiness.evidence(
                C.EV_VECTOR_RASTER_BALANCE,
                f"raster covers {cov:.0%} of the surface; vector is not dominant",
                tier=C.TIER_DIRECT, blocking=True))
        if band in ("high", "extreme"):
            ev.append(readiness.evidence(
                C.EV_COMPLEXITY, f"{paths} paths ({band}) — heavy to edit",
                tier=C.TIER_DIRECT, signal="caveat"))
        if paths:
            ev.append(readiness.evidence(
                C.EV_EDITABLE_COLORS, f"{paths} editable vector paths",
                tier=C.TIER_DIRECT))
            ev.append(readiness.evidence(
                C.EV_PATH_CLEANLINESS, f"{paths} paths parsed without error",
                tier=C.TIER_DIRECT))
        return readiness.assess(ev), facts

    # raster
    if audit.get("parse_status") == "UNREADABLE":
        ev.append(readiness.evidence(C.EV_CORRUPTION, "raster could not be decoded",
                                     tier=C.TIER_DIRECT, blocking=True))
        return readiness.assess(ev), facts
    dims = audit.get("dimensions", {}).get("value", {})
    facts.update({"dimensions": dims,
                  "dpi": audit.get("resolution_dpi", {}).get("value"),
                  "alpha": audit.get("alpha", {}).get("value"),
                  "color_mode": audit.get("color_mode", {}).get("value"),
                  "encoded_format": audit.get("encoded_format")})
    if facts.get("alpha"):
        ev.append(readiness.evidence(C.EV_TRANSPARENT_BACKGROUND,
                                     "alpha channel present", tier=C.TIER_DIRECT))
    return readiness.assess(ev), facts


# --- rendering --------------------------------------------------------------
def _source_image(rel: str, kind: str):
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = 300_000_000
    full = C.physical_path(rel, C.REPO_ROOT)
    try:
        if kind == "raster":
            return Image.open(full)
        if kind == "pdf_backed":
            import fitz
            doc = fitz.open(full)
            page = doc[0]
            z = min(1.0, RENDER_LONG_EDGE / max(page.rect.width, page.rect.height))
            pix = page.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            doc.close()
            return im
        return None                    # EPS: no render. SVG: no rasteriser here.
    except Exception:  # noqa: BLE001
        return None


# --- candidate-level assessment --------------------------------------------
def assess_candidate(cand: dict, kind: str, facts: dict, src_assessment: dict,
                     src_img) -> dict:
    ev: list[dict] = []
    rel = cand["source_file"]["relative_path"]
    seg = cand["segmentation"]

    # EPS carries ONLY the tool limitation — no geometry/quality claims at all.
    if kind == "eps":
        cand["A_technical_readiness"] = readiness.merge_source_blockers(
            readiness.assess([]), src_assessment, [])
        cand["source_technical_readiness"] = _src_ref(src_assessment)
        cand["pattern"] = pattern.analyse(rel_path=rel, image=None, is_eps=True)
        cand["raster_quality"] = None
        cand["watermark"] = None
        return cand

    # --- resolution (raster): measured on the CANDIDATE CROP -----------------
    rq = None
    if kind == "raster":
        rq = quality.assess_raster(bbox_px=cand.get("bbox_px"), source_facts=facts)
        band = rq["resolution_band"]
        if band in (C.RES_LOW_RES_REFERENCE, C.RES_TOO_LOW):
            ev.append(readiness.evidence(
                C.EV_RASTER_RESOLUTION,
                f"effective crop {rq['effective_resolution']['long_edge']}px "
                f"({band}); {rq['dpi_note']}",
                tier=C.TIER_DIRECT, blocking=True))
        else:
            ev.append(readiness.evidence(
                C.EV_RASTER_RESOLUTION,
                f"effective crop {rq['effective_resolution']['long_edge']}px "
                f"({band}); {rq['dpi_note']}", tier=C.TIER_DIRECT))
        if facts.get("alpha"):
            ev.append(readiness.evidence(C.EV_TRANSPARENT_BACKGROUND,
                                         "alpha channel present",
                                         tier=C.TIER_DIRECT))

    # --- watermark (measured on the pixels, so a crop inherits it physically) --
    wm = None
    if src_img is not None and kind in ("raster", "pdf_backed"):
        long_edge = (rq["effective_resolution"]["long_edge"] if rq
                     else max(src_img.size))
        wm = watermark.assess(rel_path=rel, image=src_img, long_edge=long_edge)
        if wm["value"]:
            ev.append(readiness.evidence(
                C.EV_WATERMARK_SUSPICION, "; ".join(wm["evidence"]),
                tier=C.TIER_HEURISTIC, blocking=True))

    # --- collection-sheet ambiguity -----------------------------------------
    if seg["status"] in (C.SEG_STATUS_AUTO_LOW_CONF, C.SEG_STATUS_MANUAL):
        ev.append(readiness.evidence(
            C.EV_COLLECTION_SHEET_AMBIGUITY,
            f"segmentation is {seg['status']}: regions may be one composition, "
            "not distinct assets — needs human confirmation",
            tier=C.TIER_HEURISTIC, blocking=True))

    # --- isolation -----------------------------------------------------------
    iso = cand.get("isolated_candidate_confidence")
    if iso is not None:
        caveat = iso < readiness.THRESHOLDS["isolation_low"]
        ev.append(readiness.evidence(
            C.EV_ISOLATION, f"isolation signal {iso}",
            tier=C.TIER_HEURISTIC, signal="caveat" if caveat else None))

    # --- source geometry evidence -------------------------------------------
    # A source QUALITY judgment (e.g. "raster covers 70% of the PAGE") describes
    # the whole surface. It may block a candidate that IS that whole surface, but
    # it must NOT block a sub-region cut out of it: a clean pure-vector cluster
    # sitting away from the embedded image is not itself raster-heavy. So for
    # sub-candidates the same evidence is carried as NON-blocking context.
    # (Safety/tool blockers are separate and DO propagate — see
    #  readiness.merge_source_blockers.)
    whole_surface = (seg["status"] in (C.SEG_STATUS_WHOLE_FILE, C.SEG_STATUS_MANUAL)
                     or seg["method"] in (C.SEG_METHOD_VECTOR_WHOLE_NATURAL,
                                          C.SEG_METHOD_VECTOR_WHOLE_FALLBACK))
    for e in src_assessment["evidence"]:
        if e["code"] in (C.EV_EMBEDDED_RASTER_DEPENDENCE, C.EV_VECTOR_RASTER_BALANCE,
                         C.EV_COMPLEXITY, C.EV_EDITABLE_COLORS,
                         C.EV_PATH_CLEANLINESS, C.EV_UNSUPPORTED_FEATURES):
            item = dict(e)
            if not whole_surface and item["blocking"]:
                item["blocking"] = False
                item["detail"] = (f"source-level context (not applied to this "
                                  f"sub-region): {e['detail']}")
            ev.append(item)

    cand_assessment = readiness.assess(ev)
    # safety/tool blockers propagate; quality judgments do not
    cand["A_technical_readiness"] = readiness.merge_source_blockers(
        cand_assessment, src_assessment, ev)
    cand["source_technical_readiness"] = _src_ref(src_assessment)
    cand["raster_quality"] = rq
    cand["watermark"] = wm
    # A repeat verdict describes a TILE. A crop out of a multi-asset source is not
    # a tile, so we do not fabricate a seamlessness verdict for it.
    is_tile = not (cand.get("collection") or {}).get("is_member", False)
    cand["pattern"] = pattern.analyse(
        rel_path=rel, image=src_img, is_eps=False,
        recolorable=(kind == "pdf_backed" and not facts.get("jpeg_shell")),
        vector=(kind in ("pdf_backed", "svg")), is_tile=is_tile)
    return cand


def _src_ref(a: dict) -> dict:
    """The parent's own verdict, kept alongside — never overriding the child."""
    return {"value": a["value"], "caused_by": a["caused_by"],
            "note": "the source file's own technical verdict; a candidate's "
                    "verdict is independent except for safety/tool blockers"}


# --- runner -----------------------------------------------------------------
def score_entry(entry: dict, inv: dict) -> dict:
    rel = entry["relative_path"]
    res = run_c2a.segment_entry(entry, inv)
    kind = run_c2a._kind((entry.get("format") or Path(rel).suffix).lower())
    _, audit = run_c1.route(rel)
    src_assessment, facts = assess_source(rel, kind, audit)
    src_img = _source_image(rel, kind)
    # A repeat/seamlessness verdict is a property of the TILE, i.e. the source
    # surface — a pattern file that segments into motifs is still a tile as a
    # whole. So the pattern verdict is computed once at SOURCE level; candidates
    # that are crops out of it are not tiles and get REQUIRES_HUMAN.
    res["source_pattern"] = pattern.analyse(
        rel_path=rel, image=src_img, is_eps=(kind == "eps"),
        recolorable=(kind == "pdf_backed" and not facts.get("jpeg_shell")),
        vector=(kind in ("pdf_backed", "svg")), is_tile=True)
    for cand in res["candidates"]:
        assess_candidate(cand, kind, facts, src_assessment, src_img)
    if src_img is not None:
        try:
            src_img.close()
        except Exception:  # noqa: BLE001
            pass
    res["source_technical_readiness"] = src_assessment
    res["kind"] = kind
    return res


def reconcile(results, integrity, runtime_s, out_bytes) -> dict:
    all_c = [c for r in results for c in r["candidates"]]
    readiness_totals = Counter(c["A_technical_readiness"]["value"] for c in all_c)
    # a repeat verdict is a TILE property -> counted per SOURCE, not per crop
    pattern_totals = Counter(r["source_pattern"]["value"] for r in results
                             if r.get("source_pattern"))
    cand_pattern_totals = Counter(c["pattern"]["value"] for c in all_c
                                  if c.get("pattern"))
    band_totals = Counter(c["raster_quality"]["resolution_band"] for c in all_c
                          if c.get("raster_quality"))
    wm_suspected = [c["candidate_id"] for c in all_c
                    if c.get("watermark") and c["watermark"]["value"]]
    shell = [r["candidates"][0]["source_file"]["relative_path"] for r in results
             if any(e["code"] == C.EV_EMBEDDED_RASTER_DEPENDENCE
                    for e in r["source_technical_readiness"]["evidence"])
             and r["candidates"]]

    blob = json.dumps(all_c, default=json_default)
    eps_ready = [c["candidate_id"] for c in all_c
                 if c["source_file"]["format"] == ".eps"
                 and c["A_technical_readiness"]["value"] in (
                     C.READY_TECHNICALLY_READY,
                     C.READY_TECHNICALLY_USABLE_WITH_CAVEATS)]
    rights_granted = [c["candidate_id"] for c in all_c
                      if any(c["B_rights_readiness"][k] for k in
                             ("commercial_use", "modification", "embedding",
                              "redistribution"))]
    gates_on = [c["candidate_id"] for c in all_c
                if c["D_retrieval_eligibility"] or c["E_automatic_use_eligibility"]
                or c["production_use"]]
    bad_vocab = [c["candidate_id"] for c in all_c
                 if c["A_technical_readiness"]["value"] not in C.TECHNICAL_READINESS]
    seam_over_cap = [c["candidate_id"] for c in all_c
                     if c.get("pattern")
                     and c["pattern"]["value"] == C.PAT_SEAMLESS_LIKELY
                     and c["pattern"]["confidence"] > C.SEAMLESS_CONFIDENCE_CAP]

    return {
        "slice": "DIP-0C2b",
        "c2a_commit": "5d77cf5cca80bb6f86f91de2069eadb4a809212b",
        "pilot_files": len(results),
        "total_candidates": len(all_c),
        "candidates_by_technical_readiness": dict(readiness_totals),
        "pattern_verdict_totals_per_source": dict(pattern_totals),
        "pattern_verdicts_per_candidate": dict(cand_pattern_totals),
        # keyed by RELATIVE PATH: the exact-duplicate EPS pair shares a basename,
        # so keying by filename would silently drop one of the 19 files
        "source_pattern_by_file": {r["candidates"][0]["source_file"]
                                   ["relative_path"]:
                                   r["source_pattern"]["value"]
                                   for r in results if r["candidates"]},
        "raster_quality_bands": dict(band_totals),
        "watermark_suspected": len(wm_suspected),
        "watermark_suspected_ids": wm_suspected,
        "embedded_raster_or_jpeg_shell_sources": sorted(
            {Path(p).name for p in shell}),
        "requiring_cleanup": readiness_totals.get(C.READY_NEEDS_CLEANUP, 0),
        "requiring_reconstruction": readiness_totals.get(
            C.READY_NEEDS_VECTOR_RECONSTRUCTION, 0),
        "blocked_by_tooling": (readiness_totals.get(C.READY_REQUIRES_TOOL, 0)
                               + readiness_totals.get(C.READY_HEADER_ONLY_PARTIAL,
                                                      0)),
        "reference_only": readiness_totals.get(C.READY_REFERENCE_ONLY, 0),
        "invariants": {
            "no_approved_reusable": C.POSTURE_APPROVED_REUSABLE not in blob,
            "no_retired_readiness_vocabulary": not any(
                old in blob for old in C.RETIRED_READINESS),
            "readiness_vocabulary_canonical": not bad_vocab,
            "eps_never_technically_ready": not eps_ready,
            "no_rights_granted": not rights_granted,
            "retrieval_and_auto_use_all_false": not gates_on,
            "seamless_confidence_capped": not seam_over_cap,
        },
        "integrity": integrity,
        "runtime_seconds": round(runtime_s, 2),
        "output_bytes": out_bytes,
    }


def _no_output_under_source() -> dict:
    src, out = C.SOURCE_ROOT.resolve(), C.OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src), "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    pilot = C.load_c2_pilot()
    inv = run_c2a._inventory_map()

    unique: dict[str, dict] = {}
    for e in pilot:
        unique.setdefault(e["relative_path"], e)

    before = snapshot()
    results, out_bytes = [], 0
    for entry in unique.values():
        res = score_entry(entry, inv)
        results.append(res)
        dest = C.OUT_CANDIDATES / f"{entry['relative_path'].replace('/', '__')}.c2b.json"
        C.assert_output_safe(dest)
        payload = json.dumps(res, default=json_default, ensure_ascii=False, indent=2)
        dest.write_text(payload, encoding="utf-8")
        out_bytes += len(payload.encode("utf-8"))
    after = snapshot()

    integrity = {"materials": compare(before, after),
                 "no_output_under_source": _no_output_under_source()}
    recon = reconcile(results, integrity, time.monotonic() - t0, out_bytes)
    p = C.OUT_REPORTS / "c2b_reconciliation.json"
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
    print(f"DIP-0C2b — {r['pilot_files']} files, {r['total_candidates']} candidates")
    print(f"  readiness:  {r['candidates_by_technical_readiness']}")
    print(f"  pattern/src:{r['pattern_verdict_totals_per_source']}")
    print(f"  pattern/cnd:{r['pattern_verdicts_per_candidate']}")
    print(f"  res bands:  {r['raster_quality_bands']}")
    print(f"  watermark:  {r['watermark_suspected']} suspected")
    print(f"  jpeg-shell: {r['embedded_raster_or_jpeg_shell_sources']}")
    print(f"  cleanup={r['requiring_cleanup']} reconstruction="
          f"{r['requiring_reconstruction']} tool-blocked={r['blocked_by_tooling']} "
          f"reference-only={r['reference_only']}")
    print(f"  invariants: {r['invariants']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']}")
    print(f"  runtime:    {r['runtime_seconds']}s, output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
