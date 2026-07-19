from .models import StudentProfile, NotificationLog
from django.conf import settings

def student_profile(request):
    unread_notifications_count = 0
    if request.user.is_authenticated:
        profile = StudentProfile.objects.filter(
            user=request.user
        ).first()
        unread_notifications_count = NotificationLog.objects.filter(
            user=request.user, success=True, is_read=False
        ).count()

        return {
            "global_student_profile": profile,
            "VAPID_PUBLIC_KEY": getattr(settings, 'VAPID_PUBLIC_KEY', ''),
            "unread_notifications_count": unread_notifications_count
        }

    return {
        "global_student_profile": None,
        "VAPID_PUBLIC_KEY": getattr(settings, 'VAPID_PUBLIC_KEY', ''),
        "unread_notifications_count": 0
    }
