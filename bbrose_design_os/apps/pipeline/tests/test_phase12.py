"""Phase 12 tests — cost ledger & budget controls (Milestone 12.2)."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings

from apps.core.models import Brand
from apps.pipeline.models import ApiCallRecord, DesignTask, GeneratedImage
from apps.pipeline.permissions import ROLE_DESIGNER
from apps.pipeline.services import cost_ledger
from apps.pipeline.services.cost_ledger import (
    BudgetExceededError,
    claude_cost_usd,
    daily_budget_exceeded,
    day_cost_usd,
    record_claude,
    record_image,
    task_cost_context,
    task_cost_usd,
)

_PRICES = {"claude-sonnet-4-6": (0.003, 0.015), "claude-opus-4-7": (0.015, 0.075)}


# §BH57(a)3: NO brand logo for these — they never meant to have one. The default BRAND_LOGO_PATH resolves
# to the REAL media/brand/logo.png, which these tests were silently reading; a lone logo now reaches the
# provider, so that accident would change their branch. This is what they always assumed.
@override_settings(BRAND_LOGO_PATH="/nonexistent/bh57/no-logo.png")
class LedgerBase(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="running", brand=self.brand,
        )


@override_settings(CLAUDE_PRICES=_PRICES, CLAUDE_PRICE_DEFAULT=(0.003, 0.015))
class TestCostComputation(LedgerBase):
    def test_claude_cost(self):
        # 1000 in @ .003 + 2000 out @ .015/1k = .003 + .030 = .033
        assert claude_cost_usd("claude-sonnet-4-6", 1000, 2000) == Decimal("0.033000")

    def test_unknown_model_uses_default(self):
        assert claude_cost_usd("mystery-model", 1000, 0) == Decimal("0.003000")

    def test_record_claude_writes_row_in_context(self):
        resp = MagicMock()
        resp.usage.input_tokens = 1000
        resp.usage.output_tokens = 1000
        with task_cost_context(self.task):
            rec = record_claude(resp, "claude-sonnet-4-6", operation="cd")
        assert rec is not None
        assert rec.provider == "anthropic"
        assert rec.operation == "cd"
        assert rec.cost_usd == Decimal("0.018000")
        assert task_cost_usd(self.task) == Decimal("0.018000")

    def test_record_claude_noop_without_task(self):
        resp = MagicMock()
        resp.usage.input_tokens = 10
        resp.usage.output_tokens = 10
        assert record_claude(resp, "claude-sonnet-4-6") is None
        assert ApiCallRecord.objects.count() == 0

    @override_settings(IMAGE_PRICE_PER_IMAGE=0.12)
    def test_record_image(self):
        rec = record_image("dall-e-3", task=self.task)
        assert rec.provider == "openai"
        assert rec.image_count == 1
        assert rec.cost_usd == Decimal("0.120000")


@override_settings(CLAUDE_PRICES=_PRICES, MAX_COST_PER_TASK=0.05)
class TestPerTaskBudget(LedgerBase):
    def _record(self, out_tokens):
        resp = MagicMock()
        resp.usage.input_tokens = 0
        resp.usage.output_tokens = out_tokens
        with task_cost_context(self.task):
            return record_claude(resp, "claude-opus-4-7", operation="x")

    def test_under_cap_ok(self):
        self._record(500)  # 500/1k * .075 = .0375 < .05
        assert task_cost_usd(self.task) < Decimal("0.05")

    def test_paid_response_is_recorded_before_next_call_is_blocked(self):
        self._record(1000)
        assert ApiCallRecord.objects.count() == 1
        from apps.pipeline.services.cost_ledger import check_task_budget
        with self.assertRaises(BudgetExceededError):
            check_task_budget(self.task)

    @override_settings(MAX_COST_PER_TASK=0)
    def test_zero_cap_disables_guard(self):
        self._record(100000)  # would be huge, but cap disabled
        assert ApiCallRecord.objects.count() == 1


@override_settings(MAX_COST_PER_DAY=1.0)
class TestDailyBudget(LedgerBase):
    def _spend(self, amount):
        ApiCallRecord.objects.create(
            task=self.task, provider="openai", model="dall-e-3",
            image_count=1, cost_usd=Decimal(str(amount)),
        )

    def test_calendar_day_reservations_are_separate_from_historical_task_rows(self):
        from apps.pipeline.services.spend_reservation import reserve
        self._spend(30)
        assert not daily_budget_exceeded()  # historical calls are not new rescue spend
        reserve('openai', 'fixture', 'gpt-image-2', 25)
        assert daily_budget_exceeded()


class TestTaskCreateDailyCap(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d", "d@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    @patch("apps.core.health.worker_available", return_value=True)
    @patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=True)
    def test_create_blocked_429(self, _budget, _worker):
        resp = self.client.post(
            "/api/tasks/create/", {"task_text": "make a box", "design_target": "packaging"},
        )
        assert resp.status_code == 429

    @patch("apps.core.health.worker_available", return_value=True)
    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    @patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=False)
    def test_create_allowed_under_cap(self, _budget, _delay, _worker):
        resp = self.client.post(
            "/api/tasks/create/", {"task_text": "make a box", "design_target": "packaging"},
        )
        assert resp.status_code == 201


class LibraryBase(TestCase):
    def setUp(self):
        from apps.core.models import Product
        from apps.pipeline.models import GeneratedImage, PackagingOutput

        self.brand = Brand.objects.create(name="Brand A", master_brief="x")
        self.other_brand = Brand.objects.create(name="Brand B", master_brief="y")
        self.product = Product.objects.create(
            brand=self.brand, product_id="BBR-CO-1", name="Rose Serum",
            category="CO", year=2026,
        )
        # Team-member boundary (hardening 2026-07-04): read endpoints require
        # a role, so the library user is a Designer.
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("u", "u@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

        # A finished (final-approved) output = a library item.
        self.task = DesignTask.objects.create(
            task_text="luxe rose serum carton", status="completed",
            brand=self.brand, product=self.product,
        )
        self.image = GeneratedImage.objects.create(
            task=self.task, direction_name="d", prompt_used="p", image_url="u",
        )
        self.output = PackagingOutput.objects.create(
            task=self.task, approved_image=self.image,
            spec_sheet={"dimensions": {"width_mm": 28}}, is_final_approved=True,
        )
        # A non-final output must NOT appear in the library.
        self.draft_task = DesignTask.objects.create(
            task_text="draft only", status="running", brand=self.brand,
        )
        self.draft_img = GeneratedImage.objects.create(
            task=self.draft_task, direction_name="d", prompt_used="p", image_url="u",
        )
        PackagingOutput.objects.create(
            task=self.draft_task, approved_image=self.draft_img,
            spec_sheet={}, is_final_approved=False,
        )


class TestLibrary(LibraryBase):
    """[The clean-up of 2026-10-04 (E10b): the old /api/library/ list, detail and reuse doors, which no page
    called, are removed with their nine tests; the Library's own pages carry the filters, the approvals in words
    and each finished design's page, and their tests are in apps/core/tests.py. The role boundary stays here.]"""

    def test_roleless_account_gets_403(self):
        # Hardening 2026-07-04: an authenticated account with NO role must not
        # see team work (future client logins / stale invites).
        nobody = User.objects.create_user("nobody", "n@t.com", "pw")
        self.client.force_login(nobody)
        assert self.client.get("/api/tasks/").status_code == 403


class TestNotifications(TestCase):
    def setUp(self):
        from apps.pipeline.permissions import ROLE_REVIEWER
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.owner = User.objects.create_user("owner", "owner@t.com", "pw")
        reviewer_group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        self.reviewer = User.objects.create_user("rev", "rev@t.com", "pw")
        self.reviewer.groups.add(reviewer_group)

    def _task(self, status="queued"):
        return DesignTask.objects.create(
            task_text="t", status=status, brand=self.brand, created_by=self.owner,
        )

    def test_gate_status_notifies_owner_and_reviewers(self):
        from django.core import mail
        from apps.pipeline.models import Notification

        task = self._task()  # created 'queued' — not a notify status
        assert Notification.objects.count() == 0

        task.status = "awaiting_gate_1"
        task.save()

        recipients = set(
            Notification.objects.filter(kind="awaiting_gate_1")
            .values_list("recipient__username", flat=True)
        )
        assert recipients == {"owner", "rev"}
        # Email to both (console backend captures to mail.outbox).
        assert len(mail.outbox) == 1
        assert set(mail.outbox[0].to) == {"owner@t.com", "rev@t.com"}

    def test_every_step_that_waits_on_a_person_is_told(self):
        # §BH55 Phase 3 (survey rows 6.25, 7.8): three gates were told; a design reaching its direction step, its
        # container's shape, its structure step, its design intent or a held set-up said nothing to anyone
        from apps.pipeline.models import Notification
        for status, words in (("awaiting_direction_selection", "choose a direction"),
                              ("awaiting_gate1_generation_configuration", "set up the concept renders"),
                              ("awaiting_container_profile", "confirm the shape"),
                              ("awaiting_design_intent_confirmation", "confirm the design intent")):
            task = self._task()
            task.status = status
            task.save()
            rows = Notification.objects.filter(task=task, kind=status)
            assert {n.message for n in rows} == {f"Design #{task.id}: {words}"}, (status, list(rows))
            # a reviewer hears it too — every waiting step is one a reviewer may act on
            assert set(rows.values_list("recipient__username", flat=True)) == {"owner", "rev"}, status

    def test_the_bell_and_the_email_speak_a_designers_words_and_open_the_design(self):
        # §BH55 Phase 3: they read "Task #53 is awaiting Gate 1 review", and the email linked /dashboard/?task=<id>,
        # which opens the home and no design
        from django.core import mail
        from apps.pipeline.models import Notification
        task = self._task()
        task.status = "awaiting_gate_1"
        task.save()
        assert {n.message for n in Notification.objects.filter(task=task)} == {f"Design #{task.id}: choose a concept"}
        body = mail.outbox[0].body
        assert f"/dashboard/designs/{task.id}/" in body and "?task=" not in body and "Open the design" in body

    def test_failed_notifies_owner_only(self):
        from apps.pipeline.models import Notification
        task = self._task()
        task.status = "failed"
        task.save()
        recipients = set(
            Notification.objects.filter(kind="failed")
            .values_list("recipient__username", flat=True)
        )
        assert recipients == {"owner"}

    def test_no_duplicate_on_unrelated_save(self):
        from apps.pipeline.models import Notification
        task = self._task("awaiting_gate_1")  # fires once on create
        assert Notification.objects.filter(kind="awaiting_gate_1").count() == 2  # owner+rev
        task.gate_1_notes = "please brighten"
        task.save(update_fields=["gate_1_notes"])  # status unchanged → no new notifies
        assert Notification.objects.filter(kind="awaiting_gate_1").count() == 2

    def test_preference_mutes_in_app(self):
        from apps.pipeline.models import Notification, NotificationPreference
        NotificationPreference.objects.create(user=self.owner, in_app=False, email=True)
        task = self._task()
        task.status = "completed"
        task.save()
        # Owner muted in-app → no row for owner (completed only targets owner).
        assert not Notification.objects.filter(recipient=self.owner).exists()

    def test_bell_api_and_mark_read(self):
        self.client.force_login(self.owner)
        task = self._task()
        task.status = "completed"
        task.save()
        body = self.client.get("/api/notifications/").json()
        assert body["unread_count"] == 1
        assert len(body["notifications"]) == 1
        self.client.post("/api/notifications/mark_read/", {})
        assert self.client.get("/api/notifications/").json()["unread_count"] == 0

    def test_preferences_api(self):
        self.client.force_login(self.owner)
        assert self.client.get("/api/notifications/preferences/").json()["email"] is True
        resp = self.client.put(
            "/api/notifications/preferences/",
            data='{"email": false}', content_type="application/json",
        )
        assert resp.json()["email"] is False


@override_settings(BRAND_LOGO_PATH="/nonexistent/bh57/no-logo.png")
class TestImageProducerResponseShapes(TestCase):
    """The gpt-image family returns base64; dall-e returns an expiring URL.
    The producer must save a durable local copy from either shape."""

    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.task = DesignTask.objects.create(
            task_text="t", status="running", brand=self.brand)
        self.prompts = [{"direction_name": "d1", "full_prompt": "p1"}]

    def _run_with(self, data_obj):
        from apps.pipeline.agents.image_producer import ImageProducerAgent
        fake = MagicMock()
        fake.data = [data_obj]
        with patch("apps.pipeline.agents.image_producer.openai.images.generate",
                   return_value=fake):
            return ImageProducerAgent(self.task, self.prompts).run()

    def test_b64_response_saves_file_without_download(self):
        import base64 as b64mod
        data = MagicMock(spec=[])  # no attributes unless set
        data.b64_json = b64mod.b64encode(b"PNGBYTES").decode()
        with patch("apps.pipeline.services.round_calls.download_image_bytes") as dl:
            imgs = self._run_with(data)
        assert len(imgs) == 1
        assert imgs[0].image_file          # durable copy exists
        assert not imgs[0].download_failed
        assert imgs[0].image_url == ""     # no provider URL in this shape
        dl.assert_not_called()             # nothing to download

    def test_url_response_still_downloads(self):
        data = MagicMock(spec=[])
        data.url = "https://provider.example/signed.png"
        with patch("apps.pipeline.services.round_calls.download_image_bytes",
                   return_value=b"PNGBYTES") as dl:
            imgs = self._run_with(data)
        assert len(imgs) == 1
        assert imgs[0].image_file
        dl.assert_called_once()

    def test_neither_shape_marks_failed(self):
        data = MagicMock(spec=[])   # neither url nor b64_json
        imgs = self._run_with(data)
        assert len(imgs) == 1
        assert imgs[0].download_failed

    def test_provider_billing_limit_fails_fast_with_actionable_message(self):
        import pytest
        from apps.pipeline.agents.image_producer import ImageProducerAgent
        from apps.pipeline.services.pipeline_errors import BillingLimitError
        prompts = [{"direction_name": f"d{i}", "full_prompt": "p"} for i in range(3)]
        boom = Exception(
            "Error code: 400 - {'error': {'message': 'Billing hard limit "
            "has been reached.', 'type': 'billing_error'}}"
        )
        with patch("apps.pipeline.agents.image_producer.openai.images.generate",
                   side_effect=boom) as gen:
            with pytest.raises(BillingLimitError, match="platform.openai.com"):
                ImageProducerAgent(self.task, prompts).run()
        gen.assert_called_once()   # aborted after the FIRST refusal, not 3

    def test_provider_billing_refusal_logs_sanitized_forensics(self):
        import pytest
        from apps.pipeline.agents.image_producer import ImageProducerAgent
        from apps.pipeline.services.pipeline_errors import BillingLimitError
        prompts = [{"direction_name": "d0", "full_prompt": "p"}]
        boom = Exception(
            "Error code: 400 - {'error': {'message': 'Billing hard limit "
            "has been reached.', 'type': 'billing_error'}}"
        )
        boom.response = MagicMock()
        boom.response.headers = {
            "x-request-id": "req_abc123",
            "openai-organization": "org-test",
            "authorization": "Bearer sk-SECRET",     # must never be captured
            "openai-processing-ms": "41",
        }
        logged = []
        with patch("apps.pipeline.agents.image_producer.openai.images.generate",
                   side_effect=boom):
            with pytest.raises(BillingLimitError):
                ImageProducerAgent(
                    self.task, prompts,
                    log_fn=lambda msg, data=None, level='info':
                        logged.append((msg, data, level)),
                ).run()
        rows = [(m, d) for m, d, lv in logged
                if 'billing limit reached' in m and lv == 'error']
        assert len(rows) == 1
        forensics = rows[0][1]['provider_forensics']
        assert forensics['x-request-id'] == 'req_abc123'
        assert forensics['openai-organization'] == 'org-test'
        assert forensics['openai-processing-ms'] == '41'
        assert 'authorization' not in forensics
        assert 'SECRET' not in str(forensics)


@override_settings(CLAUDE_PRICES=_PRICES)
class TestCallClaudeIntegration(LedgerBase):
    def test_call_claude_records_via_context(self):
        fake_resp = MagicMock()
        fake_resp.usage.input_tokens = 2000
        fake_resp.usage.output_tokens = 0
        fake_client = MagicMock()
        fake_client.messages.create.return_value = fake_resp

        from apps.pipeline.services import claude_service
        with patch.object(claude_service, "_get_client", return_value=fake_client):
            with task_cost_context(self.task):
                claude_service.call_claude(
                    "sys", "hi", model="claude-sonnet-4-6", operation="cd",
                )
        rec = ApiCallRecord.objects.get()
        assert rec.operation == "cd"
        assert rec.input_tokens == 2000
        assert rec.cost_usd == Decimal("0.006000")


class TestSpendBeforeTheClick(TestCase):
    """§BH54(k) 1, OWNER RULED 2026-09-18: "Start a design from the dashboard — target, brief, brand — and watch it
    run, with what it is doing visible rather than a spinner." Starting a design is a SPEND: what a click costs is
    said before the click — MEASURED on this system's own ledger rows, never a quote — the badge's `cost_usd` reaches
    the payload it has always read, the feed is told how many rows exist beyond the twenty it is sent, and each row
    says what it carries with no filesystem path reaching the browser."""

    def setUp(self):
        from django.core.cache import cache
        cache.delete("pipeline:spend_estimates/2")      # §BH55 Phase 3: the key moved with the payload's contents
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d54", "d54@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)
        self.tasks = [DesignTask.objects.create(task_text=f"t{i}", status="running", brand=self.brand)
                      for i in range(2)]
        for task, spent in zip(self.tasks, ("0.75", "2.75")):
            ApiCallRecord.objects.create(task=task, provider="anthropic", model="m", operation="creative_directions",
                                         cost_usd=Decimal(spent))
            ApiCallRecord.objects.create(task=task, provider="openai", model="i", operation="image:X",
                                         image_count=1, cost_usd=Decimal("0.25"))
        ApiCallRecord.objects.create(task=self.tasks[0], provider="anthropic", model="m",
                                     operation="qa_vision_review", cost_usd=Decimal("0.05"))

    def tearDown(self):
        from django.core.cache import cache
        cache.delete("pipeline:spend_estimates/2")      # §BH55 Phase 3: the key moved with the payload's contents

    def test_what_a_click_costs_is_measured_on_the_ledgers_own_rows(self):
        from apps.pipeline.spend_estimates import measured_costs
        costs = measured_costs()
        target = self.tasks[0].design_target
        assert costs["start_design"] == [{"target": target, "tasks": 2, "min_usd": 1.05, "median_usd": 2.02,
                                          "max_usd": 3.0}]
        assert costs["image_usd"] == 0.25 and costs["image_rows"] == 2 and costs["qa_per_image_usd"] == 0.05
        assert costs["rerun_images"] == {"images": 3, "usd": 0.9}
        assert costs["ledger_rows"] == 5 and "never a quote" in costs["basis"]

    def test_each_paid_step_of_the_path_is_measured_on_the_ledgers_own_rows(self):
        # §BH55 Phase 3: what a click on each paid step costs — measured on the operations that step records
        from apps.pipeline.models import ApiCallRecord
        task = self.tasks[0]
        for operation, usd in (("image_prompts", 0.04), ("dieline_estimation", 0.006),
                               ("image:flat_artwork:full", 0.25), ("image:flat_artwork:background", 0.25),
                               ("panel_translation", 0.01)):
            ApiCallRecord.objects.create(task=task, provider="anthropic", model="m", operation=operation, cost_usd=usd)
        from apps.pipeline.spend_estimates import measured_costs
        steps = measured_costs()["steps"]
        assert steps["choose_direction"] == {"usd": 0.94, "images": 3, "rows": 1}   # prompts + 3 × (a drawing + a check)
        assert steps["ask_for_changes"] == {"usd": 1.75, "rows": 2}                 # the two planning rows of this fixture
        assert steps["size_estimate"] == {"usd": 0.01, "rows": 1}                   # a size estimated from the concept
        # [E3, the clean-up of 2026-10-04] making the design makes no picture since the owner's finding on design 119
        # (cd52e1f): the two flat-artwork rows above stay on the ledger and are never priced again — it costs the label
        # copy's translation only, where that is switched on
        assert steps["make_the_design"] == {"usd": 0.0, "rows": 0, "translated": False}
        machine = measured_costs()["machine"]
        assert machine["set_size"] == 3 and machine["redraws"] == 2 and machine["translated"] is False
        assert machine["image_model"] and machine["image_size"]
        from django.core.cache import cache
        cache.delete("pipeline:spend_estimates/2")      # the measured costs are cached for a minute
        with override_settings(PANEL_TRANSLATE_ENABLED=True, ANTHROPIC_API_KEY="k"):
            assert measured_costs()["steps"]["make_the_design"] == {"usd": 0.01, "rows": 1, "translated": True}

    def test_the_status_payload_carries_the_spend_the_row_count_and_what_each_row_carries(self):
        from apps.pipeline.models import AgentLog
        task = self.tasks[0]
        for i in range(24):
            AgentLog.objects.create(task=task, agent_name="ARIA", action=f"step {i}")
        AgentLog.objects.create(task=task, agent_name="ImageProducer", action="generating image 1 of 3",
                                payload={"images": [1, 2, 3], "model": "gpt-image", "empty": "",
                                         "saved": "/Users/someone/private/media/generated/x.png"})
        body = self.client.get(f"/api/tasks/{task.id}/status/").json()
        assert body["size_from_record"] is False              # §BH55 Phase 3: the concepts step says what it spends
        assert body["logs_total"] == 25 and len(body["logs"]) == 20
        assert body["cost_usd"] == 1.05                           # 0.75 + 0.25 + 0.05: the badge has always read this key
        assert body["spend_estimates"]["rerun_images"]["usd"] == 0.9
        newest = body["logs"][0]
        assert newest["action"] == "generating image 1 of 3"
        assert newest["detail"] == "images: 3 items · model: gpt-image · saved: [path removed]"
        assert all(row["detail"] == "" for row in body["logs"][1:])

    def test_each_row_says_who_is_working_and_what_is_being_done_in_words(self):
        # §BH55 Phase 3: the feed showed the agents' own log ("ARIA: delegating to Image Producer"); each row carries it
        # unchanged, and beside it who is working and what is being done, in words — a row no rule reads keeps its words
        from apps.pipeline.models import AgentLog
        task = self.tasks[0]
        for agent, action in (("ARIA", "ARIA: delegating to Image Producer"), ("Dieline", "Dieline: scenario A determined"),
                              ("QAReviewer", "QA Reviewer: 3/3 images passed"),
                              ("ARIA", "ARIA: reached Gate 1 — three variations of 'Liquid Veil' awaiting your approval"),
                              ("ARIA", "ARIA: pipeline failed — the image service refused"),
                              ("system_recovery", "an operator's note, as written")):
            AgentLog.objects.create(task=task, agent_name=agent, action=action)
        rows = {row["action"]: row for row in self.client.get(f"/api/tasks/{task.id}/status/").json()["logs"]}
        said = {action: (row["who"], row["said"]) for action, row in rows.items()}
        assert said["ARIA: delegating to Image Producer"] == ("Studio", "drawing the concepts")
        assert said["Dieline: scenario A determined"] == ("Making", "the size comes from the product's record")
        assert said["QA Reviewer: 3/3 images passed"] == ("Checking", "3 of 3 concepts pass the check")
        assert said["ARIA: reached Gate 1 — three variations of 'Liquid Veil' awaiting your approval"][1] == \
            "three concepts of “Liquid Veil” are ready — choose one"
        assert said["ARIA: pipeline failed — the image service refused"][1] == "stopped — the image service refused"
        assert said["an operator's note, as written"] == ("Recovery", "an operator's note, as written")
        assert rows["Dieline: scenario A determined"]["agent_name"] == "Dieline"           # the row itself, unchanged

    def test_finding1_a_planning_failure_is_said_in_words_never_the_engines_codes(self):
        # his test day finding 1 (2026-09-29, design 116): "The failed notice shows engine codes; say it in words." The
        # step list said "the directions failed their checks — PALETTE_SYSTEMS_NOT_DISTINCT; REQUIRED_COPY_MISSING:…";
        # the row itself stays as written, what it says is in words, each check once
        from apps.pipeline.models import AgentLog
        task = self.tasks[0]
        codes = ("PALETTE_SYSTEMS_NOT_DISTINCT; REQUIRED_COPY_MISSING:direction[0]; REQUIRED_COPY_MISSING:direction[1]; "
                 "REQUIRED_COPY_MISSING:direction[2]")
        for agent, action in (("CreativeDirector", "Creative Director: directions failed validation — " + codes),
                              ("ARIA", "ARIA: pipeline failed — Direction planning failed validation: " + codes)):
            AgentLog.objects.create(task=task, agent_name=agent, action=action)
        rows = {row["action"]: row["said"] for row in self.client.get(f"/api/tasks/{task.id}/status/").json()["logs"]}
        words = "their colours were too alike; they left out copy your brief requires, word for word"
        assert rows["Creative Director: directions failed validation — " + codes] == \
            "the directions failed their checks — " + words
        assert rows["ARIA: pipeline failed — Direction planning failed validation: " + codes] == \
            "stopped — the three directions failed its own checks: " + words

    def test_the_composer_states_the_measured_cost_beside_the_button_that_spends(self):
        html = self.client.get("/dashboard/new/classic/").content.decode()  # [the owner's answer to the UI directions of 2026-09-25: the home is the board; the start form is at New design]
        note = html.split('id="spend-before-click"')[1].split("</p>")[0]
        assert "This button spends on the AI providers." in note
        assert "$1.05–$3.00 a task" in note and "median $2.02, 2 tasks" in note
        assert "never a quote" in note and "Trying a design on its own page spends nothing." in note  # [the owner's answer to the UI directions of 2026-09-25: the design loop is reached from the design's own page]
        assert "product_container" not in note and "Carton $" in note     # each target by its card's name
        assert html.index('id="btn-submit"') < html.index('id="spend-before-click"')


