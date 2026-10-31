# Mechanical System Proposal — `palette_mechanism/1.0` (PALT-M1 §D)

**Status: PROPOSAL. No implementation in this milestone.**

## Scope

Hinge · clasp · mirror · lid · opening angle · applicator compartment ·
sliding · rotating · folding · layered structures.

## Contract sketch

```
palette_mechanism/1.0
├── kind          HINGED | LIFT_OFF | SLIDING | ROTATING | FOLDING | LAYERED
├── hinge         { family, axis, pin_diameter_mm?, clearance_mm }
├── clasp         { family, position, magnetic { count, diameter_mm }? }
├── mirror        { present, coverage, thickness_mm, inset_mm }
├── open_state    { open_angle_deg, collision_checked }
├── applicator    { NONE | BRUSH_SLOT | PUFF_COMPARTMENT | UNDER_TRAY_DRAWER,
│                   cavity_mm }
└── levels        { count, engagement_mm }        // multi-level/stacked
```

## What research supports (and what it does not)

- Hinge families: gudgeons + pivot pin + resilient snap jaws is the classic
  compact family (R12); living hinges and external barrels also exist (R10).
- **Open angle is a functional requirement, not styling**: the lid must
  reach an obtuse angle so the mirror faces the user (R12). No public
  source states a number — our proposed 100–135° is a `DESIGN_DEFAULT` and
  is explicitly unvalidated.
- Clasps: mechanical detent or magnetic (R13); magnetic closure is also a
  refill-system norm (R15).
- **Unknowns that must not be invented**: mirror thickness and attachment,
  hinge pin diameter, gudgeon dimensions, clasp retention force, magnet
  grade/pull. These are recorded as gaps, not filled with plausible-looking
  numbers.

## Rules

1. The OPEN state is an articulated transform of the CLOSED geometry —
   never a second authored mesh.
2. Collision checking in the OPEN state is mandatory (`MECHANISM_COLLISION`):
   lid must clear the tray, mirror must clear the pans.
3. Mirror is simultaneously a plate (geometry) and a material (mirror
   finish) — the two are declared separately, never merged.
4. Any mechanism dimension without a source is tagged `DESIGN_DEFAULT` and
   can never be presented as manufacturable.
5. Multi-level and sliding structures declare `engagement_mm` so the closed
   height stays derivable.
