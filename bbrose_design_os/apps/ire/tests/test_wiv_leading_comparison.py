"""WI-V / §AB3 — the leading comparison, and the comment that was false.

§AB3 issues NO RULING on the leading, so this file contains no assertion about
which of 1.06 / 2.0 / 3.0047 em is right, and it must not acquire one. [§BH54(b)
(o): it has not. §AC1 has since ruled the leading; what (o) adds here is about the
AXIS comparing like with like against whatever constant the composer reads.] What it
pins is the three things §AB3 actually asked for and the two it turned up:

* the comparison exists at TRUE SCALE on the ruled 9.0 pt name (AB3(a));
* the incumbent is UNMOVED by producing it (AB3(b)) — rendering a comparison
  must not be a way of quietly changing the thing being compared;
* the false comment is gone (AB3(c)), with a NEGATIVE CONTROL proving the
  probe would have caught it, because a text probe that passes on a string
  that was never there is not evidence of anything;
* the clearance under the name block is constant across all three leadings,
  which is what makes the page a comparison of ONE variable and is WI-U's
  fix doing the work it was built for;
* the §11 gate that claims to police this quantity does not — RECORDED, NOT
  FIXED per §AB4(c), and pinned here so the record cannot rot silently.

LINE BOXES ARE NOT INK, and this file keeps them apart on purpose. A PDF span
bbox runs the face's ascent to its descent whether or not a glyph reaches
either end, so `_spans` returns a LINE-BOX quantity and `_ink_gap` rasterises
to get the other one. WI-V's first pass had a single number labelled "ink"
that was a box, and it produced a sentence — "ink overlaps ink" at 1.06 em —
that measurement then contradicted: the boxes overlap by 0.959 mm and the
letters clear by 1.073. Both are pinned below, because the box figure is the
one that holds for names this composer has not seen and the ink figure is the
one that stops being true the moment the product name gains a descender.
"""
from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import pathlib
import subprocess
import sys
import tokenize

import pytest

from apps.ire import back_panel, compose_dropper
from apps.ire.compose_dropper import _front_typography, compose_dropper_sheet
from apps.ire.container_concept_fidelity import RE_RULED_GEOMETRY_CODES, measure_concept_fidelity
from apps.ire.emitters.pdf_ai import emit_pdf_ai
from apps.ire.graph import Color, Document, Group, Rect, Stroke
from apps.ire.tests.test_back_panel import _BACK_ZONE, _FRONT_NAME_LINES, _FRONT_RECORD, _FRONT_ZONE, _GEOMETRY

