"""Confirm Profile UI-1 — editor configuration and gate visibility (server).

The editor is driven entirely by container_profile_editor_config/1.0: the
browser carries no archetype/variant/closure catalog and no range constants
of its own. The config uses the backend vocabulary exactly (persisted keys
from silhouettes.py / ConfirmContainerProfileView), flags the non-confirmable
'Other' honestly, carries the B4a creation hints as INITIAL_HINTS_ONLY, and
reading it mutates nothing.
"""
import re
from pathlib import Path

import pytest
from django.contrib.auth.models import Group

from apps.core.models import Brand
from apps.pipeline.models import DesignTask, GateDecision
from apps.pipeline.targets import ui as target_ui
from apps.pipeline.targets.container import SUPPORTED_ARCHETYPES
from apps.pipeline.targets.container.silhouettes import ContainerProfile

_JS = (Path(__file__).resolve().parents[3] / "static" / "js"
       / "confirm_profile.js").read_text()


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="BBROSE", master_brief="x")


@pytest.fixture
def reviewer(django_user_model):
    from apps.pipeline.permissions import ROLE_DESIGNER
    u = django_user_model.objects.create_user("ui1", password="x")
    u.groups.add(Group.objects.get_or_create(name=ROLE_DESIGNER)[0])
    return u


def make_task(brand, target="product_container",
              status="awaiting_container_profile", text="a serum bottle"):
    return DesignTask.objects.create(brand=brand, task_text=text,
                                     design_target=target, status=status)


def get_payload(client, reviewer, task):
    client.force_login(reviewer)
    r = client.get(f"/api/tasks/{task.id}/status/")
    assert r.status_code == 200
    return r.json()


class TestConfigPresence:

    def test_present_for_product_container(self, brand, reviewer, client):
        task = make_task(brand)
        cfg = get_payload(client, reviewer, task)["container_profile_editor"]
        assert cfg["schema"] == "container_profile_editor_config/1.0"
        assert cfg["gate_eligible"] is True

    def test_absent_for_packaging_and_complete_product(self, brand, reviewer,
                                                       client):
        for target in ("packaging", "complete_product"):
            task = make_task(brand, target=target, status="queued")
            payload = get_payload(client, reviewer, task)
            assert payload["container_profile_editor"] is None, target

    def test_gate_eligibility_tracks_task_state(self, brand, reviewer,
                                                client):
        for state, eligible in (("queued", False),
                                ("awaiting_gate_1", False),
                                ("awaiting_container_profile", True),
                                ("completed", False)):
            task = make_task(brand, status=state)
            cfg = get_payload(client, reviewer,
                              task)["container_profile_editor"]
            assert cfg["gate_eligible"] is eligible, state

    def test_rendering_the_config_mutates_nothing(self, brand, reviewer,
                                                  client):
        task = make_task(brand)
        get_payload(client, reviewer, task)
        task.refresh_from_db()
        assert task.status == "awaiting_container_profile"
        assert GateDecision.objects.filter(task=task).count() == 0


