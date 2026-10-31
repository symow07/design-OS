# Palette Geometry Contract Proposal — `palette_geometry/1.0` (PALT-M1 §B)

**Status: PROPOSAL. No implementation in this milestone.**

## Core departure from the bottle engine

`container_geometry/1.0` builds a mesh by revolving/lofting a **profile**.
A palette has no profile. It is an **assembly of plates** whose outline is
a 2D silhouette extruded with edge treatment, plus pockets subtracted from
the tray.

```
palette_geometry/1.0
├── outer_silhouette      (2D closed curve + corner treatment)
├── plates[]              base, tray, lid, mirror_panel, insert
├── pockets[]             derived from pan_layout/1.0, never authored twice
├── mechanism_refs        hinge/clasp anchors (palette_mechanism/1.0)
└── states                CLOSED (authoritative) + OPEN (articulated)
```

## Outer silhouette families

RECTANGLE · SQUARE · CIRCLE · OVAL · ROUNDED_RECTANGLE · POLYGON ·
CUSTOM_SILHOUETTE.

Rules carried over from the container law:
- unknown family ⇒ refuse, never default;
- `CUSTOM_SILHOUETTE` requires ≥8 authoritative outline points (identical
  to the CUSTOM cross-section rule) — a custom shape exists only when
  evidence exists;
- corner radius is an explicit parameter, never inferred.

## Plate model

Each plate declares `thickness_mm`, `material_ref`, `outline` (usually the
outer silhouette, optionally inset) and `z_position`. Closed height is
therefore **derived, not authored**:

```
closed_height = base_plate + tray_depth + pan_depth_clearance
              + lid_plate + mirror_thickness + mechanism_clearance
```

This makes the height *checkable*: a proposed 12 mm case with 5 mm pans,
2 mm walls and a 1 mm mirror is arithmetically refutable. The bottle
pipeline learned this the hard way with overlapping heights in P2/P4
intake; palettes get it structurally from day one.

## Pockets

Pockets are **generated from `pan_layout/1.0`**, never authored
independently. One source of truth prevents the layout and the geometry
disagreeing — the class of defect that produced four P1 rejections.
Each pocket carries `clearance_mm` (default range 0.15–0.40, CALCULATED)
because pressed-powder pans have wide tolerance (patent R10).

## States

`CLOSED` is the authoritative geometry state (bounds, footprint, stacking).
`OPEN` is an articulated transform about the hinge axis by `open_angle_deg`
— it must never be modelled as a second, independently authored mesh, or
the two will drift.

## Validation (fail-closed)

- `PALETTE_GEOMETRY_INCOMPLETE` when silhouette, plates or layout missing
- `PALETTE_HEIGHT_INCONSISTENT` when declared height ≠ derived height
- `PALETTE_POCKET_OUT_OF_BOUNDS` / `PALETTE_POCKET_OVERLAP`
- `PALETTE_WALL_BELOW_MINIMUM` (vs the moulding ranges, R14)
- `PALETTE_MECHANISM_COLLISION` in the OPEN state
- mesh diagnostics reused unchanged (manifold, normals, components)

## Authority

`GEOMETRY_AUTHORITY = CAD_OR_VERSIONED_PALETTE_GEOMETRY`. Material and
colour are impossible to express in this record by construction — the same
separation that `container_geometry/1.0` enforces.
