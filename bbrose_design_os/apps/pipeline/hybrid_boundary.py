"""Keep authored masters outside all legacy task mutation/acceptance routes."""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin


class HybridBoundaryMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        if not match or match.namespace not in ("pipeline", "dashboard") or match.url_name.startswith(("hybrid_", "assembly_")):
            return None
        from apps.pipeline.models import DesignTask, GeneratedImage, PackagingOutput
        from apps.pipeline.services.authored_master import is_authored
        task_id = view_kwargs.get("task_id")
        if task_id is None and "image_id" in view_kwargs:
            task_id = GeneratedImage.objects.filter(pk=view_kwargs["image_id"]).values_list("task_id", flat=True).first()
        if task_id is None and "output_id" in view_kwargs:
            task_id = PackagingOutput.objects.filter(pk=view_kwargs["output_id"]).values_list("task_id", flat=True).first()
        if task_id is None:
            return None
        task = DesignTask.objects.filter(pk=task_id).only("options").first()
        if not task or not is_authored(task):
            return None
        # Authentication stays ahead of task details; do not disclose a private task to anonymous callers.
        if not request.user.is_authenticated:
            return None
        from apps.pipeline.permissions import ALL_ROLES, user_has_role
        if not user_has_role(request.user, *ALL_ROLES):
            return JsonResponse({"error": "Your account has no team role."}, status=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            return JsonResponse({"error": "This authored master is review pending. Edit it on its authoring page; legacy approval and generation do not apply.",
                                 "code": "HYBRID_REVIEW_PENDING"}, status=409)
        if match.namespace == "dashboard" and match.url_name in ("design", "design_adjust", "history_task"):
            from apps.pipeline.services.authored_master import RETIRED_PAGE
            return JsonResponse({"error": RETIRED_PAGE, "code": "HYBRID_PAGE_RETIRED"}, status=410)
        if match.namespace == "pipeline" and match.url_name == "task_status":
            return None
        return JsonResponse({"error": "Use the authoring page and its checked revision downloads.",
                             "code": "HYBRID_LEGACY_READ_UNAVAILABLE"}, status=409)
