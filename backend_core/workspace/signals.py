import threading
import requests
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Document

# The URL of our FastAPI AI Engine
FASTAPI_PROCESS_URL = "http://localhost:8001/api/v1/process-document"

def process_document_task(document_id, file_path, project_id):
    """
    This runs in the background. It tells FastAPI to do the heavy RAG lifting,
    and updates the Django database when it finishes.
    """
    try:
        # Re-fetch the document to update its status
        doc = Document.objects.get(id=document_id)
        doc.processing_status = 'PROCESSING'
        doc.save()

        # Build the payload exactly as FastAPI expects it
        payload = {
            "document_id": str(document_id),
            "file_path": file_path,
            "project_id": str(project_id)
        }

        # Fire the request to the AI Engine
        response = requests.post(FASTAPI_PROCESS_URL, json=payload)
        
        if response.status_code == 200:
            doc.processing_status = 'COMPLETED'
        else:
            doc.processing_status = 'FAILED'
            doc.error_message = response.text
            
        doc.save()

    except Exception as e:
        # If anything crashes, we log the failure safely
        doc = Document.objects.get(id=document_id)
        doc.processing_status = 'FAILED'
        doc.error_message = str(e)
        doc.save()

@receiver(post_save, sender=Document)
def trigger_ai_pipeline(sender, instance, created, **kwargs):
    """
    Listens for new documents being saved to Postgres.
    If it's a brand new document, it spins up the background task.
    """
    if created:
        # We use threading so the Django API responds instantly to the frontend,
        # while the AI does its heavy work in the background.
        thread = threading.Thread(
            target=process_document_task,
            args=(instance.id, instance.file.path, instance.project.id)
        )
        thread.start()