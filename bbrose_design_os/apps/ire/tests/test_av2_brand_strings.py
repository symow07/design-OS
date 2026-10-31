"""§AV2 — the §AE2(c) brand-string guard, and the refusal it produced on its
first run against the real tree.

WHAT MADE THIS FILE NECESSARY. §AU5 named a promise `tools/reserved_copy.py`
makes in its own docstring — that the product name and the front descriptor are
brand (§AE2(c)), "a different reservation with a different remedy" — and
observed that the remedy had never been built. So "if the executor feeds a
placeholder descriptor into ``hierarchy_lines`` today, no instrument in the
repository will refuse it."

Measured on the guard's first run, that was worse than §AU5 supposed: a
placeholder descriptor was **already there**. ``"Facial Oil"`` sat under
``kind: "descriptor"``, unmarked, in ``test_wit_unit_analysis.py`` — and on the
day it was found ``git grep -c "Facial Oil" HEAD`` returned ``1``, in that one
file. One use is what a fabricated string looks like: no owner supplied it,
nothing cited it, and manifest row C9 was still open for the string it stood
in for. Contrast the product name at ~97 sites. It was not planted for this
test. It was found.

THAT SENTENCE WAS IN THE PRESENT TENSE AND IS NOW IN THE PAST, because §BB7(a)
retired the string and the count it states is no longer the count. It said the
grep "returns ``1``, in that one file". Measured after this commit: the file it
points at contains the string ZERO times, and this file contains it many —
every one of them prose about a dead placeholder. Keeping a present-tense
measurement of a superseded state is how a record becomes wrong without anyone
editing it. The live assertions are ``test_the_fabricated_descriptor_has_no_
use_site_left`` and its two controls, and the byte count is not among them.

That "one" became a count of USE SITES rather than byte matches, because the
first version of the assertion was falsified by this very docstring. The
reasoning is kept rather than tidied away, in the test that now measures the
same quantity at zero.

WHY A SIBLING AND NOT A WIDER ``reserved_copy`` — pinned below as a measurement
rather than left as a design opinion, because it is the whole justification for
a second file. ``reserved_copy._pairs`` gates on ``RESERVED_HEADINGS`` and
returns before its ``UNKNOWN_ROLE`` net; the descriptor dict names no heading,
so it is invisible to it — marked or unmarked, violation or not.

§AA — THE CENSUS, COUNTED BY CLASS AND WITH ITS PREDICATE STATED. The previous
version of this paragraph read "of the fifteen tests below, six build a tree
and watch this guard refuse or stay silent, two are controls …, four assert
facts about the real tree, and three pin the measurement that made this a
sibling". It is quoted rather than deleted (§AZ0(u)) because it went wrong in
TWO ways at once and only one of them was the arithmetic.

The arithmetic: §BB7(a) added tests and the number stayed at fifteen. HOW MANY
it added is deliberately not stated. The first draft of this sentence said
"nine" and the measured figure was ten — a number written in prose, inside the
paragraph explaining that numbers written in prose go wrong, wrong again. So
the additions are NAMED instead: ``TestTheRuledStringRegister`` entire, and in
``TestTheRealTree`` the ruled-string, the zero-control, the shrank-set and the
census tests. The only numbers here are the per-class table below, and that
table is asserted.

The one that mattered more: fifteen was never the number of tests in this file.
It was the number in four of the five classes, silently excluding the three
that check this file can run the way the commit path runs it — a scope the
sentence did not state and a reader could only recover by counting and finding
a discrepancy. A census whose predicate is unstated is an impression.

So it is counted by class, which makes the scope the class list itself, and
``test_the_census_in_the_docstring_is_the_census_in_the_file`` asserts these
numbers against collection so the next addition cannot leave them behind:

    TestItRefuses                                7   build a tree and watch
                                                     the guard refuse or stay
                                                     silent
    TestTheRealTree                              9   facts about the real
                                                     tree, two of them
                                                     controls against a
                                                     traversal that has
                                                     stopped working, and one
                                                     of them this table
    TestTheRuledStringRegister                   6   §BB7(a)'s third state,
                                                     including the bar that
                                                     was not moved
    TestWhyThisIsASiblingAndNotAWiderReservedCopy 3  the measurement that made
                                                     this a sibling, one of it
                                                     about a blind spot in the
                                                     OTHER guard
    TestItCanActuallyBeRunTheWayTheCommitPathRunsIt 3 script mode
"""
import os

from tools import brand_strings as bs
from tools import reserved_copy as rc

ROOT = bs.ROOT
MARKER = bs.MARKER


def _tree(tmp_path, body, name="mod.py"):
    (tmp_path / name).write_text(body, encoding="utf-8")
    return str(tmp_path)


def _refusals(tmp_path, body, name="mod.py"):
    problems, _ = bs.check(root=_tree(tmp_path, body, name))
    return problems


