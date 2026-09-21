"""Eightfold AI - live test (2026-08-26) against jobs.infineon.com
CONFIRMED this is hard: no JSON-LD, and trafilatura's "extraction" was
172KB of embedded frontend theme/config JSON, not job text - this is a
pure client-rendered JS SPA. No native fetcher attempted here; the
existing backend's Playwright tier 2 is already the right (if slow) tool
for this, and this POC found no better alternative. See report.md."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult
from .generic_probe import probe

PLATFORM = "eightfold"

_KNOWN_HOSTS = ("jobs.infineon.com",)


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in _KNOWN_HOSTS


def fetch(url: str) -> PlatformResult:
    # Deliberately still routed through the generic probe (not skipped
    # entirely) so run_all.py's results.json shows the actual failure
    # mode, not just an assumption.
    return probe(PLATFORM, url)
