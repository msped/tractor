from django.urls import path
from .views import (
    ModelListCreateView,
    ModelDetailView,
    ModelSetActiveView
)

urlpatterns = [
    path('models', ModelListCreateView.as_view(), name='model-list-create'),
    path('models/<uuid:pk>', ModelDetailView.as_view(), name='model-detail'),
    path('models/<uuid:pk>/set-active',
         ModelSetActiveView.as_view(), name='model-set-active'),
]