#: THE TOOL IS LOADED BY FILE PATH, NOT BY `from tools.wiv_leading_comparison
#: import ...`, and the reason is a measured regression rather than a taste.
#:
#: There are TWO directories named `tools` in this checkout — the project's own
#: `bbrose_design_os/tools/` (NO `__init__.py`, so a NAMESPACE package) and
#: `<git root>/tools/` (HAS one, so a REGULAR package). They are not peers.
#: A regular package beats a namespace package at ANY `sys.path` position, not
#: just an earlier one: the path finder records namespace portions and keeps
#: looking, and a regular package found later still wins. Measured on a
#: two-directory scratch case, because the whole repair turns on it.
#:
#: So `sys.path` ORDER IS NOT A LEVER HERE, and neither is the obvious repair
#: of hoisting the import to module scope to win a race. There is no race to
#: win. `apps/accounts/test_authz_policy.py` puts the git root on the path from
#: inside a test body, and from that moment `tools` means the git root's
#: package for the rest of the process however early we asked. Run alone this
#: file passed 20/20; run in the suite seven tests died on `No module named
#: 'tools.wiv_leading_comparison'`, and putting this root first changes nothing
#: at all. The only lever is `sys.modules`, and taking it is a REGRESSION, not
#: a fix — measured: with `tools` bound here first, `from tools.dip0c import
#: authz` raises `No module named 'tools.dip0c'` and the authz parity test
#: fails instead. Seven red traded for one is still red §AB4(a) does not
#: authorise.
#:
#: §AT5, 2026-08-20 — THE PARAGRAPH ABOVE WAS TRUE WHEN WRITTEN (0695ccb,
#: 2026-08-19) AND ITS CAUSAL CLAIM STOPPED BEING TRUE THE NEXT DAY. `7b77ec2`
#: (WI-3H) added `apps/ire/tests/test_wi3h_reserved_copy.py`, whose line 36 is
#: a MODULE-SCOPE `from tools import reserved_copy`. Measured: at `7b77ec2^`
#: ZERO files under `apps/` had a module-scope `tools` import; at `7b77ec2`
#: there is one. pytest imports every test module during COLLECTION, before any
#: test body runs — so `tools` is now bound as the pytest root's NAMESPACE
#: package before `test_authz_policy.py` gets to insert anything, and a
#: namespace `__path__` recomputation collects only namespace portions, so the
#: insert is a no-op and the git-root package never wins. The two accounts do
#: not conflict: the finder rule above governs an UNBOUND name, and after
#: `7b77ec2` the name is not unbound — `sys.modules['tools'].__path__` answers
#: first and the finder is never consulted. What flipped is which file loses.
#:
#: THE CONCLUSION IS UNCHANGED, AND THIS IS WHY IT IS STRONGER THAN IT WAS.
#: File-path loading plus the borrow is INDIFFERENT to the binding — it
#: consults an entry it installed itself. So the world changed underneath this
#: file on 2026-08-20 and its twenty tests did not notice, while the authz
#: test's order-DEPENDENT insert broke the same day. The argument for the shape
#: here is no longer an argument; it is an outcome.
#:
#: So this loads the file under a PRIVATE name and BORROWS `tools` for the
#: length of the exec. The borrow is not belt-and-braces: the first draft said
#: the loader "binds nothing", the test below disagreed, and the test was
#: right — the tool's own line 63 is `from tools.wim_front_render import ...`,
#: so file-path loading fixes the entry point and leaves the tool's internal
#: import standing in the exact collision it was meant to dodge.
_TOOL_NAME = "_wiv_leading_comparison_byfile"
_ROOT = pathlib.Path(__file__).resolve().parents[3]
_TOOL_PATH = _ROOT / "tools" / "wiv_leading_comparison.py"


def _tool():
    """`tools/wiv_leading_comparison.py`, loaded off disk. See `_TOOL_PATH`.

    The borrow installs a `tools` package whose `__path__` is THIS root's
    directory and nothing else, which is what makes it deterministic: a
    submodule import consults `sys.modules['tools'].__path__` and never
    reaches the path finder, so the regular-package rule above cannot apply.
    Cached under `_TOOL_NAME`, so it happens once per process, and restored in
    a `finally` whether or not the exec raises — a test file that leaves
    `sys.modules` altered on the failure path is a test file that decides
    other apps' results."""
    mod = sys.modules.get(_TOOL_NAME)
    if mod is not None:
        return mod
    borrowed = {k: sys.modules.pop(k) for k in list(sys.modules)
                if k == "tools" or k.startswith("tools.")}
    pkg = importlib.util.module_from_spec(
        importlib.machinery.ModuleSpec("tools", None, is_package=True))
    pkg.__path__ = [str(_ROOT / "tools")]
    sys.modules["tools"] = pkg
    try:
        spec = importlib.util.spec_from_file_location(_TOOL_NAME, _TOOL_PATH)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[_TOOL_NAME] = mod      # before exec, for self-reference
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            del sys.modules[_TOOL_NAME]
            raise
    finally:
        for k in [k for k in sys.modules
                  if k == "tools" or k.startswith("tools.")]:
            del sys.modules[k]
        sys.modules.update(borrowed)
    return mod


