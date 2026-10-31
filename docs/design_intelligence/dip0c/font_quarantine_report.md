# Font quarantine report

## The proposal — and it is only a proposal

| | |
|---|---|
| proposal | `QUARANTINE_CANDIDATE — the suspected duplicated dump` |
| **machine-applied** | **`False`** |
| applied by machine | `False` |
| **human-confirmed** | **`None`** (blank) |
| total files | **4,715** |
| total faces | 3,805 |
| suspected system-font faces | **706** |
| unsupported `.fon` files | 32 |
| duplicate overlap | 933 shared hashes (92.5%) |

## Three statements this report must make

1. **Folder membership alone does not prove system-font status.**
2. **System-font suspicion does not prove illegal acquisition.**
3. **Quarantine is PROPOSED, not executed.**

## False-positive risk

MATERIAL. This batch is defined by FOLDER, but suspicion is defined by NAME TABLE — and most files in the folder carry no suspicion. Accepting the batch quarantines fonts that were never individually implicated. That may still be the right call for an unverified dump; it is a judgement, and it is not the machine's.

## Evidence

Suspicion is raised **from the name table** — `achVendID`, copyright, trademark,
manufacturer. **Never from the filename** (`filename_used: false`). Foundries named:
Microsoft 359 · Monotype 196 · Adobe 172 · URW 73 · Agfa 21 · Linotype 20. Confidence is
capped at **0.85**; `legal_conclusion` is `None` and no machine may set it.

## Known exceptions

- a Microsoft/Adobe/Monotype font may be perfectly **licensed** to BBROSE
- a font may be an **internal system dependency** BBROSE genuinely needs
- **most files in the folder carry no suspicion at all** — quarantining the folder
  quarantines them too
- the foundry list is hand-written: unlisted foundries are never suspected

## Recommended disposition

Keep the dump **operationally disabled** (it already is, and always was) and **rebuild the
active library from verified sources** — rather than attempting to clear 3,780 files of
unknown provenance.

**0 files moved. 0 deleted. 0 permissions granted.**
