"""Content-measurement corrections (Phase 2A-6D-CORR-2 §2–§6, §8).

The task-#50 retry produced a substantially compliant direction set that
FOUR validator defects rejected: bounding extents read as area coverage, a
brief-required shared neutral read as palette collapse, "quietly" substring-
matching the tone cue "quiet", and comparative "different from …" clauses
classifying as what they contrast against. These tests pin each corrected
semantic and replay the full verbatim AgentLog 806 payload offline — no
provider call — proving it now passes both validators except for nothing.
"""
from __future__ import annotations

from apps.pipeline.direction_content import (
    COVERAGE_AREA,
    COVERAGE_DERIVED,
    COVERAGE_STRUCTURED,
    coverage_findings,
    validate_direction_content,
)
from apps.pipeline.direction_signature import (
    classify,
    direction_signature,
    originality_violations,
    strip_negated_spans,
    validate_semantic_distinctness,
)
from apps.pipeline.tests.fixtures_agentlog806 import AGENTLOG_806_DIRECTIONS
from apps.pipeline.tests.test_direction_content_2a6d import (
    BRIEF,
    COPY_BLOCK,
    _direction,
    _doc,
)

TASK50_BRIEF_CONTRACT = {
    "dimensions": "",
    "required_copy": ["BBROSE", "BAKED POWDER", "POLVO HORNEADO",
                      "LUMINOSIDAD SUAVE"],
    "production_constraints": ["decorative coverage no more than 20%"],
}


class TestCoverageSemantics:
    def test_explicit_area_claim_within_cap_passes(self):
        halo = _direction(graphic_elements="thin concentric halo arcs. "
                          "Total halo coverage under 18%.")
        findings = coverage_findings(BRIEF, [halo])
        assert findings[0]["source"] == COVERAGE_AREA
        assert findings[0]["area_claims"] == [18]
        assert not findings[0]["over_cap"]

    def test_explicit_area_range_above_cap_fails(self):
        field = _direction(graphic_elements="radial line field; total ink "
                           "coverage of the field approximately 40-50%")
        findings = coverage_findings(BRIEF, [field])
        assert findings[0]["area_claims"] == [50]
        assert findings[0]["over_cap"]

    def test_paired_extents_derive_a_bounding_area(self):
        # 30% height × 45% width = 13.5% — the Geometric Halo case that was
        # wrongly rejected on the retry.
        halo = _direction(layout_structure="arcs form a halo occupying "
                          "roughly 30% of panel height and 45% of panel "
                          "width. " + COPY_BLOCK)
        findings = coverage_findings(BRIEF, [halo])
        assert findings[0]["source"] == COVERAGE_DERIVED
        assert findings[0]["derived_estimates"] == [13.5]
        assert not findings[0]["over_cap"]

    def test_paired_extents_above_cap_fail(self):
        big = _direction(layout_structure="an engraved motif field spans "
                         "60% of panel height and 80% of panel width. "
                         + COPY_BLOCK)
        findings = coverage_findings(BRIEF, [big])
        assert findings[0]["derived_estimates"] == [48.0]
        assert findings[0]["over_cap"]

    def test_a_lone_width_extent_is_not_an_area(self):
        band = _direction(graphic_elements="a decorative band occupying "
                          "45% of panel width")
        findings = coverage_findings(BRIEF, [band])
        assert findings[0]["area_claims"] == []
        assert findings[0]["derived_estimates"] == []
        assert not findings[0]["over_cap"]

    def test_equal_extent_shape_derives_from_a_lone_extent(self):
        # Relief Strata's 70% emboss circle: a circle is as tall as it is
        # wide, so one extent bounds both axes — 49% stays a violation.
        emboss = _direction(layout_structure="a large centered deep-emboss "
                            "circle (70% of panel width) with concentric "
                            "rings. " + COPY_BLOCK)
        findings = coverage_findings(BRIEF, [emboss])
        assert findings[0]["derived_estimates"] == [49.0]
        assert findings[0]["over_cap"]

    def test_structured_field_takes_precedence(self):
        declared = _direction(decorative_coverage_pct=12,
                              graphic_elements="sparse halo accents")
        findings = coverage_findings(BRIEF, [declared])
        assert findings[0]["source"] == COVERAGE_STRUCTURED
        assert findings[0]["declared_pct"] == 12
        assert not findings[0]["over_cap"]

    def test_structured_field_above_cap_fails(self):
        declared = _direction(decorative_coverage_pct=35)
        assert coverage_findings(BRIEF, [declared])[0]["over_cap"]

    def test_malformed_structured_declaration_fails_closed(self):
        declared = _direction(decorative_coverage_pct="approximately half")
        finding = coverage_findings(BRIEF, [declared])[0]
        assert finding["malformed"]
        assert finding["over_cap"]

    def test_contradictory_prose_fails_closed_despite_structured_field(self):
        contradictory = _direction(
            decorative_coverage_pct=15,
            graphic_elements="engraved motif field; total ink coverage 45%")
        assert coverage_findings(BRIEF, [contradictory])[0]["over_cap"]

    def test_colon_does_not_sever_the_area_cue_from_its_percentage(self):
        emboss = _direction(graphic_elements="total emboss coverage: 70% "
                            "of the panel")
        assert coverage_findings(BRIEF, [emboss])[0]["over_cap"]


