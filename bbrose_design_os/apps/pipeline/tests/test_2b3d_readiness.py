"""Phase 2B-3D — production readiness + Gate-2 enforcement.

The Gate-2 approval path had packaging validators but no container branch: a
container output would approve straight through, and nothing represented the
HUMAN visual verdict. These tests pin container_production_readiness/1.0 and
its enforcement: a human rejection (task #51's frozen state) or an unreviewed
reconstruction blocks approval with HUMAN_VISUAL_ACCEPTANCE_REQUIRED, and
automated fidelity can never override a human rejection."""
from __future__ import annotations

from django.contrib.auth.models import Group, User
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.core.models import Brand
from apps.ire import container_production_readiness as cpr
from apps.pipeline.models import (DesignTask, GateDecision, GeneratedImage,
                                  PackagingOutput)

ROLE_REVIEWER = "Reviewer"

#: §AV1: DERIVED from the module, never re-typed. This literal used to restate
#: the reader's eight category names, which meant the test data carried the
#: same omission as the code under test — when ``content`` was added by a
#: writer in 2a92be8 and never declared here, no fixture could notice, and it
#: went unnoticed for 25 days. A clean spec is now clean *by construction*:
#: add a category to ``_SECTIONS`` and this follows it.
_CLEAN_SECTIONS = {name: [] for name in cpr._SECTIONS}


def _clean_reports() -> dict:
    """§BH50(f)(5): every fidelity report present with every axis measured,
    so the negative control below asserts an exactly-empty signal on a spec
    whose axes are all measured. An absent report is every axis unmeasured,
    and blocks — which is why a reconstructed fixture must carry them."""
    return {
        "container_fidelity_report": {
            "axes": {"product_name_presence": {"state": "MEASURED_PASS"}},
            "overall": "MEASURED_PASS"},
        "container_quantitative_fidelity/1.0": {
            "axes": {"logo_zone": {"state": "MEASURED_PASS"}}},
        "container_motif_fidelity_report": {
            "axes": {"motif_family": {"state": "MEASURED_PASS"}}},
        "container_typography_fidelity_report": {
            "axes": {"product_name": {"state": "MEASURED_PASS"}}},
        "container_concept_fidelity/1.0": {
            "axes": [{"axis": "material_object_separation",
                      "state": "MEASURED_PASS"}]},
    }


def _spec(human="none", codes=None, reconstruction=True):
    spec = {
        "backend": "container",
        "product_name": "Rosé Nectar", "sku": "BBR-CO-410",
        "container_decoration_zones/1.0": {"zones": [
            {"zone_type": "BOTTOM_CODE_ZONE"}]},
        "container_production_readiness_codes": codes or _CLEAN_SECTIONS,
    }
    if reconstruction:
        spec["container_reconstruction"] = {"status": "RECONSTRUCTED",
                                            "blockers": []}
        spec.update(_clean_reports())
        # §BH50(f)(2): a reconstructed spec carries its placeholder record; a
        # reconstruction without one is not "all copy supplied"
        spec["container_placeholder_copy/1.0"] = {
            "schema_version": "container_placeholder_copy/1.0",
            "pieces": [], "unwritten": [], "codes": [],
            "back_copy_composed_on_this_path": True}
    if human == "rejected":
        spec["container_2b3v_final_status/1.0"] = {
            "gate2_human_acceptance": "REJECTED",
            "blocking_codes": ["HUMAN_GATE2_VISUAL_REJECTION"]}
        spec["container_reconstruction_rejected/2"] = {"label": "REJECTED"}
    elif human == "accepted":
        spec[cpr.ACCEPTANCE_KEY] = {"state": cpr.HDA_ACCEPTED,
                                    "decided_by": "admin",
                                    "decided_at": "2026-07-24T00:00:00Z"}
    return spec


class HumanDesignAcceptanceTests(TestCase):
    def test_rejected_final_status_resolves_rejected_revision_required(self):
        hda = cpr.human_design_acceptance(_spec(human="rejected"))
        assert hda["state"] == "REJECTED / REVISION_REQUIRED"
        assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in hda["codes"]
        assert "HUMAN_GATE2_VISUAL_REJECTION" in hda["blocking_codes_preserved"]

    def test_unreviewed_reconstruction_is_not_reviewed_and_blocks(self):
        hda = cpr.human_design_acceptance(_spec(human="none"))
        assert hda["state"] == cpr.HDA_NOT_REVIEWED
        assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in hda["codes"]

    def test_explicit_acceptance_record_is_the_only_accepted_path(self):
        hda = cpr.human_design_acceptance(_spec(human="accepted"))
        assert hda["state"] == cpr.HDA_ACCEPTED and hda["codes"] == []
        # an acceptance without a human identity is NOT accepted
        spec = _spec(human="accepted")
        spec[cpr.ACCEPTANCE_KEY].pop("decided_by")
        assert cpr.human_design_acceptance(spec)["state"] != cpr.HDA_ACCEPTED

    def test_an_acceptance_counts_only_for_the_picture_it_names(self):
        """§BH71, after (0a): his acceptance is what stands between an unmeasured design and approval, so it counts
        only for the picture whose bytes it names — as the project stage already reads it."""
        spec = _spec(human="accepted")
        spec[cpr.ACCEPTANCE_KEY]["preview_sha256"] = "a" * 64
        void = cpr.human_design_acceptance(spec, "b" * 64)
        assert void["state"] == cpr.HDA_VOID and void["codes"] == [cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED]
        assert cpr.human_design_acceptance(spec, None)["state"] == cpr.HDA_VOID        # the picture is gone
        assert cpr.human_design_acceptance(spec, "a" * 64)["state"] == cpr.HDA_ACCEPTED
        assert cpr.human_design_acceptance(spec)["state"] == cpr.HDA_ACCEPTED           # read without the picture
        del spec[cpr.ACCEPTANCE_KEY]["preview_sha256"]                                  # written before bytes were named
        assert cpr.human_design_acceptance(spec, "b" * 64)["state"] == cpr.HDA_ACCEPTED
        clean = _spec(human="accepted")
        clean[cpr.ACCEPTANCE_KEY]["preview_sha256"] = "a" * 64
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            assert cpr.build_readiness(clean, "a" * 64)["ready"] is True
            other = cpr.build_readiness(clean, "b" * 64)
        assert other["ready"] is False and other["blocking_codes"][0] == cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED
        assert other["human_design_acceptance_state"] == cpr.HDA_VOID

    def test_automated_pass_never_overrides_human_rejection(self):
        # every automated section clean, output intent valid — still blocked
        spec = _spec(human="rejected")
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            report = cpr.build_readiness(spec)
        assert report["ready"] is False
        assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in report["blocking_codes"]
        # the human code ranks FIRST — ahead of every automated code
        assert report["blocking_codes"][0] == \
            cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED


class ReadinessAggregationTests(TestCase):
    def test_sections_aggregate_and_a_missing_icc_profile_is_a_production_note(self):
        # [the owner's answer of 2026-09-27: the print shop's CMYK profile is the maker's printing specification —
        # a production note, never a blocker. It read "missing_icc_blocks" and asserted it blocked]
        spec = _spec(human="accepted",
                     codes={**_CLEAN_SECTIONS,
                            "separations": ["WHITE_UNDERBASE_REVIEW_REQUIRED"]})
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            report = cpr.build_readiness(spec)
        joined = " ".join(report["blocking_codes"])
        assert "WHITE_UNDERBASE_REVIEW_REQUIRED" in joined
        assert cpr.MISSING_OUTPUT_INTENT not in joined
        assert any(n.startswith(cpr.MISSING_OUTPUT_INTENT) for n in report["production_notes"])
        assert report["sections"]["output_intent"]["codes"] == []
        assert report["ready"] is False

    def test_print_data_facts_block_when_missing(self):
        spec = _spec(human="accepted")
        spec.pop("sku")
        spec["container_decoration_zones/1.0"] = {"zones": []}
        report = cpr.build_readiness(spec)
        joined = " ".join(report["blocking_codes"])
        # [§BH71 (0b), the owner's goal of 2026-09-28: a missing code place is a production note naming the place
        # proposed, never a blocker — it read `"code_zone_confirmed" in joined`; the SKU still refuses]
        # [His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "a design started from a brief may be approved without an SKU. 'SKU missing' shows as a production note, never a block."] it read `"sku_present" in joined`: a missing SKU is a production note since
        assert "sku_present" not in joined and "code_zone_confirmed" not in joined
        assert any(n.startswith(cpr.BATCH_CODE_PLACE_NOT_CONFIRMED) for n in report["production_notes"])
        assert any(n.startswith(cpr.SKU_NOT_GIVEN) for n in report["production_notes"])


