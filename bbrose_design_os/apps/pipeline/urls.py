from django.urls import path

from . import views

app_name = "pipeline"

urlpatterns = [
    path("tasks/", views.TaskListView.as_view(), name="list_tasks"),
    path("tasks/create/", views.TaskCreateView.as_view(), name="create_task"),
    path("tasks/<int:task_id>/status/", views.TaskStatusView.as_view(), name="task_status"),
    path("tasks/<int:task_id>/gate1_approve/", views.Gate1ApproveView.as_view(), name="gate1_approve"),
    path("tasks/<int:task_id>/gate1_reject/", views.Gate1RejectView.as_view(), name="gate1_reject"),
    path("tasks/<int:task_id>/confirm_dimensions/", views.ConfirmDimensionsView.as_view(), name="confirm_dimensions"),
    path("tasks/<int:task_id>/gate2_approve/", views.Gate2ApproveView.as_view(), name="gate2_approve"),
    path("tasks/<int:task_id>/retry/", views.TaskRetryView.as_view(), name="task_retry"),
    path("tasks/<int:task_id>/download_spec/", views.SpecSheetDownloadView.as_view(), name="download_spec"),
]
