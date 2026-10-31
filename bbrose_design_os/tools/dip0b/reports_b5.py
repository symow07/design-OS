"""DIP-0B5 consolidated reports and DIP-0C/1 recommendations.

Generates the committed milestone documents from the manifest and the enriched
units. Deterministic: identical inputs → byte-identical markdown.
"""
from __future__ import annotations

from collections import Counter

from . import config as C

# The nine + fourteen acceptance questions the report must answer directly.
AUDIT_QUESTIONS = [
    "What do the pilot Illustrator files contain?",
    "How many meaningful units were detected?",
    "Which data is DIRECT?",
    "Which data is HEURISTIC?",
    "Which data requires Illustrator?",
    "Which data requires human review?",
    "How reliably can dielines be separated from artwork?",
    "How reliably can palette behaviour be described?",
    "How reliably can typography hierarchy be described?",
    "What should enter Historical Design Memory?",
    "What must remain excluded?",
    "What must DIP-1 persist?",
    "What must DIP-0C still audit?",
    "What does this imply for scaling from 14 to all 91 historical files?",
]

REFERENCE_MEMORY_STATEMENTS = [
    "Historical designs are reference memory, not templates.",
    "No exact historical placement geometry becomes a reusable layout.",
    "No historical dieline path enters the production dieline engine.",
    "No font-family claims were made.",
    "No OCR was used.",
    "No path-level registration association was falsely inferred.",
]

# Measured pilot totals used across the reports (kept in one place).
PILOT_FILES = 14
ALL_FILES = 91


def scale_estimate(rows: list[dict], units: list[dict]) -> dict:
    """Extrapolate the 14-file pilot to all 91. Everything is an estimate."""
    pages = len({(u["file"], u["page"]) for u in units})
    total_paths = sum(u["_vector_count"] for u in units)
    manual = sum(1 for r in rows if r["segmentation_status"] == "MANUAL_REQUIRED")
    review = sum(1 for r in rows if r["review_priority"] in ("HIGH", "MEDIUM"))
    factor = ALL_FILES / PILOT_FILES

    def est(v):
        return round(v * factor)

    return {
        "basis": f"{PILOT_FILES} pilot files, {pages} pages, {len(units)} units",
        "all_files": ALL_FILES,
        "extrapolation_factor": round(factor, 2),
        "estimated_pages": est(pages),
        "estimated_units": est(len(units)),
        "estimated_paths": est(total_paths),
        "estimated_manual_required_units": est(manual),
        "estimated_human_review_units_high_medium": est(review),
        "estimated_runtime_minutes_b1_to_b5": round(
            (pages * 8.0) * factor / 60.0, 1),
        "estimated_var_output_gb": round(0.0525 * factor, 2),
        "operationally_safe": True,
        "safety_note": ("resource guards (max_xref_scan, bounded samples, capped "
                        "render/crop px, per-page time budget) held on the pilot's "
                        "worst files (YB-1025: 77k xrefs, 9,630 transparency "
                        "groups); the same guards apply at 91 files"),
        "these_are_estimates": True,
        "sample_bias": [
            "the pilot was deliberately chosen for an easy/medium/hard spread, "
            "not at random",
            "high-complexity files were intentionally over-represented",
            "product-category and SKU-era balance across the remaining 77 files "
            "is unknown",
            "representativeness of the other 77 files is unverified — do not treat "
            "the 14-file pilot as statistically complete",
        ],
    }


def _table(headers, rows_):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for r in rows_:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return out


