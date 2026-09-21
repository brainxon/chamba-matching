"""StepStone - live test (2026-08-26) against the issue's own test URL
CONFIRMED this is blocked: a plain httpx GET to the ad page itself
already returns HTTP 403 (DataDome bot protection), before any redirect-
resolution logic even gets a chance to look for the outbound
company-ATS link the real spec's §3.4 proposed extracting.

This is a stronger negative result than the real spec anticipated (it
assumed the ad page itself would at least be fetchable) - the
redirect-resolution strategy is NOT VIABLE via a plain server-side HTTP
client. Would need a real browser session (cookies/JS challenge) to get
past DataDome, which is squarely tier 2/Playwright territory the
existing backend already has - not a new "native fetcher" win. Matches
the issue's own "Hard - DataDome bot protection; better to resolve to
the original company ATS" note, except even the resolution step itself
is blocked. See report.md.
"""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult, fail, make_client

PLATFORM = "stepstone"


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.endswith("stepstone.de") or host.endswith("stepstone.com")


def fetch(url: str) -> PlatformResult:
    try:
        with make_client() as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return fail(PLATFORM, url, "redirect-resolution", f"blocked before redirect resolution could run: {e}")

    # Unreachable today (see module docstring) - left in place for when/if
    # a browser-backed fetch (tier 2) is used to get past DataDome instead.
    return fail(PLATFORM, url, "redirect-resolution", "page fetched but outbound-link extraction not implemented")
