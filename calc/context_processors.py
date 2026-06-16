from .models import StudentProfile


def student_profile(request):
    if request.user.is_authenticated:
        profile = StudentProfile.objects.filter(
            user=request.user
        ).first()

        return {
            "global_student_profile": profile
        }

    return {
        "global_student_profile": None
    }