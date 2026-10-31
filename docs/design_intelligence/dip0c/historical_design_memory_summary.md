# Historical design memory — DIP-0B

**`PILOT_VALIDATED`: 14 of 91 historical designs (15.4%). 77 remain unaudited.**

14 Illustrator files → 15 pages → **173 design units**. The method is proven; the corpus
is not audited.

## The contract: REFERENCE MEMORY ONLY

A historical design **teaches**. It never **templates**.

**DIP-1 may persist:**
- `descriptive_layout_observations`
- `hierarchy`
- `spacing_tendencies`
- `color_relationships`
- `typography_structure`
- `decoration_density`
- `product_category_context`
- `design_era`
- `approved_reference_previews`
- `semantic_tags`
- `confidence`
- `provenance`

**DIP-1 may NEVER persist:**
- `exact_reusable_placement_coordinates`
- `complete_historical_layouts`
- `reusable_dieline_paths`
- `copied_artwork_paths`
- `template_instructions`
- `automatic_reproduction_of_old_designs`

`assert_memory_safe()` **raises** on every excluded field. A historical design that could
be *reproduced* is not reference memory — it is a template, and templates are how a design
library quietly becomes a copying machine.

Posture: **`REFERENCE_MEMORY_ONLY`**. Retrieval requires human approval and excludes
restricted geometry.
