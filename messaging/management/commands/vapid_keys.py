"""Make the push keys, once:

    deploy/manage vapid_keys --out /etc/shift-central/vapid.pem \\
        --group shift-central --subject mailto:you@example.org

Run it as root through deploy/manage (a bare manage.py fails without the
settings in /etc/shift-central.env): the key file belongs in /etc, readable by the app's group
(mode 640). It refuses to overwrite a key: replacing one cuts off every
registered phone until each person turns notifications on again."""

import base64
import os
import shutil

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Write a new VAPID private key file and print the settings for /etc/shift-central.env"

    def add_arguments(self, parser):
        parser.add_argument("--out", required=True, help="where to write the private key (PEM)")
        parser.add_argument("--group", default="", help="group to own the file, e.g. shift-central")
        parser.add_argument("--subject", default="mailto:webmaster@localhost", help="a mailto: address push services can reach")

    def handle(self, *args, out, group, subject, **options):
        key = ec.generate_private_key(ec.SECP256R1())
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        try:
            fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        except FileExistsError:
            raise CommandError(f"{out} exists; not overwriting a key that phones are registered against.") from None
        with os.fdopen(fd, "wb") as f:
            f.write(pem)
        os.chmod(out, 0o640)
        if group:
            shutil.chown(out, group=group)
        self.stdout.write("Add these to /etc/shift-central.env, then restart shift-central:\n")
        self.stdout.write(f"VAPID_PRIVATE_KEY_FILE={out}")
        self.stdout.write("VAPID_PUBLIC_KEY=" + base64.urlsafe_b64encode(public).rstrip(b"=").decode())
        self.stdout.write(f"VAPID_SUBJECT={subject}")
