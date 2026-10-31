# Renderer Evaluation — RBV-2 proposal

**Status: PROPOSED — 2026-08-04. Nothing implemented in this slice.**

## Environment audit (§4, verified on this machine)

| Capability | Finding |
|---|---|
| Blender | **NOT installed** (no `/Applications/Blender.app`, no CLI, no `bpy`) |
| 3D/CAD Python libs | none (no trimesh/open3d/moderngl/pyrender) |
| Current renderer | 2D/2.5D: ReportLab (vector PDF/AI) + PyMuPDF + `sips` rasterization + PIL/NumPy compositing |
| Material rendering | flat fills + opacity stacks only (2C-2E frosted look is layered 2D) |
| Headless capability | current stack fully headless/CI-safe; Blender supports `blender -b -P` headless on macOS |
| Determinism | current stack fully deterministic; Blender deterministic with fixed seeds, fixed samples, denoiser pinned |
| CI/test constraints | shared test Postgres; suites must run exclusively — renderer must be callable in-process or as a hermetic subprocess with pinned assets |
| Storage/artifacts | evidence-file pattern established (docs/visual_quality/*) + PackagingOutput file fields |
| Adobe Illustrator 2026 | installed — execution-verification seam exists from Gate A, NOT a 3D renderer |

## Recommendation: two-tier renderer

**Tier 1 — RBV-2a: deterministic NumPy/PIL revolve renderer (no new
dependencies).** The M3 half-width profile *is* a surface-of-revolution
profile. A lathe of the canonical dense profile + orthographic projection
+ Lambert shading (fixed light) covers every GEOMETRY VALIDATION view
(front/side/top ortho, closure detail, structure-only, overlays,
deviation views) — CI-safe, hermetic, byte-deterministic. It cannot do
credible glass/metal PBR, and that is acceptable: geometry validation
explicitly forbids material effects that conceal geometry.

**Tier 2 — RBV-2b: headless Blender (owner-approved install) for CLIENT
PRESENTATION renders.** Pipeline: deterministic product geometry →
revolved/extruded 3D form (script-generated mesh from the same canonical
profile) → standardized cameras (`real_bottle_camera_standard/1.0`) →
standardized lighting (`real_bottle_lighting_standard/1.0`) → PBR
materials (glass IOR 1.5, frosting, metal collar, rubber bulb) → PNG
review package. Install options for owner approval: `brew install --cask
blender` or the LTS dmg (~350MB). Version pinned; renders reproduced
from checked-in scene scripts, never hand-edited .blend files.

**Authority boundary (both tiers):** the Product Container geometry and
editable AI remain the structural authority; the renderer is a
visualization layer only. GPT Image is never geometric authority or
comparison truth.

## Effort and risk

| Item | Effort | Risk |
|---|---|---|
| RBV-2a revolve renderer + camera/lighting contracts | M | LOW — pure NumPy, deterministic, testable against the canonical profile |
| RBV-2b Blender integration | M–L | MEDIUM — install approval, version pinning, determinism discipline, macOS GPU/CPU render variance (mitigate: CPU-only, fixed samples) |
| Real-reference comparison plumbing (RBV-5) | M | MEDIUM — depends on reference-pack quality; fail-closed on INCOMPLETE packs |

## Rejected alternatives

- **GPT-Image/other generative renders as evidence** — forbidden: not
  deterministic, not geometric truth, and the exact failure mode the
  owner rejected.
- **Large CV/3D dependency (open3d, trimesh+pyrender)** — unnecessary for
  revolution solids; violates the "no large dependency without documented
  insufficiency" rule. Documented insufficiency exists only for PBR — and
  Blender covers that without entering the Python dependency tree.
- **Illustrator scripting as renderer** — execution-verification tool,
  wrong tool for lit 3D presentation.