class Gate2EnforcementTests(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.user = User.objects.create_user("r", "r@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="gloss", status="awaiting_gate_2",
            design_target="product_container")
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p",
            variation_number=1)
        # VQR-6: Gate-2 first requires a coherent reconstruction result
        # (readiness contract) before the 2B-3D production-readiness layer
        # runs — real tasks reaching this layer completed reconstruction, so
        # the fixture carries that evidence: confirmation record, approved
        # profile gate decision and a stat-able .ai artifact.
        spec = _spec(human="rejected")
        spec["container_confirmation"] = {
            "combined_hash": "c0ffee" * 8, "confirmed_by": "r",
            "confirmed_at": "2026-08-01T00:00:00+00:00",
            "authority": "HUMAN_CONFIRMED_CONCEPT_ONLY"}
        spec["container_resume"] = {
            "celery_task_id": "celery-2b3d",
            "requested_at": "2026-08-01T00:00:01+00:00",
            "requested_by": "r", "kind": "INITIAL_CONFIRMATION"}
        self.out = PackagingOutput.objects.create(
            task=self.task, approved_image=img, spec_sheet=spec)
        self.out.design_preview_ai.save(
            f"container_task_{self.task.id}.ai",
            ContentFile(b"%PDF-1.4\n" + b"x" * 600), save=True)
        GateDecision.objects.create(
            task=self.task, gate="container_profile", decision="approve",
            decided_by=self.user)

    def _approve(self):
        # VQR-2A: the fail-closed visual quality gate sits BEFORE this
        # production-readiness layer; these tests exercise the 2B-3D layer,
        # so quality is stubbed to PASS (the real fixture has no measurable
        # quality evidence and would 409 at the earlier gate).
        from unittest.mock import patch
        with patch("apps.pipeline.services.visual_quality_gate."
                   "evaluate_container_visual_quality",
                   return_value={"overall": "PASS",
                                 "status": "VISUAL_QUALITY_PASSED",
                                 "blocking_findings": []}):
            return self.client.post(
                f"/api/tasks/{self.task.id}/gate2_approve/",
                {"packaging_output_id": self.out.id},
                content_type="application/json")

    def test_an_acceptance_of_another_picture_approves_nothing(self):
        """§BH71, after (0a): Gate 2 reads the picture — an acceptance that names other bytes than the preview's is
        void there, and his acceptance is required again; the same bytes stand."""
        import hashlib
        from unittest.mock import patch
        spec = dict(self.out.spec_sheet)
        for k in [k for k in spec if k.startswith("container_reconstruction_rejected")
                  or k == "container_2b3v_final_status/1.0"]:
            del spec[k]
        spec[cpr.ACCEPTANCE_KEY] = {"state": cpr.HDA_ACCEPTED, "decided_by": "owner",
                                    "preview_sha256": hashlib.sha256(b"PNG-the-accepted-one").hexdigest()}
        self.out.spec_sheet = spec
        self.out.save(update_fields=["spec_sheet"])
        self.out.design_preview.save("redrawn.png", ContentFile(b"PNG-a-redrawn-one"), save=True)
        with patch("apps.pipeline.tasks.resume_aria_gate2.delay") as delay:
            resp = self._approve()
        assert resp.status_code == 409
        body = resp.json()
        assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in body["failures"]
        assert body["human_design_acceptance"] == cpr.HDA_VOID
        delay.assert_not_called()
        from apps.pipeline.targets.container import ProductContainerTarget
        rows = {r["label"]: r["value"] for r in ProductContainerTarget().review_sections(self.task)}
        assert cpr.HDA_VOID in rows["Gate-2 verdict (derived at readiness-read)"]    # the board says it too
        self.out.design_preview.save("accepted.png", ContentFile(b"PNG-the-accepted-one"), save=True)
        with patch("apps.pipeline.tasks.resume_aria_gate2.delay"):
            resp = self._approve()
        assert resp.status_code == 200 or (
            cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED not in resp.json()["failures"]
            and resp.json()["human_design_acceptance"] == cpr.HDA_ACCEPTED), resp.content

    def test_human_rejection_refuses_gate2_approval(self):
        resp = self._approve()
        assert resp.status_code == 409
        body = resp.json()
        assert body["error"] == "PRODUCTION_NOT_READY"
        assert body["human_design_acceptance"] == "REJECTED / REVISION_REQUIRED"
        assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in body["failures"]
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_2"       # not approved
        # the verdict is persisted for audit
        self.out.refresh_from_db()
        assert self.out.spec_sheet["container_production_readiness/1.0"][
            "ready"] is False

    def test_unreviewed_reconstruction_refuses(self):
        # drop only the human verdict — the reconstruction evidence stays,
        # so the refusal is 2B-3D's (not VQR-6's GATE_2_NOT_READY)
        spec = {**self.out.spec_sheet}
        spec.pop("container_2b3v_final_status/1.0", None)
        spec.pop("container_reconstruction_rejected/2", None)
        self.out.spec_sheet = spec
        self.out.save(update_fields=["spec_sheet"])
        resp = self._approve()
        assert resp.status_code == 409
        assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in resp.json()["failures"]

    def test_a_stale_accepted_spec_is_approved_with_its_staleness_kept_in_words(self):
        """§BH54(d): "What blocks is acceptance: a STALE spec is re-derived before it can be accepted and the
        re-derivation decides." A spec with an explicit acceptance record and a CLEAN saved verdict — but saved before
        the brand_strings section was declared, the one section whose silence reads clean. [His goal of 2026-10-13
        (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design"] it is approved, its staleness kept with the
        approval in words, where approval answered SPEC_STALE_REDERIVE_REQUIRED and wrote no decision."""
        spec = {**self.out.spec_sheet}
        spec.pop("container_2b3v_final_status/1.0", None)
        spec.pop("container_reconstruction_rejected/2", None)
        spec[cpr.ACCEPTANCE_KEY] = {"state": cpr.HDA_ACCEPTED, "decided_by": "admin",
                                    "decided_at": "2026-07-24T00:00:00Z"}
        spec["container_production_readiness_codes"] = {
            k: v for k, v in spec["container_production_readiness_codes"].items() if k != "brand_strings"}
        self.out.spec_sheet = spec
        self.out.save(update_fields=["spec_sheet"])
        # the one environment fact between a clean spec and READY — no ICC profile is configured here — is stubbed,
        # so the test isolates what this ruling changes: a clean, accepted, STALE spec
        from unittest.mock import patch
        with patch.object(cpr, "_output_intent", return_value={"identity": {"valid": True}, "codes": []}):
            assert cpr.build_readiness(spec)["ready"] is True      # the saved verdict is clean — and stale
            before = GateDecision.objects.filter(task=self.task).count()
            resp = self._approve()
        assert resp.status_code == 200, resp.json()
        self.out.refresh_from_db()
        kept = self.out.spec_sheet["kept_with_approval"]
        assert [k["code"] for k in kept] == [cpr.SPEC_STALE_REDERIVE_REQUIRED], kept
        assert kept[0]["words"].startswith("its checks were made before today's rules")
        assert GateDecision.objects.filter(task=self.task).count() == before + 1
        self.task.refresh_from_db()
        assert self.task.status in ("gate_2_approved", "completed")

    def test_no_provider_call_during_enforcement(self):
        from unittest.mock import patch
        with patch("apps.pipeline.services.claude_service.call_claude") as pe, \
                patch("apps.pipeline.agents.image_producer.openai.images.edit") as ie:
            self._approve()
        pe.assert_not_called()
        ie.assert_not_called()


