"""Milestone 10.1 API-hardening tests (audit H4).

Covers:
  - generation writes SVG / .ai / production PDF / spec under
    MEDIA_ROOT/dielines/<job_id>/ regardless of the process CWD;
  - object-level authorization: foreign users get 404, staff get access,
    anonymous callers get 401/403 JSON (not a 302 redirect);
  - the authenticated file route streams every deliverable kind;
  - a deliverable's address is only ever the authenticated route, never a bare
    /exports/ path.

[The clean-up of 2026-10-04 (E10d) removed the pre-merge POST generate/, GET
inspiration/ and POST save-product/ doors, which no page called, with the tests
that were theirs alone (the defaults, the inspiration labels, four authorization
cases). The files these tests read are produced through the shared export
service, the path the agent runs.]

Django TestCase + DRF APIClient (needs the DB), so these run under
``manage.py test`` and are collected-but-split under plain pytest.
"""
from __future__ import annotations

import contextlib
import shutil
import tempfile
from os import chdir as _chdir, getcwd as _getcwd
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from apps.dielines.constants import (
    DEFAULT_BLEED_MM,
    DEFAULT_BOARD_THICKNESS_MM,
    DEFAULT_GLUE_TAB_MM,
    DEFAULT_SAFE_MARGIN_MM,
    FILE_KINDS,
)
from apps.dielines.models import DielineJob


@contextlib.contextmanager
def _cwd(path):
    """contextlib.chdir backport (this env runs Python 3.10)."""
    prev = _getcwd()
    _chdir(path)
    try:
        yield
    finally:
        _chdir(prev)

_DIMS_REQUIRED_ONLY = {"width_mm": 35.0, "depth_mm": 30.0, "height_mm": 100.0}


class _Phase10Base(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user("owner", password="pw")
        self.other = User.objects.create_user("other", password="pw")
        self.staff = User.objects.create_user("staff", password="pw", is_staff=True)

        self.media_root = tempfile.mkdtemp(prefix="phase10_media_")
        self.addCleanup(shutil.rmtree, self.media_root, ignore_errors=True)
        override = override_settings(MEDIA_ROOT=self.media_root)
        override.enable()
        self.addCleanup(override.disable)

        self.job = DielineJob.objects.create(
            owner=self.owner,
            template_type="straight_tuck_end_carton",
            scenario="A",
            input_json={},
        )

    def client_for(self, user):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return client

    def generate(self, job=None):
        """A job's deliverables, made through the shared export service with the shared defaults — the path
        the agent runs (the API's own generate door left in the clean-up of 2026-10-04)."""
        from apps.dielines.services.export_service import generate_exports
        from apps.dielines.validators.schema import DielineInputJSON
        job = job or self.job
        params = DielineInputJSON(
            template=job.template_type, unit="mm", dimensions=dict(_DIMS_REQUIRED_ONLY),
            print_settings={"bleed_mm": DEFAULT_BLEED_MM, "safe_margin_mm": DEFAULT_SAFE_MARGIN_MM},
            construction={"glue_tab_mm": DEFAULT_GLUE_TAB_MM,
                          "board_thickness_mm": DEFAULT_BOARD_THICKNESS_MM},
            metadata={"product_name": "Test Carton", "product_type": "carton"},
        )
        return generate_exports(job, params)


class ExportLocationTest(_Phase10Base):
    def test_exports_land_under_media_root_regardless_of_cwd(self):
        """Generate from a throwaway CWD: every deliverable must land in
        MEDIA_ROOT/dielines/<job_id>/ (audit H4c: exports used to land in the
        process CWD). [Through the export service since the clean-up of 2026-10-04.]"""
        scratch_cwd = tempfile.mkdtemp(prefix="phase10_cwd_")
        self.addCleanup(shutil.rmtree, scratch_cwd, ignore_errors=True)

        with _cwd(scratch_cwd):
            self.generate()

        job_id = str(self.job.pk)
        export_dir = Path(self.media_root) / "dielines" / job_id
        for filename in (
            f"{job_id}.svg",
            f"{job_id}.ai",
            f"{job_id}_production.pdf",
            f"{job_id}_spec.json",
        ):
            path = export_dir / filename
            self.assertTrue(path.is_file(), f"missing deliverable: {path}")
            self.assertGreater(path.stat().st_size, 0, f"empty deliverable: {path}")

        # nothing leaked into the scratch CWD
        self.assertEqual(list(Path(scratch_cwd).rglob("*")), [])

        # stored paths are MEDIA_ROOT-relative (servable through /files/)
        self.job.refresh_from_db()
        self.assertEqual(self.job.svg_output_path, f"dielines/{job_id}/{job_id}.svg")
        self.assertEqual(self.job.ai_output_path, f"dielines/{job_id}/{job_id}.ai")
        self.assertEqual(
            self.job.pdf_output_path, f"dielines/{job_id}/{job_id}_production.pdf",
        )

    def test_a_deliverables_address_is_the_authenticated_route_only(self):
        """[It read the removed generate door's response; it reads the route helper now — which also
        proves the kept file route still resolves after the doors beside it were removed, 2026-10-04.]"""
        from apps.dielines.api.views import file_route
        job_id = str(self.job.pk)
        for kind in FILE_KINDS:
            url = file_route(self.job.pk, kind)
            self.assertEqual(url, f"/api/dielines/jobs/{job_id}/files/{kind}/")
            self.assertNotIn("/exports/", url)
            self.assertNotIn("/media/", url)


class AuthorizationTest(_Phase10Base):
    def test_anonymous_file_route_gets_401_or_403(self):
        resp = APIClient().get(f"/api/dielines/jobs/{self.job.pk}/files/svg/")
        self.assertIn(resp.status_code, (401, 403))

    def test_foreign_user_cannot_download(self):
        self.generate()
        resp = self.client_for(self.other).get(
            f"/api/dielines/jobs/{self.job.pk}/files/svg/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_staff_can_access_any_job(self):
        self.generate()
        resp = self.client_for(self.staff).get(
            f"/api/dielines/jobs/{self.job.pk}/files/svg/"
        )
        self.assertEqual(resp.status_code, 200)


class FileRouteTest(_Phase10Base):
    _MAGIC = {
        "svg": (b"<?xml", b"<svg"),
        "ai": (b"%PDF",),           # factory .ai is a copy of the production PDF
        "pdf": (b"%PDF",),
        "spec": (b"{",),
    }

    def test_file_route_streams_every_kind(self):
        self.generate()
        client = self.client_for(self.owner)
        for kind in FILE_KINDS:
            resp = client.get(f"/api/dielines/jobs/{self.job.pk}/files/{kind}/")
            self.assertEqual(resp.status_code, 200, f"kind={kind}")
            body = b"".join(resp.streaming_content)
            self.assertGreater(len(body), 0, f"kind={kind} empty")
            self.assertTrue(
                any(body.lstrip().startswith(m) for m in self._MAGIC[kind]),
                f"kind={kind} unexpected magic bytes: {body[:12]!r}",
            )

    def test_unknown_kind_is_404(self):
        resp = self.client_for(self.owner).get(
            f"/api/dielines/jobs/{self.job.pk}/files/exe/"
        )
        self.assertEqual(resp.status_code, 404)

    def test_missing_file_is_404_not_500(self):
        # job never generated → no svg on disk
        resp = self.client_for(self.owner).get(
            f"/api/dielines/jobs/{self.job.pk}/files/svg/"
        )
        self.assertEqual(resp.status_code, 404)
