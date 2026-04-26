import io
import multiprocessing
import re
import zipfile

import filetype
from rest_framework import serializers, status, viewsets
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .loader import SpanCatModelManager
from .models import (
    CustomRecognizer,
    LLMPromptSettings,
    Model,
    TrainingDocument,
    TrainingRun,
)
from .serializers import (
    CustomRecognizerSerializer,
    LLMPromptSettingsSerializer,
    ModelSerializer,
    ScheduleSerializer,
    TrainingDocumentSerializer,
    TrainingRunSerializer,
)

_MAX_SAMPLE_TEXT_LENGTH = 10_000


def _regex_worker(pattern_str, sample_text, queue):
    compiled = re.compile(pattern_str)
    matches = [
        {"start": m.start(), "end": m.end(), "text": m.group()}
        for m in compiled.finditer(sample_text)
    ]
    queue.put(matches)


class CustomRecognizerListCreateView(ListCreateAPIView):
    """List all custom recognizers or create a new one."""

    permission_classes = [IsAuthenticated]
    queryset = CustomRecognizer.objects.prefetch_related(
        "patterns", "deny_list"
    )
    serializer_class = CustomRecognizerSerializer


class CustomRecognizerDetailView(RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a custom recognizer."""

    permission_classes = [IsAuthenticated]
    queryset = CustomRecognizer.objects.prefetch_related(
        "patterns", "deny_list"
    )
    serializer_class = CustomRecognizerSerializer


class ValidateRegexView(APIView):
    """Validate a regex pattern against sample text without saving anything."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        pattern = request.data.get("pattern", "")
        sample_text = request.data.get("sample_text", "")
        if not pattern:
            return Response(
                {"error": "pattern is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(sample_text) > _MAX_SAMPLE_TEXT_LENGTH:
            return Response(
                {
                    "valid": False,
                    "error": f"sample_text exceeds {_MAX_SAMPLE_TEXT_LENGTH} character limit",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            re.compile(pattern)
        except re.error as exc:
            return Response(
                {"valid": False, "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        queue = multiprocessing.Queue()
        p = multiprocessing.Process(
            target=_regex_worker, args=(pattern, sample_text, queue)
        )
        p.start()
        p.join(timeout=5)
        if p.is_alive():
            p.kill()
            p.join()
            return Response(
                {
                    "valid": False,
                    "error": "Regex timed out — pattern is too complex",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        matches = queue.get() if not queue.empty() else []
        return Response({"valid": True, "matches": matches})


class LLMPromptSettingsView(APIView):
    """GET/PATCH the singleton LLM system prompt (admin only)."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response(
            LLMPromptSettingsSerializer(LLMPromptSettings.get()).data
        )

    def patch(self, request):
        serializer = LLMPromptSettingsSerializer(
            LLMPromptSettings.get(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ModelListCreateView(ListCreateAPIView):
    """
    API view to list SpanCat models or create a new model entry.
    GLiNER is always active and system-managed — excluded from this list.
    SpanCat models always have an associated TrainingRun; GLiNER never does.
    """

    permission_classes = [IsAdminUser]
    queryset = Model.objects.all().order_by("-created_at")
    serializer_class = ModelSerializer


class ModelDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a specific model.
    """

    permission_classes = [IsAdminUser]
    queryset = Model.objects.all()
    serializer_class = ModelSerializer
    lookup_field = "pk"

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.document_set.exists():
            return Response(
                {
                    "detail": "Cannot delete a model that has been used to process documents."
                },
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)


class ModelSetActiveView(APIView):
    """API view to set a model as active."""

    permission_classes = [IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        try:
            model = Model.objects.get(id=pk)
            SpanCatModelManager.get_instance().switch_model(model.name)
            return Response(status=status.HTTP_200_OK)
        except Model.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TrainingDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing training documents.
    Supports uploading, listing, and deleting documents.
    """

    permission_classes = [IsAdminUser]
    queryset = TrainingDocument.objects.filter(processed=False).order_by(
        "-created_at"
    )
    serializer_class = TrainingDocumentSerializer

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get("original_file")
        if not uploaded_file.name.lower().endswith(".docx"):
            raise serializers.ValidationError(
                "Only .docx files are supported."
            )
        header = uploaded_file.read(261)
        uploaded_file.seek(0)
        kind = filetype.guess(header)
        if kind is None or kind.mime != "application/zip":
            raise serializers.ValidationError(
                "File content does not match a valid .docx file."
            )
        content = uploaded_file.read()
        uploaded_file.seek(0)
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise serializers.ValidationError(
                "Only .docx files are supported."
            )
        serializer.save(created_by=self.request.user)


class TrainingScheduleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    serializer_class = ScheduleSerializer

    def get_queryset(self):
        from django_q.models import Schedule

        return Schedule.objects.filter(func="training.tasks.train_model")


class RunManualTrainingView(APIView):
    """
    Trigger training on unprocessed TrainingDocument objects.
    """

    permission_classes = [IsAdminUser]

    def post(self, request):
        docs = TrainingDocument.objects.filter(processed=False)
        if not docs.exists():
            return Response(
                {"detail": "No unprocessed training documents found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from django_q.tasks import async_task

        async_task(
            "training.tasks.train_model",
            source="training_docs",
            user=request.user,
        )

        return Response(
            {"status": "training started", "documents": docs.count()},
            status=status.HTTP_202_ACCEPTED,
        )


class TrainingRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing training runs.
    """

    permission_classes = [IsAdminUser]
    queryset = (
        TrainingRun.objects.all()
        .select_related("model")
        .order_by("-created_at")
    )
    serializer_class = TrainingRunSerializer


class TrainingStatusView(APIView):
    """Returns whether a training task is currently running."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        from django_q.models import OrmQ

        running = any(
            q.func() == "training.tasks.train_model"
            for q in OrmQ.objects.all()
        )
        return Response({"is_running": running})
