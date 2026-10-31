"""INDEPENDENT expected geometry for the three generic carton templates.

Phase 2A-6-CORR-1 §5. Every number below is derived BY HAND from the
published coordinate contract and the DECISION record — **not** produced by
the implementation under test. A test that compares the engine to its own
output proves nothing; these fixtures are the external truth the corrected
geometry must reproduce.

Derivation for the canonical case W=42, D=32, H=140, G=10, t=0.30,
thickness_compensation=True:

  ECMA panel widths (module docstring)
      front  = W            = 42.0
      side   = D + t        = 32.3   (each)
      back   = W + 2t       = 42.6
      glue   = G            = 10.0
  X contract
      x0 = 0
      x1 = G                        = 10.0
      x2 = x1 + (W + 2t)            = 52.6
      x3 = x2 + (D + t)             = 84.9
      x4 = x3 + W                   = 126.9
      x5 = x4 + (D + t)             = 159.2      == flat width
  Y contract (DECISION-016: tuck height = W × 1.227)
      y0 = 0
      y1 = 42 × 1.227               = 51.534
      y2 = y1 + H                   = 191.534
      y3 = y2 + 51.534              = 243.068    == flat height
  DECISION-015 lock notch  n = 2t   = 0.6

Horizontal creases, DECISION-021 (per hinge, never over a cut edge):
  * the tuck column creases from x_l + n to x_r − n;
  * the two side columns (dust flaps) crease across their full width;
  * the flapless main panel gets NO crease at that end;
  * the glue tab never creases (DECISION-008).
"""
from __future__ import annotations

# --- canonical inputs ---------------------------------------------------------

W, D, H, G, T = 42.0, 32.0, 140.0, 10.0, 0.30
BLEED, SAFE = 3.0, 4.0

# --- hand-derived contract coordinates ---------------------------------------

X0 = 0.0
X1 = 10.0
X2 = 52.6
X3 = 84.9
X4 = 126.9
X5 = 159.2

Y0 = 0.0
Y1 = 51.534
Y2 = 191.534
Y3 = 243.068

NOTCH = 0.6                      # 2t
FLAT_W = 159.2                   # G + 2(D+t) + W + (W+2t) = 10+64.6+42+42.6
FLAT_H = 243.068

PANEL_WIDTHS = {                 # ECMA allowances
    "glue_tab": 10.0,
    "back": 42.6,
    "side_left": 32.3,
    "front": 42.0,
    "side_right": 32.3,
}

# The STE engine seats the glue tab against the tuck-carrying BACK panel.
PANEL_SEQUENCE = ["glue_tab", "back", "side_left", "front", "side_right"]

# Vertical body creases: DECISION-001 (body height only), DECISION-008
# (start at the glue-tab edge, never through the tab).
VERTICAL_CREASES = [
    (X1, Y1, X1, Y2),
    (X2, Y1, X2, Y2),
    (X3, Y1, X3, Y2),
    (X4, Y1, X4, Y2),
]

# Column spans, for readability below.
_BACK = (X1, X2)
_SIDE_L = (X2, X3)
_FRONT = (X3, X4)
_SIDE_R = (X4, X5)


def _tuck(col, y):
    """Tuck-base crease: shortened by the lock notch at each corner."""
    return (col[0] + NOTCH, y, col[1] - NOTCH, y)


def _dust(col, y):
    """Dust-flap crease: the flap's base edge spans the full column."""
    return (col[0], y, col[1], y)


# --- expected per-template geometry ------------------------------------------

STRAIGHT_TUCK_END = {
    "template_id": "straight_tuck_end_carton",
    "corrected_version": "1.1",
    "panel_sequence": PANEL_SEQUENCE,
    "panel_widths": PANEL_WIDTHS,
    "flat_mm": (FLAT_W, FLAT_H),
    "body_height_mm": H,
    "glue_seam_side": "back",          # glue tab abuts the back panel
    # top tuck on BACK, bottom tuck on FRONT
    "top_flap_columns": {"back": "tuck", "side_left": "dust",
                         "side_right": "dust"},
    "bottom_flap_columns": {"front": "tuck", "side_left": "dust",
                            "side_right": "dust"},
    "flapless_top_panel": "front",
    "flapless_bottom_panel": "back",
    "horizontal_creases": [
        _tuck(_BACK, Y1), _dust(_SIDE_L, Y1), _dust(_SIDE_R, Y1),
        _tuck(_FRONT, Y2), _dust(_SIDE_L, Y2), _dust(_SIDE_R, Y2),
    ],
    "slit_ids": ["top-back-slit", "bottom-front-slit"],
    "component_ids": [
        "main-body", "glue-tab", "top-back-tuck", "top-left-dust",
        "top-right-dust", "bottom-front-tuck", "bottom-left-dust",
        "bottom-right-dust",
    ],
    # v1.0's defect, kept so the "before" state is pinned independently.
    "v1_0_horizontal_creases": [
        (X1, Y1, X5, Y1),
        (X1, Y2, X5, Y2),
    ],
    # front top edge (42.0) + back bottom edge (42.6) + 4 notch runs (0.6 ea)
    "v1_0_conflict_mm": 42.0 + 42.6 + 4 * NOTCH,
}

