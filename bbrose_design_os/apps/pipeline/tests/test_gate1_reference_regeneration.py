"""Reference-grounded Gate-1 regeneration (2A-6E §6–§10).

Pins: only user-approved concept references reach the provider; actual
reference IDs land in per-image provenance; a file that did not ship is
never reported as a visual reference; the influence plan survives the
Prompt Engineer; three variation prompts must differ materially before any
image spend; rejected images stay preserved; the Creative Director never
reruns and the direction selection never changes.
"""
from __future__ import annotations
from apps.pipeline.tests.quality_fixtures import critique, reviewed

import base64
import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from apps.core.models import Brand
from apps.pipeline.models import (
    ConceptInfluencePlan,
    ConceptReference,
    CreativeBrief,
    DesignTask,
    GeneratedImage,
)
from apps.pipeline.services.concept_references import (
    build_influence_plan,
    plan_hash,
)
from apps.pipeline.services.gate1_regeneration import (
    GateRegenerationError,
    check_regeneration_ready,
)
from apps.pipeline.variation_diversity import validate_variation_prompts

from .direction_fixtures import valid_document

DISTINCT_PROMPTS = [
    {"direction_name": "Editorial Soft Radiance",
     "full_prompt": "the BBROSE wordmark sits upper-left with authority; the "
                    "product name stacked lines of type offset to the right "
                    "side of the panel; an asymmetric vertical blush panel "
                    "band carries a refined micro-pattern of fine lines",
     "notes": "A"},
    {"direction_name": "Editorial Soft Radiance",
     "full_prompt": "the BBROSE wordmark placed upper-center; the product "
                    "name headline layered over one tonal background block "
                    "at the panel center; fine radiance lines form a contour "
                    "system across a pale sky blue gradient field",
     "notes": "B"},
    {"direction_name": "Editorial Soft Radiance",
     "full_prompt": "the BBROSE wordmark lower-left; the product name "
                    "headline in the upper-right; a sparse powder-particle "
                    "constellation of dots drifts from the lower-right "
                    "corner with a soft mint wash column",
     "notes": "C"},
]

REPETITIVE_PROMPTS = [
    {"direction_name": "d", "full_prompt":
        "the BBROSE wordmark upper-left; the product name stacked lines of "
        "type at the panel center; one hairline arc with tiny dots on an "
        "ivory field of color"} for _ in range(3)
]



def regen_payload(reference_ids, hash_value, break_diversity=False):
    """A valid gate1_reference_regeneration_prompts/1.0 payload."""
    def variation(vid, title, logo, name_zone, comp, color, motif):
        return {"variation_id": vid, "title": title,
                "prompt": ("a wide low-profile face-powder carton " * 10
                           + f"styled as {title} with {motif}"),
                "composition_signature": comp,
                "color_field_signature": color,
                "motif_signature": motif,
                "logo_zone": logo, "product_name_zone": name_zone,
                "decorative_coverage_pct": 15}
    variations = [
        variation("A_EDITORIAL_PANEL", "Editorial Panel", "upper-left",
                  "offset-right", "asymmetric vertical panel",
                  "blush panel on ivory", "micro-pattern fine lines"),
        variation("B_LAYERED_TYPE_FIELD", "Layered Type Field",
                  "upper-center", "center", "centered layered type field",
                  "sky blue tonal block", "radiance contour lines"),
        variation("C_POWDER_CONSTELLATION", "Powder Constellation",
                  "lower-left", "upper-right", "corner-led diagonal drift",
                  "peach and mint on warm ivory", "particle constellation"),
    ]
    if break_diversity:
        for v in variations:
            v.update({"composition_signature": "same", "logo_zone": "same",
                      "product_name_zone": "same",
                      "color_field_signature": "same",
                      "motif_signature": "same"})
    return {"schema_version": "gate1_reference_regeneration_prompts/1.0",
            "approved_reference_ids": sorted(reference_ids),
            "influence_plan_hash": hash_value,
            "variations": variations}

def _claude(payload):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


def _b64_response():
    data = MagicMock()
    data.url = None
    data.b64_json = base64.b64encode(b"fake png bytes").decode()
    response = MagicMock()
    response.data = [data]
    return response


