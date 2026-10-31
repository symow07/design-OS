"""Product identification — the "what am I designing?" step (2026-07-07).

The Amber Hour run exposed the gap: with no Product record selected, every
stage guessed independently — the Prompt Engineer defaulted to a tall
skincare-style carton (with a dropper bottle prop) for an eyeshadow palette,
reference selection lost its category bonus, and QA had no idea what product
it was judging. This service makes product identity a first-class pipeline
input, resolved ONCE per run and threaded to every stage:

    resolve_product_profile(task) -> {
        "name":            display name of the product,
        "category":        "SK" | "HC" | "CO" | "",
        "product_type":    e.g. "eyeshadow palette",
        "physical_format": AUTHORITATIVE structure only (see provenance),
        "structural_provenance": one of the STRUCTURE_* states below,
        "inferred_non_authoritative_context": quarantined structure guess,
        "source":          "record" | "inferred",
    }

From the task's Product record when one is selected; otherwise ONE fast
Claude call analyzes the task text (settings.PRODUCT_INFERENCE gates it —
off under pytest). Empty dict when nothing can be resolved; every consumer
treats the profile as advisory and degrades gracefully.

Structural provenance (2A-6D-CORR-2): the task-#50 retry failed
UNCONFIRMED_STRUCTURE_ASSUMED because this step INVENTED "small upright
rectangular tuck-end carton" for a brief that states no closure, dieline,
dimensions or template — and that guess flowed into the generation context
as if it were fact. Structure now carries provenance, and only these states
may populate authoritative structural context:

    EXPLICIT_USER_FACT         every structural assertion in the identified
                               form appears verbatim in the user's task text
    VERIFIED_PRODUCT_RECORD    the form comes from a Product record

An inferred form (INFERRED_NONAUTHORITATIVE) is quarantined in
``inferred_non_authoritative_context`` — a diagnostic field that must never
be supplied to Design Intent or direction generation as a requirement. With
nothing authoritative the structure is UNKNOWN and the generation context
says so explicitly (UNKNOWN_STRUCTURE_TEXT).
"""
from __future__ import annotations
from apps.pipeline.services.cost_ledger import BudgetExceededError as _RescueBudgetError

import logging
import re

logger = logging.getLogger(__name__)

STRUCTURE_EXPLICIT_USER_FACT = "EXPLICIT_USER_FACT"
STRUCTURE_VERIFIED_PRODUCT_RECORD = "VERIFIED_PRODUCT_RECORD"
STRUCTURE_INFERRED_NONAUTHORITATIVE = "INFERRED_NONAUTHORITATIVE"
STRUCTURE_UNKNOWN = "UNKNOWN"

#: Provenance states allowed to populate authoritative structural context.
AUTHORITATIVE_STRUCTURE_STATES = (
    STRUCTURE_EXPLICIT_USER_FACT, STRUCTURE_VERIFIED_PRODUCT_RECORD)

#: Vocabulary that turns a form phrase into a structural ASSERTION (closure
#: systems, construction, dielines) — the things a designer would build to.
_STRUCTURAL_TERMS = (
    "tuck-end", "tuck end", "auto-lock", "auto lock", "crash-lock",
    "crash lock", "snap-lock", "snap lock", "straight tuck", "reverse tuck",
    "glue-tab", "glue tab", "dieline", "die-line", "panel sequence",
)
_DIMENSION_RE = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mm|cm)\b")
_DIMENSION_PAIR_RE = re.compile(r"\b\d+(?:\.\d+)?\s*[x×]\s*\d+")

#: What the generation context says when structure is not authoritative.
#: Explicit per-fact UNKNOWNs so the model cannot fill the silence with a
#: "typical" carton, plus the confirmation marker the intent must carry.
UNKNOWN_STRUCTURE_TEXT = (
    "Carton structure: width UNKNOWN, depth UNKNOWN, height UNKNOWN, "
    "template UNKNOWN, panel sequence UNKNOWN, closure system UNKNOWN — "
    "structural confirmation required. "
    "STRUCTURAL_TEMPLATE_CONFIRMATION_REQUIRED: do not assume, estimate or "
    "invent dimensions, a carton template, a closure type or panel "
    "construction; structure is confirmed later in the pipeline.")

