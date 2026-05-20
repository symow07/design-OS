from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FieldEstimate(BaseModel):
    value: float | None
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["image", "text", "pdf", "db", "manual"]
    blocked: bool

    @model_validator(mode="after")
    def enforce_confidence_rules(self) -> "FieldEstimate":
        if self.confidence < 0.85:
            if self.value is not None:
                raise ValueError("value must be None when confidence < 0.85")
            if not self.blocked:
                raise ValueError("blocked must be True when confidence < 0.85")
        else:
            if self.value is None:
                raise ValueError("value must not be None when confidence >= 0.85")
            if self.blocked:
                raise ValueError("blocked must be False when confidence >= 0.85")
        return self


class DimensionExtractionResult(BaseModel):
    width_mm: FieldEstimate
    depth_mm: FieldEstimate
    height_mm: FieldEstimate
    bleed_mm: FieldEstimate
    safe_margin_mm: FieldEstimate
    glue_tab_mm: FieldEstimate
    scenario: Literal["A", "B"]
    can_proceed: bool

    @model_validator(mode="after")
    def enforce_can_proceed(self) -> "DimensionExtractionResult":
        fields = [
            self.width_mm,
            self.depth_mm,
            self.height_mm,
            self.bleed_mm,
            self.safe_margin_mm,
            self.glue_tab_mm,
        ]
        expected = not any(f.blocked for f in fields)
        if self.can_proceed != expected:
            raise ValueError(
                f"can_proceed must be {expected} based on blocked field states"
            )
        return self


# ---------------------------------------------------------------------------
# Dieline input schema
#
# IMPORTANT: User-supplied width_mm / depth_mm / height_mm are MANUFACTURE
# dimensions (panel-to-panel, as printed on the dieline). Inner dimensions
# are computed as manufacture - 2*board_thickness; outer dimensions are
# manufacture + 2*board_thickness.
#
# The engine derives all flap geometry from the six core inputs:
#   width_mm, depth_mm, height_mm, bleed_mm, safe_margin_mm, glue_tab_mm
# Per DECISION-016 in docs/geometry_decisions.md:
#   tuck_flap_height = width_mm * 1.227
#   dust_flap_height = depth_mm * 0.631
# ---------------------------------------------------------------------------


class _Dimensions(BaseModel):
    # Hard guards: anything below these produces a physically unprintable carton.
    width_mm: float = Field(ge=12.0)
    depth_mm: float = Field(ge=12.0)
    height_mm: float = Field(ge=60.0)


class _PrintSettings(BaseModel):
    # Industry-fixed print constants. Allow override but bound to sane range.
    bleed_mm: float = Field(default=3.0, ge=2.0, le=5.0)
    safe_margin_mm: float = Field(default=4.0, ge=3.0, le=8.0)


class _Construction(BaseModel):
    # Only fields the engine actually consumes. All tuck/dust/shoulder/slit
    # proportions are owned by DECISION-016 (measured from the reference AI
    # file) and are not user-tunable.
    glue_tab_mm: float = Field(default=10.0, ge=6.0, le=15.0)
    board_thickness_mm: float = Field(default=0.35, ge=0.2, le=1.0)
    kerf_mm: float = Field(default=0.0, ge=0.0, le=0.5)


class _Metadata(BaseModel):
    product_name: str
    product_type: str
    notes: str = ""


class DielineInputJSON(BaseModel):
    template: Literal["straight_tuck_end_carton"]
    unit: Literal["mm"]
    dimensions: _Dimensions
    print_settings: _PrintSettings
    construction: _Construction
    metadata: _Metadata

    @model_validator(mode="after")
    def enforce_structural_rules(self) -> "DielineInputJSON":
        d = self.dimensions

        if d.height_mm <= d.width_mm:
            raise ValueError(
                f"height_mm ({d.height_mm}) must be greater than width_mm ({d.width_mm})"
            )
        if d.height_mm <= d.depth_mm:
            raise ValueError(
                f"height_mm ({d.height_mm}) must be greater than depth_mm ({d.depth_mm})"
            )
        return self
