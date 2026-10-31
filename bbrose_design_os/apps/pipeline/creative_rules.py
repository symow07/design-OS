"""[His goal for the pitch, 2026-10-15 (OWNER_BLOCKER_CLEARANCE.md), A: "CREATIVITY, THE MAIN GOAL"] the planner's
creative rules, told before its first attempt and read back by the checks after it:

- (2) "THREE TRULY DIFFERENT DIRECTIONS, every design: one trend-led, one bold and unexpected, one refined and minimal,
  built from the trend brief plus my brief." The role is the slot's — d1 trend-led, d2 bold, d3 minimal (``ROLES``,
  ``role_at``) — and each direction's ``design_axis`` opens on its role's word, so the page shows it; the stored schema
  keeps its fields.
- (3) "NO DEFAULT MOTIFS: no roses, arches or the brand's rose unless my brief asks for them; never repeat a main motif
  used in my recent designs. The BBROSE logo is the brand; it is not the theme." A rose or an arch named in a direction's
  motif fields (``MOTIF_FIELDS``) and not asked for by his brief, or a main motif of his recent designs
  (``recent_motifs``) named again, is a code.

Like every planner check, none stops a design: a set that fails is retried once with its reasons, then shown with a
note (``design_direction_generator.generate_design_directions``). A design that continues its approved container keeps
that container's look, and these checks stand down for it."""
from __future__ import annotations

import re

#: the three roles, in the order the directions take them — the word each direction's design_axis opens on, and what
#: the planner is told it means
ROLES = (
    ("TREND-LED", "built from the CURRENT TREND BRIEF's newest colours, type, materials, illustration styles and "
                  "layouts — what is new this season, made BBROSE's own, never a copy of any one design"),
    ("BOLD", "bold and unexpected — a surprising idea, scale, colour clash, technique or point of view that no "
             "competitor on the shelf shows, still clean, printable and rebuilt in vector"),
    ("MINIMAL", "refined and minimal — restraint, generous space, precise type and one exquisite, richly made detail; "
                "calm, never empty"),
)
ROLE_WORDS = tuple(word for word, _means in ROLES)
#: the fields a direction's motif is read in — the motif checks' own (direction_content._MOTIF_FIELDS) and its name
MOTIF_FIELDS = ("name", "graphic_elements", "imagery_approach", "prompt_seed", "layout_structure")

#: [his (3)] the house's default motifs — never drawn unless his brief asks: the rose in any of its words (never "rose
#: gold", a colour, nor rose water or rosehip, ingredients), the arch in any of its words
DEFAULT_MOTIFS = {
    "ROSE": re.compile(r"\b(?:roses?|rosebuds?|rosettes?|damask rose)\b(?![\s-]*(?:gold|quartz|water|hip|wood|pink|"
                       r"tint|tone|blush|oil|extract|absolute))", re.I),
    "ARCH": re.compile(r"\b(?:arch|arches|arched|archway|archways)\b", re.I),
}
#: how a default motif is said to the planner
DEFAULT_WORDS = {"ROSE": "a rose (a bloom, a bud, a rose petal, the logo's rose enlarged)",
                 "ARCH": "an arch (an arched window, a portal, an archway frame)"}

DEFAULT_MOTIF_UNASKED = "DEFAULT_MOTIF_UNASKED"
RECENT_MOTIF_REPEATED = "RECENT_MOTIF_REPEATED"
#: how many of his latest designs with a chosen direction are read for their main motifs
RECENT_DESIGNS = 6


def role_of(direction) -> str:
    """The role a direction's design_axis opens on ("TREND-LED: ..."), or ""."""
    axis = " ".join(str(direction.get("design_axis") or "").split()).upper()
    for word in ROLE_WORDS:
        if re.match(r"^%s\b" % re.escape(word), axis):
            return word
    return ""


def role_at(index: int, direction=None) -> str:
    """The role of the direction in slot ``index`` — its slot's (d1 trend-led, d2 bold, d3 minimal), the role the
    planner was told for it; a direction that opens on another role's word keeps the word it wrote."""
    said = role_of(direction) if isinstance(direction, dict) else ""
    if said:
        return said
    return ROLE_WORDS[index] if 0 <= index < len(ROLE_WORDS) else ""


def _motif_text(direction) -> str:
    from apps.pipeline.direction_signature import strip_negated_spans
    return strip_negated_spans(" . ".join(str(direction.get(f) or "") for f in MOTIF_FIELDS))


def asked_defaults(text) -> tuple:
    """The default motifs his brief asks for — a rose or an arch named in its design words (the words a brief asks a
    design with, as ``direction_content.asked_motifs`` reads them: never its copy, its quoted words or the lines naming
    the product — a "Rose" serum asks for no rose)."""
    from apps.pipeline.direction_content import _NAMING_LINE_RE, _QUOTED_RE
    from apps.pipeline.direction_signature import strip_negated_spans
    from apps.pipeline.targets.container import product_words
    lines = product_words(text or "").split("\n")
    title = next((i for i, line in enumerate(lines) if line.strip()), None)
    design = _QUOTED_RE.sub(" ", "\n".join(line for i, line in enumerate(lines)
                                           if i != title and not _NAMING_LINE_RE.match(line)))
    affirmative = strip_negated_spans(design)
    return tuple(sorted(k for k, rx in DEFAULT_MOTIFS.items() if rx.search(affirmative)))