class VariationDiversityTests(TestCase):
    def test_materially_different_prompts_pass(self):
        codes, _ = validate_variation_prompts(DISTINCT_PROMPTS,
                                              "product name")
        assert codes == []

    def test_repeated_layout_and_motif_fail(self):
        codes, _ = validate_variation_prompts(REPETITIVE_PROMPTS,
                                              "product name")
        assert "VARIATION_PROMPTS_NOT_DISTINCT" in codes

    def test_unreadable_prompts_fail_closed(self):
        codes, _ = validate_variation_prompts(
            [{"full_prompt": "x"}, {"full_prompt": "y"},
             {"full_prompt": "z"}], "name")
        assert "VARIATION_DIVERSITY_UNREADABLE" in codes


@override_settings(ANTHROPIC_API_KEY="test-key", OPENAI_API_KEY="test-key")
class RegenerationTestCase(TestCase):
    def setUp(self):
        # Exercise retained legacy internals only; Day1 tests verify real admission is closed.
        hold = patch('apps.pipeline.services.gate1_regeneration.ensure_reference_refresh_enabled')
        hold.start()
        self.addCleanup(hold.stop)
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, True)
        self.user = User.objects.create_superuser("rev", "r@r.com", "pw")
        self.brand = Brand.objects.create(name="BBROSE", master_brief="x")
        self.task = DesignTask.objects.create(
            brand=self.brand, task_text="Baked Powder carton",
            status="awaiting_gate_1", created_by=self.user)
        from apps.pipeline.design_intent import (
            build_design_brief, build_design_intent)
        raw = valid_document()
        document = build_design_intent(
            brief=build_design_brief({
                "brand": "BBROSE", "product_name": "Baked Powder",
                "product_category": "face powder",
                "design_target": "packaging"}),
            intent=raw["design_intent"], directions=raw["directions"])
        self.brief = CreativeBrief.objects.create(
            task=self.task,
            design_intent={k: v for k, v in document.items()
                           if k != "directions"},
            directions=document["directions"],
            selected_direction_id=document["directions"][0]["direction_id"])
        self.old_images = [GeneratedImage.objects.create(
            task=self.task, direction_name="Editorial Soft Radiance",
            prompt_used=f"old {n}", variation_number=n) for n in (1, 2, 3)]

    def _approve_references(self, count=2):
        rows = []
        for index in range(count):
            path = Path(self.media) / f"concept{index}.png"
            path.write_bytes(b"\x89PNG concept")
            rows.append(ConceptReference.objects.create(
                task=self.task, source_type="HISTORICAL_DESIGN_REFERENCE",
                library_item_id=f"design_reference:{index}",
                title=f"gold editorial reference {index}",
                image_root="media", image_path=f"concept{index}.png",
                permission_status=ConceptReference.PERMISSION_APPROVED,
                approved_by=self.user))
        plan = build_influence_plan(self.task, rows)
        ConceptInfluencePlan.objects.create(
            task=self.task, plan=plan, plan_hash=plan_hash(plan),
            created_by=self.user)
        return rows


class ReadinessTests(RegenerationTestCase):
    def test_refuses_without_approved_references(self):
        with self.assertRaises(GateRegenerationError) as ctx:
            check_regeneration_ready(self.task)
        assert ctx.exception.code == "REGEN_NO_APPROVED_REFERENCES"

    def test_refuses_outside_gate1(self):
        self.task.status = "failed"
        self.task.save()
        with self.assertRaises(GateRegenerationError) as ctx:
            check_regeneration_ready(self.task)
        assert ctx.exception.code == "REGEN_NOT_AT_GATE1"

    def test_ready_with_approvals_and_plan(self):
        with override_settings(MEDIA_ROOT=self.media):
            self._approve_references()
            approved, plan = check_regeneration_ready(self.task)
        assert len(approved) == 2
        assert plan.plan["production_use_granted"] is False


