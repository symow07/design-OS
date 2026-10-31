"""Structured Gate-1 regeneration prompts (2A-6E-CORR-5 §4/§5).

Task #50's live regeneration failed with "0 variation prompts": the legacy
Prompt Engineer path capped output at 3,000 tokens, the richness-directed
response hit exactly that cap (ApiCallRecord 193, out=3000), the truncated
JSON failed parsing, there was no repair, and the raw response was not
preserved. This module replaces that path for reference-grounded
regeneration with an explicit versioned contract:

    gate1_reference_regeneration_prompts/1.0

* one generation call + at most ONE bounded repair carrying the exact
  schema/parser errors and the raw response;
* every raw response is preserved (observability channel) whether or not
  it parses;
* validation requires exactly three variations with the required
  identities, unique IDs, non-empty prompts, the echoed approved-reference
  IDs and influence-plan hash, and STRUCTURED pairwise diversity over the
  declared signatures — prose-only output never passes;
* zero image-provider calls until three prompts validate; a double failure
  returns the codes and the diagnostics, and the CALLER fails only the
  regeneration job — never the parent design task.
* [his goal of 2026-10-10, item 1: "NO planner check ever stops a design ... Apply this to every planner and concept
  check."] a double failure whose answer still holds three prompts is drawn anyway, its codes the note beside the
  three (``RegenPromptsResult.alike``), each bound to its direction by its slot; only an answer with no three prompts
  in it fails.
"""
from __future__ import annotations

import dataclasses
import json
import re

from django.conf import settings

GATE1_PROMPTS_SCHEMA = "gate1_reference_regeneration_prompts/1.0"
MAX_OUTPUT_TOKENS = 8000        # the 3,000-token cap truncated the payload
MAX_ATTEMPTS = 2                # one generation + one bounded repair

#: Stable failure codes (§3/§4).
GATE1_PROMPTS_PARSE_FAILURE = "PROMPT_ENGINEER_OUTPUT_PARSE_FAILURE"
GATE1_PROMPTS_SCHEMA_MISMATCH = "PROMPT_ENGINEER_SCHEMA_MISMATCH"
GATE1_PROMPTS_EMPTY = "PROMPT_ENGINEER_EMPTY_RESPONSE"
VARIATION_PROMPTS_NOT_DISTINCT = "VARIATION_PROMPTS_NOT_DISTINCT"

_REQUIRED_VARIATION_FIELDS = (
    "variation_id", "title", "prompt", "composition_signature",
    "color_field_signature", "motif_signature", "logo_zone",
    "product_name_zone", "decorative_coverage_pct",
)
_DIVERSITY_FIELDS = ("composition_signature", "color_field_signature",
                     "motif_signature", "logo_zone", "product_name_zone")
_MIN_PAIRWISE_FIELD_DIFFERENCES = 2

#: §BH67(c)4 — an identity SLOT's id: the slot letter, then the variation's own concept name in capitals and
#: underscores. A name that is only a number or a generic word is not a name.
_SLOT_ID = re.compile(r"^(?P<slot>[A-Z])_(?P<name>[A-Z0-9]+(?:_[A-Z0-9]+)*)$")
_GENERIC_NAME = re.compile(r"^(?:VARIATION|OPTION|CONCEPT|DESIGN|SLOT)?_?\d*$")

SYSTEM = f"""
You are the Prompt Engineer for BBROSE, a luxury beauty brand, building the
REFERENCE-GROUNDED Gate-1 regeneration prompts.

Your job: produce EXACTLY THREE image-generation prompts — one per required
variation identity — each a photorealistic CONCEPT PACKSHOT of the carton
with the design applied. The image model receives the official BBROSE logo
and the user-approved concept-reference images as attachments; your prompts
describe the DESIGN. Write flowing visual language. BANNED: percentage zone
layouts as production spec, pt/mm measurements, "dieline", aspect-ratio
flags. State the carton's physical form in the first sentence and never
default to a tall carton.

The three variations must be MATERIALLY different — different composition,
product-name placement, logo placement, color-field structure, motif,
Spanish-copy placement and finishing treatment — never one layout in three
colorways. Each variation's signature fields must honestly describe its
prompt.

Respond ONLY with valid JSON in exactly this shape (no markdown, no prose):
{{
  "schema_version": "{GATE1_PROMPTS_SCHEMA}",
  "approved_reference_ids": [<echo the approved reference ids you were given>],
  "influence_plan_hash": "<echo the influence-plan hash you were given>",
  "variations": [
    {{
      "variation_id": "<the required identity, e.g. A_EDITORIAL_PANEL>",
      "title": "<short display title>",
      "prompt": "<the complete image prompt>",
      "composition_signature": "<one line: the composition system>",
      "color_field_signature": "<one line: the color-field structure>",
      "motif_signature": "<one line: the decorative motif system>",
      "logo_zone": "<where the BBROSE mark sits>",
      "product_name_zone": "<where the product name sits>",
      "decorative_coverage_pct": <number>
    }},
    ... exactly three entries, one per required identity, in order ...
  ]
}}
Keep every prompt complete — do not truncate.
"""