class TestArchetypeCatalog:

    def test_the_archetypes_are_listed_in_order(self, brand, reviewer, client):
        """§BH55(a): four become five — "compact" for the owner's Phase 1 palette, before the non-confirmable
        'other', which stays last because it is the honest fallback and not a form.

        RENAMED from ``test_four_archetypes_in_order``. A count in a NAME is perishable: that is the defect
        ``test_twenty_eight_tests_declare_themselves_under_y2b`` files about ITSELF in
        ``apps/pipeline/tests/test_wig_source_string_guards.py`` — "A COUNT IN A NAME MAKES EVERY REFERENCE TO IT
        PERISHABLE, and nothing in this repository checks prose-to-symbol references." This is the first chance to
        stop repeating it here, so the number leaves the name and the assertion goes on carrying it.
        """
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        keys = [a["key"] for a in cfg["archetypes"]]
        # §BH70(1), 2026-09-27: five become eight — lipstick, mascara and pencil, before "other", which stays last.
        # Was: == ["bottle", "jar", "tube", "compact", "other"] and the five labels.
        # [§BH71 PART 3, the owner's goal of 2026-09-28: "Add each as a shape the system can draw." — eight become
        # thirteen: the tin, the sachet, the oval stick, the aerosol can and the ampoule, before "other", which stays
        # last. Was: the eight keys above and their eight labels]
        assert keys == ["bottle", "jar", "tube", "compact", "lipstick", "mascara", "pencil", "tin", "sachet",
                        "oval_stick", "aerosol", "ampoule", "other"]
        labels = [a["label"] for a in cfg["archetypes"]]
        # [the owner's answer of 2026-09-27: a gloss is asked "wand vial or squeeze tube?" and the vial is this form —
        # it read "Mascara"]
        assert labels == ["Bottle", "Jar", "Tube", "Compact / Palette", "Lipstick", "Mascara / Wand vial", "Pencil",
                          "Tin", "Sachet / Flat pouch", "Oval stick", "Aerosol can", "Ampoule / Vial", "Other"]
        assert all(a["description"] for a in cfg["archetypes"])

    def test_confirmable_flags_match_the_backend_contract(self, brand,
                                                          reviewer, client):
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        by_key = {a["key"]: a for a in cfg["archetypes"]}
        for key in SUPPORTED_ARCHETYPES:
            assert by_key[key]["confirmable"] is True
        # 'other' is a legitimate editor selection, honestly flagged as
        # outside the current confirmation contract — never hidden, never
        # silently converted to bottle
        assert by_key["other"]["confirmable"] is False
        assert "other" not in SUPPORTED_ARCHETYPES

    def test_choice_keys_stay_inside_backend_vocabulary(self, brand,
                                                        reviewer, client):
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        variant_vocab = {"cylindrical", "tapered", "square", "slim",
                         "standard",
                         "rounded_rect", "round",          # §BH55(a) compact
                         "sharpened", "twist",             # §BH70(1) pencil
                         # [§BH71 PART 3: the tin, the sachet, the oval stick, the aerosol can and the ampoule]
                         "slide", "three_side", "four_side", "oval", "straight", "necked",
                         "glass", "plastic", "vial",
                         # [§BH71 PART 3: the catalogue's — an airless bottle, a flacon, a roll-on, a sifter jar and an
                         # airless one, a cushion compact and a paperboard palette, a liner pen]
                         "airless", "flacon", "roller", "sifter", "cushion", "paperboard", "pen"}
        cap_vocab = {"screw", "pump", "flip", "lid", "crimp", "dropper",
                     "clasp", "magnet", "friction",        # §BH55(a) compact closures
                     "cap", "wand",                        # §BH70(1) lipstick, mascara and pencil closures
                     # [§BH71 PART 3: the five new forms' closures]
                     "slip", "slide", "tear_notch", "snap_cap", "overcap", "actuator",
                     "snap_tip", "twist_tab", "stopper",
                     # [§BH71 PART 3: the catalogue's closures — a nail polish's brush cap, a perfume's crimped spray,
                     # an airless pump, a fine mist, a roll-on's ball, a lip tube's nozzle, a gloss's doe-foot, a liquid
                     # liner's brush, a click pen's button]
                     "brush_cap", "crimp_spray", "airless_pump", "mist", "roller_ball", "nozzle",
                     "doe_foot", "brush", "click"}
        for a in cfg["archetypes"]:
            assert {v["key"] for v in a["variants"]} <= variant_vocab, a["key"]
            assert {c["key"] for c in a["caps"]} <= cap_vocab, a["key"]

    def test_dropper_is_selectable_for_bottles(self, brand, reviewer, client):
        # the live dropper-bottle pilot uses cap_style='dropper'; the old JS
        # catalog omitted it — the config must not repeat that gap
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        bottle = next(a for a in cfg["archetypes"] if a["key"] == "bottle")
        assert "dropper" in {c["key"] for c in bottle["caps"]}

    def test_other_has_explicit_empty_choice_lists(self, brand, reviewer,
                                                   client):
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        other = next(a for a in cfg["archetypes"] if a["key"] == "other")
        assert other["variants"] == [] and other["caps"] == []

    def test_no_duplicate_catalog_in_the_browser(self):
        # §6: the old hardcoded per-archetype map must be gone from the JS —
        # choices reach the editor only through the rendered config
        assert "CONTAINER_OPTS" not in _JS
        assert "container_profile_editor" in _JS


