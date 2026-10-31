"""[His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL: 127's and 130's backs print only "Net
content"; 132's sticker only the name and net weight. Every back label carries the full set (description, ingredients,
how to use, warnings, made in, net content, batch/exp, QR). When the brief gives no back copy, write sensible standard
copy for that product type and mark it "not confirmed — please check" beside Approve. Never leave it nearly empty."]

ONE place, for every product type and both labels — a container's back and a carton's sticker. His brief's own copy and
the product record's win piece by piece; a piece neither gives is WRITTEN here for the product's type: once per design
by the strongest model (``OPERATION`` — a fidelity call, so a $0 hold never leaves the label empty), kept on the design's
record with what it was asked (``SCHEMA``) so a design drawn again never pays for it twice. Where the call cannot be made
(no key, a refusal, an answer that is not the four pieces) the type's standard copy (``STANDARD``) stands in, said.

Written copy NEVER counts as his copy: every written piece is listed beside Approve as "not confirmed — please check"
(``show``), the acceptance codes of a piece his words do not give stay as they were, and nothing on the label itself
says "please check" (the print-data contract reads such words as a placeholder).

FIT, never a stop: the written pieces are his to replace, so where the full set does not stand on its label at the
floor, the WRITTEN pieces — never his — are set shorter (``FORMS``: shortened, then in English only), measured by the
caller on the label's own layout, before any offer of fewer languages is made.
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError

import logging
import re

logger = logging.getLogger(__name__)

SCHEMA = "label_copy_written/1.0"
#: the paid call that writes the pieces his brief and the product record leave empty (``cost_ledger.FIDELITY_OPERATIONS``)
OPERATION = "label_copy_writing"
#: the code each written piece is shown beside Approve under (``apps/dashboard/words.py``)
NOT_CONFIRMED = "LABEL_COPY_NOT_CONFIRMED"
NOT_CONFIRMED_WORDS = "not confirmed — please check"
#: what a written piece's ``source`` says on the design's record
WRITTEN_SOURCE = "written by the system for this product type — not his copy"
FROM_MODEL = "written by the model"
FROM_STANDARD = "the type's standard copy"

#: the pieces written in words, in the order a label reads them
FIELDS = ("description", "how_to_use", "ingredients", "warnings")
FIELD_WORDS = {"description": "description", "how_to_use": "how to use", "ingredients": "ingredients",
               "warnings": "warnings"}
#: a filling's batch and expiry, left blank for the filler — never an invented number
BATCH_EXP = "Batch: ______   EXP: ______"
#: CHOSEN: where neither his brief nor the product record says where it is made — BBROSE is a UAE house; marked to check
MADE_IN_PLACEHOLDER = "UAE"

#: the forms the written pieces are set in, richest first: the whole of each piece; each shortened (its first sentence,
#: the first INCI names); and each of those in English only (the pieces his words give keep their languages)
FULL, SHORT, FULL_EN, SHORT_EN, TINY_EN = "full", "short", "full_english", "short_english", "tiny_english"
FORMS = (FULL, SHORT, FULL_EN, SHORT_EN, TINY_EN)
#: … and where even the shortest does not stand, the written pieces left off one at a time, in this order, until the
#: label stands — his own pieces never: the system's copy never stops a label that stood without it
DROP_ORDER = ("description", "how_to_use", "warnings", "ingredients", "made_in", "batch")
DROP_WORDS = dict(FIELD_WORDS, made_in="place it is made", batch="batch and expiry line")
ENGLISH_ONLY = (FULL_EN, SHORT_EN, TINY_EN)
_SHORT_INCI, _TINY_INCI = 7, 4
_MAX_LEN = 600

#: product families, by the words of the product's type, name and brief — the first that matches
#: (each a whole word or phrase — "brow" never inside "brown"; a trailing "*" a word's start, "moistur*")
_FAMILY_WORDS = (
    ("gloss", ("gloss",)),
    ("lip", ("lipstick", "lip", "lips", "lip balm", "bullet")),
    ("eye", ("mascara", "eyeliner", "liner", "brow", "brows", "lash", "lashes")),
    ("powder", ("palette", "compact", "eyeshadow", "shadow", "blush", "powder", "highlighter", "bronzer", "pans")),
    ("base", ("foundation", "concealer", "primer", "tint", "bb cream", "cc cream")),
    ("fragrance", ("perfume", "fragrance", "parfum", "eau de", "mist", "cologne")),
    ("cleanser", ("cleanser", "wash", "micellar", "toner", "remover", "cleansing")),
    ("nail", ("nail", "nails", "polish", "lacquer")),
    ("serum", ("serum", "dropper", "ampoule", "essence", "face oil", "facial oil")),
    ("cream", ("cream", "jar", "moistur*", "lotion", "butter", "balm", "gel")),
)

#: the type's standard copy — typical, generic, and claim-free; each piece is shown beside Approve to be checked
STANDARD = {
    "lip": {
        "description": "A creamy lipstick that glides on smoothly with rich, even colour.",
        "how_to_use": "Apply directly to the lips, starting from the centre and working outwards.",
        "ingredients": "Ricinus Communis (Castor) Seed Oil, Octyldodecanol, Euphorbia Cerifera (Candelilla) Wax, "
                       "Ozokerite, Silica, Caprylic/Capric Triglyceride, Tocopheryl Acetate, Parfum (Fragrance). "
                       "May contain: Mica, CI 77891, CI 77491, CI 77492, CI 77499, CI 15850.",
        "warnings": "For external use only. Stop use if irritation occurs. Keep out of reach of children."},
    "gloss": {
        "description": "A lightweight lip gloss with a smooth, shiny finish.",
        "how_to_use": "Apply to the lips with the applicator, on its own or over lipstick.",
        "ingredients": "Hydrogenated Polyisobutene, Ethylhexyl Palmitate, Silica Dimethyl Silylate, "
                       "Pentaerythrityl Tetraisostearate, Tocopheryl Acetate, Parfum (Fragrance). "
                       "May contain: Mica, CI 77891, CI 77491.",
        "warnings": "For external use only. Stop use if irritation occurs. Keep out of reach of children."},
    "eye": {
        "description": "A smudge-resistant eye product for defined, lasting definition.",
        "how_to_use": "Apply along the lashes or lash line from root to tip. Remove with eye make-up remover.",
        "ingredients": "Aqua (Water), Cera Alba (Beeswax), Copernicia Cerifera (Carnauba) Wax, Stearic Acid, "
                       "Glyceryl Stearate, Triethanolamine, Phenoxyethanol, CI 77499.",
        "warnings": "For external use only. Avoid direct contact with the eyes. Stop use if irritation occurs. "
                    "Keep out of reach of children."},
    "powder": {
        "description": "Finely milled pressed powder colour that blends evenly and builds easily.",
        "how_to_use": "Pick up a little colour with a brush and blend onto the skin, building as desired.",
        "ingredients": "Talc, Mica, Magnesium Stearate, Dimethicone, Octyldodecyl Stearoyl Stearate, "
                       "Caprylyl Glycol, Phenoxyethanol. May contain: CI 77891, CI 77491, CI 77492, CI 77499.",
        "warnings": "For external use only. Stop use if irritation occurs. Keep out of reach of children."},
    "base": {
        "description": "A lightweight base that evens the look of the skin with a natural finish.",
        "how_to_use": "Shake well. Apply to clean skin and blend outwards with fingertips, brush or sponge.",
        "ingredients": "Aqua (Water), Cyclopentasiloxane, Glycerin, Dimethicone, Butylene Glycol, "
                       "PEG-10 Dimethicone, Sodium Chloride, Phenoxyethanol. "
                       "May contain: CI 77891, CI 77491, CI 77492, CI 77499.",
        "warnings": "For external use only. Avoid contact with the eyes. Stop use if irritation occurs. "
                    "Keep out of reach of children."},
    "fragrance": {
        "description": "A fine fragrance with a soft, lasting trail.",
        "how_to_use": "Spray onto pulse points from a short distance.",
        "ingredients": "Alcohol Denat., Parfum (Fragrance), Aqua (Water), Linalool, Limonene, Citronellol, Geraniol.",
        "warnings": "Flammable. Keep away from heat and flame. Avoid contact with the eyes. For external use only. "
                    "Keep out of reach of children."},
    "cleanser": {
        "description": "A gentle cleanser that lifts away make-up and impurities, leaving skin fresh.",
        "how_to_use": "Massage onto damp skin, then rinse thoroughly with water.",
        "ingredients": "Aqua (Water), Glycerin, Cocamidopropyl Betaine, Sodium Cocoyl Glycinate, Panthenol, "
                       "Citric Acid, Sodium Benzoate, Parfum (Fragrance).",
        "warnings": "For external use only. Avoid contact with the eyes; if contact occurs, rinse with water. "
                    "Keep out of reach of children."},
    "nail": {
        "description": "A glossy, chip-resistant nail colour.",
        "how_to_use": "Apply two thin coats to clean, dry nails, letting each coat dry.",
        "ingredients": "Butyl Acetate, Ethyl Acetate, Nitrocellulose, Acetyl Tributyl Citrate, Isopropyl Alcohol, "
                       "Stearalkonium Bentonite. May contain: CI 77891, CI 15850.",
        "warnings": "Highly flammable. Keep away from heat and flame. Use in a well-ventilated area. "
                    "Keep out of reach of children."},
    "serum": {
        "description": "A lightweight serum that absorbs quickly and leaves skin feeling soft and hydrated.",
        "how_to_use": "Apply a few drops to clean skin morning and evening, before moisturiser.",
        "ingredients": "Aqua (Water), Glycerin, Propanediol, Niacinamide, Sodium Hyaluronate, Panthenol, "
                       "Allantoin, Phenoxyethanol, Ethylhexylglycerin.",
        "warnings": "For external use only. Avoid contact with the eyes. Stop use if irritation occurs. "
                    "Keep out of reach of children."},
    "cream": {
        "description": "A daily cream that leaves skin feeling soft, smooth and comfortable.",
        "how_to_use": "Smooth a small amount onto clean skin of the face and neck, morning and evening.",
        "ingredients": "Aqua (Water), Glycerin, Caprylic/Capric Triglyceride, Cetearyl Alcohol, "
                       "Butyrospermum Parkii (Shea) Butter, Glyceryl Stearate, Niacinamide, Tocopherol, "
                       "Phenoxyethanol, Ethylhexylglycerin, Parfum (Fragrance).",
        "warnings": "For external use only. Avoid contact with the eyes. Stop use if irritation occurs. "
                    "Keep out of reach of children."},
    "cosmetic": {
        "description": "A beauty essential made for everyday use.",
        "how_to_use": "Apply as needed.",
        "ingredients": "Aqua (Water), Glycerin, Caprylic/Capric Triglyceride, Tocopherol, Phenoxyethanol, "
                       "Ethylhexylglycerin, Parfum (Fragrance).",
        "warnings": "For external use only. Stop use if irritation occurs. Keep out of reach of children."},
}

_SYSTEM = """You write the back-label copy of a cosmetic product: standard, sensible label copy for its product type,
which the brand will check before print.

