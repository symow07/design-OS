# STRAIGHT TUCK END CARTON 1 2 — D-derived qualification

Closure: straight tuck (top=back, bottom=front). D-derived reach (D + 16 mm lip), lip-derived shoulder.
Straight-tuck correction of 1.1; not production-authorized (physical sample required).

## Supported domain

1.1's domain MINUS the two removed defects (no TUCK_LIP_VS_HEIGHT — the
fixed 16 mm lip is < H/2 for any H>=60; no DUST_CLAMP_BOUNDARY — the
D+16 tuck zone always exceeds the 0.631 D dust). Binding edges:
`W >= 1.262 D` (dust clearance, UNCHANGED from 1.1), H>W, H>D,
D<=2.5W, glue clearance, slit web, published ranges.

## Evidence

- 12 fixtures, 10 SUPPORTED; the wide-short / large-shallow cases 1.1
  rejected are now SUPPORTED; boundary pairs stable
- property sweep seed **20260726**: 150
  in-domain + 250 whole-space, 176
  supported, 224 rejected, **0 failures**
- 1.1 unchanged/byte-stable; 1.2 geometry differs from 1.1 everywhere

## Versioning

New version 1.2 (D-derived); 1.1 kept byte-stable, non-superseded for
existing/pinned tasks; 1.2 NON-DEFAULT. Authority: TECHNICALLY_QUALIFIED_DOMAIN only.
