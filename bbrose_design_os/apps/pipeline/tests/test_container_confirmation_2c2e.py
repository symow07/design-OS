"""2C-2E — human profile/zone confirmation + selected-concept native
reconstruction. No provider is ever called
the flow STOPS at
awaiting_gate_2 — no Human Design Acceptance, no Gate-2 decision, no
Packaging."""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import TestCase
from django.utils import timezone

from apps.core.models import Brand, Product
from apps.pipeline.agents.aria import ARIAAgent
from apps.pipeline.models import (
    ApiCallRecord,
    DesignProject,
    DesignTask,
    GateDecision,
    GeneratedImage,
)
from apps.pipeline.permissions import ROLE_REVIEWER
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import selected_concept_contract as scc
from apps.pipeline.targets.container import ProductContainerTarget
from apps.pipeline.targets.container.silhouettes import (
    ContainerProfile,
    build_backbone,
)

fitz = pytest.importorskip("fitz")

User = get_user_model()

_PNG = __import__("base64").b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")

RATIONALE = {"selected_because": ["frosted dusty-rose bottle"],
             "unselected_because": {"A": "too heavy", "C": "too masculine"}}

PROFILE_PAYLOAD = {
    "archetype": "bottle", "variant": "cylindrical",
    "height_mm": 68, "width_mm": 33, "depth_mm": 33,
    "neck_ratio": 10 / 33, "cap_style": "dropper",
    "cap_width_mm": 28, "cap_height_mm": 14,
}


def _confirmed_zones(spec, back_height=36.0):
    """The mandated §4/§5/§6 zone geometry, user-confirmed. ``back_height`` — [his correction of 2026-10-07] a shorter
    back, where a test needs copy that does not stand even shrunk evenly to its floor."""
    zones = [dict(z) for z in (spec.get(cc.ZONES_SCHEMA) or {}).get(
        "zones") or []]
    geo = {"FRONT_PRINT_ZONE": (5.5, 10.0, 22.0, 40.0),
           "BACK_PRINT_ZONE": (5.5, 12.0, 22.0, back_height),
           "BOTTOM_CODE_ZONE": (9.5, 14.0, 14.0, 5.0)}
    for z in zones:
        x, y, w, h = geo[z["zone_type"]]
        z.update({"x": x, "y": y, "width": w, "height": h,
                  "user_confirmation_state": cc.ZONE_USER_CONFIRMED})
        z.pop("zone_hash", None)
    return zones


class Confirmation2C2EFixture(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name="BBROSE", master_brief="x")
        product = Product.objects.create(
            brand=brand, product_id="BBR-SK-201",
            name="Rose Damascena Night Repair Oil",
            category="SK", year=2026, product_type="carton",
            width_mm=40, depth_mm=40, height_mm=110)
        self.user = User.objects.create_superuser("confop", password="x")
        Group.objects.get_or_create(name=ROLE_REVIEWER)[0].user_set.add(
            self.user)
        self.project = DesignProject.objects.create(
            brand=brand, product=product, brief="b",
            design_target="complete_product", status="container")
        self.task = DesignTask.objects.create(
            brand=brand, product=product,
            task_text="dropper bottle serum — modern rose apothecary",
            design_target="product_container", stage="container",
            project=self.project, status="awaiting_gate_1",
            created_by=self.user)
        self.images, variations = [], []
        for n, vid in enumerate(["A_AMBER_NOCTURNE", "B_ROSE_SMOKE",
                                 "C_NOCTURNE_APOTHECARY"], start=1):
            prompt = f"photoreal frosted dropper bottle — variation {vid}"
            img = GeneratedImage.objects.create(
                task=self.task, direction_name="Damascena Nocturne",
                prompt_used=prompt, variation_number=n,
                reference_provenance={"variation_identity": vid})
            img.image_file.save(f"v{n}.png", ContentFile(_PNG), save=True)
            reviewed(img)
            self.images.append(img)
            variations.append({
                "variation_id": vid, "title": vid, "prompt": prompt,
                "typography_signature": "serif name over tracked caps",
                "composition_signature": "front-stacked hierarchy",
                # mirrors the live B_ROSE_SMOKE signature shape: a single
                # editorial rule, with negated botanical/floral vocabulary
                "motif_signature": "single fine horizontal rule above the "
                                   "product name — restrained editorial "
                                   "structure, no botanical or floral "
                                   "element",
                "cap_body_signature": "rose-gold collar, plum bulb",
                "decoration_zone_signature": "direct print, no label",
                "color_field_signature": "dusty rose frosted glass",
                "finish_signature": "soft-frost, no foil on glass",
                "native_reconstruction_plan": "typography-only front",
                "reference_ids": []})
        # the Gate-1 checkpoint preserves the plan verbatim — the identity
        # resolver consults it first (2C-2E loader correction)
        meta0 = dict(self.project.metadata or {})
        meta0["gate1_prompt_plan"] = {
            "task_id": self.task.id,
            "prompt_plan": {"payload": {"variations": variations},
                            "prompts": []}}
        self.project.metadata = meta0
        self.project.save(update_fields=["metadata"])
        self.selected = self.images[1]
        contract = scc.build_visual_contract(
            self.selected, measurements=[], human_rationale=RATIONALE)
        scc.persist_visual_contract(self.project, contract)
        scc.record_selection_decision(
            self.project, selected_image=self.selected,
            unselected_images=[self.images[0], self.images[2]],
            rationale=RATIONALE, actor=self.user,
            contract_hash=contract["contract_hash"],
            now_iso=timezone.now().isoformat())
        meta = dict(self.project.metadata)
        meta["gate1_concept_selection_event"] = {
            "event_id": "testevent" * 4, "sequence_number": 8,
            "action": "pipeline.container_concept.select",
            "signing_epoch": "epoch-test",
            "lineage": "GateDecision #1 → DecisionEvent #8"}
        self.project.metadata = meta
        self.project.save(update_fields=["metadata"])
        ARIAAgent(self.task.id).resume_after_gate_1(self.selected.id)
        self.task.refresh_from_db()
        self.output = self.task.packaging_outputs.first()
        # §BH49(a): this fixture's tests exercise the 2C-2E confirmation of the TYPED numbers and the
        # parametric drawing of them, so the fixture DECLARES that source; the product path's own default
        # (M3_FIT — refused pending the owner's ruling on five geometry rules) is exercised by
        # ProductPathDrawsFromM3Tests below, which removes the declaration.
        # §BH50(a) ruled those five rules: the product path now passes them and reaches Gate 2, so the
        # Gate-2 flow tests (ConfirmationFlowTests, and the re-render test in Corr2AmendmentTests) remove the
        # declaration and run on it, while the typed numbers keep their declaration here and are refused
        # by the re-ruled rules through the same API (ProductPathDrawsFromM3Tests).
        self._declare_drawing_source("PARAMETRIC")
        # §2 human dimension confirmation + the CORR-2 §3 closure amendment
        scc.confirm_extension_dimensions(
            self.output, actor=self.user,
            now_iso=timezone.now().isoformat())
        self.output.refresh_from_db()
        scc.amend_closure_dimensions(
            self.output, revisions=scc.CORR2_CLOSURE_REVISIONS,
            actor=self.user, now_iso=timezone.now().isoformat(),
            reason="human Gate-2 second visual review — collar too large")
        self.output.refresh_from_db()
        scc.amend_closure_dimensions(
            self.output, revisions=scc.CORR3_PROPORTION_REVISIONS,
            actor=self.user, now_iso=timezone.now().isoformat(),
            reason="human Gate-2 third visual review — final slender "
                   "proportion (70.5+2.5+9.5+21.5=104)")

    def _declare_drawing_source(self, source):
        from apps.pipeline.targets.container import m3_backbone as m3
        self.output.refresh_from_db()
        spec = self.output.spec_sheet
        if source is None:
            spec.pop(m3.DRAWING_SOURCE_SCHEMA, None)
        else:
            spec[m3.DRAWING_SOURCE_SCHEMA] = {"schema_version": m3.DRAWING_SOURCE_SCHEMA, "source": source,
                                              "declared_by": "test fixture (§BH49(a))"}
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])

    def _confirm(self, back_height=36.0):
        self.output.refresh_from_db()
        from django.test import Client
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(self.user)
        with self.captureOnCommitCallbacks(execute=True):
            r = client.post(
                f"/api/tasks/{self.task.id}/confirm_container_profile/",
                {"profile": PROFILE_PAYLOAD,
                 "zones": _confirmed_zones(self.output.spec_sheet, back_height)},
                content_type="application/json")
        self.task.refresh_from_db()
        self.output.refresh_from_db()
        return r


class ExtensionConfirmationTests(Confirmation2C2EFixture):
    def test_confirmed_values_carry_concept_authority_and_referents(self):
        ext = self.output.spec_sheet[scc.EXTENSIONS_SCHEMA]
        assert ext["confirmation_state"] == scc.HUMAN_CONFIRMED
        f = ext["fields"]
        assert f["total_height"]["value"] == 104
        assert f["total_height"]["referent"] == "INCLUDES_DROPPER_CLOSURE"
        # amended twice; the CORR-3 value governs, referent preserved
        assert f["body_height"]["value"] == 70.5
        assert f["body_height"]["referent"] == \
            "BOTTOM_BASE_TO_TOP_OF_SHOULDER"
        assert "NEVER_ADDED_TO_TOTAL_HEIGHT_TWICE" in \
            f["neck_diameter"]["referent"]
        for entry in f.values():
            assert entry["confirmation_authority"] == scc.HUMAN_CONFIRMED
            assert entry["production_verification"] == scc.NOT_MFG_VERIFIED
            assert entry["editable"] is True
            assert entry["manufacturer_confirmation_required"] is True
        assert "verified manufacturing" in \
            ext["referent_notes"]["tolerances"]

    def test_carton_dims_stay_isolated_after_confirmation(self):
        self._confirm()
        spec = self.output.spec_sheet
        secondary = spec[scc.SECONDARY_PACKAGING_KEY]
        assert secondary["referent"] == "OUTER_CARTON"
        assert (secondary["width_mm"], secondary["depth_mm"],
                secondary["height_mm"]) == (40.0, 40.0, 110.0)
        # the confirmed bottle geometry is the HUMAN's 33×68 — never 40×110
        prof = spec[cc.PROFILE_SCHEMA]
        assert prof["fields"]["body_width_mm"]["value"] == 33
        assert prof["fields"]["body_height_mm"]["value"] == 68