REVERSE_TUCK_END = {
    "template_id": "reverse_tuck_end_carton",
    "corrected_version": "1.1",
    "panel_sequence": PANEL_SEQUENCE,
    "panel_widths": PANEL_WIDTHS,
    "flat_mm": (FLAT_W, FLAT_H),
    "body_height_mm": H,
    "glue_seam_side": "back",
    # REVERSE: the tucks hinge from opposite panels to STE.
    "top_flap_columns": {"front": "tuck", "side_left": "dust",
                         "side_right": "dust"},
    "bottom_flap_columns": {"back": "tuck", "side_left": "dust",
                            "side_right": "dust"},
    "flapless_top_panel": "back",
    "flapless_bottom_panel": "front",
    "horizontal_creases": [
        _tuck(_FRONT, Y1), _dust(_SIDE_L, Y1), _dust(_SIDE_R, Y1),
        _tuck(_BACK, Y2), _dust(_SIDE_L, Y2), _dust(_SIDE_R, Y2),
    ],
    "slit_ids": ["top-front-slit", "bottom-back-slit"],
    "component_ids": [
        "main-body", "glue-tab", "top-front-tuck", "top-left-dust",
        "top-right-dust", "bottom-back-tuck", "bottom-left-dust",
        "bottom-right-dust",
    ],
    "v1_0_horizontal_creases": [
        (X1, Y1, X5, Y1),
        (X1, Y2, X5, Y2),
    ],
    "v1_0_conflict_mm": 42.6 + 42.0 + 4 * NOTCH,
}

# Auto-bottom: the bottom zone is min(W, D) × 0.75 = 32 × 0.75 = 24.0 mm,
# so the flat is shorter than the tuck styles.
AUTO_BOTTOM_ZONE = 24.0
AUTO_BOTTOM_FLAT_H = Y1 + H + AUTO_BOTTOM_ZONE     # 51.534 + 140 + 24

TUCK_TOP_AUTO_BOTTOM = {
    "template_id": "tuck_top_auto_bottom_carton",
    "corrected_version": "1.1",
    "panel_sequence": PANEL_SEQUENCE,
    "panel_widths": PANEL_WIDTHS,
    "flat_mm": (FLAT_W, AUTO_BOTTOM_FLAT_H),
    "body_height_mm": H,
    "glue_seam_side": "back",
    "top_flap_columns": {"back": "tuck", "side_left": "dust",
                         "side_right": "dust"},
    # every body column carries a lock flap, so every column hinges
    "bottom_flap_columns": {"back": "lock", "side_left": "lock",
                            "front": "lock", "side_right": "lock"},
    "flapless_top_panel": "front",
    "flapless_bottom_panel": None,
    "horizontal_creases": [
        _tuck(_BACK, Y1), _dust(_SIDE_L, Y1), _dust(_SIDE_R, Y1),
        _dust(_BACK, Y2), _dust(_SIDE_L, Y2), _dust(_FRONT, Y2),
        _dust(_SIDE_R, Y2),
    ],
    "slit_ids": ["top-back-slit"],
    "component_ids": [
        "main-body", "glue-tab", "top-back-tuck", "top-left-dust",
        "top-right-dust", "bottom-back-lock", "bottom-sl-lock",
        "bottom-front-lock", "bottom-sr-lock",
    ],
    "v1_0_horizontal_creases": [
        (X1, Y1, X5, Y1),
        (X1, Y2, X5, Y2),
    ],
    # only the top edge conflicts: the auto-bottom hinges across every column
    "v1_0_conflict_mm": 42.0 + 2 * NOTCH,
}

ALL_GENERIC = (STRAIGHT_TUCK_END, REVERSE_TUCK_END, TUCK_TOP_AUTO_BOTTOM)

# --- Skynte side-seam reference (regression pin, §8) --------------------------
# Independent derivation for the SIDE-SEAM order: glue | side | main | side |
# main, tuck height = D + lip (DECISION-019), lip = 16.
SKYNTE = {
    "template_id": "skynte_foundation_tuck_carton",
    "version": "1.0",
    "panel_sequence": ["glue_tab", "side_left", "front", "side_right", "back"],
    "panel_widths": {"glue_tab": 10.0, "side_left": 32.3, "front": 42.0,
                     "side_right": 32.3, "back": 42.6},
    "x": [0.0, 10.0, 42.3, 84.3, 116.6, 159.2],
    "y": [0.0, 48.0, 188.0, 236.0],       # y1 = D + lip = 32 + 16
    "flat_mm": (159.2, 236.0),
    "entry_slit_mm": 5.0,
    "lock_notch_mm": 0.6,
    "entry_cut_segments": 4,
    "horizontal_crease_count": 6,          # 2 dust + 1 tuck, per end
    "fold_line_count": 10,                 # + 4 vertical
    "conflict_mm": 0.0,
}
