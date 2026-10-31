"""Phase 2B-3B §1-§5/§9/§10 — production-method contract + validation.

Methods are derived from confirmed-zone techniques. The invariant under review:
a machine-proposed-then-confirmed technique is NEVER manufacturer authority, so
authority stays UNVERIFIED by construction and the gate stays blocked. Colour /
line / text checks measure the EMITTED geometry; a PASS never clears the gate,
a FAIL is advisory. All codes are production-readiness codes.
"""
from __future__ import annotations
from django.test import TestCase

from apps.ire import container_production_method as pm
from apps.ire.compose_container import compose_container_graph
from apps.pipeline.services import container_contract as cc
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)


def _profile_zones(archetype="bottle"):
    prof = cc.build_inferred_profile(archetype, estimates={
        "body_width_mm": 40.0, "body_height_mm": 110.0,
        "cap_width_mm": 20.0, "cap_height_mm": 13.0})
    return prof, cc.propose_zones(prof)


def _doc(archetype="bottle", motif=True):
    prof, zones = _profile_zones(archetype)
    motif_spec = None
    if motif:
        from apps.ire import container_motif as cm
        motif_spec = cm.build_motif_spec(
            {"verified": True, "motif_signature": "powder constellation"},
            {"fields": {}}, zones, prof)
    bb = build_backbone(ContainerProfile(archetype=archetype, width_mm=40,
                                         height_mm=110))
    return compose_container_graph(bb, product_name="Rose Nectar",
                                   name_lines=["Rose Nectar"], zones=zones,
                                   native=True, motif_spec=motif_spec)


def test_method_type_maps_technique_and_surface():
    prof, zones = _profile_zones("bottle")
    by_surface = {z["parent_surface"]: z for z in zones}
    # bottle front print zone → SCREEN_PRINT; cap-top → CAP_PRINT
    assert pm.method_type_for(by_surface["BODY_FRONT"]) == "SCREEN_PRINT"
    assert pm.method_type_for(by_surface["CAP_TOP"]) == "CAP_PRINT"
    # tube crimp bottom-code zone → BOTTOM_INKJET_CODE
    _, tzones = _profile_zones("tube")
    crimp = next(z for z in tzones if z["zone_type"] == "BOTTOM_CODE_ZONE")
    assert pm.method_type_for(crimp) == "BOTTOM_INKJET_CODE"


def test_authority_is_unverified_by_construction():
    prof, zones = _profile_zones("bottle")
    rec = pm.build_production_methods(zones, prof)
    assert rec["methods"]
    for m in rec["methods"]:
        assert m["authority_state"] != pm.VERIFIED_MANUFACTURER_CAPABILITY
        assert m["authority_state"] == pm.INFERRED_NONAUTHORITATIVE
        assert m["verification_source"] == pm.SRC_INFERRED
        assert m["manufacturer_identity"] == ""
    assert rec["all_manufacturer_verified"] is False
    assert rec["method_set_hash"]


def test_explicit_user_technique_uses_user_request_but_never_clears_gate():
    # §0 (2B-3C): a human-chosen technique (zone source EXPLICIT_USER_FACT) is
    # recorded as EXPLICIT_USER_REQUEST / USER_REQUESTED_UNVERIFIED — design
    # intent, never machine inference, and still no manufacturer authority.
    prof, zones = _profile_zones("bottle")
    zones[0]["source"] = "EXPLICIT_USER_FACT"          # user confirmed this one
    rec = pm.build_production_methods(zones, prof)
    m0 = rec["methods"][0]
    assert m0["verification_source"] == pm.SRC_USER_REQUEST
    assert m0["authority_state"] == pm.USER_REQUESTED_UNVERIFIED
    assert m0["authority_state"] != pm.VERIFIED_MANUFACTURER_CAPABILITY
    # the machine-proposed peers stay INFERRED (distinct branch)
    assert any(m["verification_source"] == pm.SRC_INFERRED
               for m in rec["methods"][1:])
    # neither branch clears the gate
    rep = pm.validate_production_methods(rec, zones, prof, _doc(motif=False))
    assert pm.TECHNIQUE_UNVERIFIED in rep["codes"]


def test_method_hash_is_deterministic():
    prof, zones = _profile_zones("jar")
    a = pm.build_production_methods(zones, prof)["method_set_hash"]
    b = pm.build_production_methods(zones, prof)["method_set_hash"]
    assert a == b and a


def test_validation_always_flags_unverified_and_needs_review():
    prof, zones = _profile_zones("bottle")
    rec = pm.build_production_methods(zones, prof)
    rep = pm.validate_production_methods(rec, zones, prof, _doc())
    # every method is unverified → gate blocked by construction
    assert pm.TECHNIQUE_UNVERIFIED in rep["codes"]
    assert pm.TRAPPING_REVIEW_REQUIRED in rep["codes"]
    assert rep["manufacturer_verified"] is False