class TestCompactArchetype:
    """§BH55(a) — the form the owner's Phase 1 brief asks for, which this system could not draw.

    The catalog entry and the backbone are ONE contract, which is this file's own subject, so they are tested
    together here rather than a catalog entry being asserted against nothing.
    """

    @staticmethod
    def _bounds(segs):
        xs, ys = [], []
        for seg in segs:
            for a in ("x", "x1", "x2"):
                v = getattr(seg, a, None)
                if v is not None:
                    xs.append(v)
            for a in ("y", "y1", "y2"):
                v = getattr(seg, a, None)
                if v is not None:
                    ys.append(v)
        return min(xs), min(ys), max(xs), max(ys)

    def test_a_compact_is_drawn_as_a_compact(self):
        from apps.pipeline.targets.container.silhouettes import (
            SUPPORTED_ARCHETYPES, ContainerProfile, build_backbone)
        assert "compact" in SUPPORTED_ARCHETYPES
        b = build_backbone(ContainerProfile(archetype="compact", width_mm=110.0, height_mm=95.0))
        assert b.archetype == "compact"
        assert b.silhouette and b.cap_region

    def test_the_brief_gets_four_pans_and_a_mirror_inside_the_case(self):
        """The brief: "four baked pans in a hinged case with a mirror". Every part inside the case it sits in."""
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        W, H = 110.0, 95.0
        b = build_backbone(ContainerProfile(archetype="compact", width_mm=W, height_mm=H))
        assert len(b.pan_regions) == 4
        assert b.mirror_region is not None
        for pan in b.pan_regions:
            x0, y0, x1, y1 = self._bounds(pan)
            assert 0 <= x0 and 0 <= y0 and x1 <= W and y1 <= H, (x0, y0, x1, y1)
        mx0, my0, mx1, my1 = self._bounds(b.mirror_region)
        assert 0 <= mx0 and mx1 <= W and my1 <= H
        assert my0 >= b.hinge_axis_mm, "the mirror is in the lid, past the hinge"
        assert b.hinge_axis_mm > 0, "the hinge is a real edge, not a coordinate of zero"

    def test_the_pan_layout_is_measured_rather_than_assumed(self):
        """A baked pan is 26-36 mm across. In the brief's case one row draws 19.3 mm and two rows draw 28.6 mm,
        so the case decides the row count — whichever layout draws the LARGEST pan — and no constant does."""
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone

        def dia(w, h, **g):
            b = build_backbone(ContainerProfile(archetype="compact", width_mm=w, height_mm=h,
                                                case_geometry=g or None))
            x0, _, x1, _ = self._bounds(b.pan_regions[0])
            return x1 - x0

        chosen = dia(110.0, 95.0)
        assert chosen > dia(110.0, 95.0, pan_rows=1), "one row draws a smaller pan and must not be chosen"
        assert 26.0 <= chosen <= 36.0, "the brief's case draws a real baked pan, %.1f mm" % chosen
        # a wide, shallow case: one row IS the larger, and it is what gets taken
        assert abs(dia(120.0, 60.0) - dia(120.0, 60.0, pan_rows=1)) < 0.01

    def test_the_pan_drawn_is_the_house_pan_the_owner_preserved(self):
        """§BH55(a): 26.0 mm, read from `palette_pan_profile.PAN_CONTRACT` whose provenance says "owner M4B-A
        preserved value" — not a second diameter derived in this module and disagreeing with his by 2.6 mm."""
        from apps.pipeline.services.palette_pan_profile import PAN_CONTRACT
        from apps.pipeline.targets.container.silhouettes import (
            ContainerProfile, build_backbone, house_pan_diameter_mm)
        house = PAN_CONTRACT["pan_outside_diameter_mm"][0]
        assert house_pan_diameter_mm() == house == 26.0
        b = build_backbone(ContainerProfile(archetype="compact", width_mm=110.0, height_mm=95.0))
        assert b.pan_diameter_source == "HOUSE_PAN_CONTRACT"
        assert b.pan_diameter_mm == house
        x0, _, x1, _ = self._bounds(b.pan_regions[0])
        assert abs((x1 - x0) - house) < 1e-6, "the circle drawn IS the house pan, not a number beside it"

    def test_a_case_too_small_for_the_house_pan_says_so_instead_of_shrinking_it(self):
        """A silently shrunken "baked pan" is how a 19.3 mm one reaches a design."""
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        b = build_backbone(ContainerProfile(archetype="compact", width_mm=45.0, height_mm=45.0))
        assert b.pan_diameter_source == "DERIVED_CASE_TOO_SMALL"
        assert b.pan_diameter_mm < 26.0
        for pan in b.pan_regions:
            x0, y0, x1, y1 = self._bounds(pan)
            assert 0 <= x0 and 0 <= y0 and x1 <= 45.0 and y1 <= 45.0

    def test_a_diameter_a_person_named_wins_and_is_labelled_as_theirs(self):
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        b = build_backbone(ContainerProfile(archetype="compact", width_mm=110.0, height_mm=95.0,
                                            case_geometry={"pan_diameter_mm": 30.0}))
        assert b.pan_diameter_source == "NAMED_BY_A_PERSON"
        assert b.pan_diameter_mm == 30.0

    def test_a_row_count_a_person_named_is_obeyed(self):
        from apps.pipeline.targets.container.silhouettes import ContainerProfile, build_backbone
        b = build_backbone(ContainerProfile(archetype="compact", width_mm=110.0, height_mm=95.0,
                                            case_geometry={"pan_rows": 1, "pan_count": 4}))
        tops = {round(self._bounds(p)[1], 1) for p in b.pan_regions}
        assert len(tops) == 1, "four pans in one row share one top edge"

    def test_the_briefs_own_words_reach_the_compact_and_the_others_do_not_move(self):
        """Measured BEFORE this change, on the owner's own brief: its CASE section scanned to JAR (because
        "compact" sat in the jar branch), its headline scanned to BOTTLE, and the product's own word PALETTE was
        heard by nothing — two texts of one brief disagreeing, and neither answer a hinged case."""
        from types import SimpleNamespace

        from apps.pipeline.targets.container import _infer_profile

        def infer(text):
            return _infer_profile(SimpleNamespace(product=None, task_text=text)).archetype

        assert infer("the CASE - hinged compact, mirror in the lid, four pans") == "compact"
        assert infer("a Rose face palette, four baked pans in a hinged case with a mirror") == "compact"
        assert infer("palette") == "compact"
        # the forms that already worked do not move
        assert infer("an apothecary jar with a lid") == "jar"
        assert infer("a lip gloss tube") == "tube"
        assert infer("a 30 ml serum bottle") == "bottle"