class TestItRefuses:
    """§AA — the guard is watched failing, not merely watched passing."""

    def test_an_unmarked_descriptor_is_refused(self, tmp_path):
        problems = _refusals(
            tmp_path, 'S = [{"text": "Botanical Radiance", '
                      '"kind": "descriptor", "rel": 0.62}]\n')
        assert len(problems) == 1
        assert problems[0].startswith(bs.UNMARKED_BRAND_STRING)
        assert "Botanical Radiance" in problems[0]

    def test_a_marked_descriptor_passes(self, tmp_path):
        """THE NEGATIVE CONTROL. Without it every assertion above would hold
        just as well on a guard that refused unconditionally."""
        assert _refusals(
            tmp_path, 'S = [{"text": "%s Botanical Radiance", '
                      '"kind": "descriptor", "rel": 0.62}]\n' % MARKER) == []

    def test_an_empty_descriptor_passes(self, tmp_path):
        assert _refusals(tmp_path,
                         'S = [{"text": "  ", "kind": "descriptor"}]\n') == []

    def test_a_descriptor_bound_to_a_module_constant_is_still_refused(
            self, tmp_path):
        """Indirection through a NAME is not a hiding place — ``_resolve``
        folds module-level constants, which is why this guard borrows it
        rather than re-implementing a weaker one."""
        problems = _refusals(
            tmp_path, 'D = "Quietly Fabricated"\n'
                      'S = [{"text": D, "kind": "descriptor"}]\n')
        assert len(problems) == 1
        assert "Quietly Fabricated" in problems[0]

    def test_a_kind_nobody_declared_halts_rather_than_passing(self, tmp_path):
        """The §AV1 / UNKNOWN_ROLE discipline. A second brand tier arriving
        later must stop this scan, not slip through it — that silent-skip is
        exactly how the readiness report lost a whole category for 25 days."""
        problems = _refusals(
            tmp_path, 'S = [{"text": "Limited Edition", '
                      '"kind": "range_name", "rel": 0.5}]\n')
        assert len(problems) == 1
        assert problems[0].startswith(bs.UNKNOWN_BRAND_KIND)
        assert "range_name" in problems[0]

    def test_a_kind_ruled_out_by_name_is_silent(self, tmp_path):
        """NOT_OURS is a DECLARED boundary, so it is silent — but it is a
        different thing from an undeclared kind, and the test above is what
        makes the difference observable."""
        assert _refusals(
            tmp_path, 'S = [{"text": "30 ml", "kind": "net_content"}]\n') == []
        assert _refusals(
            tmp_path,
            'S = [{"text": "ROSE NECTAR", "kind": "product_name"}]\n') == []

    def test_a_runtime_descriptor_is_recorded_unresolved_and_not_refused(
            self, tmp_path):
        """The seam this guard cannot close, asserted so that it is a KNOWN
        limit and not a discovered one. A descriptor computed at runtime is in
        no ``.py`` file; refusing every dynamic path is how a guard earns 139
        false findings and gets switched off. §AV3's runtime half is what
        covers this, and §AU8(e) is not satisfied without it."""
        root = _tree(tmp_path,
                     'S = [{"text": product.descriptor, "kind": "descriptor"}]\n')
        problems, unresolved = bs.check(root=root)
        assert problems == []
        assert len(unresolved) == 1
        assert unresolved[0][2] == "descriptor"


