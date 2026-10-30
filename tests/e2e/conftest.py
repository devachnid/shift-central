"""Browser tests run only with E2E=1: they need Chromium. In this
container Playwright's browser is at /opt/pw-browsers/chromium (set
E2E_CHROMIUM); CI installs one with `playwright install`."""

import os

import pytest

if not os.environ.get("E2E"):
    collect_ignore_glob = ["*"]
else:
    # Playwright's sync API keeps an event loop running in the test thread,
    # which Django's ORM refuses to be called from. The test only seeds rows.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    path = os.environ.get("E2E_CHROMIUM")
    return {**browser_type_launch_args, **({"executable_path": path} if path else {}), "args": ["--no-sandbox"]}