class ConfirmationFlowTests(Confirmation2C2EFixture):
    """§BH50(a): the Gate-2 flow is the product's, and the product draws M3 by construction (§BH49(a)), so these
    tests remove the fixture's PARAMETRIC declaration and run on the path with none. The typed numbers' own flow
    through the same API is refused by the five geometry rules re-ruled to the M3 design (ProductPathDrawsFromM3Tests)."""

    def setUp(self):
        super().setUp()
        self._declare_drawing_source(None)

    def test_confirmation_reconstructs_and_stops_at_gate_2(self):
        tasks_before = DesignTask.objects.count()
        calls_before = ApiCallRecord.objects.count()
        r = self._confirm()
        assert r.status_code == 200, r.json()
        assert self.task.status == "awaiting_gate_2"
        assert ApiCallRecord.objects.count() == calls_before
        assert DesignTask.objects.count() == tasks_before      # no Packaging
        # no automatic human decision beyond the profile confirmation
        assert not GateDecision.objects.filter(
            task=self.task, gate="gate_2").exists()
        spec = self.output.spec_sheet
        # zones confirmed; the collar exclusion SURVIVES confirmation
        zrec = spec[cc.ZONES_SCHEMA]
        assert zrec["confirmation_state"] == "CONFIRMED"
        assert {z["zone_type"] for z in zrec["zones"]} == {
            "FRONT_PRINT_ZONE", "BACK_PRINT_ZONE", "BOTTOM_CODE_ZONE"}
        assert zrec["exclusions"][0]["zone"] == "OPTIONAL_COLLAR_ZONE"
        # §8 decisions with full lineage
        dec = spec[scc.DECISIONS_SCHEMA]
        refs = dec["references"]
        assert refs["selected_image_id"] == self.selected.id
        assert refs["visual_contract_hash"] == \
            self.project.metadata[scc.META_KEY]["contract_hash"]
        assert refs["concept_selection_event"]["sequence_number"] == 8
        assert refs["combined_confirmation_hash"] == \
            spec["container_confirmation"]["combined_hash"]
        # `BODY_WRAP_LABEL_ZONE_CONFIRMED` joined this set at §AH (sprint 15).
        # It appears here even though THIS fixture is a bottle and emits no
        # wrap, because `decisions` is the contract's standing list of what the
        # contract confirms, not a per-instance record of what was drawn — the
        # zone_type assertion twenty lines up is the per-instance one, and it
        # is unchanged at three. Two different questions, two different
        # assertions, and conflating them is how a contract change gets
        # mistaken for an artwork change.
        assert {d["decision"] for d in dec["decisions"]} == {
            "CONTAINER_PROFILE_CONFIRMED", "CONCEPT_DIMENSIONS_CONFIRMED",
            "BODY_FRONT_PRINT_ZONE_CONFIRMED",
            "BODY_BACK_PRINT_ZONE_CONFIRMED", "BOTTOM_CODE_ZONE_CONFIRMED",
            "BODY_WRAP_LABEL_ZONE_CONFIRMED",
            "OPTIONAL_COLLAR_ZONE_EXCLUSION_CONFIRMED"}
        assert "production_authority" in dec["non_authorizations"]
        # reconstruction output persisted
        assert spec["container_reconstruction"]["status"] == "RECONSTRUCTED"
        assert self.output.design_preview_ai
        # censuses: zero decorative rasters, live text present
        census = spec["container_design_graph/1.1"]
        assert census["decorative_raster_count"] == 0
        assert census["primitives"]["live_text"] > 5

    def test_material_separation_and_concept_fidelity_measured(self):
        self._confirm()
        spec = self.output.spec_sheet
        mats = spec["container_material_objects/1.0"]
        names = {o["name"] for o in mats["objects"]}
        assert {"GLASS_OUTER_WALL", "GLASS_INNER_WALL", "FROST_TREATMENT",
                "PRODUCT_FILL_APPEARANCE", "GLASS_BASE_THICKNESS",
                "GLASS_SPECULAR", "COLLAR_ROSE_GOLD_BASE",
                "BULB_DARK_PLUM"} <= names
        # visualization objects (speculars, curvature, collar sheen) are
        # all nonprinting — photographic styling never prints
        assert "GLASS_SPECULAR" in mats["nonprinting_visualization"]
        assert "LEFT_EDGE_CURVATURE" in mats["nonprinting_visualization"]
        assert "COLLAR_ROSE_GOLD_SPECULAR" in \
            mats["nonprinting_visualization"]
        assert mats["classification"] == \
            "PHOTOGRAPHIC_STYLING_NOT_PRINTED_ARTWORK"
        cf = spec["container_concept_fidelity/1.0"]
        assert cf["failures"] == []
        by_axis = {a["axis"]: a for a in cf["axes"]}
        # ACTUAL geometry measured, not metadata labels
        assert by_axis["bottle_aspect_ratio"]["state"] == "MEASURED_PASS"
        assert by_axis["bulb_to_collar_proportion"]["state"] == \
            "MEASURED_PASS"
        assert by_axis["glass_wall_vs_product_fill"]["state"] == \
            "MEASURED_PASS"
        assert by_axis["transparency_relationship"]["state"] == \
            "MEASURED_PASS"
        assert by_axis["generic_label_fallback"]["state"] == "MEASURED_PASS"
        # 2C-2E-CORR-1 §12: real-shape axes — a block cannot pass these
        for axis in ("cylindrical_form", "shoulder_geometry",
                     "visible_neck", "collar_cylindrical_geometry",
                     "collar_metallic_material", "bulb_slim_dome",
                     "frosted_glass_visualization", "logo_restraint",
                     "concept_sheet_presentation"):
            assert by_axis[axis]["state"] == "MEASURED_PASS", by_axis[axis]
        # §12: unverified back copy blocks production authority
        readiness = spec["container_production_readiness_codes"]
        assert any(c.startswith("CONTENT_VERIFICATION_REQUIRED")
                   for c in readiness.get("content", []))

    def test_the_seam_check_places_itself_off_the_dropper_and_its_codes_leave_readiness(self):
        """§BH50(f)(6) on the product path, task 52's exact zone geometry
        (22.0 × 40.0 at x 5.5, USER_CONFIRMED; BODY_FRONT, BODY_BACK, BOTTOM —
        no wrapped surface). Both seam codes fired here before the ruling, off
        the hand-set placement record, and nothing pinned them. Now the record
        reads NOT_APPLICABLE naming the three surfaces and their confirmation,
        the readiness channel is present and empty, and the board says so."""
        self._confirm()
        spec = self.output.spec_sheet
        wa = spec["container_wrap_alignment"]
        assert wa["seam_check"]["state"] == "NOT_APPLICABLE"
        assert wa["aligned"] is None
        for word in ("BODY_FRONT", "BODY_BACK", "BOTTOM", "USER_CONFIRMED"):
            assert word in wa["seam_check"]["reason"], word
        assert spec["container_production_readiness_codes"]["wrap_alignment"] == []
        assert spec["container_wrap_geometry/1.0"]["wrapped_zone_ids"] == []
        rows = {r["label"]: r["value"]
                for r in ProductContainerTarget().review_sections(self.task)}
        assert rows["Wrap alignment (seam check)"].startswith("NOT_APPLICABLE")
        assert "projected face, no seam" in rows["  Wrap (BODY_FRONT)"]

    def test_unmeasured_axes_block_acceptance_at_gate_2_and_never_the_reconstruction(self):
        """§BH50(f)(5) on the product path. The task reaches awaiting_gate_2 with
        blockers [] exactly as before — exploration untouched — while Gate-2
        approval refuses on one code per unmeasured fidelity axis, derived at
        read time and persisted nowhere; the wrap axis is NOT_APPLICABLE by the
        product's own zone record, and the board shows the derived count."""
        from apps.ire import container_production_readiness as cpr
        self._confirm()
        assert self.task.status == "awaiting_gate_2"
        spec = self.output.spec_sheet
        assert spec["container_reconstruction"]["blockers"] == []
        assert "fidelity_unmeasured" not in spec["container_production_readiness_codes"]
        assert spec["container_fidelity_report"]["blocking_scope"] == "ACCEPTANCE"
        assert spec["container_fidelity_report"]["axes"]["wrap_alignment"][
            "state"] == "NOT_APPLICABLE"
        derived = cpr.fidelity_unmeasured(spec)
        codes = derived["codes"]
        assert f"{cpr.FIDELITY_UNMEASURED}: wrap_alignment" not in codes
        assert sum(c.startswith(cpr.QUANT_FIDELITY_UNMEASURED) for c in codes) == 17
        assert derived["reports_absent"] == []
        refusal = cpr.gate2_refusal(spec)
        # [§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve,
        # never a block." They read in the refusal's failures, under "(block acceptance)" and "blocks acceptance,
        # not reconstruction"; they travel beside the refusal, and the board says what they are]
        assert refusal and all(c in refusal["acceptance_warnings"] and c not in refusal["failures"] for c in codes)
        rows = {r["label"]: r["value"]
                for r in ProductContainerTarget().review_sections(self.task)}
        assert rows["Unmeasured fidelity axes (a warning beside Approve)"].startswith(
            f"{len(codes)}: ")
        assert "not measured — a warning beside Approve" in rows["Concept fidelity"]
        assert not any("block" in v for k, v in rows.items() if "Unmeasured" in k or "not measured" in k)
        copy_rows = [v for k, v in rows.items() if k == "Copy not measured yet (warnings beside Approve)"]
        assert copy_rows == [] or not any(c in copy_rows[0] for c in codes)    # never listed twice

    def test_placeholder_copy_is_its_own_blocker_listed_per_piece(self):
        """§BH50(f)(2) on the product path. Six pieces of copy nobody has
        written, each with its own blocking code, each listing where its
        marker is drawn (the strip's six, the true-scale panel's five — NET
        CONTENT drops past the panel's edge) and the state of the record's own
        field; the front's net content listed under its piece as set copy from
        a composer literal; readiness['content'] written from the record; the
        typography record carrying no placeholder field, so the same pieces
        are no longer a typography failure; the reconstruction unblocked.

        [§BH54(b) (n), 2026-09-19 — the true-scale panel's FOUR, not five: this
        fixture's back zone is the old 22 × 36 with `make_zone`'s 3.0 on its
        record, and the panel now keeps that margin — 30.0 mm of copy height
        where the 1.5 mm inset gave 33.0 — so MANUFACTURER's marker drops past
        the edge with NET CONTENT's. Counted, named, blocking; nothing shrank.
        Eleven drawings became ten.]

        [§BH67(c)2, 2026-09-24 — the front's net content is the product
        record's `net_weight` now, never the composer's literal. This fixture's
        record holds none, so the front draws none and the piece lists no
        literal drawing; the record's own words are pinned in
        ProductPathDrawsFromM3Tests.]

        [His correction of 2026-10-07: "Shrink the whole label evenly until everything fits ... Floor: 3 pt."] — the
        true-scale panel's SIX: the back's copy shrinks evenly to 3.75 pt and stands whole, MANUFACTURER's and NET
        CONTENT's markers on it again. Ten drawings became twelve.]"""
        from apps.ire import container_placeholder_copy as cpc
        self._confirm()
        spec = self.output.spec_sheet
        assert spec["container_reconstruction"]["blockers"] == []
        rec = spec[cpc.SCHEMA]
        assert rec["back_copy_composed_on_this_path"] is True
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the pieces nobody has
        # written are filled with the system's copy for the type — still unwritten, their codes kept (never his copy) —
        # and where the back cannot hold them all, the first left off (``label_copy.DROP_ORDER``) is drawn nowhere,
        # listed last; only the net content, which no copy may invent, keeps its marker
        from apps.pipeline.services import label_copy as lc
        assert rec["unwritten"] == ["ingredients", "directions", "warnings", "manufacturer", "net_content",
                                    "description"]
        assert rec["marker_drawings"] == 13
        by_slot = {p["slot"]: p for p in rec["pieces"]}
        assert by_slot["product"]["unwritten"] is False
        for slot in rec["unwritten"]:
            piece = by_slot[slot]
            assert piece["code"] == f"{cpc.CONTENT_VERIFICATION_REQUIRED}:{slot}"
            assert piece["words_on_record"]["field"]
            if slot == "description":
                assert piece["drawn_at"] == [] and piece["not_drawn"] == ["left off the back for room"]
                continue
            scales = [d["scale"] for d in piece["drawn_at"]]
            assert "schematic" in scales
            if slot == "net_content":
                assert piece["placeholder_text"] == cpc.CONTENT_VERIFICATION_REQUIRED
            else:
                assert piece["placeholder_text"] != cpc.CONTENT_VERIFICATION_REQUIRED
                assert piece["source"] == lc.WRITTEN_SOURCE
        assert sorted(d["scale"] for d in by_slot["net_content"]["drawn_at"]) == ["schematic", "true_scale"]
        assert by_slot["net_content"]["not_drawn"] == []                 # [his correction of 2026-10-07] shrunk, whole
        assert by_slot["net_content"]["literal_drawings"] == []          # §BH67(c)2: a silent record, no literal
        assert rec["unslotted"] == [] and rec["contested"] == []
        assert rec["codes"] == [f"{cpc.CONTENT_VERIFICATION_REQUIRED}:{s}"
                                for s in rec["unwritten"]]
        assert spec["container_production_readiness_codes"]["content"] == rec["codes"]
        typo = spec["container_typography_metrics/1.0"]
        assert not any(k.startswith("placeholder_") for k in typo)
        rows = {r["label"]: r["value"]
                for r in ProductContainerTarget().review_sections(self.task)}
        assert rows["Copy · NET CONTENT"].startswith(
            f"{cpc.CONTENT_VERIFICATION_REQUIRED}:net_content · drawn at back-section-5-copy")   # the description left off
        assert "front-net-content" not in rows["Copy · NET CONTENT"]          # §BH67(c)2: nothing drawn on the front
        assert "record field Product.net_weight: empty" in rows["Copy · NET CONTENT"]
        assert "Copy · PRODUCT" not in rows

    def test_the_w2_floor_reads_the_copy_printed_on_the_product_and_nothing_else(self):
        """§BH50(f)(1) on the product path. Every run the sheet composer emits
        is declared; the floor judges the printed copy on BODY_FRONT and
        BODY_BACK and finds none below its floor; the sheet's annotations are
        out of scope and listed with the smallest named beside the product's
        minimum; the strip's and the bottom diagram's depictions are counted;
        BOTTOM, whose code is drawn only in the diagram, is named not
        measured — so the verdict is absent and the axis blocks honestly, on
        the product's own gap and not on the sheet's furniture; and the
        acceptance instrument says the same with its own code."""
        from apps.ire import container_typography_metrics as ctm
        self._confirm()
        spec = self.output.spec_sheet
        typo = spec[ctm.SCHEMA]
        assert typo["size_floor_scope_undeclared_runs"] == []
        assert typo["size_floor_declared_runs"] >= 40
        judged = typo["size_floor_runs"]
        assert judged and all(r["scope_source"] == "DECLARED" for r in judged)
        assert {r["surface"] for r in judged} == {"BODY_FRONT", "BODY_BACK"}
        assert typo["runs_below_size_floor"] == []
        assert "below_size_floor" not in typo
        assert typo["unmeasured"] == ["below_size_floor"]
        assert "§BH50(f)(1)" in typo["unmeasured_reasons"]["below_size_floor"]
        assert [s["surface"] for s in typo["size_floor_surfaces_not_measured"]] == ["BOTTOM"]
        assert typo["size_floor_depicted_by_surface"]["BOTTOM"] == 1
        assert typo["size_floor_depicted_by_surface"]["BODY_BACK"] >= 12
        annotations = typo["size_floor_out_of_scope_annotations"]
        assert len(annotations) >= 20
        # [his correction of 2026-10-07] the back shrunk evenly to stand — [his review, C (7)] with the full set, to
        # its floor (3.75 when it held only its markers)
        from apps.ire.back_panel import LABEL_FLOOR_PT
        assert typo["min_text_pt"] == LABEL_FLOOR_PT
        assert typo["min_annotation_pt"] == min(a["size_pt"] for a in annotations)
        assert typo["min_annotation_pt"] < 5.0
        placeholders = [r for r in judged if r["placeholder"]]
        assert placeholders and all(r["surface"] == "BODY_BACK" for r in placeholders)
        codes = spec["container_production_readiness_codes"]["production_method"]
        assert "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED" in codes
        assert "CONTAINER_MINIMUM_TEXT_SIZE_FAILED" not in codes
        val = spec["container_production_method_validation"]
        geom = val["measurements"]
        # measured on the first run of this test, not assumed: the strip depicts
        # BODY_BACK and the bottom diagram depicts BOTTOM, so both are listed as
        # depicted; BODY_BACK also prints (the true-scale panel), so BOTTOM alone
        # has no printed run and is the one surface the methods call unmeasured
        assert geom["depicted_text_surfaces"] == ["BODY_BACK", "BOTTOM"]
        assert set(geom["min_text_size_pt_by_surface"]) == {"BODY_BACK", "BODY_FRONT"}
        assert sorted({s for m in val["per_method"]
                       for s in m["text_size_unmeasured_surfaces"]}) == ["BOTTOM"]

    def test_the_colour_counter_reconciles_every_place_the_artefact_applies_colour(self):
        """§BH50(f)(7) on the product path: the emitted sheet applies colour as
        fills, strokes, text and gradient stops; the operator reader finds each
        kind, the counter holds each colour, the two sets agree both ways, the
        section is present and empty, and no colour is read through an ICC
        conversion — the ink a fills-only reader called absent is on the page
        as strokes and text."""
        self._confirm()
        spec = self.output.spec_sheet
        rec = spec["container_font_usage/1.0"]["colour_usage/1.0"]["reconciliation"]
        assert rec["schema_version"] == "colour_reconciliation/2.0"
        assert rec["status"] == "RECONCILED" and rec["agree"] is True and rec["codes"] == []
        assert all(rec["applied"][k] for k in ("fill", "stroke", "text", "stop"))
        assert "#2A2426" in rec["applied"]["stroke"] and "#2A2426" in rec["applied"]["text"]
        assert rec["applied_not_counted"] == [] and rec["counted_not_applied"] == []
        assert spec["container_production_readiness_codes"]["colour_usage"] == []

    def test_review_board_presents_gate_2_stage(self):
        self._confirm()
        rows = ProductContainerTarget().review_sections(self.task)
        by_label = {r["label"]: r["value"] for r in rows}
        assert by_label["Next required human action"] == \
            "HUMAN GATE-2 VISUAL REVIEW"
        assert "Material objects" in by_label
        assert "Concept fidelity (measured)" in by_label
        assert "all passed" in by_label["Concept fidelity (measured)"]
        assert "Production-readiness blockers" in by_label
        # §BH50(d): the board shows the palette the artefact is drawn with, where it showed spec['colors'] (whose
        # cap #B76E79 the artefact never draws)
        assert by_label["Colour · BODY_BASE"] == "#E8C9B3 · accent_nude · BRAND_GOV"
        assert by_label["Colour · TYPE_WINE"] == "#5A2C3A · no role · SURFACE_FALLBACK"
        assert by_label["Colour · INK"] == "#2A2426 · accent_dark · SURFACE_FALLBACK"
        assert "Body colour" not in by_label and "Cap colour" not in by_label


class BackCopyBlockerTests(Confirmation2C2EFixture):
    """§BH54(b), the second block, (q): "THE BACK COPY DOES NOT FIT THIS BODY — a named blocker, not a silence … nothing
    regulatory is dropped and nothing shrinks below its floor. Record it with its own code … this blocks acceptance of
    the back, nothing else." The panel's fit record lived in document metadata nothing on the governed path read, so
    CONTAINER_BACK_PANEL_COPY_EXCEEDS_PANEL — "which blocks", in its module's words — blocked nothing there. It is
    persisted now, and an overflow is this section's own code: at acceptance, never at reconstruction."""

    def setUp(self):
        super().setUp()
        self._declare_drawing_source(None)             # the product path, which draws M3 by construction (§BH49(a))

    def test_his_review_c7_the_systems_pieces_are_left_off_a_small_back_never_its_markers(self):
        """[His review of 127, 130, 131 and 132, 2026-10-15, C (7): "Every back label carries the full set ... When the
        brief gives no back copy, write sensible standard copy ... Never leave it nearly empty."] With no copy of his, a
        22 × 24 back that cannot hold the written pieces even at 3 pt leaves them off one at a time and stands: no
        piece's record marker is printed in its place, and every piece nobody has written keeps its code at
        acceptance."""
        from apps.ire import back_panel as bp
        from apps.ire import container_placeholder_copy as cpc
        assert self._confirm(back_height=24.0).status_code == 200
        spec = self.output.spec_sheet
        assert spec[bp.SCHEMA]["fits"] is True
        form = spec["container_label_form/1.0"]
        assert form["dropped"] and "description" in form["dropped"]
        rec = spec[cpc.SCHEMA]
        assert {"description", "ingredients", "directions", "warnings"} <= set(rec["unwritten"])
        left_off = {p["slot"] for p in rec["pieces"] if p["not_drawn"] == ["left off the back for room"]}
        assert {"description", "ingredients", "directions", "warnings"} <= left_off
        assert all(not p["drawn_at"] for p in rec["pieces"] if p["slot"] in left_off)
        assert set(rec["codes"]) == set(spec["container_production_readiness_codes"]["content"])
        assert "CONTENT_VERIFICATION_REQUIRED:description" in rec["codes"]
        assert self.task.status == "awaiting_gate_2"

    def test_an_overflowing_back_is_named_at_acceptance_and_never_blocks_the_reconstruction(self):
        """[His correction of 2026-10-07: "Shrink the whole label evenly until everything fits ... Floor: 3 pt. Only if
        it still doesn't fit at 3 pt, stop and tell me".] The 22 × 36 back this fixture confirmed now holds all seven
        shrunk evenly to 3.75 pt; a 22 × 24 back does not hold them even at 3 pt, and is the overflow measured here.
        [His review of 127, 130, 131 and 132, 2026-10-15, C (7)] the pieces the system writes are left off a back too
        small for them (``test_his_review_c7_the_systems_pieces_are_left_off_a_small_back_never_its_markers``); HIS copy
        never is — so the overflow measured here is his brief's own back copy, which counts as his (a18911a, answer 3)."""
        from apps.ire import back_panel as bp
        from apps.ire import container_production_readiness as cpr
        self.task.task_text = ("dropper bottle serum — modern rose apothecary\nBack copy: Description: A nightly rose "
                               "facial oil for dry and tired skin. / Directions: Warm three drops between the palms and "
                               "press onto clean skin each evening. / Ingredients: Rosa Damascena Flower Oil, Squalane, "
                               "Tocopherol. / Warnings: For external use only; avoid the eyes; stop if irritation "
                               "occurs.")
        self.task.save(update_fields=["task_text"])
        assert self._confirm(back_height=24.0).status_code == 200
        spec = self.output.spec_sheet
        fit = spec[bp.SCHEMA]                                            # persisted: the record is read now
        assert fit["fits"] is False and fit["margin_mm"] == 3.0 and fit["size_pt"] == bp.LABEL_FLOOR_PT == 3.0
        excluded = [s["heading"] for s in fit["sections"] if s["lines_emitted"] < s["lines_required"]]
        assert excluded == ["DIRECTIONS", "WARNINGS", "NET CONTENT"]               # his own pieces: never left off
        codes = spec["container_production_readiness_codes"]["back_copy"]
        # his brief's pieces, untranslated here (no call in tests), are named beside it as before
        assert [c for c in codes if not c.startswith(cpr.BACK_COPY_DOES_NOT_FIT)] == [
            c for c in codes if c.startswith("CONTAINER_LABEL_NOT_TRILINGUAL:")]
        codes = [c for c in codes if c.startswith(cpr.BACK_COPY_DOES_NOT_FIT)]
        assert len(codes) == 1 and codes[0].startswith(cpr.BACK_COPY_DOES_NOT_FIT + ": ")
        assert "DIRECTIONS" in codes[0] and "NET CONTENT" in codes[0] and "nothing is dropped or moved" in codes[0]
        assert "as small as its floor lets the whole label shrink" in codes[0]
        blockers = spec["container_reconstruction"]["blockers"]
        assert blockers == [] and not any("BACK_COPY" in str(b) for b in blockers)   # acceptance of the back, nothing else
        assert self.task.status == "awaiting_gate_2"                                 # the reconstruction went through
        verdict = cpr.build_readiness(spec)
        assert codes[0] in verdict["blocking_codes"] and verdict["ready"] is False
        assert codes[0] in verdict["sections"]["back_copy"]["codes"]
        assert not any(i["what"] == "readiness section 'back_copy'" for i in cpr.spec_staleness(spec)["checks_predate"])

    def test_the_code_is_built_from_the_fit_record_and_an_unmeasured_fit_is_never_clean(self):
        from apps.ire import back_panel as bp
        from apps.ire import container_production_readiness as cpr
        assert cpr.back_copy_codes({"fits": True, "fit_measured": True, "codes": []}) == []
        for record, words in ((None, "no fit record"), ({"fit_measured": False, "codes": [bp.FIT_UNMEASURED]}, bp.FIT_UNMEASURED),
                              ({"emitted": False, "codes": [bp.NO_CONFIRMED_ZONE]}, bp.NO_CONFIRMED_ZONE)):
            codes = cpr.back_copy_codes(record)
            assert len(codes) == 1 and codes[0].startswith(cpr.BACK_COPY_FIT_UNMEASURED + ": ") and words in codes[0]
        over = cpr.back_copy_codes({"fits": False, "fit_measured": True, "codes": [bp.COPY_EXCEEDS_PANEL], "size_pt": 5.0,
                                    "height_required_mm": 159.32, "height_available_mm": 36.6, "overflow_mm": 122.72,
                                    "column_mm": 16.0, "sections": [{"heading": "PRODUCT", "lines_required": 3, "lines_emitted": 3},
                                                                    {"heading": "WARNINGS", "lines_required": 10, "lines_emitted": 0}]})
        assert over == [cpr.BACK_COPY_DOES_NOT_FIT + ": the back copy needs 159.32 mm of the 36.6 mm its zone gives at 5 pt — "
                        "as small as its floor lets the whole label shrink — in a 16 mm column — over by 122.72 mm; outside "
                        "the panel's edge, whole or in part: WARNINGS. nothing is dropped or moved to fit: what the edge "
                        "excludes is not drawn, and this blocks acceptance of the back"]

    def test_a_spec_saved_before_the_section_reads_unmeasured_and_stale_and_a_standing_blocker_is_read(self):
        from apps.ire import container_production_readiness as cpr
        assert self._confirm().status_code == 200
        spec = dict(self.output.spec_sheet)
        persisted = {k: v for k, v in spec["container_production_readiness_codes"].items() if k != "back_copy"}
        old = {**spec, "container_production_readiness_codes": persisted}
        verdict = cpr.build_readiness(old)
        # [§BH71 (0a): unmeasured, never clean — a warning beside Approve since; it read as the section's codes]
        assert verdict["sections"]["back_copy"]["acceptance_warnings"] == [
            cpr.BACK_COPY_FIT_UNMEASURED + ": no back copy fit on record"]
        assert verdict["sections"]["back_copy"]["codes"] == []
        stale = cpr.spec_staleness(old)
        assert stale["stale"] and {"readiness section 'back_copy'"} <= {i["what"] for i in stale["checks_predate"]}
        assert cpr.SECTION_SINCE["back_copy"][:2] == ("2026-09-19", "§BH54(b) (q)")
        # the STANDING blocker — his ruling awaited — is read at read time, whatever the panel of the day holds
        clean = {**spec, "container_production_readiness_codes": {**spec["container_production_readiness_codes"], "back_copy": []}}
        assert cpr.build_readiness(clean)["sections"]["back_copy"]["codes"] == []
        standing = {**clean, cpr.BACK_COPY_BLOCKER_KEY: {"status": cpr.BACK_COPY_AWAITING_RULING,
                                                         "summary": "fixture summary of the measurement"}}
        codes = cpr.build_readiness(standing)["sections"]["back_copy"]["codes"]
        assert codes == [cpr.BACK_COPY_DOES_NOT_FIT + ": fixture summary of the measurement"]
        ruled = {**clean, cpr.BACK_COPY_BLOCKER_KEY: {"status": "RULED", "summary": "x"}}
        assert cpr.build_readiness(ruled)["sections"]["back_copy"]["codes"] == []


