# PALT-M4C §D — selected-concept dataflow audit

**Milestone** PALT-M4C · **Date** 2026-08-06 · **Method** repository trace,
not theoretical architecture. Every claim below names a file.

## Headline

`PALETTE_SELECTED_CONCEPT_USAGE: INSUFFICIENT` is confirmed, and the
mechanism is narrower and more definite than "insufficient":

> **No palette module imports any Django model.** Not `TaskReference`,
> not `DesignTask`, not `DesignBrief`. The entire palette system is a
> pure-function library driven by hardcoded contract literals.

Verified by:

```
grep -l "from apps.pipeline.models|TaskReference|DesignTask|DesignBrief" \
     apps/pipeline/services/palette*.py apps/pipeline/services/palt*.py
-> no matches
```

The selected concept is therefore not "under-used" by the palette
engine. It is **structurally unreachable** from it.

## Where the design actually enters, and how far it gets

| Stage | Implementation | Palette reach |
|---|---|---|
| task creation | `apps/pipeline/models.py::DesignTask` | none |
| reference upload | `models.py::TaskReference` (FileField, `REFERENCE_ONLY`) | none |
| signature-checked intake | `apps/pipeline/references.py` | none |
| concept generation | `apps/pipeline/agents/image_producer.py` | none |
| owner selection | `models.py::DesignBrief.selected_direction_id` (+ `direction_selected_at`), written by `views.py:420` | none |
| review board | `apps/pipeline/review_board.py` | none |
| reference resolution | `services/visual_reference_resolver.py::resolve_visual_references(task)` | none |
| container asset resolution | `services/container_asset_resolver.py::resolve_product_assets(product)` | none |
| reference manifest | `services/reference_manifest.py` | none |
| **palette contract** | `services/palt_p1.py::build_palt_p1(outer_width, outer_depth, outer_height, inter_pan_gap, outer_margin)` | **five floats, no design channel** |
| layout kernel | `services/palette_layout_kernel.py` | consumes the contract only |
| geometry builder | `services/palette_cored_tray_geometry.py` | consumes a numeric spec dict |
| renderer | `services/blender_scripts/m4b_a_tray_views.py` | consumes OBJ paths |
| evidence | `palt_m4b_a*_evidence.py` | consumes meshes |

## The exact loss point

`build_palt_p1()` is the boundary. Its complete signature is:

```python
def build_palt_p1(outer_width=None, outer_depth=None, outer_height=None,
                  inter_pan_gap=4.0, outer_margin=5.0) -> PaletteSpec:
```

Everything downstream — layout, stack-up, mechanism, tray geometry,
sections, thickness, rendering — is derived from the `PaletteSpec` this
function returns. There is **no argument, keyword or module-level hook**
through which a selected concept, a `TaskReference`, a Design Graph node
or an owner selection can influence it.

So concept data is not "discarded" at some point inside the palette
pipeline. It never crosses into it. The loss point is the **absence of an
input channel**, which is why no amount of downstream tuning would have
surfaced it.

## What is preserved vs discarded

* **Preserved (but unused by palettes):** the uploaded file, its kind
  (`container|logo|label|inspiration|color`), original filename, media
  type, size, ordering, `REFERENCE_ONLY` status, and the owner's
  `selected_direction_id`. All of this is durable in the database.
* **Never extracted at all:** silhouette, proportion, corner character,
  pan count, pan placement, margins, spacing rhythm, mirror proportion,
  hinge/clasp position, material impression, colour zones, artwork zones,
  typography zones, style character. No component in the repository
  converts a palette concept image into structured design intent.
* **Replaced by generic defaults:** every dimension in `palt_p1.py`
  (`PROPOSED_OUTER`, the 26.0 mm pan, the 3×3 module lattice, the 4.0 mm
  gap, the 5.0 mm margin) and every value in `palette_stackup_engine.ALLOWANCES`.

## Does the selected concept affect anything?

| Aspect | Affected today |
|---|---|
| geometry | **No** |
| layout | **No** |
| materials | **No** |
| artwork | **No** |
| visual validation | **No** |

## Why containers are different

The bridge already exists for containers and was simply never extended:

* `container_asset_resolver.resolve_product_assets(product)` classifies
  references and returns a permitted-use decision per asset.
* `visual_reference_resolver.resolve_visual_references(task)` returns a
  `VisualReferenceBundle` with `approved_reference_ids`, `has_logo`,
  `reference_file_paths` and an `_influence_plan`.
* `apps/ire/container_concept_fidelity.py` and `concept_fidelity.py`
  already compare generated container output against the selected concept.

None of these are referenced by any palette module. The palette target
was built as a parallel stack that reuses the geometry discipline but
none of the design-intake discipline.

## Consequence for the roadmap

`PALETTE_DESIGN_INTENT_BRIDGE: NOT_IMPLEMENTED` is accurate, and the
remedy is additive rather than corrective: the palette contract needs an
optional `PaletteDesignIntent` input, and the geometry it drives must
record which values came from intent and which fell back to a labelled
default. No existing palette geometry has to be discarded to do it.

## Authority

This audit is a repository finding only. It establishes no manufacturing
authority and approves nothing. The selected AI concept remains
`DESIGN_INTENT_REFERENCE` and never becomes CAD, supplier or tolerance
authority.