@dataclasses.dataclass(frozen=True)
class RegenPromptsResult:
    ok: bool
    payload: dict | None
    prompts: list            # [{direction_name, full_prompt, variation_id}]
    codes: tuple
    attempts: int
    raw_responses: tuple     # every raw model response, preserved
    provider_model: str
    #: [His test blocker on design 123, 2026-10-09, (2): "Every "not distinct" check: it never stops a design."] the
    #: "too alike" codes the three still carry after the one retry, drawn anyway with a note; () where they passed —
    #: [his goal of 2026-10-10, item 1] every check they still fail, of whatever kind
    alike: tuple = ()
    #: … and which attempts came back refused for their checks and nothing else — the note says what happened
    alike_attempts: tuple = ()


#: [His goal of 2026-10-10, item 1] the slots three concepts shown with a note are bound by, where the step names none
SHOWN_SLOTS = ("A", "B", "C")


def drawable(payload, count: int) -> bool:
    """[His goal of 2026-10-10, item 1] whether an answer holds ``count`` variations, each with words to draw from —
    what three concepts shown with a note need, whatever check they fail."""
    if not isinstance(payload, dict) or not isinstance(payload.get("variations"), list):
        return False
    variations = payload["variations"]
    return len(variations) == count and all(
        isinstance(v, dict) and isinstance(v.get("prompt"), str) and v["prompt"].strip() for v in variations)


def told_by_slot(payload, directions: list, slots: tuple) -> dict:
    """[His goal of 2026-10-10, item 1] an answer shown though its checks refused it, each variation bound to the
    direction in its slot and named for it where its own id is missing or repeated (``A_VELVET_BLOOM``) — a copy;
    the answer's own ids kept where they stand apart."""
    import copy
    out = copy.deepcopy(payload)
    seen = set()
    for n, v in enumerate(out["variations"]):
        if directions:
            v["direction_id"] = directions[n]["direction_id"]
        own = v.get("variation_id")
        if not isinstance(own, str) or not own.strip() or own in seen:
            letter = slots[n] if n < len(slots) else str(n + 1)
            name = _id_name(directions[n]["name"]) if directions else ""
            v["variation_id"] = "%s_%s" % (letter, name) if name else "%s_CONCEPT_%d" % (letter, n + 1)
        seen.add(v["variation_id"])
    return out


def alike_only(codes, not_distinct_code) -> bool:
    """[His test blocker on design 123, (2)] whether ``codes`` are all the step's "not distinct" check, and some."""
    return bool(codes) and all(str(code).startswith(not_distinct_code) for code in codes)


