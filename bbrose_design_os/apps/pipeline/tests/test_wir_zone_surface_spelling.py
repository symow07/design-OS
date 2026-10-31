"""§AA WI-R — one spelling for a zone's parent surface, and the other refused.

    "Two spellings of one field; a zone written the second way looks fully
    specified and silently takes the fallback. Pick one spelling, migrate, and
    assert the other cannot enter."  — §AA4, WI-R

THE SPELLING IS ``parent_surface``, AND NOT BY MAJORITY RULE. ``surface`` is
already taken, correctly, by a different field: five modules emit records whose
own ``surface`` key names the surface the RECORD is about — ``back_panel``,
``container_wrap_geometry``, ``container_text_floor``,
``container_production_metrics``, ``compose_vector_art``. Standardising zones
on ``surface`` would merge two fields that mean different things, in a file
where they already sit one line apart (``container_wrap_geometry._wrap_record``
writes ``"surface": <the zone's parent surface>``). That is the whole reason
the two looked interchangeable. ``TestSurfaceIsStillALegalRecordKey`` below is
the false-positive control: this work item must not condemn them.

"SILENTLY TAKES THE FALLBACK" UNDERSTATED IT. Eleven consumers were measured by
renaming ``parent_surface`` -> ``surface`` on a real ``propose_zones`` set and
diffing. ONE refused. TEN carried on with a different answer:

    validate_zone_set       CONTAINER_ZONE_SURFACE_MISMATCH  <- the only refusal
    zone_set_hash           a different, entirely valid-looking identity
    project_zones           cylindrical distortion 1.0 -> 0.0
    build_production_methods  target_surfaces [BODY_BACK] -> [None]
    build_wrap_geometry     every wrap gone: wraps [] and a clean hash over it
    build_motif_spec        target_surfaces/target_zones both -> []
    compose_container_graph the whole Surface-BODY_BACK group AND its panel
                            absent from the composed artwork
    container_adapter       handoff layer name -> ""
    build_separations       a different separation_set_hash  <- SEE BELOW
    measure_label_density   a BODY_BACK zone metered with role "front"
    back_panel.size_for_surface  floors {} -> FALLBACK 5.0 (§AA's own example)

Not one of those is an error state. Every one is a plausible-looking output,
which is why the record could say FALLBACK truthfully while the zone looked
fully specified. ``TestTheOldToleranceIsCatchableAgainstTheRealThing`` puts the
tolerant read back into the live modules and shows the degradations return, so
that table is a live fact here and not a claim about a past run.

THE ``build_separations`` ROW IS THE ONE I HAD WRONG, and a mutation found it
rather than a reading. Reverting ``container_separations.py:180`` to the
tolerant read left this file at 41 passed / 1 failed, and the one failure was
the HTTP boundary — a module I had broken on purpose went uncaught. Its probe
builds a methods record and a document first, so the refusal came from
upstream and the module under test was never asked. Two facts followed, both
of them §AA's precedent — *a constraint the pipeline never reaches is a
constraint nobody has tested* — landing on my own work:

  * that read sits inside ``if needs_ub and transparency ==
    CONFIRMED_TRANSPARENT``, and the inferred bottle profile carries
    ``body_transparency`` MISSING/UNKNOWN, so the live pipeline never reaches
    it. Reaching it at all needs ``TRANSPARENT_BODY_FIXTURE`` below — a
    FIXTURE, named as one here and at every point its state is quoted.
  * reached, the misspelling changes nothing there: the filter is
    ``not in _CAP_SURFACES``, and ``propose_zones("bottle")`` proposes no cap
    zone, so both spellings return ``['z_front', 'z_back']``. The differing
    ``separation_set_hash`` in the table above is real but came from the
    upstream methods record, NOT from this read. It is the one read site
    where nothing observable distinguishes the two spellings and the raise is
    the only thing that can catch it.

AFTER: 12 of 12 refuse (the twelfth is the transparent-body probe that reaches
the separations read). ``container_contract.zone_surface`` raises and
``zone_surface_problem`` reports, so the HTTP boundary answers 400 (§16: reject
a malformed payload, never 500) while the composers fail closed.
``TestEachReadSiteRefusesOnItsOwn`` holds each of the nine bindings alone
against a tolerant tree, so no refusal in this file is credited upstream again.
Reverting each of the nine on disk, one at a time, now fails this file nine
times out of nine — contract 22, production_method 3, compose_container 3,
projection 2, wrap_geometry 2, motif 2, and 1 each for container_adapter,
container_separations and container_production_metrics. Those last three are
the ones that were masked before; that they now fail by exactly their own
isolation case is the point.
"""
from __future__ import annotations