class TestTheRealTree:
    def test_the_real_tree_is_clean(self):
        problems, _ = bs.check()
        assert problems == [], "\n".join(problems)

    def test_the_descriptor_that_was_found_is_now_retired_by_a_ruling(self):
        """The violation §AU5(2) asked to be watched, followed to its end.

        THIS TEST ASSERTED THE OPPOSITE UNTIL §BB7(a), and the superseded
        version is quoted rather than deleted (§AZ0(u)). It read:

            assert f'"{MARKER} Facial Oil"' in body
            assert '"text": "Facial Oil"' not in body

        — under a docstring saying "This asserts the marker stayed on, because
        the tempting future edit is to strip it to make the fixture read
        nicely." That instruction was RIGHT and is not being disregarded. It
        named one way out and only one: "supply C9 from the owner instead."
        The owner supplied C9 at §BB7(a). Stripping the marker was never
        permitted and still is not; retiring the whole string on a ruling is a
        different act, and it is the act the old comment asked for.

        So the assertion inverts, and what replaces it is stronger than a
        symmetric inversion would be. It is not enough that the substitute is
        gone — the slot has to hold the owner's string, or a future edit could
        satisfy "gone" by deleting the tier."""
        path = os.path.join(ROOT, "apps/ire/tests/test_wit_unit_analysis.py")
        body = open(path, encoding="utf-8").read()
        assert "Facial Oil" not in body
        assert '"text": "FACIAL SERUM", "kind": "descriptor"' in body

    def test_the_fabricated_descriptor_has_no_use_site_left(self):
        """What made it identifiable as fabricated rather than established: an
        owner-supplied value has a record and travels; this one had a single
        site. Contrast the product name, which is at ~97.

        THIS TEST FAILED ON ITS FIRST RUN, AND THE FAILURE IS RECORDED RATHER
        THAN TIDIED. It first counted BYTES — every ``"Facial Oil"`` under
        ``apps/`` — and asserted 1. Measured: 6. All five extra occurrences
        were prose I had just written to record the finding (four in this
        file's own docstring and assertions, one in the comment left at the use
        site). ``git grep -c "Facial Oil" HEAD`` returned exactly 1, so the
        claim was TRUE when taken and was falsified by the act of writing it
        down: the instrument disturbed its own measurement.

        The repair was not a bigger number, and not an exemption for this file
        — both would have kept a byte count that answers the wrong question.
        What was ever meant by "appears once" is that the string has one USE,
        i.e. one site where it is copy rather than commentary. So the count
        runs through the guard's own ``sites`` traversal, which sees dict
        values under a brand ``kind`` and cannot see a docstring at all.

        THE NUMBER IS NOW ZERO, and the traversal is why this file can say so
        while the string is still all over the prose above. HOW MANY TIMES is
        not stated: the draft said "a dozen times overhead" and the measured
        figures were 7 above this line and 17 in the file, so the sentence was
        wrong under both readings of its own scope. A byte count could not have
        made this claim from inside this docstring; that is the same property
        the original repair was for, arriving at the opposite answer.

        THE CONTROLS, AND WHAT THEY DO NOT COVER.
        ``test_a_use_site_counter_that_cannot_count_to_two`` and
        ``test_the_zero_is_a_measurement_and_not_an_empty_traversal`` both build
        a tree under ``tmp_path``, so strictly they prove the traversal works on
        a tree it is POINTED AT — not that it works on the default root this
        assertion uses. That gap is closed by
        ``test_the_ruled_string_took_its_place_and_is_registered``, which runs
        ``sites()`` with no argument and finds the registered rows. Stated
        rather than papered over, because "remains the control that stops a
        traversal returning nothing from passing this forever" was more than
        either control could carry alone.

        THAT SENTENCE READ "finds exactly one row" UNTIL §BB7(c) WIRED BOTH
        CALL SITES and the ruled descriptor acquired a second, EMITTING site.
        The gap it closes is unchanged — a default-root traversal returning
        something is what this needed — so the count is no longer quoted here,
        where it was a detail of the other test rather than a claim of this
        one.
        """
        found, _, _ = bs.sites()
        uses = [row for row in found if "Facial Oil" in row[3]]
        assert uses == []

    def test_the_ruled_string_took_its_place_and_is_registered(self):
        """The other half: the slot is not empty, it holds C9's ruled value,
        and the guard classifies it as RULED rather than as anything else.

        The three states are distinct and this asserts all three of that row's
        verdict columns, because the whole point of the third state is that it
        is NOT the second one wearing a different label: ``marked`` False (the
        owner supplied it, so the marker would be a false claim) and ``ruled``
        pointing at the register entry.

        ONE ROW -> TWO AT §BB7(c), AND THE COUNT WAS NEVER THE CLAIM. The new
        row is ``apps/ire/front_hierarchy.py``: when the owner ruled both call
        sites wired, this string stopped being something the register merely
        records and became something the front PRINTS, so it acquired an
        emission site. What the test is for is untouched — every row must be
        RULED, unmarked, and registered — so the verdict columns are now
        asserted on ALL rows rather than on ``uses[0]``, which had been reading
        one row and calling it the set.

        The count is asserted against the REGISTER rather than against a
        literal, so the next site to arrive fails here unless it is registered
        first. That is the same shape as ``RULED_STRING_OFF_SITE`` in the
        guard, restated where the count lives: an unregistered copy of the
        owner's string cannot pass by being counted.

        WHY THE LITERAL ``2`` IS NOT WRITTEN HERE, THOUGH TWO IS THE ANSWER
        TODAY. The paragraph above was written first and asserted ``len(uses)
        == 2`` underneath it, which is the defect this sprint keeps finding in
        its own prose: a sentence claiming one discipline over code practising
        another. Two assertions replace it and they catch different things —
        set equality catches a use at an UNREGISTERED path, length equality
        catches a registered path used TWICE. Neither alone is the count, and
        no literal is needed for either.

        BOTH LEGS MEASURED BEFORE BEING WRITTEN, and the second leg needed it
        more than the first. Length equality is only a real assertion if
        ``sites()`` yields one row per OCCURRENCE rather than one per file —
        otherwise a duplicated string collapses into a single row and the
        length can never disagree. Measured on a two-line throwaway tree
        holding the string twice in one file: **two rows, lines 1 and 2**. On
        the real tree it returns two rows across two files, matching the
        register exactly. So the assertion detects something rather than
        merely being true, which is the distinction
        ``test_a_use_site_counter_that_cannot_count_to_two`` below exists to
        insist on."""
        found, _, _ = bs.sites()
        uses = [row for row in found if row[3] == "FACIAL SERUM"]
        assert uses, "the traversal found no use of the ruled string at all"
        for rel, _, kind, value, marked, ruled in uses:
            assert kind == "descriptor"
            assert marked is False, f"{rel} carries {MARKER} on a RULED string"
            assert ruled is not None and ruled.ruling == "C9"
            assert ruled.source == bs.OWNER_TYPED_AT_TERMINAL
            assert rel in ruled.sites
        assert {row[0] for row in uses} == set(uses[0][5].sites)
        assert len(uses) == len(uses[0][5].sites), uses

    def test_a_use_site_counter_that_cannot_count_to_two(self, tmp_path):
        """THE CONTROL for the test above. An assertion that some count is 1 is
        worthless until something has been shown to make it 2 — otherwise a
        traversal that silently returned nothing would pass it forever."""
        found, _, _ = bs.sites(root=_tree(
            tmp_path,
            'A = [{"text": "%s Facial Oil", "kind": "descriptor"}]\n'
            'B = [{"text": "%s Facial Oil", "kind": "descriptor"}]\n'
            '# a mention of Facial Oil in a comment is not a use site\n'
            'DOC = "prose about Facial Oil"  # nor is unkinded prose\n'
            % (MARKER, MARKER)))
        uses = [row for row in found if "Facial Oil" in row[3]]
        assert len(uses) == 2, uses
        assert all(row[4] for row in uses)

    def test_the_zero_is_a_measurement_and_not_an_empty_traversal(
            self, tmp_path):
        """THE CONTROL FOR THE ZERO.
        ``test_the_fabricated_descriptor_has_no_use_site_left`` asserts an
        EMPTY list, and an empty list is also what a traversal that has stopped
        working returns — the failure mode the count-to-two control was built
        for, arriving from the other side.

        So the SAME traversal, under the SAME predicate, is shown finding the
        retired string where it genuinely is present. If this passes and the
        zero above passes, the zero is a fact about the tree.
        """
        found, _, _ = bs.sites(root=_tree(
            tmp_path,
            'S = [{"text": "%s Facial Oil", "kind": "descriptor"}]\n' % MARKER))
        uses = [row for row in found if "Facial Oil" in row[3]]
        assert len(uses) == 1, uses

    def test_the_string_is_mentioned_only_where_the_finding_is_recorded(self):
        """The drift guard the byte count was reaching for, done properly: the
        SET of files that may name this string at all, pinned the way
        ``test_container_line_weight.py`` pins the ``hierarchy_lines`` file set.
        A new file naming it fails here — which is the event worth catching,
        because a fabricated descriptor spreading is exactly how a placeholder
        becomes established by attrition."""
        naming = set()
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, "apps")):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if name.endswith(".py"):
                    path = os.path.join(dirpath, name)
                    if "Facial Oil" in open(path, encoding="utf-8").read():
                        naming.add(os.path.relpath(path, ROOT))
        assert naming == {
            "apps/ire/tests/test_av2_brand_strings.py",   # this record of it
        }, naming

    def test_retiring_the_string_shrank_that_set_rather_than_holding_it(self):
        """THE SET ABOVE USED TO HAVE TWO MEMBERS and the second one was the
        use site. §BB7(a) retired the string, and the honest question is
        whether that made the pin tighter or merely moved a name around.

        It made it tighter, and this is the assertion that says so out loud:
        the use site's file no longer names the retired string ANYWHERE, not in
        a fixture and not in the comment that explains the fixture. The comment
        left there deliberately does not reproduce it and says why — a dead
        placeholder spreading through its own obituaries is the same attrition
        the pin above exists to catch, with the sign flipped.

        IT ADDS NO DISCRIMINATION AND IS KEPT ANYWAY, WHICH IS A CHOICE AND IS
        LABELLED AS ONE. The draft justified it with "without this, a repointed
        pin that had quietly stayed the same size would read exactly like a
        repointed pin that had tightened." An audit measured that false: the
        set above is pinned by EXACT EQUALITY on a one-member set, so a set
        still holding two members already fails there, and this assertion is a
        strict consequence of it — the same fact is also asserted a third time
        at ``test_the_descriptor_that_was_found_is_now_retired_by_a_ruling``.

        It stays because deleting a green test to satisfy an audit is a bar
        being moved (§AU6(c)), and because the two above assert it about a SET
        and about a marker respectively, while this one names the file. What is
        removed is the false claim that it catches something they miss."""
        path = os.path.join(ROOT, "apps/ire/tests/test_wit_unit_analysis.py")
        assert "Facial Oil" not in open(path, encoding="utf-8").read()

    def test_the_census_in_the_docstring_is_the_census_in_the_file(self):
        """THE CENSUS CANNOT GO STALE SILENTLY ANY MORE.

        The docstring's previous count was wrong by ten and by a whole class at
        once, and nothing in the suite noticed, because a count in prose is
        checked only by a reader who decides to count. This reads the classes
        out of the module and compares.

        IT SAID "WRONG BY NINE" UNTIL AN AUDIT COUNTED IT. Ten is the measured
        figure — the same off-by-one the module docstring records thirteen
        lines above, made a second time, in the docstring of the test written
        to abolish it, because nine was taken before this test existed and was
        never retaken after it did. A number stated from inside the scope it
        counts moves when the sentence is written. This one is kept as evidence
        that knowing the defect by name does not stop it; only the assertion
        below stops it, and the assertion covers the table, not this prose.

        IT SITS INSIDE ITS OWN COUNT, WHICH IS FINE ONLY BECAUSE THE PREDICATE
        IS STATED. The first draft of this test was written into
        ``TestTheRuledStringRegister``, where it made that class's number 7
        while asserting 6 — a count moved by the act of counting, which is the
        defect this repository has now paid for repeatedly. It lives here
        because this class is "facts about the real tree" and this file is part
        of the real tree; it counts itself, and the number below says so.

        It is deliberately NOT a total. A total is satisfiable by adding one
        test and deleting another, which is exactly how a census stays green
        while becoming false — the same defect as a byte count of 1 surviving a
        second use site appearing while a mention was deleted."""
        import inspect
        import sys

        module = sys.modules[__name__]
        measured = {}
        for name, obj in vars(module).items():
            if inspect.isclass(obj) and name.startswith("Test"):
                measured[name] = sum(
                    1 for attr in vars(obj) if attr.startswith("test_"))
        assert measured == {
            "TestItRefuses": 7,
            "TestTheRealTree": 9,
            "TestTheRuledStringRegister": 6,
            "TestWhyThisIsASiblingAndNotAWiderReservedCopy": 3,
            "TestItCanActuallyBeRunTheWayTheCommitPathRunsIt": 3,
        }, measured

        # AND THE DOCSTRING'S TABLE IS PARSED, NOT SEARCHED. The first version
        # of this half did ``str(count) in doc.split(name, 1)[1][:80]`` and it
        # failed on its first run after the prose above the table gained the
        # words ``TestTheRealTree`` — ``split`` took the FIRST occurrence and
        # the window landed in a sentence. §AD0(b) again: an instrument
        # recognising a thing by an incidental feature of how it is written,
        # here "the name's first appearance is its table row".
        #
        # The repair is stricter than the window was, not a wider window. A
        # window passes on any stray digit in the following eighty characters;
        # this reads the table into a dict and compares dicts, so a class named
        # in the table but absent from the file — and the reverse — now fails.
        import re
        stated = dict(
            (m.group(1), int(m.group(2))) for m in
            re.finditer(r"^ {4}(Test\w+) +(\d+)", module.__doc__, re.M))
        assert stated == measured, (stated, measured)


