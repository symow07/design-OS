"""§AV3 — the RUNTIME half of the §AE2(c) brand-string remedy.

WHY A SECOND INSTRUMENT AT ALL. §AU5's four steps read as one guard. They are
two. Steps 1–3 ask a question about SOURCE — does a placeholder string appear,
unmarked, in a ``.py`` file — and ``tools/brand_strings.py`` answers it. §AU8(e)
asks something else entirely: *"no emission carrying a ⟪PROVISIONAL⟫ descriptor
reaches print, a proof, or any owner-facing artefact."* An emission is a runtime
object. The descriptor inside it may have come from a database row, a fixture,
or the owner-supplied C9 string that does not exist yet — **none of which are in
any source file.** A static scanner is structurally incapable of refusing those,
and if the static half alone had been called the AU5 remedy, the result would be
a guard reporting green while a provisional string went to print. That is §AA,
freshly manufactured, in the tranche whose subject is §AA.

WHAT IT KEYS ON, AND WHY THAT IS NOT §AD0(b). This walks the composed document
and looks for ``MARKER`` **in the text a node will actually print**. It does not
recognise a brand string by the shape of the code that produced it, by a node
name pattern, or by which composer branch ran. §AD0(b) — an instrument that
recognises a thing by the shape of its implementation reports on style — is the
trap here, and ``container_motif_fidelity.py:255`` records the repository
already paying for it once: a ``startswith("product-name")`` test that saw
``product-name-hero-1`` and missed ``flat-product-name-hero-1``. Node names are
used ONLY to label a finding, never to decide one, and a name this module does
not recognise is reported under its own node name rather than guessed at or
dropped.

WHY IT SCANS EVERY TEXT RUN AND NOT JUST THE FRONT TIERS. Narrowing to the
descriptor tier would re-import the static half's blind spot at runtime. The
marker means exactly one thing — this string was not supplied by the owner — so
any live text carrying it is a provisional string heading for print, wherever it
sits. Scanning everything is simultaneously simpler and stricter, and it cannot
produce a false finding: no legitimately owner-supplied copy carries a token
whose entire purpose is to say the owner did not supply it.

WHAT IT CANNOT DO, STATED HERE RATHER THAN DISCOVERED LATER (§Y2(c)).
* A marker baked into a RASTER before composition is pixels by the time this
  runs, and no string scan will see it. The native path emits live text (2C-2E
  ``direct_print`` exists precisely so a rectangular raster label is a fidelity
  failure), so this seam is narrow — but it is a seam, not a covered case.
* This judges a DOCUMENT. Anything reaching an owner outside the document —
  a filename, a dashboard string, an email — is out of scope here and is
  §AU5(4)'s separate obligation.
* ``doc.metadata`` and ``doc.title`` are not scanned. They are not printed
  copy, and widening to them would start this guard down the road
  ``reserved_copy``'s own comment describes, where a first draft produced
  "139 findings of which about a dozen were copy".

FAIL-CLOSED IMPORT, DELIBERATELY WITHOUT A FALLBACK. ``MARKER`` is imported from
the one place §AE3's token is spelled. There is no ``try/except`` around it and
no hard-coded literal behind it: a second spelling is the §AK3 defect this
repository has already paid for once, and a guard that silently degrades to a
default when its vocabulary is missing is worse than one that refuses to load.
If ``tools`` is ever unavailable to production, this module fails to import,
``container_production_readiness`` fails with it, and Gate-2 cannot run —
which is the correct direction to fail. Measured under full ``django.setup()``
before being relied on.

Pure: no Django, no ORM, no network.
"""
from __future__ import annotations

from tools.reserved_copy import PROVISIONAL_TOKEN

SCHEMA = "brand_string_runtime/1.0"

#: §AE3's marker, imported rather than re-spelled — see the module docstring.
MARKER = PROVISIONAL_TOKEN

