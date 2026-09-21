"""Personio - live test (2026-08-26) showed the individual job page
already embeds real schema.org JobPosting JSON-LD. No native fetcher
needed - see generic_probe.py's module docstring for the full finding."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult
from .generic_probe import probe

PLATFORM = "personio"


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return ".jobs.personio." in host


def fetch(url: str) -> PlatformResult:
    return probe(PLATFORM, url)