import ast
import contextlib
import copy
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.ire import back_panel as bp
from apps.ire import container_motif as cm
from apps.ire import container_production_method as cpm
from apps.ire import container_production_metrics as cmet
from apps.ire import container_separations as csep
from apps.ire import container_wrap_geometry as cwg
from apps.ire.compose_container import compose_container_graph
from apps.ire.handoff import container_adapter as ca
from apps.pipeline.models import (DesignTask, GeneratedImage,
                                  PackagingOutput)
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_projection as cp
from apps.pipeline.targets.base import DesignTarget
from apps.pipeline.targets.container.silhouettes import (ContainerProfile,
                                                         build_backbone)

ROLE_REVIEWER = "Reviewer"
PROFILE = cc.build_inferred_profile("bottle")


def right_zones() -> list[dict]:
    """A real, valid zone set — not a hand-written one, so this guard cannot
    drift away from what the contract actually proposes."""
    return cc.propose_zones(PROFILE)


def misspell(zones: list[dict]) -> list[dict]:
    return [{("surface" if k == cc.ZONE_SURFACE_KEY else k): v
             for k, v in z.items()} for z in zones]


def _doc(zones):
    return compose_container_graph(
        build_backbone(ContainerProfile(archetype="bottle", height_mm=110.0,
                                        width_mm=40.0)),
        product_name="Rose Nectar", name_lines=["Rose Nectar"],
        zones=zones, native=True, sku="RN-001")


def _node_names(doc) -> list[str]:
    out: list[str] = []

    def walk(node):
        out.append(str(node.name))
        for child in getattr(node, "children", None) or []:
            walk(child)
    walk(doc.root)
    return sorted(out)


def _adapter_layers(zones):
    graph = ca.serialize_container_handoff_graph(
        _doc(zones), {cc.ZONES_SCHEMA: {"zones": zones},
                      cc.PROFILE_SCHEMA: PROFILE})
    return sorted({lay.get("name") for lay in (graph.get("layers") or [])})


def _floor_record(zones):
    methods = cpm.build_production_methods(zones, PROFILE)
    return bp.size_for_surface(methods)[1]


def _empty_ire_doc():
    # the IRE graph's Group, not django.contrib.auth's imported above
    from apps.ire.graph import Document as _Document, Group as _IreGroup
    return _Document(page_w=210, page_h=297,
                     root=_IreGroup(name="Artwork", role="artwork", children=[]))


def transparent_body_fixture() -> dict:
    """A FIXTURE, and said so wherever its state is quoted (§AA).

    ``container_separations`` reads a zone's parent surface in exactly one
    place, behind ``needs_ub and transparency == CONFIRMED_TRANSPARENT``. The
    inferred bottle profile carries ``body_transparency`` MISSING/UNKNOWN, so
    the shipped pipeline never reaches that line — it is not a verified
    container property, it is a value this file supplies to get there. Nothing
    below claims the live profile is transparent.
    """
    profile = copy.deepcopy(PROFILE)
    profile["fields"]["body_transparency"] = {
        "value": "transparent", "source": "FIXTURE", "verification": "VERIFIED"}
    return profile


def _separations_over_a_transparent_body(zones):
    fixture = transparent_body_fixture()
    return csep.build_separations(
        cpm.build_production_methods(zones, fixture), _doc(zones), zones,
        fixture)


