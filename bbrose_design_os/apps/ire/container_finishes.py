"""§BH65(c)2 — THE FINISHES: what the press does after the ink, taught to the composer.

OWNER RULED 2026-09-22 (§BH65(c), ``OWNER_BLOCKER_CLEARANCE.md:23150-23253``, LIVE): "the planner writes engraved
fields, tactile relief and spot-UV gloss. Teach it what a cosmetics pack needs". The concept engine has written a
``finish_signature`` on every Gate-1 variation since 2B-2A, and ``container_motif_spec/1.0`` has carried a
``finish_assignments`` slot for it since then — ALWAYS ``{}``. This module fills it and applies it.

A FINISH IS A PLATE, NOT AN INK. Foil, metallic ink, spot UV, gloss varnish, soft-touch laminate, emboss and deboss
each print (or press) from their own plate after the artwork is printed. The emitter writes every plate on its OWN
PAGE of the .ai, after the artwork, as a 100 % black mask in register with page 1 and labelled with the plate's name
— the convention a printer asks for when finishes are supplied as masks. Page 1 DEPICTS each finish (foil in its
metal, a varnish as a sheen, an emboss as its relief); the depiction is never a plate, and the record says so.

WHY MASK PAGES AND NOT NAMED SPOT SWATCHES — THE ALTERNATIVE REJECTED, AND WHY. A named Separation per finish is
the other production convention, and reportlab writes it (the dieline exporter's ``CutContour`` / ``Crease`` are
such swatches). Two measurements rule it out here: (1) the preview is rendered by macOS ``sips``, which does not
simulate overprint, so a clear finish drawn as an overprinting spot on page 1 paints its alternate colour opaque
over the artwork (measured: a spot-UV swatch over a pink ground rendered (255, 255, 254)); (2) the colour
counter's artefact reader (``colour_applications``) keys a Separation by its resource name in lower case, which no
counter entry can equal, so every finish-bearing run would read ``COLOUR_USAGE_ARTEFACT_DISAGREEMENT`` — and
teaching that reader a colour space touches an instrument §BH55(3) freezes. Mask pages need neither: black is
process, and the reader already walks every page. Spot swatches stay an option for the owner to rule.

WHERE A FINISH LANDS. The concept's own sentence is parsed clause by clause ("matte soft-touch laminate ground;
rose-gold hot-stamp foil on petal outlines, window rule, circumference rule ring and BBROSE wordmark; spot gloss UV
over the cartouche interior"): each clause's finishes (read through the ONE contract, ``composer_vocabulary``) go
to each target it names. A target the composed document does not draw is recorded NOT_DRAWN, by name; the lockup
is a raster (``media/brand/logo.png``) and a plate cannot be cut from a raster, so a finish asked of it is
REFUSED_NO_VECTOR_MASTER, by name. Nothing is guessed onto an element the sentence did not name.
[THE OWNER'S SECOND ANSWER OF 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md:23803): "When I approve the logo trace, switch
the mark to it so gold foil can print." A lockup drawn from its APPROVED VECTOR MASTER (``apps/ire/brand_mark.py``)
is not a raster: the finish lands on it, APPLIED, and its plate is cut from the master's own outlines. The raster and
"no lockup is drawn" stay refused, word for word.]

§BH67(b)3 — A FINISH THAT WAS NOT SPECIFIED IS NOT APPLIED. OWNER RULED 2026-09-24 (``OWNER_BLOCKER_CLEARANCE.md:
23350``, LIVE): "THE FINISH READER INVENTS AN EMBOSS from "tactile contrast". A finish that was not specified is not
applied, the same rule as a colour." Measured on task 91's real run: "spot-UV opportunity on remaining five petal
surfaces for tactile contrast" cut a SPOT_UV plate AND an EMBOSS plate, because the contract declares "tactile" an
emboss word. Three things the reader now holds to, each the same rule:
  1. ONLY A PROCESS WORD SPECIFIES. The contract (``composer_vocabulary.FINISH_PROCESS_WORDS``) marks which of a
     finish term's words name what the press does; a word that only says how a surface looks or feels ("tactile",
     "relief", "matte", "glossy", "pearl") EVOKES the finish, is recorded by name as EVOKED_NOT_SPECIFIED and cuts
     no plate.
  2. A COUNT IS A LIMIT. "Two petal fills" in foil and "the remaining five petal surfaces" in spot UV land on two
     of the motif's units and on five of the others — never on every element of the motif, which is applying the
     finish where the sentence did not put it. The words say how many, not which: the units are spread evenly
     across the motif, and the record says so.
  3. A WINDOW'S OWN BORDER IS THE WINDOW'S. "Cartouche border" was read as the window AND a ring, and the ring row
     reported NOT_DRAWN a ring the concept never asked for. A window noun followed by border, frame, outline or
     edge is one target: the window's frame.

Pure: no Django, no ORM.
"""
from __future__ import annotations

