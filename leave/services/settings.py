from leave.models import LeaveSetting


def get():
    row = LeaveSetting.objects.first()
    return row or LeaveSetting.objects.create()
