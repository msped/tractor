from django.shortcuts import get_object_or_404
from django_q.models import OrmQ
from django_q.tasks import async_task
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Case, Document, Redaction, RedactionContext
from .serializers import (
    CaseDetailSerializer,
    CaseSerializer,
    DocumentReviewSerializer,
    DocumentSerializer,
    RedactionContextSerializer,
    RedactionSerializer,
)


class CaseExportView(APIView):
    """
    Triggers the background task to generate the case export package.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, case_id, *args, **kwargs):
        case = get_object_or_404(Case, id=case_id)

        if not case.documents.exists():
            return Response({"detail": "There are no documents to export."}, status=status.HTTP_400_BAD_REQUEST)

        if case.documents.exclude(status=Document.Status.COMPLETED).exists():
            return Response(
                {"detail": "All documents must be marked as completed before generating a disclosure package."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_id = case.start_export()

        return Response({"message": "Export process started.", "task_id": task_id}, status=status.HTTP_202_ACCEPTED)


class CaseListCreateView(ListCreateAPIView):
    """
    API view to list and create cases.
    """

    permission_classes = [IsAuthenticated]
    queryset = Case.objects.all()
    serializer_class = CaseSerializer

    def perform_create(self, serializer):
        """
        Override to set the created_by field to the current user.
        """
        serializer.save(created_by=self.request.user)


class CaseDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a case.
    """

    permission_classes = [IsAuthenticated]
    queryset = Case.objects.all()
    serializer_class = CaseDetailSerializer
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
    queryset = Document.objects.all()
    lookup_field = "case__id"
    lookup_url_kwarg = "case_id"

    def create(self, request, *args, **kwargs):
        """
        frontend should send files under the 'original_file'
        key in a multipart/form-data request.
        """
        case_id = self.kwargs.get("case_id")
        case = get_object_or_404(Case, pk=case_id)

        files = request.FILES.getlist("original_file")
        if not files:
            return Response({"detail": "No files were provided in the request."}, status=status.HTTP_400_BAD_REQUEST)

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
        if document.status in [Document.Status.ERROR, Document.Status.READY_FOR_REVIEW, Document.Status.UNPROCESSED]:
            # Delete existing redactions to avoid duplicates
            document.redactions.all().delete()
            document.status = Document.Status.PROCESSING
            document.save(update_fields=["status"])
            async_task(
                "cases.services.process_document_and_create_redactions", document.id)
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

        # Remove from the queue
        if document.processing_task_id:
            OrmQ.objects.filter(key=document.processing_task_id).delete()
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
    queryset = Document.objects.all()
    lookup_field = "id"
    lookup_url_kwarg = "document_id"


class RedactionListCreateView(ListCreateAPIView):
    """
    API view to list and create redactions for a specific document.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = RedactionSerializer
    queryset = Redaction.objects.all()
    lookup_field = "document"
    lookup_url_kwarg = "document_id"


class RedactionDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a redaction.
    """

    permission_classes = [IsAuthenticated]
    queryset = Redaction.objects.all()
    serializer_class = RedactionSerializer
    lookup_field = "id"
    lookup_url_kwarg = "pk"


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
            redaction=redaction, defaults={
                "text": serializer.validated_data["text"]}
        )

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(self.serializer_class(context).data, status=status_code)

    def delete(self, request, redaction_id, *args, **kwargs):
        context = get_object_or_404(RedactionContext, pk=redaction_id)
        context.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
