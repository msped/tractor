from django.urls import path

from .views import (
    BulkRedactionUpdateView,
    CaseDetailView,
    CaseExportView,
    CaseListCreateView,
    DocumentCancelProcessingView,
    DocumentDetailView,
    DocumentListCreateView,
    DocumentResubmitView,
    DocumentReviewView,
    ExemptionTemplateDetailView,
    ExemptionTemplateListView,
    RedactionContextView,
    RedactionDetailView,
    RedactionListCreateView,
)

urlpatterns = [
    path("cases/exemptions", ExemptionTemplateListView.as_view(),
         name="exemption-template-list"),
    path("cases/exemptions/<int:pk>", ExemptionTemplateDetailView.as_view(),
         name="exemption-template-detail"),
    path("cases", CaseListCreateView.as_view(), name="case-list-create"),
    path("cases/<uuid:case_id>", CaseDetailView.as_view(), name="case-detail"),
    path("cases/<uuid:case_id>/export",
         CaseExportView.as_view(), name="case-export"),
    path("cases/<uuid:case_id>/documents",
         DocumentListCreateView.as_view(), name="document-list-create"),
    path("cases/documents/<uuid:document_id>",
         DocumentDetailView.as_view(), name="document-detail"),
    path(
        "cases/documents/<uuid:document_id>/resubmit",
        DocumentResubmitView.as_view(),
        name="document-resubmit",
    ),
    path(
        "cases/documents/<uuid:document_id>/cancel",
        DocumentCancelProcessingView.as_view(),
        name="document-cancel",
    ),
    path(
        "cases/<uuid:case_id>/document/<uuid:document_id>/review",
        DocumentReviewView.as_view(),
        name="document-review",
    ),
    path(
        "cases/document/<uuid:document_id>/redaction", RedactionListCreateView.as_view(), name="redaction-list-create"
    ),
    path("cases/document/redaction/<uuid:pk>",
         RedactionDetailView.as_view(), name="redaction-detail"),
    path(
        "cases/document/<uuid:document_id>/redactions/bulk/",
        BulkRedactionUpdateView.as_view(),
        name="bulk-redaction-update",
    ),
    path(
        "cases/document/redaction/<uuid:redaction_id>/context", RedactionContextView.as_view(), name="redaction-context"
    ),
]
