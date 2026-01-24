from django_q.models import Schedule
from rest_framework import serializers

from cases.models import Document
from .models import Model, TrainingDocument, TrainingRun, TrainingRunCaseDoc, TrainingRunTrainingDoc


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


class TrainingRunTrainingDocSerializer(serializers.ModelSerializer):
    """Serializer for training documents in a training run."""

    class Meta:
        model = TrainingDocument
        fields = ["id", "name", "created_at", "original_file"]


class TrainingRunCaseDocSerializer(serializers.ModelSerializer):
    """Serializer for case documents in a training run."""

    case_id = serializers.ReadOnlyField(source="case.id")

    class Meta:
        model = Document
        fields = ["id", "filename", "case_id"]


class TrainingRunSerializer(serializers.ModelSerializer):
    model_name = serializers.ReadOnlyField(source="model.name")
    f1_score = serializers.ReadOnlyField(source="model.f1_score")
    precision = serializers.ReadOnlyField(source="model.precision")
    recall = serializers.ReadOnlyField(source="model.recall")
    training_documents = serializers.SerializerMethodField()
    case_documents = serializers.SerializerMethodField()

    class Meta:
        model = TrainingRun
        fields = ["id", "model_name", "source", "created_at", "f1_score", "precision", "recall", "training_documents", "case_documents"]

    def get_training_documents(self, obj):
        training_doc_links = TrainingRunTrainingDoc.objects.filter(training_run=obj).select_related("document")
        documents = [link.document for link in training_doc_links]
        return TrainingRunTrainingDocSerializer(documents, many=True).data

    def get_case_documents(self, obj):
        case_doc_links = TrainingRunCaseDoc.objects.filter(training_run=obj).select_related("document", "document__case")
        documents = [link.document for link in case_doc_links]
        return TrainingRunCaseDocSerializer(documents, many=True).data