class UndeclaredReadinessSectionTests(TestCase):
    """§AV1 — the readiness report dropped a whole category for 25 days.

    ``targets/container/__init__.py:810`` said the
    ``CONTENT_VERIFICATION_REQUIRED`` markers "surface in the readiness report
    and block production authority". They did neither: the writer persisted
    ``readiness["content"]`` (2a92be8, 2026-07-27) and the reader iterated a
    fixed tuple created three days earlier (de27a61, 2026-07-24) that did not
    contain it. Unverified INGREDIENTS copy did not block production.

    The repair is not the missing string — it is that an undeclared category
    now HALTS the report. These tests pin both halves, because a guard nobody
    has watched fire is not evidence of anything (§AA).
    """

    #: Blockers that are true of this fixture regardless of which categories
    #: are persisted, each excluded BY NAME so that the negative control below
    #: can assert an exactly-empty signal rather than a loosely-filtered one.
    #: MISSING_OUTPUT_INTENT is environmental — the test settings configure no
    #: ICC profile — and is not a readiness category at all.
    _AMBIENT = ("CONTAINER_PRINT_DATA_INCOMPLETE",
                "CONTAINER_RECONSTRUCTION_ABSENT",
                cpr.MISSING_OUTPUT_INTENT,
                cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED)

    def _signal(self, codes):
        """Blocking codes with the ambient blockers removed, so each assertion
        below is about the category under test and not about the fixture's
        reconstruction, print-data or ICC state."""
        report = cpr.build_readiness(_spec(codes=codes))
        return [c for c in report["blocking_codes"]
                if not c.startswith(self._AMBIENT)]

    def test_unverified_reserved_copy_blocks_production_authority(self):
        """The 25-day regression, stated as the thing that was false."""
        signal = self._signal({**_CLEAN_SECTIONS, "content": [
            "CONTENT_VERIFICATION_REQUIRED:ingredients",
            "CONTENT_VERIFICATION_REQUIRED:warnings"]})
        assert "CONTENT_VERIFICATION_REQUIRED:ingredients" in signal
        assert "CONTENT_VERIFICATION_REQUIRED:warnings" in signal

    def test_content_is_declared(self):
        assert "content" in cpr._SECTIONS

    def test_a_category_nobody_declared_blocks(self):
        signal = self._signal({**_CLEAN_SECTIONS,
                               "wibble": ["SOMETHING_NOBODY_READS"]})
        assert f"{cpr.UNDECLARED_READINESS_SECTION}: wibble" in signal

    def test_an_undeclared_category_blocks_even_carrying_no_codes(self):
        """The category itself is the unknown, not the codes under it. A
        writer who persists an empty list under a new name has still added a
        category this module cannot interpret, and silence there is exactly
        how ``content`` was lost."""
        signal = self._signal({**_CLEAN_SECTIONS, "wibble": []})
        assert f"{cpr.UNDECLARED_READINESS_SECTION}: wibble" in signal

    def test_undeclared_codes_are_surfaced_but_not_interpreted(self):
        report = cpr.build_readiness(_spec(codes={
            **_CLEAN_SECTIONS, "wibble": ["SOMETHING_NOBODY_READS"]}))
        entry = report["sections"]["wibble"]
        assert entry["undeclared"] is True
        assert entry["codes_not_interpreted"] == ["SOMETHING_NOBODY_READS"]
        # surfaced for diagnosis, but NOT promoted into the blocking set:
        # interpreting a code from a category nobody declared would be
        # guessing at its meaning.
        assert "SOMETHING_NOBODY_READS" not in report["blocking_codes"]

    def test_the_seam_checks_state_travels_beside_the_wrap_codes(self):
        """§BH50(f)(6): a product with no wrapped surface reads NOT_APPLICABLE
        with its reason where Gate 2 looks — beside the codes, additively —
        and a wrapped product's crossing still refuses approval."""
        spec = _spec()
        spec["container_wrap_alignment"] = {
            "codes": [], "aligned": None,
            "seam_check": {"state": "NOT_APPLICABLE",
                           "reason": "no wrapped surface in the zone set — "
                                     "z_front on BODY_FRONT (USER_CONFIRMED)",
                           "wrapped_zone_ids": [], "per_zone": []}}
        report = cpr.build_readiness(spec)
        assert report["sections"]["wrap_alignment"] == {
            "codes": [],
            "seam_check": {"state": "NOT_APPLICABLE",
                           "reason": "no wrapped surface in the zone set — "
                                     "z_front on BODY_FRONT (USER_CONFIRMED)"}}
        # a persisted record written before the state existed carries no
        # seam_check, and the section says nothing it does not know
        assert "seam_check" not in cpr.build_readiness(_spec())["sections"][
            "wrap_alignment"]
        wrapped = _spec(codes={**_CLEAN_SECTIONS,
                               "wrap_alignment": ["CONTAINER_TEXT_CROSSES_SEAM"]})
        wrapped["container_wrap_alignment"] = {
            "codes": ["CONTAINER_TEXT_CROSSES_SEAM"], "aligned": False,
            "seam_check": {"state": "APPLICABLE",
                           "reason": "wrapped surface on record: z_wrap on BODY_WRAP"}}
        refusal = cpr.gate2_refusal(wrapped)
        assert refusal and "CONTAINER_TEXT_CROSSES_SEAM" in refusal["failures"]
        assert refusal["readiness"]["sections"]["wrap_alignment"]["seam_check"][
            "state"] == "APPLICABLE"

    def test_an_unmeasured_fidelity_axis_blocks_acceptance_and_is_derived_never_declared(self):
        """§BH50(f)(5): an UNMEASURED axis in any persisted fidelity report
        is a Gate-2 blocking code, derived at read time; the section is not in
        _SECTIONS, and a writer that persisted it would be refused as
        undeclared — the §AV1 mechanism guarding the design, not bypassing it."""
        spec = _spec()
        spec["container_fidelity_report"]["axes"]["logo"] = {"state": "UNMEASURED"}
        spec["container_quantitative_fidelity/1.0"]["axes"]["logo_scale"] = {
            "state": "UNMEASURED"}
        report = cpr.build_readiness(spec)
        derived = report["sections"]["fidelity_unmeasured"]
        # [§BH71 (0a), the owner's goal of 2026-09-28: "Unmeasured checks … show as a warning beside Approve, never a block." His
        # approval overrides §BH50(f)(5): the axes read as the section's codes, in blocking_codes and in the
        # refusal's failures — they are the section's and the verdict's acceptance warnings, carried beside it]
        assert derived["acceptance_warnings"] == [
            f"{cpr.FIDELITY_UNMEASURED}: logo",
            f"{cpr.QUANT_FIDELITY_UNMEASURED}: logo_scale"]
        assert derived["codes"] == []
        assert all(c in report["acceptance_warnings"] and c not in report["blocking_codes"]
                   for c in derived["acceptance_warnings"])
        assert derived["scope"].startswith("ACCEPTANCE")
        assert "fidelity_unmeasured" not in cpr._SECTIONS
        refusal = cpr.gate2_refusal(spec)
        assert refusal and f"{cpr.FIDELITY_UNMEASURED}: logo" in refusal["acceptance_warnings"]
        assert f"{cpr.FIDELITY_UNMEASURED}: logo" not in refusal["failures"]
        persisted = _spec(codes={**_CLEAN_SECTIONS, "fidelity_unmeasured": []})
        assert f"{cpr.UNDECLARED_READINESS_SECTION}: fidelity_unmeasured" in \
            cpr.build_readiness(persisted)["blocking_codes"]
        # a MEASURED_FAIL is not an unmeasured axis: it is the report's own code
        spec["container_fidelity_report"]["axes"]["logo"] = {"state": "MEASURED_FAIL"}
        assert f"{cpr.FIDELITY_UNMEASURED}: logo" not in \
            cpr.build_readiness(spec)["blocking_codes"]

    def test_task_52s_persisted_shape_reads_every_unmeasured_axis_with_wrap_placed(self):
        """The shape task 52's spec persisted at cf88211 (archive/work/bh50_design_step3_rules_copy_palette/d/r2t/
        spec_after.json): rule 4 with seven UNMEASURED axes, quant with all
        seventeen, motif with four, typography measured, the concept report a
        list of 25 passes, three confirmed zones and no wrapped surface, and no
        persisted seam_check (written before §BH50(f)(6)). The reader derives
        27 codes: wrap_alignment is NOT_APPLICABLE by the product's own zone
        record, and every other unmeasured axis blocks. The same shape on a
        BODY_WRAP zone blocks on wrap too — 28."""
        rule4 = {a: {"state": "UNMEASURED"} for a in (
            "logo", "motif_family", "motif_position", "wrap_alignment",
            "product_name_zone", "cap_body_coordination",
            "front_back_relationship")}
        rule4["product_name_presence"] = {"state": "MEASURED_PASS"}
        quant = {a: {"state": "UNMEASURED"} for a in (
            "logo_zone", "logo_scale", "product_name", "label_density",
            "motif_density", "motif_coverage", "motif_position",
            "cap_orientation", "front_dominance", "cap_artwork_zone",
            "front_back_balance", "motif_continuation", "typography_hierarchy",
            "cap_body_coordination", "motif_color_relationship",
            "motif_scale_distribution", "motif_rotation_distribution")}
        motif = {"motif_family": {"state": "MEASURED_PASS"}}
        motif.update({a: {"state": "UNMEASURED"} for a in (
            "motif_density", "motif_coverage", "motif_position",
            "motif_continuation")})

        def zone(zid, surface, ztype):
            return {"zone_id": zid, "zone_type": ztype, "parent_surface": surface,
                    "user_confirmation_state": "USER_CONFIRMED"}
        spec = _spec()
        spec.update({
            "container_fidelity_report": {"axes": rule4,
                                          "overall": "UNMEASURED_BLOCKING"},
            "container_quantitative_fidelity/1.0": {"axes": quant,
                                                    "overall": "UNMEASURED"},
            "container_motif_fidelity_report": {"axes": motif,
                                                "overall": "MEASURED_PASS"},
            "container_typography_fidelity_report": {
                "axes": {"product_name": {"state": "MEASURED_PASS"}}},
            "container_concept_fidelity/1.0": {"axes": [
                {"axis": f"axis_{i}", "state": "MEASURED_PASS"}
                for i in range(25)]},
            "container_decoration_zones/1.0": {"zones": [
                zone("z_front", "BODY_FRONT", "FRONT_PRINT_ZONE"),
                zone("z_back", "BODY_BACK", "BACK_PRINT_ZONE"),
                zone("z_bottom_code", "BOTTOM", "BOTTOM_CODE_ZONE")]},
            "container_wrap_alignment": {
                "codes": ["CONTAINER_WRAP_SEAM_CONFLICT",
                          "CONTAINER_TEXT_CROSSES_SEAM"], "aligned": False}})
        derived = cpr.fidelity_unmeasured(spec)
        assert len(derived["codes"]) == 27
        assert sum(c.startswith(cpr.FIDELITY_UNMEASURED) for c in derived["codes"]) == 6
        assert sum(c.startswith(cpr.QUANT_FIDELITY_UNMEASURED) for c in derived["codes"]) == 17
        assert sum(c.startswith(cpr.MOTIF_FIDELITY_UNMEASURED) for c in derived["codes"]) == 4
        assert f"{cpr.FIDELITY_UNMEASURED}: wrap_alignment" not in derived["codes"]
        na = derived["not_applicable"]["container_fidelity_report:wrap_alignment"]
        assert "BODY_FRONT" in na and "USER_CONFIRMED" in na
        assert derived["reports_absent"] == []
        spec["container_decoration_zones/1.0"]["zones"][0] = zone(
            "z_wrap", "BODY_WRAP", "WRAP_LABEL_ZONE")
        derived = cpr.fidelity_unmeasured(spec)
        assert len(derived["codes"]) == 28
        assert f"{cpr.FIDELITY_UNMEASURED}: wrap_alignment" in derived["codes"]

    def test_an_absent_fidelity_report_on_a_reconstructed_spec_blocks_and_an_unreconstructed_one_does_not(self):
        spec = _spec()
        del spec["container_motif_fidelity_report"]
        derived = cpr.fidelity_unmeasured(spec)
        code = f"{cpr.FIDELITY_REPORT_ABSENT}: container_motif_fidelity_report"
        assert derived["codes"] == [code]
        assert derived["reports_absent"] == ["container_motif_fidelity_report"]
        # [§BH71 (0a): it read `code in blocking_codes` — an absent report is an acceptance warning, never a block]
        assert code in cpr.build_readiness(spec)["acceptance_warnings"]
        assert code not in cpr.build_readiness(spec)["blocking_codes"]
        unreconstructed = _spec(reconstruction=False)
        assert cpr.fidelity_unmeasured(unreconstructed)["codes"] == []
        # a misspelled zone is a finding in this read-only path, never a raise
        spec = _spec()
        spec["container_fidelity_report"]["axes"]["wrap_alignment"] = {
            "state": "UNMEASURED"}
        spec["container_decoration_zones/1.0"]["zones"] = [
            {"zone_id": "z_front", "surface": "BODY_FRONT"}]
        derived = cpr.fidelity_unmeasured(spec)
        assert f"{cpr.FIDELITY_UNMEASURED}: wrap_alignment" in derived["codes"]

    def test_the_front_copy_channel_is_declared_and_its_absence_is_unmeasured(self):
        """§BH50(f)(3): front_copy is a declared readiness section (§AV1: in
        the same commit as its writer); an overrun code in it refuses
        approval; a reconstructed spec persisted before the channel existed
        reads UNMEASURED at read time, never clean."""
        assert "front_copy" in cpr._SECTIONS
        over = "CONTAINER_FRONT_COPY_EXCEEDS_ZONE: front-support +1.5036 mm"
        refusal = cpr.gate2_refusal(_spec(codes={**_CLEAN_SECTIONS, "front_copy": [over]}))
        assert refusal and over in refusal["failures"]
        legacy = {k: v for k, v in _CLEAN_SECTIONS.items() if k != "front_copy"}
        report = cpr.build_readiness(_spec(codes=legacy))
        absent = f"{cpr.FRONT_COPY_FIT_UNMEASURED}: no front copy fit on record"
        # [§BH71 (0a): unmeasured, never clean — and a warning beside Approve, never a block: it read as the
        # section's codes and in blocking_codes]
        assert absent in report["sections"]["front_copy"]["acceptance_warnings"]
        assert absent in report["acceptance_warnings"] and absent not in report["blocking_codes"]
        assert absent not in cpr.build_readiness(_spec())["acceptance_warnings"]
        assert absent not in cpr.build_readiness(
            _spec(codes=legacy, reconstruction=False))["acceptance_warnings"]

    def test_a_safe_area_overrun_refuses_approval_and_the_zone_code_keeps_its_meaning(self):
        """§BH50(g)(1) (re-typed §BH53(a)): a run over the zone's SAFE AREA is a
        blocking code in the front_copy channel — Gate 2 refuses it by name, at
        acceptance; the zone's own code stands beside it, each true; a clean
        spec carries neither (the negative control)."""
        over = "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: front-support +5.5036 mm"
        zone = "CONTAINER_FRONT_COPY_EXCEEDS_ZONE: front-support +1.5036 mm"
        refusal = cpr.gate2_refusal(_spec(codes={**_CLEAN_SECTIONS, "front_copy": [over, zone]}))
        assert refusal and over in refusal["failures"] and zone in refusal["failures"]
        assert over not in cpr.build_readiness(_spec())["blocking_codes"]

    def test_every_declared_section_carries_the_date_it_was_declared(self):
        """§BH50(g)(4): the declaration carries its date at the one place §AV1 forces it — a section in _SECTIONS with
        no date is a census failure, and a date with no section is a stale entry."""
        assert set(cpr.SECTION_SINCE) == set(cpr._SECTIONS)
        for name, (since, ruling, commit) in cpr.SECTION_SINCE.items():
            assert len(since) == 10 and since[4] == "-" and ruling and len(commit) >= 7, name
        assert {"since", "ruling", "commit", "what"} <= set(next(iter(cpr.CHECK_EPOCHS.values())))

    def test_a_spec_short_of_heads_checks_is_marked_stale_with_the_dates_and_nothing_newly_blocks(self):
        """§BH50(g)(4), re-typed §BH53(a): "A STALE SPEC NEVER SHOWS AS CURRENT … marks the spec stale with the date
        its checks predate." A reconstructed spec persisted before three declared sections existed names each with
        its date, ruling and commit; a saved report whose overall a later rule would not write is named with its
        epoch; a /1.0 front-copy record is named; the mark changes no blocking code; a fresh spec is CURRENT; a spec
        with no reconstruction has nothing to be stale."""
        legacy = _spec(codes={k: v for k, v in _CLEAN_SECTIONS.items()
                              if k not in ("front_copy", "colour_usage", "brand_strings")})
        before = cpr.build_readiness(legacy)["blocking_codes"]
        st = cpr.spec_staleness(legacy)
        assert st["stale"] and st["latest_since"] == "2026-09-17"
        named = {i["what"]: (i["since"], i["ruling"], i["commit"]) for i in st["checks_predate"] if i["kind"] == "MISSING_SECTION"}
        assert named == {"readiness section 'front_copy'": ("2026-09-17", "§BH50(f)(3)", "518dae2"),
                         "readiness section 'colour_usage'": ("2026-09-17", "§BH50(f)(7)", "ce19952"),
                         "readiness section 'brand_strings'": ("2026-08-21", "§AV3", "0027f41")}
        assert cpr.build_readiness(legacy)["blocking_codes"] == before          # the mark blocks nothing new
        assert not cpr.spec_staleness(_spec())["stale"]                          # a fresh spec is CURRENT
        assert cpr.spec_staleness({"backend": "container"}) == {
            "stale": False, "checks_predate": [], "latest_since": None, "reason": "no reconstruction on this spec"}
        # a saved overall a later rule would not write: named with its epoch, never rewritten
        old = _spec()
        old["container_motif_fidelity_report"] = {"overall": "MEASURED_PASS",
                                                  "axes": {"a": {"state": "MEASURED_PASS"}, "b": {"state": "UNMEASURED"}}}
        old["container_front_copy_fit/1.0"] = {"schema_version": "container_front_copy_fit/1.0", "runs": []}
        st = cpr.spec_staleness(old)
        kinds = {i["kind"]: i for i in st["checks_predate"]}
        assert kinds["REPORT_OVERALL"]["commit"] == "27942c3" and kinds["REPORT_OVERALL"]["since"] == "2026-09-17"
        assert kinds["RECORD_VERSION"]["commit"] == "container_front_copy_fit/1.1" and kinds["RECORD_VERSION"]["since"] == "2026-09-18"
        assert old["container_motif_fidelity_report"]["overall"] == "MEASURED_PASS"    # the saved report is untouched
        # the rule-4 report: an unmeasured REQUIRED axis under MEASURED_PASS predates the fail-closed rule
        r4 = _spec()
        r4["container_fidelity_report"] = {"overall": "MEASURED_PASS",
                                           "axes": {"a": {"state": "MEASURED_PASS"}, "b": {"state": "UNMEASURED", "required": False}}}
        assert not any(i["kind"] == "REPORT_OVERALL" for i in cpr.spec_staleness(r4)["checks_predate"])
        r4["container_fidelity_report"]["axes"]["b"]["required"] = True
        assert any(i["commit"] == "5512cdc" for i in cpr.spec_staleness(r4)["checks_predate"])

    def test_bh70_a_generic_spec_saved_with_no_front_copy_instrument_is_stale_and_blocks_nothing_new(self):
        """§BH70(1), item 5 of the list the owner was sent, with §BH53(a)(4) ("a stale spec never shows as current"):
        the generic path's front copy is measured now, so a spec saved with its one old code — nothing could measure
        it — is marked stale with that change's date, and nothing newly blocks; a spec carrying today's reading is
        not stale for it."""
        old_code = ("CONTAINER_FRONT_COPY_FIT_UNMEASURED: no fit instrument on this path (compose_container draws its "
                    "front into backbone.label_zone; which rectangle is the zone is a contract question before any "
                    "measurement)")
        saved = _spec(codes={**_CLEAN_SECTIONS, "front_copy": [old_code]})
        before = cpr.build_readiness(saved)["blocking_codes"]
        [item] = [i for i in cpr.spec_staleness(saved)["checks_predate"] if i["kind"] == "SECTION_VERDICT"]
        assert (item["since"], item["ruling"]) == ("2026-09-27", "§BH70(1), item 5 of the list the owner was sent")
        # [§BH71 (0a): the old code is unmeasured — a warning beside Approve since, never among what refuses; it
        # read `old_code in before`]
        assert cpr.build_readiness(saved)["blocking_codes"] == before and old_code not in before
        assert old_code in cpr.build_readiness(saved)["acceptance_warnings"]
        today = ("CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (its lines are laid into the drawing's own label area, "
                 "not the zone you confirmed)")
        assert not cpr.spec_staleness(_spec(codes={**_CLEAN_SECTIONS, "front_copy": [today]}))["stale"]

    def test_the_stale_mark_blocks_nothing_but_acceptance(self):
        """§BH54(d): "A STALE MARK DOES NOT BLOCK. It says a verdict predates today's checks — information, not
        refusal. What blocks is acceptance." `build_readiness` never reads the mark; `gate2_refusal` — acceptance —
        refuses a stale spec first and by name, the saved codes beside the refusal as what they are; a fresh spec is
        judged exactly as before."""
        short = {k: v for k, v in _CLEAN_SECTIONS.items() if k != "brand_strings"}    # saved before §AV3, 2026-08-21
        from unittest.mock import patch
        stale = _spec(human="accepted", codes=short)
        assert cpr.spec_staleness(stale)["stale"]
        # no ICC profile is configured on this machine; stubbed, so READY is reachable and the ruling's effect is isolated
        with patch.object(cpr, "_output_intent", return_value={"identity": {"valid": True}, "codes": []}):
            report = cpr.build_readiness(stale)
            assert report["ready"] is True and report["blocking_codes"] == []   # the mark is information here
            refusal = cpr.gate2_refusal(stale)
            assert refusal["error"] == cpr.SPEC_STALE_REDERIVE_REQUIRED
            assert refusal["failures"] == [refusal["failures"][0]] and "2026-08-21" in refusal["failures"][0]
            assert refusal["failures"][0].startswith(cpr.SPEC_STALE_REDERIVE_REQUIRED)
            assert refusal["staleness"]["stale"] and refusal["readiness"]["ready"] is True
            # stale AND blocked: refused for staleness first; what today's reader finds in the saved record follows
            both = cpr.gate2_refusal(_spec(human="rejected", codes=short))
            assert both["error"] == cpr.SPEC_STALE_REDERIVE_REQUIRED
            assert both["failures"][0].startswith(cpr.SPEC_STALE_REDERIVE_REQUIRED)
            assert cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED in both["failures"][1:]
            # fresh: unchanged either way
            assert cpr.gate2_refusal(_spec(human="accepted")) is None
            assert cpr.gate2_refusal(_spec(human="rejected"))["error"] == "PRODUCTION_NOT_READY"

    def test_a_reconstruction_with_no_placeholder_record_is_not_all_copy_supplied(self):
        """§BH50(f)(2): the content section is written unconditionally from
        the placeholder record; a reconstructed spec that carries no record at
        all blocks at read time, so silence never reads as clean."""
        spec = _spec()
        del spec["container_placeholder_copy/1.0"]
        report = cpr.build_readiness(spec)
        absent = ("CONTENT_VERIFICATION_REQUIRED: no placeholder-copy record "
                  "on this reconstruction")
        assert absent in report["sections"]["content"]["codes"]
        assert absent in report["blocking_codes"]
        assert absent not in cpr.build_readiness(_spec())["blocking_codes"]
        assert absent not in cpr.build_readiness(
            _spec(reconstruction=False))["blocking_codes"]

    def test_a_fully_declared_spec_raises_no_undeclared_code(self):
        """The negative control. Without it the four tests above would pass on
        a build_readiness that blocked unconditionally."""
        signal = self._signal(_CLEAN_SECTIONS)
        assert signal == []

    def test_colour_usage_is_declared_and_carries_the_reconcilers_own_code(self):
        """§BH50(f)(7): the colour counter's section, declared beside the
        font counter's; the code this module derives at read time is the
        reconciler's own, spelled once."""
        from apps.ire import colour_roles as CR
        assert "colour_usage" in cpr._SECTIONS
        assert cpr.COLOUR_USAGE_UNRECONCILED_CODE == CR.COLOUR_USAGE_UNRECONCILED_CODE

    def test_the_colour_codes_refuse_gate_2_approval(self):
        """§BH50(f)(7) read with his (4): a code that says it blocks is
        measured blocking. Either colour code in the declared section refuses
        Gate-2 approval by name; the clean fixture does not refuse on colour."""
        from apps.ire import colour_roles as CR
        for code in (CR.COLOUR_USAGE_DISAGREEMENT_CODE, CR.COLOUR_USAGE_UNRECONCILED_CODE):
            refusal = cpr.gate2_refusal(_spec(codes={**_CLEAN_SECTIONS, "colour_usage": [code]}))
            assert refusal is not None and code in refusal["failures"], code
        clean = cpr.gate2_refusal(_spec())
        assert not any(str(c).startswith("COLOUR_USAGE") for c in (clean or {}).get("failures", []))

    def test_a_reconstruction_persisted_before_the_colour_section_is_unmeasured_not_clean(self):
        """A spec whose readiness codes carry no colour_usage section was
        persisted before §BH50(f)(7); silence there is the §AV1 shape and
        reads as unmeasured, which blocks — never as reconciled."""
        codes = {k: v for k, v in _CLEAN_SECTIONS.items() if k != "colour_usage"}
        report = cpr.build_readiness(_spec(codes=codes))
        absent = (f"{cpr.COLOUR_USAGE_UNRECONCILED_CODE}: no colour_usage readiness "
                  "section on this reconstruction (persisted before §BH50(f)(7))")
        assert absent in report["sections"]["colour_usage"]["codes"]
        assert absent in report["blocking_codes"]
        assert absent not in cpr.build_readiness(_spec())["blocking_codes"]
        assert absent not in cpr.build_readiness(
            _spec(codes=codes, reconstruction=False))["blocking_codes"]

    def test_bh67_colour_sources_is_declared_and_an_old_reconstruction_reads_unread(self):
        """§BH67 HARD STOP: the printed-colour audit's section is DECLARED — its codes refuse Gate 2 by name — and a
        reconstruction persisted before the audit reads CONTAINER_COLOUR_SOURCES_UNREAD, never clean; a spec with no
        reconstruction has no colour to read."""
        assert "colour_sources" in cpr._SECTIONS
        code = "CONTAINER_COLOUR_UNSOURCED:#5A2C3A:product-name-hero-0"
        refusal = cpr.gate2_refusal(_spec(codes={**_CLEAN_SECTIONS, "colour_sources": [code]}))
        assert refusal is not None and code in refusal["failures"]
        assert not any("UNDECLARED_READINESS_SECTION" in str(c) for c in refusal["failures"])
        codes = {k: v for k, v in _CLEAN_SECTIONS.items() if k != "colour_sources"}
        report = cpr.build_readiness(_spec(codes=codes))
        unread = [c for c in report["blocking_codes"] if c.startswith(cpr.COLOUR_SOURCES_UNREAD_CODE)]
        assert len(unread) == 1 and unread[0] in report["sections"]["colour_sources"]["codes"]
        assert not any(c.startswith(cpr.COLOUR_SOURCES_UNREAD_CODE)
                       for c in cpr.build_readiness(_spec())["blocking_codes"])
        assert not any(c.startswith(cpr.COLOUR_SOURCES_UNREAD_CODE)
                       for c in cpr.build_readiness(_spec(codes=codes, reconstruction=False))["blocking_codes"])

    def test_the_clean_fixture_is_derived_from_the_module(self):
        """The omission was invisible because the fixture re-typed the reader's
        eight names. Re-typing them is what this asserts can no longer drift."""
        assert set(_CLEAN_SECTIONS) == set(cpr._SECTIONS)