class TestPaletteRoles:
    def test_shared_required_neutral_across_distinct_palettes_passes(self):
        distinct = [
            _direction(color_system="Base: ivory (#FAF3EC). Secondary: "
                       "light blush pink. Accent: rose gold."),
            _direction(color_system="Base: light sky blue (#D6EAF8). "
                       "Secondary: warm ivory (#FAF3EC). Accent: pale "
                       "champagne."),
            _direction(color_system="Base: warm ivory (#FAF3EC). Secondary: "
                       "light peach. Tertiary: soft mint."),
        ]
        codes = validate_direction_content(BRIEF, _doc(distinct))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" not in codes

    def test_shared_dominant_chromatic_primary_fails(self):
        same_primary = [
            _direction(color_system=f"Base: blush pink. Neutral: ivory. "
                       f"Accent: gold. Variant {i}.") for i in range(3)]
        codes = validate_direction_content(BRIEF, _doc(same_primary))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" in codes

    def test_identical_chromatic_systems_fail_regardless_of_order(self):
        systems = ["blush pink with soft mint accents; ivory ground",
                   "soft mint fields against blush pink; cream base",
                   "blush pink and soft mint on a white ground"]
        directions = [_direction(color_system=s) for s in systems]
        codes = validate_direction_content(BRIEF, _doc(directions))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" in codes

    def test_neutral_only_palettes_with_one_ground_still_collapse(self):
        same_ground = [_direction(color_system=f"warm cream base with "
                                  f"accent {i}") for i in range(3)]
        codes = validate_direction_content(BRIEF, _doc(same_ground))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" in codes


class TestToneClassification:
    def test_quietly_does_not_classify_as_serene(self):
        tone = "Cool editorial confidence, modern, clean, quietly feminine."
        assert classify(tone, "emotional_tone") == "REFINED"

    def test_spa_calm_and_serene_classify_serene(self):
        assert classify("Serene, luminous, spa-calm and architecturally "
                        "refined.", "emotional_tone") == "SERENE"

    def test_fresh_and_warm_sensory_classifies_fresh(self):
        assert classify("Warm, light, sensory, quietly adult, fresh and "
                        "internationally modern.", "emotional_tone") == "FRESH"

    def test_genuinely_identical_tones_still_collapse(self):
        same = [_direction(name=f"d{i}", design_axis=f"axis {i}",
                           emotional_tone="serene, calm and tranquil")
                for i in range(3)]
        codes, _ = validate_semantic_distinctness(same)
        assert "EMOTIONAL_TONE_NOT_DISTINCT" in codes


