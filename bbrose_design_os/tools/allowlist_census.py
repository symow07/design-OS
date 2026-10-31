"""A179/A182 — the allowlist census, shared by the gate and the
disposition tool so neither can drift from the other.

Lives OUTSIDE apps/pipeline/services deliberately: the census scans
that tree, and a scanner living inside its own scan target would key
its own pattern strings as occurrences.

Keys are line-independent by construction (A179): a line number is
used only to locate the enclosing symbol, and no line number enters a
key. Counts are carried so co-located occurrences cannot hide behind
each other — the defect line-keying masked.
"""
import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVICES = ROOT / "apps" / "pipeline" / "services"
BASELINE = (ROOT / "docs" / "roadmap" / "palt_m6"
            / "allowlist_baseline.json")

MEASUREMENT_MODULES = [
    'palette_axis_eligibility.py', 'palette_baked_clearance.py',
    'palette_characterization_protocol.py',
    'palette_characterization_rig.py', 'palette_flake_rig.py',
    'palette_marbling_rig.py', 'palette_material_characterization.py',
    'palette_powder_axis_diagnosis.py', 'palette_powder_rigs.py',
    'palette_powder_texture_axes.py', 'palette_raking_rig.py',
    'palette_statistics.py']

FALLBACK_SHAPES = re.compile(
    r"except\s*:|except [A-Za-z]+\s*:\s*pass|else 0\.0\b|else 1\.0\b")
A32_SHAPES = re.compile(r"\.get\([^)]+,\s*[^)]+\)"
                        r"|getattr\([^)]+,[^)]+,[^)]+\)")


def symbol_of(src, lineno):
    """The enclosing def/class — does not move when a line moves."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return "<module>"
    best = "<module>"
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)) \
                and n.lineno <= lineno <= (n.end_lineno or n.lineno):
            best = n.name
    return best


class _Elide(ast.NodeTransformer):
    """A183 — elide identifier NAMES so a rename does not move a key,
    while preserving a Call's own callee name: the callee is the
    shape, not an identifier. (The first normalizer elided it, which
    would have collapsed getattr(...) with any three-argument call —
    the wrong-normalizer failure A183 warned about, caught by its own
    demonstration.)"""

    def visit_Call(self, node):
        node.args = [self.visit(a) for a in node.args]
        node.keywords = [self.visit(k) for k in node.keywords]
        if isinstance(node.func, ast.Attribute):
            node.func.value = self.visit(node.func.value)
        return node

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="_", ctx=node.ctx), node)


def normalized_shape(match_text):
    """The expression's SHAPE, or None where the fragment does not
    parse (the regex truncates at the first ')', so a nested call in
    the default position yields an unbalanced fragment). None means
    the key falls back to text, and the key says which it is."""
    frag = " ".join(match_text.split())
    src = ("_" + frag) if frag.startswith(".") else frag
    try:
        tree = ast.parse(src, mode="eval")
    except SyntaxError:
        return None
    tree = _Elide().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree)


def key_of(name, src, start, match_text):
    line = src[:start].count("\n") + 1
    shape = normalized_shape(match_text)
    tail = (f"shape:{shape}" if shape is not None
            else f"text:{' '.join(match_text.split())}")
    return f"{name}::{symbol_of(src, line)}::{tail}"


def boundary(*, only=None):
    """A190 — a sweep reports its own enumeration boundary as DATA:
    what it searched, what it could not reach, and why, BEFORE it
    reports findings. A sweep that cannot state where it stopped has
    not established where it stopped.

    Written because a collapse sweep called four historical entries
    'era files unavailable' when they were simply in a subdirectory:
    the instrument's boundary was assumed and then the sweep was
    closed on it."""
    scanned, skipped, unreadable = [], [], []
    for p in sorted(SERVICES.rglob("*.py")):
        rel = str(p.relative_to(ROOT))
        if only and p.name not in only:
            skipped.append({"file": rel,
                            "why": "not in the declared module set"})
            continue
        try:
            p.read_text()
            scanned.append(rel)
        except OSError as exc:
            unreadable.append({"file": rel, "why": type(exc).__name__})
    return {
        "root_searched": str(SERVICES.relative_to(ROOT)),
        "recursive": True,
        "subdirectories_included": sorted(
            {str(p.parent.relative_to(SERVICES))
             for p in SERVICES.rglob("*.py")
             if p.parent != SERVICES}),
        "files_scanned": len(scanned),
        "files_skipped": len(skipped),
        "files_unreadable": unreadable,
        "not_reached_and_why": [
            "anything outside apps/pipeline/services — the gate's "
            "declared scope is the services tree",
            "non-.py files",
            "historical revisions — a sweep over committed history "
            "must materialize era sources explicitly and state that "
            "it did",
        ],
    }


def census(pattern, *, only=None, skip_refusals=False):
    counts = {}
    for path in sorted(SERVICES.rglob("*.py")):
        if only and path.name not in only:
            continue
        src = path.read_text()
        for m in pattern.finditer(src):
            if skip_refusals:
                ctx = src[max(0, m.start() - 400):m.start() + 200]
                if "INSTRUMENT_REFUSED" in ctx \
                        or "STIMULUS_NOT_REALIZED" in ctx:
                    continue
            k = key_of(path.name, src, m.start(), m.group(0))
            counts[k] = counts.get(k, 0) + 1
    return counts


def current():
    return {
        "fallbacks": census(FALLBACK_SHAPES, skip_refusals=True),
        "a32": census(A32_SHAPES, only=set(MEASUREMENT_MODULES)),
    }


def diff(found, baseline):
    """Every key whose count differs, in both directions."""
    out = {}
    for k in set(found) | set(baseline):
        f, b = found.get(k, 0), baseline.get(k, 0)
        if f != b:
            out[k] = {"found": f, "allowed": b}
    return out


def assert_outcome_space_complete(dimensions, declared_branches, *,
                                  name="declaration"):
    """A249/A241 — the standing write-time check on outcome spaces.

    An outcome space that is a product of independent dimensions is
    enumerated as the product, mechanically, never by narrative. Three
    of four fails this instantly.

    Written because A115b's enumeration was incomplete in the DOWN
    direction, the down direction is what occurred, and it executed
    correctly anyway under a separate pass condition — an incomplete
    enumeration discovered by nothing going wrong, which is the most
    dangerous way for one to be discovered.

    Reference exemplar: A150's verdict-identity states — a genuine 2x2
    with all four cells declared, including
    AGREEMENT_ACROSS_INSTRUMENT_CHANGE, the cell that exists only
    because the product was taken rather than described.
    """
    import itertools
    cells = list(itertools.product(*dimensions.values()))
    if len(declared_branches) != len(cells):
        missing = len(cells) - len(declared_branches)
        raise ValueError(
            f"{name}: outcome space is {' x '.join(str(len(v)) for v in dimensions.values())}"
            f" = {len(cells)} cells but {len(declared_branches)} branches are"
            f" declared ({missing:+d}). Enumerate the product, do not"
            f" describe the cases.")
    return {"dimensions": {k: list(v) for k, v in dimensions.items()},
            "cells": len(cells), "declared": len(declared_branches),
            "complete": True}
