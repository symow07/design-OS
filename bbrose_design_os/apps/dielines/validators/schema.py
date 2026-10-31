from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class FieldEstimate(BaseModel):
    value: float | None
    confidence: float = Field(ge=0.0, le=1.0)
    source: Literal["image", "text", "pdf", "db", "manual", "container",   # §BH55: the container stage of the same project
                    "gift set",                                            # §BH55 Phase 2: a gift set's own fit
                    "container on its edge",                               # §BH70(1): a compact, standing on its edge
                    "container lying flat"]                                # [his goal of 2026-10-13, (2)] lying flat
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
    #: [his goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (2): "A palette or compact lies flat: its box's front is the
    #: lid's face (landscape)."] how the box is seen: "flat" — its front as wide as its die stands it tall, the size step
    #: naming its sides so — else as its die stands
    orientation: Literal["standing", "flat"] = "standing"

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
    # Hard guards: anything below the minima produces a physically
    # unprintable carton; anything above the maxima exceeds the print
    # shop's sheet/die budget for this template (Milestone 9.1:
    # W, D ≤ 300 mm, H ≤ 600 mm — confirm with the print shop before
    # raising).
    width_mm: float = Field(ge=12.0, le=300.0)
    depth_mm: float = Field(ge=12.0, le=300.0)
    height_mm: float = Field(ge=60.0, le=600.0)


class _PrintSettings(BaseModel):
    # Industry-fixed print constants. Allow override but bound to sane range.
    bleed_mm: float = Field(default=3.0, ge=2.0, le=5.0)
    safe_margin_mm: float = Field(default=4.0, ge=3.0, le=8.0)


class _Construction(BaseModel):
    # Only fields the engine actually consumes. All tuck/dust/shoulder/slit
    # proportions are owned by DECISION-016 (measured from the reference AI
    # file) and are not user-tunable.
    glue_tab_mm: float = Field(default=10.0, ge=6.0, le=15.0)
    # ge=0.0 (not 0.2): an explicit zero means "uncompensated reference
    # geometry" and is required by the legacy-regression guard tests.
    board_thickness_mm: float = Field(default=0.35, ge=0.0, le=1.0)
    kerf_mm: float = Field(default=0.0, ge=0.0, le=0.5)
    # Milestone 9.2 (audit C5) — opt-in board-thickness compensation.
    # False (default): legacy layout — board_thickness_mm feeds only the
    # inner/outer spec table; panel sums are raw G+W+D+W+D, exactly
    # reproducing the measured 28x28x120 engine reference snapshot.
    # True: ECMA per-panel allowances (back +2t, sides +t) plus the
    # DECISION-015 shoulder lock notches (2t) derived from
    # board_thickness_mm. See the engine module docstring.
    thickness_compensation: bool = False


class _Metadata(BaseModel):
    product_name: str
    product_type: str
    notes: str = ""


# Milestone 12.1 — per-style dimension constraints. Each style declares which
# ordering rules apply so relaxed styles (auto-bottom, for compacts/palettes)
# are not forced into the tuck-carton H > W / H > D shape. The tuck styles
# (straight, reverse) share the STE tuck geometry so they keep all three
# rules; the auto-bottom base decouples the closure from the tuck ratio, so it
# only keeps the depth/width guard that protects the top dust flaps.
_STRUCTURAL_RULES: dict[str, dict] = {
    "straight_tuck_end_carton":    {"h_gt_w": True,  "h_gt_d": True,  "max_d_over_w": 2.5},
    "reverse_tuck_end_carton":     {"h_gt_w": True,  "h_gt_d": True,  "max_d_over_w": 2.5},
    "tuck_top_auto_bottom_carton": {"h_gt_w": False, "h_gt_d": False, "max_d_over_w": 2.5},
    # DECISION-018 side-seam parametric archetype (glue | side | main | side
    # | main). Same tuck-carton proportions rules as STE.
    "skynte_foundation_tuck_carton": {"h_gt_w": True, "h_gt_d": True, "max_d_over_w": 2.5},
    # Phase 2A-9 open-source-adapted STE archetype (dimensions are INNER for
    # this template). Same tuck-carton proportion rules.
    "ecma_a20_20_01_01_ste_carton": {"h_gt_w": True, "h_gt_d": True, "max_d_over_w": 2.5},
    # 2A-9-CORR-2 reference-matched opposing-tuck archetype (INNER dims).
    "reference_opposed_tuck_carton": {"h_gt_w": True, "h_gt_d": True, "max_d_over_w": 2.5},
}

_SUPPORTED_TEMPLATES = tuple(_STRUCTURAL_RULES)


class DielineInputJSON(BaseModel):
    template: Literal[
        "straight_tuck_end_carton",
        "reverse_tuck_end_carton",
        "tuck_top_auto_bottom_carton",
        "skynte_foundation_tuck_carton",
        "ecma_a20_20_01_01_ste_carton",
        "reference_opposed_tuck_carton",
    ]
    # Phase 2A-6-CORR-1: pin a published geometry version. None = the CURRENT
    # version. Pinning is what lets a historical job reproduce its exact
    # (pre-DECISION-021) output while new work gets the corrected geometry.
    template_version: str | None = None
    unit: Literal["mm"]
    dimensions: _Dimensions
    print_settings: _PrintSettings
    construction: _Construction
    metadata: _Metadata

    @model_validator(mode="after")
    def enforce_structural_rules(self) -> "DielineInputJSON":
        d = self.dimensions
        rules = _STRUCTURAL_RULES[self.template]

        if rules["h_gt_w"] and d.height_mm <= d.width_mm:
            raise ValueError(
                f"height_mm ({d.height_mm}) must be greater than width_mm "
                f"({d.width_mm}) for {self.template}"
            )
        if rules["h_gt_d"] and d.height_mm <= d.depth_mm:
            raise ValueError(
                f"height_mm ({d.height_mm}) must be greater than depth_mm "
                f"({d.depth_mm}) for {self.template}"
            )
        # Milestone 9.1 (audit C4): beyond D = 2.5·W the dust flap cannot be
        # clamped into the tuck zone without collapsing — the wrong carton
        # style for these top-tuck geometries.
        max_ratio = rules["max_d_over_w"]
        if max_ratio and d.depth_mm > max_ratio * d.width_mm:
            raise ValueError(
                f"depth_mm ({d.depth_mm}) is more than {max_ratio}x width_mm "
                f"({d.width_mm}): this proportion cannot fold as {self.template} — "
                "use a different carton style for deep narrow products"
            )
        return self
