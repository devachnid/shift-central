"""The systemd units, the backup script and the manage wrapper: the app runs
as its own user in a sandbox, never as root.

These read the files in deploy/ rather than a running system, so they pin
what a fresh install or a redeploy copies into /etc/systemd/system. That the
directives work on the practice's VPS was checked by running the units
there; see the README's Deploy section.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
SERVICES = sorted(DEPLOY.glob("*.service"))

SANDBOX = {
    "NoNewPrivileges": "yes",
    "ProtectSystem": "strict",
    "ProtectHome": "yes",
    "PrivateTmp": "yes",
    "PrivateDevices": "yes",
    "ProtectKernelTunables": "yes",
    "ProtectKernelModules": "yes",
    "ProtectKernelLogs": "yes",
    "ProtectControlGroups": "yes",
    "ProtectClock": "yes",
    "ProtectHostname": "yes",
    "ProtectProc": "invisible",
    "ProcSubset": "pid",
    "RestrictNamespaces": "yes",
    "RestrictSUIDSGID": "yes",
    "RestrictRealtime": "yes",
    "LockPersonality": "yes",
    "CapabilityBoundingSet": "",
    "RestrictAddressFamilies": "AF_INET AF_INET6 AF_UNIX",
    "SystemCallArchitectures": "native",
    "SystemCallFilter": "@system-service",
    "SystemCallErrorNumber": "EPERM",
}


def _directives(path):
    """{key: [values]} for the [Service] section, comments skipped."""
    out, section = {}, None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("["):
            section = line
            continue
        if section == "[Service]" and "=" in line:
            key, value = line.split("=", 1)
            out.setdefault(key, []).append(value)
    return out


def test_there_are_nine_services():
    assert [p.name for p in SERVICES] == [
        "gunicorn.service", "shift-central-backup.service",
        "shift-central-clearsessions.service", "shift-central-daily-flags.service",
        "shift-central-gp-sync.service",
        "shift-central-hr-sync.service", "shift-central-leave-reminders.service",
        "shift-central-pbs.service", "shift-central-push.service"]


def test_the_push_service_runs_send_push_every_minute():
    (cmd,) = _directives(DEPLOY / "shift-central-push.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py send_push"
    assert "OnCalendar=minutely" in (DEPLOY / "shift-central-push.timer").read_text()


@pytest.mark.parametrize("unit", SERVICES, ids=lambda p: p.name)
def test_every_service_runs_as_the_shift_central_user(unit):
    d = _directives(unit)
    assert d.get("User") == ["shift-central"], "a missing User= means root"
    assert d.get("Group") == ["shift-central"]


@pytest.mark.parametrize("unit", SERVICES, ids=lambda p: p.name)
def test_every_service_keeps_its_data_in_the_closed_state_directory(unit):
    d = _directives(unit)
    assert d.get("StateDirectory") == ["shift-central"]
    assert d.get("StateDirectoryMode") == ["0700"]
    assert d.get("UMask") == ["0077"], "files the app writes are nobody else's"


@pytest.mark.parametrize("unit", SERVICES, ids=lambda p: p.name)
def test_every_service_carries_the_whole_sandbox(unit):
    d = _directives(unit)
    wrong = {k: d.get(k) for k, v in SANDBOX.items() if d.get(k) != [v]}
    assert not wrong, f"{unit.name}: sandbox directives missing or different: {wrong}"


@pytest.mark.parametrize("unit", SERVICES, ids=lambda p: p.name)
def test_no_service_reaches_into_root_home(unit):
    """/root is where the app used to live. ProtectHome=yes hides it, so a
    path there would fail at start, and pointing back there is the regression
    this change removes."""
    live = [ln for ln in unit.read_text().splitlines()
            if ln.strip() and not ln.lstrip().startswith(("#", ";"))]
    assert not [ln for ln in live if "/root" in ln]


@pytest.mark.parametrize("unit", SERVICES, ids=lambda p: p.name)
def test_the_code_runs_from_srv(unit):
    d = _directives(unit)
    for cmd in d["ExecStart"]:
        assert cmd.startswith("/srv/shift-central/"), cmd
    if unit.name not in ("shift-central-backup.service", "shift-central-pbs.service"):
        assert d.get("WorkingDirectory") == ["/srv/shift-central"]
        assert d.get("EnvironmentFile") == ["/etc/shift-central.env"]


def test_the_sync_service_runs_hr_sync():
    (cmd,) = _directives(DEPLOY / "shift-central-hr-sync.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py hr_sync"


def test_the_sync_timer_runs_every_fifteen_minutes():
    text = (DEPLOY / "shift-central-hr-sync.timer").read_text()
    assert "OnCalendar=*-*-* *:0/15:00" in text and "Persistent=true" in text


def test_the_gp_sync_service_runs_gp_sync_on_a_timer_offset_from_the_hr_one():
    (cmd,) = _directives(DEPLOY / "shift-central-gp-sync.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py gp_sync"
    text = (DEPLOY / "shift-central-gp-sync.timer").read_text()
    assert "OnCalendar=*-*-* *:7/15:00" in text and "Persistent=true" in text


def test_the_leave_reminders_run_each_weekday_morning():
    (cmd,) = _directives(DEPLOY / "shift-central-leave-reminders.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py leave_reminders"
    text = (DEPLOY / "shift-central-leave-reminders.timer").read_text()
    assert "OnCalendar=Mon..Fri *-*-* 08:20:00" in text and "Persistent=true" in text


def test_the_daily_flags_run_every_morning():
    (cmd,) = _directives(DEPLOY / "shift-central-daily-flags.service")["ExecStart"]
    assert cmd == "/srv/shift-central/.venv/bin/python manage.py daily_flags"
    text = (DEPLOY / "shift-central-daily-flags.timer").read_text()
    assert "OnCalendar=*-*-* 08:25:00" in text and "Persistent=true" in text


def test_each_timer_names_a_service_that_exists():
    """A timer starts the service of its own name; a rename of one without
    the other leaves a timer that fires at nothing."""
    for timer in sorted(DEPLOY.glob("*.timer")):
        assert timer.with_suffix(".service").exists(), timer.name


def test_gunicorn_listens_on_loopback_only():
    (cmd,) = _directives(DEPLOY / "gunicorn.service")["ExecStart"]
    assert "--bind 127.0.0.1:8323" in cmd


def test_the_env_file_comment_sets_the_database_path():
    """A fresh install that copies the comment gets a database in the state
    directory, not in the root-owned, read-only code tree."""
    assert "DB_PATH=/var/lib/shift-central/db.sqlite3" in (DEPLOY / "gunicorn.service").read_text()


# --- backup.sh -----------------------------------------------------------------

def test_backups_are_written_private_into_the_state_directory():
    script = (DEPLOY / "backup.sh").read_text()
    assert re.search(r"^umask 077$", script, re.M)
    assert "STATE_DIRECTORY" in script
    assert "/root" not in script


def test_the_backup_script_runs_and_keeps_its_copies_private(tmp_path):
    """Against a real SQLite file, with STATE_DIRECTORY as systemd sets it."""
    import sqlite3
    db = tmp_path / "db.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("create table t (x)")
    env = {**os.environ, "STATE_DIRECTORY": str(tmp_path)}
    try:
        subprocess.run(["sh", str(DEPLOY / "backup.sh")], env=env, check=True,
                       capture_output=True)
    except FileNotFoundError:
        pytest.skip("no sh")
    except subprocess.CalledProcessError as exc:
        if b"sqlite3: not found" in exc.stderr or b"sqlite3: command not found" in exc.stderr:
            pytest.skip("sqlite3 CLI not installed")
        raise
    (copy,) = (tmp_path / "backups").glob("db-*.sqlite3")
    assert copy.stat().st_mode & 0o077 == 0, oct(copy.stat().st_mode)
    assert (tmp_path / "backups").stat().st_mode & 0o077 == 0


def test_the_backup_script_archives_the_media_privately(tmp_path):
    """With uploaded documents present, a private media archive is written."""
    import sqlite3
    with sqlite3.connect(tmp_path / "db.sqlite3") as conn:
        conn.execute("create table t (x)")
    (tmp_path / "media" / "uploads").mkdir(parents=True)
    (tmp_path / "media" / "uploads" / "paper.pdf").write_bytes(b"%PDF")
    (tmp_path / "media" / "uploads" / "half.part").write_bytes(b"partial")
    env = {**os.environ, "STATE_DIRECTORY": str(tmp_path)}
    try:
        subprocess.run(["sh", str(DEPLOY / "backup.sh")], env=env, check=True, capture_output=True)
    except FileNotFoundError:
        pytest.skip("no sh")
    except subprocess.CalledProcessError as exc:
        if b"sqlite3: not found" in exc.stderr or b"sqlite3: command not found" in exc.stderr:
            pytest.skip("sqlite3 CLI not installed")
        raise
    (archive,) = (tmp_path / "backups").glob("media-*.tar.gz")
    assert archive.stat().st_mode & 0o077 == 0, oct(archive.stat().st_mode)
    import tarfile
    with tarfile.open(archive) as tar:
        names = tar.getnames()
    assert "media/uploads/paper.pdf" in names and not any(n.endswith(".part") for n in names)


def test_the_media_archive_tolerates_files_changing_while_it_is_read():
    """tar exits 1 when a file changed as it was read: the nightly copy still
    stands. Exit 2 and above (a real failure) still fails the script."""
    script = (DEPLOY / "backup.sh").read_text()
    assert "--exclude='*.part'" in script
    assert re.search(r"tar --exclude='\*\.part' .*media( .*)? \|\| \[ \$\? -eq 1 \]$", script, re.M), "exit 1 tolerated, 2 and above fails"
    assert "-le 1" not in script and "-ge" not in script


# --- off-site backup to the Proxmox Backup Server --------------------------------

def test_the_pbs_secrets_stay_out_of_the_app_users_reach():
    """The token comes from a root-read env file and the encryption key as a
    credential, so the shift-central user (and the web process) never reads either."""
    d = _directives(DEPLOY / "shift-central-pbs.service")
    assert d.get("EnvironmentFile") == ["/etc/pbs-backup/shift-central.env"]
    assert d.get("LoadCredential") == ["pbs.token:/etc/pbs-backup/shift-central.token",
                                       "pbs.key:/etc/pbs-backup/shift-central.key"]
    assert d.get("ExecStart") == ["/srv/shift-central/deploy/pbs-push.sh"]


def test_the_pbs_push_script_is_executable_and_valid_shell():
    script = DEPLOY / "pbs-push.sh"
    assert os.access(script, os.X_OK)
    try:
        subprocess.run(["sh", "-n", str(script)], check=True, capture_output=True)
    except FileNotFoundError:
        pytest.skip("no sh")


def test_the_pbs_push_script_sends_the_copies_encrypted_to_its_own_namespace():
    text = (DEPLOY / "pbs-push.sh").read_text()
    live = " ".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    assert "$state/backups" in live, "the finished copies, not the live database"
    assert "db.sqlite3" not in live
    assert "--ns shift-central" in live and "--keyfile" in live
    assert "PBS_PASSWORD_FILE" in live, "the token goes by file, not by environment"
    assert "PBS_PASSWORD=" not in text and "PBS_PASSWORD=" not in (DEPLOY / "shift-central-pbs.service").read_text()


def test_the_pbs_dropin_runs_the_push_after_a_successful_backup():
    live = [ln for ln in (DEPLOY / "shift-central-backup-pbs.conf").read_text().splitlines()
            if ln.strip() and not ln.startswith("#")]
    assert live == ["[Unit]", "OnSuccess=shift-central-pbs.service"]


# --- deploy/manage -------------------------------------------------------------

def test_the_manage_wrapper_is_executable():
    assert os.access(DEPLOY / "manage", os.X_OK)
    assert os.access(DEPLOY / "backup.sh", os.X_OK)


def test_the_wrapper_lets_systemd_read_the_settings_and_drops_to_the_app_user():
    script = (DEPLOY / "manage").read_text()
    assert "-p EnvironmentFile=/etc/shift-central.env" in script
    assert "--uid=shift-central --gid=shift-central" in script
    assert "UMask=0077" in script
    # It must not source the file: Django's generated keys hold ( and $.
    assert not re.search(r"^\s*\.\s+/etc/shift-central\.env", script, re.M)


def test_collectstatic_stays_root_and_world_readable():
    """staticfiles/ is in the root-owned code tree and WhiteNoise, as shift-central,
    must read what it writes."""
    script = (DEPLOY / "manage").read_text()
    start = script.index("= collectstatic ]")
    branch = script[start:script.index("\nelse\n", start)]
    assert "UMask=0022" in branch and "--uid" not in branch


def test_vapid_keys_runs_as_root_with_the_settings():
    """The key file goes in /etc, which the app's user cannot write, and Django
    needs the settings (a SECRET_KEY) even though the command never opens the database."""
    script = (DEPLOY / "manage").read_text()
    start = script.index("= collectstatic ]")
    head = script[start - 12:script.index("\nelse\n", start)]
    assert "= vapid_keys ]" in head and "--uid" not in head
    assert "-p EnvironmentFile=/etc/shift-central.env" in script


@pytest.mark.skipif(os.geteuid() == 0, reason="the refusal is for non-root callers")
def test_the_wrapper_refuses_to_run_without_root():
    r = subprocess.run(["sh", str(DEPLOY / "manage"), "check"],
                       capture_output=True, text=True)
    assert r.returncode == 1 and "run as root" in r.stderr


def test_the_manage_wrapper_names_this_app():
    text = (DEPLOY / "manage").read_text()
    assert "/etc/shift-central.env" in text and "--uid=shift-central" in text
    assert "rota" not in text.replace("shift-central", "")


# --- settings ------------------------------------------------------------------

def _database_name(extra_env):
    env = {k: v for k, v in os.environ.items() if k != "DB_PATH"}
    env.update({"DEBUG": "1", "DJANGO_SETTINGS_MODULE": "config.settings", **extra_env})
    return subprocess.run(
        [sys.executable, "-c",
         "import django; django.setup(); from django.conf import settings; "
         "print(settings.DATABASES['default']['NAME'])"],
        env=env, cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout.strip()


def test_db_path_moves_the_database():
    assert _database_name({"DB_PATH": "/var/lib/shift-central/db.sqlite3"}) == "/var/lib/shift-central/db.sqlite3"


def test_without_db_path_the_database_sits_beside_manage_py():
    assert _database_name({}) == str(ROOT / "db.sqlite3")


# --- the docs --------------------------------------------------------------------

def _command_lines(text):
    """Lines a reader would paste: indented code and fenced code."""
    fenced = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if fenced or line.startswith("    "):
            yield line.strip()


def test_no_doc_runs_manage_py_on_the_server_by_hand():
    """On the server every command goes through deploy/manage; a dev box
    says DEBUG=1. Anything else is a root python opening a WAL database."""
    docs = [ROOT / "README.md", *sorted((ROOT / "docs" / "admin").glob("*.md"))]
    bad = [
        f"{doc.name}: {line}"
        for doc in docs for line in _command_lines(doc.read_text())
        if "manage.py" in line and not line.startswith("DEBUG=1")
    ]
    assert not bad, bad


def test_no_doc_sources_the_env_file_into_a_shell():
    docs = [ROOT / "README.md", *sorted((ROOT / "docs" / "admin").glob("*.md"))]
    bad = [
        f"{doc.name}: {line}"
        for doc in docs for line in _command_lines(doc.read_text())
        if re.search(r"(^|[;&]\s*)\.\s+/etc/shift-central\.env", line)
    ]
    assert not bad, bad


# --- deploy/update -------------------------------------------------------------
# Run for real against a throwaway origin and a clone standing in for
# /srv/shift-central. `id`, `systemctl`, pip and deploy/manage are stand-ins
# that write what they were asked to a log; git is real.

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env={**os.environ, **GIT_ENV})


def _stub(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(0o755)


@pytest.fixture
def box(tmp_path):
    """origin (a work tree that pushes), the box (a clone), installed units, stand-ins."""
    origin, box, units, bin_ = (tmp_path / n for n in ("origin", "box", "units", "bin"))
    log = tmp_path / "log"
    (origin / "deploy").mkdir(parents=True)
    (origin / "deploy" / "update").write_text((DEPLOY / "update").read_text())
    (origin / "deploy" / "update").chmod(0o755)
    _stub(origin / "deploy" / "manage", f'echo "manage $*" >> {log}\n[ "$1 $2" != "check --deploy" ] || [ ! -e {tmp_path}/fail-check ]\n')
    (origin / "deploy" / "gunicorn.service").write_text("[Service]\nExecStart=old\n")
    (origin / "deploy" / "shift-central-hr-sync.timer").write_text("[Timer]\nOnCalendar=old\n")
    (origin / "deploy" / "shift-central-pbs.service").write_text("[Service]\n")
    (origin / "deploy" / "shift-central-backup-pbs.conf").write_text("[Service]\nold\n")
    (origin / "requirements.txt").write_text("django\n")
    (origin / ".gitignore").write_text(".venv/\n")
    _git(origin, "init", "-q", "-b", "main")
    _git(origin, "add", ".")
    _git(origin, "commit", "-q", "-m", "first")
    _git(tmp_path, "clone", "-q", str(origin), str(box))
    _stub(box / ".venv" / "bin" / "pip", f'echo "pip $*" >> {log}\n')
    _stub(bin_ / "id", 'echo 0\n')
    _stub(bin_ / "systemctl", f'echo "systemctl $*" >> {log}\n')
    (units / "shift-central-backup.service.d").mkdir(parents=True)
    for src, name in (("gunicorn.service", "shift-central.service"), ("shift-central-hr-sync.timer", "shift-central-hr-sync.timer")):
        (units / name).write_text((origin / "deploy" / src).read_text())
    (units / "shift-central-backup.service.d" / "pbs.conf").write_text((origin / "deploy" / "shift-central-backup-pbs.conf").read_text())

    def run():
        env = {**os.environ, **GIT_ENV, "PATH": f"{bin_}:{os.environ['PATH']}", "SHIFT_CENTRAL_UNITS": str(units)}
        r = subprocess.run(["sh", str(box / "deploy" / "update")], capture_output=True, text=True, env=env)
        lines = log.read_text().splitlines() if log.exists() else []
        log.unlink(missing_ok=True)
        return r, lines

    return {"origin": origin, "box": box, "units": units, "tmp": tmp_path, "run": run}


def test_update_pulls_then_runs_the_redeploy_steps_in_order(box):
    (box["origin"] / "requirements.txt").write_text("django\nopenpyxl\n")
    _git(box["origin"], "commit", "-q", "-am", "second")
    r, log = box["run"]()
    assert r.returncode == 0, r.stderr
    assert (box["box"] / "requirements.txt").read_text() == "django\nopenpyxl\n"
    assert log == ["pip install --quiet --disable-pip-version-check -r requirements.txt", "manage migrate --noinput",
                   "manage collectstatic --noinput", "manage check --deploy", "systemctl restart shift-central"]
    assert "Shift Central updated:" in r.stdout


def test_update_copies_changed_installed_units_and_names_new_ones(box):
    o = box["origin"] / "deploy"
    (o / "gunicorn.service").write_text("[Service]\nExecStart=new\n")
    (o / "shift-central-hr-sync.timer").write_text("[Timer]\nOnCalendar=new\n")
    (o / "shift-central-backup-pbs.conf").write_text("[Service]\nnew\n")
    (o / "shift-central-pbs.service").write_text("[Service]\nchanged\n")           # not installed here: left alone
    (o / "shift-central-new.timer").write_text("[Timer]\n")
    _git(box["origin"], "add", ".")
    _git(box["origin"], "commit", "-q", "-m", "units")
    r, log = box["run"]()
    assert r.returncode == 0, r.stderr
    u = box["units"]
    assert (u / "shift-central.service").read_text().endswith("new\n")              # gunicorn.service, installed under its name
    assert (u / "shift-central-hr-sync.timer").read_text().endswith("new\n")
    assert (u / "shift-central-backup.service.d" / "pbs.conf").read_text().endswith("new\n")
    assert not (u / "shift-central-pbs.service").exists() and not (u / "shift-central-new.timer").exists()
    assert "new unit, not installed: deploy/shift-central-new.timer" in r.stdout
    assert "shift-central-pbs.service" not in "".join(line for line in r.stdout.splitlines() if line.startswith("  "))
    assert log[-3:] == ["systemctl daemon-reload", "systemctl try-restart shift-central-hr-sync.timer", "systemctl restart shift-central"]


def test_a_failed_check_stops_before_the_restart_and_a_rerun_finishes(box):
    (box["origin"] / "deploy" / "gunicorn.service").write_text("[Service]\nExecStart=new\n")
    _git(box["origin"], "commit", "-q", "-am", "second")
    (box["tmp"] / "fail-check").touch()
    r, log = box["run"]()
    assert r.returncode != 0 and log[-1] == "manage check --deploy"
    assert not any(line.startswith("systemctl") for line in log)
    assert (box["units"] / "shift-central.service").read_text().endswith("old\n")
    (box["tmp"] / "fail-check").unlink()
    r, log = box["run"]()                     # nothing new to pull: the unit is still put right
    assert r.returncode == 0, r.stderr
    assert (box["units"] / "shift-central.service").read_text().endswith("new\n")
    assert log[-2:] == ["systemctl daemon-reload", "systemctl restart shift-central"]
    assert "nothing new to pull" in r.stdout


def test_local_edits_stop_the_pull_and_everything_after_it(box):
    (box["origin"] / "requirements.txt").write_text("django\nopenpyxl\n")
    _git(box["origin"], "commit", "-q", "-am", "second")
    (box["box"] / "requirements.txt").write_text("edited on the box\n")
    r, log = box["run"]()
    assert r.returncode != 0 and log == []


def test_update_is_executable_and_runs_as_one_function():
    """sh reads a script as it goes: a pull that rewrites this file mid-run would
    otherwise run the rest of the new file from the old offset."""
    assert os.access(DEPLOY / "update", os.X_OK)
    text = (DEPLOY / "update").read_text()
    assert text.rstrip().endswith('main "$@"; exit')


@pytest.mark.skipif(os.geteuid() == 0, reason="the refusal is for non-root callers")
def test_update_refuses_to_run_without_root():
    r = subprocess.run(["sh", str(DEPLOY / "update")], capture_output=True, text=True)
    assert r.returncode == 1 and "run as root" in r.stderr


def test_an_edit_the_pull_does_not_touch_stops_the_update_too(box):
    """git pull refuses only when the pull changes the edited file. An edit to
    any other tracked file, or with nothing to pull, would otherwise be restarted
    into service: code running on the box that is in no commit."""
    (box["origin"] / "requirements.txt").write_text("django\nopenpyxl\n")
    _git(box["origin"], "commit", "-q", "-am", "second")
    (box["box"] / "deploy" / "gunicorn.service").write_text("[Service]\nExecStart=edited on the box\n")
    r, log = box["run"]()
    assert r.returncode != 0 and log == []
    assert "deploy/gunicorn.service" in r.stderr and "edited on this box" in r.stderr
    assert (box["box"] / "requirements.txt").read_text() == "django\n"            # not even pulled
    _git(box["box"], "checkout", "--", "deploy/gunicorn.service")
    r, log = box["run"]()
    assert r.returncode == 0 and log[-1] == "systemctl restart shift-central"


def test_untracked_files_on_the_box_do_not_stop_the_update(box):
    (box["box"] / "notes.txt").write_text("the database and the uploads are untracked too\n")
    r, log = box["run"]()
    assert r.returncode == 0, r.stderr