Rules:
- Write ONLY the fields you are asked for: description, how_to_use, ingredients, warnings.
- description: one or two short sentences, at most 20 words, factual. No medical claims, no percentages, no "clinically
  proven", no awards, no claims you cannot know (no "vegan", no "cruelty-free").
- how_to_use: at most 25 words.
- ingredients: a TYPICAL INCI list for this product type (and its named actives, e.g. Ascorbic Acid for a vitamin C
  cream), in INCI names, comma separated, descending order, 8 to 14 names; colourants as "May contain: CI ...".
- warnings: the standard warnings for this product type, at most 25 words.
- Never repeat the brief's styling or design words (colours of the pack, patterns, typefaces); never the brand's name.
- No placeholders, no brackets [], no "TBD", no "to be confirmed".

Respond ONLY with JSON: {"description": "...", "how_to_use": "...", "ingredients": "...", "warnings": "..."}
(only the fields asked for)."""


def family_of(about: str) -> str:
    """The product's family by the words that describe it — its type, its name, its brief — else "cosmetic"."""
    words = " ".join(str(about).lower().split())
    for family, keys in _FAMILY_WORDS:
        if any(re.search(r"\b%s%s" % (re.escape(k.rstrip("*")), "" if k.endswith("*") else r"\b"), words)
               for k in keys):
            return family
    return "cosmetic"


