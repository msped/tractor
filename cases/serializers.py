import os

import filetype
from rest_framework import serializers

from .models import (
    Case,
    Document,
    DocumentExportSettings,
    ExemptionTemplate,
    Export,
    Redaction,
    RedactionContext,
    ReviewWorkflowSettings,
)
from .span_merging import serialize_merge_structure


class CaseSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    created_by = serializers.CharField(
        source="created_by.username", read_only=True
    )

    class Meta:
        model = Case
        fields = [
            "id",
            "status",
            "status_display",
            "case_reference",
            "data_subject_name",
            "data_subject_dob",
            "created_at",
            "created_by",
            "retention_review_date",
        ]


_ALLOWED_EXTENSIONS = {".docx", ".pdf", ".txt"}
# DOCX is a ZIP container — filetype identifies it as application/zip
_MIME_TO_EXT = {
    "application/pdf": ".pdf",
    "application/zip": ".docx",
}
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 100 MB


class DocumentSerializer(serializers.ModelSerializer):
    case = serializers.PrimaryKeyRelatedField(
        queryset=Case.objects.all(), write_only=True
    )
    status = serializers.CharField(source="get_status_display", read_only=True)
    # Add a write-only field for updating the status
    new_status = serializers.ChoiceField(
        choices=Document.Status,
        write_only=True,
        required=False,
        source="status",
    )
    redactions = serializers.SerializerMethodField(
        read_only=True, source="redaction_set"
    )

    def get_redactions(self, obj):
        """
        Returns a list of redactions for the document.
        """
        return RedactionSerializer(obj.redactions.all(), many=True).data

    def validate_original_file(self, file):
        ext = os.path.splitext(file.name)[1].lower()
        if ext == ".doc":
            raise serializers.ValidationError(
                "Legacy .doc files are not supported. "
                "Please save the document as .docx or PDF and re-upload."
            )
        if ext not in _ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file type '{ext}'. Accepted formats: .docx, .pdf"
            )
        if file.size > _MAX_UPLOAD_BYTES:
            raise serializers.ValidationError(
                "File exceeds the 100 MB size limit."
            )
        if ext == ".txt":
            return file
        header = file.read(261)
        file.seek(0)
        kind = filetype.guess(header)
        if kind is None or _MIME_TO_EXT.get(kind.mime) != ext:
            raise serializers.ValidationError(
                "File content does not match the declared file type."
            )
        return file

    class Meta:
        model = Document
        fields = [
            "id",
            "case",
            "original_file",
            "filename",
            "file_type",
            "status",
            "new_status",
            "extracted_text",
            "extracted_tables",
            "extracted_structure",
            "uploaded_at",
            "redactions",
        ]
        read_only_fields = [
            "id",
            "extracted_text",
            "extracted_tables",
            "extracted_structure",
            "uploaded_at",
            "filename",
            "file_type",
        ]

    def create(self, validated_data):
        original_file = validated_data.pop("original_file")
        instance = Document.objects.create(
            original_file=original_file, **validated_data
        )

        # Set filename and file_type based on the uploaded file
        instance.filename = original_file.name
        instance.file_type = os.path.splitext(original_file.name)[1]
        instance.save()

        return instance


class CaseDetailSerializer(CaseSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta(CaseSerializer.Meta):
        fields = CaseSerializer.Meta.fields + [
            "documents",
            "export_status",
            "export_file",
            "export_task_id",
        ]
        read_only_fields = ["export_status", "export_file", "export_task_id"]


class ExportSerializer(serializers.ModelSerializer):
    created_by = serializers.CharField(
        source="created_by.username", read_only=True, default=None
    )

    class Meta:
        model = Export
        fields = [
            "id",
            "sequence",
            "label",
            "created_at",
            "created_by",
            "review",
            "export_file",
        ]
        read_only_fields = fields


class RedactionContextSerializer(serializers.ModelSerializer):
    """
    Serializer for the RedactionContext model.
    """

    class Meta:
        model = RedactionContext
        fields = ["redaction", "text"]
        read_only_fields = ["redaction"]


class RedactionSerializer(serializers.ModelSerializer):
    document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(), write_only=True
    )
    context = RedactionContextSerializer(read_only=True)
    # Model property, serialized read-only for API compatibility.
    auto_accepted = serializers.BooleanField(read_only=True)

    @staticmethod
    def _decided_by_for(is_accepted, justification):
        """
        Provenance implied by a decision write through this (human-facing)
        serializer: any accept or justified rejection is a human decision;
        an unjustified non-accept means the decision is withdrawn (pending).
        """
        if is_accepted or justification:
            return Redaction.DecidedBy.HUMAN
        return None

    def create(self, validated_data):
        validated_data["decided_by"] = self._decided_by_for(
            validated_data.get("is_accepted", False),
            validated_data.get("justification"),
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if {"is_accepted", "justification"} & validated_data.keys():
            validated_data["decided_by"] = self._decided_by_for(
                validated_data.get("is_accepted", instance.is_accepted),
                validated_data.get("justification", instance.justification),
            )
        return super().update(instance, validated_data)

    class Meta:
        model = Redaction
        fields = [
            "id",
            "document",
            "start_char",
            "end_char",
            "text",
            "redaction_type",
            "justification",
            "is_suggestion",
            "is_accepted",
            "auto_accepted",
            "source",
            "created_at",
            "context",
        ]
        read_only_fields = ["id", "auto_accepted", "created_at"]


class BulkRedactionUpdateSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.UUIDField(), default=list)
    is_accepted = serializers.BooleanField()
    justification = serializers.CharField(
        required=False, allow_blank=True, allow_null=True, default=None
    )


class BulkByTextSerializer(serializers.Serializer):
    STATUS_ACCEPTED = "ACCEPTED"
    STATUS_REJECTED = "REJECTED"

    text = serializers.CharField()
    redaction_type = serializers.ChoiceField(
        choices=Redaction.RedactionType.choices
    )
    status = serializers.ChoiceField(
        choices=[(STATUS_ACCEPTED, "Accepted"), (STATUS_REJECTED, "Rejected")]
    )
    rejection_reason = serializers.CharField(
        required=False, allow_blank=True, default=""
    )


class ReviewWorkflowSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewWorkflowSettings
        fields = ["auto_accept_enabled"]


class ExemptionTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExemptionTemplate
        fields = ["id", "name", "description"]


class DocumentExportSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentExportSettings
        fields = [
            "header_text",
            "footer_text",
            "watermark_text",
            "watermark_include_case_ref",
            "page_numbers_enabled",
            "font_family",
            "disclosure_style",
        ]


class BulkCaseDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        min_length=1,
    )


class DocumentReviewSerializer(serializers.ModelSerializer):
    redactions = RedactionSerializer(many=True, read_only=True)
    merge_structure = serializers.SerializerMethodField()

    def get_merge_structure(self, obj):
        return serialize_merge_structure(obj.redactions.all())

    class Meta:
        model = Document
        fields = [
            "id",
            "case",
            "filename",
            "file_type",
            "extracted_text",
            "extracted_tables",
            "extracted_structure",
            "redactions",
            "merge_structure",
        ]
        read_only_fields = [
            "id",
            "case",
            "extracted_text",
            "extracted_tables",
            "extracted_structure",
            "filename",
            "file_type",
        ]
