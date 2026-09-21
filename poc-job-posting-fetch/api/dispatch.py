"""Dispatch a URL to its platform module by host/query-param pattern -
mirrors the real spec's §3.2 design (.issues/229-job-posting-fetch-de-
platforms/feature_spec.md). Order matters only in that the first match
wins; the modules below are mutually exclusive by host today so order
is not actually load-bearing yet, but kept deterministic anyway."""

from __future__ import annotations

from typing import Optional

from .platforms import (
    bundesagentur,
    eightfold,
    greenhouse,
    join_com,
    personio,
    phenom,
    sap_successfactors,
    softgarden,
    stepstone,
    workday,
)
from .platforms.base import PlatformResult, fail
from .known_blocked import check as check_known_blocked

_MODULES = [
    bundesagentur,
    greenhouse,
    personio,
    workday,
    sap_successfactors,
    softgarden,
    join_com,
    stepstone,
    eightfold,
    phenom,
]


def find_platform(url: str) -> Optional[str]:
    for module in _MODULES:
        if module.matches(url):
            return module.PLATFORM
    return None


def dispatch(url: str) -> PlatformResult:
    # Checked here (not just in main.py's endpoint) so run_all.py's
    # results.json reflects the same "will this actually work in the real
    # backend's network" decision as production, not "does it happen to
    # pass from whatever network this script runs on right now" - see
    # known_blocked.py's own docstring. Confirmed live 2026-08-28: this
    # exact distinction matters - Softgarden passed from a dev laptop's
    # network but failed identically to Workday from inside the real
    # backend's own Docker container.
    blocked = check_known_blocked(url)
    if blocked:
        return fail(blocked.platform, url, "fail-fast (no network call made)", blocked.reason)

    for module in _MODULES:
        if module.matches(url):
            return module.fetch(url)

    return fail("unknown", url, "dispatch", "no platform module matched this URL")
