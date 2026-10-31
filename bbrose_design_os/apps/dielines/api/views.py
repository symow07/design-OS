"""Dielines HTTP API (Milestone 10.1, audit H4).

All views are DRF APIViews with ``IsAuthenticated`` so anonymous callers get a
401/403 JSON response (the old login-required mixin redirected to the admin
login with a 302). Object-level authorization: a DielineJob is visible only to
its owner or staff; foreign users get a 404 (existence is not leaked).

[The clean-up of 2026-10-04 (E10d, on the owner's approved list): the pre-merge
doors no page called — POST generate/, GET inspiration/ and POST
<job_id>/save-product/ — are removed; a carton's deliverables are made only by the
shared export service on the agent path. What stays: the dimension form's live
check (qualify_dimensions/) and the authenticated per-job file route. ``file_route``
below and ``apps.dielines.api.payloads`` (the removed generate door's response)
are kept, uncalled, and named in the clean-up report.]
"""
from __future__ import annotations

from django.http import FileResponse, Http404
from django.urls import reverse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.dielines.constants import FILE_KINDS
from apps.dielines.models import DielineJob
from apps.dielines.services.export_service import resolve_export_file


def _get_owned_job_or_404(job_id, user) -> DielineJob:
    """Load a DielineJob enforcing owner-or-staff access.

    Foreign users get the same 404 as a missing job so job IDs cannot be
    probed (IDOR fix). Ownerless jobs (created by the agent path before a
    user touched them) are accessible to any authenticated user.
    """
    try:
        job = DielineJob.objects.get(pk=job_id)
    except (DielineJob.DoesNotExist, ValueError):
        raise Http404(f"DielineJob {job_id} not found")
    if job.owner is not None and job.owner != user and not user.is_staff:
        raise Http404(f"DielineJob {job_id} not found")
    return job


def file_route(job_id, kind: str) -> str:
    """URL of the authenticated per-job file route for a deliverable. [Uncalled since the clean-up of 2026-10-04
    removed the generate and inspiration doors that returned it; kept, and named in the clean-up report.]"""
    return reverse("dieline-job-file", kwargs={"job_id": str(job_id), "kind": kind})


class DielineJobFileView(APIView):
    """
    GET /api/dielines/jobs/<job_id>/files/<kind>/   (kind = svg|ai|pdf|spec)

    Authenticated, owner-or-staff download of a job deliverable. Paths are
    resolved and prefix-checked against MEDIA_ROOT (legacy jobs: against
    DIELINE_EXPORT_DIR) — traversal-safe.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, job_id, kind):
        if kind not in FILE_KINDS:
            raise Http404(f"Unknown file kind '{kind}'")
        job = _get_owned_job_or_404(job_id, request.user)
        target = resolve_export_file(job, kind)
        if target is None:
            raise Http404(f"No {kind} file for DielineJob {job_id}")
        return FileResponse(open(target, "rb"), filename=target.name)


class QualifyDimensionsView(APIView):
    """POST /api/dielines/qualify_dimensions/ (Phase 2A-9B §8).

    Live dimensional qualification for parametrically qualified archetypes:
    reports supported/unsupported with the EXACT violated constraints, the
    archetype version, its dimensional envelope, derived closure parameters,
    board compensation, assumptions, the folded collision status and the
    geometry hash. The user's dimensions are never clamped or altered —
    unsupported input stays unsupported and the preview stays disabled.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.dielines.qualification.domain import (
            domain_report,
            effective_bounds,
        )
        from apps.dielines.qualification.runner import adapter_for, qualify

        template = str(request.data.get("template") or "")
        # 2A-9D: an optional explicit version lets a reviewer qualify a
        # NON-DEFAULT version (e.g. the 1.2 D-derived correction) for
        # comparison. Omitting it qualifies the archetype's CURRENT
        # version — the default is never switched here.
        version = str(request.data.get("template_version") or "").strip()
        lookup = f"{template}@{version}" if version else template
        adapter = adapter_for(lookup) or adapter_for(template)
        if adapter is None:
            return Response({
                "qualification_available": False,
                "detail": f"{template!r} has no parametric qualification "
                          "contract yet — each archetype requires its own "
                          "domain, invariants and physical evidence",
            })
        try:
            user = {
                "width_mm": float(request.data["width_mm"]),
                "depth_mm": float(request.data["depth_mm"]),
                "height_mm": float(request.data["height_mm"]),
                "board_thickness_mm": float(
                    request.data.get("board_thickness_mm", 0.5)),
                "glue_tab_mm": float(request.data.get("glue_tab_mm", 12.0)),
                "bleed_mm": float(request.data.get("bleed_mm", 3.0)),
                "safe_margin_mm": float(
                    request.data.get("safe_margin_mm", 4.0)),
            }
        except (KeyError, TypeError, ValueError):
            return Response(
                {"error": "width_mm, depth_mm and height_mm are required "
                          "numbers"},
                status=status.HTTP_400_BAD_REQUEST)

        result = qualify(user, adapter)
        payload = {
            "qualification_available": True,
            "template_key": adapter.key,
            "supported": result.supported,
            "violations": result.violations + result.invariant_failures,
            "constraints": domain_report(adapter.domain_constraints),
            "envelope": effective_bounds(
                t=user["board_thickness_mm"], glue=user["glue_tab_mm"]),
            "geometry_hash": result.geometry_hash if result.supported else "",
            "derived": result.derived,
            "dimensions": result.dimensions,
            "collision": {"all_ok": result.folded_all_ok,
                          "checks": result.folded_checks},
            "assumptions": [
                "dimensions are INNER; external = inner + 2t (physical "
                "sample decides the allowance convention)",
                "score compression is not modelled in 0.1",
                "qualification is technical: physical validation is "
                "tracked separately per geometry hash and dimensional "
                "family",
            ],
            "authority": {
                "technical": "TECHNICALLY_QUALIFIED_DOMAIN (domain-scoped; "
                             "NOT production readiness)",
                "physical": "per geometry hash/dimensional family — see "
                            "physical_validation records",
            },
            "note": "dimensions are never clamped — correct the input to "
                    "enter the supported domain",
        }
        return Response(payload)
