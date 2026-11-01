"""A read-only client for the GP rota app's sessions feed, on the standard
library, in hr_client's pattern: https only outside DEBUG, no redirects,
the token never logged, the body never logged."""

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlencode, urlparse

from django.conf import settings

log = logging.getLogger("shifts.gp_sync")

# See people/services/hr_client.py: Cloudflare refuses urllib's default agent.
USER_AGENT = "ShiftCentral/1.0"


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_RefuseRedirects)


class GpError(Exception):
    pass


class GpClient:
    def __init__(self, base_url, token, *, opener=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._open = opener or (lambda req: _OPENER.open(req, timeout=timeout))

    def sessions(self, start, end):
        url = f"{self.base_url}/api/v1/sessions?" + urlencode({"from": start.isoformat(), "to": end.isoformat()})
        if urlparse(url).scheme != "https" and not settings.DEBUG:
            raise GpError("ROTA_URL is not https; the token was not sent")
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/json", "Authorization": f"Bearer {self._token}",
            "User-Agent": USER_AGENT})
        try:
            with self._open(req) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            log.warning("gp sessions -> %s", e.code)
            raise GpError(f"GP rota returned {e.code} for sessions") from None
        except (urllib.error.URLError, OSError) as e:
            log.warning("gp sessions unreachable: %s", e.__class__.__name__)
            raise GpError("GP rota unreachable") from None
        try:
            body = json.loads(raw)
        except ValueError:
            raise GpError("GP rota returned a non-JSON body for sessions") from None
        if not isinstance(body, dict) or not isinstance(body.get("sessions"), list):
            raise GpError("GP rota's sessions response has no 'sessions' list")
        return body

    @classmethod
    def from_settings(cls):
        return cls(settings.ROTA_URL, settings.ROTA_API_TOKEN)
