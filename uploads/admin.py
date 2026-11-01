from django.contrib import admin

from people.admin import ReadOnlyModelAdmin
from uploads.models import UploadedFile


@admin.register(UploadedFile)
class UploadedFileAdmin(ReadOnlyModelAdmin):
    list_display = ("title", "kind", "person", "size", "created_at")
