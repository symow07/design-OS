# Generalized Material & Colour Engine — Roadmap (GME-M1)

**Status: PROPOSAL — NOT IMPLEMENTED. No modelling, no Blender work, no
image generation in this milestone.**

P1 proved the render pipeline but hard-coded its material values (an
orange serum bottle). This milestone converts that P1-specific logic into
a parameter-driven system so any container can change colour, finish,
transparency, contents and closure materials **without rebuilding its
geometry**.

## The load-bearing rule

> Geometry identity MUST remain unchanged when only material parameters
> change.

Concretely: `build_*_assembly()` returns mesh identities; a material
change must not alter a single one. This is testable and will be
test-enforced (`material_change_preserves_mesh_identity`).

## Authority separation (extends the existing container_geometry law)

| Authority | Owns | Never owns |
|---|---|---|
| `GEOMETRY_AUTHORITY` | shape, dimensions, mesh identity | colour, finish |
| `MATERIAL_SPECIFICATION_AUTHORITY` | material class, finish, optical parameters | shape, dimensions |
| `COLOUR_AUTHORITY` | colour values + their provenance | physical form |
| `ARTWORK_AUTHORITY` | editable .AI artwork, typography | 3D form, render look |
| `RENDER_SCENE_AUTHORITY` | lighting, camera, exposure | anything above |

**No render material ever confers manufacturing authority.** A rendered
finish is an appearance approximation, never a specification a supplier
can tool from. Colour values carry provenance exactly like dimensions
(`OWNER_CONFIRMED`, `ONLINE_ANALOGOUS_REFERENCE`, `MEASURED_FROM_SAMPLE`,
`DESIGN_DEFAULT`) and a rendered colour is never promoted to a print or
masterbatch colour without its own physical authority (Pantone/lab dip).

## Required capability matrix

Materials: glass, plastic, acrylic, aluminium, rubber, powder.
Finishes: glossy, matte, frosted, satin, metallic.
Transparency: clear, tinted, translucent, opaque.
Contents: fill colour, fill transparency, fill level, volume absorption.
Optical: surface roughness, IOR, transmission, thickness.
Components: per-component material assignment (body / closure / collar /
bulb / applicator / contents / mirror / pan).
Scenes: studio lighting presets, neutral validation mode, client
presentation mode.

## Phases

- **GME-1 — Contract.** `material_specification/1.0` (see
  `generalized_material_contract_proposal.json`): a structured, validated
  specification with provenance per field. Fail-closed on unknown material
  or finish. No renderer changes.
- **GME-2 — Resolver.** Pure function `resolve_material(spec) -> shader
  parameters`. Deterministic, unit-tested against a table of expected
  optical outputs; includes the Beer-Lambert solver
  (`absorption_for_target_transmission(target_rgb, path_mm)`) that
  replaced guesswork in P1 V4.
- **GME-3 — Renderer adaptation.** The Blender studio script consumes
  resolved parameters instead of literals. **Every existing fixture must
  render byte-identically when the new path is disabled** (the standing
  non-regression rule).
- **GME-4 — Preset library.** Named presets (`frosted_amber_glass`,
  `gloss_black_acrylic`, `brushed_aluminium`, `matte_soft_touch_abs`,
  `pressed_powder_matte`, …) that are **starting points, not a closed
  list** — an arbitrary spec is always valid.
- **GME-5 — Colour system.** Colour entries with provenance and an
  explicit "render colour ≠ production colour" barrier.
- **GME-6 — Scene modes.** `NEUTRAL_VALIDATION` (clay, geometry truth) and
  `CLIENT_PRESENTATION` (studio) as declared modes, never interchangeable
  as evidence.

## Dependencies

Reuses `container_geometry/1.0`, the pinned Blender runtime, the unlit
alpha mask authority and the evidence-package pattern — all proven in P1.

## Exit criteria

Contract + resolver defined and tested; a single container renders in ≥3
distinct material specifications with **identical mesh identities**;
existing P1 V1–V4 fixtures unchanged; preset library documented as open;
owner review requested.

## Relationship to PALT-M1

The palette powder-material engine (PALT-M1 §E) is a **consumer** of this
engine, not a parallel implementation. Powder finishes are material
specifications, not bespoke palette code.
