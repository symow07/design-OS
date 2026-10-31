"""§BH65(c)3 — THE FRONT DRAWS THE CONCEPT: the arrangement a concept's own words ask for, planned for the composer.

OWNER RULED 2026-09-22 (§BH65, ``OWNER_BLOCKER_CLEARANCE.md:23150-23253``, LIVE): "The concept engine reached my own
elements from a brief that named none of them. The composer discarded them. That is the gap." Measured at (c)1:
the direct-print front — every production run since §BB7(c) — draws the §BB4 divider IN THE MOTIF'S PLACE; the
motif's language resolves and no motif node reaches the front. §BB5 records the owner accepting that swap as the
price of wiring task 52; it rules no front motif-free, and §BH65(c) reaches it.

WHAT THIS PLANS — AND WHAT DECIDES WHERE IT MAY PRINT, WHICH IS NOT THIS MODULE. This reads the concept's words
into an arrangement. WHERE any of it may print on the container front is §AU1's (C8, OWNER RULED, LIVE,
``OWNER_BLOCKER_CLEARANCE.md:5652``): "The container front, top to bottom, is: the product name; below it a single
fine horizontal rule; below that exactly one supporting line of type. The decoration element sits above or behind,
as it already does. Nothing else prints on the front." The composer's placement policy
(``compose_container._concept_front_regions``) applies that ruling, the mark's 1.0x cap-height clear space on every
side (§AY2) and §BA's motif-field-as-ground (C12), and RECORDS by name, with the millimetres, whatever the concept
asks for that the ruled front cannot hold. The ruled front — the mark, its clear space, the §BB4 divider, the type
tiers at their ruled sizes and steps — is never moved to make room.

  WINDOW   (window, cartouche, medallion)       a framed panel, its interior filled as the colour field says, the
                                                motif inside it
  FIELD    (a motif and no window words)        the motif across the region it is given
  EDGE     (edge-led, asymmetric, lower edge)   the motif led from the region's lower edge
  BEHIND   ("behind the name", "across the      the motif may sit BEHIND the type — §AU1's "behind" — only when
            face", "all-over", "full-bleed")    the concept's own words put it there
  RING     (ring, border, frame, circumference) a rule tracing inside the zone's safe margin, around everything
  OUTLINES ("alternating ... outline forms")    every other motif element outline-only — the elements a foil
                                                clause on "petal outlines" lands on
  [RULE    ("hairline rule", "horizontal rule",  the owner's second answer of 2026-09-25: "The lid is missing the
            "name-separator rule")              concept's rule, ring and radial lines." Read from EVERY sentence of
                                                the design (``lines``); a FACE draws it between its name and its
                                                Arabic line]

Every decision is recorded with the words that made it, and what the plan cannot place — a window where the type
leaves no room — is recorded by name, never squeezed.

Pure: no Django, no ORM. The palette and the colours are handed in by the caller.
"""
from __future__ import annotations

import re

from apps.ire import composer_vocabulary as V

SCHEMA = "container_concept_front/1.0"
WINDOW, FIELD, EDGE = "window", "field", "edge"

#: the concept fields that describe the arrangement (never the render prompt, which describes the packshot's scene)
_LAYOUT_FIELDS = ("composition_signature", "decoration_zone_signature", "motif_signature")
_OUTLINE_RE = re.compile(r"(?<![a-z])(outline|outlines|outline-only|outlined)(?![a-z])")
_ALTERNATE_RE = re.compile(r"(?<![a-z])(alternat\w*|mix of|some filled)(?![a-z])")
_GRADIENT_RE = re.compile(r"(?<![a-z])(gradient|veil gradient|ombre|ombré)(?![a-z])")
#: §BH67(d)2: the window's own shape, where the concept's words give it — "oval petal-window cartouche", "a round
#: medallion", "circular window" — within three words of the window word; none, and it keeps its rounded rectangle
_WINDOW_SHAPE_RE = re.compile(r"(?<![a-z])(?P<shape>oval|ovoid|ellipse|elliptical|round|circular|circle)"
                              r"(?:[\s-]+[a-z-]+){0,3}?[\s-]+(?:window|cartouche|medallion)(?![a-z])")