K = 72.0 / 25.4
RULED_PT = 9.0
#: Via the NAMED constant, not a bare `25.4 / 72.0`. WI-T's analyser read the
#: literal form as `EM_MM wants mm and got pt` — correct arithmetic it could
#: not see was a conversion, because a bare ratio carries no units and the
#: repository's name for this one does. Written this way the finding is gone
#: rather than classified: an instrument that has to be told which of its own
#: alarms to ignore gets worse every time it is told.
EM_MM = RULED_PT * back_panel.MM_PER_PT

#: The value in the source. Written out in full because §AB3(b) puts the
#: INCUMBENT in the comparison, and a test that pinned a rounded 3.0047 would
#: be pinning something the composer has never emitted.
INCUMBENT = 3.0047244094488192

#: The commit WI-V starts from — WI-U. Pinned, for the same reason WI-U pinned
#: WI-T: a control that reads `HEAD` stops being a control the moment the work
#: lands, and then it agrees with everything.
PRE_WIV = "cd846a4"

#: The exact false sentence, as one contiguous string. It is written here in a
#: form that CANNOT match the replacement comment: the replacement quotes
#: "with tight leading, one visual element" while explaining the repair, and
#: stops there. Including "dominant over everything else" is what makes this
#: probe specific to the claim rather than to the subject.
FALSE_CLAIM = "tight leading, one visual element, dominant over everything else"

SRC = "bbrose_design_os/apps/ire/compose_dropper.py"


def _source_at(commit: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{commit}:{SRC}"], text=True,
        stderr=subprocess.DEVNULL)


def _comments(src: str) -> str:
    """Every COMMENT token, joined. Comments are not in the AST, so this is
    the tokenizer rather than a substring scan of the whole file — the point
    being to look at comments and only at comments, which a grep cannot do."""
    toks = tokenize.generate_tokens(io.StringIO(src).readline)
    return "\n".join(t.string for t in toks if t.type == tokenize.COMMENT)


def _render(em: float, path) -> str:
    """The front at 1:1 and the ruled size, at one leading, emitted to PDF."""
    zone = dict(_FRONT_ZONE, x=0, y=0)
    closure_h = (_GEOMETRY["collar_height_mm"] + _GEOMETRY["bulb_height_mm"]
                 + (_GEOMETRY.get("visible_neck_mm") or 3.0))
    was = compose_dropper.NAME_LEADING_EM
    compose_dropper.NAME_LEADING_EM = em
    try:
        kids, _pl, _lg, zr = _front_typography(
            _GEOMETRY, zone, 3.0, 3.0 - closure_h, 1.0, None,
            prefix="t-", name_min=RULED_PT, name_lines=_FRONT_NAME_LINES,   # §BH68(d): the name, handed in
            **_FRONT_RECORD)     # §BH67(c)2: the record's lines, handed in
    finally:
        compose_dropper.NAME_LEADING_EM = was
    outline = Rect(name="t-zone", x=zr[0], y=zr[1], w=zr[2], h=zr[3],
                   stroke=Stroke(color=Color.from_hex("#B0A0A8"),
                                 width_mm=0.1))
    doc = Document(title="wiv", page_w=zr[2] + 6, page_h=zr[3] + 6,
                   root=Group(name="W", role="decoration",
                              children=[outline] + list(kids)))
    p = str(path / f"wiv_{em:.4f}.pdf")
    emit_pdf_ai(doc, p)
    return p


def _spans(pdf):
    import pymupdf
    d = pymupdf.open(pdf)
    rows = []
    for blk in d[0].get_text("dict")["blocks"]:
        for line in blk.get("lines", []):
            for sp in line.get("spans", []):
                if sp["text"].strip():
                    rows.append((sp["text"].strip(), sp["size"],
                                 [v / K for v in sp["bbox"]]))
    d.close()
    return sorted(rows, key=lambda r: r[2][1])


def _named(rows, prefix):
    return next(r for r in rows if r[0].startswith(prefix))


