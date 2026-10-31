"""§R4 / §S1 — the fallback-class registration, and the structural rule
that stops this defect class returning.

RBV-4 added 24 unregistered fallback-class occurrences to a gate that was
ALREADY red, and nobody noticed precisely because it was already red: a
failing test cannot report a new failure. That is the recurring-defect
shape, so it gets an assertion rather than care:

* every key registered beyond the frozen pre-registration baseline must
  carry a per-occurrence justification naming the concrete downstream
  consequence of the default (§R4: no bulk registration, no wildcard);
* the gate must be GREEN, so the next commit that introduces an
  unjustified occurrence fails immediately and is attributable to itself;
* a genuinely new unregistered occurrence must still FAIL the gate
  (§R4b's negative control) — proven, not asserted.
"""
import json
from pathlib import Path

import pytest

from apps.pipeline.tests.test_palette_statistics import (
    SERVICES, _symbol_of, composed_gate)

REPO = Path(__file__).resolve().parents[3]
BASELINE = REPO / "docs" / "roadmap" / "palt_m6" / "enforcement_closure" / \
    "gate_baseline.json"


@pytest.fixture(scope="module")
def baseline():
    return json.loads(BASELINE.read_text())


def _keys(baseline):
    return [tuple(k) for k in baseline["keys"]]


def _unregistered():
    base = set(_keys(json.loads(BASELINE.read_text())))
    found = []
    for path in sorted(SERVICES.rglob("*.py")):
        src = path.read_text()
        for shape, line in composed_gate(src):
            key = (path.name, _symbol_of(src, line), shape)
            if key not in base:
                found.append(key)
    return found


class TestRegistrationsAreJustified:
    def test_the_pre_registration_count_is_frozen(self, baseline):
        """The original 813 carry the audit arc as their disposition
        trail. The boundary between them and anything registered since
        must stay visible, or 'registered' loses its meaning."""
        # his answer by option, 2026-09-26 ("Yes, 813 to 804"): the nine keys of the supplier-outreach code he had
        # removed (§BH69(1)) left the originals with it — 813 -> 804; the 22 registered since are untouched, and
        # the boundary between them stays where a reader can see it.
        assert baseline["n_pre_registration"] == 804
        assert len(_keys(baseline)) >= baseline["n_pre_registration"]

    def test_every_newly_registered_key_carries_a_justification(self,
                                                                baseline):
        registered = {tuple(r["key"]) for r in baseline["registrations"]}
        added = set(_keys(baseline)[baseline["n_pre_registration"]:])
        missing = sorted(added - registered)
        assert missing == [], (
            "keys added to the baseline without a registration entry — "
            f"bulk registration is forbidden (§R4b): {missing[:5]}")

    def test_no_justification_is_a_placeholder(self, baseline):
        for entry in baseline["registrations"]:
            key = "|".join(entry["key"])
            assert entry["verdict"] == "COMPETENT", key
            for field in ("justification", "downstream_effect"):
                text = entry.get(field, "")
                assert len(text) >= 40, f"{key}: {field} too thin"
                # a justification must say what HAPPENS, not that it is fine
                assert text.strip().lower() not in (
                    "safe", "this is fine", "ok", "n/a"), key

    def test_every_registration_is_actually_in_the_key_list(self, baseline):
        keys = set(_keys(baseline))
        for entry in baseline["registrations"]:
            assert tuple(entry["key"]) in keys, entry["key"]

    def test_no_duplicate_registrations(self, baseline):
        seen = [tuple(r["key"]) for r in baseline["registrations"]]
        assert len(seen) == len(set(seen))

    def test_registrations_record_who_and_when(self, baseline):
        for entry in baseline["registrations"]:
            assert entry["registered_on"]
            assert entry["registered_by"]
            assert entry["authority"].startswith("§R4")


DEFECTS = REPO / "docs" / "roadmap" / "palt_m6" / "enforcement_closure" / \
    "fallback_class_defects.json"


#: A disposition either ASSERTS a defect or records one that is over.
#: Both past-tense forms are kept forever under §R4(c) — an entry is never
#: deleted — so "is this still a refutation?" cannot be answered by the
#: entry's existence, only by its disposition.
ASSERTING = ("NOT_COMPETENT",)
SETTLED = ("RESOLVED", "OVERTURNED")


