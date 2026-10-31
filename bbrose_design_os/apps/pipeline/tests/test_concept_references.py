"""Concept-reference permission + candidates + influence plan (2A-6E §3–§5).

Task #50's Gate-1 audit proved no material-library visual ever reached the
image provider and nothing recorded which references did. These tests pin
the human-gated flow: candidates are retrieved deterministically and NEVER
auto-approved; approval is a user action granting concept reference ONLY;
the influence plan carries principles and no file locator.
"""
from __future__ import annotations

import json
import shutil

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.models import Brand, DesignReference
from apps.pipeline.models import (
    ConceptInfluencePlan,
    ConceptReference,
    DesignTask,
)
from apps.pipeline.services.concept_references import (
    APPROVE_MAX,
    ConceptReferenceError,
    approve_concept_references,
    approved_references,
    build_candidates,
    build_influence_plan,
    reference_file_path,
)

TASK_TEXT = ("BBROSE Baked Powder packaging — refined feminine editorial "
             "design, blush pink and ivory pastel palette, gold accents, "
             "elegant pattern allowed")


class ConceptReferenceTestCase(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.user = User.objects.create_user(
            "reviewer", password="x", is_superuser=True)
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text=TASK_TEXT,
            status="awaiting_gate_1")

    def _seed_references(self, media_root, count=4):
        from pathlib import Path
        rows = []
        for index in range(count):
            name = f"ref{index}"
            (Path(media_root) / f"{name}.png").write_bytes(b"\x89PNG")
            rows.append(DesignReference.objects.create(
                name=name, image_path=f"{name}.png", category="CO",
                product_type="face powder",
                tags=["blush", "editorial", "gold"],
                summary="refined blush editorial powder carton"))
        return rows


class CandidateRetrievalTests(ConceptReferenceTestCase):
    def test_candidates_are_never_auto_approved(self):
        import tempfile
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with self.settings(MEDIA_ROOT=media,
                           DIP_INVENTORY_PATH="/nonexistent/inventory.jsonl"):
            self._seed_references(media)
            rows = build_candidates(self.task)
        assert rows
        assert all(r.permission_status == ConceptReference.PERMISSION_CANDIDATE
                   for r in rows)
        assert approved_references(self.task) == []

    def test_candidates_are_idempotent_and_preserve_approval(self):
        import tempfile
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with self.settings(MEDIA_ROOT=media,
                           DIP_INVENTORY_PATH="/nonexistent/inventory.jsonl"):
            self._seed_references(media)
            first = build_candidates(self.task)
            approve_concept_references(
                self.task, self.user, [first[0].pk, first[1].pk])
            again = build_candidates(self.task)
        assert len(again) == len(first)
        first[0].refresh_from_db()
        assert first[0].permission_status == \
            ConceptReference.PERMISSION_APPROVED

    def _index(self, rows):
        """Day 7 §3: the picker reads the library index (what each file SHOWS), never the inventory's file names. A fixture
        index, no house index, no previews; the DIP inventory empty so the .ai candidates stay out of the measurement."""
        import tempfile
        from pathlib import Path
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        root = Path(tmp)
        (root / "materials").mkdir()
        (root / "inventory.jsonl").write_text("")
        (root / "materials-index.json").write_text(json.dumps({"schema": "day7_materials_index/1", "items": rows}))
        return root

    @staticmethod
    def _row(sha, name, kind, tags, subject, **extra):
        row = {"sha256": sha, "name": name, "paths": ["materials/" + name], "extension": "." + name.rsplit(".", 1)[-1],
               "file_kind": "raster", "kind": kind, "subject": subject, "tags": tags, "style": [], "colours": [], "text_present": False,
               "text_seen": [], "language": "none", "surfaces": ["pattern-fill", "carton"], "preview": False, "caption_source": "day7-haiku",
               "rights": {"tier": "house", "excluded": False, "basis": "D-D7-1"}}
        row.update(extra)
        return row

    def test_material_candidates_come_from_the_library_index(self):
        import tempfile
        from pathlib import Path
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        root = self._index([self._row("a" * 64, "gold-floral-pattern.png", "pattern", ["gold", "floral", "pattern", "blush", "elegant"],
                                      "A gold floral repeat on blush pink, elegant and editorial")])
        image = root / "materials" / "gold-floral-pattern.png"
        image.write_bytes(b"\x89PNG")
        with self.settings(MEDIA_ROOT=media, DIP_INVENTORY_PATH=str(root / "inventory.jsonl"), MATERIALS_ROOT=str(root),
                           MATERIALS_INDEX_PATH=str(root / "materials-index.json"), HOUSE_INDEX_PATH=str(root / "no-house-index.json"),
                           MATERIALS_PREVIEWS_ROOT=str(root / "no-previews")):
            rows = build_candidates(self.task)
            material = [r for r in rows if r.source_type == "MATERIAL_LIBRARY"]
            assert material, "the indexed pattern should be a candidate"
            row = material[0]
            assert row.library_item_id == "materials:" + "a" * 64           # pinned by content hash
            assert row.description.startswith("role: pattern")                # its role
            assert row.ownership_status == "HOUSE_LIBRARY"                    # D-D7-1
            assert row.rights_status == "LICENSED_FOR_GENERATION_D-D7-1"
            assert row.permission_status == ConceptReference.PERMISSION_CANDIDATE
            assert "gold" in row.relevance_reason and "gold-floral-pattern" not in row.relevance_reason
            assert reference_file_path(row) == image.resolve()

    def test_irrelevant_materials_are_not_padded_in(self):
        import tempfile
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        # a file NAMED for the brief but SHOWING something else is not offered: names never rank (Day 7 §3)
        root = self._index([self._row("b" * 64, "24-hours-clock-icon.png", "icon", ["clock", "time", "hours", "dial", "flat"],
                                      "A 24-hour clock dial icon in flat grey"),
                            self._row("c" * 64, "blush-gold-elegant-pattern.png", "background", ["stars", "night", "navy", "scattered"],
                                      "Scattered white stars on a navy night field")])
        with self.settings(MEDIA_ROOT=media, DIP_INVENTORY_PATH=str(root / "inventory.jsonl"), MATERIALS_ROOT=str(root),
                           MATERIALS_INDEX_PATH=str(root / "materials-index.json"), HOUSE_INDEX_PATH=str(root / "no-house-index.json")):
            rows = build_candidates(self.task)
        assert not [r for r in rows if r.source_type == "MATERIAL_LIBRARY"]


