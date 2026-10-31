# DIP-0B known limitations

- **Path-level registration association unavailable.** `get_drawings()` discards the colourspace and the content-stream operator count does not align with the drawing list, so no thin stroke is mapped to `/Separation /All`. Document-level presence only.
- **Spot matching is heuristic** (ΔE over RGB-converted colour, tint-ramp sampled). 308 colours are present but unattributed — valid colour whose named ink is unrecoverable, not a failed match.
- **Near-black is ambiguous.** 23587 artwork paths could be K, rich black or registration; kept as artwork, flagged.
- **All typography is outlined.** Level B needs OCR (DIP-0E); no font-family claims.
- **DIMENSION_MARK_CANDIDATE = 0** under the current rule — recorded as 'not detected', not 'absent'; four pages named for spot-check.
- **Pilot is 14 of 91 files, deliberately non-random.** Extrapolations are estimates; representativeness of the other 77 is unverified.
