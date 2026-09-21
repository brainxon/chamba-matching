"""Greenhouse - CONFIRMED WORKING live against the issue's own test URL
(2026-08-26): GET https://boards-api.greenhouse.io/v1/boards/<token>/jobs/<id>?content=true
returns HTTP 200 with `title` and `content` (HTML, double HTML-entity-
encoded - e.g. the JSON string contains "&lt;p&gt;" literally, which
still needs one html.unescape() pass after JSON parsing before the tags
are real tags to strip).

Also detects Greenhouse hidden behind a custom domain via the `gh_jid`
query parameter (per the real spec's dispatch design, chamba-ai-backend-
fastapi#229) - NOT live-verified in this POC (no gh_jid example URL was
in the issue's test-URL set), flagged as such below.
"""

from __future__ import annotations

import html as html_module
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .base import PlatformResult, fail, make_client, ok

PLATFORM = "greenhouse"
_HOSTS = {"boards-api.greenhouse.io", "job-boards.eu.greenhouse.io", "job-boards.greenhouse.io"}


def matches(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host in _HOSTS or host.endswith(".greenhouse.io"):
        return True
    # gh_jid signature for Greenhouse hidden behind a custom company domain -
    # NOT live-verified (no example in the issue's test-URL set), see
    # module docstring.
    return "gh_jid" in parse_qs(parsed.query)


def _board_token_and_job_id(url: str) -> tuple[str, str] | None:
    """job-boards.eu.greenhouse.io/<token>/jobs/<id> - the only pattern
    live-verified in this POC."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 3 and parts[-2] == "jobs":
        return parts[0], parts[-1]
    return None


def fetch(url: str) -> PlatformResult:
    ids = _board_token_and_job_id(url)
    if not ids:
        return fail(PLATFORM, url, "native-api", "could not extract board token / job id from URL path")
    token, job_id = ids

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}?content=true"
    try:
        with make_client() as client:
            resp = client.get(api_url)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        return fail(PLATFORM, url, "native-api", str(e))

    content = data.get("content")
    if not content or not isinstance(content, str):
        return fail(PLATFORM, url, "native-api", "response had no content field")

    # content is HTML, itself HTML-entity-escaped in the JSON payload -
    # unescape once to get real tags, then strip them for clean text.
    unescaped_html = html_module.unescape(content)
    text = BeautifulSoup(unescaped_html, "html.parser").get_text(separator="\n").strip()

    return ok(PLATFORM, url, "native-api", text=text, title=data.get("title"), company=data.get("company_name"))
