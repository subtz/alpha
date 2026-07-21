from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from sqms import views

urlpatterns = [
    path('admin/', admin.site.urls),

    path('', include('sqms.urls')),

    # Root service worker
    path(
        "service-worker.js",
        views.service_worker,
        name="service_worker"
    ),

    # Offline fallback page
    path(
        "offline/",
        views.offline,
        name="offline"
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )