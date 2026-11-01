"""Shared documents and a person's documents (spec 5, section 6)."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404

from people.models import AuditEntry
from tests.factories import client_for, make_person, make_team, make_team_manager, make_user_for
from uploads import services
from uploads.models import UploadedFile
from uploads.services import UploadError

pytestmark = pytest.mark.django_db
PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 20


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.UPLOAD_MAX_BYTES = 1024 * 1024


@pytest.fixture
def cast():
    reception, nursing = make_team("Reception"), make_team("Nursing")
    lead = make_person(first_name="Lead", team=reception)
    make_team_manager(lead, reception)
    c = SimpleNamespace(reception=reception, nursing=nursing, lead=lead, sam=make_person(first_name="Sam", team=reception),
                        nina=make_person(first_name="Nina", team=nursing), boss=make_person(first_name="Boss", team=reception),
                        nurse_lead=make_person(first_name="NurseLead", team=nursing))
    make_team_manager(c.nurse_lead, nursing)
    for p in (lead, c.sam, c.nina, c.nurse_lead):
        make_user_for(p)
    make_user_for(c.boss, is_all_teams_manager=True)
    return c


def up(name="Handbook.pdf", data=PDF):
    return SimpleUploadedFile(name, data)


def add_shared(cast, **kw):
    return services.add(cast.lead.user, up(**kw), "Staff handbook", UploadedFile.Kind.SHARED)


def test_a_manager_adds_a_shared_file_stored_under_a_random_name(cast):
    f = add_shared(cast)
    assert f.kind == "shared" and f.original_name == "Handbook.pdf" and f.size == len(PDF) and f.title == "Staff handbook"
    assert len(f.stored_name) == 36 and f.stored_name.endswith(".pdf") and f.stored_name != "Handbook.pdf"
    path = Path(services.root()) / f.stored_name
    assert path.read_bytes() == PDF and oct(path.stat().st_mode & 0o777) == "0o600"
    assert AuditEntry.objects.filter(model="uploads.sharedfile", object_id=f.pk, field="added").exists()


def test_staff_cannot_add(cast):
    with pytest.raises(Http404):
        services.add(cast.sam.user, up(), "T", UploadedFile.Kind.SHARED)


@pytest.mark.parametrize("name, data, text", [
    ("run.exe", b"MZ\x90", "can't be uploaded"),
    ("page.html", b"<script>", "can't be uploaded"),
    ("notes", b"x", "can't be uploaded"),
    ("fake.pdf", b"<html>not a pdf</html>", "doesn't look like"),
    ("fake.png", PDF, "doesn't look like"),
    ("fake.docx", b"%PDF", "doesn't look like"),
    ("empty.pdf", b"", "empty"),
    ("big.pdf", PDF + b"0" * (1024 * 1024), "too big"),
    ("bin.txt", b"hello\x00world", "doesn't look like"),
])
def test_a_bad_file_is_refused_and_nothing_is_stored(cast, name, data, text):
    Path(services.root()).mkdir(parents=True, exist_ok=True)
    with pytest.raises(UploadError, match=text):
        services.add(cast.lead.user, up(name, data), "T", UploadedFile.Kind.SHARED)
    assert UploadedFile.objects.count() == 0
    assert not list(Path(services.root()).glob("*"))


@pytest.mark.parametrize("name, data", [
    ("pic.PNG", PNG), ("doc.docx", b"PK\x03\x04rest"), ("old.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1x"),
    ("sheet.csv", "a,b\n1,£2\n".encode("cp1252")), ("notes.txt", "héllo".encode("utf-8")), ("photo.jpeg", b"\xff\xd8\xff\xe0abc")])
def test_each_allowed_type_is_accepted(cast, name, data):
    assert services.add(cast.lead.user, up(name, data), "T", UploadedFile.Kind.SHARED).original_name == name


def test_a_hostile_file_name_is_cleaned_for_display(cast):
    f = services.add(cast.lead.user, up("../../etc/pass\nwd.pdf"), "T", UploadedFile.Kind.SHARED)
    assert "/" not in f.original_name and "\n" not in f.original_name and f.original_name.endswith(".pdf")


def test_a_failed_save_leaves_no_file_and_no_row(cast, monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(services.os, "replace", boom)
    with pytest.raises(OSError):
        add_shared(cast)
    assert UploadedFile.objects.count() == 0
    assert not list(Path(services.root()).glob("*"))


def test_everyone_downloads_shared_files_as_attachments_only(cast):
    f = add_shared(cast)
    r = client_for(cast.sam).get(f"/uploads/{f.pk}/download/")
    assert r.status_code == 200 and b"".join(r.streaming_content) == PDF
    assert r["Content-Disposition"].startswith("attachment") and "Handbook.pdf" in r["Content-Disposition"]
    assert r["Content-Type"] == "application/pdf" and r["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in r["Cache-Control"]


def test_a_missing_file_on_disk_is_a_404(cast):
    f = add_shared(cast)
    (Path(services.root()) / f.stored_name).unlink()
    assert client_for(cast.sam).get(f"/uploads/{f.pk}/download/").status_code == 404


def test_shared_delete_is_the_uploader_or_an_all_teams_manager(cast):
    other = make_person(first_name="Other", team=cast.reception)
    make_team_manager(other, cast.reception)
    make_user_for(other)
    f = add_shared(cast)
    with pytest.raises(Http404):
        services.remove(other.user, f)
    with pytest.raises(Http404):
        services.remove(cast.sam.user, f)
    services.remove(cast.boss.user, f)
    assert not UploadedFile.objects.exists() and not (Path(services.root()) / f.stored_name).exists()
    g = add_shared(cast)
    services.remove(cast.lead.user, g)
    assert AuditEntry.objects.filter(model="uploads.sharedfile", field="removed").count() == 2


def test_personal_files_are_for_that_persons_managers_only(cast):
    f = services.add(cast.lead.user, up("contract.pdf"), "Contract", UploadedFile.Kind.PERSON, person=cast.sam)
    assert AuditEntry.objects.filter(model="uploads.personfile", object_id=cast.sam.pk, field="added").exists()
    for who, status in ((cast.lead, 200), (cast.boss, 200), (cast.sam, 404), (cast.nurse_lead, 404), (cast.nina, 404)):
        assert client_for(who).get(f"/uploads/{f.pk}/download/").status_code == status, who.first_name
    assert client_for(cast.lead).get(f"/staff/{cast.sam.pk}/uploads/").status_code == 200
    for who in (cast.sam, cast.nurse_lead, cast.nina):
        assert client_for(who).get(f"/staff/{cast.sam.pk}/uploads/").status_code == 404
    assert AuditEntry.objects.filter(model="uploads.personfile", field="downloaded").count() == 2
    with pytest.raises(Http404):
        services.add(cast.nurse_lead.user, up(), "T", UploadedFile.Kind.PERSON, person=cast.sam)


def test_a_manager_cannot_see_their_own_personal_files(cast):
    f = services.add(cast.boss.user, up(), "Mine", UploadedFile.Kind.PERSON, person=cast.lead)
    assert client_for(cast.lead).get(f"/uploads/{f.pk}/download/").status_code == 404


def test_the_pages(cast):
    add_shared(cast)
    sam, lead = client_for(cast.sam), client_for(cast.lead)
    page = sam.get("/uploads/").content.decode()
    assert "Staff handbook" in page and "Handbook.pdf" in page and "Add a document" not in page
    assert "Add a document" in lead.get("/uploads/").content.decode()
    r = lead.post("/uploads/", {"title": "Rota policy", "file": up("policy.pdf")})
    assert r.status_code == 302 and UploadedFile.objects.filter(title="Rota policy").exists()
    bad = lead.post("/uploads/", {"title": "Bad", "file": up("x.exe", b"MZ")})
    assert bad.status_code == 200 and b"be uploaded" in bad.content and not UploadedFile.objects.filter(title="Bad").exists()
    assert sam.post("/uploads/", {"title": "Nope", "file": up()}).status_code == 403


def test_the_person_page_uploads_and_deletes(cast):
    lead = client_for(cast.lead)
    r = lead.post(f"/staff/{cast.sam.pk}/uploads/", {"title": "Contract", "file": up("c.pdf")})
    assert r.status_code == 302
    f = UploadedFile.objects.get()
    assert f.kind == "person" and f.person == cast.sam
    assert "Contract" in lead.get(f"/staff/{cast.sam.pk}/uploads/").content.decode()
    assert lead.post(f"/uploads/{f.pk}/delete/").status_code == 302
    assert UploadedFile.objects.count() == 0


def test_the_profile_window_links_to_a_persons_documents_for_managers(cast):
    body = client_for(cast.lead).get(f"/staff/{cast.sam.pk}/profile/").content.decode()
    assert f'href="/staff/{cast.sam.pk}/uploads/"' in body
    own = client_for(cast.sam).get(f"/staff/{cast.sam.pk}/profile/").content.decode()
    assert f"/staff/{cast.sam.pk}/uploads/" not in own


def test_the_nav_has_uploads_for_everyone(cast):
    assert 'data-nav="uploads"' in client_for(cast.sam).get("/rota/").content.decode()


def test_the_backup_script_also_archives_the_media_folder():
    script = (Path(__file__).resolve().parents[1] / "deploy" / "backup.sh").read_text()
    assert "media" in script and "tar" in script


def test_media_root_defaults_to_a_folder_beside_the_database(monkeypatch):
    """The test run swaps the database name for an in-memory one, so read the
    settings file afresh with the environment unset and check the expression."""
    import runpy

    from django.conf import settings as django_settings

    for var in ("DB_PATH", "MEDIA_ROOT"):
        monkeypatch.delenv(var, raising=False)
    fresh = runpy.run_path(str(Path(django_settings.BASE_DIR) / "config" / "settings.py"))
    assert fresh["MEDIA_ROOT"] == Path(fresh["DATABASES"]["default"]["NAME"]).parent / "media"
    assert fresh["MEDIA_ROOT"] == Path(django_settings.BASE_DIR) / "media"
    monkeypatch.setenv("DB_PATH", "/var/lib/shift-central/db.sqlite3")
    assert runpy.run_path(str(Path(django_settings.BASE_DIR) / "config" / "settings.py"))["MEDIA_ROOT"] == Path("/var/lib/shift-central/media")
