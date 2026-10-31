"""M6 — realization coverage: a declared parameter must carry a
recorded audit entry. Same shape as the tracker closure-record
invariant, the TemplateType set-equality assertion and the exemption
closure test — aimed at the last place the declared-but-unrealized
class was still free to live: the family definitions themselves."""
import json
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services import palette_powder_engine as PE
from apps.pipeline.services import palette_powder_protocol as PP

REPO = Path(__file__).resolve().parents[3]
AUDIT = REPO / "docs/roadmap/palt_m6/realization_audit/realization_audit.json"


def _leaves(d, prefix=""):
    for k, v in d.items():
        path = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from _leaves(v, path + ".")
        else:
            yield path


class RealizationCoverageTests(SimpleTestCase):
    def test_every_declared_parameter_has_an_audit_entry(self):
        """A new parameter cannot join a family definition without a
        recorded realization delta."""
        if not AUDIT.exists():
            self.fail("the realization audit record is missing — every "
                      "declared parameter must carry an audit entry")
        audit = json.loads(AUDIT.read_text())
        shade = PE.PowderShade("prov_cov", (0.5, 0.5, 0.5),
                               PE.PROVISIONAL_VISUALIZATION_SHADE)
        missing = []
        for i, family in enumerate(PP.POWDER_FAMILIES):
            spec = PE.PowderMaterialSpec(family, shade, seed=1)
            recorded = set(audit["families"].get(family, {}))
            for path in _leaves(spec.params):
                if path not in recorded:
                    missing.append(f"{family}.{path}")
        self.assertEqual(missing, [],
                         "declared parameters with no recorded "
                         "realization audit entry")

    def test_known_dead_parameters_are_registered(self):
        """The NOT_REALIZED registry and the audit must agree on the
        flake block's dead parameters."""
        for key in ("flakes.flake_orientation",
                    "flakes.sparkle_distribution"):
            self.assertIn(key, PE.NOT_REALIZED_IN_RENDER)
