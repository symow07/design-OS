"""Print-data snapshot contract + regeneration integrity (Phase 2A-6B §2–§4).

The contract the task-#47 incident bought: verified printed information must
survive regeneration, and any loss must be provable with a precise code.
"""
from __future__ import annotations

from django.test import SimpleTestCase

from apps.pipeline.services import print_data_snapshot as snap
from apps.pipeline.services.print_data import (
    PLACEHOLDER,
    VERIFIED,
    build_print_record,
)

VERIFIED_RECORD = {
    "brand_display_name": "BBROSE",
    "product_name": "Skynte Foundation",
    "product_type": "Fundación facial",
    "description": "A lightweight liquid foundation.",
    "ingredients": "AQUA, GLYCERIN, TITANIUM DIOXIDE",
    "how_to_use": "Shake well before use.",
    "warnings": "For external use only.",
    "net_weight": "30 ml / 1.0 fl. oz.",
    "item_no": "SKYNTE-FND-01",
    "barcode_ean": "5061030633823",
    "qr_url": "https://www.bbrose.com",
    "manufacturer": "YIWU YIBIN TRADING COMPANY",
    "country_of_origin": "Made in China",
    "translations": {
        "es": {"warnings": "Solo para uso externo.",
               "how_to_use": "Agitar bien antes de usar."},
        "ar": {"warnings": "للاستخدام الخارجي فقط."},
    },
}


def _snap(values=None, task_id=47):
    return snap.snapshot_from_panel_info(task_id, values or dict(VERIFIED_RECORD))


class SnapshotContractTests(SimpleTestCase):
    def test_schema_version_and_required_keys(self):
        s = _snap()
        self.assertEqual(s.schema_version, "packaging_print_data_snapshot/1.0")
        for key in ("task_id", "source", "created_at", "values", "states",
                    "translations", "legal_roles", "content_hash"):
            self.assertIn(key, s.to_dict())

    def test_hash_is_deterministic_and_time_independent(self):
        a, b = _snap(), _snap()
        self.assertEqual(a.content_hash, b.content_hash)
        self.assertNotEqual(a.created_at and b.created_at, None)
        # the timestamp is excluded from the canonical bytes
        self.assertNotIn("created_at", a.canonical())

    def test_hash_changes_when_any_value_changes(self):
        other = dict(VERIFIED_RECORD, net_weight="50 ml")
        self.assertNotEqual(_snap().content_hash, _snap(other).content_hash)

    def test_hash_changes_when_a_translation_changes(self):
        other = dict(VERIFIED_RECORD)
        other["translations"] = {"es": {"warnings": "CAMBIADO"},
                                 "ar": {"warnings": "للاستخدام الخارجي فقط."}}
        self.assertNotEqual(_snap().content_hash, _snap(other).content_hash)

    def test_translation_identities_are_hashes_not_copies(self):
        identities = _snap().translations
        self.assertIn("es", identities)
        self.assertIn("warnings", identities["es"])
        entry = identities["es"]["warnings"]
        self.assertEqual(set(entry), {"sha256", "chars"})
        self.assertNotIn("Solo para uso externo", str(identities))

    def test_legal_role_mapping_present(self):
        roles = _snap().legal_roles
        self.assertEqual(roles["ingredients"]["ingredients"], VERIFIED)
        self.assertEqual(roles["manufacturer"]["manufacturer"], VERIFIED)

    def test_snapshot_excludes_forbidden_content(self):
        blob = str(_snap().to_dict()).lower()
        for forbidden in ("password", "api_key", "secret", "token",
                          "task_text", "brief", "rationale"):
            self.assertNotIn(forbidden, blob)

    def test_normalization_is_formatting_only(self):
        self.assertEqual(snap.normalize("  a\r\nb  \t c  "), "a\nb c")
        self.assertEqual(snap.normalize("café"), snap.normalize("café"))


