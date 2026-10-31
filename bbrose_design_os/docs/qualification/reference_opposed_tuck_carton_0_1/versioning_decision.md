# Versioning decision (§9)

**reference_opposed_tuck_carton stays at 0.1.**

2A-9B added domain VALIDATION (fail-closed gate) and the qualification framework; no formula or emitted geometry changed. Proof: the task-50 fixture reproduces the approved geometry hash `0f5b8bf6bc2aa8ce0678fad3099da2d3` and content hashes cut `fe5adb1f53dc3823…` / crease `108fbcb8d8b9e84f…` exactly (pinned by test_opposed_tuck_qualification.py).

If qualification ever requires changing a template constant or formula (e.g. a parametric dust-depth law for W < D + t + 20), that ships as reference_opposed_tuck_carton/0.2 — 0.1 stays registered for historical reproduction and its physical-test approval remains bound to its hash.
