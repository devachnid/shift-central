"""A read-only client for Practice HR's people feed, on the standard library.

GET {PRACTICE_HR_URL}/api/v1/people with `Authorization: Bearer <token>`
(practice-hr/api/auth.py). The token never travels over plain http
outside DEBUG, never appears in a log line or an error, and the response
is never logged: it is everyone's name and email."""

import json
import logging
import urllib.error
import urllib.request
from urllib.parse import urlparse

from django.conf import settings

log = logging.getLogger("people.hr_sync")

# An honest product name. The standard library's default ("Python-urllib/3.x")
# is refused by Cloudflare's bot checks in front of the tunnel (a 403 before
# the request reaches the app), so every outbound client names itself.
USER_AGENT = "ShiftCentral/1.0"


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_OPENER = urllib.request.build_opener(_RefuseRedirects)


class HRError(Exception):
    pass


class HRClient:
    def __init__(self, base_url, token, *, opener=None, timeout=10):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._open = opener or (lambda req: _OPENER.open(req, timeout=timeout))

    def people(self):
        url = f"{self.base_url}/api/v1/people"
        if urlparse(url).scheme != "https" and not settings.DEBUG:
            raise HRError("PRACTICE_HR_URL is not https; the token was not sent")
        req = urllib.request.Request(url, method="GET", headers={
            "Accept": "application/json", "Authorization": f"Bearer {self._token}",
            "User-Agent": USER_AGENT})
        try:
            with self._open(req) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            log.warning("hr people -> %s", e.code)
            raise HRError(f"Practice HR returned {e.code} for people") from None
        except (urllib.error.URLError, OSError) as e:
            log.warning("hr people unreachable: %s", e.__class__.__name__)
            raise HRError("Practice HR unreachable") from None
        try:
            body = json.loads(raw)
        except ValueError:
            raise HRError("Practice HR returned a non-JSON body for people") from None
        people = body.get("people") if isinstance(body, dict) else None
        if not isinstance(people, list):
            raise HRError("Practice HR's people response has no 'people' list")
        return people

    @classmethod
    def from_settings(cls):
        return cls(settings.PRACTICE_HR_URL, settings.HR_API_TOKEN)
