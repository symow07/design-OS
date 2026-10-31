# Open-source dieline research — shortlist & recommendation

Date: 2026-07-22 · Method: GitHub REST API search (36 queries) + org
listings + direct lookups; 10 candidates shallow-cloned and inspected
(licence file, source geometry, security posture). Full data:
`github_dieline_research_manifest.json`, licence details:
`github_dieline_license_matrix.md`, feature scoring:
`github_dieline_geometry_comparison.md`.

## The landscape in one paragraph

There is **no mature, permissively licensed, retail-folding-carton dieline
library** on GitHub. The space splits into: laser-cutting box generators
(boxes.py — excellent engineering, wrong domain, GPL), industrial packaging
CAD whose carton templates are proprietary/binary (treeDiM lineage),
noncommercial or unlicensed prototypes (open-dieline, gen-package), and a
wave of dieline *viewers* that generate nothing. The one exception is a
small, professional, MIT-licensed Rhino toolkit whose ECMA A20.20.01.01
generator matches our exact use case.

## Shortlist (7)

| # | Repository | Licence | Score | Role |
|---|---|---|---|---|
| 1 | **DDR68/Rhino_Packaging_Toolkit** | MIT | 9/10 | **ADAPT** — licensed STE/RTE/crash-lock formulas |
| 2 | Chinnakrit05/gen-package | none | 7/10 | reference only (unlicensed) |
| 3 | BrownBear127/open-dieline | PolyForm-NC | 6/10 | unusable (noncommercial) |
| 4 | florianfesti/boxes | GPL-3.0 | 5/10 | reference only (copyleft, laser domain) |
| 5 | treeDiM/PackLib4ES | MIT shell / binary templates | 4/10 | reference only (never execute DLLs) |
| 6 | Moini/inkpacking | GPL-2.0 | 4/10 | reference only |
| 7 | minrogi/PLMPackLib | none | 4/10 | do not reuse |

## Top three, in detail

### 1. DDR68/Rhino_Packaging_Toolkit — MIT — ADAPT
- **Relevant source:** `packaging/ECMA_A20_20_01_01.py` (straight tuck end,
  394 lines, function `main()` + helpers `linea`/`nurbs2`),
  `packaging/ECMA_A20_20_03_01.py` (reverse tuck end),
  `packaging/ECMA_A01_55_00_01.py` (crash-lock bottom), `FEFCO_0412.py`.
- **Carton types:** ECMA A20.20.01.01 / A20.20.03.01 / A01.55.00.01, FEFCO 0412.
- **Example command:** run inside Rhino 7/8 script editor; prompts for
  L/P/A/S. (Our PoC removes the Rhino dependency entirely.)
- **Output:** Rhino layers `Taglio` (cut) / `Cordone` (crease); vector PDF
  via the repo's prepress script. PoC output: SVG.
- **Licence implications:** MIT — adaptation allowed with copyright notice;
  no copyleft. Notice embedded in the PoC header.
- **Integration effort:** LOW. Pure closed-form 2D geometry, mm units,
  ~60 segments; maps 1:1 onto our dieline path model + PDF/JSX emitters.
  One slice: port + parameter surface + tests.
- **Missing vs reference:** bleed contour, inner/mfg/outer conversion,
  automated tests — all already exist in the BBROSE engine.
- **Can it reproduce the 90×32×92 reference?** It produces a *correct,
  manufacturing-grade STE* at those dimensions (PoC verified: body 92.0,
  compensated panels 90.5/32.5, curved tuck shoulders, slit-locks, shaped
  dust flaps). Whether its flap shapes match the Pacdora die **exactly**
  cannot be claimed without the customer vector file — by design, the
  customer-dieline gate (d59a8e4) remains the authority for task #50.

### 2. Chinnakrit05/gen-package — no licence — reference only
- `src/core/templates/tuckEnd.ts`, `generateTuckEndBox(box, mat)`; SVG
  1:1 mm + 3D fold preview; thickness-aware glue width
  `max(12, 10+2t)` and dust inset `max(1.5, 2t+0.5)`.
- All rights reserved → no code reuse, no vendoring, no adaptation. Value:
  independent confirmation of thickness-formula practice.

### 3. florianfesti/boxes — GPL-3.0 — reference only
- `boxes/generators/paperbox.py` (design=`tuckbox`: single tuck lid with
  locking cut, lid radius), turtle-style edge engine, pytest coverage,
  SVG/PS export. Closest architectural inspiration for a generator
  *framework*, but the domain is laser-cut boxes (etched folds, no dust
  flap/slit geometry) and GPL-3.0 forbids incorporation.

## Security audit summary (shortlist)

- **DDR68:** no eval/exec/shell/network/file-I/O; only RhinoCommon document
  calls. Safe to read and adapt; PoC executed only my ported code.
- **gen-package:** has `server/` and `src/core/ai.ts` (provider calls) —
  never executed; read-only inspection.
- **PackLib4ES / PLMPackLib:** carton templates are opaque DLLs → never
  executed (fails the audit gate).
- **open-dieline:** excluded at the licence gate; not executed.
- No candidate was run against production credentials, user documents, the
  production database, or a browser session; all inspection happened in the
  session scratchpad.

## Recommendation

**Clean-room-informed internal implementation, seeded by ADAPTING the
MIT-licensed DDR68 formulas (attribution preserved) — do not adopt any
library wholesale.**

1. **Adopt:** nothing as a dependency. Nothing on GitHub is a drop-in
   folding-carton engine under a usable licence.
2. **Adapt (recommended):** DDR68's ECMA A20.20.01.01/A20.20.03.01
   closed-form geometry into a new *customer-grade STE archetype* inside
   the existing BBROSE dieline engine (own emitters, bleed/safe layers,
   inner/mfg/outer conversion, pytest gates). MIT permits this directly;
   clean-room ceremony is unnecessary for this one source, but no
   expression from GPL/unlicensed/noncommercial repos may leak in.
3. **Reference only:** boxes.py (framework architecture), PackLib4ES (ECMA
   coverage naming), gen-package (practice confirmation), inkpacking.
4. **Reject:** viewer cluster, corrugated calculators, unlicensed one-offs.
5. **Unchanged:** the Pacdora customer file remains the sole structural
   authority for task #50 (CUSTOMER_SUPPLIED_DIELINE outranks every
   template — including any archetype built from this research). The
   adapted archetype raises the quality of *generic* STE output for future
   tasks; it must never be presented as customer-reference parity.

### Provenance record

Repositories reviewed and their dispositions are recorded in
`github_dieline_research_manifest.json` (schema
`github_dieline_repository_audit/1.0`). Clones lived only in the session
scratchpad; nothing was vendored into the application; no package was
installed into the main environment; task #50 was not touched; no AI/image
provider was called; Gate 2 remains unapproved.