#: §BH65(c)5 — the concept's own words for a blend mode, and the mode each names
_BLEND_WORDS = (("soft light", "soft-light"), ("soft-light", "soft-light"), ("hard light", "hard-light"),
                ("multiply", "multiply"), ("screen blend", "screen"), ("overlay blend", "overlay"),
                ("color burn", "color-burn"), ("colour burn", "color-burn"), ("color dodge", "color-dodge"),
                ("colour dodge", "color-dodge"))
#: the concept's own words for a motif BEHIND the type — §AU1's "behind" is permitted only when the concept says so
_BEHIND_RE = re.compile(r"(?<![a-z])(behind the (type|name|names|typography|lettering|wordmark)|"
                        r"(across|over) the (whole |entire |full )?(front|face|lid|panel|surface)|all-over|allover|"
                        r"full-bleed|under the (type|name|names)|beneath the (type|name|names))(?![a-z])")
#: [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
#: "The lid is missing the concept's rule, ring and radial lines."] THE CONCEPT'S OWN RULE, read from EVERY sentence of
#: its design — ``composer_vocabulary.CONCEPT_FIELDS``, never the render prompt — through the finish reader's own
#: targets (``container_finishes.target_phrases``, the longest phrase winning its span), so the plan and the finish
#: reader cannot disagree about which element a phrase names: "window rule" and "cartouche rule" stay the window's.
#: Only the NOUN makes a rule — "hairline" alone is the weight of a stroke ("droplet hairline strokes", 88 C) — and a
#: rule said in the same breath as the window, a band or a cap is that element's ("window frame hairline rule", 88 A;
#: "blush-tinted rules on side band", 89 C). Measured on every face concept on record before it was written: 88 B's
#: "horizontal rule", 88 C's "single name-separator rule" and task 110's "hairline rule" are the face's rule; no
#: other concept's words give one.
_RULE_NOUNS = ("rule", "divider")
_NOT_THE_FACES_RULE = ("window", "window_interior", "band", "cap")
#: the breaths of one clause: a list item ends at a comma, an "and", an ampersand, a plus, a spaced dash (the contract's
#: ``normalise`` reads every dash as a hyphen, so "rule — four named colour roles" arrives as "rule - four …") or a slash
_ITEM_SPLIT = re.compile(r",|\s(?:and|&|\+|-|/)\s")


def lines(structured: dict | None) -> dict:
    """[the owner's second answer of 2026-09-25] The concept's own lines — ``{"rule": [hit, ...]}`` — each hit
    ``{field, words, clause, at}``: the sentence it was said in, the words of its breath, the clause (lower case, its
    negated spans removed, as every reader here removes them — "no foil rule ring" asks for nothing) and where the
    noun sits in it, for the colour reader (``colour_sources.line_colour``). [and ``"ring"``: the finish reader's own
    RULE phrases for the ring — "rim rule", "rule ring" — wherever the concept says them (task 110: "Deep Rose
    (#8B3A52) for all name type and rim rule", "Deep Rose rim rule unifies lid edge"); the ring's other words ("frame",
    "border", "circumference") stay the ``frame_ring`` scan's, read from the arrangement's sentences as they were]"""
    from apps.ire.container_finishes import target_phrases
    from apps.pipeline.direction_signature import strip_negated_spans
    out: dict = {"rule": [], "ring": []}
    for field in V.CONCEPT_FIELDS:
        value = structured.get(field) if structured is not None else None
        text = strip_negated_spans(V.normalise(str(value) if value is not None else ""))
        for clause in text.split(" . "):
            start = 0
            for cut in list(_ITEM_SPLIT.finditer(clause)) + [None]:
                end = cut.start() if cut is not None else len(clause)
                item = clause[start:end]
                phrases = target_phrases(item)
                for s, _e, target, words in phrases:
                    if target == "ring" and "rule" in words:
                        out["ring"].append({"field": field, "words": item.strip(), "clause": clause, "at": start + s})
                if not any(target in _NOT_THE_FACES_RULE for _s, _e, target, _w in phrases):
                    for s, _e, target, words in phrases:
                        if target == "rule" and words.strip() in _RULE_NOUNS:
                            out["rule"].append({"field": field, "words": item.strip(), "clause": clause,
                                                "at": start + s})
                start = cut.end() if cut is not None else len(clause)
    return out


