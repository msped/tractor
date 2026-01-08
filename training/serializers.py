from django_q.models import Schedule
from rest_framework import serializers

from .models import Model, TrainingDocument, TrainingRun


class ModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Model
        fields = ["id", "name", "path", "is_active", "created_at", "precision", "recall", "f1_score"]
        read_only_fields = ["path", "created_at", "precision", "recall", "f1_score"]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = ["id", "func", "kwargs", "schedule_type", "next_run", "repeats"]


class TrainingDocumentSerializer(serializers.ModelSerializer):
    created_by_username = serializers.ReadOnlyField(source="created_by.username")

    class Meta:
        model = TrainingDocument
        fields = ["id", "name", "original_file", "created_at", "created_by_username", "processed"]
        read_only_fields = ["id", "created_at", "created_by_username", "processed"]


class TrainingRunSerializer(serializers.ModelSerializer):
    model_name = serializers.ReadOnlyField(source="model.name")
    f1_score = serializers.ReadOnlyField(source="model.f1_score")
    precision = serializers.ReadOnlyField(source="model.precision")
    recall = serializers.ReadOnlyField(source="model.recall")

    class Meta:
        model = TrainingRun
        fields = ["id", "model_name", "source", "created_at", "f1_score", "precision", "recall"]
