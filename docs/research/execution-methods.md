# Execution methods: building faces in layers, matching the pick

The owner's goal of 2026-10-29 ("Execution: match the pick, build in layers"), §3. What was searched, what was found,
what was adopted into the existing engines (the stand die solver, the face builder, the writer) and what was rejected.
Rule: only MIT, BSD or Apache code is linked into the app.

## Found

| Method | What it is | Licence | Fit |
|---|---|---|---|
| Geometric primitive fitting with OpenCV (contours, `approxPolyDP`, `HoughCircles`, `fitEllipse`, `minAreaRect`, k-means) | segment a face into colour regions, then fit each region's boundary as circles, arcs, lines and polygons | Apache-2.0 (OpenCV 4.5+), already in the app | **high**: rings, arcs, dial ticks, medallions, frames, rules and flat fields are primitives |
| Robust circle and arc fitting: RANSAC to drop outliers, then a Taubin (or Pratt) algebraic refit on the inliers | the standard pipeline for circles from edge points; Taubin stays stable on short arcs, unlike the simple Kasa fit | algorithm (written in our code from the published method) | **high**: the dial's bands and rims are arcs seen only in part |
| Arc-spline segmentation (split a contour where one arc no longer fits within tolerance; recurse) | turns any boundary into a path of arcs and lines within a stated tolerance | algorithm | **high**: gives the 0.2 mm edge bound by construction |
| VTracer | colour raster to layered SVG with a stacking strategy (no shapes with holes), O(n) | MIT, already installed (0.6.15) | **medium**: for the free-form residue the primitives cannot fit |
| Potrace | bitmap to Bezier outlines, binary input only | GPL-2.0-or-later | rejected for linking (licence) |
| LIVE: Towards Layer-wise Image Vectorization (CVPR 2022) | adds Bezier paths layer by layer by differentiable rendering; compact, semantically layered SVG | code under its own licence (not verified); needs PyTorch and DiffVG, minutes per image on a GPU | rejected: heavy, slow, licence unverified, no gain over primitives for geometric artwork |
| Packaging prepress practice | the die on its own locked, non-printing layer; artwork on its own layer; each finish (foil, spot UV, emboss) on its own layer; type kept clear of the safe line | practice | **high**: our layer names follow it |

## Adopted

- **Primitives first, in the face builder:** each painted face is split by colour (k-means in Lab over its printed
  pixels); the ground becomes the BACKGROUND fill (the shape check's ground on the stand); each region's boundary is
  fitted as arcs and lines by arc-spline segmentation with RANSAC + Taubin circle fits (tolerance 0.2 mm), into
  SHAPES (large regions), ORNAMENT (metallic and small closed shapes) and LINEWORK (thin strokes).
- **Raster only where it is painted:** what the vectors cannot reproduce (shading, texture, gradients) is kept as a
  clipped raster on TEXTURE, its alpha the colour difference between the painting and the vector render.
- **The layer convention:** BACKGROUND, SHAPES, ORNAMENT, LINEWORK, TEXTURE, TYPE, LOGO, DIE (the die locked,
  non-printing), in the writer's .ai.
- **The shape check:** the header outline fitted against square, rounded, quadrant and arched shapes by overlap; the
  board's ground by k-means on the picture's panels (OpenCV, Apache-2.0).

- **As built (624b5a0):** VTracer is allowed but not called: what the fitted primitives cannot hold within the bar
  stays the clipped TEXTURE raster, never traced. Each vector edge is measured pixel by pixel against the painting's
  colour edges (Canny on L, a and b) and the die's edge; the region is snapped onto a painted edge within 0.4 mm and
  fitted to 0.1 mm; a piece whose edge misses 0.2 mm anywhere stays texture.

## Rejected, and why

- Potrace: GPL; it may not be linked into the app (it was the old lid tracer's, now archived).
- LIVE and other differentiable vectorisers (DiffVG-based): heavy GPU dependencies, slow, licence not verified, and
  our artwork is geometric: fitted primitives are exact where they hold and cheaper.
- Blind pixel tracing of whole faces: what the owner asked to end; VTracer stays a fallback for free-form residue
  only, never the face.

## Sources

- [LIVE: Towards Layer-wise Image Vectorization](https://ma-xu.github.io/LIVE) ([CVPR 2022](https://openaccess.thecvf.com/content/CVPR2022/html/Ma_Towards_Layer-Wise_Image_Vectorization_CVPR_2022_paper.html))
- [Comparison of raster-to-vector conversion software](https://en.wikipedia.org/wiki/Comparison_of_raster-to-vector_conversion_software) (VTracer MIT, Potrace GPL)
- [VTracer project summary](https://www.sourcepulse.org/projects/1198891)
- [Outlier detection algorithm for circle fitting](https://arxiv.org/pdf/2508.03720) (RANSAC, Taubin, Pratt compared)
- [Circle Fit (Taubin method)](https://www.mathworks.com/matlabcentral/fileexchange/22678-circle-fit-taubin-method)
- [Packaging artwork setup and dieline guidelines](https://www.customboxmakers.com/dieline-design-tips/), [Packaging dieline best practices](https://link.kohls.com/content/dam/klink/pdfs/Packaging-Dieline-Best-Practices.pdf), [Adobe community: packaging artwork in Illustrator](https://community.adobe.com/questions-652/what-is-the-best-way-to-prepare-packaging-artwork-for-print-in-illustrator-1643720)

Annotation, 2026-10-30 (the owner's part 1, CURRENT_DECISIONS.md): the fitting adopted here (OpenCV primitives, RANSAC and Taubin arcs, the prepress layer convention over a painting) is no longer used on any print file: laid over a painting it cracked it. A fitted shape would need to match the painted edge everywhere within 0.1 mm, a layer and the owner's word.