_IDENTIFY_SYSTEM = """You identify WHICH PRODUCT a packaging-design task is about,
for a beauty brand's design pipeline. Categories: SK (skincare), HC (hair care),
CO (color cosmetics).

"physical_format" must describe the CARTON'S physical form in one concrete
phrase a packaging designer would use — the form factor matters more than the
words. Examples:
  eyeshadow palette  -> "wide, low-profile landscape carton (flat palette inside)"
  lip gloss          -> "tall slim upright tuck-end carton (gloss tube inside)"
  face serum         -> "upright rectangular carton (dropper bottle inside)"
  compact powder     -> "small square low carton (round compact inside)"

You ALSO extract the brief's explicit design constraints VERBATIM — never
invented, never paraphrased into new requirements. Empty lists when the task
does not state them:
  "required_copy": consumer-facing copy lines the brief REQUIRES on the
      packaging (product names, translations, descriptors) — exact strings;
  "preferred_colors": colors the brief permits or prefers;
  "prohibited_colors": colors the brief forbids (especially as dominant);
  "prohibited_motifs": motifs/themes the brief forbids;
  "production_constraints": short normalized facts, e.g.
      "decorative coverage no more than 20%" when the brief caps decoration,
      "structure unconfirmed — no dimensions supplied" when the brief gives
      no carton dimensions or template.

Respond ONLY with valid JSON:
{
  "name": "short product display name from the task",
  "category": "SK" | "HC" | "CO" | "",
  "product_type": "short type, e.g. 'eyeshadow palette'",
  "physical_format": "one concrete phrase for the carton form",
  "required_copy": ["..."],
  "preferred_colors": ["..."],
  "prohibited_colors": ["..."],
  "prohibited_motifs": ["..."],
  "production_constraints": ["..."]
}"""


def _structural_assertions(text: str) -> list[str]:
    """The structural claims a form phrase makes (closure terms, dimensions)."""
    low = " ".join(str(text or "").lower().split())
    found = [term for term in _STRUCTURAL_TERMS if term in low]
    found += _DIMENSION_RE.findall(low)
    found += _DIMENSION_PAIR_RE.findall(low)
    return found


def classify_structural_provenance(physical_format: str,
                                   task_text: str) -> tuple[str, str, str]:
    """``(provenance, authoritative_format, quarantined_format)`` for an
    INFERRED profile's form phrase.

    An inferred form is authoritative (EXPLICIT_USER_FACT) only when it makes
    structural assertions and EVERY one of them appears verbatim in the
    user's own task text — the model repeating the user is fine; the model
    guessing is not. A form phrase with no structural assertions is still a
    carton-type speculation and stays quarantined.
    """
    fmt = " ".join(str(physical_format or "").split())
    if not fmt:
        return STRUCTURE_UNKNOWN, "", ""
    assertions = _structural_assertions(fmt)
    task_low = " ".join(str(task_text or "").lower().split())
    if assertions and all(a in task_low for a in assertions):
        return STRUCTURE_EXPLICIT_USER_FACT, fmt, ""
    return STRUCTURE_INFERRED_NONAUTHORITATIVE, "", fmt


def normalize_identified_profile(data: dict, task_text: str) -> dict:
    """The deterministic parsing/normalization boundary of the identification
    response — pure, provider-free, unit-testable. Empty dict when the
    response carries no usable identity."""
    category = str(data.get("category") or "").upper()
    if category not in ("SK", "HC", "CO"):
        category = ""

    def _string_list(key, max_items):
        value = data.get(key)
        if not isinstance(value, (list, tuple)):
            return []
        return [str(entry).strip()[:200] for entry in value
                if str(entry).strip()][:max_items]

    provenance, authoritative, quarantined = classify_structural_provenance(
        str(data.get("physical_format") or "")[:200], task_text)
    profile = {
        "name": str(data.get("name") or "")[:120],
        "category": category,
        "product_type": str(data.get("product_type") or "")[:120],
        # AUTHORITATIVE structure only — empty unless the user or a Product
        # record actually stated it (2A-6D-CORR-2).
        "physical_format": authoritative,
        "structural_provenance": provenance,
        # Diagnostic quarantine: never rendered into generation context.
        "inferred_non_authoritative_context": quarantined,
        # 2A-6D: the brief's explicit constraints, extracted verbatim so
        # the direction generator can VALIDATE against them (required
        # copy, palette rules, decorative cap). Empty = not stated.
        "required_copy": _string_list("required_copy", 8),
        "preferred_colors": _string_list("preferred_colors", 12),
        "prohibited_colors": _string_list("prohibited_colors", 8),
        "prohibited_motifs": _string_list("prohibited_motifs", 12),
        "production_constraints": _string_list("production_constraints", 8),
        "source": "inferred",
    }
    if not (profile["product_type"] or profile["name"]):
        return {}
    return profile


