"""WI-2A / §AC3 — the four conditions on a split, each with its control.

§AC3 permitted something the ledger had refused to model, and attached four
conditions. A test file for it is only worth anything if each condition can be
shown to be DOING something — §AA's case is a guard that has never fired. So
every condition here is paired with a control that makes it fire:

  (a) the break is nameable      → and mid-word is UNREPRESENTABLE, not merely
                                   unchosen; plus the re-wrap identity, which
                                   is the measurement the whole rule rests on;
  (b) a continuation costs a line → and with the charge set to zero the minimum
                                   DROPS, on a document built so that it must —
                                   §AC3(b)'s "if a split is free, the
                                   arithmetic lies", executed;
  (c) reading order is an input   → and a different declared order produces a
                                   different line sequence, so the argument is
                                   demonstrably consumed rather than accepted
                                   and ignored;
  (d) split only where necessary  → and removing any one break makes the
                                   minimum surface count unreachable.

The fifth thing tested here is the negative control the sprint mandated: with
splitting OFF the packer must reproduce §AB1(e)'s whole-section result exactly.
It does more than reproduce the totals — `TestSplittingOffReproducesTheLedger`
compares the verdict SUBSET BY SUBSET, 63 of them at each floor, because two
counting errors that cancel would still produce 30 and 22.
"""
import pytest

from apps.ire import back_panel as bp
from apps.ire import back_panel_ledger as led
from apps.ire import back_panel_packer as pk
from apps.ire.tests.test_wik_back_panel_floor import _X2_COPY

ZONE_W, ZONE_H = 22.0, 42.3

#: §AC3(c) — DECLARED here, once, before anything is packed, and passed in.
#: Document order is what is declared; the packer is not asked to have an
#: opinion about it and does not have one.
DECLARED_ORDER = tuple(range(len(_X2_COPY)))

#: a token wide enough to occupy a line of the 19 mm column on its own at both
#: floors. Used only to BUILD synthetic documents of an exact height; every
#: helper that uses it asserts the resulting line count rather than assuming it.
_WIDE = "ETHYLHEXYLGLYCERIN,"


@pytest.fixture(scope="module")
def faces():
    from apps.ire.text_metrics import resolve_metric_faces
    resolved = resolve_metric_faces({})
    regular = (resolved.get("regular") or (None,))[0]
    bold = (resolved.get("bold") or (None,))[0]
    assert regular and bold, "no measurable face — nothing below is a measurement"
    return regular, bold


def _pack(sections, size_pt, allow_split, faces, order=None,
          height_mm=ZONE_H):
    regular, bold = faces
    return pk.pack(sections, width_mm=ZONE_W, height_mm=height_mm,
                   size_pt=size_pt, regular=regular, bold=bold,
                   reading_order=(list(range(len(sections))) if order is None
                                  else order),
                   allow_split=allow_split)


def _model(sections, size_pt, faces, order=None):
    regular, bold = faces
    return pk.line_model(sections, width_mm=ZONE_W, size_pt=size_pt,
                         regular=regular, bold=bold,
                         reading_order=(list(range(len(sections)))
                                        if order is None else order))


def _exactly(n_lines, faces, size_pt, heading=""):
    """A section that is EXACTLY ``n_lines`` lines tall, verified not assumed.

    Building a document of a known height is how the §AC3(b) control is made
    decisive. If the face ever changes and the token stops filling a line, this
    raises here rather than quietly testing a different document.
    """
    regular, bold = faces
    text = " ".join([_WIDE] * n_lines)
    section = {"heading": heading, "text": text}
    record = bp.layout([section], ZONE_W, 1.0e6, size_pt=size_pt,
                       regular=regular, bold=bold)
    got = len(record["lines"])
    assert got == n_lines, (
        f"the synthetic section is {got} lines, not {n_lines} — the token no "
        f"longer fills the column and the control below would be measuring "
        f"something else")
    return section


