"""Content-faithfulness validation + safe replan (Phase 2A-6D).

Task #50's direction set passed every existing gate while contradicting the
brief. These tests pin the six content validators against trimmed replicas
of the ACTUAL rejected payloads, prove the user's replacement matrix passes,
and prove the replan path archives, replaces, and never renders.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.pipeline.direction_content import (
    coverage_cap_percent,
    raster_offending_clause,
    validate_direction_content,
)
from apps.pipeline.direction_signature import (
    classify,
    strip_negated_spans,
    validate_semantic_distinctness,
)

REQUIRED_COPY = ["BBROSE", "BAKED POWDER", "POLVO HORNEADO",
                 "LUMINOSIDAD SUAVE"]
BRIEF = {
    "dimensions": "",
    "required_copy": REQUIRED_COPY,
    "production_constraints": ["decorative coverage no more than 20%"],
}
COPY_BLOCK = ("Front copy: BBROSE, BAKED POWDER, POLVO HORNEADO, "
              "LUMINOSIDAD SUAVE.")


def _direction(**over):
    base = {
        "name": "d", "design_axis": "axis",
        "layout_structure": "clean open layout. " + COPY_BLOCK,
        "focal_hierarchy": "product name leads",
        "typography": "clean modern sans-serif",
        "color_system": "light blush pink, ivory",
        "graphic_elements": "one small vector accent",
        "imagery_approach": "native vectors only",
        "emotional_tone": "refined",
        "target_structural_guidance": "front face carries the story",
        "prompt_seed": "seed",
    }
    base.update(over)
    return base


# --- trimmed replicas of the ACTUAL rejected task-#50 directions -------------

SPIRAL_PHOTO = _direction(
    name="Mineral Bloom",
    design_axis="Image-led — photographic beauty macro IS the surface",
    layout_structure="Middle/lower band (75% height): full-bleed macro "
                     "photograph of baked powder swirl, bled to all edges",
    imagery_approach="Close-up overhead macro of a baked powder compact "
                     "swirl, warm studio lighting",
    color_system="Warm Cream (#FAF3EC) top band. Deep Rose (#8B3A52) name.",
    prompt_seed="front face dominated by a warm-lit macro of a baked powder "
                "swirl")
SPIRAL_ENGRAVED = _direction(
    name="Engraved Poudre",
    design_axis="Pattern-led — an engraved illustration field covers the "
                "primary surface",
    layout_structure="Full-face engraved illustration bleeds to all edges",
    graphic_elements="engraved line illustration: top-down powder swirl at "
                     "center, radial lines outward",
    color_system="Warm Cream (#FAF3EC) base. Deep Rose (#8B3A52) ink.",
    typography="refined copperplate engraving-style serif in a cartouche",
    prompt_seed="entire front face covered by intaglio engraving of a powder "
                "swirl")
SPIRAL_EMBOSSED = _direction(
    name="Relief Strata",
    design_axis="Material-led — emboss relief IS the design",
    layout_structure="a large centered deep-emboss circle (70% of panel "
                     "width) with concentric strata rings and a central "
                     "spiral relief",
    graphic_elements="multi-level blind emboss strata circle, deep central "
                     "spiral relief",
    imagery_approach="No photography, no illustration — emboss topography "
                     "as the image",
    color_system="Warm Cream (#FAF3EC) single surface color, rose gold foil",
    typography="wide-tracked geometric uppercase sans",
    prompt_seed="matte warm cream face with a deep-emboss spiral circle")
TASK50_SET = [SPIRAL_PHOTO, SPIRAL_ENGRAVED, SPIRAL_EMBOSSED]


def _doc(directions, **intent):
    base = {"target_structural_guidance": "", "visual_objective": "",
            "composition": ""}
    base.update(intent)
    base["directions"] = directions
    return base


class TestStructureInvention:
    def test_missing_dimensions_cannot_become_invented_dimensions(self):
        doc = _doc([_direction() for _ in range(3)],
                   visual_objective="a wide, low-profile palette box "
                                    "(approx. 100×70×30mm front-face "
                                    "proportion)")
        codes = validate_direction_content(BRIEF, doc)
        assert "UNCONFIRMED_STRUCTURE_ASSUMED:design_intent" in codes

    def test_unknown_structure_remains_unknown(self):
        doc = _doc([_direction(target_structural_guidance="Tuck-end or "
                               "auto-lock base. Side panels minimum 25mm"),
                    _direction(), _direction()])
        codes = validate_direction_content(BRIEF, doc)
        assert "UNCONFIRMED_STRUCTURE_ASSUMED:direction[0]" in codes

    def test_supplied_dimensions_disarm_the_check(self):
        brief = dict(BRIEF, dimensions="100 x 70 x 30 mm (confirmed)")
        doc = _doc([_direction(target_structural_guidance="front face "
                               "100mm wide"), _direction(), _direction()])
        codes = validate_direction_content(brief, doc)
        assert not any(c.startswith("UNCONFIRMED_STRUCTURE") for c in codes)


class TestTheRecordsOwnSizeIsNotAnAssumption:
    """§BH68(a): "measure why the check still fails and fix the cause." The brief gives the carton die and the product
    record holds it (width 170.5, depth 18, height 122.5 mm); the check refused the planner for repeating it in 6 of the
    18 attempts on record, and read it only as the fragment "5 x 122" — the splitter it shares cuts at the decimal
    point. The record's own sizes are read as such, on the raw text; every other size and every closure is refused
    exactly as before. VERBATIM clauses from the rejected payloads of tasks 96-101."""

    RECORD = (170.5, 18.0, 122.5)
    DIE_ON_RECORD = (
        "Carton front panel 170.5 × 122.5 mm organised in three horizontal zones",                      # task 100
        "Design the printed artwork for a shallow round pressed-powder compact and its folding carton "
        "(170.5 × 122.5 mm) that reads 'composed and finished skin' at shelf.",                           # task 100
        "Primary surface: carton front panel 170.5 × 122.5 mm.",                                          # task 100
        "Carton die 170.5 x 122.5 mm.",                                                                   # his brief
        "a 170.5 × 18 × 122.5 mm folding carton",
        "a 17.05 × 12.25 cm front panel",
    )
    INVENTED_ON_RECORD = (
        "Circular lid label: ~65 mm diameter.",                                                           # task 101
        "lid diameter approx 65–75mm, base depth approx 15mm",                                            # task 99
        "round shallow compact, approximately 65–75 mm diameter lid face",                                # task 96
        "Carton front 170.5 × 122.5 mm with a 3 mm bleed",                    # the record's die AND an invented bleed
        "a straight tuck end carton, 170.5 × 122.5 mm",                       # the record's die AND a closure
        "a 170 × 122 mm front",                                               # near, and not the record's
    )

    def _structure(self, text, record=RECORD, brief=BRIEF):
        doc = _doc([_direction(), _direction(), _direction()], target_structural_guidance=text)
        return [c for c in validate_direction_content(brief, doc, record_dimensions_mm=record)
                if c.startswith("UNCONFIRMED_STRUCTURE_ASSUMED")]

    def test_the_records_own_die_is_not_an_assumption(self):
        assert [t for t in self.DIE_ON_RECORD if self._structure(t)] == []

    def test_every_other_size_and_every_closure_is_still_refused(self):
        assert [t for t in self.INVENTED_ON_RECORD
                if self._structure(t) != ["UNCONFIRMED_STRUCTURE_ASSUMED:design_intent"]] == []

    def test_without_a_record_the_verdict_is_what_it_was(self):
        assert all(self._structure(t, record=()) == ["UNCONFIRMED_STRUCTURE_ASSUMED:design_intent"]
                   for t in self.DIE_ON_RECORD + self.INVENTED_ON_RECORD)

    def test_the_briefs_own_dimensions_still_stand_the_check_down(self):
        brief = dict(BRIEF, dimensions="170.5 x 122.5 mm")
        assert [t for t in self.INVENTED_ON_RECORD if self._structure(t, brief=brief)] == []

    def test_the_die_is_read_whole_before_any_split_and_the_evidence_names_what_is_left(self):
        from apps.pipeline.direction_content import RECORD_SIZE_TEXT, record_sizes_neutralised, structure_evidence
        assert "5 × 122" in strip_negated_spans("carton front 170.5 × 122.5 mm")          # WHY: the split cuts decimals
        assert record_sizes_neutralised("Carton die 170.5 x 122.5 mm.", self.RECORD) == f"Carton die {RECORD_SIZE_TEXT}."
        assert record_sizes_neutralised("Carton die 170.5 x 122.5 mm.", ()) == "Carton die 170.5 x 122.5 mm."
        found = structure_evidence(BRIEF, {"target_structural_guidance": "Carton front 170.5 × 122.5 mm with a 3 mm "
                                                                          "bleed"}, [], self.RECORD)
        assert found["design_intent"]["matched"] == "3 mm"

    def test_a_direction_that_names_the_die_is_not_refused_either(self):
        doc = _doc([_direction(layout_structure="Carton front panel 170.5 × 122.5 mm, three zones. " + COPY_BLOCK),
                    _direction(), _direction()])
        codes = validate_direction_content(BRIEF, doc, record_dimensions_mm=self.RECORD)
        assert not any(c.startswith("UNCONFIRMED_STRUCTURE") for c in codes)
        assert "UNCONFIRMED_STRUCTURE_ASSUMED:direction[0]" in validate_direction_content(BRIEF, doc)


class TestRequiredCopy:
    def test_all_required_copy_must_survive(self):
        missing_spanish = _direction(
            layout_structure="clean layout. Front copy: BBROSE, BAKED POWDER.")
        codes = validate_direction_content(
            BRIEF, _doc([missing_spanish, _direction(), _direction()]))
        assert "REQUIRED_COPY_MISSING:direction[0]" in codes
        assert "REQUIRED_COPY_MISSING:direction[1]" not in codes

    def test_copy_check_is_case_insensitive(self):
        lower = _direction(layout_structure="front copy: bbrose, baked "
                           "powder, polvo horneado, luminosidad suave")
        codes = validate_direction_content(BRIEF, _doc([lower] * 3))
        assert not any(c.startswith("REQUIRED_COPY") for c in codes)

    def test_no_required_copy_declared_means_no_check(self):
        brief = dict(BRIEF, required_copy=[])
        codes = validate_direction_content(
            brief, _doc([_direction(layout_structure="clean")] * 3))
        assert not any(c.startswith("REQUIRED_COPY") for c in codes)


class TestSharedMotifAndMedium:
    def test_three_executions_of_one_spiral_motif_fail(self):
        codes = validate_direction_content(BRIEF, _doc(TASK50_SET))
        assert "DIRECTIONS_SHARE_CORE_MOTIF:SPIRAL" in codes

    def test_photo_engraved_embossed_media_are_not_distinctness(self):
        """The rendering medium differs; the subject does not — the shared
        motif fires even though the signature validator sees three media."""
        distinct_codes, _ = validate_semantic_distinctness(TASK50_SET)
        content_codes = validate_direction_content(BRIEF, _doc(TASK50_SET))
        assert "DIRECTIONS_SHARE_CORE_MOTIF:SPIRAL" in content_codes

    def test_negated_motif_mentions_do_not_count(self):
        no_spiral = [_direction(graphic_elements="thin concentric arcs; "
                                "no powder spiral"),
                     _direction(graphic_elements="sparse vector particles; "
                                "no circular compact spiral"),
                     _direction(graphic_elements="one radiance line; no "
                                "spiral illustration")]
        codes = validate_direction_content(BRIEF, _doc(no_spiral))
        assert not any("SHARE_CORE_MOTIF" in c for c in codes)


class TestCoverageAndRaster:
    def test_cap_is_parsed_from_the_brief(self):
        assert coverage_cap_percent(BRIEF) == 20
        assert coverage_cap_percent({"production_constraints": []}) is None

    def test_seventy_percent_emboss_fails_the_cap(self):
        codes = validate_direction_content(
            BRIEF, _doc([SPIRAL_EMBOSSED, _direction(), _direction()]))
        assert "DECORATIVE_COVERAGE_EXCEEDED:direction[0]" in codes

    def test_full_face_illustration_fails_the_cap(self):
        codes = validate_direction_content(
            BRIEF, _doc([SPIRAL_ENGRAVED, _direction(), _direction()]))
        assert "DECORATIVE_COVERAGE_EXCEEDED:direction[0]" in codes

    def test_no_more_than_cap_language_passes(self):
        within = _direction(graphic_elements="circular halo motif occupying "
                            "no more than 20% of the panel")
        codes = validate_direction_content(BRIEF, _doc([within] * 3))
        assert not any("COVERAGE" in c for c in codes)

    def test_photo_dependent_direction_fails_native_vector(self):
        codes = validate_direction_content(
            BRIEF, _doc([SPIRAL_PHOTO, _direction(), _direction()]))
        assert "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_negated_photography_passes(self):
        codes = validate_direction_content(
            BRIEF, _doc([SPIRAL_EMBOSSED, _direction(), _direction()]))
        assert not any(
            c == "PRODUCTION_RASTER_DEPENDENCY:direction[0]" for c in codes)


class TestZeroIsNegation:
    """The replan of task #50 (AgentLog 792, code 34c38ac) was rejected with
    PRODUCTION_RASTER_DEPENDENCY on all three directions because each one
    DECLARED compliance — "Zero photographic imagery. Zero raster fields." —
    and "zero" was not a negation cue. The compliance statement itself
    triggered the code. These pin the fix against trimmed replicas of the
    actual rejected payload."""

    ZERO_DECLARATION = ("Zero photographic imagery. Zero raster fields. All "
                        "elements are live type and closed Bézier vector "
                        "objects.")

    def test_zero_spans_are_stripped(self):
        assert strip_negated_spans(self.ZERO_DECLARATION) == \
            "all elements are live type and closed bézier vector objects"

    def test_zero_photography_declaration_does_not_fire_raster(self):
        declared = _direction(imagery_approach=self.ZERO_DECLARATION)
        codes = validate_direction_content(BRIEF, _doc([declared] * 3))
        assert not any("PRODUCTION_RASTER_DEPENDENCY" in c for c in codes)

    def test_zero_elsewhere_does_not_mask_affirmative_photography(self):
        mixed = _direction(imagery_approach="Zero clutter; a macro "
                           "photograph of powder is the production surface")
        codes = validate_direction_content(
            BRIEF, _doc([mixed, _direction(), _direction()]))
        assert "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_replan_rejection_true_positive_survives(self):
        # direction[1] of the rejected replan genuinely violated the cap:
        # a full-bleed radial line field at 40-50% ink coverage.
        engraved_field = _direction(
            name="Engraved Radiance Field",
            layout_structure="Full-bleed radial line field on the front "
                             "panel built from a single vector origin point. "
                             + COPY_BLOCK,
            graphic_elements="Radial vector line field; total ink coverage "
                             "of the field approximately 40-50%",
            imagery_approach=self.ZERO_DECLARATION)
        codes = validate_direction_content(
            BRIEF, _doc([_direction(), engraved_field, _direction()]))
        assert "DECORATIVE_COVERAGE_EXCEEDED:direction[1]" in codes
        assert not any("PRODUCTION_RASTER_DEPENDENCY" in c for c in codes)


class TestPaletteDistinctness:
    def test_shared_neutral_hex_alone_is_not_palette_collapse(self):
        # 2A-6D-CORR-2 §3 removed the any-shared-hex rule: TASK50_SET's
        # shared #FAF3EC is warm cream — a neutral the brief may require in
        # every palette. The set still fails on its REAL defects.
        codes = validate_direction_content(BRIEF, _doc(TASK50_SET))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" not in codes
        assert any(c.startswith("DIRECTIONS_SHARE_CORE_MOTIF") for c in codes)

    def test_one_ground_color_across_all_three_fails(self):
        same_ground = [_direction(color_system=f"warm cream base with "
                                  f"accent {i}") for i in range(3)]
        codes = validate_direction_content(BRIEF, _doc(same_ground))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" in codes

    def test_distinct_grounds_pass(self):
        distinct = [_direction(color_system="light blush pink; ivory"),
                    _direction(color_system="light sky blue; champagne"),
                    _direction(color_system="light peach; soft mint")]
        codes = validate_direction_content(BRIEF, _doc(distinct))
        assert "PALETTE_SYSTEMS_NOT_DISTINCT" not in codes


class TestNegationAwareTypography:
    def test_no_decorative_script_is_not_script_led(self):
        assert classify("Product name: a classical high-contrast serif in "
                        "small uppercase. Shade: small neutral grotesque. "
                        "No decorative script.",
                        "typography_family") == "MIXED_SERIF_SANS"

    def test_distinct_from_serif_and_script_is_not_script_led(self):
        assert classify("a wide-tracked geometric uppercase sans "
                        "(contemporary, architectural — distinct from the "
                        "serif and script of other directions)",
                        "typography_family") == "GEOMETRIC_ROUNDED_SANS"

    def test_strip_negated_spans(self):
        assert strip_negated_spans("clean sans. No decorative script.") == \
            "clean sans"
        assert "spiral" not in strip_negated_spans(
            "soft arcs; no powder spiral anywhere")


class TestReplacementMatrixPasses:
    """The user's Editorial Soft Radiance / Geometric Halo / Powder Drift
    replacement set must clear every gate: signatures AND content."""

    def _set(self):
        d1 = _direction(
            name="Editorial Soft Radiance",
            design_axis="typography-led — typography is the artwork",
            layout_structure="asymmetric editorial grid; large stacked BAKED "
                             "POWDER typography; strong whitespace. "
                             + COPY_BLOCK,
            focal_hierarchy="product name leads; typography is the artwork",
            typography="condensed editorial sans-serif; oversized product "
                       "name; small neutral supporting sans-serif",
            color_system="light blush pink; ivory; restrained rose-gold "
                         "accent",
            graphic_elements="one very small radiance line or powder-dot "
                             "accent; decorative coverage below 10%",
            imagery_approach="live typography and vector rules only; zero "
                             "decorative raster dependency",
            emotional_tone="refined, editorial, confident",
            prompt_seed="editorial type field, soft radiance")
        d2 = _direction(
            name="Geometric Halo",
            design_axis="geometry-led — a restrained geometric radiance "
                        "structure",
            layout_structure="centered and balanced; circular arched halo "
                             "occupying no more than 20%. " + COPY_BLOCK,
            focal_hierarchy="motif leads; centered halo is the identity",
            typography="high-contrast serif for BAKED POWDER; restrained "
                       "sans-serif for Spanish and supporting copy",
            color_system="light sky blue; white; pale champagne accent",
            graphic_elements="thin concentric arcs; controlled halo; no "
                             "powder spiral; no particles",
            imagery_approach="native paths and strokes; no raster dependency",
            emotional_tone="serene, calm, luminous",
            prompt_seed="radiant geometric halo")
        d3 = _direction(
            name="Powder Drift",
            design_axis="movement-led — directional powder stream",
            layout_structure="diagonal corner-led movement toward the "
                             "center; front mostly open and light. "
                             + COPY_BLOCK,
            focal_hierarchy="motif leads; movement across panels",
            typography="rounded geometric sans-serif, humanist warmth",
            color_system="light peach; soft mint; warm ivory",
            graphic_elements="sparse native-vector particles; short flowing "
                             "vector lines; coverage no more than 20%; no "
                             "circular compact spiral; no centered halo",
            imagery_approach="bounded vector particles and editable flow "
                             "paths; zero decorative raster dependency",
            emotional_tone="fresh, light and airy",
            prompt_seed="powder drift across panels")
        return [d1, d2, d3]

    def test_replacement_matrix_passes_signatures(self):
        codes, _ = validate_semantic_distinctness(self._set())
        assert codes == [], codes

    def test_replacement_matrix_passes_content(self):
        codes = validate_direction_content(BRIEF, _doc(self._set()))
        assert codes == [], codes

    def test_replacement_typography_classes_all_differ(self):
        classes = [classify(d["typography"], "typography_family")
                   for d in self._set()]
        assert classes == ["CONDENSED_EDITORIAL_SANS", "MIXED_SERIF_SANS",
                           "GEOMETRIC_ROUNDED_SANS"]


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key")
class ReplanSafetyTests(TestCase):
    def setUp(self):
        from apps.core.models import Brand
        from apps.pipeline.models import CreativeBrief, DesignTask
        from apps.pipeline.tests.direction_fixtures import valid_document
        self.user = User.objects.create_superuser("t2a6d", "t@t.com", "pw")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="b")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="Baked Powder carton",
            status="awaiting_direction_selection", created_by=self.user)
        doc = valid_document()
        self.brief = CreativeBrief.objects.create(
            task=self.task, directions=doc["directions"],
            design_intent={k: v for k, v in doc.items() if k != "directions"},
            selected_direction_id="")
        self.old_ids = [d["direction_id"] for d in doc["directions"]]

    def _replan(self):
        from apps.pipeline.services.direction_replan import (
            replan_design_directions,
        )
        with patch("apps.pipeline.tasks.run_aria_pipeline.delay") as enqueue:
            with self.captureOnCommitCallbacks(execute=True):
                result = replan_design_directions(
                    self.task, self.user, "replace the set: too similar")
        return result, enqueue

    def test_replan_archives_and_clears_without_duplicates(self):
        from apps.pipeline.models import AgentLog, CreativeBrief
        result, enqueue = self._replan()
        self.task.refresh_from_db()
        self.brief.refresh_from_db()
        # archived verbatim, still available for audit
        archive = AgentLog.objects.get(pk=result["archived_log_id"])
        archived_ids = archive.payload["archived_direction_ids"]
        self.assertEqual(archived_ids, self.old_ids)
        self.assertTrue(archive.payload["design_intent"])
        # active set cleared — old directions are NOT active
        self.assertEqual(self.brief.directions, [])
        self.assertEqual(self.brief.design_intent, {})
        self.assertEqual(self.brief.selected_direction_id, "")
        self.assertEqual(
            CreativeBrief.objects.filter(task=self.task).count(), 1)
        self.assertEqual(self.task.status, "queued")
        self.assertEqual(self.task.gate_1_notes,
                         "replace the set: too similar")
        enqueue.assert_called_once_with(self.task.pk)

    @patch("apps.pipeline.agents.image_producer.openai.images.generate")
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    @patch("apps.pipeline.agents.creative_director.call_claude")
    def test_replanned_run_pauses_with_exactly_three_and_no_renders(
            self, mock_cd, mock_pe, mock_img):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import GeneratedImage
        from apps.pipeline.tests.direction_fixtures import valid_document
        block = MagicMock()
        block.type = "text"
        block.text = json.dumps(valid_document())
        response = MagicMock()
        response.content = [block]
        mock_cd.return_value = response
        self._replan()
        # [his final goal, 2026-10-05, B4, re-pinned: "NO PROMPT STEP"] the new plan goes straight to its drawing
        from apps.pipeline.tests.test_phase2a4 import _drawing_recorded
        drawn = []
        with patch.object(ARIAAgent, "_render_each_direction", _drawing_recorded(drawn)):
            ARIAAgent(self.task.id).run()
        self.task.refresh_from_db()
        self.brief.refresh_from_db()
        self.assertEqual((drawn, self.task.status), ([None], "awaiting_gate_1"))
        self.assertEqual(len(self.brief.directions), 3)
        self.assertEqual(self.brief.selected_direction_id, "")
        self.assertEqual(self.task.gate_1_notes, "")   # feedback consumed
        mock_pe.assert_not_called()
        mock_img.assert_not_called()
        self.assertEqual(
            GeneratedImage.objects.filter(task=self.task).count(), 0)
        # the feedback reached the Creative Director's user message
        _, content = mock_cd.call_args[0][:2]
        text = content if isinstance(content, str) else content[-1]["text"]
        self.assertIn("replace the set: too similar", text)

    def test_replan_refuses_after_selection(self):
        from apps.pipeline.services.direction_replan import ReplanError
        self.brief.selected_direction_id = self.old_ids[0]
        self.brief.save()
        with self.assertRaises(ReplanError) as ctx:
            self._replan()
        self.assertEqual(ctx.exception.code, "REPLAN_ALREADY_SELECTED")

    def test_replan_refuses_outside_the_pause(self):
        from apps.pipeline.services.direction_replan import ReplanError
        self.task.status = "failed"
        self.task.save()
        with self.assertRaises(ReplanError) as ctx:
            self._replan()
        self.assertEqual(ctx.exception.code, "REPLAN_NOT_PAUSED")


class TestRenderIsNotThePrintedSurface:
    """§BH57(b). Task 86 — the owner's own Phase 1 brief, first run with every connectable wire live —
    produced three directions and every one was refused unrendered with PRODUCTION_RASTER_DEPENDENCY. The
    clause, identical in all three:

        Render is photographic in style; all printed decoration is vector-only.

    The validator exists for "a direction whose PRINTED surface is a photograph". This says the opposite in
    the same sentence. It survived because `strip_negated_spans` splits on `[.;:\\n]`, so the semicolon put
    the disclaimer in a different clause, and only a NEGATIVE phrasing had ever passed — measured across
    three runs of the same brief, tasks 84 and 85 both wrote "No photographic ... in printed decoration" and
    scored zero hits.

    Same class as TestZeroIsNegation above, a different phrasing.
    """

    TASK86 = ("Concept render: compact open at 45 degrees on a pale silk surface, ribbon decoration "
              "visible on lid, four color pans in base. Render is photographic in style; all printed "
              "decoration is vector-only.")

    def test_the_actual_task_86_clause_no_longer_fires(self):
        d = _direction(imagery_approach=self.TASK86)
        codes = validate_direction_content(BRIEF, _doc([d] * 3))
        assert not any("PRODUCTION_RASTER_DEPENDENCY" in c for c in codes), codes

    def test_a_photograph_on_the_printed_surface_still_fires(self):
        """The guard the check exists for. Nothing about what is ALLOWED has moved."""
        d = _direction(graphic_elements="The lid carries a macro photograph of a damask rose")
        codes = validate_direction_content(BRIEF, _doc([d, _direction(), _direction()]))
        assert "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_the_render_exemption_cannot_be_used_to_smuggle_a_printed_photograph(self):
        """THE HOLE THIS WOULD HAVE HAD, closed on purpose. The house splitter deliberately does not break
        on "and" — it would sever a negation from the words it governs — so a render-subject exemption
        based on the first three words alone would have carried "and the lid is printed with it" along
        with it. The exemption also requires the clause to name NO printed surface."""
        d = _direction(imagery_approach="Render is photographic and the lid is printed with it")
        codes = validate_direction_content(BRIEF, _doc([d, _direction(), _direction()]))
        assert "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_a_photographic_clause_that_is_not_about_the_render_still_fires(self):
        """The exemption is about the clause's SUBJECT, not the presence of the word "render" anywhere."""
        d = _direction(design_axis="Image-led: a photography-first treatment is the production surface")
        codes = validate_direction_content(BRIEF, _doc([d, _direction(), _direction()]))
        assert "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_the_offending_clause_is_reported_so_the_repair_can_quote_it(self):
        """§BH57(b) Part B. The repair instruction used to open "its PRINTED decoration is a photograph"
        as a statement of fact. On task 86 that was false, and the failing count went UP across the two
        attempts — 2, then 3. The repair quotes this instead of asserting anything."""
        d = _direction(graphic_elements="The lid carries a macro photograph of a damask rose")
        assert "macro photograph" in raster_offending_clause(d)
        assert raster_offending_clause(_direction(imagery_approach=self.TASK86)) == ""


