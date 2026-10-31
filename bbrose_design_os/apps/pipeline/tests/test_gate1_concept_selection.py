"""container_selected_concept_visual_contract/1.0 — human Gate-1 concept
selection boundary (2C-2D). No provider is ever called in these tests; the
boundary STOPS at awaiting_container_profile — no confirmation, no
reconstruction, no Packaging."""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import copy

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    ApiCallRecord,
    DesignProject,
    DesignTask,
    GeneratedImage,
)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import selected_concept_contract as scc
from apps.pipeline.targets.container import ProductContainerTarget

User = get_user_model()

_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")

RATIONALE = {
    "selected_because": ["refined frosted dusty-rose glass bottle",
                         "premium rose-gold collar"],
    "unselected_because": {"A_AMBER_NOCTURNE": "too heavy, severe",
                           "C_NOCTURNE_APOTHECARY": "generic, masculine"},
}


def _measurements():
    return [scc._entry("frame_size", [8, 8], units="px", confidence=1.0,
                       tolerance=0, source=scc.SRC_PIXEL)]


class SelectionFixture(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        # the recorded 40×40×110 mm describe the OUTER CARTON (CORR-2 §4)
        product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201", name="Rose Damascena",
            category="SK", year=2026, product_type="carton",
            width_mm=40, depth_mm=40, height_mm=110)
        self.user = User.objects.create_superuser("selop", password="x")
        self.project = DesignProject.objects.create(
            brand=brand, product=product, brief="b",
            design_target="complete_product", status="container")
        # brief wording mirrors the live pilot: "apothecary" once matched
        # "pot" by substring and inferred a JAR — the fixture keeps the trap
        self.task = DesignTask.objects.create(
            brand=brand, product=product,
            task_text="dropper bottle serum container — modern rose "
                      "apothecary treatment, potent night repair",
            design_target="product_container", stage="container",
            project=self.project, status="awaiting_gate_1",
            created_by=self.user)
        self.images = []
        for n, vid in enumerate(["A_AMBER_NOCTURNE", "B_ROSE_SMOKE",
                                 "C_NOCTURNE_APOTHECARY"], start=1):
            img = GeneratedImage.objects.create(
                task=self.task, direction_name="Damascena Nocturne",
                prompt_used="p", variation_number=n,
                reference_provenance={"variation_identity": vid})
            img.image_file.save(f"v{n}.png", ContentFile(_PNG), save=True)
            reviewed(img)
            self.images.append(img)
        self.selected = self.images[1]
        self.unselected = [self.images[0], self.images[2]]

    def _contract(self):
        return scc.build_visual_contract(
            self.selected, measurements=_measurements(),
            human_rationale=RATIONALE)


class SelectionDecisionTests(SelectionFixture):
    def test_selection_decision_recorded_and_hashed(self):
        contract = self._contract()
        rec = scc.record_selection_decision(
            self.project, selected_image=self.selected,
            unselected_images=self.unselected, rationale=RATIONALE,
            actor=self.user, contract_hash=contract["contract_hash"],
            now_iso="2026-07-27T00:00:00+00:00")
        self.project.refresh_from_db()
        stored = self.project.metadata[scc.SELECTION_META_KEY]
        assert stored == rec
        assert stored["decision"] == "SELECT_CONTAINER_CONCEPT"
        assert stored["selected"]["image_id"] == self.selected.id
        assert stored["selected"]["variation_identity"] == "B_ROSE_SMOKE"
        assert [u["image_id"] for u in stored["unselected"]] == \
            [i.id for i in self.unselected]
        assert "preserved" in stored["unselected_disposition"]
        assert len(stored["record_hash"]) == 64
        # identity is over canonical content: same content → same hash
        again = dict(stored)
        again.pop("record_hash")
        assert scc._sha(again) == stored["record_hash"]

    def test_contract_derives_from_selected_image(self):
        contract = self._contract()
        prov = contract["provenance"]
        assert prov["source_image_id"] == self.selected.id
        assert prov["variation_identity"] == "B_ROSE_SMOKE"
        assert prov["task_id"] == self.task.id
        assert contract["schema_version"] == scc.CONTRACT_SCHEMA
        # deterministic + content-sensitive hash
        assert contract["contract_hash"] == self._contract()["contract_hash"]
        mutated = copy.deepcopy(contract)
        mutated.pop("contract_hash")
        mutated["bottle_form"]["requirements"].append("x")
        assert scc._sha(mutated) != contract["contract_hash"]
        # stored_contract_for pins to exactly the selected image
        scc.persist_visual_contract(self.project, contract)
        self.project.refresh_from_db()
        self.task.refresh_from_db()
        assert scc.stored_contract_for(self.task, self.selected) is not None
        assert scc.stored_contract_for(self.task, self.unselected[0]) is None

    def test_motif_terms_only_inside_prohibitions(self):
        contract = self._contract()
        assert scc.validate_motif_freedom(contract) == []
        # forbidden terms DO exist in the contract — as prohibitions
        text = str(contract["prohibited_interpretations"])
        assert "petal" in text and "dewdrop" in text
        # the same term outside the prohibition subtree is a violation
        bad = copy.deepcopy(contract)
        bad["front_decoration"]["rule"] = "print a petal motif band"
        problems = scc.validate_motif_freedom(bad)
        assert problems and scc.MOTIF_OUTSIDE_PROHIBITION in problems[0]

    def test_no_generic_label_fallback_authorized(self):
        contract = self._contract()
        bans = contract["front_decoration"]["prohibitions"]
        assert "a rectangular adhesive label" in bans
        assert "a generic centered label fallback" in bans
        assert contract["front_decoration"]["rule"].startswith(
            "decoration appears directly printed")


