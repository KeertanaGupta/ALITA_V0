from rest_framework import serializers
from .models import Project, Document

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'project', 'file', 'filename', 'processing_status', 'error_message', 'uploaded_at']
        read_only_fields = ['id', 'processing_status', 'error_message', 'uploaded_at','filename']

class ProjectSerializer(serializers.ModelSerializer):
    documents = DocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = ['id', 'name', 'description', 'documents', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']