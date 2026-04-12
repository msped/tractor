from django_q.models import OrmQ, Schedule
from django_q.tasks import async_task
from rest_framework import serializers, status, viewsets
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from .loader import SpanCatModelManager
from .models import LLMPromptSettings, Model, TrainingDocument, TrainingRun
from .serializers import (
    LLMPromptSettingsSerializer,
    ModelSerializer,
    ScheduleSerializer,
    TrainingDocumentSerializer,
    TrainingRunSerializer,
)


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
        if not uploaded_file.name.endswith(".docx"):
            raise serializers.ValidationError(
                "Only .docx files are supported."
            )
        serializer.save(created_by=self.request.user)


class TrainingScheduleViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = Schedule.objects.filter(func="training.tasks.train_model")
    serializer_class = ScheduleSerializer


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
        running = any(
            q.func() == "training.tasks.train_model"
            for q in OrmQ.objects.all()
        )
        return Response({"is_running": running})