class DropperZoneTests(SelectionFixture):
    def _profile(self):
        return cc.build_inferred_profile("bottle", "cylindrical")

    def test_augmentation_yields_front_back_bottom_and_excludes_collar(self):
        prof = self._profile()
        base = cc.propose_zones(prof)
        assert {z["zone_type"] for z in base} == {"FRONT_PRINT_ZONE",
                                                  "BACK_PRINT_ZONE"}
        zones = scc.augment_dropper_zones(prof, base)
        # CORR-2 §8: the collar zone is EXCLUDED, never proposed
        assert {z["zone_type"] for z in zones} == {
            "FRONT_PRINT_ZONE", "BACK_PRINT_ZONE", "BOTTOM_CODE_ZONE"}
        assert cc.validate_zone_set(zones, prof) == []
        assert all(z["user_confirmation_state"] == "PROPOSED" for z in zones)
        assert cc.zone_set_hash(zones) != cc.zone_set_hash(base)
        # bottom: technical code only, never artwork
        bottom = [z for z in zones if z["zone_type"] == "BOTTOM_CODE_ZONE"][0]
        assert bottom["permitted_techniques"] == ["BOTTOM_INKJET_CODE"]
        assert bottom["max_artwork_coverage"] <= 0.2
        # front stays direct print — no adhesive label technique anywhere
        assert "adhesive_label" not in {
            t for z in zones for t in z["permitted_techniques"]}
        # the exclusion record names the decision and its four reasons
        excl = scc.COLLAR_ZONE_EXCLUSION
        assert excl["decision"] == "EXCLUDE_FROM_CONFIRMABLE_ZONE_SET"
        assert len(excl["reasons"]) == 4

    def test_bh71_every_form_is_offered_a_code_place_of_its_own(self):
        """§BH71 (0b), the owner's goal of 2026-09-28: \"Propose a batch-code place for every form that lacks one,
        shown as a production note, not a blocker.\" Every declared form's proposal, in every variant, offers one
        code place — valid, overlapping nothing proposed beside it, an inkjet code only — and a proposal that has one is
        returned as it is; the dropper's window is the shared rule's, byte for byte."""
        from apps.pipeline.targets.container import archetypes as A
        for form in A.ARCHETYPES:
            for variant in [k for k, _ in A.vocabulary_of(form).get("variants") or ()] or [""]:
                prof = cc.build_inferred_profile(form, variant)
                zones = cc.augment_code_zones(prof, cc.propose_zones(prof))
                code = [z for z in zones if z["zone_type"] == "BOTTOM_CODE_ZONE"]
                assert len(code) == 1, (form, variant)
                assert cc.validate_zone_set(zones, prof) == [], (form, variant, cc.validate_zone_set(zones, prof))
                assert code[0]["permitted_techniques"] == ["BOTTOM_INKJET_CODE"], (form, variant)
                assert code[0]["user_confirmation_state"] == "PROPOSED", (form, variant)
                assert cc.augment_code_zones(prof, zones) == zones, (form, variant)
        prof = self._profile()
        drop = [z for z in scc.augment_dropper_zones(prof, cc.propose_zones(prof))
                if z["zone_type"] == "BOTTOM_CODE_ZONE"]
        assert [z["zone_hash"] for z in drop] == [cc.bottom_code_zone(prof)["zone_hash"]]
        # where each sits: a compact's on its base's underside below the base panel, a pencil's on its barrel's back
        comp = cc.build_inferred_profile("compact", "round")
        zc = cc.augment_code_zones(comp, cc.propose_zones(comp))
        base = next(z for z in zc if z["zone_id"] == "z_base")
        code = next(z for z in zc if z["zone_type"] == "BOTTOM_CODE_ZONE")
        assert code["parent_surface"] == "BASE_BOTTOM" and code["y"] == round(base["y"] + base["height"], 1)
        pen = cc.build_inferred_profile("pencil", "sharpened")
        assert next(z for z in cc.augment_code_zones(pen, cc.propose_zones(pen))
                    if z["zone_type"] == "BOTTOM_CODE_ZONE")["parent_surface"] == "BODY_BACK"
        # a tube 50 mm tall: its crimp window's margins took the whole 2.0 mm band and could never be confirmed
        tube = cc.build_inferred_profile("tube", "standard")
        tube["fields"]["body_height_mm"]["value"] = 50.0
        crimp = next(z for z in cc.propose_zones(tube) if z["zone_type"] == "BOTTOM_CODE_ZONE")
        assert cc.validate_zone(crimp, tube) == [] and crimp["safe_margin_mm"] == 0.5

    def test_bh71_every_code_place_holds_one_line_of_its_code(self):
        """§BH71 (0b), the owner's goal of 2026-09-28: \"Propose a batch-code place for every form that lacks one,
        shown as a production note, not a blocker.\" A place must hold its code: at every size the shape step
        takes — each form, each variant, its starting size and every 2 mm across each of its ranges — the code
        window holds one line of the bottom inkjet's own smallest text (its capability row's 2.0 pt) inside its
        margins. Measured before, on sizes the shape step takes: a tin's window at its own starting size held 0.1 mm
        of code, a compact 42 to 54 mm tall 0.1 to 0.7, a tube 52 to 66 mm tall 0.08, a mascara 8 mm deep 0.4; and
        a round record 20 mm across was offered none; and 62 sizes proposed a code window that met its base panel
        along an edge and was refused as overlapping it, by float noise. His compacts' windows and base panels are
        as they were."""
        from apps.pipeline.targets.container import archetypes as A
        from apps.pipeline.targets.ui import form_ranges
        line = cc.code_line_mm()
        assert abs(line - 2.0 * 25.4 / 72.0) < 1e-9
        for form in A.ARCHETYPES:
            nominal, ranges = A.nominal_of(form), form_ranges(form)
            base = {"body_width_mm": float(nominal["width_mm"]), "body_height_mm": float(nominal["height_mm"]),
                    "body_depth_mm": float(nominal.get("depth_mm") or nominal["width_mm"])}
            sizes = [base] + [dict(base, **{field: float(v)}) for key, field in (
                ("width_mm", "body_width_mm"), ("height_mm", "body_height_mm"), ("depth_mm", "body_depth_mm"))
                for v in sorted(set(ranges[key]) | set(range(int(ranges[key][0]), int(ranges[key][1]) + 1, 2)))]
            if form in ("compact", "tin"):                  # a round one is as long as it is wide
                sizes += [dict(base, body_width_mm=float(v), body_height_mm=float(v)) for v in range(20, 122, 2)]
            for variant in [k for k, _ in A.vocabulary_of(form).get("variants") or ()] or [""]:
                for dims in sizes:
                    prof = cc.build_inferred_profile(form, variant, dims)
                    zones = cc.augment_code_zones(prof, cc.propose_zones(prof))
                    code = [z for z in zones if z["zone_type"] == "BOTTOM_CODE_ZONE"]
                    assert len(code) == 1, (form, variant, dims)
                    z = code[0]
                    assert min(z["width"], z["height"]) - 2 * z["safe_margin_mm"] >= line - 1e-9, (
                        form, variant, dims, z["width"], z["height"], z["safe_margin_mm"])
                    assert cc.validate_zone_set(zones, prof) == [], (form, variant, dims,
                                                                    cc.validate_zone_set(zones, prof))
        for variant, w, h, window, panel in (
                ("round", 110.0, 110.0, (44.0, 84.7, 22.0, 5.5, 1.0), (15.4, 25.3, 79.2, 59.4)),
                ("rounded_rect", 110.0, 95.0, (44.0, 90.3, 22.0, 4.7, 1.0), (5.5, 4.8, 99.0, 85.5)),
                ("square", 90.0, 90.0, (36.0, 85.5, 18.0, 4.5, 1.0), (4.5, 4.5, 81.0, 81.0))):
            prof = cc.build_inferred_profile("compact", variant, {"body_width_mm": w, "body_height_mm": h})
            zones = cc.augment_code_zones(prof, cc.propose_zones(prof))
            z = next(z for z in zones if z["zone_type"] == "BOTTOM_CODE_ZONE")
            b = next(z for z in zones if z["zone_id"] == "z_base")
            assert (z["x"], z["y"], z["width"], z["height"], z["safe_margin_mm"]) == window, variant
            assert (b["x"], b["y"], b["width"], b["height"]) == panel, variant

    def test_bh71_a_learned_oval_lids_zones_keep_inside_its_ellipse(self):
        """§BH71 PART 3: a learned oval lid's lid and base are ellipses — its base panel and its code window proposed
        inside the ellipse, the code window holding one line of its code, a zone that leaves it refused by name, the
        lid's own face zone (the whole ellipse) excepted."""
        for form in ("compact", "tin"):
            prof = cc.build_inferred_profile(form, "learned_oval", {"body_width_mm": 110.0, "body_height_mm": 76.0,
                                                                   "body_depth_mm": 18.0})
            zones = cc.augment_code_zones(prof, cc.propose_zones(prof))
            assert cc.validate_zone_set(zones, prof) == [], (form, cc.validate_zone_set(zones, prof))
            base = next(z for z in zones if z["parent_surface"] == "BASE_BOTTOM" and z["zone_id"] == "z_base")
            code = next(z for z in zones if z["zone_type"] == "BOTTOM_CODE_ZONE")
            for z in (base, code):
                far = max(((px - 55.0) / 55.0) ** 2 + ((py - 38.0) / 38.0) ** 2
                          for px in (z["x"], z["x"] + z["width"]) for py in (z["y"], z["y"] + z["height"]))
                assert far <= 1.0 + 1e-9, (form, z["zone_id"], far)
            assert min(code["width"], code["height"]) - 2 * code["safe_margin_mm"] >= cc.code_line_mm() - 1e-9
            corner = dict(base, x=0.0, y=0.0, width=20.0, height=10.0)
            assert any("leaves the oval BASE_BOTTOM" in p for p in cc.validate_zone(corner, prof)), form

    def test_bh71_a_round_compacts_zones_keep_inside_its_circle(self):
        """§BH71 PART 1: a round compact's lid and base are circles across the plan — its base panel and its code
        window are proposed inside the circle, a zone that leaves it is refused by name, the lid's own face zone (the
        whole circle, §BH67(c)3) excepted, and a rectangle's zone set carried to a round confirmation diverges."""
        import math
        comp = cc.build_inferred_profile("compact", "round", {"body_width_mm": 110.0, "body_height_mm": 110.0})
        zones = cc.augment_code_zones(comp, cc.propose_zones(comp))
        assert cc.validate_zone_set(zones, comp) == [], cc.validate_zone_set(zones, comp)
        assert {z["zone_id"] for z in zones} == {"z_lid", "z_base", "z_base_code"}
        for z in zones:
            if z["zone_id"] == "z_lid":             # the whole lid: the circle's own box
                assert (z["x"], z["y"], z["width"], z["height"]) == (0.0, 0.0, 110.0, 110.0)
                continue
            far = max(math.hypot(px - 55.0, py - 55.0) for px in (z["x"], z["x"] + z["width"])
                      for py in (z["y"], z["y"] + z["height"]))
            assert far <= 55.0, (z["zone_id"], far)
        # a zone in the plan's corner is inside the box and outside the lid: refused, by name
        corner = dict(next(z for z in zones if z["zone_id"] == "z_base"), x=0.0, y=0.0, width=20.0, height=10.0)
        problems = cc.validate_zone(corner, comp)
        assert any(p.startswith(cc.ZONE_OUT_OF_BOUNDS) and "leaves the round BASE_BOTTOM" in p for p in problems), \
            problems
        # the rectangle's zones, carried to a round confirmation, no longer fit it
        rect = cc.build_inferred_profile("compact", "rounded_rect",
                                         {"body_width_mm": 110.0, "body_height_mm": 110.0})
        assert cc.zone_profile_divergence({"profile_hash": rect["profile_hash"]}, cc.propose_zones(rect), comp)

    def test_augmentation_is_idempotent_and_strips_stale_collar_zones(self):
        prof = self._profile()
        once = scc.augment_dropper_zones(prof, cc.propose_zones(prof))
        twice = scc.augment_dropper_zones(prof, once)
        assert len(twice) == len(once) == 3
        # a stale NECK_BAND proposal (pre-CORR-2 state) is removed
        stale = once + [dict(once[0], zone_type="NECK_BAND_ZONE")]
        cleaned = scc.augment_dropper_zones(prof, stale)
        assert "NECK_BAND_ZONE" not in {z["zone_type"] for z in cleaned}


