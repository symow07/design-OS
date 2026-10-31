"""§AV2 — the §AE2(c) BRAND-STRING guard: the sibling ``reserved_copy`` names
and never had.

WHY THIS IS A SIBLING AND NOT A WIDER ``reserved_copy``. §AU5(1) left "extend
its scope, or a sibling checker" to the executor. §AV2 ruled sibling, and the
reason is measured rather than stylistic. ``reserved_copy._pairs`` gates every
path on ``RESERVED_HEADINGS`` membership and returns at its line 349 *before*
the ``UNKNOWN_ROLE`` net is reached. Fed AU1's descriptor shape —
``{"text": ..., "rel": ..., "kind": "descriptor"}`` — it produces
``pairs=[] unknown=[]``: totally invisible, marked or unmarked, because the
dict names no reserved heading. Two controls confirm the scanner is otherwise
sensitive (a real reserved section is seen; a seventh spelling of ``text``
raises ``UNKNOWN_ROLE``).

That early return is not a bug. ``reserved_copy``'s own comment records that a
looser, content-paired first draft produced "139 findings of which about a
dozen were copy", and that a guard with a hundred false findings "is a guard
that gets silenced". ``RESERVED_HEADINGS`` is what bought the selectivity.
Widening it to admit brand tiers would spend exactly that, and would make
``reserved_copy``'s own SCOPE declaration false — the declaration §AU5 quotes
as the reason this remedy is owed. A guard that lies about its own scope to
cover one more case is §AD0(b) with the polarity reversed.

THE THIRD STATE, ADDED AT §BB7(a) AND NOT PRESENT WHEN THIS FILE WAS BUILT.
As first committed this guard had two verdicts for a descriptor: it carries
``MARKER``, or it is refused. Those cover a fabrication and a fabrication
honestly labelled, which were the two states §AU5 was written about — because
on the day §AU5 was written there was no third one. C9 was open, every
descriptor in the tree was invented, and the guard's own refusal message
already named the state it could not represent: "Supply it from the owner
record, or mark it provisional per §AE3." It had no idea what to do if you
actually did the first thing.

§BB7(a) ruled C9. ``RULED_STRINGS`` is that verdict: a VALUE-level register,
each entry pinned to the sites it may appear at, mirroring
``reserved_copy.RECONSTRUCTED_COPY`` — including the ``sites`` field, which
that register gained only after a mutation showed a register without one
"licenses a measurement fixture to become emitted copy".

WHAT THE THIRD STATE IS NOT. It is not an exemption for the ``descriptor``
kind. Putting ``"descriptor"`` into ``NOT_OURS`` would have closed the same
commit and would have retired the guard, since ``descriptor`` is the only kind
``BRAND_KINDS`` names — the whole instrument, switched off to admit one string.
Exactly one thing passes now that did not pass before: a registered entry's
text, under its kind, at one of its own sites.

THE DIRECTION, STATED CORRECTLY ON THE SECOND ATTEMPT. This paragraph ended
"Two new refusals arrive with it (``RULED_STRING_OFF_SITE``,
``RULED_STRING_ALTERED``), and both are strictly additional. The guard is
narrower after this change than before it." An audit measured it backwards:
the accepted set GAINED one member and lost none, so the guard is WIDER, by
exactly that one string at exactly that one file. The two new codes refuse
nothing that was not refused already — they RE-LABEL values that
``UNMARKED_BRAND_STRING`` was catching, so the operator is told he moved or
altered the owner's string instead of being told he invented one. That is a
better message, not a stricter guard, and the file says so at ``_ruled_near``
and the test file says so twice; only this paragraph had it the other way
round. It is corrected rather than deleted because a change describing itself
as a tightening while widening is the precise thing a register like this one
is at risk of being.

SCOPE: §AE2(c) BRAND AND TASTE strings only — the descriptor tier that AU1
ruled the shape of. Regulated copy (§AE2(b)) is ``reserved_copy``'s and stays
there. The two files share ``_parse_all`` and ``_resolve`` by import — §AK3,
and the shared preamble was extracted at §AV2 once there were two callers of
it; the vocabulary and the verdict are what differ.

WHAT THIS CANNOT DO, STATED HERE RATHER THAN DISCOVERED LATER. This is a
STATIC scan of source. §AU8(e) — "no emission carrying a ⟪PROVISIONAL⟫
descriptor reaches print, a proof, or any owner-facing artefact" — is a clause
about RUNTIME objects. A descriptor arriving from a database row, a fixture or
an owner-supplied C9 string is in no ``.py`` file and this scanner is
structurally incapable of refusing it. That seam is covered by the runtime half
(``BRAND_STRING_PROVISIONAL`` in ``container_production_readiness``), and the
two halves together are the §AE2(c) remedy. Neither alone is.

Pure: no Django, no ORM, no network.
"""
import ast
import importlib.util
import os
import sys

