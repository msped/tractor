from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_q.models import OrmQ
from rest_framework import status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Case,
    Document,
    DocumentExportSettings,
    ExemptionTemplate,
    Redaction,
    RedactionContext,
    ReviewWorkflowSettings,
)
from .reviews import ReviewError, open_review
from .serializers import (
    BulkByTextSerializer,
    BulkCaseDeleteSerializer,
    BulkRedactionUpdateSerializer,
    CaseDetailSerializer,
    CaseSerializer,
    DocumentExportSettingsSerializer,
    DocumentReviewSerializer,
    DocumentSerializer,
    ExemptionTemplateSerializer,
    ExportSerializer,
    InternalReviewSerializer,
    RedactionContextSerializer,
    RedactionSerializer,
    ReviewWorkflowSettingsSerializer,
)
from .span_merging import serialize_merge_structure


class DocumentExportSettingsView(APIView):
    """
    GET/PATCH the singleton document export settings (admin only).
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        serializer = DocumentExportSettingsSerializer(
            DocumentExportSettings.get()
        )
        return Response(serializer.data)

    def patch(self, request):
        serializer = DocumentExportSettingsSerializer(
            DocumentExportSettings.get(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ReviewWorkflowSettingsView(APIView):
    """
    GET/PATCH the singleton review workflow settings (admin only).
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        serializer = ReviewWorkflowSettingsSerializer(
            ReviewWorkflowSettings.get()
        )
        return Response(serializer.data)

    def patch(self, request):
        serializer = ReviewWorkflowSettingsSerializer(
            ReviewWorkflowSettings.get(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ExemptionTemplateListView(ListCreateAPIView):
    """
    GET: Returns all active exemption templates for use in the rejection dialog.
    POST: Creates a new exemption template (admin only).
    """

    serializer_class = ExemptionTemplateSerializer
    queryset = ExemptionTemplate.objects.filter(is_active=True)

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [IsAuthenticated()]


class ExemptionTemplateDetailView(RetrieveUpdateDestroyAPIView):
    """
    GET/PATCH/DELETE a single exemption template.
    """

    permission_classes = [IsAdminUser]
    serializer_class = ExemptionTemplateSerializer
    queryset = ExemptionTemplate.objects.all()


class CaseExportView(APIView):
    """
    Triggers the background task to generate the case export package.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, case_id, *args, **kwargs):
        case = get_object_or_404(Case, id=case_id)

        if case.export_status == Case.ExportStatus.PROCESSING:
            return Response(
                {"detail": "An export is already being generated."},
                status=status.HTTP_409_CONFLICT,
            )

        if not case.documents.exists():
            return Response(
                {"detail": "There are no documents to export."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if case.documents.exclude(status=Document.Status.COMPLETED).exists():
            return Response(
                {
                    "detail": "All documents must be marked as completed before generating a disclosure package."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_id = case.start_export()

        return Response(
            {"message": "Export process started.", "task_id": task_id},
            status=status.HTTP_202_ACCEPTED,
        )


class CaseExportHistoryView(ListAPIView):
    """
    Lists every preserved disclosure export for a case, ordered by sequence.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = ExportSerializer
    pagination_class = None

    def get_queryset(self):
        case = get_object_or_404(Case, id=self.kwargs["case_id"])
        return case.exports.select_related("created_by").all()


class CaseReviewView(APIView):
    """
    Opens an Internal Review on a disclosed case (idempotent: returns the
    already-open review if one exists). Available to any authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, case_id, *args, **kwargs):
        case = get_object_or_404(Case, id=case_id)
        try:
            review = open_review(case, by=request.user)
        except ReviewError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            InternalReviewSerializer(review).data,
            status=status.HTTP_200_OK,
        )


class CasePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


class CaseListCreateView(ListCreateAPIView):
    """
    API view to list and create cases.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CaseSerializer
    pagination_class = CasePagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["case_reference", "data_subject_name"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Case.objects.select_related("created_by")
        status_param = self.request.query_params.get("status")
        if status_param:
            statuses = [s.strip() for s in status_param.split(",")]
            queryset = queryset.filter(status__in=statuses)
        return queryset

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class CaseDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a case.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CaseDetailSerializer

    def get_queryset(self):
        return Case.objects.select_related("created_by").prefetch_related(
            Prefetch(
                "documents",
                queryset=Document.objects.prefetch_related(
                    Prefetch(
                        "redactions",
                        queryset=Redaction.objects.select_related("context"),
                    )
                ),
            )
        )

    lookup_field = "id"
    lookup_url_kwarg = "case_id"

    def perform_update(self, serializer):
        """
        Override to set the updated_by field to the current user.
        """
        serializer.save(updated_by=self.request.user)


class DocumentListCreateView(ListCreateAPIView):
    """
    API view to list and create documents for a specific case.
    Handles multiple file uploads in a single request.
    """

    permission_classes = [
        IsAuthenticated,
    ]
    serializer_class = DocumentSerializer
    lookup_field = "case__id"
    lookup_url_kwarg = "case_id"

    def get_queryset(self):
        return Document.objects.prefetch_related(
            Prefetch(
                "redactions",
                queryset=Redaction.objects.select_related("context"),
            )
        )

    def create(self, request, *args, **kwargs):
        """
        frontend should send files under the 'original_file'
        key in a multipart/form-data request.
        """
        case_id = self.kwargs.get("case_id")
        case = get_object_or_404(Case, pk=case_id)

        files = request.FILES.getlist("original_file")
        if not files:
            return Response(
                {"detail": "No files were provided in the request."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        documents_data = [{"case": case.pk, "original_file": f} for f in files]
        serializer = self.get_serializer(data=documents_data, many=True)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DocumentDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a document.
    """

    permission_classes = [IsAuthenticated]
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    lookup_field = "id"
    lookup_url_kwarg = "document_id"


class DocumentResubmitView(APIView):
    """
    API view to resubmit a document for processing.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, document_id, *args, **kwargs):
        document = get_object_or_404(Document, id=document_id)
        if document.status in [
            Document.Status.ERROR,
            Document.Status.READY_FOR_REVIEW,
            Document.Status.UNPROCESSED,
        ]:
            # Delete existing redactions to avoid duplicates
            document.redactions.all().delete()
            document.start_processing()
            return Response(status=status.HTTP_200_OK)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class DocumentCancelProcessingView(APIView):
    """
    API view to cancel a document that is currently processing.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, document_id, *args, **kwargs):
        document = get_object_or_404(Document, id=document_id)
        if document.status != Document.Status.PROCESSING:
            return Response(
                {"detail": "Document is not currently processing."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Remove from the queue. OrmQ.key is the cluster name, not the task
        # id, so the queued task has to be found via its decoded payload.
        if document.processing_task_id:
            for queued in OrmQ.objects.all():
                if queued.task_id() == document.processing_task_id:
                    queued.delete()
                    break
        document.redactions.all().delete()
        document.extracted_text = None
        document.extracted_tables = []
        document.extracted_structure = None
        document.status = Document.Status.UNPROCESSED
        document.processing_task_id = None
        document.save(
            update_fields=[
                "status",
                "processing_task_id",
                "extracted_text",
                "extracted_tables",
                "extracted_structure",
            ]
        )
        return Response(status=status.HTTP_200_OK)


class DocumentReviewView(RetrieveAPIView):
    """
    API view to review a document.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = DocumentReviewSerializer
    lookup_field = "id"
    lookup_url_kwarg = "document_id"

    def get_queryset(self):
        return Document.objects.prefetch_related(
            Prefetch(
                "redactions",
                queryset=Redaction.objects.select_related("context"),
            )
        )


class RedactionListCreateView(ListCreateAPIView):
    """
    API view to list and create redactions for a specific document.

    `GET ?include=merge_structure` wraps the list in an envelope that also
    carries the document's review merge pairs, so the client can revalidate
    its merge display after span geometry changes without refetching the
    full review payload.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RedactionSerializer
    lookup_field = "document"
    lookup_url_kwarg = "document_id"

    def get_queryset(self):
        return Redaction.objects.filter(
            document_id=self.kwargs["document_id"]
        ).select_related("context")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        if request.query_params.get("include") == "merge_structure":
            response.data = {
                "redactions": response.data,
                "merge_structure": serialize_merge_structure(
                    self.get_queryset()
                ),
            }
        return response


class RedactionDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a redaction.
    """

    permission_classes = [IsAuthenticated]
    queryset = Redaction.objects.all()
    serializer_class = RedactionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "pk"


class BulkRedactionUpdateView(APIView):
    """
    API view to bulk update multiple redactions for a document at once.
    """

    permission_classes = [IsAuthenticated]

    def patch(self, request, document_id):
        serializer = BulkRedactionUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]
        is_accepted = serializer.validated_data["is_accepted"]
        justification = serializer.validated_data["justification"]

        target_qs = Redaction.objects.filter(
            document_id=document_id,
            id__in=ids,
        )
        if is_accepted:
            target_qs.accept(by=Redaction.DecidedBy.HUMAN)
        elif justification:
            target_qs.reject(justification, by=Redaction.DecidedBy.HUMAN)
        else:
            # No justification means the decision is being withdrawn, not a
            # blank rejection — mirrors the frontend's pending classification.
            target_qs.reset()

        updated = Redaction.objects.filter(
            id__in=ids, document_id=document_id
        ).select_related("context")
        serializer = RedactionSerializer(updated, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RedactionContextView(APIView):
    """
    API view to get, create, or update the context for a specific redaction.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RedactionContextSerializer

    def post(self, request, redaction_id, *args, **kwargs):
        redaction = get_object_or_404(Redaction, pk=redaction_id)
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Use update_or_create to handle both creation of a new context
        # and update of an existing one.
        context, created = RedactionContext.objects.update_or_create(
            redaction=redaction,
            defaults={"text": serializer.validated_data["text"]},
        )

        status_code = (
            status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
        return Response(
            self.serializer_class(context).data, status=status_code
        )

    def delete(self, request, redaction_id, *args, **kwargs):
        context = get_object_or_404(RedactionContext, pk=redaction_id)
        context.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class BulkByTextRedactionView(APIView):
    """
    Mark all PENDING redactions matching a given text and redaction_type
    across every document in a case as ACCEPTED or REJECTED in a single
    atomic operation. Returns the count of updated redactions.

    A redaction is PENDING when no decision has been recorded for it
    (decided_by is null).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, case_id):
        serializer = BulkByTextSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        pending_qs = Redaction.objects.filter(
            document__case_id=case_id,
            text=data["text"],
            redaction_type=data["redaction_type"],
        ).pending()

        with transaction.atomic():
            if data["status"] == BulkByTextSerializer.STATUS_ACCEPTED:
                count = pending_qs.accept(by=Redaction.DecidedBy.HUMAN)
            else:
                count = pending_qs.reject(
                    data.get("rejection_reason", ""),
                    by=Redaction.DecidedBy.HUMAN,
                )

        return Response({"updated": count}, status=status.HTTP_200_OK)


class RetentionSettingsView(APIView):
    """
    GET /api/cases/settings/retention
    Returns retention configuration and two lists of cases:
    - past: retention_review_date < today
    - upcoming: retention_review_date within RETENTION_WARNING_DAYS days
    """

    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        warning_days = getattr(settings, "RETENTION_WARNING_DAYS", 30)
        cutoff = today + timedelta(days=warning_days)

        past_qs = Case.objects.filter(retention_review_date__lt=today)
        upcoming_qs = Case.objects.filter(
            retention_review_date__gte=today,
            retention_review_date__lte=cutoff,
        )

        return Response(
            {
                "auto_case_deletion_enabled": getattr(
                    settings, "AUTO_CASE_DELETION_ENABLED", True
                ),
                "retention_warning_days": warning_days,
                "past": CaseSerializer(past_qs, many=True).data,
                "upcoming": CaseSerializer(upcoming_qs, many=True).data,
            }
        )


class BulkCaseDeleteView(APIView):
    """
    POST /api/cases/retention/bulk-delete
    Deletes a list of cases by ID. Admin only.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = BulkCaseDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ids = serializer.validated_data["ids"]

        cases = Case.objects.filter(id__in=ids)
        count = cases.count()
        for case in cases.iterator():
            case.delete()

        return Response({"deleted": count}, status=status.HTTP_200_OK)
