"""§Z1 — a `size_pt` is chosen as type, never derived from a millimetre length.

The rule is a units rule, and units cannot be checked by reading the source:
`compose.py` and `compose_vector_art.py` both derive point sizes from
millimetre widths *correctly*, by multiplying through 72/25.4, and a reader
that greps for a millimetre name in a `size_pt` expression would condemn them.
So this file does not read source. It checks the one BEHAVIOUR that separates
the two cases:

    a point size derived from a millimetre quantity MOVES when that
    millimetre quantity moves; a point size chosen as type does not.

`_front_typography` receives its millimetre inputs as arguments — the zone's
width and height, the sheet origin, the panel scale `s`, and the bottle
geometry. Every one of them is varied here and the emitted `size_pt` values
must not move for any of them. That is the whole of §Z1(b) for this producer,
stated as an observation of what it emits.

**The guard is exercised against a known-bad producer as well as the real
one** (`TestTheGuardCatchesTheDefectItWasWrittenFor`). Without that, a green
result here would be consistent with a guard that cannot fail — and the defect
§Z1 corrects was itself found underneath a green axis. The known-bad producer
is the pre-fix expression verbatim: `zone_height * s * 0.05`.

Scope, stated so it is not overread: this measures ONE producer. §Z1(b) is a
repo-wide rule and nothing enforces it repo-wide; that gap is recorded in
`OWNER_REVIEW_QUEUE.md` rather than papered over with a source-string guard.
"""
import pytest

from apps.ire.compose_dropper import _front_typography

_GEOMETRY = {"total_height_mm": 104.0, "body_height_mm": 70.5,
             "body_diameter_mm": 31.5, "collar_height_mm": 9.5,
             "bulb_height_mm": 21.5, "collar_diameter_mm": 21.5,
             "bulb_width_mm": 11.0, "visible_neck_mm": 2.5,
             "neck_diameter_mm": 9.0, "base_thickness_mm": 3.5,
             "shoulder_radius_mm": 3.0, "frost_intensity": 0.7,
             "translucency": 0.35}

#: the confirmed dropper's front zone — 70% x 60% of a Ø31.5 x 70.5 body,
#: the same 22.0 x 42.3 mm `propose_zones` derives and `test_back_panel.py`
#: writes out.
_ZONE = {"zone_id": "z_front", "zone_type": "FRONT_PRINT_ZONE",
         "x": 4.8, "y": 14.1, "width": 22.0, "height": 42.3}

#: the two panel scales the composed sheet actually draws this one zone at:
#: panel 5 at a fixed 1.22, panel 8 fitted to its frame.
HERO_S = 1.22
FLAT_S = 34.0 / 22.0


def _base_call() -> dict:
    return {"g": dict(_GEOMETRY), "zone": dict(_ZONE), "ox": 158.0,
            "oy": 28.0, "s": HERO_S, "name_min": 9.0}


def _sizes(producer, call: dict) -> dict:
    """{node name: size_pt} for one call of a front-typography producer."""
    children, _, _, _ = producer(
        call["g"], call["zone"], call["ox"], call["oy"], call["s"], None,
        name_min=call["name_min"], **_named(producer))
    return {str(node.name): float(node.size_pt) for node in children
            if getattr(node, "type", "") == "text"}


def _double(value):
    return {k: (v * 2.0 if isinstance(v, (int, float)) else v)
            for k, v in value.items()}


#: every millimetre input the producer has, each as a perturbation of the call.
#: `name_min` is deliberately absent: it is a POINT size and a point size is
#: allowed — required, after §Z2 — to decide a point size.
MM_INPUTS = {
    "panel scale s": lambda c: dict(c, s=c["s"] * 2.0),
    "zone height mm": lambda c: dict(
        c, zone=dict(c["zone"], height=float(c["zone"]["height"]) * 2.0)),
    "zone width mm": lambda c: dict(
        c, zone=dict(c["zone"], width=float(c["zone"]["width"]) * 2.0)),
    "zone origin mm": lambda c: dict(
        c, zone=dict(c["zone"], x=float(c["zone"]["x"]) + 11.0,
                     y=float(c["zone"]["y"]) + 7.0)),
    "sheet origin mm": lambda c: dict(c, ox=c["ox"] + 40.0, oy=c["oy"] + 25.0),
    "bottle geometry mm": lambda c: dict(c, g=_double(c["g"])),
}


def sizes_that_moved(producer, call=None) -> dict:
    """Which emitted `size_pt` values move when a MILLIMETRE input moves.

    Returns ``{input name: {node: (before, after)}}`` — empty when every
    emitted size is a chosen point size. This is the guard; the tests below
    are three applications of it.
    """
    call = call or _base_call()
    baseline = _sizes(producer, call)
    moved: dict = {}
    for label, perturb in MM_INPUTS.items():
        after = _sizes(producer, perturb(call))
        drift = {name: (baseline[name], after[name]) for name in baseline
                 if name in after and after[name] != baseline[name]}
        if drift:
            moved[label] = drift
    return moved


