"""[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design. A failing check fixes the
drawing itself and re-checks; if it still fails, the design continues and the problem is shown beside Approve in plain
words."] What stands beside a design's Approve, for every kind of design — one reading for the page and for the
approval itself: the checks it has not passed (``kept``: each in words, kept with his approval when he approves), and
what alone refuses an approval (``refusal``) — his own acceptance of exactly this drawing not yet given (Approve gives
it), or no drawing to approve (its drawing unfinished, its file missing, its records in disagreement). A check never
refuses: it held Gate 2 until this goal — a measured visual-quality failure, a readiness section's codes, a stale
verdict, an artwork piece's codes, a die that does not fold, a label that does not stand, a front's copy over its
panel, a die outside its qualified domain, a production validation's failures."""
from __future__ import annotations

import re

#: what alone refuses an approval — his act, or nothing there to approve; never a check of the design
REFUSING = ("HUMAN_VISUAL_ACCEPTANCE_REQUIRED", "CONTAINER_RECONSTRUCTION_ABSENT", "RECONSTRUCTION_NOT_COMPLETED",
            "ARTIFACT_NOT_AVAILABLE", "TECHNICAL_INTERVENTION_REQUIRED")
#: the record his approval keeps them on
KEPT_KEY = "kept_with_approval"


#: [his last goal before the pitch, 2026-10-16, Step 1 (1): "Never show raw engine lines on a design page ("A fault in
#: the system itself — #E5DDE1:face-art-66" ×100s, "Checks it has not passed (176)"). Group internal faults into ONE
#: plain sentence, folded; show only what a designer needs to judge, in words."] a code with no words anywhere is the
#: system's own, never a check of the design: every such row is said once, here, its codes kept folded under it
INTERNAL_WORDS = ("{n} thing{s} the system noted inside its own drawing steps — none is a choice about the design, and "
                  "{each} kept with its record")
INTERNAL_CODE = "SYSTEM_NOTES"
#: a detail written in a designer's words — a language, a field, a part — said in the row; any other (a colour's hex, a
#: piece's id, a millimetre count) is the record's, kept folded under the row
_PLAIN_DETAIL = re.compile(r"[A-Za-z][A-Za-z ,;:'’&()/-]*")


def _row(code, said=None) -> dict:
    from apps.dashboard.words import FAULT_REASON, check_words, readiness_words
    code = str(code)
    head, _, detail = code.partition(":")
    # [his last goal before the pitch, 2026-10-16, Step 1 (1)] a code's words read from its head alone: read with its
    # detail, a code with no words ("CONTAINER_COLOUR_UNSOURCED:#E5DDE1:face-art-66") read as the fault's sentence
    # with the detail on it, never the fault itself — so each was its own line, 175 on design 138
    words = said or check_words(head.strip()) or readiness_words(head.strip())
    if words == FAULT_REASON:
        return {"code": head.strip(), "words": words, "_internal": code.strip()}
    if not said and detail.strip() and detail.strip() not in words:
        # its detail kept apart, so the rows of one check are said as one (``_merged``)
        return {"code": head.strip(), "words": "%s — %s" % (words, _detail_words(detail.strip())), "_base": words,
                "_detail": detail.strip()}
    return {"code": head.strip(), "words": words}


def _detail_words(detail: str) -> str:
    """A check's detail in words: a fact it names as missing said as missing, a language by its name
    (``words.DETAIL_WORDS``), the rest as written, its underscores spaces."""
    from apps.dashboard.words import DETAIL_WORDS
    if detail in DETAIL_WORDS:
        return DETAIL_WORDS[detail]
    return ", ".join(DETAIL_WORDS.get(p.strip(), p.strip().replace("_", " ")) for p in detail.split(":") if p.strip())