def _audit_report(rows, recon, units) -> str:
    types = Counter(r["candidate_type"] for r in rows)
    pages = len({(u["file"], u["page"]) for u in units})
    L = ["# DIP-0B — Historical Illustrator Design Deep Audit: consolidated report",
         "",
         f"Pilot: **{PILOT_FILES} files, {pages} pages, {recon['units']} design "
         "units.** Read-only; `materials/` unchanged throughout.", ""]
    for stmt in REFERENCE_MEMORY_STATEMENTS:
        L.append(f"> {stmt}")
    L += ["", "## Acceptance questions", ""]

    answers = {
        1: ("Multi-unit production artwork: carton dielines, surface artwork, "
            "product photos, blank spec tables, colour-swatch strips, sticker "
            "sheets, legal/ingredient text and barcodes — often all on one page."),
        2: f"{recon['units']} DesignUnitCandidates across {pages} pages — "
           + ", ".join(f"{v} {k}" for k, v in types.most_common()) + ".",
        3: ("Page boxes (pt+mm, y-down), path/raster geometry and counts, "
            "shading/SMask census, `/Separation` inks incl. `/All` registration "
            "and their full-strength sRGB, OCG names, XMP, content-stream "
            "operators, live-text and font counts (both zero)."),
        4: ("region segmentation, candidate typing, dieline structure, "
            "ΔE spot-to-ink matching, artwork descriptors, Level-A typography — "
            "each carries confidence + evidence."),
        5: ("original layer hierarchy, artboard names, live text + font "
            "identities, symbols, live effects, appearance stacks, editable "
            "swatch library — all locked in `/AIPrivateData` (present in all 14, "
            "never parsed). See native_illustrator_requirements.md."),
        6: f"{recon['review_priority_totals']['HIGH']} HIGH + "
           f"{recon['review_priority_totals']['MEDIUM']} MEDIUM priority units; "
           f"{recon['batch_group_totals']} batch groups make this tractable.",
        7: ("Yes, at the page level. 11/15 pages yielded a LIKELY_DIELINE_"
            "STRUCTURE, 1 BORDERLINE, 3 REJECTED. A dieline commonly spans "
            "several artwork candidates, so separation is a many-to-many overlay, "
            "not a clean partition — hence human confirmation."),
        8: (f"Per unit, coverage-weighted, in six strict buckets. "
            f"{recon['named_ink_matched']} colours matched a PANTONE ink by ΔE "
            f"(tint-ramp), {recon['present_but_unattributed']} are present but "
            "unattributed (valid colour, no recoverable named ink), and "
            f"{recon['flagged_near_black_artwork_total']} near-black artwork "
            "paths are flagged ambiguous. Path-level ink association is "
            "unavailable, so all matching is heuristic."),
        9: ("Level A only (bounds, apparent lines, relative scale, hierarchy "
            "rank, alignment, spacing, capitalisation appearance, density). "
            "Level B (wording, language, font, style) is unavailable: all "
            "typography is outlined and no OCR was used."),
        10: ("Primary SURFACE_ARTWORK and PRODUCT_PHOTO units with a dominant "
             f"colour ({recon['recommendation_totals']['RECOMMEND_INCLUDE']} "
             "recommended). Everything stays reference memory."),
        11: ("Spec tables, technical notes, barcodes, legal-text blocks, crop/"
             "registration material and purely technical dieline geometry "
             f"({recon['recommendation_totals']['RECOMMEND_EXCLUDE']} recommended "
             "for exclusion)."),
        12: "See recommendations_dip0c_dip1.md — 11 proposed persistence entities.",
        13: ("Reusable vector assets, motifs, patterns, backgrounds, icons, "
             "logos, brand masters, fonts, colour palettes, licence evidence and "
             "asset ownership — none audited here (pilot is HISTORICAL_DESIGN only)."),
        14: (f"Estimated ~{recon['scale_estimate']['estimated_units']} units and "
             f"~{recon['scale_estimate']['estimated_human_review_units_high_medium']} "
             "review units across all 91 files — an estimate from a deliberately "
             "non-random pilot; see the sample-bias caveats."),
    }
    for i, q in enumerate(AUDIT_QUESTIONS, 1):
        L += [f"### {i}. {q}", "", answers[i], ""]

    L += ["## Flagged-black visibility", "",
          f"- Near-black artwork paths kept as artwork, flagged ambiguous: "
          f"**{recon['flagged_near_black_artwork_total']}**",
          "- `/Separation /All` registration ink present at document level in "
          "9/14 files; path-level association **unavailable** on this pilot.",
          "- Ordinary black artwork was NOT removed from Design Memory because "
          "`/All` exists. The small `unresolved_or_ambiguous` bucket does not "
          "hide this: the flagged-black count above is the real ambiguity scale.",
          "",
          "## Review priority", "",
          *_table(["Tier", "Units"],
                  [[k, v] for k, v in recon["review_priority_totals"].items()]),
          "", "## Include / exclude recommendation (never final)", "",
          *_table(["Recommendation", "Units"],
                  [[k, v] for k, v in recon["recommendation_totals"].items()]),
          ""]
    return "\n".join(L) + "\n"


