# DIP-1B-DATA-CORR-1 — brand-candidate evidence-hash reconciliation

Status: **STALE_IGNORED_OUTPUT**. The current ignored generator output is a known,
non-authoritative later byte version. The accepted frozen version is not available at its
declared locator. This correction makes no migration, rewrites no evidence, changes no
database row, and creates no decision, assertion projection, or operational permission.

## Root of trust

The path quoted in the correction request omitted one directory. The exact committed
manifest locator is
`var/design_intelligence/audits/dip0c/c3a/brand_candidates.json`, not
`var/design_intelligence/audits/c3a/brand_candidates.json`. The 21
`dip0c3-brand:00`–`dip0c3-brand:20` records in the committed manifest identify:

- manifest/schema: `dip1b_mvp_manifest/1.0`;
- current committed manifest SHA-256:
  `7dbb22815265c0dc790e74003840fb861299beddd020179094f36129f86186aa`;
- accepted import-manifest SHA-256:
  `824434857fced5bae40d7786f3ef372a1b7ba524f72d9e9ab961eb65ce096692`;
- dataset: `dip0c3_brand_candidates/1.0`;
- exact expected source SHA-256:
  `dfccbad26e98744e78d606fec85a301a9d3d2357ff17cf8ece5fcbe7a2d9e62b`;
- exact current observed SHA-256:
  `b4a891debabebdb721b919fa793264c5e8c2e671f5e2d5f3e5218e284d2f5cbf`;
- current size: 101,488 bytes;
- locators: `json_path/1.0`, exact segments 0–20;
- manifest parser: `dip0c.brand/0.1.0`;
- generator: `tools.dip0c.run_c3a/0.1.0`;
- generator configuration: frozen `c3_pilot_manifest.json`, SHA-256
  `9dde40cf679fab5e388626b4d9ef9782536915f28a25adbc172abc2f81787d68`.

The frozen manifest is the authority for the expected identity. The physical input
identities are the 21 entry-level source hashes listed in the dependency table below (20
unique content identities because entries 08 and 09 share one physical SHA-256). Paths
and timestamps are retained only as observations.

The expected whole-file bytes were not found in Git history, committed milestone
artifacts, archived audit outputs, or database `SourceArtifact` rows. The ignored output
was never tracked by Git. The database has zero `SourceArtifact` rows for either the
expected or observed whole-JSON hash because the importer persisted physical source
artifacts and per-record hashes, not the generator-output JSON as an artifact.

The accepted import batch preserved all 21 per-record hashes. Replacing only the volatile
`extracted_at` values in memory with the values proven by those hashes reproduces exactly
101,488 bytes and `dfccbad2…e62b`. No reconstructed file was written or imported. Thus the
exact expected bytes remain unavailable, but the frozen whole-file hash is independently
reproduced from preserved import provenance.

## Classification evidence

The ignored path is the default output of `tools.dip0c.run_c3a`. PDF vector extraction
creates `Inferred` envelopes whose default `extracted_at` is the current UTC second. The
former determinism test compared selected semantic fields and then invoked the generator
again at the repository output path; it neither compared output bytes nor isolated this
ignored output. That test guard is now corrected to use a session-temporary C3a root.

The observed/current, prior-observed, and two controlled temporary versions are all
101,488 bytes and all normalize to semantic SHA-256
`3cca47770f22bd863fafdd0116556ce7934f8c4ee0e9185ff235eda395639074` when only
`extracted_at` is removed. Their whole-file hashes differ. This proves volatile generated
timestamps—not corruption, a legitimate new accepted generation, a manifest defect, or
imported mismatched content—caused the mismatch. The exact classification is therefore
`STALE_IGNORED_OUTPUT`.

The versioned, content-driven classification evidence lives in
`dip1b_evidence_integrity_registry_1_0.json`. Policies select manifest, dataset, source
role, and expected content identity; runtime behavior does not select this correction by
filename. A renamed-locator regression proves path equality is neither necessary nor
sufficient for content identity. An unrecognized new mismatch remains `UNRESOLVED` and
fails closed.

## Database dependency trace

