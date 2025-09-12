from rest_framework import serializers
from .models import Model


class ModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Model
        fields = ['id', 'name', 'path', 'is_active', 'created_at',
                  'precision', 'recall', 'f1_score']
        read_only_fields = ['path', 'created_at',
                            'precision', 'recall', 'f1_score']