import re

from apps.ire import composer_vocabulary as V

SCHEMA = "container_finish_plates/1.0"
ASSIGNMENTS_VERSION = "finish_assignments/1.0"

#: the ink finishes: the finish IS the colour the element prints in
INK_FINISHES = ("foil", "metallic_ink")
#: the clear finishes: the element keeps its own ink and the finish sits on it
CLEAR_FINISHES = ("spot_uv", "gloss_varnish", "soft_touch", "emboss", "deboss")
FINISH_KINDS = INK_FINISHES + CLEAR_FINISHES

APPLIED = "APPLIED"
NOT_DRAWN = "NOT_DRAWN"
REFUSED_NO_VECTOR_MASTER = "REFUSED_NO_VECTOR_MASTER"
#: §BH67(b)3 — the clause's words evoke the finish and no process word names it: recorded, never plated
EVOKED_NOT_SPECIFIED = "EVOKED_NOT_SPECIFIED"
#: [his goal of 2026-10-12, (6): "FINISHES are never invented: a finish plate (soft-touch, gloss, foil, emboss) is made
#: only when my brief or the concept shows it."] a finish only the planner's words name — its concept's finish line —
#: and his brief does not: recorded, never plated (gold in the picture is foil all the same: ``gold_as_drawn``)
NOT_ASKED = "NOT_ASKED"
#: the brief's fields whose words are printed on the pack — its copy, its names — never a finish asked for (124's shade
#: "Gilded Petal" is a name, not a foil)
COPY_FIELD_RE = re.compile(r"^\s*(?:lid\s+)?(?:front\s+copy|back\s+copy|shade\s+names?|arabic\s+name|product|"
                           r"description|ingredients|how\s+to\s+use|warnings|net\s+(?:content|weight))\b", re.I)
#: a field's label opening a line — "Mood:", "Shade names (row by row, left to right):"
FIELD_LABEL_RE = re.compile(r"^\s*[A-Za-z][A-Za-z ]{0,40}(?:\([^)]*\))?\s*:")
#: a row of his shade names, under their field
ROW_RE = re.compile(r"^\s*row\s*\d+\s*:", re.I)

#: the targets a finish clause can name, with the concept's words for each. The LONGEST phrase wins its span
#: ("window rule" is the window's frame, not a rule; "rule ring" is the ring).
TARGET_WORDS = {
    "window_interior": ("window-interior", "cartouche-interior", "interior", "inside-the-window",
                        "inside-the-cartouche"),
    "window": ("window", "cartouche", "window-rule", "window-frame", "cartouche-rule", "medallion",
               # §BH67(b)3: a window noun with its own border is ONE target, the window's frame — never also a ring
               "window-border", "cartouche-border", "medallion-border", "window-outline", "cartouche-outline",
               "medallion-outline", "cartouche-frame", "medallion-frame", "window-edge", "cartouche-edge"),
    "ring": ("ring", "rule-ring", "circumference", "border", "frame", "rim-rule"),
    "motif": ("petal", "petals", "petal-outlines", "outlines", "motif", "droplet", "droplets", "dewdrop",
              "dewdrops", "constellation", "particles", "veil", "ribbon", "ribbons", "bloom"),
    "name": ("name", "product-name", "names", "type", "typography", "lettering", "title", "wordmark-name"),
    "lockup": ("wordmark", "logo", "lockup", "bbrose"),
    "rule": ("rule", "rules", "hairline", "keyline", "divider"),
    "ground": ("ground", "lid", "lid-face", "field", "face", "surface", "background", "overall", "flood"),
    "band": ("band", "side-band", "side", "rim", "sidewall", "edge"),
    "cap": ("cap", "closure", "collar", "base"),
}