# SCRIPT MODE, AND WHY THIS PREAMBLE IS NOT OPTIONAL.
#
# This file was committed at 84e0018 importing ``tools.reserved_copy`` with no
# preamble. That resolves under pytest, where the pytest root is already
# ``sys.path[0]``, and dies as a bare script:
#
#     $ venv/bin/python tools/brand_strings.py
#     ModuleNotFoundError: No module named 'tools'
#
# because in script mode ``sys.path[0]`` is ``tools/`` itself. The sibling this
# file exists to complement is invoked in EXACTLY that bare-script form by
# ``tools/guarded_commit.sh``, and ``reserved_copy``'s own docstring records the
# mirror-image constraint — it may not import from ``apps/`` for this same
# reason. So the constraint was written down, in the file next door, and this
# one was built violating it in the opposite direction. A guard that runs only
# where it is not needed is the §AA shape at one remove: it reports green in the
# suite while the commit path it was built for never calls it at all.
#
# AND A sys.path PREAMBLE IS NOT ENOUGH, WHICH WAS MEASURED, NOT ASSUMED.
#
# The first fix here inserted the pytest root at ``sys.path[0]`` and its comment
# claimed that this also settled the two-roots hazard — the git root and the
# pytest root each hold a ``tools/``, the git root's WITH an ``__init__.py`` and
# the pytest root's without. A test written to pin that claim refuted it:
#
#     PYTHONPATH=<git root> venv/bin/python tools/brand_strings.py
#     ModuleNotFoundError: No module named 'tools.reserved_copy'
#
# Note the name in that error. ``tools`` RESOLVED — to the git root's package —
# and only the submodule was missing. That is PEP 420 working as specified: a
# regular package found ANYWHERE on the path beats a namespace portion found
# earlier, so position cannot win this argument and ``insert(0)`` was a fix
# whose stated reason was false. It is recorded here because the repository's
# own notes already carry "git root first on PYTHONPATH makes tools.brand_strings
# unresolvable" as a known gotcha, and a known gotcha that keeps being
# rediscovered is one nobody has removed.
#
# So the sibling is loaded BY PATH, which no sys.path ordering can misdirect.
# This is the pattern ``tools/record_integrity.py`` already uses to reach
# ``sweep_manifest``; §AK3 gives one idea one spelling, and this is that
# spelling. The cost is that ``reserved_copy`` may be executed twice in a pytest
# process — it is a pure AST scanner with no state and no Django, so the second
# execution costs a parse and changes no behaviour.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SIBLING_PATH = os.path.join(_HERE, "reserved_copy.py")
_spec = importlib.util.spec_from_file_location(
    "bbrose_tools_reserved_copy", _SIBLING_PATH)
_rc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rc)

APPS, ROOT, PROVISIONAL_TOKEN = _rc.APPS, _rc.ROOT, _rc.PROVISIONAL_TOKEN
_parse_all, _resolve = _rc._parse_all, _rc._resolve

SCHEMA = "brand_string_scan/1.0"

#: §AE3's marker, imported rather than re-spelled. Two spellings of one token
#: is the §AK3 defect this repository has already paid for once.
MARKER = PROVISIONAL_TOKEN

#: The DECLARED brand-string kinds. AU1 ruled the C8 shape as exactly one
#: supporting line under ``kind: "descriptor"``, so exactly one kind is
#: declared. This is deliberately not a taxonomy of brand tiers I invented —
#: naming tiers the owner has not ruled would be §AE2(c) work under §AE1
#: cover, which is the thing the charter reserves.
#:
#: A dict carrying a ``kind`` this set does not name is reported as
#: UNKNOWN_BRAND_KIND rather than skipped, so a second tier arriving later
#: halts this scan instead of passing through it unseen — the same discipline
#: as ``reserved_copy``'s UNKNOWN_ROLE and §AV1's UNDECLARED_READINESS_SECTION.
BRAND_KINDS = frozenset({"descriptor"})

