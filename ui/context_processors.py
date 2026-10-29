from django.conf import settings


def shell(request):
    return {"settings_practice_hr_url": settings.PRACTICE_HR_URL}