class GovernedRecordTests(ConceptReferenceTestCase):
    """§BH55 Phase 3 (survey rows 1.11, 3.9): what the MATERIALS RECORD says of each reference the picker offers, and
    what the file shows. MEASURED read-only on the development database while this was written: of the twelve
    material-library references this system has ever offered, NONE is in the tier record — the record governs 4,832
    files and the picker draws from the design-intelligence inventory's 12,473 — so the card says that in words rather
    than leaving it blank."""

    def _records(self, tmp):
        import hashlib
        from pathlib import Path
        governed = hashlib.sha256(b"a governed file").hexdigest()
        tiers = Path(tmp) / "materials_tiers.jsonl"
        tiers.write_text(json.dumps({"relative_path": "materials/rose.png", "sha256": governed, "tier": "PRODUCTION",
                                     "tier_source": "OWNER", "condition": "", "granted_by": "the owner",
                                     "granted_at": "2026-01-01"}) + "\n")
        captions = Path(tmp) / "captions.jsonl"
        captions.write_text(json.dumps({"sha256": governed,
                                        "caption": {"subject": "a rose on a cream ground", "finish": "matte"}}) + "\n")
        return governed, tiers, captions

    def _reference(self, **kw):
        from apps.pipeline.models import ConceptReference
        return ConceptReference.objects.create(task=self.task, **kw)

    def test_each_offered_reference_says_what_the_record_says_of_it(self):
        import tempfile

        from apps.dashboard import materials_library as ml
        from apps.dashboard.materials_library import record_of as governed_record
        with tempfile.TemporaryDirectory() as tmp:
            governed, tiers, captions = self._records(tmp)
            with override_settings(HISTORY_TIER_RECORD=str(tiers), MATERIALS_CAPTIONS=str(captions)):
                ml._cache["rows"] = (None, [])
                ml._cache["captions"] = (None, {})
                known = self._reference(source_type="MATERIAL_LIBRARY", library_item_id=f"materials:{governed}",
                                        title="rose", image_root="materials", image_path="materials/rose.png")
                unjudged = self._reference(source_type="MATERIAL_LIBRARY", library_item_id="materials:" + "0" * 64,
                                           title="another", image_root="materials",
                                           image_path="materials/other.png")
                house = self._reference(source_type="HISTORICAL_DESIGN_REFERENCE", library_item_id="design_reference:1",
                                        title="a past design", image_root="media", image_path="references/x.png")
                assert governed_record(known) == {"tier": "PRODUCTION", "words": "Can be placed",
                                                  "shows": "a rose on a cream ground"}
                assert governed_record(unjudged)["tier"] is None
                assert "has not judged this file" in governed_record(unjudged)["words"]
                assert governed_record(house) == {}          # a house design is not the materials record's to judge
                self.client.force_login(self.user)
                # [his goal of 2026-10-06, item 13] the screen shows what the brief matches now (and what he approved):
                # these three, as the library offers them
                from unittest import mock as _mock
                with _mock.patch("apps.pipeline.services.concept_references.build_candidates",
                                 return_value=[known, unjudged, house]):
                    body = self.client.get(f"/api/tasks/{self.task.pk}/concept_references/").json()
                shown = {row["id"]: row["record"] for row in body["candidates"]}
                assert shown[known.pk]["words"] == "Can be placed"
                assert "has not judged this file" in shown[unjudged.pk]["words"]
            ml._cache["rows"] = (None, [])
            ml._cache["captions"] = (None, {})