_TARGET_RE = [(target, re.compile(V.word_pattern(w))) for target, words in TARGET_WORDS.items() for w in words]

#: the metal words a foil or metallic clause can carry -> the plate's suffix
_METALS = (("rose-gold", "ROSE_GOLD"), ("rose gold", "ROSE_GOLD"), ("champagne", "CHAMPAGNE"),
           ("copper", "COPPER"), ("gold", "GOLD"), ("silver", "SILVER"), ("chrome", "SILVER"),
           ("platinum", "SILVER"), ("pearl", "PEARL"), ("holographic", "HOLOGRAPHIC"))

_PLATE_BASE = {"foil": "FOIL", "metallic_ink": "METALLIC", "spot_uv": "SPOT_UV", "gloss_varnish": "VARNISH_GLOSS",
               "soft_touch": "SOFT_TOUCH", "emboss": "EMBOSS", "deboss": "DEBOSS"}


def target_phrases(clause: str) -> list[tuple[int, int, str, str]]:
    """``(start, end, target, phrase)`` for every target the clause names, the LONGEST phrase winning its span — the
    reading ``_targets`` makes, with the words kept, in the order it takes them (longest first, then left to right).
    [the owner's second answer of 2026-09-25 (OWNER_BLOCKER_CLEARANCE.md, the block headed "Before I start testing"):
    "The lid is missing the concept's rule, ring and radial lines." ONE reading, shared: the concept's own plan
    (``concept_front.lines``) reads its rule and its ring through this, so the plan and the finish reader cannot
    disagree about which element a phrase names — "window rule" the window's, "rim rule" and "rule ring" the ring,
    "hairline rule" the rule.]"""
    matches = [(m.start(), m.end(), t, m.group(0)) for t, rx in _TARGET_RE for m in rx.finditer(clause)]
    matches.sort(key=lambda m: (-(m[1] - m[0]), m[0]))
    taken, kept = [], []
    for s, e, t, w in matches:
        if any(s < te and ts < e for ts, te in taken):
            continue
        taken.append((s, e))
        kept.append((s, e, t, w))
    return kept


def _targets(clause: str) -> list[str]:
    # [the owner's second answer of 2026-09-25: the longest-phrase reading moved into ``target_phrases``, unchanged,
    # so the concept's plan reads the same phrases; the targets still come back in the order it takes them]
    found = []
    for _s, _e, t, _w in target_phrases(clause):
        if t not in found:
            found.append(t)
    return found


def plate_name(kind: str, clause: str) -> str:
    base = _PLATE_BASE[kind]
    if kind in INK_FINISHES:
        low = clause.lower()
        for word, suffix in _METALS:
            if word in low:
                return f"{base}_{suffix}"
    return base


def assignments(finish_signature: str | None) -> dict:
    """``finish_assignments/1.0`` — the concept's finish sentence, clause by clause: each finish (through the ONE
    contract) with the plate it prints from and every target the clause names. A finish in a clause that names no
    target goes to the GROUND, and says so — a finish nobody placed is a flood, which is how the words read."""
    out = {"schema_version": ASSIGNMENTS_VERSION, "read_from": "finish_signature", "clauses": []}
    if not finish_signature or not str(finish_signature).strip():
        out["state"] = "NO_FINISH_SIGNATURE"
        return out
    out["state"] = "READ"
    for clause in re.split(r"[;\n]", V.normalise(finish_signature)):
        clause = clause.strip(" .")
        if not clause:
            continue
        found = {k: words for k, words in V.scan(clause).items() if k in FINISH_KINDS}
        if not found:
            continue
        # §BH67(b)3: only a process word specifies; a finish the clause merely evokes is carried, never plated
        specified = [k for k, words in found.items() if any(V.specifies(k, w, clause) for w in words)]
        targets = _targets(clause)
        out["clauses"].append({
            "clause": clause, "finishes": [{"kind": k, "plate": plate_name(k, clause)} for k in specified],
            "evoked": [{"kind": k, "words": words} for k, words in found.items() if k not in specified],
            "targets": targets or ["ground"], "target_defaulted": not targets})
    return out