#: Kinds that occur in this exact shape and are deliberately NOT this guard's,
#: each ruled out BY NAME with its reason and the instrument that does own it.
#:
#: Being explicit here is what keeps the halting discipline honest. A kind in
#: NEITHER set still halts as UNKNOWN_BRAND_KIND, so this is a declared
#: boundary a reviewer can argue with, not a silent skip.
NOT_OURS = {
    "net_content":
        "§AE2(b) REGULATED, not brand — NET CONTENT is inside "
        "reserved_copy.RESERVED_HEADINGS and is manifest row B5, already "
        "BLOCKING. AU1 rejected 'descriptor plus volume' for exactly this "
        "reason. See RESERVED_COPY_BLIND_SPOT below: reserved_copy does not "
        "presently see it in this shape, which is a gap in THAT guard and is "
        "not closed by widening this one.",
    "product_name":
        "§AE2(c), but supplied FROM THE PRODUCT RECORD rather than invented — "
        "reserved_copy's own docstring names that path. The value in use is "
        "established (97 sites across apps/), so reporting it as an unmarked "
        "fabrication would be false in the other direction: §AU0(b), an "
        "authority recorded as though it were something it is not.",
    # [the owner's message of 2026-10-29, "Fix the 5 fast tests that already failed before the merge … brand strings"]
    "TextType.POINTTEXT":
        "Illustrator's own text-frame type, not a brand tier: the native "
        "read-back script in round_files_export (native_roundtrip) records "
        "each reopened text frame as {text, layer, kind: String(t.kind), "
        "characters}, so a frame's 'kind' is Illustrator's TextType enum. "
        "Its words are the live type the writer set from the brief's COPY; "
        "the writer's read-back (fonts, sizes, colours) owns that frame, and "
        "the copy it carries is reserved_copy's.",
}

#: THE ONE PROVENANCE THIS REGISTER ADMITS. Named rather than left as free
#: text, for ``reserved_copy``'s reason: "where did this come from" is the
#: question a register exists to answer, and a prose field answers it
#: differently every time. There is exactly one name because there is exactly
#: one way a brand string may get in here — the owner typed it, in a sitting,
#: and the typing is committed. A second provenance is a second ruling.
OWNER_TYPED_AT_TERMINAL = "OWNER_TYPED_AT_TERMINAL"


class RuledString:
    """One §AE2(c) string the owner has RULED, pinned to the sites it may use.

    The guard this file implements had exactly two verdicts for a descriptor:
    it carries ``MARKER``, or it is refused. That is complete for the two
    states §AU5 was written about — a fabrication, and a fabrication honestly
    labelled. It has no verdict for the third state, which is what an owner
    ruling produces: a string that is neither invented nor provisional.

    Marking a ruled string would be false (``MARKER`` means the owner did not
    supply it, and he did). Refusing it would be false in the other direction —
    §AU0(b), an authority recorded as though it were something it is not, which
    is the reason ``NOT_OURS`` already gives for the product name. So the third
    state is declared, and it is declared at the level of the VALUE.

    NOT at the level of the KIND. Adding ``"descriptor"`` to ``NOT_OURS`` would
    have closed the same commit and would have exempted every descriptor
    forever, which is a bar being moved (§AU6(c)) dressed as a fix: the next
    fabricated descriptor would ride in behind this ruling. What is registered
    here is a string, not a category.

    ``sites`` is not decoration and the reason is measured, not stylistic.
    ``reserved_copy``'s own comment records that its register gained a ``sites``
    field only after a mutation showed a register without one "licenses a
    measurement fixture to become emitted copy". A ruled string that may appear
    anywhere is the same hole with better paperwork: register once, use
    everywhere, and the register becomes a laundering channel rather than a
    record.

    ``authority`` cites the SUBSECTION and not a line number, deliberately. The
    ``pc.vqr3_artwork_composition`` tracker field has carried three separate
    stale line numbers into ``OWNER_BLOCKER_CLEARANCE.md`` and says so about
    itself; a citation the file can move out from under is a citation that goes
    quietly wrong.
    """

    def __init__(self, text, kind, source, ruling, authority, reason, sites):
        self.text = text
        self.kind = kind
        self.source = source
        self.ruling = ruling
        self.authority = authority
        self.reason = reason
        self.sites = tuple(sites)

    def __repr__(self):
        # A test asserting on these rows prints the row on failure. Without
        # this it prints an address, which tells the reader nothing about
        # WHICH register entry was involved.
        return f"RuledString({self.ruling}: {self.text!r} {self.kind})"