def _native_report(units) -> str:
    caps = [
        ("original semantic layer hierarchy", "layer intent (art vs dieline vs notes)",
         "yes", "no", "no", "partial", "yes"),
        ("artboard names", "human-meaningful unit names", "helpful", "no", "yes",
         "yes", "maybe"),
        ("live text + exact wording", "SKU, ingredients, claims", "no*", "no",
         "yes (OCR/DIP-0E)", "yes", "maybe"),
        ("font identities", "typography provenance", "no", "no", "yes", "yes",
         "yes if brand fonts matter"),
        ("symbols and instances", "repeated-mark reuse", "no", "yes", "yes",
         "partial", "maybe"),
        ("linked-vs-embedded asset relationships", "asset provenance", "no", "yes",
         "yes", "partial", "maybe"),
        ("live effects", "appearance reconstruction", "no", "no", "yes", "no",
         "no"),
        ("appearance stacks", "fill/stroke/effect order", "no", "no", "yes", "no",
         "no"),
        ("editable swatch-library structure", "named brand inks", "helpful", "yes",
         "yes", "partial", "yes"),
        ("Illustrator-specific object semantics", "true object model", "no", "no",
         "yes", "partial", "no"),
    ]
    L = ["# Native Illustrator requirements",
         "",
         "Capabilities unavailable through the PDF-compatible layer. `/AIMetaData` "
         "+ `/AIPrivateData*` are present in all 14 pilot files and are **never "
         "parsed** — this lists what a future JSX/Illustrator-assisted audit "
         "could recover, and whether it is worth it.",
         "",
         "\\* exact wording is also reachable via OCR (DIP-0E), not only "
         "Illustrator.",
         "",
         *_table(["Capability", "Why it matters", "Needed for Design Memory?",
                  "Needed for reusable-asset extraction?", "Deferrable?",
                  "Human review an acceptable substitute?",
                  "JSX/Illustrator audit justified?"],
                 [list(c) for c in caps]),
         "",
         "## Conclusion",
         "",
         "No capability above is required for DIP-0B's stated goal (understanding "
         "what is reliably extractable). Most are deferrable, and human review "
         "substitutes for the Design-Memory-critical ones. A JSX-assisted audit "
         "is justified only if (a) brand-font identity or (b) an editable swatch "
         "library becomes a hard DIP-1 requirement. `/AIPrivateData` remains "
         "opaque and unparsed.",
         ""]
    return "\n".join(L) + "\n"