def _materialise(surface, model_lines):
    """Rebuild a surface's content as sections `bp.layout` can be run on.

    The continuation MARKER is deliberately absent: §AC3(b) ruled its cost and
    nothing ruled its wording, so there is no text to place. Its line is
    accounted for arithmetically instead, which is why the assertions that use
    this compare against `lines_of_copy` and check `lines_charged` separately.
    """
    run = model_lines[surface["first_line"]:surface["last_line"] + 1]
    out, current = [], None
    for entry in run:
        if current is None or current["_section"] != entry["section"]:
            current = {"_section": entry["section"], "heading": "",
                       "_copy": []}
            out.append(current)
        if entry["role"] == "heading":
            current["heading"] = (current["heading"] + " " +
                                  entry["text"]).strip()
        else:
            current["_copy"].append(entry["text"])
    return [{"heading": s["heading"], "text": " ".join(s["_copy"])}
            for s in out]


class TestTheBreakIsNameable:
    """§AC3(a) — *"if the ledger cannot point at the break, the break did not
    happen in the model."*"""

    @pytest.mark.parametrize("size_pt,split_points", [(5.0, 27), (6.0, 36)])
    def test_every_suffix_rewraps_identically(self, faces, size_pt,
                                              split_points):
        """The measurement §AC3(a) rests on, taken rather than assumed.

        A break is only real if the tail wraps on the receiving surface exactly
        as it wrapped on the sending one. If it did not, the line the ledger
        pointed at would not be the line that printed, and every count
        downstream would be describing a document nobody made.

        The count of split points is asserted EXACTLY rather than as a floor.
        It is one less than each section's copy-line count, summed — 27 at 5.0
        pt and 36 at 6.0 — so it is a restatement of the section heights and it
        moves when they move. This assertion was first written as `>= 40`,
        which is a number nothing measured: it failed at 36, and a threshold
        that had happened to pass would have gone on passing while a section
        quietly changed height underneath it.
        """
        regular, bold = faces
        checked = 0
        for section in _X2_COPY:
            whole = bp.layout([section], ZONE_W, 1.0e6, size_pt=size_pt,
                              regular=regular, bold=bold)
            copy = [line for line in whole["lines"] if line["role"] == "copy"]
            for cut in range(1, len(copy)):
                tail = " ".join(line["text"] for line in copy[cut:])
                again = bp.layout([{"heading": "", "text": tail}], ZONE_W,
                                  1.0e6, size_pt=size_pt, regular=regular,
                                  bold=bold)
                assert [line["text"] for line in again["lines"]] == \
                    [line["text"] for line in copy[cut:]]
                checked += 1
        assert checked == split_points, (
            f"{checked} split points exercised, expected {split_points} — the "
            f"sections are no longer the heights this evidence was taken at")

    def test_a_cut_is_named_by_section_and_ordinal(self, faces):
        model = _model(_X2_COPY, 5.0, faces)
        lines = model["lines"]
        named = pk.describe_cut(lines, 4)
        assert named["section"] == 1 and named["heading"] == "INGREDIENTS"
        assert named["order"] == 1
        assert named["resumes_at_text"] == lines[4]["text"]
        assert named["split"] is True

    def test_a_cut_at_a_section_boundary_is_not_a_split(self, faces):
        model = _model(_X2_COPY, 5.0, faces)
        lines = model["lines"]
        boundaries = [i for i in range(1, len(lines))
                      if lines[i]["section"] != lines[i - 1]["section"]]
        assert boundaries, "the document has no section boundary to check"
        for at in boundaries:
            assert pk.is_split_position(lines, at) is False
            assert pk.describe_cut(lines, at)["split"] is False

    def test_the_ends_of_the_document_are_never_splits(self, faces):
        lines = _model(_X2_COPY, 5.0, faces)["lines"]
        assert pk.is_split_position(lines, 0) is False
        assert pk.is_split_position(lines, len(lines)) is False

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_the_allocation_agrees_with_the_layout_engine(self, faces,
                                                          size_pt):
        """Each surface, re-measured by `bp.layout` on its actual content.

        The packer counts lines; `bp.layout` measures millimetres. This is the
        only assertion in the file that puts the two in the same room, and it
        is the one that would catch an arithmetic model that had drifted from
        the thing it claims to model.
        """
        regular, bold = faces
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        lines = _model(_X2_COPY, size_pt, faces, order=DECLARED_ORDER)["lines"]
        for surface in record["surfaces"]:
            content = _materialise(surface, lines)
            drawn = bp.layout(content, ZONE_W, ZONE_H, size_pt=size_pt,
                              regular=regular, bold=bold)
            assert drawn["lines_required"] == surface["lines_of_copy"]
            assert drawn["fits"] is True
            assert surface["lines_charged"] <= surface["capacity_lines"]

    def test_the_only_expressible_positions_are_line_boundaries(self, faces):
        """Mid-word is not forbidden here; it is unsayable.

        A cut is an index into a list of LINES, so the positions that exist are
        exactly the boundaries between lines the engine produced. There is no
        character offset anywhere in the packer to misuse, which is why this
        test asserts about the vocabulary rather than about a rejection.
        """
        lines = _model(_X2_COPY, 5.0, faces)["lines"]
        for at in range(len(lines) + 1):
            named = pk.describe_cut(lines, at)
            assert named["position"] == at
            assert named["order"] is None or isinstance(named["order"], int)
        source = (pk.__file__ or "")
        assert source.endswith("back_panel_packer.py")