def validate_regeneration_payload(payload, variation_identities,
                                  reference_ids, plan_hash, *,
                                  schema_version=GATE1_PROMPTS_SCHEMA,
                                  required_fields=_REQUIRED_VARIATION_FIELDS,
                                  diversity_fields=_DIVERSITY_FIELDS,
                                  min_pairwise=_MIN_PAIRWISE_FIELD_DIFFERENCES,
                                  schema_code=GATE1_PROMPTS_SCHEMA_MISMATCH,
                                  empty_code=GATE1_PROMPTS_EMPTY,
                                  not_distinct_code=VARIATION_PROMPTS_NOT_DISTINCT,
                                  identity_code=None,
                                  require_per_variation_reference_ids=False,
                                  identity_slots=None,
                                  ) -> list[str]:
    """Stable codes for a parsed payload, or []. Prose or partial output never
    passes. All contract knobs default to the packaging regeneration values
    (byte-identical); the container Gate-1 contract passes its own field set,
    schema name and codes (2B-3V §4/§5)."""
    identity_code = identity_code or schema_code
    if not isinstance(payload, dict):
        return [f"{schema_code}: response is not an object"]
    codes = []
    if payload.get("schema_version") != schema_version:
        codes.append(f"{schema_code}: schema_version must be {schema_version}")
    variations = payload.get("variations")
    if not isinstance(variations, list) or not variations:
        codes.append(f"{empty_code}: no variations array")
        return codes
    if len(variations) != 3:
        codes.append(f"{schema_code}: exactly 3 variations required, "
                     f"got {len(variations)}")
    seen_ids = []
    approved = set(reference_ids)
    for index, variation in enumerate(variations):
        if not isinstance(variation, dict):
            codes.append(f"{schema_code}: variations[{index}] is not an object")
            continue
        for field in required_fields:
            value = variation.get(field)
            if value in (None, "", []):
                codes.append(f"{schema_code}: "
                             f"variations[{index}].{field} missing or empty")
        seen_ids.append(variation.get("variation_id"))
        prompt = variation.get("prompt")
        if isinstance(prompt, str) and len(prompt.split()) < 40:
            codes.append(f"{schema_code}: variations[{index}].prompt is too "
                         "short to be a complete concept prompt")
        # §6: per-variation reference ids must be a non-empty SUBSET of the
        # approved set — references are assigned intentionally, never forced.
        if require_per_variation_reference_ids:
            per = variation.get("reference_ids")
            if not isinstance(per, list) or not per:
                codes.append(f"{schema_code}: variations[{index}].reference_ids "
                             "must be a non-empty list of approved reference ids")
            elif not set(per).issubset(approved):
                codes.append(f"{schema_code}: variations[{index}].reference_ids "
                             f"{per} are not all in the approved set "
                             f"{sorted(approved)}")
    if len(set(seen_ids)) != len(seen_ids):
        codes.append(f"{identity_code}: variation_ids are not unique")
    if identity_slots:
        # §BH67(c)4: SLOTS, not names — each id is its slot's letter and the variation's OWN concept name, in slot
        # order; no name is imposed, and a generic one is refused
        for index, slot in enumerate(identity_slots):
            vid = seen_ids[index] if index < len(seen_ids) else None
            m = _SLOT_ID.match(vid) if isinstance(vid, str) else None
            if not m or m.group("slot") != slot or _GENERIC_NAME.match(m.group("name")):
                codes.append(f"{identity_code}: variations[{index}].variation_id {vid!r} must be {slot}_<NAME> — "
                             "the slot letter, then the variation's own concept name in capitals and underscores")
    elif set(v for v in seen_ids if v) != set(variation_identities):
        codes.append(f"{identity_code}: variation_ids must be exactly "
                     f"{sorted(variation_identities)}")
    echoed = payload.get("approved_reference_ids")
    if sorted(echoed or []) != sorted(reference_ids):
        codes.append(f"{schema_code}: approved_reference_ids must echo the "
                     "supplied ids")
    if payload.get("influence_plan_hash") != plan_hash:
        codes.append(f"{schema_code}: influence_plan_hash must echo the "
                     "supplied hash")
    if codes:
        return codes
    # structured diversity (§5): every pair must differ in at least
    # ``min_pairwise`` of the declared signature fields.
    normalized = [
        {field: " ".join(str(v.get(field, "")).lower().split())
         for field in diversity_fields}
        for v in variations]
    for first in range(len(normalized)):
        for second in range(first + 1, len(normalized)):
            differences = sum(
                1 for field in diversity_fields
                if normalized[first][field] != normalized[second][field])
            if differences < min_pairwise:
                codes.append(
                    f"{not_distinct_code}: variations {first} and {second} "
                    f"differ in only {differences} signature field(s)")
    return codes


def _default_call_model(system, message, operation="gate1_regeneration_prompts"):
    from apps.pipeline.services.claude_service import call_claude
    model = settings.CLAUDE_MODEL_FAST
    return (call_claude(system, message, max_tokens=MAX_OUTPUT_TOKENS,
                        model=model, operation=operation),
            f"anthropic:{model}")


#: [his final goal, 2026-10-05, B4] the prompts were not one for each planned direction, bound by its id
PROMPTS_NOT_BOUND_TO_DIRECTIONS = "PROMPTS_NOT_BOUND_TO_DIRECTIONS"


def _name_key(name) -> str:
    return " ".join(str(name).casefold().split())


