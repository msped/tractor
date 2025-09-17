from django.urls import path
from .views import (
    ModelListCreateView,
    ModelDetailView,
    ModelSetActiveView,
    RunManualTrainingView,
    TrainingDocumentViewSet,
    TrainingScheduleViewSet,
    TrainingRunViewSet,
)

urlpatterns = [
    path('models', ModelListCreateView.as_view(), name='model-list-create'),
    path('models/<uuid:pk>', ModelDetailView.as_view(), name='model-detail'),
    path('models/<uuid:pk>/set-active',
         ModelSetActiveView.as_view(), name='model-set-active'),
    path("training/run-now", RunManualTrainingView.as_view(),
         name="training-run-now"),
    path('training-docs', TrainingDocumentViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='training-document-list'),
    path('training-docs/<uuid:pk>', TrainingDocumentViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='training-document-detail'),
    path('schedules', TrainingScheduleViewSet.as_view({
        'get': 'list',
        'post': 'create'
    }), name='schedule-list'),
    path('schedules/<int:pk>', TrainingScheduleViewSet.as_view({
        'get': 'retrieve',
        'put': 'update',
        'delete': 'destroy'
    }), name='schedule-detail'),
    path('training-runs', TrainingRunViewSet.as_view({
        'get': 'list'
    }), name='training-run-list'),
]