def _recommendations_report(recon) -> str:
    entities = [
        ("SourceFile", "one historical .ai file; sha256, size, pilot flag, "
         "PDF/Illustrator version"),
        ("HistoricalDesign", "the design a file represents; SKU/product code + "
         "era + market (human-confirmed)"),
        ("HistoricalDesignPage", "one artboard/page; boxes (pt+mm), rotation, "
         "off-canvas summary"),
        ("DesignUnit", "a DesignUnitCandidate; bbox, type, confidence, "
         "primary/off-canvas, include-in-memory decision"),
        ("TechnicalAudit", "B1 per-page facts; path/raster/clip counts, "
         "separations, /All, capability tiers, truncation"),
        ("PaletteObservation", "per-unit bucketed colour; sRGB, ΔE spot match + "
         "tint, ambiguity flags, six-class membership"),
        ("TypographyObservation", "Level-A per text-like region; bounds, lines, "
         "scale, alignment, caps appearance; Level-B null"),
        ("DielineObservation", "page-level outcome + score + evidence channels, "
         "line-class counts, unit associations (many-to-many)"),
        ("ReviewDecision", "human confirmation; separate from machine inference, "
         "with reviewer/at/version/disposition/correction_reason"),
        ("ProvenanceRecord", "algorithm versions, thresholds fingerprints, "
         "parser, extraction timestamps for every inferred value"),
        ("AssetOwnershipRestriction", "ownership/licence/restriction fields "
         "(brand-owned, third-party, unverified); gates Design-Memory inclusion"),
    ]
    L = ["# DIP-0C and DIP-1 recommendations",
         "",
         "## DIP-0C — deep audit of the non-historical library",
         "",
         "DIP-0B covered HISTORICAL_DESIGN only. DIP-0C should deep-audit the "
         "other categories, reusing the DIP-0A inventory and the read-only "
         "invariants:",
         "",
         "- reusable vector assets, motifs, patterns, backgrounds, icons",
         "- logos and brand masters (ownership never inferred from folder)",
         "- fonts — with **batchable family/source review** (the DIP-0A lesson: "
         "4,883 fonts cannot be one-by-one)",
         "- colour palettes (`.ase`) and the palette ingestion contract",
         "- licence evidence and asset ownership/restriction confirmation",
         "",
         "## DIP-1 — persistence schema (recommend for review, do not finalise)",
         "",
         "Derived from what proved measurable, with machine inference and human "
         "confirmation in separate tables:",
         "",
         *_table(["Entity", "Holds"], [list(e) for e in entities]),
         "",
         "Every inferred column pairs with its ProvenanceRecord; every "
         "human-confirmable column is null until a ReviewDecision sets it. "
         "Nothing is marked reusable production artwork.",
         "",
         "## Scale to all 91 files (estimate)",
         "",
         *_table(["Metric", "Estimate"],
                 [["Pages", recon["scale_estimate"]["estimated_pages"]],
                  ["Units", recon["scale_estimate"]["estimated_units"]],
                  ["Paths", recon["scale_estimate"]["estimated_paths"]],
                  ["MANUAL_REQUIRED units",
                   recon["scale_estimate"]["estimated_manual_required_units"]],
                  ["HIGH+MEDIUM review units",
                   recon["scale_estimate"]["estimated_human_review_units_high_medium"]],
                  ["Runtime (B1–B5, min)",
                   recon["scale_estimate"]["estimated_runtime_minutes_b1_to_b5"]],
                  ["var/ output (GB)",
                   recon["scale_estimate"]["estimated_var_output_gb"]]]),
         "",
         "**These are estimates from a deliberately non-random pilot.** "
         + " ".join(recon["scale_estimate"]["sample_bias"]),
         ""]
    return "\n".join(L) + "\n"


def generate_all(rows, batches, recon, units) -> dict:
    return {
        "historical_design_audit_report.md": _audit_report(rows, recon, units),
        "native_illustrator_requirements.md": _native_report(units),
        "recommendations_dip0c_dip1.md": _recommendations_report(recon),
        "capability_matrix.md": _capability_matrix(),
        "known_limitations.md": _known_limitations(recon),
        "summary.md": _summary(recon),
        "decisions.md": _decisions(),
    }


