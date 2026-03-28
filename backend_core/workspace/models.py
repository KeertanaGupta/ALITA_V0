from django.db import models
import uuid
import os                                           # <-- NEW IMPORT
from django.db.models.signals import post_delete    # <-- NEW IMPORT
from django.dispatch import receiver                # <-- NEW IMPORT

class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

class Document(models.Model):
    # Processing Status Choices
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, related_name='documents', on_delete=models.CASCADE)
    file = models.FileField(upload_to='project_documents/')
    filename = models.CharField(max_length=255)
    
    # AI Processing tracking
    processing_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, null=True)
    
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.filename

# ==========================================
# NEW AUTO-DELETE SIGNAL
# ==========================================
@receiver(post_delete, sender=Document)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    """
    Deletes the physical PDF file from the hard drive 
    whenever a Document is deleted from the UI/Database.
    """
    if instance.file:
        if os.path.isfile(instance.file.path):
            os.remove(instance.file.path)