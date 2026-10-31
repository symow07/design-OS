"""P1 ARC — THE FIRST ACT. The committed runner, never a scratchpad
artifact (the A91 lesson).

§BH3 gives the P1 arc a first act named for it: "the queue-control
identity naming the declaration per its line 34". §BH6(a) ruled that
line 34 governs. §BH7(a) settled WHICH value that is, against a reading
this executor had itself put in play:

    the DECLARATION identity, computed at execution time via the
    canonical declaration_identity() path — NOT protocol_identity().

WHY THE LITERAL IS ABSENT FROM THIS FILE. §BH7(c) requires the value
"computed at execution time, not pasted". Line 34 of the declaration
says the identity is "computed at execution time from the committed
bytes so the declaration cannot drift after declaration". A pasted
constant would satisfy the words and defeat the mechanism: it would go
on agreeing with a declaration that had since moved. So this runner
calls the canonical function and passes its return value straight
through. Grep this file for the expected hex and you will not find it;
that absence is the point, and it is checkable.

THE HAZARD THIS FIRST ACT WAS ONE STEP FROM COMMITTING. A protocol
identity and a declaration identity are both 16-hex sha256 prefixes and
NEITHER CARRIES ITS NAMESPACE IN ITS OWN TEXT. begin_traced_queue takes
the identity as a parameter and its only check is falsiness, so a
protocol identity would have been stamped into the declaration_identity
field with no guard firing anywhere — silently breaking the bridge that
six executed first acts depend on. That silent-acceptance hole is a
FINDING under §BH7(a); a guard for it is a SEPARATE PROPOSED BUILD and
is deliberately NOT built here.

Run from the Django/pytest root:  python docs/roadmap/palt_m6/p1_audit/p1_first_act.py
"""
import json
import os
import sys

sys.path.insert(0, os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from apps.pipeline.services import palette_m6_spreads_driver as SD
from apps.pipeline.services import palette_queue_control as QC

P1 = "docs/roadmap/palt_m6/p1_audit"
LEDGER = os.path.join(P1, "p1_queue_ledger.json")
TRACE = os.path.join(P1, "p1_firing_trace.jsonl")

os.makedirs(P1, exist_ok=True)

led = json.load(open(LEDGER)) if os.path.exists(LEDGER) else {
    "record_type": "p1_audit_queue_ledger/1.0",
    "arc": "P1 — re-measure PALT-M6 behind §BH2, audit-first",
    "governing_rulings": ["§BH3", "§BH6(a)", "§BH7(a)", "§BH7(c)"],
    "identity_namespace": (
        "declaration_identity — sha256 of the COMMITTED bytes of "
        "docs/roadmap/palt_m6/declared_spreads/"
        "spreads_campaign_declaration.json, first 16 hex, read through "
        "git show. NOT protocol_identity(), which is computed over the "
        "protocol payload and is a different register entirely."),
    "spend": {
        "renders_this_arc": 0,
        "note": ("P1 opens audit-first. This act spends no renders; the "
                 "cap that governs renders is untouched by it."),
    },
}

# ---- THE FIRST ACT -------------------------------------------------
# Computed at execution time from the committed bytes. Never pasted.
declaration_identity = SD.declaration_identity()

stamp = QC.begin_traced_queue("p1_audit", TRACE, led, declaration_identity)

json.dump(led, open(LEDGER, "w"), indent=1)

print("P1 FIRST ACT — queue:", stamp["queue"])
print("P1 FIRST ACT — declaration_identity:", stamp["declaration_identity"])
print("P1 FIRST ACT — control_site:", stamp["control_site"])
