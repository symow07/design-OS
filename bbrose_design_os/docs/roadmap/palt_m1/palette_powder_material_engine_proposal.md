# Powder & Eyeshadow Material Engine Proposal (PALT-M1 §E)

**Status: PROPOSAL. Consumer of the generalized material engine (GME-M1),
NOT a parallel implementation.**

## Requirement

Matte · shimmer · metallic · glitter · satin · baked · marbled · pressed
powder · loose-powder visual reference. **Each finish must look physically
different** — not a colour swap.

## Approach: finishes are material specifications

Each powder finish is a `material_specification/1.0` with
`material_class: POWDER` and a distinct optical signature:

| Finish | Distinguishing optical treatment |
|---|---|
| MATTE | high roughness, no specular lobe, slight surface irregularity |
| SATIN | mid roughness, broad soft specular lobe |
| SHIMMER | base matte + fine sparse high-specular flakes |
| METALLIC | high `metallic`, tight specular lobe, directional response |
| GLITTER | sparse large flakes with strong random normals — visibly discrete |
| BAKED | domed surface + subtle swirl variation + satin base |
| MARBLED | two or more colour fields blended across the pan surface |
| PRESSED | flat pressed surface with faint pressing texture and edge relief |
| LOOSE (reference) | granular, no pressed face — visual reference only |

The **surface** of a pan is also geometry-adjacent: baked domes and pressed
surfaces differ in form, so the pan surface carries a small
`surface_profile` (FLAT · DOMED · SWIRLED · EMBOSSED) owned by the palette
geometry contract, while its appearance stays in the material spec.

## The lesson carried from P1

P1 V2/V3 were rejected as "opaque brown" because appearance was tuned by
guessing shader numbers. Powder finishes must be defined by **stated
optical intent plus a validation image set**, and a finish is only accepted
when the owner can see the difference side by side. A "finish differentiation
board" (all nine finishes, same colour, same lighting) is therefore a
required deliverable of PALT-M4, not an optional extra.

## Non-goals

No claim that a rendered powder finish predicts a real formulation's
appearance. Pigment behaviour, pressing pressure and binder are formulation
matters with no authority here.
