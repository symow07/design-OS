"""Printed-data contract + completeness states (Phase 2A-6 §9–10)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.pipeline.services.print_data import (
    CODE_EXAMPLE_IDENTIFIER,
    CODE_INTERNAL_TEXT,
    CODE_LEGAL_ROLE_MISSING,
    CODE_MISSING,
    CODE_PLACEHOLDER,
    CODE_UNVERIFIED,
    MISSING,
    PLACEHOLDER,
    PRINT_FIELD_KEYS,
    UNVERIFIED,
    VERIFIED,
    build_print_record,
    forbidden_copy_strings,
    panel_info_from_record,
)

GOOD = {
    "brand_display_name": "BBROSE",
    "product_name": "Skynte Foundation",
    "product_type": "Fundación facial",
    "ingredients": "AQUA, GLYCERIN, TITANIUM DIOXIDE, DIMETHICONE",
    "how_to_use": "Shake well. Apply evenly and blend outward.",
    "warnings": "For external use only. Keep out of reach of children.",
    "net_weight": "30 ml / 1.0 fl. oz.",
    "manufacturer": "YIWU YIBIN TRADING COMPANY",
    "country_of_origin": "Made in China",
    "barcode_ean": "5061030633823",
    "item_no": "SKYNTE-FND-01",
}


class TestBoundedContract:
    def test_only_declared_fields_enter_the_record(self):
        rec = build_print_record(
            {**GOOD, "task_text": "Create a new coordinated outer packaging…",
             "prompt_used": "a photo of…", "agent_rationale": "because…"},
            verified_keys=GOOD.keys())
        assert set(rec.fields) == set(PRINT_FIELD_KEYS)
        assert "task_text" not in rec.values()
        assert "prompt_used" not in rec.values()
        # and nothing leaked into a legitimate field
        assert all("Create a new" not in v for v in rec.values().values())

    def test_verified_record_is_production_ready(self):
        rec = build_print_record(GOOD, verified_keys=GOOD.keys())
        assert rec.production_failures() == []
        assert rec.production_ready is True

    def test_states_classified_per_field(self):
        rec = build_print_record(
            {**GOOD, "ingredients": "To be confirmed", "how_to_use": ""},
            verified_keys=GOOD.keys())
        states = rec.states()
        assert states["ingredients"] == PLACEHOLDER
        assert states["how_to_use"] == MISSING
        assert states["product_name"] == VERIFIED
        assert states["shade"] == "NOT_APPLICABLE"

    def test_unverified_when_source_not_confirmed(self):
        rec = build_print_record(GOOD, verified_keys=())
        assert rec.states()["product_name"] == UNVERIFIED
        codes = {f["code"] for f in rec.production_failures()}
        assert CODE_UNVERIFIED in codes


class TestDistinctFailureCodes:
    """§10: never flatten all failures into one generic code."""

    def test_missing_and_placeholder_are_distinct(self):
        rec = build_print_record(
            {**GOOD, "ingredients": "TBD", "warnings": ""},
            verified_keys=GOOD.keys())
        by_field: dict[str, set] = {}
        for f in rec.production_failures():
            by_field.setdefault(f["field"], set()).add(f["code"])
        # A placeholder field reports BOTH facts: the copy is placeholder AND
        # its legal role is unsatisfied — distinct codes, not one merged error.
        assert CODE_PLACEHOLDER in by_field["ingredients"]
        assert CODE_MISSING in by_field["warnings"]
        assert CODE_LEGAL_ROLE_MISSING in by_field["ingredients"]

    def test_example_barcode_blocked(self):
        rec = build_print_record({**GOOD, "barcode_ean": "1234567890128"},
                                 verified_keys=GOOD.keys())
        codes = {(f["field"], f["code"]) for f in rec.production_failures()}
        assert ("barcode_ean", CODE_EXAMPLE_IDENTIFIER) in codes

    def test_malformed_barcode_blocked(self):
        rec = build_print_record({**GOOD, "barcode_ean": "12345"},
                                 verified_keys=GOOD.keys())
        assert any(f["code"] == CODE_EXAMPLE_IDENTIFIER
                   for f in rec.production_failures())

    def test_example_sku_blocked(self):
        rec = build_print_record({**GOOD, "item_no": "SKU-0000"},
                                 verified_keys=GOOD.keys())
        assert any(f["field"] == "item_no" and f["code"] == CODE_EXAMPLE_IDENTIFIER
                   for f in rec.production_failures())

    def test_internal_text_in_a_valid_field_is_caught(self):
        rec = build_print_record(
            {**GOOD, "description": "Create a new coordinated outer packaging "
                                    "design for BBROSE Skynte Foundation."},
            verified_keys=GOOD.keys())
        assert any(f["code"] == CODE_INTERNAL_TEXT
                   for f in rec.production_failures())

    def test_legal_roles_must_be_satisfied(self):
        rec = build_print_record(
            {k: v for k, v in GOOD.items() if k != "manufacturer"},
            verified_keys=GOOD.keys())
        codes = [f for f in rec.production_failures()
                 if f["code"] == CODE_LEGAL_ROLE_MISSING]
        assert any(f["field"] == "manufacturer" for f in codes)

    def test_not_applicable_role_is_accepted(self):
        source = {k: v for k, v in GOOD.items() if k != "country_of_origin"}
        rec = build_print_record(source, verified_keys=source.keys(),
                                 not_applicable=("origin",))
        assert not [f for f in rec.production_failures()
                    if f["code"] == CODE_LEGAL_ROLE_MISSING
                    and f["field"] == "origin"]


class TestPreviewVsProduction:
    def test_production_output_excludes_placeholders(self):
        rec = build_print_record({**GOOD, "ingredients": "To be confirmed"},
                                 verified_keys=GOOD.keys())
        info = panel_info_from_record(rec, allow_preview=False)
        assert "ingredients" not in info

    def test_preview_marks_placeholders_clearly(self):
        rec = build_print_record({**GOOD, "ingredients": "To be confirmed"},
                                 verified_keys=GOOD.keys())
        info = panel_info_from_record(rec, allow_preview=True)
        assert info["ingredients"].startswith("[UNAPPROVED PREVIEW]")


class TestForbiddenCopy:
    def test_task_text_and_first_line_are_forbidden(self):
        task = SimpleNamespace(
            task_text="Create a new coordinated outer packaging design.\nMore.",
            product=SimpleNamespace(name="Skynte Foundation"), brief=None)
        forbidden = forbidden_copy_strings(task)
        assert any("Create a new coordinated" in s for s in forbidden)

    def test_product_name_is_never_forbidden(self):
        task = SimpleNamespace(task_text="Skynte Foundation",
                               product=SimpleNamespace(name="Skynte Foundation"),
                               brief=None)
        assert forbidden_copy_strings(task) == ()

    def test_design_intent_text_is_forbidden(self):
        task = SimpleNamespace(
            task_text="t",
            product=SimpleNamespace(name="P"),
            brief=SimpleNamespace(design_intent={
                "visual_objective": "A soft-luxury complexion carton that "
                                    "reads modern and feminine on shelf."}))
        assert any("soft-luxury complexion" in s
                   for s in forbidden_copy_strings(task))


@pytest.mark.parametrize("value,expected", [
    ("To be confirmed according to the approved formulation.", PLACEHOLDER),
    ("[add ingredients]", PLACEHOLDER),
    ("TBD", PLACEHOLDER),
    ("N/A", PLACEHOLDER),
    ("—", PLACEHOLDER),
    ("AQUA, GLYCERIN, TITANIUM DIOXIDE", VERIFIED),
])
def test_placeholder_detection(value, expected):
    rec = build_print_record({**GOOD, "ingredients": value},
                             verified_keys=GOOD.keys())
    assert rec.states()["ingredients"] == expected
