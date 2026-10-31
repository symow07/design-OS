# Native Illustrator requirements

Capabilities unavailable through the PDF-compatible layer. `/AIMetaData` + `/AIPrivateData*` are present in all 14 pilot files and are **never parsed** — this lists what a future JSX/Illustrator-assisted audit could recover, and whether it is worth it.

\* exact wording is also reachable via OCR (DIP-0E), not only Illustrator.

| Capability | Why it matters | Needed for Design Memory? | Needed for reusable-asset extraction? | Deferrable? | Human review an acceptable substitute? | JSX/Illustrator audit justified? |
|---|---|---|---|---|---|---|
| original semantic layer hierarchy | layer intent (art vs dieline vs notes) | yes | no | no | partial | yes |
| artboard names | human-meaningful unit names | helpful | no | yes | yes | maybe |
| live text + exact wording | SKU, ingredients, claims | no* | no | yes (OCR/DIP-0E) | yes | maybe |
| font identities | typography provenance | no | no | yes | yes | yes if brand fonts matter |
| symbols and instances | repeated-mark reuse | no | yes | yes | partial | maybe |
| linked-vs-embedded asset relationships | asset provenance | no | yes | yes | partial | maybe |
| live effects | appearance reconstruction | no | no | yes | no | no |
| appearance stacks | fill/stroke/effect order | no | no | yes | no | no |
| editable swatch-library structure | named brand inks | helpful | yes | yes | partial | yes |
| Illustrator-specific object semantics | true object model | no | no | yes | partial | no |

## Conclusion

No capability above is required for DIP-0B's stated goal (understanding what is reliably extractable). Most are deferrable, and human review substitutes for the Design-Memory-critical ones. A JSX-assisted audit is justified only if (a) brand-font identity or (b) an editable swatch library becomes a hard DIP-1 requirement. `/AIPrivateData` remains opaque and unparsed.