class TestAReRunChecksTheDailyCap(TestCase):
    """§BH54(b), the second block, (k) 5: "a re-run is a spend, so it … checks the daily cap like every other spend. The
    retry view running no cap check is a defect; fix it here." The cap creation has checked since Milestone 12.2 now
    stands at the retry view and the re-run doors (three until the clean-up of 2026-10-04 left the image re-run
    alone) — before any transition, log row or dispatch. Every state here
    is one the product reaches; the `rejected` status is not among them (no door has ever written it). No test here
    spends: every dispatch is patched."""

    def setUp(self):
        from apps.pipeline.permissions import ROLE_REVIEWER
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.user = User.objects.create_user("r55", "r55@t.com", "pw")
        for role in (ROLE_DESIGNER, ROLE_REVIEWER):
            self.user.groups.add(Group.objects.get_or_create(name=role)[0])
        self.client.force_login(self.user)

    def _task(self, status, **more):
        return DesignTask.objects.create(task_text="t", status=status, brand=self.brand, **more)

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_over_the_cap_a_failed_task_is_not_re_run_and_nothing_moves(self, delay):
        from apps.pipeline.models import AgentLog
        task = self._task("failed", error_message="Direction planning failed validation")
        with patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=True):
            res = self.client.post(f"/api/tasks/{task.id}/retry/")
        assert res.status_code == 429 and "daily AI budget exceeded" in res.json()["error"]
        task.refresh_from_db()
        assert (task.status, task.error_message) == ("failed", "Direction planning failed validation")   # its reason stands
        assert not AgentLog.objects.filter(task=task).exists()             # refused BEFORE the audit row and the dispatch
        delay.assert_not_called()

    @patch("apps.pipeline.tasks.run_aria_pipeline.delay")
    def test_under_the_cap_a_failed_task_re_runs_once(self, delay):
        task = self._task("failed", error_message="Direction planning failed validation")
        with patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=False):
            res = self.client.post(f"/api/tasks/{task.id}/retry/")
        assert res.status_code == 200, res.content
        task.refresh_from_db()
        assert (task.status, task.error_message) == ("queued", "")
        delay.assert_called_once_with(task.id)

    def test_a_retry_that_spends_nothing_is_not_held_by_the_cap(self):
        task = self._task("generating_dieline")
        with patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=True):
            res = self.client.post(f"/api/tasks/{task.id}/retry/")
        assert res.status_code == 200                                     # back to the dimension gate: no spend, no cap
        task.refresh_from_db()
        assert task.status == "awaiting_dimensions"

    @patch("apps.pipeline.tasks.rerun_aria_images.delay")
    def test_over_the_cap_the_image_re_run_door_refuses_too(self, delay):
        # [the clean-up of 2026-10-04 (E8) removed the prompt and creative re-run doors; the image re-run is the one left]
        task = self._task("awaiting_gate_1")
        GeneratedImage.objects.create(task=task, direction_name="D", prompt_used="p", variation_number=1)
        with patch("apps.pipeline.services.cost_ledger.daily_budget_exceeded", return_value=True):
            res = self.client.post(f"/api/tasks/{task.id}/rerun_images/")
            assert res.status_code == 429, res.content
        task.refresh_from_db()
        assert (task.status, task.image_rerun_count) == ("awaiting_gate_1", 0)
        delay.assert_not_called()

    def test_the_rejected_status_is_not_retryable_because_no_door_writes_it(self):
        """Measured 2026-09-19: `rejected` is a choice of the model that no door has ever written (a Gate-1 rejection
        re-queues a revision; a Gate-2 rejection returns to the dimensions). A re-run for it would be a control that can
        never appear. Pinned so that the day a door DOES write it, this says the re-run is owed."""
        from apps.pipeline.views import TaskRetryView
        assert "rejected" not in TaskRetryView.RETRYABLE
        res = self.client.post(f"/api/tasks/{self._task('rejected').id}/retry/")
        assert res.status_code == 409 and "cannot be retried" in res.json()["error"]