#: every consumer that reads a zone's parent surface. The list is the guard's
#: denominator: a consumer added without an entry here is a consumer nobody
#: measured, which is the condition WI-R exists to end.
CONSUMERS = {
    "validate_zone_set": lambda zs: cc.validate_zone_set(zs, PROFILE),
    "zone_set_hash": cc.zone_set_hash,
    "project_zones": lambda zs: cp.project_zones(zs, PROFILE),
    "build_production_methods": lambda zs: cpm.build_production_methods(
        zs, PROFILE),
    "build_wrap_geometry": lambda zs: cwg.build_wrap_geometry(zs, PROFILE),
    "build_motif_spec": lambda zs: cm.build_motif_spec(
        {"motif_signature": "rose bloom"}, None, zs, PROFILE),
    "compose_container_graph": lambda zs: _node_names(_doc(zs)),
    "container_adapter": _adapter_layers,
    "build_separations": lambda zs: csep.build_separations(
        cpm.build_production_methods(zs, PROFILE), _doc(zs), zs, PROFILE),
    # the twelfth: the same call over TRANSPARENT_BODY_FIXTURE, which is the
    # only way to reach container_separations' own read at all.
    "build_separations_over_a_transparent_body":
        _separations_over_a_transparent_body,
    "measure_label_density": lambda zs: cmet.measure_label_density(
        _doc(zs), zs, None),
    "size_for_surface": _floor_record,
    # the thirteenth (§BH50(f)(6)): the seam check's own read of the zone set.
    # Probed with a geometry built from the RIGHT spelling, so a refusal is
    # attributable to validate_wrap_alignment's read and not to the builder's
    # upstream one — the masking this file's docstring records.
    "validate_wrap_alignment": lambda zs: cwg.validate_wrap_alignment(
        cwg.build_wrap_geometry(right_zones(), PROFILE), _empty_ire_doc(), zs),
}
CONSUMER_COUNT = 13   # 12 -> 13 at §BH50(f)(6): validate_wrap_alignment


def refuses(fn, zones) -> bool:
    """A refusal is a raise OR the finding code. Both are refusals; only one
    of them can be returned over HTTP, which is why there are two forms."""
    try:
        result = fn(zones)
    except cc.ZoneSurfaceSpellingError:
        return True
    return cc.ZONE_SURFACE_KEY_UNRECOGNISED in str(result)


class TestEveryConsumerRefusesTheOtherSpelling:
    def test_the_denominator_is_stated(self):
        # a guard whose subject list can quietly shrink proves nothing.
        assert len(CONSUMERS) == CONSUMER_COUNT

    @pytest.mark.parametrize("name", sorted(CONSUMERS))
    def test_the_probe_runs_on_the_correct_spelling(self, name):
        """The lesson that cost this work item two false readings.

        The first pass of this measurement reported IDENTICAL for
        ``build_motif_spec`` — because the probe called it with the wrong
        arity and compared two identical tracebacks — and SILENT for the
        handoff adapter, because the probe re-read the raw key instead of
        calling the serializer. Both were the instrument reporting on itself.
        Nothing below means anything unless the correct spelling gets through.
        """
        CONSUMERS[name](right_zones())

    @pytest.mark.parametrize("name", sorted(CONSUMERS))
    def test_the_alias_is_refused(self, name):
        assert refuses(CONSUMERS[name], misspell(right_zones())), (
            f"{name} accepted a zone spelled 'surface' and returned an answer")


CONTRACT = "apps.pipeline.services.container_contract"

#: every module that BINDS the accessor by name, mapped to a consumer whose
#: call reaches THAT binding. Nine bindings, twelve consumers: the others
#: reach bindings already in this map, so they cover the callers, not the
#: read sites. ``container_separations`` is deliberately mapped to the
#: transparent-body probe: mapped to the plain one it passes on an upstream
#: refusal, which is the defect this class exists to have caught.
BINDING_EXERCISED_BY = {
    CONTRACT: "zone_set_hash",
    "apps.pipeline.services.container_projection": "project_zones",
    "apps.ire.container_wrap_geometry": "build_wrap_geometry",
    "apps.ire.container_production_method": "build_production_methods",
    "apps.ire.container_motif": "build_motif_spec",
    "apps.ire.compose_container": "compose_container_graph",
    "apps.ire.handoff.container_adapter": "container_adapter",
    "apps.ire.container_separations":
        "build_separations_over_a_transparent_body",
    "apps.ire.container_production_metrics": "measure_label_density",
}
BINDING_COUNT = 9