def _ink_gap(pdf):
    """Millimetres of clear white between the DRAWN LETTERS of the two name
    lines — negative if they interleave. Rasterised, not derived: this is the
    quantity `_spans` cannot report, because a span bbox is the face's line
    box and is the same height for a word with descenders and a word
    without."""
    top, bottom, _n = _tool().ink_bands(pdf)
    return bottom[0] - top[1]


class TestTheFalseCommentIsGoneAndTheProbeCouldHaveCaughtIt:
    """§AB3(c). The comment is wrong TODAY and is fixed today regardless of
    what the render decides.

    The three probes here declare themselves under §Y2(b), which is in force
    repo-wide and fully converted inside `apps/ire`. That matters more than
    usual for this class: §AB3(c)'s subject IS a sentence, so the whole of it
    is source-string guarding, and a reader skimming the names would
    otherwise come away thinking the leading itself was covered here. It is
    not. It is not covered anywhere, and §AB3 is why."""

    def test_source_guard_the_claim_is_absent_from_the_shipping_comments(self):
        """SOURCE-STRING GUARD. Asserts a literal is absent from a source
        file's comment tokens and NOTHING about behaviour — no artwork
        changes if this passes or fails, and it must never be cited as
        coverage of the leading (§Y2(c))."""
        from pathlib import Path
        src = Path(compose_dropper.__file__).read_text()
        assert FALSE_CLAIM not in _comments(src)

    def test_source_guard_negative_control_the_claim_was_there_before(self):
        """SOURCE-STRING GUARD, and the premise of the one above asserted
        rather than assumed — it asserts a literal is PRESENT in a source
        file at a pinned commit, and nothing about behaviour.

        The census does not flag this one, because the read goes through
        `git show` rather than the filesystem and the detector will not
        follow a subprocess. It declares itself anyway: §Y2(b)'s subject is
        what a test PROVES, not how it got the bytes, and a guard that
        escapes the instrument on a technicality is exactly the guard whose
        name will mislead somebody later.

        Without it the test above passes identically on a file that never
        contained the sentence, on a typo in the sentence, and on a repo
        where someone deleted the whole function — three states it must not
        be unable to tell apart."""
        assert FALSE_CLAIM in _comments(_source_at(PRE_WIV))

    def test_source_guard_the_subject_survives_so_this_is_a_repair(self):
        """SOURCE-STRING GUARD. Asserts two literals are present in a source
        file's comments and nothing about behaviour.

        The phrase should survive as HISTORY: deleting the discussion along
        with the claim would hide that the artwork does not meet the §11
        spec, and that mismatch is the finding, not the embarrassment."""
        from pathlib import Path
        comments = _comments(Path(compose_dropper.__file__).read_text())
        assert "tight leading" in comments
        assert "§AB3(c)" in comments

    def test_the_claim_is_contradicted_by_measurement_not_by_taste(self,
                                                                   tmp_path):
        """'Tight' was not a matter of opinion here, and it is not close
        enough for the box/ink distinction to rescue it: at the incumbent the
        two lines clear each other by more than a whole line of type on the
        stricter of the two measurements."""
        pdf = _render(INCUMBENT, tmp_path)
        rows = _spans(pdf)
        rose, dam = _named(rows, "Rose"), _named(rows, "Damascena")
        gap = dam[2][1] - rose[2][1]
        line_box = rose[2][3] - rose[2][1]
        assert gap == pytest.approx(9.540, abs=0.001)
        assert gap == pytest.approx(INCUMBENT * EM_MM, abs=1e-6)
        # white space between the two LINE BOXES, in whole lines of type.
        # The boxes are the tighter reading — the letters clear by more —
        # so a claim of "tight" fails against the number kinder to it.
        assert (gap - line_box) / line_box > 1.2
        assert _ink_gap(pdf) > gap - line_box