class MakerSpecificationNotesTests(TestCase):
    """THE OWNER'S ANSWER OF 2026-09-27 TO THE §BH70 REPORT'S FIRST QUESTION: "Yes. A design is finished when I approve
    it. The maker's printing specification is shown as a production note, never a blocker (same as the physical
    sample)." Every code the maker's printing specification settles is a note — carried under production_notes, never in
    blocking_codes or ready; the text floor (§W2, §Y1) and every other code refuse as before; his acceptance finishes a
    design whose only codes are notes, and nothing else does."""

    _NOTES = {"production_method": ["CONTAINER_TECHNIQUE_UNVERIFIED", "CONTAINER_TRAPPING_REVIEW_REQUIRED",
                                    "CONTAINER_OVERPRINT_REVIEW_REQUIRED", "CONTAINER_COLOR_COUNT_EXCEEDED",
                                    "CONTAINER_MINIMUM_LINE_WEIGHT_FAILED"],
              "production_metrics": ["CONTAINER_REGISTRATION_REVIEW_REQUIRED", "CONTAINER_COLOR_COUNT_EXCEEDED",
                                     "CONTAINER_MAXIMUM_COVERAGE_EXCEEDED"],
              "separations": ["CONTAINER_WHITE_UNDERBASE_REQUIRED"]}

    def test_the_notes_are_the_codes_the_two_modules_write_for_the_makers_specification(self):
        from apps.ire import container_production_method as cpm
        from apps.ire import container_production_metrics as cpmet
        assert cpr.MAKER_SPECIFICATION_NOTES == {
            cpm.TECHNIQUE_UNVERIFIED, cpm.TRAPPING_REVIEW_REQUIRED, cpm.OVERPRINT_REVIEW_REQUIRED,
            cpmet.REGISTRATION_REVIEW_REQUIRED, cpm.COLOR_COUNT_EXCEEDED, cpmet.COLOR_COUNT_EXCEEDED,
            cpm.MINIMUM_LINE_WEIGHT_FAILED, cpm.MAXIMUM_COVERAGE_EXCEEDED, cpmet.MAXIMUM_COVERAGE_EXCEEDED,
            cpm.REGISTRATION_TOLERANCE_FAILED, cpmet.REGISTRATION_TOLERANCE_FAILED, cpm.WHITE_UNDERBASE_REQUIRED,
            cpr.MISSING_OUTPUT_INTENT}
        # the text floor sits in the same inferred table, and his §W2 and §Y1 own it
        assert cpm.MINIMUM_TEXT_SIZE_FAILED not in cpr.MAKER_SPECIFICATION_NOTES
        assert cpm.MINIMUM_TEXT_SIZE_UNMEASURED not in cpr.MAKER_SPECIFICATION_NOTES
        assert cpr.is_production_note("MISSING_OUTPUT_INTENT: NOT_CONFIGURED")      # read by its head, detail kept

    def test_a_design_whose_only_codes_are_notes_is_finished_when_he_accepts_it_and_not_before(self):
        codes = {**_CLEAN_SECTIONS, **self._NOTES}
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            report = cpr.build_readiness(_spec(human="accepted", codes=codes))
            finished = cpr.gate2_refusal(_spec(human="accepted", codes=codes))
            waiting = cpr.gate2_refusal(_spec(codes=codes))
        assert report["ready"] is True and report["blocking_codes"] == []
        assert finished is None                                                  # his acceptance finishes it
        assert waiting["failures"] == [cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED]    # and nothing else stands
        noted = set(report["production_notes"])
        assert {c for cs in self._NOTES.values() for c in cs} <= noted
        assert any(n.startswith(cpr.MISSING_OUTPUT_INTENT) for n in noted)
        assert set(waiting["production_notes"]) == noted                        # said beside a refusal, never in it
        assert report["sections"]["production_method"] == {
            "codes": [], "production_notes": self._NOTES["production_method"]}
        assert "production_notes" not in report["sections"]["content"]          # a section with none keeps its shape

    def test_the_text_floor_and_every_other_code_still_refuse(self):
        for section, code in (("production_method", "CONTAINER_MINIMUM_TEXT_SIZE_FAILED"),
                              # [§BH71 (0a): ("production_method", "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED") stood
                              # here — an unmeasured text size is a warning beside Approve since (AcceptanceWarningTests)]
                              ("production_method", "CONTAINER_METHOD_SURFACE_MISMATCH"),
                              ("production_method", "CONTAINER_MATERIAL_TECHNIQUE_MISMATCH"),
                              ("production_method", "CONTAINER_TECHNIQUE_UNSUPPORTED"),
                              ("production_metrics", "CONTAINER_LABEL_DENSITY_FAILED"),
                              ("front_copy", "CONTAINER_FRONT_COPY_EXCEEDS_SAFE_AREA: product-name-hero-0 +1.0 mm"),
                              ("content", "CONTENT_VERIFICATION_REQUIRED: ingredients"),
                              ("colour_sources", "CONTAINER_COLOUR_SOURCES_UNREAD: its printed colours")):
            report = cpr.build_readiness(_spec(human="accepted", codes={**_CLEAN_SECTIONS, section: [code]}))
            assert code in report["blocking_codes"] and report["ready"] is False, code
            assert code not in report["production_notes"], code

    def test_nothing_saved_is_rewritten_and_no_saved_design_turns_stale_for_it(self):
        import copy
        spec = _spec(human="accepted", codes={**_CLEAN_SECTIONS, **self._NOTES})
        before = copy.deepcopy(spec)
        cpr.build_readiness(spec)
        cpr.gate2_refusal(spec)
        assert spec == before
        assert cpr.spec_staleness(spec) == cpr.spec_staleness(_spec(human="accepted"))

    def test_each_note_is_said_in_words_that_refuse_nothing(self):
        """§BH50(f)(4): a label that blocks nothing must not say it blocks."""
        from apps.dashboard.words import PRODUCTION_NOTE_WORDS, production_note_words
        assert set(PRODUCTION_NOTE_WORDS) == set(cpr.MAKER_SPECIFICATION_NOTES)
        for code in cpr.MAKER_SPECIFICATION_NOTES:
            words = production_note_words(code).lower()
            assert not any(w in words for w in ("block", "refus", "cannot", "must", "wait")), (code, words)
        assert production_note_words("MISSING_OUTPUT_INTENT: NOT_CONFIGURED").endswith(" — NOT_CONFIGURED")