#: modules that reach the accessor through ``cc.`` and therefore share the
#: contract's binding. Named rather than silently absent from the map above.
#: ``targets.container`` is the read-only Review Board row, which asks
#: ``zone_surface_problem`` first and prints the code instead of raising —
#: a board must not 500 because a stored zone is spelled wrong.
SHARE_THE_CONTRACT_BINDING = frozenset({"apps.pipeline.views",
                                        "apps.pipeline.targets.container"})


def _tolerant(zone):
    """The pre-WI-R read, exactly: take the one spelling, ignore the other."""
    return zone.get(cc.ZONE_SURFACE_KEY)


@contextlib.contextmanager
def tolerant_in(modules):
    with contextlib.ExitStack() as stack:
        for module in modules:
            stack.enter_context(patch(f"{module}.zone_surface", _tolerant))
        yield


class TestEachReadSiteRefusesOnItsOwn:
    """The hole a mutation found in the class above.

    Reverting ``container_separations.py:180`` to ``z.get("parent_surface")``
    left this file at 41 passed, 1 failed — and the one failure was the HTTP
    boundary, not the module I had just broken. ``build_separations``'s probe
    builds its methods record and its document first, so the refusal arrived
    from upstream and the module under test was never asked. The same masking
    covered ``container_adapter`` and ``measure_label_density``: all three
    build a document before they read a zone. A clean result from a code path
    that was never reached is not a result — the lesson WI-Q's `:682` and this
    item's two broken probes had already taught, arriving a third time.

    So: patch the accessor tolerant in every module EXCEPT one and require the
    consumer to refuse anyway. Then the refusal is attributable to that read.
    """

    def test_the_binding_list_is_stated(self):
        assert len(BINDING_EXERCISED_BY) == BINDING_COUNT
        assert set(BINDING_EXERCISED_BY.values()) <= set(CONSUMERS)

    def test_source_guard_no_module_binds_the_accessor_without_a_case(self):
        """SOURCE-STRING GUARD (§Y2). The denominator, audited against the
        tree rather than remembered.

        A module that imports the accessor by name owns a binding that can be
        reverted on its own, so it needs its own case below. A module that
        reaches it through ``cc.`` shares the contract's binding and is named
        in ``SHARE_THE_CONTRACT_BINDING`` instead of quietly missing.

        DECLARED because it reads source, not because §Y2's census demanded
        it: the census classifies a test as a guard only when EVERY assertion
        is a literal-in-source claim, and these assert on a derived set of
        module names, so it is not counted either way. It is labelled anyway.
        A guard is not exempt from the register because the register's own
        classifier cannot see it — and this one earns its source read: it is
        the denominator OF a behavioural guard, not a substitute for one.
        """
        root = Path(settings.BASE_DIR) / "apps"
        own, shared = {CONTRACT}, set()
        for path in sorted(root.rglob("*.py")):
            if "tests" in path.parts or path.name.startswith("test_"):
                continue
            text = path.read_text()
            if "zone_surface" not in text:
                continue
            module = ".".join(path.relative_to(root.parent)
                              .with_suffix("").parts)
            module = module[:-len(".__init__")] \
                if module.endswith(".__init__") else module
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, ast.ImportFrom) and any(
                        a.name == "zone_surface" for a in node.names):
                    own.add(module)
            if "cc.zone_surface(" in text:
                shared.add(module)
        assert own == set(BINDING_EXERCISED_BY), (
            "a module binds zone_surface with no isolation case: "
            f"{sorted(own ^ set(BINDING_EXERCISED_BY))}")
        assert shared == SHARE_THE_CONTRACT_BINDING, sorted(shared)

    @pytest.mark.parametrize("module", sorted(BINDING_EXERCISED_BY))
    def test_the_module_refuses_with_every_other_binding_tolerant(self, module):
        consumer = BINDING_EXERCISED_BY[module]
        others = [m for m in BINDING_EXERCISED_BY if m != module]
        with tolerant_in(others):
            assert refuses(CONSUMERS[consumer], misspell(right_zones())), (
                f"{module} did not refuse on its own: with every other "
                f"binding tolerant, {consumer} returned an answer. The "
                f"refusal measured elsewhere came from upstream, not from "
                f"this module's read.")

    @pytest.mark.parametrize("module", sorted(BINDING_EXERCISED_BY))
    def test_the_isolation_case_fails_when_the_binding_is_reverted(self, module):
        """The negative control on the isolation, per §Z4/WI-J.

        Identical harness, one difference: the module under test is tolerant
        too. If the consumer still refused here, the case above would be
        passing for some reason other than the read it claims to measure.
        This is the mutation that found the hole, run in-process, on all nine
        bindings instead of the one I happened to pick by hand.
        """
        consumer = BINDING_EXERCISED_BY[module]
        with tolerant_in(BINDING_EXERCISED_BY):
            assert not refuses(CONSUMERS[consumer], misspell(right_zones())), (
                f"{consumer} refuses even with {module} reverted, so its "
                f"isolation case does not measure {module}")


