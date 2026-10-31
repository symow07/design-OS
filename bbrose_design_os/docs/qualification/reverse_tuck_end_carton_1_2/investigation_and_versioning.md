# REVERSE TUCK END CARTON 1 2 — D-derived qualification

Closure: reverse/mirror tuck (top=front, bottom=back). D-derived reach (D + 16 mm lip), lip-derived shoulder.
PROVISIONAL (no measured reference); stays provisional.

## Supported domain

1.1's domain MINUS the two removed defects (no TUCK_LIP_VS_HEIGHT — the
fixed 16 mm lip is < H/2 for any H>=60; no DUST_CLAMP_BOUNDARY — the
D+16 tuck zone always exceeds the 0.631 D dust). Binding edges:
`W >= 1.262 D` (dust clearance, UNCHANGED from 1.1), H>W, H>D,
D<=2.5W, glue clearance, slit web, published ranges.

## Evidence

- 12 fixtures, 10 SUPPORTED; the wide-short / large-shallow cases 1.1
  rejected are now SUPPORTED; boundary pairs stable
- property sweep seed **20260727**: 150
  in-domain + 250 whole-space, 175
  supported, 225 rejected, **0 failures**
- 1.1 unchanged/byte-stable; 1.2 geometry differs from 1.1 everywhere

## Mirror audit — CLEAN

Top tuck over the FRONT column, bottom over BACK, slits on the
mirrored panels, flat + cut area identical to STE 1.2 at the same
dims. No coordinate sign / local-origin error.

## Versioning

New version 1.2 (D-derived); 1.1 kept byte-stable, non-superseded for
existing/pinned tasks; 1.2 NON-DEFAULT. Authority: TECHNICALLY_QUALIFIED_DOMAIN only.
