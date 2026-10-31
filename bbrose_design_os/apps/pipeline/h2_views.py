"""H2 design-request review surface (§O-session work item 3).

The CORR-1 lesson applied to the H2 pipeline: committed run trees are not
a human review boundary — the dashboard must serve them. READ-ONLY: the
page and APIs render state and artifacts; owner decisions land ONLY
through the clearance sheet (no decision endpoint exists here, by rule).

Artifact serving is whitelist-only and root-bounded: names resolve through
a per-request map built from the committed register and fixed filenames —
never from arbitrary path input.
"""
from __future__ import annotations

import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render

from apps.pipeline.services import h2_design_request as H2

PALT_H2 = os.path.join(settings.BASE_DIR, "docs", "roadmap", "palt_h2")
EMISSION_RECORD = os.path.join(settings.BASE_DIR, "docs", "roadmap",
                               "palt_m7", "ai_emission",
                               "m7_ai_emission_record.json")


def _index():
    return H2.design_request_index(PALT_H2, EMISSION_RECORD)


def _artifact_map(req_id):
    """The ONLY servable artifacts for a request: contact sheet, candidate
    preview PNGs (names from the committed register), and final-stage PNGs
    (fixed directory, .png only)."""
    if req_id not in H2.KNOWN_REQUEST_DIRS:
        raise Http404("unknown request")
    base = os.path.join(PALT_H2, req_id)
    mapping = {"contact-sheet": os.path.join(base, "contact_sheet.png")}
    reg = H2._load(os.path.join(base, "candidates",
                                "candidate_register.json")) or {}
    for c in reg.get("candidates", []):
        cid = str(c.get("candidate_id", "")).lower()
        png = str(c.get("png", ""))
        if cid and png.endswith(".png") and "/" not in png:
            mapping["candidate-" + cid] = os.path.join(
                base, "candidates", png)
    final_dir = os.path.join(base, "final")
    if os.path.isdir(final_dir):
        for fn in sorted(os.listdir(final_dir)):
            if fn.endswith(".png"):
                key = "final-" + fn[:-4].replace("_", "-").lower()
                mapping[key] = os.path.join(final_dir, fn)
    return mapping


@login_required
def h2_requests_page(request):
    return render(request, "dashboard/h2_design_requests.html",
                  {"index": _index()})


@login_required
def h2_status(request):
    return JsonResponse(_index())


@login_required
def h2_artifact(request, req_id, name):
    mapping = _artifact_map(req_id)
    path = mapping.get(name)
    if path is None or not os.path.isfile(path):
        raise Http404(name)
    resolved = os.path.realpath(path)
    if not resolved.startswith(os.path.realpath(
            os.path.join(PALT_H2, req_id)) + os.sep):
        raise Http404(name)  # root-bounded, always
    return FileResponse(open(resolved, "rb"), content_type="image/png")