class TestTheOldToleranceIsCatchableAgainstTheRealThing:
    """Put ``zone.get("parent_surface")`` back into the live modules.

    §Z4/WI-J discipline: a guard that has never seen the defect it forbids is
    a guard nobody has tested. These do not use a synthetic copy of the
    composer — they patch the accessor the shipped modules call, so the
    degradations in this file's header are measured, not remembered.
    """

    @staticmethod
    def _tolerant(zone):
        return zone.get(cc.ZONE_SURFACE_KEY)

    def test_the_back_panel_group_disappears_from_the_artwork(self):
        zones = misspell(right_zones())
        with patch("apps.ire.compose_container.zone_surface", self._tolerant):
            names = _node_names(_doc(zones))
        assert not any(n.startswith("Surface-") for n in names)
        assert not any("panel-BODY_BACK" in n for n in names)
        # and with the guard in place it is refused instead of vanishing
        assert refuses(CONSUMERS["compose_container_graph"], zones)

    def test_every_wrap_disappears_and_the_hash_stays_clean(self):
        zones = misspell(right_zones())
        # the wrap module's OWN binding, not the contract's: it used to reach
        # the accessor through ``cc.`` and patching there was enough, which is
        # precisely why its refusal could not be told apart from the
        # contract's. Binding it by name is what made the isolation possible.
        with tolerant_in(["apps.ire.container_wrap_geometry"]):
            geo = cwg.build_wrap_geometry(zones, PROFILE)
        assert geo["wraps"] == []
        assert geo["review_required"] is False        # nothing flagged at all
        assert geo["wrap_set_hash"]                   # a clean identity over []

    def test_a_back_zone_is_metered_as_a_front_zone(self):
        zones = misspell(right_zones())
        # the composer is patched too, only so there IS a document to meter:
        # the subject of this test is the metric, not the artwork.
        with patch("apps.ire.compose_container.zone_surface", self._tolerant), \
                patch("apps.ire.container_production_metrics.zone_surface",
                      self._tolerant):
            density = cmet.measure_label_density(_doc(zones), zones, None)
        roles = [e["role"] for e in density["per_zone"]]
        assert roles == ["front", "front"], roles
        assert all(e["surface"] is None for e in density["per_zone"])
        # the correctly spelled set still distinguishes them
        good = cmet.measure_label_density(_doc(right_zones()), right_zones(),
                                          None)
        assert sorted(e["role"] for e in good["per_zone"]) == ["back", "front"]

    def test_the_text_floor_falls_back_and_says_nothing_about_why(self):
        """§AA's own example, reproduced."""
        zones = misspell(right_zones())
        with patch("apps.ire.container_production_method.zone_surface",
                   self._tolerant):
            record = _floor_record(zones)
        assert record["source"].startswith("FALLBACK")
        assert record["size_pt"] == 5.0
        # the record is TRUE and still misleads: nothing in it names a spelling
        assert cc.ZONE_SURFACE_KEY not in str(record)
        assert "surface" not in str(record.get("source"))


