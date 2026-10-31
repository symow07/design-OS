"""§AK/WI-3H — the register of reconstructed reserved copy, and its refusals.

§AE2(b) reserves regulated copy from the executor and gives the reason in
one sentence: *"A generated cosmetic warning that reads correctly, on a
product that is actually manufactured and actually sold, is a real harm to
a real person — and it passes review precisely because it looks like
copy."* §AE3 requires every substitute to carry the literal token
``⟪PROVISIONAL⟫``.

Measured at WI-3H, that token appeared in **zero** ``.py`` files while
three prose documents described it as being in use, and what stood in its
place in the fixtures was a twenty-name INCI list bound to a variable
called ``_REAL``. The good news, which is most of the story and is
asserted here rather than assumed: the PRODUCTION path never fabricated.

WHAT THIS FILE IS FOR. `tools/reserved_copy.py` is a guard, and §AA says a
guard nobody has seen fire is not evidence of anything. SEVEN of the
fifteen tests below build a tree and watch it refuse; FOUR assert the
real one; THREE state the blind spot as a number. One of the seven —
`test_a_registered_string_that_migrates_to_another_file_is_refused` —
exists because the guard was mutation-tested rather than read, and the
first register turned out to bless a fixture string ON THE EMITTER.

WHY THE GUARD IS NARROW, stated because the alternative was tried. The
first draft paired a reserved heading with every string in the enclosing
expression, on the §AD0(b) reasoning that matching a dict's key NAMES
would be recognising a thing by the shape of its implementation. Run once
against `apps/`, it produced 139 findings of which about twelve were copy:
it reported dict keys and the prose that DESCRIBES cuts as though both
were copy. §AD0(b) cuts both ways. The role vocabulary is now declared,
and `test_an_unknown_text_role_key_halts_rather_than_passing` is what
stops the declaration going quietly stale.
"""
import os

from tools import reserved_copy as rc

ROOT = rc.ROOT


def _tree(tmp_path, body, name="mod.py"):
    (tmp_path / name).write_text(body, encoding="utf-8")
    return str(tmp_path)


def _refusals(tmp_path, body, name="mod.py"):
    problems, _ = rc.check(root=_tree(tmp_path, body, name))
    return problems


class TestTheRealTree:
    """What is actually in `apps/` today, measured not predicted."""

    def test_the_register_accounts_for_every_reserved_string_in_apps(self):
        """The green half of the pair. It means one thing only: every
        reserved-copy string under `apps/` is the production marker, the
        charter token, empty, or registered with a named source and a
        named manifest row. It does NOT mean the copy is right — none of
        it is copy at all."""
        problems, _ = rc.check()
        assert problems == []

    def test_the_production_path_supplies_no_reserved_copy_at_all(self):
        """The assertion that would matter if only one survived.

        `_back_sections_from_record` is the single source of back-panel
        sections on an emitted sheet. All six reserved headings come out
        as the marker, and each one appends a readiness code. NET CONTENT
        joined them at §AK4 on 2026-08-20 — it had been a hardcoded
        `30 ml / 1.01 fl. oz.` with `verified=True` since the function
        was written, which is to say it emitted a MANDATORY QUANTITY
        DECLARATION as though someone had supplied it.
        """
        from apps.pipeline.targets.container import (
            CONTENT_VERIFICATION_REQUIRED, _back_sections_from_record)

        class _P:
            name = "Rose Damascena Serum"

        sections, codes = _back_sections_from_record(_P())
        reserved = {s["heading"]: s["text"] for s in sections
                    if s["heading"] in rc.RESERVED_HEADINGS}
        assert set(reserved) == {"DESCRIPTION", "INGREDIENTS", "DIRECTIONS",
                                 "WARNINGS", "MANUFACTURER", "NET CONTENT"}
        assert set(reserved.values()) == {CONTENT_VERIFICATION_REQUIRED}
        assert len(codes) == 6
        registered = {r.text for r in rc.RECONSTRUCTED_COPY}
        assert not registered & set(reserved.values())

    def test_every_register_entry_names_a_source_and_a_manifest_row(self):
        """§AK3 clause 3 — the register is the ask, not the answer. An
        entry without a row is a reconstruction that has stopped asking
        for its replacement, which is the failure mode this whole
        mechanism exists to prevent one level down."""
        known = {rc.WRITTEN_BY_EXECUTOR,
                 rc.DERIVED_FROM_PUBLISHED_ARITHMETIC,
                 rc.QUOTED_FROM_A_RECONSTRUCTION}
        assert rc.RECONSTRUCTED_COPY, "an empty register asserts nothing"
        for entry in rc.RECONSTRUCTED_COPY:
            assert entry.source in known, entry.heading
            assert entry.manifest_row, entry.heading
            assert entry.sites, entry.heading
            for site in entry.sites:
                assert os.path.exists(os.path.join(ROOT, site)), site
            assert len(entry.reason) > 40, entry.heading
            assert entry.heading in rc.RESERVED_HEADINGS

    def test_the_two_spellings_of_the_marker_are_bound_in_one_place(self):
        """§AK3 clause 1. A future executor greps `⟪PROVISIONAL⟫` because
        §AE3(c)/(d) tell it to. Before WI-3H that grep returned three
        prose documents and no code, so it would have concluded there
        were no substitutions in the repository. The binding is what
        makes either spelling reach the other."""
        text = open(rc.__file__, encoding="utf-8").read()
        assert rc.PROVISIONAL_TOKEN in text
        assert rc.PRODUCTION_SPELLING in text
        assert rc.PROVISIONAL_TOKEN == "⟪PROVISIONAL⟫"
        assert set(rc.ACCEPTED_MARKERS) == {rc.PROVISIONAL_TOKEN,
                                            rc.PRODUCTION_SPELLING}


