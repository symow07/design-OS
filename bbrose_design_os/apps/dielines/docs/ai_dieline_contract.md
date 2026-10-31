# BB Rose OS — AI Dieline Contract

Version: 1.0
Date: 2026

## What Claude is allowed to generate

- Product dimensions (width_mm, depth_mm, height_mm) as estimates
- Bleed and margin settings as estimates
- Construction parameters (glue_tab, top_flap, bottom_flap) as estimates
- Confidence scores per field (0.0–1.0)
- Source attribution per field (image / text / pdf / db / manual)
- Metadata (product_name, product_type, notes)
- Inspiration references from past approved designs

## What Claude is NOT allowed to generate

- SVG files or SVG path data
- Vector coordinates of any kind
- Cut line geometry
- Fold line geometry
- Dieline panel positions
- Illustrator-compatible output
- Any geometry whatsoever

## Why this rule exists

AI language models do not produce deterministically accurate geometry.
A 0.1mm error in a carton dieline can cause a print run to fail.
All geometry in BB Rose OS is generated exclusively by deterministic
Python code in apps/dielines/geometry/.

Claude's role is to estimate dimensions from context and return
strict JSON. A human confirms those dimensions before geometry runs.
The geometry engine then produces exact, validated coordinates.

## Confidence threshold

Fields with confidence >= 0.85 are pre-filled with an estimated tag.
Fields with confidence < 0.85 are left blank and require manual entry.
No dieline is generated until all 8 required fields have valid values.

## The output pipeline

Claude → DimensionExtractionResult JSON
→ Human confirms form
→ DielineInputJSON (validated by Pydantic)
→ calculate_straight_tuck_end() (pure Python)
→ DielineCoordinates
→ export_svg() (svgwrite)
→ validate_svg()
→ SVG file saved to exports/
→ DielineJob stored in PostgreSQL

At no point in this pipeline does Claude touch geometry.
