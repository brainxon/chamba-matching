"""Bundesagentur für Arbeit (Jobsuche) - CONFIRMED WORKING live against the
issue's own arbeitsagentur.de test domain (2026-08-26):

  1. The public-facing detail URL /jobsuche/jobdetail/<refnr> uses the RAW
     `referenznummer` directly in the path (confirmed: fetching
     https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003133331-S
     returns HTTP 200).
  2. GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{base64(refnr)}
     with header X-API-Key: jobboerse-jobsuche returns HTTP 200 with a JSON
     body containing `stellenangebotsTitel` (title) and
     `stellenangebotsBeschreibung` (the full description, Markdown-ish).

No web scraping, no JS rendering needed - this is the single strongest
candidate of all 10 platforms.
"""

from __future__ import annotations

import base64
from urllib.parse import urlparse

from .base import PlatformResult, fail, make_client, ok
from ..config import settings

PLATFORM = "bundesagentur"
_DETAIL_PATH_MARKER = "/jobsuche/jobdetail/"


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.endswith("arbeitsagentur.de") and _DETAIL_PATH_MARKER in url


def _extract_refnr(url: str) -> str | None:
    path = urlparse(url).path
    if _DETAIL_PATH_MARKER not in path:
        return None
    return path.split(_DETAIL_PATH_MARKER, 1)[1].strip("/")


def fetch(url: str) -> PlatformResult:
    refnr = _extract_refnr(url)
    if not refnr:
        return fail(PLATFORM, url, "native-api", "could not extract referenznummer from URL path")

    encoded = base64.b64encode(refnr.encode()).decode()
    api_url = f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{encoded}"

    try:
        with make_client() as client:
            resp = client.get(api_url, headers={"X-API-Key": settings.arbeitsagentur_api_key})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001 - deliberate: any failure here just means "this tier didn't work"
        return fail(PLATFORM, url, "native-api", str(e))

    description = data.get("stellenangebotsBeschreibung")
    if not description or not isinstance(description, str):
        return fail(PLATFORM, url, "native-api", "response had no stellenangebotsBeschreibung")

    return ok(
        PLATFORM,
        url,
        "native-api",
        text=description,
        title=data.get("stellenangebotsTitel"),
        referenznummer=refnr,
        firma=data.get("firma"),
    )
