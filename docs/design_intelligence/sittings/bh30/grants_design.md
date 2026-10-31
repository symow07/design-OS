§BH30(d) GRANTS — design of the channel extension (draft; code lands as its own commit after pass 2)

SHAPE. apps/ire/container_font_owner_grant.py keeps OWNER_GRANT_BH26 byte-for-byte (the Noto
pair) and gains OWNER_GRANTS_BH30: a TUPLE of grant dicts of the SAME shape (schema
container_font_owner_grant/1.0), one per licence text, each naming ONLY the face sha256s that
licence text shipped beside:
  · one grant per family folder under static/fonts/brand2026/ whose licence is the family's
    OFL.txt (Poppins 18 faces; Montserrat[wght]+Italic 2; Playfair 2; Quicksand 1; Bebas Neue 1;
    Great Vibes 1; Amatic SC 2; Shadows 1; Grand Hotel 1; Cairo-Bold 1 with OFL.txt@e86936fd;
    Raleway-Light 1; Lato-Black 1; Rubik-Bold 1) — licence_id = the text's own name,
    "SIL Open Font License, Version 1.1";
  · Montserrat-Regular.ttf under OFL_at_9548902f.txt (its commit-time text) — its own grant row;
  · OpenSans-Semibold.ttf under LICENSE.txt — licence_id "Apache License, Version 2.0".
  Each grant: granted_by "BBrose", granted_at = the landing date, licence_evidence_path =
  the in-corpus licence file (absolute via Path(__file__).parents[2] / "static" / "fonts" /
  "brand2026" / …), licence_evidence_sha256 = measured at build time, face_sha256s = the
  file sha256s from PROVENANCE.json (re-hashed at build time; a mismatch = stop).
  OWNER_GRANTS = (OWNER_GRANT_BH26,) + OWNER_GRANTS_BH30 — the applied set.

APPLY. apply_owner_grant(authority, *, grants=OWNER_GRANTS): for each face, the FIRST grant
naming its sha256 governs (no face is named by two grants — asserted by a test over the
tuple); per grant the evidence file is RE-HASHED on every application (VOID ⇒ that grant's
faces fall to LICENCE_REVIEW_REQUIRED through machine_writable_verification; nothing
conferred); a face named by no grant is returned untouched; a malformed grant applies to
nothing. Semantics for the Noto pair identical to today (regression test keeps the exact
record). The single-grant signature `grant=` stays accepted for the existing six tests.

TESTS (added to the existing test file, no new file → no manifest regen):
  · every OWNER_GRANTS row: required fields present; evidence path exists in the corpus and
    hashes to its pinned sha256 (measured, not asserted from memory); every face sha256 is a
    file under brand2026/ (or the Noto pair) — the grant describes bytes that exist;
  · no sha256 appears in two grants;
  · fail-closed per grant: hash mismatch on ONE grant's evidence voids only that grant's
    faces (LRR), the others still confer; unknown sha256 ⇒ untouched;
  · the Noto record byte-identical to the §BH26 expectation (regression);
  · a brand face record through build_font_authority's builder + apply → VFP / USER_CONFIRMED /
    is_fallback False / licence fields from the grant.

WHAT STAYS BYTE-IDENTICAL: container_font_authority.py (both ceilings, both guards, the GATE
region 7fbeb8f1fe10b0fb); the historical TEST blob b32030dc827263e4. No ceiling moves: the
grant enters as OWNER DATA downstream, exactly as §BH26(a) built.
