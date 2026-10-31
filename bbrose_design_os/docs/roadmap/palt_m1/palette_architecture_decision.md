# Palette Architecture Decision (PALT-M1 §8)

**Status: RECOMMENDATION — owner decision required.**

## Options considered

**A. Specialized Product Container family.** Palettes become another
archetype inside the existing Product Container target.
*Rejected.* The container target is built around an axisymmetric or
lofted **profile revolve** with a closure stacked on top. A palette is
not a profile: it is an assembly of plates, a module lattice, a hinge with
two articulated states, and artwork on several faces. Forcing palettes
into the bottle silhouette architecture would corrupt both — precisely
what the owner instruction forbids.

**B. Fully dedicated Design Target, built from scratch.**
*Rejected.* It would duplicate machinery that P1 already proved and that
is product-agnostic: the geometry-authority record, mesh diagnostics, the
pinned Blender runtime, the unlit-alpha mask authority, the neutral-clay
vs material render separation, the versioned evidence package and the
strict owner-review loop. Duplication would let the two diverge.

## Recommendation: **HYBRID**

> **Palettes are a dedicated Design Target with its own geometry and
> layout contracts, sitting on the shared, product-agnostic engine
> layers.**

```
                 shared engine layers (reused as-is)
  ┌──────────────────────────────────────────────────────────┐
  │ geometry authority record · mesh diagnostics · pinned     │
  │ Blender runtime · mask authority (unlit alpha) · neutral  │
  │ clay vs material modes · generalized material engine      │
  │ (GME-M1) · evidence packaging · owner-review gates        │
  └──────────────────────────────────────────────────────────┘
        ▲                                   ▲
        │                                   │
  Product Container target            PALETTE target  ← NEW
  (profile revolve + closure)         (plate assembly + module lattice
                                       + mechanism + open/closed states)
```

### What the palette target owns exclusively
- `palette_geometry/1.0` — case/lid/tray plates, not profiles
- `pan_layout/1.0` — the module lattice and occupancy
- `palette_mechanism/1.0` — hinge, clasp, mirror, open angle, states
- powder surface treatment *as a consumer of the material engine*
- multi-face artwork zones (lid top, base back, interior, per-pan labels)

### What it must NOT own
- its own material system (uses GME-M1)
- its own renderer, mask logic or evidence format
- any manufacturing authority

## How the recommendation accounts for the owner's stated factors

| Factor | Handled by |
|---|---|
| variable geometry | dedicated outer-silhouette engine (7 families incl. CUSTOM) |
| complex internal layouts | module lattice with multi-module occupancy |
| open and closed states | mechanism contract carries an articulated state; both states are mandatory evidence |
| powder materials | material engine finishes (matte/shimmer/metallic/glitter/satin/baked/marbled) |
| mirrors and mechanisms | mechanism contract; mirror is a material + a plate |
| artwork reconstruction | multi-face artwork zones feeding the existing IRE/.AI path |
| Illustrator export | unchanged artwork authority — palettes add zones, not a new exporter |
| future gift sets | a palette is a placeable component with a declared footprint |
| future display stands | same footprint contract drives stand cavities |

## Consequences if the owner chooses otherwise

Choosing (A) would require the container profile engine to gain plate and
lattice concepts it was explicitly designed not to have, and would put the
bottle regression fixtures at risk. Choosing (B) would double the surface
that every future engine improvement must be applied to. The hybrid is the
only option that keeps P1 as a stable regression fixture while letting
palettes have honest geometry.

**Owner decision required before PALT-M2 begins.**