class TestTheRuledStringRegister:
    """§BB7(a)'s third state. The guard had two verdicts and an owner ruling
    produces a value neither of them describes."""

    _RULED = 'S = [{"text": "FACIAL SERUM", "kind": "descriptor"}]\n'

    def test_the_ruled_string_still_refuses_away_from_its_sites(self, tmp_path):
        """THE WHOLE REASON THE REGISTER IS VALUE-LEVEL AND SITE-PINNED. A
        ruling authorises a string somewhere, not everywhere. Without this, the
        register is a laundering channel: register once, use anywhere.

        The precedent is measured, not invented — ``reserved_copy``'s register
        gained its own ``sites`` field only after a mutation showed that a
        register without one "licenses a measurement fixture to become emitted
        copy"."""
        problems = _refusals(tmp_path, self._RULED)
        assert len(problems) == 1
        assert problems[0].startswith(bs.RULED_STRING_OFF_SITE)
        assert "C9" in problems[0]

    def test_a_reshaped_ruled_string_is_refused_and_named_as_reshaped(
            self, tmp_path):
        """Case and spacing are characters. §BB7(a) records the string
        "verbatim, case included: two words, one space, both uppercase".

        THE REFUSAL IS NOT NEW AND THE MESSAGE IS. Every value here is refused
        with or without this branch, as an unmarked fabrication — so this
        widens no permission. What it buys is a true sentence: the operator is
        told he altered the owner's string, not that he invented one. In a
        repository whose §BB7 exists because the owner's punctuation was
        altered inside quotation marks, that distinction is the finding.

        AND THE PROHIBITION IT ENFORCES IS THE EXECUTOR'S, NOT THE OWNER'S.
        §BB7(a) flags it as his in its own words and adds: "If the owner wants
        `Facial Serum`, or a volume appended, he says so and this paragraph
        does not stand in his way." The register says the same thing in its
        own comment, so the inference cannot be read off this code as a
        ruling."""
        for reshaped in ('Facial Serum', 'FACIAL  SERUM', 'facial serum'):
            problems = _refusals(
                tmp_path,
                'S = [{"text": "%s", "kind": "descriptor"}]\n' % reshaped)
            assert len(problems) == 1, (reshaped, problems)
            assert problems[0].startswith(bs.RULED_STRING_ALTERED), reshaped
            assert "FACIAL SERUM" in problems[0], reshaped

    def test_a_reshaped_string_was_already_refused_before_this_branch(
            self, tmp_path):
        """THE CONTROL THAT PROVES THE PARAGRAPH ABOVE. The claim "this widens
        no permission" is only worth making if the pre-existing refusal is
        shown, rather than asserted from memory: a value that is neither the
        ruled string nor marked carries no MARKER, which is what
        UNMARKED_BRAND_STRING has always fired on. Same input shape, no
        register entry to match, still exactly one refusal."""
        problems = _refusals(
            tmp_path, 'S = [{"text": "Radiance Serum", "kind": "descriptor"}]\n')
        assert len(problems) == 1
        assert problems[0].startswith(bs.UNMARKED_BRAND_STRING)

    def test_the_register_did_not_exempt_the_descriptor_kind(self):
        """THE BAR THAT WAS NOT MOVED (§AU6(c)). The cheap fix for §BB7(a) was
        one line — put "descriptor" into NOT_OURS — and it would have passed
        every green test in this file while retiring the guard entirely, since
        ``descriptor`` is the ONLY kind ``BRAND_KINDS`` names.

        So the shape is asserted, not just the behaviour: the kind is still
        this guard's, and NOT_OURS still names exactly the two kinds it named
        before."""
        assert "descriptor" in bs.BRAND_KINDS
        assert "descriptor" not in bs.NOT_OURS
        # two -> three on 2026-10-29 (the owner's message, "Fix the 5 fast tests … brand strings"): Illustrator's native
        # text-frame type, ruled out BY NAME with its owner; the descriptor kind is still this guard's
        assert set(bs.NOT_OURS) == {"net_content", "product_name", "TextType.POINTTEXT"}

    def test_every_register_entry_cites_a_ruling_and_an_authority(self):
        """A register row without a citation is an executor's assertion in a
        table, which is the §AU0(b) shape the register exists to prevent. The
        authority names a SUBSECTION rather than a line, deliberately: the
        tracker field for this node has carried three separate stale line
        numbers into this same clearance file.

        AND THE CITATION IS RESOLVED, NOT JUST SHAPED. The first version of
        this test asserted ``":" not in entry.authority`` and stopped there. An
        audit put the obvious question to it: a row citing a subsection that
        does not exist passes a shape check, so the test whose docstring says
        an uncited row "is an executor's assertion in a table" was itself
        asserting nothing about the table's citations. It now opens the file
        and looks the subsection up — and finding the file at all is the
        two-roots hazard in miniature, since ``OWNER_BLOCKER_CLEARANCE.md``
        lives at the GIT root and does not resolve from the pytest root this
        guard runs under.

        The shape check is kept alongside it, with its message corrected. It
        cannot detect every line-number spelling — ``§BB7(a) L10479`` passes
        it — so it no longer claims to. It rules out the one spelling that
        would otherwise be natural to write."""
        git_root = os.path.dirname(ROOT)
        assert bs.RULED_STRINGS, "the register is empty"
        for entry in bs.RULED_STRINGS:
            assert entry.source == bs.OWNER_TYPED_AT_TERMINAL
            assert entry.ruling.strip()
            assert entry.authority.startswith("OWNER_BLOCKER_CLEARANCE.md §")
            assert ":" not in entry.authority, \
                f"{entry.ruling} cites {entry.authority!r}; a colon here is " \
                f"the line-number spelling, and line numbers go stale"
            assert entry.kind in bs.BRAND_KINDS
            assert entry.sites, f"{entry.ruling} is pinned to no site"
            assert entry.reason.strip()
            assert MARKER not in entry.text, \
                f"{entry.ruling} registers a PROVISIONAL string as ruled"

            name, subsection = entry.authority.split(" §", 1)
            path = os.path.join(git_root, name)
            assert os.path.exists(path), f"{entry.ruling} cites absent {path}"
            body = open(path, encoding="utf-8").read()
            assert subsection in body, \
                f"{entry.ruling} cites §{subsection}, which is not in {name}"

    def test_the_registered_text_is_what_the_owner_typed(self):
        """Pinned against the ruling's own words. §BB7(a): "two words, one
        space, both uppercase".

        THE DOCSTRING SAID "rather than against itself" AND THE FIRST
        ASSERTION IS EXACTLY THAT — a literal copy of the value under test.
        The three that follow are the ones the sentence describes; they are
        what the ruling's words translate to, and they would fail on
        ``Facial Serum``, ``FACIAL  SERUM`` and ``FACIAL SERUM 30 ml`` without
        naming any of them. The literal is kept as the byte-for-byte pin the
        register's whole premise rests on, and the claim is narrowed to what
        is true of the rest."""
        entry, = [e for e in bs.RULED_STRINGS if e.ruling == "C9"]
        assert entry.text == "FACIAL SERUM"
        assert entry.text.split(" ") == ["FACIAL", "SERUM"]
        assert entry.text.isupper()
        assert MARKER not in entry.text