#: THE REGISTER — one string, because one has been ruled.
#:
#: WHAT THE OWNER RULED AND WHAT HE DID NOT, kept apart here because §BB7(a)
#: keeps them apart and collapsing them would widen a ruling by transcription.
#: He typed the characters. §BB7(a) then records, IN ITS OWN WORDS, that the
#: prohibitions on reshaping them — no case-fold, no hyphen, no appended volume
#: — are "the executor's reading, and are marked as his", an inference from
#: what "verbatim" has to mean rather than a sentence the owner wrote, and it
#: says outright: "If the owner wants ``Facial Serum``, or a volume appended,
#: he says so and this paragraph does not stand in his way."
#:
#: So ``RULED_STRING_ALTERED`` below enforces an EXECUTOR INFERENCE. It is a
#: refusal either way — an altered value is refused today as an unmarked
#: fabrication — and what the inference buys is a true message instead of a
#: false one, which matters in a repository whose §BB7 exists because the
#: owner's punctuation was altered inside quotation marks twice.
RULED_STRINGS = (
    RuledString(
        text="FACIAL SERUM",
        kind="descriptor",
        source=OWNER_TYPED_AT_TERMINAL,
        ruling="C9",
        authority="OWNER_BLOCKER_CLEARANCE.md §BB7(a)",
        reason="The front descriptor line. Manifest row C9 was BLOCKING from "
               "the day this guard was built — its first run found the "
               "fabricated stand-in that row was open for — and §BB3 declined "
               "to rule it, authorising a ⟪PROVISIONAL⟫ substitute instead. "
               "That substitute killed both wired deliverable paths in §BB6 "
               "on BRAND_STRING_PROVISIONAL and is the reason the wiring was "
               "reverted. §BB7(a) rules the string and closes the row: two "
               "words, one space, both uppercase, recorded verbatim.",
        #: The second site is the EMISSION site, and it arrived when §BB7(c)
        #: wired both call sites: the string stopped being a thing the register
        #: records and became a thing the front prints. It is a production
        #: module rather than a third copy at each call site because
        #: front_hierarchy.py supplies the tiers to the ONE composer both wired
        #: call sites reach — so this ruling has exactly one emitted spelling,
        #: and RULED_STRING_ALTERED still guards it against drift.
        #:
        #: "BOTH", NOT "ALL THREE" — an earlier draft of this comment said all
        #: three and was false. `compose_dropper_sheet` is a third production
        #: composer and is NOT fed from here: its front already draws a
        #: DIFFERENT product's descriptor ("N I G H T   R E P A I R   O I L",
        #: `compose_dropper.py:682`), and §BE forbids overwriting one product's
        #: copy with another's. Whether the front hierarchy gains a per-product
        #: source in place of this ruled literal is OWNER-RESERVED, so this
        #: tuple must not grow a dropper row until that is ruled.
        #:
        #: §BH65(b)1 RULED IT, 2026-09-22: "Derive it from the product; where no
        #: record says what the product is, print nothing rather than a wrong
        #: word." The front hierarchy now takes each product's own descriptor
        #: from its record, so this string is NO LONGER EMITTED from
        #: `front_hierarchy.py` and that site is removed. The ruling stands and
        #: the string stays registered: it is still the owner's words for a
        #: facial serum, and the measurement fixture still carries it. The
        #: register is NARROWER for this — one site fewer, none added.
        #:
        #: §BH67(c)2 RULED THE DROPPER'S SOURCE TOO, 2026-09-24: "Derive both
        #: from the product record; where the record is silent, print nothing."
        #: The dropper front's letter-spaced descriptor constant is gone; it prints
        #: its own product's descriptor or none. This tuple still has no dropper
        #: row, because the dropper still prints no ruled string.
        sites=("apps/ire/tests/test_wit_unit_analysis.py",)),
)