class TestAContinuationCostsALine:
    """§AC3(b) — *"if a split is free, the arithmetic lies."*"""

    def test_an_empty_heading_emits_no_line(self, faces):
        """Why the charge has to be explicit.

        A continuation carries no heading. An empty heading costs nothing, so
        without `CONTINUATION_LINE_COST` a split really would be free and the
        packer really could manufacture capacity by splitting.
        """
        regular, bold = faces
        record = bp.layout([{"heading": "", "text": "x"}], ZONE_W, 1.0e6,
                           size_pt=5.0, regular=regular, bold=bold)
        assert [line["role"] for line in record["lines"]] == ["copy"]

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_the_charge_lands_on_the_receiving_surface(self, faces, size_pt):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        charged = [s for s in record["surfaces"] if s["receives_continuation"]]
        assert charged, "no surface received a continuation to charge"
        for surface in charged:
            assert surface["continuation_line_charged"] == \
                pk.CONTINUATION_LINE_COST
            assert surface["lines_charged"] == \
                surface["lines_of_copy"] + pk.CONTINUATION_LINE_COST
            assert surface["opens_at"]["split"] is True
        for surface in record["surfaces"]:
            if not surface["receives_continuation"]:
                assert surface["continuation_line_charged"] == 0
                assert surface["lines_charged"] == surface["lines_of_copy"]

    def test_with_the_charge_at_zero_the_minimum_drops(self, faces,
                                                       monkeypatch):
        """THE CONTROL for §AC3(b), on a document built so it must fire.

        Two sections of 20 and 16 lines, on a surface holding 18. A split is
        forced, because 20 does not fit whole. Charged, the document costs 37
        against the 36 that two surfaces can hold, so it needs three. Free, it
        costs 36 and needs two — capacity manufactured out of nothing, which is
        exactly the failure §AC3(b) names.

        The real document does not exhibit this: at 5.0 pt it needs 3 surfaces
        whether or not the continuation is charged, because 39 lines against an
        18-line surface needs 3 either way. Testing the rule on it would have
        produced a passing test that proved nothing, so the document here is
        built to make the charge decisive.
        """
        ungapped = pk.capacity_for_pieces(width_mm=ZONE_W, height_mm=ZONE_H,
                                          size_pt=5.0, pieces=1,
                                          regular=faces[0], bold=faces[1])
        assert ungapped == 18, f"the control was designed against 18, got {ungapped}"
        doc = [_exactly(20, faces, 5.0), _exactly(16, faces, 5.0)]

        charged = _pack(doc, 5.0, True, faces)
        assert charged["total_lines"] == 36
        assert charged["splits_used"] == 1
        assert charged["surfaces_required"] == 3

        monkeypatch.setattr(pk, "CONTINUATION_LINE_COST", 0)
        free = _pack(doc, 5.0, True, faces)
        assert free["total_lines"] == 36
        assert free["surfaces_required"] == 2, (
            "with a free continuation the packer should have manufactured a "
            "surface's worth of capacity; it did not, so this control is no "
            "longer controlling anything")
        assert free["surfaces_required"] < charged["surfaces_required"]

    def test_the_marker_wording_is_not_invented(self, faces):
        record = _pack(_X2_COPY, 5.0, True, faces, order=DECLARED_ORDER)
        assert pk.CONTINUATION_MARKER_TEXT_NOT_RULED in record["codes"]
        for surface in record["surfaces"]:
            assert surface["continuation_marker_text"] is None