class TestWhyThisIsASiblingAndNotAWiderReservedCopy:
    """§AV2's justification, pinned as measurement. If ``reserved_copy`` is
    ever taught this shape these tests should fail, and the sibling should
    then be reconsidered rather than kept out of habit."""

    def test_reserved_copy_cannot_see_a_descriptor_dict_at_all(self):
        import ast
        for src in ('{"text": "Botanical", "rel": 0.62, "kind": "descriptor"}',
                    '{"text": "%s Botanical", "rel": 0.6, '
                    '"kind": "descriptor"}' % MARKER):
            node = ast.parse(src, mode="eval").body
            pairs, unknown = rc._pairs(node, {}, {})
            assert pairs == [] and unknown == [], src

    def test_reserved_copy_is_otherwise_sensitive(self):
        """The control that makes the claim above a finding rather than a
        broken import: the same function DOES see a reserved section, and its
        UNKNOWN_ROLE net DOES fire for a misspelled text key."""
        import ast
        seen, _ = rc._pairs(ast.parse(
            '{"heading": "INGREDIENTS", "text": "Aqua"}', mode="eval").body,
            {}, {})
        assert len(seen) == 1
        _, unknown = rc._pairs(ast.parse(
            '{"heading": "WARNINGS", "blurb": "Avoid eyes"}',
            mode="eval").body, {}, {})
        assert len(unknown) == 1

    def test_the_reserved_copy_blind_spot_is_real_and_still_open(self):
        """A registered §AE2(b) reconstruction pinned to ONE site has travelled
        to another file in the ``kind`` shape, and ``reserved_copy`` reports
        zero problems — its RECONSTRUCTION_OFF_SITE rule exists to catch
        exactly this and structurally cannot. Reported by §AV2, not repaired by
        it: closing it changes a working guard and belongs in its own ruling.

        When someone does close it, this test fails, and that is the signal to
        delete it rather than to weaken the repair.

        THE CONSTANT LOST ITS LINE NUMBER AND THIS TEST LOST A DEAD BINDING.
        It read ``rel, line = site.rsplit(":", 1)`` and then never used
        ``line`` — so the pin carried a number no assertion could falsify, and
        it was 21 lines stale when written and 37 after this commit moved the
        string it points at. The search below is what actually located the
        finding all along."""
        rel, text, row = bs.RESERVED_COPY_BLIND_SPOT
        body = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert text in body, f"{text!r} no longer at {rel}"
        registered = {r.text: r for r in rc.RECONSTRUCTED_COPY}
        assert text in registered, f"{text!r} is not a registered reconstruction"
        assert rel not in registered[text].sites, \
            f"{rel} is now a permitted site — the blind spot may be closed"
        assert registered[text].manifest_row == row
        problems, _ = rc.check()
        assert problems == [], "reserved_copy now refuses something; re-read this"


