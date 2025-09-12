from rest_framework import status
from rest_framework.generics import (
    ListCreateAPIView,
    RetrieveUpdateDestroyAPIView
)
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser
from .loader import SpacyModelManager
from .models import Model
from .serializers import ModelSerializer


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
