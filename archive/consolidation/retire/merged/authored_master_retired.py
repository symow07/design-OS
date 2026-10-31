"""The authored masters' page names, archived with their pages (the owner's goal of 2026-10-29). Copied whole
from bbrose_design_os/apps/pipeline/services/authored_master.py, hybrid_boundary.py and views.py at a634230; kept as text."""

# authored_master.page_name
def page_name(task):
    return 'dashboard:assembly_master_task' if backend(task)=='hybrid_assembly' else 'dashboard:hybrid_master_task'


# hybrid_boundary.HybridBoundaryMiddleware.process_view — the redirect to the authoring page
        if match.namespace == "dashboard" and match.url_name in ("design", "design_adjust", "history_task"):
            from apps.pipeline.services.authored_master import page_name
            return redirect(page_name(task), task_id=task_id)


# views.TaskStatusView.get — the authoring page link
        if is_authored(task):
            from django.urls import reverse
            from apps.pipeline.services.authored_master import page_name
            return Response({"id": task.pk, "status": task.status, "authoring_backend": task.options["authoring_backend"],
                             "creative_acceptance": "review_pending", "production_ready": False,
                             "revision": task.options.get("current_revision"),
                             "page_url": reverse(page_name(task), args=[task.pk])})
