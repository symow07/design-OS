"""WI-T — §Z1(b) as a DIMENSIONAL ANALYSIS, so the unit is computed and not spelled.

WHY A THIRD INSTRUMENT, WHEN TWO ALREADY WATCH THIS RULE
---------------------------------------------------------
§Z1(b): *"No `size_pt` anywhere in this repo may be derived from a millimetre
quantity. A type size is chosen as type."* Two instruments already exist and
each has a blind spot that the other does not close.

**The grep.** WI-Q measured it: searching `compose_container.py` for `size_pt`
finds four lines and misses `centered_text(name, text, cx, y, size, ...)`,
where the size is the **fifth positional argument** and the word `size_pt`
never appears at the call site. 17 of 21 nodes, and the four it misses are
the four that matter.

**WI-Q's perturbation harness.** It moves the product's millimetres and asks
which `size_pt` values moved. That is a real behavioural test and it caught 25
sites. But it can only see clause **(B)**, scale-dependence — and §Z1(c) names
the exact shape it cannot see::

    front-support = max(3.4, zh * 0.034)

At every scale in use the literal wins, so the value **never moves**, and a
harness that perturbs millimetres and watches the output reports it clean. It
is still a point size derived from a millimetre length. §Z1(c) calls this out
as the proof that the units "are not merely wrong, they are not consistent
with each other" — a defect that is invisible to perturbation *by
construction*, because the literal floor is what hides it.

So this module computes clause **(A)**: is the number dimensionally a point
size? It reads the code, but it does not read the code as TEXT — it walks the
AST and does exponent arithmetic on millimetre and point. `zh * 0.14` is
millimetres because `zh` is millimetres, whatever it is called; and
`p.width * 2.835 * 0.075` is points because 2.835 is a mm->pt conversion,
even though a string search for "mm" would condemn it. §Y2's objection to
source-string guards is that they compare spellings; this compares dimensions.

WHAT IT REFUSES TO GUESS
-------------------------
`UNKNOWN` is the default and it never produces a finding. A quantity earns a
dimension only from a declared root, a suffix, a conversion constant, or
arithmetic over things that already have one. Everything else stays unknown
and is silently allowed. **This under-reports on purpose**: an analyser that
guesses produces a register nobody trusts, and the register is the deliverable.

The declared roots below are the semantic content of this instrument, and they
are assumptions about THIS repository, written down rather than buried:
`.width`/`.height`/`.x`/`.y` on a geometry object are millimetres; the bare
literals 2.835 and 0.35278 are unit conversions rather than magic numbers.

THE COEFFICIENT ASSUMPTION, AND WHY THE FIRST VERSION FOUND NOTHING
--------------------------------------------------------------------
The first working version of this module was run against
`compose_container.py` — the file §AB names as carrying the sprint's only live
production defect — and reported **nothing at all**. The cause was the strict
rule that unknown times anything is unknown::

    lx, ly, lw, lh = backbone.label_zone        # mm, from a declared root
    zx, zy, zw, zh = px(lx), py(ly), lw * s, lh * s

`s` is the sheet's scale factor and carries no suffix, so `lh * s` was unknown,
so `zh` was unknown, so `zh * 0.14` was unknown, and the defect the instrument
was built to catch was invisible to it. **One untyped coefficient anywhere
upstream erased the dimension of everything downstream.** That is not
conservatism, it is collapse: the strict rule makes the analyser silent on
real code rather than cautious about it.

So under `*` and `/` an operand with no known dimension is read as a
**dimensionless coefficient**. `lh * s` is millimetres. This is an assumption
and it can be wrong: an unrecognised conversion *function* — something this
file's `CONVERSION_LITERALS` and `NAMED_CONSTANTS` do not list — would be read
as a coefficient and its result given the wrong dimension.

Because it can be wrong, every dimension that used it is marked `ASSUMED`
rather than `EXACT`, and every finding records whether it needed the
assumption. :func:`certain` and :func:`assumed` split the register in two, so
"how much of this rests on the assumption" is a number rather than a worry.
Addition, `max` and `min` never use it — an unknown operand there still
produces unknown — because those are the operations where two genuinely
different dimensions meet, and guessing at that boundary would manufacture
exactly the MIXED findings the instrument exists to report.

WHAT IT CANNOT DO, STATED SO IT IS NOT DISCOVERED LATER
---------------------------------------------------------
It is intra-procedural and flow-insensitive: assignments are read in source
order and the last one wins, so a dimension set inside one branch of an `if`
is visible after it. It does not follow a value into a helper function it does
not know, so a size laundered through an untyped helper comes back UNKNOWN and
is allowed. It has no notion of a loop carrying a dimension forward.

Each of those is a way for a real violation to escape, and none of them is
hypothetical. This instrument raises the floor; it is not a proof.
"""
from __future__ import annotations

