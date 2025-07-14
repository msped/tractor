import os
from rest_framework import serializers
from .models import Case, Document, Redaction


class CaseSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source='get_status_display')
    created_by = serializers.CharField(
        source='created_by.username', read_only=True)
    updated_by = serializers.CharField(
        source='updated_by.username', read_only=True)

    class Meta:
        model = Case
        fields = [
            'id',
            'status',
            'case_reference',
            'data_subject_name',
            'data_subject_dob',
            'created_at',
            'updated_at',
            'updated_by',
            'created_by',
            'retention_review_date'
        ]


class DocumentSerializer(serializers.ModelSerializer):
    case = serializers.PrimaryKeyRelatedField(
        queryset=Case.objects.all(), write_only=True)
    status = serializers.CharField(source='get_status_display', read_only=True)
    # Add a write-only field for updating the status
    new_status = serializers.ChoiceField(
        choices=Document.Status,
        write_only=True,
        required=False,
        source='status'
    )
    redactions = serializers.SerializerMethodField(
        read_only=True,
        source='redaction_set'
    )

    def get_redactions(self, obj):
        """
        Returns a list of redactions for the document.
        """
        return RedactionSerializer(obj.redactions.all(), many=True).data

    class Meta:
        model = Document
        fields = [
            'id',
            'case',
            'original_file',
            'filename',
            'file_type',
            'status',
            'new_status',
            'extracted_text',
            'uploaded_at',
            'redactions',
        ]
        read_only_fields = ['id', 'extracted_text',
                            'uploaded_at', 'filename', 'file_type']

    def create(self, validated_data):
        """
        Override to handle file uploads and set the filename and file_type.
        """
        original_file = validated_data.pop('original_file')
        instance = Document.objects.create(
            original_file=original_file, **validated_data)

        # Set filename and file_type based on the uploaded file
        fileName, fileExtension = os.path.splitext(original_file.name)
        instance.filename = fileName
        instance.file_type = fileExtension
        instance.save()

        return instance


class CaseDetailSerializer(CaseSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta(CaseSerializer.Meta):
        fields = CaseSerializer.Meta.fields + ['documents']


class RedactionSerializer(serializers.ModelSerializer):
    document = serializers.PrimaryKeyRelatedField(
        queryset=Document.objects.all(), write_only=True)

    class Meta:
        model = Redaction
        fields = [
            'id',
            'document',
            'start_char',
            'end_char',
            'text',
            'redaction_type',
            'justification',
            'is_suggestion',
            'is_accepted',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class DocumentReviewSerializer(serializers.ModelSerializer):
    redactions = RedactionSerializer(many=True, read_only=True)

    class Meta:
        model = Document
        fields = [
            'id',
            'case',
            'filename',
            'file_type',
            'extracted_text',
            'redactions'
        ]
        read_only_fields = ['id', 'case',
                            'extracted_text', 'filename', 'file_type']