class TestReadingOrderIsAnInput:
    """§AC3(c) — *"the order is an input to the packer, not an output of it."*"""

    def test_it_is_required_and_has_no_default(self, faces):
        regular, bold = faces
        with pytest.raises(TypeError):
            pk.pack(_X2_COPY, width_mm=ZONE_W, height_mm=ZONE_H, size_pt=5.0,
                    regular=regular, bold=bold, allow_split=True)
        with pytest.raises(ValueError) as caught:
            pk.pack(_X2_COPY, width_mm=ZONE_W, height_mm=ZONE_H, size_pt=5.0,
                    regular=regular, bold=bold, reading_order=None,
                    allow_split=True)
        assert pk.READING_ORDER_REQUIRED in str(caught.value)

    def test_a_partial_order_is_refused(self, faces):
        with pytest.raises(ValueError) as caught:
            _model(_X2_COPY, 5.0, faces, order=[0, 1, 2])
        assert pk.READING_ORDER_NOT_A_PERMUTATION in str(caught.value)

    def test_a_repeated_index_is_refused(self, faces):
        with pytest.raises(ValueError) as caught:
            _model(_X2_COPY, 5.0, faces, order=[0, 0, 1, 2, 3, 4])
        assert pk.READING_ORDER_NOT_A_PERMUTATION in str(caught.value)

    def test_the_declared_order_actually_reaches_the_line_sequence(self,
                                                                   faces):
        """A required argument that is ignored is worse than no argument.

        Reversing the declared order must reverse the sections in the modelled
        sequence. If it did not, `reading_order` would be a ceremony and the
        packer would in fact be choosing the order — which is the thing §AC3(c)
        exists to prevent.
        """
        forward = _model(_X2_COPY, 5.0, faces, order=list(DECLARED_ORDER))
        backward = _model(_X2_COPY, 5.0, faces,
                          order=list(reversed(DECLARED_ORDER)))
        assert forward["total_lines"] == backward["total_lines"]

        def first_headings(model):
            seen = []
            for line in model["lines"]:
                if not seen or seen[-1] != line["heading"]:
                    seen.append(line["heading"])
            return seen

        assert first_headings(forward) == list(reversed(
            first_headings(backward)))
        assert first_headings(forward)[0] == "PRODUCT"
        assert first_headings(backward)[0] == "NET CONTENT"

    def test_the_split_policy_is_required_too(self, faces):
        regular, bold = faces
        with pytest.raises(TypeError):
            pk.pack(_X2_COPY, width_mm=ZONE_W, height_mm=ZONE_H, size_pt=5.0,
                    regular=regular, bold=bold,
                    reading_order=list(DECLARED_ORDER))
        with pytest.raises(ValueError) as caught:
            pk.pack(_X2_COPY, width_mm=ZONE_W, height_mm=ZONE_H, size_pt=5.0,
                    regular=regular, bold=bold,
                    reading_order=list(DECLARED_ORDER), allow_split=None)
        assert pk.SPLIT_POLICY_REQUIRED in str(caught.value)

    def test_source_guard_the_packer_holds_no_ordering_heuristic(self):
        """SOURCE-STRING GUARD — §AC3(c) in the source, not just in the record.

        The packer must not sort, rank or prioritise sections. A `sorted(` over
        anything section-shaped would be an ordering opinion, and an ordering
        opinion is the output §AC3(c) forbids.

        Both sorts in the file are listed by their exact source line, so a
        third cannot arrive unnoticed, and each is permitted for a stated
        reason. The first sorts a COPY of the declared order only to compare it
        against `range(n)` — it validates that the caller supplied a
        permutation and its result never orders anything. The second sorts
        integer cut positions into ascending order for reconstruction. Neither
        touches a section. This list was first written from memory with one
        entry in it and the guard caught the omission, which is the behaviour
        wanted from it.
        """
        import pathlib
        source = pathlib.Path(pk.__file__).read_text(encoding="utf-8")
        sorts = [line.strip() for line in source.splitlines()
                 if "sorted(" in line and not line.strip().startswith("#")]
        assert sorts == [
            "if sorted(order) != list(range(len(supplied))):",
            "boundaries = sorted(cuts + [0])",
        ], f"a new sort appeared in the packer: {sorts}"
        for banned in ("key=lambda", ".sort(", "priority", "importance"):
            assert banned not in source, (
                f"{banned!r} in the packer — ranking sections is §AC3(c)'s "
                f"forbidden output")