The read-only reconciliation traces every affected `SourceArtifact`,
`SourceLocationObservation`, `ImportBatch`, `ImportRecord`, `CorpusItem`,
`EvidenceReference`, `ObservedFact`, `MachineClassification`, `BrandCandidateProfile`,
`ReviewCandidate`, signed `DecisionEvent`, and `HumanAssertionProjection`. Its JSON mode
reports every database UUID, exact source hash, every imported record hash, structured
evidence locator, import batch, browser visibility, review-manifest membership, signed
assertion reference, and projection reference for each candidate.

All rows have two candidate-record versions and two paired `source:<stable-key>`
declaration-record versions in batches
`f1f9b8a3-8b33-4f90-8357-b2b7fac49e05` and
`12a0736c-020c-46d6-b0e8-674c6789bd6d`. The last hash column is the accepted batch's
candidate-record hash. Each JSON dependency object includes all four exact import-record
UUIDs/hashes and the `SourceLocationObservation` link to the appropriate source-declaration
record. Seven candidates belong to `dip1b_review_manifest/1.0`; all 21 are browser visible.
Every row has zero signed assertion and zero human-projection references.

| Stable candidate | Physical source SHA-256 | Initial record SHA-256 | Accepted record SHA-256 | Review task |
| --- | --- | --- | --- | --- |
| `brand:dip0c3-brand:00` | `9417d05f8c81abfdd0e724d402557accab4e5bf0ab7639640b97003c5841e954` | `79c09ee9bd70922d288ef1118bf631b05b98680300e3ba4111d97935ab95d584` | `789841b049d0842b994bdee4536ab5729e0941ee7704834ed39e944b4116881e` | yes |
| `brand:dip0c3-brand:01` | `7a63f38b93fcf9789e338465025fe0dc4f70ce726dca16937eeba331617cb7d9` | `9e492e6718c2336dbb057439dfeb342b6b6340066ea23d21763cfd6631e53b40` | `ffa92f26eaf4e3fcf3cef879330ea381c5565fc8123a17cde29f89040f71aa3a` | yes |
| `brand:dip0c3-brand:02` | `3076e98742139c0e0d1e4b1c38be3378109de85c0e30b6994aadb91abe7e87e6` | `006710b1b49ca95e6cb56f0a2e55abbdce0ae59201c6c79192e0f980787a36ef` | `d5eab953cfb0e8c828a550594a7379af92cdf5a8caf49e1af2bf51c43097edd9` | yes |
| `brand:dip0c3-brand:03` | `4475663c1debfbba4f132e0458f4045e057f6d473854d16ebc3100c8b630af0a` | `014c550491adf10e5bb87990ed2e202bc6cfd67d45b4c93c9fe54a0fc0f8e6a9` | `4e3550123b9e1bb76c2894fd111a3161ac7572f72484cb6adad02d5f0b6d1440` | yes |
| `brand:dip0c3-brand:04` | `f7b9afec5e1cafe90eecbf813a908393fa963f958fe78f22e8be71a565d5a423` | `f68cf0bc6528bd38875f043da789a3fb38b802aafc3fe61168dfbfc74ce2384b` | `1eb7b746ef6f2cbc3420ddb7c1e033a6fdea37aebd62de0aa5b25ec9b3e7b19c` | yes |
| `brand:dip0c3-brand:05` | `3b24f51ce69dfb7de0c0d55e1fa2508f675c2e0607311ecda9e0cf1f7a0c17e2` | `1eefea313d56bf8f7644fef3da4c52cb7b5dea1cfb463f428ffbb131f7a4ed29` | `b5ac45673cd7f806d6cbe52da28fde6b0a385081c40e6c6fdb26510e1f8bb0e3` | yes |
| `brand:dip0c3-brand:06` | `67bf6ba247732c3f5ce88b561d1e166fcd01c1788bdfd9c1c9a39c9ff54d97c3` | `201dd9ab125a4ace2dd8262b8d27050369ace142f751c0eec4884ace75ddbc49` | `c866f6fb7ec266eb31463dec5e68c11e43671940b29f9c28017ff0837c7ad43c` | yes |
| `brand:dip0c3-brand:07` | `a624d9e8629b8a0592c02e3b3de345030da8ca3f3c992ae92c4ebdbb67c5a6ef` | `e5ea90d5037cdb9ad85c8af2aea2924f809d83a7c5eb264f6f887903ee4e8860` | `703de3c9169fb4fab185196142426f74b4b3cc01634633ecc30ef04b6821d0ca` | no |
| `brand:dip0c3-brand:08` | `9dd75754f80b30d7a979703fdf4dc7fef65f9f321e5a7441db649cd3367951ab` | `146f8e33cbfbf25f31236352d8dd6fad1ffc111e72144eb35625b3ea97100022` | `2b5dbed272226f70dc452782db9e8727ae8792fe7b35b9839b30167dd50609c4` | no |
| `brand:dip0c3-brand:09` | `9dd75754f80b30d7a979703fdf4dc7fef65f9f321e5a7441db649cd3367951ab` | `f42286196e0e5134e45e3b79af5548cc7c30a850a1ca1fcaed914b2941168e5b` | `b5d556be766b5b29b4bdb9dcaa53fedd621bf7d456e9af2bb1dd19d518695be0` | no |
| `brand:dip0c3-brand:10` | `0af5fc0f486407a8824d9ab79c2fe3d1f1d623d090045b1355ebb4bb9a28d038` | `fcdb58f52399ad2245942cb7c1954e9179f5ee907b2fd20228509816f580d572` | `664d9d8cf326a8c94dd221f819fa1b8656efdef3c4470dd612980b4269fbdc89` | no |
| `brand:dip0c3-brand:11` | `699d20aa6884051b666d49d4502ac44edea5018aca250ada1a21dabeca22934a` | `d3bc09c020e88025b5b6c0fc1598eee9fae4fe556388937b1c5911af717d7e76` | same | no |
| `brand:dip0c3-brand:12` | `674c2afda72dbad7f79f144653c612e04a8ecbc9691a2cc8cbacd531d6647577` | `a64b9b3bacf6bd52afdf8cca144ab763f47d85566033f04549a0b30521ed42c7` | same | no |
| `brand:dip0c3-brand:13` | `6ef961c5bd05044690be2ff643f6544a4c1755eaf26b74e43da8b07467041b2a` | `4e06913f601d92a40307cca1bf23d02989c2831b77c9557eeea5233477152ed7` | same | no |
| `brand:dip0c3-brand:14` | `82f415be8b47d92f700d50cfefffeee9cf82a0ff5a2bf641158fb2d972521c4f` | `7ab216a4a60c9509b4f9714c5c2bfeae32d8688c1192c2139234a03ecdf30460` | same | no |
| `brand:dip0c3-brand:15` | `b0a6cfcb6a4d331e6a08832840c030081fd44a88d6485b4ccbb72fc9c8368e63` | `3a5c62a58b42dd35a4780585abd84924c6b0d3a4b7334f46df1aa4aebecefda3` | `941f99b6aaad4e7366b8fbee1905c38417aa35ef37dcb2966d6b32ce29a9148a` | no |
| `brand:dip0c3-brand:16` | `b1af3c923e10180b592ed15a1757408d5c05dd7d8fe1bbe36f779f67f135b404` | `2da946b27e7ba59c134e713669e546429ff2ca30330def1bca2815e3c6028230` | `896a3b8c888206a11ef4dd20e382f97defb854bf891a0a53e026f313265da531` | no |
| `brand:dip0c3-brand:17` | `624453b69289152ecaa6131aadefaffc3b6dfeeb4e4e58d07ea32e15afeddba4` | `6a981a5239e94c6173e43922e0a7859c2183ff0ccbe7f54d58dc4e12c2d15372` | `be9df6a3ec3f7602d13dcd5ef087cf88a68dc493351e3c5d55dcdcc0d954f534` | no |
| `brand:dip0c3-brand:18` | `4c1aa90ddcc85e753dc22a9d3b857706707f1aa3423579a2635bc6b5b404fbeb` | `bfafa17f521d965fc6ba3e8d2fcb9ee9e3875b860edd60fc6b04561bd0971568` | `ea2e9ec9c088665c3885850ef331dbc7f65a47e914ad0299dedc53f455d7aafc` | no |
| `brand:dip0c3-brand:19` | `3406388bca7717167c05869f43520bc3aff856ba457afe2a7ae35f74a8b090fd` | `e0225fe270a06458509183bf99a27f54ccdbf18b423cd566c06ee1b6ff0f7e30` | same | no |
| `brand:dip0c3-brand:20` | `49e9e52c47a862e6e312d571fd7884c50013bf18d4c5602310f08e1a4f7301b0` | `919edd0c8c0b69863fd34eae95ee81a1b01ca16e4be3591c0b1aa94755eb2def` | same | no |

