"""Shared contract every platform module follows - mirrors the real
backend's job_posting_url_fetcher_service.py convention: never raise,
always return a result object the caller can log/inspect, even on
failure. That "never raise" discipline is the actual thing this POC is
validating is practical per platform, not just whether extraction works."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

from ..config import settings

log = logging.getLogger(__name__)


@dataclass
class PlatformResult:
    platform: str
    url: str
    success: bool
    text: Optional[str] = None
    title: Optional[str] = None
    strategy: str = ""
    error: Optional[str] = None
    raw_meta: dict = field(default_factory=dict)


def make_client() -> httpx.Client:
    return httpx.Client(
        timeout=settings.http_timeout_seconds,
        follow_redirects=True,
        headers={"User-Agent": settings.user_agent},
    )


def fail(platform: str, url: str, strategy: str, error: str) -> PlatformResult:
    log.warning("%s: %s failed (%s): %s", platform, url, strategy, error)
    return PlatformResult(platform=platform, url=url, success=False, strategy=strategy, error=error)


def ok(platform: str, url: str, strategy: str, text: str, title: Optional[str] = None, **raw_meta) -> PlatformResult:
    return PlatformResult(
        platform=platform,
        url=url,
        success=True,
        text=text,
        title=title,
        strategy=strategy,
        raw_meta=raw_meta,
    )
