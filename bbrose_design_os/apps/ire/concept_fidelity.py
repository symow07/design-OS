"""Selected-concept fidelity validation (2A-6E-CORR-7).

Task #50's production artwork replaced the approved Powder Constellation
concept with a generic ruled-stripe pattern and a small centered label, and
nothing measured the loss. This validator compares the COMPOSED document
against the selected variation's structured record — design intent and
structural relationships, never pixels — and fails closed with

    SELECTED_CONCEPT_FIDELITY_FAILED

before any production export. It must fail when: the product name collapses
to a small (or centered single) label; the logo moves to an unsupported
centered position; the principal motif family changes (e.g. constellation →
stripes); the particle constellation is absent or out of the declared
density band; the vertical Spanish copy is missing; or the selected
hierarchy is not preserved.
"""
from __future__ import annotations

SELECTED_CONCEPT_FIDELITY_FAILED = "SELECTED_CONCEPT_FIDELITY_FAILED"

#: Which design languages legitimately express which motif vocabularies.
_MOTIF_LANGUAGE_MAP = (
    (("particle", "constellation", "dot", "scatter", "powder", "speck"),
     ("powder_constellation",)),
    (("stripe", "ruled", "pinstripe", "line pattern"), ("ruled_field",)),
    (("liquid", "pour", "veil", "flow"), ("liquid_veil",)),
    (("contour", "topographic", "terrain"), ("contour_terrain",)),
    (("petal", "floral", "botanical"), ("petal_scatter",)),
    (("strata", "band", "block"), ("strata_field",)),
)


class ConceptFidelityError(ValueError):
    code = SELECTED_CONCEPT_FIDELITY_FAILED

    def __init__(self, failures: list[str]):
        super().__init__(
            SELECTED_CONCEPT_FIDELITY_FAILED + ": " + "; ".join(failures))
        self.failures = list(failures)


def _text_runs(doc) -> list:
    return [node for node, _ in doc.walk() if node.type == "text"]


def _expected_languages(motif_signature: str) -> tuple[str, ...]:
    text = (motif_signature or "").lower()
    for keywords, languages in _MOTIF_LANGUAGE_MAP:
        if any(keyword in text for keyword in keywords):
            return languages
    return ()


def validate_concept_fidelity(doc, spec: dict) -> list[str]:
    """Failure descriptions for a composed document vs the selected concept
    spec, or []. Deterministic structural checks — no pixel similarity."""
    if not spec:
        return []
    failures: list[str] = []
    style = str(doc.metadata.get("style", ""))
    motif_signature = str(spec.get("motif_signature", ""))

    # 1. principal motif family: the composed language must be one the
    #    selected motif supports — a constellation must never print stripes
    expected = _expected_languages(motif_signature)
    if expected and style not in expected:
        failures.append(
            f"principal motif family changed: the selected concept's motif "
            f"({motif_signature[:60]}…) requires one of {expected}, but the "
            f"composition used {style!r}")

    # 2. motif presence + density band
    if "powder_constellation" in expected:
        particle_count = sum(
            1 for node, parent in doc.walk()
            if node.type == "path"
            and str(getattr(node, "name", "")).startswith("particle-"))
        if particle_count == 0:
            failures.append("the particle constellation is absent")
        elif not (12 <= particle_count <= 600):
            failures.append(
                f"constellation density out of band ({particle_count} "
                "particles)")

    # 3. product-name hierarchy: stacked lines at a meaningful scale,
    #    left-anchored when the concept says so — never a small label
    name_lines = [line for line in (spec.get("name_lines") or []) if line]
    runs = _text_runs(doc)
    name_runs = [r for r in runs
                 if str(r.name).startswith("product-name")]
    if name_lines:
        if len(name_runs) < min(2, len(name_lines)):
            failures.append(
                "the product name is not the selected stacked hierarchy "
                f"({len(name_runs)} name run(s) for "
                f"{len(name_lines)} required line(s))")
        undersized = [r for r in name_runs if r.size_pt < 14.0]
        if name_runs and len(undersized) == len(name_runs):
            failures.append(
                "the product name is reduced to a small label "
                f"(max {max(r.size_pt for r in name_runs):.1f} pt)")
        zone = str(spec.get("product_name_zone", "")).lower()
        if ("left" in zone
                and name_runs
                and all(r.align == "center" for r in name_runs)):
            failures.append(
                "the product name is centered but the selected concept "
                "left-aligns it")

    # 4. vertical secondary copy
    vertical = spec.get("vertical_copy")
    if vertical:
        vertical_runs = [
            r for r in runs
            if abs(float(getattr(r, "rotation_deg", 0.0) or 0.0)) >= 45.0
            and vertical.split()[0] in r.text.upper()]
        if not vertical_runs:
            failures.append(
                f"the vertical copy ({vertical!r}) is missing")

    # 5. remaining secondary copy present somewhere as live text
    all_text = " ".join(r.text.upper() for r in runs)
    for phrase in (spec.get("secondary_copy") or []):
        if phrase and phrase not in all_text:
            failures.append(f"required copy {phrase!r} is missing")

    # 6. logo zone: an upper-left concept logo must not re-center — the
    #    composer declares the zone it actually used
    logo_zone = str(spec.get("logo_zone", "")).lower()
    if "upper left" in logo_zone or "upper-left" in logo_zone:
        used = str(doc.metadata.get("logo_zone_used", ""))
        if used != "upper-left":
            failures.append(
                f"the logo zone is {used or 'undeclared'} but the selected "
                "concept places it upper-left")

    return failures