class Corr2AmendmentTests(Confirmation2C2EFixture):
    def test_amendment_is_additive_and_preserves_history(self):
        ext = self.output.spec_sheet[scc.EXTENSIONS_SCHEMA]
        # BOTH amendments on record, each preserving its prior values
        assert len(ext["amendments"]) == 2
        am1, am2 = ext["amendments"]
        assert am1["previous_values"]["collar_diameter"] == 28
        assert am1["revised"]["collar_diameter"] == 24
        assert am2["previous_values"]["collar_diameter"] == 24
        assert am2["previous_values"]["body_diameter"] == 33
        assert am2["revised"] == {
            "body_diameter": 31.5, "body_height": 70.5,
            "neck_diameter": 9, "visible_neck_height": 2.5,
            "collar_diameter": 21.5, "collar_height": 9.5,
            "bulb_width": 11, "bulb_height": 21.5}
        for am in (am1, am2):
            assert am["amendment"] == "HUMAN_CONCEPT_DIMENSION_AMENDMENT"
            assert am["authority"] == scc.HUMAN_CONFIRMED
            assert len(am["amendment_hash"]) == 64
        assert len(ext["extensions_hash"]) == 64
        f = ext["fields"]
        assert f["body_diameter"]["value"] == 31.5
        assert f["body_height"]["value"] == 70.5
        assert f["collar_diameter"]["value"] == 21.5
        assert f["collar_height"]["value"] == 9.5
        assert f["bulb_width"]["value"] == 11
        assert f["bulb_height"]["value"] == 21.5
        assert f["neck_diameter"]["value"] == 9
        assert f["visible_neck_height"]["value"] == 2.5
        for name in ("collar_diameter", "collar_height", "bulb_width",
                     "bulb_height", "visible_neck_height",
                     "body_diameter", "body_height"):
            assert f[name]["production_verification"] == scc.NOT_MFG_VERIFIED
            assert f[name]["manufacturer_confirmation_required"] is True

    def test_rejection_survives_the_corrected_rerender(self):
        # a prior human rejection stays on record through the machine re-run
        spec = self.output.spec_sheet
        spec["container_reconstruction_rejected_2026_07_27_gate2"] = {
            "state": "REJECTED", "codes": ["HUMAN_GATE2_VISUAL_REJECTION"],
            "rejected_output": {"design_preview": "x.png"}}
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        GateDecision.objects.create(task=self.task, gate="gate_2",
                                    decision="reject",
                                    decided_by=self.user, notes="r")
        self._declare_drawing_source(None)   # §BH50(a): the re-render is the product's, on the path with no declaration
        self._confirm()
        assert self.task.status == "awaiting_gate_2"
        spec = self.output.spec_sheet
        assert "container_reconstruction_rejected_2026_07_27_gate2" in spec
        from apps.pipeline.targets.composite import stage_human_acceptance
        hda = stage_human_acceptance(self.task)
        assert hda["state"].startswith("REJECTED")
        # no automatic approval appeared
        assert not GateDecision.objects.filter(
            task=self.task, gate="gate_2", decision="approve").exists()


class DropperGeometryTests(TestCase):
    def _backbone(self):
        return build_backbone(ContainerProfile(
            archetype="bottle", variant="cylindrical", height_mm=104,
            width_mm=33, neck_ratio=10 / 33, cap_style="dropper",
            closure_geometry={"collar_h": 14, "bulb_h": 22, "collar_w": 28,
                              "base_thickness": 3.5, "shoulder_radius": 3}))

    def test_dropper_backbone_separates_collar_and_bulb(self):
        b = self._backbone()
        assert b.collar_region is not None and b.bulb_region is not None
        assert b.base_band_mm == 3.5
        # collar band sits between the bulb and the body
        collar_ys = [getattr(s, "y", None) for s in b.collar_region
                     if getattr(s, "y", None) is not None]
        assert min(collar_ys) == 22 and max(collar_ys) == 36

    def test_generic_composition_fails_material_fidelity(self):
        from apps.ire.compose_container import compose_container_graph
        from apps.ire.container_concept_fidelity import (
            MATERIAL_RELATIONSHIP_FAILED,
            measure_concept_fidelity,
        )
        doc = compose_container_graph(self._backbone(), colors={},
                                      product_name="X")
        report = measure_concept_fidelity(doc, {
            "total_height_mm": 104, "body_height_mm": 68,
            "body_diameter_mm": 33, "collar_height_mm": 14,
            "bulb_height_mm": 22, "collar_diameter_mm": 28,
            "base_thickness_mm": 3.5})
        assert MATERIAL_RELATIONSHIP_FAILED in report["failures"]

    def test_block_shapes_fail_the_real_shape_axes(self):
        """§12: swapping the believable geometry for flat blocks must trip
        the mandated codes even when every nominal dimension matches."""
        from apps.ire import container_concept_fidelity as ccf
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.graph import Rect, SolidFill, Color

        geometry = {
            "total_height_mm": 104.0, "body_height_mm": 70.5,
            "body_diameter_mm": 31.5, "collar_height_mm": 9.5,
            "bulb_height_mm": 21.5, "collar_diameter_mm": 21.5,
            "bulb_width_mm": 11.0, "visible_neck_mm": 2.5,
            "neck_diameter_mm": 9.0, "base_thickness_mm": 3.5,
            "shoulder_radius_mm": 3.0, "frost_intensity": 0.7,
            "translucency": 0.35}
        zones = [{"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE",
                  "x": 5.5, "y": 10.0, "width": 22.0, "height": 40.0},
                 {"zone_id": "z_bottom", "zone_type": "BOTTOM_CODE_ZONE",
                  "x": 9.5, "y": 14.0, "width": 14.0, "height": 5.0}]
        doc = compose_dropper_sheet(
            geometry, zones=zones, reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X",
            back_sections=[{"heading": "P", "text": "x"}],
            revision_status="TEST", drawing_source="PARAMETRIC")   # §BH49(a): this test's subject is the parametric drawing
        # §BH50(a): JULY'S BOTTLE FAILS THE FIVE RULES RE-RULED TO THE CHOSEN DESIGN, by test. Until the ruling this
        # line read `== []`: the 2026-07-27 thresholds were written for this drawing. Re-derived from the M3 render's
        # measured values with two-sided bands, the typed numbers' bottle (top/body 0.2857, neck 0.2667, collar
        # w/h 1.9907, bulb 0.5116 x collar, aspect 2.0182) fails every one and nothing else.
        july = ccf.measure_concept_fidelity(doc, geometry)
        assert set(july["failures"]) == set(ccf.RE_RULED_GEOMETRY_CODES)
        july_axes = {a["axis"]: a for a in july["axes"]}
        assert july_axes["cylindrical_form"]["value"] == "curves=5, top/body=0.29"
        # §BH50(f)(8) line 7: rule 3 reads July's visible waist — its glass, whose top sits below its collar's
        # bottom, narrows to 0.2857 x body in the interval (was the NECK_GLASS box, 0.27); still outside the band
        assert july_axes["visible_neck"]["value"]["waist_over_body"] == 0.2857
        assert july_axes["collar_cylindrical_geometry"]["value"] == 1.99
        assert july_axes["bulb_slim_dome"]["value"]["width_vs_collar"] == 0.51
        assert july_axes["bulb_slim_dome"]["value"]["aspect"] == 2.02
        # §BH50(f)(8) line 8: July's parametric bulb has no skirt, so its shaft IS its box — the shaft leg reads
        # 0.5116 (inside the band by 0.0007, as the list states) and the slenderness 2.0182 fails it by 0.124
        assert july_axes["bulb_slim_dome"]["value"]["shaft_vs_collar"] == 0.5116
        assert july_axes["bulb_slim_dome"]["value"]["slenderness"] == 2.0182
        # degrade: replace the believable bottle parts with flat blocks at
        # the SAME nominal dimensions
        nodes = {str(n.name): (n, p) for n, p in doc.walk()
                 if getattr(n, "name", None)}
        for victim, rect in (
                ("GLASS_OUTER_WALL", Rect(name="GLASS_OUTER_WALL", x=128,
                                          y=79.5, w=43.6, h=91.6,
                                          fill=SolidFill(
                                              color=Color.from_hex("#D8BEB8"),
                                              opacity=0.35))),
                ("BULB_DARK_PLUM", Rect(name="BULB_DARK_PLUM", x=140, y=32,
                                        w=25, h=29,
                                        fill=SolidFill(
                                            color=Color.from_hex("#3F2A33"))))):
            node, parent = nodes[victim]
            parent.children[parent.children.index(node)] = rect
        # drop the shoulder ellipse + curvature shades (the block world)
        for gone in ("SHOULDER_ELLIPSE", "LEFT_EDGE_CURVATURE"):
            node, parent = nodes[gone]
            parent.children.remove(node)
        report = ccf.measure_concept_fidelity(doc, geometry)
        assert ccf.MATERIAL_RELATIONSHIP_FAILED in report["failures"]
        # rebuild with shades present but block wall/bulb: shape axes fire
        doc2 = compose_dropper_sheet(
            geometry, zones=zones, reference_path=None, logo_path=None,
            product_name="Rose Damascena", sku="X",
            back_sections=[{"heading": "P", "text": "x"}],
            revision_status="TEST")
        nodes2 = {str(n.name): (n, p) for n, p in doc2.walk()
                  if getattr(n, "name", None)}
        for victim, rect in (
                ("GLASS_OUTER_WALL", Rect(name="GLASS_OUTER_WALL", x=128,
                                          y=79.5, w=43.6, h=91.6,
                                          fill=SolidFill(
                                              color=Color.from_hex("#D8BEB8"),
                                              opacity=0.35))),
                ("BULB_DARK_PLUM", Rect(name="BULB_DARK_PLUM", x=140, y=32,
                                        w=25, h=29,
                                        fill=SolidFill(
                                            color=Color.from_hex("#3F2A33"))))):
            node, parent = nodes2[victim]
            parent.children[parent.children.index(node)] = rect
        report2 = ccf.measure_concept_fidelity(doc2, geometry)
        assert ccf.CYLINDRICAL_FORM_NOT_PRESERVED in report2["failures"]
        assert ccf.SHOULDER_GEOMETRY_FAILED in report2["failures"]
        assert ccf.BULB_GEOMETRY_FAILED in report2["failures"]


class TheOneAnchorTests(TestCase):
    """§BH48(b) / §BH49(a) — the one millimetre anchor, the ruling's 31.5 mm on the body, and nothing else. It
    lived in the REFIT fitter (container_profile_fit.py) and was pinned there; the clean-up of 2026-10-04 removed
    REFIT on the owner's word and moved the anchor first, its value unchanged, into m3_backbone — the drawing
    that uses it. The fitter's own tests left with it (git history keeps them); §BH49's hard stop "the anchor
    moving" is held here."""

    def test_the_anchor_is_the_rulings_31_5_and_nothing_else(self):
        from apps.pipeline.targets.container import m3_backbone as m3
        self.assertEqual(m3.ANCHOR_MM, 31.5)