# ---------------------------------------------------------------------------------------------------------------
# APPLYING — the clauses land on the elements the composed document draws, by the names its composers give them
# ---------------------------------------------------------------------------------------------------------------

#: a target the composer does not draw on any view it composes, with the reason
_NEVER_DRAWN = {
    "band": "the side band is not a surface this sheet draws (a compact in PLAN shows its lid; a bottle's front)",
    "cap": "a closure is a moulded part; its colour is the cap colour record, not a printed finish",
}
#: the silver family has no brand record; every other metal depicts in the brand's own metallic
_SILVER = "#C4C4C4"
DIVIDER = "rule-front-single"


def _product(doc):
    """§BH65(c)10 — the PRODUCT's own artwork: the first top-level group the composer marks role "product" (the
    container sheet's `Container`, the dropper sheet's hero `Bottle`). Never the sheet's depiction panels
    (`Surfaces`), which draw a surface's continuation at SHEET scale — measured on task 89's real run at (c)9: the foil
    clause "on petal outlines" found two outline sparkles in the "LID TOP" strip panel and a foil plate was cut from
    them, a plate that would sit on the sheet and not on the lid."""
    from apps.ire.graph import Group
    for top in getattr(doc.root, "children", ()):
        if isinstance(top, Group) and top.role == "product":
            return top
    return doc.root


def _walk(node):
    from apps.ire.graph import Group
    yield node
    if isinstance(node, Group):
        for c in node.children:
            yield from _walk(c)


def _leaves(node):
    from apps.ire.graph import Group
    if isinstance(node, Group):
        for c in node.children:
            yield from _leaves(c)
    else:
        yield node


def _front_groups(doc) -> list:
    from apps.ire.graph import Group
    return [n for n in _walk(_product(doc)) if isinstance(n, Group) and n.name == "FRONT_DIRECT_PRINT" and n.clip]


def _named(doc, suffix: str) -> list:
    return [n for n in _walk(_product(doc)) if (getattr(n, "name", "") or "").endswith(suffix)]


#: [his look at 117 drawn from its map, 2026-10-02] a motif's drawn units a finish sentence names by their own noun, the
#: words that name each — "drip outlines ... and sparkle stars" puts the plate on the stars as well as the outlines
NAMED_UNITS = {"sparkle": ("sparkle", "sparkles", "star", "stars"), "drip": ("drip", "drips")}


def _named_units(clause: str) -> tuple:
    return tuple(unit for unit, words in NAMED_UNITS.items()
                 if any(re.search(r"(?<![a-z])%s(?![a-z])" % w, clause) for w in words))


def _motif_leaves(doc, outlines_only: bool, named: tuple = ()) -> list:
    from apps.ire.graph import Group
    out = []
    for n in _walk(_product(doc)):
        # a motif group is named motif-*, behind the dropper's view prefix where it has one ("cu0-motif-front")
        if isinstance(n, Group) and re.match(r"^(?:[a-z0-9]+-)?motif", n.name or ""):
            for leaf in _leaves(n):
                if (leaf.name or "").endswith(DIVIDER):
                    continue
                if outlines_only and not (getattr(leaf, "fill", None) is None and getattr(leaf, "stroke", None)) \
                        and not any(unit in (leaf.name or "") for unit in named):
                    continue
                out.append(leaf)
    return out