#: [his answer 4 of 2026-10-02] the brief's constraint lists a design started from a product record reads from its brief
BRIEF_CONSTRAINT_KEYS = ("required_copy", "preferred_colors", "prohibited_colors", "prohibited_motifs",
                         "production_constraints")


def _brief_constraints(task, log) -> dict:
    """[His answer 4 of 2026-10-02.] The brief's own constraints (BRIEF_CONSTRAINT_KEYS) for a design whose product
    comes from a record: the brief-only path's one extraction call on the task's words, the record's identity untouched;
    {} where inference is off, there is no key, the brief is empty, or the call fails (never raises)."""
    from django.conf import settings
    text = str(task.task_text).strip() if task.task_text else ""
    if not text or not settings.PRODUCT_INFERENCE or not settings.ANTHROPIC_API_KEY:
        return {}
    try:
        from apps.pipeline.services.claude_service import call_claude, extract_json
        response = call_claude(_IDENTIFY_SYSTEM, f"Task: {text}", max_tokens=900, model=settings.CLAUDE_MODEL_FAST,
                               operation="product_identification")
        read = normalize_identified_profile(extract_json(response), text)
    except Exception as exc:  # noqa: BLE001 — advisory step, never block the run
        if isinstance(exc, _RescueBudgetError):
            raise
        logger.warning("brief constraint extraction failed: %s", exc)
        return {}
    got = {k: list(read[k]) for k in BRIEF_CONSTRAINT_KEYS if read and read.get(k)}
    if got:
        log("ARIA: the brief's own constraints read beside the product record — "
            + ", ".join("%s %d" % (k, len(v)) for k, v in got.items()))
    return got


def brief_mood(text) -> str:
    """[His answer 4 of 2026-10-02 (6badb27): "the concept check's mood follows the brief".] The brief's own "Mood:"
    paragraph — its words after the colon to the first blank line, whitespace collapsed, at most 400 characters; '' when
    the brief states none. Read from the words, never inferred."""
    import re
    m = re.search(r"^[ \t]*mood[ \t]*:[ \t]*(.+?)(?:\r?\n[ \t]*\r?\n|\Z)", str(text), re.I | re.M | re.S)
    if not m:
        return ""
    return " ".join(m.group(1).split())[:400]


def resolve_product_profile(task, log=None) -> dict:
    """Resolve the product identity for this task. Never raises."""
    log = log or (lambda msg, data=None, level="info": None)

    product = getattr(task, "product", None)
    if product is not None:
        dimensions = product.dimensions or ""
        profile = {
            "name": product.name,
            "category": product.category or "",
            "product_type": product.product_type or "",
            "physical_format": dimensions,
            "structural_provenance": (STRUCTURE_VERIFIED_PRODUCT_RECORD
                                      if dimensions else STRUCTURE_UNKNOWN),
            "inferred_non_authoritative_context": "",
            "source": "record",
        }
        log(
            f"ARIA: product identified from record — {product.name} "
            f"[{product.category or '?'}] {product.product_type or ''}".strip()
        )
        # [his answer 4 of 2026-10-02 (6badb27): "designs started from a product record read the brief's colours and
        # copy"] the record names the product; the brief still states what it requires — its five constraint lists,
        # read the way a brief-only design reads them, beside the record's identity
        profile.update(_brief_constraints(task, log))
        _mood = brief_mood(task.task_text)
        if _mood:
            profile["mood"] = _mood                   # [his answer 4 of 2026-10-02] the brief's own mood, read
        return profile

    from django.conf import settings
    if not settings.PRODUCT_INFERENCE or not settings.ANTHROPIC_API_KEY:
        return {}

    try:
        from apps.pipeline.services.claude_service import call_claude, extract_json

        response = call_claude(
            _IDENTIFY_SYSTEM,
            f"Task: {task.task_text}",
            max_tokens=900,
            model=settings.CLAUDE_MODEL_FAST,
            operation="product_identification",
        )
        profile = normalize_identified_profile(
            extract_json(response), task.task_text or "")
        if not profile:
            return {}
        _mood = brief_mood(task.task_text)
        if _mood:
            profile["mood"] = _mood                   # [his answer 4 of 2026-10-02] the brief's own mood, read
        quarantined = profile["inferred_non_authoritative_context"]
        form_note = (
            profile["physical_format"]
            or (f"inferred form, non-authoritative — excluded from "
                f"generation context: {quarantined}" if quarantined
                else "form unknown"))
        log(
            f"ARIA: product identified from the task — "
            f"{profile['product_type'] or profile['name']} "
            f"[{profile['category'] or '?'}] ({form_note})"
        )
        return profile
    except Exception as exc:  # noqa: BLE001 — advisory step, never block the run
        if isinstance(exc, _RescueBudgetError):
            raise
        logger.warning("product identification failed: %s", exc)
        return {}