class ProductPathDrawsFromM3Tests(Confirmation2C2EFixture):
    """§BH49(a) — the live path resolves to M3_FIT by construction; the typed numbers only by declaration; an
    unknown declaration is refused by name (REFIT, (i), among them since the clean-up of 2026-10-04 removed it). Through the confirmation API, as production runs it:
    the resume wrapper turns a refusal into ``generation_error`` and returns the task to its gate.
    §BH50(a) — the five geometry rules are re-ruled to the M3 render's measured values: the undeclared path now
    passes them and reaches Gate 2, and a declaration of the typed numbers draws July's bottle, which they refuse."""

    def _refused(self, source):
        from apps.pipeline.targets.container import m3_backbone as m3
        self._declare_drawing_source(source)
        self._confirm()
        spec = self.output.spec_sheet
        return spec, spec.get("generation_error", ""), m3

    def test_a_front_whose_fit_carries_no_code_is_clean_at_readiness_not_unrecorded(self):
        """THE OWNER'S SECOND ANSWER OF 2026-09-25, found by task 52's redraw: since Gate 2 measures the front's height
        a fit can carry no code at all, and the target read that clean fit as "no fit record on this run" — a refusal
        of a front that holds. A one-word name that fits, and a record that prints nothing else on the front."""
        spec = dict(self.output.spec_sheet or {})
        spec["product_name"] = "Rose"
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        spec, error, _m3 = self._refused(None)
        assert error == "", error
        fit = spec["container_front_copy_fit/1.1"]
        assert [r["text"] for r in fit["name_runs"]] == ["Rose"]
        assert fit["codes"] == [] and {r["state"] for r in fit["vertical_runs"]} == {"HELD"}
        assert spec["container_production_readiness_codes"]["front_copy"] == []

    def test_with_no_declaration_the_path_draws_m3_passes_the_re_ruled_rules_and_reaches_gate_2(self):
        # §BH49(a) pinned this path REFUSED_PENDING_RULING on the five rules; §BH50(a) ruled them, and retired that status
        spec, error, m3 = self._refused(None)
        assert error == "", error
        assert self.task.status == "awaiting_gate_2"
        rec = spec["container_reconstruction"]
        assert rec == {"status": "RECONSTRUCTED", "blockers": []}
        assert spec["container_concept_fidelity/1.0"]["failures"] == []
        # §BH50(f)(8) line 7: on the product path the waist reader reads the band's own centre — the pin that the
        # live path draws the waist the centre was set on
        from apps.ire import container_concept_fidelity as ccf
        _axes = {a["axis"]: a for a in spec["container_concept_fidelity/1.0"]["axes"]}
        assert _axes["visible_neck"]["value"]["waist_over_body"] == round(ccf.NECK_TO_BODY_BAND[0], 4)
        # §BH50(f)(8) line 8: and the dome reader reads its two centres there
        assert _axes["bulb_slim_dome"]["value"]["shaft_vs_collar"] == round(ccf.SHAFT_TO_COLLAR_BAND[0], 4)
        assert _axes["bulb_slim_dome"]["value"]["slenderness"] == round(ccf.BULB_SLENDERNESS_BAND[0], 4)
        src = spec[m3.DRAWING_SOURCE_SCHEMA]
        assert src["source"] == m3.DRAWING_M3_FIT
        assert src["anchor_mm"] == 31.5 and src["anchor_source"] == "m3_backbone.ANCHOR_MM"
        # §BH71 PART 1: "the design says when the fallback was used" — the dropper keeps the M3 drawing §BH49
        # chose, and its outline's record says so beside the drawing source
        from apps.pipeline.services import concept_outline as co
        from apps.pipeline.targets.container import OUTLINE_SOURCE_KEY
        outline = spec[OUTLINE_SOURCE_KEY]
        assert (outline["source"], outline["reason"]) == (co.TEMPLATE_FALLBACK, co.TRACE_NOT_TRACED_FORM), outline
        assert outline["detail"] == "the dropper keeps the M3 drawing chosen at §BH49"
        assert self.output.design_preview_ai
        # §BH50(b): the composer's record of the small copy at the floor reaches the spec sheet — both inside
        # the zone, the OUTER BOUND (§BH50(g)(1)); the verdict is against the safe area, below
        fit = spec["container_front_copy_fit/1.1"]
        # §BH67(c)2, 2026-09-24: "Derive both from the product record; where the record is silent, print nothing."
        # This fixture's record is SILENT on both — product_type "carton", packaging-only (§BH65(b)1), and no
        # net_weight — so the front prints neither line and the fit has no small-copy run to judge
        assert fit["runs"] == []
        # §BH50(f)(3): the front copy reaches Gate 2 as its own readiness
        # channel. §BH50(g)(1), re-typed §BH53(a) 2026-09-17: "THE 16.0 mm SAFE
        # AREA GOVERNS THE FRONT … Gate 2 refuses the current front until it is
        # re-laid, and that refusal is correct." On this product the support
        # line is refused on the safe area (22.0 − 2 × 3.0 = 16.0 mm) by
        # 5.5036 mm — his "5.5 mm" — while the outer bound holds it by 0.4964;
        # the net content is inside; the vertical axis stays the honest
        # unmeasured code — all at acceptance, never the reconstruction
        # [the owner's second answer of 2026-09-25: the vertical axis is measured since — every run inside the band]
        # [§BH67(c)2: the support line refused here was the letter-spaced
        # "N I G H T   R E P A I R   O I L" literal his (c)2 retired; on this
        # silent record nothing prints there, and the NAME's refusal stands]
        assert fit["safe_area_mm"] == 16.0
        # §BH68(d), OWNER RULED 2026-09-24: "Derive it from the product record; print nothing where the record is
        # silent." THE RECORD'S NAME NOW REACHES THE FRONT, and this record's name — "Rose Damascena Night Repair Oil",
        # the real BBR-SK-201's — is the one the hard-coded "Rose" / "Damascena" stood in for. The ruled wrap (§BD(b),
        # `wrap_name`) sets it "Rose Damascena" / "Night Repair" / "Oil", and the instrument measures each line in the
        # face the emitter draws: the first 28.5909 mm — past the safe area by 12.5909 mm and past the ZONE itself by
        # 6.5909 mm, so the hero panel's clip cuts it — the second 21.028 mm, past the safe area by 5.028 mm, the third
        # held. Gate 2 refuses the front by name and that refusal is correct (§BH50(f)(3): "Text that does not fit is a
        # design problem to solve, not a number to shrink"). The wrap balances the five words over at most three lines
        # — two, two, one — and measures no line: even by its own estimate the first is 23.31 mm against the 20.68 mm
        # it wraps to. How a name this long breaks across this lockup is the owner's, and nothing here decides it.
        # Until §BH68(d) the pin was "Damascena" alone, past the safe area by 3.5897 mm.
        assert fit["overruns"] == [
            {"code": "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA", "run": "product-name-hero-0",
             "over_mm": pytest.approx(12.5909, abs=1e-3), "limit_mm": 16.0},
            {"code": "CONTAINER_FRONT_COPY_EXCEEDS_ZONE", "run": "product-name-hero-0",
             "over_mm": pytest.approx(6.5909, abs=1e-3), "limit_mm": 22.0},
            {"code": "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA", "run": "product-name-hero-1",
             "over_mm": pytest.approx(5.028, abs=1e-3), "limit_mm": 16.0}]
        # §BH50(g)(2): the product name is front copy — each line judged on the safe area like any other run
        hero = {r["name"]: r for r in fit["name_runs"]}
        assert [(n, hero[n]["text"], hero[n]["state"]) for n in sorted(hero)] == [
            ("product-name-hero-0", "Rose Damascena", "EXCEEDS_SAFE_AREA"),
            ("product-name-hero-1", "Night Repair", "EXCEEDS_SAFE_AREA"),
            ("product-name-hero-2", "Oil", "HELD")]
        assert spec["container_production_readiness_codes"]["front_copy"] == [
            "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: product-name-hero-0 +12.5909 mm",
            "CONTAINER_FRONT_COPY_EXCEEDS_ZONE: product-name-hero-0 +6.5909 mm",
            "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: product-name-hero-1 +5.028 mm"]
        # THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — the three lines and no net
        # content sit inside this 40.0 mm front's safe band at print size, so the vertical line that closed this list goes
        assert {r["state"] for r in spec["container_front_copy_fit/1.1"]["vertical_runs"]} == {"HELD"}
        assert spec["container_reconstruction"]["blockers"] == []
        from apps.ire.container_production_readiness import gate2_refusal
        refusal = gate2_refusal(spec)
        # §BH68(d): the record's name is refused at Gate 2 by name — on the safe area and past the zone itself
        assert refusal and {"CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: product-name-hero-0 +12.5909 mm",
                            "CONTAINER_FRONT_COPY_EXCEEDS_ZONE: product-name-hero-0 +6.5909 mm"} <= set(refusal["failures"])
        assert not any("front-support" in str(c) for c in refusal["failures"])      # §BH67(c)2: nothing drawn there
        rows = {r["label"]: r["value"]
                for r in ProductContainerTarget().review_sections(self.task)}
        assert "Front copy · front-support" not in rows
        # §BH68(d): the record's name on the board, line by line, as the instrument reads it — the first past the zone
        assert rows["Front copy · product-name-hero-0"].startswith("EXCEEDS_SAFE_AREA · 28.5909 mm at 9.0 pt in Montserrat-Bold")
        assert "outer bound 22.0 mm (-6.5909 mm" in rows["Front copy · product-name-hero-0"]
        assert rows["Front copy · product-name-hero-1"].startswith("EXCEEDS_SAFE_AREA · 21.028 mm at 9.0 pt in Montserrat-Bold")
        assert rows["Front copy · product-name-hero-2"].startswith("HELD · ")
        # THE OWNER'S SECOND ANSWER OF 2026-09-25: "Make Gate 2 measure the front's height." — the board's vertical row
        # reads the measure, where it read "UNMEASURED"; a refusal on the axis reaches the Gate-2 verdict row as a code
        assert rows["Front copy · vertical"].startswith("MEASURED at print size")
        # §BH50(g)(4): the board prints the reader's own verdict, derived at readiness-read, and a fresh product-path
        # spec reads CURRENT — every declared section is the run's
        assert rows["Gate-2 verdict (derived at readiness-read)"].startswith(f'{len(refusal["failures"])} blocking: ')
        # [the owner's answer of 2026-09-27: the maker's printing specification is a production note — on the board,
        # never among what Gate 2 refuses the design for]
        notes = rows["Production notes (for the printer)"]          # [his answer on the safe margin, 2026-10-01]
        assert " for the printer, never a reason it is refused: " in notes and "CONTAINER_TECHNIQUE_UNVERIFIED" in notes
        assert not any(str(c).startswith("CONTAINER_TECHNIQUE_UNVERIFIED") for c in refusal["failures"])
        assert "CONTAINER_TECHNIQUE_UNVERIFIED" in refusal["production_notes"]
        assert rows["Spec checks"].startswith("CURRENT as of ")
        assert "as persisted by the run" in rows["Production-readiness blockers"]
        # §BH50(d): the palette the sheet is drawn with reaches the spec sheet — four materials through brand_gov
        palette = {r["name"]: r for r in spec["container_palette/1.0"]["rows"]}
        assert {n for n, r in palette.items() if r["source"] == "BRAND_GOV"} == {
            "BODY_BASE", "GLASS_BASE", "ROSE_GOLD_LIGHT", "ROSE_GOLD_SPECULAR"}

    def test_bh67c2_the_front_prints_the_records_net_content_and_no_carton_descriptor(self):
        """§BH67(c)2 on the product path: BBR-SK-201's own record holds net_weight "30 ml e 1 fl. oz." and product_type
        "carton". The front prints the record's net content in the record's own spelling — never the "30 ml /
        1.01 fl. oz." literal — and no descriptor, a carton being what the product ships in (§BH65(b)1); the front's
        literal-copy rows name the record as their source."""
        self.task.product.net_weight = "30 ml e 1 fl. oz."          # BBR-SK-201's record, as held
        self.task.product.save(update_fields=["net_weight"])
        spec, error, _m3 = self._refused(None)
        assert error == "", error
        fit = spec["container_front_copy_fit/1.1"]
        assert [(r["name"], r["size_pt"], r["safe_area_state"]) for r in fit["runs"]] == [
            ("front-net-content", 5.0, "INSIDE")]
        pieces = {p["slot"]: p for p in spec["container_placeholder_copy/1.0"]["pieces"]}
        drawn = pieces["net_content"]["literal_drawings"]
        assert [(d["node"], d["text"]) for d in drawn] == [
            ("front-net-content", "30 ml e 1 fl. oz."), ("flat-front-net-content", "30 ml e 1 fl. oz.")]
        assert all(d["source"].startswith("Product.net_weight") for d in drawn)

    def test_a_declaration_of_the_typed_numbers_draws_julys_bottle_and_the_re_ruled_rules_find_it(self):
        # [his goal of 2026-10-13, (1): "NO check ever stops a design"] the re-ruled rules still find July's bottle — kept
        # on the record, BLOCKED — and the design goes on to Gate 2, each rule it fails said beside Approve in words
        from apps.dashboard.words import check_words
        from apps.ire import container_concept_fidelity as ccf
        spec, error, m3 = self._refused("PARAMETRIC")
        assert error == "", error
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_2"
        rec = spec["container_reconstruction"]
        assert rec["status"] == "BLOCKED"
        assert set(rec["blockers"]) == set(ccf.RE_RULED_GEOMETRY_CODES)
        shown = {r["code"]: r["what"] for r in spec["checks_shown/1.0"]}
        # [his review, C (7)] beside them, each piece of the back the system wrote: "not confirmed — please check"
        from apps.pipeline.services import label_copy as lc
        assert set(shown) == set(ccf.RE_RULED_GEOMETRY_CODES) | {lc.NOT_CONFIRMED}
        assert all(shown[c].startswith(check_words(c)) and check_words(c) for c in shown
                   if c != lc.NOT_CONFIRMED), shown
        assert spec[m3.DRAWING_SOURCE_SCHEMA]["source"] == m3.DRAWING_PARAMETRIC
        # refused on the geometry and nothing else: every other concept-fidelity axis still passes on July's bottle
        assert set(spec["container_concept_fidelity/1.0"]["failures"]) == set(ccf.RE_RULED_GEOMETRY_CODES)
        # the refused render is persisted with every report BEFORE the fail-closed raise, so it exists to be looked at
        assert self.output.design_preview_ai

    def test_a_declaration_of_refit_is_refused_by_name_now_it_is_removed(self):
        # the clean-up of 2026-10-04 removed REFIT (his goal: "M3 DRAWS was chosen; git history is REFIT's
        # history"); a record still declaring it is refused at the door by name, and nothing is fitted or drawn
        spec, error, m3 = self._refused("REFIT")
        assert error.startswith("CONTAINER_DRAWING_SOURCE_UNKNOWN"), error
        assert self.task.status == "awaiting_container_profile"
        assert "container_profile_fit/1.0" not in spec
        assert spec.get("container_reconstruction", {}).get("status") != "RECONSTRUCTED"

    def test_a_declaration_naming_anything_else_is_refused_by_name(self):
        spec, error, m3 = self._refused("SOMETHING_ELSE")
        assert error.startswith("CONTAINER_DRAWING_SOURCE_UNKNOWN"), error
        assert self.task.status == "awaiting_container_profile"


def _rows54():
    """sha256 of every model's rows in primary-key order, the sessions table apart — a render writes none of them."""
    import hashlib
    import json

    from django.apps import apps as _apps
    from django.db import DatabaseError, transaction
    digest = {}
    for model in _apps.get_models():
        if model._meta.label == "sessions.Session":
            continue
        try:
            with transaction.atomic():
                rows = list(model.objects.order_by("pk").values())
        except DatabaseError:
            continue
        digest[model._meta.label] = hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()
    return digest