import ast
import pathlib
from dataclasses import dataclass
from typing import Iterable, Optional

#: Exponent pairs. ``Dim(1, 0)`` is a length in millimetres, ``Dim(0, 1)`` a
#: size in points, ``Dim(0, 0)`` a dimensionless ratio. A mm->pt conversion is
#: ``Dim(-1, 1)``: it cancels a millimetre and produces a point.
UNKNOWN = "unknown"
LITERAL = "literal"
EXACT = "exact"
#: the exponents are believed, but the coefficient assumption was used to get
#: them — see the module docstring. A dimension, with its provenance attached.
ASSUMED = "assumed"


@dataclass(frozen=True)
class Dim:
    """A quantity's dimension as exponents of millimetre and point."""

    mm: int = 0
    pt: int = 0
    kind: str = EXACT

    # -- constructors ------------------------------------------------------
    @staticmethod
    def unknown() -> "Dim":
        return Dim(0, 0, UNKNOWN)

    @staticmethod
    def literal() -> "Dim":
        """A bare number. Dimensionally neutral until context gives it one —
        `8.0` in a point sink is 8 points, and in a `max()` beside a
        millimetre length it is the literal floor §Z1(c) is about."""
        return Dim(0, 0, LITERAL)

    # -- predicates --------------------------------------------------------
    @property
    def is_unknown(self) -> bool:
        return self.kind == UNKNOWN

    @property
    def is_literal(self) -> bool:
        return self.kind == LITERAL

    @property
    def is_definite(self) -> bool:
        """Has exponents worth comparing. ASSUMED counts — the assumption is
        recorded on the finding, not used to suppress it."""
        return self.kind in (EXACT, ASSUMED)

    @property
    def is_mm(self) -> bool:
        return self.is_definite and (self.mm, self.pt) == (1, 0)

    @property
    def is_pt(self) -> bool:
        return self.is_definite and (self.mm, self.pt) == (0, 1)

    @property
    def is_ratio(self) -> bool:
        return self.is_definite and (self.mm, self.pt) == (0, 0)

    def __str__(self) -> str:
        if self.is_unknown:
            return "?"
        if self.is_literal:
            return "lit"
        parts = []
        for label, exp in (("mm", self.mm), ("pt", self.pt)):
            if exp:
                parts.append(label if exp == 1 else f"{label}^{exp}")
        body = "*".join(parts) if parts else "1"
        return f"~{body}" if self.kind == ASSUMED else body


MM = Dim(1, 0)
PT = Dim(0, 1)
RATIO = Dim(0, 0)
#: multiply a millimetre by this to get points
PT_PER_MM = Dim(-1, 1)
#: multiply a point by this to get millimetres
MM_PER_PT = Dim(1, -1)


# --- the declared semantics of THIS repository -------------------------------

#: Named constants whose dimension is known. These are the repo's own spellings
#: of the two conversions; see `back_panel.MM_PER_PT` and `geometry_report`.
NAMED_CONSTANTS = {
    "MM_PER_PT": MM_PER_PT,
    "_MM_PER_PT": MM_PER_PT,
    "PT_TO_MM": MM_PER_PT,
    "_PT_TO_MM": MM_PER_PT,
    "PT_PER_MM": PT_PER_MM,
    "_PT_PER_MM": PT_PER_MM,
    "MM_TO_PT": PT_PER_MM,
    "_MM_TO_PT": PT_PER_MM,
}

#: Bare numeric literals that are conversions rather than coefficients. The
#: repo writes `p.width * 2.835 * 0.075` and means it; WI-J's defence of
#: `compose.py` rests on exactly this reading, so the analyser has to share it
#: or it would condemn the code WI-J correctly exonerated.
CONVERSION_LITERALS = {
    2.835: PT_PER_MM,
    2.8346: PT_PER_MM,
    2.83465: PT_PER_MM,
    2.834645669291339: PT_PER_MM,
    0.35278: MM_PER_PT,
    0.352778: MM_PER_PT,
    0.3527777777777778: MM_PER_PT,
}

