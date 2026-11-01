"""Uploaded documents (spec 5, section 6). Files are stored under a random
name outside anything served; the only way out is open_file, which checks
the permission and always sends a download."""

import logging
import os
import secrets
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, Http404

from people.services import access, audit
from uploads.models import UploadedFile

log = logging.getLogger("uploads")

# extension -> (content type, the signature its first bytes must carry)
ZIP, OLE = b"PK\x03\x04", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
TYPES = {
    "pdf": ("application/pdf", (b"%PDF",)),
    "doc": ("application/msword", (OLE,)),
    "xls": ("application/vnd.ms-excel", (OLE,)),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (ZIP,)),
    "xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (ZIP,)),
    "odt": ("application/vnd.oasis.opendocument.text", (ZIP,)),
    "ods": ("application/vnd.oasis.opendocument.spreadsheet", (ZIP,)),
    "png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    "jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    "txt": ("text/plain; charset=utf-8", None),
    "csv": ("text/csv; charset=utf-8", None),
}


class UploadError(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def root():
    return Path(settings.MEDIA_ROOT) / "uploads"


def _clean_name(name):
    base = os.path.basename((name or "").replace("\\", "/"))
    base = "".join(ch for ch in base if ch.isprintable() and ch not in '<>:"|?*')
    return base.strip()[:200] or "file"


def _looks_like_text(data):
    if b"\x00" in data:
        return False
    for encoding in ("utf-8", "cp1252"):
        try:
            data.decode(encoding)
            return True
        except UnicodeDecodeError:
            continue
    return False


# --- who ----------------------------------------------------------------------

def can_manage_person_files(user, person):
    return access.can_manage(user, person)


def _may_add(user, kind, person):
    if not access.is_manager(user):
        raise Http404
    if kind == UploadedFile.Kind.PERSON and (person is None or not can_manage_person_files(user, person)):
        raise Http404


def _may_see(user, uploaded):
    if uploaded.kind == UploadedFile.Kind.SHARED:
        return user.is_authenticated
    return can_manage_person_files(user, uploaded.person)


def _may_delete(user, uploaded):
    if uploaded.kind == UploadedFile.Kind.SHARED:
        return access.is_all_teams(user) or (access.is_manager(user) and uploaded.uploaded_by_id == user.pk)
    return can_manage_person_files(user, uploaded.person)


# --- the verbs ----------------------------------------------------------------

def add(user, upload, title, kind, person=None):
    _may_add(user, kind, person)
    original = _clean_name(upload.name)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in TYPES:
        raise UploadError("That kind of file can't be uploaded. Use PDF, Word, Excel, OpenDocument, text, CSV, PNG or JPEG.")
    if upload.size == 0:
        raise UploadError("That file is empty.")
    if upload.size > settings.UPLOAD_MAX_BYTES:
        raise UploadError(f"That file is too big: the limit is {settings.UPLOAD_MAX_BYTES // (1024 * 1024)} MB.")
    content_type, signatures = TYPES[ext]
    head = upload.read(8192)
    upload.seek(0)
    ok = _looks_like_text(upload.read()) if signatures is None else any(head.startswith(s) for s in signatures)
    upload.seek(0)
    if not ok:
        raise UploadError(f"That file doesn't look like a .{ext} file.")
    title = (title or "").strip()[:120] or original
    stored = f"{secrets.token_hex(16)}.{ext}"
    folder = root()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    final, partial = folder / stored, folder / (stored + ".part")
    try:
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as out:
            for chunk in upload.chunks():
                out.write(chunk)
        os.replace(partial, final)
        with transaction.atomic():
            row = UploadedFile.objects.create(kind=kind, person=person, title=title, original_name=original,
                                              stored_name=stored, size=upload.size, uploaded_by=user)
            _audit(user, row, "added", title)
    except BaseException:
        for leftover in (partial, final):
            leftover.unlink(missing_ok=True)
        raise
    return row


def _audit(user, row, field, text):
    if row.kind == UploadedFile.Kind.SHARED:
        audit.record_as(user, "uploads.sharedfile", row.pk, {field: ("", text)}, note="document")
    else:
        audit.record_as(user, "uploads.personfile", row.person_id, {field: ("", text)}, note=f"document · {row.person.name}")


def remove(user, uploaded):
    if not _may_delete(user, uploaded):
        raise Http404
    with transaction.atomic():
        _audit(user, uploaded, "removed", uploaded.title)
        uploaded.delete()
    (root() / uploaded.stored_name).unlink(missing_ok=True)


def open_file(user, uploaded):
    if not _may_see(user, uploaded):
        raise Http404
    path = root() / uploaded.stored_name
    if not path.is_file():
        log.warning("upload %s: file missing on disk", uploaded.pk)
        raise Http404
    if uploaded.kind == UploadedFile.Kind.PERSON:
        _audit(user, uploaded, "downloaded", uploaded.title)
    ext = uploaded.stored_name.rsplit(".", 1)[-1]
    response = FileResponse(open(path, "rb"), as_attachment=True, filename=uploaded.original_name)
    response["Content-Type"] = TYPES[ext][0]
    response["X-Content-Type-Options"] = "nosniff"
    return response


def shared_files():
    return UploadedFile.objects.filter(kind=UploadedFile.Kind.SHARED).select_related("uploaded_by__person")


def person_files(user, person):
    if not can_manage_person_files(user, person):
        raise Http404
    return UploadedFile.objects.filter(kind=UploadedFile.Kind.PERSON, person=person).select_related("uploaded_by__person")
