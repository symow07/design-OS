"""§AK/WI-3H — reserved copy is registered or it is refused.

§AE2(b) reserves regulated copy from the executor: warnings, manufacturer
lines, ingredients, directions, claims, and the mandatory quantity
declaration. §AE3 requires every substitute to carry the literal token
``⟪PROVISIONAL⟫``. Measured at WI-3H, that token appeared in zero ``.py``
files while three prose documents described it as being in use.

What stands in its place on the PRODUCTION path is
``CONTENT_VERIFICATION_REQUIRED``, which is a working fail-loud marker
under a different name. §AK3 binds the two spellings here, in one place,
so that a search for either finds both. The production path keeps its
spelling; renaming a live marker to satisfy a document would move
``container_back_content_codes`` for no gain.

What stands in its place in the FIXTURES is a twenty-ingredient INCI
list in correct nomenclature, bound to a variable named ``_REAL``. §AK3
rules that this is a reconstruction for measurement and that the repair
is a register rather than a deletion: deleting it would take AD1's
measurement basis with it. A reconstruction for measurement is a
legitimate act; presenting one as copy is not; the difference is
recorded here.

WHEN THIS REFUSES: a string sitting next to a reserved heading in the
same expression, anywhere under ``apps/``, that is not the production
marker, not the charter token, not empty, and not registered below with
a named reason and a named source. It also refuses when a register entry
names text that no longer appears under ``apps/`` — a register that
outlives its subject is A315's clause-4 lesson one level up, and both
directions are checked.

WHAT IT DOES NOT SEE: text assembled at runtime, text read from a file
or a database row, and text reached through a subscript or an attribute.
Those resolve to no constant and are reported as UNRESOLVED rather than
passed over, so the extent of the blind spot is a number this prints
rather than a silence.

SCOPE: §AE2(b) REGULATED COPY only. The PRODUCT heading is deliberately
outside it — the product name comes from the record on the production
path and is brand (§AE2(c)), a different reservation with a different
remedy. Declaring the scope is what stops it being SILENT_EXTENT_LOSS.
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPS = os.path.join(ROOT, "apps")

#: §AK3 clause 1 — the two spellings of one idea, bound in one place.
#: ``PROVISIONAL_TOKEN`` is what §AE3 names and what a future executor
#: greps for. ``PRODUCTION_SPELLING`` is what the emitter has said since
#: before the charter. Neither is the "real" one; the binding is.
PROVISIONAL_TOKEN = "⟪PROVISIONAL⟫"
PRODUCTION_SPELLING = "CONTENT_VERIFICATION_REQUIRED"
ACCEPTED_MARKERS = (PROVISIONAL_TOKEN, PRODUCTION_SPELLING)

#: The headings whose adjacent text is reserved under §AE2(b). NET
#: CONTENT is here because a quantity declaration is a claim about the
#: product (§AK4), not because it reads like prose.
RESERVED_HEADINGS = frozenset({
    "INGREDIENTS", "WARNINGS", "MANUFACTURER", "DIRECTIONS",
    "DESCRIPTION", "CLAIMS", "NET CONTENT",
})


class Reconstruction:
    """One registered reconstruction, pinned to its exact text AND to
    the files it is permitted to appear in.

    Keyed by TEXT and not by variable name: a rename must not silently
    unregister anything, and a reconstruction that drifts by one
    character is a different reconstruction that has not been ruled on.

    ``sites`` exists because of a hole found by mutation, not by
    reading. The first version of this register made a string
    permissible ANYWHERE once registered. Putting the old
    ``add("NET CONTENT", "30 ml / 1.01 fl. oz.", True)`` back on the
    production path left ``check()`` perfectly green — the string was
    registered, so the guard blessed it on the emitter. A register that
    licenses a measurement fixture to become emitted copy is worse than
    no register, because it converts "we know about this" into "this is
    fine". Registration is permission to MEASURE against a string in a
    named place; it is not permission for that string to exist.

    ``manifest_row`` is not decoration — §AK3 clause 3 says the register
    is the ask and not the answer, and the row is where the ask stays
    open.
    """

    def __init__(self, heading, text, reason, source, manifest_row, sites):
        self.heading = heading
        self.text = text
        self.reason = reason
        self.source = source
        self.manifest_row = manifest_row
        self.sites = tuple(sites)


#: The three provenances a reconstruction in this tree actually has.
#: Named rather than free text, because "where did this come from" is
#: the question the register exists to answer and a prose field answers
#: it differently every time.
#:
#:   WRITTEN_BY_EXECUTOR — composed to have something to measure. No
#:     external document. The weakest provenance there is.
#:   DERIVED_FROM_PUBLISHED_ARITHMETIC — back-computed from numbers a
#:     prior record published, and reproducing them. Stronger, and still
#:     not a source: it reproduces a SHAPE, not a text.
#:   QUOTED_FROM_A_RECONSTRUCTION — a fragment of one of the above,
#:     appearing in a cut specification. Inherits its parent's standing
#:     and can be no stronger.
WRITTEN_BY_EXECUTOR = "WRITTEN_BY_EXECUTOR"
DERIVED_FROM_PUBLISHED_ARITHMETIC = "DERIVED_FROM_PUBLISHED_ARITHMETIC"
QUOTED_FROM_A_RECONSTRUCTION = "QUOTED_FROM_A_RECONSTRUCTION"

_INCI_TEXT = (
    "AQUA (WATER), ROSA DAMASCENA FLOWER WATER, GLYCERIN, PROPANEDIOL, "
    "NIACINAMIDE, SODIUM HYALURONATE, ROSA DAMASCENA FLOWER OIL, "
    "TOCOPHEROL, PANTHENOL, ALLANTOIN, XANTHAN GUM, CITRIC ACID, "
    "SODIUM BENZOATE, POTASSIUM SORBATE, PHENOXYETHANOL, "
    "ETHYLHEXYLGLYCERIN, CITRONELLOL, GERANIOL, LINALOOL, FARNESOL")

#: THE REGISTER — twelve distinct strings across fifteen sites, every
#: one of them measured out of the tree by the scan below at WI-3H and
#: none of them typed in from memory.
#:
#: Read the `source` column before the `reason` column. Every entry in
#: this table is an invented statement about a cosmetic product. None of
#: them is copy. Registering one does not make it copy — §AK3 clause 3 —
#: it records that a measurement was taken against an invented string
#: and that the measurement is void the day the owner supplies the real
#: one (§AE3(d)).
RECONSTRUCTED_COPY = (
    Reconstruction(
        heading="INGREDIENTS", text=_INCI_TEXT,
        source=WRITTEN_BY_EXECUTOR,
        reason="AD1's entire measurement basis. A twenty-name INCI list in "
               "correct nomenclature, ordered as a declaration is ordered, "
               "ending in the four EU-declarable fragrance allergens. It is "
               "the subject of `ingredient_ceiling` and of the finding that "
               "no on-pack copy fits this panel — delete it and that finding "
               "becomes unmeasurable, which is why §AK3 registers rather "
               "than deletes. Entered at 7de2369 (2026-08-18) under a commit "
               "headline that calls it REAL REGULATORY COPY. It is not. That "
               "headline is in the permanent record and cannot be edited; "
               "this row is the correction that travels with the string.",
        sites=("apps/ire/tests/test_back_panel.py",),
        manifest_row="B4"),
    Reconstruction(
        heading="DIRECTIONS",
        text="Apply 2-3 drops to cleansed skin morning and evening.",
        source=WRITTEN_BY_EXECUTOR,
        reason="An instruction for use, invented alongside the INCI list at "
               "7de2369 to give the DIRECTIONS section a length. Directions "
               "of use are reserved under §AE2(b): a wrong dosage on a "
               "product someone puts on their face is advice, not a "
               "placeholder that happens to read well.",
        sites=("apps/ire/tests/test_back_panel.py",),
        manifest_row="B6"),
    Reconstruction(
        heading="WARNINGS",
        text="For external use only. Avoid contact with eyes. Discontinue "
             "use if irritation occurs. Keep out of reach of children.",
        source=DERIVED_FROM_PUBLISHED_ARITHMETIC,
        reason="Back-computed from the numbers §X2 published — 39 lines x "
               "2.11667 mm + 5 gaps x 0.8 mm = 86.55 mm, and 613 - 431 = 182 "
               "characters over 10 lines — after the sprint-8 probe that "
               "held the original never landed in the repo. It reproduces "
               "every structural number and misses the character "
               "denominator by five (608 against 613), which "
               "`test_the_x2_document_itself_and_what_could_not_be_"
               "reproduced` states out loud rather than closing by "
               "inventing five characters. The arithmetic pins a SHAPE. It "
               "does not pin these four sentences, and four sentences that "
               "fit the shape are not the four that were there.",
        sites=("apps/ire/tests/test_wik_back_panel_floor.py",),
        manifest_row="B1"),
    Reconstruction(
        heading="MANUFACTURER",
        text="BBROSE Ltd, London N1 6NT, Great Britain.",
        source=DERIVED_FROM_PUBLISHED_ARITHMETIC,
        reason="Same derivation and the same limit as WARNINGS above, and "
               "this one carries a specific postcode. A responsible "
               "person's name and address is mandatory and is the line a "
               "regulator reads first; a plausible one is worse than an "
               "absent one, because an absent one gets supplied.",
        sites=("apps/ire/tests/test_wik_back_panel_floor.py",),
        manifest_row="B2"),
    Reconstruction(
        heading="NET CONTENT", text="30 ml / 1.01 fl. oz.",
        source=WRITTEN_BY_EXECUTOR,
        reason="A mandatory quantity declaration with no field behind it — "
               "`volume_ml`, `net_content`, `fill_volume` and `capacity_ml` "
               "exist nowhere in `apps/`. Until 2026-08-20 this literal was "
               "also on the PRODUCTION path with `verified=True`, emitting "
               "as copy and carrying no code; §AK4 moved it to "
               "CONTENT_VERIFICATION_REQUIRED and the readiness codes went "
               "5 -> 6. What remains registered here are the three FIXTURE "
               "sites. The measured cost either side of that change was "
               "identical — 2 lines and 4.233 mm at 5.0 pt, 2 lines and "
               "5.080 mm at 6.0 pt — so no layout number depends on it.",
        sites=("apps/ire/back_panel_copy.py",
               "apps/ire/tests/test_back_panel.py"),
        manifest_row="B5"),

    # The cut table in `back_panel_copy.py`. §AK2 called this file "not a
    # copy source", which is true and was not the whole truth: it quotes
    # the reconstructions above in order to price cuts against them, and
    # a quotation of an invented ingredient list is an invented
    # ingredient list in a smaller box. The scan found all seven.
    Reconstruction(
        heading="INGREDIENTS", text="AQUA (WATER)",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut INCI_AQUA_GLOSS `removes`. A fragment of _INCI_TEXT.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B4"),
    Reconstruction(
        heading="INGREDIENTS", text="AQUA",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut INCI_AQUA_GLOSS `replacement` — a PROPOSED ingredient "
               "name, which is a proposal about a real product's "
               "declaration and is reserved for the same reason the list is.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B4"),
    Reconstruction(
        heading="INGREDIENTS",
        text=", CITRONELLOL, GERANIOL, LINALOOL, FARNESOL",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut INCI_DROP_FRAGRANCE_ALLERGENS `removes`. The cut is "
               "recorded REFUSED_MANDATORY with its measured saving kept, "
               "so that the next person to propose it reads the refusal "
               "instead of rediscovering the saving.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B4"),
    Reconstruction(
        heading="DIRECTIONS", text=" to cleansed skin",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut DIRECTIONS_SHORTENED `removes`. A fragment of the "
               "invented directions line.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B6"),
    Reconstruction(
        heading="WARNINGS", text=" Discontinue use if irritation occurs.",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut WARNINGS_TO_MANDATORY_MINIMUM `removes`. One of the four "
               "derived sentences, and the cut's own `permission` field "
               "already records that which of the four is a required "
               "precaution is NOT ESTABLISHED.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B1"),
    Reconstruction(
        heading="MANUFACTURER", text=", Great Britain",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut MANUFACTURER_ADDRESS_ABBREVIATED `removes`. The country "
               "from a derived address.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B2"),
    Reconstruction(
        heading="NET CONTENT", text="30 ml",
        source=QUOTED_FROM_A_RECONSTRUCTION,
        reason="Cut NET_CONTENT_METRIC_ONLY `replacement` — a PROPOSED "
               "quantity declaration, derived from a quantity that has no "
               "field behind it.",
        sites=("apps/ire/back_panel_copy.py",),
        manifest_row="B5"),
)


def _registry_by_text():
    return {r.text: r for r in RECONSTRUCTED_COPY}


def _py_files(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith(".py"):
                out.append(os.path.join(dirpath, name))
    return sorted(out)


def _module_constants(tree):
    """Module-level ``NAME = "..."`` bindings, folded.

    Implicit concatenation is already one Constant by the time ast sees
    it, so a five-line INCI list arrives here as one string.
    """
    consts = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    consts[target.id] = node.value.value
    return consts


#: The declared role vocabulary. A reserved heading sits under one of
#: HEADING_ROLE_KEYS; the string that renders as its copy sits under one
#: of TEXT_ROLE_KEYS in the same dict.
#:
#: The first draft of this scan flattened every string in the enclosing
#: expression and paired on content instead of on role, to avoid the
#: §AD0(b) trap of recognising a thing by the shape of its
#: implementation. Run once, it produced 139 findings of which about a
#: dozen were copy: it reported the dict KEYS (`'heading'`, `'cut_id'`)
#: and the prose that DESCRIBES cuts as though both were copy. §AD0(b)
#: cuts both ways — an instrument too loose to tell a subject from its
#: description reports on neither, and a guard with a hundred false
#: findings is a guard that gets silenced. So the pairing is by role,
#: the vocabulary is named here, and vocabulary drift is caught by
#: UNKNOWN_ROLE below rather than by hoping someone notices.
HEADING_ROLE_KEYS = frozenset({"heading", "section"})
TEXT_ROLE_KEYS = frozenset({"text", "body", "copy", "removes", "replacement"})


def _pairs(node, consts, cross):
    """(heading, text_node) pairs declared by one expression.

    Two forms are recognised and both are named:

    * a DICT carrying a reserved heading under a heading-role key and a
      string under a text-role key — the section-record shape that
      ``back_sections`` is built from and that the cut table in
      ``back_panel_copy`` reuses;
    * a CALL whose first positional argument is a reserved heading and
      whose second is a string — the ``add("NET CONTENT", "...", True)``
      helper on the production path, which is the one site where a
      reserved literal reaches an emitted sheet.

    A dict that names a reserved heading and carries strings under NO
    text-role key is reported as UNKNOWN_ROLE, so that a seventh spelling
    of "text" halts this scan the way a new file kind halts record
    selection (A403), rather than passing through it unseen.
    """
    out, unknown = [], []
    if isinstance(node, ast.Dict):
        keyed = {}
        for k, v in zip(node.keys, node.values):
            if isinstance(k, ast.Constant) and isinstance(k.value, str):
                keyed[k.value] = v
        headings = []
        for key in HEADING_ROLE_KEYS & set(keyed):
            _, kind, value = (None,) + _resolve(keyed[key], consts, cross)
            if kind in ("LITERAL", "NAME") and value in RESERVED_HEADINGS:
                headings.append(value)
        if not headings:
            return out, unknown
        texts = TEXT_ROLE_KEYS & set(keyed)
        if not texts:
            strings = [k for k, v in keyed.items()
                       if k not in HEADING_ROLE_KEYS
                       and isinstance(v, ast.Constant)
                       and isinstance(v.value, str) and v.value.strip()]
            if strings:
                unknown.append((headings[0], sorted(strings)))
            return out, unknown
        for heading in headings:
            for key in sorted(texts):
                out.append((heading, keyed[key]))
        return out, unknown
    if isinstance(node, ast.Call) and len(node.args) >= 2:
        _, kind, value = (None,) + _resolve(node.args[0], consts, cross)
        if kind in ("LITERAL", "NAME") and value in RESERVED_HEADINGS:
            out.append((value, node.args[1]))
    return out, unknown


def _resolve(node, consts, cross):
    """(kind, value) for one sibling: LITERAL, NAME, or UNRESOLVED."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return "LITERAL", node.value
    if isinstance(node, ast.Name):
        if node.id in consts:
            return "NAME", consts[node.id]
        hits = cross.get(node.id)
        if hits and len(set(hits)) == 1:
            return "NAME", hits[0]
        return "UNRESOLVED", node.id
    if isinstance(node, ast.JoinedStr):
        return "UNRESOLVED", "<f-string>"
    if isinstance(node, (ast.Subscript, ast.Attribute, ast.Call,
                         ast.BinOp, ast.IfExp)):
        return "UNRESOLVED", type(node).__name__
    return None, None