class TestAbsentIsNotMisspelled:
    """The negative control on the fix itself (§AA4(c), no chained fixes).

    A zone with NEITHER spelling is a different condition. It was already
    reported by ``validate_zone`` as ``... on None``; turning it into a raise
    here would be a second fix riding on this one, and it would have taken the
    committed ``_FRONT_ZONE`` fixture down with it.
    """

    def test_neither_spelling_returns_none_rather_than_raising(self):
        assert cc.zone_surface({"zone_id": "z"}) is None
        assert cc.zone_surface_problem({"zone_id": "z"}) is None

    def test_the_absent_case_still_reports_the_old_finding(self):
        problems = cc.validate_zone({"zone_id": "z", "zone_type":
                                     "FRONT_PRINT_ZONE"}, PROFILE)
        assert any(p.startswith(cc.ZONE_SURFACE_MISMATCH) for p in problems)
        assert not any(p.startswith(cc.ZONE_SURFACE_KEY_UNRECOGNISED)
                       for p in problems)

    def test_both_spellings_present_is_refused_as_ambiguous(self):
        zone = {"zone_id": "z", cc.ZONE_SURFACE_KEY: "BODY_FRONT",
                "surface": "BODY_BACK"}
        problem = cc.zone_surface_problem(zone)
        assert problem is not None
        # the message says WHY, because "both are present" is not obviously
        # wrong until you ask which one wins.
        assert "which of them is authority" in problem
        with pytest.raises(cc.ZoneSurfaceSpellingError):
            cc.zone_surface(zone)


class TestSurfaceIsStillALegalRecordKey:
    """The false-positive control — WI-J's grep lesson, applied.

    WI-J refused a string guard because the repo contains correct code a
    string guard would condemn. The same applies here in a sharper form: a
    guard phrased as "no dict may carry `surface`" would condemn five shipped
    record formats. The rule is about ZONES, and these prove it stayed there.
    """

    def test_wrap_records_still_name_their_own_surface(self):
        geo = cwg.build_wrap_geometry(right_zones(), PROFILE)
        assert geo["wraps"], "no wraps to check — the control is vacuous"
        assert all("surface" in w and w["surface"] for w in geo["wraps"])

    def test_the_text_floor_record_still_names_its_own_surface(self):
        assert _floor_record(right_zones())["surface"] == bp.SURFACE

    def test_the_density_record_still_names_its_own_surface(self):
        density = cmet.measure_label_density(_doc(right_zones()),
                                             right_zones(), None)
        assert {e["surface"] for e in density["per_zone"]} == {"BODY_FRONT",
                                                              "BODY_BACK"}


class TestNoProducerEmitsTheOtherSpelling:
    """Close the door at the source, not only at the readers."""

    def test_make_zone(self):
        zone = cc.make_zone("z", "FRONT_PRINT_ZONE", "BODY_FRONT", x=1, y=1,
                            width=10, height=10, curvature_type=cc.FLAT)
        assert cc.ZONE_SURFACE_KEY in zone
        assert not any(a in zone for a in cc.ZONE_SURFACE_ALIASES)

    def test_propose_zones_for_every_archetype(self):
        for archetype in ("bottle", "jar", "tube"):
            zones = cc.propose_zones(cc.build_inferred_profile(archetype))
            assert zones, archetype
            for zone in zones:
                assert cc.zone_surface(zone), (archetype, zone.get("zone_id"))
                assert not any(a in zone for a in cc.ZONE_SURFACE_ALIASES)