def assert_concept_fidelity(doc, spec: dict) -> None:
    failures = validate_concept_fidelity(doc, spec)
    if failures:
        raise ConceptFidelityError(failures)


__all__ = ["validate_concept_fidelity", "assert_concept_fidelity",
           "validate_concept_geometry", "assert_concept_geometry",
           "GEOMETRY_TARGETS", "ConceptFidelityError",
           "SELECTED_CONCEPT_FIDELITY_FAILED"]


# --- geometry-based gate (2A-6E-CORR-8 §9) ------------------------------------
#
# The declaration checks above proved insufficient: a composition whose
# BAKED/POWDER group was 24% of panel height (target 42-58%) and whose
# constellation was 69 tiny particles passed with zero failures
# (FIDELITY_VALIDATED_DECLARATIONS_NOT_GEOMETRY). These checks measure the
# ACTUAL emitted vector geometry against the selected concept's target
# relationships.

#: §4 target bands, as fractions of the front panel.
GEOMETRY_TARGETS = {
    "name_group_h": (0.40, 0.60),        # contract 42-58% ± small tolerance
    "name_group_w": (0.36, 0.52),        # contract 38-50% ± small tolerance
    "logo_frame_w": (0.28, 0.50),        # contract 32-45% ± tolerance
    "constellation_front_count": (90, 150),
    "constellation_centroid_min": (0.55, 0.55),   # lower-right
    "lower_right_share_min": 0.5,
    "constellation_span_min": 0.5,       # bounding w and h — movement,
                                         # never an isolated box
    "coverage_band": (0.13, 0.22),       # contract 15-20% ± tolerance
    "side_continuation_share": (0.08, 0.22),      # contract 10-20%
    "other_surface_particle_cap": 8,     # flaps + opposite side stay quiet
}