def _parse_all(root):
    """Every parsable module under ``root``, with the cross-module constant
    index both scanners resolve NAMEs against.

    Returns ``(parsed, cross)``, where ``parsed`` maps path -> (tree, consts)
    and ``cross`` maps a constant's name -> every value it takes anywhere. A
    name is only trusted when that list is unanimous; ``_resolve`` is what
    enforces that, and it is already shared.

    EXTRACTED AT §AV2 and not before, because until the §AE2(c) sibling existed
    there was one caller and no second spelling to bind. §AK3 says two
    spellings of one idea get bound in one place, and the overlap measurement
    that closed §AV4's bet (a) is what made the duplication visible: of the 45
    lines ``brand_strings`` shared verbatim with this module, this preamble was
    the largest contiguous block. The bet HELD at 36.9% against a 60% losing
    condition, so this is not a repair of a wrong ruling — the sibling is still
    a sibling. It is the shared machinery being shared by import, which is what
    ``brand_strings``'s SCOPE note already claimed was the arrangement.

    Unparsable files are skipped, not reported. A scanner is not a linter, and
    a `SyntaxError` in a file under `apps/` will be found by the thing that
    imports it long before it is found here.
    """
    parsed, cross = {}, {}
    for path in _py_files(root):
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (OSError, SyntaxError):
            continue
        consts = _module_constants(tree)
        parsed[path] = (tree, consts)
        for name, value in consts.items():
            cross.setdefault(name, []).append(value)
    return parsed, cross


