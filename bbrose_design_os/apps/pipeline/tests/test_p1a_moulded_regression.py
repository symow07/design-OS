"""M4B-B — PALT-P1A is the engineering regression fixture.

M4B-B adds a rectangular ES3083 family to the same assembly. The owner's
constraint is that improvements to P1B must not break P1A, so every
component identity of the round assembly is pinned here BEFORE the family
parameter exists. If the default path ever moves, this fails first.
"""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services import palette_identity as PI
from apps.pipeline.services import palette_moulded_geometry as MG

REPO = Path(__file__).resolve().parents[3]
PIN = REPO / "docs" / "roadmap" / "palt_m4b" / "p1a_moulded_identity_pin.json"


def _identities():
    comps, _dims = MG.build_moulded_components()
    return {n: PI.mesh_geometry_identity(c) for n, c in sorted(comps.items())}


class P1AMouldedIdentityTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pin = json.loads(PIN.read_text())
        cls.ids = _identities()

    def test_the_component_set_is_unchanged(self):
        self.assertEqual(sorted(self.ids), sorted(self.pin["components"]))
        self.assertEqual(len(self.ids), self.pin["component_count"])

    def test_every_component_identity_is_unchanged(self):
        for name, want in sorted(self.pin["components"].items()):
            with self.subTest(component=name):
                self.assertEqual(self.ids.get(name), want)

    def test_the_aggregate_identity_is_unchanged(self):
        import hashlib
        agg = hashlib.sha256(
            repr(sorted(self.ids.items())).encode()).hexdigest()[:16]
        self.assertEqual(agg, self.pin["aggregate_identity"])

    def test_it_is_deterministic(self):
        self.assertEqual(_identities(), self.ids)

    def test_the_round_pan_family_is_still_round(self):
        comps, _ = MG.build_moulded_components()
        self.assertEqual(sum(1 for n in comps if n.startswith("metal_pan_")),
                         9)
        self.assertEqual(sum(1 for n in comps
                             if n.startswith("pocket_cutter_")), 9)
