"""Phenom - the issue's own test URL had EXPIRED (HTTP 410 Gone) by the
time this POC ran (2026-08-26), so this could NOT be live-verified.
Wired to the generic probe as a best-effort attempt only - the issue
itself already rates this "Hard - JS SPA with hidden widgets/JSON API",
and nothing in this POC contradicts that. See report.md."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult
from .generic_probe import probe

PLATFORM = "phenom"

_KNOWN_HOSTS = ("jobs.msd.com",)


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host in _KNOWN_HOSTS


def fetch(url: str) -> PlatformResult:
    return probe(PLATFORM, url)
