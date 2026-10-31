"""Operational revision stamp (Phase 2A-6C-CORR §8).

A stale worker must be detectable operationally, not only by process-start
forensics. current_revision() reports the running revision, and a failed
Creative Director run records it.
"""
from __future__ import annotations

from django.test import SimpleTestCase, override_settings

from apps.pipeline.services.revision import current_revision, revision_report


class RevisionStampTests(SimpleTestCase):
    def setUp(self):
        current_revision.cache_clear()

    def tearDown(self):
        current_revision.cache_clear()

    def test_revision_is_non_empty(self):
        rev = current_revision()
        assert rev and rev != "unknown", rev

    @override_settings(CODE_REVISION="deadbeef")
    def test_explicit_build_stamp_wins(self):
        current_revision.cache_clear()
        assert current_revision() == "deadbeef"
        assert revision_report() == {"code_revision": "deadbeef"}

    def test_report_is_credential_free(self):
        blob = str(revision_report()).lower()
        for secret in ("password", "secret", "token", "api_key"):
            assert secret not in blob


class WorkerRevisionProbeTests(SimpleTestCase):
    def test_probe_task_returns_current_revision(self):
        from apps.pipeline.tasks import report_worker_revision
        # eager call runs in-process; the value is the running revision
        assert report_worker_revision.run() == current_revision()