def standard_copy(about: str) -> dict:
    """The type's standard copy, every piece."""
    return dict(STANDARD[family_of(about)])


def kept(spec: dict | None) -> dict:
    """What this design's record keeps of the written pieces: ``{"about", "written", "by", ...}`` or {}."""
    got = (spec or {}).get(SCHEMA)
    return dict(got) if isinstance(got, dict) else {}


def _clean(text) -> str:
    return " ".join(str(text).split())[:_MAX_LEN]


def _ask(about: str, fields: tuple, log) -> dict:
    """ONE call to the strongest model for the pieces asked; {} where it cannot be made or its answer is not them."""
    from django.conf import settings
    if not settings.LABEL_COPY_WRITING or not settings.ANTHROPIC_API_KEY:
        return {}
    import json

    from apps.pipeline.services.claude_service import call_claude, extract_json
    try:
        response = call_claude(
            _SYSTEM, "Product: %s\nWrite these fields: %s" % (about, json.dumps(list(fields))),
            max_tokens=1200, model=settings.CLAUDE_MODEL_HEAVY, operation=OPERATION)
        data = extract_json(response)
    except Exception as exc:  # noqa: BLE001 — the type's standard copy stands in, said
        if isinstance(exc, _RescueBudgetError):
            raise
        logger.warning("label copy writing failed: %s", exc)
        log("ARIA: the label's missing pieces could not be written by the model (%s) — the type's standard copy "
            "stands in, marked to check" % type(exc).__name__, level="warning")
        return {}
    if not isinstance(data, dict):
        return {}
    return {f: _clean(data[f]) for f in fields if isinstance(data.get(f), str) and data[f].strip()}