class CodePlaceNoteTests(TestCase):
    """§BH71 (0b), the owner's goal of 2026-09-28: \"Propose a batch-code place for every form that lacks one, shown as
    a production note, not a blocker.\" A design whose confirmed zones carry no code place reads a production note
    naming the place its form's proposal offers — it read CONTAINER_PRINT_DATA_INCOMPLETE: code_zone_confirmed,
    blocking; the product's name and SKU still refuse."""

    def _spec(self, **kw):
        from apps.pipeline.services import container_contract as cc
        spec = _spec(human="accepted", **kw)
        spec[cc.PROFILE_SCHEMA] = cc.build_inferred_profile("compact", "round")
        spec["container_decoration_zones/1.0"] = {"zones": cc.propose_zones(spec[cc.PROFILE_SCHEMA])}
        return spec

    def test_a_missing_code_place_is_a_note_naming_the_proposed_one(self):
        from apps.dashboard.words import production_note_words
        from apps.pipeline.services import container_contract as cc
        spec = self._spec()
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            report = cpr.build_readiness(spec)
        assert report["ready"] is True and not any("code_zone_confirmed" in c for c in report["blocking_codes"])
        place = cc.code_zone_for(spec[cc.PROFILE_SCHEMA], spec["container_decoration_zones/1.0"]["zones"])
        note = f"{cpr.BATCH_CODE_PLACE_NOT_CONFIRMED}: proposed — {cc.code_place_words(place)}"
        assert note in report["production_notes"] and report["sections"]["print_data"]["production_notes"] == [note]
        assert "on the base's underside, at its foot" in note and " mm window at " in note
        assert production_note_words(note).startswith("where the batch code prints is settled with the filler")
        assert cpr.MAKER_SPECIFICATION_NOTES < cpr.PRODUCTION_NOTES                # the maker's set stays as ruled

    def test_a_confirmed_code_place_says_nothing_and_a_missing_name_or_sku_still_refuses(self):
        from apps.pipeline.services import container_contract as cc
        spec = self._spec()
        record = spec[cc.PROFILE_SCHEMA]
        spec["container_decoration_zones/1.0"]["zones"] = cc.augment_code_zones(
            record, spec["container_decoration_zones/1.0"]["zones"])
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            report = cpr.build_readiness(spec)
            nameless = cpr.build_readiness({**self._spec(), "product_name": "", "sku": ""})
        assert not any(n.startswith(cpr.BATCH_CODE_PLACE_NOT_CONFIRMED) for n in report["production_notes"])
        assert f"{cpr.CONTAINER_PRINT_DATA_INCOMPLETE}: product_name_present" in nameless["blocking_codes"]
        # [His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "a design started from a brief may be approved without an SKU. 'SKU missing' shows as a production note, never a block."] it read `sku_present in nameless["blocking_codes"]`: the SKU is a note; the name still refuses
        assert not any("sku_present" in c for c in nameless["blocking_codes"])
        assert any(n.startswith(cpr.SKU_NOT_GIVEN) for n in nameless["production_notes"])

    def test_his_122_a_design_with_no_sku_yet_may_be_approved_and_is_told_beside_approve(self):
        """[His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (1): "a design started from a brief may be approved without an SKU. 'SKU missing' shows as a production note, never a block."] 117 and 122, started from his brief, carry no SKU: their review is ready, the missing SKU said
        beside Approve in words — never a reason it is refused; one given since is said nowhere."""
        from apps.dashboard.words import production_note_words
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            bare = cpr.build_readiness({**self._spec(), "sku": ""})
            given = cpr.build_readiness({**self._spec(), "sku": "BBR-HC-122"})
        note = next(n for n in bare["production_notes"] if n.startswith(cpr.SKU_NOT_GIVEN))
        assert bare["ready"] is True and not any("sku" in c for c in bare["blocking_codes"]), bare["blocking_codes"]
        assert production_note_words(note).startswith("no SKU yet — add it beside Approve whenever you have it")
        assert not any(n.startswith(cpr.SKU_NOT_GIVEN) for n in given["production_notes"])


