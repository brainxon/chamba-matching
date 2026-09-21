"""Softgarden - the issue's own test URL had EXPIRED (HTTP 404) by the
time this POC ran (2026-08-26), so this could NOT be live-verified
either way. Left wired to the generic probe per the issue's own "Easy -
server-rendered + JSON-LD" rating (hypothesis, not confirmed) - see
report.md for the honest "inconclusive" verdict and a note to re-run
against a fresh posting."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult
from .generic_probe import probe

PLATFORM = "softgarden"


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return host.endswith("softgarden.de") or host.endswith("softgarden.io")


def fetch(url: str) -> PlatformResult:
    return probe(PLATFORM, url)
