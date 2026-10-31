"""§BH67(b)2 — the display wordmark: where the concept's most visible element drops, and the one drop the record
settles.

OWNER RULED 2026-09-24 (OWNER_BLOCKER_CLEARANCE.md, LIVE): "THE DISPLAY WORDMARK IS LOST. The original's most visible
element never reaches the drawn file. Find where it drops." The transcription read it: the original's display
wordmark is its product NAME set as a logotype — FOCUS — and the executor does not rename the product.

A concept names its display wordmark in its own words: task 91's typography is "High-contrast old-style Latin serif
('Focus') over matching Naskh ('فوكس')", and its picture sets 'Focus' large above the window with 'فوكس' beneath. The
product record's name is "Focus Pressed Powder" (the brief's words: "working name FOCUS"). The wordmark drops in three
places, each a separate attribute, and ``read`` names all three:

- TEXT — the drawn name was the record's WHOLE name, where the concept sets only its leading word. The concept's
  display name is taken ONLY when it is the record's own leading phrase, word for word (Latin and Arabic each against
  their own field): nothing is invented and nothing renamed — the words are the record's, in the length the concept
  draws them, in the record's own spelling (a concept that sets them in other letter case is noted, never followed
  here). The remainder stays on the record and off the face, said by name — UNLESS the concept sets the rest of the
  name as well, quoted or not, anywhere in its own words: then nothing is trimmed, the record's name prints whole, and
  the record says why, so the face never drops a line its concept sets. Quoted words that are not the record's are
  refused by name and never printed; a quoted later part of the record's name is the record's, and is not refused.
- FACE — the concept's own face leads where it names one from the granted set (§BH67(c)5, ``concept_typeface``); a
  style ("high-contrast old-style serif") names none, and the role layer decides.
- SIZE — the name prints at its tier size. Sizing it from the surface it prints on is §BH67(b)4, and waits on the
  question put to the owner about §Z1(b) ("No size_pt anywhere in this repo may be derived from a millimetre
  quantity").

Pure: words in, a record out.
"""
from __future__ import annotations

import re

SCHEMA = "container_display_name/1.0"
GOVERNED_BY = "§BH67(b)2"
DISPLAY, RECORD_NAME = "CONCEPT_DISPLAY_NAME", "RECORD_NAME"
NOT_THE_RECORDS_WORDS = "DISPLAY_NAME_NOT_THE_RECORDS_WORDS"

_FIELDS = ("typography_signature", "composition_signature")
_QUOTED = re.compile(r"['‘’\"“”]([^'‘’\"“”]{1,48})['‘’\"“”]")
_ARABIC = re.compile(r"[؀-ۿ]")
_WORD = re.compile(r"[\w؀-ۿ]+", re.UNICODE)


def _words(text: str) -> list[str]:
    return _WORD.findall((text or "").lower())


def _run_at(want: list[str], have: list[str]) -> int | None:
    """Where ``want``'s words sit as one unbroken run inside ``have``'s — the first word's index — else None."""
    span = len(want)
    if not span:
        return None
    for i in range(len(have) - span + 1):
        if have[i:i + span] == want:
            return i
    return None


def _leading(phrase: str, name: str) -> str | None:
    """The record's own words for ``phrase`` when it is the record name's LEADING phrase, word for word — in the
    record's spelling — else None."""
    want, have = _words(phrase), _WORD.findall(name or "")
    if not want or len(want) > len(have) or [w.lower() for w in have[:len(want)]] != want:
        return None
    if len(want) == len(have):
        return None                      # the whole name: nothing to settle, the record's name prints as it is
    # the record's own characters from its first word to the end of the matched phrase
    end = [m.end() for m in _WORD.finditer(name)][len(want) - 1]
    return name[:end].strip()