Run `python manage.py reconcile_dip1b_brand_candidate_hash --json` for the complete
bounded trace, including the exact UUIDs and locators that would make this table
unreadably wide.

Two local reconciliations were byte-for-byte identical with hash
`810c3775810f650160a1561e52c9a7283bb6768c8d9e58751728e4f19ed702a1`:

- 84 linked `ImportRecord` versions: 42 source-declaration versions and 42 candidate
  versions, covering 21 current candidates and 20 physical artifacts;
- 21 accepted-batch source-declaration records and 21 accepted-batch candidate records;
  six current candidate-record hashes still match because those records contain no
  volatile timestamp;
- 7 affected review tasks;
- 0 affected/global `DecisionEvent` rows;
- 0 affected/global `HumanAssertionProjection` rows;
- 0 affected/global ALLOWED `OperationalPermissionProjection` rows;
- projection publication state unchanged;
- `database_changed=false`.

Before and after counts were identical: 79 source artifacts, 81 location observations,
3 import batches, 783 import records, 117 corpus items, 291 evidence references, 291
observed facts, 277 machine classifications, 22 brand profiles, 46 review candidates,
0 decision events, 0 human assertion projections, 1 projection generation, and 0 ALLOWED
permissions.

## General resolver and fail-closed behavior

`evaluate_evidence_integrity(corpus_item, evidence_refs=None)` returns status, reason
codes, affected artifact IDs, expected and observed hashes, verified and unresolved
source versions, and an evaluation timestamp. It is read-only and always reports
`grants_authority=false`.

