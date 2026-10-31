"""RBV-3 review-package surface (CORR-1 applied to the RBV programme).

Committed packages are not a human review boundary — the dashboard must
serve them. READ-ONLY: the page and APIs render committed package state
and artifacts; owner decisions land ONLY through the clearance sheet after
batching in OWNER_REVIEW_QUEUE.md (no decision endpoint exists here, by
rule).

Artifact serving is whitelist-only and root-bounded: names resolve
through a per-package map built from the committed package manifest —
never from arbitrary path input; ``.png`` only.
"""
from __future__ import annotations

import json
import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render

from apps.pipeline.services.rbv3_review_package import MANIFEST_NAME

#: committed RBV evidence root — referenced views resolve inside it, and
#: nowhere else
EVIDENCE_ROOT = os.path.join(settings.BASE_DIR, "docs", "visual_quality",
                             "rbv")
PACKAGES_ROOT = os.path.join(EVIDENCE_ROOT, "review_packages")


def _packages() -> list[dict]:
    out = []
    if not os.path.isdir(PACKAGES_ROOT):
        return out
    for pid in sorted(os.listdir(PACKAGES_ROOT)):
        manifest_path = os.path.join(PACKAGES_ROOT, pid, MANIFEST_NAME)
        if os.path.isfile(manifest_path):
            manifest = json.load(open(manifest_path))
            out.append({"package_id": pid, "manifest": manifest})
    return out


def _artifact_map(package_id: str) -> dict:
    """The ONLY servable artifacts for a package: the contact sheet, the
    reference PNGs (both in-package) and the mode-A view PNGs (REFERENCED
    from the committed render evidence, per the package storage policy) —
    all by manifest name, never from path input.

    Returns ``{name: (path, root)}``; every path is bounded to its root.
    """
    base = os.path.join(PACKAGES_ROOT, package_id)
    manifest_path = os.path.join(base, MANIFEST_NAME)
    if not os.path.isfile(manifest_path):
        raise Http404("unknown package")
    manifest = json.load(open(manifest_path))
    mapping = {"contact-sheet":
               (os.path.join(base, manifest["contact_sheet"]["file"]), base)}
    mode_a = manifest["modes"]["GEOMETRY_VALIDATION"]
    source_dir = os.path.join(settings.BASE_DIR, mode_a["view_source_dir"])
    for view, entry in mode_a["views"].items():
        fn = str(entry.get("source_file", ""))
        if fn.endswith(".png") and "/" not in fn:
            mapping["view-" + view] = (os.path.join(source_dir, fn),
                                       EVIDENCE_ROOT)
    for i, ref in enumerate(manifest.get("references", [])):
        fn = str(ref.get("file", ""))
        if fn.endswith(".png") and "/" not in fn:
            mapping[f"reference-{i}"] = (os.path.join(base, fn), base)
    return mapping


@login_required
def rbv3_packages_page(request):
    return render(request, "dashboard/rbv3_review_packages.html",
                  {"packages": _packages()})


@login_required
def rbv3_status(request):
    return JsonResponse({"schema": "rbv3_dashboard_index/1.0",
                         "packages": _packages()})


@login_required
def rbv3_artifact(request, package_id, name):
    entry = _artifact_map(package_id).get(name)
    if entry is None or not os.path.isfile(entry[0]):
        raise Http404(name)
    path, root = entry
    resolved = os.path.realpath(path)
    if not resolved.startswith(os.path.realpath(root) + os.sep):
        raise Http404(name)  # root-bounded, always
    return FileResponse(open(resolved, "rb"), content_type="image/png")
