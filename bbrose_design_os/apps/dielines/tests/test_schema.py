import pytest
from pydantic import ValidationError

from apps.dielines.validators.schema import (
    DielineInputJSON,
    DimensionExtractionResult,
    FieldEstimate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_field_estimate(confidence: float, value: float | None = None, blocked: bool | None = None) -> dict:
    if blocked is None:
        blocked = confidence < 0.85
    if value is None and confidence >= 0.85:
        value = 100.0
    return {"value": value, "confidence": confidence, "source": "image", "blocked": blocked}


def make_extraction_result(**overrides) -> dict:
    base = {
        "width_mm": make_field_estimate(0.90, 30.0),
        "depth_mm": make_field_estimate(0.90, 10.0),
        "height_mm": make_field_estimate(0.90, 80.0),
        "bleed_mm": make_field_estimate(0.90, 3.0),
        "safe_margin_mm": make_field_estimate(0.90, 4.0),
        "glue_tab_mm": make_field_estimate(0.90, 10.0),
        "scenario": "A",
        "can_proceed": True,
    }
    base.update(overrides)
    return base


def make_valid_input() -> dict:
    # Dimensions must satisfy the parametric guards (>=12 mm w/d, >=60 mm h)
    return {
        "template": "straight_tuck_end_carton",
        "unit": "mm",
        "dimensions": {"width_mm": 20.0, "depth_mm": 20.0, "height_mm": 130.0},
        "print_settings": {"bleed_mm": 3.0, "safe_margin_mm": 4.0},
        "construction": {"glue_tab_mm": 10.0},
        "metadata": {"product_name": "Eyeliner", "product_type": "cosmetic"},
    }


# ---------------------------------------------------------------------------
# FieldEstimate
# ---------------------------------------------------------------------------

class TestFieldEstimate:
    def test_confidence_084_sets_blocked_and_null_value(self):
        fe = FieldEstimate(**make_field_estimate(0.84, value=None, blocked=True))
        assert fe.blocked is True
        assert fe.value is None

    def test_confidence_085_allows_value(self):
        fe = FieldEstimate(**make_field_estimate(0.85, value=42.0, blocked=False))
        assert fe.blocked is False
        assert fe.value == 42.0

    def test_confidence_084_with_value_raises(self):
        with pytest.raises(ValidationError, match="value must be None"):
            FieldEstimate(value=10.0, confidence=0.84, source="image", blocked=True)

    def test_confidence_085_with_none_value_raises(self):
        with pytest.raises(ValidationError, match="value must not be None"):
            FieldEstimate(value=None, confidence=0.85, source="image", blocked=False)

    def test_confidence_084_not_blocked_raises(self):
        with pytest.raises(ValidationError, match="blocked must be True"):
            FieldEstimate(value=None, confidence=0.84, source="image", blocked=False)

    def test_confidence_085_blocked_raises(self):
        with pytest.raises(ValidationError, match="blocked must be False"):
            FieldEstimate(value=10.0, confidence=0.85, source="image", blocked=True)

    def test_confidence_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            FieldEstimate(value=None, confidence=1.1, source="image", blocked=True)


# ---------------------------------------------------------------------------
# DimensionExtractionResult
# ---------------------------------------------------------------------------

class TestDimensionExtractionResult:
    def test_can_proceed_true_when_all_unblocked(self):
        result = DimensionExtractionResult(**make_extraction_result())
        assert result.can_proceed is True

    def test_can_proceed_false_when_any_blocked(self):
        data = make_extraction_result(
            width_mm=make_field_estimate(0.70, value=None, blocked=True),
            can_proceed=False,
        )
        result = DimensionExtractionResult(**data)
        assert result.can_proceed is False

    def test_can_proceed_mismatch_raises(self):
        data = make_extraction_result(can_proceed=False)  # all fields are unblocked
        with pytest.raises(ValidationError, match="can_proceed must be True"):
            DimensionExtractionResult(**data)

    def test_can_proceed_mismatch_true_raises(self):
        data = make_extraction_result(
            height_mm=make_field_estimate(0.60, value=None, blocked=True),
            can_proceed=True,  # wrong — should be False
        )
        with pytest.raises(ValidationError, match="can_proceed must be False"):
            DimensionExtractionResult(**data)


# ---------------------------------------------------------------------------
# DielineInputJSON
# ---------------------------------------------------------------------------

class TestDielineInputJSON:
    def test_valid_payload_passes(self):
        obj = DielineInputJSON(**make_valid_input())
        assert obj.template == "straight_tuck_end_carton"
        assert obj.unit == "mm"
        assert obj.metadata.notes == ""

    def test_height_smaller_than_width_raises(self):
        data = make_valid_input()
        # width=20, set height=18 < width but >= the 60mm min — must fail
        # the structural rule (height > width) before the dimension floor.
        # Use width=80, height=70 for an unambiguous case.
        data["dimensions"] = {"width_mm": 80.0, "depth_mm": 20.0, "height_mm": 70.0}
        with pytest.raises(ValidationError, match="height_mm.*must be greater than width_mm"):
            DielineInputJSON(**data)

    def test_height_equal_to_width_raises(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 80.0, "depth_mm": 20.0, "height_mm": 80.0}
        with pytest.raises(ValidationError, match="height_mm.*must be greater than width_mm"):
            DielineInputJSON(**data)

    def test_height_smaller_than_depth_raises(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 20.0, "depth_mm": 80.0, "height_mm": 70.0}
        with pytest.raises(ValidationError, match="height_mm.*must be greater than depth_mm"):
            DielineInputJSON(**data)

    def test_width_below_12_raises(self):
        data = make_valid_input()
        data["dimensions"]["width_mm"] = 10.0
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_height_below_60_raises(self):
        data = make_valid_input()
        data["dimensions"]["height_mm"] = 50.0
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_bleed_below_range_raises(self):
        data = make_valid_input()
        data["print_settings"]["bleed_mm"] = 1.9
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_bleed_above_range_raises(self):
        data = make_valid_input()
        data["print_settings"]["bleed_mm"] = 5.1
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_glue_tab_below_range_raises(self):
        data = make_valid_input()
        data["construction"]["glue_tab_mm"] = 5.9
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_glue_tab_above_range_raises(self):
        data = make_valid_input()
        data["construction"]["glue_tab_mm"] = 15.1
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_top_flap_field_removed(self):
        # top_flap_mm / bottom_flap_mm are no longer accepted.
        # Pydantic ignores unknown fields by default, so this just
        # verifies the canonical valid input still passes.
        data = make_valid_input()
        obj = DielineInputJSON(**data)
        assert not hasattr(obj.construction, "top_flap_mm")

    def test_metadata_notes_defaults_to_empty_string(self):
        data = make_valid_input()
        obj = DielineInputJSON(**data)
        assert obj.metadata.notes == ""

    def test_wrong_template_raises(self):
        data = make_valid_input()
        data["template"] = "unknown_type"
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_wrong_unit_raises(self):
        data = make_valid_input()
        data["unit"] = "cm"
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    # --- Milestone 9.1: maximum dimensions ---------------------------------

    def test_width_above_300_raises(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 301.0, "depth_mm": 20.0, "height_mm": 400.0}
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_depth_above_300_raises(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 200.0, "depth_mm": 301.0, "height_mm": 400.0}
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_height_above_600_raises(self):
        data = make_valid_input()
        data["dimensions"]["height_mm"] = 601.0
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)

    def test_max_envelope_accepted(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 300.0, "depth_mm": 300.0, "height_mm": 600.0}
        assert DielineInputJSON(**data).dimensions.width_mm == 300.0

    # --- Milestone 9.1: depth > 2.5 × width is the wrong carton style ------

    def test_depth_more_than_2_5x_width_raises_with_clear_message(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 12.0, "depth_mm": 40.0, "height_mm": 60.0}
        with pytest.raises(ValidationError, match="different carton style"):
            DielineInputJSON(**data)

    def test_depth_exactly_2_5x_width_accepted(self):
        data = make_valid_input()
        data["dimensions"] = {"width_mm": 16.0, "depth_mm": 40.0, "height_mm": 90.0}
        assert DielineInputJSON(**data).dimensions.depth_mm == 40.0

    # --- Milestone 9.2: opt-in thickness compensation ----------------------

    def test_thickness_compensation_defaults_false(self):
        obj = DielineInputJSON(**make_valid_input())
        assert obj.construction.thickness_compensation is False
        assert obj.construction.board_thickness_mm == 0.35

    def test_thickness_compensation_opt_in(self):
        data = make_valid_input()
        data["construction"]["thickness_compensation"] = True
        data["construction"]["board_thickness_mm"] = 0.45
        obj = DielineInputJSON(**data)
        assert obj.construction.thickness_compensation is True
        assert obj.construction.board_thickness_mm == 0.45

    def test_board_thickness_zero_allowed(self):
        # explicit zero = uncompensated reference geometry (regression tests)
        data = make_valid_input()
        data["construction"]["board_thickness_mm"] = 0.0
        assert DielineInputJSON(**data).construction.board_thickness_mm == 0.0

    def test_board_thickness_above_1mm_raises(self):
        data = make_valid_input()
        data["construction"]["board_thickness_mm"] = 1.1
        with pytest.raises(ValidationError):
            DielineInputJSON(**data)