class TestProportionsAndDefaults:

    def test_ranges_and_defaults_match_the_backend(self, brand, reviewer,
                                                   client):
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        by_key = {p["key"]: p for p in cfg["proportions"]}
        assert set(by_key) == {"height_mm", "width_mm", "depth_mm",
                               "neck_ratio"}
        # §BH65(e): the backend's bottle defaults are no longer dataclass field defaults — a field nobody set
        # is None in the RECORD — they are the bottle's declared `nominal`, which the builder draws from. The
        # editor's defaults must agree with THAT one source, and the unsized bottle must draw at it.
        from apps.pipeline.targets.container import archetypes as A
        from apps.pipeline.targets.container.silhouettes import build_backbone
        d = A.nominal_of("bottle")
        assert by_key["height_mm"]["default"] == d["height_mm"]
        assert by_key["width_mm"]["default"] == d["width_mm"]
        assert by_key["neck_ratio"]["default"] == d["neck_ratio"]
        drawn = build_backbone(ContainerProfile(archetype="bottle"))
        assert (drawn.width_mm, drawn.height_mm) == (d["width_mm"], d["height_mm"])
        # the neck bounds are the silhouettes clamp, verbatim
        assert by_key["neck_ratio"]["min"] == 0.2
        assert by_key["neck_ratio"]["max"] == 0.7
        for p in cfg["proportions"]:
            assert p["min"] < p["max"]
            assert p["step"] > 0

    def test_proportion_note_disclaims_manufacturing(self, brand, reviewer,
                                                     client):
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        assert cfg["proportion_note"] == (
            "These controls define relative silhouette proportions, not "
            "manufacturing dimensions.")
        assert cfg["preview_disclaimer"] == \
            "A preview of the shape — not a production drawing"

    def test_config_carries_no_paths_or_supplier_language(self, brand,
                                                          reviewer, client):
        import json
        cfg = get_payload(client, reviewer,
                          make_task(brand))["container_profile_editor"]
        dump = json.dumps(cfg).lower()
        for banned in ("/media/", "/users/", "task_refs", "supplier",
                       "tolerance", "manufactur"):
            # "manufacturing" appears ONLY inside the explicit disclaimer
            if banned == "manufactur":
                assert dump.count("manufactur") == 1
                assert "not manufacturing dimensions" in dump
            else:
                assert banned not in dump, banned