class ApprovalTests(ConceptReferenceTestCase):
    def _candidates(self, count=5):
        rows = []
        for index in range(count):
            rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:{index}",
                title=f"blush editorial reference {index}",
                image_root="media", image_path=f"ref{index}.png"))
        return rows

    def test_approval_is_bounded_two_to_four(self):
        rows = self._candidates()
        with self.assertRaises(ConceptReferenceError) as ctx:
            approve_concept_references(self.task, self.user, [rows[0].pk])
        assert ctx.exception.code == "REFERENCE_APPROVAL_COUNT_OUT_OF_RANGE"
        with self.assertRaises(ConceptReferenceError):
            approve_concept_references(
                self.task, self.user, [r.pk for r in rows[:APPROVE_MAX + 1]])

    def test_approval_grants_concept_reference_only(self):
        rows = self._candidates()
        result = approve_concept_references(
            self.task, self.user, [rows[0].pk, rows[1].pk])
        rows[0].refresh_from_db()
        assert rows[0].permission_status == \
            "USER_APPROVED_FOR_CONCEPT_REFERENCE"
        assert rows[0].approved_by == self.user
        # concept permission NEVER implies production use — structurally
        assert rows[0].production_use_allowed is False
        plan = ConceptInfluencePlan.objects.get(task=self.task)
        assert plan.plan["production_use_granted"] is False
        assert plan.plan_hash == result["plan_hash"]

    def test_wrong_task_reference_refuses(self):
        other = DesignTask.objects.create(
            brand=self.brand, task_text="other", status="queued")
        foreign = ConceptReference.objects.create(
            task=other, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id="design_reference:x", title="foreign",
            image_root="media", image_path="x.png")
        mine = self._candidates(1)[0]
        with self.assertRaises(ConceptReferenceError) as ctx:
            approve_concept_references(
                self.task, self.user, [mine.pk, foreign.pk])
        assert ctx.exception.code == "REFERENCE_WRONG_TASK"

    def test_reapproval_replaces_the_previous_selection(self):
        rows = self._candidates()
        approve_concept_references(
            self.task, self.user, [rows[0].pk, rows[1].pk])
        approve_concept_references(
            self.task, self.user, [rows[2].pk, rows[3].pk])
        approved = {r.pk for r in approved_references(self.task)}
        assert approved == {rows[2].pk, rows[3].pk}


class InfluencePlanTests(ConceptReferenceTestCase):
    def test_plan_describes_principles_without_any_locator(self):
        row = ConceptReference.objects.create(
            task=self.task, source_type="MATERIAL_LIBRARY",
            library_item_id="materials:" + "c" * 60,
            title="gold-floral-linework-pattern",
            description="PATTERN from the materials library",
            image_root="materials",
            image_path="materials/gold-floral-linework-pattern.png",
            permission_status=ConceptReference.PERMISSION_APPROVED)
        plan = build_influence_plan(self.task, [row])
        blob = json.dumps(plan).lower()
        assert "materials/" not in blob
        assert ".png" not in blob
        reference = plan["references"][0]
        assert reference["permission"] == \
            "USER_APPROVED_FOR_CONCEPT_REFERENCE"
        assert "copy the same layout" in reference["prohibited_from_copying"]
        assert "gold" in reference["palette_influence"]
        assert plan["production_use_granted"] is False

    def test_a_locator_in_the_plan_fails_closed(self):
        from apps.pipeline.services.concept_references import _assert_no_locator
        with self.assertRaises(AssertionError):
            _assert_no_locator({"note": "see materials/foo.png"})