class TestItCanActuallyBeRunTheWayTheCommitPathRunsIt:
    """THE DEFECT THIS CLASS EXISTS FOR, NAMED PLAINLY.

    §AV2 committed this guard at ``84e0018`` importing ``tools.reserved_copy``
    with no path preamble. Every test above passes under pytest, where the
    pytest root is already ``sys.path[0]``. Run the way ``guarded_commit.sh``
    runs its sibling — ``venv/bin/python tools/brand_strings.py``, where
    ``sys.path[0]`` is ``tools/`` — it raised ``ModuleNotFoundError: No module
    named 'tools'`` and exited 1.

    So for one commit there was a §AE2(c) guard whose whole test file was green
    and which could not be invoked on the path it was built to protect. Nothing
    in that file could have noticed, because every test in it ran the guard as
    an IMPORT. §AA says a guard nobody has seen fire is not evidence of
    anything; this is the narrower case — a guard seen firing only in the one
    place where firing does not matter.

    THIS PARAGRAPH SAID "twenty green tests … all twenty" AND THE NUMBER WAS
    FIFTEEN. ``git show 84e0018:…/test_av2_brand_strings.py | grep -c
    "def test_"`` returns 15. It is not restated as fifteen, because the
    argument never needed a number — what it needs is "all of them", which is
    the predicate that makes the point and cannot go stale. The wrong number
    survived because it sat outside the census paragraph's scope: §AA counted
    four of five classes, and this is the fifth. That is the same unstated
    scope §AA is an apology for, caught on the other side of it.
    """

    def _script(self, *args):
        import subprocess
        import sys as _sys
        return subprocess.run(
            [_sys.executable, os.path.join("tools", "brand_strings.py"), *args],
            capture_output=True, text=True, cwd=ROOT)

    def test_the_guard_runs_as_a_bare_script_and_not_only_as_an_import(self):
        """THE REGRESSION PIN. This is the test whose absence let the defect
        ship: it invokes the file the way the commit path does, as a
        subprocess, rather than importing it the way every other test here
        does. Before the preamble it failed with ModuleNotFoundError."""
        r = self._script()
        assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
        assert "BRAND_STRINGS_OK" in r.stdout
        assert "ModuleNotFoundError" not in r.stderr

    def test_it_survives_the_git_root_being_first_on_pythonpath(self):
        """THE TEST THAT REFUTED THE FIRST FIX, KEPT BECAUSE IT DID.

        The first repair inserted the pytest root at ``sys.path[0]`` and its
        comment claimed that also settled the two-roots hazard. This test was
        written to pin that claim and instead broke it::

            ModuleNotFoundError: No module named 'tools.reserved_copy'

        ``tools`` resolved — to the GIT ROOT's package, which has an
        ``__init__.py`` and no ``reserved_copy.py``. PEP 420 gives a regular
        package precedence over a namespace portion no matter which comes first
        on the path, so no ordering could have fixed it. The sibling is now
        loaded by file path, and this asserts the configuration the repository's
        own notes record as a recurring gotcha."""
        import subprocess
        import sys as _sys
        git_root = os.path.dirname(ROOT)
        env = dict(os.environ, PYTHONPATH=git_root)
        r = subprocess.run(
            [_sys.executable, os.path.join("tools", "brand_strings.py")],
            capture_output=True, text=True, cwd=ROOT, env=env)
        assert r.returncode == 0, f"stdout={r.stdout!r} stderr={r.stderr!r}"
        assert "BRAND_STRINGS_OK" in r.stdout

    def test_source_guard_the_commit_path_invokes_this_guard_and_refuses_on_it(
            self):
        """SOURCE-STRING GUARD — §Y2(b). This asserts NOTHING about behaviour.

        It reads ``tools/guarded_commit.sh`` and checks that the invocation and
        the refusal are both present. §Y2(c), the limit, stated rather than
        engineered away: **this cannot prove the block runs, only that it is
        written.** The proof that it runs was taken by hand — an unmarked
        descriptor planted under ``apps/`` produced
        ``GUARDED_COMMIT_REFUSED: brand strings (§AV2/§AU5)`` with exit 1, and
        the same descriptor carrying the marker produced ``BRAND_STRINGS_OK``
        and exit 0.

        That observation is NOT repeated here as a test on purpose. Doing it
        automatically means writing a ``.py`` file under ``apps/`` mid-run, and
        ``test_wig_source_string_guards.py`` and ``test_wit_unit_analysis.py``
        both walk and AST-parse ``apps/`` at test time — so the honest test
        would inject spurious failures into two other files. A weaker check
        that says so beats a stronger one that corrupts its neighbours."""
        body = open(os.path.join(ROOT, "tools", "guarded_commit.sh"),
                    encoding="utf-8").read()
        assert "venv/bin/python tools/brand_strings.py" in body, \
            "the commit path no longer invokes the §AE2(c) guard"
        assert "GUARDED_COMMIT_REFUSED: brand strings" in body, \
            "the commit path invokes the guard but does not refuse on it"
        invoke = body.index("venv/bin/python tools/brand_strings.py")
        # ANCHOR ON THE REFUSAL, NOT ON THE STRING "TIER_2". The first draft
        # used ``body.index("TIER_2")`` and failed 8950 < 2569, because the
        # first mention of TIER_2 is a comment 140 lines above the block that
        # runs it. The test was right to fail and the instrument was wrong:
        # AD0(b), an instrument recognising a thing by an incidental feature of
        # how it is written. The refusal line is the block.
        tier2 = body.index('GUARDED_COMMIT_REFUSED: TIER_2=')
        assert invoke < tier2, \
            "the brand guard must run before TIER_2, so a refusal is not " \
            "hidden behind an eight-minute suite"