class TestItRefuses:
    """§AA — seven trees this guard is watched refusing."""

    def test_an_unregistered_reserved_string_is_refused(self, tmp_path):
        problems = _refusals(tmp_path, 'S = [{"heading": "WARNINGS",\n'
                                       '      "text": "Avoid the eyes."}]\n')
        assert len(problems) == 1
        assert problems[0].startswith("UNREGISTERED_RESERVED_COPY")
        assert "WARNINGS" in problems[0] and "Avoid the eyes." in problems[0]

    def test_both_markers_and_an_empty_string_pass(self, tmp_path):
        body = ('S = [{"heading": "INGREDIENTS", "text": "%s"},\n'
                '     {"heading": "WARNINGS", "text": "%s"},\n'
                '     {"heading": "MANUFACTURER", "text": ""}]\n'
                % (rc.PRODUCTION_SPELLING, rc.PROVISIONAL_TOKEN))
        assert _refusals(tmp_path, body) == []

    def test_a_registered_string_that_drifts_by_one_character_is_refused(
            self, tmp_path):
        """The register is keyed by TEXT, not by variable name or file
        path. A rename must not silently unregister anything, and a
        reconstruction that drifts by one character is a different
        reconstruction that has not been ruled on."""
        pinned = "BBROSE Ltd, London N1 6NT, Great Britain."
        entry, = [r for r in rc.RECONSTRUCTED_COPY if r.text == pinned]
        assert entry.sites == ("apps/ire/tests/test_wik_back_panel_floor.py",)
        drifted = pinned.replace("N1 6NT", "N1 6NU")
        problems = _refusals(
            tmp_path, 'S = [{"heading": "MANUFACTURER", "text": %r}]\n'
                      % drifted)
        assert len(problems) == 1
        assert problems[0].startswith("UNREGISTERED_RESERVED_COPY")
        assert "N1 6NU" in problems[0]

    def test_a_registered_string_that_migrates_to_another_file_is_refused(
            self, tmp_path):
        """THE HOLE FOUND BY MUTATION, kept shut by a test.

        The first register made a string permissible anywhere once
        registered. Putting the old
        `add("NET CONTENT", "30 ml / 1.01 fl. oz.", True)` back on the
        production path left `check()` perfectly green: the string was
        in the register, so the guard blessed it on the emitter. The
        defect was invisible from reading and took ten seconds to find
        by mutating. A register that lets a measurement fixture become
        emitted copy is worse than no register — it converts "we know
        about this" into "this is fine".
        """
        pinned = "30 ml / 1.01 fl. oz."
        entry, = [r for r in rc.RECONSTRUCTED_COPY if r.text == pinned]
        assert "apps/ire/tests/test_back_panel.py" in entry.sites
        problems = _refusals(tmp_path,
                             'S = [{"heading": "NET CONTENT", "text": %r}]\n'
                             % pinned)
        assert len(problems) == 1
        assert problems[0].startswith("RECONSTRUCTION_OFF_SITE")
        assert entry.manifest_row in problems[0]

    def test_a_register_entry_whose_text_left_the_tree_is_refused(
            self, tmp_path, monkeypatch):
        """A315 clause 4 one level up: the check runs in both
        directions. A register that outlives its subject is a document
        describing a repository that no longer exists, and it is exactly
        as misleading as an unregistered string — more so, because it
        reads as diligence."""
        ghost = rc.Reconstruction(
            heading="WARNINGS", text="A sentence no file contains.",
            source=rc.WRITTEN_BY_EXECUTOR, reason="planted by this test",
            manifest_row="B1", sites=("apps/ire/tests/test_back_panel.py",))
        monkeypatch.setattr(rc, "RECONSTRUCTED_COPY",
                            rc.RECONSTRUCTED_COPY + (ghost,))
        # against the REAL tree — the ghost is the only entry that is not
        # in it, which is what makes this one refusal and not thirteen.
        problems, _ = rc.check()
        assert len(problems) == 1
        assert problems[0].startswith("STALE_REGISTRATION")
        assert "WARNINGS" in problems[0]

    def test_the_stale_direction_is_off_for_an_overridden_root_on_purpose(
            self, tmp_path):
        """The scoping above, asserted rather than left as a comment.
        Asked of a two-line temp tree, the stale check would report all
        twelve real entries as missing and bury whatever the test was
        written to see — which is how it was discovered, by writing the
        five refusal tests and getting 13 findings each time."""
        root = _tree(tmp_path, "S = []\n")
        assert rc.check(root=root)[0] == []
        forced, _ = rc.check(root=root, include_stale=True)
        assert len(forced) == len(rc.RECONSTRUCTED_COPY) == 12
        assert all(p.startswith("STALE_REGISTRATION") for p in forced)

    def test_an_unknown_text_role_key_halts_rather_than_passing(
            self, tmp_path):
        """A403's discipline applied to the role vocabulary: a new
        spelling of "text" HALTS the scan instead of being skipped by
        it. Without this, adding `{"heading": "WARNINGS", "prose": ...}`
        anywhere would make the copy invisible to the guard and the
        guard would keep reporting green."""
        problems = _refusals(tmp_path, 'S = [{"heading": "WARNINGS",\n'
                                       '      "prose": "Avoid the eyes."}]\n')
        assert len(problems) == 1
        assert problems[0].startswith("UNKNOWN_ROLE")
        assert "prose" in problems[0]

    def test_the_call_form_is_seen_and_not_only_the_dict_form(self, tmp_path):
        """The production path does not build a dict literal — it calls
        `add("NET CONTENT", "...", True)`. A guard that only understood
        dicts would have reported green over the one site in this
        repository where a reserved literal actually reached an emitted
        sheet, which is the site it was built to find."""
        problems = _refusals(tmp_path, 'def f(add):\n'
                                       '    add("NET CONTENT", "50 ml", True)\n')
        assert len(problems) == 1
        assert problems[0].startswith("UNREGISTERED_RESERVED_COPY")
        assert "50 ml" in problems[0]


