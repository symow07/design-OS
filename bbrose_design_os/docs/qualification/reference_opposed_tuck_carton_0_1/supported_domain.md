# Supported dimensional domain — reference_opposed_tuck_carton/0.1

Phase 2A-9B §2. Every constraint is DERIVED (closure geometry, material compensation, slit/ear construction, flap collision, minimum manufacturing features) — never guessed. Outside the domain the generator fails closed with `DIMENSION_COMBINATION_UNSUPPORTED` naming the exact constraint.

| Constraint | Formula | Derivation |
|---|---|---|
| BOARD_RANGE | `0.3 <= board_thickness_mm <= 1` | manufacturing caliper range for folding-carton board; every compensation in the contract derives from t |
| WIDTH_RANGE | `12 <= width_mm <= 300` | print-shop sheet/die budget (schema Milestone 9.1) |
| DEPTH_RANGE | `12 <= depth_mm <= 300` | print-shop sheet/die budget |
| HEIGHT_RANGE | `60 <= height_mm <= 600` | print-shop sheet/die budget |
| GLUE_RANGE | `6 <= glue_tab_mm <= 15` | adhesive-joint practice bounds |
| BLEED_RANGE | `2 <= bleed_mm <= 5` | prepress practice bounds |
| SAFE_RANGE | `3 <= safe_margin_mm <= 8` | prepress practice bounds |
| HEIGHT_GT_WIDTH | `H > W` | tuck-carton proportion: the tuck closure needs the body taller than the opening span |
| HEIGHT_GT_DEPTH | `H > D` | tuck-carton proportion |
| GLUE_CLEARANCE | `D + 2t >= G + 3` | the glue flap laps inside the side span; less than 3 mm of clearance overlaps the side fold (adapted-source guard) |
| DUST_BASE_MIN | `(D + t) - 2*chamfer - taper >= 2` | dust-flap base after the 3 mm chamfer and 2 mm taper must keep a 2 mm manufacturable base (minimum feature) |
| FOLD_HINGE_MIN | `(W + t) - 2*slit_l >= 10` | the tuck-fold crease is shortened by a 7 mm entry slit at each end; below a 10 mm remaining span the fold has no functional hinge |
| TUCK_TIP_MIN | `(W + t) - 2*(slit_l + 2t) >= 4` | the flat tuck tip between the Bezier shoulders must keep a 4 mm span or the shoulders cross (self-intersection) |
| DUST_PAIR_CLEARANCE | `W - (D + t + hook) >= 2` | FOLDED: opposing dust flaps (depth (P + hook - t)/2 each) meet across the inner width; W - 2*dust_d >= 2 mm or they collide (measured on the actual outlines by the folded checks) |
| EAR_ENGAGEMENT | `slit_d - 2t >= 0.5` | the entry slit must cross the fold beyond the 2t locking ear by >= 0.5 mm or the ear cannot snap in |
| HOOK_VS_BODY | `H >= hook + 2t + 2` | FOLDED: the tuck hook folds down inside the opposite main face and must clear the body height |

## Effective envelope

At t = 0.5 mm, glue 12 mm:
```json
{
  "board_thickness_mm": [
    0.3,
    1.0
  ],
  "width_mm_min_at_depth_floor": 32.5,
  "width_mm_max": 300.0,
  "depth_mm_min": 14.0,
  "depth_mm_max_given_W": "W - t - 20",
  "height_mm": [
    60.0,
    600.0
  ],
  "height_rule": "H > W and H > D",
  "width_depth_rule": "W >= D + t + 20 (folded dust clearance)"
}
```
At t = 1.0 mm, glue 12 mm:
```json
{
  "board_thickness_mm": [
    0.3,
    1.0
  ],
  "width_mm_min_at_depth_floor": 33.0,
  "width_mm_max": 300.0,
  "depth_mm_min": 13.0,
  "depth_mm_max_given_W": "W - t - 20",
  "height_mm": [
    60.0,
    600.0
  ],
  "height_rule": "H > W and H > D",
  "width_depth_rule": "W >= D + t + 20 (folded dust clearance)"
}
```

Headline rules: **W ≥ D + t + 20** (folded dust clearance), **H > W and H > D**, D ≥ 12, W ≤ 300, H ≤ 600, t ∈ [0.3, 1.0] (above t = 1.0 the 2.5 mm entry slit no longer crosses the 2t ear by the 0.5 mm engagement minimum).