def scan(root=APPS):
    """Every reserved-copy site under ``root``.

    ``root`` is overridable so a test can build a whole tree and watch
    this refuse without editing the real one (§AA, and the same repair
    WI-3G made to ``classify_complement``).

    Returns (findings, unresolved, unknown_roles, seen_texts).
    """
    parsed, cross = _parse_all(root)

    registry = _registry_by_text()
    findings, unresolved, unknown_roles, seen = [], [], [], set()
    for path, (tree, consts) in sorted(parsed.items()):
        rel = os.path.relpath(path, ROOT)
        for node in ast.walk(tree):
            pairs, unknown = _pairs(node, consts, cross)
            for heading, keys in unknown:
                unknown_roles.append(
                    (rel, getattr(node, "lineno", 0), heading, keys))
            for heading, text_node in pairs:
                kind, value = _resolve(text_node, consts, cross)
                if kind is None:
                    continue
                line = getattr(text_node, "lineno",
                               getattr(node, "lineno", 0))
                if kind == "UNRESOLVED":
                    unresolved.append((rel, line, heading, value))
                    continue
                if value in ACCEPTED_MARKERS or not value.strip():
                    continue
                seen.add(value)
                entry = registry.get(value)
                if entry is None:
                    findings.append(("UNREGISTERED", rel, line, heading,
                                     value, None))
                elif rel not in entry.sites:
                    findings.append(("OFF_SITE", rel, line, heading,
                                     value, entry))
    return findings, unresolved, unknown_roles, seen


