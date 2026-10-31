"""§BH50(f)(2), OWNER RULED 2026-09-13 — PLACEHOLDER COPY IS ITS OWN BLOCKER,
not a typography failure.

    "Eleven markers means eleven pieces of copy nobody has written; name that
    with its own code, blocking, and list them so I can supply the words.
    Never let placeholder text pass as set copy."

Measured before this record existed: the six unwritten slots of the back
copy already carried their own blocking code, CONTENT_VERIFICATION_REQUIRED
:<slot>, in the declared readiness ``content`` section (Gate-2 approval, no
override, never the reconstruction) — and the SAME six pieces were counted a
second time, as eleven findings, by the typography axis
(``placeholder_text_present``), while no record said, per piece, where the
copy is drawn and what stands in for it. The eleven markers were six pieces:
the strip draws all six (``back-section-{i}-copy``), the true-scale panel
draws five (``back-panel-{i}-copy-*``; NET CONTENT drops past its edge).

This record is that list. It is built on every reconstruction from the DRAWN
document, joined to the composer's own section map (``doc.metadata
["back_copy_drawings"]``) and never by matching a run's name to a heading —
names label a finding, they never decide it. A drawn placeholder no slot
accounts for is ``unslotted`` and blocks; the contested "N/A" token blocks as
``contested``. The typography axis stops reading placeholders in the commit
that makes this record exist, and in no other, so at no commit does
placeholder text pass as set copy. §W5(a)'s two permitted placeholders stay
permitted and non-gating; §W5(b)'s "FAILS the axis" is where the finding
blocked before — it blocks HERE now, at acceptance; §W5(c) and (d) stand.
The composer's literal front net content is listed under its piece as set
copy from a literal, not verified — the piece is already coded, so no new
block is invented and the literal never reads as supplied.

Never a reconstruction blocker: a design is tried with its copy unwritten,
and it is not accepted with it.
"""
from __future__ import annotations

from apps.ire.container_typography_metrics import (
    PERMITTED_PLACEHOLDER_RUNS,
    measure_placeholder_text,
)

SCHEMA = "container_placeholder_copy/1.0"
#: the drawn marker and the code's prefix — the spelling §AK3 binds to
#: tools/reserved_copy.py; targets/container names the same constant
CONTENT_VERIFICATION_REQUIRED = "CONTENT_VERIFICATION_REQUIRED"
POLICY = ("§BH50(f)(2): placeholder copy blocks as its own code at acceptance "
          "(Gate-2 approval), one code per piece of copy nobody has written; "
          "the finding names the run and the text; §W5(a) permitted "
          "placeholders stay non-gating; §W5(c)/(d) stand; never a "
          "reconstruction blocker")

#: the product record's own field behind each slot, read for its STATE only
#: (non-empty / empty) — provenance UNVERIFIED, and the container path has
#: never read it: whether those words are the owner's is his question
_RECORD_FIELDS = {
    "description": ("Product.description",),
    "ingredients": ("Product.ingredients",),
    "directions": ("Product.how_to_use",),
    "warnings": ("Product.warnings_text",),
    "manufacturer": ("Brand.regulatory_text",),
    "net_content": ("Product.net_weight",),
}
EXCLUSIONS = (
    "the bottom code 'BATCH — MFG — EXP —' is inkjet variable data the filling "
    "line prints, not copy the owner writes",
    "the sheet's annotations (panel labels, census and dimension lines, swatch "
    "labels) are not product copy",
    "the §W5(a) permitted placeholders (the back-label EAN, the distributor "
    "identity) are permitted and non-gating",
)


def _slot(heading: str) -> str:
    return str(heading or "").lower().replace(" ", "_")


def copy_fields(product) -> dict:
    """{slot: {field, state}} — the state of the product record's own field
    behind each slot. ``state`` is 'non-empty', 'empty' or 'no field'; never
    the text, and never a claim about whose words they are."""
    out = {}
    for slot, (field,) in _RECORD_FIELDS.items():
        model, attr = field.split(".")
        obj = product if model == "Product" else getattr(product, "brand", None)
        if obj is None or not hasattr(obj, attr):
            out[slot] = {"field": field, "state": "no field"}
            continue
        value = getattr(obj, attr, None)
        out[slot] = {"field": field,
                     "state": "non-empty" if str(value or "").strip() else "empty",
                     "provenance": "UNVERIFIED — never read by the container path"}
    return out


def _runs(doc) -> dict:
    return {str(getattr(n, "name", "") or ""): n for n, _ in doc.walk()
            if getattr(n, "type", "") == "text"}


