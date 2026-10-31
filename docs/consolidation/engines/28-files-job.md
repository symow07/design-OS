# 28 · Files job

`apps/pipeline/services/round_files_job.py` · chain step: **Make my files (the build's steps and its paid context)**

## What it does today (read from its code)
`run_step` (:501) runs read, stand, faces and files; `execution_brief` (:74) turns missing sizes into marked estimates;
`read_picture` (:331) is the paid reading of the picked picture; `prepare_stand` (:432); `build_outputs` (:446) writes
every object and the drawing; `provider_check` (:36), `checked_inputs` (:318), `input_snapshot` (:93), `tag_completed`
(:480); its paid face context downloads through image_producer.download_image_bytes.

## The run ($0)
Round 3's brief made an execution brief; the job tests of the files page file run.
Recorded in [runs/28.json](runs/28.json), made by `docs/consolidation/probe.py 28`. What came out:
- `estimates_mm`: {}
- `dimensions_mm`: {"depth": 15.0, "width": 15.0, "height": 100.0, "cap_height": 30.0}
- own tests (test_round_files_page.py, -k "job or read or provider"): **12 deselected in 0.30s**
- seconds: 1.1; files written: 0 (kept in the run folder, not committed)

## Verdict: GOOD

## Parts worth keeping
- `execution_brief`, `read_picture`, `prepare_stand`, `build_outputs`, `run_step`.