class ApiTests(ConceptReferenceTestCase):
    def test_candidate_endpoint_lists_without_approving(self):
        import tempfile
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, True)
        with self.settings(MEDIA_ROOT=media,
                           DIP_INVENTORY_PATH="/nonexistent/inventory.jsonl"):
            self._seed = self._seed_references(media)
            self.client.force_login(self.user)
            response = self.client.get(
                f"/api/tasks/{self.task.pk}/concept_references/")
        assert response.status_code == 200
        data = response.json()
        assert data["approved_ids"] == []
        assert data["select_between"] == [2, 4]
        assert all(c["permission_status"] == "CANDIDATE"
                   for c in data["candidates"])
        assert all(c["production_use_allowed"] is False
                   for c in data["candidates"])

    def test_approve_endpoint_records_the_human_action(self):
        rows = [ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id=f"design_reference:{i}", title=f"r{i}",
            image_root="media", image_path=f"r{i}.png") for i in range(2)]
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": [rows[0].pk, rows[1].pk]}),
            content_type="application/json")
        assert response.status_code == 200
        assert response.json()["approved_ids"] == sorted(
            [rows[0].pk, rows[1].pk])
        from apps.pipeline.models import AgentLog
        log = AgentLog.objects.filter(
            task=self.task,
            action__contains="Concept references approved").first()
        assert log is not None and log.actor == self.user

    def test_approve_response_carries_verifiable_statuses(self):
        """2A-6E-CORR-1: a client must be able to confirm persistence from
        the response instead of inferring it from a 200."""
        rows = [ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id=f"design_reference:s{i}", title=f"s{i}",
            image_root="media", image_path=f"s{i}.png") for i in range(3)]
        self.client.force_login(self.user)
        posted_ids = [rows[0].pk, rows[1].pk]
        response = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": posted_ids}),
            content_type="application/json")
        assert response.status_code == 200
        statuses = {int(k): v for k, v in response.json()["statuses"].items()}
        for pk in posted_ids:
            assert statuses[pk] == "USER_APPROVED_FOR_CONCEPT_REFERENCE"
        assert statuses[rows[2].pk] == "CANDIDATE"   # unselected unchanged
        for pk in posted_ids:                        # persisted, not just said
            assert ConceptReference.objects.get(pk=pk).permission_status == \
                "USER_APPROVED_FOR_CONCEPT_REFERENCE"

    def test_repeated_approval_is_idempotent(self):
        rows = [ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id=f"design_reference:i{i}", title=f"i{i}",
            image_root="media", image_path=f"i{i}.png") for i in range(2)]
        self.client.force_login(self.user)
        ids = [r.pk for r in rows]
        first = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": ids}), content_type="application/json")
        second = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": ids}), content_type="application/json")
        assert first.status_code == second.status_code == 200
        assert first.json()["approved_ids"] == second.json()["approved_ids"]
        assert first.json()["plan_hash"] == second.json()["plan_hash"]

    def test_unauthorized_approval_fails(self):
        row = ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id="design_reference:u", title="u",
            image_root="media", image_path="u.png")
        outsider = User.objects.create_user("outsider", password="x")
        self.client.force_login(outsider)
        response = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": [row.pk, row.pk]}),
            content_type="application/json")
        assert response.status_code == 403
        row.refresh_from_db()
        assert row.permission_status == ConceptReference.PERMISSION_CANDIDATE

    def test_wrong_task_state_refuses_with_stable_code(self):
        self.task.status = "completed"
        self.task.save()
        rows = [ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id=f"design_reference:t{i}", title=f"t{i}",
            image_root="media", image_path=f"t{i}.png") for i in range(2)]
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": [r.pk for r in rows]}),
            content_type="application/json")
        assert response.status_code == 409
        assert response.json()["code"] == "TASK_STATE_REJECTED"
        for row in rows:
            row.refresh_from_db()
            assert row.permission_status == \
                ConceptReference.PERMISSION_CANDIDATE

    def test_api_errors_are_visible_in_the_response_body(self):
        """postAction surfaces data.error — a refusal must carry one."""
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": []}), content_type="application/json")
        assert response.status_code == 400
        assert response.json()["error"]
        assert response.json()["code"] == \
            "REFERENCE_APPROVAL_COUNT_OUT_OF_RANGE"

    def test_approval_makes_no_provider_call(self):
        from apps.pipeline.models import ApiCallRecord
        rows = [ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id=f"design_reference:p{i}", title=f"p{i}",
            image_root="media", image_path=f"p{i}.png") for i in range(2)]
        before = ApiCallRecord.objects.count()
        self.client.force_login(self.user)
        response = self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": [r.pk for r in rows]}),
            content_type="application/json")
        assert response.status_code == 200
        assert ApiCallRecord.objects.count() == before

    def test_successful_approval_unlocks_regeneration(self):
        from apps.pipeline.services.gate1_regeneration import (
            check_regeneration_ready)
        rows = [ConceptReference.objects.create(
            task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
            library_item_id=f"design_reference:r{i}", title=f"r{i}",
            image_root="media", image_path=f"r{i}.png") for i in range(2)]
        self.client.force_login(self.user)
        self.client.post(
            f"/api/tasks/{self.task.pk}/concept_references/approve/",
            data=json.dumps({"ids": [r.pk for r in rows]}),
            content_type="application/json")
        approved, plan = check_regeneration_ready(self.task)
        assert len(approved) == 2 and plan.plan_hash
        # and the candidates endpoint (the JS unlock condition) reflects it
        listing = self.client.get(
            f"/api/tasks/{self.task.pk}/concept_references/").json()
        assert sorted(listing["approved_ids"]) == sorted(r.pk for r in rows)

    def test_thumbnail_is_bounded_to_the_declared_root(self):
        row = ConceptReference.objects.create(
            task=self.task, source_type="MATERIAL_LIBRARY",
            library_item_id="materials:" + "d" * 60, title="escape",
            image_root="materials", image_path="../../etc/passwd")
        with override_settings(MATERIALS_ROOT="/tmp/nonexistent-root"):
            with self.assertRaises(AssertionError):
                reference_file_path(row)