#: MEASURED, 2026-08-21, and recorded because it is a finding about a
#: DIFFERENT guard that this one turned up on its first run.
#:
#: ``reserved_copy`` registers "30 ml" as a reconstruction pinned to the single
#: site ``apps/ire/back_panel_copy.py`` (manifest row B5), and its
#: RECONSTRUCTION_OFF_SITE rule exists to stop a registered string travelling —
#: its own comment says the ``sites`` field was added after a mutation showed
#: that a register without it "licenses a measurement fixture to become emitted
#: copy". That string now also appears in
#: ``apps/ire/tests/test_wit_unit_analysis.py`` under ``kind: "net_content"``
#: and ``reserved_copy.check()`` returns ZERO problems, because the dict names
#: no ``heading`` key and ``_pairs`` returns before it can look further.
#:
#: So the §AE2(b) guard has the same structural blind spot for the ``kind``
#: vocabulary that made this sibling necessary for §AE2(c). Reported, not
#: repaired here: closing it means teaching ``reserved_copy`` a second dict
#: shape, which is a change to a working guard and belongs in its own ruling.
#:
#: THE LINE NUMBER CAME OFF THIS CONSTANT, AND THE REASON IS THE SAME ONE
#: ``RuledString.authority`` gives. It read
#: ``"apps/ire/tests/test_wit_unit_analysis.py:533"``. Measured: the string was
#: at 554 before this commit and the comment inserted above the descriptor tier
#: moved it to 570 — so the pin was 21 lines stale when it was written down and
#: this commit pushed it to 37, twenty lines below a new paragraph explaining
#: that a citation the file can move out from under goes quietly wrong. Nothing
#: caught it: the test that reads this constant split the number off and never
#: used it. The number is gone; the file path and the string are what identify
#: the finding, and the test searches for the string.
RESERVED_COPY_BLIND_SPOT = (
    "apps/ire/tests/test_wit_unit_analysis.py", "30 ml", "B5")

#: The key naming a brand string's tier, and the keys its text may sit under.
KIND_ROLE_KEYS = frozenset({"kind"})
TEXT_ROLE_KEYS = frozenset({"text"})

UNMARKED_BRAND_STRING = "UNMARKED_BRAND_STRING"
UNKNOWN_BRAND_KIND = "UNKNOWN_BRAND_KIND"
RULED_STRING_OFF_SITE = "RULED_STRING_OFF_SITE"
RULED_STRING_ALTERED = "RULED_STRING_ALTERED"


def _ruled_exact(value, kind):
    """The register entry whose text and kind this value IS, or ``None``.

    Byte equality, and nothing looser. ``value`` reaching here has already been
    resolved to a literal, so there is no normalisation to undo and none is
    applied: the owner typed characters and this compares characters.
    """
    for entry in RULED_STRINGS:
        if entry.text == value and entry.kind == kind:
            return entry
    return None


def _ruled_near(value, kind):
    """The register entry this value is a RESHAPING of, or ``None``.

    Case-folded and whitespace-collapsed, and only consulted after
    ``_ruled_exact`` has said no — so a hit here is by construction a value
    that is the ruled string in every respect except the characters.

    THIS WIDENS NO PERMISSION. Every value it catches is refused with or
    without it, because a reshaped ruled string carries no ``MARKER`` and is
    an ``UNMARKED_BRAND_STRING``. What it changes is which sentence the
    operator reads: "you altered the owner's string" rather than "you invented
    a string", and only the first of those is true.
    """
    def _fold(text):
        return " ".join(text.split()).casefold()

    folded = _fold(value)
    for entry in RULED_STRINGS:
        if entry.kind == kind and _fold(entry.text) == folded:
            return entry
    return None


def _brand_pairs(node, consts, cross):
    """(kind, text_node) pairs declared by one dict expression, plus unknowns.

    Recognises the AU1 shape: a dict carrying a brand ``kind`` under a
    kind-role key and a string under a text-role key. Unlike
    ``reserved_copy._pairs`` there is no CALL form, because a brand descriptor
    has no ``add(heading, text, verified)`` analogue on the production path —
    it arrives as a record in a list.

    A dict whose ``kind`` is a string OUTSIDE ``BRAND_KINDS`` but which
    otherwise has this exact shape is returned as an unknown, not dropped.
    """
    out, unknown = [], []
    if not isinstance(node, ast.Dict):
        return out, unknown
    keyed = {}
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and isinstance(k.value, str):
            keyed[k.value] = v
    kind_keys = KIND_ROLE_KEYS & set(keyed)
    texts = TEXT_ROLE_KEYS & set(keyed)
    if not kind_keys or not texts:
        return out, unknown
    for key in sorted(kind_keys):
        kind, value = _resolve(keyed[key], consts, cross)
        if kind not in ("LITERAL", "NAME"):
            continue
        if value in BRAND_KINDS:
            for text_key in sorted(texts):
                out.append((value, keyed[text_key]))
        elif value in NOT_OURS:
            continue          # declared as another instrument's, by name
        else:
            unknown.append((value, sorted(texts)))
    return out, unknown


