from .models import StudentProfile


from django.conf import settings

def student_profile(request):
    if request.user.is_authenticated:
        profile = StudentProfile.objects.filter(
            user=request.user
        ).first()

        return {
            "global_student_profile": profile,
            "VAPID_PUBLIC_KEY": getattr(settings, 'VAPID_PUBLIC_KEY', '')
        }

    return {
        "global_student_profile": None,
        "VAPID_PUBLIC_KEY": getattr(settings, 'VAPID_PUBLIC_KEY', '')
    }