# ---------------------------------------------------------------------------
# §BH60(b) — THE ORIGINAL ARTWORK IS WITHHELD FROM A REPRODUCTION RUN.
#
# Owner §BH60: the engine gets "a test with an answer" — reproduce a design the
# house has already made, and the deliverable is the measured distance. His (b):
# "IT DOES NOT GET THE ORIGINAL ARTWORK, in any form, at any stage. If the
# original is reachable from any reference the run can see, say so and exclude
# it by name."
#
# It IS reachable: a DesignReference row carries a `summary` describing the
# artwork and an `anatomy` holding the original's exact hex palette and its type
# hierarchy in prose, and `build_candidates` feeds the summary to the planner.
# ---------------------------------------------------------------------------


class WithheldReferenceTests(ConceptReferenceTestCase):

    def _project_withholding(self, ids):
        from apps.pipeline.models import DesignProject
        project = DesignProject.objects.create(
            brand=self.brand, created_by=self.user,
            metadata={"withheld_design_reference_ids": list(ids)})
        self.task.project = project
        self.task.save(update_fields=["project"])
        return project

    def _withheld_media(self):
        """A MEDIA_ROOT of this test's own, removed when the test ends. These tests once wrote fixed
        /tmp/bh60-withheld* folders that outlived every run."""
        import tempfile
        media = tempfile.mkdtemp(prefix="bh60-withheld-")
        self.addCleanup(shutil.rmtree, media, True)
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(override.disable)
        return media

    def test_a_withheld_reference_reaches_neither_the_record_nor_the_planner(self):
        media = self._withheld_media()
        rows = self._seed_references(media, count=4)
        target = rows[0]
        self._project_withholding([target.pk])
        candidates = build_candidates(self.task)
        ids = [c.library_item_id for c in candidates]
        self.assertNotIn("design_reference:%d" % target.pk, ids)
        # ...and the other three are untouched: withholding one design must not
        # starve the run of the house context the test exists to exercise
        for other in rows[1:]:
            self.assertIn("design_reference:%d" % other.pk, ids)
        # nothing was persisted for it either
        self.assertFalse(ConceptReference.objects.filter(
            task=self.task,
            library_item_id="design_reference:%d" % target.pk).exists())

    def test_withholding_nothing_is_the_ordinary_case_and_changes_nothing(self):
        media = self._withheld_media()
        rows = self._seed_references(media, count=3)
        before = [c.library_item_id for c in build_candidates(self.task)]
        self._project_withholding([])
        after = [c.library_item_id for c in build_candidates(self.task)]
        self.assertEqual(before, after)
        self.assertEqual(len(rows), 3)

    def test_a_withheld_reference_is_never_shown_to_the_creative_director_nor_the_prompt_engineer(self):
        """FOUND ON THE §BH65(d) RE-RUN, 2026-09-23. The Creative Director attaches the rows
        `select_reference_records` chooses as IMAGES, with their anatomy, to the call that writes the directions; ARIA
        hands the closest one's anatomy to the Prompt Engineer. §BH60's withholding reached the candidates and never
        this channel, and on task 89's run and task 90's the original itself was the first of four."""
        from apps.pipeline.services.reference_index import select_reference_records, select_references
        media = self._withheld_media()
        rows = self._seed_references(media, count=4)
        target = rows[0]
        # withholding nothing, the target is reachable here — which is the whole defect
        self.assertIn(target.pk, [r.pk for r in select_reference_records(self.task, 4)])
        self._project_withholding([target.pk])
        chosen = select_reference_records(self.task, 4)
        self.assertNotIn(target.pk, [r.pk for r in chosen])
        self.assertEqual({r.pk for r in chosen}, {r.pk for r in rows[1:]})   # the rest of the house stays
        self.assertFalse([p for p in select_references(self.task, 4) if p.endswith(target.image_path)])

    def test_the_same_artwork_in_another_library_is_withheld_with_it(self):
        """FB-2060 is DesignReference 15 AND the AI-design-library file `.../FB-2060 白卡.ai`, a candidate under its
        own `ai:` id. The link is the reference's own `source_file`, measured on the record — never its title."""
        from unittest import mock
        media = self._withheld_media()
        target = self._seed_references(media, count=2)[0]
        target.source_file = "FB-X 白卡.ai"
        target.save(update_fields=["source_file"])

        def ai_row(name):
            return {"source_type": "AI_DESIGN_LIBRARY", "library_item_id": "ai:" + name,
                    "title": name.rsplit(".", 1)[0], "description": "HISTORICAL_DESIGN native .ai source",
                    "relevance_reason": "matches product vocabulary", "retrieval_score": 5.0,
                    "ownership_status": "HOUSE_PRODUCTION_LINEAGE_UNCONFIRMED", "rights_status": "UNVERIFIED",
                    "is_vector": True, "image_root": "materials",
                    "image_path": "materials/historical AI production designs/" + name}

        with mock.patch("apps.pipeline.services.ai_style_profile.ai_design_candidates",
                        return_value=[ai_row("FB-X 白卡.ai"), ai_row("OTHER.ai")]):
            self._project_withholding([target.pk])
            ids = [c.library_item_id for c in build_candidates(self.task)]
            self.assertNotIn("ai:FB-X 白卡.ai", ids)
            self.assertIn("ai:OTHER.ai", ids)
            self.assertFalse(ConceptReference.objects.filter(task=self.task,
                                                             library_item_id="ai:FB-X 白卡.ai").exists())
            self._project_withholding([])                      # withholding nothing, it is a candidate like any other
            self.assertIn("ai:FB-X 白卡.ai", [c.library_item_id for c in build_candidates(self.task)])

    def test_the_withheld_list_is_read_from_the_projects_own_record(self):
        """§BH60(b): the exclusion is ON THE RECORD, named, not hidden in code.
        This module carries no target of its own — a reader sees WHICH design a
        run withheld by reading that run's project."""
        from apps.pipeline.services.concept_references import (
            WITHHELD_REFERENCE_IDS_KEY, withheld_reference_ids)
        self.assertEqual(withheld_reference_ids(self.task), set())
        self._project_withholding([15, "16", "not-an-id"])
        self.assertEqual(withheld_reference_ids(self.task), {15, 16})
        self.assertEqual(WITHHELD_REFERENCE_IDS_KEY, "withheld_design_reference_ids")