class BeginOutputBoundaryTests(SelectionFixture):
    def _select(self):
        contract = self._contract()
        scc.persist_visual_contract(self.project, contract)
        scc.record_selection_decision(
            self.project, selected_image=self.selected,
            unselected_images=self.unselected, rationale=RATIONALE,
            actor=self.user, contract_hash=contract["contract_hash"],
            now_iso="2026-07-27T00:00:00+00:00")
        # the real post-approval entrypoint: marks the winner approved and
        # hands off to the container target's begin_output
        ARIAAgent(self.task.id).resume_after_gate_1(self.selected.id)
        self.task.refresh_from_db()
        self.project.refresh_from_db()

    def test_selection_stops_at_profile_confirmation_no_packaging(self):
        tasks_before = DesignTask.objects.count()
        calls_before = ApiCallRecord.objects.count()
        self._select()
        # the boundary: profile-confirmation gate, nothing beyond it
        assert self.task.status == "awaiting_container_profile"
        assert ApiCallRecord.objects.count() == calls_before  # zero calls
        assert DesignTask.objects.count() == tasks_before     # no new stage
        out = self.task.packaging_outputs.first()
        assert out is not None and out.spec_sheet["backend"] == "container"
        assert out.dieline_job_id is None
        prof = out.spec_sheet[cc.PROFILE_SCHEMA]
        assert prof["confirmation_state"] == "UNCONFIRMED"
        assert not [f for f in prof["fields"].values()
                    if f.get("verification") == "VERIFIED"]
        # §5 concept seeds present, INFERRED only — and the human-selected
        # dropper-bottle archetype beats the keyword heuristic ("apothecary"
        # in the brief must never yield a jar here)
        assert prof["archetype"] == "bottle"
        assert prof["fields"]["archetype"]["value"] == "bottle"
        assert out.spec_sheet["container_profile"]["archetype"] == "bottle"
        assert "PIPETTE_DROPPER" in prof["fields"]["cap_type"]["value"]
        assert "FROSTED_TRANSLUCENT_GLASS" in \
            prof["fields"]["body_material"]["value"]
        assert cc.validate_zone_set(
            out.spec_sheet[cc.ZONES_SCHEMA]["zones"], prof) == []
        # §8 front/back/bottom PROPOSED; the collar zone EXCLUDED
        zrec = out.spec_sheet[cc.ZONES_SCHEMA]
        assert zrec["confirmation_state"] == "PROPOSED"
        assert {z["zone_type"] for z in zrec["zones"]} == {
            "FRONT_PRINT_ZONE", "BACK_PRINT_ZONE", "BOTTOM_CODE_ZONE"}
        assert zrec["exclusions"][0]["zone"] == "OPTIONAL_COLLAR_ZONE"
        assert zrec["exclusions"][0]["decision"] == \
            "EXCLUDE_FROM_CONFIRMABLE_ZONE_SET"
        # §4 carton dims never enter container geometry
        assert prof["fields"]["body_width_mm"]["value"] is None
        assert prof["fields"]["body_height_mm"]["value"] is None
        assert out.spec_sheet["container_profile"]["height_mm"] is None
        assert out.spec_sheet["container_profile"]["width_mm"] is None
        secondary = out.spec_sheet[scc.SECONDARY_PACKAGING_KEY]
        assert secondary["referent"] == "OUTER_CARTON"
        assert (secondary["width_mm"], secondary["height_mm"]) == (40.0, 110.0)
        finding = out.spec_sheet[scc.REFERENT_FINDING_KEY]
        assert set(finding["codes"]) == set(scc.CARTON_CONTAMINATION_CODES)
        # §5/§6 concept dimension proposal + extensions, all unconfirmed
        dim = out.spec_sheet[scc.DIM_PROPOSAL_SCHEMA]
        assert all(p["verification_state"] == scc.CONCEPT_ONLY
                   and p["manufacturer_confirmation_required"]
                   and p["editable_before_confirmation"]
                   for p in dim["proposals"])
        total = [p for p in dim["proposals"] if p["field"] == "total_height"][0]
        assert "closure" in total["note"]            # dropper inclusion stated
        assert "NOT BBR-SK-201" in dim["analog_disclaimer"]
        ext = out.spec_sheet[scc.EXTENSIONS_SCHEMA]
        assert ext["confirmation_state"] == "UNCONFIRMED"
        assert all(f["editable"] for f in ext["fields"].values())
        assert {"base_thickness", "bulb_height", "total_height",
                "nominal_capacity", "frost_intensity"} <= set(ext["fields"])
        # selected approved; alternatives preserved, unselected, visible
        for img in self.images:
            img.refresh_from_db()
        assert self.selected.is_approved is True
        assert all(not i.is_approved and not i.superseded
                   for i in self.unselected)

    def test_review_sections_present_the_selection_stage(self):
        self._select()
        rows = ProductContainerTarget().review_sections(self.task)
        by_label = {r["label"]: r["value"] for r in rows}
        assert "SELECT_CONTAINER_CONCEPT" in by_label["Gate-1 selection"]
        assert f"#{self.selected.id}" in by_label["Gate-1 selection"]
        assert "preserved" in by_label["Unselected alternatives"]
        assert scc.CONTRACT_SCHEMA in by_label["Visual contract"]
        assert "Concept-only facts" in by_label
        assert "Missing production facts" in by_label
        assert by_label["Next required human action"] == (
            "CONFIRM PRODUCT CONTAINER PROFILE AND DECORATION ZONES")
        assert any(label.startswith("Visual-quality warning")
                   for label in by_label)
        # CORR-2 §10: dimensional attribution + exclusions on the board
        assert "OUTER_CARTON" in by_label["Secondary packaging (outer carton)"]
        assert "CARTON_DIMENSIONS_NOT_CONTAINER_DIMENSIONS" in \
            by_label["Dimension referent finding"]
        assert "Concept dimension proposal" in by_label
        assert "EXCLUDE_FROM_CONFIRMABLE_ZONE_SET" in \
            by_label["Zone excluded — OPTIONAL_COLLAR_ZONE"]
        # not shown as reconstructed / Gate-2 ready
        assert self.task.status == "awaiting_container_profile"
        assert "Reconstruction" not in str(by_label)

    def test_warnings_addendum_preserves_the_contract_hash(self):
        self._select()
        contract_before = self.project.metadata[scc.META_KEY]
        record = scc.persist_warnings_addendum(self.project)
        self.project.refresh_from_db()
        assert self.project.metadata[scc.META_KEY] == contract_before
        assert record["base_contract_hash"] == \
            contract_before["contract_hash"]
        warnings = scc.all_warnings(self.project)
        assert len(warnings) == 8 + 3
        assert "carton dimensions must never populate bottle geometry" in \
            warnings
        # the review board shows all eleven
        rows = ProductContainerTarget().review_sections(self.task)
        shown = [r for r in rows
                 if r["label"].startswith("Visual-quality warning")]
        assert len(shown) == 11

    def test_without_contract_the_legacy_proposal_is_unchanged(self):
        # no metadata records → plain bottle proposal (front+back only)
        self.task.status = "gate_1_approved"
        self.task.save()
        ProductContainerTarget().begin_output(ARIAAgent(self.task.id),
                                              self.selected)
        out = self.task.packaging_outputs.first()
        zrec = out.spec_sheet[cc.ZONES_SCHEMA]
        # [§BH71 (0b), the owner's goal of 2026-09-28: every form is offered a batch-code place — it read front and
        # back only]
        assert {z["zone_type"] for z in zrec["zones"]} == {
            "FRONT_PRINT_ZONE", "BACK_PRINT_ZONE", "BOTTOM_CODE_ZONE"}
        # the heuristic default survives untouched — no dropper seed leaked
        # [§BH55 Phase 1, 2026-09-19: the cap is now the BRIEF'S OWN WORD — this
        # fixture's brief reads "dropper bottle serum container", so the heuristic
        # proposes a dropper where it proposed its screw default. What this test
        # guards still holds and is asserted: no contract seed leaked — no
        # extension record, no concept dimension proposal.]
        prof = out.spec_sheet[cc.PROFILE_SCHEMA]
        assert (prof["fields"].get("cap_type") or {}).get("value") == "dropper"
        assert scc.EXTENSIONS_SCHEMA not in out.spec_sheet
        assert scc.DIM_PROPOSAL_SCHEMA not in out.spec_sheet

    def test_a_carton_record_is_not_proposed_as_the_container(self):
        """§BH55 Phase 1 — this fixture's record, like the pilot's, is its CARTON: 40 × 40 × 110 mm (CORR-2 §4). That
        finding held on the pilot's contract path only; every other path proposed the carton's size as the container's,
        sourced VERIFIED_PRODUCT_RECORD. The carton stays the product's; the container is sized from the product's own
        net content, as an inference a person confirms or changes."""
        self.task.product.net_weight = "30 ml e 1 fl. oz."
        self.task.product.save(update_fields=["net_weight"])
        self.task.status = "gate_1_approved"
        self.task.save()
        ProductContainerTarget().begin_output(ARIAAgent(self.task.id),
                                              self.selected)
        out = self.task.packaging_outputs.first()
        f = out.spec_sheet[cc.PROFILE_SCHEMA]["fields"]
        assert (f["body_width_mm"]["value"], f["body_height_mm"]["value"]) == (33.0, 96.0)
        assert {f[k]["source"] for k in ("body_width_mm", "body_height_mm")} == {cc.SRC_INFERRED}
        assert f["body_depth_mm"]["value"] is None                  # never the carton's 40
        legacy = out.spec_sheet["container_profile"]
        assert (legacy["width_mm"], legacy["height_mm"]) == (33.0, 96.0)


