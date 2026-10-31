# Palette Risks and Unknowns (PALT-M1)

## Critical risks

**RK-1 — Visual-fidelity risk repeats.** P1 needed four revisions and was
still not approved. Palettes have *more* surfaces (case, lid, mirror, nine
powder faces) and therefore more ways to look wrong.
*Mitigation:* the finish-differentiation board and side-by-side owner
review are gates, not extras; no pilot proceeds to full evidence until its
material specification is accepted in isolation.

**RK-2 — No manufacturer-authoritative reference exists.** Every dimension
found is a supplier catalogue, retailer listing or patent. No public
technical drawing with tolerances was obtainable.
*Mitigation:* everything is tagged; nothing claims manufacturing accuracy;
a supplier drawing remains the only path to `MANUFACTURER_CONFIRMED`.

**RK-3 — Pan tolerance is genuinely wide** (stated in patent R10, never
quantified anywhere). A pocket sized to a nominal 26 mm pan may not accept
real pans.
*Mitigation:* clearance is an explicit parameter (0.15–0.40 CALCULATED);
retention must be compliant; refill compatibility is validated, not assumed.

**RK-4 — Patent entanglement.** Refillable palettes are a dense patent
area (sliding drawers, spring tabs, living hinges, tray locks, magnetic
clasps).
*Mitigation:* the "must not be copied" list is recorded per reference;
PALT-P3 deliberately uses only long-established generic magnetic retention;
any mechanism resembling a claimed one needs legal review before tooling.
**This is a legal matter that engineering cannot clear.**

**RK-5 — Open/closed state divergence.** Authoring two meshes would let
them drift.
*Mitigation:* OPEN is an articulated transform only; collision-checked.

**RK-6 — Layout/geometry double authorship.** If pockets and layout are
authored separately they will disagree.
*Mitigation:* pockets are generated from `pan_layout/1.0` — one source.

**RK-7 — Material engine coupling.** If palettes ship their own powder
shaders, GME-M1 and palettes diverge immediately.
*Mitigation:* palettes may only consume the material engine; a palette-
local shader is a review failure.

**RK-8 — Scope explosion.** Eleven taxonomy axes multiply fast.
*Mitigation:* three pilots only; every other combination stays declarative
until asked for.

**RK-9 — Artwork complexity is underestimated.** Palettes need lid, base,
interior and *per-pan* shade labels with regulatory zones — more artwork
surfaces than any bottle.
*Mitigation:* artwork treated as its own phase (PALT-M6), not folded into
geometry.

## Explicit unknowns (never to be invented)

mirror thickness and attachment · hinge pin and gudgeon dimensions · clasp
retention force · magnet grade/thickness/pull · draft angles · numeric pan
tolerance · standard open angle in degrees · BBROSE's own preferences on
format, size, refillability and price positioning.

## Open owner decisions

1. **Architecture** — approve HYBRID (recommended), or choose container-
   family or fully-dedicated.
2. **Refillability** — is refill a BBROSE product promise? It changes
   retention, tolerance and cost.
3. **Format priority** — which pilot first? (recommendation: PALT-P1.)
4. **Size positioning** — compact/travel, standard, or pro/large.
5. **Case material** — ABS baseline, or aluminium/PCR/paperboard for
   sustainability positioning.
6. **Mirror** — required on every palette?
7. **Whether to seek supplier technical drawings**, the only route to
   `MANUFACTURER_CONFIRMED` dimensions.
