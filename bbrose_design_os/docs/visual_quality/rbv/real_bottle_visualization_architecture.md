# Real Bottle Visualization Architecture — RBV program

**Status: PROPOSED — 2026-08-04.** Response to the owner rejection of
abstract fixtures (`VQR_2B_A_OWNER_VISUAL_REVIEW:
REJECTED_AS_NON_REALISTIC_VISUAL_EVIDENCE`). Nothing here is implemented
in this slice; VQR-2B-B stays blocked.

## 1. The two-mode principle (§3)

One geometry, two strictly separated output standards:

**A. GEOMETRY VALIDATION RENDER** — objective comparison against CAD,
dimensions and real product views. Outputs: FRONT/SIDE/TOP_ORTHOGRAPHIC,
CLOSURE_DETAIL, STRUCTURE_ONLY, REFERENCE_VS_RECONSTRUCTION,
ALIGNED_OVERLAY, DEVIATION_VIEW. Fixed scale/camera/crop, neutral
background and material, no decorative lighting, no perspective where
orthographic comparison is required, no effects that conceal geometry.

**B. CLIENT PRESENTATION RENDER** — premium cosmetic review. Outputs:
front presentation, three-quarter hero, closure detail, artwork
presentation, material presentation, client-presentation artboard
(the `CLIENT_PRESENTATION_ARTBOARD` the owner already ruled
REQUIRED_NOT_YET_IMPLEMENTED). Realistic materials, standardized studio
lighting, resolved artwork, refined typography, controlled reflections —
and **never** the structural concept sheet re-badged as presentation.

Geometry verdicts come only from mode A. Presentation appeal comes only
from mode B. Neither substitutes for the other.

## 2. Pipeline

```
real_bottle_reference_pack/1.0  (owner-supplied authority)
        │
        ▼
DETERMINISTIC PRODUCT GEOMETRY  (M3 canonical profile / confirmed dims)
        │ revolve/extrude
        ▼
3D FORM ──► RBV-2a NumPy ortho renderer ──► GEOMETRY VALIDATION package
        └─► RBV-2b headless Blender ──────► CLIENT PRESENTATION package
        │
        ▼
real_bottle_visual_comparison/1.0  (per-domain, fail-closed)
        │
        ▼
claude_visual_review/1.0  (findings BLOCKING/MAJOR/MINOR/VISUAL_POLISH;
                           never self-approving)
        │
        ▼
OWNER — final authority
```

Structural authority stays with the Product Container geometry and the
editable AI. Renderers visualize; they never define truth. GPT Image is
design-intent reference only (§1 authority order).

## 3. Contracts in this program

| Contract | File | Role |
|---|---|---|
| `real_bottle_reference_pack/1.0` | real_bottle_reference_standard.md | what counts as reference authority |
| `real_bottle_camera_standard/1.0` | camera_standard_proposal.json | identical cameras/scale for comparison |
| `real_bottle_lighting_standard/1.0` | lighting_standard_proposal.json | validation vs presentation lighting |
| `real_bottle_visual_comparison/1.0` | real_bottle_comparison_contract.json | per-domain fail-closed comparison |
| `claude_visual_review/1.0` | claude_visual_review_contract.json | structured Claude inspection, owner-final |

## 4. Fixture policy after the rejection

- Existing synthetic fixtures → **ENGINEERING_REGRESSION_FIXTURES**:
  they keep the measurement engine honest (determinism, invariants,
  reason codes) and are never again presented as visual-quality evidence.
- New library → **REAL_BOTTLE_GOLDEN_REFERENCES**: built only from
  owner-accepted reference packs; immutable after acceptance.
- Visual-quality percentages do not move because architecture documents
  exist (tracker enforced).

## 5. Milestones (inserted before VQR-2B-B)

| ID | Scope | Effort |
|---|---|---|
| RBV-1 | Real bottle reference standard + first owner reference pack intake | S–M (blocked on owner inputs) |
| RBV-2 | Deterministic visualization renderer (2a NumPy ortho; 2b Blender presentation) | M / M–L |
| RBV-3 | Standard visual review package (both modes, per camera/lighting contracts) | M |
| RBV-4 | Claude visual review contract execution (owner-budgeted provider calls) | S–M |
| RBV-5 | Real-bottle comparison gate (feeds VQR-2B-B silhouette fidelity) | M |

Dependencies: RBV-1 blocks everything (no reference, no truth). RBV-2a
can proceed against the M3 canonical profile in parallel with reference
intake; RBV-2b needs the Blender install decision. VQR-2B-B consumes
RBV-5.