class TestInitialHints:

    def test_hints_parse_from_the_creation_brief(self, brand, reviewer,
                                                 client):
        task = make_task(brand, text=(
            "Rose Launch\n\na 30 ml serum bottle\n\n"
            "[Container type: bottle; Product category: serum; "
            "Capacity: 30 ml; Closure: gold dropper]"))
        cfg = get_payload(client, reviewer, task)["container_profile_editor"]
        assert cfg["initial_hints"] == {
            "container_type": "bottle", "product_category": "serum",
            "capacity": "30 ml", "closure": "gold dropper"}
        assert cfg["hints_status"] == "INITIAL_HINTS_ONLY"

    def test_partial_and_missing_hints(self, brand, reviewer, client):
        task = make_task(brand, text="a serum bottle\n\n"
                                     "[Container type: other]")
        cfg = get_payload(client, reviewer, task)["container_profile_editor"]
        assert cfg["initial_hints"] == {"container_type": "other"}
        bare = make_task(brand, text="a serum bottle, no hints block")
        cfg2 = get_payload(client, reviewer, bare)["container_profile_editor"]
        assert cfg2["initial_hints"] == {}

    def test_free_text_hints_stay_verbatim(self, brand, reviewer, client):
        # a closure hint is prose, not a persisted key — nothing maps it
        task = make_task(brand, text=(
            "x\n\n[Container type: bottle; Product category: lip oil; "
            "Capacity: about 15ml, tall; Closure: rose-gold pump maybe]"))
        cfg = get_payload(client, reviewer, task)["container_profile_editor"]
        assert cfg["initial_hints"]["closure"] == "rose-gold pump maybe"
        cap_keys = {c["key"] for a in cfg["archetypes"] for c in a["caps"]}
        assert "rose-gold pump maybe" not in cap_keys

    def test_hint_parser_is_pure(self):
        assert target_ui.parse_container_hints("") == {}
        assert target_ui.parse_container_hints(None) == {}
        got = target_ui.parse_container_hints(
            "prefix [Container type: jar] suffix")
        assert got == {"container_type": "jar"}


    def test_finding2_the_sizes_a_brief_states_in_words_are_read_and_nothing_is_guessed(self):
        """His test day finding 2 (2026-09-29, design 117): "Tube about 50 mm across, 180 mm tall" never reached the
        shape step. A size stated in these words is read, in mm or cm; two different values for one size are not
        guessed between; a brief that states none gives nothing."""
        got = target_ui.brief_stated_sizes(
            "Type: body lotion in a squeeze tube.\nSize: 200 ml. Tube about 50 mm across, 180 mm tall.")
        assert got == {"width_mm": 50.0, "height_mm": 180.0, "said": "50 mm across · 180 mm tall"}
        assert target_ui.brief_stated_sizes("a jar 6.5 cm wide and 4 cm deep") == {
            "width_mm": 65.0, "depth_mm": 40.0, "said": "6.5 cm wide · 4 cm deep"}
        assert target_ui.brief_stated_sizes("a tube 50 mm across, its carton 60 mm across, 180 mm tall") == {
            "height_mm": 180.0, "said": "180 mm tall"}
        for nothing in ("", None, "200 ml ℮ 6.7 fl oz", "a 30 ml serum, tall and slim"):
            assert target_ui.brief_stated_sizes(nothing) == {}


class TestFrontendContractStrings:
    """Source-level pins for behaviors the browser suite proves live."""

    def test_no_dead_confirm_and_no_new_endpoint(self):
        # the ONE existing endpoint remains the only POST target, exactly
        # once each for confirm and resume. Since UI-2A the live "Confirm &
        # Reconstruct" action exists solely inside the reviewed dialog.
        assert _JS.count("confirm_container_profile/") == 2
        assert _JS.count("Confirm and draw it") == 1
        assert 'id="cpd-confirm"' in _JS

    def test_preview_is_local_and_honest(self):
        assert "A preview of the shape — not a production drawing" in _JS or \
            "preview_disclaimer" in _JS
        # the preview never fetches: canvas drawing only
        assert "getContext('2d')" in _JS
        for banned in ("images.edit", "images.generate", "openai",
                       "/api/generate"):
            assert banned not in _JS

    def test_other_never_renders_as_bottle(self):
        assert "archetype-icon-other" in _JS
        assert "Custom container form" in _JS
