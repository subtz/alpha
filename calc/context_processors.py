from .models import StudentProfile


from django.conf import settings

def student_profile(request):
    context = {
        "global_student_profile": None,
        "VAPID_PUBLIC_KEY": getattr(settings, 'VAPID_PUBLIC_KEY', '')
    }
    if request.user.is_authenticated:
        profile = StudentProfile.objects.filter(
            user=request.user
        ).first()
        context["global_student_profile"] = profile

    return context