class TestTheProductIsWhatIsPhotographed:
    """§BH68(a): "THE PLANNER MUST PASS ITS OWN CHECK BEFORE I TEST ... measure why the check still fails and fix the
    cause." Every raster flag on record was measured (20 directions, tasks 51-96): the check refused the CONCEPT RENDER
    far more often than a photographic print — the product photographed for the render, in the very fields the prompt
    gives the render. Two readings are added and the rule is not moved; these are the proof, both ways."""

    #: VERBATIM from the rejected payloads of tasks 90, 93, 95 and 96 — each flagged at 9f7f2ec, each about the render
    RENDER_ON_RECORD = (
        'the closed compact and carton photographed on a blush silk surface under warm diffused light, shallow depth of field',
        "carton and closed compact photographed at a slight angle on a blush silk surface, a real powder puff beside them, soft rim light catching the carton's spot uv particles",
        'the closed compact and carton are visualised in a warm diffused studio scene on a blush surface — this is a render photograph of the physical product,',
        'the carton standing upright on a warm cream surface with the compact open beside it showing the powder pan, warm side light echoing the gold circle — this is a render photograph of the physical product only',
        'the carton and closed compact visualised as a packshot in a soft blush-toned studio environment with a powder puff beside them, rim light catching the surface — this is a render photograph of the physical product only,',
        'the carton photographed at a 15-degree angle under raking light so the embossed polygon and petal particles catch directional gloss against the matte body',
        'the carton photographed at a gentle angle under directional studio light so the embossed foil polygon catches directional gloss against the matte body',
        'the carton and compact photographed on a warm cream silk surface with soft side-light catching the foil wordmark',
        'a folding carton with a warm-gold foil upper panel bearing an engraved abstract petal-lattice relief and the rose-gold bbrose wordmark, transitioning to a matte pale petal lower zone with a bilingual product name in deep rose, photographed at a slight three-quarter angle so the foil panel catches directional light against the soft matte body, concept render only',
        'spot uv rings catch light differently from matte ground — photographed as a studio packshot',
        'compact photographed flat-lay or at a slight 10° tilt, very even soft diffused light, to show the typographic clarity and the rule as a physical design element',
        'this lighting and photography exist only in the concept render file — nothing photographic appears in the print artwork',
        'compact photographed at a 20° tilt on a pale pink silk-effect draped surface (silk surface is concept-render scene only —',
    )

    #: a photograph ON or AS the printed decoration — render-labelled ones included — must still fire
    MUST_STILL_FIRE = (
        'concept render only — the lid artwork is a macro photograph of rose petals',
        'the carton panel printed with a photographed rose field',
        'photographic petal texture across the label',
        'render is photographic and the lid is printed with it',
        'a photograph of dew drops forms the lid decoration',
        'macro photography of powder texture as the printed background',
        'the compact photographed on silk, a photograph of petals printed on its lid',
        'a photograph of the product printed on the panel',
        'the compact photographed with its lid carrying a photographic rose texture',
        'the concept render shows a photographic rose image printed across the carton',
        'nothing but a macro photograph of petals covers the label',
    )

    #: on record and flagged on purpose after this change: task 51's photographic surface, a true positive, and task
    #: 87's clause, which mixes the render's photography with the lid's printed type in one sentence
    STAYS_ON_RECORD = (
        'image-led — a full-bleed macro photograph is the entire surface',
        'closed bbrose rose glow palette compact on blush-linen surface, lid showing large interleaved arabic and english product names in deep rose and warm cream on a full blush ground, bbrose rose-gold wordmark above, two hairline rose-gold rules framing the type, editorial luxury beauty photography, warm directional light',
    )

    def _fires(self, text):
        d = _direction(imagery_approach=text)
        codes = validate_direction_content(BRIEF, _doc([d, _direction(), _direction()]))
        return "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_every_render_clause_on_record_no_longer_fires(self):
        assert [t for t in self.RENDER_ON_RECORD if self._fires(t)] == []

    def test_a_photograph_on_the_printed_decoration_still_fires_render_label_or_not(self):
        assert [t for t in self.MUST_STILL_FIRE if not self._fires(t)] == []

    def test_bh70_answer_3_his_core_products_are_photographed_for_the_render_as_a_compact_is(self):
        """The owner's answer of 2026-09-27 to the §BH70 report's third question: "Yes, free that check. Lipstick,
        mascara and pencil are core products." The sentence this check passed for a compact and refused for his slim
        forms (acceptance-time entry 16) reads as the render for each; a photograph printed on one still fires."""
        said = "the {} photographed at a 15-degree angle under raking light on a pale pink silk surface"
        forms = ("compact", "lipstick", "mascara", "pencil", "eyeliner", "liner", "lip gloss", "wand vial")
        assert [f for f in forms if self._fires(said.format(f))] == []
        printed = "the {} photographed on silk, a photograph of petals printed on its label"
        assert [f for f in forms if not self._fires(printed.format(f))] == []

    def test_what_stays_on_record_still_fires(self):
        assert all(self._fires(t) for t in self.STAYS_ON_RECORD)

    def test_the_nothing_negation_is_this_checks_own_and_the_shared_cues_are_untouched(self):
        """The diversity classifiers read NEGATION_SPAN_CUES; "nothing" is cut only inside the raster check."""
        from apps.pipeline.direction_signature import NEGATION_SPAN_CUES, strip_negated_spans
        assert "nothing " not in NEGATION_SPAN_CUES
        assert "photographic" in strip_negated_spans("nothing photographic appears in the print artwork")

    def test_the_repair_says_exactly_the_form_the_reader_accepts(self):
        from apps.pipeline.design_direction_generator import _repair_message
        d = _direction(imagery_approach="The lid carries a macro photograph of a damask rose")
        msg = _repair_message(["PRODUCTION_RASTER_DEPENDENCY:direction[0]"], "{}", directions=[d])
        # [THE OWNER'S SECOND ANSWER OF 2026-09-25: "Task 106 is caused by your own repair wording." The forms now name
        # THE PRODUCT, which the reader accepts for any product, and "the subject of the photography" — the phrase the
        # planner copied and this check refused — is gone]
        assert "'the product photographed on a blush silk surface'" in msg
        assert "'a render photograph of the product'" in msg
        assert "subject of the photography" not in msg
        # and the forms it names are ones the reader accepts
        assert not self._fires("the product photographed on a blush silk surface")
        assert not self._fires("a render photograph of the product")

    def _fires_in(self, field, text):
        d = _direction(**{field: text})
        codes = validate_direction_content(BRIEF, _doc([d, _direction(), _direction()]))
        return "PRODUCTION_RASTER_DEPENDENCY:direction[0]" in codes

    def test_no_sentence_of_the_raster_repair_trips_the_check_wherever_a_planner_copies_it(self):
        """THE OWNER'S SECOND ANSWER OF 2026-09-25: "Task 106 is caused by your own repair wording." The planner copied
        the repair's "make the PRODUCT the subject of the photography" into its render sentence and this check refused
        the copy. The test that would have caught it: every sentence of the repair's raster block and of the
        explanation's raster line, placed in every field the check reads — none may fire."""
        import re

        from apps.pipeline.design_direction_generator import _repair_message
        from apps.pipeline.direction_content import _RASTER_FIELDS
        from apps.pipeline.direction_signature import explain_validation_failure
        code = "PRODUCTION_RASTER_DEPENDENCY:direction[0]"
        msg = _repair_message([code], "{}", directions=None)
        block = msg[msg.index("## Raster-dependency failures"):]
        guidance = [line for line in explain_validation_failure([_direction(), _direction(), _direction()], [code])
                    if "rebuildable from native vectors" in line]
        assert guidance, "the explanation's raster line is gone"
        sentences = [s.strip(" -") for part in [block] + guidance for s in re.split(r"(?<=[.;:?!])\s+", part)
                     if len(s.strip(" -")) > 3]
        assert len(sentences) >= 8
        assert [(field, s) for s in sentences for field in _RASTER_FIELDS if self._fires_in(field, s)] == []

    def test_task_106_copied_the_old_phrase_and_it_fired_and_the_new_repair_has_none(self):
        """AgentLog 1844, attempt 2, verbatim: the render sentence ends with the repair's own phrase, and that tail is
        what fired — the same sentence without it passes."""
        from apps.pipeline.design_direction_generator import _repair_message
        from apps.pipeline.tests.fixtures_agentlog1844_1865 import TASK_106
        text = TASK_106["direction_0"]["imagery_approach"]
        tail = " — the physical product is the subject of the photography"
        assert tail in text and TASK_106["codes"] == ["PRODUCTION_RASTER_DEPENDENCY:direction[0]"]
        assert self._fires_in("imagery_approach", text)
        assert not self._fires_in("imagery_approach", text.replace(tail, ""))
        msg = _repair_message(["PRODUCTION_RASTER_DEPENDENCY:direction[0]"], "{}", directions=None)
        assert "subject of the photography" not in msg