def _live_entries():
    """Entries that are still ASSERTING a defect.

    Filtered POSITIVELY, on the vocabulary the register actually uses,
    rather than by excluding RESOLVED — which was the shape here before,
    and which fails open: a disposition with a typo in it, or a new
    past-tense verdict nobody thought to exclude, was silently treated as
    a live refutation or as none at all depending on which way the test
    read. `test_the_disposition_vocabulary_is_closed` is what makes the
    positive filter safe.

    Module-level and shared DELIBERATELY. This began as a staticmethod on
    one test class and was called from another, where it raised
    AttributeError — a guard that cannot execute is not a guard, and it
    reported as a plain failure among others rather than as a broken
    instrument. More to the point, `_line_collisions` below had grown its
    OWN notion of "refuted" that counted settled entries, so the file held
    two disagreeing definitions of the word the whole §AP argument turns
    on. One definition, one place.
    """
    register = json.loads(DEFECTS.read_text())
    return [d for d in register["defects"]
            if d["disposition"].startswith(ASSERTING)]


class TestEveryOccurrenceIsDisposed:
    """Correction 2 — the structural fix, in the form the honest outcome
    actually permits.

    The gate is NOT green: 27 keys were judged not competent, overturned
    on refutation, or left unverified, and §R4c says those are recorded as
    defects and LEFT FAILING rather than registered to buy a green suite.
    So 'the gate is green' is the wrong assertion. The right one is that
    NOTHING IS UNACCOUNTED FOR: every unregistered occurrence must appear
    in the defect register with a disposition. A new occurrence introduced
    by a later commit is in neither list and fails here, attributable to
    the commit that added it — which is the property RBV-4's 24 silent
    additions lacked."""

    def test_every_unregistered_occurrence_has_a_recorded_disposition(self):
        register = json.loads(DEFECTS.read_text())
        disposed = {tuple(d["key"]) for d in register["defects"]}
        undisposed = sorted(set(_unregistered()) - disposed)
        assert undisposed == [], (
            f"{len(undisposed)} fallback-class occurrence(s) are neither "
            "registered nor recorded as defects. Judge each and either "
            "register it with a justification or record it as a defect "
            f"(see tools/gate_registration.py): {undisposed[:5]}")

    def test_the_defect_register_states_why_each_is_left_failing(self):
        register = json.loads(DEFECTS.read_text())
        assert "LEFT FAILING" in register["authority"]
        assert register["defects"]
        for defect in register["defects"]:
            assert defect["disposition"]
            body = defect.get("finding") or defect.get(
                "claimed_justification") or ""
            assert len(body) >= 40, defect["key"]

    def test_an_entry_still_asserting_a_defect_has_one_to_point_at(self):
        """A register that silently keeps entries for fixed defects
        overstates the debt, and — worse — leaves a disposition sitting
        ready to pre-approve the same shape if it returns. An entry that
        still SAYS a defect is being left failing must have something
        that is actually failing.

        Stated this way round on purpose. The predicate here is not "the
        occurrence is gone" — it is "the key is no longer among the
        UNREGISTERED occurrences", and those are different claims. A key
        that was registered still occurs; it just no longer fails the
        gate. So the honest settlement is not always RESOLVED (the
        occurrence was repaired away); it can also be OVERTURNED (the
        refuted occurrence was repaired and the one surviving under the
        same coarse key was re-judged competent). Demanding the word
        RESOLVED for that second case would force an entry to claim a
        repair that did not happen, to satisfy a test."""
        stale = sorted("|".join(d["key"]) for d in _live_entries()
                       if tuple(d["key"]) not in set(_unregistered()))
        assert stale == [], (
            f"{len(stale)} defect entr(ies) still assert NOT_COMPETENT, "
            "but their key is no longer an unregistered occurrence — so "
            "nothing is being left failing. Settle each with a stated "
            f"reason (§R4c: never delete): {stale}")

    def test_a_settled_entry_says_how_it_was_settled(self):
        """Widened from RESOLVED to every settled form, because settling
        is what removes an entry from `_live_entries` and therefore from
        the collision check — so the reason has to be on the record, or
        "overturned" becomes a one-word way to delete an entry that
        §R4(c) says may never be deleted.

        The retired judgment must still be legible too: an entry that
        forgets it once found a real defect cannot show that the judgment
        which found it was correct.

        TWO schemas satisfy that, and enumerating them is deliberate.
        Entries settled by the current machinery carry
        `disposition_before_resolution`. The two settled in sprint 4 under
        §U3 predate that field and record the retired verdict in the §T2a
        form instead — `votes`, two independent refuters, both `refuted`.
        Back-filling the newer field onto them would mean writing down a
        disposition string nobody can now read off anything, which is
        inventing a record of a past judgment to satisfy a test. The
        older record is not absence; it is a different record. What still
        fails here is an entry with NEITHER."""
        register = json.loads(DEFECTS.read_text())
        for d in register["defects"]:
            if not d["disposition"].startswith(SETTLED):
                continue
            key = "|".join(d["key"])
            assert len(d.get("resolution", "")) >= 60, key
            current = d.get("disposition_before_resolution", "") \
                .startswith(ASSERTING)
            sprint4 = bool(d.get("votes")) and all(
                v.get("refuted") for v in d["votes"])
            assert current or sprint4, (
                f"{key}: settled without recording what it said before — "
                "the register must still show the judgment it is "
                "retiring, either as disposition_before_resolution or as "
                "the §T2a votes that refuted it")

    def test_no_key_is_both_registered_and_a_LIVE_defect(self):
        """A key cannot be blessed and refuted AT THE SAME TIME.

        Compared against LIVE entries only. A key whose defect entry has
        been overturned on re-judgment — the occurrence that earned the
        NOT_COMPETENT verdict was repaired away, and the occurrence that
        survives under the same coarse key is a different expression
        judged competent on a fresh refutation — is legitimately in both
        files, and §R4(c) forbids deleting the entry that recorded the
        original defect. What is forbidden is a live refutation and a
        registration standing together, which is the §AP contradiction one
        grain up from the line."""
        base = json.loads(BASELINE.read_text())
        registered = {tuple(r["key"]) for r in base["registrations"]}
        live = {tuple(d["key"]) for d in _live_entries()}
        assert not (registered & live), sorted(registered & live)

    def test_a_genuinely_new_occurrence_would_still_be_caught(self):
        """§R4b NEGATIVE CONTROL, proven rather than asserted: the
        detector fires on a fresh fallback shape, and a key absent from
        the baseline is reported as unregistered."""
        src = ("def brand_new_helper(d):\n"
               "    return d.get('missing', 0)\n")
        hits = composed_gate(src)
        assert hits, "the detector no longer fires on a fallback shape"

        shape = sorted(hits)[0][0]
        base = set(_keys(json.loads(BASELINE.read_text())))
        invented = ("a_module_that_does_not_exist.py", "brand_new_helper",
                    shape)
        assert invented not in base, (
            "the baseline must not contain an invented key — if this "
            "fails the baseline has been broadened with a wildcard")

    def test_registration_did_not_weaken_the_detector(self):
        """The gate must still fire on the corpus it was built from —
        registering occurrences must not have touched the detector."""
        from apps.pipeline.tests.test_palette_statistics import (
            GuardCorpusTests)
        missed = [name for name, src in GuardCorpusTests.CORPUS
                  if not composed_gate(src)]
        assert missed == [], f"the enforcing gate now misses: {missed}"