def _capability_matrix() -> str:
    return ("# DIP-0B capability matrix\n\n"
            "| Tier | Meaning | Examples |\n|---|---|---|\n"
            "| DIRECT | read from the PDF structure | boxes, path/raster counts, "
            "`/Separation` inks + `/All`, shading census, OCG names, live-text "
            "count (0) |\n"
            "| HEURISTIC | inferred by rule, with confidence | region typing, "
            "dieline outcome, ΔE spot match, artwork descriptors, Level-A "
            "typography |\n"
            "| REQUIRES_ILLUSTRATOR | locked in `/AIPrivateData` | layer "
            "hierarchy, live text, fonts, symbols, effects, swatch library |\n"
            "| REQUIRES_HUMAN | only a designer settles it | wording, language, "
            "type style, SKU, era, ownership, final include/exclude |\n")


def _known_limitations(recon) -> str:
    return ("# DIP-0B known limitations\n\n"
            "- **Path-level registration association unavailable.** "
            "`get_drawings()` discards the colourspace and the content-stream "
            "operator count does not align with the drawing list, so no thin "
            "stroke is mapped to `/Separation /All`. Document-level presence only.\n"
            "- **Spot matching is heuristic** (ΔE over RGB-converted colour, "
            "tint-ramp sampled). "
            f"{recon['present_but_unattributed']} colours are present but "
            "unattributed — valid colour whose named ink is unrecoverable, not a "
            "failed match.\n"
            "- **Near-black is ambiguous.** "
            f"{recon['flagged_near_black_artwork_total']} artwork paths could be "
            "K, rich black or registration; kept as artwork, flagged.\n"
            "- **All typography is outlined.** Level B needs OCR (DIP-0E); no "
            "font-family claims.\n"
            "- **DIMENSION_MARK_CANDIDATE = 0** under the current rule — recorded "
            "as 'not detected', not 'absent'; four pages named for spot-check.\n"
            "- **Pilot is 14 of 91 files, deliberately non-random.** Extrapolations "
            "are estimates; representativeness of the other 77 is unverified.\n")


def _summary(recon) -> str:
    return ("# DIP-0B summary\n\n"
            f"14 files, {recon['units']} units. "
            f"Review priority {recon['review_priority_totals']}; "
            f"recommendations {recon['recommendation_totals']}; "
            f"{recon['batch_group_totals']} batch groups. "
            f"{recon['named_ink_matched']} named-ink matches, "
            f"{recon['present_but_unattributed']} unattributed, "
            f"{recon['flagged_near_black_artwork_total']} flagged near-black. "
            "Historical designs are reference memory, not templates; no OCR; no "
            "font-family claims; no path-level registration inferred; no geometry "
            "exported in a production-reusable format.\n")


def _decisions() -> str:
    return ("# DIP-0B decisions of record\n\n"
            "- `DIELINE_CANDIDATE` / `LIKELY_DIELINE_STRUCTURE` — never a "
            "confirmed dieline; three outcomes with a config-driven review band.\n"
            "- A thin structural stroke is NOT technical ink; a colour is "
            "excluded only when B3 typed that path technical.\n"
            "- Registration is not black; `/All` never a confident artwork match; "
            "black artwork never auto-stripped.\n"
            "- Six colour buckets incl. `unresolved_or_ambiguous`; unattributed "
            "process colour kept distinct from a failed spot match.\n"
            "- Level-A typography only; Level B unavailable; DIP-0E is the future "
            "OCR milestone.\n"
            "- Machine inference and human confirmation live in separate blocks; "
            "a batch is a review convenience, never an auto-applied decision.\n"
            "- Historical designs are reference memory, not templates.\n")


def write_milestone(docs: dict, rows, batches, recon) -> dict:
    C.DOCS_ROOT.mkdir(parents=True, exist_ok=True)
    for name, text in docs.items():
        p = C.DOCS_ROOT / name
        C.assert_output_safe(p)
        p.write_text(text, encoding="utf-8")
    return {"docs_dir": str(C.DOCS_ROOT), "written": sorted(docs)}
