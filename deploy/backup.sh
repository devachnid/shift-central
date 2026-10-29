#!/bin/sh
# Nightly copy of the database, kept 30 days, run by
# shift-central-backup.service as the shift-central user. Each copy is
# complete: staff names, emails, hours, allowances and managers' notes, and
# session keys that work as login cookies. So it is written readable by nobody
# else (umask 077) into the app's own state directory, which is closed too.
# systemd sets STATE_DIRECTORY from the unit's StateDirectory=.
set -eu
umask 077
state="${STATE_DIRECTORY:-/var/lib/shift-central}"
mkdir -p "$state/backups"
sqlite3 "$state/db.sqlite3" ".backup '$state/backups/db-$(date +%F).sqlite3'"
find "$state/backups" -name 'db-*.sqlite3' -mtime +30 -delete
