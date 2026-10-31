from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from apps.core.health import run_health_checks


@login_required
@require_GET
def serve_media(request, path):
    """GET /files/<path> — authenticated media download (local storage mode).

    Milestone 8.1: replaces the unauthenticated DEBUG-only /media/ mapping.
    Resolves the requested path against MEDIA_ROOT with strict path-traversal
    protection (fully resolve, then verify the MEDIA_ROOT prefix) and streams
    the file via FileResponse.
    """
    media_root = Path(settings.MEDIA_ROOT).resolve()
    try:
        target = (media_root / path).resolve()
    except (OSError, ValueError):
        raise Http404("Invalid path")
    if not target.is_relative_to(media_root) or not target.is_file():
        raise Http404("File not found")
    # Authored revisions have stricter role/hash checks than generic media.
    # Include staging: an unpublished file has no output-bound download route.
    if target.is_relative_to(media_root / "dielines" / "hybrid"):
        raise Http404("Use the revision's checked artifact download.")
    # §BH54(b), OWNER RULED 2026-09-18 (supersedes §BH53(b)): "The door refuses a request when the file lies under the
    # reference folders — the predicate slice 1 already withholds by — or when the file HAS a tier row that is not
    # PRODUCTION. Everything else is served as today." The tier record governs source materials; the system's own
    # outputs under MEDIA_ROOT have no row, and "no tier row" is evidence of nothing about an output — served.
    refusal = door_refusal(target, media_root)
    if refusal is not None:
        return HttpResponse(refusal, status=403, content_type="text/plain; charset=utf-8")
    from apps.core.pinned_media import IntegrityRefused, verified_master_file
    try:
        verified = verified_master_file(target, media_root, path)
    except IntegrityRefused as refused:
        return HttpResponse(str(refused), status=409, content_type="text/plain; charset=utf-8")
    if verified is not None:
        return FileResponse(verified, filename=target.name)
    return FileResponse(open(target, "rb"), filename=target.name)


def door_refusal(target: Path, media_root: Path) -> str | None:
    """§BH54(b): the refusal, by name with its code, or None when the file is served. Order: the folder clause first
    (a folder-refused file is never read), then the tier clause, which hashes the bytes and joins them to the tier
    record the way history reads tiers; a file with no row — every output the system makes — is served; a sha256 the
    record gives two tiers HAS a row that is not PRODUCTION and is refused with both named; a conditioned PRODUCTION
    row is PRODUCTION here (credit is enforced where a material is PLACED, never where a file is served)."""
    from apps.dashboard.history import REFUSED_REFERENCE_FOLDER, reference_folder, sha256_of, tiers_by_sha
    from apps.ire.materials_placement import REFUSED_REFERENCE_ASSET
    folder = reference_folder(target, media_root)
    if folder is not None:
        return f"{REFUSED_REFERENCE_FOLDER}: {target.name} — under media/{folder}, a REFERENCE-class directory (§BH54(b))"
    tiers = tiers_by_sha()
    if not tiers:
        return None
    found = tiers.get(sha256_of(target))
    if found and found != ["PRODUCTION"]:
        return f"{REFUSED_REFERENCE_ASSET}: {target.name} — tier {' + '.join(found)} by the tier record; only PRODUCTION is served (§BH54(b))"
    return None


@require_GET
def healthz(request):
    """GET /healthz — unauthenticated health probe (Milestone 8.7).

    Checks DB always; Redis + celery worker heartbeat when not in eager mode
    (eager mode reports {"celery": "eager"}). 200 when healthy, 503 otherwise.
    """
    checks = run_health_checks()
    healthy = all(value in ("ok", "eager") for value in checks.values())
    return JsonResponse(checks, status=200 if healthy else 503)