def _resolve(doc, target: str, clause: str, refused_approval: dict | None = None) -> tuple[list, str, str]:
    """``(nodes, state, how)`` — the drawn elements a target names in ``doc``. [The owner's second answer of
    2026-09-25: ``refused_approval`` — ``{"codes", "reason"}`` of a brand-mark approval ON FILE that does not hold
    (``brand_mark.REFUSED``), handed in only then — is what the raster lockup's row says instead of "until a vector
    master exists".]"""
    from apps.ire.graph import Image, Path, TextRun
    if target in _NEVER_DRAWN:
        return [], NOT_DRAWN, _NEVER_DRAWN[target]
    if target == "lockup":
        # [the owner's second answer of 2026-09-25: the mark drawn from its approved vector master takes the finish]
        from apps.ire import brand_mark
        marks = [n for n in _named(doc, "logo") if brand_mark.is_mark(n)]
        if marks:
            return marks, APPLIED, ("the lockup, drawn from its approved vector master (%s): the plate is cut from "
                                    "the master's own outlines" % marks[0].asset_id)
        logos = [n for n in _named(doc, "logo") if isinstance(n, Image)]
        if logos and refused_approval is not None:
            # [the owner's second answer of 2026-09-25, §BH58(e): a master and its approval ARE on file and the approval
            # does not hold — the row says so with its code; "until a vector master exists" would name a cause that
            # was not measured]
            return [], REFUSED_NO_VECTOR_MASTER, (
                "the lockup is placed as a raster (media/brand/logo.png) because the brand-mark approval on file is "
                "refused (%s: %s), and a finish plate cannot be cut from a raster"
                % (", ".join(refused_approval["codes"]), refused_approval["reason"]))
        return [], REFUSED_NO_VECTOR_MASTER, (
            "the lockup is placed as a raster (media/brand/logo.png, the controlled fallback until a vector master "
            "exists) and a finish plate cannot be cut from a raster" if logos else "no lockup is drawn")
    if target == "ground":
        nodes = _front_groups(doc)
        return nodes, (APPLIED if nodes else NOT_DRAWN), "the front's clipped region, flooded"
    if target == "name":
        # [his look at 117 drawn from its map, 2026-10-02] a name drawn as the picture's traced lettering is the name
        nodes = [n for n in _walk(_product(doc)) if (isinstance(n, TextRun) and "product-name" in (n.name or ""))
                 or (isinstance(n, Path) and (n.name or "").startswith(TRACED_NAME))]
        return nodes, (APPLIED if nodes else NOT_DRAWN), (
            "the name drawn as the picture's traced lettering" if any(isinstance(n, Path) for n in nodes)
            else "the product-name runs")
    if target == "rule":
        nodes = [n for n in _named(doc, DIVIDER) if isinstance(n, Path)]
        return nodes, (APPLIED if nodes else NOT_DRAWN), "the front's rule (§BB4's divider)"
    if target == "motif":
        outlines = bool(re.search(r"(?<![a-z])outlines?(?![a-z])", clause))
        named = _named_units(clause)
        nodes = _motif_leaves(doc, outlines, named)
        return nodes, (APPLIED if nodes else NOT_DRAWN), (
            ("the motif's outline-only elements" + "".join(" and its %ss" % u for u in named)) if outlines
            else "the motif's elements")
    suffix = {"window": "window-frame", "window_interior": "window-interior", "ring": "frame-ring"}[target]
    nodes = _named(doc, suffix)
    return nodes, (APPLIED if nodes else NOT_DRAWN), f"the element named *{suffix}"


#: §BH67(b)3 — a count the clause gives the motif: "two petal fills", "the remaining five petal surfaces". A number
#: inside a range ("seven-to-nine petals") is not a count of where a finish goes.
_COUNT_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
                "ten": 10, "eleven": 11, "twelve": 12}
_MOTIF_UNIT = r"(?:petals?|droplets?|dewdrops?|drops?|beads?|leaf|leaves|blooms?|strands?|particles?|dots?)"
_COUNT_RE = re.compile(r"(?<![a-z-])(?P<rem>(?:the\s+)?(?:remaining|other)\s+)?(?P<n>"
                       + "|".join(_COUNT_WORDS) + r"|\d{1,2})\s+(?:[a-z]+\s+){0,2}?" + _MOTIF_UNIT + r"(?![a-z])")
#: a motif's UNIT is one drawn thing — a droplet, a petal — named up to its index ("dewdrop-core-12" in
#: "dewdrop-core-12-bead"; "petal-3" in "petal-3-outline"); a highlight belongs to the unit it lights
#: ("dewdrop-highlight-core-12"). Two clusters may share an index ("dewdrop-core-6", "dewdrop-drift-6"): two units.
_UNIT_RE = re.compile(r"^(?P<unit>.*?-\d+)(?=-|$)")