class PlannerPromptsNameEveryFormTests(TestCase):
    def test_bh70_the_planner_is_never_told_every_product_is_a_bottle(self):
        """§BH70(1), item 4: the Gate-1 planner was told the container is "a bottle or tube" and every concept varies its
        "cap/body relationship"; the direction guidance named a jar, bottle, tube and compact and their "label zones".
        The planner is told the product's own form and the closure/body relationship; the guidance names every form."""
        from apps.pipeline import design_direction_generator as ddg
        from apps.pipeline.services import container_gate1 as cg1
        from apps.pipeline.targets.container import archetypes as A
        for text in (cg1.CONTAINER_SYSTEM, cg1.CONTAINER_GATE1_DIRECTIVES):
            assert "a bottle or" not in text and "cap/body relationship" not in text
            assert "closure/body relationship" in text
        guidance = ddg.TARGET_GUIDANCE["product_container"].lower()
        assert all(A.vocabulary_of(f)["label"].lower().split(" / ")[0] in guidance for f in A.ARCHETYPES)


class ArchetypeInferenceTests(TestCase):
    """2C-2D-CORR-1: whole-word archetype keywords — 'apothecary' is not a
    pot, 'potent' is not a pot, 'spot' is not a pot."""

    def _infer(self, text):
        from types import SimpleNamespace

        from apps.pipeline.targets.container import _infer_profile
        return _infer_profile(SimpleNamespace(product=None,
                                              task_text=text)).archetype

    def test_word_boundaries(self):
        assert self._infer("modern rose apothecary dropper") == "bottle"
        assert self._infer("a potent serum for spot treatment") == "bottle"
        assert self._infer("a frosted cream jar") == "jar"
        # [the owner's answer of 2026-09-27: "when a brief says "gloss" without saying which, ask me: wand vial or
        # squeeze tube." A bare gloss names no form; New design asks him. It read "tube"]
        assert self._infer("a shimmering lip gloss") is None
        # §BH55(a): a compact powder is a COMPACT. It read "jar" because the jar branch owned the word, which is
        # what made the owner's own palette brief scan to jar in one paragraph and bottle in another.
        assert self._infer("a compact powder") == "compact"
        assert self._infer("a four pan baked palette") == "compact"

    def test_bh71_a_lid_no_variant_draws_is_never_given_the_forms_first_variant(self):
        """§BH71 PART 3, the owner's goal of 2026-09-28: \"It never squeezes a product into the wrong shape.\" Measured at
        adf7942: \"an oval compact of pressed powder\" was proposed a rounded rectangle and \"an oval tin of lip balm\"
        a round tin — the form's FIRST variant, in silence. A lid shape a brief names that no variant of a form drawn
        in plan draws is proposed no variant; matched tightly, so a product called \"Rose Heart\" or \"Star Glow\", a
        \"flower oil\" or \"an oval mirror\" names none, and a form drawn standing (its own traced outline) is not
        touched."""
        from types import SimpleNamespace
        from apps.pipeline.targets.container import _infer_profile, lid_shape_named_in
        for text, form, kind in (("an oval compact of pressed powder", "compact", "oval"),
                                 ("an oval tin of lip balm", "tin", "oval"),
                                 ("an oval pressed powder compact", "compact", "oval"),
                                 ("a heart-shaped compact", "compact", "heart"),
                                 ("a hexagonal eyeshadow palette", "compact", "hexagon")):
            p = _infer_profile(SimpleNamespace(product=None, task_text=text))
            assert (p.archetype, p.variant) == (form, None), (text, p.archetype, p.variant)
            assert lid_shape_named_in(form, text)["kind"] == kind, text
        for text, form, variant in (("a round compact", "compact", "round"),
                                    ("Rose Heart pressed powder compact", "compact", "rounded_rect"),
                                    ("a compact with rosa damascena flower oil", "compact", "rounded_rect"),
                                    ("Star Glow palette", "compact", "rounded_rect"),
                                    ("a compact with an oval mirror", "compact", "rounded_rect"),
                                    ("an oval deodorant stick", "oval_stick", "oval")):
            p = _infer_profile(SimpleNamespace(product=None, task_text=text))
            assert (p.archetype, p.variant) == (form, variant), (text, p.archetype, p.variant)
            assert lid_shape_named_in(p.archetype, text) is None, text

    def test_bh71_the_catalogues_shapes_are_named_by_their_own_words(self):
        """§BH71 PART 3: a nail polish, a perfume, a roll-on, an airless serum, a facial mist, a cushion, a loose
        powder and a liner pen each name their form, and the brief's own words choose the variant and closure that
        draw them — a roll-on deodorant a bottle, not a stick."""
        from types import SimpleNamespace
        from apps.pipeline.targets.container import _infer_profile
        cases = {"a red nail polish": ("bottle", None, "brush_cap"),
                 "an eau de parfum": ("bottle", "flacon", "crimp_spray"),
                 "a roll-on deodorant": ("bottle", "roller", "roller_ball"),
                 "an airless serum": ("bottle", "airless", "airless_pump"),
                 "a facial mist": ("bottle", None, "mist"),
                 "a cushion foundation": ("compact", "cushion", None),
                 "a loose powder with a sifter": ("jar", "sifter", None),
                 "an eyeliner pen": ("pencil", "pen", None),
                 "a lip gloss with a doe-foot wand": ("mascara", None, "doe_foot")}
        for text, (form, variant, closure) in cases.items():
            p = _infer_profile(SimpleNamespace(product=None, task_text=text))
            assert p.archetype == form, (text, p.archetype)
            assert variant is None or p.variant == variant, (text, p.variant)
            assert closure is None or p.cap_style == closure, (text, p.cap_style)
        # and never squeezed by a word that says the opposite: a fragrance-free cream is no perfume, an ingredient
        # list's "Parfum" names no bottle, and a nail polish remover has no brush in its cap
        for text in ("a fragrance-free face cream", "a perfume-free body lotion",
                     "Ingredients: Aqua, Glycerin, Parfum, Linalool"):
            p = _infer_profile(SimpleNamespace(product=None, task_text=text))
            assert p.archetype != "bottle" and p.cap_style != "crimp_spray", (text, p.archetype, p.cap_style)
        remover = _infer_profile(SimpleNamespace(product=None, task_text="a nail polish remover"))
        assert remover.archetype == "bottle" and remover.cap_style != "brush_cap", remover.cap_style

    def test_bh71_the_new_forms_are_named_by_their_own_words(self):
        """§BH71 PART 3: a balm tin, a sheet mask, a deodorant stick, a dry shampoo and an ampoule each name their
        own form — before the form their words would otherwise fall to — and none of the forms that worked moves; a
        round compact is proposed round (no word here said \"round\", and it was proposed a rounded rectangle)."""
        cases = {"a vanilla lip balm tin": "tin", "a solid perfume in a slide tin": "tin",
                 "a hydrating sheet mask": "sachet", "a sample sachet of night cream": "sachet",
                 "an aluminium-free deodorant": "oval_stick", "a cooling body stick": "oval_stick",
                 "a volumising dry shampoo": "aerosol", "a flexible hair spray": "aerosol",
                 "a vitamin C ampoule": "ampoule", "a single-dose hair serum": "ampoule",
                 "a creamy lip balm stick": "lipstick", "a frosted cream jar": "jar",
                 "a 30 ml serum bottle": "bottle", "a facial mist spray": "bottle", "a four pan baked palette": "compact",
                 "a tube you can squeeze": "tube"}
        for text, form in cases.items():
            assert self._infer(text) == form, (text, self._infer(text), form)
        from types import SimpleNamespace
        from apps.pipeline.targets.container import _infer_profile
        for text, variant in (("a round pressed powder compact", "round"), ("a slide tin of balm", "slide"),
                              ("a necked dry shampoo can, an aerosol", "necked")):
            task = SimpleNamespace(product=None, task_text=text)
            assert _infer_profile(task).variant == variant, (text, _infer_profile(task).variant)

    def test_the_slim_forms_are_named_by_their_own_words(self):
        """§BH70(1), items 2 and 3 of the list sent to him: "lipstick", "mascara" and "stick" were read as a squeeze
        tube with a crimped end, and "eyeliner" and "pencil" named no form. Each names its own now — and the forms
        that already worked do not move: a bare gloss is still a tube (which of its two forms a gloss is here is the
        owner's word), and a gloss with a wand is the mascara's vial, as the mascara card says. [His word came on
        2026-09-27: a bare gloss names no form, and New design asks him — wand vial or squeeze tube.]"""
        cases = {"a matte lipstick in a gold case": "lipstick", "a creamy lip balm stick": "lipstick",
                 "a lengthening mascara": "mascara", "a tube of volumising mascara": "mascara",
                 "a liquid eyeliner": "mascara", "a lip gloss with a doe-foot wand": "mascara",
                 "a waterproof eyeliner pencil": "pencil", "a kohl eyeliner": "pencil", "a brow pencil": "pencil",
                 "a lip liner": "pencil",
                 # [his word, 2026-09-27: a bare gloss names no form and New design asks him; a gloss said with a
                 # vial is the wand vial, one squeezed is the tube, and his answer on the brief reads the same]
                 "a shimmering lip gloss": None, "a lip gloss in a glass vial": "mascara",
                 "a squeeze lip gloss": "tube", "a lip gloss\n\n[Container type: wand vial]": "mascara",
                 "a lip gloss\n\n[Container type: squeeze tube]": "tube",
                 "a 15 ml lip gloss tube": "tube", "a frosted cream jar": "jar",
                 "a four pan baked palette": "compact", "a 30 ml serum bottle": "bottle", "a body oil": None}
        for text, form in cases.items():
            assert self._infer(text) == form, (text, self._infer(text), form)
        from apps.pipeline.targets.container import FORM_WORDS
        from apps.pipeline.targets.container import archetypes as A
        assert [f for f, _ in FORM_WORDS if f not in A.ARCHETYPES] == []     # every form named is a declared one

    def test_the_proposal_speaks_its_archetypes_vocabulary_and_hears_the_briefs_closure(self):
        """§BH55 Phase 1 — measured on a no-spend dry run of new products: a jar or tube brief proposed the
        bottle-only variant "cylindrical" and the dashboard's own confirmation was refused
        (PROFILE_VALIDATION_FAILED); a dropper brief proposed a screw cap. Every proposal now validates for its
        own archetype, and the brief's closure and form words choose."""
        from types import SimpleNamespace

        from apps.pipeline.targets.container import _infer_profile
        from apps.pipeline.targets.ui import validate_container_profile_payload

        def infer(text):
            p = _infer_profile(SimpleNamespace(product=None, task_text=text))
            return p.archetype, p.variant, p.cap_style
        cases = {"a 50 ml face cream jar": ("jar", "standard", "lid"),
                 "a 15 ml lip gloss tube": ("tube", "standard", "screw"),
                 # §BH70(1), 2026-09-27: a mascara is a form of its own — its closure is its wand, and a crimp is
                 # not one of its words. Was: ("tube", "slim", "crimp"), the squeeze tube his list named (item 2).
                 "a slim mascara tube with a crimp seal": ("mascara", "slim", "wand"),
                 "a 30 ml glass dropper bottle for a facial serum": ("bottle", "cylindrical", "dropper"),
                 "a square bottle with a lotion pump": ("bottle", "square", "pump"),
                 "a toner bottle [Cap or closure: flip-top]": ("bottle", "cylindrical", "flip"),
                 # §BH61(a) MOVED THIS. It asserted ("bottle", "cylindrical", "screw") — "a body oil"
                 # names NO form word, and the reader returned bottle because bottle was the `else`.
                 # "Nothing falls back to bottle. An archetype that cannot be resolved is refused by name."
                 # A body oil could be a bottle, a jar or a tube; the system does not pick, and the editor
                 # says so instead of pre-selecting. The variant/closure stay None with it.
                 "a body oil": (None, None, None),
                 "a cream jar with a screw lid": ("jar", "standard", "lid")}
        for text, expected in cases.items():
            got = infer(text)
            assert got == expected, (text, got)
            archetype, variant, cap = got
            assert validate_container_profile_payload(
                {"archetype": archetype, "variant": variant, "cap_style": cap}) == [], text
        # a closure word the archetype does not offer is not forced onto it: a dropper is no jar closure
        assert infer("a cream jar with a dropper")[2] == "lid"

    def test_the_proposal_takes_its_size_from_the_capacity_the_brief_names(self):
        """§BH55 Phase 1 — measured on a no-spend dry run of new products: every one was proposed at the editor's
        default size whatever its brief said. A bottle is now proposed at the size its capacity names — the one
        container a person confirmed on this machine (30 ml: 33 mm wide, drawn 96.306 mm tall with its closure)
        scaled by the cube root of the capacity ratio, the scale held inside the editor's own ranges. The expected
        sizes were computed outside this file, not by the code under test."""
        from types import SimpleNamespace

        from apps.pipeline.targets.container import _infer_profile
        from apps.pipeline.targets.ui import validate_container_profile_payload

        def size(text, product=None):
            p = _infer_profile(SimpleNamespace(product=product, task_text=text))
            return p.width_mm, p.height_mm
        cases = {"a 30 ml glass dropper bottle for a facial serum": (33.0, 96.0),
                 "a 50ml serum bottle": (39.0, 114.0),
                 "a toner bottle [Container type: Bottle; Capacity: 100 mL]": (49.0, 144.0),
                 # §BH61(a) MOVED THIS. It asserted (26.0, 76.0) — a bottle's size for a brief that never
                 # says bottle. The capacity sizing runs only for a BOTTLE, and "a 15 ml facial oil" no
                 # longer resolves to one, so no size is proposed either. Sizing an unnamed form as a
                 # bottle is the same guess wearing a third hat.
                 # §BH61(a) MOVED THIS. It asserted (26.0, 76.0) — a bottle's size for a brief that never
                 # says bottle. Capacity sizing runs only for a BOTTLE, so no size is proposed; the
                 # dataclass's own field defaults (40.0 x 110.0) are what remains, and THOSE are named
                 # under §BH61(d) as a registry this commit does not unify.
                 # §BH65(e) MOVED IT AGAIN, and this is the unification that comment deferred: the field
                 # defaults are gone, so "no size is proposed" now reads as no size — (None, None).
                 "a 15 ml facial oil": (None, None),
                 "a 1 fl. oz. dropper bottle": (33.0, 96.0),
                 "a 5 ml travel bottle": (20.0, 58.0),          # the scale held at the editor's floor, proportion kept
                 "a 1000 ml body wash bottle": (69.0, 200.0)}   # ... and at its ceiling
        for text, expected in cases.items():
            got = size(text)
            assert got == expected, (text, got)
            assert validate_container_profile_payload(
                {"archetype": "bottle", "width_mm": got[0], "height_mm": got[1]}) == [], text
        # §BH65(e): was (40.0, 110.0), a BOTTLE's size — proposed for a jar ("a 50 ml face cream jar") and for
        # a brief naming no form at all, under comments saying "nothing is proposed". Now nothing is.
        default = (None, None)
        assert size("a body oil") == default                     # no capacity named: nothing is proposed from one
        assert size("a 30 ml serum and a 50 ml cream bottle") == default   # two volumes are not a capacity
        assert size("a 50 ml face cream jar") == default         # no confirmed jar on this machine to scale from
        carton = SimpleNamespace(product_type="carton", width_mm=40, depth_mm=40, height_mm=110,
                                 net_weight="30 ml e 1 fl. oz.")
        assert size("a dropper bottle for a night oil", carton) == (33.0, 96.0)   # its net content, not its carton
        assert size("a 50 ml dropper bottle", carton) == (39.0, 114.0)            # the brief's own words first
        own = SimpleNamespace(product_type="serum", width_mm=35, depth_mm=25, height_mm=95, net_weight="30 ml")
        assert size("a 30 ml serum bottle", own) == (35.0, 95.0)  # a record of the product itself still sizes it


