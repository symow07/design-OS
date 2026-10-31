"""TEMPORARY (Day 9, orn_b1): B-1's Arabic lockup — the face's own outlines, the copy re-extracted word for word, the
shared output form, the lettering switches, the foil limits through the engine, and the services gate. DB-free."""
from __future__ import annotations

import math
import unicodedata
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from apps.pipeline.services import orn_b1 as O


def _union(rings):
    return unary_union([Polygon(r) for r in rings])


def test_the_module_adds_no_gate_key():
    from apps.pipeline.tests.test_palette_statistics import composed_gate
    assert composed_gate(Path(O.__file__).read_text()) == set()