def test_motif_line_weight_and_color_count_are_measured():
    prof, zones = _profile_zones("bottle")
    rec = pm.build_production_methods(zones, prof)
    rep = pm.validate_production_methods(rec, zones, prof, _doc(motif=True))
    g = rep["measurements"]
    # the design-language motif strokes below a typical screen minimum → a
    # REAL measured line-weight signal (never silently scaled)
    assert g["min_line_weight_mm"] is not None
    assert pm.MINIMUM_LINE_WEIGHT_FAILED in rep["codes"]
    # a multi-colour motif exceeds the CAP_PRINT 2-colour limit
    assert g["printed_color_count"] >= 2


def test_pass_against_defaults_never_clears_the_gate():
    # even if we force-verify the constraint values, authority still blocks
    prof, zones = _profile_zones("bottle")
    rec = pm.build_production_methods(zones, prof)
    rep = pm.validate_production_methods(rec, zones, prof, _doc(motif=False))
    # no manufacturer verification anywhere → TECHNIQUE_UNVERIFIED present
    assert pm.TECHNIQUE_UNVERIFIED in rep["codes"]
    assert rep["manufacturer_verified"] is False


# ---------------------------------------------------------------------------
# §BH57(e) / §BH55(a) — A COMPACT HAS SURFACES TO DECORATE.
#
# Written when the owner's Rose Glow Palette reached the shape gate and was
# REFUSED: "CONTAINER_PROFILE_CONFIRMATION_REQUIRED: unknown archetype". A
# SECOND archetype registry — `_ARCHETYPE_SURFACES`, the map of which surfaces
# each form offers — still held bottle, jar and tube, while the editor's
# vocabulary had already accepted compact. A form is only real when both know
# it. The surfaces are the owner's own two words, "the lid artwork and the
# base panel", plus the two side walls of a closed case.
# ---------------------------------------------------------------------------


class CompactDecorationSurfaceTests(TestCase):

    PROFILE = {
        "schema_version": "container_profile/1.0",
        "archetype": "compact", "variant": "rounded_rect",
        "fields": {
            "body_width_mm": {"value": 110.0, "source": "USER_CONFIRMED_VISUAL_PROFILE",
                              "verification": "USER_CONFIRMED"},
            "body_height_mm": {"value": 95.0, "source": "USER_CONFIRMED_VISUAL_PROFILE",
                               "verification": "USER_CONFIRMED"},
            "body_depth_mm": {"value": 18.0, "source": "USER_CONFIRMED_VISUAL_PROFILE",
                              "verification": "USER_CONFIRMED"},
        },
    }

    def test_a_compact_is_a_known_archetype_to_the_contract_not_only_to_the_editor(self):
        """The refusal this fixes: the editor accepted `compact` and the contract did not."""
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container.silhouettes import SUPPORTED_ARCHETYPES
        problems = cc.validate_profile(self.PROFILE)
        self.assertEqual([p for p in problems if "unknown archetype" in p], [])
        # and the two registries agree, which is the thing that was untrue
        for archetype in SUPPORTED_ARCHETYPES:
            self.assertTrue(cc.surfaces_for(archetype),
                            "%s can be drawn but offers no surface to decorate" % archetype)

    def test_the_surfaces_are_the_lid_and_the_base_and_their_two_walls(self):
        from apps.pipeline.services import container_contract as cc
        self.assertEqual(cc.surfaces_for("compact"),
                         ("LID_TOP", "LID_EDGE", "BASE_BOTTOM", "BASE_EDGE"))
        # the mirror and the pan field are INSIDE the case and are not printed: they are
        # geometry on the backbone, never decoration surfaces
        self.assertNotIn("MIRROR", cc.surfaces_for("compact"))
        self.assertNotIn("PAN_FIELD", cc.surfaces_for("compact"))

    def test_the_lid_and_base_are_the_plan_and_the_walls_are_the_thickness(self):
        """A compact is drawn in PLAN: width x height is the lid seen from above, depth is the closed
        thickness, which the lid and the base divide between them."""
        from apps.pipeline.services import container_contract as cc
        g = cc.surface_geometry(self.PROFILE)
        self.assertEqual((g["LID_TOP"]["w"], g["LID_TOP"]["h"]), (110.0, 95.0))
        self.assertEqual((g["BASE_BOTTOM"]["w"], g["BASE_BOTTOM"]["h"]), (110.0, 95.0))
        self.assertEqual(g["LID_EDGE"]["h"], 9.0)
        self.assertEqual(g["BASE_EDGE"]["h"], 9.0)
        self.assertEqual(g["LID_TOP"]["curvature"], cc.FLAT)

    def test_the_two_zones_are_the_ones_the_brief_names(self):
        """His words: "the lid artwork and the base panel"."""
        from apps.pipeline.services import container_contract as cc
        zones = cc.propose_zones(self.PROFILE)
        by_surface = {z["parent_surface"]: z for z in zones}
        self.assertEqual(sorted(by_surface), ["BASE_BOTTOM", "LID_TOP"])
        for z in zones:
            self.assertIn(z["zone_type"], cc.ZONE_TYPES)
            self.assertGreater(z["width"], 0)
            self.assertGreater(z["height"], 0)

    def test_the_base_panel_is_measured_generously_because_the_question_is_whether_it_holds_the_copy(self):
        """His brief: the regulatory copy goes "on the surface that can hold them — the carton or the base,
        MEASURED, not assumed". A base zone cropped for looks would answer that question falsely."""
        from apps.pipeline.services import container_contract as cc
        zones = {z["parent_surface"]: z for z in cc.propose_zones(self.PROFILE)}
        base, lid = zones["BASE_BOTTOM"], zones["LID_TOP"]
        # §BH67(c)3 made the LID the whole lid face, so the lid is now the larger of the two — the comparison this
        # test used to make was between two executor choices, and the lid's is his now. The base's own generosity,
        # the point of the test, is measured absolutely and stands.
        self.assertGreater(lid["width"] * lid["height"], base["width"] * base["height"])
        self.assertGreater(base["width"] * base["height"], 8000.0)      # mm^2, room for a panel of copy

    def test_bh67c3_the_lid_zone_is_the_whole_lid_face(self):
        """§BH67(c)3: "THE COMPACT'S PRINT ZONE IS THE WHOLE LID". The zone is the lid face the silhouette draws —
        the plan less the hinge band — at full width, to the front edge, with the 3.0 mm safe margin standing."""
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container.silhouettes import COMPACT_DEFAULTS, compact_lid_face
        lid = {z["parent_surface"]: z for z in cc.propose_zones(self.PROFILE)}["LID_TOP"]
        hinge = COMPACT_DEFAULTS["hinge_mm"]
        self.assertEqual((lid["x"], lid["y"], lid["width"], lid["height"]), (0.0, hinge, 110.0, 95.0 - hinge))
        self.assertEqual(compact_lid_face(110.0, 95.0),
                         {"x_mm": 0.0, "y_mm": hinge, "width_mm": 110.0, "height_mm": 95.0 - hinge})
        self.assertEqual(lid["safe_margin_mm"], 3.0)
        self.assertEqual(lid["zone_type"], "FRONT_PRINT_ZONE")


