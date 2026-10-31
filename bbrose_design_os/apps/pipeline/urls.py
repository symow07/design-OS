from django.urls import path

from . import live_views, notifications_views, views

app_name = "pipeline"

urlpatterns = [
    # 2C-2A-CORR-3 — Web Research review (§17)
    path("web-research/sessions/<int:session_id>/",
         views.WebResearchSessionView.as_view(), name="web_research_session"),
    path("web-research/sources/<int:source_id>/decision/",
         views.WebSourceDecisionView.as_view(), name="web_source_decision"),
    path("web-research/sources/<int:source_id>/thumbnail/",
         views.WebSourceThumbnailView.as_view(), name="web_source_thumbnail"),
    path("web-research/sessions/<int:session_id>/visual-review/<str:kind>/",
         views.WebResearchVisualReviewFileView.as_view(),
         name="web_visual_review_file"),
    path("web-research/sessions/<int:session_id>/visual-review-corr1/"
         "<str:kind>/",
         views.WebResearchVisualReviewFileView.as_view(
             manifest_key="visual_review_corr1"),
         name="web_visual_review_corr1_file"),
    # Milestone 12.4 — notifications
    path("notifications/", notifications_views.NotificationListView.as_view(), name="notifications"),
    path("notifications/mark_read/", notifications_views.NotificationMarkReadView.as_view(), name="notifications_mark_read"),
    path("notifications/preferences/", notifications_views.NotificationPreferenceView.as_view(), name="notification_prefs"),
    path("tasks/", views.TaskListView.as_view(), name="list_tasks"),
    path("tasks/create/", views.TaskCreateView.as_view(), name="create_task"),
    # §BH69(2): one inspiration picture read into words before a design is started
    path("inspiration/read/", views.InspirationReadView.as_view(), name="inspiration_read"),
    path("tasks/<int:task_id>/inspiration/", views.TaskInspirationView.as_view(), name="task_inspiration"),
    path("tasks/<int:task_id>/status/", views.TaskStatusView.as_view(), name="task_status"),
    # [his goal of 2026-10-13, (6)] the design's drawings, large on its page
    path("tasks/<int:task_id>/drawing/", views.DrawingViewsView.as_view(), name="task_drawing_views"),
    path("tasks/<int:task_id>/drawing/<int:page>.png", views.DrawingPictureView.as_view(), name="task_drawing_picture"),
    # Milestone 13.2 — SSE live updates
    path("tasks/<int:task_id>/events/", live_views.task_events, name="task_events"),
    # [his goal of 2026-10-06, item 2] where a waiting design stands, asked by its open page
    path("tasks/<int:task_id>/where/", live_views.task_where, name="task_where"),
    path("tasks/<int:task_id>/select_direction/", views.SelectDirectionView.as_view(), name="select_direction"),
    path("tasks/<int:task_id>/gate1_approve/", views.Gate1ApproveView.as_view(), name="gate1_approve"),
    path("tasks/<int:task_id>/gate1_reject/", views.Gate1RejectView.as_view(), name="gate1_reject"),
    path("tasks/<int:task_id>/concept_redraw/", views.ConceptRedrawView.as_view(), name="concept_redraw"),
    path("tasks/<int:task_id>/confirm_dimensions/", views.ConfirmDimensionsView.as_view(), name="confirm_dimensions"),
    path("tasks/<int:task_id>/size_flags/", views.SizeFlagsView.as_view(), name="size_flags"),
    # [his final goal, 2026-10-05, C5] his choice of a stopped label's offers
    path("tasks/<int:task_id>/label_offer/", views.LabelOfferView.as_view(), name="label_offer"),
    path("tasks/<int:task_id>/print_data/", views.PrintDataView.as_view(), name="print_data"),
    # [his answers after 122 was redrawn, 2026-10-08, (1)] his optional SKU, at any time
    path("tasks/<int:task_id>/sku/", views.DesignSkuView.as_view(), name="design_sku"),
    path("tasks/<int:task_id>/confirm_container_profile/", views.ConfirmContainerProfileView.as_view(), name="confirm_container_profile"),
    path("tasks/<int:task_id>/propose_container_zones/", views.ProposeContainerZonesView.as_view(), name="propose_container_zones"),
    # §BH71 PART 3: learn the lid shape the approved concept shows
    path("tasks/<int:task_id>/learn_shape/", views.LearnShapeView.as_view(), name="learn_shape"),
    # §BH71 PART 2: the trend board — one click on a picture, the press, a thumbnail from quarantine
    path("tasks/<int:task_id>/trends/continue/", views.TrendContinueView.as_view(), name="trend_continue"),
    path("tasks/<int:task_id>/trends/<int:pick_id>/", views.TrendPickView.as_view(), name="trend_pick"),
    path("tasks/<int:task_id>/trends/<int:pick_id>/thumbnail/", views.TrendThumbnailView.as_view(),
         name="trend_thumbnail"),
    path("tasks/<int:task_id>/reconstruction-artifact/<str:role>/",
         views.ReconstructionArtifactView.as_view(),
         name="reconstruction_artifact"),
    path("tasks/<int:task_id>/gate2_approve/", views.Gate2ApproveView.as_view(), name="gate2_approve"),
    # [his review of 119, 2026-10-05, point 6] the label's translations confirmed by a person
    path("tasks/<int:task_id>/confirm_translations/", views.ConfirmTranslationsView.as_view(),
         name="confirm_translations"),
    path("tasks/<int:task_id>/gate2_reject/", views.Gate2RejectView.as_view(), name="gate2_reject"),
    path("tasks/<int:task_id>/retry/", views.TaskRetryView.as_view(), name="task_retry"),
    path("tasks/<int:task_id>/rerun_images/", views.RerunImagesView.as_view(), name="rerun_images"),
    path("tasks/<int:task_id>/download_spec/", views.SpecSheetDownloadView.as_view(), name="download_spec"),
    path("tasks/<int:task_id>/concept_references/", views.ConceptReferenceCandidatesView.as_view(), name="concept_references"),
    path("tasks/<int:task_id>/concept_references/approve/", views.ConceptReferenceApproveView.as_view(), name="concept_references_approve"),
    path("tasks/<int:task_id>/generate_handoff/", views.GenerateHandoffView.as_view(), name="generate_handoff"),
    path("concept_references/<int:reference_id>/thumbnail/", views.ConceptReferenceThumbnailView.as_view(), name="concept_reference_thumbnail"),
    path("images/<int:image_id>/redownload/", views.ImageRedownloadView.as_view(), name="image_redownload"),
    path("images/<int:image_id>/update_prompt/", views.ImagePromptUpdateView.as_view(), name="image_update_prompt"),
    path("tasks/<int:task_id>/references/<int:reference_id>/",
         views.task_reference_file,
         name="task-reference-file"),
]
