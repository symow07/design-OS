"""WI-H (§Y3) — the triage of finding 5, and its verdict.

THE QUESTION. `container_visual_graph.resolve_selected_variation_identity`
opens with a fail-closed `if image is None`. WI-F recorded it as possibly dead:
`PackagingOutput.approved_image` is a `NOT NULL` ForeignKey, clearing it raises
`IntegrityError`, so "for any persisted output the branch is dead code".
§Y3 ruled that this may not be acted on either way until it is known which it
is, and that the model constraint is not the proof — the CALL SITES are.

THE VERDICT: **§Y3(c). The branch is reachable. It stays, with a behavioural
test that discriminates it.**

WHAT WAS MEASURED, AND WHY IT WAS MEASURED RATHER THAN READ
-----------------------------------------------------------
§Y3(a) says read the call sites and do not infer from the model. Reading tells
you an argument's NAME. A profile hook keyed on each function's own code
object was run over the three suites that drive this path, recording for every
entry the argument's type, its primary key and its `approved_image_id` at the
moment of the call, plus a line hook on the `raise` itself:

    reconstruct_container                 26 entries
        PackagingOutput, approved_image_id set   26      None: 0
    resolve_selected_variation_identity   32 entries
        PackagingOutput, approved_image_id set   31
        PackagingOutput, approved_image_id None   1
    the raise at container_visual_graph.py:131   EXECUTED, once,
        by IdentityTests::test_missing_approved_image_fails_closed

So: through `reconstruct_container` the branch is never taken — WI-F's reading
of the production path was right. Through the function's own contract it is
taken, today, by a test that already existed.

The instrument was wrong first and the correction is the point. Version 1 used
`sys.setprofile` for both jobs and reported the branch NEVER EXECUTED while in
the same run reporting a call that passed `approved_image_id=None`. Those
cannot both be true. Profile hooks receive call/return/exception events only,
so a local trace function returned from one is never asked for line events:
the branch could not have been observed whether or not it ran. "Never
executed" was a property of the instrument, and it was the answer that would
have justified deleting the branch. Reachability needs `sys.settrace`.

MUTATION EVIDENCE. The two branch lines were deleted, the three suites run,
and the file restored by copy and verified sha256-identical
(`60dbb355c03e8c7ba9baff87bb75042e414c988ee4082debade1894b369c0f13`). Exactly
one test failed — `IdentityTests::test_missing_approved_image_fails_closed` —
with `AttributeError: 'NoneType' object has no attribute 'prompt_used'` from
the line that had been sitting behind the guard. The branch is load-bearing.

WHAT THE EXISTING TEST'S ASSERTION IS ACTUALLY WORTH. It asserts
`exc.value.code == SELECTED_CONTAINER_VARIATION_IDENTITY_REQUIRED`. `code` is
a CLASS attribute of `SelectedVariationIdentityError`, carried identically by
all four raises in that function, so it cannot tell you WHICH branch fired.
What caught the mutation was `pytest.raises(...)` on the exception type, not
the `.code` line — the same shape of defect §Y2 is about, in a test that is
otherwise behavioural. `reason` is per-raise, so the tests below assert that
instead and pair each with the sibling it must not be confused for.

§Y3(d) IS WHERE THE ORIGINAL READING WENT WRONG. `IntegrityError` is evidence
about the database, not about the code path, and here the two genuinely
disagree. The database does refuse a null column. The code path never asks it
to: the branch is reached by an in-memory instance and no write is attempted,
because Django raises `RelatedObjectDoesNotExist` for a cleared non-null FK
and that exception subclasses `AttributeError` — which is exactly what
`getattr(output, "approved_image", None)` swallows to produce the `None` the
branch tests. Both facts are pinned below, since the whole finding turned on
mistaking one for the other.
"""
from __future__ import annotations

import ast
import base64
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.core.models import Brand, Product
from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
from apps.pipeline.services import container_contract as cc
from apps.pipeline.services import container_visual_graph as cvg
from apps.pipeline.targets import DesignTarget

APPS = Path(cvg.__file__).parents[2]

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4"
    "z8Dwn4EBAAT/Af9jZv5kAAAAAElFTkSuQmCC")

#: The branch's own words, distinct from every sibling raise in the function.
BRANCH_REASON = "no approved image on the output"
SIBLING_REASON = "the approved image has no persisted prompt to verify against"


def _call_sites(func_name: str) -> dict[str, list[int]]:
    """``"apps/..." -> [line, ...]`` for every textual call of ``func_name``.

    Structural rather than substring — an import or a docstring mention is not
    a call site — but still a statement about TEXT. See the guard below for
    what that does and does not establish.
    """
    sites: dict[str, list[int]] = {}
    for path in sorted(APPS.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except (SyntaxError, UnicodeDecodeError):       # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = (fn.attr if isinstance(fn, ast.Attribute)
                    else fn.id if isinstance(fn, ast.Name) else None)
            if name == func_name:
                rel = str(path.relative_to(APPS.parent))
                sites.setdefault(rel, []).append(node.lineno)
    return sites


