import re

from django_q.models import Schedule
from rest_framework import serializers

from cases.models import Document

from .models import (
    DEFAULT_SYSTEM_PROMPT,
    CustomDenyListItem,
    CustomPattern,
    CustomRecognizer,
    LLMPromptSettings,
    Model,
    TrainingDocument,
    TrainingRun,
    TrainingRunCaseDoc,
    TrainingRunTrainingDoc,
)

# Admin-supplied recognizer patterns run against every uploaded document with no
# match-time timeout, so a catastrophic-backtracking regex would hang the worker.
# We cap the pattern length and probe compiled patterns against adversarial inputs
# under a wall-clock timeout to reject likely-ReDoS patterns at creation time.
_MAX_REGEX_LENGTH = 1000
_REDOS_PROBE_TIMEOUT = 0.25  # seconds
_REDOS_PROBES = [
    "a" * 4096 + "!",
    "0" * 4096 + "!",
    " " * 4096 + "!",
    "a0 " * 1365 + "!",
]


def _is_catastrophic_regex(value):
    """Return True if ``value`` exhibits catastrophic backtracking on a probe.

    Uses the third-party ``regex`` module's match-time ``timeout``. If that module
    is unavailable the check is skipped (syntactic validation still applies)."""
    try:
        import regex
    except ImportError:  # pragma: no cover - regex is a transitive dependency
        return False

    try:
        compiled = regex.compile(value)
    except regex.error:
        # Syntactic errors are reported by the caller's re.compile check.
        return False

    for probe in _REDOS_PROBES:
        try:
            compiled.search(probe, timeout=_REDOS_PROBE_TIMEOUT)
        except TimeoutError:
            return True
    return False


class CustomPatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomPattern
        fields = ["id", "name", "regex", "score"]
        read_only_fields = ["id"]

    def validate_regex(self, value):
        if len(value) > _MAX_REGEX_LENGTH:
            raise serializers.ValidationError(
                f"Pattern is too long (max {_MAX_REGEX_LENGTH} characters)."
            )
        try:
            re.compile(value)
        except re.error as exc:
            raise serializers.ValidationError(f"Invalid regex: {exc}") from exc
        if _is_catastrophic_regex(value):
            raise serializers.ValidationError(
                "Pattern is too slow (possible catastrophic backtracking). "
                "Simplify nested quantifiers such as (a+)+ or (a|a)*."
            )
        return value


class CustomDenyListItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomDenyListItem
        fields = ["id", "value"]
        read_only_fields = ["id"]


class CustomRecognizerSerializer(serializers.ModelSerializer):
    patterns = CustomPatternSerializer(many=True, required=False, default=list)
    deny_list = CustomDenyListItemSerializer(
        many=True, required=False, default=list
    )

    class Meta:
        model = CustomRecognizer
        fields = [
            "id",
            "name",
            "description",
            "entity_type",
            "is_active",
            "created_at",
            "updated_at",
            "patterns",
            "deny_list",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, data):
        # Only enforce the constraint when at least one of the list fields is
        # being explicitly set (i.e. not a partial update on unrelated fields).
        if "patterns" in data or "deny_list" in data:
            patterns = data.get("patterns", [])
            deny_list = data.get("deny_list", [])
            if not patterns and not deny_list:
                raise serializers.ValidationError(
                    "A recognizer must have at least one pattern or deny-list item."
                )
        return data

    def create(self, validated_data):
        patterns_data = validated_data.pop("patterns", [])
        deny_list_data = validated_data.pop("deny_list", [])
        recognizer = CustomRecognizer.objects.create(**validated_data)
        for p in patterns_data:
            CustomPattern.objects.create(recognizer=recognizer, **p)
        for d in deny_list_data:
            CustomDenyListItem.objects.create(recognizer=recognizer, **d)
        return recognizer

    def update(self, instance, validated_data):
        patterns_data = validated_data.pop("patterns", None)
        deny_list_data = validated_data.pop("deny_list", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if patterns_data is not None:
            instance.patterns.all().delete()
            for p in patterns_data:
                CustomPattern.objects.create(recognizer=instance, **p)
        if deny_list_data is not None:
            instance.deny_list.all().delete()
            for d in deny_list_data:
                CustomDenyListItem.objects.create(recognizer=instance, **d)
        return instance


class LLMPromptSettingsSerializer(serializers.ModelSerializer):
    default_system_prompt = serializers.SerializerMethodField()

    class Meta:
        model = LLMPromptSettings
        fields = ["system_prompt", "default_system_prompt"]
        read_only_fields = ["default_system_prompt"]

    def get_default_system_prompt(self, obj):
        return DEFAULT_SYSTEM_PROMPT


class ModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Model
        fields = [
            "id",
            "name",
            "path",
            "is_active",
            "created_at",
            "precision",
            "recall",
            "f1_score",
        ]
        read_only_fields = [
            "path",
            "created_at",
            "precision",
            "recall",
            "f1_score",
        ]


class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = [
            "id",
            "func",
            "kwargs",
            "schedule_type",
            "next_run",
            "repeats",
        ]


class TrainingDocumentSerializer(serializers.ModelSerializer):
    created_by_username = serializers.ReadOnlyField(
        source="created_by.username"
    )

    class Meta:
        model = TrainingDocument
        fields = [
            "id",
            "name",
            "original_file",
            "created_at",
            "created_by_username",
            "processed",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "created_by_username",
            "processed",
        ]


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
        fields = [
            "id",
            "model_name",
            "source",
            "created_at",
            "f1_score",
            "precision",
            "recall",
            "training_documents",
            "case_documents",
        ]

    def get_training_documents(self, obj):
        training_doc_links = TrainingRunTrainingDoc.objects.filter(
            training_run=obj
        ).select_related("document")
        documents = [link.document for link in training_doc_links]
        return TrainingRunTrainingDocSerializer(documents, many=True).data

    def get_case_documents(self, obj):
        case_doc_links = TrainingRunCaseDoc.objects.filter(
            training_run=obj
        ).select_related("document", "document__case")
        documents = [link.document for link in case_doc_links]
        return TrainingRunCaseDocSerializer(documents, many=True).data
