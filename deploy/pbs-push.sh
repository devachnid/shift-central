#!/bin/sh
# Push the nightly database copy to the Proxmox Backup Server, run by
# shift-central-pbs.service as the shift-central user straight after
# shift-central-backup.service. It sends the finished copies in
# $state/backups, never the live WAL database. The repository address and
# certificate fingerprint (not secrets) arrive as PBS_* variables from
# /etc/pbs-backup/shift-central.env. The API token and the encryption key are
# systemd credentials, passed by file: a token in the environment would be
# readable from /proc by any other process running as shift-central, such as
# the web service. The copy is encrypted here: the server holds no plaintext.
set -eu
state="${STATE_DIRECTORY:-/var/lib/shift-central}"
creds="${CREDENTIALS_DIRECTORY:?run this under shift-central-pbs.service}"
export PBS_PASSWORD_FILE="$creds/pbs.token"
exec proxmox-backup-client backup "data.pxar:$state/backups" \
    --ns shift-central --backup-id shift-central \
    --keyfile "$creds/pbs.key"