#: Attribute names that hold millimetres on this repo's geometry objects.
#: `.width` on a panel is a millimetre length; there is no pixel geometry in
#: `apps/ire`. Declared rather than inferred, and wrong the day that changes.
MM_ATTRIBUTES = {
    "width", "height", "x", "y", "w", "h",
    "label_zone", "flat_width", "flat_height",
}

#: Mapping-key spellings that hold millimetres, e.g. `zone["height"]`.
MM_KEYS = {"width", "height", "x", "y", "w", "h"}

#: Owners whose geometry is in POINTS, not millimetres. PyMuPDF's `page.rect`
#: is a PDF rectangle and PDF user space is points — `page.rect.width` is the
#: one `.width` in this repo that is not a millimetre, and reading it as one
#: made `w_mm = page.rect.width / MM_TO_PT` look like a unit error when it is
#: the correct conversion.
PT_ATTRIBUTE_OWNERS = {"rect", "mediabox", "cropbox"}

#: Callables that return their argument's dimension unchanged. `px`/`py` are
#: the sheet's mm->mm projection closures; without them the analyser loses the
#: zone origin and under-reports.
DIMENSION_PRESERVING = {"px", "py", "float", "abs", "round", "int"}

#: Callables that always return a dimensionless COUNT. Without this, a
#: character count is unknown, and `mm / (count * mm_per_pt)` cannot be shown
#: to be the point size it is — a legitimate fit-to-width reads as a violation.
#: `int` belongs above, NOT here: truncating a millimetre yields a millimetre.
#: Putting it here invented a MIXED in `palt_m4b_a_evidence.py` on first run.
COUNT_CALLS = {"len", "ord"}

#: Call sinks that REQUIRE a dimension. Positional index or keyword -> Dim.
#: `centered_text` is the whole reason this file exists: its size is the fifth
#: POSITIONAL argument, which is what made it invisible to a grep for `size_pt`.
CALL_SINKS = {
    "centered_text": {2: MM, 3: MM, 4: PT, "size_pt": PT, "cx": MM, "y": MM},
    "TextRun": {"size_pt": PT, "x": MM, "y": MM},
}

#: Any keyword argument with this name is a point size, whatever it is called on.
PT_KEYWORDS = {"size_pt"}


@dataclass(frozen=True)
class Finding:
    """One dimensional contradiction, at the line that commits it."""

    path: str
    line: int
    kind: str
    expr: str
    detail: str
    #: False when the coefficient assumption was needed to reach this
    #: dimension. A finding, with the strength of its own evidence attached.
    certain: bool = True

    @property
    def key(self) -> tuple:
        """Stable identity for a register that may only shrink."""
        return (pathlib.Path(self.path).name, self.line, self.kind)

    def __str__(self) -> str:
        mark = "" if self.certain else " (assumed)"
        return (f"{pathlib.Path(self.path).name}:{self.line} {self.kind}: "
                f"{self.expr}  [{self.detail}]{mark}")


#: A point size built from a millimetre length. §Z1(b) verbatim.
PT_FROM_MM = "PT_FROM_MM"
#: A millimetre length built from a point size with no conversion — §Z1(b)
#: running backwards, which is the shape WI-P fixed in `compose_dropper`.
MM_FROM_PT = "MM_FROM_PT"
#: `max()`, `min()` or `+` over two DEFINITE and DIFFERENT dimensions.
MIXED = "MIXED"


