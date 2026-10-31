from django.urls import path

from .api.views import (
    DielineJobFileView,
    QualifyDimensionsView,
)

# [the clean-up of 2026-10-04 (E10d): generate/, inspiration/ and <job_id>/save-product/ — the pre-merge doors no
# page called — are removed; the dimension form's live check and the authenticated file route stay]
urlpatterns = [
    path("qualify_dimensions/", QualifyDimensionsView.as_view(), name="qualify-dimensions"),
    path(
        "jobs/<uuid:job_id>/files/<str:kind>/",
        DielineJobFileView.as_view(),
        name="dieline-job-file",
    ),
]
