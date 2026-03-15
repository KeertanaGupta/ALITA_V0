from rest_framework import viewsets, parsers, status
from rest_framework.response import Response
from .models import Project, Document
from .serializers import ProjectSerializer, DocumentSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by('-created_at')
    serializer_class = ProjectSerializer

class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all().order_by('-uploaded_at')
    serializer_class = DocumentSerializer
    
    # We need this to accept file uploads (multipart form data)
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def perform_create(self, serializer):
        # We extract the original filename from the uploaded file automatically
        file_obj = self.request.data.get('file')
        if file_obj:
            serializer.save(filename=file_obj.name)
        else:
            serializer.save()