class ExplorationRenderTests(Confirmation2C2EFixture):
    """§BH54(k) 2, OWNER RULED 2026-09-18 — THE DESIGN LOOP, its first step: "See variations side by side at full size,
    adjust a parameter and re-render, as EXPLORATION under §BH51(a) as ratified: ungoverned, no commit, no gate, no
    register entry, never claiming a state it has not earned. Trying a design must not cost a gate." A render is
    started from the owner's task page, on the product path (the M3 backbone by construction), and writes the
    exploration store and NOTHING the gate reads: no row of any model, no media, no provider call. Every other account
    is refused by name before a byte is drawn (§BH54(i)); a task no exploration can be drawn of is refused by name."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import tempfile
        from pathlib import Path

        from django.test import override_settings
        cls._tmp54 = tempfile.TemporaryDirectory()
        cls.store54 = Path(cls._tmp54.name) / "explorations"
        cls._override54 = override_settings(EXPLORATION_STORE=str(cls.store54), OWNER_ACCOUNT="confop")
        cls._override54.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override54.disable()
        cls._tmp54.cleanup()
        super().tearDownClass()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.store54, ignore_errors=True)
        super().tearDown()

    def _client(self, user=None):
        from django.test import Client
        client = Client(HTTP_HOST="127.0.0.1")
        if user is not None:
            client.force_login(user)
        return client

    def _url(self):
        return f"/dashboard/history/tasks/{self.task.id}/explore/"

    def test_the_owner_renders_an_exploration_from_the_task_page_and_nothing_the_gate_reads_moves(self):
        import hashlib
        import json
        from unittest.mock import patch

        from django.core.files.storage import FileSystemStorage

        from apps.dashboard import explorations
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        assert self.task.status == "awaiting_gate_2"
        owner = self._client(self.user)                          # "confop" is the owner here; login moves last_login
        page = owner.get(f"/dashboard/history/tasks/{self.task.id}/").content.decode()
        assert f'action="{self._url()}"' in page and "Render an exploration of this task" in page
        rows = _rows54()                                          # snapshot AFTER the login
        with patch.object(FileSystemStorage, "_save", side_effect=AssertionError("a render wrote media")), \
                patch("apps.pipeline.services.claude_service.call_claude",
                      side_effect=AssertionError("a render called a provider")) as claude:
            r = owner.post(self._url())
        assert r.status_code == 302, r.content[:300]
        slug = r["Location"].split("/explorations/")[1].split("/")[0]
        assert slug.startswith(f"t{self.task.id}-loop-") and r["Location"].endswith("#R001")
        assert _rows54() == rows        # no row of any model: no log, no decision, no spend record, no spec, no file name
        assert not claude.called
        study = self.store54 / slug
        assert sorted(p.name for p in study.iterdir()) == ["R001.json", "R001.png", "index.json"]
        record = json.loads((study / "R001.json").read_text())
        assert record["status"] == explorations.EXPLORATION_STATUS and explorations.claims(record) == ""
        assert record["task"] == self.task.id and record["made_by"].startswith("confop")
        png = (study / "R001.png").read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and hashlib.sha256(png).hexdigest() == record["picture_sha256"]
        assert record["codes_on_the_drawing"]["front_copy"]        # the drawing's own codes travel, as information
        assert record["fallback_literals_still_drawn"]             # §BH54(j): today's colours, every literal named
        assert [z["zone_id"] for z in record["zones_drawn"]][:2] == ["z_front", "z_back"]
        # seen where explorations are seen, under the §BH51(a) words; the task page links the study
        shown = owner.get(f"/dashboard/history/explorations/{slug}/").content.decode()
        assert f'src="/dashboard/history/explorations/{slug}/R001.png"' in shown and 'id="R001"' in shown
        assert explorations.EXPLORATION_STATUS in shown
        assert owner.get(f"/dashboard/history/explorations/{slug}/R001.png").status_code == 200
        assert f"/dashboard/history/explorations/{slug}/" in owner.get(
            f"/dashboard/history/tasks/{self.task.id}/").content.decode()
        # the same inputs draw the same pixels: a second render is a second record of one picture
        r2 = owner.post(self._url())
        assert r2.status_code == 302 and r2["Location"].endswith("#R002")
        second = json.loads((study / "R002.json").read_text())
        assert (second["inputs_sha256"], second["picture_sha256"]) == (record["inputs_sha256"], record["picture_sha256"])
        assert _rows54() == rows

    def test_every_other_request_is_refused_by_name_and_draws_nothing(self):
        from unittest.mock import patch

        from apps.ire import materials_placement as mp
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        other = User.objects.create_user("plain54", password="x")
        refused = self._client(other).post(self._url())
        body = refused.content.decode()
        assert refused.status_code == 403 and body.startswith("EXPLORATIONS_OWNER_ONLY: REFUSED") and "plain54" in body
        assert self._client().post(self._url()).status_code == 302              # anonymous: to the login
        owner = self._client(self.user)
        assert owner.get(self._url()).status_code == 405                        # the control is a POST and nothing else
        # a refusal at the emitter's placement seam — ahead of every byte — is named, and nothing is written
        with patch.object(mp, "refuse_or_skip",
                          side_effect=mp.PlacementRefused(mp.REFUSED_REFERENCE_ASSET, "materials/reference.png")):
            seam = owner.post(self._url())
        text = seam.content.decode()
        assert seam.status_code == 409 and text.startswith("EXPLORATION_RENDER_REFUSED_BY_THE_COMPOSER: REFUSED")
        assert "PlacementRefused" in text and "REFUSED_REFERENCE_ASSET" in text
        # a record that declares the typed numbers draws no exploration: the loop draws the M3 backbone only
        self._declare_drawing_source("PARAMETRIC")
        typed = owner.post(self._url())
        assert typed.status_code == 409
        assert typed.content.decode().startswith("EXPLORATION_RENDER_DRAWS_THE_M3_BACKBONE_ONLY: REFUSED")
        page = owner.get(f"/dashboard/history/tasks/{self.task.id}/").content.decode()
        assert "EXPLORATION_RENDER_DRAWS_THE_M3_BACKBONE_ONLY" in page and f'action="{self._url()}"' not in page
        assert not self.store54.exists() or not any(self.store54.rglob("*"))    # five refusals, not one byte


class ExplorationLoopTests(ExplorationRenderTests):
    """§BH54(k) 2 — "See variations side by side at full size, adjust a parameter and re-render." The loop page: the
    knobs an exploration may turn — the two print zones, the product name, the unwritten back pieces as DRAFT words
    (§BH54(h)), the four retained appearance fields, the raster's dpi — and the pictures side by side. A knob changes
    one picture's inputs in memory: the task's record is what it was, and the picture's record names every knob turned."""

    # the inherited tests run once, in ExplorationRenderTests; here they would only repeat
    test_the_owner_renders_an_exploration_from_the_task_page_and_nothing_the_gate_reads_moves = None
    test_every_other_request_is_refused_by_name_and_draws_nothing = None

    def _loop(self):
        return f"/dashboard/history/tasks/{self.task.id}/loop/"

    def test_a_knob_turned_is_a_new_picture_named_for_what_changed_and_the_record_of_the_task_is_untouched(self):
        import json

        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        page = owner.get(self._loop()).content.decode()
        assert "Adjust and re-render" in page and 'name="front_width"' in page and 'name="copy_net_content"' in page
        assert "No exploration of this task yet" in page
        rows = _rows54()
        first = owner.post(self._url(), {"from_loop": "1"})                       # the task as it stands
        assert first.status_code == 302 and "/loop/?study=" in first["Location"] and first["Location"].endswith("#R001")
        turned = owner.post(self._url(), {"from_loop": "1", "front_x": "2.0", "front_width": "26.0",
                                          "copy_net_content": "30 ml e 1.01 fl. oz.", "translucency": "0.5",
                                          "frost_intensity": ""})
        assert turned.status_code == 302 and "show=R001&show=R002" in turned["Location"]
        assert _rows54() == rows                                                   # the task's record is what it was
        slug = turned["Location"].split("study=")[1].split("&")[0]
        a, b = (json.loads((self.store54 / slug / f"{p}.json").read_text()) for p in ("R001", "R002"))
        assert a["what_changed"].startswith("nothing") and a["knobs"] == {}
        assert b["knobs"] == {"front_zone": {"x": 2.0, "width": 26.0}, "draft_copy": {"NET CONTENT": "30 ml e 1.01 fl. oz."},
                              "appearance": {"translucency": 0.5}}
        assert "front zone" in b["what_changed"] and "→ 26 ×" in b["what_changed"]
        assert "NET CONTENT: DRAFT words" in b["what_changed"] and "translucency" in b["what_changed"]
        assert b["draft_copy_sections"] == ["NET CONTENT"]
        assert [z["width"] for z in b["zones_drawn"] if z["zone_id"] == "z_front"] == [26.0]
        assert a["picture_sha256"] != b["picture_sha256"] and a["inputs_sha256"] != b["inputs_sha256"]
        # side by side: both pictures on the loop page, the second's knobs offered back to adjust from
        shown = owner.get(turned["Location"].split("#")[0]).content.decode()
        assert shown.count('class="card exploration"') == 2 and 'id="R001"' in shown and 'id="R002"' in shown
        assert "at full size" in shown and f"/dashboard/history/explorations/{slug}/R002.png" in shown
        again = owner.get(self._loop() + f"?study={slug}&from=R002&size=fit").content.decode()
        assert 'name="front_width" inputmode="decimal" value="26.0"' in again and "30 ml e 1.01 fl. oz.</textarea>" in again
        assert 'class="strip fit"' in again

    def test_the_loop_says_itself_in_words_its_fingerprints_and_codes_folded(self):
        # [the owner's answer to the UI directions of 2026-09-25, (d) "Plain words everywhere. No engine codes on
        # screen." — a picture's fingerprint, the drawing's codes and its time were on screen as the record wrote them]
        import re
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        first = owner.post(self._url(), {"from_loop": "1"})
        page = owner.get(first["Location"].split("#")[0]).content.decode()
        shown = re.sub(r"<[^>]+>", " ", re.sub(r"<details\b.*?</details>", " ", page, flags=re.S))
        assert "fingerprint" in shown and "sha256" not in shown, shown
        assert not re.search(r"\d{4}-\d\d-\d\dT\d\d", shown), shown
        assert "sha256" in page and 'name="picture_sha256"' in page      # each fingerprint still on the page, folded

    def test_a_bad_number_refuses_the_whole_render_by_name_and_the_loop_is_the_owners(self):
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        for field, value, words in (("front_width", "wide", "is not a number"), ("dpi", "1200", "outside 72"),
                                    ("translucency", "3", "outside 0")):
            r = owner.post(self._url(), {"from_loop": "1", field: value})
            text = r.content.decode()
            assert r.status_code == 409 and text.startswith("EXPLORATION_KNOB_REFUSED: REFUSED") and words in text, text
        other = User.objects.create_user("plain55", password="x")
        refused = self._client(other).get(self._loop())
        assert refused.status_code == 403 and refused.content.decode().startswith("EXPLORATIONS_OWNER_ONLY: REFUSED")
        assert self._client().get(self._loop()).status_code == 302
        assert owner.post(self._loop()).status_code == 405                          # the page is a GET and nothing else
        assert not self.store54.exists() or not any(self.store54.rglob("*"))