def read(structured: dict | None, *, product_name: str, product_name_ar: str | None = None) -> dict:
    """``container_display_name/1.0``: the display name the concept quotes, checked against the record."""
    out = {"schema_version": SCHEMA, "governed_by": GOVERNED_BY, "state": "NO_STRUCTURED_RECORD",
           "record_name": product_name or "", "record_name_ar": product_name_ar or None,
           "quoted": [], "name": {"source": RECORD_NAME, "text": product_name or ""},
           "name_ar": {"source": RECORD_NAME, "text": product_name_ar or None}, "refused": [], "off_the_face": []}
    if not structured:
        return out
    out["state"] = "READ"
    texts = {field: str(structured.get(field) or "") for field in _FIELDS}
    for field, text in texts.items():
        for m in _QUOTED.finditer(text):
            phrase = m.group(1).strip()
            if phrase and phrase not in [q["text"] for q in out["quoted"]]:
                out["quoted"].append({"text": phrase, "field": field, "script": "arabic" if _ARABIC.search(phrase)
                                      else "latin"})
    for key, record, script in (("name", product_name, "latin"), ("name_ar", product_name_ar, "arabic")):
        if not record:
            continue
        have, lead, parts = _words(record), None, []
        for q in (q for q in out["quoted"] if q["script"] == script):
            at = _run_at(_words(q["text"]), have)
            if at is None:
                out["refused"].append({"element": key, "quoted": q["text"], "code": NOT_THE_RECORDS_WORDS,
                                       "why": "the concept quotes words that are not the record's name — never "
                                              "printed; the record's name prints"})
            elif at == 0 and lead is None and _leading(q["text"], record):
                lead = q
            else:
                parts.append(q["text"])
        if lead is None:
            if parts:
                out[key]["why"] = ("the concept quotes the record's own words (%s) but no leading phrase of them to "
                                   "set alone — the record's name prints" % ", ".join("'%s'" % t for t in parts))
            continue
        own = _leading(lead["text"], record)
        rest = record[len(own):].strip(" -–—,")
        also = next((field for field, text in texts.items() if _run_at(_words(rest), _words(text)) is not None),
                    None)
        if parts or also:
            more = ["'%s'" % t for t in parts] + (["'%s', in its %s" % (rest, also)]
                                                   if also and _words(rest) not in [_words(t) for t in parts] else [])
            out[key]["why"] = ("the concept sets its display name '%s' AND more of the record's name as well — %s — so "
                               "nothing is trimmed: the record's name prints whole" % (lead["text"], "; ".join(more)))
            continue
        out[key] = {"source": DISPLAY, "text": own, "quoted": lead["text"], "field": lead["field"],
                    "why": "the concept sets its display name as the record's own leading phrase"}
        if _WORD.findall(lead["text"]) != _WORD.findall(own):
            out[key]["case"] = {"concept": lead["text"], "drawn": own,
                                "why": "the concept sets the words in other letter case; the drawn text keeps the "
                                       "record's spelling"}
        if rest:
            out["off_the_face"].append({"element": key, "text": rest,
                                        "reason": "the rest of the record's name — not in the concept's "
                                                  "wordmark; it stays on the record and off the face"})
    return out


def drops(reading: dict, *, typeface: dict | None, name_size_pt: float, drawn_face: str | None,
          name_size: dict | None = None) -> list[dict]:
    """Where the display wordmark drops, attribute by attribute: TEXT, FACE and SIZE, each with its state.
    ``name_size`` is the face's §BH68(b) step record; a caller that hands in none keeps the tier's state."""
    name = reading.get("name") or {}
    face = (typeface or {}).get("name") or {}
    return [
        {"attribute": "text",
         "state": "CONCEPT" if name.get("source") == DISPLAY else "RECORD_NAME",
         "drawn": name.get("text"), "concept": (name.get("quoted") or next(
             (q["text"] for q in reading.get("quoted") or [] if q["script"] == "latin"), None)),
         "why": "; ".join(filter(None, (name.get("why") or "the concept quotes no display name that is the record's "
                                                           "leading phrase", (name.get("case") or {}).get("why"))))},
        {"attribute": "face",
         "state": ("CONCEPT" if face.get("verdict") == "LEADS" else
                   "REFUSED" if face.get("verdict") == "REFUSED" else "ROLE_LAYER"),
         "drawn": drawn_face, "concept": face.get("words"),
         "why": face.get("why") or "the concept names a style and no face from the granted set (§BH67(c)5)"},
        ({"attribute": "size", "state": "SCALE_STEP", "drawn": name_size["step_pt"], "concept": None,
          "why": name_size["why"] + " (§BH68(b)); larger steps refused: "
                 + ("; ".join("%g pt — %s" % (r["step_pt"], r["why"][0]) for r in name_size["larger_steps_refused"])
                    or "none")}
         if name_size else
         {"attribute": "size",
          "state": "TIER_SIZE", "drawn": name_size_pt, "concept": None,
          "why": "the name prints at its tier size; sizing it from the surface it prints on is §BH67(b)4, which "
                 "waits on the owner's answer on §Z1(b)"}),
    ]


__all__ = ["SCHEMA", "GOVERNED_BY", "DISPLAY", "RECORD_NAME", "NOT_THE_RECORDS_WORDS", "read", "drops"]
