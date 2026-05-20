from django.urls import path

from .api.views import GenerateDielineView, InspirationView, SaveProductView

urlpatterns = [
    path("generate/", GenerateDielineView.as_view(), name="dieline-generate"),
    path("inspiration/", InspirationView.as_view(), name="inspiration"),
    path("<uuid:job_id>/save-product/", SaveProductView.as_view(), name="save-product"),
]
