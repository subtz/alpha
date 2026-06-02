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
    # HOME / AUTH
    # ==================================================
    path(
        '',
        views.home,
        name='home'
    ),

    path(
        'login/',
        views.login_view,
        name='login'
    ),

    path(
        'logout/',
        auth_views.LogoutView.as_view(
            next_page='/'
        ),
        name='logout'
    ),

    path(
        'register/',
        views.register,
        name='register'
    ),

    # ==================================================
    # STUDENT
    # ==================================================
    path(
        'dashboard/',
        views.dashboard,
        name='dashboard'
    ),

    path(
        'queues/',
        views.queue_list,
        name='queue_list'
    ),

    path(
        'queues/join/<int:queue_id>/',
        views.join_queue,
        name='join_queue'
    ),

    # ==================================================
    # LIVE DISPLAY
    # ==================================================
    path(
        'display/',
        views.queue_display,
        name='queue_display'
    ),

    # ==================================================
    # STAFF DASHBOARD
    # ==================================================
    path(
        'staff/dashboard/',
        views.staff_dashboard_home,
        name='staff_dashboard_home'
    ),

    path(
        'staff/dashboard/<int:queue_id>/',
        views.queue_control_dashboard,
        name='queue_control_dashboard'
    ),

    path(
        'staff/dashboard/status/<int:queue_id>/',
        views.queue_status_api,
        name='queue_status_api'
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

    path(
        'staff/auto-mode/toggle/<int:queue_id>/',
        views.toggle_auto_mode,
        name='toggle_auto_mode'
    ),

    path(
        'staff/auto-mode/interval/<int:queue_id>/',
        views.set_auto_interval,
        name='set_auto_interval'
    ),

    # ==================================================
    # REPORTS
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