def sites(root=APPS):
    """Every RESOLVED brand-string site under ``root``, MARKED OR NOT.

    Returns (found, unresolved, unknown_kinds), where ``found`` is a list of
    ``(rel, line, kind, value, marked, ruled)``. ``marked`` records whether the
    value already carries ``MARKER``; ``ruled`` is the ``RuledString`` this
    value exactly is, or ``None``. ``scan`` is exactly this with the rows that
    are cleared — marked, or ruled AND on one of their register's sites —
    dropped.

    THE SIXTH COLUMN IS A SEPARATE COLUMN ON PURPOSE. Folding "ruled" into
    "marked" would give one field two meanings and make
    ``test_the_ruled_string_took_its_place_and_is_registered`` unable to say
    what it is for — it asserts ``marked is False`` and ``ruled is not None``
    on the SAME row, which is unstatable in one field. MARKER means the owner
    did NOT supply this; a ruled string is the case where he did. One idea, one
    spelling (§AK3) cuts both ways — two ideas may not share one.

    (This paragraph cited ``test_the_descriptor_that_was_found_is_still_marked``
    until an audit observed that the same commit had renamed it. A citation to
    a test that no longer exists is an argument resting on nothing, which is
    what the surrounding paragraphs say about line numbers, in the other
    vocabulary.)

    WHY THIS IS SPLIT OUT rather than left inside ``scan``. "Where are the
    brand strings" and "which brand strings are refused" are two questions over
    one traversal, and §AK3 gives one idea one spelling. The second question is
    the guard; the first is what an owner-facing report needs, and what a test
    needs to count the sites of a string that is ALREADY marked — ``scan``
    cannot answer that, because marking a string is precisely how it leaves
    ``scan``'s output.

    ``root`` is overridable so a test can build a whole tree and watch this
    refuse without editing the real one — §AA, and the same accommodation
    ``reserved_copy.scan`` and ``classify_complement`` already make.
    """
    parsed, cross = _parse_all(root)

    found, unresolved, unknown_kinds = [], [], []
    for path, (tree, consts) in sorted(parsed.items()):
        rel = os.path.relpath(path, ROOT)
        for node in ast.walk(tree):
            pairs, unknown = _brand_pairs(node, consts, cross)
            line = getattr(node, "lineno", 0)
            for bad_kind, keys in unknown:
                unknown_kinds.append((rel, line, bad_kind, keys))
            for kind, text_node in pairs:
                resolved, value = _resolve(text_node, consts, cross)
                text_line = getattr(text_node, "lineno", line)
                if resolved == "UNRESOLVED":
                    # NOT a finding. A descriptor computed at runtime is
                    # precisely what a static scan cannot judge, and reporting
                    # every dynamic path is how a guard earns its 139 false
                    # findings and gets silenced. This is the seam the runtime
                    # half exists to cover, and it is recorded, not hidden.
                    unresolved.append((rel, text_line, kind, value))
                    continue
                if resolved != "LITERAL" and resolved != "NAME":
                    continue
                if not value.strip():
                    continue
                found.append((rel, text_line, kind, value,
                              MARKER in value, _ruled_exact(value, kind)))
    return found, unresolved, unknown_kinds


