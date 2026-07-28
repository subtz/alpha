# ==================================================
# URL IMPORTS
# ==================================================
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

# ==================================================
# URL PATTERNS
# ==================================================
urlpatterns = [

    # ==================================================
    # HOME / AUTH
    # ==================================================
    path('', views.home, name='home'),

    path('login/', views.login_view, name='login'),

    path('logout/', auth_views.LogoutView.as_view(next_page='/'), name='logout'),

    path('register/', views.register, name='register'),

    path('verify-email/<uidb64>/<token>/', views.verify_email, name='verify_email'),

    path('resend-confirmation/', views.resend_confirmation, name='resend_confirmation'),

    # ==================================================
    # PASSWORD RESET
    # ==================================================
    path(
        'password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='sqms/password_reset_form.html',
            success_url=reverse_lazy('password_reset_done'),
            email_template_name='sqms/password_reset_email.html'
        ),
        name='password_reset'
    ),

    path(
        'password_reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='sqms/password_reset_done.html'
        ),
        name='password_reset_done'
    ),

    path(
        'notifications/',
        views.notifications_page,
        name='notifications'
    ),

    path(
        'queue/my-status/',
        views.student_queue_status,
        name='student_queue_status'
    ),

    path(
        'reset/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='sqms/password_reset_confirm.html',
            success_url=reverse_lazy('password_reset_complete')
        ),
        name='password_reset_confirm'
    ),

    path(
        'reset/done/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='sqms/password_reset_complete.html'
        ),
        name='password_reset_complete'
    ),

    # ==================================================
    # STUDENT
    # ==================================================
    path('dashboard/', views.dashboard, name='dashboard'),

    path('queues/', views.queue_list, name='queue_list'),

    path('queues/join/<int:queue_id>/', views.join_queue, name='join_queue'),

    path(
        'profile/picture/upload/',
        views.profile_picture_upload,
        name='profile_picture_upload'
    ),

    path(
        'profile/picture/update/',
        views.update_profile_picture,
        name='update_profile_picture'
    ),

    # ==================================================
    # LIVE DISPLAY
    # ==================================================
    path('display/', views.queue_display, name='queue_display'),

    path('push/subscribe/', views.save_push_subscription, name='push_subscribe'),

    # ==================================================
    # STAFF DASHBOARD
    # ==================================================
    path('staff/dashboard/', views.staff_dashboard_home, name='staff_dashboard_home'),

    path('staff/analytics/', views.analytics_dashboard, name='analytics_dashboard'),

    path('staff/dashboard/<int:queue_id>/', views.queue_control_dashboard, name='queue_control_dashboard'),

    path('staff/dashboard/status/<int:queue_id>/', views.queue_status_api, name='queue_status_api'),

    # ==================================================
    # STAFF ACTIONS
    # ==================================================
    path('staff/serve/<int:queue_id>/', views.serve_current, name='serve_current'),

    path('staff/skip/<int:queue_id>/', views.skip_current, name='skip_current'),

    path('staff/toggle/<int:queue_id>/', views.toggle_queue_pause, name='toggle_queue_pause'),

    path('staff/auto-mode/toggle/<int:queue_id>/', views.toggle_auto_mode, name='toggle_auto_mode'),

    path('staff/auto-mode/interval/<int:queue_id>/', views.set_auto_interval, name='set_auto_interval'),

    # ==================================================
    # REPORTS
    # ==================================================
    path('staff/reports/', views.staff_reports, name='staff_reports'),

    path('staff/reports/export/', views.export_reports_pdf, name='export_reports_pdf'),

    path('staff/send-test-push/', views.send_test_push, name='send_test_push'),

    path('staff/notification-logs/', views.get_notification_logs, name='get_notification_logs'),
]

#temporary for use just after we introduced the new database
path('setup-admin/', views.create_superuser),