class InfluenceSurvivalTests(RegenerationTestCase):
    @patch("apps.pipeline.agents.prompt_engineer.call_claude")
    def test_influence_plan_survives_prompt_engineer(self, mock_pe):
        from apps.pipeline.agents.prompt_engineer import PromptEngineerAgent
        mock_pe.return_value = _claude({"prompts": DISTINCT_PROMPTS})
        with override_settings(MEDIA_ROOT=self.media):
            rows = self._approve_references()
        plan = ConceptInfluencePlan.objects.get(task=self.task).plan
        PromptEngineerAgent([self.brief.directions[0]], None,
                            variation_mode=True, influence_plan=plan).run()
        sent = mock_pe.call_args.args[1]
        assert "Approved material references (concept influence ONLY)" in sent
        assert "material_influence_plan/1.0" in sent
        assert "copy the same layout" in sent
        assert str(rows[0].pk) in sent   # reference_id reaches the model


class FullRegenerationTests(RegenerationTestCase):
    def _run(self, payloads):
        """payloads: list of dicts (or callables producing dicts) returned by
        the gate1_prompts transport per attempt."""
        from apps.pipeline.agents.aria import ARIAAgent
        with override_settings(MEDIA_ROOT=self.media,
                               IMAGE_MODEL="gpt-image-1",
                               BRAND_LOGO_PATH=""):
            self.rows = self._approve_references()
            responses = [
                _claude(p(self) if callable(p) else p) for p in payloads]
            with patch("apps.pipeline.agents.creative_director.call_claude") \
                    as mock_cd, \
                    patch("apps.pipeline.services.claude_service.call_claude",
                          side_effect=responses) as mock_pe, \
                    patch("apps.pipeline.agents.image_producer.openai.images"
                          ".edit", return_value=_b64_response()) as mock_edit, \
                    patch("apps.pipeline.agents.image_producer.openai.images"
                          ".generate") as mock_gen, \
                    patch("apps.pipeline.agents.qa_reviewer.call_claude",
                          return_value=_claude(critique(8))):
                ARIAAgent(self.task.pk).regenerate_gate1_with_references()
        self.task.refresh_from_db()
        return mock_cd, mock_pe, mock_edit, mock_gen

    def _valid_payload(self, break_diversity=False):
        plan = ConceptInfluencePlan.objects.get(task=self.task)
        return regen_payload(
            [r.pk for r in self.rows] if hasattr(self, "rows") else [],
            plan.plan_hash, break_diversity=break_diversity)

    def test_full_regeneration_with_provenance(self):
        mock_cd, mock_pe, mock_edit, mock_gen = self._run(
            [lambda t: t._valid_payload()])
        # no Creative Director rerun, no direction-selection change
        mock_cd.assert_not_called()
        self.brief.refresh_from_db()
        assert self.brief.selected_direction_id == \
            self.brief.directions[0]["direction_id"]
        assert self.task.status == "awaiting_gate_1"
        # approved concept files actually reached the provider
        mock_gen.assert_not_called()
        kwargs = mock_edit.call_args.kwargs
        assert len(kwargs["image"]) == 2      # the two approved references
        assert "USER-APPROVED CONCEPT REFERENCES" in kwargs["prompt"]
        # per-image provenance records exactly what shipped
        new_images = GeneratedImage.objects.filter(
            task=self.task, superseded=False).exclude(
            pk__in=[i.pk for i in self.old_images])
        assert new_images.count() == 3
        identities = set()
        for image in new_images:
            provenance = image.reference_provenance
            assert sorted(provenance["concept_reference_ids"]) == \
                sorted(r.pk for r in self.rows)
            assert len(provenance["visual_files_passed"]) == 2
            assert provenance["influence_plan_hash"] == \
                ConceptInfluencePlan.objects.get(task=self.task).plan_hash
            identities.add(provenance["variation_identity"])
        assert identities == {"A_EDITORIAL_PANEL", "B_LAYERED_TYPE_FIELD",
                              "C_POWDER_CONSTELLATION"}
        # the replaced images are preserved, superseded, never deleted
        for old in self.old_images:
            old.refresh_from_db()
            assert old.pk and old.superseded

    def test_missing_approved_file_blocks_the_spend(self):
        # 2B-3V §3: a missing approved-reference file BLOCKS pre-spend — the
        # provider is never called (no partial spend on the surviving file),
        # and the block is recorded honestly.
        with override_settings(MEDIA_ROOT=self.media):
            self._approve_references()
        (Path(self.media) / "concept0.png").unlink()   # after approval
        from apps.pipeline.agents.image_producer import ImageProducerAgent
        from apps.pipeline.models import AgentLog
        with override_settings(MEDIA_ROOT=self.media,
                               IMAGE_MODEL="gpt-image-1", BRAND_LOGO_PATH=""):
            with patch("apps.pipeline.agents.image_producer.openai.images"
                       ".edit") as mock_edit, \
                    patch("apps.pipeline.agents.image_producer.openai.images"
                          ".generate") as mock_gen:
                images = ImageProducerAgent(
                    self.task, [DISTINCT_PROMPTS[0]], require_visual=True).run()
        assert images == []
        mock_edit.assert_not_called()
        mock_gen.assert_not_called()
        log = (AgentLog.objects.filter(task=self.task,
                                       action__icontains="pre-spend")
               .order_by("-id").first())
        assert "APPROVED_REFERENCE_FILE_MISSING" in log.action

    def test_repetitive_prompts_are_drawn_after_their_one_retry_with_a_note(self):
        """[Re-pinned by his test blocker on design 123, 2026-10-09 (transcribed at ea2b98b), (2): "Every "not distinct"
        check: it never stops a design. On failure it retries once with the reason; if it still fails, it shows me the
        three anyway with a note, and I choose."] Repetitive twice: drawn, its record carrying the codes, and the page's
        note says so in words. (A redraw refused on another check still draws nothing:
        test_his_final_goal_b4_a_redraw_bound_to_other_directions_draws_nothing.)"""
        from apps.dashboard.words import alike_words
        mock_cd, mock_pe, mock_edit, mock_gen = self._run(
            [lambda t: t._valid_payload(break_diversity=True),
             lambda t: t._valid_payload(break_diversity=True)])
        assert mock_pe.call_count == 2        # one bounded repair, with the reason
        assert mock_edit.call_count == 3      # drawn anyway
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"
        assert not self.task.error_message
        assert alike_words(self.task) == [
            "Shown anyway: the instructions for the three concept pictures came back too alike twice — the three "
            "concepts were too alike; made once more with that reason, they did not change. You choose."]

    def test_repair_pass_recovers_diversity(self):
        mock_cd, mock_pe, mock_edit, _ = self._run(
            [lambda t: t._valid_payload(break_diversity=True),
             lambda t: t._valid_payload()])
        assert mock_pe.call_count == 2
        assert self.task.status == "awaiting_gate_1"
        assert mock_edit.call_count == 3

    def test_the_trend_boards_words_reach_the_redrawn_concepts_and_never_a_picture(self):
        """§BH71 PART 2: concepts drawn again with approved references take the trend board's ticked pictures as their
        words too, quoted as data, after his own pictures' — never an unticked one's, a title, a link or a picture."""
        from apps.pipeline.models import InspirationReading, TrendBoard, TrendPick
        board = TrendBoard.objects.create(task=self.task, status=TrendBoard.CONFIRMED, subject="cosmetic packaging",
                                          confirmed_how="his click")
        kept = []
        for n in (1, 2):
            sha = ("%x" % (self.task.id * 32 + n)).rjust(64, "0")
            InspirationReading.objects.create(sha256=sha, reading={
                "layout": "", "mood": "", "finish": "", "type_style": "", "colour_words": "",
                "take": "a redrawn trend take %d" % n, "seen_not_taken": ["ACME"]})
            kept.append(TrendPick.objects.create(board=board, number=n, kind=TrendPick.PICTURE, platform="dribbble",
                                                 page_url="https://dribbble.com/shots/%d" % n, title="ACME",
                                                 image_url="https://cdn.dribbble.com/%d.png" % n, sha256=sha,
                                                 used=n == 1))
        board.used_at_confirm = [kept[0].pk]
        board.save()
        mock_cd, mock_pe, mock_edit, mock_gen = self._run([lambda t: t._valid_payload()])
        message = mock_pe.call_args_list[0].args[1]
        assert "<<trends>>" in message and "a redrawn trend take 1" in message
        for never in ("a redrawn trend take 2", "ACME", "dribbble.com"):
            assert never not in message, never
        assert len(mock_edit.call_args.kwargs["image"]) == 2          # the two approved references, never a picture

    def test_an_inspiration_pictures_words_reach_the_redrawn_concepts_and_the_picture_does_not(self):
        """§BH69(2): "The directions and concepts use what it read." Drawing the concepts again with approved references
        takes the design's inspiration pictures as their words, quoted as data — what was seen and never taken, the
        picture's name and its bytes stay out, and only the approved references are attached."""
        from django.core.files.base import ContentFile

        from apps.pipeline.models import InspirationReading, TaskReference
        from apps.pipeline.services import inspiration
        picture = b"\x89PNG\r\n\x1a\n" + b"\x07" * 48
        with override_settings(MEDIA_ROOT=self.media):
            ref = TaskReference(task=self.task, kind=inspiration.KIND, original_filename="secret-pin-name.png",
                                media_type="image/png", file_size=len(picture), sha256=inspiration.sha256_of(picture))
            ref.image.save("secret-pin-name.png", ContentFile(picture), save=True)
        InspirationReading.objects.create(sha256=ref.sha256, reading={
            "layout": "one mark centred on a quiet field", "mood": "calm", "finish": "soft-touch matte",
            "type_style": "thin serif capitals", "colour_words": "blush and warm gold",
            "take": "quiet space around one gold line", "seen_not_taken": ["LUMIERE PARIS"]})
        mock_cd, mock_pe, mock_edit, mock_gen = self._run([lambda t: t._valid_payload()])
        message = mock_pe.call_args_list[0].args[1]
        assert "quiet space around one gold line" in message
        assert "<<inspiration>>" in message and "<<end inspiration>>" in message
        for never in ("LUMIERE PARIS", "secret-pin-name", "task_refs/"):
            assert never not in message, never
        assert len(mock_edit.call_args.kwargs["image"]) == 2          # the two approved references, never the picture