class TestTheLineBoxAndTheInkAreDifferentQuantities:
    """The correction WI-V's own measurement forced, pinned so it cannot be
    lost again. At the tight end of §AB3(a)'s comparison the two disagree
    about whether anything is wrong, and the difference is not a rounding
    detail — it is 2.0 mm, two thirds of an em."""

    def test_at_the_tight_leading_the_boxes_overlap_and_the_letters_do_not(
            self, tmp_path):
        pdf = _render(1.06, tmp_path)
        rows = _spans(pdf)
        rose, dam = _named(rows, "Rose"), _named(rows, "Damascena")
        assert rose[2][3] - dam[2][1] == pytest.approx(0.959, abs=0.002)
        assert _ink_gap(pdf) == pytest.approx(1.073, abs=0.005)

    def test_the_gap_between_them_is_the_face_not_the_render(self, tmp_path):
        """Two thirds of an em of difference, and it is structural: the box
        pays for a descent `Rose` never uses and an ascent `Damascena` only
        reaches with a cap. Asserted as a SIZE so that a change of face —
        which would move it — cannot pass as noise."""
        pdf = _render(1.06, tmp_path)
        rows = _spans(pdf)
        rose, dam = _named(rows, "Rose"), _named(rows, "Damascena")
        box = rose[2][3] - dam[2][1]
        assert _ink_gap(pdf) - (-box) == pytest.approx(2.032, abs=0.01)
        assert (_ink_gap(pdf) + box) / EM_MM == pytest.approx(0.64, abs=0.02)

    @pytest.mark.parametrize("em", [1.06, 2.0, INCUMBENT])
    def test_the_ink_never_actually_touches_at_any_of_the_three(self, em,
                                                                tmp_path):
        """Recorded as a fact about THESE TWO WORDS and nothing wider.
        §AB2(f) has the composer setting names it has not seen; a name with a
        descender on line one closes 1.073 mm without the leading moving, so
        this test would go on passing while the statement it looks like it is
        making stopped being true. That is what the box measurement above is
        for, and why both live here."""
        assert _ink_gap(_render(em, tmp_path)) > 0


class TestTheComparisonExistsAtTrueScale:
    """§AB3(a): 1.06, 2.0, 3.0047 em, at 9.0 pt, at s=1.0."""

    @pytest.mark.parametrize("em,expected_mm", [
        (1.06, 3.366), (2.0, 6.350), (INCUMBENT, 9.540)])
    def test_each_leading_renders_at_the_ruled_size(self, em, expected_mm,
                                                    tmp_path):
        rows = _spans(_render(em, tmp_path))
        rose, dam = _named(rows, "Rose"), _named(rows, "Damascena")
        assert rose[1] == pytest.approx(RULED_PT, abs=1e-6)
        assert dam[1] == pytest.approx(RULED_PT, abs=1e-6)
        assert dam[2][1] - rose[2][1] == pytest.approx(expected_mm, abs=0.001)


class TestTheClearanceBelowTheNameIsTheSameInAllThree:
    """This is the property that makes the page a comparison of ONE variable,
    and it is WI-U's fix earning its keep: before it, the support line sat at
    a fraction of the drawn zone while the block above was physical, so the
    leading and the collision moved together."""

    def test_damascena_to_night_repair_oil_does_not_depend_on_the_leading(
            self, tmp_path):
        seen = []
        for em in (1.06, 2.0, INCUMBENT):
            rows = _spans(_render(em, tmp_path))
            dam, nig = _named(rows, "Damascena"), _named(rows, "N I G")
            seen.append(nig[2][1] - dam[2][3])
        assert max(seen) - min(seen) < 1e-5, (
            "the support stack must follow the name block, not the zone")
        assert all(v == pytest.approx(1.518, abs=0.001) for v in seen)


