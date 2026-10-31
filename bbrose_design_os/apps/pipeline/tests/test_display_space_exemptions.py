"""Gate C — the exemption set is closed and enumerable."""
from pathlib import Path

from django.test import SimpleTestCase

from apps.pipeline.services.display_space_exemptions import (
    DISPLAY_SPACE_EXEMPT_MODULES)

REPO = Path(__file__).resolve().parents[3]
TOKEN = "DISPLAY_SPACE_BY_DECLARATION"


class ExemptionSetClosureTests(SimpleTestCase):
    def test_declared_set_equals_marked_set(self):
        marked = set()
        for path in (REPO / "apps").rglob("*.py"):
            rel = str(path.relative_to(REPO))
            if "display_space_exemptions" in rel or "/tests/" in rel:
                continue
            if TOKEN in path.read_text(errors="ignore"):
                marked.add(rel)
        self.assertEqual(
            marked, set(DISPLAY_SPACE_EXEMPT_MODULES),
            "a module carrying the exemption token must be in the "
            "declared registry and vice versa — the set is CLOSED; a "
            "ninth site appears only by failing this test")

    def test_every_exempt_module_states_its_reason(self):
        for rel in DISPLAY_SPACE_EXEMPT_MODULES:
            text = (REPO / rel).read_text()
            idx = text.index(TOKEN)
            self.assertIn("(", text[idx:idx + 60],
                          f"{rel}: the exemption must carry its reason")