class MeasurementTests(TestCase):
    def _synthetic(self, tmp):
        from PIL import Image, ImageDraw
        im = Image.new("RGB", (256, 384), (238, 230, 224))   # light bg
        d = ImageDraw.Draw(im)
        d.rectangle([35, 35, 110, 330], fill=(182, 154, 150))   # carton
        d.rectangle([150, 75, 190, 130], fill=(49, 34, 32))     # dark bulb
        d.rectangle([145, 130, 195, 165], fill=(196, 130, 84))  # gold collar
        d.rectangle([135, 165, 205, 340], fill=(216, 190, 184))  # pink body
        path = f"{tmp}/synthetic.png"
        im.save(path)
        return path

    def test_measurements_are_bounded_and_attributed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            results = scc.measure_selected_concept(self._synthetic(tmp))
        names = {e["measurement"] for e in results}
        assert {"frame_size", "negative_space_fraction",
                "dominant_palette_6", "bulb_bbox"} <= names
        for e in results:
            assert set(e) >= {"measurement", "value", "units", "confidence",
                              "tolerance", "source", "verification_state"}
            assert e["units"] != "mm"          # never production dimensions
            assert e["verification_state"] in (scc.CONCEPT_ONLY,
                                               scc.UNAVAILABLE)
            assert e["source"] in (scc.SRC_PIXEL, scc.SRC_AGENT_VISUAL)

    def test_blank_image_degrades_gracefully(self):
        import tempfile

        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/blank.png"
            Image.new("RGB", (64, 64), (240, 236, 232)).save(path)
            results = scc.measure_selected_concept(path)
        by_name = {e["measurement"]: e for e in results}
        assert by_name["bulb_bbox"]["verification_state"] == scc.UNAVAILABLE
        assert by_name["frame_size"]["value"] == [64, 64]