class TestTheSettingIsUnmovedByBeingCompared:
    """§AB3(b). Producing the comparison must not change the thing compared.

    §AC1 RULED AND THE SETTING IS NOW 2.0 em, so this class no longer asserts
    that the shipping value IS the incumbent — it asserts that RENDERING A
    COMPARISON DOES NOT CHANGE IT, which is what §AB3(b) was always about and
    is the property that survives a ruling. Both readings were true until
    §AC1; only one of them was the point, and pinning the wrong one is how a
    test starts failing for a reason unrelated to its own subject.

    The incumbent is still asserted to EXIST at its exact float, under
    §AC1(f), because `tools/wiv_leading_comparison.py` renders it as one of
    the three panels and a comparison against a rounded 3.0047 would be a
    comparison against something the composer never emitted.
    """

    def test_the_module_constant_is_the_ruled_value_and_the_incumbent_survives(
            self):
        assert compose_dropper.NAME_LEADING_EM == 2.0
        assert compose_dropper.NAME_LEADING_INCUMBENT_EM == INCUMBENT

    def test_the_tools_swap_restores_even_when_the_render_raises(self):
        """Reads the shipping value BEFORE the swap rather than naming it.

        Written as `== INCUMBENT` this test failed on §AC1 — not because the
        restore broke, but because the literal it restored TO had been ruled.
        A restore test that names the value it expects is testing the ruling;
        this one tests the restore.
        """
        was = compose_dropper.NAME_LEADING_EM
        leading = _tool().leading
        with pytest.raises(RuntimeError):
            with leading(1.06):
                assert compose_dropper.NAME_LEADING_EM == 1.06
                raise RuntimeError("boom")
        assert compose_dropper.NAME_LEADING_EM == was


