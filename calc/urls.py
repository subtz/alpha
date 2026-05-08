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
    path('login/', views.login_view, name='login'),

    # Logout route — logs the user out and redirects
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    # Registration page — user sign-up form
    path('register/', views.register, name='register'),

    # Dashboard route — only accessible after login
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # base.html route — renders base.html template
    path('base/', views.base, name='base'),
    
    # Smart Queue routes
    path('queues/', views.queue_list, name='queue_list'),
    path('queues/join/<int:queue_id>/', views.join_queue, name='join_queue'),
    path('display/', views.queue_display, name='queue_display'),

    # Staff queue control dashboard
    path('staff/dashboard/', views.queue_control_dashboard, name='queue_control_dashboard'),
    path('staff/dashboard/<int:queue_id>/', views.queue_control_dashboard, name='queue_control_dashboard'),
    path('staff/reports/', views.staff_reports, name='staff_reports'),
    path('staff/reports/export/', views.export_reports_pdf, name='export_reports_pdf'),
    path('staff/serve/', views.serve_current, name='serve_current'),
    path('staff/skip/', views.skip_current, name='skip_current'),
    path('staff/toggle/<int:queue_id>/', views.toggle_queue_pause, name='toggle_queue_pause'),
]