class TestTheAliasCannotBePersisted(TestCase):
    """Where a zone actually ENTERS: ``request.data.get('zones')``.

    ``views.ConfirmContainerProfileView`` assigns the request body straight to
    ``zones`` after checking only that it is a list of dicts. That is the one
    path by which a spelling nobody wrote in this repo could still reach the
    database, so the refusal is asserted at the boundary and not only in the
    library.
    """

    def setUp(self):
        brand = Brand.objects.create(name="B", master_brief="x")
        product = Product.objects.create(
            brand=brand, product_id="CO-411", name="Rose Nectar",
            category="CO", year=2026, product_type="serum",
            width_mm=35, depth_mm=25, height_mm=95)
        group, _ = Group.objects.get_or_create(name=ROLE_REVIEWER)
        user = User.objects.create_user("wir", "wir@t.com", "pw")
        user.groups.add(group)
        self.client.force_login(user)
        self.task = DesignTask.objects.create(
            brand=brand, product=product, task_text="serum",
            status="awaiting_container_profile",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)
        image = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used="p",
            variation_number=1)
        self.out = PackagingOutput.objects.create(
            task=self.task, approved_image=image,
            spec_sheet={"backend": "container",
                        "container_profile": {"archetype": "tube"}})

    def _post(self, zones):
        return self.client.post(
            f"/api/tasks/{self.task.id}/confirm_container_profile/",
            {"profile": {"archetype": "tube", "variant": "slim",
                         "height_mm": 95, "width_mm": 35, "depth_mm": 25,
                         "cap_style": "screw"}, "zones": zones},
            content_type="application/json")

    @patch("apps.pipeline.tasks.resume_aria_container_profile.delay")
    def test_a_misspelled_zone_is_rejected_as_a_payload_not_a_crash(self, delay):
        record = cc.merge_product_record_dims(
            cc.build_inferred_profile("tube", "slim"), self.task.product)
        zones = cc.propose_zones(record)
        for zone in zones:
            zone["user_confirmation_state"] = cc.ZONE_USER_CONFIRMED
        response = self._post(misspell(zones))
        # 400, not 500: §16 boundary. A raise from the accessor deeper in the
        # view would have been an honest refusal and a broken API.
        assert response.status_code == 400
        detail = " ".join(response.json()["detail"])
        assert cc.ZONE_SURFACE_KEY_UNRECOGNISED in detail
        delay.assert_not_called()
        self.out.refresh_from_db()
        assert cc.ZONES_SCHEMA not in self.out.spec_sheet
        self.task.refresh_from_db()
        assert self.task.status == "awaiting_container_profile"


#: Zones in the repo that name no parent surface AT ALL. Recorded, not fixed
#: (§AA4(c)) — "absent" is a different condition from "misspelled", and
#: supplying a surface a fixture never asserted is a fixture-design decision,
#: not a spelling migration. §Y2 shape: this may only shrink.
NO_SURFACE_AT_ALL = frozenset({
    # apps/ire/tests/test_back_panel.py — the dropper's front zone. Its sibling
    # `_BACK_ZONE` was the one misspelled zone dict in the repo and is migrated
    # by this work item; this one was never spelled at all.
    "apps.ire.tests.test_back_panel._FRONT_ZONE",
})


class TestTheOneMisspelledZoneIsGone:
    def test_the_migrated_fixture_uses_the_contract_spelling(self):
        from apps.ire.tests.test_back_panel import _BACK_ZONE, _FRONT_ZONE
        assert cc.zone_surface(_BACK_ZONE) == "BODY_BACK"
        assert not any(a in _BACK_ZONE for a in cc.ZONE_SURFACE_ALIASES)
        # the sibling is the registered exception and must stay exactly that:
        # absent, not misspelled.
        assert cc.zone_surface(_FRONT_ZONE) is None
        assert cc.zone_surface_problem(_FRONT_ZONE) is None

    def test_the_register_of_surfaceless_zones_only_shrinks(self):
        assert len(NO_SURFACE_AT_ALL) <= 1