The resolver joins item import provenance to manifest stable keys and data-source content
identities. It treats persisted evidence artifacts as distinct verified versions; one
verified physical artifact cannot validate an unrelated generator-output declaration.
Missing, changed, ambiguous, or unrecognized versions fail closed. Browser and signed
assertion code consume only this general result.

Affected browser and review pages show `REVIEW REQUIRED`, the exact unresolved version ID,
expected and observed hashes, stable source keys, and explicit statements that machine
classifications are non-authoritative and operational permissions remain denied. They do
not expose absolute filesystem paths.

For affected candidates:

- `EVIDENCE_SUFFICIENT` is rejected before event append;
- evidence-dependent classification and correction are rejected;
- `EVIDENCE_INSUFFICIENT` remains available;
- `CLARIFICATION_REQUIRED` remains available;
- caller-supplied status cannot bypass the resolver;
- machine classifications cannot establish sufficiency;
- the projector independently rejects a stale sufficient-evidence event.

Unrelated candidates remain reviewable. No canonical, palette, ownership, licence,
permission, retrieval, recommendation, generation, or legacy-cutover decision is part of
this correction.

## Verification

- focused integrity/importer regression: 25 passed;
- intelligence application suite: 89 passed;
- accounts suite: 258 passed;
- final CI-equivalent application suite: 883 passed, 1 skipped, and 1 documented Pacdora
  test deselected;
- frozen DIP-0/DIP-0B/DIP-0C tooling: 1,014 passed;
- scoped Ruff, Python compilation, Django system checks, migration-drift detection, and
  whitespace checks: clean; deploy checks report only the existing local weak-key warning;
- two local development-database reconciliations were identical and read-only;
- the ignored output remained
  `b4a891debabebdb721b919fa793264c5e8c2e671f5e2d5f3e5218e284d2f5cbf`;
- the frozen MVP and C3 pilot manifests remained `7dbb2281…86aa` and `9dde40cf…d68`;
- frozen DIP milestone trees and `materials/` remained clean.
