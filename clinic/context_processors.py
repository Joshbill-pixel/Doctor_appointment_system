from django.conf import settings

from .models import Notification


def portal(request):
    user = getattr(request, "user", None)
    authenticated = bool(user and user.is_authenticated)
    return {
        "cutoff_hours": settings.CHANGE_CUTOFF_HOURS,
        "unread_count": Notification.objects.filter(user=user, is_read=False).count() if authenticated else 0,
        "is_doctor": authenticated and getattr(user, "doctor_profile", None) is not None,
        "clinic": {
            "name": settings.CLINIC_NAME,
            "full_name": settings.CLINIC_FULL_NAME,
            "address": settings.CLINIC_ADDRESS,
            "phone": settings.CLINIC_PHONE,
            "email": settings.CLINIC_EMAIL,
        },
    }
