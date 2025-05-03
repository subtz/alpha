from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),  # Admin URL
    path('accounts/', include('django.contrib.auth.urls')),  # Include Django's built-in auth URLs (login, logout, password reset)
    path('', include('calc.urls')),  # Include your app's URLs
]
