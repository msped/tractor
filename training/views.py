from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import viewsets
from rest_framework.permissions import IsAdminUser
from django_q.models import Schedule
from django_q.tasks import async_task
from rest_framework import serializers
from .loader import SpacyModelManager
from .models import Model, TrainingDocument, TrainingRun
from .serializers import (
    ModelSerializer,
    ScheduleSerializer,
    TrainingDocumentSerializer,
    TrainingRunSerializer
)


class ModelListCreateView(ListCreateAPIView):
    """
    API view to list all trained models or create a new model entry.
    """
    permission_classes = [IsAdminUser]
    queryset = Model.objects.all().order_by('-created_at')
    serializer_class = ModelSerializer


class ModelDetailView(RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a specific model.
    """
    permission_classes = [IsAdminUser]
    queryset = Model.objects.all()
    serializer_class = ModelSerializer
    lookup_field = 'pk'


class ModelSetActiveView(APIView):
    """API view to set a model as active."""
    permission_classes = [IsAdminUser]

    def post(self, request, pk, *args, **kwargs):
        try:
            model = Model.objects.get(id=pk)
            SpacyModelManager.get_instance().switch_model(model.name)
            return Response(status=status.HTTP_200_OK)
        except Model.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)


class TrainingDocumentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing training documents.
    Supports uploading, listing, and deleting documents.
    """
    permission_classes = [IsAdminUser]
    queryset = TrainingDocument.objects.all().order_by('-created_at')
    serializer_class = TrainingDocumentSerializer

    def perform_create(self, serializer):
        uploaded_file = self.request.FILES.get('original_file')
        if not uploaded_file.name.endswith('.docx'):
            raise serializers.ValidationError(
                "Only .docx files are supported.")
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
                status=status.HTTP_400_BAD_REQUEST
            )

        async_task("training.tasks.train_model",
                   source="training_docs", user=request.user)

        return Response(
            {"status": "training started", "documents": docs.count()},
            status=status.HTTP_202_ACCEPTED
        )


class TrainingRunViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing training runs.
    """
    permission_classes = [IsAdminUser]
    queryset = TrainingRun.objects.all().select_related(
        'model').order_by('-created_at')
    serializer_class = TrainingRunSerializer
