# Open-source dieline research — licence matrix

Date: 2026-07-22. Every classification below comes from reading the actual
licence file in a cloned copy (or verified absence), never from GitHub's
metadata badge alone. Public source code on GitHub does not itself grant
reuse rights; "NONE" means all rights reserved.

| Repository | Licence (file read) | Classification | Commercial use | Attribution | Copyleft reach | Verdict for BBROSE |
|---|---|---|---|---|---|---|
| DDR68/Rhino_Packaging_Toolkit | MIT (`LICENSE`) | **PERMISSIVE_REUSE_CANDIDATE** | yes | notice required | none | adapt with attribution — the only fully usable geometry source |
| treeDiM/PackLib4ES | MIT (`LICENSE`) — but carton templates are **binary plugin DLLs** | **LICENCE_AMBIGUOUS** (templates) / permissive (framework) | framework only | notice required | none | reference only; never execute the DLLs |
| sp1ritCS/vueBoxProgramm | MPL-2.0 (`LICENSE.md`) | COPYLEFT_REVIEW_REQUIRED (weak, file-level) | yes with file-level obligations | yes | modified MPL files only | wrong domain anyway (corrugated RSC) |
| florianfesti/boxes | GPL-3.0 (`LICENSE.txt`) | COPYLEFT_REVIEW_REQUIRED | only under GPL | yes | strong | reference only; do not copy expressions |
| Moini/inkpacking | GPL-2.0 (`LICENSE`) | COPYLEFT_REVIEW_REQUIRED | only under GPL | yes | strong | reference only |
| BrownBear127/open-dieline | PolyForm Noncommercial 1.0.0 (`LICENSE`) | **NONCOMMERCIAL_ONLY** | **no** | yes | n/a | unusable — do not copy, do not adapt |
| Chinnakrit05/gen-package | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | do not reuse |
| mcl1080/Box_Pattern_Generator | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | do not reuse |
| minrogi/PLMPackLib | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | do not reuse (unlicensed mirror) |
| aminahmadahmadi/Dieline | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | do not reuse |
| treeDiM/DXF2Diecut | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | format knowledge only |
| bikinon/d0427 | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | do not reuse |
| GIGAJOHUB/OpenDieline | no licence file | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | do not reuse |
| 2D→3D viewer cluster (~15 repos) | mostly none | NO_LICENCE_ALL_RIGHTS_RESERVED | no | n/a | n/a | not generators; reject |

## Obligations if the recommendation (adapt DDR68, MIT) is followed

- Preserve the MIT copyright + permission notice wherever the adapted
  formulas ship (source header is sufficient; already present in the PoC).
- No copyleft, no patent clause, no NOTICE file requirement.
- The adaptation must not import anything from the GPL/no-licence/
  noncommercial candidates — their role is bounded to "evidence of common
  practice", and no source expression from them was copied into the PoC.

## AGPL note

No AGPL candidate reached the shortlist; `AGPL_NETWORK_OBLIGATION_REVIEW`
was therefore never triggered.