def build(doc, *, sections, content_codes, copy_fields=None,
          composed: bool = True) -> dict:
    """The record. ``sections`` and ``content_codes`` are the target's own
    (``_back_sections_from_record``); the drawings come from the composer's
    map in ``doc.metadata``; the placeholder findings from the ruled detector
    (§W5). ``composed`` False is the non-dropper path, which composes no back
    copy: the record says so, and an empty section is told apart from
    "all copy supplied"."""
    runs = _runs(doc)
    meta = doc.metadata or {}
    drawings = meta.get("back_copy_drawings") or {}
    literals = meta.get("copy_literals") or []
    fields = copy_fields or {}
    codes_by_slot = {}
    for code in content_codes or []:
        if ":" in code:
            codes_by_slot[code.split(":", 1)[1]] = code
    pieces = []
    accounted: set[str] = set()
    for index, sec in enumerate(sections or []):
        heading = str(sec.get("heading", ""))
        slot = _slot(heading)
        text = str(sec.get("text", ""))
        code = codes_by_slot.get(slot)
        drawn = drawings.get(str(index)) or {}
        drawn_at = []
        for scale in ("strip", "true_scale"):
            for name in drawn.get(scale) or []:
                node = runs.get(name)
                if node is None:
                    continue
                accounted.add(name)
                drawn_at.append({"node": name,
                                 "scale": "schematic" if scale == "strip"
                                 else "true_scale",
                                 "size_pt": getattr(node, "size_pt", None),
                                 "text": str(getattr(node, "text", ""))})
        not_drawn = [scale for scale in ("strip", "true_scale")
                     if drawn.get(scale) is not None
                     and not any(d["scale"] == ("schematic" if scale == "strip"
                                                 else "true_scale")
                                 for d in drawn_at)]
        piece = {"index": index, "slot": slot, "heading": heading,
                 "code": code, "unwritten": code is not None,
                 "placeholder_text": text if code else None,
                 "drawn_at": drawn_at,
                 "not_drawn": not_drawn,
                 "words_on_record": fields.get(slot),
                 "literal_drawings": [
                     {"node": lit.get("node"), "text": lit.get("text"),
                      "source": lit.get("source")}
                     for lit in literals if lit.get("slot") == slot]}
        if index == 0 and not code and not sec.get("source"):
            piece["note"] = "the product's name, verified from the record"
        if sec.get("source"):
            # [his rules of 2026-10-02, rule 5: "THE BACK IS DRAWN ... with the brief's back copy"] words drawn from
            # his brief, said so — not typed through the copy channel (§BH54(b) (k) 4), which holds none of them
            piece["source"] = sec["source"]
            piece["note"] = ("his words, from his brief's back copy (his rule 5 of 2026-10-02) — his copy for acceptance, "
                             "his answer 3 of the same day (a18911a): \"My brief's back copy counts as my copy for "
                             "acceptance.\"")
        pieces.append(piece)
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (7)] a piece the system's copy would fill, left off the back
    # for room, is drawn nowhere — its marker never printed — and still unwritten: its code stays, for acceptance
    drawn_slots = {p["slot"] for p in pieces}
    for slot, code in codes_by_slot.items():
        if slot not in drawn_slots:
            pieces.append({"index": None, "slot": slot, "heading": slot.upper(), "code": code, "unwritten": True,
                           "placeholder_text": None, "drawn_at": [], "not_drawn": ["left off the back for room"],
                           "words_on_record": fields.get(slot), "literal_drawings": []})
    detected = measure_placeholder_text(doc)
    unslotted = [f for f in detected.get("findings") or []
                 if f.get("node_name") not in accounted]
    contested = list(detected.get("contested") or [])
    codes = [p["code"] for p in pieces if p["code"]]
    codes += [f"{CONTENT_VERIFICATION_REQUIRED}:unslotted:{f['node_name']}"
              for f in unslotted]
    codes += [f"{CONTENT_VERIFICATION_REQUIRED}:contested:{c['node_name']}"
              for c in contested]
    return {
        "schema_version": SCHEMA,
        "policy": POLICY,
        "back_copy_composed_on_this_path": bool(composed),
        "pieces": pieces,
        "unwritten": [p["slot"] for p in pieces if p["unwritten"]],
        "marker_drawings": sum(len(p["drawn_at"]) for p in pieces if p["unwritten"]),
        "unslotted": unslotted,
        "contested": contested,
        "permitted": list(detected.get("permitted") or []),
        "permitted_runs": sorted(PERMITTED_PLACEHOLDER_RUNS),
        "exclusions": list(EXCLUSIONS),
        "codes": codes,
        "blocks": "ACCEPTANCE (Gate-2 approval, through readiness['content']); "
                  "never the reconstruction",
    }


__all__ = ["SCHEMA", "CONTENT_VERIFICATION_REQUIRED", "POLICY", "EXCLUSIONS",
           "build", "copy_fields"]
