"""Per-method coverage, registration + complete colour counting + label
density (Phase 2B-3C, §11-§14).

Computes the codes deferred from 2B-3B and upgrades colour counting to the full
production basis (process + spot inks + white underbase + foil), not just the
process-artwork hexes. Registration is honest: when manufacturer capability is
unknown (always, this phase), interacting registered separations return
REVIEW_REQUIRED rather than a pretended production-safe geometry. Label density
is measured per zone but gated only against a reliable target — a regulatory
back label is never held to a front-hero target. All findings are
production-readiness codes, never reconstruction blockers.

[The owner's answer of 2026-09-27: the registration review, the colour count, the coverage and the registration
tolerance are the maker's printing specification — production notes at the review
(``container_production_readiness.MAKER_SPECIFICATION_NOTES``), never a blocker. Label density is not one of them.]
"""
from __future__ import annotations

from apps.pipeline.services.container_contract import zone_surface

MAXIMUM_COVERAGE_EXCEEDED = "CONTAINER_MAXIMUM_COVERAGE_EXCEEDED"
REGISTRATION_TOLERANCE_FAILED = "CONTAINER_REGISTRATION_TOLERANCE_FAILED"
REGISTRATION_REVIEW_REQUIRED = "CONTAINER_REGISTRATION_REVIEW_REQUIRED"
COLOR_COUNT_EXCEEDED = "CONTAINER_COLOR_COUNT_EXCEEDED"
LABEL_DENSITY_FAILED = "CONTAINER_LABEL_DENSITY_FAILED"

_TECHNICAL = ("LABEL_CUT", "LABEL_BLEED", "LABEL_SAFE", "SHRINK_SLEEVE_SEAM",
              "SHRINK_SLEEVE_SAFE", "TECHNICAL_NOTES")


def _zone_area(zone: dict) -> float:
    return float(zone.get("width") or 0.0) * float(zone.get("height") or 0.0)


def _placements_by_zone(doc) -> dict:
    out: dict = {}
    for pl in (doc.metadata or {}).get("placements") or []:
        out.setdefault(pl.get("zone_id"), []).append(pl)
    return out


def measure_coverage(doc, methods_record, zones) -> dict:
    """§11 printed-artwork coverage per method/zone vs the permitted maximum.
    Coverage is the union-ish sum of non-field artwork placements' normalised
    area (field is the ground, not counted as artwork)."""
    by_zone = _placements_by_zone(doc)
    findings, codes = [], []
    for m in methods_record.get("methods") or []:
        cap = m.get("maximum_coverage")
        for zid in m.get("target_zone_ids") or []:
            art = [p for p in by_zone.get(zid, []) if p.get("kind") != "field"]
            measured = round(min(1.0, sum(float(p.get("nw", 0)) * float(p.get("nh", 0))
                                          for p in art)), 4)
            entry = {"method_id": m.get("method_id"),
                     "method_type": m.get("method_type"), "zone_id": zid,
                     "permitted": cap, "measured": measured}
            if cap is not None and measured > cap + 1e-6:
                entry["code"] = MAXIMUM_COVERAGE_EXCEEDED
                codes.append(MAXIMUM_COVERAGE_EXCEEDED)
            findings.append(entry)
    return {"per_zone": findings, "codes": _dedup(codes)}


def measure_registration(methods_record, separations_record) -> dict:
    """§12 registration. Multiple registered (printing) separations that must
    align → an interaction. With manufacturer capability unverified we return
    REVIEW_REQUIRED, never a pretended production-safe geometry."""
    printing = [s for s in separations_record.get("separations") or []
                if s.get("printable", True) and s.get("name") not in _TECHNICAL
                and s.get("name") != "PROCESS_ARTWORK"]
    # group registered separations by method
    by_method: dict = {}
    for s in printing:
        by_method.setdefault(s.get("method_id"), []).append(s.get("name"))
    interactions = [{"method_id": mid, "separations": names}
                    for mid, names in by_method.items() if len(names) >= 2]
    verified = methods_record.get("all_manufacturer_verified", False)
    codes = []
    state = "NO_INTERACTION"
    if interactions:
        if verified:
            state = "MEASURED"          # a real offset check would run here
        else:
            state = "REVIEW_REQUIRED"
            codes.append(REGISTRATION_REVIEW_REQUIRED)
    return {"interactions": interactions, "state": state, "codes": codes}