def _units(nodes) -> dict:
    units: dict = {}
    for n in nodes:
        m = _UNIT_RE.match(re.sub(r"(?<![a-z])highlight-", "", n.name or ""))
        units.setdefault(m.group("unit") if m else (n.name or f"unnamed-{len(units)}"), []).append(n)

    def order(key):
        m = re.search(r"-(\d+)$", key)
        return (int(m.group(1)), key) if m else (10 ** 6, key)
    return dict(sorted(units.items(), key=lambda kv: order(kv[0])))


def _spread(keys: list, n: int) -> list:
    """``n`` of ``keys``, spaced evenly through them in order — deterministic, and never the first ``n`` bunched."""
    if n >= len(keys):
        return list(keys)
    return [keys[int((i + 0.5) * len(keys) / n)] for i in range(n)]


def _counted(nodes: list, clause: str, taken: set, shown_metal: tuple = ()) -> tuple[list, dict | None]:
    """The motif's nodes a counted clause names, and the record of the choice; ``taken`` holds the units earlier
    clauses already counted ("the remaining five" reads it). [§BH71 PART 1: ``shown_metal`` — the units the concept
    picture shows lit like metal, measured on it (route A), passed for a clause whose finish is a metal — are the
    ones it counts when their number is the clause's: the words say how many, the picture which.]"""
    m = _COUNT_RE.search(clause)
    if not m or not nodes:
        return nodes, None
    n = _COUNT_WORDS.get(m.group("n")) or int(m.group("n"))
    units = _units(nodes)
    pool = [k for k in units if k not in taken] if m.group("rem") else list(units)
    metal = [k for k in pool if k in shown_metal]
    pick = _spread(pool, n)
    chosen = "spread evenly through the motif — the words say how many, not which"
    if metal and len(metal) == n:
        pick = metal
        chosen = "the ones the concept picture shows lit like metal — the words say how many, the picture which"
    elif metal:
        chosen += " (the picture shows %d lit like metal, the words say %d)" % (len(metal), n)
    taken.update(pick)
    return [node for k in pick for node in units[k]], {
        "count": n, "words": m.group(0).strip(), "of": len(units), "from_remaining": bool(m.group("rem")),
        "units": pick, "chosen": chosen}


def _shown_metal(doc) -> tuple:
    """§BH71 PART 1: the hero's units the concept picture shows lit like metal, as the face recorded them (the
    measured hero, `compose_container._concept_face`) — () for a drawing that carries no measured hero."""
    face = ((doc.metadata or {}).get("concept_front") or {}).get("face") or {}
    return tuple((face.get("hero") or {}).get("metal_units") or ())


def depiction_hex(kind: str, plate: str, brand_metallic_hex: str) -> str | None:
    """What an INK finish looks like on page 1. Every metal depicts in the brand's own metallic record (its flat
    stand-in when the record carries no hex) except the silver family, which no brand record holds."""
    if kind not in INK_FINISHES:
        return None
    return _SILVER if plate.endswith("_SILVER") else brand_metallic_hex


#: the drawn name the picture's traced lettering makes (`compose_container._map_type_group`)
TRACED_NAME = "product-name-traced"
#: [his look at 117 drawn from its map, 2026-10-02] how a front drawn from its concept picture depicts an ink finish
AS_DRAWN = "its own colour as drawn, measured from the concept picture"


def _drawn_hexes(nodes) -> list:
    """The colours ``nodes`` are drawn in — a fill's, a stroke's, a mark's recolour, a run's ink."""
    out = set()
    for n in nodes:
        for paint in (getattr(n, "fill", None), getattr(n, "stroke", None)):
            if getattr(paint, "color", None) is not None:
                out.add(paint.color.to_hex().upper())
        for attr in ("recolor", "color"):
            if getattr(n, attr, None) is not None:
                out.add(getattr(n, attr).to_hex().upper())
    return sorted(out)


#: [his answers after 117 was redrawn on his rules, 2026-10-02 (a18911a), answer 2: "Gold in the picture is foil: the rule
#: above the band goes on the foil plate. That is the rule for every design."] how a part drawn in the picture's gold
#: is plated, said on its row
GOLD_IS_FOIL = ("drawn in the concept picture's gold, so on the gold plate — his rule: \"Gold in the picture is foil ... "
                "That is the rule for every design\" (2026-10-02, a18911a)")
