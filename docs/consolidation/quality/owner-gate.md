# The owner gate — quality

**Job:** each face's jobs (draw, preview, eye), the owner's Accept or Redraw per face, then Make my files.
File: `apps/pipeline/services/round_files_gate.py`.

**The bar, in numbers:** one paid call per worker delivery; a claim's cap enforced before each call; nothing made
without the owner's Accept on every face; a designer round's flat pick reaches the files; a stale die solved again at $0.

**Before → after, same input.**
- The flat pick: before, `start` refused a `flat_die_handoff/1` pick (`FLAT_PICK_WAITS`): the chain stopped at the
  design pick. After (`15cbaac`): the picked flat painting is installed at $0 and the faces start
  (T/test_round_files_faces.py::test_a_flat_pick_starts_its_files_and_reaches_every_face_waiting_for_the_owner).
- Round 3's real run: restand solved its stand again for the sightline ($0), flatten claimed attempt 3 from the owner's
  policy, 13 edits under its $3 (spent $2.5137), the system's one redraw on four flagged panels, the back made from the
  board at $0, every face drawn and previewed, the proof sheet made — then it waits: 8 of 8 faces drawn, 0 accepted.
- Make my files on a copy of round 3's current drawings (`engines/runs/chain-live-1029.json`): bottle-front.ai, cap.ai,
  stand.ai (15 checks each, Illustrator's save 14 and reopen 13 checks each), die.pdf / die.dxf / die.cf2 /
  assembly.pdf read back within 0.0003 mm, 11 files in the zip.
The parts moved in (the files outbox and job, `build_stand`) are identical to their donors but for import repointing
and the sightline default (`runs/moved-parts.json`).

**Verdict: BETTER** — the chain's one break closed; the system repairs once and then hands the face to the owner.

**Weakest point:** two real-run faults were found only by running it (the flat folder left on an old die; a board face
made but not saved), each fixed with a test; a third kind may be waiting in a path no real run has taken yet.
