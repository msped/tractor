from django.urls import path
from .views import (
    CaseListCreateView,
    CaseDetailView,
    DocumentListCreateView,
    DocumentDetailView,
    DocumentReviewView,
    RedactionListCreateView,
    CaseExportView,
    RedactionDetailView,
    RedactionContextView,
)

urlpatterns = [
    path('cases', CaseListCreateView.as_view(), name='case-list-create'),
    path('cases/<uuid:case_id>', CaseDetailView.as_view(), name='case-detail'),
    path('cases/<uuid:case_id>/export',
         CaseExportView.as_view(), name='case-export'),
    path('cases/<uuid:case_id>/documents',
         DocumentListCreateView.as_view(), name='document-list-create'),
    path(
        'cases/documents/<uuid:document_id>',
        DocumentDetailView.as_view(),
        name='document-detail'
    ),
    path('cases/<uuid:case_id>/document/<uuid:document_id>/review',
         DocumentReviewView.as_view(),
         name='document-review',
         ),
    path('cases/document/<uuid:document_id>/redaction',
         RedactionListCreateView.as_view(),
         name='redaction-list-create'),
    path('cases/document/redaction/<uuid:pk>',
         RedactionDetailView.as_view(), name='redaction-detail'),
    path('cases/document/redaction/<uuid:redaction_id>/context',
         RedactionContextView.as_view(),
         name='redaction-context'),
]
