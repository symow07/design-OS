"""Phase 14 tests — ops/logging (Milestone 14.1) + entrypoint hardening."""
import json
import subprocess
from pathlib import Path

from django.test import TestCase

from apps.core.middleware import JsonLogFormatter, get_request_id

_PROJECT_DIR = Path(__file__).resolve().parents[3]


class EntrypointScriptTests(TestCase):
    """docker-entrypoint.sh must be valid sh and exec its command — docker is
    not available on every dev machine, so CI is the first place this would
    otherwise be caught."""

    def test_syntax(self):
        proc = subprocess.run(
            ["sh", "-n", str(_PROJECT_DIR / "docker-entrypoint.sh")],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr

    def test_execs_command_when_no_db_and_setup_skipped(self):
        proc = subprocess.run(
            ["sh", str(_PROJECT_DIR / "docker-entrypoint.sh"), "echo", "EP-OK"],
            capture_output=True, text=True, timeout=30,
            env={"PATH": "/usr/bin:/bin", "SKIP_DJANGO_SETUP": "1"},
        )
        assert proc.returncode == 0, proc.stderr
        assert "EP-OK" in proc.stdout


class RequestIDMiddlewareTests(TestCase):
    def test_response_gets_request_id_header(self):
        resp = self.client.get("/healthz")
        assert resp.status_code in (200, 503)     # healthz always responds
        assert resp.headers.get("X-Request-ID")

    def test_inbound_request_id_is_echoed(self):
        resp = self.client.get("/healthz", HTTP_X_REQUEST_ID="abc123xyz")
        assert resp.headers.get("X-Request-ID") == "abc123xyz"

    def test_request_id_defaults_outside_request(self):
        # No active request → the context default.
        assert get_request_id() == "-"


class HardeningTests(TestCase):
    """2026-07-04 hardening: SSE ping events and the thickness-compensation
    passthrough. [The provisional-geometry ack and the batch budget pre-flight
    lived only in the API doors the clean-up of 2026-10-04 removed (E10c, E10d);
    their tests left with them.]"""

    def setUp(self):
        from django.contrib.auth.models import Group, User
        from apps.core.models import Brand
        from apps.pipeline.permissions import ROLE_DESIGNER
        self.brand = Brand.objects.create(name="B", master_brief="x")
        group, _ = Group.objects.get_or_create(name=ROLE_DESIGNER)
        self.user = User.objects.create_user("d", "d@t.com", "pw")
        self.user.groups.add(group)
        self.client.force_login(self.user)

    def test_sse_emits_ping_events(self):
        from apps.pipeline.live_views import _event_stream
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.create(
            task_text="t", status="completed", brand=self.brand)
        frames = "".join(_event_stream(task.id, last_log_id=0, max_seconds=5))
        assert "event: ping" in frames        # visible to EventSource JS
        assert "event: settled" in frames

    def test_dimension_gate_passes_thickness_compensation(self):
        from apps.dielines.validators.schema import DielineInputJSON
        from apps.pipeline.agents.dieline_agent import DielineAgent
        captured = {}

        def fake_exports(job, params, log=None, **kwargs):
            captured["params"] = params
            return {}

        from unittest.mock import patch
        agent = DielineAgent.__new__(DielineAgent)  # skip __init__ plumbing
        agent.log = lambda *a, **k: None
        with patch("apps.pipeline.agents.dieline_agent.generate_exports",
                   side_effect=fake_exports):
            agent.generate(None, {
                "width_mm": 28, "depth_mm": 28, "height_mm": 120,
                "board_thickness_mm": 0.45, "thickness_compensation": True,
            })
        params = captured["params"]
        assert isinstance(params, DielineInputJSON)
        assert params.construction.thickness_compensation is True
        assert params.construction.board_thickness_mm == 0.45

    def test_roleless_account_blocked_from_sse(self):
        from django.contrib.auth.models import User
        from apps.pipeline.models import DesignTask
        task = DesignTask.objects.create(
            task_text="t", status="completed", brand=self.brand)
        nobody = User.objects.create_user("nobody2", "n2@t.com", "pw")
        self.client.force_login(nobody)
        assert self.client.get(f"/api/tasks/{task.id}/events/").status_code == 403


class JsonLogFormatterTests(TestCase):
    def test_emits_valid_json_with_fields(self):
        import logging
        rec = logging.LogRecord(
            name="apps.pipeline", level=logging.INFO, pathname=__file__,
            lineno=1, msg="hello %s", args=("world",), exc_info=None,
        )
        rec.request_id = "rid-42"
        out = json.loads(JsonLogFormatter().format(rec))
        assert out["logger"] == "apps.pipeline"
        assert out["level"] == "INFO"
        assert out["message"] == "hello world"
        assert out["request_id"] == "rid-42"