def _structure_is_authoritative(profile: dict) -> bool:
    """Whether physical_format may enter generation context. Profiles from
    before 2A-6D-CORR-2 carry no provenance: a record profile stays
    authoritative; an inferred one is quarantined (fail-safe)."""
    provenance = profile.get("structural_provenance")
    if provenance is not None:
        return provenance in AUTHORITATIVE_STRUCTURE_STATES
    return profile.get("source") == "record"


#: [his answer 1 of 2026-10-02 (6badb27): "the brief's colours go into the step that MAKES the concept picture, not only
#: the drawing"] how the brief's colours are said to the step that writes a concept picture's prompt — its own colour
#: rule, the planner's (`design_direction_generator._colour_rule`), so the two never disagree
BRIEF_COLOURS_HEADING = ("THE BRIEF'S COLOURS — they win: name them in every prompt's colour field; beside them only the "
                         "BBROSE logo and at most ONE house accent; never pulled back to the house colours")


def brief_colours_text(profile: dict) -> str:
    """The brief's preferred colours and the colours it forbids as dominant, as the profile read them, under
    BRIEF_COLOURS_HEADING; '' when the brief names none (the prompt then reads exactly as before)."""
    if not profile:
        return ""
    preferred = [str(c).strip() for c in (profile.get("preferred_colors") if profile.get("preferred_colors") else [])
                 if str(c).strip()]
    prohibited = [str(c).strip() for c in (profile.get("prohibited_colors") if profile.get("prohibited_colors") else [])
                  if str(c).strip()]
    if not preferred and not prohibited:
        return ""
    lines = [BRIEF_COLOURS_HEADING]
    if preferred:
        lines.append("Colours: " + "; ".join(preferred))
    if prohibited:
        lines.append("Never a dominant colour: " + "; ".join(prohibited))
    return "\n".join(lines)


def with_brief_colours(block: str, profile: dict) -> str:
    """``block`` with the brief's colours after it (``brief_colours_text``), or ``block`` unchanged."""
    said = brief_colours_text(profile)
    return block + "\n\n" + said if said else block


def profile_text(profile: dict) -> str:
    """Human/model-readable one-block rendering of a profile ('' when empty).

    Renders ONLY authoritative structure. When structure is inferred or
    unknown it renders the explicit UNKNOWN block instead — the quarantined
    inference is never shown to a generation stage.
    """
    if not profile:
        return ""
    lines = []
    if profile.get("name"):
        lines.append(f"Product: {profile['name']}")
    if profile.get("category"):
        lines.append(f"Category: {profile['category']}")
    if profile.get("product_type"):
        lines.append(f"Type: {profile['product_type']}")
    if profile.get("physical_format") and _structure_is_authoritative(profile):
        lines.append(f"Carton form: {profile['physical_format']}")
    else:
        lines.append(UNKNOWN_STRUCTURE_TEXT)
    if profile.get("source") == "inferred":
        lines.append("(identified from the task text)")
    return "\n".join(lines)
