"""System-font-copy suspicion (DIP-0C4b).

**This raises a suspicion. It never establishes guilt.**

A font whose name table says *"© 2018 Microsoft Corporation"* and whose `achVendID` is
`MS` is *evidence* that the file originated as an operating-system font. It is **not**
evidence that BBROSE copied it illegally — the font may be licensed, may ship with a
tool BBROSE owns, may be an internal system dependency. So the outcome is a
**QUARANTINE_CANDIDATE with reasons**, and a human decides.

**Nothing is inferred from a filename.** My own first probe "detected" system fonts in
*Barista **Script*** and *ALLOVER **MODERN** DEMO* by substring — which is exactly the
class of mistake this project has refused since C3a. Suspicion is raised from the
**name table**: vendor ID, copyright, trademark, manufacturer, unique ID. The filename
is recorded as context and carries **zero** weight.
"""
from __future__ import annotations

import re

from . import config as C

PARSER = f"{C.TOOL_NAME}.font_provenance/{C.TOOL_VERSION}"
SCHEMA_VERSION = "font_provenance/1.0"

# --- outcomes ------------------------------------------------------------------
SUSPECTED_SYSTEM_FONT_COPY = "SUSPECTED_SYSTEM_FONT_COPY"
SYSTEM_FONT_EVIDENCE_PRESENT = "SYSTEM_FONT_EVIDENCE_PRESENT"
SYSTEM_FONT_STATUS_UNCERTAIN = "SYSTEM_FONT_STATUS_UNCERTAIN"
NO_SYSTEM_FONT_EVIDENCE = "NO_SYSTEM_FONT_EVIDENCE"
OUTCOMES = (SUSPECTED_SYSTEM_FONT_COPY, SYSTEM_FONT_EVIDENCE_PRESENT,
            SYSTEM_FONT_STATUS_UNCERTAIN, NO_SYSTEM_FONT_EVIDENCE)

# --- the evidence, and ONLY from the name table --------------------------------
# Vendor IDs that identify an operating-system or major-platform foundry. Four bytes
# of self-declared metadata — strong evidence, never proof.
OS_VENDOR_IDS = {
    "MS": "Microsoft", "MSFT": "Microsoft",
    "APPL": "Apple",
    "MONO": "Monotype", "MT": "Monotype",
    "ADBE": "Adobe",
    "LINO": "Linotype",
    "DYNA": "DynaComware",
    "AGFA": "Agfa Monotype",
    "B&H": "Bitstream",
    "URW": "URW",
}

COPYRIGHT_PATTERNS = {
    "Microsoft": re.compile(r"microsoft\s+corp", re.I),
    "Apple": re.compile(r"apple\s+(inc|computer)", re.I),
    "Monotype": re.compile(r"monotype\s+(imaging|corporation|typography)", re.I),
    "Adobe": re.compile(r"adobe\s+systems|adobe\s+inc", re.I),
    "Linotype": re.compile(r"linotype", re.I),
    "DynaComware": re.compile(r"dynacomware|dynalab", re.I),
    "Ascender": re.compile(r"ascender\s+corp", re.I),
    "Founder": re.compile(r"beijing\s+founder|founder\s+group", re.I),
}

# Evidence codes.
EV_OS_VENDOR_ID = "OS_VENDOR_ID"
EV_OS_COPYRIGHT = "OS_COPYRIGHT_STRING"
EV_OS_TRADEMARK = "OS_TRADEMARK_STRING"
EV_OS_MANUFACTURER = "OS_MANUFACTURER_STRING"
EV_DUMP_FOLDER = "IN_SUSPECTED_DUMP_FOLDER"     # context only — never sufficient
EV_DUPLICATE_OF_SUSPECT = "EXACT_DUPLICATE_OF_A_SUSPECTED_SYSTEM_FONT"

# Weights. Name-table evidence carries the decision; folder carries none on its own.
WEIGHTS = {
    EV_OS_COPYRIGHT: 0.45,
    EV_OS_VENDOR_ID: 0.30,
    EV_OS_TRADEMARK: 0.15,
    EV_OS_MANUFACTURER: 0.10,
    EV_DUPLICATE_OF_SUSPECT: 0.20,
    EV_DUMP_FOLDER: 0.0,        # DELIBERATELY ZERO. Location proves nothing — the
                                # rule has held since C3a and it holds here.
}
SUSPECT_THRESHOLD = 0.45        # a copyright string alone is enough to ASK
CONFIDENCE_CAP = 0.85           # never certainty: a licensed Microsoft font is legal


