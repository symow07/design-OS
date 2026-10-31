# Revised Quality Critical Path — 2026-08-04 (RBV insertion)

Owner rejection of abstract fixtures inserts the Real Bottle
Visualization program before reconstruction-side comparison. The
tracker's validated `critical_path_nodes` is the machine copy of this
path.

```
DONE   VQR-6  single artifact/status authority        (owner accepted)
DONE   VQR-2A fail-closed visual quality gate          (owner accepted)
DONE   VQR-1  M3 backbone integration                  (conditionally accepted,
                                                        structural scope; 35×95
                                                        rejected by proportion
                                                        policy)
DONE*  VQR-2B-A concept-side analysis                  (*engine validated;
                                                        visual evidence
                                                        REJECTED as abstract)
──────────────────────────────────────────────────────────────────────
NEXT   RBV-1  real bottle reference standard + owner reference pack
       │        (BLOCKED on owner inputs — see pilot recommendation)
       ├─ RBV-2a deterministic ortho renderer (parallel; M3 profile)
       ▼
       RBV-2  visualization renderer (2a geometry / 2b Blender presentation)
       ▼
       RBV-3  standard visual review package (both modes)
       ▼
       RBV-4  Claude visual review contract execution (owner-budgeted)
       ▼
       RBV-5  real-bottle comparison gate
       ▼
       VQR-2B-B reconstruction-side comparison
                (canonical bounds 3.0606; production sizing alignment;
                 bounded-adaptation refusal after 1.05 calibration)
       ▼
       Design Graph 2.0 + typography authority + minimum component library
       ▼
       VQR-3 artwork composition → VQR-4 typography → adjustment studio
       ▼
       VQR-5 materials → CLIENT_PRESENTATION_ARTBOARD → ACC-2 acceptance
```

**What changed**: RBV-1…RBV-5 now precede VQR-2B-B; the golden fixture
node is reclassified ENGINEERING_REGRESSION_FIXTURES; a future
REAL_BOTTLE_GOLDEN_REFERENCES library node exists NOT_STARTED; the M3
proportion-policy calibration verdict now happens on RBV evidence, not
abstract renders. No visual-quality percentage moved from documentation
alone.

**Owner reviews expected**: RBV-1 pack acceptance · RBV-2b Blender
install approval · RBV-3 first real review package · RBV-4 budget
authorization · RBV-5/2B-B calibration verdict.