def test_finding1_the_palette_check_reads_colours_as_written_its_rules_unchanged():
    """His test day finding 1 (2026-09-29, design 116): his three colour worlds were refused as "the same set of
    chromatic colours" — pink, blush, gold, deep rose each. "No hot pink" in two lines was read as naming pink, and
    coral, the third world, is a colour the check could not see. Read as written, run 2's second attempt opens on three
    colours and is not refused; the three rules still refuse what they refused (the existing tests above)."""
    from apps.pipeline.direction_content import _check_palette_distinctness, palette_evidence
    run2_attempt2 = [
        "Upper zone: hot pink #E8327A. Lower zone: soft blush #F2C4CE. Drip paths: gradient hot pink to pale cream. "
        "Gold outlined type: Warm Gold #CBA87D. Deep Rose #8B3A52 for BBROSE logo and descriptor lines. Cream #FAF3EC "
        "for back panel ground.",
        "Ground: Blush #F2C4CE. Secondary ground: Warm Cream #FAF3EC for back panel. Type: Deep Rose #8B3A52 for product "
        "name and descriptor lines. Gold: Warm Gold #CBA87D for foil logo, drip path, and petal outlines. No hot pink. "
        "Accent: single Pale Petal #F7DDE3 petal fills at very low opacity.",
        "Ground: Warm Cream #FAF3EC. Illustration linework: Deep Rose #8B3A52 for primary contour paths. Secondary "
        "linework and cross-hatch fills: Warm Gold #CBA87D. Coconut flesh fill: pale cream #FFF8EF with light hatching. "
        "Rose petal fills: Blush #F2C4CE with Deep Rose contour paths. Base coral band: warm coral #E8735A. Product "
        "name: Deep Rose #8B3A52. No hot pink.",
    ]
    directions = [{"color_system": text} for text in run2_attempt2]
    assert _check_palette_distinctness(directions) == []
    rows = palette_evidence(directions)["rows"]
    assert [r["primary"] for r in rows] == ["pink", "blush", "deep rose"]
    assert "pink" not in rows[1]["chromatic"] and "pink" not in rows[2]["chromatic"]
    assert "coral" in rows[2]["chromatic"]
    refused = [{"color_system": "Ground: blush. Accents: gold. No coral."},
               {"color_system": "Blush field with gold. Never coral."},
               {"color_system": "Blush ground, gold type; no coral anywhere."}]
    assert _check_palette_distinctness(refused) == ["PALETTE_SYSTEMS_NOT_DISTINCT"]