class TestTheGateThatClaimsToPoliceThisDoesNot:
    """RECORDED, NOT FIXED (§AB4(c)). `container_concept_fidelity.py:461`
    compares a MILLIMETRE gap against a POINT size, and separately has no
    lower bound at all, so a name block can collide with itself and pass.

    `_axis` composes the WHOLE SHEET rather than the typography fragment the
    rest of this file renders, and that is not incidental. The gate returns
    EARLY — at line 128, on the first axis — when the material objects are
    absent, so a fragment never reaches §11 at all and `axes` comes back one
    item long. The first version of this class asserted MEASURED_PASS on a
    report that had never run the rule; the assertion failed loudly, but it
    would have been equally wrong had it been written to pass. So the gate is
    measured HERE on the document the pipeline actually hands it
    (`targets/container/__init__.py:1276`), and the finding below is about
    the shipping configuration rather than about a stub."""

    def _report(self, em):
        was = compose_dropper.NAME_LEADING_EM
        compose_dropper.NAME_LEADING_EM = em
        try:
            doc = compose_dropper_sheet(
                _GEOMETRY, zones=[_FRONT_ZONE, _BACK_ZONE],
                reference_path=None, logo_path=None,
                product_name="Rose Damascena", sku="X",
                back_sections=[{"heading": "P", "text": "x"}],
                revision_status="TEST", drawing_source="PARAMETRIC")   # §BH49(a): this evidence measures the PARAMETRIC composition (the typed numbers); the product path draws M3 by construction
        finally:
            compose_dropper.NAME_LEADING_EM = was
        return measure_concept_fidelity(doc, _GEOMETRY)

    def _axis(self, em):
        return next(a for a in self._report(em)["axes"]
                    if a["axis"] == "product_name_unified_block")

    def test_a_block_set_looser_than_the_ruled_leading_is_refused(self):
        """§BH54(b) (o) — THE TEST THAT FAILS BEFORE AND PASSES AFTER. The sheet is composed with its name set at the
        old incumbent and measured under the composer's ruled constant. While the check compared millimetres with
        points its ceiling was 4.11 em and this block PASSED; comparing em with em it is refused, by the code the axis
        has always named. No assertion here says which leading is right: it is refused for being LOOSER than
        whatever `NAME_LEADING_EM` the composer reads."""
        from apps.ire.container_concept_fidelity import TYPOGRAPHY_NOT_PRESERVED
        assert INCUMBENT > compose_dropper.NAME_LEADING_EM                 # the premise, stated
        report = self._report(INCUMBENT)
        axis = next(a for a in report["axes"] if a["axis"] == "product_name_unified_block")
        assert axis["state"] == "MEASURED_FAIL" and TYPOGRAPHY_NOT_PRESERVED in report["failures"]
        assert axis["value"]["leading_em"] == pytest.approx(INCUMBENT, abs=1e-3)
        assert axis["value"]["units"] == {"leading": "mm", "size": "pt"}
        # and at the ruled leading itself it passes — the fix refuses nothing he ruled
        ruled = self._axis(compose_dropper.NAME_LEADING_EM)
        assert ruled["state"] == "MEASURED_PASS"
        assert ruled["value"]["leading_em"] == pytest.approx(compose_dropper.NAME_LEADING_EM, abs=1e-4)

    # [§BH54(b) (o): this was parametrized over 1.06, 2.0 AND the incumbent 3.0047 — "silent at every leading".
    # Comparing like with like, the incumbent is refused (the test above); at and under the ruled leading the gate
    # is as silent as it was, the COLLIDING 1.06 em included: the axis is still an upper bound with no floor.]
    @pytest.mark.parametrize("em", [1.06, 2.0])
    def test_the_whole_gate_is_silent_at_every_leading_including_a_colliding_one(
            self, em):
        report = self._report(em)
        assert next(a for a in report["axes"]
                    if a["axis"] == "product_name_unified_block"
                    )["state"] == "MEASURED_PASS"
        # and nothing else catches it either: the sheet whose product name
        # overlaps itself by 0.959 mm is a clean pass on every axis there is
        # -- §BH50(a): every axis but the five geometry rules re-ruled to the M3
        # design, which this PARAMETRIC (typed-number) bottle now fails; none of
        # the five reads the type, so the claim about the type stands
        assert set(report["failures"]) <= set(RE_RULED_GEOMETRY_CODES)

    def test_it_passed_because_the_units_were_wrong_in_its_own_favour_and_no_longer_does(self):
        """Its target string says 'leading <=1.45xsize'. At the incumbent the
        leading is 3.0047 em, more than double that, and it passes — because
        the 9.540 mm gap is being compared against 9.0 pt x 1.45 = 13.05,
        which is a number in the wrong unit and 2.8x too large.

        [§BH54(b) (o), 2026-09-19 — "THE HERO-LEADING CHECK IS A DEFECT, not a
        question … Fix it to compare like with like." The paragraph above is
        what WI-V found, kept as the history it is; the two arithmetic lines
        below still say what the check COMPUTED. What it computes now is the
        same gap and the same size, in em, against the ruled leading: refused.]"""
        axis = self._axis(INCUMBENT)
        assert axis["value"]["leading"] == pytest.approx(9.54, abs=0.01)
        assert axis["value"]["size"] == pytest.approx(RULED_PT, abs=1e-6)
        assert 9.54 <= RULED_PT * 1.45          # what it computed: mm vs pt
        assert not INCUMBENT <= 1.45            # what it said it computed
        assert axis["value"]["leading_em"] == pytest.approx(INCUMBENT, abs=1e-3)      # what it computes now
        assert axis["state"] == "MEASURED_FAIL" and "the ruled" in axis["target"]

    def test_and_fixing_only_the_units_would_still_admit_a_set_past_the_floor(
            self, tmp_path):
        """So the tool's `em<=1.45` column is NOT the repair. The rule is an
        upper bound with no floor at all, and the face's metric floor at
        9.0 pt is 1.362 em — measured, not assumed — so 1.06 em sets the two
        lines inside each other's line boxes and still satisfies `<=1.45` in
        either unit.

        [§BH54(b) (o): the units ARE fixed now, and this is still so — the
        axis is an upper bound with no floor. The floor is §AC1's ("the metric
        floor binds"), guarded on the composer's side.]"""
        pdf = _render(1.06, tmp_path)
        rows = _spans(pdf)
        rose, dam = _named(rows, "Rose"), _named(rows, "Damascena")
        box_overlap = rose[2][3] - dam[2][1]
        assert box_overlap == pytest.approx(0.959, abs=0.002)
        assert 1.06 <= 1.45
        assert self._axis(1.06)["state"] == "MEASURED_PASS"


