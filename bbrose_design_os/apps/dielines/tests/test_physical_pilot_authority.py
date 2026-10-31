"""2A-9E commit 5 — physical pilot + authority-state guards.

Pins: the pilot manifest exists with 6 exact-100%-scale PDFs (3 per
archetype); a single exact-hash FIT_PASS grants only
PHYSICALLY_VALIDATED_INSTANCE; a dimensional family needs multiple
representative passes; no manifest/result grants manufacturer authority.
"""
from __future__ import annotations

import json
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase

from apps.dielines.models import DielineJob
from apps.dielines.services.physical_validation import (
    ALLOWED_OUTCOMES,
    dimensional_family_blockers,
    promotion_blockers,
    record_physical_validation,
)

PILOT = Path("docs/qualification/physical_pilot_1_2")


class PilotManifestTests(TestCase):
    def test_pilot_has_three_samples_per_archetype(self):
        manifest = json.loads((PILOT / "pilot_manifest.json").read_text())
        samples = manifest["samples"]
        assert len(samples) == 6
        by_arch = {}
        for s in samples:
            by_arch.setdefault(s["archetype"], []).append(s)
        assert set(by_arch) == {"straight_tuck_end_carton/1.2",
                                "reverse_tuck_end_carton/1.2"}
        for arch, rows in by_arch.items():
            assert len(rows) == 3, arch
            families = {r["family"] for r in rows}
            assert "wide_short_1v1_reject" in families
            assert all(r["status"] == "AWAITING_SAMPLE" for r in rows)
            assert all((PILOT / r["pdf"]).exists() for r in rows)

    def test_outcome_vocabulary_is_a_superset(self):
        # 2A-9E names present AND the original names retained
        assert {"TUCK_ENTRY_FAILURE", "SLIT_OR_NOTCH_FAILURE"} <= \
            ALLOWED_OUTCOMES
        assert {"MAJOR_TUCK_ENTRY_FAILURE", "LOCKING_SLIT_FAILURE",
                "DUST_FLAP_COLLISION", "FIT_PASS"} <= ALLOWED_OUTCOMES


class AuthorityGrantTests(TestCase):
    def setUp(self):
        self.job = DielineJob.objects.create(
            template_type="straight_tuck_end_carton", scenario="B",
            input_json={}, extraction_result={})
        self.user = User.objects.create_user("pa", "p@a.com", "pw")
        self.key = "straight_tuck_end_carton/1.2"

    def test_single_fit_pass_grants_instance_only(self):
        assert promotion_blockers(self.job, template_key=self.key,
                                  geometry_hash="h1")  # blocked before
        record_physical_validation(
            self.job, self.user, template_key=self.key,
            geometry_hash="h1", outcome="FIT_PASS",
            sample_printed_at_100pct=True)
        # instance cleared for h1
        assert promotion_blockers(self.job, template_key=self.key,
                                  geometry_hash="h1") == []
        # but the FAMILY is not (needs multiple representative passes)
        assert dimensional_family_blockers(
            self.job, template_key=self.key,
            family_hashes=["h1", "h2", "h3"])

    def test_family_needs_multiple_representative_passes(self):
        for h in ("h1", "h2", "h3"):
            record_physical_validation(
                self.job, self.user, template_key=self.key,
                geometry_hash=h, outcome="FIT_PASS",
                sample_printed_at_100pct=True)
        assert dimensional_family_blockers(
            self.job, template_key=self.key,
            family_hashes=["h1", "h2", "h3"], minimum_passes=3) == []
        # a different instance hash is still not family-cleared
        assert dimensional_family_blockers(
            self.job, template_key=self.key,
            family_hashes=["h1", "h2", "h3", "h4"], minimum_passes=3)

    def test_no_manufacturer_authority_is_machine_granted(self):
        from apps.dielines.qualification.authority import (
            AuthorityError,
            authority_record,
        )
        # manufacturer authority requires an explicit manufacturer identity
        with self.assertRaises(AuthorityError):
            authority_record(
                state="PRODUCTION_AUTHORIZED_BY_MANUFACTURER",
                archetype_key=self.key, validation_source="x",
                evidence_identity="y")