def ensure(spec: dict, about: str, missing, log=None) -> dict:
    """[His review, C (7)] The pieces ``missing`` — those his brief and the product record leave empty — written ONCE for
    this design and kept on ``spec``: a record that already holds every piece missing now, for the same product words,
    is read and nothing is paid; else the strongest model writes them (one fidelity call) and the type's standard copy
    fills any piece it does not give. ``{field: words}``."""
    log = log if log is not None else (lambda msg, data=None, level="info": None)
    missing = tuple(f for f in FIELDS if f in set(missing))
    if not missing:
        return {}
    have = kept(spec)
    same = have.get("about") == about
    written = have["written"] if same and isinstance(have.get("written"), dict) else {}
    standard = set(have["from_standard"]) if same and isinstance(have.get("from_standard"), list) else set(FIELDS)
    # the pieces the model already wrote for these product words are kept — only the rest is asked for
    by_model = {f: written[f] for f in FIELDS if written.get(f) and f not in standard}
    ask = tuple(f for f in missing if f not in by_model)
    if not ask:
        return {f: by_model[f] for f in missing}
    wrote = _ask(about, ask, log)
    floor = standard_copy(about)
    out = {f: by_model[f] if f in by_model else wrote[f] if wrote.get(f) else floor[f] for f in missing}
    from_standard = sorted((standard - set(by_model) - set(wrote)) & set(FIELDS))
    spec[SCHEMA] = {"schema_version": SCHEMA, "about": about, "family": family_of(about),
                    "written": dict(written, **out),
                    "by": FROM_MODEL if not set(missing) & set(from_standard) else FROM_STANDARD,
                    "from_standard": from_standard}
    if wrote:
        log("ARIA: the label's %s written for this product type — not confirmed, shown to be checked"
            % ", ".join(FIELD_WORDS[f] for f in ask if wrote.get(f)))
    return out


def written_for(spec: dict | None, about: str, missing) -> dict:
    """The written pieces as kept — never paid for here (the design loop's and every redraw's reading): each piece
    ``missing`` the record holds for these product words, else the type's standard copy."""
    have = kept(spec)
    written = have["written"] if isinstance(have.get("written"), dict) and have.get("about") == about else {}
    floor = standard_copy(about)
    return {f: written[f] if written.get(f) else floor[f] for f in FIELDS if f in set(missing)}


_SENTENCE = re.compile(r"(?<=[.!?۔])\s+")


def shortened(field: str, text: str, form: str) -> str:
    """A written piece in ``form``: whole; or its first sentence (an ingredient list its first INCI names — fewest at
    its shortest). A sentence is never cut inside itself."""
    text = _clean(text)
    if form in (FULL, FULL_EN) or not text:
        return text
    if field == "ingredients":
        names = [n.strip() for n in re.split(r",\s*", text.split("May contain")[0].rstrip(" .")) if n.strip()]
        keep = _TINY_INCI if form == TINY_EN else _SHORT_INCI
        return ", ".join(names[:keep]).rstrip(".") + "."
    return _SENTENCE.split(text)[0]


def english_only(form: str | None) -> bool:
    return form in ENGLISH_ONLY


#: a carton's ``panel_info``: the pieces of it the system wrote, the form they are set in, and whether its regulatory line
#: is the system's placeholder origin
PANEL_WRITTEN_KEY = "written"
PANEL_FORM_KEY = "label_form"
PANEL_MADE_IN_KEY = "made_in_written"
#: the written pieces left off a carton's label for room (``DROP_ORDER``)
PANEL_DROPPED_KEY = "written_left_off"
#: the English a carton label's translations were made of, piece by piece
TRANSLATED_ENGLISH_KEY = "translated_english"


