"""RBV-3 review surface — read-only guarantees over the real committed
package tree."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase


class Rbv3ReviewSurfaceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "rbv3reviewer", password="x")
        self.client.force_login(self.user)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        for url in ("/dashboard/visual-quality/rbv3/",
                    "/api/visual-quality/rbv3/"):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_page_lists_p1_v4_with_honest_state(self):
        r = self.client.get("/dashboard/visual-quality/rbv3/")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn("p1_v4", body)
        self.assertIn("NOT A REAL BOTTLE COMPARISON", body)
        self.assertIn("ABSENT_BLOCKED", body)
        self.assertIn("RENDER_OFF_CENTER:closure_detail", body)
        self.assertIn("OWNER_BLOCKER_CLEARANCE", body)
        self.assertIn("no decision controls", body)

    def test_status_json_carries_the_committed_manifest(self):
        data = json.loads(self.client.get(
            "/api/visual-quality/rbv3/").content)
        self.assertEqual(data["schema"], "rbv3_dashboard_index/1.0")
        by_id = {p["package_id"]: p["manifest"]
                 for p in data["packages"]}
        m = by_id["p1_v4"]
        self.assertEqual(m["schema"], "rbv3_review_package/1.0")
        self.assertFalse(m["owner_review"]["granted"])
        self.assertEqual(m["camera_standard"]["status"], "ACTIVE")
        self.assertEqual(m["modes"]["CLIENT_PRESENTATION"]["status"],
                         "ABSENT_BLOCKED")

    def test_artifacts_serve_as_png(self):
        for name in ("contact-sheet", "view-front", "view-normals"):
            r = self.client.get(
                f"/api/visual-quality/rbv3/p1_v4/{name}/")
            self.assertEqual(r.status_code, 200, name)
            self.assertEqual(r["Content-Type"], "image/png")
            body = b"".join(r.streaming_content)  # repo pattern: drain
            self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n", name)

    def test_unknown_package_and_name_refuse(self):
        self.assertEqual(self.client.get(
            "/api/visual-quality/rbv3/not_a_package/contact-sheet/"
        ).status_code, 404)
        for name in ("manifest", "review_package_manifest",
                     "view-nonexistent"):
            self.assertEqual(self.client.get(
                f"/api/visual-quality/rbv3/p1_v4/{name}/"
            ).status_code, 404, name)

    def test_no_decision_endpoint_exists(self):
        r = self.client.post("/dashboard/visual-quality/rbv3/",
                             {"decision": "ACCEPT"})
        self.assertIn(r.status_code, (200, 405),
                      "page accepts no decision semantics")
        from apps.pipeline import rbv_views
        self.assertFalse(
            any("decision" in n for n in dir(rbv_views)),
            "a decision channel bypassing the clearance sheet exists")
        body = self.client.get(
            "/dashboard/visual-quality/rbv3/").content.decode()
        # [the owner's answer to the UI directions of 2026-09-25: the page is in the one shell, whose top bar carries the
        # one search box — a form that only finds; no form on the page posts]
        self.assertNotRegex(body, r'<form[^>]*method="post"')