class _FunctionScope(ast.NodeVisitor):
    """Dimensions for the names in one function body."""

    def __init__(self, analyser: "UnitAnalyser", parent: Optional[dict] = None):
        self.a = analyser
        self.names: dict[str, Dim] = dict(parent or {})
        #: name -> line it was last assigned on. A violation is reported at the
        #: SINK, which is often far from the line that built the quantity;
        #: without this the register points at the call and not at the
        #: arithmetic, and §AB names the arithmetic.
        self.origins: dict[str, int] = {}

    # -- expression dimension ---------------------------------------------
    def dim(self, node: ast.AST) -> Dim:
        meth = getattr(self, "_dim_" + type(node).__name__, None)
        return meth(node) if meth else Dim.unknown()

    def _dim_Constant(self, node: ast.Constant) -> Dim:
        if isinstance(node.value, bool) or not isinstance(
                node.value, (int, float)):
            return Dim.unknown()
        conv = CONVERSION_LITERALS.get(round(float(node.value), 12))
        return conv if conv is not None else Dim.literal()

    def _dim_Name(self, node: ast.Name) -> Dim:
        if node.id in self.names:
            return self.names[node.id]
        if node.id in NAMED_CONSTANTS:
            return NAMED_CONSTANTS[node.id]
        return self.a.suffix_dim(node.id)

    def _dim_Attribute(self, node: ast.Attribute) -> Dim:
        if node.attr in NAMED_CONSTANTS:
            return NAMED_CONSTANTS[node.attr]
        suffix = self.a.suffix_dim(node.attr)
        if not suffix.is_unknown:
            return suffix
        if node.attr in MM_ATTRIBUTES:
            owner = node.value
            name = (owner.attr if isinstance(owner, ast.Attribute)
                    else owner.id if isinstance(owner, ast.Name) else "")
            return PT if name.lower() in PT_ATTRIBUTE_OWNERS else MM
        return Dim.unknown()

    def _dim_Subscript(self, node: ast.Subscript) -> Dim:
        key = node.slice
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            suffix = self.a.suffix_dim(key.value)
            if not suffix.is_unknown:
                return suffix
            if key.value in MM_KEYS:
                return MM
        return Dim.unknown()

    def _dim_UnaryOp(self, node: ast.UnaryOp) -> Dim:
        return self.dim(node.operand) if isinstance(
            node.op, (ast.UAdd, ast.USub)) else Dim.unknown()

    def _dim_BinOp(self, node: ast.BinOp) -> Dim:
        left, right = self.dim(node.left), self.dim(node.right)
        if isinstance(node.op, ast.Mult):
            return self._combine_mul(left, right, +1)
        if isinstance(node.op, ast.Div):
            return self._combine_mul(left, right, -1)
        if isinstance(node.op, (ast.Add, ast.Sub)):
            return self._agree((left, right), node, "+/-")
        if isinstance(node.op, (ast.Pow, ast.Mod, ast.FloorDiv)):
            return Dim.unknown()
        return Dim.unknown()

    def _combine_mul(self, left: Dim, right: Dim, sign: int) -> Dim:
        """Exponents add under `*` and subtract under `/`.

        An unknown operand is read as a dimensionless coefficient and the
        result is marked ASSUMED — the module docstring explains why the
        strict alternative made the analyser silent on real code.
        """
        if left.is_unknown and right.is_unknown:
            return Dim.unknown()
        if left.is_literal and right.is_literal:
            return Dim.literal()
        # A bare number multiplied by a CONVERSION was written in the unit the
        # conversion consumes — `5 * MM_TO_PT` is five millimetres expressed in
        # points, not a loose mm^-1*pt. This is what a conversion means, so the
        # result is its OUTPUT unit and the reading is exact.
        if sign > 0 and (left.is_literal or right.is_literal):
            other = right if left.is_literal else left
            if _is_conversion(other):
                return PT if (other.mm, other.pt) == (-1, 1) else MM
        if left.is_unknown or right.is_unknown:
            known = right if left.is_unknown else left
            # The assumption earns its keep ONLY when the known side carries a
            # real length or size. Against a literal or a plain ratio it tells
            # us nothing; against a CONVERSION it contradicts itself, because a
            # conversion exists precisely to change dimension, so the quantity
            # it multiplies is by definition not dimensionless. Both refusals
            # were bought with false positives: `sizes[index] * 2.835` came out
            # mm^-1*pt and condemned a line WI-J had already exonerated, and
            # `adv_b * 2 * k` did the same once `adv_b * 2` had been laundered
            # into a literal. An unknown stays unknown until it meets a
            # dimension worth propagating.
            if (known.is_literal or known.is_ratio or _is_conversion(known)
                    or not known.is_definite):
                return Dim.unknown()
            lm, lp = (0, 0) if left.is_unknown else (left.mm, left.pt)
            rm, rp = (0, 0) if right.is_unknown else (right.mm, right.pt)
            return Dim(lm + sign * rm, lp + sign * rp, ASSUMED)
        kind = ASSUMED if ASSUMED in (left.kind, right.kind) else EXACT
        return Dim(left.mm + sign * right.mm,
                   left.pt + sign * right.pt, kind)

    def _dim_Call(self, node: ast.Call) -> Dim:
        name = _callee(node)
        if name in COUNT_CALLS:
            return RATIO
        if name in ("max", "min") and node.args:
            return self._agree([self.dim(a) for a in node.args], node, name)
        if name in DIMENSION_PRESERVING and node.args:
            return self.dim(node.args[0])
        return Dim.unknown()

    def _dim_GeneratorExp(self, node) -> Dim:
        """`max(len(ln) for ln in lines)` — the generator's dimension is its
        element's. Without this the whole call collapses to unknown."""
        return self.dim(node.elt)

    _dim_ListComp = _dim_GeneratorExp
    _dim_SetComp = _dim_GeneratorExp

    def visit_Compare(self, node: ast.Compare) -> None:
        """`a > b` over two different dimensions is the same defect as `a + b`.

        Added after the instrument had already been run over the repo: the
        re-fit test in `compose_container` reads
        ``longest * size * _CHAR_W > zw * 0.94``, comparing a POINT width
        against a MILLIMETRE one. Nothing is assigned and nothing reaches a
        sink, so the assignment and call-sink checks both walked past it. A
        comparison is where a unit error decides a branch, which is worse than
        where it decides a number.
        """
        self.generic_visit(node)
        if len(node.ops) != 1 or isinstance(
                node.ops[0], (ast.Is, ast.IsNot, ast.In, ast.NotIn)):
            return
        self._agree((self.dim(node.left), self.dim(node.comparators[0])),
                    node, "comparison")

    def _dim_IfExp(self, node: ast.IfExp) -> Dim:
        return self._agree((self.dim(node.body), self.dim(node.orelse)),
                           node, "conditional")

    def _agree(self, dims: Iterable[Dim], node: ast.AST, what: str) -> Dim:
        """Combine operands that must share a dimension.

        A LITERAL adopts whatever it sits beside — `max(8.0, zh * 0.14)` is a
        literal floor over a millimetre length, and the contradiction is
        reported where the result reaches a point sink, not here. Two DEFINITE
        and different dimensions are reported here, because `max(pt, mm)` is
        already wrong regardless of where it goes.

        The coefficient assumption is NOT used here: one unknown operand and
        the whole expression is unknown. `+`, `max` and `min` are where two
        real dimensions meet, and guessing at that boundary would manufacture
        the very findings this instrument exists to report.
        """
        dims = list(dims)
        real = [d for d in dims if d.is_definite]
        if any(d.is_unknown for d in dims):
            return Dim.unknown()
        if not real:
            return Dim.literal()
        first = real[0]
        self.a.checks += len(real) - 1
        for other in real[1:]:
            if (other.mm, other.pt) != (first.mm, first.pt):
                self.a.report(node, MIXED, f"{what} over {first} and {other}",
                              certain=not any(d.kind == ASSUMED
                                              for d in (first, other)))
                return Dim.unknown()
        kind = ASSUMED if any(d.kind == ASSUMED for d in real) else EXACT
        return Dim(first.mm, first.pt, kind)

    # -- statements --------------------------------------------------------
    def visit_Assign(self, node: ast.Assign) -> None:
        self.generic_visit(node)
        value = self.dim(node.value)
        for target in node.targets:
            self._bind(target, value, node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self.generic_visit(node)
        if node.value is not None:
            self._bind(node.target, self.dim(node.value), node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self.generic_visit(node)
        if isinstance(node.target, ast.Name) and isinstance(
                node.op, (ast.Add, ast.Sub)):
            self._agree((self.names.get(node.target.id, Dim.unknown()),
                         self.dim(node.value)), node, "augmented +/-")

    def _bind(self, target: ast.AST, value: Dim, node: ast.AST) -> None:
        if isinstance(target, ast.Name):
            self.origins[target.id] = getattr(node, "lineno", 0)
            # NAMED_CONSTANTS outranks the suffix law: `_PT_TO_MM` ends in
            # `_mm` and is not a millimetre, it is the conversion INTO one.
            # An explicit declaration beats a pattern in the name every time.
            if target.id in NAMED_CONSTANTS:
                self.names[target.id] = NAMED_CONSTANTS[target.id]
                return
            declared = self.a.suffix_dim(target.id)
            if not declared.is_unknown:
                self._check(value, declared, node, target.id)
                self.names[target.id] = declared
            else:
                self.names[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            elts = (node.value.elts
                    if isinstance(getattr(node, "value", None),
                                  (ast.Tuple, ast.List))
                    else None)
            # `a, *rest = pair` and any mis-shaped unpack: the positional
            # correspondence breaks down, so fall back to the whole value's
            # dimension rather than indexing off the end. Found by running the
            # analyser over the repo, which is the only way it surfaces.
            if elts is not None and (len(elts) != len(target.elts)
                                     or any(isinstance(e, ast.Starred)
                                            for e in target.elts)):
                elts = None
            for i, elt in enumerate(target.elts):
                self._bind(elt, self.dim(elts[i]) if elts else value, node)

    def visit_Call(self, node: ast.Call) -> None:
        self.generic_visit(node)
        sinks = CALL_SINKS.get(_callee(node), {})
        for index, arg in enumerate(node.args):
            expected = sinks.get(index)
            if expected is not None:
                self._check(self.dim(arg), expected, arg, f"arg {index}")
        for kw in node.keywords:
            expected = sinks.get(kw.arg)
            if expected is None and kw.arg in PT_KEYWORDS:
                expected = PT
            if expected is not None:
                self._check(self.dim(kw.value), expected, kw.value,
                            f"{kw.arg}=")

    def _check(self, actual: Dim, expected: Dim, node: ast.AST,
               where: str) -> None:
        if not actual.is_definite:
            return
        self.a.checks += 1
        if (actual.mm, actual.pt) == (expected.mm, expected.pt):
            return
        # A dimensionless quantity satisfies any sink. `size_pt=9.0` is a type
        # size chosen as type, which is §Z1(b) being OBEYED; calling it
        # PT_FROM_MM would be a mislabel, and a register full of mislabels is
        # worse than a smaller true one. Only real exponents contradict.
        if actual.is_ratio:
            return
        kind = (PT_FROM_MM if expected.is_pt else
                MM_FROM_PT if expected.is_mm else MIXED)
        detail = f"{where} wants {expected} and got {actual}"
        if isinstance(node, ast.Name) and node.id in self.origins:
            detail += f"; {node.id} built on line {self.origins[node.id]}"
        self.a.report(node, kind, detail, certain=actual.kind == EXACT)

    # -- nested functions get their own scope ------------------------------
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.a.walk_function(node, parent=self.names)

    visit_AsyncFunctionDef = visit_FunctionDef


def _is_conversion(dim: Dim) -> bool:
    """A dimension that trades one unit for the other, in either direction."""
    return dim.is_definite and (dim.mm, dim.pt) in ((-1, 1), (1, -1))


def _callee(node: ast.Call) -> str:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


class UnitAnalyser:
    """Dimensional analysis of one source file."""

    def __init__(self, path: str, source: str):
        self.path = path
        self.source = source
        self.lines = source.splitlines()
        self.findings: list[Finding] = []
        #: how many times a dimension was actually COMPARED against another.
        #: WI-Q's lesson: a violation count with no denominator can be made to
        #: look small by an analyser that quietly stopped looking.
        self.checks = 0

    @staticmethod
    def suffix_dim(name: str) -> Dim:
        """§Z1(a) is a naming law, so the suffix IS a declaration.

        Case-folded, because the repo writes module constants in caps and
        `DIVIDER_WIDTH_PT` is every bit as much a declaration as `size_pt`.
        The case-sensitive first version missed both of them and then let the
        coefficient assumption invent a dimension for the gap it left.
        """
        lowered = name.lower()
        # `_mm_per_pt` / `_pt_per_mm` DECLARE a conversion, and the naming law
        # should be able to say so: a rate is as declarable as a length. This
        # is what lets a call site express "millimetres of advance per point of
        # size" and be read as the exact arithmetic it is, instead of as the
        # bare coefficient it used to be.
        if lowered.endswith("_mm_per_pt"):
            return MM_PER_PT
        if lowered.endswith("_pt_per_mm"):
            return PT_PER_MM
        # `px_per_mm` ends in `_mm` and is the RECIPROCAL of a millimetre.
        # Three sites in the repo are named that way and the first version
        # read every one of them as a length, then reported the arithmetic
        # around them as MIXED. A density is not a length.
        if lowered.endswith("_per_mm") or lowered.endswith("_per_pt"):
            return Dim.unknown()
        if lowered.endswith("_mm") or lowered.endswith("_mm_"):
            return MM
        if lowered.endswith("_pt"):
            return PT
        return Dim.unknown()

    def report(self, node: ast.AST, kind: str, detail: str,
               certain: bool = True) -> None:
        line = getattr(node, "lineno", 0)
        text = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append(
            Finding(self.path, line, kind, text, detail, certain))

    def walk_function(self, node: ast.AST, parent: Optional[dict] = None) -> None:
        scope = _FunctionScope(self, parent)
        args = getattr(node, "args", None)
        if args is not None:
            for arg in (list(args.posonlyargs) + list(args.args) +
                        list(args.kwonlyargs)):
                dim = self.suffix_dim(arg.arg)
                if not dim.is_unknown:
                    scope.names[arg.arg] = dim
        for stmt in node.body:
            scope.visit(stmt)

    def run(self) -> list[Finding]:
        """Every finding in this source, and `self.checks` beside it.

        WI-3E: THE ACCUMULATORS ARE RESET HERE, and they were not always. This
        method re-walked and APPENDED, so a second call on one instance returned
        two findings where there is one and left `checks` at two where it is
        one — measured (1,1) -> (2,2) -> (3,3). Both halves of this instrument's
        register scaled with how many times somebody asked.

        It was latent rather than live, and that was checked rather than
        assumed: `census()` builds one analyser per file and calls this once.
        The reason it was worth repairing anyway is that the duplicate findings
        carry an IDENTICAL key, so the corruption was invisible to the register
        test that compares a SET of keys and visible only to the one that
        compares a length. A defect that hides from the thorough-looking test
        and shows in the formality is not one to leave for a caller who retries.

        Resetting rather than memoising, deliberately: this makes `run()` a
        function of `self.source` and nothing else, which is what all four
        call sites already assume. Memoising would preserve the assumption and
        add a cache to be invalidated.
        """
        self.findings = []
        self.checks = 0
        tree = ast.parse(self.source)
        module = _FunctionScope(self)
        for stmt in tree.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.walk_function(stmt)
            elif isinstance(stmt, ast.ClassDef):
                for sub in stmt.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.walk_function(sub)
                    else:
                        module.visit(sub)
            else:
                module.visit(stmt)
        self.findings.sort(key=lambda f: (f.line, f.kind))
        return self.findings


def analyse_source(source: str, path: str = "<source>") -> list[Finding]:
    """Dimensional findings for a snippet. The negative controls use this."""
    return UnitAnalyser(path, source).run()


def analyse_path(path) -> list[Finding]:
    p = pathlib.Path(path)
    return UnitAnalyser(str(p), p.read_text()).run()


def certain(findings: Iterable[Finding]) -> list[Finding]:
    """The findings that did NOT need the coefficient assumption."""
    return [f for f in findings if f.certain]


def assumed(findings: Iterable[Finding]) -> list[Finding]:
    """The findings that DID. Kept countable so the cost of the assumption is
    a number rather than a caveat."""
    return [f for f in findings if not f.certain]


def census(root, pattern: str = "*.py") -> tuple[list[Finding], int]:
    """Every module under `root`: its findings AND the number of dimension
    comparisons that produced them.

    Both halves, from one walk, because they are only meaningful together.
    A register of seven means nothing until the denominator is beside it —
    seven out of eight hundred is an instrument that looked and mostly found
    nothing, and seven out of nine is an instrument that barely looked. WI-Q
    made the same point about its own backlog and it applies harder here,
    because this analyser can go quiet by DESIGN: every `UNKNOWN` is a place
    it declined to guess, and enough of them would produce a clean register
    that means only that the analyser stopped seeing.
    """
    out: list[Finding] = []
    checks = 0
    for path in sorted(pathlib.Path(root).rglob(pattern)):
        if "__pycache__" in path.parts:
            continue
        try:
            analyser = UnitAnalyser(str(path), path.read_text())
            out.extend(analyser.run())
            checks += analyser.checks
        except SyntaxError:                                  # pragma: no cover
            continue
    return out, checks


def analyse_tree(root, pattern: str = "*.py") -> list[Finding]:
    """Every module under `root`, sorted, so the register is reproducible."""
    return census(root, pattern)[0]