class RegenerationJobTests(RegenerationTestCase):
    """2A-6E-CORR-2 §4/§5/§6: the click's lifecycle is one pollable job."""

    def _request(self):
        from apps.pipeline.services.gate1_regeneration import (
            request_gate1_regeneration)
        with patch("apps.pipeline.tasks.regenerate_gate1_references.delay") \
                as mock_delay:
            mock_delay.return_value = MagicMock(id="celery-abc")
            with self.captureOnCommitCallbacks(execute=True):
                result = request_gate1_regeneration(self.task, self.user)
        return result, mock_delay

    def test_request_creates_one_bound_job_and_enqueues_once(self):
        from apps.pipeline.models import Gate1RegenerationJob
        with override_settings(MEDIA_ROOT=self.media):
            rows = self._approve_references()
        result, mock_delay = self._request()
        assert result["accepted"] is True
        job = Gate1RegenerationJob.objects.get(pk=result["job_id"])
        assert job.task_id == self.task.pk
        assert job.direction_id == self.brief.selected_direction_id
        assert sorted(job.approved_reference_ids) == \
            sorted(r.pk for r in rows)
        assert job.influence_plan_hash == \
            ConceptInfluencePlan.objects.get(task=self.task).plan_hash
        assert job.variation_identities == [
            "A_EDITORIAL_PANEL", "B_LAYERED_TYPE_FIELD",
            "C_POWDER_CONSTELLATION"]
        assert mock_delay.call_count == 1
        assert mock_delay.call_args.args == (job.pk,)
        job.refresh_from_db()
        assert job.celery_task_id == "celery-abc"

    def test_duplicate_clicks_return_the_same_active_job(self):
        from apps.pipeline.models import Gate1RegenerationJob
        with override_settings(MEDIA_ROOT=self.media):
            self._approve_references()
        first, mock_delay_1 = self._request()
        self.task.refresh_from_db()
        second, mock_delay_2 = self._request()
        assert second["job_id"] == first["job_id"]
        assert second["already_active"] is True
        assert mock_delay_2.call_count == 0        # no duplicate enqueue
        assert Gate1RegenerationJob.objects.filter(task=self.task).count() == 1

    def test_missing_reference_file_fails_job_with_zero_provider_calls(self):
        from pathlib import Path
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import Gate1RegenerationJob
        with override_settings(MEDIA_ROOT=self.media):
            self._approve_references()
        result, _ = self._request()
        (Path(self.media) / "concept0.png").unlink()
        with override_settings(MEDIA_ROOT=self.media,
                               IMAGE_MODEL="gpt-image-1", BRAND_LOGO_PATH=""):
            with patch("apps.pipeline.agents.prompt_engineer.call_claude") \
                    as mock_pe, \
                    patch("apps.pipeline.agents.image_producer.openai.images"
                          ".edit") as mock_edit, \
                    patch("apps.pipeline.agents.image_producer.openai.images"
                          ".generate") as mock_gen:
                ARIAAgent(self.task.pk).regenerate_gate1_with_references(
                    job_id=result["job_id"])
        job = Gate1RegenerationJob.objects.get(pk=result["job_id"])
        assert job.status == "failed"
        assert "missing on disk" in job.error
        mock_pe.assert_not_called()
        mock_edit.assert_not_called()
        mock_gen.assert_not_called()

    def test_changed_approval_set_fails_the_stale_job(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import Gate1RegenerationJob
        with override_settings(MEDIA_ROOT=self.media):
            rows = self._approve_references(count=3)
        result, _ = self._request()
        # demote one of three: the remaining two still clear the count
        # floor, but no longer match the set the job was bound to
        rows[0].permission_status = ConceptReference.PERMISSION_CANDIDATE
        rows[0].save()
        with override_settings(MEDIA_ROOT=self.media):
            with patch("apps.pipeline.agents.image_producer.openai.images"
                       ".edit") as mock_edit:
                ARIAAgent(self.task.pk).regenerate_gate1_with_references(
                    job_id=result["job_id"])
        job = Gate1RegenerationJob.objects.get(pk=result["job_id"])
        assert job.status == "failed"
        assert "changed since" in job.error
        mock_edit.assert_not_called()

    def test_completed_job_produces_three_images_with_provenance(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import Gate1RegenerationJob
        with override_settings(MEDIA_ROOT=self.media):
            rows = self._approve_references()
        result, _ = self._request()
        plan = ConceptInfluencePlan.objects.get(task=self.task)
        payload = regen_payload([r.pk for r in rows], plan.plan_hash)
        with override_settings(MEDIA_ROOT=self.media,
                               IMAGE_MODEL="gpt-image-1", BRAND_LOGO_PATH=""):
            with patch("apps.pipeline.agents.creative_director.call_claude") \
                    as mock_cd, \
                    patch("apps.pipeline.services.claude_service.call_claude",
                          return_value=_claude(payload)), \
                    patch("apps.pipeline.agents.image_producer.openai.images"
                          ".edit", return_value=_b64_response()), \
                    patch("apps.pipeline.agents.qa_reviewer.call_claude",
                          return_value=_claude(critique(8))):
                ARIAAgent(self.task.pk).regenerate_gate1_with_references(
                    job_id=result["job_id"])
        mock_cd.assert_not_called()                 # Creative Director never
        job = Gate1RegenerationJob.objects.get(pk=result["job_id"])
        assert job.status == "completed" and job.finished_at
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_gate_1"
        new_images = GeneratedImage.objects.filter(
            task=self.task, superseded=False).exclude(
            pk__in=[i.pk for i in self.old_images])
        assert new_images.count() == 3
        for image in new_images:
            assert sorted(image.reference_provenance
                          ["concept_reference_ids"]) == \
                sorted(r.pk for r in rows)
        for old in self.old_images:                  # preserved, superseded
            old.refresh_from_db()
            assert old.pk and old.superseded

    def _b4_redraw(self, bind):
        """[His final goal, 2026-10-05, B4] at Gate 1 before he picks: the redraw asked for, then run."""
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import Gate1RegenerationJob
        CreativeBrief.objects.filter(pk=self.brief.pk).update(selected_direction_id="")
        with override_settings(MEDIA_ROOT=self.media):
            rows = self._approve_references()
        result, _ = self._request()
        plan = ConceptInfluencePlan.objects.get(task=self.task)
        payload = regen_payload([r.pk for r in rows], plan.plan_hash)
        if bind:
            # [his test findings on design 121, 2026-10-07, item 1] "wrong": each variation names ANOTHER direction
            ids = [d["direction_id"] for d in self.brief.directions]
            for v, d in zip(payload["variations"], ids[1:] + ids[:1] if bind == "wrong" else ids):
                v["direction_id"] = d
        sent = []

        def answer(*a, **k):
            sent.append(a[1] if len(a) > 1 else k.get("user_message", ""))
            return _claude(payload)
        with override_settings(MEDIA_ROOT=self.media, IMAGE_MODEL="gpt-image-1", BRAND_LOGO_PATH=""):
            with patch("apps.pipeline.agents.creative_director.call_claude") as mock_cd, \
                    patch("apps.pipeline.services.claude_service.call_claude", side_effect=answer), \
                    patch("apps.pipeline.agents.image_producer.openai.images.edit",
                          return_value=_b64_response()) as mock_edit, \
                    patch("apps.pipeline.agents.qa_reviewer.call_claude",
                          return_value=_claude(critique(8))):
                ARIAAgent(self.task.pk).regenerate_gate1_with_references(job_id=result["job_id"])
        mock_cd.assert_not_called()
        return Gate1RegenerationJob.objects.get(pk=result["job_id"]), sent, mock_edit

    def test_his_final_goal_b4_before_a_pick_the_redraw_draws_the_three_directions_one_each(self):
        """[His final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away ... He picks a
        picture."] No direction is chosen before he picks a picture: the references redraw draws the three planned
        directions again, one picture each, bound to its direction by id, grounded in his references."""
        job, sent, mock_edit = self._b4_redraw(bind=True)
        assert job.direction_id == "" and job.status == "completed", (job.status, job.error)
        assert "The three creative directions" in sent[0] and "ONE variation for each" in sent[0]
        fresh = GeneratedImage.objects.filter(task=self.task, superseded=False).exclude(
            pk__in=[i.pk for i in self.old_images]).order_by("pk")
        assert [i.direction_id for i in fresh] == [d["direction_id"] for d in self.brief.directions]
        assert mock_edit.call_count == 3
        self.brief.refresh_from_db()
        assert self.brief.selected_direction_id == ""                     # still his to pick

    def test_his_final_goal_b4_a_redraw_bound_to_other_directions_draws_nothing(self):
        """[His test findings on design 121, 2026-10-07, item 1: "Make them agree, so a design can never stop here
        again."] variations that leave their directions' ids out are bound by their slots and drawn (the test above's
        bind=False, which drew nothing here until the two id rules agreed); variations that name ANOTHER direction drew
        nothing, refused by name — until [Re-pinned by his goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 1: "NO planner check ever stops a design (not only "not distinct"): on failure it retries once with the reason; if it still fails, it shows me the three directions with a plain note, and I choose. Apply this to every planner and concept check."] Now asked once more with why, then drawn bound to
        the directions by their slots."""
        job, sent, mock_edit = self._b4_redraw(bind="wrong")
        assert job.status == "completed", (job.status, job.error)
        assert len(sent) == 2 and mock_edit.call_count == 3
        fresh = GeneratedImage.objects.filter(task=self.task, superseded=False).exclude(
            pk__in=[i.pk for i in self.old_images]).order_by("pk")
        assert [i.direction_id for i in fresh] == [d["direction_id"] for d in self.brief.directions]

    def test_his_test_findings_121_a_redraw_that_leaves_its_ids_out_is_bound_by_its_slots(self):
        job, _sent, mock_edit = self._b4_redraw(bind=False)
        assert job.status == "completed", (job.status, job.error)
        assert mock_edit.call_count == 3
        fresh = GeneratedImage.objects.filter(task=self.task, superseded=False).exclude(
            pk__in=[i.pk for i in self.old_images]).order_by("pk")
        assert [i.direction_id for i in fresh] == [d["direction_id"] for d in self.brief.directions]

    def test_duplicate_worker_delivery_is_ignored(self):
        from apps.pipeline.agents.aria import ARIAAgent
        from apps.pipeline.models import Gate1RegenerationJob
        with override_settings(MEDIA_ROOT=self.media):
            self._approve_references()
        result, _ = self._request()
        Gate1RegenerationJob.objects.filter(pk=result["job_id"]).update(
            status="completed")
        with patch("apps.pipeline.agents.prompt_engineer.call_claude") \
                as mock_pe:
            ARIAAgent(self.task.pk).regenerate_gate1_with_references(
                job_id=result["job_id"])
        mock_pe.assert_not_called()

    def test_worker_task_is_registered(self):
        from config.celery import app
        assert "apps.pipeline.tasks.regenerate_gate1_references" in app.tasks
