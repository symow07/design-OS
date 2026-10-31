"""DIP-0C1 runner — per-file technical audit over the frozen pilot.

Read-only. Routes each pilot file to its format module, wraps the result in a
unified envelope that keeps the two axes strictly apart — technical readiness
(axis A, from the module) never mixes with the rights block (axis B, all
false/unverified) and the retrieval gate stays off regardless. No machine record
ever carries `APPROVED_REUSABLE`: every posture goes through
`config.machine_posture`. Materials integrity is snapshotted before and after and
the run exits non-zero if anything under the source tree changed or if output
resolves inside it.

    python -m tools.dip0c.run_c1
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from tools.dip0.integrity import snapshot, compare
from tools.dip0.provenance import Inferred, human_block
from tools.dip0.report import json_default
from tools.dip0b import config as BC
from tools.dip0b.limits import Budget

from . import classify_override as co
from . import config as C
from . import eps_ghostscript, eps_header, pdf_vector, raster, svg

PDF_BACKED = {".ai", ".pdf"}
RASTER_EXT = {".jpg", ".jpeg", ".png", ".psd", ".webp", ".tif", ".tiff", ".gif"}
DEFERRED = {".ase": "DIP-0C3 (colour-palette / ASE parser)",
            ".otf": "DIP-0C4 (font family/source grouping)",
            ".ttf": "DIP-0C4 (font family/source grouping)",
            ".woff": "DIP-0C4 (font family/source grouping)",
            ".woff2": "DIP-0C4 (font family/source grouping)"}


def _inventory_map() -> dict:
    path = (C.REPO_ROOT / "var" / "design_intelligence" / "audits" / "dip0"
            / "inventory" / "inventory.jsonl")
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                out[r["relative_path"]] = r
    return out


def route(rel_path: str) -> tuple[str, dict]:
    """Dispatch by extension. Returns (kind, audit_dict)."""
    ext = Path(rel_path).suffix.lower()
    if ext in PDF_BACKED:
        return "pdf_backed", pdf_vector.audit(rel_path, Budget(BC.DEFAULT_LIMITS))
    if ext == ".svg":
        return "svg", svg.audit(rel_path)
    if ext in RASTER_EXT:
        return "raster", raster.audit(rel_path)
    if ext == ".eps":
        a = eps_header.audit(rel_path)
        a["ghostscript_adapter"] = eps_ghostscript.audit(rel_path)  # C1B blocked
        return "eps", a
    if ext in DEFERRED:
        return "deferred", {"format": ext, "parser": f"{C.TOOL_NAME}.deferred",
                            "parse_status": "DEFERRED",
                            "deferred_to": DEFERRED[ext],
                            "note": "recognised in C1; deep audit in a later slice",
                            "technical_readiness": None}
    return "unsupported", {"format": ext, "parse_status": "UNSUPPORTED",
                           "technical_readiness": None}


def _classification(rel_path: str, kind: str, audit: dict, orig_cat: str) -> dict:
    """Override only where the plan allows: PDFs (and EPS) that are really
    licence docs / decks / guidelines / collections. .ai geometry alone never
    triggers an override — but a third-party brand name still informs posture."""
    fn = Path(rel_path).name
    ext = Path(rel_path).suffix.lower()
    third = co.third_party_brand(fn)
    if ext == ".pdf":
        pages = audit.get("page_count", 1)
        text = _first_page_text(rel_path)
        return co.classify_pdf(fn, page_count=pages, first_page_text=text,
                               original_category=orig_cat, third_party=third)
    if ext == ".eps":
        # header-only text: use creator/title as a weak signal, no page text
        return co.classify_pdf(fn, page_count=1, first_page_text="",
                               original_category=orig_cat, third_party=third)
    return co.override_record(orig_cat, None, "no reclassification indicated",
                              [], 0.0)


def _first_page_text(rel_path: str) -> str:
    try:
        import fitz
        d = fitz.open(C.physical_path(rel_path, C.REPO_ROOT))
        t = d[0].get_text("text")
        d.close()
        return t
    except Exception:  # noqa: BLE001
        return ""


def _posture(rel_path: str, override: dict) -> dict:
    """Machine reuse-posture CANDIDATE. Never APPROVED_REUSABLE (guarded)."""
    fn = Path(rel_path).name
    low = fn.lower()
    ext = Path(rel_path).suffix.lower()
    is_font = ext in (".otf", ".ttf", ".woff", ".woff2")
    quarantine = is_font and (rel_path.startswith("materials/Fonts/")
                              or "(a)" in low or "arslan" in low)

    if co.third_party_brand(fn):
        posture, reason = C.POSTURE_THIRD_PARTY_RESTRICTED, "third-party brand name"
    elif "bbrose" in low:
        posture, reason = C.POSTURE_BRAND_MASTER_CANDIDATE, "BBROSE brand candidate"
    elif quarantine:
        posture, reason = C.POSTURE_QUARANTINED, "font quarantine location"
    elif override["audit_category_override"]:
        return co.posture_hint(override, is_font_quarantine=quarantine)
    else:
        posture, reason = C.POSTURE_REUSABLE_AFTER_REVIEW, "default: review required"

    return Inferred(value=C.machine_posture(posture), source="posture_rule",
                    evidence=[reason], confidence=0.4,
                    parser=f"{C.TOOL_NAME}.run_c1").to_dict()


def audit_entry(entry: dict, inv: dict) -> dict:
    rel = entry["relative_path"]
    kind, audit = route(rel)
    orig_cat = entry.get("inventory_category_original", "UNKNOWN")
    override = _classification(rel, kind, audit, orig_cat)
    posture = _posture(rel, override)
    inv_rec = inv.get(rel, {})
    return {
        "relative_path": rel,
        "filename": Path(rel).name,
        "sha256": inv_rec.get("sha256"),
        "size_bytes": inv_rec.get("size_bytes"),
        "format": entry.get("format"),
        "test_role": entry.get("test_role"),
        "inventory_category_original": orig_cat,
        "expected_capability": entry.get("expected_capability"),
        "kind": kind,
        "audit": audit,
        # axis A — technical readiness comes straight from the module
        "technical_readiness": audit.get("technical_readiness"),
        # axis B — rights, all false/unverified; NEVER derived from axis A
        "rights": C.rights_block(),
        "reuse_posture_candidate": posture,
        "retrieval_gate": C.retrieval_gate(),
        "classification_override": override,
        "human": human_block(),
    }


def reconcile(records: list[dict], integrity: dict, runtime_s: float,
              out_bytes: int) -> dict:
    from collections import Counter
    by_kind = Counter(r["kind"] for r in records)
    by_fmt = Counter(r["format"] for r in records)
    readiness = Counter(r["technical_readiness"]["value"]
                        for r in records if r["technical_readiness"])
    postures = Counter(r["reuse_posture_candidate"]["value"] for r in records)
    overrides = [{"file": r["filename"],
                  "original": r["classification_override"]
                  ["inventory_category_original"],
                  "override": r["classification_override"]
                  ["audit_category_override"]}
                 for r in records
                 if r["classification_override"]["audit_category_override"]]
    eps = [r for r in records if r["kind"] == "eps"]
    tiff_previews = sum(1 for r in eps
                        if r["audit"]["tiff_preview"].get("present"))
    svgs = [r for r in records if r["kind"] == "svg"]
    unsafe_svg = sum(1 for r in svgs
                     if not r["audit"]["security"]["safe_to_ingest"]["value"])
    jpeg_shells = [r["filename"] for r in records if r["kind"] == "pdf_backed"
                   and r["audit"]["raster"]["jpeg_shell"]["value"]]
    failures = [r["filename"] for r in records
                if r["audit"].get("parse_status") in
                ("UNREADABLE", "MALFORMED_XML", "NOT_PSD", "UNSUPPORTED")]
    approved_leak = [r["filename"] for r in records
                     if C.POSTURE_APPROVED_REUSABLE
                     in json.dumps(r, default=json_default)]
    # No record may carry retired readiness vocabulary, and every scored readiness
    # value must belong to the canonical axis-A vocabulary.
    blob_all = json.dumps(records, default=json_default)
    retired_leak = [old for old in C.RETIRED_READINESS if old in blob_all]
    bad_readiness = [r["filename"] for r in records
                     if r["technical_readiness"]
                     and r["technical_readiness"]["value"]
                     not in C.TECHNICAL_READINESS]
    retrieval_on = [r["filename"] for r in records
                    if any(r["retrieval_gate"][k] for k in
                           ("retrieval", "automatic_use", "embedding",
                            "production_use"))]
    return {
        "slice": "DIP-0C1",
        "generated_at": Inferred(value=None, source="").to_dict()["extracted_at"],
        "pilot_count": len(records),
        "by_kind": dict(by_kind),
        "by_format": dict(by_fmt),
        "technical_readiness_totals": dict(readiness),
        "reuse_posture_totals": dict(postures),
        "classification_overrides": overrides,
        "eps": {"count": len(eps),
                "all_require_ghostscript_for_geometry": all(
                    r["audit"]["vector_geometry"]["tier"] == C.TIER_REQUIRES_TOOL
                    for r in eps),
                "tiff_previews_extractable": tiff_previews,
                "ghostscript_adapter_status": (eps[0]["audit"]
                    ["ghostscript_adapter"]["adapter_status"] if eps else None),
                "ghostscript_capability_state": (eps[0]["audit"]
                    ["ghostscript_adapter"]["eps_capability_state"] if eps
                    else None)},
        "svg": {"count": len(svgs), "unsafe_or_rejected": unsafe_svg},
        "jpeg_shell_files": jpeg_shells,
        "parser_failures": failures,
        "invariants": {
            "no_approved_reusable_in_machine_output": not approved_leak,
            "approved_reusable_leaks": approved_leak,
            "retrieval_gate_all_off": not retrieval_on,
            "retrieval_leaks": retrieval_on,
            "no_retired_readiness_vocabulary": not retired_leak,
            "retired_readiness_leaks": retired_leak,
            "readiness_vocabulary_canonical": not bad_readiness,
        },
        "integrity": integrity,
        "runtime_seconds": round(runtime_s, 2),
        "output_bytes": out_bytes,
    }


def _no_output_under_source() -> dict:
    src = C.SOURCE_ROOT.resolve()
    out = C.OUTPUT_ROOT.resolve()
    inside = out == src or src in out.parents
    return {"output_root": str(out), "source_root": str(src),
            "output_inside_source": inside, "ok": not inside}


def main(argv=None) -> int:
    t0 = time.monotonic()
    C.ensure_output_dirs()
    pilot = C.load_pilot()
    inv = _inventory_map()

    before = snapshot()
    records = []
    out_bytes = 0
    for entry in pilot:
        rec = audit_entry(entry, inv)
        records.append(rec)
        safe_name = rec["relative_path"].replace("/", "__")
        dest = C.OUT_TECHNICAL / f"{safe_name}.json"
        C.assert_output_safe(dest)
        payload = json.dumps(rec, default=json_default, ensure_ascii=False,
                             indent=2)
        dest.write_text(payload, encoding="utf-8")
        out_bytes += len(payload.encode("utf-8"))
    after = snapshot()

    integrity = {
        "materials": compare(before, after),
        "no_output_under_source": _no_output_under_source(),
    }
    recon = reconcile(records, integrity, time.monotonic() - t0, out_bytes)
    recon_path = C.OUT_REPORTS / "c1_reconciliation.json"
    C.assert_output_safe(recon_path)
    recon_path.write_text(json.dumps(recon, default=json_default,
                                     ensure_ascii=False, indent=2),
                          encoding="utf-8")

    ok = (integrity["materials"]["unchanged"]
          and integrity["no_output_under_source"]["ok"]
          and recon["invariants"]["no_approved_reusable_in_machine_output"]
          and recon["invariants"]["retrieval_gate_all_off"]
          and recon["invariants"]["no_retired_readiness_vocabulary"]
          and recon["invariants"]["readiness_vocabulary_canonical"])
    _print_summary(recon)
    if not ok:
        print("\nFAILED: integrity or invariant violation", file=sys.stderr)
        return 1
    return 0


def _print_summary(r: dict) -> None:
    print(f"DIP-0C1 pilot audit — {r['pilot_count']} files")
    print(f"  by kind:    {r['by_kind']}")
    print(f"  readiness:  {r['technical_readiness_totals']}")
    print(f"  postures:   {r['reuse_posture_totals']}")
    print(f"  overrides:  {len(r['classification_overrides'])} "
          f"({[o['override'] for o in r['classification_overrides']]})")
    print(f"  jpeg-shell: {r['jpeg_shell_files']}")
    print(f"  eps:        {r['eps']['count']} files, "
          f"{r['eps']['tiff_previews_extractable']} TIFF previews, "
          f"gs={r['eps']['ghostscript_adapter_status']}")
    print(f"  svg:        {r['svg']['count']} ({r['svg']['unsafe_or_rejected']} "
          f"unsafe/rejected)")
    print(f"  failures:   {r['parser_failures']}")
    print(f"  invariants: no_APPROVED_REUSABLE="
          f"{r['invariants']['no_approved_reusable_in_machine_output']} "
          f"retrieval_off={r['invariants']['retrieval_gate_all_off']}")
    print(f"  integrity:  materials_unchanged="
          f"{r['integrity']['materials']['unchanged']} "
          f"output_outside_source={r['integrity']['no_output_under_source']['ok']}")
    print(f"  runtime:    {r['runtime_seconds']}s, output {r['output_bytes']} bytes")


if __name__ == "__main__":
    raise SystemExit(main())
