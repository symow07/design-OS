# How to Design on a Custom Pouch Dieline (PackMojo)

## Source

- Title: How to Design on a Custom Pouch Dieline | Packaging Design 101
- Channel: PackMojo (855 subs; converter's own design-guidance series — same
  series as the folding-carton dieline note Bf7XPpnwQrE)
- URL: https://www.youtube.com/watch?v=WdCpQLeuNqg
- Duration: 1:43 · Watched: 2026-08-24
- Transcript source: auto captions (tabbed panel, shadow-root scrape)
- Detail mode: transcript-only

## Claims

1. `t=0:12`–`t=0:17` A pouch dieline ships with a companion **orientation
   guide** — designers are told to check placement against it, not the dieline
   alone.
2. `t=0:34`–`t=0:38` Bleed rule restated for pouches: artwork at the edge must
   extend beyond the die line.
3. `t=0:42`–`t=0:44` Format split: custom pouches come as **stand-up pouches**
   and **flat pouches**.
4. `t=0:50`–`t=0:55` A stand-up pouch is made from **three sheets of film**:
   front, back, and bottom (the bottom sheet forms the gusset).
5. `t=1:00`–`t=1:10` All three panels (front, back, bottom) keep the SAME
   artwork orientation on the dieline — no rotated panels, unlike carton
   dielines where glue-flap panels can be inverted.
6. `t=1:14`–`t=1:16` Designs placed on the corners will not be visible after
   assembly — corner zones are loss zones.
7. `t=1:18`–`t=1:23` Final check is against the orientation guide for location
   and orientation before handoff.

## Engine hooks

- Claim 4 gives the structural model for `pouch_standup`: 3-web construction
  (front/back/bottom-gusset). The bottom gusset is a real printable panel —
  engine artwork zoning must treat it as a third face, not a fold-under.
- Claims 5–6 are pouch-specific layout rules for the emitter: uniform
  orientation across panels, plus corner keep-out zones (seal areas eat the
  corners). This differs from carton logic — worth encoding as per-format
  panel rules, not shared ones.
- Claim 1 extends the "manufacturer supplies the dieline" rule: for pouches the
  supplier hands over TWO authorities — dieline + orientation guide. The OS
  handoff checklist for pouch jobs should require both.
- Claim 3: engine format vocabulary gains `pouch_standup` vs `pouch_flat`.

## Limits

- Converter marketing tutorial, 1:43 — no dimensions, no seal-width numbers,
  no material/laminate structure evidence (film layers ≠ laminate plies here;
  "three sheets" is web count, not barrier construction).
- PackMojo-specific template conventions; other converters rotate panels
  differently.
- Auto captions garble "dieline" as "diine" throughout; cleaned.
- Conflicts: none; opens the flexible_pouches domain.