class TestTheGuardCatchesTheDefectItWasWrittenFor:
    """The falsifying input, so §Z1(b) is a guard and not an intention.

    A test that only ever runs against corrected code proves the code and the
    guard are consistent; it does not prove the guard would notice. These two
    supply the missing half from both sides — a producer with the defect must
    be caught, and a producer without it must not be.
    """

    @staticmethod
    def _defective(g, zone, ox, oy, s, logo_path, prefix="", name_min=9.0):
        """§Z2(a)'s target as it stood before the fix: five percent of a
        scaled millimetre length, stored in a field named pt."""
        from apps.ire.compose_dropper import _hex, centered_text
        zh = float(zone["height"]) * s
        return ([centered_text(f"{prefix}front-brand", "BBROSE", 0.0, 0.0,
                               zh * 0.05, _hex("TYPE_WINE"), font="bold")],
                [], "", (0.0, 0.0, 0.0, 0.0))

    @staticmethod
    def _chosen(g, zone, ox, oy, s, logo_path, prefix="", name_min=9.0):
        """The same run, sized as type."""
        from apps.ire.compose_dropper import _hex, centered_text
        return ([centered_text(f"{prefix}front-brand", "BBROSE", 0.0, 0.0,
                               6.0, _hex("TYPE_WINE"), font="bold")],
                [], "", (0.0, 0.0, 0.0, 0.0))

    def test_a_size_derived_from_a_millimetre_quantity_is_caught(self):
        moved = sizes_that_moved(self._defective)
        assert "panel scale s" in moved, \
            "the guard did not notice a size_pt that is 5% of a scaled mm"
        assert "zone height mm" in moved
        assert moved["panel scale s"]["front-brand"] == (2.5803, 5.1606)

    def test_the_same_run_sized_as_type_is_not_caught(self):
        """Vacuity, from the other side. A guard that flags every producer
        would also 'catch' the defect and would mean nothing."""
        assert sizes_that_moved(self._chosen) == {}

    def test_the_guard_looks_at_more_than_the_scale(self):
        """`s` is not the only millimetre input, and a fix that removed only
        the `s` term would still be deriving type from a zone dimension."""
        def zone_only(g, zone, ox, oy, s, logo_path, prefix="", name_min=9.0):
            from apps.ire.compose_dropper import _hex, centered_text
            return ([centered_text(f"{prefix}front-brand", "BBROSE", 0.0, 0.0,
                                   float(zone["height"]) * 0.05,
                                   _hex("TYPE_WINE"), font="bold")],
                    [], "", (0.0, 0.0, 0.0, 0.0))

        moved = sizes_that_moved(zone_only)
        assert "zone height mm" in moved
        assert "panel scale s" not in moved


class TestNoEmittedTypeSizeIsDerivedFromAMillimetre:
    """§Z1(b) applied to the real producer."""

    def test_no_size_moves_when_any_millimetre_input_moves(self):
        assert sizes_that_moved(_front_typography) == {}

    @pytest.mark.parametrize("name_min", [9.0, 6.5])
    def test_that_holds_at_both_of_the_scales_the_sheet_draws(self, name_min):
        """Panel 5 and panel 8 are the same physical zone at two drawing
        scales (§Z1(d)). The emitted type must be the same type."""
        hero = _sizes(_front_typography,
                      dict(_base_call(), s=HERO_S, name_min=name_min))
        flat = _sizes(_front_typography,
                      dict(_base_call(), s=FLAT_S, name_min=name_min))
        assert hero == flat

    def test_the_only_input_that_may_change_a_size_is_a_point_size(self):
        """`name_min` is in points, so it is allowed to decide one — and it
        must actually reach the emitted run, or the parameter is decoration."""
        at_9 = _sizes(_front_typography, dict(_base_call(), name_min=9.0))
        at_65 = _sizes(_front_typography, dict(_base_call(), name_min=6.5))
        assert at_9["product-name-hero-0"] == 9.0
        assert at_65["product-name-hero-0"] == 6.5


class TestTheWordmarkIsAChosenSixPoint:
    """§Z2(a) — the value the millimetre arithmetic was reaching for."""

    def test_front_brand_is_six_point(self):
        assert _sizes(_front_typography, _base_call())["front-brand"] == 6.0

    def test_it_is_the_same_six_point_on_the_flat_panel(self):
        flat = _sizes(_front_typography,
                      dict(_base_call(), s=FLAT_S, name_min=6.5))
        assert flat["front-brand"] == 6.0

    def test_it_is_at_or_above_the_floor_the_axis_judges_it_against(self):
        """The floor on this document's hero surface is `ADHESIVE_LABEL`'s
        4.0 pt — the loosest LABEL/PRINT entry in the capability table, and
        still above the 2.5803 the millimetre arithmetic produced. Read from
        the table so a table change shows up here as a changed floor.

        `BOTTOM_INKJET_CODE`'s 2.0 is excluded deliberately: it is a batch
        code on a crimp, not front artwork, and quoting it would let the
        smallest number in the table stand in for the one that governs.
        """
        from apps.ire.container_production_method import _METHOD_DEFAULTS
        floor = _METHOD_DEFAULTS["ADHESIVE_LABEL"]["min_text_pt"]
        assert floor == _METHOD_DEFAULTS["WRAP_LABEL"]["min_text_pt"] == 4.0
        assert _sizes(_front_typography, _base_call())["front-brand"] >= floor


def _named(producer) -> dict:
    """§BH68(d), OWNER RULED 2026-09-24: the lockup's module default name is gone ("Derive it from the product record;
    print nothing where the record is silent"), so the fixture's two lines are handed to a producer that takes them;
    the historical producers above never took a name and are called exactly as before. Defined here, at the end, so
    no line above moves: test_wit_unit_analysis registers this file's defective fixtures by their line numbers."""
    import inspect

    from apps.ire.tests.test_back_panel import _FRONT_NAME_LINES
    return {"name_lines": _FRONT_NAME_LINES} if "name_lines" in inspect.signature(producer).parameters else {}