class OwnerAcceptanceTests(ExplorationRenderTests):
    """§BH54(b), the second block, (k) 3 — "ACCEPTANCE is my act alone, through the §BH26(a)-shaped channel, carrying my
    identity, the time, and the sha256 of exactly what I accepted. The machine may never write it, and a stale spec is
    re-derived first per (d). … both are proved here by test, in both directions — an acceptance that lacks any of the
    three fields is refused by name, and a REFERENCE asset placed in an exploration is refused by name." """

    test_the_owner_renders_an_exploration_from_the_task_page_and_nothing_the_gate_reads_moves = None
    test_every_other_request_is_refused_by_name_and_draws_nothing = None

    def _rendered(self):
        import json
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        r = owner.post(self._url())
        assert r.status_code == 302, r.content[:300]
        slug = r["Location"].split("/explorations/")[1].split("/")[0]
        return owner, slug, json.loads((self.store54 / slug / "R001.json").read_text())

    def _accept(self, client, slug, sha, decision="ACCEPTED", **more):
        return client.post(f"/dashboard/history/tasks/{self.task.id}/accept/",
                           {"study": slug, "picture": "R001", "picture_sha256": sha, "decision": decision, **more})

    def test_the_owner_accepts_a_picture_and_the_three_fields_are_recorded_and_reverified_on_every_read(self):
        from django.utils import timezone

        from apps.dashboard import explorations, owner_channel
        from apps.dashboard.models import OwnerAcceptance
        owner, slug, record = self._rendered()
        before = timezone.now()
        r = self._accept(owner, slug, record["picture_sha256"], note="the front reads well")
        assert r.status_code == 302 and r["Location"].endswith("#acts"), r.content[:300]
        act = OwnerAcceptance.objects.get()
        assert act.decided_by == self.user and act.decision == "ACCEPTED"                     # his identity
        assert before <= act.decided_at <= timezone.now()                                     # the time
        assert act.picture_sha256 == record["picture_sha256"]                                 # the sha256 of exactly that
        assert (act.inputs_sha256, act.knobs, act.task_id) == (record["inputs_sha256"], {}, self.task.id)
        page = owner.get(f"/dashboard/history/tasks/{self.task.id}/loop/?study={slug}").content.decode()
        assert "Your acts on this task" in page and act.picture_sha256 in page and ">confop<" in page
        from django.utils.html import escape
        assert escape(owner_channel.VERIFIED) in page and "Accept this picture" in page     # the page escapes the apostrophe
        # the exploration's own record is what it was: it still claims nothing, and is still an exploration
        assert explorations.claims(record) == "" and OwnerAcceptance.objects.count() == 1
        # a second act is a second row, never an update
        assert self._accept(owner, slug, record["picture_sha256"], decision="REJECTED").status_code == 302
        assert [a.decision for a in OwnerAcceptance.objects.order_by("pk")] == ["ACCEPTED", "REJECTED"]
        # re-verified on every read: drifted bytes read VOID, a missing picture reads VOID — shown, never a pass
        png = self.store54 / slug / "R001.png"
        png.write_bytes(png.read_bytes() + b"\x00")
        assert {a["verification"] for a in owner_channel.acts_for(self.task)} == {owner_channel.VOID_DRIFT}
        assert escape(owner_channel.VOID_DRIFT) in owner.get(
            f"/dashboard/history/tasks/{self.task.id}/loop/?study={slug}").content.decode()
        png.unlink()
        assert {a["verification"] for a in owner_channel.acts_for(self.task)} == {owner_channel.VOID_GONE}

    def test_an_acceptance_lacking_any_of_the_three_fields_is_refused_by_name_and_nothing_is_written(self):
        import datetime

        from django.contrib.auth.models import AnonymousUser
        from django.db import IntegrityError, transaction
        from django.utils import timezone

        from apps.dashboard import owner_channel as ch
        from apps.dashboard.models import OwnerAcceptance
        owner, slug, record = self._rendered()
        sha, now = record["picture_sha256"], timezone.now()
        other = User.objects.create_user("plain56", password="x")
        good = dict(user=self.user, decided_at=now, task=self.task, study=slug, picture="R001", picture_sha256=sha,
                    decision="ACCEPTED")
        for change, code in (
                ({"user": None}, ch.ACCEPTANCE_REFUSED_NO_IDENTITY),
                ({"user": AnonymousUser()}, ch.ACCEPTANCE_REFUSED_NO_IDENTITY),
                ({"user": other}, ch.ACCEPTANCE_REFUSED_NOT_THE_OWNER),
                ({"decided_at": None}, ch.ACCEPTANCE_REFUSED_NO_TIME),
                ({"decided_at": datetime.datetime(2026, 9, 19, 1, 0)}, ch.ACCEPTANCE_REFUSED_NO_TIME),   # no zone: not a time
                ({"picture_sha256": ""}, ch.ACCEPTANCE_REFUSED_NO_SHA256),
                ({"picture_sha256": "abc"}, ch.ACCEPTANCE_REFUSED_NO_SHA256),
                ({"picture_sha256": "0" * 64}, ch.ACCEPTANCE_REFUSED_NOT_THESE_BYTES),
                ({"picture": "R999"}, ch.ACCEPTANCE_REFUSED_PICTURE),
                ({"decision": "APPROVED"}, ch.ACCEPTANCE_REFUSED_DECISION)):
            with self.assertRaises(ch.ChannelRefused) as refused:
                ch.record_acceptance(**{**good, **change})
            assert refused.exception.code == code and str(refused.exception).startswith(code + ": REFUSED"), change
        # the same refusals through the door, by name; another account and the anonymous never reach the channel
        assert self._accept(owner, slug, "").content.decode().startswith(ch.ACCEPTANCE_REFUSED_NO_SHA256)
        assert self._accept(owner, slug, "0" * 64).status_code == 409
        outsider = self._accept(self._client(other), slug, sha)
        assert outsider.status_code == 403 and "plain56" in outsider.content.decode()
        assert self._accept(self._client(), slug, sha).status_code == 302
        assert owner.get(f"/dashboard/history/tasks/{self.task.id}/accept/").status_code == 405
        # a stale spec is re-derived first (§BH54(d)): the saved verdict predates a check, so nothing of it is accepted
        self.output.refresh_from_db()
        spec = self.output.spec_sheet
        spec["container_production_readiness_codes"] = {
            k: v for k, v in spec["container_production_readiness_codes"].items() if k != "brand_strings"}
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        stale = self._accept(owner, slug, sha)
        assert stale.status_code == 409 and stale.content.decode().startswith(ch.ACCEPTANCE_REFUSED_SPEC_STALE)
        assert "SPEC_STALE_REDERIVE_REQUIRED" in stale.content.decode()
        assert OwnerAcceptance.objects.count() == 0                       # sixteen refusals, not one row
        # and the database itself holds the line: a row lacking the sha256 cannot exist
        with self.assertRaises(IntegrityError), transaction.atomic():
            OwnerAcceptance.objects.create(task=self.task, study=slug, picture="R001", decision="ACCEPTED",
                                           decided_by=self.user, decided_at=now, picture_sha256="",
                                           inputs_sha256=record["inputs_sha256"])

    def test_the_machine_writes_no_acceptance(self):
        """The governed path — confirmation, reconstruction, a Gate-2 approval attempt, a retry attempt, the render route —
        writes no act: the one writer is the owner's click on the loop page."""
        from apps.dashboard.models import OwnerAcceptance
        owner, slug, _record = self._rendered()
        owner.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": self.output.id},
                   content_type="application/json")
        owner.post(f"/api/tasks/{self.task.id}/confirm_container_profile/", {"profile": {}},
                   content_type="application/json")
        owner.post(self._url(), {"from_loop": "1", "translucency": "0.5"})
        assert OwnerAcceptance.objects.count() == 0

    def test_a_reference_asset_placed_in_an_exploration_is_refused_by_name_and_production_bytes_are_placed(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path

        from django.test import override_settings
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        concept = Path(self.selected.image_file.path)
        sha = hashlib.sha256(concept.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            for tier, expect in (("REFERENCE", 409), ("PRODUCTION", 302)):
                record = Path(tmp) / f"{tier.lower()}_tiers.jsonl"
                record.write_text(json.dumps({"relative_path": "materials/x.png", "tier": tier, "sha256": sha}) + "\n")
                with override_settings(HISTORY_TIER_RECORD=str(record)):
                    r = owner.post(self._url())
                assert r.status_code == expect, (tier, r.content[:300])
                if tier == "REFERENCE":
                    text = r.content.decode()
                    assert text.startswith("EXPLORATION_REFUSED_REFERENCE_ASSET: REFUSED")
                    assert concept.name in text and "tier REFERENCE by the tier record" in text
                    assert not self.store54.exists() or not any(self.store54.rglob("*.png"))   # refused before a byte
        assert len(list(self.store54.rglob("R*.png"))) == 1                                    # the PRODUCTION direction drew


class OwnerCopyTests(ExplorationRenderTests):
    """§BH54(b), the second block, (k) 4 — THE COPY CHANNEL: "I type the six pieces into the product from the loop page,
    each piece's room shown as I type, an over-room warning that informs rather than refuses, and the words landing as
    my act with the same three fields." The words in these tests are fixture words and say so: the executor writes no
    regulated copy, in a fixture either (§AE2(b))."""

    test_the_owner_renders_an_exploration_from_the_task_page_and_nothing_the_gate_reads_moves = None
    test_every_other_request_is_refused_by_name_and_draws_nothing = None

    WORDS = "fixture words typed by the owner of this test\nnever copy of any product"

    def _copy(self):
        return f"/dashboard/history/tasks/{self.task.id}/copy/"

    def _room(self):
        return f"/dashboard/history/tasks/{self.task.id}/copy-room/"

    def _sections(self):
        from apps.pipeline.targets.container import _back_sections_from_record
        sections, codes = _back_sections_from_record(self.task.product)
        return {s["heading"]: s["text"] for s in sections}, codes

    def test_the_owner_types_a_piece_and_it_lands_with_the_three_fields_and_the_governed_path_prints_it(self):
        from django.utils import timezone
        from django.utils.html import escape

        from apps.dashboard import owner_channel as ch
        from apps.dashboard.models import OwnerCopy
        from apps.pipeline.targets.container import CONTENT_VERIFICATION_REQUIRED
        self._declare_drawing_source(None)
        owner = self._client(self.user)
        sha = ch.words_sha256(self.WORDS)
        # the first step SHOWS him the words, their sha256 and their room, and writes nothing (a browser sends CRLF)
        shown = owner.post(self._copy(), {"copy_net_content": self.WORDS.replace("\n", "\r\n") + "  "})
        page = shown.content.decode()
        assert shown.status_code == 200 and "Read the words before they land" in page and sha in page
        assert "These are my words — save them" in page and OwnerCopy.objects.count() == 0
        # the second step — his click on that page — lands them with the three fields
        before = timezone.now()
        landed = owner.post(self._copy(), {"confirm": "1", "copy_net_content": self.WORDS, "sha256_net_content": sha})
        assert landed.status_code == 302 and landed["Location"].endswith("/loop/#words"), landed.content[:300]
        row = OwnerCopy.objects.get()
        assert row.typed_by == self.user and before <= row.typed_at <= timezone.now()          # identity, the time
        assert row.text_sha256 == sha and row.text == self.WORDS                              # the sha256 of exactly those
        assert (row.product_id, row.piece) == (self.task.product_id, "NET CONTENT")
        # the governed path prints the piece through the channel — and only that piece
        texts, codes = self._sections()                                 # a typed line break is handed over as a space
        assert texts["NET CONTENT"] == " ".join(self.WORDS.split()) and len(codes) == 5
        assert "CONTENT_VERIFICATION_REQUIRED:net_content" not in codes
        assert {texts[p] for p in OwnerCopy.PIECES if p != "NET CONTENT"} == {CONTENT_VERIFICATION_REQUIRED}
        assert self._confirm().status_code == 200                       # the governed reconstruction reads it too
        spec = self.output.spec_sheet
        assert len(spec["container_back_content_codes"]) == 5
        assert "CONTENT_VERIFICATION_REQUIRED:net_content" not in spec["container_back_content_codes"]
        loop = owner.get(f"/dashboard/history/tasks/{self.task.id}/loop/").content.decode()
        assert "Your words in this product" in loop and sha in loop and escape(ch.COPY_VERIFIED) in loop
        assert 'data-room-url="' + self._room() + '"' in loop and "js/loop.js" in loop and 'id="room-total"' in loop
        # a second act is a second row, and the newest is the product's copy
        newer = self.WORDS + "\na later line"
        assert owner.post(self._copy(), {"confirm": "1", "copy_net_content": newer,
                                         "sha256_net_content": ch.words_sha256(newer)}).status_code == 302
        assert OwnerCopy.objects.count() == 2 and self._sections()[0]["NET CONTENT"] == " ".join(newer.split())
        # re-verified on every read: stored words that are not the words the act names read VOID and are NOT copy
        OwnerCopy.objects.filter(text=newer).update(text="words nobody typed")
        assert ch.copy_for(self.task.product)["NET CONTENT"]["verification"] == ch.COPY_VOID
        assert ch.written_copy(self.task.product) == {}
        texts, codes = self._sections()
        assert texts["NET CONTENT"] == CONTENT_VERIFICATION_REQUIRED and len(codes) == 6
        assert escape(ch.COPY_VOID) in owner.get(f"/dashboard/history/tasks/{self.task.id}/loop/").content.decode()

    def test_copy_lacking_any_of_the_three_fields_is_refused_by_name_and_nothing_is_written(self):
        import datetime

        from django.contrib.auth.models import AnonymousUser
        from django.db import IntegrityError, transaction
        from django.utils import timezone

        from apps.dashboard import owner_channel as ch
        from apps.dashboard.models import OwnerCopy
        owner, now, sha = self._client(self.user), timezone.now(), ch.words_sha256(self.WORDS)
        other = User.objects.create_user("plain57", password="x")
        good = dict(user=self.user, typed_at=now, product=self.task.product, piece="NET CONTENT", text=self.WORDS,
                    text_sha256=sha)
        for change, code in (
                ({"user": None}, ch.COPY_REFUSED_NO_IDENTITY),
                ({"user": AnonymousUser()}, ch.COPY_REFUSED_NO_IDENTITY),
                ({"user": other}, ch.COPY_REFUSED_NOT_THE_OWNER),
                ({"typed_at": None}, ch.COPY_REFUSED_NO_TIME),
                ({"typed_at": datetime.datetime(2026, 9, 19, 1, 0)}, ch.COPY_REFUSED_NO_TIME),      # no zone: not a time
                ({"text_sha256": ""}, ch.COPY_REFUSED_NO_SHA256),
                ({"text_sha256": "abc"}, ch.COPY_REFUSED_NO_SHA256),
                ({"text_sha256": "0" * 64}, ch.COPY_REFUSED_NOT_THESE_WORDS),
                ({"product": None}, ch.COPY_REFUSED_NO_PRODUCT),
                ({"piece": "PRODUCT"}, ch.COPY_REFUSED_NOT_A_PIECE),
                ({"text": "  "}, ch.COPY_REFUSED_NO_WORDS)):
            with self.assertRaises(ch.ChannelRefused) as refused:
                ch.record_copy(**{**good, **change})
            assert refused.exception.code == code and str(refused.exception).startswith(code + ": REFUSED"), change
            assert str(refused.exception).endswith("(§BH54(b) (k) 4)")
        # the same refusals at the door, by name
        no_sha = owner.post(self._copy(), {"confirm": "1", "copy_net_content": self.WORDS})
        assert no_sha.status_code == 409 and no_sha.content.decode().startswith(ch.COPY_REFUSED_NO_SHA256)
        wrong = owner.post(self._copy(), {"confirm": "1", "copy_net_content": self.WORDS, "sha256_net_content": "0" * 64})
        assert wrong.status_code == 409 and wrong.content.decode().startswith(ch.COPY_REFUSED_NOT_THESE_WORDS)
        # all the pieces of one click land together or none does
        half = owner.post(self._copy(), {"confirm": "1", "copy_net_content": self.WORDS, "sha256_net_content": sha,
                                         "copy_warnings": self.WORDS, "sha256_warnings": "0" * 64})
        assert half.status_code == 409 and OwnerCopy.objects.count() == 0
        assert owner.post(self._copy(), {"confirm": "1"}).content.decode().startswith(ch.COPY_REFUSED_NO_WORDS)
        outsider = self._client(other).post(self._copy(), {"confirm": "1", "copy_net_content": self.WORDS,
                                                           "sha256_net_content": sha})
        assert outsider.status_code == 403 and "plain57" in outsider.content.decode()
        assert self._client(other).post(self._room(), {}).status_code == 403
        assert self._client().post(self._copy(), {"confirm": "1"}).status_code == 302          # the anonymous: the login
        assert owner.get(self._copy()).status_code == 405 and owner.get(self._room()).status_code == 405
        assert OwnerCopy.objects.count() == 0                            # twenty refusals, not one row
        with self.assertRaises(IntegrityError), transaction.atomic():     # and the database itself holds the line
            OwnerCopy.objects.create(product=self.task.product, piece="NET CONTENT", text=self.WORDS,
                                     typed_by=self.user, typed_at=now, text_sha256="")

    def test_each_pieces_room_is_measured_and_an_over_room_piece_is_warned_of_and_saved_all_the_same(self):
        from apps.dashboard import owner_channel as ch
        from apps.dashboard.models import OwnerCopy
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        rows = _rows54()
        standing = owner.post(self._room(), {}).json()
        assert set(standing["pieces"]) == set(OwnerCopy.PIECES)
        assert {p["state"] for p in standing["pieces"].values()} == {"unwritten"} and "All seven sections need" in standing["total_line"]
        tall = {"back_height": "110"}                                    # the zone as typed in the form: room is re-measured
        short = owner.post(self._room(), {"copy_net_content": "fixture words", **tall}).json()
        piece = short["pieces"]["NET CONTENT"]
        assert short["fits"] is True and (piece["state"], piece["copy_lines"], piece["over"]) == ("typed", 1, False)
        assert piece["room_lines"] > standing["pieces"]["NET CONTENT"]["room_lines"] and short["zone"]["height"] == 110.0
        many = " ".join(["fixture"] * 900)                               # far more words than a 110 mm zone holds
        long = owner.post(self._room(), {"copy_net_content": many, **tall}).json()
        piece = long["pieces"]["NET CONTENT"]
        assert long["fits"] is False and piece["over"] and piece["copy_lines"] > piece["room_lines"] > 0
        assert piece["line"].startswith("OVER ITS ROOM") and "saved all the same" in piece["line"] and long["overflow_mm"] > 0
        bad = owner.post(self._room(), {"back_height": "tall"})
        assert bad.status_code == 409 and bad.content.decode().startswith("EXPLORATION_KNOB_REFUSED")
        assert _rows54() == rows and not any(self.store54.rglob("*"))    # measuring wrote nothing, anywhere
        # over its room a piece is WARNED of and saved all the same — every character of it, none cut
        shown = owner.post(self._copy(), {"copy_net_content": many}).content.decode()
        assert "OVER ITS ROOM" in shown and "These are my words — save them" in shown
        saved = owner.post(self._copy(), {"confirm": "1", "copy_net_content": many,
                                          "sha256_net_content": ch.words_sha256(many)})
        assert saved.status_code == 302 and OwnerCopy.objects.get().text == many and len(many) > 6000

    def test_the_machine_writes_no_copy_and_a_draft_is_never_copy(self):
        from apps.dashboard.models import OwnerCopy
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        drawn = owner.post(self._url(), {"from_loop": "1", "copy_net_content": "draft fixture words"})
        assert drawn.status_code == 302                                   # a DRAFT is drawn in an exploration …
        assert OwnerCopy.objects.count() == 0 and len(self._sections()[1]) == 6      # … and is never the product's copy
        # a draft is never CUT either: over the limit it is refused by name, where it was silently truncated before
        cut = owner.post(self._url(), {"from_loop": "1", "copy_description": "x" * 6001})
        text = cut.content.decode()
        assert cut.status_code == 409 and text.startswith("EXPLORATION_KNOB_REFUSED") and "6001 characters" in text


class DesignAcceptanceTests(Confirmation2C2EFixture):
    """§BH55 PHASE 1 — HIS ACCEPTANCE OF A GOVERNED DESIGN. Nothing in the product wrote the container acceptance a Complete
    Product project waits for (`container_human_visual_acceptance`: one reader, no writer outside tests), so no project
    could reach its packaging stage. This is the door: his act alone, his identity, the time, and the sha256 of the exact
    preview he looked at — re-hashed from its bytes before anything is written, and re-verified on every read."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.test import override_settings
        cls._override58 = override_settings(OWNER_ACCOUNT="confop")      # "confop" is the owner here
        cls._override58.enable()

    @classmethod
    def tearDownClass(cls):
        cls._override58.disable()
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self._declare_drawing_source(None)             # the product path (§BH49(a))

    def _client(self, user=None):
        from django.test import Client
        client = Client(HTTP_HOST="127.0.0.1")
        if user is not None:
            client.force_login(user)
        return client

    def _decide(self, client, sha, decision="ACCEPTED", **more):
        return client.post(f"/dashboard/history/tasks/{self.task.id}/accept-design/",
                           {"output_id": self.output.id, "preview_sha256": sha, "decision": decision, **more})

    def _preview_sha(self):
        import hashlib
        self.output.refresh_from_db()
        with self.output.design_preview.open("rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()

    def test_the_owner_accepts_the_design_with_the_three_fields_and_the_project_reads_it(self):
        from django.utils import timezone

        from apps.dashboard import owner_channel as ch
        from apps.dashboard.models import DesignAcceptance
        from apps.ire.container_production_readiness import ACCEPTANCE_KEY, human_design_acceptance
        from apps.pipeline.targets.composite import stage_human_acceptance
        assert self._confirm().status_code == 200 and self.task.status == "awaiting_gate_2"
        owner = self._client(self.user)
        sha = self._preview_sha()
        # the panel is told the preview's sha256, computed from its bytes, and that the viewer is the owner
        payload = owner.get(f"/api/tasks/{self.task.id}/status/").json()["design_acceptance"]
        assert (payload["preview_sha256"], payload["viewer_is_owner"], payload["at_its_gate"]) == (sha, True, True)
        assert payload["output_id"] == self.output.id and payload["acts"] == []
        before = timezone.now()
        r = self._decide(owner, sha, note="fixture note")
        assert r.status_code == 200, r.content[:300]
        body = r.json()
        assert body["decision"] == "ACCEPTED" and body["preview_sha256"] == sha and "recorded" in body["next"]
        act = DesignAcceptance.objects.get()
        assert act.decided_by == self.user and before <= act.decided_at <= timezone.now()
        assert (act.preview_sha256, act.output_id, act.task_id) == (sha, self.output.id, self.task.id)
        self.output.refresh_from_db()
        record = self.output.spec_sheet[ACCEPTANCE_KEY]
        assert (record["state"], record["decided_by"], record["preview_sha256"], record["act_id"]) == \
            ("ACCEPTED", "confop", sha, act.pk)
        assert human_design_acceptance(self.output.spec_sheet)["state"] == "ACCEPTED"
        assert stage_human_acceptance(self.task)["state"] == "ACCEPTED"             # what the project waits for
        # a second act is a second row, and his last word stands: REJECTED reads as rejected
        assert self._decide(owner, sha, decision="REJECTED").status_code == 200
        assert [a.decision for a in DesignAcceptance.objects.order_by("pk")] == ["ACCEPTED", "REJECTED"]
        self.output.refresh_from_db()
        assert human_design_acceptance(self.output.spec_sheet)["state"].startswith("REJECTED")
        assert stage_human_acceptance(self.task)["state"] != "ACCEPTED"
        # re-verified on every read: an accepted design whose preview bytes change reads VOID and advances nothing
        assert self._decide(owner, sha).status_code == 200
        assert stage_human_acceptance(self.task)["state"] == "ACCEPTED"
        self.output.refresh_from_db()                   # the door wrote the record; save over the fresh one
        self.output.design_preview.save("changed.png", ContentFile(b"\x89PNG\r\n\x1a\nnot the same picture"), save=True)
        assert stage_human_acceptance(self.task)["state"] == "VOID"
        assert {a["verification"] for a in ch.design_acts_for(self.task)} == {ch.DESIGN_VOID_DRIFT}

    def test_an_act_lacking_any_field_is_refused_by_name_and_nothing_is_written(self):
        import datetime

        from django.contrib.auth.models import AnonymousUser
        from django.utils import timezone

        from apps.dashboard import owner_channel as ch
        from apps.dashboard.models import DesignAcceptance
        from apps.ire.container_production_readiness import ACCEPTANCE_KEY
        assert self._confirm().status_code == 200
        owner, sha, now = self._client(self.user), self._preview_sha(), timezone.now()
        other = User.objects.create_user("plain58", password="x")
        good = dict(user=self.user, decided_at=now, task=self.task, output=self.output, preview_sha256_given=sha,
                    decision="ACCEPTED")
        for change, code in (
                ({"user": None}, ch.DESIGN_REFUSED_NO_IDENTITY),
                ({"user": AnonymousUser()}, ch.DESIGN_REFUSED_NO_IDENTITY),
                ({"user": other}, ch.DESIGN_REFUSED_NOT_THE_OWNER),
                ({"decided_at": None}, ch.DESIGN_REFUSED_NO_TIME),
                ({"decided_at": datetime.datetime(2026, 9, 19, 1, 0)}, ch.DESIGN_REFUSED_NO_TIME),
                ({"preview_sha256_given": ""}, ch.DESIGN_REFUSED_NO_SHA256),
                ({"preview_sha256_given": "abc"}, ch.DESIGN_REFUSED_NO_SHA256),
                ({"decision": "APPROVED"}, ch.DESIGN_REFUSED_DECISION),
                ({"output": None}, ch.DESIGN_REFUSED_NO_DESIGN),
                ({"preview_sha256_given": "0" * 64}, ch.DESIGN_REFUSED_NOT_THESE_BYTES)):
            with self.assertRaises(ch.ChannelRefused) as refused:
                ch.record_design_acceptance(**{**good, **change})
            assert refused.exception.code == code and str(refused.exception).endswith("(§BH55 Phase 1)"), change
        # at the door, by name; another account and the anonymous never reach the channel; the door takes no GET
        assert self._decide(owner, "0" * 64).content.decode().startswith(ch.DESIGN_REFUSED_NOT_THESE_BYTES)
        assert owner.post(f"/dashboard/history/tasks/{self.task.id}/accept-design/",
                          {"preview_sha256": sha, "decision": "ACCEPTED"}).content.decode() \
            .startswith(ch.DESIGN_REFUSED_NO_DESIGN)                         # no output named
        outsider = self._decide(self._client(other), sha)
        assert outsider.status_code == 403 and "plain58" in outsider.content.decode()
        assert self._decide(self._client(), sha).status_code == 302
        assert owner.get(f"/dashboard/history/tasks/{self.task.id}/accept-design/").status_code == 405
        # a design not at its gate is not accepted; a stale spec is re-derived first
        DesignTask.objects.filter(pk=self.task.pk).update(status="completed")
        self.task.refresh_from_db()
        with self.assertRaises(ch.ChannelRefused) as refused:
            ch.record_design_acceptance(**{**good, "task": self.task})
        assert refused.exception.code == ch.DESIGN_REFUSED_NOT_AT_ITS_GATE
        DesignTask.objects.filter(pk=self.task.pk).update(status="awaiting_gate_2")
        self.task.refresh_from_db()
        spec = self.output.spec_sheet
        spec["container_production_readiness_codes"] = {
            k: v for k, v in spec["container_production_readiness_codes"].items() if k != "brand_strings"}
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])
        with self.assertRaises(ch.ChannelRefused) as refused:
            ch.record_design_acceptance(**{**good, "task": self.task, "output": self.output})
        assert refused.exception.code == ch.DESIGN_REFUSED_SPEC_STALE
        assert DesignAcceptance.objects.count() == 0                         # every refusal, not one row
        self.output.refresh_from_db()
        assert ACCEPTANCE_KEY not in self.output.spec_sheet

    def test_the_machine_writes_no_acceptance_and_another_viewer_is_offered_no_control(self):
        from apps.dashboard.models import DesignAcceptance
        from apps.ire.container_production_readiness import ACCEPTANCE_KEY
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        owner.post(f"/api/tasks/{self.task.id}/gate2_approve/", {"packaging_output_id": self.output.id},
                   content_type="application/json")
        owner.post(f"/api/tasks/{self.task.id}/confirm_container_profile/", {"profile": {}},
                   content_type="application/json")
        assert DesignAcceptance.objects.count() == 0
        self.output.refresh_from_db()
        assert ACCEPTANCE_KEY not in self.output.spec_sheet
        other = User.objects.create_user("plain59", password="x")
        from django.contrib.auth.models import Group

        from apps.pipeline.permissions import ROLE_REVIEWER
        other.groups.add(Group.objects.get_or_create(name=ROLE_REVIEWER)[0])
        payload = self._client(other).get(f"/api/tasks/{self.task.id}/status/").json()["design_acceptance"]
        assert payload["viewer_is_owner"] is False and payload["preview_sha256"] == self._preview_sha()


class ZoneProfileDivergenceTests(Confirmation2C2EFixture):
    """§BH64(b) — ONE SOURCE FOR THE NUMBERS, AND A REFUSAL BY NAME.

    The defect these pin was measured on task 89 and is general: a
    confirmation that EDITS A DIMENSION is refused, and the refusal branch
    persisted the edited profile beside the zones proposed from the profile it
    replaced. The stored record then contradicted itself — a compact at
    80 x 80 mm carrying a 139.8 x 95.5 mm zone on its lid — and the screen
    could never be confirmed again, because the 409 hands the same stranded
    zones back and ``confirm_profile.js:1271`` re-posts them. It needed no
    mismatched product row; any edit that shrinks a surface did it.

    The repair is not that the refusal branch stops writing — §13 wants it to
    write, so the Review Board can show which zone failed. It is that a
    profile and a zone set are only ever written as a PAIR THAT WAS DERIVED
    TOGETHER, and the block says which profile its numbers are about.
    """

    #: every surface smaller than the fixture's, inside the editor ranges
    SMALLER = dict(PROFILE_PAYLOAD, width_mm=20, height_mm=40, depth_mm=10,
                   neck_ratio=0.3, cap_width_mm=18, cap_height_mm=8)

    def _post(self, payload):
        from django.test import Client
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(self.user)
        r = client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            payload, content_type="application/json")
        self.task.refresh_from_db()
        self.output.refresh_from_db()
        return r

    def _fits(self, zones, record):
        return not [p for p in cc.validate_zone_set(zones, record)
                    if p.startswith(cc.ZONE_OUT_OF_BOUNDS)]

    def test_the_pipelines_own_proposal_says_which_profile_it_came_from(self):
        spec = self.output.spec_sheet
        block, record = spec[cc.ZONES_SCHEMA], spec[cc.PROFILE_SCHEMA]
        assert block["profile_hash"] == cc.profile_hash(record)
        assert cc.zone_set_belongs_to(block, record)
        assert self._fits(block["zones"], record)

    def test_a_refusal_never_stores_a_zone_that_does_not_fit_its_own_surface(self):
        import copy
        spec = self.output.spec_sheet
        standing = spec[cc.ZONES_SCHEMA]["zones"]
        # PRECONDITION, so this cannot pass without exercising the defect:
        # the standing proposal genuinely does not fit the smaller body.
        shrunk = cc.merge_user_profile(
            copy.deepcopy(spec[cc.PROFILE_SCHEMA]),
            {"body_width_mm": 20.0, "body_height_mm": 40.0,
             "body_depth_mm": 10.0})
        assert not self._fits(standing, shrunk)

        r = self._post({"profile": self.SMALLER})
        assert r.status_code == 409, r.content
        after = self.output.spec_sheet
        stored_record, stored_block = (after[cc.PROFILE_SCHEMA],
                                       after[cc.ZONES_SCHEMA])
        # the pair that WAS written was derived together, and fits
        assert cc.zone_set_belongs_to(stored_block, stored_record)
        assert self._fits(stored_block["zones"], stored_record)
        # and the substitution was announced — nothing changes unannounced
        told = r.json()["zone_set_rederived"]
        assert told["reason"] == cc.ZONE_PROFILE_DIVERGED
        assert told["now_derived_from"] == cc.profile_hash(stored_record)
        assert told["was_derived_from"] != told["now_derived_from"]

    def test_an_unstamped_legacy_block_announces_its_substitution_too(self):
        """FOUND ON THE LIVE RUN by the §AD0(a) leg written to find it (L8), and the fixture could not
        have caught it: every block this fixture writes is stamped by `zone_set_record`, so the only
        unstamped blocks in existence are the ones that predate §BH64(b) — which is what the §BH60 clone
        run's output 69 was.

        The notice was guarded on `rederived_from is not None`. An unstamped block's `profile_hash` is
        None, so the guard silenced the announcement for exactly the blocks that cannot say which profile
        they came from. Output 69 was re-derived correctly and told nobody, which is the half of §BH64(b)
        that is not "one source for the numbers": nothing changes under the owner unannounced.
        """
        spec = self.output.spec_sheet
        block = dict(spec[cc.ZONES_SCHEMA])
        block.pop("profile_hash")                    # a block as it was written before §BH64(b)
        spec[cc.ZONES_SCHEMA] = block
        self.output.spec_sheet = spec
        self.output.save(update_fields=["spec_sheet"])

        r = self._post({"profile": self.SMALLER})
        assert r.status_code == 409, r.content
        told = r.json()["zone_set_rederived"]
        assert told["was_derived_from"] == cc.ZONE_SET_UNSTAMPED
        assert told["reason"] == cc.ZONE_PROFILE_DIVERGED
        assert told["detail"], "the substitution names the zones it replaced"
        after = self.output.spec_sheet
        assert cc.zone_set_belongs_to(after[cc.ZONES_SCHEMA], after[cc.PROFILE_SCHEMA])
        assert self._fits(after[cc.ZONES_SCHEMA]["zones"], after[cc.PROFILE_SCHEMA])

    def test_confirmed_zones_from_another_profile_are_refused_by_name(self):
        spec = self.output.spec_sheet
        stale = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED)
                 for z in spec[cc.ZONES_SCHEMA]["zones"]]
        was_profile = cc.profile_hash(spec[cc.PROFILE_SCHEMA])
        was_zones = spec[cc.ZONES_SCHEMA]["zone_set_hash"]

        r = self._post({"profile": self.SMALLER, "zones": stale})
        assert r.status_code == 409, r.content
        body = r.json()
        assert body["error"] == cc.ZONE_PROFILE_DIVERGED, body
        assert body["zone_set_profile_hash"] == was_profile
        # NOTHING was written: two human acts disagree and the machine does
        # not pick between them.
        after = self.output.spec_sheet
        assert cc.profile_hash(after[cc.PROFILE_SCHEMA]) == was_profile
        assert after[cc.ZONES_SCHEMA]["zone_set_hash"] == was_zones

        # AND THERE IS A WAY OUT: the refusal carries a proposal that fits, and
        # confirming that instead is no longer this refusal. One zone is left
        # unconfirmed so the assertion stops here rather than reconstructing.
        fresh = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED)
                 for z in body["zones"]]
        fresh[-1]["user_confirmation_state"] = cc.ZONE_PROPOSED
        r2 = self._post({"profile": self.SMALLER, "zones": fresh})
        assert r2.json()["error"] == cc.ZONE_CONFIRMATION_REQUIRED, r2.json()

    #: every body surface LARGER than the fixture's — whose record holds no size, its zones proposed from the
    #: contract's fallback 100 x 50, exactly as design 117's were — so the standing proposal still fits inside it
    LARGER = dict(PROFILE_PAYLOAD, width_mm=60, height_mm=140, depth_mm=60)

    def test_finding2_areas_proposed_for_other_sizes_are_refused_by_name_even_when_they_still_fit(self):
        """His test day finding 2 (2026-09-29, design 117): his tube set to 180 x 50 mm kept the 35 x 55 mm front
        proposed from the fallback 100 x 50 — it still fit, so the door let it through, and his whole front would
        have been drawn into the tube's upper part. A set proposed for other sizes is now refused by name whether or
        not it fits, in words, with this size's own proposal; nothing is written; confirming that proposal passes."""
        import copy
        spec = self.output.spec_sheet
        standing = spec[cc.ZONES_SCHEMA]["zones"]
        # the record the door builds from LARGER — every value the view promotes from that payload
        larger = cc.merge_user_profile(copy.deepcopy(spec[cc.PROFILE_SCHEMA]), {
            "archetype": "bottle", "variant": "cylindrical", "body_width_mm": 60.0, "body_depth_mm": 60.0,
            "body_height_mm": 140.0, "neck_ratio": 10 / 33, "cap_type": "dropper", "cap_width_mm": 28.0,
            "cap_height_mm": 14.0})
        # PRECONDITION, so this cannot pass without the defect's shape: the standing set still FITS the larger
        # body, and it is not the larger body's proposal
        assert self._fits(standing, larger)
        proposal = cc.augment_code_zones(larger, cc.propose_zones(larger))
        assert ({z["zone_id"]: (z["width"], z["height"]) for z in standing}
                != {z["zone_id"]: (z["width"], z["height"]) for z in proposal})
        was_profile = cc.profile_hash(spec[cc.PROFILE_SCHEMA])
        was_zones = spec[cc.ZONES_SCHEMA]["zone_set_hash"]

        stale = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED) for z in standing]
        r = self._post({"profile": self.LARGER, "zones": stale})
        assert r.status_code == 409, r.content
        body = r.json()
        assert body["error"] == cc.ZONE_PROFILE_DIVERGED, body
        assert any(d.startswith(cc.ZONE_PROPOSED_FOR_OTHER_SIZES) for d in body["detail"]), body["detail"]
        assert body["reason"].startswith("These print areas were worked out for other sizes"), body
        assert ({z["zone_id"]: (z["width"], z["height"]) for z in body["zones"]}
                == {z["zone_id"]: (z["width"], z["height"]) for z in proposal})
        after = self.output.spec_sheet                                     # nothing written
        assert cc.profile_hash(after[cc.PROFILE_SCHEMA]) == was_profile
        assert after[cc.ZONES_SCHEMA]["zone_set_hash"] == was_zones

        fresh = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED) for z in body["zones"]]
        fresh[-1]["user_confirmation_state"] = cc.ZONE_PROPOSED            # stop before reconstructing
        r2 = self._post({"profile": self.LARGER, "zones": fresh})
        assert r2.json()["error"] == cc.ZONE_CONFIRMATION_REQUIRED, r2.json()

    def test_finding2_the_step_is_given_the_areas_for_the_sizes_it_shows_and_nothing_is_written(self):
        """His test day finding 2 (2026-09-29, design 117): the shape step asks the server for the print areas of the
        sizes it shows. The answer is the proposal for the very record the door would confirm; nothing is written;
        confirming it passes the door; a size out of range, or a design not at its shape step, is refused by name."""
        import copy

        from django.test import Client

        from apps.pipeline import views as pv
        spec = copy.deepcopy(self.output.spec_sheet)
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(self.user)
        url = f"/api/tasks/{self.task.id}/propose_container_zones/"
        r = client.post(url, {"profile": self.LARGER}, content_type="application/json")
        assert r.status_code == 200, r.content
        body = r.json()
        record = pv._container_profile_record(self.task, spec, "bottle", self.LARGER,
                                              pv._clean_container_profile(self.LARGER, "bottle"))
        want = cc.augment_code_zones(record, cc.propose_zones(record))
        assert ({z["zone_id"]: (z["x"], z["y"], z["width"], z["height"]) for z in body["zones"]}
                == {z["zone_id"]: (z["x"], z["y"], z["width"], z["height"]) for z in want})
        assert body["profile_hash"] == record["profile_hash"] and all(z["zone_hash"] for z in body["zones"])
        self.output.refresh_from_db()
        self.task.refresh_from_db()
        assert self.output.spec_sheet == spec and self.task.status == "awaiting_container_profile"

        fresh = [dict(z, user_confirmation_state=cc.ZONE_USER_CONFIRMED) for z in body["zones"]]
        fresh[-1]["user_confirmation_state"] = cc.ZONE_PROPOSED            # stop before reconstructing
        assert self._post({"profile": self.LARGER, "zones": fresh}).json()["error"] == cc.ZONE_CONFIRMATION_REQUIRED

        bad = client.post(url, {"profile": dict(self.LARGER, height_mm=9999)}, content_type="application/json")
        assert bad.status_code == 400 and bad.json()["error"] == "PROFILE_VALIDATION_FAILED", bad.content
        self.task.status = "awaiting_gate_2"
        self.task.save(update_fields=["status"])
        late = client.post(url, {"profile": self.LARGER}, content_type="application/json")
        assert late.status_code == 409 and late.json()["error"] == "PROPOSAL_NOT_AT_THE_SHAPE_STEP", late.content

    def test_a_change_that_moves_no_surface_does_not_strand_its_zones(self):
        """The refusal is gated on the zones no longer FITTING, not on the
        profile hash moving. ``profile_hash`` covers colour notes, materials
        and every other field; refusing on drift alone would refuse every
        edit that touched none of the surfaces."""
        import copy
        spec = self.output.spec_sheet
        record, block = spec[cc.PROFILE_SCHEMA], spec[cc.ZONES_SCHEMA]
        zones = block["zones"]
        assert cc.zone_profile_divergence(block, zones, record) == []

        moved = copy.deepcopy(record)
        moved["fields"]["body_material"] = {
            "value": "glass", "source": cc.SRC_USER_FACT,
            "verification": cc.VERIFIED}
        assert cc.profile_hash(moved) != cc.profile_hash(record)
        assert not cc.zone_set_belongs_to(block, moved)
        assert cc.zone_profile_divergence(block, zones, moved) == []

    def test_source_guard_the_zone_block_is_built_in_exactly_one_place(self):
        """SOURCE-STRING GUARD (§Y2(b)) — §BH64(b)'s ONE SOURCE, enforced.

        A zone set's coordinates mean nothing except against one profile's
        surfaces, so the block that carries them is built by
        ``container_contract.zone_set_record`` and nowhere else: it is what
        stamps the profile the numbers were derived from, and a second
        constructor could write the pair apart again exactly as the three
        removed sites did. A zone block is recognisable in source by the one
        thing every one of them has — ``"schema_version"`` paired with
        ``ZONES_SCHEMA`` — and after this commit production holds exactly one
        such line. Tests may still fabricate a block; a fixture that writes an
        unstamped one is how the legacy path stays covered.
        """
        import pathlib
        import re
        apps = pathlib.Path(__file__).resolve().parents[2]
        builders = []
        for path in sorted(apps.rglob("*.py")):
            rel = str(path.relative_to(apps.parent))
            if "/tests/" in rel:
                continue
            for n, line in enumerate(
                    path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r'"schema_version":\s*(cc\.)?ZONES_SCHEMA', line):
                    builders.append(f"{rel}:{n}")
        assert len(builders) == 1, "\n".join(builders)
        assert builders[0].startswith(
            "apps/pipeline/services/container_contract.py:"), builders


