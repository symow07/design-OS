# DIP-1B-5A deterministic brand evidence

## Version identity

`dip1b_brand_evidence/2.0` is a new technical-evidence dataset derived from the
preserved C3a records. It is not a repair, replacement, or reinterpretation of
`dip0c3_brand_candidates/1.0`.

The three content identities remain distinct:

- original frozen expected C3a SHA-256:
  `dfccbad26e98744e78d606fec85a301a9d3d2357ff17cf8ece5fcbe7a2d9e62b`;
- stale ignored generator output SHA-256:
  `b4a891debabebdb721b919fa793264c5e8c2e671f5e2d5f3e5218e284d2f5cbf`;
- deterministic successor SHA-256:
  `7f887093fc8acec25eb31680be909df92580bf06f226732c7d717ef1db34032e`.

The original bytes were not recovered. The frozen manifest and the stale ignored
output were not modified.

## Canonicalization contract

The dataset pins:

- dataset and schema identifier `dip1b_brand_evidence/2.0`;
- generator `bbrose.intelligence.brand_evidence/2.0`;
- canonicalizer `bbrose.intelligence.brand_evidence.canonical_json/1.0`;
- C3 configuration hash
  `9dde40cf679fab5e388626b4d9ef9782536915f28a25adbc172abc2f81787d68`;
- frozen MVP manifest hash
  `7dbb22815265c0dc790e74003840fb861299beddd020179094f36129f86186aa`;
- accepted import-manifest hash
  `824434857fced5bae40d7786f3ef372a1b7ba524f72d9e9ab961eb65ce096692`;
- 21 stable candidate records and their preserved ImportRecord hashes;
- 21 logical source locations and 20 unique physical content hashes;
- every canonical record hash, the complete dataset hash, and byte size.

Canonical output is UTF-8, sorted-key compact JSON with one trailing LF. Records
are ordered by stable candidate key. Identical semantic inputs therefore produce
byte-identical output regardless of input ordering.

The technical whitelist preserves C3a parser observations, format, representation,
readiness measurements, candidate labels, and capability limitations. A missing
format-specific measurement is represented as `null` and named in
`unavailable_technical_fields`; it is not invented.

The following volatile execution values are recursively excluded from evidence
identity: extraction/runtime timestamps, runtime and temporary paths, temporary
directories, host, and hostname. Human, ownership, licence, permission, canonical
brand-master, and other authority-bearing C3a fields are not projected.

The binding manifest is
`dip1b_brand_evidence_manifest/2.0`, SHA-256
`c1f1f398e47654b22037219f92d4e8ee0fdddb8340f34bb4d337af3d7ffdf23e`.
Repeated generation against the accepted 21 ImportRecords reproduced both files
byte-for-byte.

## Authority boundary

This dataset verifies bounded technical evidence only. It does not establish:

- brand identity or canonical status;
- ownership, licence, or rights to use;
- official palette authority;
- approval or governance readiness;
- retrieval, automatic use, export, production use, or any operational permission.
