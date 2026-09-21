"""JOIN - live test (2026-08-26) showed real schema.org JobPosting JSON-LD
present after following join.com's own redirect. No native fetcher
needed - see generic_probe.py's module docstring for the full finding."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult
from .generic_probe import probe

PLATFORM = "join"


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == "join.com" or host.endswith(".join.com")


def fetch(url: str) -> PlatformResult:
    return probe(PLATFORM, url)