#: … the plate it joins where no clause names a gold one
GOLD_IS_FOIL_PLATE = ("foil", "FOIL_GOLD")


def asked(brief: str | None) -> set:
    """[His goal of 2026-10-12, (6).] The finishes his brief asks for, read as the concept's finish line is read
    (``assignments``) from his own words — never from what prints on the pack: its copy, its Arabic name, its product
    line and his shade names are left out."""
    kept, copy = [], False
    for line in str(brief or "").replace("\r\n", "\n").split("\n"):
        if ROW_RE.match(line):
            continue
        if FIELD_LABEL_RE.match(line):
            copy = bool(COPY_FIELD_RE.match(line))
        elif not line.strip():
            copy = False
        if not copy:
            kept.append(line)
    return {f["kind"] for clause in assignments("\n".join(kept)).get("clauses") or () for f in clause["finishes"]}


def as_asked(record: dict | None, brief: str | None) -> tuple:
    """``(record, set_aside)`` — the concept's finish clauses keeping only the finishes his brief asks for (``asked``);
    each other one a NOT_ASKED row, said, never plated."""
    if not record or not record.get("clauses"):
        return record, []
    wanted = asked(brief)
    clauses, rows = [], []
    for clause in record["clauses"]:
        kept = [f for f in clause["finishes"] if f["kind"] in wanted]
        for f in clause["finishes"]:
            if f["kind"] not in wanted:
                rows.append({"finish": f["kind"], "plate": f["plate"], "target": None, "state": NOT_ASKED,
                             "how": "named only in the concept's finish line (\"%s\") — his brief does not ask for it"
                                    % clause["clause"], "nodes": []})
        clauses.append(dict(clause, finishes=kept))
    return dict(record, clauses=clauses), rows