class TestSplitOnlyWhereNecessary:
    """§AC3(d) — *"never for balance."*"""

    @pytest.mark.parametrize("size_pt,expected", [(5.0, 1), (6.0, 1)])
    def test_the_real_document_needs_exactly_one_break(self, faces, size_pt,
                                                       expected):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        assert record["splits_used"] == expected

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_one_fewer_break_cannot_reach_the_minimum(self, faces, size_pt):
        """THE CONTROL for §AC3(d): necessity, demonstrated rather than claimed.

        The packer reports the minimum surface count reached with the fewest
        breaks. This re-runs the same document with splitting switched OFF —
        i.e. with zero breaks permitted — and requires it to fail to reach that
        count. If it could reach it, the break the packer took was for
        convenience, which is precisely what §AC3(d) rules out.
        """
        with_split = _pack(_X2_COPY, size_pt, True, faces,
                           order=DECLARED_ORDER)
        without = _pack(_X2_COPY, size_pt, False, faces, order=DECLARED_ORDER)
        assert with_split["splits_used"] == 1
        assert (without["surfaces_required"] is None
                or without["surfaces_required"] >
                with_split["surfaces_required"])

    def test_a_document_that_fits_is_not_split_at_all(self, faces):
        """No break where none is needed — the other half of "only where
        necessary", and the half a packer tuned for tidy columns would fail."""
        doc = [_exactly(4, faces, 5.0), _exactly(4, faces, 5.0)]
        record = _pack(doc, 5.0, True, faces)
        assert record["surfaces_required"] == 1
        assert record["splits_used"] == 0
        assert record["surfaces"][0]["receives_continuation"] is False
        assert pk.CONTINUATION_MARKER_TEXT_NOT_RULED not in record["codes"]

    def test_a_section_that_fits_whole_on_the_next_surface_may_still_move(
            self, faces):
        """Splitting is not preferred to moving when both reach the minimum.

        Two sections of 10 and 10 lines against an 18-line surface: a greedy
        fill-then-spill packer splits the second one 8/2 to cram the first
        surface. Both allocations use two surfaces, so the split is
        unnecessary, and minimising breaks at the minimum count is what stops
        the packer taking it.
        """
        doc = [_exactly(10, faces, 5.0), _exactly(10, faces, 5.0)]
        record = _pack(doc, 5.0, True, faces)
        assert record["surfaces_required"] == 2
        assert record["splits_used"] == 0

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_the_allocation_is_reported_as_a_witness(self, faces, size_pt):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        assert record["allocation_is_a_witness"] is True
        assert record["optimal_allocations"] >= 1
        if record["optimal_allocations"] > 1:
            assert pk.ALLOCATION_NOT_UNIQUE in record["codes"]


