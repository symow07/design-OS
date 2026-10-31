# 25 · Image guard

`apps/pipeline/services/image_guard.py` · chain step: **Every paid image call (its inputs and words)**

## What it does today (read from its code)
`check` (:213) refuses an image call's inputs before payment: a non-OpenAI provider, another model, a competitor's name
in the words, a missing file, a rejected house design, a web picture, a file outside `ALLOWED_ROOTS`. `guarded_call`
(:255) logs every call to `CALL_LOG`. `denylist` (:160) hashes every rejected and web picture. Its roots and log are
pinned to Day 12 (`ALLOWED_ROOTS` :57, `CALL_LOG` docs/audit/day-12/image-calls.jsonl, `TODAY_OPERATION_PREFIX`
'day12/'). The flow does not call `check`: round_calls, round_ideas_calls, round_files_job, round_files_faces and
round_designer use `competitor_in`, `_under` with `WEB_ROOTS`, `APPROVED_LOGO` and `denylist`.

## The run ($0)
`check` given round 3's own inputs as a flat painting would send them (the picked picture, the flat template) and a
prompt with a competitor's name; its refusal tests run.
Recorded in [runs/25.json](runs/25.json), made by `docs/consolidation/probe.py 25`. What came out:
- `allowed_roots`: ["/Users/symow/Desktop/bbrose-systemOS/docs/audit/day-12", "/Users/symow/Desktop/bbrose-systemOS/materials", "/Users/symow/Desktop/bbrose-systemOS/bbrose_design_os/var/design_intelligence/previews/materials", "/Users/symow/Deskto…
- `call_log`: /Users/symow/Desktop/bbrose-systemOS/docs/audit/day-12/image-calls.jsonl
- `picked_picture`: {"error": "ImageCallRefused: input /Users/symow/Desktop/bbrose-systemOS/docs/rounds/lip-gloss-product-and-counter-stand-9634b86f91/files/source.png (style reference) is outside the roots a Day 11 image call may draw on"}
- `flat_template`: {"error": "ImageCallRefused: input /Users/symow/Desktop/bbrose-systemOS/docs/rounds/lip-gloss-product-and-counter-stand-9634b86f91/files/flat/template.png (template) is outside the roots a Day 11 image call may draw on"}
- `competitor_word`: {"error": "ImageCallRefused: D-D8-7: the prompt names a competitor brand (Fenty)"}
- own tests (test_day8_concepts.py, -k "refused or rejected or competitor"): **6 passed, 46 deselected in 0.20s**
- seconds: 44.2; files written: 0 (kept in the run folder, not committed)

## Verdict: PARTLY
Good: the four parts the flow uses. Broken for the chain: `check` refuses the round's own pictures, because its roots
are Day 12's; the flow never calls it.

## Parts worth keeping
- `competitor_in`, `_under` + `WEB_ROOTS`, `APPROVED_LOGO`, `denylist` — what the flow uses.