# =====================================================================================================================
# [His test blocker on design 122, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 29c2288), items 2, 4 and 6.]
#
# "Never show me a concept the system can't draw. Check each picture's readability BEFORE showing it; if one fails, redraw
# it automatically ... and only show it when it passes." "If even the redraw fails, never a dead end: offer me in words what
# I can do (redraw for $X, draw this concept from the template, or pick another), each with a button." "The refusal label
# 'ITS MAP CANNOT DRAW IT' is shouting engine words; say it plainly."
#
# The check's own rules, one by one (``targets.container.readable``); the whole path — 122's own one-colour brief, Start to
# finished files — is the wiring check's (test_wiring_check: test_complete_product_one_colour and
# test_his_test_blocker_122_where_the_redraw_fails_too_his_three_offers_each_a_button).
import io
import re
import shutil
import tempfile
from unittest import mock
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from apps.pipeline.models import DesignTask, GeneratedImage
from apps.pipeline.targets.container import readable

_ENGINE_WORDS_122 = re.compile(r"[A-Z_]{6,}")


def _png_122(ground, product):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (400, 600), ground)
    ImageDraw.Draw(img).rectangle((150, 100, 250, 520), fill=product)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _one_pink_tube_122():
    """122's tube as its concepts came, painted as the wiring check paints it: a pale pink tube, red lettering, on a pale
    pink ground — the trace finds no one standing product on it."""
    from apps.pipeline.tests.test_wiring_check import ONE_PINK_GROUND, one_colour, paint, standing_parts
    return paint(one_colour(standing_parts(150, 40, 0.14, name="Rose Blossom", name_share=0.8)), ONE_PINK_GROUND)


