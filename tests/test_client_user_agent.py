"""Both outbound clients name themselves. The standard library's default agent
("Python-urllib/3.x") is refused by Cloudflare's bot checks in front of the
tunnel with a 403 that never reaches the app, which made the first sync on a
tunnelled staging box fail."""

import io
import json
from datetime import date

from people.services.hr_client import USER_AGENT, HRClient
from shifts.services.gp_client import GpClient


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _capture(body):
    seen = []

    def opener(req):
        seen.append(req)
        return _Resp(json.dumps(body).encode())

    return seen, opener


def test_the_hr_client_sends_its_own_user_agent():
    seen, opener = _capture({"people": []})
    HRClient("https://hr.example", "t", opener=opener).people()
    assert seen[0].get_header("User-agent") == USER_AGENT
    assert "urllib" not in USER_AGENT.lower()


def test_the_gp_client_sends_its_own_user_agent():
    seen, opener = _capture({"sessions": []})
    GpClient("https://rota.example", "t", opener=opener).sessions(date(2027, 1, 1), date(2027, 1, 31))
    assert seen[0].get_header("User-agent") == USER_AGENT