class TestTheToolLoadsUnderTheNameCollisionThatBrokeIt:
    """The seven-failure import bug, pinned as a NEGATIVE CONTROL (§AB0(c)).

    The failure was invisible to every way of running this file except the
    canonical one: 20/20 alone, 13/20 in the suite, because the poisoning is
    done by a DIFFERENT app's test at run time. A control that only reproduces
    under a 600-second whole-suite run is not a control anybody will use, so
    the collision is staged here directly and cheaply.

    Both directions are asserted, because the repair has to survive being on
    either side of the race — and the direction that made me discard the
    obvious fix is the second one.
    """

    @contextlib.contextmanager
    def _clean_tools(self):
        """Run the body with no `tools*` in `sys.modules` and no cached tool,
        then put back exactly what was there.

        Surgical, not `sys.modules.clear()` — the first draft cleared and
        re-`update`d, and the next test died inside numpy with `cannot load
        module more than once per process`. Extension modules do not survive
        being evicted and reinstated, so a control that wrecks the process to
        stage its collision is not a control."""
        touched = {k: sys.modules.pop(k) for k in list(sys.modules)
                   if k == "tools" or k.startswith("tools.")}
        cached = sys.modules.pop(_TOOL_NAME, None)     # force a real exec
        saved_path = list(sys.path)
        try:
            yield
        finally:
            sys.path[:] = saved_path
            for k in [k for k in sys.modules
                      if k == "tools" or k.startswith("tools.")]:
                del sys.modules[k]
            sys.modules.update(touched)
            if cached is not None:
                sys.modules[_TOOL_NAME] = cached

    def _poisoned(self):
        """The GIT ROOT on the path and `tools` bound to the regular package
        there. Undone by `_clean_tools` — this file does not get to decide the
        binding for the rest of the session.

        This used to name its source, `apps/accounts/test_authz_policy.py:207`,
        the in-body `sys.path.insert` that produced exactly this state. §AT
        moved that check into a subprocess, so NO test in this repo produces
        the state any more and line 207 is now a comment. The reference is
        removed rather than renumbered: a guard that names a caller stops being
        a guard the day the caller changes, and this helper already CONSTRUCTS
        the hostile state rather than waiting for someone else to."""
        app_root = str(pathlib.Path(__file__).resolve().parents[3])   # the ONE tools package's root since 2026-10-04
        sys.path.insert(0, app_root)
        importlib.import_module("tools.dip0c")

    def test_the_tool_still_loads_when_tools_is_bound_to_the_other_root(self):
        """`_TOOL_NAME` is EVICTED first, and that line is the test. Without
        it `_tool()` returns the module some earlier test already cached, the
        poisoning never touches an import, and the assertion passes on a
        premise that did not run — the same way this sprint's §11 gate class
        first 'proved' MEASURED_PASS on an axis the report never emitted."""
        with self._clean_tools():
            self._poisoned()
            # since the clean-up of 2026-10-04 there is ONE `tools` package: binding it through dip0c no longer hides
            # the tool, which is exactly the hazard gone; the tool still loads either way
            assert importlib.util.find_spec("tools.wiv_leading_comparison") is not None
            assert _tool().INK_ZOOM == 24.0

    def test_and_it_hands_back_the_binding_it_borrowed(self):
        """The direction that killed the module-scope fix. Whoever binds
        `tools` first wins it for the process, so a repair that wins the race
        is a repair that makes `tools.dip0c` unimportable and MOVES the
        failure. Asserted by importing the other root's submodule after the
        tool has loaded — the thing that raised `No module named
        'tools.dip0c'` when this was tried the obvious way."""
        with self._clean_tools():
            assert _tool().INK_ZOOM == 24.0
            assert "tools" not in sys.modules          # handed back
            self._poisoned()                           # must still work
            assert importlib.import_module("tools.dip0c") is not None