class _Readable122(TestCase):
    def setUp(self):
        media = tempfile.mkdtemp(prefix="readable_")
        self.addCleanup(shutil.rmtree, media, True)
        self.enterContext(override_settings(MEDIA_ROOT=media, DESIGN_MAP_READ=True))
        self.user = User.objects.create_superuser("r122", "r@example.invalid", "x")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="the house")
        product = Product.objects.create(brand=self.brand, product_id="R-122", name="Rose Blossom", category="SK",
                                         year=2026, product_type="hand cream")
        self.task = DesignTask.objects.create(brand=self.brand, product=product, design_target="product_container",
                                              task_text="A hand cream tube.\n\n[Container type: tube]",
                                              status="awaiting_gate_1", created_by=self.user)
        self.image = GeneratedImage.objects.create(task=self.task, direction_name="Blossom Signature",
                                                   prompt_used="a pale pink tube", variation_number=1)
        self.image.image_file.save("concept.png", ContentFile(_one_pink_tube_122()))
        self.logged = []
        self.aria = mock.MagicMock(task=self.task)
        self.aria.log.side_effect = lambda action, **kw: self.logged.append((action, kw))


class Readable122CheckTests(_Readable122):
    def test_a_read_that_named_no_part_is_never_taken_for_nothing_to_draw(self):
        from apps.pipeline.services import concept_design_map as dm
        unread = {"state": dm.MAP_READ, "parts": [], "problems": [dm.PARTS_UNREAD + ": the read raised"],
                  "cost": {"usd": "0.097665"}}
        with mock.patch("apps.pipeline.targets.container.map_read_refused", return_value=""), \
                mock.patch.object(dm, "read_parts", return_value=unread):
            found = readable.check(self.aria, self.image)
        self.assertEqual((found["state"], found["why"]), (readable.UNCHECKED, "its parts could not be read just now"))

    def test_a_check_that_raises_shows_the_concept_unchecked_and_never_stops_the_design(self):
        from apps.pipeline.services import concept_design_map as dm
        with mock.patch("apps.pipeline.targets.container.map_read_refused", return_value=""), \
                mock.patch.object(dm, "read_parts", side_effect=RuntimeError("socket closed")):
            found = readable.check(self.aria, self.image)
        self.assertEqual((found["state"], found["why"]), (readable.UNCHECKED, "its check could not run just now"))
        action, kw = self.logged[-1]
        self.assertIn("could not be checked just now — it is shown", action)
        self.assertIn("RuntimeError: socket closed", kw["payload"]["error"])

    def test_a_concept_with_no_picture_is_unchecked(self):
        self.image.image_file = ""
        self.assertEqual(readable.check(self.aria, self.image)["state"], readable.UNCHECKED)

    def test_a_pale_pink_tube_on_its_pink_ground_is_its_background_said_in_words(self):
        from apps.pipeline.services import claude_service
        with mock.patch("apps.pipeline.targets.container.map_read_refused", return_value=""), \
                mock.patch.object(claude_service, "call_claude", side_effect=AssertionError("a paid read")):
            found = readable.check(self.aria, self.image)      # the local trace finds no product: nothing paid
        self.assertEqual((found["state"], found["background"]), (readable.NOT_DRAWABLE, True))
        self.assertEqual(readable.why_in_words(found),
                         "the product can't be told apart from its background, so its shape can't be cut out")


class Readable122WordsTests(_Readable122):
    def test_every_reason_is_said_in_words_never_an_engine_code(self):
        parts = [{"kind": "window", "name": "centred cleared elliptical window", "why": "no tracer draws a framed panel "
                  "yet"}, {"kind": "rule", "name": "thin pink ellipse outline", "why": "not traced"}]
        for found in ({"background": True}, {"parts": parts}, {"why": "its parts could not be traced from the picture"},
                      {"background": True, "redraw_failed": "its redraw could not be made just now"}, {}):
            said = readable.why_in_words(found)
            self.assertIsNone(_ENGINE_WORDS_122.search(said), said)
        self.assertEqual(readable.why_in_words({"parts": parts}),
                         "2 of its parts can't be drawn yet: centred cleared elliptical window — a framed window, which "
                         "it cannot draw yet; thin pink ellipse outline (not traced)")


class Readable122OffersTests(_Readable122):
    COSTS = {"image_usd": 0.25, "qa_per_image_usd": 0.0424, "steps": {"design_map_read": {"usd": 0.09, "rows": 4}}}

    def test_three_offers_each_a_button_the_redraw_priced_as_every_click_is(self):
        with mock.patch("apps.pipeline.spend_estimates.measured_costs", return_value=self.COSTS):
            offers = readable.offers(self.task, [])
        self.assertEqual([(o["key"], o["cost_usd"]) for o in offers],
                         [("redraw", "0.38"), ("template", "0.00"), ("another", "0.00")])
        self.assertEqual(offers[0]["words"], "Redraw it on a plain contrasting backdrop")
        self.assertEqual(offers[1]["words"], "Draw it from the tube's standard layout, with your brief's words — not "
                                             "this picture's design")

    def test_where_parts_are_the_blocker_the_redraw_offers_to_leave_them_out(self):
        parts = [{"kind": "window", "name": "centred cleared elliptical window", "why": ""},
                 {"kind": "rule", "name": "thin pink ellipse outline", "why": ""}]
        with mock.patch("apps.pipeline.spend_estimates.measured_costs", return_value=self.COSTS):
            offers = readable.offers(self.task, parts)
        self.assertEqual(offers[0]["words"], "Redraw it without the 2 parts that can't be drawn yet")
        with mock.patch("apps.pipeline.spend_estimates.measured_costs", return_value=self.COSTS):
            one = readable.offers(self.task, parts[:1])
        self.assertEqual(one[0]["words"], "Redraw it without the part that can't be drawn yet")

    def test_a_form_not_known_is_named_as_its_forms(self):
        self.task.task_text = "A hand cream."
        self.task.product.product_type = ""
        with mock.patch("apps.pipeline.spend_estimates.measured_costs", return_value=self.COSTS), \
                mock.patch("apps.pipeline.targets.container.form_of_task", return_value=None):
            offers = readable.offers(self.task, [])
        self.assertTrue(offers[1]["words"].startswith("Draw it from its form's standard layout"), offers[1])


class Readable123CartonTests(_Readable122):
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "The
    check before I see the concepts and the check at drawing time must agree: a concept shown as drawable must
    draw."] A carton's concept is drawable only once its copy is measured where it draws, on its carton's size."""

    def setUp(self):
        import json
        import os
        super().setUp()
        from apps.pipeline.services import concept_design_map as dm
        here = os.path.join(os.path.dirname(__file__), "fixtures_123")
        self.task.design_target = "packaging"
        self.task.task_text = ('Rose Blossom Hand Cream, its tall carton.\n\nFront copy: BBROSE logo, "Rose Blossom", '
                               '"Hand Cream / كريم اليدين", 60 ml ℮ 2 fl oz.')
        self.task.save()
        self.image.direction_name = "Garden Wrap"
        self.image.image_file.save("garden_wrap.png", ContentFile(open(os.path.join(here, "concept_150.png"), "rb")
                                                                   .read()))
        self.image.reference_provenance = {dm.SCHEMA: json.load(open(os.path.join(here, "concept_150_map.json")))}
        self.image.save()

    def test_a_carton_whose_copy_runs_onto_copy_is_drawable_its_copy_settled_where_it_draws(self):
        """[His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Text
        collisions are fixed by spacing or shrinking, never refused".] Garden Wrap's kept read, its size not known yet:
        drawable — nothing of its copy is refused before it is drawn."""
        from apps.pipeline.services import claude_service
        with mock.patch.object(claude_service, "call_claude", side_effect=AssertionError("a paid read")):
            found = readable.check(self.aria, self.image)                 # its read kept: nothing paid
        self.assertEqual(found["state"], readable.DRAWABLE, found)

    def test_a_cartons_offers_are_a_redraw_or_another_concept(self):
        with mock.patch("apps.pipeline.spend_estimates.measured_costs", return_value=Readable122OffersTests.COSTS):
            self.assertEqual([o["key"] for o in readable.offers(
                self.task, [{"kind": "shape", "name": "oval", "why": ""}])], ["redraw", "another"])