def assess(face: dict, *, in_dump_folder: bool = False,
           duplicate_of_suspect: bool = False) -> dict:
    """Suspicion for ONE face, from its name table. The filename is not consulted."""
    names = face.get("names") or {}
    vendor = (face.get("vendor_id") or "").strip()
    evidence: list[dict] = []
    foundries: set[str] = set()

    if vendor in OS_VENDOR_IDS:
        foundries.add(OS_VENDOR_IDS[vendor])
        evidence.append({
            "code": EV_OS_VENDOR_ID, "field": "OS/2.achVendID",
            "value": vendor, "foundry": OS_VENDOR_IDS[vendor],
            "note": "a 4-byte SELF-DECLARED vendor tag. Strong evidence of origin, "
                    "not proof of it."})

    for field, nid in (("copyright", EV_OS_COPYRIGHT),
                       ("trademark", EV_OS_TRADEMARK),
                       ("manufacturer", EV_OS_MANUFACTURER)):
        text = names.get(field) or ""
        for foundry, rx in COPYRIGHT_PATTERNS.items():
            m = rx.search(text)
            if m:
                foundries.add(foundry)
                evidence.append({
                    "code": nid, "field": f"name.{field}",
                    "value": text[:120], "matched": m.group(0),
                    "foundry": foundry})
                break

    if duplicate_of_suspect:
        evidence.append({
            "code": EV_DUPLICATE_OF_SUSPECT, "field": "sha256",
            "note": "byte-identical to a file whose name table names an OS foundry"})

    if in_dump_folder:
        evidence.append({
            "code": EV_DUMP_FOLDER, "field": "source_path",
            "weight": 0.0,
            "note": "CONTEXT ONLY. Folder location carries ZERO weight — it has never "
                    "proved ownership in this project and it does not start now."})

    score = sum(WEIGHTS.get(e["code"], 0.0) for e in evidence)
    confidence = round(min(score, CONFIDENCE_CAP), 3)

    # THE OUTCOME IS DECIDED BY SUBSTANTIVE EVIDENCE ONLY.
    #
    # `EV_DUMP_FOLDER` is weighted 0.0 — but a weight of zero is not enough. If mere
    # PRESENCE in the evidence list could still push a face out of
    # NO_SYSTEM_FONT_EVIDENCE and into "uncertain", then folder location would be
    # changing the answer through the back door, and 2,972 innocent faces would be
    # flagged for living in the wrong directory. Location is CONTEXT. It is recorded,
    # it is shown to the reviewer, and it moves nothing.
    substantive = [e for e in evidence if WEIGHTS.get(e["code"], 0.0) > 0.0]
    name_table_evidence = [e for e in evidence
                           if e["code"] in (EV_OS_VENDOR_ID, EV_OS_COPYRIGHT,
                                            EV_OS_TRADEMARK, EV_OS_MANUFACTURER)]
    if score >= SUSPECT_THRESHOLD:
        outcome = SUSPECTED_SYSTEM_FONT_COPY
    elif name_table_evidence:
        outcome = SYSTEM_FONT_EVIDENCE_PRESENT
    elif substantive:
        outcome = SYSTEM_FONT_STATUS_UNCERTAIN
    else:
        outcome = NO_SYSTEM_FONT_EVIDENCE

    return {
        "schema_version": SCHEMA_VERSION,
        "face_id": face["face_id"],
        "outcome": outcome,
        "confidence": confidence,
        "confidence_cap": CONFIDENCE_CAP,
        "foundries": sorted(foundries),
        "vendor_id": vendor or None,
        "copyright": (names.get("copyright") or "")[:160] or None,
        "trademark": (names.get("trademark") or "")[:160] or None,
        "manufacturer": names.get("manufacturer"),
        "evidence": sorted(evidence, key=lambda e: e["code"]),
        "filename_used": False,
        "note": "HEURISTIC. This is a suspicion raised from the NAME TABLE. It does "
                "NOT state that the font was copied illegally — a Microsoft font may "
                "be perfectly licensed to BBROSE, or ship with a tool BBROSE owns. "
                "A human decides.",
        "legal_conclusion": None,          # never machine-set
        "human_confirmation": None,        # human only
        "parser": PARSER,
    }
