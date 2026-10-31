# How a soap pump works (3D Animation)

## Source

- Title: How a soap pump works (3D Animation)
- Channel: ScienceWorld
- URL: https://www.youtube.com/watch?v=LitUpL3j5Wc
- Duration: 2:40 · Watched: 2026-08-24
- Transcript source: captions (auto-generated, scraped via YouTube transcript panel —
  yt-dlp was bot-walled this session, see Limits)
- Detail mode: transcript + 1 frame (title-card full cutaway showing spring, ball
  check valve, piston, actuator inside a transparent bottle)

## Claims

1. `t=0:16` The pump mechanism is a syringe generalised: pull the plunger, liquid is
   sucked up; push it, liquid is forced out.
2. `t=0:40`–`t=0:57` A one-way valve on the seal changes the syringe into a pump:
   pulling sucks liquid as before, pushing opens the valve and moves liquid up into
   the barrel instead of back out the tip.
3. `t=1:04` A plastic ball + spring between tip and seal create enough liquid
   pressure and make the stroke return automatic — the ball is the check valve seat,
   the spring restores the head.
4. `t=1:28` Repeated push/release strokes ratchet liquid up the dip tube until it
   reaches the top (priming).
5. `t=2:01`–`t=2:16` First actuation only primes (sucks soap up); output at the
   nozzle arrives on the *second* push. Priming stroke ≠ dispensing stroke.

## Engine hooks

- Dropper/pump target geometry: the functional stack (actuator → rod → spring →
  ball check valve → dip tube) is a fixed vertical order; any closure silhouette the
  engine draws for a pump product must reserve vertical height for this stack —
  actuator travel is real, not decorative.
- C10 context (dropper front, SIZE axis): the actuator + collar zone is mechanically
  determined; artwork cannot borrow height from it. Relevant when the engine
  computes printable panel height on pump/dropper formats.
- VQ render realism: a pump head drawn with no collar/travel gap reads as fake.

## Limits

- Consumer-grade animation of a *soap* pump; treatment/lotion pump dosages, lockup
  heads, and cosmetic collar finishes are not covered.
- No dimensions, neck finishes, or materials given — nothing here sizes anything.
- Does not override any committed authority; purely mechanism vocabulary.
- Evidence caveat: yt-dlp (sandbox) was blocked by YouTube bot-check this session;
  transcript was scraped from the watch-page transcript panel in the owner's
  browser. Player stream would not buffer (readyState 0), so only the title-card
  cutaway frame was captured — mechanism steps rest on transcript, not frames.