def validate_concept_geometry(doc, spec: dict, front_bounds_mm) -> list[str]:
    """Stable §9 codes for the EMITTED geometry vs the selected concept."""
    if not spec:
        return []
    from apps.ire.geometry_report import measure_front_geometry

    report = measure_front_geometry(doc, front_bounds_mm)
    targets = GEOMETRY_TARGETS
    failures: list[str] = []

    name_group = report.get("product_name_group")
    if name_group:
        low_h, high_h = targets["name_group_h"]
        low_w, high_w = targets["name_group_w"]
        if name_group["h"] < low_h:
            failures.append(
                f"PRODUCT_NAME_TOO_SMALL: the stacked group is "
                f"{name_group['h']:.0%} of panel height (target ≥{low_h:.0%})")
        if not (low_w <= name_group["w"] <= high_w):
            failures.append(
                f"PRODUCT_NAME_NOT_DOMINANT: the group spans "
                f"{name_group['w']:.0%} of panel width (contract "
                f"{low_w:.0%}-{high_w:.0%})")
        if name_group["h"] > high_h:
            failures.append(
                f"PRODUCT_NAME_NOT_DOMINANT: the group is "
                f"{name_group['h']:.0%} of panel height (contract "
                f"≤{high_h:.0%})")
    elif spec.get("name_lines"):
        failures.append("PRODUCT_NAME_TOO_SMALL: no product-name group "
                        "was emitted")

    logo_frame = report.get("logo_frame_group")
    zone = str(spec.get("logo_zone", "")).lower()
    if "upper left" in zone or "upper-left" in zone:
        if logo_frame is None:
            failures.append("LOGO_FRAME_TOO_SMALL: no logo/frame group "
                            "was emitted")
        else:
            if logo_frame["w"] < targets["logo_frame_w"][0]:
                failures.append(
                    f"LOGO_FRAME_TOO_SMALL: the logo/frame group spans "
                    f"{logo_frame['w']:.0%} of panel width (target "
                    f"≥{targets['logo_frame_w'][0]:.0%})")
            if logo_frame["x"] > 0.25 or logo_frame["y"] > 0.30:
                failures.append(
                    "LOGO_ZONE_MISMATCH: the logo/frame group is not in "
                    "the upper-left region")

    vertical = report.get("vertical_copy")
    if spec.get("vertical_copy"):
        if vertical is None:
            failures.append("VERTICAL_COPY_ZONE_MISMATCH: the vertical copy "
                            "was not emitted")
        elif (vertical["x"] < 0.80 or vertical["y"] < -0.02
              or vertical["y"] + vertical["h"] > 1.05):
            failures.append(
                "VERTICAL_COPY_ZONE_MISMATCH: the vertical copy is outside "
                f"the right-edge zone (x={vertical['x']:.2f}, "
                f"y={vertical['y']:.2f})")

    constellation = report.get("constellation") or {}
    motif = str(spec.get("motif_signature", "")).lower()
    if any(k in motif for k in ("particle", "constellation", "dot",
                                "scatter")):
        count = constellation.get("front_count", 0)
        low_n, high_n = spec.get("constellation_count_band",
                                 targets["constellation_front_count"])
        if count < low_n:
            failures.append(
                f"CONSTELLATION_TOO_SPARSE: {count} front particles "
                f"(target {low_n}-{high_n})")
        centroid = constellation.get("centroid")
        min_x, min_y = targets["constellation_centroid_min"]
        if centroid and (centroid["x"] < min_x or centroid["y"] < min_y):
            failures.append(
                f"CONSTELLATION_ZONE_MISMATCH: centroid "
                f"({centroid['x']:.2f}, {centroid['y']:.2f}) is not in the "
                "lower-right region")
        share = (constellation.get("quadrant_share") or {}).get(
            "lower_right", 0.0)
        bounding = constellation.get("bounding")
        span_ok = bounding and bounding["w"] >= \
            targets["constellation_span_min"] and \
            bounding["h"] >= targets["constellation_span_min"]
        if share < targets["lower_right_share_min"] or not span_ok:
            failures.append(
                "CONSTELLATION_DENSITY_PROFILE_MISMATCH: lower-right share "
                f"{share:.0%} / bounding "
                f"{(bounding or {}).get('w', 0):.0%}×"
                f"{(bounding or {}).get('h', 0):.0%} — the field must mass "
                "at the lower-right corner and disperse across the panel, "
                "never sit as an isolated box")
        coverage = constellation.get("coverage_fraction")
        if coverage is not None:
            low_c, high_c = targets["coverage_band"]
            if not (low_c <= coverage <= high_c):
                failures.append(
                    "CONSTELLATION_DENSITY_PROFILE_MISMATCH: printed "
                    f"coverage {coverage:.1%} is outside the contract band "
                    f"({low_c:.0%}-{high_c:.0%})")
        side = constellation.get("side_continuation_count", 0)
        low_s, high_s = targets["side_continuation_share"]
        if count:
            ratio = side / count
            if side == 0:
                failures.append("SIDE_CONTINUATION_MISSING: no particles "
                                "continue onto the adjacent panel")
            elif not (low_s <= ratio <= high_s):
                failures.append(
                    "CONSTELLATION_DENSITY_PROFILE_MISMATCH: adjoining-side "
                    f"continuation is {ratio:.0%} of the front count "
                    f"(contract {low_s:.0%}-{high_s:.0%})")
        excess = sum((constellation.get("other_surface_counts") or {})
                     .values())
        if excess > targets["other_surface_particle_cap"]:
            failures.append(
                "CONSTELLATION_DENSITY_PROFILE_MISMATCH: "
                f"{excess} particles on flaps/the opposite side "
                f"(cap {targets['other_surface_particle_cap']})")

    # §8: the selected tall condensed typography needs a HUMAN-confirmed
    # licensed face — the NotoSans placeholder cannot express it
    if "condensed" in str(spec.get("product_name_zone", "")).lower() \
            and not spec.get("confirmed_font"):
        failures.append(
            "FONT_CONFIRMATION_REQUIRED: the selected concept uses tall "
            "condensed typography and no licensed face has been confirmed")

    return failures


def assert_concept_geometry(doc, spec: dict, front_bounds_mm) -> None:
    failures = (validate_concept_fidelity(doc, spec)
                + validate_concept_geometry(doc, spec, front_bounds_mm))
    if failures:
        raise ConceptFidelityError(failures)