def _merged(rows: list) -> list:
    """[His goal of 2026-10-13, (5): "Secondary actions are small and quiet; technical details fold away."] The rows of one
    check said as ONE — its words once, then each thing it found: grouped by their first part where each has two ("the
    back label is not in all three languages — Spanish: description, ingredients; Arabic: description") — never one row
    a field, seven times over."""
    out, groups, internal = [], {}, []
    for row in rows:
        if "_internal" in row:
            internal.append(row["_internal"])
            continue
        if "_base" not in row:
            out.append(row)
            continue
        key = (row["code"], row["_base"])
        if key not in groups:
            groups[key] = {"code": row["code"], "_base": row["_base"], "_details": []}
            out.append(groups[key])
        if row["_detail"] not in groups[key]["_details"]:
            groups[key]["_details"].append(row["_detail"])
    said = []
    for row in out:
        if "_details" not in row:
            said.append(row)
            continue
        details = row["_details"]
        parts = [d.split(":", 1) for d in details]
        if not all(_PLAIN_DETAIL.fullmatch(_detail_words(d)) for d in details):
            # [his last goal before the pitch, 2026-10-16, Step 1 (1)] what the record names it by is kept, folded
            said.append({"code": row["code"], "words": "%s%s" % (row["_base"], " (%d)" % len(details)
                                                                  if len(details) > 1 else ""),
                         "details": [_detail_words(d) for d in details]})
            continue
        if len(details) > 1 and all(len(p) == 2 for p in parts):
            by = {}
            for first, rest in parts:
                by.setdefault(first.strip(), []).append(_detail_words(rest.strip()))
            text = "; ".join("%s: %s" % (_detail_words(first), ", ".join(rest)) for first, rest in by.items())
        else:
            text = "; ".join(_detail_words(d) for d in details)
        said.append({"code": row["code"], "words": "%s — %s" % (row["_base"], text)})
    if internal:
        n = len(internal)
        said.append({"code": INTERNAL_CODE, "internal": True, "details": internal,
                     "words": INTERNAL_WORDS.format(n=n, s="" if n == 1 else "s", each="it is" if n == 1 else
                                                    "each is")})
    return said


def gate2_problems(task, output, *, preview_sha256=None, quality=...) -> dict:
    """``{"refusal": a refusal's payload or None, "kept": [{"code", "words"}], "verdict": the container's readiness or
    None}`` — every check the design stands at Gate 2 without passing, in words, and whether its approval is refused."""
    spec = output.spec_sheet or {}
    kept, refusal, verdict = [], None, None
    if task.design_target == "product_container":
        from apps.pipeline.services.reconstruction_status import (VISUAL_QUALITY_GATE_FAILED,
                                                                  build_container_gate2_readiness)
        readiness = build_container_gate2_readiness(task, quality=quality)
        if readiness is None or (not readiness["ready"] and readiness["reason_code"] != VISUAL_QUALITY_GATE_FAILED):
            refusal = {"error": "GATE_2_NOT_READY",
                       "reason_code": (readiness or {}).get("reason_code") or "RECONSTRUCTION_CONTRACT_MISSING",
                       "visual_quality": (readiness or {}).get("visual_quality")}
        elif not readiness["ready"]:
            kept += [_row(c) for c in (readiness.get("visual_quality") or {}).get("blocking_codes") or []] or [
                _row(VISUAL_QUALITY_GATE_FAILED)]
    if refusal is None and (spec.get("backend") == "container" or spec.get("container_reconstruction")):
        from apps.ire.container_production_readiness import build_readiness, gate2_refusal
        verdict = build_readiness(spec, preview_sha256=preview_sha256)
        held = gate2_refusal(spec, preview_sha256=preview_sha256)
        if held is not None:
            refusing = [c for c in held.get("failures") or [] if str(c).split(":")[0].strip() in REFUSING]
            if refusing:
                refusal = dict(held, failures=refusing)
            kept += [_row(c) for c in held.get("failures") or [] if str(c).split(":")[0].strip() not in REFUSING]
    if spec.get("backend") == "artwork":
        from apps.dielines.registry import PHYSICAL_SAMPLE_VALIDATION_REQUIRED as _SAMPLE
        from apps.ire.compose_artwork import COPY_UNMEASURED as _UNMEASURED
        kept += [_row(c) for c in (spec.get("artwork_record/1.0") or {}).get("codes") or []
                 if c != _SAMPLE and not str(c).startswith(_UNMEASURED)]
    from apps.pipeline.targets import get_target
    hold = get_target(task.design_target).gate2_hold(task, output)
    if hold:
        said = hold.get("said")
        if isinstance(said, list):
            kept += [_row(hold["error"], s) for s in said]
        elif said:
            kept.append(_row(hold["error"], said))
        elif hold.get("violations"):
            # a die outside its template's qualified domain: what it breaks, and what would make it
            from apps.dashboard.words import check_words
            broken = [str(v).split(":", 1)[1].strip() if ":" in str(v) else str(v) for v in hold["violations"]]
            kept.append(_row(hold["error"], "%s — %s%s" % (
                check_words(hold["error"]), "; ".join(broken),
                ("; it needs %s" % hold["needs"]) if hold.get("needs") else "")))
        else:
            kept += [_row(c) for c in hold.get("codes") or [hold["error"]]]
    seen, out = set(), []
    for row in _merged(kept):
        if row["words"] not in seen:
            seen.add(row["words"])
            out.append(row)
    return {"refusal": refusal, "kept": out, "verdict": verdict}