class TestTheReasonIsGuardedAndNotOnlyTheKey:
    """§AL3(c) — the register was keyed more coarsely than the reasons it
    carries, so a reason could stop being true without anything noticing.

    `test_a_defect_entry_that_no_longer_occurs_is_marked_resolved` above
    is the guard that existed, and it is GREEN. It asks whether the KEY
    still occurs. A key is (file, symbol, shape) and holds every
    occurrence of that shape in that symbol — up to fifteen of them — so
    it survives as long as ANY occurrence survives, including the weak
    ones the entry's own text exculpates.

    Every finding in this register is written `JUDGED BY ITS WEAKEST
    OCCURRENCE, <line>`. That is the right method — a key is only as
    competent as its worst member — and it is exactly what the key-level
    guard cannot see. Measured 2026-08-20: five entries named a weakest
    occurrence that `cd7fa9f` REPAIRED in the same commit that wrote the
    entry. The key survived through its weaker siblings, the guard stayed
    green, and the reason had been false for three days.

    So the guard moves to the reason. Each live entry names the SOURCE
    TEXT of its weakest occurrence, not its line number: line numbers
    drift on every edit above them and would make this a churn generator,
    while the expression itself is stable and is the thing the finding is
    actually about. When that text is gone, the repair happened and the
    entry must be re-judged from what survives (§AL3(a)) — registered if
    the survivors are competent, re-written with a new weakest occurrence
    if they are not.
    """

    _live_entries = staticmethod(_live_entries)

    def test_the_disposition_vocabulary_is_closed(self):
        """The positive filter above is only safe while every disposition
        is recognisable. A verdict spelled in a way neither branch knows
        would be counted as history by the filter and as nothing by the
        reader."""
        known = ("NOT_COMPETENT", "RESOLVED", "OVERTURNED")
        register = json.loads(DEFECTS.read_text())
        unknown = sorted({d["disposition"] for d in register["defects"]
                          if not d["disposition"].startswith(known)})
        assert unknown == [], (
            "these dispositions are outside the register's vocabulary, so "
            "no guard here knows whether they assert a defect or record "
            f"one that is over: {unknown}")

    def test_every_live_defect_entry_names_its_weakest_occurrence(self):
        """Fail-closed on vocabulary drift: an entry added without the
        field is not silently exempt from the guard below it. Written
        this way round because the failure mode being closed IS a check
        that quietly covers less than it appears to."""
        missing = sorted("|".join(d["key"]) for d in self._live_entries()
                         if not (d.get("weakest_occurrence") or {}).get(
                             "source"))
        assert missing == [], (
            f"{len(missing)} live defect entr(ies) name no weakest "
            "occurrence, so §AL3(c)'s staleness guard cannot see them. "
            "Add weakest_occurrence.source — the exact expression the "
            f"finding is judged by: {missing}")

    def test_a_named_weakest_occurrence_still_exists_in_its_file(self):
        """§AL3(a). The entry may not carry a reason that has stopped
        being true."""
        stale = []
        for entry in self._live_entries():
            filename = entry["key"][0]
            source = entry["weakest_occurrence"]["source"]
            matches = [p for p in SERVICES.rglob(filename)]
            assert matches, f"{filename} named by a defect entry is gone"
            if not any(source in p.read_text() for p in matches):
                stale.append((("|".join(entry["key"])), source))
        assert stale == [], (
            f"{len(stale)} defect entr(ies) are judged by a weakest "
            "occurrence that NO LONGER EXISTS — the repair landed and "
            "the reason did not follow it. Re-judge each key from its "
            "surviving occurrences under §AL3(a): either register it "
            "with a justification, or rewrite the entry naming its new "
            f"weakest occurrence. {stale}")

    def test_the_named_occurrence_is_an_expression_not_a_line_number(self):
        """A source snippet short enough to match anything is not a
        citation. Six characters would match `.get(` across the whole
        tree and the guard above would never fire again."""
        for entry in self._live_entries():
            source = entry["weakest_occurrence"]["source"]
            key = "|".join(entry["key"])
            assert len(source) >= 12, f"{key}: snippet too short to cite"
            assert not source.strip().isdigit(), (
                f"{key}: a line number is not the occurrence — line "
                "numbers drift and the expression does not")

    @staticmethod
    def _lines_of(source, text):
        """Every 1-based line where `source` starts inside `text`."""
        head = source.splitlines()[0]
        rows = text.splitlines()
        return [i + 1 for i, row in enumerate(rows)
                if head in row and source in "\n".join(rows[i:i + 4])]

    def test_the_named_occurrence_lies_inside_the_symbol_the_key_names(self):
        """LENGTH IS NOT SPECIFICITY, and the guard above measures
        length. Found by hand while populating the field, not by
        reasoning about it: the honest citation for
        validate_ledger_row|except_swallow is thirty characters long,
        passes every check above, and STILL matches a completely
        different function — `except (TypeError, ValueError)` survives
        at line 1078 in a symbol the entry is not about, while the site
        the finding is judged by became `except Exception` four lines
        of comment ago. A citation that can be satisfied from another
        function is a citation that reports on the file, not the key.

        Only entries whose source is still present are checked; the
        ones that are simply gone belong to the staleness guard above
        and must not be counted twice."""
        misplaced = []
        for entry in self._live_entries():
            filename, symbol = entry["key"][0], entry["key"][1]
            source = entry["weakest_occurrence"]["source"]
            for path in SERVICES.rglob(filename):
                text = path.read_text()
                hits = self._lines_of(source, text)
                if not hits:
                    continue
                if not any(_symbol_of(text, n) == symbol for n in hits):
                    misplaced.append((
                        "|".join(entry["key"]),
                        sorted({_symbol_of(text, n) for n in hits})))
        assert misplaced == [], (
            f"{len(misplaced)} defect entr(ies) cite a weakest "
            "occurrence that exists in the named FILE but not in the "
            "named SYMBOL, so the staleness guard is being satisfied "
            "by an unrelated function and would not notice this key's "
            f"own site being repaired: {misplaced}")

    def test_the_symbol_guard_catches_a_citation_that_moved_house(self):
        """§AA on the guard immediately above, demonstrated against the
        REAL case that produced it rather than an invented one.

        `except (TypeError, ValueError)` is what
        validate_ledger_row|except_swallow was judged by. It is still
        in the file. The staleness guard would therefore pass it — and
        be wrong, because the cost-parse handler it names is now
        `except Exception`. This asserts both halves: present in the
        file, absent from the symbol."""
        path = SERVICES / "rbv4_claude_review.py"
        text = path.read_text()
        loose = "except (TypeError, ValueError)"
        hits = self._lines_of(loose, text)
        assert hits, (
            "the loose citation is gone from the file entirely, so it "
            "no longer demonstrates the difference between the two "
            "guards — pick another that survives elsewhere")
        symbols = {_symbol_of(text, n) for n in hits}
        assert "validate_ledger_row" not in symbols, (
            "the loose citation is back inside validate_ledger_row, so "
            f"the file no longer exhibits the hole: {sorted(symbols)}")

    def test_the_guard_fires_on_a_reason_that_has_gone(self):
        """§AA — demonstrated, not asserted. The stale case is
        constructed here because the real one is being repaired in the
        same work item, and a guard whose only evidence is a state the
        commit removes has no evidence at the moment anyone reads it."""
        entry = {"key": ["rbv5_comparison_gate.py", "compare", "regex"],
                 "disposition": "NOT_COMPETENT",
                 "weakest_occurrence": {
                     "source": 'budget.get("authorized_by_nobody", "")'}}
        filename = entry["key"][0]
        source = entry["weakest_occurrence"]["source"]
        present = any(source in p.read_text()
                      for p in SERVICES.rglob(filename))
        assert not present, (
            "the constructed stale snippet was actually found — pick "
            "one that is genuinely absent or this proves nothing")