class DropperKeepsItsOwnColoursTests(ExplorationRenderTests):
    """[The owner's pick of 2026-09-25 — the design page is C's: "pick an element and try colours and faces from a
    library that stays open".] Colours and faces are tried on a lid's FACE. The bottle sheet draws its own fixed colours
    and faces today (its palette kept as ruled at §BH50(f)(9)), so on the dropper those two knobs are refused by name
    and draw nothing; every knob the bottle had draws as it did."""

    test_the_owner_renders_an_exploration_from_the_task_page_and_nothing_the_gate_reads_moves = None
    test_every_other_request_is_refused_by_name_and_draws_nothing = None

    def test_a_colour_or_a_face_on_the_bottle_is_refused_by_name_and_its_own_knobs_still_draw(self):
        from apps.dashboard import exploration_render as ER
        self._declare_drawing_source(None)
        assert self._confirm().status_code == 200
        owner = self._client(self.user)
        for field, value in (("colour_name", "#8B3A52"), ("face_name", "Poppins-Bold")):
            r = owner.post(self._url(), {field: value})
            text = r.content.decode()
            assert r.status_code == 409 and text.startswith(ER.KNOBS_FOR_A_FACE_ONLY + ": REFUSED"), text[:300]
        offer = ER.knob_offer(self.task)
        assert (offer["form"], offer["refused"], offer["elements"], offer["faces"]) == (
            "dropper", ER.KNOBS_FOR_A_FACE_ONLY, [], [])
        assert not self.store54.exists() or not any(self.store54.rglob("*"))
        assert owner.post(self._url(), {"translucency": "0.5"}).status_code == 302


