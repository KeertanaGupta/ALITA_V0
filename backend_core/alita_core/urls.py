from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # This mounts our workspace APIs under the /api/v1/ prefix
    path('api/v1/workspace/', include('workspace.urls')), 
]

# This is CRITICAL for local development to serve uploaded PDFs
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)