def bound_to_directions(prompts: list, directions: list):
    """[His final goal, 2026-10-05, B4: "Three truly different concepts drawn straight away".] ``prompts`` — one for
    each of ``directions`` by its ``direction_id``, each named as its direction is — put in the directions' order, or
    None where they are not exactly that (a direction with no prompt, two prompts for one, an id never planned).
    [B4c] Prompts that carry no ids but each name a direction exactly (the plan's names are distinct) are bound by the
    name; the caller says so."""
    ids = [d["direction_id"] for d in directions]
    keys = [p.get("direction_id") for p in prompts]
    if len(prompts) != len(directions):
        return None
    if sorted(str(k) for k in keys) != sorted(ids):
        named = {_name_key(d["name"]): d["direction_id"] for d in directions}
        keys = [named.get(_name_key(p.get("direction_name"))) for p in prompts]
        if sorted(str(k) for k in keys) != sorted(ids):
            return None
    by_id = {d["direction_id"]: d for d in directions}
    out = [dict(p, direction_id=k, direction_name=by_id[k]["name"]) for p, k in zip(prompts, keys)]
    return sorted(out, key=lambda p: ids.index(p["direction_id"]))


#: [his final goal, 2026-10-05, B4c] the one more ask a prompt step not bound to the directions is given, with why
PROMPTS_REPAIR = ("Your previous answer was refused: it must hold EXACTLY one prompt for each of the creative directions "
                  "above — three in all — each carrying that direction's direction_id, copied exactly, and its name.")


#: [his test findings on design 121, 2026-10-07, item 1] an id with its direction's id folded in after its slot
#: ("A_d1_REBEL_BLOOM"), and any id in its slot's letter with its own name in another case or separator ("A-Rebel Bloom")
_ID_IN_SLOT = re.compile(r"^\s*(?P<slot>[A-Za-z])(?:[\s_\-:]+(?:(?P<dir>d\d+)(?=[\s_\-:]|$)[\s_\-:]*)?"
                         r"(?P<name>.*?))?\s*$", re.I)


def _id_name(text) -> str:
    """A concept name as the slot rule writes it: capitals and underscores."""
    if not text:
        return ""
    return re.sub(r"[^A-Z0-9]+", "_", str(text).upper()).strip("_")


def agree_ids(payload, *, identity_slots=None, directions=None) -> list:
    """[His test findings on design 121, 2026-10-07 (OWNER_BLOCKER_CLEARANCE.md): "The ID binding from your last round
    (B4c) clashes with the older naming rule. Make them agree, so a design can never stop here again."] The two id rules
    read as one: a variation's SLOT binds it to its direction — A the first, B the second, C the third, as the step
    orders them — so a direction id never belongs inside a variation id. MEASURED on 121: the live model's first answer
    named its variations by their slots (``A_REBEL_BLOOM``) and left the direction ids out, and was refused by the
    binding; told to copy them, its second put them inside its ids (``A_d1_REBEL_BLOOM``), and was refused by the slot
    rule. Now: a direction id a variation leaves out is its slot's direction's; one folded into its id is lifted out
    when it is that slot's own; an id in its slot's letter is written in capitals and underscores; an id whose name is
    generic or empty takes the variation's own title. The payload is read in place; what was read so is returned, in
    words, for the log. A direction id that names ANOTHER direction is left for the binding to refuse, with why."""
    variations = payload.get("variations") if isinstance(payload, dict) else None
    if not isinstance(variations, list):
        return []
    said = []
    for n, variation in enumerate(variations):
        if not isinstance(variation, dict):
            continue
        own_dir = (directions[n].get("direction_id") if directions and n < len(directions) else None)
        slot = identity_slots[n] if identity_slots and n < len(identity_slots) else None
        vid = variation.get("variation_id")
        m = _ID_IN_SLOT.match(vid) if slot and isinstance(vid, str) else None
        if m and m.group("slot").upper() == slot and (
                m.group("dir") is None or own_dir is None or m.group("dir").lower() == str(own_dir).lower()):
            name = _id_name(m.group("name"))
            if not name or _GENERIC_NAME.match(name):
                name = _id_name(variation.get("title"))
            new = "%s_%s" % (slot, name)
            if new != vid and name and _SLOT_ID.match(new) and not _GENERIC_NAME.match(name):
                variation["variation_id"] = new
                said.append("%s read as %s" % (vid, new))
        if own_dir and not variation.get("direction_id"):
            variation["direction_id"] = own_dir
            said.append("%s bound to %s by its slot" % (variation.get("variation_id"), own_dir))
    return said