def _text(mapping, key) -> str:
    value = mapping.get(key) if isinstance(mapping, dict) else None
    return _clean(value) if isinstance(value, str) else ""


def fill_panel(spec: dict, info: dict, previous: dict, about: str, log=None) -> dict:
    """[His review, C (7): "132's sticker only the name and net weight."] A carton sticker's full set: each piece of
    ``info`` (``panel_info``) that is empty — or that still carries the words this design's last run WROTE (a stored
    label handed back as the size step's override is not his copy) — written for the product's type (``ensure``, paid
    once, kept on ``spec``), named under PANEL_WRITTEN_KEY; an empty regulatory line given the placeholder origin
    ("Made in UAE"), named under PANEL_MADE_IN_KEY. His words and the product record's always stand. Returns the
    pieces written."""
    before = previous.get(PANEL_WRITTEN_KEY) if isinstance(previous, dict) else None
    before = set(before) if isinstance(before, (list, tuple)) else set()
    missing = [f for f in FIELDS if not _text(info, f) or (f in before and _text(info, f) == _text(previous, f))]
    written = ensure(spec, about, missing, log=log)
    for field, words in written.items():
        info[field] = words
    info[PANEL_WRITTEN_KEY] = [f for f in FIELDS if f in written]
    origin = "Made in %s" % MADE_IN_PLACEHOLDER
    was_placeholder = isinstance(previous, dict) and previous.get(PANEL_MADE_IN_KEY) is True
    if not _text(info, "regulatory_text") or (was_placeholder and _text(info, "regulatory_text") == origin):
        info["regulatory_text"] = origin
        info[PANEL_MADE_IN_KEY] = True
    else:
        info.pop(PANEL_MADE_IN_KEY, None)
    return written


def show(spec: dict, written: dict, *, made_in: str | None = None, qr: str | None = None,
         qr_drawn: bool = True, form: str | None = None, dropped=()) -> None:
    """[His review, C (7)] Each written piece beside Approve, "not confirmed — please check", with the start of its
    words — and the placeholder origin and the QR's address where those are the system's — replacing what an earlier
    run of this design showed under the same code (a piece he has since given is no longer listed)."""
    from apps.ire import self_check
    rows = [r for r in spec.get(self_check.CHECKS_SHOWN_KEY) or [] if r.get("code") != NOT_CONFIRMED]
    spec[self_check.CHECKS_SHOWN_KEY] = rows
    for field in FIELDS:
        if written.get(field):
            words = _clean(written[field])
            self_check.keep_shown(spec, NOT_CONFIRMED, "the label's %s was written for this product type (\"%s%s\") "
                                  "— %s" % (FIELD_WORDS[field], words[:70], "…" if len(words) > 70 else "",
                                            NOT_CONFIRMED_WORDS), OPTIONS)
    if made_in:
        self_check.keep_shown(spec, NOT_CONFIRMED, "the label says it is made in %s, which neither the brief nor the "
                              "product record states — %s" % (made_in, NOT_CONFIRMED_WORDS), OPTIONS)
    if qr:
        self_check.keep_shown(spec, NOT_CONFIRMED, ("the label's QR code leads to %s, the brand's own site — %s" % (
            qr, NOT_CONFIRMED_WORDS)) if qr_drawn else ("the label's QR code (to %s) has no room on this back and is "
                                                        "not drawn — %s" % (qr, NOT_CONFIRMED_WORDS)), OPTIONS)
    for piece in dropped or ():
        self_check.keep_shown(spec, NOT_CONFIRMED, "no room on this back for the written %s — it is not printed; the "
                              "label stands with every piece of yours" % DROP_WORDS[piece], OPTIONS)
    if form in (SHORT, SHORT_EN, TINY_EN, FULL_EN):
        self_check.keep_shown(spec, NOT_CONFIRMED, "the written pieces are set %s so the whole label stands on its back "
                              "— %s" % (FORM_WORDS[form], NOT_CONFIRMED_WORDS), OPTIONS)


FORM_WORDS = {FULL: "whole", SHORT: "shortened", FULL_EN: "in English only",
              SHORT_EN: "shortened and in English only", TINY_EN: "at their shortest and in English only"}
OPTIONS = ("type the product's own words for it in its copy", "ask for changes")
