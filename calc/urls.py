# ==================================================
# URL IMPORTS
# ==================================================
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

# ==================================================
# URL PATTERNS
# ==================================================
urlpatterns = [

    # ==================================================
    # AUTH / HOME
    # ==================================================
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),
    path('register/', views.register, name='register'),

    # ==================================================
    # STUDENT DASHBOARD
    # ==================================================
    path('dashboard/', views.dashboard, name='dashboard'),

    # ==================================================
    # QUEUE SYSTEM (STUDENTS)
    # ==================================================
    path('queues/', views.queue_list, name='queue_list'),

    path(
        'queues/join/<int:queue_id>/',
        views.join_queue,
        name='join_queue'
    ),

    path('display/', views.queue_display, name='queue_display'),

    # ==================================================
    # STAFF DASHBOARD (ENTRY POINT)
    # ==================================================
    path(
        'staff/dashboard/',
        views.staff_dashboard_home,
        name='staff_dashboard_home'
    ),

    # ==================================================
    # STAFF DASHBOARD (QUEUE CONTROL)
    # ==================================================
    path(
        'staff/dashboard/<int:queue_id>/',
        views.queue_control_dashboard,
        name='queue_control_dashboard'
    ),

    # ==================================================
    # STAFF ACTIONS
    # ==================================================
    path(
        'staff/serve/<int:queue_id>/',
        views.serve_current,
        name='serve_current'
    ),

    path(
        'staff/skip/<int:queue_id>/',
        views.skip_current,
        name='skip_current'
    ),

    path(
        'staff/toggle/<int:queue_id>/',
        views.toggle_queue_pause,
        name='toggle_queue_pause'
    ),

    # ==================================================
    # REPORTING SYSTEM
    # ==================================================
    path(
        'staff/reports/',
        views.staff_reports,
        name='staff_reports'
    ),

    path(
        'staff/reports/export/',
        views.export_reports_pdf,
        name='export_reports_pdf'
    ),
]