class TestTheCallSiteEnumeration:
    """§Y3(a) — the enumeration the ruling asked for, kept where it can rot
    loudly. If a second production caller appears, the triage below was
    performed against a world that no longer exists and has to be redone."""

    def test_source_guard_reconstruct_container_has_one_production_call_site(self):
        """SOURCE-STRING GUARD (§Y2). Enumerates calls by parsing source.
        **It asserts nothing about behaviour** and is not citable as coverage
        (§Y2(c)): a call site that exists in text may never execute, and one
        that executes may pass anything at all. What establishes what the call
        sites actually PASS is the profile-hook measurement in the module
        docstring, and what establishes reachability is the behavioural pair
        in ``TestTheBranchIsReachedNotMerelyPresent``.

        Its job is narrow and real: to fail when the enumeration §Y3's triage
        rests on stops being the enumeration.
        """
        sites = _call_sites("reconstruct_container")
        production = {p for p in sites if "/tests/" not in p}
        assert production == {"apps/pipeline/agents/aria.py"}

    def test_source_guard_the_branchs_function_has_one_production_call_site(self):
        """SOURCE-STRING GUARD (§Y2). As above — a textual enumeration, no
        behavioural claim, not citable as coverage (§Y2(c)). The branch lives
        in ``resolve_selected_variation_identity``, so its callers are what
        the triage is about; ``reconstruct_container`` is the only one, which
        is why the two questions were ever conflated.
        """
        sites = _call_sites("resolve_selected_variation_identity")
        production = {p for p in sites if "/tests/" not in p}
        assert production == {"apps/pipeline/targets/container/__init__.py"}


class _Case(TestCase):
    def setUp(self):
        self.brand = Brand.objects.create(name="B", master_brief="x")
        self.product = Product.objects.create(
            brand=self.brand, product_id="CO-Y3", name="Rose Nectar",
            category="CO", year=2026, product_type="bottle")
        self.task = DesignTask.objects.create(
            brand=self.brand, product=self.product, task_text="a bottle",
            status="awaiting_container_profile",
            design_target=DesignTarget.PRODUCT_CONTAINER.value)

    def _output(self, *, prompt="A luxe rose bottle, ROSE NECTAR"):
        img = GeneratedImage.objects.create(
            task=self.task, direction_name="D", prompt_used=prompt,
            variation_number=1, reference_provenance={})
        img.image_file.save("c.png", ContentFile(_PNG), save=True)
        return PackagingOutput.objects.create(
            task=self.task, approved_image=img,
            spec_sheet={"backend": "container", "product_name": "Rose Nectar",
                        cc.PROFILE_SCHEMA: cc.build_inferred_profile("bottle")})


class TestTheBranchIsReachedNotMerelyPresent(_Case):
    """§Y3(c). Reachable, so it gets a behavioural test and stays."""

    def test_the_branch_raises_with_its_own_reason(self):
        out = self._output()
        out.approved_image = None
        with pytest.raises(cvg.SelectedVariationIdentityError) as exc:
            cvg.resolve_selected_variation_identity(self.task, out)
        assert exc.value.reason == BRANCH_REASON

    def test_the_sibling_path_raises_with_a_different_reason(self):
        """The control. Without it, the test above is satisfied by any
        fail-closed exit from the function, which is the weakness that made
        the pre-existing ``.code`` assertion worth less than it looked: `code`
        is one class attribute shared by every raise, so it is constant across
        exactly the alternatives a branch test needs to tell apart."""
        out = self._output(prompt="   ")
        with pytest.raises(cvg.SelectedVariationIdentityError) as exc:
            cvg.resolve_selected_variation_identity(self.task, out)
        assert exc.value.reason == SIBLING_REASON
        assert exc.value.reason != BRANCH_REASON

    def test_the_two_paths_are_indistinguishable_by_the_code_alone(self):
        """Stated as a fact about the module rather than left implicit, so
        that a future reader who reaches for ``.code`` to identify a branch
        finds out here instead of in a survivor report."""
        out = self._output()
        out.approved_image = None
        with pytest.raises(cvg.SelectedVariationIdentityError) as branch:
            cvg.resolve_selected_variation_identity(self.task, out)
        with pytest.raises(cvg.SelectedVariationIdentityError) as sibling:
            cvg.resolve_selected_variation_identity(
                self.task, self._output(prompt=""))
        assert branch.value.code == sibling.value.code
        assert branch.value.reason != sibling.value.reason


class TestWhyItIsReachableAtAll(_Case):
    """The mechanism, pinned. Django's behaviour here is the entire reason a
    ``NOT NULL`` column does not make this branch dead, and a version that
    changed it would silently turn a fail-closed refusal into an
    ``AttributeError`` on the next line."""

    def test_a_cleared_non_null_foreign_key_raises_an_attributeerror_subclass(self):
        out = self._output()
        out.approved_image = None
        with pytest.raises(AttributeError):
            out.approved_image                                  # noqa: B018

    def test_which_is_why_getattr_with_a_default_yields_none(self):
        """``resolve_selected_variation_identity`` reads the field exactly
        this way, so this is the line that manufactures the ``None`` the
        branch tests for — not a database row, not a migration."""
        out = self._output()
        out.approved_image = None
        assert getattr(out, "approved_image", None) is None


class TestTheDatabaseIsNotTheCodePath(_Case):
    """§Y3(d) — both halves, because the finding turned on merging them."""

    def test_the_database_does_refuse_the_null_when_asked_to_store_it(self):
        """WI-F's observation, reproduced and correctly labelled: this is
        evidence about the COLUMN. It is true, and it was never the
        question."""
        out = self._output()
        out.approved_image = None
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                out.save()

    def test_but_the_branch_is_reached_without_asking_it_to(self):
        """...and this is the answer to the question that was asked. The
        branch is reached with no write attempted, so the constraint never
        gets a say. An `IntegrityError` met while trying to reach a branch
        says the route through the database is closed; it says nothing about
        whether the branch has another route in, and here it does.
        """
        out = self._output()
        pk, before = out.pk, out.approved_image_id
        out.approved_image = None
        with pytest.raises(cvg.SelectedVariationIdentityError) as exc:
            cvg.resolve_selected_variation_identity(self.task, out)
        assert exc.value.reason == BRANCH_REASON
        stored = PackagingOutput.objects.get(pk=pk)
        assert stored.approved_image_id == before          # nothing was written
