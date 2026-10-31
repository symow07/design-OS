"""H2 review surface — read-only guarantees over the real run trees."""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase


class H2ReviewSurfaceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            "h2reviewer", password="x")
        self.client.force_login(self.user)

    def test_anonymous_is_redirected(self):
        self.client.logout()
        for url in ("/dashboard/design-requests/", "/api/design-requests/"):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_page_lists_all_three_requests_with_decisions(self):
        r = self.client.get("/dashboard/design-requests/")
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        for rid in ("es3083_lid_alt_01", "fb3093_compact_01",
                    "fb3093_compact_02"):
            self.assertIn(rid, body)
        self.assertIn("OWNER_BLOCKER_CLEARANCE", body)
        self.assertIn("no decision controls", body)

    def test_status_json_derives_the_recorded_outcomes(self):
        data = json.loads(self.client.get(
            "/api/design-requests/").content)
        by_id = {r["request_id"]: r for r in data["requests"]}
        self.assertEqual(by_id["es3083_lid_alt_01"]["stage"], "accepted")
        self.assertEqual(by_id["fb3093_compact_01"]["stage"], "rejected")
        # C3 accepted per §N; the finalised C1 re-verified and ACCEPTED
        # per §P -> all emissions approved, so the round-2 tree reads
        # accepted (the §O supersede history stays visible on the entry)
        self.assertEqual(by_id["fb3093_compact_02"]["stage"], "accepted")
        c1 = next(e for e in by_id["fb3093_compact_02"]["emissions"]
                  if e["ai"] == "fb3093_lid_C1.ai")
        self.assertTrue(c1["superseded"])
        self.assertTrue(c1["owner_approved"])

    def test_contact_sheet_serves_for_each_run_tree(self):
        for rid in ("es3083_lid_alt_01", "fb3093_compact_02"):
            r = self.client.get(
                f"/api/design-requests/{rid}/contact-sheet/")
            self.assertEqual(r.status_code, 200, rid)
            self.assertEqual(r["Content-Type"], "image/png")
            body = b"".join(r.streaming_content)  # repo pattern: drain
            self.assertEqual(body[:8], b"\x89PNG\r\n\x1a\n", rid)

    def test_candidate_artifact_serves_from_register_names(self):
        r = self.client.get(
            "/api/design-requests/fb3093_compact_02/candidate-c1/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content)[:8],
                         b"\x89PNG\r\n\x1a\n")

    def test_unknown_request_and_name_refuse(self):
        self.assertEqual(self.client.get(
            "/api/design-requests/not_a_request/contact-sheet/"
        ).status_code, 404)
        self.assertEqual(self.client.get(
            "/api/design-requests/fb3093_compact_02/brief-json/"
        ).status_code, 404)

    def test_no_decision_endpoint_exists(self):
        r = self.client.post("/dashboard/design-requests/",
                             {"decision": "ACCEPT"})
        self.assertIn(r.status_code, (200, 405),
                      "page accepts no decision semantics")
        from apps.pipeline import h2_views
        self.assertFalse(
            any("decision" in n for n in dir(h2_views)),
            "a decision channel bypassing the clearance sheet exists")