#: The blocking readiness code, emitted as ``BRAND_STRING_PROVISIONAL: <tier>``.
#: BLOCKING and never advisory. A provisional string is by definition one the
#: owner has not supplied, and §AE2(c) reserves that decision to the owner; a
#: warning would let production authority be granted over invented brand copy,
#: which is the whole thing the clause forbids.
BRAND_STRING_PROVISIONAL = "BRAND_STRING_PROVISIONAL"

#: §AU5(4)/§AU8(e). Raised when a document carrying provisional brand copy
#: reaches a path that would produce an OWNER-FACING ARTEFACT — the editable
#: .ai, its PNG proof, or the native handoff package.
#:
#: Distinct from the readiness code above, and the distinction is the point.
#: ``BRAND_STRING_PROVISIONAL`` DESCRIBES a document; this REFUSES to hand one
#: over. §AV3 emitted the description and nothing consumed it as a refusal, so
#: the .ai was written 72 lines before the description was even computed. A
#: code that only ever appears in a report is a code that stops nothing.
BRAND_STRING_ARTEFACT_WITHHELD = "BRAND_STRING_ARTEFACT_WITHHELD"

#: The two node names the TIERED branch of
#: ``compose_container._native_decoration`` gives emitted tiers
#: (``compose_container.py:244``). These LABEL findings; they never decide one.
#: See the docstring on why that distinction is the difference between this and
#: an §AD0(b) instrument.
#:
#: §AV5 correction, by measurement (§AD0(a)). This previously read "the two node
#: names ``_native_decoration`` gives emitted tiers", which is not what the
#: composer does. Composing a real container and reading back the marked runs
#: returned ``undeclared_node:product-name-0`` and ``undeclared_node:sheet-
#: title`` — neither spelling covered. There are THREE live spellings, not two:
#:
#:   * ``product-name-hero`` / ``front-<kind>`` — line 244, the TIERED branch,
#:     the one §AU5(3) has not yet supplied. Covered.
#:   * ``product-name-<i>`` — line 315, the ``name_lines`` FALLBACK branch,
#:     inside the same function. This is the branch that runs TODAY.
#:   * ``sheet-title`` — line 550, outside the function entirely.
#:
#: WHY "THE TIERED BRANCH" AND NOT THE KEYWORD, WHICH IS A §Y2 QUESTION AND NOT
#: A STYLE ONE. My first version of this comment named that branch by its dict
#: key. Doing so put the keyword into a PRODUCTION module and turned
#: ``TestTheRecordSaysWhichRuleIsActuallyDrawn`` red — the §Y2 tripwire that
#: asserts, by exact set equality, which files mention it. I had three options
#: and two of them were bad:
#:
#:   * DELETE the sentence — that is "shaping the record to suit the
#:     instrument", which the tripwire's own docstring names and forbids.
#:   * ADD this file to the allow-list — worse, and this is the reason for the
#:     choice. Every one of the five permitted entries is the composer itself,
#:     its rationale module, or a test. This module is neither: it is
#:     production. A production file on a detector's allow-list is a HOLE, because
#:     a later real supply inside it would leave the grep green. That is
#:     weakening a detector to buy green, which §AL4/§Y2 forbid outright, and
#:     the tripwire's docstring separately warns that extending the list "must
#:     not become a habit" — the fifth entry was already flagged as the weakest.
#:   * NAME THE BRANCH ANOTHER WAY — no fact is lost. The branch is identified
#:     here by function and by LINE NUMBER, which is strictly more precise than
#:     the key was, and the tripwire stays armed at five files for §AU5(3),
#:     which is the event it exists to catch.
#:
#: This is NOT the double-star-dict evasion that §Y2 forbids (spelled out in
#: ``test_container_line_weight.py``, which is on the allow-list and can carry
#: it). That one respells a live CALL so the grep cannot see a supply that is
#: really happening. Nothing here supplies anything; this is a comment naming a
#: branch it does not call, and the module neither imports nor invokes the
#: composer.
#:
#: The guard still BLOCKED both uncovered spellings, because ``_tier_of`` is
#: total and an unrecognised name falls to ``UNDECLARED_TIER_PREFIX`` rather
#: than being dropped — the halting discipline working as designed. So this is a
#: LABEL-QUALITY limitation, not a leak, and it is left standing rather than
#: patched: widening the matcher to chase spellings is the ``startswith
#: ("product-name")`` move that produced the ``flat-product-name-hero-1`` defect
#: this module's docstring already cites. A tier nobody declared still blocks,
#: and it reports under its own name so the reader can see which one it was.
HERO_NODE_NAME = "product-name-hero"
FRONT_NODE_PREFIX = "front-"