class TestContrastLanguage:
    def test_different_from_serif_does_not_classify_serif(self):
        assert classify(
            "Rounded geometric sans-serif — materially different from the "
            "high-contrast serif used in direction 2.",
            "typography_family") == "GEOMETRIC_ROUNDED_SANS"

    def test_affirmative_serif_before_the_contrast_still_classifies(self):
        # span truncation keeps what comes BEFORE the contrast cue
        assert classify("uses a serif, different from direction 1",
                        "typography_family") == "SERIF_LED"

    def test_contrast_in_one_sentence_does_not_leak_into_another(self):
        text = ("The halo is different from direction 1. A powder particle "
                "stream drifts across the panel.")
        assert "particle stream drifts" in strip_negated_spans(text)


class TestMotifPrecedence:
    def test_particles_described_as_circles_are_particle_flow(self):
        assert classify("18–28 vector dot particles (circles 1–3 mm) with "
                        "curved flow paths", "motif_family") == "PARTICLE_FLOW"

    def test_halo_arcs_are_geometric_halo(self):
        assert classify("3–5 thin concentric partial arcs form a halo, "
                        "centered on panel", "motif_family") == "GEOMETRIC_HALO"

    def test_generic_shapes_stay_geometric_abstract(self):
        assert classify("abstract circles arranged on a strict grid",
                        "motif_family") == "GEOMETRIC_ABSTRACT"

    def test_priority_is_not_table_order(self):
        # GEOMETRIC_ABSTRACT precedes PARTICLE_FLOW in the table; specific
        # particle evidence must still win over the generic "circles" hit.
        assert classify("dot particles rendered as circles",
                        "motif_family") == "PARTICLE_FLOW"


class TestAgentLog806OfflineReplay:
    """§8: the verbatim rejected payload of the retry, revalidated offline
    under the corrected validators — no model, no provider, no task
    mutation. Expected: every code that fired was a measurement defect;
    the direction set passes signature AND content validation."""

    def test_signature_validation_passes(self):
        codes, warnings = validate_semantic_distinctness(AGENTLOG_806_DIRECTIONS)
        assert codes == []

    def test_expected_signature_matrix(self):
        signatures = [direction_signature(d) for d in AGENTLOG_806_DIRECTIONS]
        assert [s["typography_family"] for s in signatures] == [
            "CONDENSED_EDITORIAL_SANS", "MIXED_SERIF_SANS",
            "GEOMETRIC_ROUNDED_SANS"]
        assert signatures[1]["motif_family"] == "GEOMETRIC_HALO"
        assert signatures[2]["motif_family"] == "PARTICLE_FLOW"
        assert [s["emotional_tone"] for s in signatures] == [
            "REFINED", "SERENE", "FRESH"]

    def test_content_validation_passes(self):
        codes = validate_direction_content(
            TASK50_BRIEF_CONTRACT, _doc(list(AGENTLOG_806_DIRECTIONS)))
        assert codes == []

    def test_coverage_findings_match_the_declared_values(self):
        findings = coverage_findings(TASK50_BRIEF_CONTRACT,
                                     AGENTLOG_806_DIRECTIONS)
        assert not any(f["over_cap"] for f in findings)
        assert 10 in findings[0]["area_claims"]          # "under 10%"
        assert 18 in findings[1]["area_claims"]          # "under 18%"
        assert 13.5 in findings[1]["derived_estimates"]  # 30% h × 45% w
        assert 20 in findings[2]["area_claims"]          # "under 20%"

    def test_no_originality_violations(self):
        assert originality_violations(AGENTLOG_806_DIRECTIONS) == []

    def test_pairwise_floor_passes_for_every_pair(self):
        signatures = [direction_signature(d) for d in AGENTLOG_806_DIRECTIONS]
        dimensions = list(signatures[0].keys())
        for first in range(3):
            for second in range(first + 1, 3):
                differences = sum(
                    1 for dim in dimensions
                    if "UNCLASSIFIED" not in (signatures[first][dim],
                                              signatures[second][dim])
                    and signatures[first][dim] != signatures[second][dim])
                assert differences >= 3, (first, second, differences)
