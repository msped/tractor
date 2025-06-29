from django.urls import path
from .views import (CaseListCreateView, CaseDetailView,
                    DocumentListCreateView, DocumentDetailView)

urlpatterns = [
    path('cases', CaseListCreateView.as_view(), name='case-list-create'),
    path('cases/<uuid:case_id>', CaseDetailView.as_view(), name='case-detail'),
    path(
        'cases/<uuid:case_id>/detail',
        CaseDetailView.as_view(),
        name='case-detail'
    ),
    path('cases/<uuid:case_id>/documents',
         DocumentListCreateView.as_view(), name='document-list-create'),
    path(
        'cases/documents/<uuid:document_id>',
        DocumentDetailView.as_view(),
        name='document-detail'
    ),
]