# --------------------------------------------------------------------------
# §AP — the two registers, compared at the grain of a LINE.
# --------------------------------------------------------------------------

def _resolve_named_files(names):
    """``(resolved, unresolvable)`` for basenames as the registers spell
    them.

    Both register files key on a BARE FILENAME. Resolving that against the
    top level of ``services/`` alone silently skipped nine files that live
    in ``services/blender_scripts/`` — a fail-open in the check itself,
    which is precisely the defect class §AP is about, and it was in the
    first draft of this very function. So resolution is recursive, and a
    basename that resolves to zero files or to more than one is RETURNED
    as unresolvable rather than skipped. A file the check cannot find is
    a file the check is not checking, and it has to say so.
    """
    index = {}
    for path in SERVICES.rglob("*.py"):
        index.setdefault(path.name, []).append(path)
    resolved, unresolvable = {}, {}
    for name in names:
        hits = index.get(name, [])
        if len(hits) == 1:
            resolved[name] = hits[0]
        else:
            unresolvable[name] = [str(h.relative_to(SERVICES)) for h in hits]
    return resolved, unresolvable


def _line_collisions(blessed=None, refuted=None, sources=None):
    """Every ``(file, function, line)`` that is blessed under one detector
    shape and refuted under another.

    §AP5 binds this: lines are resolved from the CURRENT source through
    the CURRENT detector, NEVER from any line number stored in either
    record. The stored numbers are prose — they were written on different
    days against code that has since moved, and comparing them is the
    staleness §AL3(a) already found, not a check for it.
    """
    if blessed is None:
        blessed = {tuple(k) for k in json.loads(BASELINE.read_text())["keys"]}
    if refuted is None:
        # LIVE entries only, via the one shared definition. A settled
        # entry — resolved, or overturned on re-judgment — is history,
        # not a verdict, and §R4(c) keeps it on file forever. Counting it
        # as a refutation would make "overturn" mean "contradict yourself
        # permanently", so no re-judgment could ever land and §R4(c)
        # would have quietly outlawed changing one's mind.
        #
        # This is the narrowing §AL4 warns about, so it is bounded in
        # writing: it may NOT be used to settle an entry whose occurrence
        # still stands unjudged. An entry leaves this set only by
        # carrying a >=60-char resolution
        # (`test_a_resolved_entry_says_how_it_was_resolved`) under a
        # disposition inside a closed vocabulary
        # (`test_the_disposition_vocabulary_is_closed`), and the planted
        # -disagreement control below still fires on a live one.
        refuted = {tuple(d["key"]) for d in _live_entries()}
    if sources is None:
        named = {k[0] for k in blessed} | {k[0] for k in refuted}
        resolved, _ = _resolve_named_files(named)
        sources = {name: path.read_text() for name, path in resolved.items()}

    out = []
    for name, src in sorted(sources.items()):
        per_line = {}
        for shape, line in composed_gate(src):
            per_line.setdefault(line, set()).add(shape)
        for line, shapes in sorted(per_line.items()):
            func = _symbol_of(src, line)
            b = sorted(s for s in shapes if (name, func, s) in blessed)
            r = sorted(s for s in shapes if (name, func, s) in refuted)
            if b and r:
                out.append({"file": name, "function": func, "line": line,
                            "blessed_under": b, "refuted_under": r,
                            "source": src.splitlines()[line - 1].strip()})
    return out


