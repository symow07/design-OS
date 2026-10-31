"""DIP-0B1 outputs: per-file technical JSON, capability matrix, reconciliation.

Heavy artifacts stay under `var/design_intelligence/audits/dip0b/` (git-ignored).
Only the lightweight milestone record is ever committed (safeguard 10).
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from tools.dip0.report import json_default

from . import config as C

# Capabilities and where they actually come from. Written into every run so the
# boundary is a recorded fact, not tribal knowledge.
CAPABILITY_MATRIX = {
    C.TIER_DIRECT: [
        "page/artboard count", "MediaBox/CropBox/ArtBox/TrimBox/BleedBox (pt+mm, y-down)",
        "rotation", "path counts by type", "path width/dash/cap/join/opacity histograms",
        "bounded per-path sample (bbox, colours, seqno, layer)",
        "clip and transparency-group counts", "raster count/bounds/pixels/bpc/colourspace/filter",
        "shading, pattern and SMask census", "/Separation table incl. /All registration",
        "spot full-strength sRGB via tint transform", "OCG layer names",
        "XMP presence + document metadata", "content-stream operator census",
        "live text span count (measured: 0)", "embedded font count (measured: 0)",
    ],
    C.TIER_HEURISTIC: [
        "glyph_scale_fill_ratio (TEXT_LIKE_GEOMETRY_CANDIDATE evidence — may be "
        "outlined type OR icons/ornaments/motifs/decorative linework)",
        "thin_nofill_stroke_count (structural evidence for B3, not a dieline claim)",
    ],
    C.TIER_REQUIRES_ILLUSTRATOR: list(C.ILLUSTRATOR_ONLY_CAPABILITIES),
    C.TIER_REQUIRES_HUMAN: [
        "exact wording (unavailable / requires OCR)",
        "language (unavailable / requires OCR or human confirmation)",
        "precise type style (uncertain)",
        "whether text-like geometry is really type or decoration",
    ],
}


def _write_json(path: Path, obj) -> Path:
    C.assert_output_safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False,
                               default=json_default), encoding="utf-8")
    return path


def write_technical(record: dict, out_dir: Path | None = None) -> Path:
    out_dir = Path(out_dir or C.OUT_TECHNICAL)
    stem = Path(record["relative_path"]).stem
    return _write_json(out_dir / f"{stem}.technical.json", record)


def reconcile(records: list[dict]) -> dict:
    pages = sum(len(r["pages"]) for r in records)
    path_totals = [p["paths"]["total"] for r in records for p in r["pages"]]
    raster_totals = [p["rasters"]["count"] for r in records for p in r["pages"]]
    clip_totals = [p["paths"]["clips_total"] for r in records for p in r["pages"]]
    group_totals = [p["paths"]["groups_total"] for r in records for p in r["pages"]]

    spot_names: Counter = Counter()
    reg_files = []
    for r in records:
        for n in r["separations"]["spot_names"]:
            spot_names[n] += 1
        if r["separations"]["has_registration"]:
            reg_files.append(r["filename"])

    # A bounded sample is not data loss: aggregates still cover every path.
    data_loss = [r["filename"] for r in records if r["limits"]["data_loss"]]
    sampled = [r["filename"] for r in records if r["limits"]["sampling_limits"]]
    off_canvas = {r["filename"]: sum(p["off_canvas"]["total_off_canvas"]
                                     for p in r["pages"]) for r in records}
    multipage = {r["filename"]: len(r["pages"]) for r in records if len(r["pages"]) > 1}

    live_text = sum(p["live_text"]["span_count"]["value"]
                    for r in records for p in r["pages"])
    fonts = sum(p["live_text"]["embedded_font_count"]["value"]
                for r in records for p in r["pages"])

    ai_private = {r["filename"]: r["ai_private_data"]["container_objects"]
                  for r in records}

    def rng(v):
        return {"min": min(v), "max": max(v), "total": sum(v)} if v else None

    return {
        "files": len(records),
        "pages": pages,
        "paths": rng(path_totals),
        "rasters": rng(raster_totals),
        "clips": rng(clip_totals),
        "groups": rng(group_totals),
        "shadings": rng([r["xobjects"]["shadings"] for r in records]),
        "patterns": rng([r["xobjects"]["patterns"] for r in records]),
        "smasks": rng([r["xobjects"]["smasks"] for r in records]),
        "transparency_groups": rng([r["xobjects"]["transparency_groups"] for r in records]),
        "separations": {
            "distinct_spot_inks": len(spot_names),
            "spot_ink_frequency": dict(spot_names.most_common()),
            "files_with_registration": reg_files,
            "registration_count": len(reg_files),
        },
        "live_text_spans_total": live_text,
        "embedded_fonts_total": fonts,
        "all_typography_outlined": live_text == 0 and fonts == 0,
        "multipage_files": multipage,
        "files_with_data_loss": data_loss,
        "files_with_bounded_sampling": sampled,
        "aggregates_complete_for_all_files": not data_loss,
        "off_canvas_objects_by_file": off_canvas,
        "ai_private_container_objects_by_file": ai_private,
        "ai_private_parsed": False,
        "capability_matrix": CAPABILITY_MATRIX,
    }


def write_reports(records: list[dict], recon: dict, previews: dict,
                  integrity: dict) -> dict:
    _write_json(C.OUT_REPORTS / "reconciliation.json", recon)
    _write_json(C.OUT_REPORTS / "previews.json", previews)
    md = write_summary_md(recon, previews, integrity)
    return {"summary_md": str(md)}


def write_summary_md(recon: dict, previews: dict, integrity: dict) -> Path:
    p = C.OUT_REPORTS / "b1_summary.md"
    C.assert_output_safe(p)
    p.parent.mkdir(parents=True, exist_ok=True)

    def r(k):
        v = recon[k]
        return f"{v['min']}–{v['max']} (total {v['total']})" if v else "—"

    lines = [
        "# DIP-0B1 — Technical Illustrator/PDF inspection",
        "",
        f"- Pilot files processed: **{recon['files']}** · pages: **{recon['pages']}**",
        f"- Paths per page: {r('paths')}",
        f"- Rasters per page: {r('rasters')}",
        f"- Clips per page: {r('clips')} · Groups per page: {r('groups')}",
        f"- Shadings: {r('shadings')} · Patterns: {r('patterns')} · "
        f"SMasks: {r('smasks')} · Transparency groups: {r('transparency_groups')}",
        "",
        "## Typography", "",
        f"- Live text spans across every file and page: **{recon['live_text_spans_total']}**",
        f"- Embedded fonts: **{recon['embedded_fonts_total']}**",
        f"- All typography outlined: **{recon['all_typography_outlined']}**",
        "",
        "Glyph-scale geometry is recorded as `TEXT_LIKE_GEOMETRY_CANDIDATE` only. "
        "It may equally be icons, ornaments, motifs or decorative linework, and is "
        "never asserted to be type. Font family is never inferred from visual "
        "resemblance. No OCR is used in DIP-0B.",
        "",
        "## Separations", "",
        f"- Distinct spot inks: **{recon['separations']['distinct_spot_inks']}**",
        f"- Files carrying `/Separation /All` (registration): "
        f"**{recon['separations']['registration_count']}** / {recon['files']}",
        "",
        "Registration is a DIRECT technical-ink signal. Technical inks never enter "
        "BBROSE palette intelligence.",
        "",
        "## Native Illustrator boundary", "",
        f"- `/AIMetaData` + `/AIPrivateData*` containers per file: "
        f"{recon['ai_private_container_objects_by_file']}",
        f"- Payload parsed: **{recon['ai_private_parsed']}** — presence, size and "
        "structural evidence only. Layer names, live text, symbols, effects and "
        "appearances remain `REQUIRES_ILLUSTRATOR`.",
        "",
        "## Guards & truncation", "",
        f"- Files where information was **lost** (data_loss): "
        f"**{recon['files_with_data_loss'] or 'none'}**",
        f"- Files where only a **bounded sample** of per-path detail was written: "
        f"{len(recon['files_with_bounded_sampling'])} / {recon['files']}",
        f"- Aggregate statistics complete for every file: "
        f"**{recon['aggregates_complete_for_all_files']}**",
        "",
        "A bounded sample is not truncation of the analysis: every histogram and "
        "count above covers all paths. Only `data_loss` limits reduce confidence.",
        "",
        "## Off-canvas geometry", "",
        f"- Objects outside the design surface, by file: "
        f"{recon['off_canvas_objects_by_file']}",
        "",
        "Preserved, never discarded; previews and primary statistics are clipped to "
        "the ArtBox.",
        "",
        "## Multi-page (artboard) files", "",
        f"- {recon['multipage_files'] or 'none'}",
        "",
        "## Integrity", "",
        f"- `materials/` unchanged: **{integrity['source_unchanged']}**",
        f"- Output outside source root: **{integrity['output_outside_source']}**",
        "",
        "Historical designs are reference memory, not templates.",
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def write_milestone_docs(recon: dict, summary_md: Path) -> dict:
    """Lightweight, committed record. Never the technical JSON, previews or samples."""
    docs = C.DOCS_ROOT
    C.assert_output_safe(docs)
    docs.mkdir(parents=True, exist_ok=True)
    (docs / "b1_summary.md").write_text(summary_md.read_text(encoding="utf-8"),
                                        encoding="utf-8")
    _write_json(docs / "capability_matrix.json", CAPABILITY_MATRIX)
    return {"docs_dir": str(docs)}
