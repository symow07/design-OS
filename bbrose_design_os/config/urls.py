from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from apps.core.views import healthz, serve_media

from apps.pipeline import h2_views, rbv_views, vq_views

urlpatterns = [
    path("api/design-requests/", h2_views.h2_status),
    path("api/design-requests/<slug:req_id>/<slug:name>/",
         h2_views.h2_artifact),
    path("dashboard/design-requests/", h2_views.h2_requests_page),
    path("api/visual-quality/rbv3/", rbv_views.rbv3_status),
    path("api/visual-quality/rbv3/<slug:package_id>/<slug:name>/",
         rbv_views.rbv3_artifact),
    path("dashboard/visual-quality/rbv3/", rbv_views.rbv3_packages_page),
    path("api/visual-quality/vq1/", vq_views.vq1_status),
    path("api/visual-quality/vq1/<slug:name>/", vq_views.vq1_artifact),
    path("dashboard/visual-quality/vq1/", vq_views.vq1_review_page),
    path("dashboard/visual-quality/vq1/decision/",
         vq_views.vq1_review_decision),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("api/", include("apps.pipeline.urls")),
    path("api/dielines/", include("apps.dielines.urls")),
    path("dashboard/", include("apps.dashboard.urls")),
    path("intelligence/", include("apps.intelligence.urls")),
    # Unauthenticated liveness/readiness probe (Milestone 8.7).
    path("healthz", healthz, name="healthz"),
    # Authenticated media downloads (local storage backend) — registered in
    # BOTH debug and production. The old DEBUG-only static() mapping that
    # served /media/ without auth was removed (Milestone 8.1 / audit C1).
    path("files/<path:path>", serve_media, name="serve_media"),
    path("", RedirectView.as_view(url="/dashboard/", permanent=False)),
]