from .test_wif_reconstruct_container import FaceFormCase  # noqa: E402 — a base with no tests of its own


class FaceFormExplorationTests(FaceFormCase):
    """[The owner's goal of 2026-09-25, "THE UI, DESIGNED THIS TIME", rule (d): "The library is usable WHILE designing,
    not a separate trip." His pick: the design page is C's — "pick an element and try colours and faces from a library
    that stays open".] The loop draws a confirmed lid's FACE from production's own inputs, the concept's reading taken
    from the design's record and never paid for; a colour is tried from the brand's palette and a face from the
    granted catalogue, each named in the picture's record, and anything outside is refused by name (§BH51's hard stop:
    "a face or colour outside the governed sets reaching a render"). Nothing the gate reads is written: no row, no
    media byte, no provider call, no change to the design's record (§BH54(j): "the product keeps today's colours")."""

    PALETTE = (
        ("Blush Core", "CS-001", [
            {"role": "Primary", "name": "Blush", "hex": "#F2C4CE", "usage": "Main surfaces, hero cartons"},
            {"role": "Secondary", "name": "Pale Petal", "hex": "#F7DDE3", "usage": "Interior, secondary panels"},
            {"role": "Accent", "name": "Deep Rose", "hex": "#8B3A52", "usage": "Typography, fine detail lines"},
            {"role": "Metallic", "name": "Rose Gold", "hex": "Metallic 10122 C", "usage": "Caps, closures, foil detail"},
            {"role": "Ground", "name": "Warm Cream", "hex": "#FAF3EC", "usage": "Base packaging, backgrounds"},
            {"role": "Ground", "name": "Warm Gold", "hex": "#CBA87D",
             "usage": "Warm gold ground panels, gold fields behind type"}]),
        ("Nude Warm", "CS-002", [
            {"role": "Primary", "name": "Warm Nude", "hex": "#E8C9B3", "usage": "Main surfaces, warm hero packaging"},
            {"role": "Secondary", "name": "Soft Sand", "hex": "#F0DECB", "usage": "Secondary panels, interiors"},
            {"role": "Accent", "name": "Cocoa Rose", "hex": "#7A4A42", "usage": "Typography, fine detail lines"}]),
    )

    def setUp(self):
        super().setUp()
        import tempfile
        from pathlib import Path

        from django.test import override_settings

        from apps.core.models import STATUS_CANONICAL, ColorSystem
        self._tmpf = tempfile.TemporaryDirectory()
        self.store = Path(self._tmpf.name) / "explorations"
        self._overridef = override_settings(EXPLORATION_STORE=str(self.store), OWNER_ACCOUNT="faceowner")
        self._overridef.enable()
        self.owner = User.objects.create_user("faceowner", password="x")
        for name, system_id, palette in self.PALETTE:
            ColorSystem.objects.create(brand=self.brand, name=name, system_id=system_id, status=STATUS_CANONICAL,
                                       palette=palette)
        # [his goal of 2026-10-12, (6): "a finish plate ... is made only when my brief or the concept shows it"] the
        # brief asks for the foil its concept prints the wordmark and the hairline rule in, so the rule stays in foil
        self.task.task_text = "a pressed powder compact; Rose Gold hot-foil on the BBROSE wordmark and the hairline rule"
        self.task.save(update_fields=["task_text"])
        _aria, self.out = self._face()
        spec = self.out.spec_sheet                        # confirmed at the gate, as the confirmation view writes it
        spec["container_profile/1.0"]["confirmation_state"] = "CONFIRMED"
        spec["container_confirmation"] = {"combined_hash": "0" * 32, "confirmed_at": "2026-09-25T00:00:00+00:00",
                                          "confirmed_by": "faceowner", "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY"}
        self.out.spec_sheet = spec
        self.out.save(update_fields=["spec_sheet"])

    def tearDown(self):
        self._overridef.disable()
        self._tmpf.cleanup()
        super().tearDown()

    def _owner(self):
        from django.test import Client
        client = Client(HTTP_HOST="127.0.0.1")
        client.force_login(self.owner)
        return client

    def _url(self):
        return f"/dashboard/history/tasks/{self.task.id}/explore/"

    @staticmethod
    def _media():
        from pathlib import Path

        from django.conf import settings
        return sorted(str(p) for p in Path(settings.MEDIA_ROOT).rglob("*"))

    def test_a_lids_face_draws_from_its_record_and_nothing_the_gate_reads_moves(self):
        import hashlib
        import json
        from unittest.mock import patch

        from django.core.files.storage import FileSystemStorage

        from apps.dashboard import exploration_render as ER
        from apps.dashboard import explorations
        from apps.core import tests as core_tests                 # the seam's own list of governed files
        owner = self._owner()                                  # the login moves last_login: snapshot after it
        assert f'action="{self._url()}"' in owner.get(f"/dashboard/history/tasks/{self.task.id}/").content.decode()
        rows, media = _rows54(), self._media()
        files = core_tests.ExplorationSeamTests._governed_files(self)
        sheet = json.dumps(self.out.spec_sheet, sort_keys=True, default=str)
        with patch.object(FileSystemStorage, "_save", side_effect=AssertionError("a render wrote media")), \
                patch("apps.pipeline.services.claude_service.call_claude",
                      side_effect=AssertionError("a render called a provider")) as claude:
            r = owner.post(self._url())
        assert r.status_code == 302, r.content[:300]
        assert (_rows54(), self._media()) == (rows, media) and not claude.called
        assert core_tests.ExplorationSeamTests._governed_files(self) == files     # register, ledger, tier record …
        self.out.refresh_from_db()
        assert json.dumps(self.out.spec_sheet, sort_keys=True, default=str) == sheet    # the design's record: as it was
        slug = r["Location"].split("/explorations/")[1].split("/")[0]
        study = self.store / slug
        assert sorted(p.name for p in study.iterdir()) == ["R001.json", "R001.png", "index.json"]
        record = json.loads((study / "R001.json").read_text())
        assert record["status"] == explorations.EXPLORATION_STATUS and explorations.claims(record) == ""
        assert record["form"].startswith("a lid's face") and record["what_changed"] == ER.NOTHING_CHANGED
        assert (record["colours_tried"], record["faces_tried"]) == ([], [])
        assert record["faces_as_they_stand"]["name_ar"] == "Noto Naskh Arabic (NotoNaskhArabic-Regular)"
        assert record["sheet_status_line"] == ER.SHEET_STATUS_LINE
        png = (study / "R001.png").read_bytes()
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and hashlib.sha256(png).hexdigest() == record["picture_sha256"]
        assert owner.get(f"/dashboard/history/explorations/{slug}/R001.png").status_code == 200
        assert owner.get(f"/dashboard/history/tasks/{self.task.id}/loop/").status_code == 200   # the loop serves a face

    def test_bh70_a_lids_loop_offers_no_glass_knob_and_says_why(self):
        """§BH70(1), item 21 of the list the owner was sent: the design loop offered a lid's design the bottle's four
        glass fields and the back copy as render knobs, and a render with either is refused on a lid. The glass
        fieldset is not offered on a lid and the page says why; the copy boxes say they keep words, not a render."""
        owner = self._owner()
        page = owner.get(f"/dashboard/history/tasks/{self.task.id}/loop/").content.decode()
        assert "Glass — the four retained appearance fields" not in page
        assert "the four glass fields are a bottle" in page and "a render with words typed here is refused" in page

    def test_a_colour_and_a_face_tried_change_the_picture_and_are_named_in_its_record(self):
        import json

        from apps.dashboard import exploration_render as ER
        from apps.dashboard import explorations
        owner = self._owner()
        first = owner.post(self._url(), HTTP_ACCEPT="application/json")    # the design page's answer: JSON, no redirect
        assert first.status_code == 200 and first["Content-Type"].startswith("application/json"), first.content[:300]
        a = first.json()
        assert (a["picture"], a["what_changed"]) == ("R001", ER.NOTHING_CHANGED)
        tried = owner.post(self._url(), {"colour_name": "#7a4a42", "colour_ring": "#CBA87D",
                                         "face_name": "PlayfairDisplay[wght]"}, HTTP_ACCEPT="application/json")
        assert tried.status_code == 200, tried.content[:300]
        b = tried.json()
        assert b["picture"] == "R002" and b["url"] == "/dashboard/history/explorations/%s/R002.png" % b["study"]
        assert ("the name in Cocoa Rose #7A4A42 (Nude Warm, Accent) — it stood in Deep Rose #8B3A52 (Blush Core, Accent)"
                in b["what_changed"])
        assert "the ring in Warm Gold #CBA87D (Blush Core, Ground)" in b["what_changed"]
        assert "the name set in Playfair Display (PlayfairDisplay[wght]) — it stood in Poppins" in b["what_changed"]
        assert isinstance(b["codes"], list)
        record = json.loads((self.store / b["study"] / "R002.json").read_text())
        assert [c["colour"] for c in record["colours_tried"]] == ["Cocoa Rose #7A4A42 (Nude Warm, Accent)",
                                                                 "Warm Gold #CBA87D (Blush Core, Ground)"]
        assert [f["face"] for f in record["faces_tried"]] == ["Playfair Display (PlayfairDisplay[wght])"]
        assert explorations.claims(record) == ""
        before = json.loads((self.store / b["study"] / "R001.json").read_text())
        # the emitted file itself embeds the granted face — and only the instance the role layer pins for the name's role,
        # never the variable file's default instance (§BH33(2): "a variable face never renders its default instance")
        from apps.ire import font_roles as FR
        pinned = FR.instance_for("PlayfairDisplay[wght]", FR.CONCEPT_NAME)["postscript"]
        assert [n for n in record["faces_embedded"] if n.startswith("PlayfairDisplay")] == [pinned], (
            record["faces_embedded"])
        assert not any(name.startswith("PlayfairDisplay") for name in before["faces_embedded"])
        assert record["picture_sha256"] != before["picture_sha256"]
        assert record["inputs_sha256"] != before["inputs_sha256"]
        assert owner.get(b["url"]).status_code == 200

    def test_a_face_whose_concept_is_not_read_is_refused_by_name_and_nothing_is_written(self):
        from unittest.mock import patch

        from apps.dashboard import exploration_render as ER
        from apps.pipeline.services import concept_layout as L
        spec = self.out.spec_sheet
        spec.pop(L.SPEC_KEY)
        self.out.spec_sheet = spec
        self.out.save(update_fields=["spec_sheet"])
        owner = self._owner()
        rows = _rows54()
        with patch("apps.pipeline.services.claude_service.call_claude",
                   side_effect=AssertionError("the loop called a provider")) as claude:
            r = owner.post(self._url())
            j = owner.post(self._url(), HTTP_ACCEPT="application/json")
            offer, explorable = ER.knob_offer(self.task), ER.explorable(self.task)
        text = r.content.decode()
        assert r.status_code == 409 and text.startswith(ER.RENDER_NEEDS_THE_CONCEPTS_READING + ": REFUSED"), text[:300]
        assert "has not been read for this drawing yet" in text and "paid step on the governed path" in text
        assert j.status_code == 409 and j.json()["refused"] == ER.RENDER_NEEDS_THE_CONCEPTS_READING
        assert not {"kind", "text"} <= set(j.json())
        assert (offer["form"], offer["refused"]) == (None, ER.RENDER_NEEDS_THE_CONCEPTS_READING)
        assert explorable["form"] is False and ER.RENDER_NEEDS_THE_CONCEPTS_READING in explorable["reason"]
        assert not claude.called and _rows54() == rows
        assert not self.store.exists() or not any(self.store.rglob("*"))

    def test_colours_and_faces_outside_the_governed_sets_are_refused_by_name(self):
        from apps.dashboard import exploration_render as ER
        owner = self._owner()
        for fields, code, words in (
                ({"colour_name": "#123456"}, ER.COLOUR_OUTSIDE_THE_PALETTE,
                 "is not a colour of the brand's palette (Blush Core, Nude Warm)"),
                ({"colour_name": "deep rose"}, ER.KNOB_REFUSED, "is not a colour"),
                ({"face_name": "Didot-Bold"}, ER.FACE_OUTSIDE_THE_SET, "is not a face of the granted set"),
                ({"face_name": "NotoNaskhArabic-Regular"}, ER.FACE_CANNOT_SET_THE_ROLE, "carries no Latin letters"),
                ({"face_name_ar": "Cairo-Bold"}, ER.FACE_CANNOT_SET_THE_ROLE, "§BH33(1)"),
                ({"colour_rule": "#8B3A52"}, ER.COLOUR_NOT_SEEN, "prints in the concept's own foil"),
                ({"translucency": "0.5"}, ER.KNOBS_FOR_THE_BOTTLE_ONLY, "no glass")):
            r = owner.post(self._url(), fields)
            text = r.content.decode()
            assert r.status_code == 409 and text.startswith(code + ": REFUSED") and words in text, (fields, text[:300])
        assert not self.store.exists() or not any(self.store.rglob("*"))                  # not one byte
        same = owner.post(self._url(), {"face_name_ar": "NotoNaskhArabic-Regular"}, HTTP_ACCEPT="application/json")
        assert same.status_code == 200 and same.json()["what_changed"] == ER.NOTHING_CHANGED   # its own face: no change

    def test_the_offer_says_what_can_be_tried_on_this_face_and_writes_nothing(self):
        from apps.dashboard import exploration_render as ER
        rows = _rows54()
        offer = ER.knob_offer(self.task)
        assert offer["form"] == "face" and _rows54() == rows
        assert not self.store.exists() or not any(self.store.rglob("*"))
        elements = {e["element"]: e for e in offer["elements"]}
        assert set(elements) == {"ground", "name", "rule", "ring", "motif"}
        assert elements["name"]["standing"]["words"] == "Deep Rose #8B3A52 (Blush Core, Accent)"
        assert elements["name"]["standing"]["source"].startswith("the concept's own")
        assert elements["rule"]["can_take_a_colour"] is False and "foil" in elements["rule"]["why_not"]
        assert elements["ring"]["can_take_a_colour"] is True and elements["ground"]["can_take_a_colour"] is True
        words = {p["words"] for p in offer["palette"]}
        assert {"Warm Gold #CBA87D (Blush Core, Ground)", "Deep Rose #8B3A52 (Blush Core, Accent)",
                "Cocoa Rose #7A4A42 (Nude Warm, Accent)"} <= words
        rose_gold = next(p for p in offer["palette"] if p["name"] == "Rose Gold")
        assert rose_gold["hex"] == "#C9A24B" and "stand-in" in rose_gold["depicted"]
        roles = {r["role"]: r for r in offer["roles"]}
        assert roles["name"]["standing"]["stem"] == "Poppins-Light" and "PlayfairDisplay[wght]" in roles["name"]["offer"]
        assert roles["name_ar"]["offer"] == ["NotoNaskhArabic-Regular"]
        assert any(n["stem"] == "Cairo-Bold" and "§BH33(1)" in n["why"] for n in roles["name_ar"]["not_offered"])
        # [the executor, U7a] an Arabic face that CAN set the name is offered — never dropped between the two lists
        from unittest.mock import patch
        real = ER._arabic_face

        def cairo_can(stem, standing):
            if stem != "Cairo-Bold":
                return real(stem, standing)
        with patch.object(ER, "_arabic_face", cairo_can):
            again = {r["role"]: r for r in ER.knob_offer(self.task)["roles"]}["name_ar"]
        assert again["offer"] == ["NotoNaskhArabic-Regular", "Cairo-Bold"]
        assert not any(n["stem"] == "Cairo-Bold" for n in again["not_offered"])
        face = next(f for f in offer["faces"] if f["stem"] == "PlayfairDisplay[wght]")
        assert face["specimen"].startswith("/dashboard/brand/faces/") and face["roles"] == ["name"]
        assert self._owner().get(face["specimen"]).status_code == 200