class AcceptanceWarningTests(TestCase):
    """§BH71 (0a), the owner's goal of 2026-09-28: "My approval overrides §BH50(f)(5). Unmeasured checks (fidelity to
    the concept, copy fit) show as a warning beside Approve, never a block." Every code that refuses only because a
    check is unmeasured is an acceptance warning — beside a refusal, never in it, and never marked passed; a
    measured failure, a run never drawn and the instruments of §BH67's hard stops still refuse."""

    _WARNED = {"front_copy": ["CONTAINER_FRONT_COPY_FIT_UNMEASURED: vertical (no print-size block was handed to "
                              "the instrument)"],
               "back_copy": ["CONTAINER_BACK_COPY_FIT_UNMEASURED: no back panel instrument on this path"],
               "production_method": ["CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED"]}

    def test_an_unmeasured_check_is_a_warning_and_his_acceptance_finishes_the_design(self):
        codes = {**_CLEAN_SECTIONS, **self._WARNED}
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            spec = _spec(human="accepted", codes=codes)
            spec["container_quantitative_fidelity/1.0"]["axes"]["logo_scale"] = {"state": "UNMEASURED"}
            report = cpr.build_readiness(spec)
            finished = cpr.gate2_refusal(spec)
            waiting = cpr.gate2_refusal(_spec(codes=codes))
        warned = {c for cs in self._WARNED.values() for c in cs}
        assert report["ready"] is True and report["blocking_codes"] == []
        assert set(report["acceptance_warnings"]) == warned | {f"{cpr.QUANT_FIDELITY_UNMEASURED}: logo_scale"}
        assert finished is None                                                  # his acceptance finishes it
        assert waiting["failures"] == [cpr.HUMAN_VISUAL_ACCEPTANCE_REQUIRED]    # and nothing else stands
        assert set(waiting["acceptance_warnings"]) == warned                    # said beside it, never in it
        assert report["sections"]["production_method"] == {
            "codes": [], "acceptance_warnings": ["CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED"]}
        assert "acceptance_warnings" not in report["sections"]["content"]        # a section with none keeps its shape
        assert cpr.is_acceptance_warning(f"{cpr.BACK_COPY_FIT_UNMEASURED}: CONTAINER_BACK_PANEL_FIT_UNMEASURED")

    def test_a_measured_failure_a_run_never_drawn_and_the_hard_stops_instruments_still_refuse(self):
        for section, code in (("front_copy", "CONTAINER_FRONT_COPY_EXCEEDS_ZONE: front-support +1.5036 mm"),
                              ("front_copy", "CONTAINER_FRONT_COPY_FIT_UNMEASURED: product-name-hero-0 (NOT_DRAWN)"),
                              ("production_method", "CONTAINER_MINIMUM_TEXT_SIZE_FAILED"),
                              ("colour_usage", "COLOUR_USAGE_UNRECONCILED"),
                              ("colour_sources", "CONTAINER_COLOUR_SOURCES_UNREAD: its printed colours"),
                              ("font", "FONT_USAGE_UNRECONCILED"),
                              ("content", "CONTENT_VERIFICATION_REQUIRED: ingredients")):
            with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
                report = cpr.build_readiness(_spec(human="accepted", codes={**_CLEAN_SECTIONS, section: [code]}))
            assert code in report["blocking_codes"] and report["ready"] is False, code
            assert code not in report["acceptance_warnings"], code

    def test_bh71_the_shades_unconfirmed_arabic_is_said_beside_approve_never_a_block(self):
        """His answer of 2026-09-29 to the §BH71 report, (4): the record's shade drawn with an Arabic the executor wrote
        is marked beside Approve while the record says so (§BH55(a): "marked rather than assumed") — words not
        confirmed yet, said apart from the checks not measured yet — and never refuses: his acceptance still finishes
        the design."""
        from apps.dashboard.words import acceptance_warning_rows, acceptance_warning_words
        code = ("CONTAINER_SHADE_ARABIC_UNCONFIRMED: the shade's Arabic 'طبيعي' was written by the executor and nobody "
                "has confirmed it — Product.shade_names")
        with override_settings(PRODUCTION_ICC_PROFILE_PATH=""):
            report = cpr.build_readiness(_spec(human="accepted", codes={**_CLEAN_SECTIONS, "content": [code]}))
        assert report["ready"] is True and report["blocking_codes"] == [], report["blocking_codes"]
        assert report["acceptance_warnings"] == [code]
        assert code.split(":")[0] in cpr.UNCONFIRMED_WARNINGS
        said = "the shade name's Arabic, written by the executor — not confirmed yet"
        assert acceptance_warning_words(code) == said
        assert acceptance_warning_rows([code]) == [{"code": "CONTAINER_SHADE_ARABIC_UNCONFIRMED", "words": said}]

    def test_nothing_saved_is_rewritten_by_reading_the_warnings(self):
        import copy
        spec = _spec(codes={**_CLEAN_SECTIONS, **self._WARNED})
        before = copy.deepcopy(spec)
        cpr.build_readiness(spec)
        cpr.gate2_refusal(spec)
        assert spec == before

    def test_each_warning_is_said_in_words_that_refuse_nothing(self):
        """§BH50(f)(4): a label that blocks nothing must not say it blocks."""
        from apps.dashboard.words import (ACCEPTANCE_WARNING_WORDS, VQ_AXIS_WARNING_WORDS, acceptance_warning_rows,
                                          acceptance_warning_words, vq_axis_warning_words)
        from apps.pipeline.services.visual_quality_gate import REQUIRED_AXES
        assert set(cpr.ACCEPTANCE_WARNINGS) <= set(ACCEPTANCE_WARNING_WORDS)
        assert set(VQ_AXIS_WARNING_WORDS) == set(REQUIRED_AXES)
        said = [acceptance_warning_words(c) for c in ACCEPTANCE_WARNING_WORDS] + [
            vq_axis_warning_words(a) for a in REQUIRED_AXES]
        unconfirmed = {acceptance_warning_words(c) for c in cpr.UNCONFIRMED_WARNINGS}
        for words in said:
            # [his answer of 2026-09-29 to the §BH71 report, (4)] words nobody has confirmed say so; every check with
            # no measurement says that
            assert words.endswith(" — not confirmed yet" if words in unconfirmed else " — not measured yet"), words
            assert not any(w in words.lower() for w in ("block", "refus", "cannot", "must", "wait")), words
        rows = acceptance_warning_rows([f"{cpr.QUANT_FIDELITY_UNMEASURED}: logo_scale",
                                        f"{cpr.QUANT_FIDELITY_UNMEASURED}: motif_coverage",
                                        "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED"])
        assert rows == [{"code": cpr.QUANT_FIDELITY_UNMEASURED,
                         "words": "the drawing's measures against its concept — not measured yet (2 measures)"},
                        {"code": "CONTAINER_MINIMUM_TEXT_SIZE_UNMEASURED",
                         "words": "the size of copy drawn only as a picture of the product — not measured yet"}]