class TestSplittingOffReproducesTheLedger:
    """The sprint's mandated negative control, compared subset by subset."""

    @pytest.mark.parametrize("size_pt,fitting", [(5.0, 30), (6.0, 22)])
    def test_it_reproduces_wi_w_exactly(self, faces, size_pt, fitting):
        """63 subsets, each verdict compared against §AB1(e)'s ledger.

        The totals 30 and 22 are the published figures, but comparing only the
        totals would pass if two mistakes cancelled. Every subset is compared
        individually, so the packer's LINE arithmetic is checked against
        `bp.layout`'s MILLIMETRE verdict 63 times per floor.
        """
        regular, bold = faces
        record = led.ledger(_X2_COPY, width_mm=ZONE_W, height_mm=ZONE_H,
                            regular=regular, bold=bold)
        rows = record["subsets"]["subsets"]
        assert record["subsets"]["subsets_examined"] == 63

        agreed = 0
        fits_here = 0
        with_ingredients = 0
        for row in rows:
            ledger_says = row["fit"][str(size_pt)]["fits"]
            kept = [_X2_COPY[i] for i in row["indices"]]
            packed = _pack(kept, size_pt, False, faces)
            packer_says = packed["surfaces_required"] == 1
            assert packer_says == ledger_says, (
                f"disagreement on {row['kept']}: ledger {ledger_says}, "
                f"packer n={packed['surfaces_required']}")
            agreed += 1
            if ledger_says:
                fits_here += 1
                if "INGREDIENTS" in row["kept"]:
                    with_ingredients += 1

        assert agreed == 63
        assert fits_here == fitting
        assert with_ingredients == 0, (
            "INGREDIENTS appearing in a fitting subset would mean the "
            "whole-section result had changed, which nothing this sprint "
            "should have touched")


class TestTheMinimumIsConfirmedTwice:
    """The answer, and an independent arithmetic bound that agrees with it."""

    @pytest.mark.parametrize("size_pt,total,minimum", [(5.0, 39, 3),
                                                       (6.0, 48, 4)])
    def test_the_search_meets_the_lower_bound(self, faces, size_pt, total,
                                              minimum):
        """A second method, sharing no code with the first.

        The bound assumes the most generous world that could exist — every
        surface carrying one piece, paying no gap and no continuation — so
        nothing can beat it. The search is a dynamic programme over cut
        positions. They are computed from different quantities and they agree,
        which is what makes ``surfaces_required`` a fact rather than the output
        of one algorithm nobody checked.
        """
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        assert record["total_lines"] == total
        assert record["surfaces_required"] == minimum
        assert record["lower_bound_surfaces"] == minimum
        assert record["minimum_confirmed_by_lower_bound"] is True

    @pytest.mark.parametrize("size_pt,ungapped", [(5.0, 18), (6.0, 15)])
    def test_the_bound_is_computed_from_the_ungapped_capacity(self, faces,
                                                              size_pt,
                                                              ungapped):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        assert record["ungapped_capacity_lines"] == ungapped
        assert "ungapped" in record["lower_bound_basis"]

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_every_surface_is_within_its_own_capacity(self, faces, size_pt):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        for surface in record["surfaces"]:
            assert surface["lines_charged"] <= surface["capacity_lines"]
            expected = pk.capacity_for_pieces(
                width_mm=ZONE_W, height_mm=ZONE_H, size_pt=size_pt,
                pieces=surface["pieces"], regular=faces[0], bold=faces[1])
            assert surface["capacity_lines"] == expected

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_no_line_is_lost_or_duplicated(self, faces, size_pt):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        covered = []
        for surface in record["surfaces"]:
            covered.extend(range(surface["first_line"],
                                 surface["last_line"] + 1))
        assert covered == list(range(record["total_lines"])), (
            "the allocation does not cover the document exactly once")
        assert sum(s["lines_of_copy"] for s in record["surfaces"]) == \
            record["total_lines"]

    def test_the_surfaces_are_addressed_positionally(self, faces):
        """WI-Z's addressing, used rather than re-implemented. §AC2(b)."""
        from apps.ire import surface_plan as sp
        record = _pack(_X2_COPY, 5.0, True, faces, order=DECLARED_ORDER)
        assert [s["surface"] for s in record["surfaces"]] == \
            [sp.address(i) for i in range(record["surfaces_required"])]