class BrandStringRefusal(ValueError):
    """§AW1 — the refusal ``BRAND_STRING_ARTEFACT_WITHHELD`` names, raised at
    the point of WRITING rather than reported somewhere near it.

    A ``ValueError`` SUBCLASS deliberately, and the choice is load-bearing.
    ``targets/container/__init__.py:1521`` already raises a bare ``ValueError``
    carrying this code, so every handler that exists today catches this one too.
    A fresh exception hierarchy would have made the new closure invisible to
    handlers already written against the old one, and escaping past an existing
    ``except ValueError`` is a CRASH, not a refusal. §AV5's own comment records
    this repository paying for that distinction once: a closure that "failed
    CLOSED, but it failed closed by CRASHING, on the clean path too".

    Carries the report, not just a message. A refusal that cannot say WHICH
    string stopped it is one somebody eventually switches off rather than
    diagnoses — the same reasoning ``brand_string_report`` gives for keeping
    the runs alongside the codes.
    """

    def __init__(self, report: dict, *, artefact: str):
        self.code = BRAND_STRING_ARTEFACT_WITHHELD
        self.report = report
        self.artefact = artefact
        super().__init__(
            f"{BRAND_STRING_ARTEFACT_WITHHELD}: refusing to write {artefact} — "
            "the composed document carries provisional brand copy: "
            + "; ".join(report["codes"]))

#: A marked run whose node name matches neither spelling is reported under this
#: prefix plus the name itself. Not dropped and not guessed — the same halting
#: discipline as ``BRAND_KINDS`` / ``UNKNOWN_ROLE`` /
#: ``UNDECLARED_READINESS_SECTION``: a tier nobody declared still blocks.
UNDECLARED_TIER_PREFIX = "undeclared_node"


def _tier_of(name: str) -> str:
    """The tier label for an emitted node name.

    Deliberately total: every name gets a label, because a finding this
    function cannot classify must still be a finding. The hero is matched by
    EQUALITY rather than prefix, which is the direct lesson of the
    ``flat-product-name-hero-1`` defect — a prefix test on this name has
    already been wrong once in this repository.
    """
    name = name or ""
    if name == HERO_NODE_NAME:
        return "product_name"
    if name.startswith(FRONT_NODE_PREFIX):
        return name[len(FRONT_NODE_PREFIX):] or f"{UNDECLARED_TIER_PREFIX}:{name}"
    return f"{UNDECLARED_TIER_PREFIX}:{name or '<unnamed>'}"


def provisional_runs(doc) -> list[dict]:
    """Every live text run in ``doc`` whose printed text carries ``MARKER``.

    Returns a list of ``{"node", "tier", "text"}``, ordered by the document's
    own depth-first walk so a report reads in emission order rather than in
    whatever order a set happened to iterate.
    """
    out = []
    for node, _parent in doc.walk():
        if getattr(node, "type", None) != "text":
            continue
        text = getattr(node, "text", "") or ""
        if MARKER in text:
            name = getattr(node, "name", "") or ""
            out.append({"node": name, "tier": _tier_of(name), "text": text})
    return out


