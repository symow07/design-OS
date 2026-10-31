# Representative physical-validation plan (§10)

Property-based testing qualifies the continuous domain TECHNICALLY; these representative samples validate the MANUFACTURING assumptions. One task-50 sample never production-confirms the archetype (TASK_50_GEOMETRY_APPROVAL_IS_INSTANCE_SPECIFIC; ARCHETYPE_FULL_DIMENSIONAL_QUALIFICATION is not granted).

Physical qualification is tracked separately per geometry hash, dimensional family, board thickness and printer/cutter/manufacturer (apps.dielines.services.physical_validation records).

| Family | fixture | inner W×D×H | t | geometry hash | status |
|---|---|---|---|---|---|
| small | small_shallow | 34.0×12.0×61.0 | 0.5 | `7c2612a4c1c6c1aa` | AWAITING SAMPLE |
| shallow | medium_shallow | 70.0×15.0×100.0 | 0.5 | `23efd35f4eded617` | AWAITING SAMPLE |
| deep | medium_deep | 70.0×49.0×110.0 | 0.5 | `2fc5c597ba46cc60` | AWAITING SAMPLE |
| tall | tall_narrow | 33.0×12.0×590.0 | 0.3 | `dc54e1018a13a769` | AWAITING SAMPLE |
| large | large_deep | 279.0×258.0×320.0 | 0.8 | `c157c49cd6c9247c` | AWAITING SAMPLE |
| task #50 | task_50_exact | 90.0×32.0×92.0 | 0.5 | `0f5b8bf6bc2aa8ce` | APPROVED FOR PHYSICAL TEST (user, 2026-07-22) |

Only recorded FIT_PASS results (100%-scale printed samples) advance anything; a screenshot or on-screen review never counts. Physical-test PDFs for the non-task-50 fixtures are generated on demand from the committed geometry hashes.