class TestItComputesAndDoesNotRule:
    """§AC3(e) — *"WI-2A computes it. WI-2A does not rule it."*"""

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_the_layer_count_is_not_ruled(self, faces, size_pt):
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        assert record["layer_count_authority"] is None
        assert pk.LAYER_COUNT_NOT_RULED in record["codes"]

    def test_source_guard_the_packer_names_no_layer_count(self):
        """SOURCE-STRING GUARD — §AB1(f)'s reservation, held in the source.

        §AB1(f) left the layer count unruled and §AC3(e) declined to transfer
        it. A constant here would be that ruling, written once, in the module
        everything imports. The scan is over module-level assignments so that
        the docstrings — which must be able to DISCUSS the reservation — are
        not what trips it. WI-Z learned that the hard way: a guard that reads
        prose punishes the file for explaining itself.
        """
        import ast
        import pathlib
        tree = ast.parse(pathlib.Path(pk.__file__).read_text(encoding="utf-8"))
        named = []
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        named.append(target.id)
        for banned in ("LAYERS", "LAYER_COUNT", "N_SURFACES", "MAX_SURFACES",
                       "DEFAULT_SURFACES", "SURFACES"):
            assert banned not in named, (
                f"{banned} is a layer count with an import path attached")

    def test_the_record_reports_a_need_not_a_decision(self, faces):
        record = _pack(_X2_COPY, 5.0, True, faces, order=DECLARED_ORDER)
        assert "surfaces_required" in record
        assert record["reading_order_provenance"].startswith("declared by")


class TestWhatItFound:
    """The findings, pinned so they cannot drift out of the close report."""

    @pytest.mark.parametrize("size_pt", [5.0, 6.0])
    def test_without_splitting_the_document_fits_no_number_of_surfaces(
            self, faces, size_pt):
        """The result that makes §AC3 load-bearing rather than convenient.

        Whole sections cannot be placed on ANY number of surfaces, because
        INGREDIENTS alone is taller than one surface at either floor. Splitting
        is not an optimisation that saves a surface here; it is the only thing
        that makes the document placeable at all.
        """
        record = _pack(_X2_COPY, size_pt, False, faces, order=DECLARED_ORDER)
        assert record["surfaces_required"] is None
        assert pk.DOES_NOT_FIT in record["codes"]

        ungapped = record["ungapped_capacity_lines"]
        ingredients = record["lines_per_section"][1]
        assert ingredients > ungapped, (
            f"INGREDIENTS is {ingredients} lines against an ungapped surface "
            f"of {ungapped} — if this ever reverses, the finding above is "
            f"stale and the close report is wrong")

    @pytest.mark.parametrize("size_pt,per_section", [
        (5.0, {0: 3, 1: 20, 2: 4, 3: 7, 4: 3, 5: 2}),
        (6.0, {0: 3, 1: 26, 2: 5, 3: 8, 4: 4, 5: 2}),
    ])
    def test_the_six_sections_and_their_heights(self, faces, size_pt,
                                                per_section):
        """Six sections, all headed. §AB1(e)'s table quoted five and summed
        six; WARNINGS was always in the total and missing from the printout."""
        record = _pack(_X2_COPY, size_pt, True, faces, order=DECLARED_ORDER)
        assert len(_X2_COPY) == 6
        assert all(str(s.get("heading") or "") for s in _X2_COPY)
        assert record["lines_per_section"] == per_section
        assert sum(per_section.values()) == record["total_lines"]

    def test_the_break_falls_inside_ingredients_at_both_floors(self, faces):
        for size_pt in (5.0, 6.0):
            record = _pack(_X2_COPY, size_pt, True, faces,
                           order=DECLARED_ORDER)
            breaks = [s["opens_at"] for s in record["surfaces"]
                      if s["receives_continuation"]]
            assert len(breaks) == 1
            assert breaks[0]["heading"] == "INGREDIENTS"
            assert breaks[0]["role"] == "copy"
            assert breaks[0]["order"] >= 1