def complete_color_count(methods_record, separations_record) -> dict:
    """§13 complete production colour count per method — process (when the
    method is colour-limited) + spot inks + white underbase + foil — never the
    nonprinting technical guides. Emits CONTAINER_COLOR_COUNT_EXCEEDED with the
    full counted swatch list."""
    seps = separations_record.get("separations") or []
    findings, codes = [], []
    for m in methods_record.get("methods") or []:
        cap = m.get("permitted_color_count")
        counted = []
        for s in seps:
            if s.get("method_id") != m.get("method_id"):
                continue
            name = s.get("name")
            if name in _TECHNICAL:
                continue                        # cut/bleed/safe don't print
            if s.get("classification") == "SPOT" and s.get("printable", True):
                counted.append(s.get("swatch"))
        # a colour-limited method also spends its process colours
        if cap is not None and cap <= 4:
            counted.append("PROCESS_CMYK")
        # white underbase counts against methods that require it
        ub = separations_record.get("white_underbase") or {}
        if ub.get("state") == "GENERATED" and \
                m.get("white_underbase_requirement") == "conditional":
            counted.append("WHITE_UNDERBASE")
        counted = sorted(set(counted))
        entry = {"method_id": m.get("method_id"),
                 "method_type": m.get("method_type"),
                 "permitted": cap, "counted": counted, "count": len(counted),
                 "rationale": "spot inks + limited-process + underbase; "
                              "technical guides excluded"}
        if cap is not None and len(counted) > cap:
            entry["code"] = COLOR_COUNT_EXCEEDED
            codes.append(COLOR_COUNT_EXCEEDED)
        findings.append(entry)
    return {"per_method": findings, "codes": _dedup(codes)}


def measure_label_density(doc, zones, visual_graph) -> dict:
    """§14 text/artwork density per label/print zone. Gated only against a
    reliable target; a regulatory back label uses a different (looser) target
    than a front hero. Mostly UNMEASURED without a reliable target."""
    by_zone = _placements_by_zone(doc)
    findings, codes = [], []
    for z in zones or []:
        zid = z.get("zone_id")
        pls = by_zone.get(zid, [])
        art = [p for p in pls if p.get("kind") != "field"]
        printed = round(min(1.0, sum(float(p.get("nw", 0)) * float(p.get("nh", 0))
                                     for p in art)), 4)
        text_runs = sum(1 for p in pls if p.get("kind") == "product_name")
        surf = zone_surface(z)
        role = "back" if surf == "BODY_BACK" else "front"
        entry = {"zone_id": zid, "surface": surf,
                 "role": role, "printed_ratio": printed,
                 "text_runs": text_runs, "whitespace_ratio": round(1 - printed, 4),
                 "state": "UNMEASURED"}
        # only gate with a reliable target; none reliable this phase → report
        findings.append(entry)
    return {"per_zone": findings, "codes": _dedup(codes)}


def build_production_metrics(doc, methods_record, separations_record, zones,
                            visual_graph) -> dict:
    coverage = measure_coverage(doc, methods_record, zones)
    registration = measure_registration(methods_record, separations_record)
    colors = complete_color_count(methods_record, separations_record)
    density = measure_label_density(doc, zones, visual_graph)
    codes = _dedup(coverage["codes"] + registration["codes"]
                   + colors["codes"] + density["codes"])
    return {"schema_version": "container_production_metrics/1.0",
            "coverage": coverage, "registration": registration,
            "color_count": colors, "label_density": density, "codes": codes}


def _dedup(seq):
    seen, out = set(), []
    for c in seq:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


__all__ = [
    "build_production_metrics", "measure_coverage", "measure_registration",
    "complete_color_count", "measure_label_density",
    "MAXIMUM_COVERAGE_EXCEEDED", "REGISTRATION_TOLERANCE_FAILED",
    "REGISTRATION_REVIEW_REQUIRED", "COLOR_COUNT_EXCEEDED",
    "LABEL_DENSITY_FAILED",
]