class Readable122RedrawTests(_Readable122):
    def _edit(self, picture):
        def edit(**kw):
            self.sent = kw
            data = mock.MagicMock(url=None)
            data.b64_json = __import__("base64").b64encode(picture).decode()
            return mock.MagicMock(data=[data], _request_id="req", id="img")
        return edit

    def test_a_redraw_replaces_the_picture_on_the_same_concept_and_keeps_what_it_replaced(self):
        import hashlib

        from apps.pipeline.models import ApiCallRecord
        old = _one_pink_tube_122()
        new = _png_122((47, 45, 44), (246, 216, 222))
        prov = {"container_variation_contract": {"variation_id": "A_BLOSSOM"},
                "container_design_map/1.0": {"state": "UNREAD"}, "design_map_stop/1.0": {"concept": True}}
        self.image.reference_provenance = prov
        self.image.save()
        with mock.patch("openai.images.edit", side_effect=self._edit(new)):
            cost = readable.redraw(self.aria, self.image, {"words": "deep charcoal-grey", "hex": "#2F2D2C"},
                                   ("centred cleared elliptical window",))
        self.image.refresh_from_db()
        with self.image.image_file.open("rb") as fh:
            self.assertEqual(fh.read(), new)
        rec = self.image.reference_provenance[readable.REDRAWN_KEY]
        self.assertEqual((rec["from_sha256"], rec["sha256"], rec["cost_usd"], rec["left_out"]),
                         (hashlib.sha256(old).hexdigest(), hashlib.sha256(new).hexdigest(), cost,
                          ["centred cleared elliptical window"]))
        # the old picture's read and stop are dropped; its contract, its prompt and its direction kept
        self.assertEqual(sorted(self.image.reference_provenance),
                         ["concept_redrawn/1.0", "container_variation_contract"])
        self.assertEqual((self.image.prompt_used, self.image.direction_name), ("a pale pink tube", "Blossom Signature"))
        self.assertTrue(self.sent["prompt"].startswith(
            "Redraw this exact product design so it can be read: the SAME product"), self.sent["prompt"])
        self.assertIn("with ONLY these parts left out, their place left as the plain surface around them: centred "
                      "cleared elliptical window.", self.sent["prompt"])
        self.assertEqual(ApiCallRecord.objects.get(task=self.task).operation,
                         "image:redrawn so it can be read:Blossom Signature")
        # the picture sent as the image service takes a file — MEASURED: 122's first redraw sent a Django file field,
        # which the service refused
        from openai._files import is_file_content
        self.assertEqual([(f[1], f[2]) for f in self.sent["image"]], [(old, "image/png")])
        self.assertTrue(all(is_file_content(f) for f in self.sent["image"]))

    @override_settings(MAX_COST_PER_TASK=0.01)
    def test_a_spending_cap_reached_refuses_the_redraw_before_anything_is_paid(self):
        from apps.pipeline.models import ApiCallRecord
        from apps.pipeline.services.cost_ledger import BudgetExceededError
        ApiCallRecord.objects.create(task=self.task, provider="openai", model="m", operation="image:x", image_count=1,
                                     cost_usd="0.25")
        with mock.patch("openai.images.edit") as edit, self.assertRaises(BudgetExceededError):
            readable.redraw(self.aria, self.image, {"words": "deep charcoal-grey", "hex": "#2F2D2C"})
        edit.assert_not_called()

    def test_a_redraw_that_fails_changes_nothing_and_keeps_his_offers(self):
        found = {"state": readable.NOT_DRAWABLE, "background": True}
        with mock.patch("openai.images.edit", side_effect=RuntimeError("upstream 500")):
            again, redrawn = readable._redraw_and_check(self.aria, self.image, found)
        self.assertIsNone(redrawn)
        self.assertEqual(readable.why_in_words(again), "the product can't be told apart from its background, so its "
                         "shape can't be cut out; its redraw could not be made just now")

    def test_a_redraw_the_picture_service_refuses_for_its_credits_says_so_and_what_he_can_do(self):
        # MEASURED on 122, 2026-10-07: the service's own words when its account has no credits left
        refusal = RuntimeError("Error code: 429 - {'error': {'message': 'You have no credits remaining.', 'type': "
                               "'insufficient_quota', 'code': 'credit_balance_exhausted'}}")
        with mock.patch("openai.images.edit", side_effect=refusal):
            again, redrawn = readable._redraw_and_check(self.aria, self.image, {"state": readable.NOT_DRAWABLE,
                                                                                "background": True})
        self.assertIsNone(redrawn)
        said = readable.why_in_words(again)
        self.assertTrue(said.endswith("; its redraw was refused: the picture service's spending limit is reached — add "
                                      "credits at platform.openai.com, then press Redraw"), said)
        self.assertIsNone(_ENGINE_WORDS_122.search(said), said)

    def test_his_go_122_a_stop_its_own_check_now_finds_drawable_is_lifted_and_kept_beside(self):
        # [his go of 2026-10-08] 149 was stopped at approval before line art could be drawn: its check, finding it
        # drawable now, lifts the stop — the page shows no refusal — and keeps it beside, under its own key
        stop = {"at": "2026-10-07T12:00:00+00:00", "why": "its parts could not all be drawn", "concept": True}
        self.image.reference_provenance = {"design_map_stop/1.0": stop}
        self.image.save()
        assert readable._record(self.aria, self.image, {"state": readable.DRAWABLE}, None) == "drawable"
        self.image.refresh_from_db()
        prov = self.image.reference_provenance
        self.assertNotIn("design_map_stop/1.0", prov)
        self.assertEqual(prov[readable.STOP_LIFTED_KEY]["why"], stop["why"])
        self.assertEqual(prov[readable.STOP_LIFTED_KEY]["lifted_at"], prov[readable.CHECK_KEY]["at"])

    def test_a_light_product_is_redrawn_on_charcoal_and_a_dark_one_on_white(self):
        self.assertEqual(readable.backdrop_for(_png_122((240, 206, 210), (246, 216, 222)))["words"], "deep charcoal-grey")
        self.assertEqual(readable.backdrop_for(_png_122((240, 240, 240), (60, 20, 30)))["words"], "clean white")


class Readable122DoorTests(_Readable122):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def test_the_redraw_door_refuses_a_concept_that_can_be_drawn_in_words(self):
        prov = {readable.CHECK_KEY: {"state": readable.DRAWABLE}}
        self.image.reference_provenance = prov
        self.image.save()
        with mock.patch("apps.pipeline.tasks.redraw_concept.delay") as later:
            r = self.client.post("/api/tasks/%d/concept_redraw/" % self.task.pk, {"image_id": self.image.pk},
                                 content_type="application/json")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["error"], "This concept can be drawn already — it needs no redraw.")
        later.assert_not_called()

    def test_his_redraw_button_runs_the_redraw_for_a_concept_that_cannot_be_drawn(self):
        self.image.reference_provenance = {readable.CHECK_KEY: {"state": readable.NOT_DRAWABLE}}
        self.image.save()
        with mock.patch("apps.pipeline.tasks.redraw_concept.delay") as later:
            r = self.client.post("/api/tasks/%d/concept_redraw/" % self.task.pk, {"image_id": self.image.pk},
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200, r.content)
        later.assert_called_once_with(self.task.pk, self.image.pk)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "running")
        from apps.pipeline.models import AgentLog
        self.assertTrue(AgentLog.objects.filter(task=self.task, actor=self.user,
                                                action="Concept redraw requested by r122 — 'Blossom Signature'").exists())

    def test_his_template_button_keeps_his_choice_on_the_concept(self):
        reviewed(self.image)
        with mock.patch("apps.pipeline.tasks.resume_aria_gate1.delay"):
            r = self.client.post("/api/tasks/%d/gate1_approve/" % self.task.pk,
                                 {"image_id": self.image.pk, "from_template": True}, content_type="application/json")
        self.assertIn(r.status_code, (200, 202), r.content)
        self.image.refresh_from_db()
        self.assertEqual(self.image.reference_provenance[readable.FROM_TEMPLATE_KEY]["by"], "r122")