class TestTheTwoRegistersCannotDisagreeAboutALine:
    """§AP — a registration key names ``(file, function, detector_shape)``,
    and ONE PHYSICAL LINE CAN MATCH MORE THAN ONE SHAPE. So an occurrence
    can carry a COMPETENT registration in ``gate_baseline.json`` and a
    NOT_COMPETENT refutation in ``fallback_class_defects.json`` at the same
    time, about the same line, and the two records never meet — because
    only the first is read by the gate and the key grain is too coarse to
    see the disagreement.

    ``test_no_key_is_both_registered_and_a_defect`` above already compares
    the two registers. It compares them AT THE KEY GRAIN, and passes, and
    passed all through the three days the h2 fail-open sat refuted in one
    file and blessed in the other. That test is not wrong; it is answering
    a different question. This class asks the question that catches it.

    §AP3(c) is why the direction matters: a STALE DEFECT ENTRY FAILS SAFE
    and leaves a gate red that should be green — visible, annoying,
    harmless. A STALE REGISTRATION FAILS OPEN and leaves a defect blessed.
    """

    def test_no_line_is_both_blessed_and_refuted(self):
        collisions = _line_collisions()
        assert collisions == [], (
            f"{len(collisions)} line(s) carry a COMPETENT registration "
            "under one detector shape and a NOT_COMPETENT refutation under "
            "another. Re-judge the registration against the code it names "
            "— do not delete the defect entry (§R4c). "
            + "; ".join("%s::%s:%d blessed=%s refuted=%s | %s"
                        % (c["file"], c["function"], c["line"],
                           c["blessed_under"], c["refuted_under"],
                           c["source"][:70])
                        for c in collisions))

    def test_an_overturned_key_would_still_collide_if_it_were_live(self):
        """§AA, aimed at the narrowing itself rather than at the check.

        `_line_collisions` counts LIVE refutations only. That narrowing is
        load-bearing — it is what let the two re-judged keys be registered
        while §R4(c) keeps their defect entries on file forever — and a
        narrowing that silently stopped detecting anything would look
        exactly like this one from the outside: green suite, no collisions
        reported.

        So the claim is made falsifiable. Feed the SAME real sources and
        the SAME real baseline, with the overturned keys put back in the
        refuted set, and the collision must reappear. If this test ever
        goes green with an empty result, the liveness filter is no longer
        the reason `test_no_line_is_both_blessed_and_refuted` passes, and
        the two-key registration is resting on a check that has stopped
        looking."""
        overturned = {tuple(d["key"])
                      for d in json.loads(DEFECTS.read_text())["defects"]
                      if d["disposition"].startswith("OVERTURNED")}
        assert overturned, (
            "no overturned entries — if the re-judged keys were settled "
            "some other way this control is measuring nothing and must "
            "be rewritten against whatever replaced them")
        would_collide = _line_collisions(refuted=overturned)
        assert {c["file"] for c in would_collide} == {k[0] for k in overturned}, (
            "the overturned keys no longer collide even when treated as "
            "live, so liveness is NOT what is keeping the register "
            "consistent and the real reason is unexamined: "
            f"{would_collide}")

    def test_every_file_a_register_names_resolves_to_exactly_one_file(self):
        """The check's own fail-open guard. A basename that resolves to
        nothing, or ambiguously to two files, is a file this class is
        silently not checking."""
        named = {k[0] for k in json.loads(BASELINE.read_text())["keys"]}
        named |= {tuple(d["key"])[0]
                  for d in json.loads(DEFECTS.read_text())["defects"]}
        _, unresolvable = _resolve_named_files(named)
        assert unresolvable == {}, (
            "these basenames are named by a register but do not resolve to "
            f"exactly one file under services/: {unresolvable}")

    def test_the_check_catches_a_planted_disagreement(self):
        """§AA NEGATIVE CONTROL — a guard nobody has seen fire is not
        evidence. One synthetic line matching two shapes, blessed under
        one and refuted under the other."""
        src = ('def planted(cfg):\n'
               '    return cfg.get("k", "")\n')
        found = _line_collisions(
            blessed={("planted.py", "planted", "lookup_default")},
            refuted={("planted.py", "planted", "regex")},
            sources={"planted.py": src})
        assert len(found) == 1, found
        assert found[0]["line"] == 2
        assert found[0]["blessed_under"] == ["lookup_default"]
        assert found[0]["refuted_under"] == ["regex"]

    def test_two_verdicts_about_one_function_and_no_shared_line_is_legal(self):
        """§AP4(3) THE CONTROL, and the reason this is a property of the
        keying scheme rather than a blanket ban.

        ``rbv3::_compose_sheet`` holds an ``ifexp`` registration and three
        refuted shapes, over entirely different lines. That is two verdicts
        about one function with nothing in common, and it is not a
        contradiction. If this class flagged it, it would be measuring
        coarse keys rather than disagreement.

        ``rbv4::load_review_package`` is here for a stronger reason: at
        cd7fa9f it WAS a collision, on lines 274 and 299, and the repair
        this sprint moved it into this group. A control that used to be a
        positive is the best evidence the check responds to the fix rather
        than to the file's identity."""
        blessed = {tuple(k) for k in json.loads(BASELINE.read_text())["keys"]}
        refuted = {tuple(d["key"])
                   for d in json.loads(DEFECTS.read_text())["defects"]}
        collided = {(c["file"], c["function"]) for c in _line_collisions()}
        for name, func in (("rbv3_review_package.py", "_compose_sheet"),
                           ("rbv4_claude_review.py", "load_review_package")):
            has_b = any(k[0] == name and k[1] == func for k in blessed)
            has_r = any(k[0] == name and k[1] == func for k in refuted)
            assert has_b and has_r, (
                f"{name}::{func} no longer holds both kinds of verdict, so "
                "it is not a control any more — pick another or drop it")
            assert (name, func) not in collided, (
                f"{name}::{func} was the control and now collides")
