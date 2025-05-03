from django.urls import path                             # Import path to define URL patterns
from django.contrib.auth import views as auth_views      # Import Django's built-in authentication views
from . import views                                       # Import views from the current app (calc)
urlpatterns = [
    path('', views.home, name='home'),                   # Home page view, accessible at the root URL (e.g. /)
    
    # Login view using Django's built-in LoginView
    # Will look for a template named login.html
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    
    # Logout view using Django's built-in LogoutView
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
# calc/urls.py
from django.urls import path
from . import views  # Import views from the current app

urlpatterns = [
    path('register/', views.register, name='register'),  # Register route
]
# calc/urls.py
from django.urls import path
from . import views  # Import views from the current app

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),  # Dashboard route, only accessible by logged-in users
]