class RegenerationIntegrityTests(SimpleTestCase):
    def test_unchanged_data_passes(self):
        c = snap.compare_snapshots(_snap(), _snap())
        self.assertTrue(c.passed)
        self.assertTrue(c.identical)
        self.assertEqual(c.failures, [])

    def test_formatting_only_normalization_passes_and_is_explicit(self):
        messy = dict(VERIFIED_RECORD,
                     warnings="For external use only.  \r\n")
        c = snap.compare_snapshots(_snap(), _snap(messy))
        self.assertTrue(c.passed, c.failures)

    def test_dropped_field_fails(self):
        lossy = {k: v for k, v in VERIFIED_RECORD.items() if k != "warnings"}
        c = snap.compare_snapshots(_snap(), _snap(lossy))
        self.assertFalse(c.passed)
        self.assertIn(snap.PRINT_DATA_FIELD_DROPPED, c.codes())
        self.assertIn(snap.VERIFIED_PRINT_DATA_WOULD_BE_LOST, c.codes())

    def test_replaced_field_fails(self):
        changed = dict(VERIFIED_RECORD, ingredients="AQUA ONLY")
        c = snap.compare_snapshots(_snap(), _snap(changed))
        self.assertIn(snap.PRINT_DATA_FIELD_CHANGED, c.codes())
        self.assertIn(snap.VERIFIED_PRINT_DATA_WOULD_BE_LOST, c.codes())

    def test_default_substitution_gets_its_own_code(self):
        defaults = {"product_name": "Generic Product"}
        substituted = dict(VERIFIED_RECORD, product_name="Generic Product")
        c = snap.compare_snapshots(_snap(), _snap(substituted),
                                   defaults=defaults)
        self.assertIn(snap.PRINT_DATA_DEFAULT_SUBSTITUTED, c.codes())
        self.assertNotIn(snap.PRINT_DATA_FIELD_CHANGED, c.codes())

    def test_placeholder_insertion_fails(self):
        placeholdered = dict(VERIFIED_RECORD, ingredients="To be confirmed")
        after = _snap(placeholdered)
        self.assertEqual(after.states["ingredients"], PLACEHOLDER)
        c = snap.compare_snapshots(_snap(), after)
        self.assertIn(snap.VERIFIED_PRINT_DATA_WOULD_BE_LOST, c.codes())

    def test_translation_loss_fails(self):
        lost = dict(VERIFIED_RECORD)
        lost["translations"] = {"es": lost["translations"]["es"]}
        c = snap.compare_snapshots(_snap(), _snap(lost))
        self.assertIn(snap.TRANSLATION_DATA_LOST, c.codes())
        self.assertTrue(any("ar" in f["field"] for f in c.failures))

    def test_translation_change_fails(self):
        changed = dict(VERIFIED_RECORD)
        changed["translations"] = {
            "es": {"warnings": "OTRO TEXTO",
                   "how_to_use": "Agitar bien antes de usar."},
            "ar": {"warnings": "للاستخدام الخارجي فقط."}}
        c = snap.compare_snapshots(_snap(), _snap(changed))
        self.assertIn(snap.TRANSLATION_DATA_LOST, c.codes())

    def test_legal_role_reassignment_fails(self):
        moved = {k: v for k, v in VERIFIED_RECORD.items()
                 if k != "manufacturer"}
        c = snap.compare_snapshots(_snap(), _snap(moved))
        self.assertIn(snap.LEGAL_ROLE_MAPPING_CHANGED, c.codes())

    def test_newly_supplied_data_is_not_a_loss(self):
        richer = dict(VERIFIED_RECORD, shade="Ivory 02")
        c = snap.compare_snapshots(_snap(), _snap(richer))
        self.assertTrue(c.passed, c.failures)

    def test_no_partial_success(self):
        """One failure is enough — `passed` is never partially true."""
        lossy = {k: v for k, v in VERIFIED_RECORD.items() if k != "net_weight"}
        c = snap.compare_snapshots(_snap(), _snap(lossy))
        self.assertFalse(c.passed)
        self.assertFalse(c.identical)

    def test_snapshot_binding_mismatch_is_detected(self):
        s = _snap()
        self.assertEqual(snap.assert_snapshot_binding(s.content_hash, s), [])
        failures = snap.assert_snapshot_binding("deadbeef", s)
        self.assertEqual(failures[0]["code"], snap.PRINT_DATA_SNAPSHOT_MISMATCH)


class PrecedenceTests(SimpleTestCase):
    """§4 — stored record > explicit override > defaults; never a generated
    fallback for a required production field."""

    DEFAULTS = {"product_name": "Default Product",
                "warnings": "Default warning text.",
                "net_weight": "10 ml"}

    def test_stored_verified_value_is_never_replaced_by_a_default(self):
        c = snap.compare_snapshots(
            _snap(), _snap(dict(VERIFIED_RECORD, **self.DEFAULTS)),
            defaults=self.DEFAULTS)
        self.assertIn(snap.PRINT_DATA_DEFAULT_SUBSTITUTED, c.codes())
        substituted = {f["field"] for f in c.failures
                       if f["code"] == snap.PRINT_DATA_DEFAULT_SUBSTITUTED}
        self.assertEqual(substituted, {"product_name", "warnings",
                                       "net_weight"})

    def test_defaults_may_fill_a_truly_absent_field(self):
        sparse = {k: v for k, v in VERIFIED_RECORD.items()
                  if k != "shade"}
        filled = dict(sparse, shade="Ivory 02")
        c = snap.compare_snapshots(_snap(sparse), _snap(filled),
                                   defaults={"shade": "Ivory 02"})
        self.assertTrue(c.passed, c.failures)

    def test_task_without_product_row_keeps_its_own_record(self):
        """The incident case: no Product defaults at all must still leave the
        stored task-specific record intact."""
        c = snap.compare_snapshots(_snap(), _snap(), defaults={})
        self.assertTrue(c.passed)
        record = build_print_record(
            VERIFIED_RECORD, verified_keys=VERIFIED_RECORD.keys())
        self.assertEqual(record.states()["product_name"], VERIFIED)
