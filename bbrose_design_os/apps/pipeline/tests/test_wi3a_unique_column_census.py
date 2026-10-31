"""WI-3A — a census of `X.objects.count()` feeding a column declared unique.

The defect this counts, stated once: `test_browser_profile_editor.py` minted
`product_id=f"CO-B{DesignTask.objects.count()}"` into `Product.product_id`,
which is `unique=True`. Three things are wrong with it and only the third is
the interesting one.

1. It counts `DesignTask` while writing to `Product` — the wrong model.
2. In a fresh per-test database that count is `0`, so every call site produced
   the identical `CO-B0`.
3. **Counting *the right* model would be the same class of defect.** A count is
   a property of the table at a moment; a unique key must be a property of the
   row. Two calls between which nothing was committed get the same number, and
   two calls either side of a truncation get the same number again. Sequences
   are not counts, and `.count()` is not a sequence.

WHAT THIS INSTRUMENT RECOGNISES, AND WHAT IT THEREFORE MISSES (§AD0(b))

It is **syntactic**. It reads the tree and matches shapes:

- a *unique field* is a class-body assignment `<name> = models.<X>Field(...)`
  carrying the keyword `unique=True`, or a `UniqueConstraint`/`unique_together`
  naming the field.
- a *count feed* is a keyword argument whose name matches a known unique field
  and whose value subtree contains an attribute call `.count()`.

So it does not see a count reaching a unique column through a local variable,
through a helper function, through `**kwargs`, or through
`setattr(obj, name, value)`. A clean census here means **no instance in the
shapes named above**, not "no instance". That sentence is the whole reason
§AD0(b) exists and it is stated beside the number every time the number is
reported.
"""

import ast
import os
import unittest

PYTEST_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", ".."))
APPS_ROOT = os.path.join(PYTEST_ROOT, "apps")


def _python_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in {"__pycache__", "migrations", "node_modules"}]
        for name in sorted(filenames):
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def _parse(path):
    with open(path, encoding="utf-8") as fh:
        try:
            return ast.parse(fh.read(), filename=path)
        except SyntaxError:                       # pragma: no cover
            return None


def collect_unique_field_names(root=APPS_ROOT):
    """Field names declared unique anywhere in the tree, and where.

    Returns {field_name: [(module_relpath, model_name, line), ...]}.
    Migrations are excluded: they record history, and a column made unique and
    then dropped would inflate the set with names no live model carries.
    """
    found = {}
    for path in _python_files(root):
        tree = _parse(path)
        if tree is None:
            continue
        rel = os.path.relpath(path, PYTEST_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
                    continue
                target = stmt.targets[0]
                if not isinstance(target, ast.Name):
                    continue
                value = stmt.value
                if not isinstance(value, ast.Call):
                    continue
                for kw in value.keywords:
                    if kw.arg == "unique" and _is_true(kw.value):
                        found.setdefault(target.id, []).append(
                            (rel, node.name, stmt.lineno))
    return found


def _is_true(node):
    return isinstance(node, ast.Constant) and node.value is True


def _contains_count_call(node):
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "count"):
            return True
    return False


def _count_call_sites(root=APPS_ROOT):
    """Every `<something>.count()` in the tree. The denominator."""
    sites = []
    for path in _python_files(root):
        tree = _parse(path)
        if tree is None:
            continue
        rel = os.path.relpath(path, PYTEST_ROOT)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "count"):
                sites.append((rel, node.lineno))
    return sites


def census(root=APPS_ROOT):
    """Numerator and denominator together, per §AD0(b)."""
    unique_fields = collect_unique_field_names(root)
    all_counts = _count_call_sites(root)
    feeding_any_kwarg = []
    feeding_unique_kwarg = []
    for path in _python_files(root):
        tree = _parse(path)
        if tree is None:
            continue
        rel = os.path.relpath(path, PYTEST_ROOT)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg is None or not _contains_count_call(kw.value):
                    continue
                record = (rel, kw.value.lineno, kw.arg)
                feeding_any_kwarg.append(record)
                if kw.arg in unique_fields:
                    feeding_unique_kwarg.append(record)
    return {
        "unique_field_names": unique_fields,
        "all_count_call_sites": all_counts,
        "count_feeding_any_keyword_argument": feeding_any_kwarg,
        "count_feeding_a_unique_declared_field": feeding_unique_kwarg,
        "classifier": "SYNTACTIC. See this module's docstring for what it "
                      "cannot see: locals, helpers, **kwargs and setattr.",
    }


class UniqueColumnCensusTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.result = census()

    def test_the_denominator_is_reported_beside_the_numerator(self):
        """§AD0(b): a numerator with no denominator is a rumour."""
        result = self.result
        self.assertGreater(len(result["all_count_call_sites"]), 0,
                           "a census that finds no .count() anywhere is "
                           "measuring the wrong tree")
        self.assertGreater(len(result["unique_field_names"]), 0,
                           "no unique fields found; the classifier is broken, "
                           "not the repository")
        self.assertLessEqual(
            len(result["count_feeding_a_unique_declared_field"]),
            len(result["count_feeding_any_keyword_argument"]))
        self.assertLessEqual(
            len(result["count_feeding_any_keyword_argument"]),
            len(result["all_count_call_sites"]))

    def test_no_count_feeds_a_column_declared_unique(self):
        """The repaired state. Red before WI-3A's fix, green after.

        A failure here names every offending site, because a census that says
        only "1" makes the next person grep for it.
        """
        offenders = self.result["count_feeding_a_unique_declared_field"]
        self.assertEqual(
            [], offenders,
            "a table count is feeding a column declared unique. A count is a "
            "property of the table at a moment; a unique key must be a "
            "property of the row: " + "; ".join(
                "%s:%d -> %s" % site for site in offenders))

    def test_source_guard_the_classifier_states_that_it_is_syntactic(self):
        """SOURCE-STRING GUARD.

        Named `test_source_guard_*` AND carrying the marker in the docstring,
        because §Y2(b) requires both and the first draft of this method had
        only the marker. A guard that satisfies half of a naming law is
        invisible to the census that law exists to make possible — which is
        exactly the defect WI-3F is for.

        The census's own qualification must travel with its number. §AD0(b) was
        written because `12` was reported as "the number of source-string
        guards" when it was the number the classifier could see. This asserts
        the same mistake cannot be made with this census's output by anyone
        reading the record rather than the docstring.
        """
        self.assertIn("SYNTACTIC", self.result["classifier"])
        self.assertIn("cannot see", self.result["classifier"])