def plan(structured: dict | None, motif_spec: dict | None, *, ground_hex: str, edge_hex: str | None) -> dict:
    """``container_concept_front/1.0`` — the arrangement the selected concept's own words ask for. ``ground_hex``
    is the face's own colour (the window's centre); ``edge_hex`` is the colour the colour-field sentence names for
    the window's edge (the caller reads it from the brand palette), or None for a solid window."""
    out = {"schema_version": SCHEMA, "state": "NO_STRUCTURED_RECORD", "layout": None, "ring": False,
           "outlines": False, "behind": False, "blend": None, "fade": None, "glow": False, "shadow": False,
           "window_fill": None, "window_shape": None, "motif": False, "name_style": None, "why": {},
           # §BH67: the face's own colour, for a plain window fill and a glow no concept gives a colour of its own
           "ground_hex": ground_hex,
           # [the owner's second answer of 2026-09-25: "The lid is missing the concept's rule, ring and radial lines."]
           # the concept's own rule — ``lines`` — which a FACE draws between its name and its Arabic line
           "rule": False}
    if not structured:
        return out
    out["state"] = "READ"
    words = {}
    for field in _LAYOUT_FIELDS:
        for key, hits in V.scan(str(structured.get(field) or "")).items():
            words.setdefault(key, set()).update(hits)
    has_motif = (motif_spec or {}).get("reconstruction_capability") == "SUPPORTED"
    out["motif"] = has_motif
    if "window" in words:
        out["layout"], out["why"]["layout"] = WINDOW, sorted(words["window"])
    elif "edge_led" in words and has_motif:
        out["layout"], out["why"]["layout"] = EDGE, sorted(words["edge_led"])
    elif "band" in words and has_motif:
        # §BH65(c)9: a band or stripe of the motif is a FIELD across the region §AU1 gives it
        out["layout"], out["why"]["layout"] = FIELD, sorted(words["band"])
    elif has_motif:
        out["layout"], out["why"]["layout"] = FIELD, ["a supported motif and no window or edge words"]
    if "frame_ring" in words:
        out["ring"], out["why"]["ring"] = True, sorted(words["frame_ring"])
    # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start
    # testing"): "The lid is missing the concept's rule, ring and radial lines."] the concept's own rule, from every
    # sentence of its design (``lines``): a FACE draws it between its name and its Arabic line
    # (compose_container._concept_face); the ruled front keeps §AU1's own rule and reads nothing here
    concept_lines = lines(structured)
    rule = concept_lines["rule"]
    if rule:
        out["rule"], out["why"]["rule"] = True, sorted({"%s (%s)" % (h["words"], h["field"]) for h in rule})
    # [the same answer: the ring the concept calls a RULE — "rim rule", "rule ring" — read from every sentence of its
    # design (``lines``), as the finish reader has always read it (container_finishes.TARGET_WORDS["ring"]); ADDED to the
    # ``frame_ring`` scan above, which stands as it was. Until this the two readers disagreed: the finish reader has read
    # "rim rule" as the ring since §BH65(c)2, and the plan read no ring from it — task 110's lid drew none.]
    ring = concept_lines["ring"]
    if ring:
        out["ring"] = True
        framed = out["why"].get("ring")
        out["why"]["ring"] = sorted(set(framed if framed is not None else []) | {"%s (%s)" % (h["words"], h["field"])
                                                                                 for h in ring})
    if out["layout"] == WINDOW:
        shape_text = " . ".join(V.normalise(structured.get(f) or "") for f in _LAYOUT_FIELDS + ("motif_signature",))
        m = _WINDOW_SHAPE_RE.search(shape_text)
        if m:
            out["window_shape"] = "round" if m.group("shape") in ("round", "circular", "circle") else "oval"
            out["why"]["window_shape"] = [m.group(0)]
    from apps.pipeline.direction_signature import strip_negated_spans
    layout_text = strip_negated_spans(" . ".join(V.normalise(structured.get(f) or "") for f in _LAYOUT_FIELDS))
    behind = sorted({m.group(0) for m in _BEHIND_RE.finditer(layout_text)})
    if behind and has_motif:
        out["behind"], out["why"]["behind"] = True, behind
    for words, mode in _BLEND_WORDS:
        if has_motif and words in layout_text + " . " + V.normalise(structured.get("color_field_signature") or ""):
            out["blend"], out["why"]["blend"] = mode, [words]
            break
    # §BH65(c)6: the concept's own fade and glow words — read through the one contract
    fade_words = sorted(V.scan(layout_text).get("soft_mask", []))
    if has_motif and fade_words:
        direction = next((d for d, rx in (("down", r"(downward|down|toward the (base|bottom|lower))"),
                                          ("up", r"(upward|up|toward the top)")) if re.search(rx, layout_text)),
                         "out")
        out["fade"], out["why"]["fade"] = direction, fade_words
    shadow_words = sorted(V.scan(layout_text).get("soft_shadow", []))            # §BH65(c)7
    if has_motif and shadow_words:
        out["shadow"], out["why"]["shadow"] = True, shadow_words
    glow_words = sorted(V.scan(layout_text).get("glow", []))
    if has_motif and glow_words:
        out["glow"], out["why"]["glow"] = True, glow_words
    motif_text = V.normalise(structured.get("motif_signature") or "")
    if has_motif and _OUTLINE_RE.search(motif_text):
        out["outlines"] = True
        out["why"]["outlines"] = sorted({m.group(0) for m in _OUTLINE_RE.finditer(motif_text)}
                                        | {m.group(0) for m in _ALTERNATE_RE.finditer(motif_text)})
    # §BH65(c)8: the concept's own tracking and small-caps words, for the name tier — "wide" tracking is 0.15 em,
    # plain tracking 0.08 em; small caps print as capitals at the run's own size (the contract says APPROXIMATED)
    from apps.pipeline.direction_signature import strip_negated_spans as _strip
    type_text = _strip(V.normalise(structured.get("typography_signature") or ""))
    type_terms = V.scan(type_text, strip_negation=False)
    style = {}
    if "tracking" in type_terms:
        style["tracking_em"] = 0.15 if re.search(r"(?<![a-z])(wide|widely|generous|open)[-\s]?(ly )?tracked|"
                                                  r"wide[-\s]tracking|tracked wide", type_text) else 0.08
    if "small_caps" in type_terms:
        style["text_case"] = "upper"
    if style:
        out["name_style"] = style
        out["why"]["name_style"] = sorted(set(type_terms.get("tracking", []) + type_terms.get("small_caps", [])))
    field_text = V.normalise(structured.get("color_field_signature") or "")
    if out["layout"] == WINDOW:
        if edge_hex and _GRADIENT_RE.search(field_text) and "window" in field_text:
            out["window_fill"] = {"kind": "radial", "centre": ground_hex, "edge": edge_hex}
        else:
            out["window_fill"] = {"kind": "solid", "hex": ground_hex}
        out["why"]["window_fill"] = (["the colour field names a gradient within the window"]
                                     if out["window_fill"]["kind"] == "radial" else ["the face's own colour"])
    return out




def gradient_edge_hex(color_field_signature: str | None, palette, ground_hex: str) -> str | None:
    """The colour the colour-field sentence names AFTER the word "gradient" — the window's edge — read through the
    brand's own palette record (``colour_sources.mentions``), skipping the ground colour itself. None when the
    sentence names no gradient, or no colour after it."""
    from apps.pipeline.targets.container.colour_sources import mentions
    text = str(color_field_signature or "")
    m = _GRADIENT_RE.search(V.normalise(text))
    if not m:
        return None
    for mention in mentions(text, palette):
        if mention["start"] > m.start() and mention["hex"] and mention["hex"].upper() != (ground_hex or "").upper():
            return mention["hex"]
    return None


__all__ = ["SCHEMA", "WINDOW", "FIELD", "EDGE", "plan", "gradient_edge_hex", "lines"]