def direction_binding_codes(payload, directions: list) -> list:
    """[His final goal, B4] the structured contract's three variations, in slot order, each its direction's by id."""
    want = [d["direction_id"] for d in directions]
    variations = payload.get("variations") if isinstance(payload, dict) else None
    got = [v.get("direction_id") for v in variations] if isinstance(variations, list) else []
    if got != want:
        # [his test findings on design 121, item 1] said where the id goes — its own field, never inside variation_id
        return ["%s: the variations name %s, where the three directions are %s, in order — each in the variation's "
                "own \"direction_id\" field, never inside its variation_id" % (PROMPTS_NOT_BOUND_TO_DIRECTIONS, got, want)]
    return []


def build_regeneration_prompts(*, direction, product_block, influence_plan,
                               plan_hash, reference_ids,
                               variation_identities, richness_directives,
                               log=None, call_model=None,
                               system=SYSTEM,
                               schema_version=GATE1_PROMPTS_SCHEMA,
                               required_fields=_REQUIRED_VARIATION_FIELDS,
                               diversity_fields=_DIVERSITY_FIELDS,
                               min_pairwise=_MIN_PAIRWISE_FIELD_DIFFERENCES,
                               schema_code=GATE1_PROMPTS_SCHEMA_MISMATCH,
                               empty_code=GATE1_PROMPTS_EMPTY,
                               not_distinct_code=VARIATION_PROMPTS_NOT_DISTINCT,
                               identity_code=None,
                               require_per_variation_reference_ids=False,
                               operation="gate1_regeneration_prompts",
                               max_attempts=None,
                               identity_slots=None,
                               directions=None,
                               ) -> RegenPromptsResult:
    """Exactly three validated variation prompts, or a failed result with
    every raw response preserved and zero image calls made. Contract knobs
    default to packaging regeneration; the container Gate-1 contract passes its
    own system prompt, field set, schema name and codes (2B-3V §4/§5/§6).
    [His final goal, 2026-10-05, B4] ``directions`` — the three planned directions, one variation for each, in slot
    order, each echoing its direction's id; ``direction`` is then unused."""
    log = log or (lambda *a, **k: None)
    call = call_model or (
        lambda sys_, msg: _default_call_model(sys_, msg, operation=operation))
    from apps.pipeline.services.claude_service import (
        extract_text, loads_tolerant)

    identities_block = (
        # §BH67(c)4: slots — the model names each variation from its own concept; no name is handed to it
        ["## Variation identities — three SLOTS, named by each variation's own concept",
         ", ".join(f"{slot}_<NAME>" for slot in identity_slots)
         + " (capitals and underscores; no name is given to you, and none is a default)"]
        if identity_slots else
        ["## Required variation identities (produce EXACTLY these three)",
         json.dumps(list(variation_identities))])
    message = "\n".join([
        *identities_block,
        "",
        "## Variation briefs — each must be materially different",
        richness_directives.strip(),
        "",
        "## Product Profile (the carton form MUST match this product)",
        product_block,
        "",
        *(["## The three creative directions — ONE variation for each, in slot order: A realises the first, B the "
           "second, C the third, each inside its own direction; copy that direction's direction_id into the "
           "variation's \"direction_id\"",
           json.dumps(directions, ensure_ascii=False)[:12000]] if directions else
          ["## The selected creative direction (stay inside it)",
           json.dumps(direction, ensure_ascii=False)[:8000]]),
        "",
        "## Approved material references (concept influence ONLY)",
        "Express their design principles; never instruct copying a layout, "
        "reproducing a pattern or imitating a recognizable design. No "
        "production use is granted.",
        json.dumps(influence_plan, ensure_ascii=False)[:4000],
        "",
        "## Echo fields (copy verbatim into your JSON)",
        f"approved_reference_ids: {json.dumps(sorted(reference_ids))}",
        f"influence_plan_hash: {plan_hash}",
        "",
        "Return the complete JSON document now.",
    ])

    raw_responses: list[str] = []
    codes: list[str] = []
    payload = None
    provider_model = ""
    shown = None        # [his test blocker on design 123, (2); his goal of 2026-10-10, item 1] the latest three refused
    alike_attempts: list = []

    # a caller under a strict provider-call budget may cap the loop at one
    # generation attempt (no repair call); default keeps generation + repair
    attempts_cap = max_attempts or MAX_ATTEMPTS
    for attempt in range(1, attempts_cap + 1):
        text = message if attempt == 1 else "\n".join([
            "Your previous response was REJECTED:",
            *[f"- {code}" for code in codes],
            "",
            "Return the COMPLETE corrected JSON document — full replacement, "
            "every variation present, no truncation, no prose.",
            "",
            "## Your previous response",
            raw_responses[-1][:20000],
        ])
        log(f"Gate-1 prompts: generation attempt {attempt} of {attempts_cap}")
        raw_output, provider_model = call(system, text)
        raw_text = (extract_text(raw_output)
                    if hasattr(raw_output, "content") else str(raw_output))
        raw_responses.append(raw_text)
        try:
            payload = loads_tolerant(raw_text)
        except ValueError as exc:
            payload = None
            codes = [f"{GATE1_PROMPTS_PARSE_FAILURE}: {str(exc)[:300]}"]
            continue
        # [his test findings on design 121, item 1] the two id rules read as one, before either is checked
        agreed = agree_ids(payload, identity_slots=identity_slots, directions=directions)
        if agreed:
            log("Gate-1 prompts: the ids read by their slots — " + "; ".join(agreed))
        codes = validate_regeneration_payload(
            payload, variation_identities, reference_ids, plan_hash,
            schema_version=schema_version, required_fields=required_fields,
            diversity_fields=diversity_fields, min_pairwise=min_pairwise,
            schema_code=schema_code, empty_code=empty_code,
            not_distinct_code=not_distinct_code, identity_code=identity_code,
            require_per_variation_reference_ids=require_per_variation_reference_ids,
            identity_slots=identity_slots)
        if directions:
            # [his final goal, B4] each variation its own direction's — [his goal of 2026-10-10, item 1] where it is
            # not, said, and bound by its slot when it is shown
            codes = list(codes) + direction_binding_codes(payload, directions)
        if not codes:
            shown = (payload, (), attempt)
            break
        if drawable(payload, len(directions) if directions else len(SHOWN_SLOTS)):
            # [his goal of 2026-10-10, item 1: "NO planner check ever stops a design"] three to draw, refused by a
            # check: kept to be drawn with a note after the one retry
            slots = tuple(identity_slots) if identity_slots else SHOWN_SLOTS
            shown = (told_by_slot(payload, directions, slots), tuple(codes), None)
            alike_attempts.append(attempt)
    if shown is not None:
        # [his test blocker on design 123, (2); his goal of 2026-10-10, item 1] passed — or still refused after the one
        # retry: drawn anyway, with a note
        payload, alike, attempt = shown
        prompts = [{
            # [his final goal, B4] each variation its own direction's, by id
            "direction_name": directions[n]["name"] if directions else direction.get("name", ""),
            "direction_id": directions[n]["direction_id"] if directions else direction.get("direction_id"),
            "full_prompt": v["prompt"],
            "variation_id": v["variation_id"],
            "notes": v.get("title", ""),
            # CORR-2: per-variation assigned reference subset (None for the
            # packaging contract, which has no per-variation reference_ids —
            # keeps the union routing path unchanged).
            "assigned_reference_ids": v.get("reference_ids"),
        } for n, v in enumerate(payload["variations"])]
        return RegenPromptsResult(
            ok=True, payload=payload, prompts=prompts, codes=(),
            # every attempt made, where the three shown are too alike — the note says what happened
            attempts=attempt if attempt is not None else len(raw_responses), raw_responses=tuple(raw_responses),
            provider_model=provider_model, alike=alike,
            alike_attempts=tuple(alike_attempts) if alike else ())
    return RegenPromptsResult(
        ok=False, payload=payload, prompts=[], codes=tuple(codes),
        attempts=MAX_ATTEMPTS, raw_responses=tuple(raw_responses),
        provider_model=provider_model)


__all__ = ["build_regeneration_prompts", "validate_regeneration_payload",
           "RegenPromptsResult", "GATE1_PROMPTS_SCHEMA", "MAX_OUTPUT_TOKENS",
           "GATE1_PROMPTS_PARSE_FAILURE", "GATE1_PROMPTS_SCHEMA_MISMATCH",
           "GATE1_PROMPTS_EMPTY", "VARIATION_PROMPTS_NOT_DISTINCT"]
