"""PRODUCT_CONTAINER target (Phase B3).

Activates the container target on the shared pipeline: concept generation
steered toward a container packshot (concept_prompt_profile), a confirm-
profile gate (the container's answer to packaging's dimension gate), then
reconstruction onto the parametric silhouette backbone (B1) via the container
composer (B2) → editable .AI + PNG preview, reviewed through the canonical
Design Review Board (contributes only review_sections — no bespoke screen).
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError
from apps.pipeline.targets.container import archetypes as _declared

import os
import re
import tempfile
from dataclasses import asdict

from apps.pipeline.targets.base import DesignTarget, TargetStrategy
from apps.pipeline.targets.container.silhouettes import (
    SUPPORTED_ARCHETYPES,
    ContainerBackbone,
    ContainerProfile,
    build_backbone,
)

__all__ = [
    "ContainerProfile", "ContainerBackbone", "build_backbone",
    "SUPPORTED_ARCHETYPES", "ProductContainerTarget", "reconstruct_container",
]

_DEFAULT_CAP_HEX = "#C9A24B"
_DEFAULT_BODY_HEX = "#EAD7D2"

#: §BH55 Phase 4 ("the dead colour dict" — the queue's name; measured, it is not dead, and what it kills is live).
#: THE DROPPER PATH'S COLOURS. `reconstruct_container` builds a design's colours from its own concept — the body
#: sampled from the approved render (`dominant_color_hex`), the cap and product from the CONFIRMED profile's
#: recorded hexes, which that code's own comment says "beats the generic gold default and the whole-image median".
#: Then, on the dropper path, `colors` is REBOUND to this constant and all of it is discarded — three lines under
#: the comment that reads "Colours are concept authority from the selected render's measured palette."
#:
#: The sheet is not the consumer: `compose_dropper_sheet` takes no colours at all and draws from its own MATERIALS
#: through the §BH50(d) palette layer. These three hexes reach exactly two readers — the review board's fallback
#: when a design has no `container_palette/1.0` record (`_spec_rows`), and
#: `apps/pipeline/services/native_handoff.py:245`, which hands them to `compose_container_graph(colors=...)` where
#: `apps/ire/compose_container.py:817-818` draw the bottle's body and cap. So the Illustrator file a designer opens
#: for any dropper is drawn with these, identically, whatever the design is.
#:
#: They are also not what the sheet draws. BODY_BASE's literal IS #D8BEB8, but its §BH39 role accent_nude resolves
#: to the brand swatch #E8C9B3 and the glass moves ΔE76 9.54, so the sheet draws #E8C9B3 where the handoff draws
#: #D8BEB8; PRODUCT_FILL #C9A6A0 matches; and the cap #B76E79 is drawn nowhere in this system — the composer's
#: rose-gold base is #BC7480 — which is what §BH50(d) meant by "a hard-coded dict whose cap #B76E79 the artefact
#: never draws", and why the board stopped reading this and reads the palette record instead.
#:
#: WHICH colours a dropper's handoff should draw with is a colour decision on the path every accepted design takes,
#: and it is the owner's: §BH52 waits on his colour choice, and §BH50(d) rules that assigning a role to the
#: remaining materials "is the owner's line". Under §BH55 clause 3 no hex moves here. The question is entry 12 on
#: docs/roadmap/bh55/ACCEPTANCE_TIME_LIST.md, and PipelineHandoffColourTests
#: (apps/pipeline/tests/test_container_target.py) measures all four sources so they cannot diverge further unseen.
HANDOFF_COLOURS = {"body": "#D8BEB8", "cap": "#B76E79", "product": "#C9A6A0"}

#: §BH70(1), item 4 of the list he was sent: the directive every container concept is made with read "a bottle, jar or
#: tube ... label, cap, body colours ... standing upright" for every product — a palette was asked for a label and a cap
#: and to stand upright, and a compact was not named at all. It now names the product's own form, as that form is seen:
#: in elevation, standing upright; in plan, seen from above as it is held — and names no form when none is known.
_ANY_FORM_WORDS = ("the product's own form, as its brief names it — a bottle, a jar, a tube, a compact or palette, a "
                   "lipstick, a mascara, a pencil, a tin, a sachet, an oval stick, an aerosol can, an ampoule or "
                   "another")


#: [His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own for
#: every new design, for a wand vial and a carton".] How a concept is pictured so its design map can read it: the map
#: cuts one standing product from a plain ground, and the lip gloss vials on record could not be cut (task 51's six: a
#: pink vial leaning on a pink wall over its own reflection) — a form drawn standing straight-on, one drawn in plan
#: square from above, and either on a ground it can be told from
#: [the owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "Concept pictures
#: for drawing show the product alone: no props (no rose), straight-on, plain background. Styled shots are for mood
#: only."] 119's chosen concept laid a rose beside its carton: the directive barred only what touched the product, and
#: the prompt step's own brief asks for "one or two styling props"
MAP_ALONE = ("THE PRODUCT ALONE: no props of any kind anywhere in the picture — no flowers, petals, leaves, stones, "
             "drops, fabric, stands or styling — this overrides any scene, surface or styling prop asked for below; a "
             "styled scene is for mood only, never this picture.")
MAP_STANDING_POSE = "straight-on to the camera, its front facing it, not leaning, tilted or turned;"
MAP_PLAN_POSE = "square from directly above its face;"
MAP_GROUND = ("the whole product in frame with clear space around it, on a plain seamless ground in a tone clearly "
              "lighter or darker than the product, with nothing in front of it, touching it or overlapping it — its "
              "design is drawn from the picture exactly as pictured. " + MAP_ALONE)


#: [his goal for the pitch, 2026-10-15, A (4): "DEPTH AND DETAIL: layered backgrounds, textures, several colours,
#: gradients, rich illustration and things happening behind the hero, all still clean vector and faithful to the
#: concept"] — on the product's own printed faces; the picture itself stays the product alone on its plain ground
MAP_DEPTH = ("Its printed artwork is rich and layered: a ground of two or three planes (colour fields, smooth "
             "gradients), a texture drawn as crisp vector (stipple grain, fine hatching or a pattern), several colours, "
             "and a hero illustration with things happening behind and around it — every shape with a clean, crisp "
             "edge, flat print-ready artwork; no photographic texture, no blur except a soft glow. Every word stands on "
             "a calm, clear area in strong contrast with what lies behind it, never over the hero illustration. No rose "
             "and no arch unless the brief asks for one.")


def concept_directive(form=None, text="") -> str:
    """The concept directive for a product of this form — or, with no form known, for whichever form its brief names.
    [The owner's answer of 2026-09-27, (4): a product the form's vessel holds besides its namesake is named for what
    it is, in the vessel — "a lip gloss in a wand vial", never "a mascara" (``product_in_form``).]"""
    if _declared.is_known(form):
        label = _declared.vocabulary_of(form)["label"].lower().replace(" / ", " or ")
        what = "a %s" % (product_in_form(form, text) or label)
        seen = ("seen from above, closed, as it is held" if _declared.drawn_as_of(form) == _declared.PLAN
                else "standing upright, closed")
        pose = (MAP_PLAN_POSE if _declared.drawn_as_of(form) == _declared.PLAN else MAP_STANDING_POSE)
    else:
        what, seen, pose = _ANY_FORM_WORDS, "as it is held and seen", MAP_STANDING_POSE
    return ("This design target is a PRODUCT CONTAINER, not a carton or box. The hero object is the PRODUCT ITSELF — "
            f"{what}. Design its own applied artwork: its printed surfaces, its closure and body colours, the logo and "
            f"the product name, as a clean studio packshot of the product {seen}, made to be traced: {pose} "
            + MAP_GROUND + " " + MAP_DEPTH + " Do NOT design a folding carton, a box, or a dieline — those are a "
            "different target.")


def form_of_task(task):
    """The form a task's design is made in: its record's (the profile he confirmed at the shape step, or the one it
    proposed from his choice), else the Container type he chose, else the one form its product row and brief name,
    else None (``form_choice``)."""
    if task is None:
        return None
    output = None
    try:
        output = task.packaging_outputs.order_by("-id").first()
    except Exception:                                    # noqa: BLE001 — a task with no outputs names no record
        output = None
    recorded = (((getattr(output, "spec_sheet", None) or {}).get("container_profile/1.0") or {}).get("archetype")
                if output is not None else None)
    if _declared.is_known(recorded):
        return recorded
    return form_choice(brief_text(task))["form"]      # [his goal of 2026-10-06, item 1] his choice, then his words


def brief_text(task) -> str:
    """The words a task names its product with: its product row's type and its brief — what the form words read."""
    product = getattr(task, "product", None)
    return "%s %s" % (getattr(product, "product_type", "") or "", getattr(task, "task_text", "") or "")


def product_name_for(task, product) -> tuple[str, str]:
    """``(the name a container's front prints, where it came from)``. [His test day finding 3, 2026-09-30, design 117:
    with no product record the name was ``task_text[:60]`` — "Coconut Rose Body Lotion (test)\\r\\n\\r\\nProduct: BBROSE
    Coconut R" — drawn as a three-line hero.] The product record's name; else the product name the planner read from
    the brief (its stored brief, ``CreativeBrief.design_intent["brief"]``), the house's own name dropped from its front
    since the mark carries it; else the brief's first line."""
    name = " ".join(str(getattr(product, "name", "") or "").split())
    if name:
        return name, "the product record's name"
    from apps.pipeline.models import CreativeBrief
    intent = CreativeBrief.objects.filter(task=task).values_list("design_intent", flat=True).first()
    brief = intent.get("brief") if isinstance(intent, dict) else None
    brief = brief if isinstance(brief, dict) else {}
    named = " ".join(str(brief.get("product_name") or "").split())
    house = " ".join(str(brief.get("brand") or "").split())
    if named:
        if house and named.lower().startswith(house.lower() + " ") and named[len(house):].strip():
            return named[len(house):].strip(), ("the brief's product name, as the planner read it, without the "
                                                 "house's own name the mark carries")
        return named, "the brief's product name, as the planner read it"
    first = next((line.strip() for line in str(getattr(task, "task_text", "") or "").splitlines() if line.strip()), "")
    return first[:60], "the brief's first line"


def drawing_name(task, spec: dict) -> tuple[str, str | None]:
    """``(the name the drawing prints, its source when it was read again here, else None)``: the name on the record,
    except one written from the brief's first sixty characters when the design has no product record — design 117's —
    which is read again (``product_name_for``). A name the owner set is kept as it is."""
    held = spec.get("product_name") or ""
    if getattr(task, "product", None) is None and held and held == str(getattr(task, "task_text", "") or "")[:60]:
        return product_name_for(task, None)
    return held, None


#: the Gate-1 product block when the product record gives none — it read "(bottle or tube)" for every product
PRODUCT_BLOCK_FALLBACK = ("A BBROSE product, in its own form ({form}); derive the exact silhouette from the creative "
                          "direction — never a flat carton.")


def _infer_profile(task) -> ContainerProfile:
    """Best-effort initial profile from the product record — the human
    confirms/overrides it at the gate before reconstruction.

    [§BH55 Phase 1, 2026-09-19: a record that describes the product's CARTON
    no longer sizes the container, and a bottle whose record carries no size
    of its own is sized from the capacity its brief names — see below.]"""
    import re
    product = getattr(task, "product", None)
    text = brief_text(task).lower()          # [§BH71 PART 3: the one reading, the lid's shape heard in it too]
    # 2C-2D-CORR-1: whole words only — a substring scan turned "apothecary"
    # into a jar ("pot") on the live pilot brief; "potent"/"spot" would too.
    # §BH55(a): COMPACT is scanned FIRST and "compact" leaves the jar branch. Measured on the owner's own brief
    # before this change: its CASE section ("hinged compact, mirror in the lid, four pans") scanned to JAR, its
    # headline ("a Rose face palette, four baked pans in a hinged case") scanned to BOTTLE, and the product's own
    # word PALETTE was heard by nothing — two texts of one brief disagreeing, and neither answer a hinged case.
    # §BH61(a) EXPOSED THIS: bottle had NO WORDS OF ITS OWN. It was only ever the `else` — the form you got
    # when nothing else matched — which is exactly why removing the fallback turned every dropper brief into
    # an unresolved archetype. It is now named like the other three, from the word-list the asset resolver
    # already declares (`container_asset_resolver._ARCHETYPE_WORDS["bottle"]`), so this is not new vocabulary.
    # §BH61(a): NOTHING FALLS BACK TO BOTTLE. The last branch used to read `archetype = "bottle"`, so a
    # brief that named no form at all was proposed as a bottle and the form pre-selected it. A text
    # that names no form now yields NO archetype, the hint carries None, and the editor says so
    # instead of choosing (`no_proposal_reason`). This is a HINT reader, so it returns rather than
    # raising — its caller is the one that must not invent a value.
    # §BH70(1): the words are `FORM_WORDS` below, read by `form_named_in` — the tube's branch read "mascara",
    # "lipstick" and "stick" as a squeeze tube, and they now name forms of their own.
    archetype = form_choice(text)["form"]            # [his goal of 2026-10-06, item 1] his choice, then his words
    kw = {}
    # §BH55 PHASE 1 — the proposal's SIZE, measured on a no-spend dry run of new products: every new product was
    # proposed at the editor's default size whatever its brief said ("a 5 ml" and "a 200 ml" bottle alike), and a
    # product whose record is its CARTON (product_type "carton" — CORR-2 §4 measured that such a record's sizes are
    # the OUTER carton, and kept them out of the pilot's contract path only) was proposed at the carton's size. A
    # record of the product itself still sizes it; a carton's record never does; a bottle with no size of its own
    # is sized from the capacity its brief names (`_bottle_size_for`). A proposal: a person confirms or changes it.
    if product is not None and not _record_describes_carton(product):
        for attr, field in (("height_mm", "height_mm"), ("width_mm", "width_mm")):
            val = getattr(product, attr, None)
            if val:
                kw[field] = float(val)
    if not kw and archetype == "bottle":      # §BH61(a): only a bottle is sized as a bottle
        kw.update(_bottle_size_for(_capacity_ml(text, product)))
    # §BH55 PHASE 1 — the proposal speaks its archetype's own vocabulary, and hears the brief's closure. MEASURED on
    # a no-spend dry run of new products (the dashboard's own requests, rolled back): a jar or tube brief proposed the
    # BOTTLE-only variant "cylindrical" (this dataclass's default) and the dashboard's own confirmation was REFUSED —
    # PROFILE_VALIDATION_FAILED, "variant 'cylindrical' is not valid for Jar"; and a dropper brief proposed a screw
    # cap, so a dropper concept was drawn as a screw-cap bottle. The brief's own words choose (the composer's "Cap or
    # closure" hint is part of the brief text); else the archetype's FIRST option in the editor's vocabulary
    # (targets/ui.py CONTAINER_EDITOR_ARCHETYPES), which is what the confirmation validates against. A proposal,
    # confirmed or changed by a person at the gate.
    from apps.pipeline.targets.ui import CONTAINER_EDITOR_ARCHETYPES
    cfg = next((a for a in CONTAINER_EDITOR_ARCHETYPES if a["key"] == archetype), {})
    caps = [k for k, _ in cfg.get("caps", [])]
    variants = [k for k, _ in cfg.get("variants", [])]
    # §BH61(a): the trailing `else "screw"` / `else "cylindrical"` were two more bottle fallbacks — they
    # fired exactly when `cfg` was empty, i.e. when NO archetype was resolved, so an unnamed form was
    # proposed with a bottle's closure and a bottle's variant. With no archetype there is no vocabulary to
    # choose from, and the proposal carries None for both rather than a bottle's words.
    cap = next((k for k, words in _CAP_WORDS if k in caps and re.search(words, text)),
               caps[0] if caps else None)
    variant = next((k for k, words in _VARIANT_WORDS if k in variants and re.search(words, text)),
                   variants[0] if variants else None)
    if lid_shape_named_in(archetype, text) is not None:
        # [§BH71 PART 3, the owner's goal of 2026-09-28: "It never squeezes a product into the wrong shape." A lid
        # shape the brief names that no variant of the form draws — "an oval compact", "an oval tin" — was proposed
        # the form's FIRST variant, a rounded rectangle and a round tin. The proposal carries none, and the record
        # says which shape was named (`_seed_outline_proposal`)]
        variant = None
    return ContainerProfile(archetype=archetype, variant=variant, cap_style=cap, **kw)


#: §BH70(1) — THE WORDS A TEXT NAMES A FORM WITH, whole words, read in this order. A hinged case first — "palette"
#: and "compact" are never a jar or a bottle (§BH55(a)) — then a jar; then the three slim forms BEFORE the tube,
#: because the tube's branch read "mascara", "lipstick" and "stick" as a squeeze tube with a crimped end, and a brief
#: that says "a mascara tube" or "a tube of lipstick" means the mascara or the lipstick; a liquid liner or a gloss
#: with a wand is the mascara's vial, a liner without "liquid" is a pencil; then the tube and the bottle, their words
#: as they were. A bare "gloss" still names a tube: a gloss comes in a squeeze tube and in a wand vial alike, and
#: which one it is here is the owner's word, not this list's. A text naming none of these names no form (§BH61(a)).
#: [HIS WORD, 2026-09-27 — "Neither: when a brief says "gloss" without saying which, ask me: wand vial or squeeze
#: tube." A bare "gloss" names no form now, and New design asks him (``gloss_question``). A gloss said with a wand or
#: a vial is the mascara's vial; one said with a tube, or squeezed, is the tube; his answer rides the brief as
#: "[Container type: wand vial]" or "[Container type: squeeze tube]", which these words read.]
#: §BH71 PART 3: a perfume in a brief's own words — the bottle's form, the crimped spray and the flacon share them —
#: never "fragrance-free" or "perfume-free", and never an ingredient list's bare "Parfum"
_PERFUME_WORDS = r"perfume(?![- ]free)|fragrance(?![- ]free)|eau de (?:parfum|toilette|cologne)|extrait de parfum"
FORM_WORDS = (
    ("compact", r"\b(palette|compact|pans?|hinged|baked|cushion)\b"),
    # [§BH71 PART 3: the five new forms, each before the form its words would otherwise fall to — a balm TIN before
    # the jar's "pot", a SACHET or a sheet mask before anything, a deodorant's OVAL STICK before the lipstick's
    # "stick", a dry shampoo's CAN before the bottle's "spray", an AMPOULE before the bottle's "serum"]
    ("tin", r"\b(tins?|slide tins?)\b"),
    ("bottle", r"\broll[- ]?ons?\b|\brollerballs?\b"),        # [a roll-on deodorant is a bottle, not a stick]
    ("sachet", r"\b(sachets?|sheet masks?|sample packs?)\b"),
    ("jar", r"\b(jar|pot|sifter|loose powder)\b"),
    ("oval_stick", r"\b(deodorants?|antiperspirants?|deo|body sticks?|oval sticks?)\b"),
    ("lipstick", r"\b(lipsticks?|lip ?sticks?|sticks?)\b"),
    ("mascara", r"\b(mascaras?|wands?|liquid (?:eye)?liners?)\b"
                r"|\bgloss(?:es)?\b[^.;:]{0,40}\bvials?\b|\bvials?\b[^.;:]{0,40}\bgloss(?:es)?\b"),
    ("pencil", r"\b(pencils?|(?:eye|lip) ?liners?|liners?|kohl|kajal|pens?)\b"),
    ("tube", r"\btube\b|\bsqueeze\b[^.;:]{0,40}\bgloss(?:es)?\b|\bgloss(?:es)?\b[^.;:]{0,40}\bsqueeze\b"),
    ("aerosol", r"\b(aerosols?|dry shampoos?|hair ?sprays?|spray cans?)\b"),
    ("ampoule", r"\b(ampoules?|ampules?|single[- ]dose|sample vials?)\b"),
    ("bottle", r"\b(bottle|dropper|serum|pump|spray|" + _PERFUME_WORDS + r"|nail polish|airless|mists?)\b"),
)


#: [His word after the fix for design 118, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 1dea9c5): "the trend search
#: uses the brief's own product words (lip gloss, wand vial), for every design".] The labels a brief's copy is given
#: under — the words printed on the pack, never the words that say what the product is: design 118's "Carton back: How
#: to use: apply to lips alone or over lipstick." read its lip gloss in a wand vial as a lipstick
COPY_FIELD_RE = re.compile(r"^[ \t]*(?:[a-z][a-z ]{0,20}\bcopy|(?:(?:carton|vial|tube|bottle|box|pack|jar|label|"
                           r"lid|cap)[ \t]+)?(?:front|back|side|top|bottom|base)s?|how to use|directions|ingredients|"
                           r"inci|warnings?|cautions?)[ \t]*:", re.I)
#: a line another field's label opens ("Colours: ...") — where a copy field's run-on lines end
FIELD_LABEL_RE = re.compile(r"^[ \t]*[a-z][a-z ]{0,30}:", re.I)


def product_words(text) -> str:
    """[His word of 2026-10-03.] A brief's own words for what its product is — the brief with its copy fields left out:
    each line a copy label opens (COPY_FIELD_RE) and the lines that run on from it, to a blank line or a line another
    field's label opens (FIELD_LABEL_RE). What the form, the trend search and the gloss question read."""
    out, in_copy = [], False
    for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if COPY_FIELD_RE.match(line):
            in_copy = True
            continue
        if in_copy and (not line.strip() or FIELD_LABEL_RE.match(line)):
            in_copy = False
        if not in_copy:
            out.append(line)
    return "\n".join(out)


def form_named_in(text):
    """The form a text names in words, or None — never a default (§BH61(a)). THE one reading of form words: the
    container's own proposal (`_infer_profile`) and the Complete Product pilot (`complete_product_pilot`) both read
    it, where each kept a copy of its own and the copies disagreed — the pilot called a compact a jar and anything
    unnamed a bottle (§BH70(1)). [His goal of 2026-10-06, item 1: "Never a guess from picture readings or word order."]
    A text that names two forms names None here — it read the first of ``FORM_WORDS`` that matched, so design 51's
    "a blush/peach palette" made its lip-gloss tube a compact — and the one asking is ``form_question``."""
    named = forms_named_in(text)
    return named[0] if len(named) == 1 else None


#: [His goal of 2026-10-06, item 1.] Form words in one clause name ONE thing — "a deodorant stick", "a tube of
#: volumising mascara", "a solid perfume in a slide tin", "a lip gloss with a doe-foot wand", "a cream jar with a
#: dropper": no sentence, line, comma, colon or bracket between them; that thing is the form of its more particular word,
#: the one ``FORM_WORDS`` lists first (the list orders the words of one product: "deodorant" before "stick", "mascara"
#: before "tube", a tin before a perfume it holds). Form words in two clauses are two things — design 120's "Container
#: type: jar" line and its "squeeze tube" line, design 51's "lip-gloss tube" and its "blush/peach palette" — and are
#: never chosen between by that order.
_CLAUSE_BREAK = re.compile(r"[.;:!?\n,()\[\]]")


def forms_named_in(text) -> list:
    """Every form a text names in its own words, in the order the text names them — each clause once (a word inside
    another form's longer words, or beside them in one clause, is that clause's), never chosen between."""
    low = (text or "").lower()
    spans = []                                      # (start, end, the FORM_WORDS entry it matched, its form)
    for i, (form, words) in enumerate(FORM_WORDS):
        spans += [(m.start(), m.end(), i, form) for m in re.finditer(words, low)]
    spans = [s for s in spans                       # a match inside another form's longer match is that match's
             if not any(o[3] != s[3] and o[0] <= s[0] and s[1] <= o[1] and o[1] - o[0] > s[1] - s[0] for o in spans)]
    spans.sort()
    phrases = []
    for start, end, entry, form in spans:
        last = phrases[-1] if phrases else None
        if last is not None and (start <= last["end"] or not _CLAUSE_BREAK.search(low[last["end"]:start])):
            last["end"] = max(last["end"], end)
            last["entries"].add((entry, form))
        else:
            phrases.append({"end": end, "entries": {(entry, form)}})
    out = []
    for phrase in phrases:
        form = min(phrase["entries"])[1]            # the clause's more particular word: its entry listed first
        if form not in out:
            out.append(form)
    return out


#: [His goal of 2026-10-06, item 1 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a9ac953): "Rule, for every design: the
#: Container type I choose ALWAYS wins. Then my brief's own words. Never a guess from picture readings or word order."]
#: His choice rides the brief as "[Container type: …]" — New design's Container type field (static/js/poll.js), his
#: answer when he is asked which, a palette's own start (targets/palette.py). MEASURED on design 120: that field sent
#: "jar"; the line was read with the brief as one text, among its words, and ``FORM_WORDS`` lists jar before tube — the
#: only "jar" in the design was the field's. It is read first now, by itself, and the brief's words only without it.
CHOSEN_TYPE_RE = re.compile(r"\[Container type:\s*([^;\]\n]*)", re.I)
_CHOSEN_FIELD_RE = re.compile(r"Container type:\s*[^;\]\n]*;?[ \t]*", re.I)


def chosen_form(text) -> tuple:
    """``(form, said)``: the form his last Container type choice names — a key ("tube", "Oval Stick") or his words
    ("squeeze tube", "wand vial") — and his words as he chose; ``(None, said)`` for "Other", which names no form the
    system draws; ``(None, "")`` where he chose none."""
    said = ""
    for m in CHOSEN_TYPE_RE.finditer(str(text or "")):
        if m.group(1).strip():
            said = m.group(1).strip()
    if not said:
        return None, ""
    key = re.sub(r"[\s\-]+", "_", said.lower())
    if _declared.is_known(key):
        return key, said
    named = forms_named_in(said)
    return (named[0] if len(named) == 1 else None), said


def without_choice(text) -> str:
    """The brief without his Container type field — what the brief's own words are read in. The rest of that line (the
    product's category, size and closure) is his own words and stays."""
    return re.sub(r"\[\s*\]", "", _CHOSEN_FIELD_RE.sub("", str(text or "")))


def form_choice(text) -> dict:
    """THE one reading of a design's form [his goal of 2026-10-06, item 1]: ``{"form", "source", "said", "named"}`` —
    the Container type he chose (source "chosen"; "Other" names none), else the one form the brief's own words name
    (source "brief"), else None; ``named`` is every form the brief's own words name, so that two are asked about at
    New design (``form_question``), never chosen between. No picture reading is read here."""
    chosen, said = chosen_form(text)
    named = forms_named_in(product_words(without_choice(text)))
    if said:
        return {"form": chosen, "source": "chosen", "said": said, "named": named}
    return {"form": named[0] if len(named) == 1 else None, "source": "brief" if len(named) == 1 else "",
            "said": "", "named": named}


def form_label(form) -> str:
    """A form in his words, as New design's Container type list names it."""
    return _declared.vocabulary_of(form)["label"] if _declared.is_known(form) else str(form or "")


def form_line(task, inside=False) -> str:
    """[His goal of 2026-10-06, item 1: "The chosen type holds through the title, the trend search, the directions, the
    concepts, the shape step and the carton."] The line every concept prompt carries: the product's form and whose
    word it is — "" where none is known. A container's prompt read its form only where no product profile was read; a
    carton's (``inside``) never named the product it holds."""
    form = form_of_task(task)
    if not _declared.is_known(form):
        return ""
    text = brief_text(task)
    reading = form_choice(text)
    whose = ("the owner's Container type, chosen at New design" if reading["source"] == "chosen"
             and reading["form"] == form else "as the brief's own words name it" if reading["form"] == form
             else "as confirmed at the shape step")
    what = product_in_form(form, text) or form_label(form).lower().replace(" / ", " or ")
    return ("THE PRODUCT %s: a %s — %s. It overrides any other form a word of the brief, a reference or a trend "
            "picture suggests." % ("INSIDE THIS CARTON" if inside else "'S FORM", what, whose)).replace(" 'S", "'S")


#: the line a design's feed opens with: the form it is made in and whose word that is
FORM_SAID = "ARIA: the product's form —"


def form_said(task) -> str | None:
    """[His goal of 2026-10-06, item 1: "tell me in words".] The feed's first line for a design made in a product's form
    (a container, or a carton round one): its form and whose word it is — his Container type, else his brief's own
    words — or that he chose none and his brief names none once; None for a design no form is made in."""
    if getattr(task, "design_target", None) not in (DesignTarget.PRODUCT_CONTAINER.value, DesignTarget.PACKAGING.value):
        return None
    reading = form_choice(brief_text(task))
    if reading["source"] == "chosen" and reading["form"]:
        return "%s %s, your Container type (“%s”)" % (FORM_SAID, form_label(reading["form"]), reading["said"])
    if reading["source"] == "chosen":
        return "%s none drawn yet: your Container type is “%s” — the shape step asks you" % (FORM_SAID, reading["said"])
    if reading["form"]:
        return "%s %s, as your brief's own words name it" % (FORM_SAID, form_label(reading["form"]))
    if reading["named"]:
        return "%s not chosen — your brief names %s; the shape step asks you" % (
            FORM_SAID, " and ".join(form_label(f).lower() for f in reading["named"]))
    return None


#: [His goal of 2026-10-06, item 1.] What New design asks before anything is created or spent, beside the gloss
#: question: a brief whose own words name two forms with no Container type chosen; and — the executor's extension, his to
#: veto — a Container type that differs from the one form his brief's words name (design 120: "Jar" chosen, "squeeze
#: tube" written). His choice stands first and wins by one click; nothing is started until he answers.
FORM_QUESTION = "CONTAINER_TYPE_QUESTION"
FORM_DIFFERS = "CONTAINER_TYPE_DIFFERS"


def form_question(text, confirmed=False):
    """The question New design asks before anything starts, or None — a gloss with no container (``gloss_question``),
    two forms in the brief's own words with none chosen, or a chosen Container type his brief's words do not name
    (unless he has ``confirmed`` it). Words and choices in his own terms; his answer comes back as his Container type."""
    reading = form_choice(text)
    named = reading["named"]
    if reading["source"] == "chosen":
        if confirmed or reading["form"] is None or not named or reading["form"] in named:
            return None
        words = ", ".join("“%s”" % form_label(f).lower() for f in named)
        return {"error": FORM_DIFFERS, "question": "%s or %s?" % (form_label(reading["form"]),
                                                                  " or ".join(form_label(f) for f in named)),
                "words": ("You chose %s as the Container type, and your brief's own words say %s. Your choice wins — "
                          "start as %s, or change it to what your brief says. Nothing has been started or spent."
                          % (form_label(reading["form"]), words, form_label(reading["form"]))),
                "choices": ([{"key": reading["form"], "label": "%s — your Container type" % form_label(reading["form"]),
                              "keeps": True}]
                            + [{"key": f, "label": "%s — your brief's words" % form_label(f)} for f in named])}
    if len(named) > 1:
        return {"error": FORM_QUESTION, "question": "Which is it in — %s?" % " or ".join(form_label(f) for f in named),
                "words": ("Your brief names %s. Choose the one the product comes in; it is kept as your Container "
                          "type. Nothing has been started or spent."
                          % " and ".join(form_label(f).lower() for f in named)),
                "choices": [{"key": f, "label": form_label(f)} for f in named]}
    return gloss_question(text)


#: THE OWNER'S ANSWER OF 2026-09-27 TO THE §BH70 REPORT'S FOURTH QUESTION: "Neither: when a brief says "gloss"
#: without saying which, ask me: wand vial or squeeze tube." A gloss named as the PRODUCT — a finish's gloss
#: (high-gloss, a gloss varnish, spot or selective gloss, gloss details) is not the product and asks nothing.
GLOSS_QUESTION = "GLOSS_CONTAINER_QUESTION"
GLOSS_CHOICES = (("wand vial", "Wand vial"), ("squeeze tube", "Squeeze tube"))
_GLOSS_PRODUCT_RE = re.compile(r"\bgloss(?:es)?\b")
_GLOSS_FINISH_RE = re.compile(
    r"\b(?:high|semi|super|spot|selective|uv)[- ]?gloss\b"
    r"|\bgloss(?:es)?\s+(?:finish(?:es)?|varnish(?:es)?|coat(?:ing)?s?|laminat\w*|uv|effects?|details?|paper|inks?|"
    r"levels?|accents?|spots?)\b")


def gloss_question(text):
    """What New design asks before anything is created or spent — or None: a text that names a gloss as its product
    and no container for it (``form_named_in`` reads no form in it). Words and choices in his own terms."""
    reading = form_choice(text)                      # [his goal of 2026-10-06, item 1] his choice, then his words
    low = product_words(without_choice(text)).lower()   # [his word of 2026-10-03] its own words, never its copy
    if reading["said"] or reading["named"] or not _GLOSS_PRODUCT_RE.search(_GLOSS_FINISH_RE.sub(" ", low)):
        return None
    return {"error": GLOSS_QUESTION, "question": "Wand vial or squeeze tube?",
            "words": "Your brief says gloss without saying which it comes in. Nothing has been started or spent.",
            "choices": [{"key": key, "label": label} for key, label in GLOSS_CHOICES]}


#: a form's vessel, in his words, when it holds a product other than its namesake — the mascara's is the wand vial
VESSEL_WORDS = {"mascara": "wand vial", "tube": "squeeze tube"}
#: the products those vessels hold besides their namesakes, each named for what it is (the mascara's declaration:
#: "a mascara, or a gloss or liquid liner with a wand")
_VESSEL_PRODUCTS = (("lip gloss", _GLOSS_PRODUCT_RE), ("liquid eyeliner", re.compile(r"\bliquid (?:eye)?liners?\b")))


def product_in_form(form, text=""):
    """What a concept is told the product is, in words without an article: a product the form's vessel holds besides
    its namesake — "lip gloss in a wand vial" — or the mascara itself when its brief says so; None otherwise, the
    form's label standing. A finish's gloss is not a product."""
    vessel = VESSEL_WORDS.get(form)
    if vessel is None:
        return None
    low = _GLOSS_FINISH_RE.sub(" ", (text or "").lower())
    if form == "mascara" and re.search(r"\bmascaras?\b", low):
        return "mascara"
    return next(("%s in a %s" % (words, vessel) for words, rx in _VESSEL_PRODUCTS if rx.search(low)), None)


def map_sets_the_name(spec: dict | None, output) -> bool:
    """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): the map path for a wand vial.] True
    where the design's front is set from its concept's map — a map on record READ this output's approved picture and
    names a type line — so the name is set where and as large as the picture sets it (`compose_container._map_type_group`),
    its width measured at acceptance as every front line's is, and the ruled size's stop (`name_fits_front`) does not
    apply."""
    import hashlib

    from apps.pipeline.services import concept_design_map as dm
    rec = (spec or {}).get(dm.SCHEMA) or {}
    archetype = ((spec or {}).get("container_profile") or {}).get("archetype")
    pic = _map_bytes(getattr(output, "approved_image", None), archetype) if output is not None else None
    return bool(rec.get("state") == dm.MAP_READ and pic and rec.get("source_sha256") == hashlib.sha256(pic).hexdigest()
                and any(p.get("kind") == "type" for p in rec.get("parts") or []))


def name_fits_front(profile: ContainerProfile, name: str, *, map_sets_name: bool = False):
    """None when the product's name can be set across this form's front; else the stop, in words and numbers.

    §BH70(1) and his §BD(b), "A clipped brand name never ships": the front the composer sets a name on is the form's
    label zone, and it clips anything wider. A single word wider than that zone at the size a name prints on the ruled
    front (`HERO_NAME_PT`, the size production draws it at) can only be cut off — so the shape step says so and stops,
    before anything is drawn, rather than the drawing failing later or shipping a cut name. A face form is not asked:
    its name is set by the largest step its own lid holds (§BH68(b)). Running a name along a pencil's length is how a
    pencil is printed and is not built: the instruments that measure a front read its words as running across it, and
    teaching them otherwise is the owner's word, not this function's.

    [His go of 2026-10-02: the map path for a wand vial — "Strawberry", "Watermelon" or "Champagne" stopped a 16 mm vial
    whose picture sets its name in two smaller lines] ``map_sets_name`` (``map_sets_the_name``): the front is set from
    its concept's map, the name where and as large as the picture sets it — no stop at the ruled size; a line wider than
    the front he confirmed is measured over it at acceptance (`generic_front_copy_fit`)."""
    if not name or map_sets_name or not _declared.is_known(profile.archetype) or _declared.is_face(profile.archetype):
        return None
    from apps.ire.compose_container import HERO_NAME_PT, name_width_estimate_mm
    front_mm = build_backbone(profile).label_zone[2]
    word = max(name.split(), key=lambda w: name_width_estimate_mm(w, HERO_NAME_PT), default="")
    word_mm = name_width_estimate_mm(word, HERO_NAME_PT)
    if word_mm <= front_mm:
        return None
    label = _declared.vocabulary_of(profile.archetype)["label"].lower().replace(" / ", " or ")
    return {
        "code": "CONTAINER_NAME_WIDER_THAN_ITS_FRONT", "word": word, "word_mm": round(word_mm, 1),
        "front_mm": round(front_mm, 1), "size_pt": HERO_NAME_PT,
        "reason": (f"The name \u201c{name}\u201d does not fit across this {label}'s front: its word \u201c{word}\u201d "
                   f"needs {word_mm:.1f} mm at the size a name is printed, and the front is {front_mm:.1f} mm "
                   "across. It would be cut off, so nothing is drawn. A wider product, or a shorter name, fits; "
                   "running the name along the product's length is not built yet."),
    }


#: §BH55 Phase 1: the words a brief names a closure or a form with — whole words, as the archetype scan above
_CAP_WORDS = (("dropper", r"\b(dropper|pipette)\b"),
              # [§BH71 PART 3: the catalogue's closures, each before the one its words would otherwise fall to]
              ("airless_pump", r"\bairless\b"), ("brush_cap", r"\bnail polish(?! remover)\b"),
              ("crimp_spray", r"\b(" + _PERFUME_WORDS + r")\b"), ("mist", r"\bmists?\b"),
              ("roller_ball", r"\broll[- ]?ons?\b|\brollerballs?\b"), ("doe_foot", r"\bdoe[- ]?foot\b"),
              ("brush", r"\bliquid (?:eye)?liners?\b"), ("click", r"\bclick\b"),
              ("nozzle", r"\b(nozzle|applicator tip)\b"),
              ("pump", r"\b(pump|airless|dispenser)\b"),
              ("flip", r"\bflip(?:[- ]?top)?\b"), ("crimp", r"\bcrimp(?:ed)?\b"), ("lid", r"\blid\b"))
_VARIANT_WORDS = (("square", r"\bsquare\b"), ("tapered", r"\btapered\b"), ("slim", r"\b(slim|slender)\b"),
                  # [§BH71 PART 3: a brief's own word for a form's shape — a round compact was proposed a rounded
                  # rectangle because no word here said "round" (the research leaf's measure)]
                  ("round", r"\bround\b"), ("slide", r"\bslid(?:e|ing)\b"), ("oval", r"\boval\b"),
                  ("necked", r"\bnecked\b"), ("four_side", r"\bfour[- ]side\b"),
                  ("cushion", r"\bcushion\b"), ("paperboard", r"\b(paperboard|magnetic book)\b"),
                  ("sifter", r"\b(sifter|loose powder)\b"), ("airless", r"\bairless\b"),
                  ("flacon", r"\b(" + _PERFUME_WORDS + r"|flacon)\b"),
                  ("roller", r"\broll[- ]?ons?\b|\brollerballs?\b"), ("pen", r"\bpens?\b"))

_LID_NOUNS = r"(?:compacts?|palettes?|tins?|cases?|lids?)"
#: §BH71 PART 3, the owner's goal of 2026-09-28: "When a concept shows a shape the system doesn't know, it says so and
#: offers to learn it. It never squeezes a product into the wrong shape." A LID'S shape a brief names that no variant of
#: a form drawn in plan draws — (kind, pattern, the words said). Matched tightly: the shape word before the form's own
#: noun, or "X-shaped" — so a product called "Rose Heart" or "Star Glow", a "flower oil" in its ingredients or "petal
#: sheen" in its theme names no shape (measured on his 65 briefs: none matches; "petal" and "flower" appear in two as
#: the product's own description, task 51 a compact).
LID_SHAPE_WORDS = (
    ("oval", r"\boval\s+(?:[a-z-]+\s+){0,2}?" + _LID_NOUNS + r"\b|\boval[- ]shaped\b", "an oval lid"),
    ("hexagon", r"\bhexagon(?:al)?\s+(?:[a-z-]+\s+){0,2}?" + _LID_NOUNS + r"\b|\bhexagon(?:al)?[- ]shaped\b",
     "a six-sided lid"),
    ("octagon", r"\boctagon(?:al)?\s+(?:[a-z-]+\s+){0,2}?" + _LID_NOUNS + r"\b|\boctagon(?:al)?[- ]shaped\b",
     "an eight-sided lid"),
    ("heart", r"\bheart[- ]shaped\b", "a heart-shaped lid"),
    ("shell", r"\b(?:sea)?shell[- ]shaped\b", "a shell-shaped lid"),
    ("star", r"\bstar[- ]shaped\b", "a star-shaped lid"),
    ("flower", r"\b(?:flower|petal)[- ]shaped\b", "a flower-shaped lid"),
    ("teardrop", r"\bteardrop[- ]shaped\b|\bteardrop\s+" + _LID_NOUNS + r"\b", "a teardrop-shaped lid"),
)


def lid_shape_named_in(archetype, text: str) -> dict | None:
    """``{"kind", "words"}`` — the lid shape ``text`` names for a form drawn in PLAN when no variant of that form
    draws it (`LID_SHAPE_WORDS`); None for a form drawn standing (its drawing is its concept's own traced outline —
    no variant to squeeze it into), for a text that names no lid shape, and for one a declared variant draws."""
    import re
    if not _declared.is_known(archetype) or _declared.drawn_as_of(archetype) != _declared.PLAN:
        return None
    variants = {k for k, _label in _declared.variants_of(archetype)}
    for kind, pattern, words in LID_SHAPE_WORDS:
        if kind not in variants and re.search(pattern, (text or "").lower()):
            return {"kind": kind, "words": words}
    return None


#: §BH71 PART 3: the sentence the shape step says of a lid no variant draws, by where it was seen
UNKNOWN_SHAPE_SENTENCE = {
    "concept": "The approved concept shows %s — a shape the system does not draw yet, so no shape is chosen for you:"
               " choose the nearest yourself.",
    "brief": "The brief names %s — a shape the system does not draw yet, so no shape is chosen for you: choose the"
             " nearest yourself.",
}

#: §BH55 Phase 1 — the ONE container on this machine whose size a person confirmed from a concept: task 52's, for
#: product 5 (net content "30 ml e 1 fl. oz."), output 39 — body 33 mm wide (USER_CONFIRMED_VISUAL_PROFILE) and
#: drawn 96.306 mm tall with its closure (container_drawing_source/1.0). The generic silhouette draws the WHOLE
#: container, closure included, inside the editor's height, so it is the drawn total that is scaled — not the 68 mm
#: body the pilot's dropper sheet extends by its closure. The task was rejected as a DESIGN; this is its confirmed
#: size, not its picture — and its proportion is that confirmed profile's, not any concept's own: nothing here
#: reads a new concept's proportion. No jar or tube on this machine carries a confirmed size; neither is scaled.
_BOTTLE_REFERENCE = {"capacity_ml": 30.0, "width_mm": 33.0, "height_mm": 96.306}
#: a volume in the brief's own words — whole numbers or one or two decimals, never a thousands separator
_ML_WORDS = r"(?<![\d.,])(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:ml|millilit(?:re|er)s?)\b"
_FL_OZ_WORDS = r"(?<![\d.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*fl\.?\s*oz\b"
_ML_PER_FL_OZ = 29.5735


def _record_describes_carton(product) -> bool:
    """CORR-2 §4, measured on the pilot's record: a product row whose type is a carton records the OUTER CARTON —
    its sizes are the box (the packaging stage reads them as the carton), never the container inside it."""
    import re
    return bool(re.search(r"\bcarton\b", (getattr(product, "product_type", "") or "").lower()))


def _capacity_ml(text: str, product) -> float | None:
    """The capacity the brief names in its own words (the composer's "Capacity" hint is part of the brief text),
    else the product record's own net content. Millilitres first; fluid ounces only when no millilitres are named.
    Two different volumes in the brief are not a capacity: nothing is proposed from them."""
    import re
    net = (getattr(product, "net_weight", "") or "").lower() if product is not None else ""
    for words in (text or "", net):
        found = {round(float(v.replace(",", ".")), 1) for v in re.findall(_ML_WORDS, words)}
        if not found:
            found = {round(float(v.replace(",", ".")) * _ML_PER_FL_OZ, 1)
                     for v in re.findall(_FL_OZ_WORDS, words)}
        if len(found) > 1:
            return None
        if found:
            return found.pop()
    return None


def _bottle_size_for(capacity_ml: float | None) -> dict:
    """§BH55 Phase 1: a bottle proposed at the size its capacity names — the confirmed reference scaled by the cube
    root of the capacity ratio (its proportion kept, the volume's scale), the scale held so both sides land inside
    the editor's own ranges (targets/ui.py CONTAINER_EDITOR_PROPORTIONS, never widened), rounded to the editor's
    1 mm step. Nothing without a capacity. A proposal: a person confirms or changes it at the gate."""
    if not capacity_ml or capacity_ml <= 0:
        return {}
    from apps.pipeline.targets.ui import CONTAINER_EDITOR_PROPORTIONS
    rng = {p["key"]: (p["min"], p["max"]) for p in CONTAINER_EDITOR_PROPORTIONS}
    ref = _BOTTLE_REFERENCE
    lo = max(rng["width_mm"][0] / ref["width_mm"], rng["height_mm"][0] / ref["height_mm"])
    hi = min(rng["width_mm"][1] / ref["width_mm"], rng["height_mm"][1] / ref["height_mm"])
    scale = min(max((capacity_ml / ref["capacity_ml"]) ** (1 / 3), lo), hi)
    return {"width_mm": float(round(ref["width_mm"] * scale)),
            "height_mm": float(round(ref["height_mm"] * scale))}


def _seed_concept_proposals(record: dict, approved_image) -> dict:
    """2B-3V UI correction §2: seed CONCEPT-ONLY visual proposals (body/cap
    color, transparency, front orientation) from the SELECTED variation's
    persisted contract signatures — always INFERRED_NONAUTHORITATIVE, never
    photo/manufacturer authority. Absent signatures leave fields untouched."""
    from apps.pipeline.services import container_contract as cc

    prov = (getattr(approved_image, "reference_provenance", None) or {})
    contract = prov.get("container_variation_contract") or {}
    if not contract:
        return record
    import copy
    out = copy.deepcopy(record)
    fields = out.setdefault("fields", {})

    def _propose(name, text):
        if text:
            fields[name] = {"value": f"{str(text)[:180]} (concept-only)",
                            "source": cc.SRC_INFERRED,
                            "verification": cc.INFERRED}

    _propose("cap_color", contract.get("cap_body_signature"))
    _propose("body_base_color", contract.get("color_field_signature"))
    _propose("body_transparency", contract.get("color_field_signature"))
    _propose("front_orientation",
             "front = decorated face of the selected concept "
             f"({prov.get('variation_identity', '')})")
    _propose("back_orientation", "opposite the proposed front")
    out["profile_hash"] = cc.profile_hash(out)
    return out


def _concept_bytes(image) -> bytes | None:
    """The approved concept picture's bytes, or None — a picture that cannot be opened is said by the trace."""
    f = getattr(image, "image_file", None)
    if not f or not getattr(f, "name", ""):
        return None
    try:
        with f.open("rb") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def _is_face(archetype) -> bool:
    return bool(archetype) and _declared.is_known(archetype) and _declared.is_face(archetype)


def _map_bytes(image, archetype) -> bytes | None:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2): "ONE ENGINE: palettes and compacts run
    the same map-first path as the tube and carton"] The picture a design's map reads: a face form's lid stood square
    (``concept_outline.lid_picture``) — a compact's map reads its lid as a carton's reads its front — every other form's
    concept as it stands; None where there is none (the lid's trace said why)."""
    pic = _concept_bytes(image)
    if pic is None or not _is_face(archetype):
        return pic
    from apps.pipeline.services import concept_outline as co
    lid = co.lid_picture(pic)
    return lid["png"] if lid["state"] == co.LID_STRAIGHTENED else None


def _reading_shape(spec: dict | None) -> tuple:
    """(the lid's shape the concept's own reading names, its product box as fractions of the frame) — the vision
    read's ``surface_shape`` and ``surface_box`` when a read is on record, never a read made here."""
    rec = (spec or {}).get("container_concept_layout/1.0") or {}
    if rec.get("state") != "READ":
        return None, None
    box, size = rec.get("surface_box"), (rec.get("image") or {}).get("size_px")
    frac = ([box[0] / size[0], box[1] / size[1], box[2] / size[0], box[3] / size[1]]
            if box and size and len(box) == 4 and len(size) == 2 else None)
    return rec.get("surface_shape"), frac


def trace_concept(archetype: str, image, spec: dict | None = None, *, cap_style: str | None = None,
                  named_shape: str | None = None) -> dict | None:
    """§BH71 PART 1: the approved concept's outline (`services.concept_outline`) — a form drawn in PLAN by its lid's
    rim, a form drawn in ELEVATION standing, read about its own axis — or None for a form this trace does not read:
    the dropper, which keeps the M3 drawing §BH49 chose, and a form the declaration does not know. Local pixels only
    — nothing paid, nothing written."""
    from apps.pipeline.services import concept_outline as co
    if not _declared.is_known(archetype):           # [his goal for the pitch, B (9)] a dropper traced too
        return None
    if _declared.drawn_as_of(archetype) == _declared.PLAN:
        if not _declared.traced_variants_of(archetype):     # [§BH71 PART 3: a flat pouch has no lid to trace]
            return None
        shape, box = _reading_shape(spec)
        named_by = "the concept's reading"
        if shape is None and named_shape == "oval":
            # [§BH71 PART 3: no reading names the lid when the shape step is proposed (the concept's read comes
            # later, and is paid), so an ellipse was read as a round lid seen tilted even when the brief says "an oval
            # compact" — the brief's own name for the lid names it, and the record says whose name it was]
            shape, named_by = named_shape, "the brief's words"
        trace = co.trace_plan(_concept_bytes(image), reading_shape=shape, surface_box=box)
        if shape is not None:
            trace["named_by"] = named_by
        return trace
    return co.trace_elevation(_concept_bytes(image))


def _learned_variant_on(record: dict, variant: str) -> dict:
    """§BH71 PART 3: the record with a learned lid's variant proposed — the brief names a lid shape its form has
    learned (a concept's trace, below, still proposes what its picture shows)."""
    import copy
    from apps.pipeline.services import container_contract as cc
    out = copy.deepcopy(record)
    out["variant"] = variant
    out["fields"]["variant"] = cc._field(variant, source=cc.SRC_INFERRED, verification=cc.INFERRED)
    out["profile_hash"] = cc.profile_hash(out)
    return out


def _unknown_shape_on(record: dict, shape: dict, seen: str) -> dict:
    """§BH71 PART 3: the record with no variant proposed and the lid shape no variant draws said on it —
    ``unknown_shape`` {kind, words, source, sentence}; the person chooses at the shape step, nothing for them."""
    import copy
    from apps.pipeline.services import container_contract as cc
    out = copy.deepcopy(record)
    out["variant"] = ""
    out["fields"]["variant"] = cc._field(None, source=cc.SRC_UNKNOWN, verification=cc.MISSING)
    out["unknown_shape"] = {"kind": shape["kind"], "words": shape["words"],
                            "source": {"concept": "the approved concept", "brief": "the brief"}[seen],
                            "sentence": UNKNOWN_SHAPE_SENTENCE[seen] % shape["words"]}
    out["profile_hash"] = cc.profile_hash(out)
    return out


#: [His goal after the pitch page, 2026-10-15, A (3): "SHAPES AND PROPORTIONS come from the concept ... (131 drawn
#: landscape when the concept is portrait)"] a size within this of the form's own starting size (``nominal``) is that
#: starting size — nobody chose it; and a height the concept's proportion gives within this share of the one given is
#: the same height
NOMINAL_MATCH_MM = 0.05
CONCEPT_HEIGHT_AGREES = 0.03


def concept_proportion_size(archetype: str, width_mm, height_mm, trace: dict | None, brief: str = "") -> tuple:
    """[His goal after the pitch page, 2026-10-15, A (3)] ``(width, height, why)`` — the size a product is drawn at. A
    size the brief declares wins, and so does any size a person or a record chose; only the form's own starting size
    (``archetypes.nominal``), confirmed as it opened, gives way to the concept's own proportion — the height its traced
    outline gives the width (``concept_outline.plan_height_ratio`` in plan, ``height_to_width`` in elevation, a round
    width form's drawn width). ``why`` is None where the size stands as given. MEASURED on 131: its concept a portrait
    palette (0.888 wide to 1 tall), proposed 110 x 123.8 mm, confirmed at the compact's starting 110 x 95 — landscape."""
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.targets.container.silhouettes import drawn_width_mm
    from apps.pipeline.targets.ui import brief_stated_sizes
    if (not _declared.is_known(archetype) or width_mm is None or height_mm is None or not trace
            or trace.get("state") != co.TRACED_FROM_CONCEPT):
        return width_mm, height_mm, None
    nominal = _declared.nominal_of(archetype)
    if (abs(float(width_mm) - float(nominal["width_mm"])) > NOMINAL_MATCH_MM
            or abs(float(height_mm) - float(nominal["height_mm"])) > NOMINAL_MATCH_MM):
        return width_mm, height_mm, None
    stated = brief_stated_sizes(brief)
    if "width_mm" in stated or "height_mm" in stated:
        return width_mm, height_mm, None
    if trace.get("view") == "PLAN":
        if trace.get("kind") not in (co.ROUND, co.SQUARE, co.ROUNDED_RECT, co.OVAL):
            return width_mm, height_mm, None
        height = float(width_mm) * co.plan_height_ratio(trace)
    elif trace.get("height_to_width"):
        height = drawn_width_mm(archetype, float(width_mm)) * float(trace["height_to_width"])
    else:
        return width_mm, height_mm, None
    height = round(height, 1)
    if abs(height - float(height_mm)) <= CONCEPT_HEIGHT_AGREES * float(height_mm):
        return width_mm, height_mm, None
    return width_mm, height, ("the %s's starting size %s x %s mm, confirmed as it opened, gives way to the concept's own "
                              "proportion: %s x %s mm" % (archetype, _mm(width_mm), _mm(height_mm), _mm(width_mm),
                                                          _mm(height)))


def _mm(value) -> str:
    """A length in millimetres as words write it — no trailing zero."""
    return ("%.1f" % float(value)).rstrip("0").rstrip(".")


def _seed_outline_proposal(record: dict, approved_image, spec: dict | None = None, *,
                           named_shape: dict | None = None, traced: dict | None = None) -> tuple:
    """§BH71 PART 1, the owner's goal of 2026-09-28: \"Take the drawn outline and proportions from the chosen concept
    picture itself.\" The traced lid's variant and its height, derived from the width by the picture's aspect, seeded
    as INFERRED proposals for the shape step — a person confirms or changes them, as every proposal. A product
    record's height the trace disagrees with is replaced in the PROPOSAL and said on the trace's record, by value and
    source. Returns (the record, the trace — None for a form the trace does not read)."""
    import copy
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.services import container_contract as cc
    cap_style = ((record.get("fields") or {}).get("cap_style") or {}).get("value")
    trace = trace_concept(record.get("archetype") or "", approved_image, spec, cap_style=cap_style,
                          named_shape=(named_shape or {}).get("kind"))
    # [§BH71 PART 3: the form's own names for its traced lids — its learned ones too, when the caller read them
    # (`services.learned_shapes.traced_variants`); a lid shape the brief names that the form has learned is its variant]
    known = {}
    if _declared.is_known(record.get("archetype")):
        known = _declared.traced_variants_of(record["archetype"])
    if traced is not None:
        known = traced
    if named_shape and named_shape["kind"] in known:
        record = _learned_variant_on(record, known[named_shape["kind"]])
        named_shape = None
    if trace is None:
        if named_shape:                      # [§BH71 PART 3: no picture to trace — the brief's words say it]
            return _unknown_shape_on(record, named_shape, "brief"), None
        return record, None
    unknown = co.unknown_shape(trace, known=known)
    if unknown is not None:
        # [§BH71 PART 3: the concept shows a lid no variant draws — it is said, and no variant is proposed: the
        # record kept the form's FIRST variant, so the shape step offered a rounded rectangle for an oval lid]
        return _unknown_shape_on(record, unknown, "concept"), dict(trace, proposal={})
    if named_shape:
        # [§BH71 PART 3: the brief names a lid no variant draws — its words are said and nothing is squeezed into a
        # variant, whatever the picture's outline reads as (a heart's rim can read as a tilted circle)]
        return _unknown_shape_on(record, named_shape, "brief"), dict(trace, proposal={})
    fields = record.get("fields") or {}
    width = (fields.get("body_width_mm") or {}).get("value") or _declared.nominal_of(record["archetype"])["width_mm"]
    proposal = co.proposal(trace, record["archetype"], width_mm=float(width), traced_variants=known or None)
    if not proposal:
        return record, dict(trace, proposal={})
    out = copy.deepcopy(record)
    replaced = {}
    if proposal.get("variant"):
        out["variant"] = proposal["variant"]
        out["fields"]["variant"] = cc._field(proposal["variant"], source=cc.SRC_INFERRED, verification=cc.INFERRED)
    was = out["fields"].get("body_height_mm") or {}
    if trace.get("view") == "ELEVATION" and was.get("source") == cc.SRC_PRODUCT_RECORD \
            and was.get("value") is not None:
        # a standing product's height in its picture foreshortens with the camera's pitch; the product record's own
        # height is a measurement, so it stands, and the traced outline is drawn to it (a round lid's height is
        # its width by geometry, and replaces the record's — above)
        proposal = {k: v for k, v in proposal.items() if k != "height_mm"}
    if proposal.get("height_mm") is not None:
        if was.get("value") is not None and abs(float(was["value"]) - proposal["height_mm"]) > 0.05:
            replaced["body_height_mm"] = {"was": was["value"], "source": was.get("source")}
        out["fields"]["body_height_mm"] = cc._field(proposal["height_mm"], source=cc.SRC_INFERRED,
                                                   verification=cc.INFERRED)
    out["profile_hash"] = cc.profile_hash(out)
    return out, dict(trace, proposal=dict(proposal, replaced=replaced))


def _read_hero(spec: dict, concept_path, archetype: str) -> dict:
    """§BH71 PART 1: the hero element of a round lid's concept, measured (``concept_outline.trace_hero``) — read on
    the trace this picture's bytes carry on the record, else traced here, locally. Never paid, never written here."""
    import hashlib
    from apps.pipeline.services import concept_outline as co
    try:
        data = open(concept_path, "rb").read() if concept_path else None
    except OSError:
        data = None
    if not data:
        return {"schema_version": co.HERO_SCHEMA, "state": co.HERO_NOT_READ, "reason": co.TRACE_NO_CONCEPT_IMAGE}
    trace = spec.get(co.SCHEMA)
    if trace is None or trace.get("source_sha256") != hashlib.sha256(data).hexdigest():
        shape, box = _reading_shape(spec)
        trace = co.trace_plan(data, reading_shape=shape, surface_box=box)
    return co.trace_hero(data, trace)


FRONT_LABEL_SCHEMA = "container_front_label/1.0"
#: the source ``container_front_label/1.0`` names when the front copy is laid into the front he confirmed
FRONT_LABEL_CONFIRMED = "CONFIRMED_FRONT_ZONE"
#: the forms whose confirmed front zone their front copy is laid into — [his test day finding 3, 2026-09-30] the tube;
#: every other form's proposed zone starts on its shoulder or neck, and moving its copy there is measured form by form
FRONT_ZONE_LABEL_FORMS = ("tube",)
#: the heights across a front zone at which the drawn body is measured to hold it — its top, its foot and between
FRONT_ZONE_HEIGHTS = 9


def _outline_span(silhouette, y0: float, y1: float):
    """The run across the drawn outline that holds at every height from ``y0`` to ``y1`` — ``(left, right)``, the
    largest left crossing and the smallest right one over ``FRONT_ZONE_HEIGHTS`` heights — or None where a height has
    fewer than two crossings. Read off the outline as drawn (`container_concept_fidelity._flatten`), curves sampled."""
    from apps.ire.container_concept_fidelity import _flatten

    polys = _flatten(silhouette)
    left, right = None, None
    for i in range(FRONT_ZONE_HEIGHTS):
        y = y0 + (y1 - y0) * i / (FRONT_ZONE_HEIGHTS - 1)
        xs = [x0 + (y - ya) * (x1 - x0) / (yb - ya)
              for poly in polys for (x0, ya), (x1, yb) in zip(poly, poly[1:]) if (ya - y) * (yb - y) <= 0 and ya != yb]
        if len(xs) < 2:
            return None
        left = min(xs) if left is None else max(left, min(xs))
        right = max(xs) if right is None else min(right, max(xs))
    return left, right


def _profile_with_front_zone(profile, spec: dict, records: list | None = None):
    """[His test day finding 3, 2026-09-30, design 117: a tube's front copy was laid into its drawing's own label box —
    0.78 of its width by 0.55 of its body — and not into the 35 x 99 mm front he had confirmed, though the executor had
    told him everything after the shape step is drawn from those areas; §BH64(b)'s one source for the numbers.] The
    confirmed profile with its label the confirmed FRONT_PRINT_ZONE — on BODY_FRONT, which spans the drawing's height, so
    its numbers are the drawing's own — when the form is one of FRONT_ZONE_LABEL_FORMS and the zone lies on the drawn
    body clear of its closure; held inside the body's outline across its height where the body is narrower than the zone
    (a squeeze tube narrows to its round end), the narrowing said in millimetres; else the profile as it was, the
    reason said. ``container_front_label/1.0`` says which, appended to ``records`` — and dropped on every other path, so
    no reader takes a previous run's."""
    from dataclasses import replace

    from apps.pipeline.targets.container.m3_backbone import build_container_backbone

    def said(record):
        if records is not None:
            records.append(("set", FRONT_LABEL_SCHEMA, dict(record, schema_version=FRONT_LABEL_SCHEMA)))
    if profile.label_zone is not None or profile.archetype not in FRONT_ZONE_LABEL_FORMS:
        if records is not None:
            records.append(("drop", FRONT_LABEL_SCHEMA, None))
        return profile
    zones = (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []
    front = next((z for z in zones if z.get("zone_type") == "FRONT_PRINT_ZONE"
                  and z.get("parent_surface") == "BODY_FRONT"), None)
    if front is None:
        said({"source": "THE_DRAWINGS_OWN_LABEL", "reason": "no confirmed front zone on the body's front"})
        return profile
    x, y, w, h = (float(front[k]) for k in ("x", "y", "width", "height"))
    backbone, _record = build_container_backbone(profile)
    cap_ys = [seg.y for seg in backbone.cap_region if hasattr(seg, "y")]
    clear = not cap_ys or y >= max(cap_ys) or y + h <= min(cap_ys)        # its closure above it, or below it
    # [his answers after 122 was redrawn, 2026-10-08, (2): "measures against MY confirmed print area, not the drawing's
    # own"] the body measured across the zone's safe band — where the copy may print — never its very edge: 122's outline,
    # traced from its concept, closes to a point at the crimped end (y = 0), so a front confirmed from there was refused
    # and the copy laid into the drawing's own label
    inset = float(front["safe_margin_mm"]) if front.get("safe_margin_mm") is not None else 0.0
    inset = inset if 0.0 <= inset and 2.0 * inset < h else 0.0
    span = (_outline_span(backbone.silhouette, y + inset, y + h - inset)
            if clear and y >= 0 and y + h <= profile.height_mm else None)
    if span is None or min(x + w, span[1]) <= max(x, span[0]):
        said({"source": "THE_DRAWINGS_OWN_LABEL", "reason": "the confirmed front zone (%g x %g mm at %g, %g) does not lie "
                                                            "on the drawn body clear of its closure" % (w, h, x, y)})
        return profile
    lx, rx = max(x, span[0]), min(x + w, span[1])
    record = {"source": FRONT_LABEL_CONFIRMED, "zone_id": front.get("zone_id"), "zone_mm": [x, y, w, h],
              "label_mm": [round(lx, 3), y, round(rx - lx, 3), h]}
    if rx - lx < w:
        record["narrowed"] = ("held inside the drawn body, %.1f mm wide where it is narrowest across the zone's height, "
                              "%.1f mm narrower than the zone" % (rx - lx, w - (rx - lx)))
    said(record)
    return replace(profile, label_zone=(lx, y, rx - lx, h))


def _map_colours(spec: dict, image_sha: str | None) -> dict:
    """[His answer after test day finding 3, 2026-09-30, (1): "I don't want hard-coded colors. I would like the system
    to trace the colors from the given image. Not from the written." His check of the map, (2): the cap keeps "the
    darker #CC1E4E the picture shows".] The colours the concept picture's own map gives the drawing — ``{key: (hex,
    what named it)}`` for the body (the upper field), the lower field, the cap (the closure, as measured) and the type's
    ink (the colour most of its type lines print in), and ``"split"``: where the upper field meets the lower, midway
    between the one's foot and the other's top, as a share of the height — from ``container_design_map/1.0`` on record
    when it is a READ map of THIS picture (its sha256 the approved picture's), else ``{}``."""
    from collections import Counter

    from apps.pipeline.services import concept_design_map as dm
    rec = spec.get(dm.SCHEMA) or {}
    if rec.get("state") != dm.MAP_READ or not image_sha or rec.get("source_sha256") != image_sha:
        return {}
    parts = [p for p in rec.get("parts") or [] if p.get("colour")]
    fields = sorted((p for p in parts if p["kind"] == "field"), key=lambda p: p["box"][1])
    out = {}
    if fields:
        out["body"] = (fields[0]["colour"], "the concept picture's map — its part \"%s\"" % fields[0]["name"])
    if len(fields) > 1:
        out["body_lower"] = (fields[1]["colour"], "the concept picture's map — its part \"%s\"" % fields[1]["name"])
        out["split"] = round((fields[0]["box"][3] + fields[1]["box"][1]) / 2.0, 4)
    if rec.get("read") == dm.LID_READ and fields:
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] a lid's ground is the face its plan draws
        out["cap"] = (fields[0]["colour"], "the concept's lid's map — its ground, \"%s\"" % fields[0]["name"])
    cap = next((p for p in parts if p["kind"] == "closure"), None)
    if cap is not None:
        out["cap"] = (cap["colour"], "the concept picture's map — its part \"%s\", as the picture shows it" % cap["name"])
    inks = Counter(p["colour"] for p in parts if p["kind"] == "type")
    if inks:
        out["ink"] = (inks.most_common(1)[0][0], "the concept picture's map — the colour most of its type lines print in")
    return out


def proposal_for(record: dict, spec: dict | None, output) -> list[dict]:
    """[His yes of 2026-09-30, transcribed at 5d23649] The print areas the shape step proposes for ``record`` — from the
    concept's map where one is on record for the design's approved picture (``cc.propose_zones_with_map``: the parts it
    prints, turned as the drawing turns the product from the picture, kept above the cap where the cap stands at the
    foot), else the contract's own proposal, byte for byte."""
    pic = _concept_bytes(getattr(output, "approved_image", None)) if output is not None else None
    return _proposal_from_map(record, spec, pic)


def _proposal_from_map(record: dict, spec: dict | None, pic: bytes | None) -> list[dict]:
    """``proposal_for`` on the picture's own bytes — the door the shape step opens at (``begin_output``, before an
    output exists) and every later one: from the concept's map where it READ this picture, else the contract's own."""
    import hashlib

    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.services import container_contract as cc
    from apps.pipeline.targets.container.silhouettes import STOOD_ON_CLOSURE_FORMS
    spec = spec or {}
    rec = spec.get(dm.SCHEMA) or {}
    if rec.get("state") != dm.MAP_READ or not pic or rec.get("source_sha256") != hashlib.sha256(pic).hexdigest():
        return cc.augment_code_zones(record, cc.propose_zones(record))
    trace = spec.get(co.SCHEMA) or {}
    # [his goal after the pitch page, 2026-10-15, A (3)] where the picture's closure is, by its map — never by which end
    # of the outline is narrower (``closure_up``); its line from the map too where the trace was read the other way up
    pictured_on_closure = closure_at_picture_foot(spec)
    drawn_on_closure = pictured_on_closure and record.get("archetype") in STOOD_ON_CLOSURE_FORMS
    closure = trace.get("closure_share")
    if (trace.get("stood_narrow_end_up") is True) != pictured_on_closure:
        closure = _map_closure_line(spec)
    return cc.propose_zones_with_map(
        record, rec.get("parts"), flip=pictured_on_closure != drawn_on_closure,
        cap_top_share=(1.0 - float(closure)) if drawn_on_closure and closure is not None else None,
        # [his go of 2026-10-02: a wand vial's front proposed from its map] the print below a cap that stands on top
        body_top_share=float(closure) if not drawn_on_closure and closure is not None else None)


def map_read_refused(task, pic: bytes | None) -> str:
    """Why the concept's design map is not read now, in words — the read switched off, no picture, no model key, the
    day's or this design's spending cap reached — or "" where it may be read."""
    from django.conf import settings

    from apps.pipeline.services import cost_ledger
    if not settings.DESIGN_MAP_READ:
        return "the read is switched off (DESIGN_MAP_READ)"
    if not pic:
        return "the approved concept picture could not be opened"
    if not settings.ANTHROPIC_API_KEY:
        return "no model key is set"
    if cost_ledger.daily_budget_exceeded():
        raise cost_ledger.BudgetExceededError("The day's spending cap is reached; no fallback design was produced.")
    try:
        cost_ledger.check_task_budget(task)
    except cost_ledger.BudgetExceededError:
        raise
        return "this design's spending cap is reached"
    return ""


def stop_at_gate_one(aria, approved_image, why: str, parts: list, concept: bool, record: dict | None) -> None:
    """[The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "NO SILENT
    FALLBACK. If the map can't read the concept, STOP and tell me why, with options. Never hand me a different
    design."] The design goes back to Gate 1 with nothing drawn and no output made: its concept no longer the chosen
    one, the reason in words — and each part that would not be drawn — kept on the concept (MAP_STOP_KEY) and said in
    the design's log with his three options (STOP_OPTIONS). ``concept``: the reason is the picture's own, so choosing it
    again stops again — never a missing key or a spending cap. ``record``: the map's read, kept on the picture, so a
    second choice of it pays nothing."""
    from django.utils import timezone

    from apps.pipeline.services import concept_design_map as dm
    prov = dict(approved_image.reference_provenance or {})
    prov[dm.MAP_STOP_KEY] = {"at": timezone.now().isoformat(), "why": why, "parts": parts, "concept": concept,
                             "options": list(dm.STOP_OPTIONS)}
    if record is not None:
        prov[dm.SCHEMA] = record
    approved_image.reference_provenance = prov
    approved_image.is_approved = False
    approved_image.save(update_fields=["reference_provenance", "is_approved"])
    aria.task.status = "awaiting_gate_1"
    aria.task.save()
    named = "; ".join("%s %r: %s" % (p["kind"], p["name"], p["why"]) for p in parts)
    aria.log("ARIA: %s — the chosen concept cannot be drawn from its design map: %s%s. Nothing was drawn; the design is "
             "back at Gate 1 — %s." % (dm.MAP_STOP, why, (" (" + named + ")") if named else "",
                                        ", or ".join(dm.STOP_OPTIONS)),
             payload={"code": dm.MAP_STOP, "image_id": approved_image.pk, "why": why, "parts": parts,
                      "concept": concept}, level="warning")


#: [His test findings on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (7).] the size he
#: confirmed, kept on the output as he confirms it: ``{"dims": the confirmed dimensions, "at": when}``
CONFIRMED_SIZE_KEY = "size_confirmed"


def keep_confirmed_size(output, confirmed: dict) -> None:
    """[His test findings on design 123, (7): "The concept check and drawing check use the confirmed size once known."]
    His confirmed size kept on ``output`` as he confirms it — the size step's values when it opens again
    (``static/js/gates.js``: what he typed before a refusal first, then this)."""
    from django.utils import timezone
    spec = dict(output.spec_sheet or {})
    spec[CONFIRMED_SIZE_KEY] = {"dims": dict(confirmed), "at": timezone.now().isoformat()}
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])


def drawable_verdict(task, record: dict, pic: bytes | None) -> dict:
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "The
    check before I see the concepts and the check at drawing time must agree: a concept shown as drawable must draw. Make
    them one check, and add it to the wiring check with 123's real concepts."]
    The one check, wherever it is made — before the concept is shown (``readable.check``), when it is chosen
    (``map_drawable``) and as it is drawn (``front_checked``'s own trace of the same read): the concept's shapes traced
    from its map, and every part the map names drawn, by the words on record its front takes (a carton's, where the read
    names a carton's face). ``{"shapes", "undrawn" (None where nothing traced), "sources"}``. Read once and kept, the
    same read gives the same verdict at all three: 123's Garden Wrap was read again at approval, beside a retry, and the
    second read named its scalloped band a "band" where the first had named it a "shape". [His test findings on design
    123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at cbdf721), (4): "Text collisions are fixed by spacing or
    shrinking, never refused".] Copy running onto copy is no part it refuses: the front's copy is settled where it is
    drawn, at the size he confirmed (``packaging.settle_front_copy``)."""
    from apps.pipeline.services import concept_design_map as dm
    name, _source = product_name_for(task, task.product)
    sources = type_sources_for(task, name, carton=bool(record.get("face_box_px")))
    shapes = dm.trace_shapes(pic, record, sources=sources)
    if record.get("read") == dm.LID_READ and shapes.get("state") == dm.SHAPES_TRACED:
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3)] a lid's illustration is drawn whole by its
        # art — redrawn flat and traced in colour as the lid is drawn; a refusal there stops the design, by name
        shapes["illustrations"] = [{"part": p["name"], "drawn_by": "the lid's art, redrawn flat and traced in colour"}
                                   for p in record.get("parts") or [] if p.get("kind") == dm.ILLUSTRATION]
    undrawn = dm.undrawn_parts(record, shapes, sources) if shapes.get("state") == dm.SHAPES_TRACED else None
    if undrawn is not None:
        undrawn = undrawn + _ground_painted(shapes)
    return {"shapes": shapes, "undrawn": undrawn, "sources": sources}


def _ground_painted(shapes: dict) -> list:
    """[His second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (2): "a
    concept shown as drawable must draw".] Each traced solid most of which the picture prints in its ground's colour
    (``concept_design_map._ground_share`` over SHAPE_PARAMS["shape_ground_share"]) — drawn, it would fill that ground
    with its ink: Blossom Arch's oval, read in its line art's own pink, traced as the pale ground round its rose."""
    from apps.pipeline.services import concept_design_map as dm
    out = []
    for sh in shapes.get("shapes") or []:
        if "ground_share" in sh and sh["ground_share"] > dm.SHAPE_PARAMS["shape_ground_share"]:
            out.append({"kind": "shape", "name": sh["part"],
                        "why": "most of what it would paint, the picture leaves in its pale ground — drawn, it would "
                               "fill its place with its pink, never the frame and the drawing it shows"})
    return out


def map_drawable(aria, approved_image, record: dict | None, pic: bytes | None) -> dict | None:
    """[The owner's finding on design 119, 2026-10-03.] The concept's design map checked before anything is drawn from
    it: its shapes traced (``concept_design_map.trace_shapes``, $0) and every part it names drawn
    (``undrawn_parts``) — the shapes, to be kept beside the map; or, where the map was not read, did not read, or
    names a part the drawing would not draw, the design stopped at Gate 1 (``stop_at_gate_one``) and None. With the read
    switched off (DESIGN_MAP_READ, as under every test) nothing is checked: ``{}``."""
    from django.conf import settings

    from apps.pipeline.services import concept_design_map as dm
    if not settings.DESIGN_MAP_READ:
        return {}
    if record is None:
        why = map_read_refused(aria.task, pic)
        if not why:
            why = "the read took this design past its spending cap"
        stop_at_gate_one(aria, approved_image, "its design map was not read — " + why, [], False, None)
        return None
    if record.get("state") != dm.MAP_READ:
        stop_at_gate_one(aria, approved_image, "its design map could not be read — %s" % record.get("detail"), [],
                         True, record)
        return None
    verdict = drawable_verdict(aria.task, record, pic)          # [his second blocker on 123, (2)] the one check
    shapes, undrawn = verdict["shapes"], verdict["undrawn"]
    if shapes.get("state") != dm.SHAPES_TRACED:
        stop_at_gate_one(aria, approved_image, "its parts could not be traced — %s" % shapes.get("reason"), [], True,
                         record)
        return None
    if undrawn:
        # [his goal of 2026-10-13, (1): "NO check ever stops a design"] the design goes on; each part it will not draw
        # is said beside Approve where it is drawn (``front_checked``), with what he can do
        aria.log("ARIA: %d of the parts the concept prints would not be drawn as the picture prints them — the design "
                 "goes on, and each is said beside Approve" % len(undrawn), payload={"undrawn": undrawn},
                 level="warning")
    prov = dict(approved_image.reference_provenance or {})
    if dm.MAP_STOP_KEY in prov:
        prov.pop(dm.MAP_STOP_KEY)                      # drawn now: an earlier stop of this concept no longer stands
        approved_image.reference_provenance = prov
        approved_image.save(update_fields=["reference_provenance"])
    return shapes


#: [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3)] kept on the drawing's record: the lid's art as traced
LID_ART_DRAWN_KEY = "container_lid_art_drawn/1.0"


def lid_words(task, archetype: str) -> str:
    """How the lid's redraw names it: a palette's lid where a compact is a palette, else its own form's ("tin's lid") —
    never another product's words."""
    import re
    said = " ".join(str(w) for w in (brief_text(task), getattr(task.product, "product_type", "") if task.product else ""))
    if archetype == "compact" and re.search(r"\bpalette\b", said, re.I):
        return "palette's lid"
    return "%s's lid" % str(archetype).replace("_", " ")


def kept_lid_art_trace(image, archetype, product_mm: tuple | None = None, spec: dict | None = None) -> dict | None:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3)] The lid's art, traced from its flat redraw kept on the
    concept — nothing paid, nothing made; None where no redraw of this concept is kept, its check against the lid's map
    refused it, or it does not trace. [His goal after the pitch page, 2026-10-15, A (3)] nor where it was made for a lid
    of another proportion than the one drawn now (``product_mm``, ``lid_art.kept_lid_art``)."""
    if image is None or not _is_face(archetype):
        return None
    from . import lid_art as _la
    kept = _la.kept_lid_art(image, product_mm)
    if kept is None:
        return None
    # [his goal after the pitch page, B (11)] a redraw its check did not place exactly is drawn all the same, its own
    # lettering under the words left out, what its check saw said beside Approve where it was made (``lid_art_or_stop``)
    traced = _la.trace_art(_la.lid_art_bytes(kept), kept.get("lid_shape") == "round")
    if traced.get("state") != _la.TRACED:
        return None
    from apps.pipeline.services import concept_outline as co
    lid = co.lid_picture(_concept_bytes(image)) if _concept_bytes(image) else {}
    grain = _grain_of(lid["png"], spec) if spec is not None and lid.get("state") == co.LID_STRAIGHTENED else {}
    said = [p for p in ((spec or {}).get("container_design_map/1.0") or {}).get("parts") or []
            if p.get("kind") in ("type", "mark") and p.get("box")]
    return dict(_la.without_words(traced, [p["box"] for p in said], [p.get("colour") for p in said]),
                registration=kept.get("registration"), **grain)


def lid_art_or_stop(aria, output, archetype) -> dict | None:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3) and (4): "NO SILENT FALLBACK, ever: if a part can't
    be drawn, stop and tell me which part and why, with options."] The lid's art where the lid is drawn: its flat redraw
    kept, or made now at the size he confirmed (``lid_art.ensure_lid_art``, paid once), and traced in colour; or the
    design stopped at Gate 1 (``stop_at_gate_one``), the illustration named with why, and None — never the face drawn
    from the form's own layout instead; and the redraw checked against the lid's map (``lid_art.registration``) before
    it is drawn, its misplaced parts named. [His goal of 2026-10-13, (1): "NO check ever stops a design."] A check of
    the art it does not pass — a lid that cannot be cut from the picture, a redraw that does not trace or does not stand
    where the concept does — is said beside Approve with what he can do, and the lid drawn on without its illustration
    (``{}``); only the picture service's failure stops the design at Gate 1 (None)."""
    from apps.pipeline.services import concept_outline as co

    from . import lid_art as _la
    image = output.approved_image
    spec = output.spec_sheet or {}
    pic = _concept_bytes(image)
    lid = co.lid_picture(pic) if pic else {"state": co.LID_NOT_STRAIGHTENED, "reason": "no concept picture"}
    parts = [p for p in (spec.get("container_design_map/1.0") or {}).get("parts") or [] if p.get("kind") == "illustration"]
    named = [{"kind": "illustration", "name": p["name"]} for p in parts] or [{"kind": "illustration", "name": "the lid's art"}]
    if lid["state"] != co.LID_STRAIGHTENED:
        return _lid_art_gone_past(aria, output, "the lid's illustration is not drawn: its lid could not be cut from the "
                                  "concept picture — %s" % lid["reason"])
    confirmed = spec.get("container_profile/1.0") or {}
    size = _profile_size_mm(confirmed, spec)
    made = _la.ensure_lid_art(aria, image, lid, size, lid_words(aria.task, archetype))
    if made.get("state") != _la.REDRAWN:
        stop_at_gate_one(aria, image, "its illustration could not be redrawn flat — %s" % made["why"],
                         [dict(n, why=made["why"]) for n in named], False, None)
        return None
    traced = _la.trace_art(_la.lid_art_bytes(made), lid["shape"] == "round")
    if traced.get("state") != _la.TRACED:
        return _lid_art_gone_past(aria, output, "the lid's illustration is not drawn: its flat redraw could not be "
                                  "traced in colour — %s" % traced["why"])
    # its self-check: the redraw laid on the lid as it is drawn, part by part against the lid's map — a line of type it
    # would print over flowers the concept keeps clear, or an illustration it leaves out, stops the design by name
    held = _la.registration(_la.lid_art_bytes(made), lid["png"],
                            (spec.get("container_design_map/1.0") or {}).get("parts") or [], lid["shape"] == "round")
    prov = dict(image.reference_provenance or {})              # kept with the redraw it checked: drawn only REGISTERED
    prov[_la.LID_ART_KEY] = dict(prov[_la.LID_ART_KEY], registration={k: held[k] for k in ("state", "boxes", "params")})
    image.reference_provenance = prov
    image.save(update_fields=["reference_provenance"])
    said = [p for p in (spec.get("container_design_map/1.0") or {}).get("parts") or []
            if p.get("kind") in ("type", "mark") and p.get("box")]
    if held.get("state") != _la.REGISTERED:
        # [his goal after the pitch page, B (11); the third brand-new brief, 137: its art refused, its lid then not
        # drawn at all and the design sent back to its shape] the art drawn as redrawn, its own lettering under the
        # words left out, and what its check saw said beside Approve — never a lid without its illustration, never a stop
        _lid_art_gone_past(aria, output, "the lid's illustration is drawn as it was redrawn, but its flat redraw does "
                           "not stand exactly where the concept draws it — %s" % held["why"])
    return dict(_la.without_words(traced, [p["box"] for p in said], [p.get("colour") for p in said]),
                registration=held, **_grain_of(lid["png"], spec))


def _grain_of(picture: bytes, spec: dict, top: float = 0.0, foot: float = 1.0) -> dict:
    """[His review of 127-132, 2026-10-15, C (5): "131's sky grain"] ``{"grain": ...}`` — the print's own grain measured
    in ``picture`` where the map reads one (``ire.grain``), the map's boxes taken into the picture's frame (below ``top``
    of the product for a face); {} where it reads none."""
    from apps.ire import grain as _grain

    from . import lid_art as _la
    boxes = []
    for b in _la.textured_boxes((spec.get("container_design_map/1.0") or {}).get("parts")):
        x0, y0, x1, y1 = (float(v) for v in b)
        if y1 > top and y0 < foot:
            boxes.append([x0, (max(y0, top) - top) / (foot - top), x1, (min(y1, foot) - top) / (foot - top)])
    words = []
    for p in (spec.get("container_design_map/1.0") or {}).get("parts") or []:
        if p.get("kind") in ("type", "mark") and p.get("box") and float(p["box"][3]) > top and float(p["box"][1]) < foot:
            x0, y0, x1, y1 = (float(v) for v in p["box"])
            words.append([x0, (max(y0, top) - top) / (foot - top), x1, (min(y1, foot) - top) / (foot - top)])
    got = _grain.measure(picture, boxes, words) if picture and boxes else None
    return {"grain": got} if got else {}


#: [his goal of 2026-10-13, (1)] what he can do about a lid drawn without its illustration
LID_ART_OPTIONS = ("ask for changes to have the illustration redrawn (about $0.25)", "choose another concept at Gate 1")


def _lid_art_gone_past(aria, output, what: str) -> dict:
    """[His goal of 2026-10-13, (1): "NO check ever stops a design ... the design continues and the problem is shown
    beside Approve in plain words."] A check of the lid's art it does not pass: kept on the output, said beside Approve
    with what he can do, and the lid drawn on without its illustration — ``{}``, never a stop and never silent."""
    from apps.ire import self_check as _sc
    from . import lid_art as _la
    spec = dict(output.spec_sheet or {})
    _sc.keep_shown(spec, _la.ART_NOT_TRACED, what, LID_ART_OPTIONS)
    output.spec_sheet = spec
    output.save(update_fields=["spec_sheet"])
    aria.log("ARIA: %s — the design goes on, and it is said beside Approve" % what, level="warning")
    return {}


def _drawn_lid_mm(spec: dict) -> tuple | None:
    """[His goal after the pitch page, 2026-10-15, A (3)] The lid's size as it is drawn now — its confirmed record's —
    or None where the record gives none (the kept art is then not checked against it)."""
    try:
        return _profile_size_mm(spec.get("container_profile/1.0") or {}, spec)
    except ValueError:
        return None


def _profile_size_mm(confirmed: dict, spec: dict) -> tuple:
    """The lid's size he confirmed — its width and its height in plan, as the shape step keeps them (its ``fields``) —
    else the profile's; a ValueError, said, where neither gives it."""
    fields = confirmed.get("fields") or {}
    width = (fields.get("body_width_mm") or {}).get("value")
    height = (fields.get("body_height_mm") or {}).get("value")
    if width is None or height is None:
        legacy = spec.get("container_profile") or {}
        width, height = legacy.get("width_mm"), legacy.get("height_mm")
    if width is None or height is None:
        raise ValueError("the lid's size is not on record — its shape step names no width and height")
    return float(width), float(height)


def front_checked(aria, output, archetype) -> dict | None:
    """[The owner's finding on design 119, 2026-10-03 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 32898c7): "NO SILENT
    FALLBACK ... Never hand me a different design".] The second check, where the design is drawn: the front its map on
    record draws (``_map_front``, its shapes kept), and every part the map names drawn (``undrawn_parts``) —
    ``{"front": …}``; or the design stopped at Gate 1 (``stop_at_gate_one``) and None. With the read switched off (as
    under every test) nothing is checked: ``{"front": the front, or None}``. A design whose map was read before this
    check, or traced under other numbers, is checked here. [His test blocker on design 124, 2026-10-11, (2)-(4)] a face
    form's too — its map read from its lid, its illustration drawn by its art, then its art made and checked
    (``lid_art_or_stop``)."""
    from django.conf import settings

    from apps.pipeline.services import concept_design_map as dm

    from .readable import FROM_TEMPLATE_KEY
    if (getattr(output.approved_image, "reference_provenance", None) or {}).get(FROM_TEMPLATE_KEY):
        return {"front": None}             # [his item 4] his own choice: drawn from the form's own layout, said at Gate 1
    spec = output.spec_sheet or {}
    pic = _map_bytes(output.approved_image, archetype)      # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] a face form's lid
    made: list = []
    name, _source = product_name_for(aria.task, aria.task.product)
    sources = type_sources_for(aria.task, name, carton=bool((spec.get(dm.SCHEMA) or {}).get("face_box_px")))
    front = _map_front(spec, pic, made, sources=sources)
    if made:
        _write_records(spec, made)
        output.spec_sheet = spec
        output.save(update_fields=["spec_sheet"])
    if not settings.DESIGN_MAP_READ:
        return {"front": front}
    if front is None:
        stop_at_gate_one(aria, output.approved_image, "its front could not be drawn from its design map — no map of "
                         "this picture that traces is on record", [], True, None)
        return None
    if _is_face(archetype):
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] a face form's illustration drawn whole by its art
        front = dict(front, shapes=dict(front["shapes"], illustrations=[
            {"part": p["name"], "drawn_by": "the lid's art, redrawn flat and traced in colour"}
            for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("kind") == dm.ILLUSTRATION]))
    undrawn = dm.undrawn_parts(spec.get(dm.SCHEMA) or {}, front["shapes"], sources) + _ground_painted(front["shapes"])
    if undrawn:
        # [his goal of 2026-10-13, (1): "NO check ever stops a design"] each part it will not draw as the picture prints
        # it said beside Approve, by name and why, with what he can do — the design goes on
        from apps.ire import self_check as _sc
        spec = dict(output.spec_sheet or {})
        for part in undrawn:
            _sc.keep_shown(spec, dm.MAP_STOP, "the %s %r is not drawn as the concept prints it — %s"
                           % (part.get("kind", "part"), part.get("name", ""), part.get("why", "")), dm.STOP_OPTIONS)
        output.spec_sheet = spec
        output.save(update_fields=["spec_sheet"])
        aria.log("ARIA: %d of the parts the concept prints are not drawn as it prints them — the design goes on, and each "
                 "is said beside Approve" % len(undrawn), payload={"undrawn": undrawn}, level="warning")
    if _is_face(archetype) and lid_art_or_stop(aria, output, archetype) is None:
        return None                 # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (4)] its art made once every other part draws
    return {"front": front}


def _read_design_map(aria, archetype, approved_image) -> dict | None:
    """[His go of 2026-10-02 (OWNER_BLOCKER_CLEARANCE.md, transcribed at a18911a): "build the map path to run on its own
    for every new design".] The approved concept's design map (``container_design_map/1.0``) for every form — a form
    drawn standing read from its concept as it stands, a face form from its lid stood square ([his test blocker on design
    124, 2026-10-11, (2): "ONE ENGINE"], ``read_lid_parts``) — kept from this design's earlier output where one READ this
    picture (``concept_design_map.held_parts`` / ``held_lid_parts``: nothing paid), else read now (one vision call on
    this design's ledger). A face form whose lid cannot be cut from its picture is UNREAD, said. None, said in the
    design's log, where it is not read: the read switched off, no picture, no key, a spending cap reached, or the read
    itself taking the design past its cap."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import cost_ledger
    # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] a face form's map read from its lid stood square,
    # as a carton's front is — never skipped
    face = _is_face(archetype)
    pic = _map_bytes(approved_image, archetype)
    if face and pic is None and _concept_bytes(approved_image) is not None:
        return {"state": dm.MAP_UNREAD, "detail": "its lid could not be traced in the concept picture"}
    # [the owner's finding on design 119, 2026-10-03] … or on the picture itself, where a stop kept it
    kept = [(approved_image.reference_provenance or {}).get(dm.SCHEMA)]
    kept += [(earlier.spec_sheet or {}).get(dm.SCHEMA)
             for earlier in aria.task.packaging_outputs.exclude(spec_sheet=None).order_by("-pk")]
    for rec in kept:
        held = dm.held_lid_parts(rec, pic) if face else dm.held_parts(rec, pic)
        if held is not None:
            aria.log("ARIA: the concept's design map is on record for this picture — kept, nothing spent")
            return held
    why = map_read_refused(aria.task, pic)
    if why:
        aria.log("ARIA: the concept's design map was not read — %s; the drawing follows the form's own layout and "
                 "says so" % why, level="warning")
        return None
    words = (getattr(approved_image, "reference_provenance", None) or {}).get("container_variation_contract") or {}
    try:
        rec = dm.read_lid_parts(aria.task, pic) if face else dm.read_parts(aria.task, pic, structured=words)
    except cost_ledger.BudgetExceededError:
        raise
        aria.log("ARIA: the concept's design map was read, and the read took this design past its spending cap — its "
                 "parts were not kept; the drawing follows the form's own layout and says so", level="warning")
        return None
    if rec["state"] != dm.MAP_READ:
        aria.log("ARIA: the concept's design map could not be read — %s; nothing spent; the drawing follows the form's "
                 "own layout and says so" % rec["detail"], level="warning")
        return rec
    aria.log("ARIA: the concept's design map read — %d parts named, $%s on this design's ledger%s"
             % (len(rec["parts"]), rec["cost"]["usd"],
                ("; " + "; ".join(rec["problems"][:3])) if rec["problems"] else ""))
    return rec


#: [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5): "list them for me to check"] the pans the drawing
#: shows — each its name, colour, finish and source — kept on the record for the Review Board
TRAY_PANS_KEY = "container_tray_pans/1.0"
#: [his goal of 2026-10-12] the open tray as drawn (palette_tray's record), on the spec where the wiring check reads it
OPEN_TRAY_DRAWN_KEY = "palette_open_tray/1.0"


def _tray_rows(spec: dict) -> list[dict]:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5)] One Review Board row per row of the open tray:
    each pan's shade name, its colour, its finish and where they came from — for him to check."""
    from . import tray_picture as _tp
    rows = []
    for r, row in enumerate(spec.get(TRAY_PANS_KEY) or []):
        rows.append({"label": "Tray, row %d" % (r + 1), "value": "; ".join(
            "%s — %s, %s (%s)" % (p["name"], p["hex"], p["finish"],
                                  "from the tray picture" if p["source"] == _tp.FROM_PICTURE
                                  else "from its name and the concept's palette") for p in row)})
    return rows


def _score_rows(spec: dict) -> list[dict]:
    """[His answer 3 of 2026-10-02: the score "can say 'matches' without my eye".] The Review Board's row for the drawing
    against its concept's full-size trace (``concept_design_map.score_traced``), in words; none where no front was
    drawn from its picture."""
    from apps.pipeline.services import concept_design_map as dm
    score = spec.get(dm.SCORE_TRACED_SCHEMA)
    if not score:
        return []
    if "unread" in score:
        return [{"label": "Against its concept", "value": score["unread"]}]
    bars = "within ΔE %g and %g mm" % (score["bars"]["delta_e"], score["bars"]["mm"])
    if score["matches"]:
        return [{"label": "Against its concept", "value": "MATCHES — all %d parts %s of the concept's full-size trace"
                 % (score["of"], bars)}]
    off = ["%s (%s)" % (r["part"], ", ".join(w for w in (
        ("ΔE %s" % r["delta_e"]) if r["delta_e"] is not None and r["delta_e"] > score["bars"]["delta_e"] else "",
        ("%s mm off" % r["offset_mm"]) if r["offset_mm"] is not None and r["offset_mm"] > score["bars"]["mm"] else "",
        "not placed" if r["offset_mm"] is None else "") if w)) for r in score["parts"] if not r["matches"]]
    return [{"label": "Against its concept", "value": "%d of %d parts %s of the concept's full-size trace; not yet: %s"
             % (score["passed"], score["of"], bars, "; ".join(off))}]


def map_front_colour_sources(map_front: dict | None) -> dict:
    """[His answer after test day finding 3, (1): "trace the colors from the given image".] ``{hex: the record it came
    from}`` for every colour a map front prints — each band's fill and gold edge, each rule's ink, each scattered motif's
    one ink, each traced or typed line's ink — said as the concept picture's map, part by part, so §BH67's printed-colour
    audit reads them; ``{}`` with no map front."""
    if not map_front:
        return {}
    shapes = map_front.get("shapes") or {}
    out: dict = {}

    def said(hx, part, what):
        if hx:
            out.setdefault(str(hx).upper(), "the concept picture's map — its part \"%s\", %s" % (part, what))
    for band in shapes.get("bands") or []:
        said(band.get("fill"), band.get("part"), "its fill as the map measured it")
        said(band.get("edge_ink"), band.get("part"), "its gold edge, measured at full size")
        # [his look at 117 drawn from its map, 2026-10-02] its edge's light and shade and the pale line inside it
        for layer in (band.get("relief") or {}).get("layers") or []:
            said(layer.get("ink"), band.get("part"), "its edge's %s, measured in its band" % layer.get("name"))
        for offset, hx in (band.get("arches") or {}).get("stops") or []:
            said(hx, band.get("part"), "its arches' colour %d%% of the way down them" % round(100 * float(offset)))
    for rule in shapes.get("rules") or []:
        said(rule.get("ink"), rule.get("part"), "its ink, measured at full size")
        said(rule.get("ink_lit"), rule.get("part"), "its lit middle, its lightest gold")
        said(rule.get("ink_shade"), rule.get("part"), "its shade, its darkest gold")
    for scatter in shapes.get("scatters") or []:
        said(scatter.get("ink"), scatter.get("part"), "its one ink, measured over all its shapes' cores")
        said(scatter.get("ink_lit"), scatter.get("part"), "its lit heart, its cores' lightest gold")
        said(scatter.get("ink_shade"), scatter.get("part"), "its rim, its cores' darkest gold")
    for line in shapes.get("types") or []:
        if line.get("words"):
            said(line.get("ink"), line.get("part"), "its ink as the map measured it")
            # [his look at 117 drawn from its map, 2026-10-02] each layer of its lettering, measured on the picture
            for layer in (line.get("lettering_layers") or {}).get("layers") or []:
                said(layer.get("ink"), line.get("part"), "its lettering's %s, measured in its band" % layer.get("name"))
    # [his look at 117 drawn from its map, 2026-10-02: "The foil gold, it's the picture, not the brand"] the mark is
    # drawn from its master in the picture's own gold
    for mark in shapes.get("marks") or []:
        said(mark.get("ink"), mark.get("part"), "its gold ink, the mark drawn from its approved master in it")
    # [his go of 2026-10-08, item 1: "Keep each motif in the picture's own colour"] line art and frames in their own ink,
    # a window in the surface it shows — each measured on the picture at full size
    for line in shapes.get("lines") or []:
        flat = line.get("flat") or {}
        if flat.get("state") == "TRACED" and not line.get("undrawn"):
            # [his test finding on design 122's drawing, 2026-10-08, A and B] drawn from its flat redraw, in that ink
            out.setdefault(str(flat["ink"]).upper(), "the flat redraw of the concept's motif \"%s\" — its ink, read on "
                           "its strokes' cores, evenly lit" % line.get("part"))
            continue
        said(line.get("ink"), line.get("part"), "its line art's ink, the core of its strokes at full size")
    for frame in shapes.get("frames") or []:
        said(frame.get("ink"), frame.get("part"), "its frame's ink, the core of its line at full size")
    for window in shapes.get("windows") or []:
        said(window.get("fill"), window.get("part"), "the surface its window shows, measured inside it")
    # [his last goal before the pitch, 2026-10-16, Step 1 (1): "Never show raw engine lines on a design page ("A fault in
    # the system itself — #E5DDE1:face-art-66" ×100s ...)"] the face's and the lid's art traced from their flat redraws —
    # every region's colour, its sky's, its glow's and its grain's — are the concept's, said so; never unsourced
    for key, what in (("face_art", "the face"), ("lid_art", "the lid")):
        art = map_front.get(key)
        if not isinstance(art, dict) or art.get("state") != "TRACED":
            continue
        for region in art.get("regions") or []:
            said(region.get("fill"), what, "a region of its flat redraw, traced in colour")
        for row in (art.get("sky") or {}).get("rows") or []:
            for hx in row:
                said(hx, what, "its redraw's sky, a corner of its smooth field")
        for band in (art.get("glow") or {}).get("bands") or []:
            said(band.get("hex") if isinstance(band, dict) else None, what, "its light's soft glow")
        for hx in ((art.get("grain") or {}).get("tones") or {}):
            said(hx, what, "its print's grain, a dot of its measured tone")
    return out


def _sets_words(shapes: dict) -> bool:
    """[His rule 1, 2026-10-05] the shapes hold a display or turned line — one whose setting takes the words on record."""
    return any(str(t.get("lettering")).lower() == "display" or t.get("rotation") in (90, -90)
               for t in shapes.get("types") or [])


def _map_front(spec: dict, pic: bytes | None, records: list, sources: list | None = None) -> dict | None:
    """[His answer after test day finding 3, 2026-09-30: each part "the same way, draw it"; the layout "exactly the
    picture".] The front the concept's map draws — ``{"shapes": container_design_shapes/1.0}`` — where a READ map of THIS
    picture is on record and its shapes trace; the shapes traced once and kept beside the map (``records``), traced
    again when the picture or the tracer's parameters are not the ones on record; else None."""
    import hashlib

    from apps.pipeline.services import concept_design_map as dm
    rec = spec.get(dm.SCHEMA) or {}
    if rec.get("state") != dm.MAP_READ or not pic or rec.get("source_sha256") != hashlib.sha256(pic).hexdigest():
        return None
    shapes = spec.get(dm.SHAPES_SCHEMA)
    # traced again whenever the picture or ANY of the tracer's numbers differ from the ones on record — a version alone
    # did not move as the tracer learned the stars, the mark and the type
    # [the owner's finding on design 119, 2026-10-03] compared as the record keeps them: a record's round trip turns
    # the tracer's tuples to lists, and every draw had traced again (a display line's setting, some twenty seconds)
    import json
    # [his rule 1, 2026-10-05] and whenever the words on record a display line is set in are not the ones it was set in
    if not (isinstance(shapes, dict) and shapes.get("source_sha256") == rec["source_sha256"]
            and json.loads(json.dumps(shapes.get("params"))) == json.loads(json.dumps(dm.SHAPE_PARAMS))
            and (not _sets_words(shapes) or shapes.get("sources_sha256") == dm.sources_sha256(sources))):
        shapes = dm.trace_shapes(pic, rec, sources=sources)
        records.append(("set", dm.SHAPES_SCHEMA, shapes))
    if shapes.get("state") != dm.SHAPES_TRACED or not (shapes.get("bands") or shapes.get("rules")
                                                         or shapes.get("scatters") or shapes.get("marks")
                                                         or shapes.get("types") or shapes.get("shapes")):
        return None
    # the map's own name for the motif a band's gold edge draws (117's "cream drip arches with gold contour")
    edge_part = next((p["name"] for p in rec.get("parts") or []
                      if p.get("kind") == "motif" and "drip" in str(p.get("name")).lower()), None)
    return {"shapes": shapes, "edge_part": edge_part}


def _part_boxes(spec: dict) -> dict:
    """The concept map's parts' boxes, by name (fractions of the product)."""
    from apps.pipeline.services import concept_design_map as dm
    return {p["name"]: p["box"] for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("box")}


def _box_mm(box, product_mm) -> tuple:
    """A part's box, clipped to the product, in millimetres (width, height)."""
    x0, y0 = max(0.0, float(box[0])), max(0.0, float(box[1]))
    x1, y1 = min(1.0, float(box[2])), min(1.0, float(box[3]))
    return (x1 - x0) * float(product_mm[0]), (y1 - y0) * float(product_mm[1])


def ensure_flat_motifs(aria, output, spec: dict, product_mm: tuple, parts: list | None = None) -> list:
    """[His test finding on design 122's drawing, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 3e965d0), A1:
    "Never trace motifs from the concept photo. First redraw the motif as a FLAT, front-on, high-resolution artwork ...
    This picture is never printed; it only feeds the tracer."] Each line-art motif of the approved concept redrawn flat
    once — a paid picture, kept on the concept (``flat_motif.SCHEMA``), so the design drawn again pays nothing. Returns
    the drawing's stop for each it could not make, said why — never a trace of the photo in its place. ``parts``: the
    motifs to redraw, by name, where the caller has its front already (a carton's — [his second test blocker on design 123, 2026-10-09 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 2f42010), (4): "a standalone carton gets the same flat redraw before tracing"]);
    else every line-art motif of the container's front."""
    from apps.pipeline.services import flat_motif as fm
    from apps.pipeline.services.cost_ledger import BudgetExceededError
    image = getattr(output, "approved_image", None)
    if parts is None:
        pic = _concept_bytes(image)
        map_front = _map_front(spec, pic, [], sources=type_sources_for(aria.task, drawing_name(aria.task, spec)[0],
                                                                        carton=False))
        if image is None or not map_front:
            return []
        parts = [line["part"] for line in map_front["shapes"].get("lines") or []]
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (2)] and each solid motif its photo's trace breaks
        parts += broken_shape_parts(spec, pic, map_front)
    if image is None:
        return []
    boxes, codes = _part_boxes(spec), []
    for part in parts:
        if fm.kept_flat(image, part, face_mm=product_mm) is not None:     # [his goal of 2026-10-13, (2)] its shape's
            continue
        if fm.kept_flat(image, part) is not None:
            aria.log("ARIA: the flat redraw of '%s' kept on the concept was drawn for another shape of box — it is not "
                     "used, and is redrawn for this one" % part, level="warning")
        if part not in boxes:
            codes.append("%s: %s — the concept's map gives it no place" % (fm.FLAT_REFUSED, part))
            continue
        width_mm, height_mm = _box_mm(boxes[part], product_mm)
        try:
            fm.redraw_flat(aria, image, part, width_mm, height_mm, product_mm)
        except BudgetExceededError as exc:
            raise
            from apps.pipeline.services.cost_ledger import spend_held
            # [his goal of 2026-10-13, (2)] a design whose spending is held at $0 says so, never "past its cap"
            codes.append("%s: %s — %s" % (fm.FLAT_REFUSED, part, "this design's spending is held at $0, so it was not "
                                          "redrawn (about $0.25 to draw)" if spend_held(exc)
                                          else "a redraw would take this design past its spending cap"))
        except Exception as exc:  # noqa: BLE001 — a redraw that fails stops the drawing, said; nothing drawn in its place
            if isinstance(exc, _RescueBudgetError):
                raise
            from apps.pipeline.services.pipeline_errors import is_billing_error
            aria.log("ARIA: the flat redraw of '%s' could not be made — the motif is not drawn" % part, level="warning",
                     payload={"error": "%s: %s" % (type(exc).__name__, str(exc)[:300])})
            codes.append("%s: %s — %s" % (fm.FLAT_REFUSED, part, "the picture service's spending limit is reached — "
                                          "add credits at platform.openai.com, then draw it again"
                                          if is_billing_error(exc) else "the picture service could not make it just now"))
    return codes


def _with_flat_motifs(map_front, spec: dict, image, face_mm=None):
    """[His finding, A2–A4.] ``map_front`` with each line-art motif traced from its flat redraw's OUTLINES
    (``flat_motif.trace_flat``) where one is kept on the concept — ``flat`` on the line; one with none, or one its check
    finds not whole, left ``undrawn``, said — never traced from the concept photo."""
    from apps.pipeline.services import flat_motif as fm
    if not map_front or image is None or not (map_front["shapes"].get("lines") or []):
        return map_front
    boxes, out = _part_boxes(spec), []
    for line in map_front["shapes"]["lines"]:
        record = fm.kept_flat(image, line["part"], face_mm=face_mm)
        if record is None or line["part"] not in boxes:
            other = face_mm is not None and fm.kept_flat(image, line["part"]) is not None
            out.append(dict(line, undrawn="its flat redraw was drawn for another shape of box — redrawn for this one "
                                          "it is drawn (about $0.25)" if other
                            else "no flat redraw of it is kept — the concept photo is never traced"))
            continue
        png = fm.flat_bytes(record)
        traced = fm.trace_flat(png, boxes[line["part"]], record["product_mm"])
        if traced["state"] != fm.TRACED:
            out.append(dict(line, flat=traced, undrawn=traced["why"]))
            continue
        gold = None if traced.get("art") else concept_gold_ink(spec, image, line["part"])
        if gold is not None:
            # [His review of 127, 130, 131 and 132, 2026-10-15, D (11): "126 ... gold rose (not brown/black)"] line art
            # the concept's map names gold is drawn in the concept's own gold — its lit gold, read on the photo — and
            # printed as the gold is, never in the darker brown its flat redraw drew its lines in
            out.append(dict(line, gold=True, flat=dict(traced, ink=gold, ink_from="the concept photo's own gold, lit")))
            continue
        # [His review of 127, 130, 131 and 132, 2026-10-15, C (2)] a motif traced in its colours is also kept as one
        # ink's clean outlines — what the flaps, the sides and the inside repeat it in (``compose._concept_motif``)
        from apps.ire.compose import ROUND_FIELD_SHARE
        bw, bh = _box_mm(boxes[line["part"]], (1.0, 1.0))
        mono = (fm.trace_flat(png, boxes[line["part"]], record["product_mm"], colour=False)
                if traced.get("art") and bw * bh < ROUND_FIELD_SHARE else None)
        out.append(dict(line, flat=traced, **({"flat_mono": mono} if mono and mono["state"] == fm.TRACED else {})))
    return dict(map_front, shapes=dict(map_front["shapes"], lines=one_field_once(out)))


#: [His goal after the pitch page, B (10): 140's front "looks doubled ... far denser than the concept's spaced oat
#: flakes"] two all-over parts redrawn over one box (their boxes overlapping SAME_FIELD_IOU or more) in one set of inks
#: (each within SAME_FIELD_DE, CIEDE76) are ONE field: each part's redraw draws the whole pattern — 140's "oat grains
#: scattered" and its "honey droplets" were each redrawn as the oats AND the drops, and printed one over the other
SAME_FIELD_IOU = 0.8
SAME_FIELD_DE = 12.0


def _drawn_inks(line: dict) -> list:
    flat = line.get("flat") or {}
    return list(flat.get("colours") or []) if flat.get("art") else [flat.get("ink")]


def one_field_once(lines: list) -> list:
    """``lines`` with each all-over field drawn once: a field part (its traced box over ``compose.ROUND_FIELD_SHARE`` of
    the front) whose box and inks are an earlier field's is ``drawn_with`` that one — counted drawn, never drawn again."""
    from apps.ire.compose import ROUND_FIELD_SHARE
    from apps.pipeline.services import flat_motif as fm

    def clipped(b):
        return max(0.0, float(b[0])), max(0.0, float(b[1])), min(1.0, float(b[2])), min(1.0, float(b[3]))

    def area(b):
        return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])
    fields, out = [], []
    for line in lines:
        flat = line.get("flat") or {}
        if line.get("undrawn") or flat.get("state") != fm.TRACED or not flat.get("box") \
                or area(clipped(flat["box"])) < ROUND_FIELD_SHARE:
            out.append(line)
            continue
        box, inks = clipped(flat["box"]), _drawn_inks(line)
        same = None
        for other, obox, oinks in fields:
            inter = area((max(box[0], obox[0]), max(box[1], obox[1]), min(box[2], obox[2]), min(box[3], obox[3])))
            union = area(box) + area(obox) - inter
            if union > 0 and inter / union >= SAME_FIELD_IOU and len(inks) == len(oinks) and all(
                    a and b and fm.delta_e(a, b) <= SAME_FIELD_DE for a, b in zip(inks, oinks)):
                same = other
                break
        if same is None:
            fields.append((line, box, inks))
            out.append(line)
            continue
        out.append(dict(line, drawn_with=same["part"], drawn_with_why=(
            "its flat redraw is %r's own field — the same box, the same inks: the one field is drawn once" % same["part"])))
    return out


#: [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] a line-art motif whose map words name gold (``GOLD_WORDS``,
#: or "foil") is inked in its concept's gold: the pixels of its box the map's own gold test passes
#: (``concept_design_map.is_gold_hex``'s numbers), their brighter half's median — the lit gold, never its shade or the
#: ground between the fine lines; none where fewer than ``GOLD_INK_LEAST`` of the box is gold
GOLD_INK_LEAST = 0.002


def concept_gold_ink(spec: dict, image, part_name: str) -> str | None:
    """The concept photo's own lit gold in the map part ``part_name``'s box, where the map names it gold; else None."""
    import cv2
    import numpy as np
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    rec = spec.get(dm.SCHEMA) or {}
    part = next((p for p in rec.get("parts") or [] if p.get("name") == part_name and p.get("box")), None)
    words = " ".join(str(part.get(k) or "") for k in ("finish", "name")) if part is not None else ""
    if part is None or not (GOLD_WORDS.search(words) or re.search(r"\bfoil\b", words, re.I)):
        return None
    pic = _concept_bytes(image)
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR) if pic else None
    if img is None:
        return None
    lab = fm._lab(img)
    found = fm._product_frame(img, lab, rec.get("product_box_px"))
    if found is None:
        return None
    (px0, py0, px1, py1), _product = found
    bx0, by0, bx1, by1 = (float(v) for v in part["box"])
    x0, x1 = int(px0 + max(0.0, bx0) * (px1 - px0)), int(px0 + min(1.0, bx1) * (px1 - px0))
    y0, y1 = int(py0 + max(0.0, by0) * (py1 - py0)), int(py0 + min(1.0, by1) * (py1 - py0))
    cut, cut_lab = img[y0:y1, x0:x1], lab[y0:y1, x0:x1]
    if not cut.size:
        return None
    P = dm.SHAPE_PARAMS
    L, A, B = cut_lab[..., 0], cut_lab[..., 1], cut_lab[..., 2]
    gold = (B > P["gold_b_min"]) & (B > A + P["gold_b_over_a"]) & (L > P["gold_l_min"])
    if float(gold.mean()) < GOLD_INK_LEAST:
        return None
    lit = gold & (L >= float(np.median(L[gold])))
    b, g, r = (int(v) for v in np.median(cut[lit], axis=0))
    return "#%02X%02X%02X" % (r, g, b)


def flat_motif_codes(map_front) -> list:
    """[His finding, A4: "The self-check fails a motif with broken strokes or fragments."] A motif its flat redraw's check
    finds not whole stops the drawing, said why.
    [His review of 127, 130, 131 and 132, 2026-10-15, C (2): "never printed broken"] and a solid motif whose trace from
    the photo is broken, left out (``_with_flat_shapes``) — said beside Approve, never a stop."""
    from apps.pipeline.services import flat_motif as fm
    shapes = (map_front or {}).get("shapes") or {}
    return ["%s: %s — %s" % (fm.MOTIF_BROKEN, line["part"], line["undrawn"])
            for line in shapes.get("lines") or []
            if line.get("undrawn") and line.get("flat") is not None] + [
        "%s: %s — %s" % (fm.SHAPE_BROKEN, shape["part"], shape["undrawn"])
        for shape in shapes.get("shapes") or [] if shape.get("undrawn")]


def _shape_kinds(spec: dict) -> dict:
    """The concept map's parts' kinds, by name."""
    from apps.pipeline.services import concept_design_map as dm
    return {p["name"]: p["kind"] for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("name")}


def broken_shape_parts(spec: dict, pic: bytes | None, map_front) -> list:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (2): "a motif that can't be traced cleanly ... is redrawn flat
    and traced again"] The solid motifs of the front (the map's "shape" parts) whose trace from the photo is not whole
    (``flat_motif.shape_whole``), by name — each redrawn flat once (``ensure_flat_motifs``)."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    if not map_front or not pic:
        return []
    kinds, record = _shape_kinds(spec), spec.get(dm.SCHEMA) or {}
    out = []
    for shape in (map_front.get("shapes") or {}).get("shapes") or []:
        if kinds.get(shape.get("part")) != "shape":
            continue
        whole = shape["whole"] if "whole" in shape else fm.shape_whole(pic, record, shape)
        if not whole["ok"]:
            out.append(shape["part"])
    return out


#: a closure ends at a step of its outline where one row is narrower than the row above it by this share, within this
#: share of the product's height above where its map box ends
CLOSURE_STEP = {"narrower": 0.08, "reach": 0.06}


#: [his word of 2026-10-17 on 142: "caps keep the concept's gloss" — its red cap on its red body, no colour run to end
#: it, its outline's end read at the cap's own shine (0.062) where its map's box ends at 0.354] where the colour cannot
#: end a closure, its map box's edge stands when the outline's reading lies this far from it (a share of the height)
CLOSURE_BOX_DISAGREE = 0.1


def closure_by_its_box(record: dict, outline_share, refused: dict) -> dict:
    """``closure_edge``'s answer where it refused: the map box's own body-side edge, where the outline's reading
    (``outline_share``) lies CLOSURE_BOX_DISAGREE or more from it; else the refusal as it was."""
    closure = next((p for p in record.get("parts") or [] if p.get("kind") == "closure" and p.get("box")), None)
    if closure is None or outline_share is None:
        return refused
    b0, b1 = float(closure["box"][1]), float(closure["box"][3])
    foot = (b0 + b1) / 2.0 > 0.5
    edge, share, side = b1, b1, "top"
    if foot:
        edge, share, side = b0, 1.0 - b0, "foot"
    if abs(share - float(outline_share)) < CLOSURE_BOX_DISAGREE:
        return refused
    return {"part": closure.get("name"), "edge": round(edge, 5), "side": side,
            "by": "its map box's edge — its colour no different from the body's, its outline's reading %s far from it"
                  % round(float(outline_share), 4)}


def closure_step(profile: list, share: float) -> float:
    """[His last goal before the pitch, 2026-10-16, Step 2] where a closure on top ends by its outline: between the rows
    ``profile`` ([(t, s)], top down) steps in — one CLOSURE_STEP["narrower"] narrower than the row above it — the lowest
    such step within CLOSURE_STEP["reach"] above ``share``; ``share`` itself where its outline takes no such step."""
    found = None
    for (t0, s0), (t1, s1) in zip(profile, profile[1:]):
        if share - CLOSURE_STEP["reach"] <= float(t1) <= share and float(s1) < (1.0 - CLOSURE_STEP["narrower"]) * float(s0):
            found = (float(t0) + float(t1)) / 2.0
    if found is None:
        return share
    return found


def _with_flat_shapes(map_front, spec: dict, image, pic: bytes | None, face_mm=None):
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (2): "NO BROKEN MOTIFS: a motif that can't be traced cleanly
    (132's side and flap flower, which looks like a fidget spinner) is redrawn flat and traced again; never printed
    broken."] ``map_front`` with each solid motif (a "shape" part) measured against the picture it was traced from
    (``whole``: ``flat_motif.shape_whole``). One that is not whole is drawn from its flat redraw kept on the concept —
    traced in its own colours (``flat``) and, for the flaps, the sides and the inside that repeat it in one ink, as one
    ink's clean outlines (``flat_mono``); where none is kept, or its redraw does not trace whole, it is left out
    (``undrawn``), said beside Approve (``flat_motif_codes``) — never printed broken."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    if not map_front or not pic or not (map_front.get("shapes") or {}).get("shapes"):
        return map_front
    kinds, record, boxes, out = _shape_kinds(spec), spec.get(dm.SCHEMA) or {}, _part_boxes(spec), []
    for shape in map_front["shapes"]["shapes"]:
        if kinds.get(shape.get("part")) != "shape":
            out.append(shape)
            continue
        whole = fm.shape_whole(pic, record, shape)
        shape = dict(shape, whole=whole)
        if whole["ok"]:
            out.append(shape)
            continue
        kept = fm.kept_flat(image, shape["part"], face_mm=face_mm) if image is not None else None
        if kept is None or shape["part"] not in boxes:
            out.append(dict(shape, undrawn="%s; no flat redraw of it is kept to trace again — it is left out, never "
                                           "printed broken (about $0.25 to redraw)" % whole["why"]))
            continue
        png = fm.flat_bytes(kept)
        traced = fm.trace_flat(png, boxes[shape["part"]], kept["product_mm"])
        if traced["state"] != fm.TRACED:
            out.append(dict(shape, flat=traced, undrawn="%s, and its flat redraw does not trace whole either: %s — it "
                                                        "is left out" % (whole["why"], traced["why"])))
            continue
        mono = fm.trace_flat(png, boxes[shape["part"]], kept["product_mm"], colour=False)
        out.append(dict(shape, flat=traced, **({"flat_mono": mono} if mono["state"] == fm.TRACED else {}),
                        redrawn="%s — drawn from its flat redraw, traced again" % whole["why"]))
    return dict(map_front, shapes=dict(map_front["shapes"], shapes=out))


#: [His goal after the pitch page, 2026-10-15, A (2): "METALS: gold and chrome are drawn as metallic (highlights and
#: shadows as the concept shows), never flat tan or grey; gold goes on the foil plate."] the words a concept's map gives a
#: closure's finish or name that make it metal; and the words that say it is not, whatever its colour
METAL_WORDS = re.compile(r"\b(gold|golden|chrome|chromed|silver|metal|metallic|mirror|polished|brushed|foil|"
                         r"aluminium|aluminum|brass|copper|bronze|steel|pewter)\b", re.I)
NOT_METAL_WORDS = re.compile(r"\b(matte|matt|soft[- ]touch|frosted|rubber|silicone|wood|wooden|glass|plastic)\b", re.I)
# [His review of 127, 130, 131 and 132, 2026-10-15, D (11); the lead's look at 134: its "brushed bronze collar" drawn
# as chrome] a bronze finish is a warm metal, printed as the gold is
GOLD_WORDS = re.compile(r"\b(gold|golden|brass|bronze)\b", re.I)
#: … and a closure the words do not name, read as metal by its light alone: one whose light runs at least
#: ``METAL_SPREAD_L`` (L*) from its shade to its shine across it, its lit colour gold (``is_gold_hex``) or a near-neutral
#: grey (chroma, a* b*, under ``METAL_NEUTRAL_CHROMA``) — a pale matte cap, shaded, runs far less
METAL_SPREAD_L = 35.0
METAL_NEUTRAL_CHROMA = 8.0


#: [his word of 2026-10-17 on 142] a closure its map's words call glossy, whose light runs at least GLOSS_SPREAD_L
#: (L*) from its shade to its shine, is drawn in that light
GLOSS_WORDS = re.compile(r"\b(gloss|glossy|lacquer|lacquered|shiny|shine|high[- ]shine|patent)\b", re.I)
GLOSS_SPREAD_L = 25.0


def _glossy(part: dict, run: dict) -> bool:
    """Whether a closure part is drawn glossy: its words name a gloss and no matte, and its light runs GLOSS_SPREAD_L."""
    words = " ".join(str(part[k]) for k in ("finish", "name") if part.get(k))
    return (GLOSS_WORDS.search(words) is not None and NOT_METAL_WORDS.search(words) is None
            and float(run["spread"]) >= GLOSS_SPREAD_L)


def _metal_of(part: dict, lit_hex: str, run: dict | None):
    """``("gold" | "chrome", why)`` for a closure part that is metal, else ``(None, why)``: its own words first (the map's
    ``finish`` and ``name``), then its light (``METAL_SPREAD_L``)."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services.flat_motif import _lab_of
    words = " ".join(str(part.get(k) or "") for k in ("finish", "name"))
    gold = bool(GOLD_WORDS.search(words)) or dm.is_gold_hex(lit_hex)
    if METAL_WORDS.search(words):
        return ("gold" if gold else "chrome"), "its concept's own words: \"%s\"" % words.strip()
    if NOT_METAL_WORDS.search(words) or run is None or float(run["spread"]) < METAL_SPREAD_L:
        return None, "its concept's words name no metal and its light runs %s L*" % (
            "unread" if run is None else round(float(run["spread"]), 1))
    _l, a, b = _lab_of(lit_hex)
    if dm.is_gold_hex(lit_hex) or (a * a + b * b) ** 0.5 < METAL_NEUTRAL_CHROMA:
        return ("gold" if gold else "chrome"), "its light runs %.0f L* across it, shade to shine" % float(run["spread"])
    return None, "its light runs %.0f L*, but its colour is neither gold nor a neutral grey" % float(run["spread"])


#: [His review of 127, 130, 131 and 132, 2026-10-15, D (11); the lead's look at 134's flacon] a closure the concept's
#: map reads as two parts — its cap and, under it, its collar — is drawn as both where each part's own box is at least
#: ``CLOSURE_PART_MIN_SHARE`` of the product's height and the two meet within ``CLOSURE_PARTS_MEET`` of it
CLOSURE_PART_MIN_SHARE = 0.02
CLOSURE_PARTS_MEET = 0.03


def closure_parts(rec: dict) -> tuple | None:
    """``(the cap's part, the collar's part)`` — the concept map's two closure parts, top down, where it reads two that
    stand one on the other (``CLOSURE_PART_MIN_SHARE``, ``CLOSURE_PARTS_MEET``); None where it reads one, or more than
    two."""
    parts = sorted((p for p in rec.get("parts") or [] if p.get("kind") == "closure" and p.get("box")),
                   key=lambda p: float(p["box"][1]))
    if len(parts) != 2:
        return None
    (_a, ay0, _b, ay1), (_c, by0, _d, by1) = ([float(v) for v in p["box"]] for p in parts)
    if min(ay1 - ay0, by1 - by0) < CLOSURE_PART_MIN_SHARE or abs(by0 - ay1) > CLOSURE_PARTS_MEET:
        return None
    return parts[0], parts[1]


#: [His review of 127, 130, 131 and 132, 2026-10-15, D (11): droppers, collars "as the concept shows"; the lead's look at
#: 135's tube: its flip-top drawn "a flat yellow rectangle ... no flip-top or hinge detail"] a closure's own seam — the
#: line its lid parts from its base along, a flip-top's split — read on the concept photo: inside the closure's box, its
#: middle ``across`` of its width, the rows between ``band`` of its height (its top face's rim above, its foot below, are
#: its outline's own edges), each row's median change of L* down the picture. A seam is a LINE: a fall and a rise of at
#: least ``least_l`` L* a pixel (and ``over`` times the closure's own median row) within ``line_px`` rows of each other,
#: the line between them at least ``contrast_l`` L* darker than the closure on both sides (a groove, never a shine) —
#: never one edge (a bulb's step on its collar), never where the map sets type or a mark on the closure, never where the
#: outline's own width steps (``step_share``). Drawn as a line across the closure in the line's own colour — at most
#: ``most``. The executor's, new.
SEAM = {"version": 1, "across": 0.8, "band": (0.3, 0.92), "least_l": 0.8, "over": 6.0, "most": 2, "blur_px": 1.5,
        "line_px": 8, "contrast_l": 4.0, "step_share": 0.03}


def closure_seams_of(spec: dict, pic: bytes | None, archetype: str) -> list:
    """``[{"at": share of the product's height in the drawing's frame, "hex", "width_share"}]`` — the seams the concept
    photo shows across its closure (``SEAM``); ``[]`` where it shows none, or the form is drawn in plan."""
    import cv2
    import numpy as np
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    if not pic or not _declared.is_known(archetype) or _declared.drawn_as_of(archetype) == _declared.PLAN:
        return []
    rec = spec.get(dm.SCHEMA) or {}
    closure = next((p for p in rec.get("parts") or [] if p.get("kind") == "closure" and p.get("box")), None)
    img = cv2.imdecode(np.frombuffer(pic, np.uint8), cv2.IMREAD_COLOR)
    if closure is None or img is None:
        return []
    lab = fm._lab(img)
    found = fm._product_frame(img, lab, rec.get("product_box_px"))
    if found is None:
        return []
    P = SEAM
    (px0, py0, px1, py1), _product = found
    bx0, by0, bx1, by1 = (float(v) for v in closure["box"])
    span = float(py1 - py0)
    x0, x1 = px0 + bx0 * (px1 - px0), px0 + bx1 * (px1 - px0)
    cx, half = (x0 + x1) / 2.0, P["across"] * (x1 - x0) / 2.0
    c0, c1 = int(max(0, cx - half)), int(min(img.shape[1], cx + half))
    top, foot = py0 + by0 * span, py0 + by1 * span
    r0 = int(max(1, top + P["band"][0] * (foot - top)))
    r1 = int(min(img.shape[0] - 2, top + P["band"][1] * (foot - top)))
    if c1 - c0 < 8 or r1 - r0 < 5:
        return []
    soft = cv2.GaussianBlur(lab[..., 0], (0, 0), P["blur_px"])
    down = cv2.Sobel(soft, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    rows = np.median(down[r0:r1, c0:c1], axis=1)
    floor = float(np.median(np.median(np.abs(down[int(top):int(foot), c0:c1]), axis=1)))
    least = max(P["least_l"], P["over"] * floor)
    # the shares of the product's height the map sets type or a mark on, and where the traced outline's width steps
    covered = [(float(p["box"][1]), float(p["box"][3])) for p in rec.get("parts") or []
               if p.get("kind") in ("type", "mark") and p.get("box")]
    prof = (spec.get("container_outline_trace/1.0") or {}).get("profile") or []
    stood = (spec.get(OUTLINE_SOURCE_KEY) or {}).get("stands_on_closure") is True
    turned = (spec.get("container_outline_trace/1.0") or {}).get("stood_narrow_end_up") is True

    def steps_at(at):
        t = (1.0 - at) if turned else at
        near = [w for u, w in prof if abs(float(u) - t) <= 0.02]
        return len(near) > 1 and max(near) - min(near) > P["step_share"]
    out = []
    i = 1
    while i < len(rows) - 1 and len(out) < int(P["most"]):
        if abs(float(rows[i])) < least or abs(float(rows[i])) < abs(float(rows[i - 1])) \
                or abs(float(rows[i])) < abs(float(rows[i + 1])):
            i += 1
            continue
        pair = next((j for j in range(i + 1, min(len(rows) - 1, i + int(P["line_px"]) + 1))
                     if float(rows[j]) * float(rows[i]) < 0 and abs(float(rows[j])) >= least), None)
        if pair is None:
            i += 1
            continue
        y = r0 + (i + pair) // 2
        line_l = float(np.median(lab[y, c0:c1, 0]))
        beside = [float(np.median(lab[r0 + i - 2, c0:c1, 0])), float(np.median(lab[r0 + pair + 2, c0:c1, 0]))]
        at = (y - py0) / span
        if min(b - line_l for b in beside) >= P["contrast_l"] and not steps_at(at) \
                and not any(a <= at <= b for a, b in covered):
            b_, g_, r_ = (int(v) for v in np.median(img[y, c0:c1], axis=0))
            out.append({"at": round((1.0 - at) if stood else at, 4), "hex": "#%02X%02X%02X" % (r_, g_, b_),
                        "width_share": round(max(1, pair - i) / span, 4)})
        i = pair + 1
    return out


def closure_looks_of(spec: dict, pic: bytes | None, archetype: str, colors: dict, sources: dict) -> dict | None:
    """[His goal after the pitch page, 2026-10-15, A (2) and A (3)] A standing product's closure as the parts its concept
    shows, each read on its own box of the concept photo — ``{"cap": look, "bulb": look}`` for the parts that are metal,
    each look ``{"metal": "gold" | "chrome", "lightness": [[offset, L*], ...], "why"}`` (``flat_motif.light_run``) — and
    each part's lit colour set in ``colors`` with its source: a dropper's collar (``cap``) and its bulb (``bulb``) each
    from its own part of the closure's box, split where the drawing splits them (``silhouettes.closure_split``), never one
    muddy reading of both. None where nothing is metal; a form drawn in plan (a lid's face) has no closure to read."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import flat_motif as fm
    if not pic or not _declared.is_known(archetype) or _declared.drawn_as_of(archetype) == _declared.PLAN:
        return None
    rec = spec.get(dm.SCHEMA) or {}
    closure = next((p for p in rec.get("parts") or [] if p.get("kind") == "closure" and p.get("box")), None)
    if closure is None:
        return None
    framed = rec.get("product_box_px")
    x0, y0, x1, y1 = (float(v) for v in closure["box"])
    boxes = {"cap": [x0, y0, x1, y1]}
    parts = {"cap": closure}
    source = spec.get(OUTLINE_SOURCE_KEY) or {}
    split = source.get("closure_split_in_picture")
    if split is not None and y0 < float(split) < y1:
        # a dropper's bulb above its collar: each its own box, its own colour
        boxes = {"bulb": [x0, y0, x1, float(split)], "cap": [x0, float(split), x1, y1]}
        parts = {"bulb": closure, "cap": closure}
    two = closure_parts(rec)
    if two is not None and source.get("collar_split") is not None:
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11); the lead's look at 134] a cap on its collar, as the
        # concept's map reads them: each read on its own part's box, in its own words — the drawing splits them there
        boxes = {"cap": [float(v) for v in two[0]["box"]], "collar": [float(v) for v in two[1]["box"]]}
        parts = {"cap": two[0], "collar": two[1]}
    looks = {}
    for key, box in boxes.items():
        lit = fm.lit_face(pic, box, framed)
        if lit is None:
            continue
        if key not in colors or len(boxes) > 1:
            colors[key] = lit
            sources[key] = ("the concept photo's \"%s\" — its %s's own part of the closure, on its evenly lit face"
                            % (parts[key].get("name"), {"cap": ("cap" if "collar" in boxes else "collar")
                                                        if len(boxes) > 1 else "closure",
                                                        "bulb": "bulb", "collar": "collar"}[key]))
        run = fm.light_run(pic, box, framed)
        metal, why = _metal_of(parts[key], colors[key], run)
        if metal is not None and run is not None:
            looks[key] = {"metal": metal, "lightness": run["lightness"], "spread": run["spread"], "why": why,
                          "version": run["version"]}
            sources[key] = sources.get(key, "") + " — drawn as %s, its light as the concept shows it (%s)" % (metal, why)
        elif run is not None and _glossy(parts[key], run):
            # [his word of 2026-10-17 on 142: "caps keep the concept's gloss"] a glossy cap drawn in its own light as
            # the concept shows it — its shine and its shade across it — never one flat colour
            looks[key] = {"metal": None, "gloss": True, "lightness": run["lightness"], "spread": run["spread"],
                          "why": "its concept's own words name a gloss and its light runs %.0f L*" % float(run["spread"]),
                          "version": run["version"]}
            sources[key] = sources.get(key, "") + " — drawn glossy, its light as the concept shows it"
    return looks or None


def _flat_colours(map_front, mapped: dict, pic: bytes | None = None, spec: dict | None = None) -> tuple:
    """[His finding, B: "Measure colours from the flat, evenly lit redraw (not the shaded photo), correct for
    lighting".] ``(colours to draw, the concept's colours to check them against)``, each ``{key: (hex, how it was
    read)}``: the body the flat redraw's evenly lit ground (its largest motif's); the photo's other colours — the lower
    field, the cap, the type — with the photo's lighting taken off by the gain that takes its body to that ground
    (``flat_motif.lit_gain``); and each motif's ink as its flat redraw draws it. Nothing where no motif was redrawn."""
    from apps.pipeline.services import flat_motif as fm
    traced = [line for line in ((map_front or {}).get("shapes") or {}).get("lines") or []
              if (line.get("flat") or {}).get("state") == fm.TRACED and not line.get("undrawn")]
    if not traced or "body" not in mapped:
        # [his goal for the pitch, B (7): "Colours from the flat redraw, never from shadows"] with no motif redrawn —
        # a face drawn from its flat art — the cap is still read on its evenly lit face, never in its shadow
        from apps.pipeline.services import concept_design_map as dm
        closure = next((p for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("kind") == "closure"
                        and p.get("box")), None) if spec is not None else None
        framed = (spec.get(dm.SCHEMA) or {}).get("product_box_px") if spec is not None else None
        lit = fm.lit_face(pic, closure["box"], framed) if (closure is not None and pic and "cap" in mapped) else None
        if lit is None:
            return {}, {}, None
        return ({"cap": (lit, "the concept photo's \"%s\" on its evenly lit face — its shaded side and its shine left "
                              "out" % closure["name"])}, {}, None)
    main = max(traced, key=lambda line: (line["flat"]["box"][2] - line["flat"]["box"][0])
               * (line["flat"]["box"][3] - line["flat"]["box"][1]))
    ground = main["flat"]["ground"]
    gain = fm.lit_gain(mapped["body"][0], ground)
    out = {"body": (ground, "the flat redraw of the concept's motif \"%s\" — its evenly lit ground" % main["part"])}
    for key in ("body_lower", "cap", "ink"):
        if key in mapped:
            out[key] = (fm.corrected(mapped[key][0], gain),
                        "%s — the photo's lighting taken off (the gain that takes its body to the flat redraw's "
                        "ground)" % mapped[key][1])
    # the cap, a solid the photo shades, read on its evenly lit face
    from apps.pipeline.services import concept_design_map as dm
    closure = next((p for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("kind") == "closure"
                    and p.get("box")), None) if spec is not None else None
    # [his goal of 2026-10-13, (10): "colour drift"] the product where the map found it, never where the photo's corners
    # say — a vignetted ground read as the product put 126's cap in its shadow and its gold rose's lines in the black
    framed = (spec.get(dm.SCHEMA) or {}).get("product_box_px") if spec is not None else None
    lit = fm.lit_face(pic, closure["box"], framed) if (closure is not None and pic) else None
    if lit is not None and "cap" in mapped:
        out["cap"] = (lit, "the concept photo's \"%s\" on its evenly lit face — its shaded side and its shine left out"
                      % closure["name"])
    # the concept's own colours, as its photo shows them — the check's other side (``colour_check_of``): the map's reading
    # of its body, its cap and its type, and its lines' own ink read as the flat redraw's is
    refs = {key: (mapped[key][0], "the concept photo — %s" % mapped[key][1]) for key in ("body", "cap", "ink")
            if key in mapped}
    if lit is not None and "cap" in mapped:
        # [his B, as for the drawing] a solid the photo shades is its evenly lit face — never the map's reading over its
        # shade (126's gold cap: #442B09, its shadow), which the check would "repair" the drawing to. [His goal for the
        # pitch, 2026-10-15, B (5): ""PASS" means "matches the concept", never only "the files match each other""] and
        # never the lit face itself, the very colour drawn: a check against its own colour always holds. The cap's
        # colour is judged where it is seen, by the designer's eye against the concept (``designers_eye``)
        refs.pop("cap", None)
    for line in traced:
        if line["flat"].get("art"):
            continue                                   # in its own colours: no one ink to read off the photo
        if line.get("gold") is True and line["flat"].get("ink_from"):
            continue                                   # [his review, D (11)] its ink IS the photo's gold: judged by eye
        ink = fm.photo_line_ink(pic, line["flat"]["box"], mapped["body"][0], framed) if pic else None
        if ink is not None:
            refs["line art: %s" % line["part"]] = (ink, "the concept photo — its lines' own ink, read as the flat "
                                                        "redraw's is")
    return out, refs, gain


#: the colours the concept's map measures on each of its traced parts — each read off the shaded photo
_MAP_MEASURED = (("types", ("ink",)), ("frames", ("ink",)), ("windows", ("fill",)), ("rules", ("ink",)),
                 ("shapes", ("fill", "ink")))


def _lit_off(map_front, gain):
    """[His finding, B: "correct for lighting".] ``map_front`` with every colour its map measured off the photo — each
    type line's ink, each frame's, window's, rule's and shape's — taken through the photo's lighting gain; ``map_front``
    as it is where no motif was redrawn flat (``gain`` None)."""
    from apps.pipeline.services import flat_motif as fm
    if not map_front or gain is None:
        return map_front
    shapes = dict(map_front["shapes"])
    for name, keys in _MAP_MEASURED:
        shapes[name] = [dict(item, **{k: fm.corrected(item[k], gain) for k in keys
                                      if isinstance(item.get(k), str) and str(item[k]).startswith("#")})
                        for item in shapes.get(name) or []]
    return dict(map_front, shapes=shapes)


def colour_check_of(colors: dict, sources: dict, map_front) -> dict:
    """[His finding, B: "check each drawn colour against the concept by eye-level difference (ΔE), failing any that
    drift."] The drawing's colours — its body, its lower field, its cap, its type and each motif's ink — against the
    concept's (``_flat_colours``), by CIEDE2000; a colour his brief or his own turn set is his, never failed against the
    picture (his ruling: his brief's colours win)."""
    from apps.pipeline.services import flat_motif as fm
    refs = (map_front or {}).get("concept_colours") or {}
    drawn = {key: colors[key] for key in ("body", "body_lower", "cap", "ink") if isinstance(colors.get(key), str)}
    for line in ((map_front or {}).get("shapes") or {}).get("lines") or []:
        if (line.get("flat") or {}).get("state") == fm.TRACED and not line.get("undrawn") and not line["flat"].get("art"):
            # an illustrated motif drawn in its own colours has no one ink to check: the designer's eye judges it
            drawn["line art: %s" % line["part"]] = line["flat"]["ink"]
    his = {key for key in drawn if "brief" in str(sources.get(key)) or "your" in str(sources.get(key))}
    record = fm.colour_check({k: v for k, v in drawn.items() if k not in his}, refs)
    for key in sorted(his):
        record["roles"][key] = {"drawn": drawn[key], "state": "HIS_COLOUR", "read": str(sources.get(key))}
    return record


def repair_drifting_colours(doc, colors: dict, map_front, record: dict) -> list:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "A failing check fixes the drawing itself and
    re-checks."] Each colour the colour check finds drifting from the concept's (``record``'s DRIFTS roles) redrawn in
    the concept's own — every fill, stroke, stop and line of the drawing in that colour, the role's colour on record and
    a line art's ink — and said, one line each; nothing where nothing drifts. A colour his brief set is never one."""
    from apps.ire.graph import Color
    swaps, said = {}, []
    for role, row in (record.get("roles") or {}).items():
        if row.get("state") != "DRIFTS" or not row.get("concept"):
            continue
        if role.startswith("line art: "):
            # [his goal for the pitch, 2026-10-15, B (7): "Colours from the flat redraw, never from shadows; a traced
            # motif keeps its colours (126's gold rose came out black/brown)"] a motif's ink is its flat redraw's: the
            # photo's reading of its lines (their darkest share, where its shadow lies) is said beside it, never drawn
            said.append("the %s colour stands ΔE %.1f from the concept photo's reading of its lines (%s) — kept as its "
                        "flat redraw draws it, %s" % (role, row.get("delta_e") or 0.0, row["concept"], row["drawn"]))
            continue
        swaps[str(row["drawn"]).upper()] = str(row["concept"]).upper()
        if role in colors:
            colors[role] = row["concept"]
        said.append("the %s colour drifted from the concept's (ΔE %.1f) — redrawn in the concept's own, %s"
                    % (role, row.get("delta_e") or 0.0, row["concept"]))
    if not swaps:
        return []

    def swap(color):
        if color is not None and color.to_hex().upper() in swaps:
            new = Color.from_hex(swaps[color.to_hex().upper()])
            color.r, color.g, color.b, color.cmyk = new.r, new.g, new.b, None

    roots = [doc.root] + ([doc.inside] if getattr(doc, "inside", None) is not None else [])
    for root in roots:
        stack = [root]
        while stack:
            node = stack.pop()
            for attr in ("fill", "stroke"):
                paint = getattr(node, attr, None)
                if paint is None:
                    continue
                swap(getattr(paint, "color", None))
                for stop in getattr(paint, "stops", None) or []:
                    swap(stop.color)
            swap(getattr(node, "color", None))
            stack.extend(getattr(node, "children", None) or [])
    return said


def arabic_name_for(task) -> tuple:
    """``(the product's Arabic name in his words, where it is on record)`` — the product record's Arabic name, else his
    brief's "Arabic name:" line; ``(None, None)`` where neither gives one. [His review of 119, 2026-10-05, point 6:
    "where my brief gives the Arabic, use my words exactly (with the shadda)."]"""
    from apps.pipeline.services import concept_design_map as dm
    product = getattr(task, "product", None)
    name_ar = " ".join(str(getattr(product, "name_ar", "") or "").split()) if product is not None else ""
    if name_ar:
        return name_ar, "the product record's Arabic name"
    for text, origin in dm.brief_line_fields(brief_text(task)):
        if origin == "the brief's Arabic name":
            return text, origin
    return None, None


def type_sources_for(task, product_name: str, carton: bool | None = None) -> list:
    """[His answer after test day finding 3; the executor's proposal recorded with it: the small copy "typed from the
    brief".] The sources on record a front's type may take its words from, each said: the product's name, its Arabic
    name where the product record holds one, each phrase of the brief's front copy, and [his second look at 117 and his
    rules of 2026-10-02] the brief's own Arabic name and scent line (``brief_line_fields``)."""
    from apps.pipeline.services import concept_design_map as dm
    out = [(product_name, "the product's name on the record")] if product_name else []
    product = getattr(task, "product", None)
    name_ar = (getattr(product, "name_ar", "") or "").strip() if product is not None else ""
    if name_ar:
        out.append((name_ar, "the product record's Arabic name"))
    brief = brief_text(task)
    # [his rules 1 and 2 for 119 and every design, 2026-10-05: "My brief's words win over the picture's text"; "Keep the
    # '·' between 'LIP GLOSS' and the Arabic"] every line of the brief that gives the piece its words — a carton its
    # "Carton front:" and its "Carton side:" (a picture may print a side's phrase on its front), a container its "Vial
    # copy:" (``carton``: None, every one) — before the brief's one-line fields, as before; and each phrase setting
    # English beside Arabic followed by its two halves, the separator kept on the English one
    fields = [f for f in dm.brief_front_fields(brief)
              if carton is None or (f[1] == "the brief's carton front") == bool(carton)]
    sides = [(p, "the brief's side copy") for p in dm.brief_side_copy(brief)] if carton is not False else []
    # [his answers after the fixes for design 122, 2026-10-08, (2): "the drawing must always print my brief's size"] his
    # brief's size, wherever his brief states it, before the product record's net content (§BH67(c)2) — the first size
    # among them is the one a size line takes (``concept_design_map.type_sources``)
    size = dm.brief_size(brief)
    record_size = (getattr(product, "net_weight", "") or "").strip() if product is not None else ""
    phrases = (out + [(p, "the brief's front copy") for p in dm.brief_front_copy(brief)] + fields + sides
               + [field for field in dm.brief_line_fields(brief) if field[0] != name_ar])
    said = {text for text, _origin in phrases}
    phrases += ([size] if size and size[0] not in said else []) + (
        [(record_size, "the product record's net content")] if record_size and record_size not in said else [])
    return [entry for text, origin in phrases
            for entry in [(text, origin)] + [(half, origin) for half in dm.script_halves(text)]]


def _body_fields(spec: dict, structured: dict | None, palette, archetype) -> tuple:
    """[His test day finding 3, 2026-09-30] (where the concept's upper colour field meets its lower, as a share of the
    drawing's height, and the two fields) — the fields its `color_field_signature` names (`colour_sources.colour_fields`)
    split where the concept picture's colour changes down the product's axis (`colour_sources.field_split`, on the trace
    on record, turned as the drawing turns it); (None, []) when the words name no two fields, the picture's outline was
    not traced, or its colours give neither field a run of its own."""
    from apps.pipeline.services import concept_outline as co
    from apps.pipeline.targets.container import colour_sources as _cs
    from apps.pipeline.targets.container.silhouettes import STOOD_ON_CLOSURE_FORMS
    fields = _cs.colour_fields(structured, palette)
    trace = spec.get(co.SCHEMA) or {}
    if not fields or trace.get("state") != co.TRACED_FROM_CONCEPT or not trace.get("axis_colours"):
        return None, []
    # [his goal after the pitch page, 2026-10-15, A (3)] the trace's own frame turned to the drawing's wherever the two
    # differ: a tube drawn on its cap as pictured, and a product the trace stood on its closure that its map shows closure
    # up (``closure_up``)
    drawn_as_pictured = not closure_at_picture_foot(spec) or archetype in STOOD_ON_CLOSURE_FORMS
    traced_as_pictured = trace.get("stood_narrow_end_up") is not True
    turned = drawn_as_pictured != traced_as_pictured and trace.get("closure_share") is not None
    split = _cs.field_split(trace["axis_colours"], [row[0] for row in trace.get("profile") or []], fields[0][0],
                            fields[1][0], closure_share=trace.get("closure_share"), turned=turned)
    return (split, fields) if split is not None else (None, [])


FRONT_FIELDS_SCHEMA = "container_front_fields/1.0"
#: [his test day finding 3, 2026-09-30] the layout words that place the mark in the upper field and the name in the lower
_UPPER_MARK = re.compile(r"(?<![a-z])(upper|top)(?![a-z]).*(?<![a-z])(logo|mark|lockup)(?![a-z])"
                         r"|(?<![a-z])(logo|mark|lockup)(?![a-z]).*(?<![a-z])(upper|top)(?![a-z])")
_LOWER_NAME = re.compile(r"(?<![a-z])(lower|bottom)(?![a-z]).*(?<![a-z])name(?![a-z])"
                         r"|(?<![a-z])name(?![a-z]).*(?<![a-z])(lower|bottom)(?![a-z])")


def _front_fields(structured: dict | None) -> list[str]:
    """[His test day finding 3, 2026-09-30, design 117: his concept sets its logo on the hot-pink field and its name on
    the soft-pink one, and the drawing set the logo on the line between them with the name under it] The concept's own
    words that place the mark in the upper field and the name in the lower — one clause of its
    `decoration_zone_signature` or `composition_signature` for each ("upper zone reserved for logo", "lower zone for
    name and descriptor stack") — or [] unless both are said."""
    mark = name = None
    for key in ("decoration_zone_signature", "composition_signature"):
        for clause in re.split(r"[,;]", str((structured or {}).get(key) or "")):
            low = clause.lower()
            if mark is None and _UPPER_MARK.search(low):
                mark = clause.strip()
            if name is None and _LOWER_NAME.search(low):
                name = clause.strip()
    return [mark, name] if mark and name else []


def _profile_with_outline(profile, spec: dict, output, records: list | None = None, keep_m3: bool = False):
    """§BH71 PART 1 — ONE DERIVATION, BOTH DRAWING CALLERS (``reconstruct_container`` and ``face_form_inputs``): the
    confirmed profile with the outline traced from its approved concept, attached only when the shape confirmed is
    the shape the concept shows, and the drawing's record of which drew — ``container_outline_source/1.0``,
    TRACED_FROM_CONCEPT or TEMPLATE_FALLBACK with the reason by name — appended to ``records`` for the caller to
    write. A trace on record for these bytes is read; else it is traced here, locally, for nothing — [his test day
    finding 3, 2026-09-30: design 117's record was a fallback made before the trace could read it, and was read again
    at every draw] and so is a form drawn in elevation whose trace on record was made under other trace parameters;
    a trace made here is written beside the drawing."""
    import hashlib
    from dataclasses import replace
    from apps.pipeline.services import concept_outline as co
    # [his goal for the pitch, 2026-10-15, B (9): "Shapes from the concept, not crude templates (126's bottle)"] a dropper
    # bottle is traced from its concept like every bottle — his Q8's M3 drawing turned for its silhouette
    # … save a dropper whose geometry he confirmed (``keep_m3``), or one drawn with no concept map read (the frosted M3
    # sheet of 2C-2E, drawn from no map): the M3 drawing §BH49 chose for it stands
    from apps.pipeline.services import concept_design_map as _dmr
    if profile.cap_style == "dropper" and (spec.get(_dmr.SCHEMA) or {}).get("state") != _dmr.MAP_READ:
        keep_m3 = True
    if not _declared.is_known(profile.archetype) or (keep_m3 and profile.cap_style == "dropper") \
            or (_declared.drawn_as_of(profile.archetype) == _declared.PLAN
                and not _declared.traced_variants_of(profile.archetype)):
        # "the design says when the fallback was used" — on every form, not only where a trace ran
        if records is not None:
            detail = "a form the declaration does not know"
            if keep_m3 and profile.cap_style == "dropper":
                detail = "the dropper keeps the M3 drawing chosen at §BH49"
            elif _declared.is_known(profile.archetype):
                detail = "a flat %s has no lid to trace — its template draws it" % profile.archetype
            records.append(("set", OUTLINE_SOURCE_KEY, dict(co.not_traced(profile.archetype, profile.variant,
                                                                          detail=detail),
                                                            schema_version=OUTLINE_SOURCE_KEY)))
        return profile
    image = getattr(output, "approved_image", None)
    data = _concept_bytes(image)
    sha = hashlib.sha256(data).hexdigest() if data else None
    trace = spec.get(co.SCHEMA)
    view = _declared.drawn_as_of(profile.archetype)
    if data is not None and (trace is None or trace.get("source_sha256") != sha or trace.get("view") != view
                             or (view == _declared.ELEVATION
                                 and (trace.get("params") or {}).get("version") != co.TRACE_PARAMS["version"])):
        trace = trace_concept(profile.archetype, image, spec, cap_style=profile.cap_style)
        if records is not None and trace is not None:
            records.append(("set", co.SCHEMA, trace))
    known = _declared.traced_variants_of(profile.archetype)
    from apps.pipeline.services import learned_shapes
    if learned_shapes.kind_of(profile.variant) is not None:
        # [§BH71 PART 3: a learned lid — its trace is drawn when the concept shows it; its record must be there]
        if learned_shapes.find(profile.archetype, profile.variant) is None:
            raise ValueError("%s: the %s's learned shape %r is not on record — it cannot be drawn" % (
                learned_shapes.LEARNED_SHAPE_MISSING, profile.archetype, profile.variant))
        known = learned_shapes.traced_variants(profile.archetype)
    outline, source = co.outline_for(trace if data is not None else None, archetype=profile.archetype,
                                     variant=profile.variant, image_sha256=sha, traced_variants=known or None)
    if outline is not None and outline.get("kind") == co.PROFILE and profile.width_mm and profile.height_mm:
        # the confirmed size the outline is drawn to, beside the one the picture's own proportion gives the width
        from apps.pipeline.targets.container.silhouettes import drawn_width_mm
        _drawn_w = drawn_width_mm(profile.archetype, profile.width_mm)      # [his answer after finding 3, (4)]
        source = dict(source, drawn_mm=[round(_drawn_w, 2), profile.height_mm],
                      picture_height_mm=round(_drawn_w * float(outline["height_to_width"]), 1))
        # [his answer after test day finding 3: the layout "exactly the picture"; his check of the map: the cap as the
        # picture shows it] the closure meets the body where the picture's closure colour begins, where its map is on
        # record — turned into the outline's own frame, which stands the product narrow end up
        from apps.pipeline.services import concept_design_map as _dm
        _rec = spec.get(_dm.SCHEMA) or {}
        if data is not None and _rec.get("state") == _dm.MAP_READ and _rec.get("source_sha256") == sha:
            _edge = _dm.closure_edge(data, _rec)
            if "refused" in _edge:
                _edge = closure_by_its_box(_rec, outline.get("closure_share"), _edge)
            if "refused" not in _edge:
                # [His goal after the pitch page, 2026-10-15, A (3)] the outline stood closure up by where the picture's
                # own closure is, never by which end is narrower: a jar with a tapered foot was stood on its lid
                outline, _turned = closure_up(outline, _edge["side"])
                if _turned:
                    source = dict(source, stands_on_closure=outline["stands_on_closure"], turned_closure_up=_turned)
                _share = (1.0 - _edge["edge"]) if _edge["side"] == "foot" else _edge["edge"]
                if "map box's edge" in str(_edge.get("by")):
                    # [his last goal before the pitch, Step 2, 138: its black cap drawn down over its plum neck, narrow and
                    # notched] where its colour cannot say where the closure ends, its outline can: the step where the
                    # traced width narrows just above the box's edge
                    _share = closure_step(outline["profile"], _share)
                source = dict(source, closure_share=round(_share, 4), closure_by=(
                    "the concept picture's map: where its closure's own colour begins, measured at full size — the "
                    "outline's narrowing read %s" % outline.get("closure_share")))
                outline = dict(outline, closure_share=round(_share, 4))
    if outline is not None and outline.get("kind") == co.PROFILE and profile.cap_style == "dropper":
        # [His goal after the pitch page, 2026-10-15, A (3): "128's grey-block dropper"] where its bulb meets its collar,
        # as the drawing splits them (``silhouettes``) — so each is coloured from its own part of the picture
        from apps.pipeline.targets.container import silhouettes as _sil
        _prof, _c, _said = _sil.closure_shaped(outline["profile"], outline["closure_share"], profile.cap_style,
                                               profile.archetype)
        _split = _sil.closure_split(_prof, _c)
        if _split is not None:
            source = dict(source, closure_split=_split, closure_split_in_picture=round(
                (1.0 - _split) if outline.get("stands_on_closure") is True else _split, 4))
    elif outline is not None and outline.get("kind") == co.PROFILE and data is not None:
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11); the lead's look at 134's flacon: its gold collar
        # drawn in its plum cap's colour] a closure its concept's map reads as a cap on its collar: split where the
        # collar's own part begins — in the outline's own frame, which may stand it closure up — inside the closure
        from apps.pipeline.services import concept_design_map as _dm2
        _rec2 = spec.get(_dm2.SCHEMA) or {}
        _two = closure_parts(_rec2) if _rec2.get("source_sha256") == sha else None
        if _two is not None:
            _at = float(_two[1]["box"][1])
            _at = (1.0 - _at) if outline.get("stands_on_closure") is True else _at
            if 0.0 < _at < float(outline["closure_share"]):
                outline = dict(outline, collar_split=round(_at, 4))
                source = dict(source, collar_split=round(_at, 4), collar_by=(
                    "the concept picture's map: its \"%s\" on its \"%s\"" % (_two[0].get("name"), _two[1].get("name"))))
    if outline is not None and outline.get("kind") in _PLAN_RECT_KINDS and data is not None and trace is not None:
        # [His goal after the pitch page, A (3): "131 ... with a cream border"] the rim its concept shows round the lid's
        # art, read on the lid stood square — drawn as its rim, in its colour (``silhouettes.lid_border_region``)
        _lid = co.lid_picture(data, trace)
        _rim = co.lid_border(_lid["png"]) if _lid.get("state") == co.LID_STRAIGHTENED and _lid["shape"] == "rect" \
            else None
        if _rim is not None:
            outline = dict(outline, border=_rim)
            source = dict(source, border=_rim)
    if records is not None:
        records.append(("set", OUTLINE_SOURCE_KEY, dict(source, schema_version=OUTLINE_SOURCE_KEY)))
    return replace(profile, outline=outline) if outline else profile


def closure_at_picture_foot(spec: dict) -> bool:
    """[His goal after the pitch page, 2026-10-15, A (3)] Whether the concept pictures its product standing on its
    closure: where its map names the closure, by where that closure is (its box's middle below the product's); else as
    the elevation trace stood it (narrow end up)."""
    from apps.pipeline.services import concept_design_map as dm
    from apps.pipeline.services import concept_outline as co
    rec = spec.get(dm.SCHEMA) or {}
    closure = next((p for p in rec.get("parts") or [] if p.get("kind") == "closure" and p.get("box")), None)
    if rec.get("state") == dm.MAP_READ and closure is not None:
        return (float(closure["box"][1]) + float(closure["box"][3])) / 2.0 > 0.5
    return (spec.get(co.SCHEMA) or {}).get("stood_narrow_end_up") is True


def _map_closure_line(spec: dict):
    """The line the map's closure meets its body at, as a share of the height from the closure's end — its box's far
    edge; None where the map names no closure."""
    from apps.pipeline.services import concept_design_map as dm
    closure = next((p for p in (spec.get(dm.SCHEMA) or {}).get("parts") or [] if p.get("kind") == "closure"
                    and p.get("box")), None)
    if closure is None:
        return None
    y0, y1 = float(closure["box"][1]), float(closure["box"][3])
    return round(1.0 - y0, 4) if (y0 + y1) / 2.0 > 0.5 else round(y1, 4)


#: [His goal after the pitch page, 2026-10-15, A (3)] the plan kinds whose lid is a rectangle its rim is read round
_PLAN_RECT_KINDS = ("square", "rounded_rect")


def closure_up(outline: dict, side: str) -> tuple:
    """[His goal after the pitch page, 2026-10-15, A (3): "SHAPES AND PROPORTIONS come from the concept"] ``(the
    elevation outline stood closure up, why or None)``. The trace stands every picture narrow end up
    (``concept_outline._read_standing``) and says so (``stands_on_closure``); the map knows where the picture's closure
    is (``closure_edge``'s ``side``, the picture's top or its foot). Where the two disagree — a jar narrower at its foot
    than at its lid, read as standing on its lid — the outline is turned end over end back, its closure up, and
    ``stands_on_closure`` says what the picture shows: True only where the closure is at the picture's foot."""
    flipped = outline.get("stands_on_closure") is True
    on_closure = side == "foot"
    if flipped == on_closure:
        return outline, None
    turned = [[round(1.0 - float(t), 4), s] for t, s in reversed(outline.get("profile") or [])]
    return dict(outline, profile=turned, stands_on_closure=on_closure), (
        "the picture's closure is at its %s, so the outline is stood with its closure up — not by its narrower end"
        % ("foot" if on_closure else "top"))


def round_lid_problems(doc) -> list[str]:
    """§BH71 PART 1: what a round lid's face leaves outside the lid's circle at the name step chosen — where the
    concept's own arrangement puts it, outside at every step — as containment problems, by name
    (``compose_container._outside_the_round_lid``). [] for every other lid."""
    from apps.pipeline.services import container_projection as cp
    face = (doc.metadata.get("concept_front") or {}).get("face") or {}
    return ["%s: the %s leaves the round lid by %.2f mm" % (cp.DECORATION_OUTSIDE_ZONE, gone["element"],
                                                           gone["beyond_mm"])
            for gone in (face.get("round_lid") or {}).get("outside") or []] + [
        # [§BH71 PART 3: and a learned oval lid's ellipse]
        "%s: the %s leaves the oval lid by %.2f mm" % (cp.DECORATION_OUTSIDE_ZONE, gone["element"], gone["beyond_mm"])
        for gone in (face.get("oval_lid") or {}).get("outside") or []]


#: §BH71 PART 1: which drew the container's outline, and why — written beside the drawing on every run
OUTLINE_SOURCE_KEY = "container_outline_source/1.0"


def _selection_rows(task) -> list[dict]:
    """2C-2D §8: the human Gate-1 selection, the selected-concept visual
    contract, the concept-only/missing-facts split, the persisted warnings
    and the next required human action — read-only surfacing of the
    project-level records. Empty for tasks without them."""
    from apps.pipeline.services import selected_concept_contract as scc
    project = getattr(task, "project", None)
    meta = (project.metadata or {}) if project else {}
    sel = meta.get(scc.SELECTION_META_KEY)
    contract = meta.get(scc.META_KEY)
    rows: list[dict] = []
    if isinstance(sel, dict):
        s = sel.get("selected") or {}
        rows.append({"label": "Gate-1 selection",
                     "value": (f'{sel.get("decision")} — image '
                               f'#{s.get("image_id")} '
                               f'({s.get("variation_identity")}) by '
                               f'{sel.get("decided_by")}')})
        alts = "; ".join(f'#{u.get("image_id")} {u.get("variation_identity")}'
                         for u in (sel.get("unselected") or []))
        if alts:
            rows.append({"label": "Unselected alternatives",
                         "value": f"{alts} — preserved in project history"})
        rows.append({"label": "Selection record hash",
                     "value": str(sel.get("record_hash", ""))[:12]})
    event = meta.get("gate1_concept_selection_event")
    if isinstance(event, dict):
        rows.append({"label": "Signed selection event",
                     "value": (f'{event.get("action")} · seq '
                               f'#{event.get("sequence_number")} · '
                               f'{str(event.get("event_id",""))[:12]} · '
                               f'epoch {event.get("signing_epoch")}')})
        rows.append({"label": "Decision lineage",
                     "value": str(event.get("lineage", ""))})
    if isinstance(contract, dict):
        rows.append({"label": "Visual contract",
                     "value": (f'{contract.get("schema_version")} · '
                               f'{str(contract.get("contract_hash",""))[:12]}')})
        rows.append({"label": "Concept-only facts",
                     "value": ("~30 ml capacity (concept-only) · frosted "
                               "translucent dusty-rose glass · pipette "
                               "dropper, rose-gold collar, dark-plum bulb · "
                               "tall STE carton family")})
        rows.append({"label": "Missing production facts",
                     "value": ("no confirmed physical dimensions · no "
                               "manufacturer evidence · collar dimensions "
                               "absent · capacity, base thickness, frost "
                               "intensity unconfirmed")})
        for i, warning in enumerate(scc.all_warnings(project), 1):
            rows.append({"label": f"Visual-quality warning {i}",
                         "value": str(warning)})
    if rows and task.status == "awaiting_container_profile":
        rows.append({"label": "Next required human action",
                     "value": ("CONFIRM PRODUCT CONTAINER PROFILE AND "
                               "DECORATION ZONES")})
    elif rows and task.status == "awaiting_gate_2":
        rows.append({"label": "Next required human action",
                     "value": "HUMAN GATE-2 VISUAL REVIEW"})
    return rows


def _reconstruction_2c2e_rows(spec: dict) -> list[dict]:
    """2C-2E §16: material-object breakdown, measured concept-fidelity
    findings and production-readiness blockers — read-only surfacing."""
    rows: list[dict] = []
    mats = spec.get("container_material_objects/1.0")
    if isinstance(mats, dict):
        printing = [o["name"] for o in mats.get("objects", [])
                    if o.get("printing")]
        viz = mats.get("nonprinting_visualization") or []
        rows.append({"label": "Material objects",
                     "value": f'{len(mats.get("objects", []))} independent '
                              f'({", ".join(viz)} nonprinting '
                              "visualization)" if viz else
                              f'{len(printing)} printing objects'})
    cf = spec.get("container_concept_fidelity/1.0")
    if isinstance(cf, dict):
        measured = [a for a in cf.get("axes", [])
                    if a.get("state") != "UNMEASURED"]
        rows.append({"label": "Concept fidelity (measured)",
                     "value": (f'{len(measured)} axes measured · '
                               + (("FAILED: "
                                   + ", ".join(cf.get("failures")))
                                  if cf.get("failures") else "all passed"))})
    codes = spec.get("container_production_readiness_codes") or {}
    flat = [c for group in codes.values() for c in (group or [])]
    if flat:
        rows.append({"label": "Production-readiness blockers",
                     "value": f'{len(flat)}: ' + " · ".join(flat[:8])
                              + (" …" if len(flat) > 8 else "")
                              + " — as persisted by the run (§BH50(g)(4): the reader's verdict, derived now, is its own row)"})
    # §BH50(f)(5): the acceptance blockers the persisted codes do not carry —
    # derived at read time, so his board does not under-report them
    from apps.ire.container_production_readiness import fidelity_unmeasured
    derived = fidelity_unmeasured(spec)
    if derived["codes"]:
        # [§BH71 (0a): it read "(block acceptance)" — an unmeasured axis is a warning beside Approve since]
        rows.append({"label": "Unmeasured fidelity axes (a warning beside Approve)",
                     "value": f'{len(derived["codes"])}: '
                              + " · ".join(derived["codes"][:8])
                              + (" …" if len(derived["codes"]) > 8 else "")
                              + " — derived at read time; not measured, and never marked passed "
                                "(§BH50(f)(5), superseded in part by §BH71 (0a))"})
    # §BH50(f)(2): one row per piece of copy nobody has written, so he can
    # supply the words against the row
    pc = spec.get("container_placeholder_copy/1.0") or {}
    for piece in pc.get("pieces") or []:
        if not piece.get("unwritten"):
            continue
        drawn = ", ".join(f'{d["node"]} ({d["scale"]}, {d["size_pt"]} pt)'
                          for d in piece.get("drawn_at") or [])
        words = piece.get("words_on_record") or {}
        rows.append({"label": f'Copy · {piece["heading"]}',
                     "value": f'{piece["code"]} · drawn at {drawn or "nowhere"}'
                              + (f' · not drawn at {", ".join(piece["not_drawn"])}'
                                 if piece.get("not_drawn") else "")
                              + f' · record field {words.get("field", "?")}: '
                                f'{words.get("state", "?")}'
                              + (" · drawn as set copy from a composer literal: "
                                 + ", ".join(lit["node"] for lit in piece["literal_drawings"])
                                 if piece.get("literal_drawings") else "")})
    # §BH50(f)(3): the front copy, run by run, in millimetres — an overrun is a
    # design problem to solve. §BH50(g)(1) (re-typed §BH53(a)): the board says
    # where each run stands against the zone's SAFE AREA, which governs, and
    # against the zone, the outer bound. A /1.0 record (persisted before §BH53)
    # is read as what it was: a verdict against the zone, the safe area measured
    # and not ruled — never re-labelled.
    fit = spec.get("container_front_copy_fit/1.1") or {}
    legacy_fit = not fit and bool(spec.get("container_front_copy_fit/1.0"))
    if legacy_fit:
        fit = spec["container_front_copy_fit/1.0"]
    # §BH50(g)(2): the product name is front copy — its runs sit on the board beside the small copy
    for run in list(fit.get("runs") or []) + list(fit.get("name_runs") or []):
        if "width_mm" in run:
            value = (f'{run["state"]} · {run["width_mm"]} mm at {run["size_pt"]} pt in '
                     f'{run.get("face")}')
            if legacy_fit:
                value += (f' · zone {run["zone_width_mm"]} mm ({run["spare_mm"]:+} mm) — a record persisted '
                          f'before §BH53: its verdict is against the zone, and its safe area')
                if run.get("safe_area_mm") is not None:
                    value += (f' {run["safe_area_mm"]} mm ({run["spare_to_safe_area_mm"]:+} mm, '
                              f'{run["safe_area_state"]}) was measured, not ruled')
                else:
                    value += " was unmeasured"
            else:
                if run.get("safe_area_mm") is not None:
                    value += (f' · safe area {run["safe_area_mm"]} mm ({run["spare_to_safe_area_mm"]:+} mm, '
                              f'{run["safe_area_state"]}; governs — §BH50(g)(1))')
                else:
                    value += (" · safe area UNMEASURED (no usable safe_margin_mm on the zone record; "
                              "governs — §BH50(g)(1))")
                value += (f' · outer bound {run["zone_width_mm"]} mm ({run["spare_mm"]:+} mm, '
                          f'{run.get("outer_bound_state")})')
        else:
            value = f'{run["state"]} · {run.get("reason", "")}'
        rows.append({"label": f'Front copy · {run["name"]}', "value": value})
    if fit.get("vertical"):
        rows.append({"label": "Front copy · vertical", "value": str(fit["vertical"])})
    return rows


def _checks_date(task, output, spec) -> tuple[str, str]:
    """§BH50(g)(4): the record-side date of a spec's checks — the reconstruction's own 'reached Gate 2' log,
    else container_resume.requested_at, else the output row's creation, which is the begin-output time and says so."""
    from apps.pipeline.models import AgentLog
    log = (AgentLog.objects.filter(task=task, agent_name="ARIA", action__contains="reached Gate 2")
           .order_by("-timestamp").first())
    if log is not None:
        return log.timestamp.strftime("%Y-%m-%d %H:%MZ"), "the reconstruction's 'reached Gate 2' log"
    resume = (spec.get("container_resume") or {}).get("requested_at")
    if resume:
        return str(resume)[:16], "container_resume.requested_at"
    if output is not None and output.created_at:
        return (output.created_at.strftime("%Y-%m-%d %H:%MZ"),
                "the output row's creation — the begin-output time, hours before its checks")
    return "unknown", "no record-side date"


def _readiness_read_rows(task, output, spec) -> list[dict]:
    """§BH50(g)(4), re-typed §BH53(a): both halves of "A STALE SPEC NEVER SHOWS AS CURRENT" — the Gate-2 reader's own
    verdict, derived at readiness-read (the persisted row says what the run wrote), and the stale mark with the dates
    its checks predate. Nothing rewritten, nothing newly blocking; a spec with no reconstruction has no rows here."""
    from apps.dashboard.owner_channel import preview_sha256
    from apps.ire.container_production_readiness import build_readiness, spec_staleness
    if not spec.get("container_reconstruction"):
        return []
    verdict = build_readiness(spec, preview_sha256(output)[0] if output is not None else ...)   # §BH71
    blocking = verdict["blocking_codes"]
    rows = [{"label": "Gate-2 verdict (derived at readiness-read)",
             "value": ((f'{len(blocking)} blocking: ' + " · ".join(blocking[:8]) + (" …" if len(blocking) > 8 else ""))
                       if blocking else "no blocking code")
                      + f' · human design acceptance {verdict["human_design_acceptance_state"]} — the reader Gate 2 '
                      "enforces, derived now (§BH50(g)(4)); the persisted row above is what the run wrote"}]
    # [the owner's answer of 2026-09-27: the maker's printing specification is shown as a production note, never a
    # blocker — here, where the review board shows what Gate 2 reads]
    notes = verdict.get("production_notes") or []
    if notes:
        # [his answer on the safe margin, 2026-10-01: the notes now carry a part printed as the picture prints it too]
        rows.append({"label": "Production notes (for the printer)",
                     "value": f'{len(notes)} for the printer, never a reason it is refused: '
                              + " · ".join(notes[:8]) + (" …" if len(notes) > 8 else "")})
    # [§BH71 (0a): what is not measured yet — a warning beside Approve, never a reason it is refused]
    from apps.ire.container_production_readiness import fidelity_unmeasured
    listed = set(fidelity_unmeasured(spec)["codes"])          # the fidelity row lists these already
    warned = [c for c in verdict.get("acceptance_warnings") or [] if c not in listed]
    if warned:
        rows.append({"label": "Copy not measured yet (warnings beside Approve)",
                     "value": f'{len(warned)}, never a reason it is refused and never marked passed: '
                              + " · ".join(warned[:8]) + (" …" if len(warned) > 8 else "")})
    stale = spec_staleness(spec)
    when, source = _checks_date(task, output, spec)
    if stale["stale"]:
        rows.append({"label": "Spec checks",
                     "value": f'STALE — checks as of {when} ({source}) predate: '
                              + "; ".join(f'{i["what"]} — {i["ruling"]}, {i["since"]} ({i["commit"]})'
                                          for i in stale["checks_predate"])
                              + " · nothing rewritten, nothing newly blocking (§BH50(g)(4))"})
    else:
        rows.append({"label": "Spec checks",
                     "value": f'CURRENT as of {when} ({source}) — every declared section and report the reader knows '
                              "is HEAD's (§BH50(g)(4))"})
    return rows


def _fact_hygiene_rows(spec: dict) -> list[dict]:
    """2C-2D-CORR-2 §10: dimensional attribution — the concept-only
    dimension proposal, the outer-carton dims under their own referent, the
    contamination finding and the collar-zone exclusion."""
    from apps.pipeline.services import selected_concept_contract as scc
    rows: list[dict] = []
    finding = spec.get(scc.REFERENT_FINDING_KEY)
    if isinstance(finding, dict):
        rows.append({"label": "Dimension referent finding",
                     "value": " · ".join(finding.get("codes") or [])})
    secondary = spec.get(scc.SECONDARY_PACKAGING_KEY)
    if isinstance(secondary, dict):
        rows.append({"label": "Secondary packaging (outer carton)",
                     "value": (f'{secondary.get("width_mm")} × '
                               f'{secondary.get("depth_mm")} × '
                               f'{secondary.get("height_mm")} mm — '
                               f'{secondary.get("referent")}, '
                               f'{secondary.get("verification")} — never '
                               "container geometry")})
    dim = spec.get(scc.DIM_PROPOSAL_SCHEMA)
    if isinstance(dim, dict):
        rows.append({"label": "Concept dimension proposal",
                     "value": (f'{dim.get("schema_version")} — every value '
                               "editable, CONCEPT_ONLY_UNVERIFIED, "
                               "manufacturer confirmation required")})
        for p in dim.get("proposals") or []:
            val = p.get("value")
            val_s = (f'{val[0]}–{val[1]}' if isinstance(val, list) and
                     len(val) == 2 else str(val))
            rows.append({"label": f'  {p.get("field")}',
                         "value": (f'{val_s} {p.get("unit") or ""} '
                                   f'[{p.get("source")}, conf '
                                   f'{p.get("confidence")}, '
                                   f'{p.get("verification_state")}]')})
    ext = spec.get(scc.EXTENSIONS_SCHEMA)
    if isinstance(ext, dict):
        rows.append({"label": "Profile extensions",
                     "value": (f'{ext.get("schema_version")} · '
                               f'{len(ext.get("fields") or {})} fields · '
                               f'{ext.get("confirmation_state")}')})
    for excl in (spec.get("container_decoration_zones/1.0") or {}).get(
            "exclusions") or []:
        rows.append({"label": f'Zone excluded — {excl.get("zone")}',
                     "value": (f'{excl.get("decision")}: '
                               + "; ".join(excl.get("reasons") or []))})
    return rows


def _contract_rows(spec: dict) -> list[dict]:
    """§13 Review Board rows for the versioned container_profile/1.0 +
    container_decoration_zones/1.0 records. Read-only surfacing of schema
    version, confirmation state, per-field verification, zones + states, the
    identity hashes, and any pending refusal — never fabricates a zone."""
    from apps.pipeline.services import container_contract as cc
    rows: list[dict] = []
    prof = spec.get(cc.PROFILE_SCHEMA)
    if not prof:
        return rows
    rows.append({"label": "Container contract", "value": cc.PROFILE_SCHEMA})
    rows.append({"label": "Profile state",
                 "value": str(prof.get("confirmation_state", "UNCONFIRMED"))})
    rows.append({"label": "Profile source",
                 "value": str(prof.get("profile_source", cc.SRC_UNKNOWN))})
    fields = prof.get("fields") or {}
    for name, lab in (("body_width_mm", "Body width"),
                      ("body_height_mm", "Body height"),
                      ("neck_ratio", "Neck ratio"), ("cap_type", "Cap type")):
        f = fields.get(name) or {}
        if f.get("value") is not None:
            rows.append({"label": lab,
                         "value": f'{f["value"]} ({f.get("verification")})'})
    rows.append({"label": "Profile hash",
                 "value": str(prof.get("profile_hash", ""))[:12]})

    zrec = spec.get(cc.ZONES_SCHEMA) or {}
    zones = zrec.get("zones") or []
    rows.append({"label": "Decoration zones",
                 "value": f'{len(zones)} · {zrec.get("confirmation_state", "PROPOSED")}'})
    for z in zones:
        # §AA WI-R — the REPORTING form of the refusal, not the raise. This is
        # a read-only board over data that is already stored; a board that 500s
        # because a stored zone is spelled wrong tells the reader nothing and
        # hides every other row. The boundary that stops it being stored is in
        # `views.py`; here the code goes in the cell.
        surface = (cc.ZONE_SURFACE_KEY_UNRECOGNISED
                   if cc.zone_surface_problem(z) else cc.zone_surface(z))
        rows.append({
            "label": f'  {z.get("zone_type", "ZONE")}',
            "value": (f'{surface} · '
                      f'{z.get("width")}×{z.get("height")}mm · '
                      f'{z.get("user_confirmation_state", cc.ZONE_PROPOSED)}')})
    if zrec.get("zone_set_hash"):
        rows.append({"label": "Zone-set hash",
                     "value": str(zrec["zone_set_hash"])[:12]})
    conf = spec.get("container_confirmation") or {}
    if conf.get("combined_hash"):
        rows.append({"label": "Combined confirmation",
                     "value": str(conf["combined_hash"])[:12]})
    if spec.get("generation_error"):
        rows.append({"label": "Pending review",
                     "value": str(spec["generation_error"])})
    return rows


def _handoff_rows(spec: dict) -> list[dict]:
    """§21 Review Board rows for the Native Illustrator Handoff package —
    labelled distinctly from the legacy raster output and the native
    reconstruction; human visual authority always visible."""
    h = spec.get("container_handoff")
    if not h:
        return []
    rows = [{"label": "Native Illustrator handoff",
             "value": f'{h.get("schema_version")} · {h.get("handoff_label")}'},
            {"label": "  files",
             "value": " · ".join(sorted((h.get("files") or {}).values()))},
            {"label": "  layers/groups",
             "value": f'{h.get("layer_count")} layers · '
                      f'{h.get("group_count")} groups'},
            {"label": "  swatches/spots",
             "value": f'{h.get("swatch_count")} process · '
                      f'{h.get("spot_count")} spot'},
            {"label": "  census",
             "value": f'live text {h.get("live_text_count")} · raster '
                      f'fallback {h.get("raster_fallback_count")} · '
                      f'decorative rasters {h.get("decorative_raster_count")}'},
            {"label": "  fonts", "value": ", ".join(h.get("fonts") or [])},
            {"label": "  surfaces",
             "value": ", ".join(h.get("surfaces") or [])},
            {"label": "  separations",
             "value": ", ".join(h.get("separations") or []) or "none"},
            {"label": "  human visual acceptance",
             "value": str(h.get("human_visual_acceptance_state"))},
            {"label": "  execution",
             "value": f'{h.get("execution_state")} · explicit-only'}]
    if h.get("validation_codes"):
        rows.append({"label": "  validation",
                     "value": "; ".join(h["validation_codes"])})
    return rows


def _reconstruction_rows(spec: dict) -> list[dict]:
    """§15 Review Board rows for the 2B-2 native reconstruction: selected
    variation identity, the identity hashes, native output + legacy warning,
    census, projection method, containment result, three-state fidelity and
    any reconstruction blockers — so the reviewer can tell the original
    concept, the legacy raster output and the native reconstruction apart."""
    rows: list[dict] = []
    ident = spec.get("container_selected_variation/1.0")
    if not ident:
        return rows                       # pre-2B-2 output; nothing to add
    vid = ident.get("variation_id") or ident.get("direction_name") or "?"
    rows.append({"label": "Selected variation",
                 "value": f'{vid} · verified={ident.get("verified")}'
                          f' · record={ident.get("structured_record_present")}'})

    prof = spec.get("container_profile/1.0") or {}
    zrec = spec.get("container_decoration_zones/1.0") or {}
    vg = spec.get("container_selected_concept_visual_graph/1.0") or {}
    hashes = [("profile", prof.get("profile_hash")),
              ("zones", zrec.get("zone_set_hash")),
              ("visual-graph", vg.get("visual_graph_hash")),
              ("variation", ident.get("source_hash"))]
    rows.append({"label": "Identity hashes",
                 "value": " · ".join(f'{k}:{str(h)[:8]}' for k, h in hashes if h)})
    # §BH71 PART 1: "the design says when the fallback was used" — which drew the outline, and why
    if spec.get(OUTLINE_SOURCE_KEY):
        from apps.pipeline.services import concept_outline as _co
        rows.append({"label": "Drawn outline", "value": _co.words(spec[OUTLINE_SOURCE_KEY])})

    cdg = (spec.get("container_design_graph/1.1")
           or spec.get("container_design_graph/1.0") or {})
    if cdg:
        prim = cdg.get("primitives") or {}
        rows.append({"label": "Native reconstruction",
                     "value": f'{cdg.get("mode", "?")} · '
                              f'{prim.get("live_text", 0)} live text · '
                              f'{prim.get("vector_paths", 0)} vector paths'})
        rows.append({"label": "Decorative rasters",
                     "value": f'{cdg.get("decorative_raster_count", 0)} '
                              f'(reference {prim.get("reference_rasters", 0)} · '
                              f'logo {prim.get("logo_rasters", 0)})'})
        inv = cdg.get("surface_inventory") or {}
        if inv:
            rows.append({"label": "Surface artwork",
                         "value": " · ".join(f'{k}:{v}' for k, v in sorted(inv.items()))})
        if cdg.get("motif_family"):
            rows.append({"label": "Motif rendered via",
                         "value": str(cdg["motif_family"])})
        fbr = cdg.get("front_back_relationship") or {}
        if fbr.get("back_role"):
            rows.append({"label": "Front / back",
                         "value": f'{fbr.get("front_role")} / {fbr.get("back_role")}'})
        rows.append({"label": "Output types",
                     "value": "native vector reconstruction "
                              "(legacy raster output superseded)"})

    # [THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The house mark's state — a row only when an approval is on file,
    # so a board with none is the board it always was]
    from apps.ire import brand_mark as _brand_mark
    mark = spec.get(_brand_mark.SCHEMA)
    if isinstance(mark, dict):
        rows.append({"label": "Brand mark",
                     "value": ("drawn from the approved vector master %s" % mark["master"]["sha256"][:16]
                               if mark.get("master") is not None else
                               "the PNG — the approval on file is refused: %s" % "; ".join(mark["codes"]))})

    mspec = spec.get("container_motif_spec/1.0") or {}
    if mspec.get("reconstruction_capability"):
        cap = mspec["reconstruction_capability"]
        rv = mspec.get("rendered_via")
        rows.append({"label": "Motif reconstruction",
                     "value": (f'{cap} · via {rv}' if rv else cap)
                              + (" (approximate)"
                                 if mspec.get("rendered_via_is_approximate") else "")})
    mfid = spec.get("container_motif_fidelity_report") or {}
    if mfid and mfid.get("overall"):
        rows.append({"label": "Motif fidelity",
                     "value": str(mfid["overall"])
                              # §BH50(f)(4): the label says what it blocks — [§BH71 (0a): nothing, now]
                              + (" · not measured — a warning beside Approve"
                                 if mfid["overall"] == "UNMEASURED_BLOCKING"
                                 else "")})
        for code in (mfid.get("failures") or []):
            rows.append({"label": "  Motif failure", "value": code})

    # §14 surface classification: which surfaces carry artwork vs technical only
    manifest = spec.get("container_native_output_manifest") or {}
    if manifest.get("surfaces_with_artwork"):
        rows.append({"label": "Surfaces with artwork",
                     "value": ", ".join(manifest["surfaces_with_artwork"])})
    if manifest.get("technical_only_surfaces"):
        rows.append({"label": "Technical-only surfaces",
                     "value": ", ".join(manifest["technical_only_surfaces"])})

    proj = spec.get("container_projection_report") or {}
    if proj.get("zones"):
        methods = sorted({z.get("method") for z in proj["zones"] if z.get("method")})
        rows.append({"label": "Projection",
                     "value": ", ".join(methods)
                              + (" · REVIEW REQUIRED" if proj.get("review_required")
                                 else "")})
    cont = spec.get("container_zone_containment_report") or {}
    if cont:
        rows.append({"label": "Zone containment",
                     "value": "all artwork contained" if cont.get("contained")
                              else f'{len(cont.get("problems") or [])} issue(s)'})
    fid = spec.get("container_fidelity_report") or {}
    if fid:
        c = fid.get("counts") or {}
        rows.append({"label": "Concept fidelity",
                     "value": f'{fid.get("overall", "?")} '
                              f'(pass {c.get("measured_pass", 0)} · '
                              f'fail {c.get("measured_fail", 0)} · '
                              f'unmeasured {c.get("unmeasured", 0)}'
                              + (f' · n/a {c["not_applicable"]}'
                                 if c.get("not_applicable") else "") + ")"
                              # §BH50(f)(4): the label says what it blocks — [§BH71 (0a): nothing, now]
                              + (" · not measured — a warning beside Approve"
                                 if fid.get("overall") == "UNMEASURED_BLOCKING"
                                 else "")})
        for code in (fid.get("failures") or []):
            rows.append({"label": "  Fidelity failure", "value": code})
    # 2B-3A §18: font authority (identities + states) + the production-font
    # gate codes (a Gate-2 concern, not a reconstruction blocker)
    fa = spec.get("container_font_authority/1.0") or {}
    for f in (fa.get("faces") or []):
        rows.append({"label": f'  Font ({f.get("role")})',
                     "value": f'{f.get("font_family") or "?"} · '
                              f'{f.get("verification")}'
                              + (" · fallback" if f.get("is_fallback") else "")})
    rcodes = spec.get("container_production_readiness_codes") or {}
    for code in (rcodes.get("font") or []):
        rows.append({"label": "Production-font gate", "value": str(code)})
    mreal = spec.get("material_influence_realization/1.0") or {}
    if mreal.get("state"):
        rows.append({"label": "Material influence",
                     "value": f'{mreal["state"]} · {len(mreal.get("references") or [])} ref(s)'})
    for code in (rcodes.get("material") or []):
        rows.append({"label": "Material readiness", "value": str(code)})

    # 2B-3B §15: production methods + authority (a Gate-2 concern)
    pmr = spec.get("container_production_method/1.0") or {}
    for m in (pmr.get("methods") or []):
        rows.append({"label": f'  Method ({m.get("method_type") or "?"})',
                     "value": f'{"/".join(m.get("target_surfaces") or [])} · '
                              f'{m.get("authority_state")}'})
    for code in (rcodes.get("production_method") or []):
        rows.append({"label": "Production-method gate", "value": str(code)})
    sep = spec.get("container_production_separations/1.0") or {}
    if sep.get("separations"):
        names = [s.get("name") for s in sep["separations"]]
        rows.append({"label": "Separations",
                     "value": f'{len(names)} · ' + ", ".join(names[:6])
                              + ("…" if len(names) > 6 else "")})
        ub = (sep.get("white_underbase") or {}).get("state")
        if ub:
            rows.append({"label": "White underbase", "value": str(ub)})
    for code in (rcodes.get("separations") or []):
        rows.append({"label": "Separation readiness", "value": str(code)})

    # 2B-3C §20: quantitative fidelity (measured / unmeasured / failed)
    qfr = spec.get("container_quantitative_fidelity/1.0") or {}
    if qfr.get("counts"):
        c = qfr["counts"]
        rows.append({"label": "Quantitative fidelity",
                     "value": f'{qfr.get("overall")} · pass {c.get("MEASURED_PASS", 0)}'
                              f' · fail {c.get("MEASURED_FAIL", 0)}'
                              f' · unmeasured {c.get("UNMEASURED", 0)}'})
    for code in (rcodes.get("quantitative_fidelity") or []):
        rows.append({"label": "Quantitative failure", "value": str(code)})

    # 2B-3C §7-§10: true wrap production geometry + seam/alignment
    wg = spec.get("container_wrap_geometry/1.0") or {}
    from apps.ire.container_wrap_geometry import WRAPPED_SURFACES
    for w in (wg.get("wraps") or []):
        # §BH50(f)(6): a projected face carries no seam, and the board says so
        # instead of printing the record's seam field on a surface with no
        # wrap; a record written before the flag existed is read by surface
        wrapped = (w["wrapped"] if "wrapped" in w
                   else w.get("surface") in WRAPPED_SURFACES)
        seam = (f'seam {w.get("seam_position")}' if wrapped
                else "projected face, no seam")
        detail = f'{w.get("curvature_type")} · {seam}'
        if w.get("circumference_mm"):
            detail += f' · C={w["circumference_mm"]}mm'
        rows.append({"label": f'  Wrap ({w.get("surface")})', "value": detail})
    seam_check = (spec.get("container_wrap_alignment") or {}).get("seam_check") or {}
    if seam_check.get("state") and seam_check.get("state") != "APPLICABLE":
        rows.append({"label": "Wrap alignment (seam check)",
                     "value": f'{seam_check["state"]} — {seam_check.get("reason")}'})
    for code in (rcodes.get("wrap_alignment") or []):
        rows.append({"label": "Wrap alignment", "value": str(code)})

    # 2B-3C §11-§14: coverage / registration / complete colour count
    metrics = spec.get("container_production_metrics/1.0") or {}
    reg = (metrics.get("registration") or {}).get("state")
    if reg:
        rows.append({"label": "Registration", "value": str(reg)})
    for cc_entry in (metrics.get("color_count") or {}).get("per_method") or []:
        rows.append({"label": f'  Colours ({cc_entry.get("method_type")})',
                     "value": f'{cc_entry.get("count")} / '
                              f'{cc_entry.get("permitted")}'})
    for code in (rcodes.get("production_metrics") or []):
        rows.append({"label": "Production metric", "value": str(code)})

    # 2B-3C §16/§17: per-reference material attribution + similarity risk
    mr11 = spec.get("material_influence_realization/1.1") or {}
    for r in (mr11.get("references") or []):
        realized = [d for d, v in (r.get("dimensions") or {}).items()
                    if v.get("status") == "REALIZED"]
        rows.append({"label": f'  Reference {r.get("reference_id")}',
                     "value": f'claims {r.get("claimed_dimensions")} · '
                              f'realized {realized}'})
    for code in (rcodes.get("material_attribution") or []):
        rows.append({"label": "Material attribution", "value": str(code)})

    recon = spec.get("container_reconstruction") or {}
    for code in (recon.get("blockers") or []):
        # [his goal of 2026-10-13, (1)] a check it went on past, in its words — never its code
        from apps.dashboard.words import check_words as _words
        rows.append({"label": "A check it went on past",
                     "value": _words(str(code)) or "a check of the drawing did not pass"})
    return rows


class ProductContainerTarget(TargetStrategy):
    name = DesignTarget.PRODUCT_CONTAINER.value

    def concept_structure_id(self, aria):
        return None                       # containers have no packaging structure

    def concept_prompt_profile(self, aria) -> str:
        # §BH70(1): the product's own form, from its record or the words its brief uses — and, since the owner's
        # answer of 2026-09-27, the product its vessel holds when that is not the form's namesake
        task = getattr(aria, "task", None)
        return concept_directive(form_of_task(task), brief_text(task) if task is not None else "")

    def gate1_variation_plan(self, aria, direction):
        """2B-3V §4/§5/§6 + CORR-2 §7: the container's initial Gate-1 set is
        ALWAYS the structured variation contract (container_gate1_variations/1.0
        — named A/B/C identities, seven-axis diversity, native-reconstruction
        plans), validated BEFORE any image call. It never reverts to generic
        unnamed variations.

        When the task carries approved concept references + an influence plan,
        each variation also declares its OWN subset of those references
        (CORR-2 per-variation grounding, routed exactly by the ImageProducer).
        With no approved references the contract still runs — structured, but
        without visual grounding. There is no hidden minimum-count rule; one
        approved reference is used only where assigned."""
        from apps.pipeline.services import container_gate1 as cg1
        from apps.pipeline.services import gate1_checkpoint as ckpt
        from apps.pipeline.services.concept_references import approved_references
        from apps.pipeline.services.gate1_prompts import (
            RegenPromptsResult,
            build_regeneration_prompts,
        )
        from apps.pipeline.services.product_profile import profile_text

        # 2C-2C-CORR-1 §3: a VALIDATED checkpointed plan is reused when its
        # whole authority context is unchanged — Prompt Engineer is skipped
        # and no PE ApiCallRecord is created. Any drift fails closed with
        # the stable invalidation code; the plan is never silently rebuilt.
        checkpoint = ckpt.load_checkpoint(aria.task)
        if checkpoint is not None:
            ok, codes = ckpt.verify_checkpoint(aria.task)
            if not ok:
                return RegenPromptsResult(
                    ok=False, payload=None, prompts=[], codes=tuple(codes),
                    attempts=0,
                    raw_responses=("<checkpoint context mismatch — new "
                                   "human authorization required before "
                                   "another Prompt Engineer call>",),
                    provider_model="")
            if checkpoint.get("state") == ckpt.STATE_BILLING_BLOCKED:
                # §6: after a provider billing block the owner must record
                # the explicit acknowledgement before ANY image spend
                # (acknowledge_billing flips the state back to VALIDATED)
                return RegenPromptsResult(
                    ok=False, payload=None, prompts=[],
                    codes=(ckpt.BILLING_ACK_REQUIRED,),
                    attempts=0,
                    raw_responses=("<retry held: owner billing "
                                   "acknowledgement required — zero "
                                   "provider calls made>",),
                    provider_model="")
            # §BH67(c)4: the plan's OWN ids — a slot-named plan stores no identities in its context, and reading those
            # counted zero missing images for the budget guard on every default-contract checkpoint
            missing = [vid for vid in ckpt.plan_variation_ids(checkpoint)
                       if ckpt.existing_variation_image(aria.task, vid)
                       is None]
            guard = ckpt.budget_guard(aria.task,
                                      planned_calls=len(missing) * 2)
            if guard:
                return RegenPromptsResult(
                    ok=False, payload=None, prompts=[],
                    codes=tuple(guard), attempts=0,
                    raw_responses=("<stopped before spend: provider-call "
                                   "budget would be exceeded>",),
                    provider_model="")
            aria.log("Gate-1 prompts: reusing the VALIDATED checkpointed "
                     f"plan {checkpoint['prompt_plan_hash'][:16]} from "
                     f"ApiCallRecord "
                     f"{checkpoint['prompt_engineer_call_id']} — Prompt "
                     "Engineer skipped, no provider call",
                     agent='PromptEngineer')
            return ckpt.checkpoint_plan_result(aria.task, aria=aria)

        approved = approved_references(aria.task)
        plan_obj = getattr(aria.task, "concept_influence_plan", None)
        has_refs = bool(approved) and plan_obj is not None

        profile = aria._product_profile()
        _form = form_of_task(aria.task)
        product_block = profile_text(profile) or PRODUCT_BLOCK_FALLBACK.format(
            form=(product_in_form(_form, brief_text(aria.task))
                  or (_declared.vocabulary_of(_form)["label"].lower().replace(" / ", " or ")
                      if _declared.is_known(_form) else "whichever its brief names")))
        if form_line(aria.task) and form_line(aria.task) not in product_block:   # [his goal of 2026-10-06, item 1]
            product_block = form_line(aria.task) + "\n\n" + product_block
        # B4b-3B §13: the owner's uploaded references (categories + REFERENCE
        # ONLY constraints) ride the product block into the structured
        # variation-contract prompt. Tasks without uploads are byte-stable.
        # ``aria`` may be a reduced facade in tests — no manifest method
        # simply means no uploaded-reference block.
        from apps.pipeline.services.reference_manifest import (
            prompt_engineer_reference_context)
        _ref_ctx = prompt_engineer_reference_context(
            aria._reference_manifest()
            if hasattr(aria, "_reference_manifest") else {})
        if _ref_ctx:
            product_block = (product_block
                             + "\n\nOWNER-UPLOADED REFERENCES "
                               "(REFERENCE ONLY):\n" + _ref_ctx)
        # [his answer 1 of 2026-10-02 (6badb27)] the brief's own colours, said to the step that makes the concept picture
        from apps.pipeline.services.product_profile import with_brief_colours
        product_block = with_brief_colours(product_block, profile)
        # §BH71 PART 2: the trend board's words after them — quoted as data, never a picture
        from apps.pipeline.services import trend_board
        product_block = trend_board.with_trends(product_block, aria.task)
        # 2C-2C: a composite-project task may carry its OWN human-mandated
        # variation specification (identities + per-variation contract
        # directives + an optional strict prompt-attempt cap for provider
        # budgets) in project.metadata. Tasks without a project or spec —
        # task #51 and every regression — keep the module constants
        # byte-for-byte.
        project = getattr(aria.task, "project", None)
        spec = (((project.metadata or {}).get("gate1_variation_spec") or {})
                if project else {})
        # §BH67(c)4: a person's own identities for this project are enforced exactly; otherwise the three are SLOTS the
        # variations name from their own concepts — no house identity is a default (CONTAINER_VARIATION_SLOTS)
        identities = spec.get("variation_identities") or ()
        slots = None if identities else cg1.CONTAINER_VARIATION_SLOTS
        directives = (spec.get("richness_directives")
                      or cg1.CONTAINER_GATE1_DIRECTIVES)
        result = build_regeneration_prompts(
            direction=direction,
            product_block=product_block,
            influence_plan=(plan_obj.plan if has_refs else {}),
            plan_hash=(plan_obj.plan_hash if has_refs else ""),
            reference_ids=([r.pk for r in approved] if has_refs else []),
            variation_identities=identities,
            richness_directives=directives,
            max_attempts=spec.get("max_prompt_attempts"),
            log=aria._log_for('PromptEngineer'),
            system=cg1.CONTAINER_SYSTEM,
            schema_version=cg1.CONTAINER_GATE1_SCHEMA,
            required_fields=(cg1.CONTAINER_REQUIRED_FIELDS if has_refs
                             else cg1.CONTAINER_REQUIRED_FIELDS_NO_REFS),
            diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS,
            min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
            schema_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
            empty_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
            not_distinct_code=cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT,
            identity_code=cg1.CONTAINER_VARIATION_IDENTITY_MISSING,
            require_per_variation_reference_ids=has_refs,
            operation="container_gate1_variations",
            identity_slots=slots,
        )
        # 2C-2C-CORR-1 §2: a PASSED fresh plan on a composite-project task
        # is promoted to the retryable checkpoint immediately, so a later
        # EXTERNAL provider failure never forces a rebuild. Legacy tasks
        # (no project) are untouched.
        if getattr(result, "ok", False) and project is not None:
            from apps.pipeline.models import ApiCallRecord
            last_call = ApiCallRecord.objects.order_by("-id").first()
            ckpt.create_checkpoint(
                aria.task, payload=result.payload, prompts=result.prompts,
                pe_call_id=(last_call.id if last_call else None),
                provider_model=result.provider_model)
        return result

    def check_concepts(self, aria, images):
        """[His test blocker on design 122, 2026-10-07, items 2 and 4] every concept checked before it is shown
        (``readable.check_concepts``)."""
        from .readable import check_concepts
        return check_concepts(aria, images)

    def gate1_direction_plan(self, aria, directions):
        """[His final goal, 2026-10-05, B4: "Three directions planned privately and validated. Three truly different
        concepts drawn straight away."] The container's structured Gate-1 contract (the same schema, seven signatures,
        native-reconstruction plans) with ONE variation for each planned direction, in slot order, each echoing its
        direction's id — one planner call, as the three variations of one direction took. A project that names its own
        variation identities keeps them (a person's decision); a checkpointed plan is not reused here — it was made for
        one direction."""
        from apps.pipeline.services import container_gate1 as cg1
        from apps.pipeline.services.concept_references import approved_references
        from apps.pipeline.services.gate1_prompts import build_regeneration_prompts
        from apps.pipeline.services.product_profile import profile_text, with_brief_colours
        from apps.pipeline.services.reference_manifest import prompt_engineer_reference_context
        from apps.pipeline.services import trend_board

        approved = approved_references(aria.task)
        plan_obj = getattr(aria.task, "concept_influence_plan", None)
        has_refs = bool(approved) and plan_obj is not None
        profile = aria._product_profile()
        _form = form_of_task(aria.task)
        product_block = profile_text(profile) or PRODUCT_BLOCK_FALLBACK.format(
            form=(product_in_form(_form, brief_text(aria.task))
                  or (_declared.vocabulary_of(_form)["label"].lower().replace(" / ", " or ")
                      if _declared.is_known(_form) else "whichever its brief names")))
        if form_line(aria.task) and form_line(aria.task) not in product_block:   # [his goal of 2026-10-06, item 1]
            product_block = form_line(aria.task) + "\n\n" + product_block
        _ref_ctx = prompt_engineer_reference_context(
            aria._reference_manifest() if hasattr(aria, "_reference_manifest") else {})
        if _ref_ctx:
            product_block = product_block + "\n\nOWNER-UPLOADED REFERENCES (REFERENCE ONLY):\n" + _ref_ctx
        product_block = with_brief_colours(product_block, profile)
        product_block = trend_board.with_trends(product_block, aria.task)
        project = getattr(aria.task, "project", None)
        spec = (((project.metadata or {}).get("gate1_variation_spec") or {}) if project else {})
        identities = spec.get("variation_identities") or ()
        return build_regeneration_prompts(
            direction={}, directions=list(directions),
            product_block=product_block,
            influence_plan=(plan_obj.plan if has_refs else {}),
            plan_hash=(plan_obj.plan_hash if has_refs else ""),
            reference_ids=([r.pk for r in approved] if has_refs else []),
            variation_identities=identities,
            richness_directives=spec.get("richness_directives") or cg1.CONTAINER_DIRECTIONS_DIRECTIVES,
            max_attempts=spec.get("max_prompt_attempts"),
            log=aria._log_for('PromptEngineer'),
            system=cg1.CONTAINER_SYSTEM,
            schema_version=cg1.CONTAINER_GATE1_SCHEMA,
            required_fields=(cg1.CONTAINER_REQUIRED_FIELDS if has_refs else cg1.CONTAINER_REQUIRED_FIELDS_NO_REFS),
            diversity_fields=cg1.CONTAINER_DIVERSITY_FIELDS,
            min_pairwise=cg1.CONTAINER_MIN_PAIRWISE_DIFFERENCES,
            schema_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
            empty_code=cg1.CONTAINER_VARIATION_CONTRACT_NOT_PRESERVED,
            not_distinct_code=cg1.CONTAINER_GATE1_VARIATIONS_NOT_DISTINCT,
            identity_code=cg1.CONTAINER_VARIATION_IDENTITY_MISSING,
            require_per_variation_reference_ids=has_refs,
            operation="container_gate1_variations",
            identity_slots=None if identities else cg1.CONTAINER_VARIATION_SLOTS,
        )

    def begin_output(self, aria, approved_image):
        """After Gate 1: infer the container profile, create the output row,
        and pause at the confirm-profile gate (mirrors _run_dieline_estimate)."""
        from apps.pipeline.models import PackagingOutput

        from apps.pipeline.services.authored_master import is_authored
        if is_authored(aria.task):
            raise ValueError("Authored masters compile from their pinned DesignSpec on the serum artwork page.")

        profile = _infer_profile(aria.task)
        product = getattr(aria.task, "product", None)
        # 2B-1: seed the versioned container_profile/1.0 record with every
        # value INFERRED_NONAUTHORITATIVE (§8 photo-safety enforced here, not
        # only at confirm) + PROPOSED decoration zones. Additive keys; the
        # legacy `container_profile` dict below is left untouched so
        # reconstruction and legacy readers keep working.
        from apps.pipeline.services import container_contract as cc
        estimates = {"body_width_mm": asdict(profile).get("width_mm"),
                     "body_height_mm": asdict(profile).get("height_mm"),
                     "neck_ratio": asdict(profile).get("neck_ratio"),
                     "cap_type": asdict(profile).get("cap_style")}
        versioned = cc.build_inferred_profile(
            profile.archetype, asdict(profile).get("variant", ""),
            estimates={k: v for k, v in estimates.items() if v is not None})
        # 2B-3V UI correction §2: product-record dims (incl. depth) seed the
        # proposal AS RECORDED — the depth of a 35×25×95 tube must never be
        # absent from the contract the human reviews. Concept-only visual
        # proposals (colors, transparency) come from the SELECTED variation's
        # signatures as INFERRED_NONAUTHORITATIVE, never verified.
        # [§BH55 Phase 1, 2026-09-19: a record that describes the product's CARTON is not merged — CORR-2 §4's
        # finding, below, held on the pilot's path only; its sizes stay the carton's, which the packaging stage
        # reads from the product row itself.]
        if aria.task.product is not None and not _record_describes_carton(aria.task.product):
            versioned = cc.merge_product_record_dims(versioned, aria.task.product)
        versioned = _seed_concept_proposals(versioned, approved_image)
        # §BH71 PART 1: the outline traced from the approved concept — its kind and proportions proposed at the shape
        # step (a person confirms them, as every proposal), the trace kept on the record with its reason when it cannot
        from apps.pipeline.services import learned_shapes
        versioned, outline_trace = _seed_outline_proposal(
            versioned, approved_image, named_shape=lid_shape_named_in(profile.archetype, brief_text(aria.task)),
            traced=learned_shapes.traced_variants(profile.archetype))
        # [his go of 2026-10-02 (a18911a): "build the map path to run on its own for every new design"] the approved
        # concept's design map, read once per picture: the shape step proposes its print areas from it, the drawing
        # draws from it (`_map_front`)
        from apps.pipeline.services import concept_design_map as _dm
        from apps.pipeline.services import concept_outline as _co
        # [his test blocker on design 122, 2026-10-07, item 4: "draw this concept from the template"] his own choice, by
        # its button: the drawing follows the form's own layout with his brief's words, never the picture's design, and
        # says so — the one door past his finding on design 119's "never drawn from the form's own layout instead"
        from .readable import FROM_TEMPLATE_KEY
        template = (approved_image.reference_provenance or {}).get(FROM_TEMPLATE_KEY)
        design_map = None if template else _read_design_map(aria, profile.archetype, approved_image)
        if template:
            aria.log("ARIA: drawn from the %s's standard layout with your brief's words — your choice; not the picture's "
                     "design" % profile.archetype)
        # [the owner's finding on design 119, 2026-10-03: "NO SILENT FALLBACK"] a form the map draws is drawn from its map,
        # or the design stops at Gate 1 with why — never drawn from the form's own layout instead
        traced_shapes = {}
        if not template:
            # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] every form's map checked — a face form's
            # from its lid stood square
            traced_shapes = map_drawable(aria, approved_image, design_map, _map_bytes(approved_image, profile.archetype))
            if traced_shapes is None:
                return
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5): "after I pick a concept, draw one more picture
        # of the open palette in the same style"] made once and kept; a refusal said, the pans then from their names
        ensure_open_tray(aria, approved_image, profile.archetype)
        proposed = _proposal_from_map(versioned, {_dm.SCHEMA: design_map, _co.SCHEMA: outline_trace},
                                      _concept_bytes(approved_image))       # §BH71 (0b), from the map where it read
        # 2C-2D: a project-level selected-concept visual contract pinned to
        # THIS approved image proposes the §5/§7 dropper profile (archetype
        # included — the keyword heuristic is weaker evidence than the
        # human-selected concept) and the §8 zone set, re-proposed on the
        # corrected record. CORR-2 §4: the product record's dims describe
        # the OUTER CARTON, so the versioned profile is rebuilt WITHOUT
        # them — they survive only under the secondary-packaging record.
        # Without the contract the legacy proposal is byte-identical.
        from apps.pipeline.services import selected_concept_contract as scc
        contract = scc.stored_contract_for(aria.task, approved_image)
        extras = {}
        if contract is not None:
            # §BH61(b)(c) — THE REFUSAL GOES AT THE DOOR. This branch applies the SELECTED-CONCEPT VISUAL
            # CONTRACT, whose seeder asserts bottle/cylindrical (selected_concept_contract.py:798) because it
            # was written for the serum-dropper concept. It used to take whatever archetype it was handed and
            # write bottle/cylindrical/dropper over it — "precisely how my palette became a bottle". It now
            # states its scope and refuses anything else by name, rather than rewriting the form it was given.
            _declared.require_scope(
                "the selected-concept visual contract path (begin_output)",
                profile.archetype, serves=("bottle",))
            from dataclasses import replace
            profile = replace(profile, archetype="bottle",
                              variant="cylindrical", cap_style="dropper",
                              height_mm=None, width_mm=None)
            versioned = cc.build_inferred_profile("bottle", "cylindrical")
            versioned = _seed_concept_proposals(versioned, approved_image)
            versioned = scc.seed_profile_from_visual_contract(versioned,
                                                              contract)
            proposed = scc.augment_dropper_zones(versioned,
                                                 cc.propose_zones(versioned))
            dim_proposal = scc.build_concept_dimension_proposal(contract)
            extras = {
                scc.DIM_PROPOSAL_SCHEMA: dim_proposal,
                scc.EXTENSIONS_SCHEMA:
                    scc.build_profile_extensions(dim_proposal),
                scc.SECONDARY_PACKAGING_KEY:
                    scc.secondary_packaging_record(aria.task.product),
                scc.REFERENT_FINDING_KEY: scc.dimension_referent_finding(),
            }
        from apps.ire import front_hierarchy as _fh
        _name, _name_source = product_name_for(aria.task, product)   # [his test day finding 3]
        PackagingOutput.objects.create(
            task=aria.task, approved_image=approved_image,
            spec_sheet={
                "backend": "container",
                "container_profile": asdict(profile),
                cc.PROFILE_SCHEMA: versioned,
                # §BH64(b): the pipeline's first proposal is stamped with
                # the profile it was proposed from, like every later write.
                cc.ZONES_SCHEMA: cc.zone_set_record(
                    proposed, versioned, confirmation_state="PROPOSED",
                    **({"exclusions": [dict(scc.COLLAR_ZONE_EXCLUSION)]}
                       if contract is not None else {})),
                "product_name": _name,
                "product_name_source": _name_source,
                # §BH65(b)1: what the product IS, from its own record, beside its name.
                _fh.SPEC_KEY: _fh.descriptor_from_record(
                    getattr(product, "product_type", None)),
                # [his answers after 122 was redrawn, (1)] the product record's SKU, else the one he typed
                "sku": aria.task.sku_on_record(),
                **extras,
                # §BH71 PART 1: the concept's traced outline, read once, by the picture's sha256
                **({"container_outline_trace/1.0": outline_trace} if outline_trace is not None else {}),
                # [his go of 2026-10-02] the concept's design map, read once, by the picture's sha256
                **({_dm.SCHEMA: design_map} if design_map is not None else {}),
                # [the owner's finding on design 119, 2026-10-03] … and its shapes, traced once when it was checked
                **({_dm.SHAPES_SCHEMA: traced_shapes} if traced_shapes else {}),
            },
        )
        aria.task.status = "awaiting_container_profile"
        aria.task.save()
        aria.log("ARIA: reached container-profile gate — confirm the container "
                 "structure before reconstruction")

    def review_sections(self, task) -> list[dict]:
        """Container SPECIFICATIONS for the Review Board (target-specific)."""
        output = task.current_output()
        spec = (output.spec_sheet if output else None) or {}
        rows = _selection_rows(task)
        rows.extend(_fact_hygiene_rows(spec))
        rows.extend(_reconstruction_2c2e_rows(spec))
        rows.extend(_readiness_read_rows(task, output, spec))     # §BH50(g)(4)
        rows.extend(_score_rows(spec))                            # [his answer 3 of 2026-10-02]
        rows.extend(_tray_rows(spec))                             # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5)]
        rows.extend(self._spec_rows(task, spec))
        return rows

    def _spec_rows(self, task, spec) -> list[dict]:
        p = spec.get("container_profile") or {}
        colors = spec.get("colors") or {}
        rows = []
        if p.get("archetype"):
            rows.append({"label": "Container", "value": p["archetype"].title()})
        if p.get("variant"):
            rows.append({"label": "Variant", "value": str(p["variant"])})
        if p.get("height_mm") and p.get("width_mm"):
            rows.append({"label": "Size",
                         "value": f'{p["width_mm"]} × {p["height_mm"]} mm'})
        if p.get("cap_style"):
            # §BH70(1), item 21 of the list the owner was sent: the closure in its form's own words — "Closure: Clasp" on
            # a compact, where the board said "Cap: clasp"
            rows.append({"label": "Closure", "value": _closure_words(p.get("archetype"), p["cap_style"])})
        palette = spec.get("container_palette/1.0")
        if palette:
            # §BH50(d): the board shows the palette the artefact is drawn with, from the composer's record, where it
            # showed spec['colors'] — a hard-coded dict whose cap #B76E79 the artefact never draws. spec['colors']
            # itself is left as it is: the native handoff recomposes from it (§BH48(d)'s queued observation)
            for r in palette.get("rows") or []:
                rows.append({"label": f'Colour · {r["name"]}',
                             "value": f'{r["hex"]} · {r["role"] or "no role"} · {r["source"]}'})
        else:
            part = (_declared.closure_part_of(p["archetype"]).capitalize() if _declared.is_known(p.get("archetype"))
                    else "Closure")
            for key, lab in (("body", "Body colour"), ("cap", f"{part} colour")):
                if colors.get(key):
                    rows.append({"label": lab, "value": str(colors[key])})
        if spec.get("product_name"):
            rows.append({"label": "Product", "value": spec["product_name"]})
        if spec.get("sku"):
            rows.append({"label": "SKU", "value": spec["sku"]})
        rows.extend(_contract_rows(spec))
        rows.extend(_reconstruction_rows(spec))
        rows.extend(_handoff_rows(spec))
        return rows


def _closure_words(archetype, key) -> str:
    """§BH70(1), item 21: a closure key in its form's own label ("clasp" → "Clasp"); the key as it is when the form
    does not declare it."""
    if _declared.is_known(archetype):
        for known, label in _declared.closures_of(archetype):
            if known == key:
                return label
    return str(key)


def _uploaded_paths(task) -> dict:
    """{kind: filesystem_path} for the task's uploaded references (last upload
    per single-use kind wins). Empty when there are none (B4b)."""
    out = {}
    try:
        refs = list(task.references.all())
    except Exception:  # noqa: BLE001
        return out
    for r in refs:
        try:
            path = r.image.path
        except (ValueError, NotImplementedError):
            continue
        if os.path.exists(path):
            out[r.kind] = path
    return out


def _profile_from_confirmed(confirmed: dict) -> ContainerProfile:
    allowed = {"archetype", "variant", "height_mm", "width_mm", "neck_ratio",
               "cap_style", "label_zone", "decoration_zone"}
    kw = {k: v for k, v in (confirmed or {}).items() if k in allowed and v is not None}
    # §BH61(a): a CONFIRMED profile with no archetype is a stop, not a bottle. Without this the
    # dataclass raises a bare TypeError naming a positional argument; the owner's rule is that the
    # refusal says which value was missing and where it was looked for.
    kw["archetype"] = _declared.resolve(
        kw.get("archetype"), looked_in=["the confirmed container_profile record"])
    return ContainerProfile(**kw)


#: 2C-2E §12: back sections come from the VERIFIED product record; anything
#: unavailable carries the bounded marker — never pseudo-text. The markers
#: surface in the readiness report and block production authority.
#:
#: §AV1 — that last sentence was FALSE from 2026-07-27 to 2026-08-21. The
#: markers were persisted under ``readiness["content"]`` (below) but
#: ``container_production_readiness._SECTIONS`` did not declare ``content``, so
#: the reader dropped them and unverified INGREDIENTS copy did not block
#: anything. It is true now, and ``UndeclaredReadinessSectionTests`` is what
#: keeps it true. Recorded rather than quietly corrected, because a comment
#: that silently becomes accurate teaches nobody why it was wrong.
CONTENT_VERIFICATION_REQUIRED = "CONTENT_VERIFICATION_REQUIRED"


#: The owner's VQ-2 logo confirmation. Read for the asset paths it actually
#: names — never for a path this module would like to exist.
VQ2_LOGO_RECORD = os.path.join(
    "docs", "visual_quality", "vq2", "vq2_authoritative_bbrose_logo.json")


def _owner_confirmed_logo_assets() -> list[str]:
    """Absolute paths of the logo files the owner confirmed, or an empty
    list when no confirmation record is on disk. An empty list means the
    measurement records the confirmation as unknown, which is the truth —
    it must never be read as "not confirmed".

    [THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    switch the mark to it so gold foil can print." The approved vector master is read from ITS approval record
    (``docs/brand/mark/approval.json``, apps/ire/brand_mark.py) and joins this list only when that record holds; the
    VQ2 record above is a different drawing and never approves the master.]"""
    import json

    from django.conf import settings as _settings

    from apps.ire import brand_mark as _brand_mark
    approved = _brand_mark.confirmed_assets()
    try:
        with open(os.path.join(_settings.BASE_DIR, VQ2_LOGO_RECORD)) as fh:
            record = json.load(fh)
    except (OSError, ValueError):
        return approved
    if not (record.get("owner_confirmation") or {}).get("codes"):
        return approved
    named = [record.get(k) for k in
             ("canonical_ai", "canonical_pdf", "preview_png")]
    return [os.path.join(_settings.BASE_DIR, p) for p in named if p] + approved


def lid_shade(product) -> dict | None:
    """[his answer of 2026-09-29 to the §BH71 report, (4): "the lid drawing draws the shade name my brief asks for"]
    the shade a lid draws: the product record's own ONE shade (``Product.shade_names``, §BH55(a)), its English and
    its Arabic as held, and whether its Arabic is marked the executor's and unconfirmed (``AR_UNCONFIRMED``). None
    where the record holds no shade, or more than one — a palette's shades are its pans', not its lid's — and a
    test's stand-in that is not a saved row."""
    from apps.core.models import AR_UNCONFIRMED
    rows = [r for r in (getattr(product, "shade_names", None) or []) if isinstance(r, dict)
            and ((r.get("en") or "").strip() or (r.get("ar") or "").strip())]
    if len(rows) != 1:
        return None
    row = rows[0]
    return {"en": (row.get("en") or "").strip(), "ar": (row.get("ar") or "").strip(),
            "ar_unconfirmed": row.get("ar_source") == AR_UNCONFIRMED,
            "source": "Product.shade_names — the record's one shade, as held"}


#: [his answer of 2026-09-29, (4)] the lid drew the record's shade with an Arabic the executor wrote and nobody has
#: confirmed — marked beside Approve while the record says so, never a block
SHADE_ARABIC_UNCONFIRMED = "CONTAINER_SHADE_ARABIC_UNCONFIRMED"


def shade_codes(doc) -> list[str]:
    """The readiness codes of the shade a lid drew — read off the document composed, never off its inputs: its Arabic
    marked the executor's and unconfirmed is ``SHADE_ARABIC_UNCONFIRMED`` with the words drawn; none otherwise."""
    face = (doc.metadata.get("concept_front") or {}).get("face") or {}
    shade = face.get("shade") or {}
    if shade.get("ar") and shade.get("ar_unconfirmed"):
        return ["%s: the shade's Arabic %r was written by the executor and nobody has confirmed it — "
                "Product.shade_names" % (SHADE_ARABIC_UNCONFIRMED, shade["ar"])]
    return []


def _owner_copy(product) -> dict:
    """§BH54(b) (k) 4 — the pieces the OWNER typed into this product through his channel
    (apps/dashboard/owner_channel.py): ``{heading: words}``, each the newest act for its piece and only while
    its words still hash to the sha256 that act names. The ONE source of reserved copy on the production path:
    nothing here is written by the executor (§AE2(b)); a piece he has not typed stays
    CONTENT_VERIFICATION_REQUIRED and blocks; a product that is not a saved row (a test's stand-in) has no
    channel to read. Runs of whitespace are collapsed to one space — the panel's own normalisation
    (``back_panel.layout``) — so a line break he typed never reaches a ``drawString`` as a control character;
    the stored act keeps exactly what he typed."""
    if getattr(product, "pk", None) is None:
        return {}
    from apps.dashboard import owner_channel
    return {heading: " ".join(words.split())
            for heading, words in owner_channel.written_copy(product).items()}


#: [his answers after 117 was redrawn on his rules, 2026-10-02 (a18911a), answer 3: "My brief's back copy counts as my
#: copy for acceptance."] the slot a heading of his brief's back copy fills, by the words it is headed with
BRIEF_BACK_SLOTS = {"DIRECTIONS": ("how to use", "directions", "usage", "to use"),
                    "INGREDIENTS": ("ingredients", "inci", "composition"),
                    "WARNINGS": ("warnings", "warning", "caution", "precautions"),
                    "DESCRIPTION": ("description", "about"),
                    # [his answers after the fixes for design 122, (2)] his brief's size (``back_copy``)
                    "NET CONTENT": ("net content", "net contents", "net weight", "net wt", "contents")}
#: the heading his brief's size is drawn under on a container's back
NET_CONTENT_HEADING = "Net content"


def back_copy(task) -> dict:
    """[His answers after the fixes for design 122, 2026-10-08, (2): "the drawing must always print my brief's size (60
    ml), never the picture's text. Confirm that holds for every design."] His brief's back copy
    (``concept_design_map.brief_back_copy``), and his brief's size (``brief_size``) its own piece under "Net content"
    where the back copy states none — so every container's back prints his size, in his words."""
    from apps.pipeline.services import concept_design_map as dm
    brief = brief_text(task)
    back = dm.brief_back_copy(brief)
    size = dm.brief_size(brief)
    if size is None or any(dm.size_stated(sec.get("text")) is not None for sec in back["sections"]):
        return back
    return dict(back, sections=list(back["sections"]) + [{"heading": NET_CONTENT_HEADING, "text": size[0],
                                                          "source": size[1]}])


def net_content(task) -> str | None:
    """[His answers after the fixes for design 122, (2).] The size a container's front prints: his brief's
    (``brief_size``), else the product record's as held (§BH67(c)2, ``front_hierarchy.net_content_for``), else none."""
    from apps.ire.front_hierarchy import net_content_for
    from apps.pipeline.services import concept_design_map as dm
    size = dm.brief_size(brief_text(task))
    if size is not None:
        return size[0]
    return net_content_for(getattr(task, "product", None))


#: [his final goal, 2026-10-05 (transcribed at 32e9aaf), A: "Go: container back labels are trilingual too (English,
#: Spanish, Arabic), translated per design."] the back's English, translated once at the profile step and kept with the
#: words it translated (a back whose English is as before keeps its translations, nothing spent); a piece of his
#: English the back carries without its Spanish or its Arabic holds Gate 2 by name
CONTAINER_TRANSLATIONS_KEY = "container_translations/1.0"
CONTAINER_LABEL_NOT_TRILINGUAL = "CONTAINER_LABEL_NOT_TRILINGUAL"
#: [his final goal, 2026-10-05, C5: "Only if it still doesn't fit, STOP and offer: ... or fewer languages"; A: "container
#: back labels are trilingual too"] the languages a container's back carries (his choice of the stop's offers), the offers
#: measured to hold it where three cannot stand, and the profile he confirmed, kept so his choice can make it again
LABEL_LANGUAGES = ("en", "es", "ar")
CONTAINER_LABEL_LANGUAGES_KEY = "container_label_languages"
CONTAINER_LABEL_OFFERS_KEY = "container_label_offers/1.0"
CONTAINER_CONFIRMED_KEY = "container_confirmed_profile"


def label_languages(spec: dict) -> tuple:
    """The languages a container's back carries: his choice of the stop's offers, else all three."""
    chosen = (spec or {}).get(CONTAINER_LABEL_LANGUAGES_KEY)
    return tuple(chosen) if chosen else LABEL_LANGUAGES


def confirmed_profile_of(spec: dict) -> dict:
    """The profile he confirmed at the shape step, as the confirm door handed it on — kept on the record since C5c;
    for a container drawn before, read back from its confirmed profile record's fields."""
    kept = (spec or {}).get(CONTAINER_CONFIRMED_KEY)
    if kept:
        return dict(kept)
    from apps.pipeline.services import container_contract as cc
    fields = ((spec or {}).get(cc.PROFILE_SCHEMA) or {}).get("fields") or {}
    out = {}
    for key, field in (("archetype", "archetype"), ("variant", "variant"), ("cap_style", "cap_type")):
        value = (fields.get(field) or {}).get("value")
        if value:
            out[key] = value
    for key in ("height_mm", "width_mm", "depth_mm"):
        value = (fields.get("body_" + key) or {}).get("value")
        if value is not None:
            out[key] = float(value)
    return out


def back_label_offers(compose_again, english_sections, kept: dict | None, languages_now) -> list:
    """[His final goal, 2026-10-05, C5 + A] A container's back that cannot stand in its languages: each set of fewer
    languages (the carton's own, ``compose.FEWER_LANGUAGES``) its back holds — measured by composing the container again
    with that back (``compose_again(sections) -> Document``, nothing paid) and reading the back panel's own fit —
    ``[{"offer": "fewer_languages", "languages", "doc"}]``."""
    from apps.ire import back_panel as _back_panel
    from apps.ire.compose import FEWER_LANGUAGES
    out = []
    for subset in FEWER_LANGUAGES:
        if not set(subset) < set(languages_now):
            continue
        sections, _codes = trilingual_sections(english_sections, kept, languages=subset)
        doc = compose_again(sections)
        fit = (doc.metadata or {}).get(_back_panel.SCHEMA) or {}
        if fit.get("fits") is True:
            out.append({"offer": "fewer_languages", "languages": list(subset), "doc": doc})
    return out


def _save_label_offers(spec: dict, task_id: int, offers: list, why: list) -> None:
    """The offers drawn — each container's sheet as a picture, kept beside the design. A back that stopped with no
    smaller set it holds keeps an empty list (measured: none holds); a back that stands keeps none."""
    if not offers:
        if why:
            spec[CONTAINER_LABEL_OFFERS_KEY] = []
        else:
            spec.pop(CONTAINER_LABEL_OFFERS_KEY, None)
        return
    import tempfile

    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage

    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png
    kept = []
    with tempfile.TemporaryDirectory(prefix="container_offer_") as td:
        for o in offers:
            stem = "-".join(o["languages"])
            ai = emit_pdf_ai(o["doc"], os.path.join(td, stem + ".ai"))
            png = os.path.join(td, stem + ".png")
            row = {"offer": o["offer"], "languages": o["languages"], "why": why}
            if pdf_to_png(ai, png):
                with open(png, "rb") as f:
                    row["png"] = default_storage.save("containers/label_offer_task_%d_%s.png" % (task_id, stem),
                                                      ContentFile(f.read()))
            kept.append(row)
    spec[CONTAINER_LABEL_OFFERS_KEY] = kept
_SLOT_FIELD = {"DESCRIPTION": "description", "INGREDIENTS": "ingredients", "DIRECTIONS": "how_to_use",
               "WARNINGS": "warnings"}


def _slot_of(heading) -> str | None:
    words = str(heading or "").strip().rstrip(":").lower()
    return next((slot for slot, names in BRIEF_BACK_SLOTS.items() if words in names or words == slot.lower()), None)


def back_english(sections) -> dict:
    """The back's pieces that are translated: ``{field: his English}`` — description, ingredients, how to use,
    warnings, where his words give them (a piece still waiting on his words is not translated)."""
    out = {}
    for sec in sections or []:
        if sec.get("one_language"):
            continue                # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] a written piece set in
            #                         English only so the whole label stands: never sent to be translated
        field = _SLOT_FIELD.get(_slot_of(sec.get("heading")))
        text = " ".join(str(sec.get("text") or "").split())
        if field and text and text != CONTENT_VERIFICATION_REQUIRED and field not in out:
            out[field] = text
    return out


def translate_back(task, spec: dict, sections, log=None) -> None:
    """[His final goal, A.] The back's English translated into Spanish and Arabic — ONE paid call, the carton label's
    own (``panel_translate.translate_panel_info``) — kept on the design's record with the English it translated; a back
    whose English is as before keeps its translations and nothing is spent."""
    english = back_english(sections)
    if not english:
        return
    kept = spec.get(CONTAINER_TRANSLATIONS_KEY) or {}
    if kept.get("english") == english and kept.get("translations"):
        return
    from apps.pipeline.services.panel_translate import translate_panel_info
    spec[CONTAINER_TRANSLATIONS_KEY] = {"english": english,
                                        "translations": translate_panel_info(english, task=task, log=log)}


def trilingual_sections(sections, kept: dict | None, languages=LABEL_LANGUAGES) -> tuple[list, list]:
    """The back's sections in English, then Spanish, then Arabic — each language's pieces in his order, under their
    own headings; the Arabic carries no ingredients (INCI names are printed once, in Latin); Spanish ingredients that
    are the English's own words are printed once, under "INGREDIENTS / INGREDIENTES". ``(sections, codes)``: a piece of
    his English without its translation — CONTAINER_LABEL_NOT_TRILINGUAL, by language and piece. ``languages`` — [his
    final goal, C5c] the languages the back carries (his choice of a stopped back's offers); a language left out is his
    choice, never a code."""
    from apps.dielines.exporters.info_panel import _AR_LABELS, _ES_LABELS
    sections = [dict(s, lang="en", **({"fine": True} if _SLOT_FIELD.get(_slot_of(s.get("heading"))) in
                                      ("ingredients", "warnings") else {})) for s in sections or []]
    english = back_english(sections)
    if not english:
        return sections, []
    kept = kept or {}
    translations = (kept.get("translations") or {}) if kept.get("english") == english else {}
    out, codes = list(sections), []
    labels = {"es": _ES_LABELS, "ar": _AR_LABELS}
    for lang in ("es", "ar"):
        if lang not in languages:
            continue
        words_of = translations.get(lang) or {}
        for sec in sections:
            field = _SLOT_FIELD.get(_slot_of(sec.get("heading")))
            if field not in english or (lang == "ar" and field == "ingredients") or sec.get("one_language"):
                continue
            words = " ".join(str(words_of.get(field) or "").split())
            if not words:
                codes.append("%s:%s:%s" % (CONTAINER_LABEL_NOT_TRILINGUAL, lang, field))
                continue
            if lang == "es" and field == "ingredients" and words.lower() == english[field].lower():
                at = out.index(sec)                       # the English ingredients, headed in both languages
                out[at] = dict(sec, heading="%s / %s" % (str(sec["heading"]).rstrip(":"),
                                                         labels["es"]["ingredients"].rstrip(":")))
                continue
            out.append({"heading": labels[lang][field].rstrip(":"), "text": words, "lang": lang,
                        "source": "the system's translation of his English",
                        **({"fine": True} if field in ("ingredients", "warnings") else {})})
    return out, codes


#: [His review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL ... Every back label carries the full
#: set (description, ingredients, how to use, warnings, made in, net content, batch/exp, QR)."] the headings a piece is
#: drawn under where his words give none — each one ``_slot_of`` reads back to its piece, so it is translated as his are
WRITTEN_HEADINGS = {"description": "Description", "how_to_use": "How to use", "ingredients": "Ingredients",
                    "warnings": "Warnings"}
MADE_IN_HEADING = "Made in"
BATCH_HEADING = "Batch / EXP"
#: the form the written pieces are set in on this design's back (``label_copy.FORMS``) and whether its QR is drawn —
#: measured at the shape step, read by every drawing of the design after it
LABEL_FORM_KEY = "container_label_form/1.0"
_FIELD_SLOT = {field: slot for slot, field in _SLOT_FIELD.items()}


def label_about(task) -> str:
    """The words the label's missing pieces are written from: the product's name, its type and its brief's description
    of the product — never its styling (the brief's words from "Style:" on are left out)."""
    import re
    product = getattr(task, "product", None)
    brief = " ".join(str(getattr(task, "task_text", "") or "").split())
    kind = re.search(r"\[Container type:\s*([^\]]+)\]", brief)
    said = re.split(r"\bStyle\s*:|\bFront copy\s*:|\bBack copy\s*:|\[", brief)[0].strip()[:300]
    parts = [str(getattr(product, "name", "") or ""), str(getattr(product, "product_type", "") or ""), said,
             ("(%s)" % kind.group(1).strip()) if kind else ""]
    return " ".join(p for p in (" ".join(x.split()) for x in parts) if p)


def label_qr(task) -> str | None:
    """The address the label's QR code carries: the product record's own, else the brand's site — never invented."""
    product, brand = getattr(task, "product", None), getattr(task, "brand", None)
    for url in (getattr(product, "qr_url", None), getattr(brand, "website", None)):
        if url and str(url).strip():
            return str(url).strip()
    return None


def _says(sections, pattern) -> bool:
    import re
    return any(re.search(pattern, "%s %s" % (s.get("heading") or "", s.get("text") or ""), re.I)
               for s in sections or [])


def label_back(task, spec: dict | None, *, form: str | None = None, record_sections=None) -> dict:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (7).] A container's back with the FULL set: his brief's back
    copy and his size (``back_copy``) — or, on the dropper's sheet, the product record's sections
    (``record_sections``) — each piece neither gives taken from the product record's copy, else WRITTEN for the
    product's type (``label_copy``: read as kept, never paid for here), then where it is made, his size and the batch
    and expiry left blank for the filler. ``{"sections", "kept", "written", "made_in", "qr", "form",
    "batch_code_place"}`` — ``kept`` the back's translations read for the form its written pieces are set in."""
    from apps.pipeline.services import label_copy as lc
    spec = spec or {}
    form = form or (spec.get(LABEL_FORM_KEY) or {}).get("form") or lc.FULL
    back = back_copy(task)
    owner = _owner_copy(getattr(task, "product", None))
    if record_sections is not None:
        his, tail, extra = [dict(s) for s in record_sections], [], []
    else:
        from apps.pipeline.services import concept_design_map as dm
        n = len(dm.brief_back_copy(brief_text(task))["sections"])
        his, tail, extra = [dict(s) for s in back["sections"][:n]], [dict(s) for s in back["sections"][n:]], []
        for field in lc.FIELDS:                       # the product record's copy, where his brief gives none
            slot = _FIELD_SLOT[field]
            if field not in back_english(his) and owner.get(slot):
                extra.append({"heading": WRITTEN_HEADINGS[field], "text": owner[slot],
                              "source": "his copy for the product"})
    have = back_english(his + extra)
    missing = [f for f in lc.FIELDS if f not in have]
    about = label_about(task)
    # [his review, C (7)] a written piece left off for room where even the shortest form does not stand (``ensure_label``)
    dropped = set((spec.get(LABEL_FORM_KEY) or {}).get("dropped") or ())
    written = {f: t for f, t in lc.written_for(spec, about, missing).items() if f not in dropped}
    one = {"one_language": True} if lc.english_only(form) else {}
    pieces = {f: dict({"heading": WRITTEN_HEADINGS[f], "text": lc.shortened(f, written[f], form),
                       "source": lc.WRITTEN_SOURCE, "written": True}, **one) for f in written}
    if record_sections is not None:
        # the dropper's sheet: each piece the record has not given filled in place (its code stays — written copy is
        # never his copy for acceptance)
        for sec in his:
            field = _SLOT_FIELD.get(_slot_of(sec.get("heading")))
            if sec.get("text") == CONTENT_VERIFICATION_REQUIRED and field in pieces:
                sec.update(pieces.pop(field), heading=sec["heading"])
        size = net_content(task)
        for sec in his:
            if sec.get("text") == CONTENT_VERIFICATION_REQUIRED and _slot_of(sec.get("heading")) == "NET CONTENT" \
                    and size:
                sec.update(text=size, source="his brief's size")
        # a piece the system writes, left off for room, is not drawn at all — never its record's marker printed in its
        # place (its code stays on the record: written copy is never his copy for acceptance)
        gone = {f for f in dropped if f in lc.FIELDS}
        his = [sec for sec in his if not (sec.get("text") == CONTENT_VERIFICATION_REQUIRED and (
            _SLOT_FIELD.get(_slot_of(sec.get("heading"))) in gone
            or ("made_in" in dropped and str(sec.get("heading", "")).upper() == "MANUFACTURER")))]
    sections = his + extra + [pieces[f] for f in lc.FIELDS if f in pieces]
    made_in = None
    if not _says(sections + tail, r"\bmade in\b|\borigin\b") and not owner.get("MANUFACTURER") \
            and "made_in" not in dropped:
        made_in = lc.MADE_IN_PLACEHOLDER
        filled = next((s for s in sections if str(s.get("heading", "")).upper() == "MANUFACTURER"
                       and s.get("text") == CONTENT_VERIFICATION_REQUIRED), None)
        if filled is not None:
            filled.update(text="Made in %s" % made_in, source=lc.WRITTEN_SOURCE, written=True)
        else:
            sections.append({"heading": MADE_IN_HEADING, "text": made_in, "source": lc.WRITTEN_SOURCE,
                             "written": True})
    sections += tail
    if not _says(sections, r"\bbatch\b|\bexp\b|\blot\b") and "batch" not in dropped:
        sections.append({"heading": BATCH_HEADING, "text": lc.BATCH_EXP, "source": "left blank for the filler"})
    return {"sections": sections, "kept": _kept_for(spec, task, sections, form, record_sections), "form": form,
            "written": {f: written[f] for f in written}, "made_in": made_in, "qr": label_qr(task),
            "batch_code_place": back["batch_code_place"]}


def _kept_for(spec: dict, task, sections, form: str, record_sections) -> dict | None:
    """The back's translations for ``sections``: as kept where the English they translated is these sections'; where
    the written pieces are set shorter or in English only, the translations of the whole set read for that form — each
    written piece's translation shortened as its English is, a piece set in English only left out — never paid again."""
    from apps.pipeline.services import label_copy as lc
    kept = spec.get(CONTAINER_TRANSLATIONS_KEY)
    english = back_english(sections)
    if not kept or kept.get("english") == english or form == lc.FULL:
        return kept
    whole = label_back(task, dict(spec, **{LABEL_FORM_KEY: {"form": lc.FULL}}), form=lc.FULL,
                       record_sections=record_sections)
    if kept.get("english") != back_english(whole["sections"]):
        return kept
    written = set(whole["written"])
    adapted = {lang: {f: (lc.shortened(f, t, form) if f in written else t) for f, t in (words or {}).items()
                      if f in english}
               for lang, words in (kept.get("translations") or {}).items()}
    return {"english": english, "translations": adapted}


def ensure_label(aria, spec: dict, zones, body_width_mm, *, methods_record=None, packaging: bool = False,
                 record_sections=None) -> dict:
    """[His review of 127, 130, 131 and 132, 2026-10-15, C (7).] At the shape step, the one place the back's copy is
    paid for: the pieces his words and the product record leave empty written once for the product's type
    (``label_copy.ensure`` — a fidelity call, kept), the whole back translated once (``translate_back``), and the form
    the written pieces are set in MEASURED on the back's own layout (``compose_information_panels`` at its floor, its
    QR with it): the richest form at which the whole label stands — its QR given up only where no form stands with it
    — kept on the record (LABEL_FORM_KEY); each written piece shown beside Approve. Never a stop: where no form stands,
    the shortest is kept and the back's own fit says so as before."""
    from apps.ire.compose_container import compose_information_panels
    from apps.pipeline.services import label_copy as lc
    task = aria.task
    log = getattr(aria, "log", None)
    whole = label_back(task, dict(spec, **{LABEL_FORM_KEY: {"form": lc.FULL}}), form=lc.FULL,
                       record_sections=record_sections)
    missing = [f for f in lc.FIELDS if f in whole["written"]]
    if missing:
        lc.ensure(spec, label_about(task), missing, log=log)
        whole = label_back(task, dict(spec, **{LABEL_FORM_KEY: {"form": lc.FULL}}), form=lc.FULL,
                           record_sections=record_sections)
    translate_back(task, spec, whole["sections"], log=log)
    # the written pieces' translations, where the back's translation was made: else they are set in English only — the
    # system's own copy is never a piece missing its languages (his pieces keep their codes as before)
    kept = spec.get(CONTAINER_TRANSLATIONS_KEY) or {}
    translated = kept.get("english") == back_english(whole["sections"]) and all(
        all((kept.get("translations") or {}).get(lang, {}).get(f) for lang in ("es", "ar")
            if lang in label_languages(spec) and not (lang == "ar" and f == "ingredients"))
        for f in whole["written"])
    forms = (lc.FORMS if translated else lc.ENGLISH_ONLY) if whole["written"] else (lc.FULL,)
    qr = whole["qr"]
    chosen = None
    for with_qr in ((True, False) if qr else (False,)):
        for form in forms:
            back = label_back(task, dict(spec, **{LABEL_FORM_KEY: {"form": form}}), form=form,
                              record_sections=record_sections)
            sections, _codes = trilingual_sections(back["sections"], back["kept"], languages=label_languages(spec))
            _groups, fit = compose_information_panels(
                sections, zones, body_width_mm, 0.0, 0.0, methods_record=methods_record, heading_role="heading",
                copy_role="body", packaging=packaging, qr_url=qr if with_qr else None,
                doc_metadata={"typography_surface": "apps/ire/compose_container.py::compose_container_graph"})
            if fit.get("fits") is True:
                chosen = {"form": form, "qr": with_qr}
                break
        if chosen is not None:
            break
    if chosen is None:
        # [his review, C (7)] where even the shortest form does not stand, the written pieces are left off one at a
        # time (``label_copy.DROP_ORDER``) until it does — his own pieces never; the system's copy never stops a back
        last = lc.TINY_EN if whole["written"] else lc.FULL
        order = [p for p in lc.DROP_ORDER if p in whole["written"] or (p == "made_in" and whole["made_in"])
                 or (p == "batch" and any(s.get("heading") == BATCH_HEADING for s in whole["sections"]))]
        for k in range(1, len(order) + 1):
            trial = {"form": last, "qr": False, "dropped": order[:k]}
            back = label_back(task, dict(spec, **{LABEL_FORM_KEY: trial}), record_sections=record_sections)
            sections, _codes = trilingual_sections(back["sections"], back["kept"], languages=label_languages(spec))
            _groups, fit = compose_information_panels(
                sections, zones, body_width_mm, 0.0, 0.0, methods_record=methods_record, heading_role="heading",
                copy_role="body", packaging=packaging,
                doc_metadata={"typography_surface": "apps/ire/compose_container.py::compose_container_graph"})
            if fit.get("fits") is True:
                chosen = trial
                break
        if chosen is None:
            chosen = {"form": last, "qr": False, "dropped": order, "stands": False}
    spec[LABEL_FORM_KEY] = dict(chosen, schema_version=LABEL_FORM_KEY)
    lc.show(spec, {f: t for f, t in whole["written"].items() if f not in (chosen.get("dropped") or ())},
            made_in=whole["made_in"] if "made_in" not in (chosen.get("dropped") or ()) else None,
            qr=qr if qr and qr == getattr(getattr(task, "brand", None), "website", None) else None,
            qr_drawn=chosen["qr"], form=chosen["form"], dropped=chosen.get("dropped") or ())
    return label_back(task, spec, record_sections=record_sections)


def _back_sections_from_record(product, brief_back: dict | None = None) -> tuple[list[dict], list[str]]:
    """[§BH54(b) (k) 4 and his answer 3 of 2026-10-02.] The back's sections: each piece his copy channel holds, or else
    the piece his brief's back copy gives (``brief_back``: ``concept_design_map.brief_back_copy``) — his copy for
    acceptance, said by its ``source`` — or else the marker and its code; the brief's pieces no slot names after them."""
    name = getattr(product, "name", "") or ""
    sections, codes = [], []
    written = _owner_copy(product)   # §BH54(b) (k) 4: his words, or nothing
    briefed, extra = {}, []
    for sec in (brief_back or {}).get("sections") or []:
        slot = next((s for s, words in BRIEF_BACK_SLOTS.items() if str(sec["heading"]).strip().lower() in words), None)
        if slot is not None and slot not in briefed:
            briefed[slot] = sec
        else:
            extra.append(sec)

    def add(heading, text, verified):
        if not verified and heading in briefed:
            # [his answer 3 of 2026-10-02] his brief's words for the piece: his copy, said so
            sections.append({"heading": heading, "text": briefed[heading]["text"],
                             "source": briefed[heading]["source"]})
            return
        sections.append({"heading": heading,
                         "text": text if verified
                         else CONTENT_VERIFICATION_REQUIRED})
        if not verified:
            codes.append(f"{CONTENT_VERIFICATION_REQUIRED}:"
                         f"{heading.lower().replace(' ', '_')}")
    add("PRODUCT", name, bool(name))
    add("DESCRIPTION", written.get("DESCRIPTION", ""), "DESCRIPTION" in written)
    add("INGREDIENTS", written.get("INGREDIENTS", ""), "INGREDIENTS" in written)
    add("DIRECTIONS", written.get("DIRECTIONS", ""), "DIRECTIONS" in written)
    add("WARNINGS", written.get("WARNINGS", ""), "WARNINGS" in written)
    add("MANUFACTURER", written.get("MANUFACTURER", ""), "MANUFACTURER" in written)
    # §AK4/WI-3H — this line read `add("NET CONTENT", "30 ml / 1.01 fl.
    # oz.", True)` until 2026-08-20. Six of the seven sections were
    # honest about their provenance; this one was a MANDATORY QUANTITY
    # DECLARATION hardcoded to a literal and passed `verified=True`, so
    # it emitted as copy, carried no code, and was indistinguishable in
    # the record from a value someone supplied. There is no field to
    # read it from: `volume_ml`, `net_content`, `fill_volume` and
    # `capacity_ml` do not exist anywhere in `apps/`, so nothing was
    # ever bound and this is not a stale binding. A quantity
    # declaration is a claim about the product and is reserved under
    # §AE2(b), so it is not replaced with a different number — it joins
    # its five neighbours and becomes OWNER_INPUT_MANIFEST row B5.
    # [§BH54(b) (k) 4, 2026-09-19: the field this comment says does not exist
    # now does — the owner's copy channel. The declaration is HIS words,
    # carrying his identity, the time and their sha256, or it is the marker;
    # it is never a literal again.]
    add("NET CONTENT", written.get("NET CONTENT", ""), "NET CONTENT" in written)
    sections.extend(extra)            # [his answer 3] his brief's pieces no slot names ("Made in UAE"), his copy too
    return sections, codes


def _dm_back(task) -> dict:
    """[His answer 3 of 2026-10-02.] His brief's back copy, read — and his brief's size with it (``back_copy``)."""
    return back_copy(task)


def brand_palette_systems(task) -> list:
    """The ColorSystems ``_brand_palette`` reads, in the order it reads them — ``[(system, its swatches), ...]``: the
    product's own first, then every canonical one of the brand. [The owner's answer to the UI directions of
    2026-09-25 (his pick: the design page is C's — "pick an element and try colours and faces from a library that
    stays open"): the design loop offers these swatches and names each by its system, so the colours it offers are
    exactly the ones the composer's colour sources read — one reading, never a second list.]"""
    from apps.core.models import STATUS_CANONICAL, ColorSystem
    systems = []
    own = getattr(getattr(task, "product", None), "color_system", None)
    if own is not None:
        systems.append((own, own.palette or []))
    for system in ColorSystem.objects.filter(brand_id=getattr(task, "brand_id", None),
                                             status=STATUS_CANONICAL).order_by("id"):
        systems.append((system, system.palette or []))
    return systems


def _brand_palette(task):
    """§BH65(b)2 — the brand's OWN colour record: the product's ColorSystem first, then every canonical one.
    Returned as the swatch dicts the brand wrote (`{role, name, hex, pantone, usage}`)."""
    swatches = []
    for _system, palette in brand_palette_systems(task):
        swatches.extend(palette)
    return swatches


def face_drawn_boxes(doc) -> tuple:
    """§BH67(d)2 / (e): THE LAYOUT MEASURE's drawn half — ``(surface_mm, {kind: [x0, y0, x1, y1]})``: each face
    element's box in the DRAWN file, as fractions of the surface, read off the drawn nodes (the name and Arabic runs
    at their emitted advance widths). [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the
    block headed "Before I start testing"): "The lid is missing the concept's rule, ring and radial lines." Moved
    here unchanged from ``reconstruct_container``, which calls it where the reading stood, so the measure can be
    read without the database; and the concept's rule is read beside its window and its ring.]"""
    from apps.ire.back_panel import MM_PER_PT as _MM_PER_PT
    from apps.ire.compose_container import FACE_RULE, _leaf_box
    from apps.ire.text_metrics import resolve_metric_faces, text_width_mm
    _face_rec = (doc.metadata.get("concept_front") or {}).get("face") or {}
    _zone_box = (_face_rec.get("concept_layout") or {}).get("surface_mm")
    _metric = resolve_metric_faces(doc.metadata)
    _drawn = {}
    if _zone_box:
        _zx, _zy, _zw, _zh = _zone_box

        def _frac(x0, y0, x1, y1):
            return [round((x0 - _zx) / _zw, 4), round((y0 - _zy) / _zh, 4), round((x1 - _zx) / _zw, 4),
                    round((y1 - _zy) / _zh, 4)]
        _placed = _face_rec.get("placed") or {}
        if "mark" in _placed:
            _mx, _my, _mw, _mh = _placed["mark"]["box"]
            _drawn["mark"] = _frac(_mx, _my, _mx + _mw, _my + _mh)
        for _kind, _prefix in (("name", "product-name-hero"), ("name_ar", "product-name-ar")):
            _runs = [n for n, _ in doc.walk() if getattr(n, "type", "") == "text"
                     and (n.name or "").startswith(_prefix) and not (_prefix == "product-name-hero"
                                                                     and (n.name or "").endswith("-ar"))]
            _boxes = []
            for _r in _runs:
                _size_mm = _r.size_pt * _MM_PER_PT
                _txt = _r.text.upper() if _r.text_case == "upper" else _r.text
                _label = (_metric.get(_r.font) or _metric.get("arabic" if _kind == "name_ar" else "display")
                          or (None,))[0]
                _w = text_width_mm(_txt, _size_mm, _label) + (_r.tracking_em or 0.0) * _size_mm * max(
                    0, len(_txt) - 1)
                _x0 = _r.x - _w / 2.0 if _r.align == "center" else (_r.x - _w if _r.align == "right" else _r.x)
                from apps.ire.container_brand_usage import text_ink_top
                _boxes.append((_x0, text_ink_top(_r.y, _r.size_pt), _x0 + _w, _r.y + _size_mm * 0.22))
            if _boxes:
                _drawn[_kind] = _frac(min(b[0] for b in _boxes), min(b[1] for b in _boxes),
                                      max(b[2] for b in _boxes), max(b[3] for b in _boxes))
        # [the owner's second answer of 2026-09-25: the concept's rule, read beside its window and its ring]
        for _kind, _name in (("window", "window-frame"), ("ring", "frame-ring"), ("rule", FACE_RULE)):
            _node = next((n for n, _ in doc.walk() if (n.name or "") == _name), None)
            _b = _leaf_box(_node) if _node is not None else None
            if _b:
                _drawn[_kind] = _frac(_b[0], _b[1], _b[0] + _b[2], _b[1] + _b[3])
        # the motif: the union of its drawn leaves, wherever the face put it (inside its window, or its region)
        _motif = next((n for n, _ in doc.walk() if (n.name or "") in ("motif-window", "motif-field", "motif-edge")),
                      None)
        def _leaf_boxes(node):
            kids = getattr(node, "children", None)
            if kids is not None and getattr(node, "type", "") == "group":
                return [b for k in kids for b in _leaf_boxes(k)]
            b = _leaf_box(node)
            return [b] if b else []
        _leaves = _leaf_boxes(_motif) if _motif is not None else []
        if _leaves:
            _drawn["motif"] = _frac(min(b[0] for b in _leaves), min(b[1] for b in _leaves),
                                    max(b[0] + b[2] for b in _leaves), max(b[1] + b[3] for b in _leaves))
    return _zone_box, _drawn


# ---------------------------------------------------------------------------------------------------------------------
# ONE DERIVATION, TWO CALLERS. [The owner's goal of 2026-09-25, "THE UI, DESIGNED THIS TIME", rule (d): "The library
# is usable WHILE designing, not a separate trip." — and his pick for the design page, C's: "pick an element and try
# colours and faces from a library that stays open".] What `reconstruct_container` hands the container composer is
# derived by the functions below, moved out of it unchanged, so the design loop (apps/dashboard/exploration_render.py)
# draws a face from exactly the inputs production draws it from. They READ the task's rows and the output's spec sheet
# and WRITE NOTHING: every record production persists is appended to `records` — ("set", key, value) or
# ("drop", key, None) — in the order it was made, and only `reconstruct_container` writes them onto the spec sheet
# (`_write_records`), in a `finally`, so a run that fails part-way leaves on the sheet exactly the records it left
# before the move. The derivation saves nothing, logs nothing and writes no file. The vision read is a parameter:
# production's `cached_or_read` reads, and SPENDS, when the concept picture has not been read; the loop's reader never
# does. (Drawing is the composer's own business — it may rasterise the approved mark in a temporary directory to
# measure its band, as it does for production.)
# ---------------------------------------------------------------------------------------------------------------------


def _write_records(spec: dict, records: list) -> None:
    """Write a derivation's records onto ``spec`` in the order they were made — the writes ``reconstruct_container``
    made inline before the derivation moved out of it."""
    for op, key, value in records:
        if op == "drop":
            spec.pop(key, None)
        else:
            spec[key] = value


def _turn_colour(colors: dict, sources: dict, turned: dict, key: str) -> None:
    """The design loop's colour on one composer key — ``turned[key]`` is ``(hex, the words that name it)`` — set where
    production sets that key. Never reached on a production call (no ``turned``)."""
    if key not in turned:
        return
    hx, words = turned[key]
    if key == "motif":
        colors[key], sources[key] = [hx], [words]
    else:
        colors[key], sources[key] = hx, words


def _composer_inputs(task, output, spec: dict, *, records: list, colours: dict | None = None) -> dict:
    """WHAT EVERY CONTAINER COMPOSER IS HANDED before the form's own branch — the verified variation, the concept
    image, the visual graph, the colours and the record each came from, the zones, the name, the motif spec, the house
    mark, the transparency and the production methods — moved here unchanged from ``reconstruct_container``. Reads
    ``spec``, writes nothing: its records go to ``records`` (see the block above).

    ``colours`` is the design loop's and None on every production call: ``{key: (hex, words)}`` for the keys the
    composer paints a face with — ``cap`` (a plan form's lid face), ``ink``, ``rule``, ``ring``, ``motif`` — each set
    where production sets that key, so what production derives from it follows: the lid's ground is set before the
    motif's colours are chosen against it and before the window's centre is taken from it (``_front_plan``)."""
    from apps.pipeline.services import container_visual_graph as cvg
    from apps.pipeline.services.flat_artwork import dominant_color_hex

    # 2B-2 slice 1: resolve + verify the EXACT approved variation (fail closed
    # — the resume wrapper turns SelectedVariationIdentityError into the stable
    # refusal code and returns to the gate; the direction is never substituted).
    resolved = cvg.resolve_selected_variation_identity(task, output)
    records.append(("set", cvg.IDENTITY_SCHEMA, resolved["identity"]))

    # User uploads (Phase B4b) are preferred where applicable.
    uploads = _uploaded_paths(task)

    # approved concept image (colour source), best-effort
    concept_path = None
    approved = output.approved_image
    if approved and approved.image_file:
        try:
            concept_path = approved.image_file.path
        except (ValueError, NotImplementedError):
            concept_path = None

    # 2B-2 slice 1: derive the deterministic selected-concept visual graph
    # (no provider) from the verified variation + local image analysis.
    visual_graph = cvg.build_visual_graph(
        task, output, spec.get("container_profile/1.0") or {},
        resolved["structured"], concept_path)
    records.append(("set", cvg.SCHEMA, visual_graph))

    # reference shown on the sheet: an uploaded container photo if present,
    # else the approved concept render (TEMPORARY_VISUAL_REFERENCE_ONLY — never
    # placed as printable artwork).
    ref_path = uploads.get("container") or concept_path
    # colour sampled from the approved concept (the actual design), else ref.
    color_src = concept_path or ref_path
    body = dominant_color_hex(color_src) if color_src else _DEFAULT_BODY_HEX
    colors = {"body": body, "cap": _DEFAULT_CAP_HEX}
    # 2B-3V-CORR-4: the CONFIRMED profile's concept-seeded colour fields are
    # the selected concept's own palette — an explicit hex recorded there
    # (e.g. the blush cap "#F2C4CE") beats the generic gold default and the
    # whole-image median. Concept authority only; absent hexes change nothing.
    import re as _re
    _pf = (spec.get("container_profile/1.0") or {}).get("fields") or {}

    def _profile_hex(field_name):
        m = _re.search(r"#[0-9A-Fa-f]{6}",
                       str((_pf.get(field_name) or {}).get("value") or ""))
        return m.group(0).upper() if m else None

    cap_hex = _profile_hex("cap_color")
    if cap_hex:
        colors["cap"] = cap_hex
    body_hex = _profile_hex("body_base_color")
    colors["product"] = body_hex or cap_hex or "#F2C4CE"

    # §BH65(b)2 — "The lid takes the detailing colour as its field colour. Fix it, and say which record each
    # colour should come from." A form drawn in PLAN shows its LID FACE, and a lid face is ground, not closure:
    # it never takes `_DEFAULT_CAP_HEX`, which is the flat stand-in for the brand's Metallic swatch — "Caps,
    # closures, foil detail". Closure caps (forms drawn in ELEVATION) are unchanged. See colour_sources.py.
    from apps.pipeline.targets.container import colour_sources as _cs
    _archetype = (spec.get("container_profile/1.0") or {}).get("archetype")
    _sources = {
        "body": ("measured from the approved concept image" if color_src
                 else "no concept image — the body default `_DEFAULT_BODY_HEX`"),
        "product": ("the concept's own `body_base_color` sentence — its first hex" if body_hex
                    else "the concept's own `cap_color` sentence — its first hex" if cap_hex
                    else "the Blush default — the brand ColorSystem's Primary \"Main surfaces, hero cartons\""),
    }
    # §BH67 HARD STOP — "a finish or colour applied that nothing specified". The body is the concept's own words
    # before a measurement of its image (task 91 measured `#958879`, the shadowed sidewall, where the words say Warm
    # Cream); the TYPE and the MOTIF print in colours a record names — the concept's words, else the brand swatch
    # whose usage the brand wrote for the job — never the composer's stand-ins. See colour_sources.py.
    _palette = _brand_palette(task)
    _structured_colours = resolved.get("structured") if isinstance(resolved, dict) else None
    _body_words, _body_words_source = _cs.body_colour(_structured_colours, _palette)
    if _body_words:
        colors["body"], _sources["body"] = _body_words, _body_words_source
    elif body_hex:
        # [his test day finding 3, 2026-09-30, design 117: the whole picture's dominant colour, backdrop and all —
        # #F9C3BA, ΔE 63 from its hot-pink body — where the concept's own body sentence names the body's hex]
        colors["body"], _sources["body"] = body_hex, "the concept's own `body_base_color` sentence — its first hex"
    # [his test day finding 3, 2026-09-30, design 117: "the chosen pink is wrong" — his concept's body is two colour
    # fields, hot pink over soft pink, and the drawing painted one] the fields its own words name, split where its
    # picture splits them: the upper field is the body's colour, the lower drawn over it to the foot
    body_split, _fields = _body_fields(spec, _structured_colours, _palette, _archetype)
    # [his test day finding 3: and the front laid out in those fields, where the concept's own words place it]
    front_fields = _front_fields(_structured_colours) if body_split is not None else []
    if front_fields:
        records.append(("set", FRONT_FIELDS_SCHEMA, {
            "schema_version": FRONT_FIELDS_SCHEMA, "split_share": body_split, "words": front_fields,
            "laid": "the mark centred in the part of the confirmed front above the split; the name stack begun below "
                    "it, by the clear space the mark keeps"}))
    else:
        records.append(("drop", FRONT_FIELDS_SCHEMA, None))
    if body_split is not None:
        colors["body"], _sources["body"] = _fields[0][0], (
            "the concept's own `color_field_signature` — \"%s\" — the upper field" % _fields[0][1])
        colors["body_lower"], _sources["body_lower"] = _fields[1][0], (
            "the concept's own `color_field_signature` — \"%s\" — the lower field, from %.0f %% of the height down, "
            "where the concept picture's colour changes" % (_fields[1][1], 100 * body_split))
    _ink_hex, _sources["ink"] = _cs.type_ink(_structured_colours, _palette)
    if _ink_hex:
        colors["ink"] = _ink_hex
    if _declared.is_known(_archetype) and _declared.drawn_as_of(_archetype) == _declared.PLAN:
        _lid_hex, _lid_source = _cs.lid_face_colour(_pf, _brand_palette(task))
        colors["cap"] = _lid_hex or colors["body"]
        _sources["cap"] = (_lid_source if _lid_hex
                           else "measured from the approved concept image — " + _lid_source)
    else:
        # [his test day finding 3, 2026-09-30: a cap whose words name its colour without a hex takes that colour — 117's
        # "matching full-gloss hot pink" — never the stand-in; the stand-in only where its words name none]
        _cap_named, _cap_named_source = (None, None) if cap_hex else _cs.cap_colour(
            str((_pf.get("cap_color") or {}).get("value") or ""),
            str((_pf.get("body_base_color") or {}).get("value") or ""), _palette)
        if _cap_named:
            colors["cap"] = _cap_named
        _sources["cap"] = ("the concept's own `cap_color` sentence — its first hex" if cap_hex
                           else "the concept's own `cap_color` sentence — " + _cap_named_source if _cap_named
                           else "the brand ColorSystem's Metallic swatch — \"Caps, closures, foil detail\" — "
                                "as the flat stand-in `_DEFAULT_CAP_HEX`, because 10122 C carries no hex")
    # [his answer after test day finding 3 (1), his check of the map (2)] the concept picture's own map, where it is on
    # record for this picture, ahead of every colour the concept's words give — the owner's own turns below still win
    import hashlib as _hashlib
    _pic = _map_bytes(getattr(output, "approved_image", None), _archetype)   # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] a lid's
    _mapped = _map_colours(spec, _hashlib.sha256(_pic).hexdigest() if _pic else None)
    for _key in ("body", "body_lower", "cap", "ink"):
        if _key in _mapped:
            colors[_key], _sources[_key] = _mapped[_key]
    if "split" in _mapped and "body_lower" in _mapped:
        body_split = _mapped["split"]
    # [his answer after test day finding 3: drawn as the picture draws it] the parts' shapes, traced from the same picture
    # [his rules 1 and 2] the container's own lines on record, for the name the drawing prints (drawing_name, below)
    map_front = _map_front(spec, _pic, records, sources=type_sources_for(task, drawing_name(task, spec)[0], carton=False))
    # [his test finding on design 122's drawing, 2026-10-08, A and B] each motif traced from its flat redraw, never the
    # photo; the colours read from that redraw, the photo's lighting taken off — the concept's, to check the drawing by
    map_front = _with_flat_motifs(map_front, spec, getattr(output, "approved_image", None))
    # [His review of 127, 130, 131 and 132, 2026-10-15, C (2)] each solid motif whole, or drawn from its flat redraw
    map_front = _with_flat_shapes(map_front, spec, getattr(output, "approved_image", None), _pic)
    if map_front is not None and _is_face(_archetype):
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (3)] the lid's art, traced from its flat redraw
        # kept on the concept — never made here (the design loop never pays); its absence is said where it is drawn
        map_front = dict(map_front, lid_art=kept_lid_art_trace(getattr(output, "approved_image", None), _archetype,
                                                               _drawn_lid_mm(spec), spec))
    if map_front is not None and not _is_face(_archetype):
        # [his goal for the pitch, 2026-10-15, A (4), B (7)] the face's art, traced from its flat redraw kept on the
        # concept and checked where the concept draws — never made here; refused, said beside Approve where it was made
        from . import face_art as _fa
        _traced_face = _fa.traced_face(getattr(output, "approved_image", None), spec)
        if _traced_face is not None and _traced_face.get("state") == "TRACED":
            # the parts the face's art draws leave the map's own drawing and its checks: its type and its mark stay
            # — and [his review of 127-132, C (4): "its Arabic runs outside the oval"] its windows and frames kept to hold
            # its lines inside them, never drawn (``compose_container._frame_room``)
            held = {"windows": map_front["shapes"].get("windows") or [], "frames": map_front["shapes"].get("frames") or []}
            map_front = dict(map_front, face_art=_traced_face, holders=held, shapes={
                k: v for k, v in map_front["shapes"].items()
                if k not in ("bands", "lines", "shapes", "frames", "rules", "scatters", "windows")})
        elif _traced_face is not None:
            map_front = dict(map_front, face_art_refused=_traced_face["why"])
    _flat_set, _flat_refs, _gain = _flat_colours(map_front, _mapped, _pic, spec)
    for _key, (_hex, _words) in _flat_set.items():
        colors[_key], _sources[_key] = _hex, _words
    # [His goal after the pitch page, 2026-10-15, A (2) and A (3)] the closure's parts, each read on its own box, and how
    # the light runs across a metal one — its highlights and its shadows where the concept shows them
    closure_looks = closure_looks_of(spec, _pic, _archetype, colors, _sources)
    closure_seams = closure_seams_of(spec, _pic, _archetype)   # [his review, D (11); the lead's look at 135]
    if _declared.is_known(_archetype) and _declared.drawn_as_of(_archetype) == _declared.PLAN:
        # [his goal after the pitch page, A (3): "131 ... with a cream border"] a lid whose concept shows a rim round its
        # art: the case is the rim's colour, and the rim drawn in it (``silhouettes.lid_border_region``)
        _rim = (spec.get(OUTLINE_SOURCE_KEY) or {}).get("border")
        if _rim and _rim.get("hex"):
            colors["body"] = colors["border"] = _rim["hex"]
            _sources["body"] = _sources["border"] = ("the concept's own rim round its lid's art, read on the lid stood "
                                                     "square (concept_outline.lid_border)")
    map_front = _lit_off(map_front, _gain)
    if map_front is not None:
        map_front = dict(map_front, concept_colours=_flat_refs)
    if colours:
        # [the design loop] the owner's ground on the lid, before the motif's colours are chosen against it
        _turn_colour(colors, _sources, colours, "cap")
    _motif_sourced = _cs.motif_colours(_structured_colours, _palette, ground_hex=colors.get("cap"))
    colors["motif"] = [hx for hx, _src in _motif_sourced]
    _sources["motif"] = [src for _hx, src in _motif_sourced]
    # [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    # "The lid is missing the concept's rule, ring and radial lines."] a FACE draws the concept's own lines — its rule —
    # each in the colour the concept's words give it, else the brand swatch whose usage names fine detail lines; never
    # the type ink by accident, and each named here beside every other colour (colour_sources.line_colour)
    # [and its ring, which borrowed the type ink until now: sourced for every face, since a ring the arrangement's own
    # words draw ("frame", "border") needs a colour as much as the rim rule does]
    if _declared.is_known(_archetype) and _declared.is_face(_archetype):
        for _line in ("rule", "ring"):
            _line_hex, _line_source = _cs.line_colour(_structured_colours, _palette, element=_line,
                                                      stand_in=_DEFAULT_CAP_HEX)
            if _line_hex is not None:
                colors[_line], _sources[_line] = _line_hex, _line_source
    if colours:
        # [the design loop] the owner's colours on the type, the lines and the motif, where each is set above
        for _key in ("ink", "rule", "ring", "motif"):
            _turn_colour(colors, _sources, colours, _key)
        _motif_sourced = list(zip(colors["motif"], _sources["motif"]))
    records.append(("set", _cs.SCHEMA, {"schema_version": _cs.SCHEMA, "colors": dict(colors), "sources": _sources}))

    # 2B-2: NATIVE reconstruction — the confirmed decoration zones drive
    # native artwork; the raster label (make_flat_artwork) is gone, so the
    # decorative raster count is 0. The logo is the one controlled fallback.
    zones = (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []
    # [his test day finding 3, 2026-09-30: a name written from the brief's first sixty characters is read again]
    product_name, _name_source = drawing_name(task, spec)
    if _name_source is not None:
        spec["product_name"] = product_name
        records.append(("set", "product_name", product_name))
        records.append(("set", "product_name_source", _name_source))
    # preserve the exact selected name as LIVE text (§9) — never drop words
    name_lines = [product_name] if product_name else []
    # [his answer after test day finding 3] the front's traced type lines, each with the words a source on record gives it
    if map_front and (map_front.get("shapes") or {}).get("types"):
        from apps.pipeline.services import concept_design_map as _dm
        map_front = dict(map_front, shapes=dict(map_front["shapes"], types=_dm.type_sources(
            map_front["shapes"]["types"], type_sources_for(task, product_name, carton=False))))
    profile_record = spec.get("container_profile/1.0") or {}

    # 2B-2A slice 1: author the native motif spec from the SELECTED variation
    # (fail-closed VECTOR_RECONSTRUCTION_REVIEW_REQUIRED if unrebuildable).
    # Persisted BEFORE any render so a review-required motif keeps its report.
    from apps.ire import container_motif as cm
    motif_spec = cm.build_motif_spec(
        resolved["structured"], visual_graph or {}, zones, profile_record)
    records.append(("set", cm.SCHEMA, motif_spec))

    # THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace,
    # switch the mark to it so gold foil can print." The house mark through its one switch (apps/ire/brand_mark.py):
    # `png` is exactly the raster picked here before — an uploaded logo, else BRAND_LOGO_PATH, either only if it
    # exists — and `master` the approved vector master when docs/brand/mark/approval.json holds, else None. An
    # uploaded logo stays the task's own raster. The state is recorded only when an approval is on file (approved,
    # or refused with its code); with none on file the spec is what it always was — and a record a run made while an
    # approval WAS on file is not left standing to describe a run made without one.
    from apps.ire import brand_mark as _brand_mark
    _house = _brand_mark.house_mark(uploads)
    logo_path, logo_master = _house["png"], _house["master"]
    if _house["state"] in (_brand_mark.APPROVED, _brand_mark.REFUSED):
        records.append(("set", _brand_mark.SCHEMA, _brand_mark.selection_record(_house)))
    else:
        records.append(("drop", _brand_mark.SCHEMA, None))

    # 2B-3V-CORR-3 §6: a body whose CONFIRMED profile records transparency
    # composes as a transparent wall + separate visible product colour, never
    # one opaque fill. Concept authority only (profile field is UNVERIFIED).
    transparency = None
    profile_fields = (spec.get("container_profile/1.0") or {}).get("fields") or {}
    _opacity = str((profile_fields.get("body_opacity") or {}).get("value") or "")
    _btrans = str((profile_fields.get("body_transparency") or {}).get("value") or "")
    if "transparent" in (_opacity + " " + _btrans).lower():
        transparency = {"state": "TRANSPARENT",
                        "product_color": colors.get("product", "#F2C4CE")}

    # §W2 made the production-method capability table the authority on the
    # typography size floor, so the methods are derived BEFORE the axis that
    # reads them. §Z3(a) moved the derivation one step earlier still: the back
    # panel's copy is SET at BODY_BACK's own floor, so the composer needs the
    # same record. It is built once, here, and the composer and the axis are
    # handed the identical object — a composer that took a fallback while the
    # axis resolved a table floor is exactly how 15 runs came to sit at 5.0 pt
    # under a 6.0 pt floor. build_production_methods is pure and reads only
    # `zones` and `profile_record`, neither of which is rebound or mutated
    # between here and the typography block below.
    from apps.ire.container_production_method import build_production_methods
    methods_record = build_production_methods(zones, profile_record)
    return {"resolved": resolved, "concept_path": concept_path, "ref_path": ref_path, "colors": colors,
            "sources": _sources, "motif_sourced": _motif_sourced, "archetype": _archetype,
            "zones": zones, "product_name": product_name, "name_lines": name_lines,
            "profile_record": profile_record, "motif_spec": motif_spec, "house": _house, "logo_path": logo_path,
            "logo_master": logo_master, "transparency": transparency, "methods_record": methods_record,
            "body_split": body_split, "front_fields": bool(front_fields), "map_front": map_front,
            "approved_image": getattr(output, "approved_image", None), "closure_looks": closure_looks,
            "closure_seams": closure_seams}


def _front_plan(task, spec: dict, inputs: dict, *, records: list, read_layout,
                name_face: dict | None = None) -> dict:
    """THE NON-DROPPER FRONT — the arrangement the selected concept's own words ask for, the face its product name
    prints in and, on a FACE form, the reading of the concept's arrangement, its Arabic line, its display name and its
    vision layout — moved here unchanged from ``reconstruct_container``'s non-dropper branch, with the composer's
    whole call (``compose``) built from them. Reads ``spec``, writes nothing: the vision record goes to ``records``.

    ``read_layout`` reads the concept picture's layout: ``concept_layout.cached_or_read`` on every production call —
    which SPENDS a vision call when the picture has not been read — and, in the design loop, a reader that only ever
    returns the reading already on the record. ``name_face`` is the design loop's and None on every production call:
    the lead the owner tries on the name, a catalogue stem the role layer verifies, set where the concept's own lead
    is set."""
    # §BB7(c), the owner's own typed words at OWNER_BLOCKER_CLEARANCE.md
    # :10559 — "Wire both call sites ... One front from every path. My
    # ruling." Supplying `hierarchy_lines` sets `direct_print`, which
    # REPLACES the native decoration group with the ruled typographic
    # front. That trade is the ruling's content, not a side effect: the
    # decorative branch is what §BB6 reverted to and §BB7(b) re-authorised
    # away from.
    from apps.ire import brand_mark as _brand_mark
    from apps.ire.front_hierarchy import descriptor_for, ruled_front_hierarchy
    colors, resolved, motif_spec = inputs["colors"], inputs["resolved"], inputs["motif_spec"]
    _archetype, product_name = inputs["archetype"], inputs["product_name"]
    # §BH65(c)3: the arrangement the selected concept's own words ask for — its window, ring and motif — planned
    # here and drawn by the composer into the confirmed zone's free area below the ruled type block. The window's
    # centre is the face's own colour (the lid face on a form drawn in PLAN, the body otherwise); its edge is the
    # brand palette colour the colour-field sentence names after "gradient", when it names one.
    from apps.ire import concept_front as _cfront
    _face_hex = colors["cap"] if (_declared.is_known(_archetype)
                                  and _declared.drawn_as_of(_archetype) == _declared.PLAN) else colors["body"]
    concept_front_plan = _cfront.plan(
        resolved["structured"], motif_spec, ground_hex=_face_hex,
        edge_hex=_cfront.gradient_edge_hex((resolved["structured"] or {}).get("color_field_signature"),
                                            _brand_palette(task), _face_hex))
    # §BH67(c)5: the face the concept NAMES for its product name, read against the granted set — the layer's own
    # catalogue. The name prints at DISPLAY, which pins no variable instance (§BH33(2)) [§BH68(c): 700 — the
    # heading pin — unless the face declares its own display instance].
    from apps.ire import concept_typeface as _ctype
    from apps.ire.font_roles import INSTANCE_WEIGHT_BY_ROLE as _PINS, catalogue as _font_catalogue
    concept_front_plan["typeface"] = _ctype.read(resolved["structured"], _font_catalogue(),
                                                 name_role_pin=_PINS.get("display"))
    typeface_as_read = concept_front_plan["typeface"]
    if name_face is not None:
        # [the design loop] the face the owner tries on the name leads it, through the same role layer
        concept_front_plan["typeface"] = dict(concept_front_plan["typeface"], name=name_face)
    # §BH66(a), OWNER RULED 2026-09-23: on a form whose primary surface is its FACE "the concept's own arrangement
    # governs" — so a face-form run carries the reading of where the concept's words put the mark, the name, the
    # Arabic line and the motif, and the composer lays the face out from it. Which forms have a face is DECLARED
    # (`archetypes.primary_surface_of`); the Arabic is the product record's own, as held, and nothing else.
    if _is_face(_archetype) and (inputs.get("map_front") or {}).get("lid_art"):
        # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] the lid drawn from its concept's map and its
        # art — its words' arrangement neither read nor paid for
        concept_front_plan["face"] = {"state": "MAP", "surface": _declared.primary_surface_of(_archetype)["surface"]}
    elif _declared.is_known(_archetype) and _declared.is_face(_archetype):
        from apps.ire import concept_face as _cface
        _name_ar = (getattr(task.product, "name_ar", "") or "").strip() or None
        _shade = lid_shade(task.product)       # [his answer of 2026-09-29, (4)] the record's one shade, or None
        concept_front_plan["face"] = dict(
            _cface.read(resolved["structured"], layout=concept_front_plan.get("layout"),
                        has_arabic=bool(_name_ar), product_name=product_name, has_shade=bool(_shade)),
            surface=_declared.primary_surface_of(_archetype)["surface"], name_ar=_name_ar,
            name_ar_source=("Product.name_ar as held — the product record carries no provenance for it"
                            if _name_ar else None), shade=_shade)
        # §BH67(b)2: the display wordmark the concept quotes — taken only as the record's own leading phrase
        from apps.ire import display_name as _dname
        concept_front_plan["face"]["display_name"] = _dname.read(
            resolved["structured"], product_name=product_name, product_name_ar=_name_ar)
        # §BH67(d)1: THE CONCEPT IMAGE AS ART DIRECTION — the approved concept read as structure by a vision step,
        # once per image (cached on the spec by its sha256, the prompt version and the model), its cost on the
        # task's ledger. Read here, recorded here; the composer draws from it under every standing rule (d)2.
        from apps.pipeline.services import concept_layout as _clayout
        _surface = _declared.primary_surface_of(_archetype)["surface"]
        _vision = read_layout(
            task, spec, image_path=inputs["concept_path"], surface=_surface,
            surface_words=("the %s's %s — the face of the product, seen from above as a person holds it"
                           % (_archetype, _surface.replace("_", " ").lower())),
            structured=resolved["structured"])
        records.append(("set", _clayout.SPEC_KEY, _vision))
        concept_front_plan["face"]["vision_layout"] = _vision
        # §BH71 PART 1: "The concept's hero element (e.g. 91's rose-gold flower emblem), its finish and its material
        # carry into the drawing." The hero MEASURED on the approved concept (route A: its window's place and each
        # unit's pose on the lid rectified by its own rim; no pixel traced) — local pixels, nothing paid, recorded
        # either way; the composer draws it where it drew the procedural motif, which stays when it is not read.
        from apps.pipeline.services import concept_outline as _co
        _hero = _read_hero(spec, inputs.get("concept_path"), _archetype)
        records.append(("set", _co.HERO_SCHEMA, _hero))
        if _hero.get("state") == _co.HERO_FROM_CONCEPT:
            concept_front_plan["hero"] = _hero
            concept_front_plan["face"]["measured"] = {"window": _co.hero_window_box(_hero)}
    # [his rules for cloning a design from a picture, 2026-10-02, rule 5: "THE BACK IS DRAWN: replace the placeholders
    # ('INFO · INCI · CODE', 'BATCH') with the brief's back copy"] the brief's own back copy, drawn on the back — in the
    # strip and at the size it prints — and its batch code's place drawn as the confirmed code zone's window
    # [his answers after the fixes for design 122, (2)] with his brief's size; [his review of 127, 130, 131 and 132,
    # 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] and the full set — each piece his words leave empty as the shape step
    # wrote it, in the form it measured (``label_back``: read, never paid for here)
    back = label_back(task, spec)
    # [his final goal, 2026-10-05, A] the back in English, then Spanish, then Arabic — its translations read from the
    # record the profile step kept, never asked for here (this plan is also the design loop's, which never pays)
    back_sections, back_codes = trilingual_sections(back["sections"], back["kept"],
                                                    languages=label_languages(spec))
    _qr = back["qr"] if (spec.get(LABEL_FORM_KEY) or {}).get("qr") else None
    open_tray = palette_tray_plan(task, _archetype, colors, records, image=inputs.get("approved_image"))
    compose = dict(
        reference_path=inputs["ref_path"], logo_path=inputs["logo_path"],
        colors=colors, product_name=product_name,
        sku=spec.get("sku", ""), zones=inputs["zones"], name_lines=inputs["name_lines"],
        native=True, motif_spec=motif_spec, transparency=inputs["transparency"],
        hierarchy_lines=ruled_front_hierarchy(
            product_name, descriptor=descriptor_for(spec, task.product)),
        concept_front=concept_front_plan, body_split=inputs.get("body_split"),
        map_front=inputs.get("map_front"),          # [his answer after test day finding 3: drawn as the picture draws it]
        front_fields=inputs.get("front_fields") is True,
        label_is_front=(spec.get(FRONT_LABEL_SCHEMA) or {}).get("source") == FRONT_LABEL_CONFIRMED,
        **({"back_sections": back_sections, "back_panel": {"methods_record": inputs.get("methods_record"),
                                                           **({"qr_url": _qr} if _qr else {})}}
           if back["sections"] else {}),
        **({"batch_code_place": back["batch_code_place"]} if back["batch_code_place"] else {}),
        **({"open_tray": open_tray} if open_tray else {}),
        # [his goal after the pitch page, A (2)] handed over only where a closure is metal, so every other call is, keyword
        # for keyword, the call it was
        **({"closure_looks": inputs["closure_looks"]} if inputs.get("closure_looks") else {}),
        # [his review of 127, 130, 131 and 132, 2026-10-15, D (11)] handed over only where the concept shows a seam
        **({"closure_seams": inputs["closure_seams"]} if inputs.get("closure_seams") else {}),
        **_brand_mark.master_kwargs(inputs["logo_master"]))
    return {"concept_front": concept_front_plan, "compose": compose, "typeface": typeface_as_read,
            "back_codes": back_codes, "back_english": list(back["sections"]), "back_kept": back["kept"]}


def ensure_open_tray(aria, image, archetype) -> dict | None:
    """[his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5)] The open palette's picture for a compact whose brief
    names its pans — made once from the chosen concept and kept (``tray_picture.ensure_tray``), or its refusal said in
    the design's log (the pans then take their names' finishes and the concept's palette, each said so); None, and
    nothing paid, for every other form, a compact whose brief names no pans, or with the map's read switched off."""
    from django.conf import settings
    if archetype != "compact" or not settings.DESIGN_MAP_READ:
        return None
    from apps.ire import palette_tray as _palette_tray

    from . import tray_picture as _tp
    product = aria.task.product
    shades = product.shade_names if product is not None and isinstance(product.shade_names, list) else []
    tray = _palette_tray.read_tray(brief_text(aria.task), shades=shades)
    if tray is None:
        return None
    got = _tp.ensure_tray(aria, image, tray)
    if got.get("state") == _tp.REFUSED:
        aria.log("ARIA: the open palette's picture could not be made — %s; its pans take their names' finishes and "
                 "the concept's palette, each said so" % got["why"], level="warning", payload={"code": got["code"]})
    return got


#: [his goal of 2026-10-10, item 2] what the drawing's record keeps of the tray read from his brief
OPEN_TRAY_KEY = "palette_open_tray_read/1.0"


def palette_tray_plan(task, archetype, colors: dict, records: list, image=None) -> dict | None:
    """[His goal of 2026-10-10 (OWNER_BLOCKER_CLEARANCE.md), item 2: "A palette design must include the whole palette: the lid AND the open tray with its 18 pans in 3 rows of 6, each shade name from my brief printed under its pan."]
    A compact's open tray, read from his brief's own words at $0 (``palette_tray.read_tray``: the grid, the pans' shape
    and each pan's shade name, else the record's shades) and drawn in the design's own colours — the case's body for
    its insert, the type's ink for its names, the motif's colours for the frame round its pans; None for every other
    form, and for a compact whose brief names no pans (its record says so)."""
    if archetype != "compact":
        return None
    from apps.ire import palette_tray as _palette_tray
    product = task.product
    shades = product.shade_names if product is not None and isinstance(product.shade_names, list) else []
    tray = _palette_tray.read_tray(brief_text(task), shades=shades)
    records.append(("set", OPEN_TRAY_KEY, {"schema_version": OPEN_TRAY_KEY, "tray": tray,
                                           "why": ("read from %s" % tray["source"]) if tray else
                                           "the brief names no pans and the record no shades: no tray drawn"}))
    if tray is None:
        return None
    edges = [h for h in colors["motif"] if h] if isinstance(colors.get("motif"), list) else []
    # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5): "Every pan gets a real shade colour and finish
    # ... from that picture or, if needed, from the shade name and the concept's palette"] the open palette's picture
    # kept on the concept read at $0 into his grid; each pan its colour and finish, its source said — never grey
    from . import tray_picture as _tp
    kept = _tp.kept_tray(image) if image is not None else None
    read = _tp.read_tray_picture(_tp.tray_bytes(kept), tray["rows"], tray["cols"]) if kept is not None else None
    if read is not None:
        records.append(("set", _tp.TRAY_READ_KEY, read))
    palette = [h for h in [colors.get("cap"), colors.get("body")] + list(colors.get("motif") or []) if h]
    # [his goal of 2026-10-12, (11)–(13)] the tray's own inks as its picture prints them — the rims' gold, the glow
    # round each pan, the names' ink; none where no picture was read (the tray drawn as before)
    seen = read if read is not None and read.get("state") == _tp.READ else {}
    # [his goal of 2026-10-12, (12)] the inside of the lid the tray picture shows above its pans, straightened and
    # traced as the lid's art is ($0)
    lid_inside = None
    if seen:
        from . import lid_art as _la
        strip, lid_rec = _tp.lid_inside_strip(_tp.tray_bytes(kept), min(p["box_px"][1] for p in seen["pans"][0]))
        if strip is not None:
            # [his goal of 2026-10-13, (7)] read from the tray's photograph: its arches and ovals drawn as lines, its
            # straight edges the photograph's own — never drawn as rules
            traced = _la.trace_art(strip, False, kinds=("arch", "oval"))
            lid_rec = {**lid_rec, "trace": {k: traced.get(k) for k in ("state", "measured", "why")}}
            if traced.get("state") == _la.TRACED:
                lid_inside = traced
        records.append(("set", _tp.LID_INSIDE_KEY, lid_rec))
    return {"tray": tray, "ground_hex": colors["body"], "ink_hex": colors["ink"] if colors.get("ink") else colors["cap"],
            "edge_hexes": edges if edges else [colors["cap"], colors["body"]],
            "pans": _tp.pans_for(tray, read, palette),
            "rim_hex": seen.get("rim"), "glow_hex": seen.get("glow"), "name_hex": seen.get("names_ink"),
            "lid_inside": lid_inside}


def _compose_front(backbone, compose: dict):
    """The container composer's ONE call for every non-dropper form — production's and the design loop's alike, so
    §BB7(c)'s ruled front is fed from this module and no other."""
    from apps.ire.compose_container import compose_container_graph
    return compose_container_graph(backbone, **compose)


def _finish_inputs(task, inputs: dict) -> dict:
    """What ``container_finishes.apply`` is handed after the composer draws — the concept's finish assignments, the
    brand Metallic's depiction and a refused approval on file — moved here unchanged from ``reconstruct_container``.
    §BH65(c)2: foil depicts in the brand's own Metallic record — its flat stand-in when the record carries no hex,
    which is the stand-in `colour_sources` names for "Caps, closures, foil detail"."""
    from apps.ire import brand_mark as _brand_mark
    from apps.pipeline.targets.container import colour_sources as _cs
    _metal_hex, _metal_source = _cs.metallic_hex(_brand_palette(task), _DEFAULT_CAP_HEX)
    # [the owner's second answer of 2026-09-25, §BH58(e): an approval on file that does not hold is said in the lockup's
    # row with its codes — handed over only then, so every other call is, keyword for keyword, the call it was]
    _house = inputs["house"]
    _refused_mark = ({"refused_approval": {"codes": list(_house["codes"]), "reason": _house["reason"]}}
                     if _house["state"] == _brand_mark.REFUSED else {})
    # [his goal of 2026-10-12, (6): "FINISHES are never invented: a finish plate ... is made only when my brief or the
    # concept shows it."] the concept's finish line keeps only what his brief asks for; the rest is said, never plated
    # — and the gold plate it names, if any, still names the picture's gold (``gold_plate``)
    from apps.ire import container_finishes as _finishes
    _asked_for, _set_aside = _finishes.as_asked(inputs["motif_spec"].get("finish_assignments"),
                                                getattr(task, "task_text", ""))
    _clauses = (inputs["motif_spec"].get("finish_assignments") or {}).get("clauses") or ()
    _named_gold = next(((f["kind"], f["plate"]) for c in _clauses for f in c["finishes"]
                        if f["kind"] in _finishes.INK_FINISHES and f["plate"].endswith("_GOLD")), None)
    # each handed over only where it says something, so every other call is, keyword for keyword, the call it was
    _asked = {**({"set_aside": tuple(_set_aside)} if _set_aside else {}),
              **({"gold_plate": _named_gold} if _named_gold and inputs["map_front"] else {})}
    if inputs["map_front"]:
        # [his look at 117 drawn from its map, 2026-10-02: "Always the colors, the picture, not the brand. Every single
        # color should play a role when we are working on generating the image, not after"] a front drawn from its
        # concept picture keeps every foil part in the picture's colour it was drawn in
        return {"assignments": _asked_for,
                "kwargs": dict(brand_metallic_hex=_metal_hex, depict_as_drawn=True, **_refused_mark, **_asked),
                "depiction_source": PICTURE_DEPICTION}
    return {"assignments": _asked_for,
            "kwargs": dict(brand_metallic_hex=_metal_hex, **_refused_mark, **_asked), "depiction_source": _metal_source}


#: [his look at 117 drawn from its map, 2026-10-02] where a front drawn from its concept picture takes its foil's look
PICTURE_DEPICTION = ("each foil part in its own colour as drawn, measured from the concept picture — \"Always the "
                     "colors, the picture, not the brand\" (his look at 117 drawn from its map, 2026-10-02)")


def _apply_finishes(doc, finish: dict) -> dict:
    """§BH65(c)2: THE FINISHES THE CONCEPT NAMED, APPLIED TO WHAT THE COMPOSER DREW — the one call, production's and
    the design loop's."""
    from apps.ire import container_finishes as _finishes
    kwargs = dict(finish["kwargs"])
    if kwargs.get("depict_as_drawn"):
        # [his answer 2 of 2026-10-02 (a18911a): "Gold in the picture is foil"] the nodes the composer drew in its gold
        mf = (doc.metadata or {}).get("map_front") or {}
        kwargs["gold_as_drawn"] = tuple(mf.get("gold_nodes") or ())
    finish_application = _finishes.apply(doc, finish["assignments"], **kwargs)
    finish_application["depiction_source"] = finish["depiction_source"]
    return finish_application


def face_form_inputs(task, output, confirmed: dict, *, read_layout, colours: dict | None = None,
                     name_face: dict | None = None, moved_zones: dict | None = None,
                     product_name: str | None = None) -> dict:
    """ONE DERIVATION, TWO CALLERS — the composer's inputs for a FACE form (a form whose primary surface is its face:
    the compact's lid, drawn in plan), derived by the very functions ``reconstruct_container`` calls for its
    non-dropper branch, and WRITING NOTHING: the spec sheet is read through a deep copy — the output itself too, as a
    shallow copy whose sheet is that copy — the records production would persist come back under ``records`` and are
    never written, and nothing is saved, logged or written to a file.

    ``read_layout`` is the vision read's reader (the design loop hands one that never calls a provider);
    ``colours``, ``name_face``, ``moved_zones`` and ``product_name`` are the design loop's knobs, set in the copy before
    anything is derived from it — ``moved_zones`` is ``{zone_type: {field: value}}``. Draw the result with
    ``draw_face_form``."""
    import copy
    spec = copy.deepcopy(output.spec_sheet or {})
    archetype = _declared.require_scope(
        "the face-form derivation (face_form_inputs)",
        (spec.get("container_profile/1.0") or {}).get("archetype"),
        serves=tuple(a for a in _declared.VOCABULARY if _declared.is_face(a)))
    for zone in (spec.get("container_decoration_zones/1.0") or {}).get("zones") or []:
        zone.update((moved_zones or {}).get(zone.get("zone_type")) or {})
    if product_name:
        spec["product_name"] = product_name
    view = copy.copy(output)               # read as production reads its output, its sheet the working copy
    view.spec_sheet = spec
    from apps.pipeline.targets.container.m3_backbone import build_container_backbone
    profile = _profile_from_confirmed(confirmed)
    records: list = []
    profile = _profile_with_outline(profile, spec, view, records)        # §BH71 PART 1: the same derivation
    # [his goal after the pitch page, 2026-10-15, A (3)] the outline's record on the copy before the composer's inputs
    # read it (its rim's colour), as ``reconstruct_container`` writes it before them; written again below, unchanged
    _write_records(spec, records)
    backbone, structure_record = build_container_backbone(profile)
    inputs = _composer_inputs(task, view, spec, records=records, colours=colours)
    _write_records(spec, records)          # the copy reads, from here, as production's sheet reads at this point
    front = _front_plan(task, spec, inputs, records=records, read_layout=read_layout, name_face=name_face)
    return dict(inputs, archetype=archetype, profile=profile, backbone=backbone, structure_record=structure_record,
                concept_front=front["concept_front"], compose=front["compose"], typeface=front["typeface"],
                finish=_finish_inputs(task, inputs), records=records)


def draw_face_form(inputs: dict) -> tuple:
    """The face drawn from ``face_form_inputs`` — the composer's one call and the finishes applied to what it drew,
    the two steps ``reconstruct_container`` takes. Returns ``(document, finish application)``; writes nothing."""
    doc = _compose_front(inputs["backbone"], inputs["compose"])
    return doc, _apply_finishes(doc, inputs["finish"])


#: §BH70(1), item 5 of the list the owner was sent: the runs of a front the generic composer draws that are judged
#: beside the product name — the ruled front's descriptor; the name runs are judged as the dropper's are (§BH50(g)(2),
#: re-typed §BH53(a): the product name is front copy) [his answer of 2026-09-29 to the §BH71 report, (4): and a lid's
#: shade line, its English run — its Arabic, like the name's Arabic line, held inside the lid by the composer]
GENERIC_FRONT_COPY_RUNS = ("front-descriptor", "product-shade")
#: why the height of the block is not measured, per path — the words the review board shows beside the code
GENERIC_FRONT_HEIGHT_UNMEASURED = {
    "ruled": ("its lines are laid into the drawing's own label area, not the zone you confirmed, so where each line "
              "sits and how tall the block is are not measured against that zone — only each line's width is"),
    # [his test day finding 3, 2026-09-30: a tube's lines are laid into the front he confirmed (`_profile_with_front_zone`)]
    "ruled_in_zone": ("its lines are laid into the zone you confirmed, held inside the drawn body, at true size, but how "
                      "tall the block is has no instrument on this path yet — only each line's width is measured"),
    "face": ("the lid's lines are laid into the zone you confirmed, at true size, but how tall the block is has no "
             "instrument on this path yet — only each line's width is measured"),
}
#: why nothing is measured when the confirmed zones hold no front zone — a jar's proposed label is one zone round it
GENERIC_NO_FRONT_ZONE = ("no front zone was confirmed for this product, so its front copy has nothing to be measured "
                         "against — a label that wraps the whole product, as a jar's does, has no front of its own")


#: the names a front drawn from its concept's map types its lines under (``compose_container._map_type_group``)
MAP_FRONT_COPY_PREFIXES = ("front-descriptor-", "product-name-hero-")


def _map_front_copy_fit(doc, front: dict, on_sheet: dict) -> dict:
    """[His answers after 122 was redrawn, 2026-10-08 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 0b0c7e7), (2): "Fix the
    front-copy fit check so it measures against MY confirmed print area, not the drawing's own."] A front drawn from its
    concept's map sets each line where the picture prints it, inside his confirmed front — never in the drawing's own
    label area: so every line it types (``MAP_FRONT_COPY_PREFIXES``) is measured against his confirmed front, across
    against its safe area and down against its safe band, by the dropper's own instrument (``front_copy_fit``); until
    this its lines other than the name were read by nothing, and its height was said to be laid in the drawing's label.
    A line the picture prints within the band's margin but inside his front is the production note his answer on the safe
    margin gave (ZONE_SAFE_MARGIN_AS_PICTURED, 2026-10-01), never a block; a line past his front's edge is refused."""
    from apps.ire.compose_container import FRONT_DIRECT_PRINT_GROUP
    from apps.ire.compose_dropper import FRONT_COPY_EXCEEDS_SAFE_BAND, front_copy_fit
    from apps.ire.container_production_readiness import ZONE_SAFE_MARGIN_AS_PICTURED
    from apps.ire.font_roles import ARABIC_ROLE_FOR, base_role
    top, scale = float(on_sheet["top_mm"]), float(on_sheet["scale"])
    lines = []
    for group, _ in doc.walk():
        if getattr(group, "type", "") != "group" or group.name != FRONT_DIRECT_PRINT_GROUP:
            continue
        stack = list(group.children)
        while stack:
            node = stack.pop(0)
            stack.extend(getattr(node, "children", None) or [])
            if getattr(node, "type", "") == "text" and str(node.name).startswith(MAP_FRONT_COPY_PREFIXES):
                if node.rotation_deg:
                    # [his fixes to 142, 2026-10-17, (1)] a run set on end has no baseline across the band: its length
                    # down the zone is held by the walk across (``front_copy_fit``), against the zone's height
                    continue
                # a run set right to left is drawn in the Arabic face of its role (``pdf_ai``), and read in it
                role = node.font or "regular"
                font = ARABIC_ROLE_FOR.get(base_role(role), "arabic") if getattr(node, "rtl", False) else role
                lines.append({"name": node.name, "text": node.text, "size_pt": node.size_pt, "font": font,
                              "baseline_mm": (float(node.y) - top) / scale})
    copy_runs = tuple(line["name"] for line in lines if line["name"].startswith("front-descriptor-"))
    record = front_copy_fit(doc, front, lines, copy_runs=copy_runs)
    height = float(front["height"])
    margin = float(front["safe_margin_mm"]) if front.get("safe_margin_mm") is not None else 0.0
    rows = {row["name"]: row for row in record.get("vertical_runs") or []}
    codes = []
    for code in record["codes"]:
        name = code.split(":", 1)[1].strip().split(" ", 1)[0] if code.startswith(FRONT_COPY_EXCEEDS_SAFE_BAND) else ""
        row = rows.get(name)
        if row is not None and row.get("ink_top_mm", -1.0) >= 0.0 and row.get("ink_bottom_mm", height + 1.0) <= height:
            codes.append(f"{ZONE_SAFE_MARGIN_AS_PICTURED}: {name} sits inside the {margin:g}mm safe margin of zone "
                         f"{front.get('zone_id')}, where the concept picture prints it")
            row["state"] = "AS_PICTURED"
        else:
            codes.append(code)
    record["codes"] = codes
    record["measured_against"] = ("your confirmed front %s, %g x %g mm — each line where the concept picture prints it"
                                  % (front.get("zone_id"), float(front["width"]), height))
    return record


def generic_front_copy_fit(doc, zones, archetype, *, laid_in_zone: bool = False):
    """§BH70(1), item 5 of the list the owner was sent: THE FRONT COPY OF A PRODUCT THE GENERIC COMPOSER DRAWS, MEASURED
    by the dropper's own instrument (`compose_dropper.front_copy_fit`) against the zone the person confirmed.

    Every form but the dropper carried one code here, "no fit instrument on this path", with the note that which
    rectangle is the zone — the drawing's label area or the confirmed FRONT_PRINT_ZONE — is a contract question first.
    That question decides where a line sits and how tall the block is; it does not decide how wide a line is. The sheet
    draws the product at s = 1 (`compose_container._sheet_layout` gives the hero a box of the backbone's own size), so
    each run is set at its print size and its width, in the face the emitter draws it with, is its own whatever
    rectangle it was laid into. So each line is measured ACROSS against the confirmed zone's safe area, which governs
    (§BH50(g)(1), re-typed §BH53(a)), the zone recorded beside it as the outer bound; the height stays UNMEASURED with
    its reason per path (``GENERIC_FRONT_HEIGHT_UNMEASURED``) and blocks acceptance as every UNMEASURED code does
    (§BH50(f)(5)); and a line drawn in the front that no instrument reads is named UNMEASURED, never passed. Returns
    the fit record, or None when the confirmed zones hold no front zone. ``laid_in_zone``: [his test day finding 3] the
    ruled front was laid into the confirmed zone (``container_front_label/1.0``), and its sentence says so."""
    front = next((z for z in zones or [] if z.get("zone_type") == "FRONT_PRINT_ZONE"), None)
    if front is None:
        return None
    from apps.ire.compose_container import FRONT_DIRECT_PRINT_GROUP
    from apps.ire.compose_dropper import FRONT_COPY_FIT_UNMEASURED, front_copy_fit
    on_sheet = ((doc.metadata or {}).get("map_front") or {}).get("zone_on_sheet")
    if on_sheet:
        record = _map_front_copy_fit(doc, front, on_sheet)
    else:
        record = front_copy_fit(doc, front, None, copy_runs=GENERIC_FRONT_COPY_RUNS,
                                vertical_unmeasured=GENERIC_FRONT_HEIGHT_UNMEASURED[
                                    "face" if _declared.is_face(archetype) else
                                    "ruled_in_zone" if laid_in_zone else "ruled"])
    judged = {row["name"] for row in record["runs"] + record["name_runs"]}
    seen, not_read = set(), []
    for group, _ in doc.walk():
        if getattr(group, "type", "") != "group" or group.name != FRONT_DIRECT_PRINT_GROUP:
            continue
        stack = list(group.children)
        while stack:
            node = stack.pop(0)
            stack.extend(getattr(node, "children", None) or [])
            if getattr(node, "type", "") == "text" and id(node) not in seen and node.name not in judged:
                seen.add(id(node))
                not_read.append({"name": node.name, "text": node.text})
    for run in not_read:
        record["codes"].append(f"{FRONT_COPY_FIT_UNMEASURED}: {run['name']} (no instrument reads this line on this "
                               "path)")
    record["not_read"] = not_read
    # [his go of 2026-10-02: the map path for a wand vial] a line a front drawn from its picture typed wider than the
    # front he confirmed, measured where it was typed (`compose_container._map_type_group`) — its overrun holds acceptance
    record["codes"].extend(((doc.metadata or {}).get("map_front") or {}).get("codes") or [])
    return record


def _designers_eye(aria, output, doc, spec, ai_path, out_dir, font_usage, colors, sources, fixed, shown):
    """[His goal for the pitch, 2026-10-15, B (5)] the designer's eye on the drawing just emitted (``designers_eye``):
    its record on the spec (``designers_eye.SCHEMA``), its fixes with the drawing's own, what it still sees beside
    Approve; the path of the file as last drawn — drawn again after each round of fixes."""
    from django.conf import settings
    from apps.ire import views_of as _views_of
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.pipeline.services import designers_eye as _eye
    if not getattr(settings, "DESIGNERS_EYE", True) or not settings.ANTHROPIC_API_KEY:
        return ai_path                                 # no model to look with: nothing could have been drawn either
    concept = _concept_bytes(output.approved_image) if output.approved_image is not None else None
    if not concept:
        return ai_path
    box = _eye.design_box(_views_of.views(doc))
    state = {"path": ai_path, "first": True}

    def draw():
        if not state["first"]:
            state["path"] = emit_pdf_ai(doc, os.path.join(out_dir, "container.ai"), usage_out=font_usage)
        state["first"] = False
        return _eye.render(state["path"], box)
    mine = [v for k, v in (colors or {}).items()
            if isinstance(v, str) and ("brief" in str((sources or {}).get(k)) or "your" in str((sources or {}).get(k)))]
    # a standing product's closure shown enlarged too — never a compact's lid, seen square from above
    standing = not _is_face(((spec or {}).get("container_profile") or {}).get("archetype"))
    record = _eye.check(concept, draw, doc, mine=mine, log=aria.log, task=aria.task, top=standing)
    spec[_eye.SCHEMA] = record
    fixed += [{"kind": "designer's eye", "fixed": True, "what": w} for w in record["fixed"]]
    shown += _eye.shown(record)
    aria.log("ARIA: the designer's eye — %s, $%s" % ({"PASS": "the drawing matches its concept",
                                                      "DIFFERS": "%d difference(s) left, said beside Approve"
                                                                 % len(record["left"]),
                                                      "NOT_LOOKED": "it could not look"}[record["state"]],
                                                     record["cost_usd"]),
             payload={"designers_eye": {k: record[k] for k in ("state", "fixed", "left", "summary", "cost_usd")}})
    return state["path"]


def reconstruct_container(
    aria, output, confirmed: dict, *, confirmed_fonts: dict | None = None
) -> None:
    """Reconstruct the editable container from the confirmed profile + zones.

    2B-2 native path: the confirmed decoration zones drive NATIVE artwork
    (tinted field, keyline, live product name); the raster label is gone, so
    the decorative raster count is 0. The reference photo stays
    TEMPORARY_VISUAL_REFERENCE_ONLY (its own labelled group) and the logo is
    the one controlled raster fallback. Persists container_design_graph/1.0
    (the primitive census) and emits the .AI + PNG onto the existing
    PackagingOutput file fields.

    P2-b: `confirmed_fonts` is the SEAM for owner-confirmed faces, kept
    deliberately separate from `confirmed`. `confirmed` is a GEOMETRY
    confirmation -- `_profile_from_confirmed` admits eight shape keys and no
    font key -- so threading faces through it would let a shape reviewer
    confer a font licence. Licence authority is never inferred.

    THE PRODUCTION PRODUCER OF THIS ARGUMENT IS LIVE — §BH26(b) wired the
    §BH12(a) Option B join (container_font_evidence_join.join_document_fonts)
    at the call site below: when a caller passes nothing, the seam is fed from
    the live c4c face_manifest join over the faces the emitter will use, capped
    at LICENCE_REVIEW_REQUIRED / MACHINE_DERIVED, so the production record no
    longer rests on the DEFAULT column. §BH26(a)'s owner grant
    (apps/ire/container_font_owner_grant.py) is applied DOWNSTREAM, after the
    build and before the gate, conferring the owner's states on the two
    sha256-named faces; where the evidence is absent (a clean clone) the join
    yields nothing and the default column stands beneath the grant. A caller's
    explicit mapping is honoured as before. An empty or absent value records
    the confirmation as UNKNOWN and must never be read as "not confirmed".
    """
    from django.core.files.base import ContentFile

    from apps.ire.brand_string_runtime import brand_string_report
    from apps.ire.compose_container import container_design_graph_record
    from apps.ire.emitters.pdf_ai import emit_pdf_ai
    from apps.ire.rasterize import pdf_to_png

    profile = _profile_from_confirmed(confirmed)
    spec = output.spec_sheet or {}
    spec[CONTAINER_CONFIRMED_KEY] = dict(confirmed or {})    # [his final goal, C5c] so his choice can make it again

    # 2C-2E: a HUMAN_CONFIRMED_CONCEPT_ONLY extensions record switches the
    # bottle to the confirmed dropper geometry — TOTAL height including the
    # closure, the collar/bulb split, the visible base band, and the
    # confirmed front zone as the typography area. Concept authority only.
    from apps.pipeline.services import selected_concept_contract as scc
    geometry = scc.confirmed_dropper_geometry(spec)
    # §BH49(a): the drawing source, resolved BEFORE the profile is built from the numbers — M3_FIT by
    # construction; PARAMETRIC only by the task's declared record; anything else refused by name — REFIT too,
    # whose branch left with its fitter in the clean-up of 2026-10-04 (git history keeps both).
    from apps.pipeline.targets.container import m3_backbone as _m3
    drawing_source = _m3.drawing_source_of(spec)
    sheet_source = drawing_source
    if geometry is not None:
        # §BH61(b)(c) — THE REFUSAL GOES AT THE DOOR. `geometry` is a CONFIRMED DROPPER geometry record
        # (collar, bulb, pipette); a compact has no collar. This branch used to rewrite any archetype to
        # bottle/cylindrical/dropper. It states its scope instead.
        _declared.require_scope(
            "the confirmed-dropper reconstruction path (reconstruct_container)",
            profile.archetype, serves=("bottle",))
        from dataclasses import replace as _dc_replace
        closure_h = geometry["collar_height_mm"] + geometry["bulb_height_mm"]
        _zones = (spec.get("container_decoration_zones/1.0") or {}
                  ).get("zones") or []
        _front = next((z for z in _zones
                       if z.get("zone_type") == "FRONT_PRINT_ZONE"), None)
        label = None
        if _front is not None:
            label = (float(_front["x"]), closure_h + float(_front["y"]),
                     float(_front["width"]), float(_front["height"]))
        profile = _dc_replace(
            profile, archetype="bottle", variant="cylindrical",
            cap_style="dropper",
            height_mm=geometry["total_height_mm"],
            width_mm=geometry["body_diameter_mm"],
            neck_ratio=(geometry["neck_diameter_mm"] or 10.0)
            / geometry["body_diameter_mm"],
            label_zone=label,
            closure_geometry={
                "collar_h": geometry["collar_height_mm"],
                "bulb_h": geometry["bulb_height_mm"],
                "collar_w": geometry["collar_diameter_mm"]
                or geometry["body_diameter_mm"] * 0.85,
                "base_thickness": geometry["base_thickness_mm"] or 3.5,
                "shoulder_radius": geometry["shoulder_radius_mm"] or 3.0,
            })
    # §BH48(b)(ii) / §BH49(a): on M3_FIT — the product's source by construction — the profile is
    # DERIVED from the accepted fit (one isotropic scale from the ruling's one anchor, ANCHOR_MM, on
    # the body) and the fit's own outlines are what the sheet draws; the derivation is recorded
    # beside the source.
    if geometry is not None and drawing_source == _m3.DRAWING_M3_FIT:
        profile_m3, geometry, derivation = _m3.m3_profile_geometry(_m3.ANCHOR_MM, geometry, profile.archetype)
        derivation["anchor_source"] = "m3_backbone.ANCHOR_MM"   # the ruling's parameter, where it lives since REFIT left
        closure_h = geometry["collar_height_mm"] + geometry["bulb_height_mm"]
        label = None
        if _front is not None:
            label = (float(_front["x"]), closure_h + float(_front["y"]),
                     float(_front["width"]), float(_front["height"]))
        profile = _dc_replace(profile_m3, label_zone=label,
                              decoration_zone=profile.decoration_zone)
        spec[_m3.DRAWING_SOURCE_SCHEMA] = derivation
    # VQR-1: the ONE backbone selector — Bottle+dropper uses the
    # owner-accepted M3 assembly (fail-closed hash-verified), everything
    # else keeps the parametric builder; the structure record feeds the
    # design graph so the quality gate's closure axis can finally measure.
    from apps.pipeline.targets.container.m3_backbone import (
        build_container_backbone,
    )
    # §BH71 PART 1: the outline traced from the approved concept, attached when the shape confirmed is the concept's —
    # ONE DERIVATION, BOTH DRAWING CALLERS (`_profile_with_outline`); which drew, and why, written beside the drawing
    _made_outline: list = []
    profile = _profile_with_outline(profile, spec, output, _made_outline, keep_m3=geometry is not None)
    profile = _profile_with_front_zone(profile, spec, _made_outline)   # [his test day finding 3: his front, his copy]
    _write_records(spec, _made_outline)
    backbone, structure_record = build_container_backbone(profile)

    # ONE DERIVATION, TWO CALLERS (the block just above this function): the verified variation, the concept image, the
    # visual graph, the colours and the record each came from, the zones, the name, the motif spec, the house mark,
    # the transparency and the production methods — derived by `_composer_inputs`, moved there unchanged; its records
    # are written here, in the order it made them, and in a `finally`, so a run that fails part-way leaves on the sheet
    # exactly the records it left before the move.
    from apps.ire import brand_mark as _brand_mark
    from apps.ire import container_motif as cm
    from apps.pipeline.services import container_visual_graph as cvg
    from apps.pipeline.targets.container import colour_sources as _cs
    # [his test finding on design 122's drawing, 2026-10-08, A1] each line-art motif redrawn flat before it is traced —
    # a paid picture, made once and kept; one that cannot be made stops the drawing, said
    # [his goal for the pitch, 2026-10-15, A (4), B (7)] a product drawn standing: its printed face redrawn flat once and
    # traced in colour, as a lid's art is (``face_art``) — its motifs need no redraw of their own then
    from . import face_art as _fa
    _face = None
    from django.conf import settings as _fa_settings
    from apps.pipeline.services import concept_design_map as _fa_dm
    if _fa_settings.FACE_ART and not _is_face(profile.archetype) and (spec.get(_fa_dm.SCHEMA) or {}).get(
            "state") == _fa_dm.MAP_READ:
        _face = _fa.ensure_face_art(aria, output, profile.archetype)
        if _face.get("state") != _fa.REDRAWN:
            from apps.ire import self_check as _fsc
            _fsc.keep_shown(spec, _fa.FACE_ART_NOT_DRAWN, "the product's printed face is drawn from its map alone, "
                            "not from its flat redraw — %s" % _face["why"], _fa.FACE_ART_OPTIONS)
    _flat_refused = [] if (_face or {}).get("state") == _fa.REDRAWN else ensure_flat_motifs(
        aria, output, spec, (backbone.width_mm, backbone.height_mm))
    _made: list = []
    try:
        _inputs = _composer_inputs(aria.task, output, spec, records=_made)
    finally:
        _write_records(spec, _made)
    resolved, ref_path = _inputs["resolved"], _inputs["ref_path"]
    colors, _sources, _motif_sourced = _inputs["colors"], _inputs["sources"], _inputs["motif_sourced"]
    zones, product_name, name_lines = _inputs["zones"], _inputs["product_name"], _inputs["name_lines"]
    profile_record, motif_spec = _inputs["profile_record"], _inputs["motif_spec"]
    logo_path, logo_master = _inputs["logo_path"], _inputs["logo_master"]
    methods_record = _inputs["methods_record"]

    # 2C-2E-CORR-1: the confirmed dropper path composes through the
    # DEDICATED designer-grade sheet composer — believable cylindrical
    # geometry, three-part closure, frosted material stack, live hierarchy,
    # readable back, bottom diagram, 12-section presentation. Colours are
    # concept authority from the selected render's measured palette. Every
    # non-dropper container keeps compose_container_graph byte-identically.
    back_sections, content_codes = [], []   # §BH50(f)(2): stated on every path
    if geometry is not None:
        back_sections, content_codes = _back_sections_from_record(
            aria.task.product, _dm_back(aria.task))
        # [his final goal, 2026-10-05, A] the back in English, then Spanish, then Arabic — translated once, here;
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] each piece the record has
        # not given written for the product's type, in the form measured on this back (its codes stay: never his copy)
        _label = ensure_label(aria, spec, _inputs["zones"], backbone.width_mm,
                              methods_record=_inputs["methods_record"], record_sections=back_sections)
        back_sections = _label["sections"]
        english_back = list(back_sections)
        back_sections, trilingual_codes = trilingual_sections(back_sections, _label["kept"],
                                                              languages=label_languages(spec))
        spec["container_back_content_codes"] = content_codes
        rejections = sorted(k for k in spec if k.startswith(
            "container_reconstruction_rejected"))
        status_line = (f"HUMAN GATE-2: REJECTED ({len(rejections)}) → "
                       "CORRECTED — awaiting human review"
                       if rejections else
                       "FIRST RECONSTRUCTION — awaiting human review")
        from apps.ire.compose_dropper import FRONT_COPY_FIT_SCHEMA, PALETTE_SCHEMA, compose_dropper_sheet
        # §BH55 Phase 4: the same three hexes, named and measured at HANDOFF_COLOURS above — including what this
        # rebind discards (the concept-authority colours built at the top of this function) and who reads the
        # result (the native handoff). No hex moves: the choice is entry 12 on the ACCEPTANCE-TIME list.
        colors = dict(HANDOFF_COLOURS)
        # §13: prior outputs appear on the sheet as REVIEW references
        prior_outputs = []
        from django.conf import settings as _settings
        for i, key in enumerate(rejections):
            png = ((spec.get(key) or {}).get("rejected_output") or {}
                   ).get("design_preview")
            if png:
                path = os.path.join(_settings.MEDIA_ROOT, png)
                if os.path.exists(path):
                    prior_outputs.append(
                        (f"REJECTED r{i + 1}" if i == 0
                         else f"CORR-{i} (rejected)", path))
        # §BH67(c)2: the front's descriptor is the PRODUCT RECORD's — §BH65(b)1's derivation from `product_type` — and a
        # silent record prints nothing; [his answers after the fixes for design 122, (2)] its net content his brief's
        # size, else the record's `net_weight` as held (`net_content`)
        from apps.ire.front_hierarchy import descriptor_for as _descriptor_for
        def _dropper_sheet(sections):
            # [his final goal, 2026-10-05, C5c] the one production call — the design's own back, and each offer's
            return compose_dropper_sheet(
                geometry, zones=zones, reference_path=ref_path,
                logo_path=logo_path, product_name=product_name,
                sku=spec.get("sku", ""), back_sections=sections,
                revision_status=status_line, prior_outputs=prior_outputs,
                methods_record=methods_record,
                drawing_source=sheet_source, backbone=backbone,
                descriptor=_descriptor_for(spec, aria.task.product),
                net_content=net_content(aria.task),     # [his answers after the fixes for design 122, (2)]
                # [his review of 127, 130, 131 and 132, 2026-10-15, C (7)] the back's QR, where it was measured to stand
                **({"back_qr_url": _label["qr"]} if _label["qr"] and (spec.get(LABEL_FORM_KEY) or {}).get("qr")
                   else {}),
                **_brand_mark.master_kwargs(logo_master))
        doc = _dropper_sheet(back_sections)
        # §BH50(b): the composer's record of whether the confirmed front zone holds the small copy at the
        # floor is persisted, so it is read — the back panel's named overrun lives in document metadata
        # nothing reads, and a name nothing reads says nothing
        if FRONT_COPY_FIT_SCHEMA in doc.metadata:
            spec[FRONT_COPY_FIT_SCHEMA] = doc.metadata[FRONT_COPY_FIT_SCHEMA]
        # §BH50(f)(3): the front-copy codes from THIS run's document, never
        # from the spec, which is seeded from the previous run
        # [THE OWNER'S SECOND ANSWER OF 2026-09-25, found by task 52's redraw: since Gate 2 measures the front's height a
        # fit record can carry NO code — a clean front — and the `or` that stood here read that empty list as "no fit
        # record on this run", a blocking code on a front that holds. Only a missing record is unmeasured now.]
        front_copy_fit_record = doc.metadata.get(FRONT_COPY_FIT_SCHEMA)
        if front_copy_fit_record is None:
            front_copy_codes = ["CONTAINER_FRONT_COPY_FIT_UNMEASURED: no fit record on this run"]
        else:
            front_copy_codes = list(front_copy_fit_record["codes"])
        # §BH50(d): the palette the sheet is drawn with, persisted so the Review Board reads it
        if PALETTE_SCHEMA in doc.metadata:
            spec[PALETTE_SCHEMA] = doc.metadata[PALETTE_SCHEMA]
        # §BH54(b) (q): "a named blocker, not a silence". The comment above named this gap and left it — "the back
        # panel's named overrun lives in document metadata nothing reads". It is read now: the fit record of THIS
        # run's document is persisted, and its codes are the back_copy readiness section — at acceptance, never here
        from apps.ire import back_panel as _back_panel
        from apps.ire.container_production_readiness import back_copy_codes as _back_copy_codes
        if _back_panel.SCHEMA in doc.metadata:
            spec[_back_panel.SCHEMA] = doc.metadata[_back_panel.SCHEMA]
        back_copy_codes = _back_copy_codes(doc.metadata.get(_back_panel.SCHEMA)) + trilingual_codes
        # [his final goal, 2026-10-05, C5c] a back that cannot stand: the stop offers each set of fewer languages its
        # back holds, measured and drawn by composing the sheet again — nothing paid
        _stopped = [c for c in back_copy_codes if str(c).startswith("CONTAINER_BACK_COPY_DOES_NOT_FIT")]
        _save_label_offers(spec, aria.task.id, back_label_offers(
            _dropper_sheet, english_back, _label["kept"], label_languages(spec))
            if _stopped else [], _stopped)
    else:
        # §BH54(b) (q): the generic composer draws no true-scale back panel, so nothing measures its back copy
        back_copy_codes = ["CONTAINER_BACK_COPY_FIT_UNMEASURED: no back panel instrument on this path"]
        # §BH50(f)(3)/(5) said here that the generic composer had front copy and no fit instrument, and that which
        # rectangle is its zone (backbone.label_zone scaled by s, not the confirmed FRONT_PRINT_ZONE) was a contract
        # question first. §BH70(1), item 5 of the list the owner was sent: that question decides where a line sits and
        # how tall the block is, not how wide a line is — so the front copy is measured ACROSS once the finishes are
        # applied, below (`generic_front_copy_fit`), and the rest stays UNMEASURED with its reason.
        # §BB7(c)'s ruled front, the concept's arrangement, the name's face and, on a FACE form, the reading of the
        # concept's arrangement, its Arabic line, display name and vision layout: ONE DERIVATION, TWO CALLERS —
        # `_front_plan`, moved there unchanged, with the composer's whole call; drawn by the composer's one call
        # (`_compose_front`). The vision read is `cached_or_read` here: it SPENDS when the picture has not been read.
        from apps.pipeline.services import concept_layout as _clayout
        # [his final goal, 2026-10-05, A] the back's English translated once, here, before the plan reads it;
        # [his review of 127, 130, 131 and 132, 2026-10-15, C (7): "NEVER AN EMPTY LABEL"] the full set — the pieces
        # his words leave empty written once for the product's type, the form they are set in measured on this back
        ensure_label(aria, spec, _inputs["zones"], backbone.width_mm, methods_record=_inputs["methods_record"],
                     packaging=_is_face(_inputs["archetype"]))
        _made = []
        try:
            _front = _front_plan(aria.task, spec, _inputs, records=_made, read_layout=_clayout.cached_or_read)
        finally:
            _write_records(spec, _made)
        concept_front_plan = _front["concept_front"]
        from django.conf import settings as _settings_map
        from .readable import FROM_TEMPLATE_KEY as _FROM_TEMPLATE
        _template = (getattr(output.approved_image, "reference_provenance", None) or {}).get(_FROM_TEMPLATE)
        if _settings_map.DESIGN_MAP_READ and _is_face(_inputs["archetype"]) and not _template and not (
                (_inputs.get("map_front") or {}).get("lid_art")):
            # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (4): "NO SILENT FALLBACK, ever"] a face form
            # is drawn from its concept's map and its art, never from its form's own layout — said, by name; his own
            # "draw from template" (his blocker on 122, item 4) the one door past it, said at Gate 1
            raise RuntimeError("its lid is not drawn: %s" % (
                "its lid's art is not on record for this concept" if _inputs.get("map_front")
                else "its concept's map is not on record for its lid"))
        doc = _compose_front(backbone, _front["compose"])
        _tray_drawn = (doc.metadata.get("open_tray") or {}).get("pans")
        # [his goal of 2026-10-12: "Add 1, 4, 5, 6, 9 and 10 to the wiring check."] the tray as drawn — its finishes
        # measured, its inks, its names against their floor, the lid's inside — on the record the checks read
        _tray_record = doc.metadata.get("open_tray") or {}
        if _tray_record.get("pans_drawn") is not None:
            spec[OPEN_TRAY_DRAWN_KEY] = {k: _tray_record.get(k) for k in (
                "pans_drawn", "rim_hex", "glow_hex", "name_hex", "name_pt", "name_floor_pt", "name_contrast_de",
                "lid_inside")}
        elif OPEN_TRAY_DRAWN_KEY in spec:
            del spec[OPEN_TRAY_DRAWN_KEY]
        if _tray_drawn:
            spec[TRAY_PANS_KEY] = _tray_drawn                # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (5)] listed where he reviews
        elif TRAY_PANS_KEY in spec:
            del spec[TRAY_PANS_KEY]
        if (_inputs.get("map_front") or {}).get("lid_art"):
            from apps.pipeline.services.concept_design_map import is_gold_hex as _is_gold
            spec[LID_ART_DRAWN_KEY] = {k: v for k, v in _inputs["map_front"]["lid_art"].items()
                                       if k not in ("sky", "regions")}
            # [his goal of 2026-10-12, (4)] how many of its regions the picture's gold drew — the foil plate's to hold
            spec[LID_ART_DRAWN_KEY]["gold_regions"] = sum(1 for r in _inputs["map_front"]["lid_art"]["regions"]
                                                          if _is_gold(r["fill"]))
            # [his goal of 2026-10-13, (7)-(9)] where it is drawn on the sheet and how — read by the wiring check
            spec[LID_ART_DRAWN_KEY]["drawn"] = (((doc.metadata or {}).get("map_front") or {}).get("lid_art") or {})
        # [his rules for cloning a design from a picture, 2026-10-02, rule 5: "THE BACK IS DRAWN"] the brief's back copy
        # the composer drew, and its panel's fit at the size it prints: read as the dropper's is (§BH54(b) (q)); a run
        # that drew no panel leaves none behind from a previous one, and stays UNMEASURED with its reason
        from apps.ire import back_panel as _back_panel
        from apps.ire.container_production_readiness import back_copy_codes as _back_copy_codes
        back_sections = list(_front["compose"].get("back_sections") or [])
        if _back_panel.SCHEMA in doc.metadata:
            spec[_back_panel.SCHEMA] = doc.metadata[_back_panel.SCHEMA]
            back_copy_codes = _back_copy_codes(doc.metadata[_back_panel.SCHEMA]) + list(_front["back_codes"])
        elif _back_panel.SCHEMA in spec:
            del spec[_back_panel.SCHEMA]
        # [his final goal, 2026-10-05, C5c] a back that cannot stand: the stop offers each set of fewer languages its
        # back holds, measured and drawn by composing the sheet again — nothing paid
        _stopped = [c for c in back_copy_codes if str(c).startswith("CONTAINER_BACK_COPY_DOES_NOT_FIT")]
        _save_label_offers(spec, aria.task.id, back_label_offers(
            lambda secs: _compose_front(backbone, dict(_front["compose"], back_sections=secs)), _front["back_english"],
            _front["back_kept"], label_languages(spec)) if _stopped else [], _stopped)

    # §BH65(c)2: THE FINISHES THE CONCEPT NAMED, APPLIED TO WHAT THE COMPOSER DREW — before any instrument reads the
    # document, so every reading is of the document that is emitted. Each clause of the concept's finish sentence
    # lands on the elements its targets name; a target not drawn is recorded NOT_DRAWN and the lockup (a raster)
    # REFUSED_NO_VECTOR_MASTER, by name. Foil depicts in the brand's own Metallic record — its flat stand-in when
    # the record carries no hex, which is the stand-in `colour_sources` names for "Caps, closures, foil detail".
    # [The owner's second answer of 2026-09-25: a lockup drawn from its approved vector master takes the finish —
    # APPLIED, its plate cut from the master's own outlines.]
    from apps.ire import container_finishes as _finishes
    finish_application = _apply_finishes(doc, _finish_inputs(aria.task, _inputs))
    # [his final goal, 2026-10-05, C7: "THE SYSTEM CHECKS ITS OWN WORK"] the traced outlines and the signs repaired
    # before anything measures or draws the graph; the drawn sheet read after it is drawn
    from apps.ire import self_check as _self_check
    _check_regions = _self_check.sheet_frame(doc)
    _check_fixed, _check_shown = _self_check.repair_said(doc, _check_regions)
    if geometry is None:
        # [his answer 3 of 2026-10-02 (6badb27): "The score's yardstick is a full-size trace of the concept, so it can say
        # 'matches' without my eye."] the drawing, its finishes applied, against its concept's full-size trace; a run
        # that drew no front from its picture leaves none behind from a previous one
        from apps.pipeline.services import concept_design_map as _dm_score
        _traced = (_inputs.get("map_front") or {}).get("shapes")
        _pic = _map_bytes(output.approved_image, _inputs["archetype"])     # [his test blocker on design 124, 2026-10-11 (OWNER_BLOCKER_CLEARANCE.md, transcribed at 6cd2bc6), (2)] a lid's
        _png = _dm_score.product_png(doc, px_per_mm=_dm_score.SCORE_PX_PER_MM) if _traced else None
        if _traced and _pic and _png:
            spec[_dm_score.SCORE_TRACED_SCHEMA] = _dm_score.score_traced(
                _traced, _pic, spec.get(_dm_score.SCHEMA) or {}, _png,
                drawn_boxes=((doc.metadata or {}).get("map_front") or {}).get("boxes") or {},
                size_mm=(backbone.width_mm, backbone.height_mm),
                edge_to_edge=((doc.metadata or {}).get("map_front") or {}).get("edge_to_edge"))
        else:
            spec.pop(_dm_score.SCORE_TRACED_SCHEMA, None)
        # §BH70(1), item 5 of the list the owner was sent: the generic path's front copy, measured on the document that
        # is emitted — its finishes applied — against the confirmed zone; the record is THIS run's, and a run with no
        # confirmed front zone leaves none behind from a previous one
        from apps.ire.compose_dropper import FRONT_COPY_FIT_SCHEMA as _FIT_SCHEMA
        _generic_fit = generic_front_copy_fit(doc, zones, profile.archetype, laid_in_zone=(
            spec.get(FRONT_LABEL_SCHEMA) or {}).get("source") == FRONT_LABEL_CONFIRMED)
        if _generic_fit is None:
            if _FIT_SCHEMA in spec:
                del spec[_FIT_SCHEMA]
            front_copy_codes = [f"CONTAINER_FRONT_COPY_FIT_UNMEASURED: {GENERIC_NO_FRONT_ZONE}"]
        else:
            spec[_FIT_SCHEMA] = _generic_fit
            front_copy_codes = list(_generic_fit["codes"])

    # §BH67 HARD STOP, made a check the run cannot pass silently: every colour a PRINTED element of the container
    # composer's product carries is one a record names, or its code blocks ACCEPTANCE by name (readiness, below).
    # The dropper composer's palette is §BH50(f)(9)'s, kept as ruled, and is not read here — the record says so.
    if geometry is not None:
        printed_audit = {"schema_version": _cs.PRINTED_SCHEMA, "state": "NOT_READ", "codes": [],
                         "why": "the dropper composer prints from §BH50(f)(9)'s palette, kept as ruled; this audit "
                                "reads the container composer's product"}
    else:
        from apps.ire.compose_container import declared_tints
        _sourced = {}
        # [the owner's second answer of 2026-09-25: the face's rule prints in the colour its own record names, read
        # beside the others — and its ring]
        # [His review of 127, 130, 131 and 132, 2026-10-15, D (11)] and each closure part read on its own part
        for _key in ("cap", "body", "product", "ink", "rule", "ring", "bulb", "collar"):
            if colors.get(_key):
                _sourced.setdefault(colors[_key], "%s — %s" % (_key, _sources.get(_key)))
        for _hx, _src in _motif_sourced:
            _sourced.setdefault(_hx, "motif — " + _src)
        _edge = ((concept_front_plan or {}).get("window_fill") or {}).get("edge")
        if _edge:
            _sourced.setdefault(_edge, "window gradient edge — the concept's own `color_field_signature`, the colour "
                                       "it names after \"gradient\"")
        for _hx, _what in declared_tints(colors).items():
            _sourced.setdefault(_hx, _what)
        # [his answer after test day finding 3, (1)] the map front's colours, each the concept picture's own
        for _hx, _what in map_front_colour_sources(_inputs.get("map_front")).items():
            _sourced.setdefault(_hx, _what)
        printed_audit = _cs.printed_colour_audit(doc, _sourced)
    spec[_cs.PRINTED_SCHEMA] = printed_audit

    # §BH67(c)5: the face the concept named for its product name, and the face that printed it — the concept's own
    # when it sits in the granted set and the layer verified it, else the display chain's, with the refusal by name
    if geometry is None and (concept_front_plan or {}).get("typeface"):
        from apps.ire import concept_typeface as _ctype
        from apps.ire.font_roles import CONCEPT_NAME, resolve_document
        _typeface = dict(concept_front_plan["typeface"])
        _led = resolve_document(doc)["resolutions"].get(CONCEPT_NAME)
        _typeface["drawn"] = ({"by": "the display chain — the concept named no granted face that can lead"}
                              if _led is None else
                              {"by": "the concept's own face" if _led.get("stem") == (_typeface.get("name") or {})
                               .get("stem") else "the display chain — the lead did not verify",
                               "stem": _led.get("stem"), "postscript": _led.get("postscript"),
                               "tried": _led.get("tried")})
        spec[_ctype.SCHEMA] = _typeface

    # §BH67(b)2: WHERE THE DISPLAY WORDMARK DROPS — text, face and size, each with its state — for a face form
    if geometry is None and ((concept_front_plan or {}).get("face") or {}).get("display_name"):
        from apps.ire import display_name as _dname
        from apps.ire.font_roles import resolve_document as _resolve
        _faces = _resolve(doc)["faces"]
        _name_font = next((n.font for n, _ in doc.walk() if (n.name or "").startswith("product-name-hero")), "bold")
        _drawn_face = (_faces.get(_name_font) or _faces.get("display") or (None,))[0]
        _reading = concept_front_plan["face"]["display_name"]
        # §BH68(b): the size the face drew — its scale step, on the face's own record — never the bottle's tier
        _step = (((doc.metadata or {}).get("concept_front") or {}).get("face") or {}).get("name_size")
        spec[_dname.SCHEMA] = dict(_reading, drops=_dname.drops(
            _reading, typeface=concept_front_plan.get("typeface"), name_size_pt=(_step or {}).get("step_pt"),
            drawn_face=_drawn_face, name_size=_step))

    # §BH67(d)2 / (e): THE LAYOUT MEASURE — each element's box in the DRAWN file against the concept's, as fractions of
    # the surface, read off the drawn nodes (the name and Arabic runs at their emitted advance widths)
    _vision_rec = ((concept_front_plan or {}).get("face") or {}).get("vision_layout") if geometry is None else None
    if (_vision_rec or {}).get("state") == "READ":
        from apps.pipeline.services import concept_layout as _clayout
        _zone_box, _drawn = face_drawn_boxes(doc)
        spec[_clayout.MEASURE_SCHEMA] = {"schema_version": _clayout.MEASURE_SCHEMA, "governed_by": "§BH67(e)",
                                         "surface_mm": _zone_box, "rows": _clayout.measure(_vision_rec, _drawn)}

    # §8 honesty: only the zones an artwork placement was actually emitted into
    # are "consumed" (front-view emission today; back/cap/side not yet drawn).
    emitted_zone_ids = sorted({p.get("zone_id")
                               for p in (doc.metadata.get("placements") or [])
                               if p.get("zone_id")})
    graph_record = container_design_graph_record(
        doc, zones_consumed=emitted_zone_ids, mode="native")
    # VQR-1: structural provenance + measurable geometry facts. These keys
    # are exactly what the VQR-2A gate honors: closure_assembly flips the
    # closure axis from UNMEASURED, product_bounds flips silhouette
    # fidelity, and the artboard evidence is in the emitted document
    # itself. Absent honestly when the composer did not produce them.
    graph_record["backbone_source"] = structure_record["backbone_source"]
    if structure_record.get("closure_assembly"):
        graph_record["closure_assembly"] = \
            structure_record["closure_assembly"]
    _pb = doc.metadata.get("product_bounds_mm")
    if _pb:
        _MMPT = 72.0 / 25.4
        graph_record["product_bounds"] = {
            "width_pt": round(_pb[0] * _MMPT, 3),
            "height_pt": round(_pb[1] * _MMPT, 3)}
    if doc.metadata.get("artboard_mm"):
        graph_record["artboard_mm"] = doc.metadata["artboard_mm"]
        graph_record["artboard_policy"] = doc.metadata.get("artboard_policy")
    # [his goal of 2026-10-10, item 2] the sheet's height a palette's open tray takes at the size it prints
    _tray = doc.metadata.get("open_tray")
    if isinstance(_tray, dict) and _tray.get("sheet_grown_mm"):
        graph_record["open_tray_sheet_mm"] = _tray["sheet_grown_mm"]

    # Design Graph 2.0: promote the 1.1 census into a record that also names
    # its SEMANTIC COMPONENTS, each with recorded provenance. Additive by
    # construction — every 1.1 key survives, and build() refuses if any key
    # the visual-quality gate reads (product_bounds, reconstruction_
    # silhouette, closure_assembly) were dropped, because that loss would
    # otherwise be silent and simply re-UNMEASURE an axis.
    #
    # Components are derived ONLY from what the composer's own naming makes
    # evident; an unclassifiable node stays a primitive in the census rather
    # than being guessed into a role. bounds_mm and constraints stay absent:
    # no producer measures them yet, and inventing a value to populate the
    # field is what the provenance rule forbids.
    from apps.ire import design_graph_v2 as _dg2
    graph_record = _dg2.build(
        graph_record,
        components=_dg2.components_from_document(
            doc, backbone_source=structure_record["backbone_source"]))

    # 2B-2 slice 3: project each confirmed zone onto its surface curvature and
    # validate that every emitted placement is contained (§6/§7).
    from apps.ire.container_fidelity import measure_fidelity
    from apps.pipeline.services import container_projection as cp
    projection = cp.project_zones(zones, profile_record)
    containment = cp.validate_zone_containment(
        doc.metadata.get("placements") or [], zones, profile_record)
    containment += round_lid_problems(doc)            # §BH71 PART 1: a round lid's circle, measured

    # 2B-2 slice 4: measure the EMITTED artwork against the selected-concept
    # visual graph (three-state — MEASURED_PASS / MEASURED_FAIL / UNMEASURED).
    fidelity = measure_fidelity(
        doc, spec.get(cvg.SCHEMA) or {}, name_lines=name_lines,
        census=graph_record.get("primitives"), zones=zones)

    # 2B-2A: measure the EMITTED motif geometry vs the motif spec (a SUPPORTED
    # motif that rendered its expected node type now PASSES); and the emitted
    # front/back relationship (§6).
    from apps.ire.container_fidelity import measure_front_back
    from apps.ire.container_motif_fidelity import (
        validate_motif_fidelity,
        validate_typography_hierarchy,
    )
    motif_fidelity = validate_motif_fidelity(doc, motif_spec)
    # 2B-3V-CORR-3 §7: the emitted type must carry the hierarchy, not merely
    # exist — the product name visibly dominant over supporting copy.
    typography_fidelity = validate_typography_hierarchy(doc, product_name)
    # §6: the concept's front/back INTENT is vision-only (UNMEASURED); this
    # measures the EMITTED roles and fails only on a real collapse (a hero
    # motif on the back, or a non-hero front).
    front_back = doc.metadata.get("front_back_relationship") or {}
    front_back.update(measure_front_back(doc))

    # VQR-3: measure the logo AS EMITTED. The visual-quality gate has read
    # container_logo_metrics/1.0 since VQR-2A with no producer, so the logo
    # axis has been UNMEASURED — blocking — for the whole arc. The owner's
    # confirmed asset paths are passed in so the record can say whether the
    # file that rendered is the file the owner authorised; it reports unknown
    # rather than False when no confirmation record is on disk.
    from apps.ire import container_logo_metrics as clm
    logo_metrics = clm.measure_logo_metrics(
        doc, confirmed_assets=_owner_confirmed_logo_assets())
    if logo_metrics is not None:
        spec[clm.SCHEMA] = logo_metrics

    # VQR-3: the composition axis reads container_composition_metrics/1.0 and
    # has had no producer for the same reason. It supplied two of three fields
    # and omitted blocking_overlaps, which was a design policy no owner record
    # stated, until §W3 stated it. All three are measured now, so the axis is
    # decidable — and still goes UNMEASURED where §W3(d) applies.
    from apps.ire import container_composition_metrics as ccm
    composition_metrics = ccm.measure_composition_metrics(doc)
    if composition_metrics is not None:
        spec[ccm.SCHEMA] = composition_metrics

    # VQR-4: the last gate-read contract with no producer. The typography
    # axis was worse than unmeasured — a partial record PASSED it, because
    # three absent defect flags read as False. The gate now demands presence.
    # The two fields this withheld as design policy were ruled by §W5
    # (placeholder allow-list) and §W3 (overlap), so all four are measured —
    # and any one of them going absent still returns the axis to UNMEASURED.
    # §W2 made the production-method capability table the authority on the
    # typography size floor, so the methods are derived BEFORE the axis that
    # reads them — `methods_record` is built once above the composition (§Z3)
    # and is the SAME object the back panel was set from. Its result is used
    # unchanged; validation still runs in the production-readiness block.
    from apps.ire import container_typography_metrics as ctm
    typography_metrics = ctm.measure_typography_metrics(doc, methods_record)
    if typography_metrics is not None:
        spec[ctm.SCHEMA] = typography_metrics

    # 2B-3A §1/§2: font authority + confirmation gate. This is a PRODUCTION-
    # READINESS concern — the codes do NOT enter `blockers` (concept review
    # continues on the fallback face; Gate-2 approval enforces them in 2B-3D).
    from apps.ire.container_font_authority import (
        build_font_authority,
        font_confirmation_gate,
    )
    # §BH26(b): THE PRODUCER GOES LIVE. When the caller passes no mapping —
    # every production call — the seam is fed from the live c4c face_manifest
    # join over the faces the emitter will actually use: ceiling
    # LICENCE_REVIEW_REQUIRED, source MACHINE_DERIVED, nothing above. Absent
    # or unreadable evidence (a clean clone) yields nothing and the default
    # column stands. An explicit mapping from a caller is honoured as before.
    if confirmed_fonts is None:
        from apps.ire.container_font_evidence_join import join_document_fonts
        confirmed_fonts = join_document_fonts(doc)["confirmed_fonts"]
    font_authority = build_font_authority(doc, confirmed_fonts=confirmed_fonts)
    # §BH26(a): the OWNER-GRANT channel — owner-conferred states enter as
    # OWNER DATA, after the build and before the gate. Fail-closed: the
    # licence file is re-hashed on every application and only the two
    # sha256-named faces can receive anything; a void grant falls back to
    # LICENCE_REVIEW_REQUIRED through the machine guard. The channel is not
    # the seam and no ceiling moved to admit it.
    from apps.ire.container_font_owner_grant import apply_owner_grant
    font_authority = apply_owner_grant(font_authority)
    font_gate_codes = font_confirmation_gate(font_authority)

    # 2B-3A §3/§4/§5: material-influence realization. Reuses the task-scoped
    # approved references + persisted influence plan; NOT_APPLICABLE when the
    # task has none (the common path). Also a production-readiness concern —
    # its code is NOT a reconstruction blocker.
    from apps.pipeline.services import concept_references as cr
    from apps.pipeline.services import container_material_realization as cmr
    _approved = cr.approved_references(aria.task)
    _plan_obj = getattr(aria.task, "concept_influence_plan", None)
    if _approved and _plan_obj is not None:
        plan = dict(_plan_obj.plan or {})
        plan.setdefault("plan_hash", _plan_obj.plan_hash)
        material_realization = cmr.build_realization(aria.task, doc, plan)
    else:
        material_realization = cmr.not_applicable_realization(aria.task)

    # 2B-3B §1-§5/§9/§10: production methods DERIVED from the confirmed-zone
    # techniques (authority UNVERIFIED by construction — no manufacturer
    # evidence channel this phase) + validation against the EMITTED geometry.
    # Production-readiness codes, NOT reconstruction blockers.
    from apps.ire.container_production_method import (
        validate_production_methods,
    )
    method_validation = validate_production_methods(
        methods_record, zones, profile_record, doc)

    # 2B-3B §6-§8/§11-§14: production separations + swatch/spot contract. A
    # data manifest with visibility defaults — finishes are hidden named
    # separations, never opaque fills painted over the artwork (§7).
    from apps.ire.container_separations import (
        build_separations,
        combined_production_hash,
    )
    separations_record = build_separations(
        methods_record, doc, zones, profile_record)
    production_combined_hash = combined_production_hash(
        methods_record, separations_record)

    # 2B-3C §2-§6: quantitative fidelity — gates only against RELIABLE
    # selected-concept targets (coverage/logo/name); everything else is
    # UNMEASURED by construction. A MEASURED_FAIL is a production-readiness
    # finding, NOT a reconstruction blocker.
    from apps.ire.container_quant_fidelity import measure_quantitative_fidelity
    quant_fidelity = measure_quantitative_fidelity(
        doc, spec.get(cvg.SCHEMA) or {}, motif_spec, zones=zones)

    # 2B-3C §7-§10: true seam-aware wrap PRODUCTION geometry (a data record,
    # not a re-emission) + alignment measurement. Readiness codes, not blockers.
    from apps.ire.container_wrap_geometry import (
        build_wrap_geometry,
        validate_wrap_alignment,
    )
    wrap_geometry = build_wrap_geometry(zones, profile_record)
    wrap_alignment = validate_wrap_alignment(wrap_geometry, doc, zones)

    # 2B-3C §11-§14: per-method coverage + registration + complete colour count
    # + label density. Readiness codes, not reconstruction blockers.
    from apps.ire.container_production_metrics import build_production_metrics
    production_metrics = build_production_metrics(
        doc, methods_record, separations_record, zones, spec.get(cvg.SCHEMA) or {})

    # 2B-3C §15-§17: precise per-reference material attribution + similarity
    # risk (additive material_influence_*/1.1; the 2B-3A /1.0 record stays).
    from apps.pipeline.services import container_material_influence as cmi
    if _approved:
        influence_plan_11 = cmi.build_container_influence_plan(aria.task, _approved)
        material_realization_11 = cmi.build_container_realization(
            aria.task, doc, influence_plan_11)
        similarity = cmi.similarity_risk(material_realization_11)
    else:
        influence_plan_11 = None
        material_realization_11 = cmi.not_applicable_realization(aria.task)
        similarity = {"flagged_reference_ids": [], "codes": []}

    # reconstruction blockers: an unrebuildable motif (§3, distinct code), a
    # projection review, an out-of-zone placement, a MEASURED_FAIL base- or
    # motif-fidelity axis, or a collapsed front/back relationship. UNMEASURED
    # axes never block the RECONSTRUCTION; since §BH50(f)(5) they block
    # ACCEPTANCE — Gate-2 approval — through
    # container_production_readiness.fidelity_unmeasured, derived at read time
    # and never persisted here.
    # 2C-2E §15: ACTUAL geometry/material fidelity of the emitted dropper —
    # measured node boxes and opacities against the HUMAN-confirmed values.
    # Failures are reconstruction blockers: a generic schematic bottle, a
    # collapsed material stack or a label-like front must not pass.
    concept_fidelity = None
    if geometry is not None:
        from apps.ire.container_concept_fidelity import (
            measure_concept_fidelity,
        )
        concept_fidelity = measure_concept_fidelity(doc, geometry)
        spec["container_concept_fidelity/1.0"] = concept_fidelity
        spec["container_material_objects/1.0"] = {
            "schema_version": "container_material_objects/1.0",
            "objects": [
                {"name": n, "printing": n not in (
                    doc.metadata.get("nonprinting_objects") or [])}
                for n in ("GLASS_OUTER_WALL", "GLASS_INNER_WALL",
                          "FROST_TREATMENT", "PRODUCT_FILL_APPEARANCE",
                          "LEFT_EDGE_CURVATURE", "RIGHT_EDGE_CURVATURE",
                          "CENTRAL_GLASS_LIGHT", "GLASS_SPECULAR",
                          "SHOULDER_REFRACTION", "GLASS_BASE_THICKNESS",
                          "BASE_REFRACTION", "COLLAR_ROSE_GOLD_BASE",
                          "COLLAR_ROSE_GOLD_LIGHT",
                          "COLLAR_ROSE_GOLD_SPECULAR",
                          "COLLAR_ROSE_GOLD_SHADOW", "COLLAR_TOP_RIM",
                          "COLLAR_BOTTOM_RIM", "BULB_DARK_PLUM",
                          "FRONT_DIRECT_PRINT", "BACK_DIRECT_PRINT",
                          "BOTTOM_TECHNICAL_CODE")],
            "nonprinting_visualization":
                doc.metadata.get("nonprinting_objects") or [],
            "classification": "PHOTOGRAPHIC_STYLING_NOT_PRINTED_ARTWORK",
        }

    blockers: list[str] = []
    if concept_fidelity is not None:
        blockers.extend(concept_fidelity["failures"])
    if motif_spec.get("reconstruction_capability") == cm.CAP_REVIEW_REQUIRED:
        blockers.append(motif_spec.get("review_code",
                                       cm.VECTOR_RECONSTRUCTION_REVIEW_REQUIRED))
    if projection.get("review_required"):
        blockers.append(projection["code"])
    # [his answer on the print area's safe margin, 2026-10-01: a part inside the margin where the concept picture prints
    # it is a production note beside Approve, never a block]
    from apps.ire.container_production_readiness import is_production_note as _is_note
    containment_notes = [c for c in containment if _is_note(c)]
    containment = [c for c in containment if not _is_note(c)]
    blockers.extend(containment)
    blockers.extend(fidelity["failures"])
    blockers.extend(motif_fidelity["failures"])
    blockers.extend(typography_fidelity["failures"])
    if front_back and not front_back.get("roles_distinct", True):
        blockers.append("CONTAINER_FRONT_BACK_RELATIONSHIP_FAILED")
    # [his test finding on design 122's drawing, 2026-10-08, A and B] a motif not redrawn flat, or not whole, and a
    # colour drawn that drifts from the concept's, each stop the drawing, said
    from apps.pipeline.services import flat_motif as _fm
    blockers.extend(_flat_refused)
    blockers.extend(flat_motif_codes(_inputs.get("map_front")))
    _colour_check = colour_check_of(colors, _sources, _inputs.get("map_front"))
    if _colour_check["codes"]:
        # [his goal of 2026-10-13, (1): "A failing check fixes the drawing itself and re-checks"] a colour that drifts from
        # the concept's is redrawn in the concept's own, said as a fix; the check is run again on what it made
        _recoloured = repair_drifting_colours(doc, colors, _inputs.get("map_front"), _colour_check)
        if _recoloured:
            _check_fixed += [{"kind": "colour", "fixed": True, "what": w} for w in _recoloured]
            _colour_check = colour_check_of(colors, _sources, _inputs.get("map_front"))
    spec[_fm.COLOUR_CHECK_SCHEMA] = _colour_check
    blockers.extend(_colour_check["codes"])

    # §AU5(4)/§AU8(e) — THE ARTEFACT GATE, and the reason it sits HERE.
    # `emit_pdf_ai` ran on this line unconditionally: 72 lines before
    # `brand_string_report` computed whether the document was fit to be seen,
    # and 105 before the fail-closed raise below. Both the .ai and the PNG were
    # attached to `output` and persisted by the `output.save()` further down, so
    # a BLOCKED reconstruction still shipped an editable .ai to
    # `review_board.py:203` (`editable_ai_url`) and to the composite's
    # "Editable Design .ai" row. The verdict was computed; the artefact had
    # already outrun it.
    #
    # The REPORT moves up rather than the emit moving down, because the emit is
    # the thing that must be conditional. A gate that runs after the file exists
    # is a description of the file, not a gate on it.
    # [his goal of 2026-10-13, (1): "NO check ever stops a design"] a line whose words the owner did not supply is left out
    # of the drawing — never drawn (§AE2(c)) — and said beside Approve; the design and its files go on without it
    from apps.ire.brand_string_runtime import leave_out_provisional as _leave_out
    _left_out = _leave_out(doc)
    brand_strings = brand_string_report(doc)
    if _left_out:
        brand_strings = dict(brand_strings, left_out=_left_out)
    # ONLY the brand strings withhold. A geometry blocker does NOT, and the
    # distinction is deliberate rather than an oversight — my first version of
    # this gate seeded it with `list(blockers)`, which silently reversed a
    # decision this repository had already made and recorded:
    # `FailClosedAtTheReconstructionGateTests` is titled "A blocked
    # reconstruction refuses — and keeps its evidence", and asserts the refused
    # artwork "is still on the output to look at". That test going red is what
    # found the overreach.
    #
    # The two are not the same claim and do not earn the same treatment. A
    # geometry-blocked .ai is DIAGNOSTIC: a reviewer opens it to see what the
    # reconstruction got wrong, which is the whole reason it is kept. A
    # provisional brand string is not a diagnosis of a broken artefact — its
    # presence in a downloadable .ai IS the §AE2(c) violation, because the
    # clause reserves brand copy to the owner and the file hands invented copy
    # to them under the house's name. Evidence for a reviewer and an artefact
    # for an owner are different objects; only the second is withheld here.
    artefact_withheld = (list(brand_strings["codes"])
                         if not brand_strings["clean"] else [])

    ai_name = png_name = None
    # §BH32(f): the usage record — filled by the emitter when the artefact is
    # written; a withheld artefact has nothing to count and says so.
    from apps.ire import colour_roles as _CR
    font_usage = {"schema_version": "container_font_usage/1.0",
                  "status": "ARTEFACT_WITHHELD", "faces": [],
                  "reconciliation": {"status": "NOT_EMITTED", "agree": False, "codes": []},
                  # §BH50(f)(7): no artefact, nothing to read — unmeasured, and an
                  # unmeasured axis blocks acceptance (his (5)); never an empty pass
                  _CR.USAGE_SCHEMA: {"schema_version": _CR.USAGE_SCHEMA, "status": _CR.NOT_EMITTED,
                                     "reconciliation": {"schema_version": _CR.RECONCILIATION_SCHEMA,
                                                        "status": _CR.NOT_EMITTED, "agree": None,
                                                        "codes": [_CR.COLOUR_USAGE_UNRECONCILED_CODE]}}}
    if artefact_withheld:
        # A STALE ARTEFACT IS WORSE THAN NO ARTEFACT. A prior run may have
        # attached a valid .ai; leaving it on the output would show the owner
        # last week's proof under this week's verdict, which is the failure the
        # gate exists to prevent, one step removed.
        if output.design_preview_ai:
            output.design_preview_ai.delete(save=False)
        if output.design_preview:
            output.design_preview.delete(save=False)
    else:
        # the working files live only as long as the save needs them (the clean-up of 2026-10-04: one
        # container_* folder was left in the temp folder per drawing, 60,731 of them)
        with tempfile.TemporaryDirectory(prefix="container_") as out_dir:
            ai_path = emit_pdf_ai(doc, os.path.join(out_dir, "container.ai"),
                                  usage_out=font_usage)          # §BH32(f)
            _check_shown += _self_check.inspect_said(ai_path, doc, _check_regions)
            # [his goal for the pitch, 2026-10-15, B (5): "DESIGNER'S EYE: after every drawing, render it beside its
            # concept and have a vision model list every visible difference ... Fix and re-check"] the drawing as its
            # file prints it, looked at beside its concept; the fixes the engine has levers for made, the file drawn
            # again, looked at again; PASS only where it matches the concept; what it still sees said beside Approve
            ai_path = _designers_eye(aria, output, doc, spec, ai_path, out_dir, font_usage, colors, _sources,
                                     _check_fixed, _check_shown)
            png_path = os.path.join(out_dir, "container.png")
            have_png = pdf_to_png(ai_path, png_path)

            ai_name = f"container_task_{aria.task.id}.ai"
            with open(ai_path, "rb") as f:
                output.design_preview_ai.save(
                    ai_name, ContentFile(f.read()), save=False)
            # [his final goal, 2026-10-05, C6] the native, layered .ai, built in Illustrator where it is here
            from apps.dielines.services.export_service import _native
            native = _native(doc, os.path.join(out_dir, "container_native.ai"),
                             lambda msg, data=None, level="info": None, drawing=ai_path)
            if native.get("code") == "NATIVE_AI_DROPS_ELEMENTS":
                # [his bug on design 124, 2026-10-12: "make it fail if anything is dropped"] a layered file that
                # does not carry the drawing whole is not offered, and the drawing's own check says so
                _check_shown.append({"kind": "native file", "fixed": False,
                                     "what": "the layered Illustrator file was not offered: %s; the design .ai is the "
                                             "file to open" % native.get("reason")})
            if native.get("built") and native.get("path"):
                from django.core.files.storage import default_storage
                with open(native["path"], "rb") as f:
                    native["path"] = default_storage.save(f"containers/container_native_task_{aria.task.id}.ai",
                                                          ContentFile(f.read()))
            spec["native_ai/1.0"] = native
            if have_png:
                png_name = f"container_task_{aria.task.id}.png"
                with open(png_path, "rb") as f:
                    output.design_preview.save(
                        png_name, ContentFile(f.read()), save=False)

    spec["container_profile"] = asdict(profile)
    spec["colors"] = colors
    from apps.ire import views_of as _views_of          # [his goal of 2026-10-13, (6)] each drawing's place, for his page
    spec[_views_of.SCHEMA] = _views_of.views(doc)
    spec[_self_check.SCHEMA] = _self_check.record(_check_fixed, _check_shown if not artefact_withheld else _check_shown + [
        {"kind": "check", "fixed": False, "what": "the sheet was withheld, so no drawn file was read"}])
    # The record is now a 2.0 SUPERSET of the 1.1 census. It is published
    # under its true key AND under the 1.1 key, because the 1.1 key is the
    # live lookup for the visual-quality gate, the review board and the
    # committed spec sheets — repointing every reader in this commit would
    # be a wider change than the wiring it serves. Both names resolve to
    # the same object, every 1.1 field is present and correct, and the
    # record self-describes via schema_version/extends rather than by the
    # key it was fetched under.
    spec[_dg2.SCHEMA] = graph_record
    spec["container_design_graph/1.1"] = graph_record
    spec["container_projection_report"] = projection
    spec["container_zone_containment_report"] = {
        "problems": containment, "contained": not containment,
        **({"production_notes": containment_notes} if containment_notes else {})}     # [his answer on the margin]
    # §BH50(f)(2): placeholder copy is its own blocker — one record per piece
    # of copy nobody has written, built from the DRAWN document joined to the
    # composer's own section map; carried by readiness['content'] at
    # acceptance and never a reconstruction blocker.
    from apps.ire import container_placeholder_copy as cpc
    placeholder_copy = cpc.build(
        doc, sections=back_sections, content_codes=content_codes,
        copy_fields=cpc.copy_fields(aria.task.product),
        composed=geometry is not None or bool(doc.metadata.get("back_copy_drawings")))   # [rule 5] the back drawn
    spec[cpc.SCHEMA] = placeholder_copy
    spec["container_fidelity_report"] = fidelity
    spec["container_motif_fidelity_report"] = motif_fidelity
    spec["container_typography_fidelity_report"] = typography_fidelity
    spec["container_front_back_relationship/1.0"] = front_back
    # 2B-3A: font authority + interim production-readiness codes. Kept OUT of
    # `blockers` on purpose — production-readiness is a Gate-2 concern (the full
    # container_production_readiness/1.0 report + Gate-2 refusal land in 2B-3D).
    spec["container_font_authority/1.0"] = font_authority
    spec["container_font_usage/1.0"] = font_usage            # §BH32(f)
    spec["material_influence_realization/1.0"] = material_realization
    spec["container_production_method/1.0"] = methods_record
    spec["container_production_method_validation"] = method_validation
    spec["container_production_separations/1.0"] = separations_record
    spec["container_production_combined_hash"] = production_combined_hash
    spec["container_quantitative_fidelity/1.0"] = quant_fidelity
    spec["container_wrap_geometry/1.0"] = wrap_geometry
    spec["container_wrap_alignment"] = wrap_alignment
    spec["container_production_metrics/1.0"] = production_metrics
    if influence_plan_11 is not None:
        spec["material_influence_plan/1.1"] = influence_plan_11
    spec["material_influence_realization/1.1"] = material_realization_11
    spec["container_reference_similarity"] = similarity
    # §BH65(c): the ONE contract's record of this run — each term the selected concept used, whether THIS run's
    # document drew it, and a named code for each it did not. REPORT ONLY: it joins no readiness section, because
    # §BH65 sets no threshold and governance stands still (§BH55(3)).
    from apps.ire import composer_vocabulary as _cv
    spec[_cv.SCHEMA] = _cv.realization(resolved["structured"], doc, motif_spec, finishes=finish_application)
    # §BH65(c)2: the finishes' own record — what the concept asked, where each landed, and the plates the emitter
    # wrote (one page each, after the artwork); NOT_EMITTED when the artefact was withheld
    spec[_finishes.SCHEMA] = {
        "schema_version": _finishes.SCHEMA, "assignments": motif_spec.get("finish_assignments"),
        "applied": finish_application["applied"], "codes": finish_application["codes"],
        "depiction_source": finish_application["depiction_source"],
        "plates": font_usage.get(_finishes.SCHEMA) or {"state": "NOT_EMITTED"}}
    readiness = spec.get("container_production_readiness_codes") or {}
    # §BH32(f): a counter/artefact disagreement is a defect — its code joins
    # the font readiness beside the gate's own codes
    readiness["font"] = list(font_gate_codes) + list(
        (font_usage.get("reconciliation") or {}).get("codes") or [])
    # §BH50(f)(7): the colour counter's reconciliation — every place the
    # artefact applies colour, both ways — joins acceptance under its own
    # section; a record without a reconciliation reads unmeasured, never clean
    _colour_recon = (font_usage.get(_CR.USAGE_SCHEMA) or {}).get("reconciliation")
    readiness["colour_usage"] = (list(_colour_recon.get("codes") or [])
                                 if isinstance(_colour_recon, dict) and "codes" in _colour_recon
                                 else [_CR.COLOUR_USAGE_UNRECONCILED_CODE])
    readiness["material"] = material_realization.get("codes", [])
    readiness["production_method"] = method_validation.get("codes", [])
    _ub = (separations_record.get("white_underbase") or {}).get("code")
    readiness["separations"] = [_ub] if _ub else []
    readiness["quantitative_fidelity"] = quant_fidelity.get("failures", [])
    readiness["wrap_alignment"] = wrap_alignment.get("codes", [])
    readiness["production_metrics"] = production_metrics.get("codes", [])
    # [his answer on the print area's safe margin, 2026-10-01] the zone check's production notes, read beside Approve as
    # every section's notes are (``_split_notes``) — in a declared section, so no reconstruction before it reads stale
    readiness["production_metrics"] += containment_notes
    readiness["material_attribution"] = (material_realization_11.get("codes", [])
                                         + similarity.get("codes", []))
    # 2C-2E §12: unverified back copy blocks PRODUCTION authority (a Gate-2
    # concern, visible in the readiness report — not a reconstruction blocker)
    # §BH50(f)(2): written UNCONDITIONALLY from the placeholder record, so an
    # empty section is "no unwritten copy on this reconstruction" and never
    # "the check did not run" — the §AV1 disease one level down, closed; the
    # codes are the six slot codes plus any unslotted or contested drawing.
    readiness["content"] = list(placeholder_copy["codes"])
    # [his answer of 2026-09-29 to the §BH71 report, (4)] the record's shade drawn with an Arabic the executor wrote:
    # marked beside Approve while the record says so (§BH55(a): "marked rather than assumed"), never a block
    readiness["content"] += shade_codes(doc)
    # §BH50(f)(3): the front copy at Gate 2 — written on every path from this
    # run's document; an overrun, an undrawn or unmeasurable run and the
    # unmeasured vertical axis block acceptance and never the reconstruction
    readiness["front_copy"] = list(front_copy_codes)
    # §BH54(b) (q): the back copy at Gate 2 — it blocks acceptance of the back, nothing else
    readiness["back_copy"] = list(back_copy_codes)
    # §AV3: the RUNTIME half of the §AE2(c) brand-string remedy. Read off the
    # DOCUMENT that was actually composed above, not off the inputs that were
    # meant to produce it — a descriptor arriving from a database row or an
    # owner-supplied C9 string is in no source file, and refusing it is the
    # whole thing tools/brand_strings.py structurally cannot do. Written
    # UNCONDITIONALLY, including the empty list: a section that only appears
    # when it has something to say is a section whose silence cannot be
    # distinguished from its absence, which is precisely the failure §AV1
    # spent this tranche repairing one level up.
    # COMPUTED ABOVE, at the artefact gate, not here. This line used to call
    # `brand_string_report(doc)` — it was the ONLY caller, and it ran 72 lines
    # after the .ai had already been written. It is left as an assignment so
    # the record still lands in the spec exactly as §AV3 built it; only the
    # moment of measurement moved, and it moved to before the artefact.
    spec["container_brand_strings/1.0"] = brand_strings
    readiness["brand_strings"] = list(brand_strings["codes"])
    # §BH67 HARD STOP: a printed colour no record names blocks ACCEPTANCE, in its own section, written on every run —
    # the house's own distinction (§BH50(f)(5), (7)): the reconstruction and its evidence stand for the reviewer, and
    # the artwork can never be approved while one printed colour has no source
    readiness["colour_sources"] = list(printed_audit.get("codes") or [])
    spec["container_production_readiness_codes"] = readiness
    # §10 native-output manifest: the deterministic views + records produced,
    # with the legacy raster output preserved for audit (never overwritten).
    inv = graph_record.get("surface_inventory") or {}
    spec["container_native_output_manifest"] = {
        # /1.1 DISCHARGES TWO SCHEMA CHANGES, ONE OF THEM RETROSPECTIVE.
        #
        # (a) §AW4 item 4 (clearance:6458): `/1.0` gained `artefact_withheld`
        #     and `concept_sheet_ai`/`preview_png` went from always-string to
        #     nullable, with NO version bump — an undisclosed contract change.
        #     §AW4(4) said it would be "taken to /1.1 in the commit that
        #     follows this section". Six commits followed and none did it.
        # (b) `reports` -> `records_on_sheet` + `records_on_sheet_extent`,
        #     below.
        #
        # The bump is free and that was measured before it was taken, not
        # assumed: the version string is written HERE and nowhere else, and
        # `grep -rn 'container_native_output_manifest/1'` across apps and
        # tools returns no other line. Nothing pins it and nothing reads
        # `reports`.
        "schema_version": "container_native_output_manifest/1.1",
        # §AU5(4): the manifest names what was ACTUALLY produced. It used to
        # interpolate both filenames unconditionally, so it asserted a
        # `concept_sheet_ai` existed on every run — including the blocked ones
        # where no such file was ever written. A manifest that describes the
        # happy path regardless of which path ran is not a manifest.
        "views": {"front_hero": True,
                  "surface_panels": graph_record.get("surface_groups", []),
                  "concept_sheet_ai": ai_name,
                  "preview_png": png_name},
        # Stated positively so the absence is legible rather than inferred from
        # two nulls — the §AV1 lesson, one level down: a silence that cannot be
        # told from an omission is not a record.
        "artefact_withheld": sorted(set(artefact_withheld)),
        "surfaces_with_artwork": sorted(
            s for s, role in inv.items() if role not in ("code_area",)),
        "technical_only_surfaces": sorted(
            s for s, role in inv.items() if role == "code_area"),
        # /1.1 REPLACES `reports` WITH THIS. The list it replaces named seven
        # records and was hand-written by eye off one screenful: lines 1406-1414
        # are eight consecutive `spec[...] =` report assignments and it named
        # six of them, skipping `container_design_graph/2.0` (1406) and
        # `container_typography_fidelity_report` (1413) — the second of which
        # sits BETWEEN two it did name. Beyond that screenful it saw nothing:
        # of the 31 records `test_wif_reconstruct_container.PERSISTED_RECORDS`
        # pins this path as adding, 24 were unnamed. That is §AR2 — a
        # hand-kept second copy of a set the code already holds — and it
        # drifted the way §AR2 says a second copy drifts.
        #
        # It was NOT lying about existence, which is the more dramatic reading
        # and the one I checked first: `test_wif_reconstruct_container.py:401`
        # asserts `PERSISTED_RECORDS <= set(spec)` on the BLOCKED path, and all
        # seven named records are in PERSISTED_RECORDS, so they survive the
        # refusal. This is not the §AU5(4) defect fixed twelve lines above in
        # `views`. It is incompleteness with no stated membership rule.
        #
        # DERIVED, not enumerated, and the key renamed to say what it holds.
        # "reports" implied a curated subset, and curating it means deciding
        # per record whether `colors` or `container_profile` is a "report" —
        # a judgement with no rule behind it, made again at every new record,
        # which is exactly how the old list went wrong. `records_on_sheet`
        # needs no judgement. The one exclusion is structural rather than
        # taste: this record is being built as a value OF `spec`, and on a
        # resumed run the previous manifest is already on the spec sheet, so
        # without the filter the field would contain itself on re-runs and not
        # on first runs.
        #
        # NOT `records_written`, which was the first name and over-claimed by
        # one word. `begin_output` seeds keys of its own — `backend` is on the
        # sheet before this function is entered — so a name asserting
        # authorship would have been a smaller version of the same mistake
        # `reports` made: a field name that implies a filter nothing applies.
        #
        # The drift guard this needs already exists and is not rebuilt here:
        # PERSISTED_RECORDS is asserted with EXACT set equality at
        # `test_wif_reconstruct_container.py:216`, so a new record cannot reach
        # this manifest without first failing that test and forcing a
        # deliberate edit. A second enumeration guarding the same set would be
        # the §AR2 this change removes.
        "records_on_sheet": sorted(
            k for k in spec if k != "container_native_output_manifest"),
        # §AY0(d): the absence carries its extent. This is measured AT THIS
        # LINE, so records assigned after it are structurally absent rather
        # than not produced — `container_reconstruction` is written six lines
        # below and can never appear here.
        "records_on_sheet_extent": (
            "every key on the spec sheet when this manifest was built; "
            "records assigned after this point (container_reconstruction) "
            "are structurally absent, not missing"),
        "legacy_raster_preserved": True,
    }
    # §BH50(a) ruled the five geometry rules §BH49(b) held pending, so REFUSED_PENDING_RULING is retired
    # (targets/container/m3_backbone.py): a reconstruction the rules refuse is BLOCKED, whatever drew it.
    spec["container_reconstruction"] = {
        "status": "BLOCKED" if blockers else "RECONSTRUCTED",
        "blockers": blockers}
    # persist the native output + ALL reports BEFORE any fail-closed raise so
    # the report survives (the resume wrapper only adds generation_error).
    spec.pop("generation_error", None)
    output.spec_sheet = spec
    output.save()

    if blockers or _left_out:
        # [His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design. A failing check fixes
        # the drawing itself and re-checks; if it still fails, the design continues and the problem is shown beside
        # Approve in plain words."] a check the drawing does not pass — its own repairs made above, its checks run on
        # what they made — is kept on the record (BLOCKED, as before) and said beside Approve in its words; the design
        # goes on to Gate 2. It stopped here, back at the shape step, until this goal.
        from apps.dashboard.words import check_words as _words
        from apps.ire import self_check as _sc
        for code in blockers:
            head, _, detail = str(code).partition(":")
            said = _words(head.strip()) or "a check of the drawing did not pass"
            _sc.keep_shown(spec, head.strip(), said + ((" — " + detail.strip()) if detail.strip() else ""),
                           ("ask for changes to have it drawn again", "approve it as it stands"))
        for run in _left_out:
            _sc.keep_shown(spec, "BRAND_STRING_PROVISIONAL", "the %s line is left out — its words were not supplied by "
                           "you, and the system never writes brand copy" % run["tier"],
                           ("give its words in the brief or the product's record, then ask for changes",))
        output.spec_sheet = spec
        output.save()
        aria.log("Container: the drawing goes on past %d check(s) it did not pass — each said beside Approve"
                 % (len(blockers) + len(_left_out)), level="warning",
                 payload={"blockers": blockers, "left_out": _left_out})
    if not brand_strings["clean"]:
        # §AU5(4)/§AU8(e). Reached only when the GEOMETRY is sound and the WORDS
        # are not — the case the reconstruction gate above has no opinion about
        # and would have waved through with a full set of artefacts attached.
        # Raised AFTER `output.save()`, deliberately, so the brand-string record
        # naming the offending runs survives for whoever has to fix it; the
        # artefact itself was already withheld at the gate, 100 lines up, which
        # is where withholding has to happen to mean anything.
        from apps.ire.brand_string_runtime import BRAND_STRING_ARTEFACT_WITHHELD
        aria.log("Container: artefact withheld — provisional brand copy "
                 f"{brand_strings['codes']}", level="warning")
        raise ValueError(f"{BRAND_STRING_ARTEFACT_WITHHELD}: "
                         + "; ".join(brand_strings["codes"]))
    aria.log(f"Container: reconstructed {profile.archetype} concept sheet "
             "(editable .ai + preview)")