def check(root=APPS, include_stale=None):
    """Refusal lines, or an empty list. Both directions (A315 clause 4).

    ``include_stale`` governs the SECOND direction — "is every register
    entry still earning its place". That question is asked of the
    register against the tree it describes, which is ``apps/``; asked of
    a two-line temp tree it reports all twelve entries as stale and
    buries the finding the test was written to see. So it defaults to ON
    for the real tree and OFF for an overridden one, and the default is
    a named argument rather than a hidden branch, because a check that
    quietly switches itself off is the shape of A316.
    """
    if include_stale is None:
        include_stale = os.path.abspath(root) == os.path.abspath(APPS)
    findings, unresolved, unknown_roles, seen = scan(root)
    problems = []
    for kind, rel, line, heading, value, entry in findings:
        shown = value if len(value) <= 90 else value[:87] + "..."
        if kind == "UNREGISTERED":
            problems.append(
                f"UNREGISTERED_RESERVED_COPY: {rel}:{line} {heading} -> "
                f"{shown!r} — reserved under §AE2(b). Supply it from the "
                f"record, mark it {PRODUCTION_SPELLING}, or register it in "
                f"RECONSTRUCTED_COPY with a named source and a manifest row.")
        else:
            problems.append(
                f"RECONSTRUCTION_OFF_SITE: {rel}:{line} {heading} -> "
                f"{shown!r} — registered for {list(entry.sites)} and this is "
                f"not one of them. Registration permits MEASURING against "
                f"this string where it was ruled on; it does not permit the "
                f"string to travel (manifest row {entry.manifest_row}).")
    for rel, line, heading, keys in unknown_roles:
        problems.append(
            f"UNKNOWN_ROLE: {rel}:{line} {heading} carries strings under "
            f"{keys} and no text-role key — extend TEXT_ROLE_KEYS or rule "
            f"the keys out by name")
    if include_stale:
        for r in RECONSTRUCTED_COPY:
            if r.text not in seen:
                problems.append(
                    f"STALE_REGISTRATION: {r.heading} is registered but its "
                    f"text no longer appears under apps/ "
                    f"(source: {r.source})")
    return problems, unresolved


def main():
    problems, unresolved = check()
    print(f"reserved headings: {len(RESERVED_HEADINGS)}  "
          f"registered reconstructions: {len(RECONSTRUCTED_COPY)}  "
          f"unresolved siblings: {len(unresolved)}")
    for rel, line, heading, what in unresolved[:12]:
        print(f"  UNRESOLVED {rel}:{line} {heading} <- {what}")
    if len(unresolved) > 12:
        print(f"  ... and {len(unresolved) - 12} more")
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        print(f"RESERVED_COPY_REFUSED: {len(problems)}", file=sys.stderr)
        return 1
    print("RESERVED_COPY_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
