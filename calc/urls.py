# calc/urls.py

# Import path to define URL routes
from django.urls import path

# Import Django's built-in authentication views for login/logout
from django.contrib.auth import views as auth_views

# Import views from the current app (calc)
from . import views

# Define all URL patterns in ONE list to avoid overwriting
urlpatterns = [
    # Home page route — shown at http://127.0.0.1:8000/
    path('', views.home, name='home'),

    # Login route — renders login.html template
    path('login/', auth_views.LoginView.as_view(template_name='calc/login.html'), name='login'),

    # Logout route — logs the user out and redirects
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # Registration page — user sign-up form
    path('register/', views.register, name='register'),

    # Dashboard route — only accessible after login
    path('dashboard/', views.dashboard, name='dashboard'),
    
     # base.html route — renders base.html template
    path('base/', views.base, name='base'),
]