def scan(root=APPS):
    """The REFUSABLE brand-string sites: ``sites`` minus the cleared ones.

    Returns (findings, unresolved, unknown_kinds) — findings being
    ``(code, rel, line, kind, value, entry)``, where ``code`` is the verdict
    and ``entry`` is the register row a ruled-string verdict is about, or
    ``None``.

    THE FINDING TUPLE GAINED A VERDICT COLUMN and did not gain a second
    traversal. Three refusals now come out of here and they are not variants
    of one message: an unmarked fabrication is a string nobody authorised, an
    off-site ruled string is an authorised string spreading past its
    authorisation, and an altered one is the owner's characters changed. A
    caller that had to infer which from the value would be doing the guard's
    job in the guard's caller.

    EXACTLY ONE THING PASSES HERE THAT DID NOT PASS BEFORE: a register entry's
    text, under its kind, at one of its own sites. Every other value is refused
    on the same terms as before — not on stricter ones, which is what this
    sentence claimed until an audit checked it and found no input anywhere that
    the new codes refuse and the old one did not. Same refusals, better names,
    one new permission. That is what makes this a third state rather than a
    hole, and calling it a tightening would have been the flattering version.
    """
    found, unresolved, unknown_kinds = sites(root)
    findings = []
    for rel, line, kind, value, marked, ruled in found:
        if marked:
            continue
        if ruled is not None:
            if rel in ruled.sites:
                continue
            findings.append((RULED_STRING_OFF_SITE, rel, line, kind,
                             value, ruled))
            continue
        near = _ruled_near(value, kind)
        if near is not None:
            findings.append((RULED_STRING_ALTERED, rel, line, kind,
                             value, near))
            continue
        findings.append((UNMARKED_BRAND_STRING, rel, line, kind, value, None))
    return findings, unresolved, unknown_kinds


def check(root=APPS):
    """Refusal lines, or an empty list, plus the unresolved siblings."""
    findings, unresolved, unknown_kinds = scan(root)
    problems = []
    for code, rel, line, kind, value, entry in findings:
        shown = value if len(value) <= 90 else value[:87] + "..."
        if code == RULED_STRING_OFF_SITE:
            problems.append(
                f"{RULED_STRING_OFF_SITE}: {rel}:{line} {kind} -> {shown!r} — "
                f"{entry.ruling} is RULED and this is the owner's string, but "
                f"this file is not one of its registered sites "
                f"({', '.join(entry.sites)}). A ruling authorises a string "
                f"where the register says, not everywhere. Add the site to "
                f"RULED_STRINGS if the use is intended — which is a visible "
                f"edit to a register, and is the point.")
        elif code == RULED_STRING_ALTERED:
            problems.append(
                f"{RULED_STRING_ALTERED}: {rel}:{line} {kind} -> {shown!r} — "
                f"this is {entry.ruling}'s ruled string with its characters "
                f"changed. The owner typed {entry.text!r} and "
                f"{entry.authority} records it verbatim. Reproduce it exactly "
                f"or get a new ruling; an executor may not reshape a ruled "
                f"string. (That prohibition is the executor's inference, "
                f"flagged as his at {entry.authority} — the refusal is not: "
                f"this value carries no {MARKER} either.)")
        else:
            problems.append(
                f"{UNMARKED_BRAND_STRING}: {rel}:{line} {kind} -> {shown!r} — "
                f"reserved under §AE2(c) BRAND AND TASTE. This string was not "
                f"supplied by the owner and does not carry {MARKER}. Supply it "
                f"from the owner record, or mark it provisional per §AE3.")
    for rel, line, bad_kind, keys in unknown_kinds:
        problems.append(
            f"{UNKNOWN_BRAND_KIND}: {rel}:{line} carries text under "
            f"{keys} with kind {bad_kind!r}, which BRAND_KINDS does not name "
            f"— declare the tier in BRAND_KINDS once the owner has ruled it, "
            f"or rule the kind out by name. A brand tier nobody declared is "
            f"not silently skipped.")
    return problems, unresolved


def main():
    problems, unresolved = check()
    found, _, _ = sites()
    marked = sum(1 for row in found if row[4])
    # ON ITS OWN SITE, not merely matching a register row. This counted every
    # exact match, so a ruled string that had travelled somewhere it is not
    # authorised would be summarised on stdout as "1 ruled" in the same run
    # that refused it on stderr — the summary line contradicting the verdict
    # underneath it, which is the one place an operator looks first.
    ruled = sum(1 for row in found
                if row[5] is not None and row[0] in row[5].sites)
    print(f"brand kinds: {sorted(BRAND_KINDS)}  "
          f"sites: {len(found)} ({marked} already marked, {ruled} ruled)  "
          f"registered: {len(RULED_STRINGS)}  "
          f"unresolved siblings: {len(unresolved)}")
    for rel, line, kind, what in unresolved[:12]:
        print(f"  UNRESOLVED {rel}:{line} {kind} <- {what}")
    if len(unresolved) > 12:
        print(f"  ... and {len(unresolved) - 12} more")
    if problems:
        for p in problems:
            print(p, file=sys.stderr)
        print(f"BRAND_STRINGS_REFUSED: {len(problems)}", file=sys.stderr)
        return 1
    print("BRAND_STRINGS_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