def apply(doc, record: dict | None, *, brand_metallic_hex: str, refused_approval: dict | None = None,
          depict_as_drawn: bool = False, gold_as_drawn: tuple = (), set_aside: tuple = (),
          gold_plate: tuple | None = None) -> dict:
    """Set every clause's finish on the drawn elements its targets name. Returns ``{"applied": [...], "codes":
    [...]}`` — one row per (clause, finish, target), APPLIED with the node names, or NOT_DRAWN /
    REFUSED_NO_VECTOR_MASTER with the reason, and one EVOKED_NOT_SPECIFIED row per finish a clause only evoked
    (§BH67(b)3). Never raises; never places a finish the sentence did not ask for, nor where it did not put it.
    [The owner's second answer of 2026-09-25: ``refused_approval`` — the ``{"codes", "reason"}`` of a brand-mark
    approval on file that does not hold, passed by the caller only then — is carried on the lockup's row
    (``approval_refused``) and said in its reason; the finish codes are unchanged.]
    [His look at 117 drawn from its map, 2026-10-02: "Always the colors, the picture, not the brand."]
    ``depict_as_drawn`` — a front drawn from its concept picture: an ink finish takes no depiction of its own, so each
    part prints on page 1 in the picture's colour it was drawn in; its row says so (``depiction``) with those colours
    (``depiction_hexes``) in place of the brand's ``depiction_hex``.
    ``gold_as_drawn`` — the names of the nodes a front drawn from its concept picture drew in the picture's gold: each
    not already printing in an ink finish joins the gold plate a clause names (117's), or FOIL_GOLD where none does
    (GOLD_IS_FOIL, his rule of 2026-10-02), on one row of its own."""
    from apps.ire.graph import Color, Finish
    rows, codes = [dict(r) for r in set_aside], []          # [his goal of 2026-10-12, (6)] what the planner alone named
    counted: set = set()                  # §BH67(b)3: motif units an earlier clause counted
    for clause in (record or {}).get("clauses") or ():
        for ev in clause.get("evoked") or ():
            rows.append({"finish": ev["kind"], "plate": None, "target": None, "state": EVOKED_NOT_SPECIFIED,
                         "how": "the clause's words (%s) evoke it and no process word names it — no plate is cut"
                                % ", ".join(ev["words"]), "nodes": [], "words": list(ev["words"])})
            codes.append(f"CONTAINER_FINISH_{EVOKED_NOT_SPECIFIED}:{ev['kind']}:{ev['words'][0]}")
        if not clause["finishes"]:
            continue
        resolved = {}
        for target in clause["targets"]:
            nodes, state, how = _resolve(doc, target, clause["clause"], refused_approval)
            count = None
            if target == "motif":
                metal = ()
                if any(f["kind"] in INK_FINISHES for f in clause["finishes"]):
                    metal = _shown_metal(doc)             # §BH71 PART 1: the picture says which
                nodes, count = _counted(nodes, clause["clause"], counted, metal)
            resolved[target] = (nodes, state, how, count)
        for fin in clause["finishes"]:
            as_drawn = depict_as_drawn and fin["kind"] in INK_FINISHES
            hex_ = None if as_drawn else depiction_hex(fin["kind"], fin["plate"], brand_metallic_hex)
            finish = Finish(kind=fin["kind"], plate=fin["plate"],
                            appearance=Color.from_hex(hex_) if hex_ else None)
            for target in clause["targets"]:
                nodes, state, how, count = resolved[target]
                for n in nodes:
                    if all(f.plate != finish.plate for f in n.finishes):
                        n.finishes.append(finish)
                rows.append({"finish": fin["kind"], "plate": fin["plate"], "target": target, "state": state,
                             "how": how, "nodes": sorted({n.name or type(n).__name__ for n in nodes})[:12],
                             **({"depiction_hex": hex_} if hex_ else {}), **({"count": count} if count else {}),
                             **({"depiction": AS_DRAWN, "depiction_hexes": _drawn_hexes(nodes)} if as_drawn else {}),
                             # [the owner's second answer of 2026-09-25: the refused approval on file, by its codes]
                             **({"approval_refused": {"codes": list(refused_approval["codes"]),
                                                      "reason": refused_approval["reason"]}}
                                if (target == "lockup" and state != APPLIED and refused_approval is not None)
                                else {})})
                if state != APPLIED:
                    codes.append(f"CONTAINER_FINISH_{state}:{fin['kind']}:{target}")
    if gold_as_drawn:
        named = [(f["kind"], f["plate"]) for clause in (record or {}).get("clauses") or () for f in clause["finishes"]
                 if f["kind"] in INK_FINISHES and f["plate"].endswith("_GOLD")]
        kind, plate = named[0] if named else (gold_plate or GOLD_IS_FOIL_PLATE)
        hex_ = None if depict_as_drawn else depiction_hex(kind, plate, brand_metallic_hex)
        finish = Finish(kind=kind, plate=plate, appearance=Color.from_hex(hex_) if hex_ else None)
        wanted = set(gold_as_drawn)
        found = [n for n in _walk(_product(doc)) if (getattr(n, "name", "") or "") in wanted
                 and not hasattr(n, "children")]
        added = []
        for n in found:
            if not any(f.kind in INK_FINISHES for f in n.finishes):
                n.finishes.append(finish)
                added.append(n.name)
        rows.append({"finish": kind, "plate": plate, "target": "gold_as_drawn",
                     "state": APPLIED if found else NOT_DRAWN, "how": GOLD_IS_FOIL,
                     "nodes": sorted(set(added))[:12], "count": len(added),
                     **({"depiction_hex": hex_} if hex_ else {}),
                     **({"depiction": AS_DRAWN, "depiction_hexes": _drawn_hexes(found)} if depict_as_drawn else {})})
    return {"applied": rows, "codes": codes}


__all__ = ["SCHEMA", "ASSIGNMENTS_VERSION", "INK_FINISHES", "CLEAR_FINISHES", "FINISH_KINDS", "APPLIED",
           "NOT_DRAWN", "REFUSED_NO_VECTOR_MASTER", "EVOKED_NOT_SPECIFIED", "NOT_ASKED", "TARGET_WORDS", "plate_name",
           "assignments", "asked", "as_asked", "depiction_hex",
           "AS_DRAWN", "NAMED_UNITS", "TRACED_NAME", "GOLD_IS_FOIL", "GOLD_IS_FOIL_PLATE",
           "apply", "target_phrases"]