class TestWhatItDoesNotSee:
    """§AD0(c) and §Y2(c) — the blind spot is a number this prints."""

    def test_unresolvable_text_is_counted_rather_than_skipped(self, tmp_path):
        """Text assembled at runtime, or reached through a subscript or
        a call, resolves to no constant. It is reported as UNRESOLVED
        rather than passed over, so the extent of the blind spot is
        measurable instead of silent. It is deliberately NOT a refusal:
        making it one would fail the suite on every f-string near a
        heading and the guard would be turned off within a sprint."""
        _, unresolved = rc.check(root=_tree(
            tmp_path, 'def f(n):\n'
                      '    return [{"heading": "WARNINGS", "text": f"{n}"}]\n'))
        assert len(unresolved) == 1
        assert unresolved[0][2] == "WARNINGS"
        assert unresolved[0][3] == "<f-string>"

    def test_the_real_tree_blind_spot_is_nine_sites(self):
        """Pinned so that a fourth shows up as a changed number rather
        than as nothing. All three are locals inside tests that build
        copy at runtime; none is on the production path.

        [§BH54(b) (k) 4, 2026-09-19 — it showed up, as it was pinned to:
        THREE became NINE, and the six new sites ARE on the production
        path. They are the six reserved headings of
        `_back_sections_from_record`, whose text now comes from the
        OWNER'S COPY CHANNEL — a database row he typed, carrying his
        identity, the time and the sha256 of exactly those words,
        re-verified on every read — which is "text read from a
        database row", the blind spot this guard names for itself. The
        guard cannot read a row; what it still sees is that no LITERAL
        stands beside those headings, and the test above proves a
        product with no typed piece emits the marker six times.]"""
        _, unresolved = rc.check()
        assert len(unresolved) == 9
        assert {u[0] for u in unresolved} == {
            "apps/ire/back_panel_copy.py",
            "apps/ire/tests/test_back_panel.py",
            "apps/pipeline/targets/container/__init__.py"}
        assert sorted(u[2] for u in unresolved if u[0].startswith("apps/pipeline/")) == [
            "DESCRIPTION", "DIRECTIONS", "INGREDIENTS", "MANUFACTURER", "NET CONTENT", "WARNINGS"]

    def test_the_scope_is_declared_and_excludes_the_product_name(self):
        """§AE2(b) REGULATED COPY only. PRODUCT is brand — §AE2(c) — a
        different reservation with a different remedy, and it comes from
        the record on the production path rather than from a literal.
        Declaring the scope is what stops it being SILENT_EXTENT_LOSS:
        a reader can see what is out and why, instead of inferring
        coverage from a passing test."""
        assert "PRODUCT" not in rc.RESERVED_HEADINGS
        assert rc.RESERVED_HEADINGS == frozenset({
            "INGREDIENTS", "WARNINGS", "MANUFACTURER", "DIRECTIONS",
            "DESCRIPTION", "CLAIMS", "NET CONTENT"})