def leave_out_provisional(doc) -> list[dict]:
    """[His goal of 2026-10-13 (OWNER_BLOCKER_CLEARANCE.md), (1): "NO check ever stops a design."] Every live text run
    carrying ``MARKER`` taken out of ``doc`` — the words the owner did not supply never drawn (§AE2(c) unloosened), the
    design drawn on without them — and returned as ``provisional_runs`` lists them, for the design to say beside
    Approve."""
    runs, gone = [], []
    for node, parent in doc.walk():
        if getattr(node, "type", None) == "text" and MARKER in (getattr(node, "text", "") or "") and parent is not None:
            name = getattr(node, "name", "") or ""
            runs.append({"node": name, "tier": _tier_of(name), "text": node.text})
            gone.append((node, parent))
    for node, parent in gone:
        parent.children.remove(node)
    return runs


def readiness_codes(doc) -> list[str]:
    """The blocking readiness codes for ``doc``, or an empty list.

    Deduplicated and sorted: two provisional tiers of the same kind are one
    fact about the design, and a readiness report that repeats a code once per
    text run is a report nobody finishes reading. The RUNS are what carry the
    detail, and ``brand_string_report`` keeps them.
    """
    return sorted({f"{BRAND_STRING_PROVISIONAL}: {run['tier']}"
                   for run in provisional_runs(doc)})


def brand_string_report(doc) -> dict:
    """The persisted §AV3 record: the codes plus the runs that produced them.

    Kept as a record and not just a code list because a blocking code that
    cannot tell you WHICH string blocked is a code somebody will eventually
    switch off rather than diagnose.
    """
    runs = provisional_runs(doc)
    return {
        "schema_version": SCHEMA,
        "marker": MARKER,
        "provisional_runs": runs,
        "codes": sorted({f"{BRAND_STRING_PROVISIONAL}: {r['tier']}"
                         for r in runs}),
        "clean": not runs,
    }


def refuse_if_provisional(doc, *, artefact: str) -> dict:
    """§AW1 — refuse to produce ``artefact`` from ``doc`` when it carries
    provisional brand copy. Returns the report when the document is clean.

    THE ONE PLACE A CALLER HAS TO REMEMBER NOTHING. §AV5 closed three call sites
    by hand and declared the paths covered; an audit then found a fourth,
    unguarded, in a different app — ``dielines/services/export_service.py``,
    which composes with ``product_name=`` and writes both an editable .ai and a
    PNG proof, and where ``grep -rn brand_string`` returned nothing. A list of
    call sites is a thing that must stay correct forever and silently stops
    being correct the moment somebody adds a writer. §AW1 rules the closure down
    to the WRITER instead, because every artefact passes through one.

    Returns the report rather than None so that a caller which already needs the
    record does not compute it twice, and so this is a drop-in replacement for
    the ``brand_string_report(doc)`` line the three existing gates already run.

    NO OPT-OUT PARAMETER, and its absence is the design. A ``force=`` or
    ``allow_provisional=`` flag would be the hole: the first caller that needed
    a marked document "just for diagnosis" would take it, and the closure would
    be advisory from then on. The container target already distinguishes the two
    cases correctly without one — a GEOMETRY-blocked .ai is kept as diagnostic
    evidence, while provisional brand copy is withheld outright, because "its
    presence in a downloadable .ai IS the §AE2(c) violation"
    (``targets/container/__init__.py:1360``). If a future path genuinely needs
    an exception, that is a RULING, not a keyword argument.
    """
    report = brand_string_report(doc)
    if not report["clean"]:
        raise BrandStringRefusal(report, artefact=artefact)
    return report


__all__ = ["SCHEMA", "MARKER", "BRAND_STRING_PROVISIONAL",
           "BRAND_STRING_ARTEFACT_WITHHELD", "BrandStringRefusal",
           "HERO_NODE_NAME", "FRONT_NODE_PREFIX", "UNDECLARED_TIER_PREFIX",
           "provisional_runs", "readiness_codes", "brand_string_report",
           "refuse_if_provisional"]
