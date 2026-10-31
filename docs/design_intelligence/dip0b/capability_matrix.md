# DIP-0B capability matrix

| Tier | Meaning | Examples |
|---|---|---|
| DIRECT | read from the PDF structure | boxes, path/raster counts, `/Separation` inks + `/All`, shading census, OCG names, live-text count (0) |
| HEURISTIC | inferred by rule, with confidence | region typing, dieline outcome, ΔE spot match, artwork descriptors, Level-A typography |
| REQUIRES_ILLUSTRATOR | locked in `/AIPrivateData` | layer hierarchy, live text, fonts, symbols, effects, swatch library |
| REQUIRES_HUMAN | only a designer settles it | wording, language, type style, SKU, era, ownership, final include/exclude |