class TestMigratingTheFixtureChangedNothingItDrew:
    """§AA's standing rule: when the effect on production output is zero, that
    goes next to the fix.

    It is zero here for a reason worth naming. ``compose_dropper_sheet`` finds
    the back zone by ``zone_type``, never by surface, so the artwork was
    identical before and after — 201 nodes, same names, sizes and coordinates.
    """

    def test_the_dropper_sheet_never_reads_the_parent_surface(self):
        from apps.ire.compose_dropper import compose_dropper_sheet
        from apps.ire.tests.test_back_panel import (_BACK_ZONE, _FRONT_ZONE,
                                                    _GEOMETRY, _LIVE, _METHODS)

        def sheet(zones):
            doc = compose_dropper_sheet(
                _GEOMETRY, zones=zones, reference_path=None, logo_path=None,
                product_name="Rose Damascena", sku="X", back_sections=_LIVE,
                revision_status="TEST", methods_record=_METHODS)
            out = []

            def walk(node):
                out.append((str(node.name), getattr(node, "size_pt", None),
                            round(float(getattr(node, "x", 0) or 0), 9),
                            round(float(getattr(node, "y", 0) or 0), 9)))
                for child in getattr(node, "children", None) or []:
                    walk(child)
            walk(doc.root)
            return out

        migrated = sheet([_FRONT_ZONE, _BACK_ZONE])
        pre_migration = sheet([_FRONT_ZONE,
                               {("surface" if k == cc.ZONE_SURFACE_KEY else k): v
                                for k, v in _BACK_ZONE.items()}])
        assert migrated, "no nodes — the comparison would be vacuous"
        assert migrated == pre_migration


class TestTheSecondCauseTheRulingDidNotName:
    """RECORDED, NOT FIXED (§AA4(c)).

    §AA's finding reads: "a confirmed back zone with no ``parent_surface``
    silently takes the fallback". True of the mechanism. But the fixture it
    was found on reaches the fallback by TWO independent routes, and the
    spelling is only the first: the zone carries no ``permitted_techniques``,
    so ``method_type_for`` returns None, the method is UNSUPPORTED and
    ``surface_floors`` drops it whatever the surface says.

    Migrating the spelling therefore fixes the record's ``target_surfaces``
    ([None] -> [BODY_BACK]) and does NOT move the panel off the fallback. And
    when the technique is supplied too, the size is 5.0 pt either way, because
    SCREEN_PRINT's capability floor equals §W2(b)'s fallback. Two causes
    removed, zero millimetres of change — which is the honest reason this work
    item did not go looking for a third.
    """

    @staticmethod
    def _fixture_zones():
        from apps.ire.tests.test_back_panel import _BACK_ZONE, _FRONT_ZONE
        return [_FRONT_ZONE, _BACK_ZONE]

    def test_the_spelling_fix_made_the_record_truthful(self):
        methods = cpm.build_production_methods(self._fixture_zones(), PROFILE)
        assert [m["target_surfaces"] for m in methods["methods"]] == [
            [None], ["BODY_BACK"]]      # [None] is _FRONT_ZONE, the registered
        #                                 surfaceless one — not a misspelling

    def test_and_the_panel_still_takes_the_fallback_for_the_second_reason(self):
        methods = cpm.build_production_methods(self._fixture_zones(), PROFILE)
        assert [m["method_type"] for m in methods["methods"]] == [None, None]
        record = bp.size_for_surface(methods)[1]
        assert record["source"].startswith("FALLBACK")
        assert record["size_pt"] == 5.0

    def test_supplying_the_technique_resolves_it_to_the_same_number(self):
        from apps.ire.tests.test_back_panel import _BACK_ZONE, _FRONT_ZONE
        with_technique = dict(_BACK_ZONE,
                              permitted_techniques=["screen_printing"])
        methods = cpm.build_production_methods([_FRONT_ZONE, with_technique],
                                               PROFILE)
        record = bp.size_for_surface(methods)[1]
        assert not record["source"].startswith("FALLBACK")
        assert record["size_pt"] == 5.0          # the floor equals §W2(b)'s
        # WI-N's ruling is untouched by any of this: still nobody's confirmation
        assert record["method_confirmed"] is False
        assert record["size_is_an_assumption"] is True
