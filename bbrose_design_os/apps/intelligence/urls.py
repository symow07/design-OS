from django.urls import path

from . import views

app_name = "intelligence"

urlpatterns = [
    path("search/", views.intelligence_search, name="search"),
    # separate POST endpoint: /search/ stays strictly GET-only and never calls out
    path("search/semantic/", views.intelligence_semantic_search, name="semantic-search"),
    path("corpus/", views.corpus_list, name="corpus-list"),
    path("corpus/<uuid:item_id>/", views.corpus_detail, name="corpus-detail"),
    path("reviews/", views.review_queue, name="review-queue"),
    path("reviews/<uuid:candidate_id>/", views.review_detail, name="review-detail"),
    path("reviews/<uuid:candidate_id>/claim/", views.review_claim, name="review-claim"),
    path("reviews/<uuid:candidate_id>/release/", views.review_release,
         name="review-release"),
    path("reviews/<uuid:candidate_id>/classify/", views.review_classify,
         name="review-classify"),
    path("reviews/<uuid:candidate_id>/correct/", views.review_correct,
         name="review-correct"),
    path("reviews/<uuid:candidate_id>/semantic-metadata/resolve-conflict/",
         views.review_resolve_semantic_metadata_conflict,
         name="review-resolve-semantic-metadata-conflict"),
    path("reviews/<uuid:candidate_id>/preview/<uuid:evidence_id>/",
         views.review_evidence_preview, name="review-evidence-preview"),
    path("reviews/<uuid:candidate_id>/semantic-metadata/",
         views.review_record_semantic_metadata, name="review-record-semantic-metadata"),
    path("reviews/<uuid:candidate_id>/semantic-metadata/correct/",
         views.review_correct_semantic_metadata, name="review-correct-semantic-metadata"),
    path("reviews/<uuid:candidate_id>/assess-evidence/", views.review_assess_evidence,
         name="review-assess-evidence"),
    path("reviews/<uuid:candidate_id>/request-clarification/",
         views.review_request_clarification, name="review-request-clarification"),
    path("reviews/<uuid:candidate_id>/governance/attest/",
         views.governance_attest, name="governance-attest"),
    path("reviews/<uuid:candidate_id>/governance/finalize/",
         views.governance_finalize, name="governance-finalize"),
    path("reviews/<uuid:candidate_id>/governance/<str:event_id>/revoke/",
         views.governance_revoke, name="governance-revoke"),
]