def default_motif_codes(directions, asked=()) -> list:
    """A code for each direction naming a default motif his brief does not ask for."""
    out = []
    for i, direction in enumerate(d for d in directions if isinstance(d, dict)):
        text = _motif_text(direction)
        for key, rx in DEFAULT_MOTIFS.items():
            if key not in asked and rx.search(text):
                out.append("%s:%s:%s — %s is no motif of this design unless the brief asks for it"
                           % (DEFAULT_MOTIF_UNASKED, key, direction.get("direction_id") or "d%d" % (i + 1),
                              DEFAULT_WORDS[key]))
    return out


def _groups_in(text) -> set:
    from apps.pipeline.direction_content import _MOTIF_GROUPS
    low = " %s " % text.lower()
    found = {g for g, words in _MOTIF_GROUPS.items() if any(w in low for w in words)}
    found |= {k for k, rx in DEFAULT_MOTIFS.items() if rx.search(text)}
    return found


def recent_motifs(task, n=RECENT_DESIGNS) -> list:
    """[his (3)] the main motifs of his latest designs: ``[{"design", "name", "motif", "groups"}]`` — for each of the
    ``n`` latest designs before this one whose direction was chosen, that direction's name, its graphic elements (its main
    motif, in the planner's own words) and the motif groups they name. Never this design's own project: a Complete
    Product's carton continues its container on purpose."""
    from apps.pipeline.models import CreativeBrief
    rows = (CreativeBrief.objects.exclude(selected_direction_id="").exclude(task_id=task.pk)
            .select_related("task").order_by("-task__created_at"))
    if task.project_id is not None:
        rows = rows.exclude(task__project_id=task.project_id)
    out = []
    for brief in rows[: n * 3]:
        chosen = next((d for d in (brief.directions or []) if isinstance(d, dict)
                       and d.get("direction_id") == brief.selected_direction_id), None)
        if chosen is None:
            continue
        motif = " ".join(str(chosen.get("graphic_elements") or "").split())
        if not motif:
            continue
        out.append({"design": brief.task_id, "name": str(chosen.get("name") or ""), "motif": motif[:240],
                    "groups": sorted(_groups_in(motif))})
        if len(out) >= n:
            break
    return out


def recent_motif_codes(directions, recent, asked=()) -> list:
    """A code for each direction whose graphic elements name a motif group one of his recent designs was built on."""
    banned = {}
    for row in recent:
        for group in row["groups"]:
            if group not in asked:
                banned.setdefault(group, row["design"])
    out = []
    for i, direction in enumerate(d for d in directions if isinstance(d, dict)):
        from apps.pipeline.direction_signature import strip_negated_spans
        hit = _groups_in(strip_negated_spans(str(direction.get("graphic_elements") or "")))
        for group in sorted(hit & set(banned)):
            out.append("%s:%s:%s — design %s was built on it; give this direction its own main motif"
                       % (RECENT_MOTIF_REPEATED, group, direction.get("direction_id") or "d%d" % (i + 1),
                          banned[group]))
    return out


def codes(directions, *, asked=(), recent=()) -> list:
    """Every creative code a set of directions carries."""
    directions = [d for d in (directions or []) if isinstance(d, dict)]
    return default_motif_codes(directions, asked) + recent_motif_codes(directions, recent, asked)


def rules_text(*, asked=(), recent=()) -> str:
    """What the planner is told before its first attempt: the three roles, the default motifs it may not draw, and the
    main motifs of his recent designs it may not draw again."""
    lines = ["The three directions take one role each, in this order, and each direction's design_axis OPENS on its "
             "role's word and a colon (\"TREND-LED: ...\"):"]
    lines += ["- %s — %s." % (word, means) for word, means in ROLES]
    unasked = [DEFAULT_WORDS[k] for k in DEFAULT_MOTIFS if k not in asked]
    if unasked:
        lines += ["", "NO DEFAULT MOTIFS: the brief does not ask for " + " or ".join(unasked) + " — no direction draws "
                  "one, names one or frames its design with one. The BBROSE logo (its small rose inside the O) is the "
                  "brand, placed as it is; it is never the theme, and its rose is never enlarged into a motif. \"Rose "
                  "gold\" as a colour is allowed."]
    if recent:
        lines += ["", "HIS RECENT DESIGNS' MAIN MOTIFS — never a direction's main motif again (find a new subject "
                  "story, a new visual idea):"]
        lines += ["- design %s, \"%s\": %s" % (r["design"], r["name"], r["motif"]) for r in recent]
    lines += ["", "DEPTH AND DETAIL: every direction's printed surface is rich and layered — a ground built of two or "
              "three planes (colour fields, smooth gradients), a texture drawn in vector (grain stipple, fine hatching, "
              "a pattern), several colours, and a hero illustration with things happening behind and around it; the "
              "MINIMAL direction keeps that craft in one exquisite detail on a calm, softly graded field. All of it "
              "clean vector a person can rebuild — never a photograph."]
    return "\n".join(lines)
