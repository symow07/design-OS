"""C1 — the template registry and the TemplateType enum must agree.

Two templates (ecma_a20_20_01_01_ste_carton,
reference_opposed_tuck_carton) were registered and renderable but not
enumerable, so some code paths could reach them and others could not —
the declared-versus-realized defect class wearing dieline clothes. The
enum gained the two members; this test pins the lists together so a
third divergence cannot appear silently in either direction.
"""
from django.test import SimpleTestCase

from apps.dielines import registry
from apps.dielines.models import TemplateType


class TemplateRegistryAgreementTests(SimpleTestCase):
    def test_registry_ids_and_enum_values_are_the_same_set(self):
        registered = {defn.template_id
                      for defn in registry._REGISTRY.values()}
        enumerated = set(TemplateType.values)
        self.assertEqual(
            registered, enumerated,
            "a template registered without an enum member is reachable "
            "by some code paths and not others; an enum member without "
            "a registration promises a template that does not exist")