# ---------------------------------------------------------------------------
# §BH61(c) — THE CONFORMANCE TEST. Both halves, per §BH61(a).
#
# The owner found the THIRD per-archetype registry by using the product: he
# chose a palette and the shape step offered him a Bottle, pre-selected. "Had I
# clicked through, my palette would have been rebuilt as a bottle and nothing
# would have said so."
#
# "so the next archetype fails at the gate with a list of what it lacks,
#  instead of in front of me."
# ---------------------------------------------------------------------------


class ArchetypeConformanceTests(TestCase):
    """HALF ONE: every declared archetype has every dependent vocabulary."""

    def test_every_archetype_has_every_dependent_vocabulary(self):
        from apps.pipeline.targets.container import archetypes as A
        lacking = {a: A.missing_vocabulary(a) for a in A.ARCHETYPES
                   if A.missing_vocabulary(a)}
        self.assertEqual(lacking, {},
                         "an archetype is declared but incomplete — it lacks: %s" % lacking)

    def test_every_form_declares_its_primary_surface_and_only_a_face_escapes_au1(self):
        """§BH66(a), his words: "§AU1 governs bottle, jar and tube fronts as it always has. It does NOT govern a
        compact lid, and it does not govern any future form whose primary surface is its face." One fact per form,
        DECLARED — never inferred from the form's name — and every form's primary surface is one of its own."""
        from apps.pipeline.targets.container import archetypes as A
        for archetype in A.ARCHETYPES:
            declared = A.primary_surface_of(archetype)
            self.assertIn(declared["surface"], A.surfaces_of(archetype))
            self.assertIn(declared["kind"], (A.FRONT, A.FACE))
        # [§BH71 PART 3: a tin's lid is the whole of the product as it is held — a face; a sachet's front is printed
        # as a label is, ruled]
        self.assertEqual({a for a in A.ARCHETYPES if A.is_face(a)}, {"compact", "tin"})
        self.assertEqual(A.primary_surface_of("compact"), {"surface": "LID_TOP", "kind": A.FACE})

    def test_a_new_archetype_fails_here_with_a_list_of_what_it_lacks(self):
        """THE POINT OF THE TEST, exercised rather than asserted: a fifth form declared with no
        vocabulary is reported by NAME with the list, which is what the owner asked the gate to print."""
        from apps.pipeline.targets.container import archetypes as A
        # [§BH71 PART 3: the sachet is declared now — the form nobody declared is a hamper]
        self.assertEqual(
            sorted(A.missing_vocabulary("hamper")),
            sorted(list(A.DEPENDENT_VOCABULARY) + ["(not declared)"]))

    def test_every_dependent_registry_reads_the_one_declaration(self):
        """The three registries the owner's three failures found — the drawer, the decoration surfaces
        and the editor — agree with the declaration BY CONSTRUCTION, not by coincidence."""
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container import archetypes as A
        from apps.pipeline.targets.container.silhouettes import SUPPORTED_ARCHETYPES
        from apps.pipeline.targets.ui import CONTAINER_EDITOR_ARCHETYPES
        self.assertEqual(set(SUPPORTED_ARCHETYPES), set(A.ARCHETYPES))
        for archetype in A.ARCHETYPES:
            self.assertEqual(cc.surfaces_for(archetype), A.surfaces_of(archetype))
        editor = {a["key"]: a for a in CONTAINER_EDITOR_ARCHETYPES if a["confirmable"]}
        self.assertEqual(set(editor), set(A.ARCHETYPES))
        for key, entry in editor.items():
            self.assertEqual([tuple(v) for v in entry["variants"]], list(A.variants_of(key)))
            self.assertEqual([tuple(c) for c in entry["caps"]], list(A.closures_of(key)))

    def test_a_field_that_does_not_apply_to_the_chosen_form_is_not_offered(self):
        """§BH61(b), his words: "no neck proportion on a hinged case, no cap dimensions where there is
        no cap". The proportions list was FLAT — the same four controls for every form."""
        from apps.pipeline.targets.ui import proportions_for
        compact = [p["key"] for p in proportions_for("compact")]
        bottle = [p["key"] for p in proportions_for("bottle")]
        self.assertNotIn("neck_ratio", compact)
        self.assertIn("neck_ratio", bottle)
        from apps.pipeline.targets.container import archetypes as A
        self.assertFalse(A.VOCABULARY["compact"]["has_cap_dimensions"])
        self.assertTrue(A.VOCABULARY["bottle"]["has_cap_dimensions"])

    def test_a_slim_form_is_entered_and_confirmed_at_its_real_size(self):
        """§BH70(1), items 3 and 14 of the list sent to him: a tube could not be entered narrower than 20 mm, so "a
        pencil, eyeliner or slim mascara can't be entered at its real size", and a pencil had no form at all. A slim
        and a full one of each slim form — a 7 and a 12 mm pencil, a 12 and a 20 mm mascara, a 15 and a 24 mm
        lipstick — is accepted by the server, reachable on the form's own rows, and CONFIRMABLE: the print areas the
        contract proposes for it pass the contract at that size. Below its own floor it is refused, by the same rows."""
        from apps.pipeline.services import container_contract as cc
        from apps.pipeline.targets.container import archetypes as A
        from apps.pipeline.targets.ui import proportions_for, validate_container_profile_payload
        real = {"lipstick": ((70, 15), (90, 24)), "mascara": ((120, 12), (140, 20)), "pencil": ((150, 7), (120, 12))}
        for form, sizes in real.items():
            variant, closure = A.variants_of(form)[0][0], A.closures_of(form)[0][0]
            rows = {p["key"]: (p["min"], p["max"]) for p in proportions_for(form)}
            for h, w in sizes:
                payload = {"archetype": form, "variant": variant, "cap_style": closure,
                           "height_mm": h, "width_mm": w, "depth_mm": w}
                self.assertEqual(validate_container_profile_payload(payload), [], (form, h, w))
                self.assertTrue(rows["width_mm"][0] <= w <= rows["width_mm"][1], (form, w, rows))
                record = cc.merge_user_profile(cc.build_inferred_profile(form, variant), {
                    "archetype": form, "variant": variant, "cap_type": closure,
                    "body_height_mm": h, "body_width_mm": w, "body_depth_mm": w})
                zones = cc.propose_zones(record)
                self.assertTrue({"FRONT_PRINT_ZONE", "BACK_PRINT_ZONE"} <= {z["zone_type"] for z in zones}, zones)
                for zone in zones:
                    zone["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
                self.assertIsNone(cc.evaluate_confirmation(record, zones),
                                  (form, h, w, cc.validate_zone_set(zones, record)))
            floor = rows["width_mm"][0]
            self.assertTrue(validate_container_profile_payload(
                {"archetype": form, "height_mm": sizes[0][0], "width_mm": floor - 1, "depth_mm": floor}))

    def test_a_name_that_would_be_cut_off_is_named_before_anything_is_drawn(self):
        """§BH70(1) and his §BD(b), "A clipped brand name never ships": the shape step's own check. A pencil 7 mm across
        cannot carry "Rose Glow" across its front at the size a name prints — the stop names the word and both widths;
        a 12 mm pencil of the same name can. A 20 mm bottle named "Rosewaterglow" is stopped as well, which is not a
        slim form's defect but the front's; a 40 x 110 bottle named "Rose Nectar" is not; and a compact is never asked,
        because a face sets its name by the largest step its own lid holds (§BH68(b))."""
        from apps.pipeline.targets.container import name_fits_front
        from apps.pipeline.targets.container.silhouettes import ContainerProfile

        def stop(archetype, height_mm, width_mm, name):
            from apps.pipeline.targets.container import archetypes as A
            return name_fits_front(ContainerProfile(
                archetype=archetype, variant=A.variants_of(archetype)[0][0], cap_style=A.closures_of(archetype)[0][0],
                height_mm=height_mm, width_mm=width_mm), name)
        pencil = stop("pencil", 150, 7, "Rose Glow")
        self.assertEqual(pencil["code"], "CONTAINER_NAME_WIDER_THAN_ITS_FRONT")
        self.assertIn(pencil["word"], ("Rose", "Glow"))
        self.assertGreater(pencil["word_mm"], pencil["front_mm"])
        self.assertIn("Rose Glow", pencil["reason"])
        self.assertNotIn("CONTAINER_", pencil["reason"])
        self.assertIsNone(stop("pencil", 150, 12, "Rose Glow"))
        self.assertIsNotNone(stop("bottle", 60, 20, "Rosewaterglow"))
        self.assertIsNone(stop("bottle", 110, 40, "Rose Nectar"))
        self.assertIsNone(stop("compact", 95, 110, "Rosewaterglowingly"))

    def test_a_measurement_a_form_does_not_have_is_refused(self):
        """§BH70(1), item 13, and §BH61(b), his words: "no neck proportion on a hinged case, no cap dimensions where
        there is no cap". A compact's record said a person had verified its neck ratio of 0.42 — the shape step sent a
        neck for every form and the server took it. The server now refuses a neck for a form without one and a cap's
        sizes for a form without a cap; a bottle's neck and its cap's sizes are taken as before."""
        from apps.pipeline.targets.ui import validate_container_profile_payload as validate
        for form in ("jar", "tube", "compact", "lipstick", "mascara", "pencil"):
            self.assertTrue(any("neck_ratio does not apply" in e
                                for e in validate({"archetype": form, "neck_ratio": 0.42})), form)
        self.assertTrue(any("do not apply to Compact" in e
                            for e in validate({"archetype": "compact", "cap_width_mm": 20})))
        self.assertEqual(validate({"archetype": "bottle", "neck_ratio": 0.42, "cap_width_mm": 20,
                                   "cap_height_mm": 12}), [])

    def test_bh71_a_lid_the_concept_shows_is_learned_once_and_offered_to_every_design(self):
        """§BH71 PART 3, the owner's goal of 2026-09-28: "When a concept shows a shape the system doesn't know, it says
        so and offers to learn it." A shape the approved concept's own trace shows is learned at one call — once for its
        form — and the design is re-proposed with it: its variant, its length from the picture's aspect as seen, its
        zones and code place inside it. From then on it is a variant of the form at every design's shape step: offered
        with the server's own drawing, validated, and proposed when a concept or a brief shows it. A shape only a
        brief's words name, one the system does not draw, or one with no trace on record is refused by name."""
        from types import SimpleNamespace
        from django.contrib.auth.models import User
        from django.core.files.base import ContentFile
        from apps.core.models import Brand
        from apps.pipeline.models import DesignTask, GeneratedImage, LearnedShape, PackagingOutput
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.services import learned_shapes as ls
        from apps.pipeline.targets import ui
        from apps.pipeline.targets.container import _seed_outline_proposal, lid_shape_named_in
        from apps.pipeline.tests.test_vqr2b_concept_analysis import _lid_png
        brand = Brand.objects.create(name="B", master_brief="x")
        user = User.objects.create_user("learner")

        def task_with(kind="oval", source="the approved concept", trace=True):
            task = DesignTask.objects.create(brand=brand, task_text="an oval pressed powder compact",
                                             design_target="product_container", status="awaiting_container_profile")
            record = cc.build_inferred_profile("compact", "", {"body_width_mm": 110.0, "body_height_mm": 95.0,
                                                               "body_depth_mm": 18.0})
            record["unknown_shape"] = {"kind": kind, "words": "an %s lid" % kind, "source": source, "sentence": "s"}
            spec = {cc.PROFILE_SCHEMA: record, "container_profile": {"archetype": "compact", "variant": ""}}
            if trace:
                spec[co.SCHEMA] = {"state": co.TRACED_FROM_CONCEPT, "view": "PLAN", "kind": kind, "aspect": 0.7,
                                   "source_sha256": "ab" * 32}
            img = GeneratedImage.objects.create(task=task, direction_name="D")
            img.image_file.save("concept.png", ContentFile(_lid_png((250, 170), 0.0)), save=True)
            PackagingOutput.objects.create(task=task, approved_image=img, spec_sheet=spec)
            return task
        for task, why in ((task_with(source="the brief"), "a brief's words alone"),
                          (task_with(kind="heart"), "heart"), (task_with(trace=False), "trace")):
            with self.assertRaises(ls.NotLearnable) as refused:
                ls.learn(task, user)
            assert refused.exception.code == ls.NOT_LEARNABLE, why
        assert not LearnedShape.objects.exists()
        first = task_with()
        said = ui._unknown_shape(first)
        assert said["learnable"] and said["learn_url"] == "/api/tasks/%d/learn_shape/" % first.id
        assert not ui._unknown_shape(task_with(source="the brief"))["learnable"]
        assert ui.validate_container_profile_payload({"archetype": "compact", "variant": "learned_oval", "cap_style":
                                                      "clasp", "width_mm": 110, "height_mm": 77, "depth_mm": 18})
        row, created = ls.learn(first, user)
        assert created and (row.form, row.kind, row.source_task_id, row.learned_by) == ("compact", "oval", first.id, user)
        assert ls.learn(first, user) == (row, False)                                  # a replay: what it learned
        second = task_with()
        assert ls.learn(second, user) == (row, False) and LearnedShape.objects.count() == 1   # once for its form
        assert second.packaging_outputs.first().spec_sheet[cc.PROFILE_SCHEMA]["variant"] == "learned_oval"
        spec = first.packaging_outputs.first().spec_sheet
        record = spec[cc.PROFILE_SCHEMA]
        assert record["variant"] == "learned_oval" and "unknown_shape" not in record
        assert record["fields"]["body_height_mm"]["value"] == 77.0 and record["profile_hash"] == cc.profile_hash(record)
        zones = spec[cc.ZONES_SCHEMA]["zones"]
        assert cc.validate_zone_set(zones, record) == [] and spec[cc.ZONES_SCHEMA]["profile_hash"] == record["profile_hash"]
        assert ui._unknown_shape(first) is None
        # every design's shape step offers it, drawn by the server; the validation takes it for the compact only
        other = DesignTask.objects.create(brand=brand, task_text="a compact", design_target="product_container",
                                          status="awaiting_container_profile")
        compact = next(a for a in ui.container_profile_editor_config(other)["archetypes"] if a["key"] == "compact")
        assert {"key": "learned_oval", "label": "Oval (learned)"} in compact["variants"]
        assert len(compact["outlines"]["learned_oval"]["outline"]) >= 4
        assert ui.validate_container_profile_payload({"archetype": "compact", "variant": "learned_oval", "cap_style":
                                                      "clasp", "width_mm": 110, "height_mm": 77, "depth_mm": 18}) == []
        assert ui.validate_container_profile_payload({"archetype": "tin", "variant": "learned_oval", "cap_style":
                                                      "screw", "width_mm": 60, "height_mm": 40, "depth_mm": 15})
        # a concept that shows it, and a brief that names it, now propose it — not said unknown
        picture = SimpleNamespace(image_file=ContentFile(_lid_png((250, 170), 0.0), name="concept.png"))
        base = cc.build_inferred_profile("compact", "", {"body_width_mm": 110.0, "body_height_mm": 95.0})
        out, trace = _seed_outline_proposal(base, picture, named_shape=lid_shape_named_in("compact", "an oval compact"),
                                            traced=ls.traced_variants("compact"))
        assert out["variant"] == "learned_oval" and "unknown_shape" not in out and trace["kind"] == co.OVAL
        words_only, _t = _seed_outline_proposal(base, SimpleNamespace(image_file=None),
                                                named_shape=lid_shape_named_in("compact", "an oval compact"),
                                                traced=ls.traced_variants("compact"))
        assert words_only["variant"] == "learned_oval" and "unknown_shape" not in words_only

    def test_bh71_a_round_tin_is_as_long_as_it_is_wide_and_every_new_form_is_offered(self):
        """§BH71 PART 3: a round tin's lid is a circle as a round compact's is; and the shape step offers each new
        form with its own variants, closures, sizes and the server's drawing of every variant."""
        from apps.pipeline.targets import ui
        errors = ui.validate_container_profile_payload(
            {"archetype": "tin", "variant": "round", "cap_style": "screw", "height_mm": 40, "width_mm": 42,
             "depth_mm": 18})
        assert any("as long as it is wide" in e for e in errors), errors
        cards = {c["key"]: c for c in ui.CONTAINER_EDITOR_ARCHETYPES}
        for form in ("tin", "sachet", "oval_stick", "aerosol", "ampoule"):
            card = cards[form]
            assert card["confirmable"] and card["variants"] and card["caps"] and card["ranges"], form
            assert set(card["outlines"]) == {k for k, _ in card["variants"]}, form
            assert all(len(o["outline"]) >= 4 and len(o["closure"]) >= 4 for o in card["outlines"].values()), form

    def test_bh71_a_round_compact_is_as_long_as_it_is_wide(self):
        """§BH71 PART 1: a round compact's lid is a circle, so seen from above it is as long as it is wide — a round lid
        confirmed 110 by 95 would be drawn as neither, and the server says so; square and rounded rectangles keep their
        own sizes."""
        from apps.pipeline.targets.ui import validate_container_profile_payload as validate
        round_ = {"archetype": "compact", "variant": "round", "width_mm": 110, "height_mm": 95, "depth_mm": 18}
        self.assertTrue(any("round compact's lid is a circle" in e for e in validate(round_)))
        self.assertEqual(validate(dict(round_, height_mm=110)), [])
        self.assertEqual(validate(dict(round_, variant="rounded_rect")), [])

    def test_the_forms_that_worked_keep_the_ranges_they_had(self):
        """§BH70(1): a form's own ranges widen ITS rows only — bottle, jar, tube and compact are offered and validated
        exactly as before, the shared rows untouched.

        [§BH71 PART 3, the owner's goal of 2026-09-28: "Add each as a shape the system can draw" — the catalogue's
        pages give a roll-on 15 mm across and a lotion pump bottle 250 mm tall, a sifter jar 20 mm tall and a 5 g pot
        18, a twelve-well palette 197 mm wide and a paperboard one 8 mm thin: the bottle, the jar and the compact now
        declare their own ranges, each containing the shared rows it had; the tube keeps the shared rows exactly, and
        the shared rows themselves are untouched. Was: all four equal to the shared rows]"""
        from apps.pipeline.targets.ui import CONTAINER_EDITOR_PROPORTIONS, form_ranges, proportions_for
        shared = {p["key"]: (p["min"], p["max"]) for p in CONTAINER_EDITOR_PROPORTIONS}
        # [his answer after test day finding 3, 2026-09-30, (4) round: a tube's width is its round diameter, and its
        # width row starts at a lip tube's 13 mm; its height and depth rows stay the shared rows exactly. Was: the tube
        # equal to the shared rows]
        self.assertEqual(form_ranges("tube"), dict(shared, width_mm=(13, 120)))
        for p in proportions_for("tube"):
            self.assertEqual((p["min"], p["max"]), (13, 120) if p["key"] == "width_mm" else shared[p["key"]], p)
        for form in ("bottle", "jar", "compact"):
            own = form_ranges(form)
            for key, (lo, hi) in shared.items():             # each still takes every size it took before
                self.assertLessEqual(own[key][0], lo, (form, key))
                self.assertGreaterEqual(own[key][1], hi, (form, key))
        self.assertEqual(form_ranges("bottle")["width_mm"][0], 12)                  # a roll-on
        self.assertEqual(form_ranges("jar")["height_mm"][0], 15)                    # a sifter jar, a 5 g pot
        self.assertEqual(form_ranges("compact")["depth_mm"][0], 6)                  # a paperboard palette


class NothingFallsBackToBottleTests(TestCase):
    """HALF TWO (§BH61(a)): no code path produces an archetype that was not chosen or proposed."""

    def test_an_unresolvable_archetype_refuses_and_says_where_it_looked(self):
        from apps.pipeline.targets.container import archetypes as A
        with self.assertRaises(A.ArchetypeUnresolved) as ctx:
            A.resolve(None, "", looked_in=["the confirmed record", "the product row"])
        message = str(ctx.exception)
        self.assertIn(A.ARCHETYPE_UNRESOLVED, message)
        self.assertIn("the confirmed record", message)       # WHERE it looked
        self.assertIn("the product row", message)
        self.assertNotIn("falls back", message.replace(
            "Nothing falls back to bottle", ""))             # ...and it does not

    def test_a_bottle_only_path_refuses_another_form_by_name(self):
        """§BH61(b)(c): "the refusal goes at the door, not in the middle"."""
        from apps.pipeline.targets.container import archetypes as A
        with self.assertRaises(A.ArchetypeOutOfScope) as ctx:
            A.require_scope("m3_profile_geometry", "compact", serves=("bottle",))
        self.assertIn(A.ARCHETYPE_OUT_OF_SCOPE, str(ctx.exception))
        self.assertIn("compact", str(ctx.exception))

    def test_the_container_profile_has_no_default_archetype(self):
        """§BH61(a): a profile with no archetype is a refusal, not a bottle. The dataclass carried
        `archetype: str = "bottle"`, so every ContainerProfile built without one WAS a bottle."""
        from apps.pipeline.targets.container.silhouettes import ContainerProfile
        with self.assertRaises(TypeError):
            ContainerProfile()                              # no archetype -> cannot be built

    def test_a_brief_that_names_no_form_yields_no_archetype(self):
        """The hint reader returned "bottle" for any text it did not recognise. A text naming no form
        now yields None, and the editor says so rather than pre-selecting."""
        from apps.pipeline.targets import container as C
        self.assertIsNone(C._infer_profile(_TaskLike("a lovely thing in a nice colour")).archetype)
        self.assertEqual(C._infer_profile(_TaskLike("a rose face palette, four baked pans")).archetype,
                         "compact")
        self.assertEqual(C._infer_profile(_TaskLike("dropper bottle serum")).archetype, "bottle")

    def test_source_guard_no_bottle_fallback_survives_on_the_route(self):
        """SOURCE-STRING GUARD (§Y2(b)). §BH61(a): "A default that reappears anywhere fails the gate."

        The route is the four files the owner's palette travelled through. A literal bottle may be
        COMPARED against here (§BH61(b)(a): "a comparison that reads the value is not a guess") but never
        PRODUCED as a fallback, so this guard bans the three shapes a fallback takes.
        """
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[2]
        # The three shapes a FALLBACK takes. A bottle named by its own words in an `elif` is a
        # RESOLUTION, not a fallback, and is not banned — that distinction is §BH61(b)(a)'s.
        banned = ('or "bottle"', "or 'bottle'", 'return "bottle"',
                  'else:\n        archetype = "bottle"')
        offenders = []
        for rel in ("pipeline/targets/container/__init__.py",
                    "pipeline/targets/ui.py",
                    "pipeline/services/container_asset_resolver.py",
                    "pipeline/services/native_handoff.py"):
            text = (root / rel).read_text()
            for needle in banned:
                if needle in text:
                    offenders.append("%s: %s" % (rel, needle))
        self.assertEqual(offenders, [], "a bottle fallback reappeared on the route: %s" % offenders)

    def test_source_guard_no_archetype_default_hides_in_a_get_or_an_or(self):
        """SOURCE-STRING GUARD (§Y2(b)). §BH64(c): the eleventh fallback "hid inside a `.get()` default
        where a search for literals could not reach; add that shape to the conformance test so the
        twelfth cannot hide the same way".

        Three differences from the guard above, and each one is the owner's point.

        IT READS EVERYTHING, not four named files. The eleventh was `views.py:1177` and the twelfth was
        `targets/ui.py:308`; the first is not on that list and the second is, which is how a file can be
        on the route, be edited by §BH61(c) itself, and still keep a default.

        IT BANS THE TWO SHAPES A DEFAULT TAKES WHEN IT IS NOT A BARE LITERAL: `.get(key, "<form>")` in
        Python and `|| "<form>"` in JavaScript. Both were invisible to a search for archetype literals
        because the literal is an ARGUMENT, not an assignment.

        IT READS THE BROWSER. `static/js/` is where the owner looks, and `confirm_profile.js:74` held a
        `|| 'bottle'` through the whole of §BH61 because no guard in this repository read JavaScript.

        `other` IS EXCLUDED BY NAME, measured rather than assumed: it is not a form, it is the honest
        "none of these", and `gates.js:164` and `review_board.js:145` both use the English word for an
        unrelated category. Banning it would fail on two files that have nothing to do with containers.

        AND COMMENT LINES ARE SKIPPED, because the FIRST thing this guard caught was the comment written
        beside the repair explaining the `|| 'bottle'` it had just removed. A default in prose is not a
        default. A guard that cannot be explained in the source it guards would be bought at the price of
        the next author not being able to say what was wrong here.
        """
        import pathlib
        import re
        from apps.pipeline.targets.container import archetypes as A
        apps = pathlib.Path(__file__).resolve().parents[2]
        inner = apps.parent
        names = "|".join(A.ARCHETYPES)
        # §BH65(e): AND a `.get()` whose default is a form's BUILDER FUNCTION — `build_backbone` held
        # `_ARCHETYPES.get(profile.archetype, _bottle)`, a default this pattern could not see because it is an
        # identifier, not a string. The family's last member hid in the shape the last guard left open.
        get_default = re.compile(r"""\.get\(\s*[^,()]+,\s*(?:(['"])(%s)\1|_(%s)\b)""" % (names, names))
        or_default = re.compile(r"""\|\|\s*(['"])(%s)\1""" % names)
        offenders = []
        for path in sorted(apps.rglob("*.py")):
            rel = str(path.relative_to(inner))
            if "/tests/" in rel:
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("#"):
                    continue
                if get_default.search(line):
                    offenders.append("%s:%d %s" % (rel, n, line.strip()))
        for path in sorted((inner / "static" / "js").rglob("*.js")):
            rel = str(path.relative_to(inner))
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if line.lstrip().startswith("//") or line.lstrip().startswith("*"):
                    continue
                if or_default.search(line) or get_default.search(line):
                    offenders.append("%s:%d %s" % (rel, n, line.strip()))
        self.assertEqual(offenders, [],
                         "an archetype default hid in a .get() or an ||:\n" + "\n".join(offenders))


class _TaskLike:
    """The smallest thing `_infer_profile` reads: a task with text and no product."""

    def __init__(self, text):
        self.task_text = text
        self.product = None
