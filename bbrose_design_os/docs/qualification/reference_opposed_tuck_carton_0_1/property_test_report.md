# Property-based qualification sweep

Seed **20260722** (deterministic; a failing seed reproduces directly via `seeded_property_sweep(opposed_tuck_adapter(), seed=...)`).

- in-domain samples (must fully qualify): 150
- random space samples (qualify or fail closed): 250
- supported and invariant-clean: 189
- rejected by the domain with named constraints: 211
- failures / crashes / distorted geometry: **0**
- runtime: 0.6 s

Every supported combination held all §3 invariants (panel sequence, attachment, contours, slit/ear alignment, folded collisions, reconciliation, determinism). The same sweep runs in the test suite (test_opposed_tuck_qualification.py).
