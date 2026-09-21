"""Fail-fast layer - checked BEFORE any network call. If a URL's host
matches a platform we've already confirmed the fetch itself gets blocked
by (not an extraction problem - see report.md), skip straight to telling
the user to paste the text manually instead of burning the full ~10-40s
tiered-fetch timeout budget on an attempt we already know will fail.

This is a UX-layer intervention point, independent of ever solving the
underlying WAF block (Cloudflare on Workday, Akamai-style on StepStone) -
see the "④ el frontend, antes de intentar el fetch" option discussed for
issue #229. Kept as its own tiny module (not folded into dispatch.py) so
it's obvious this is a distinct kind of decision: "don't even try",
not "try and this platform's own fetch() will handle it".
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class KnownBlocked:
    platform: str
    reason: str


# Confirmed live (2026-08-26/27, from inside the actual Linux backend
# container - see report.md) - httpx-equivalent fetches get a raw
# connection reset/403 before any content is ever received. Revisit this
# list if the underlying WAF situation ever changes (see report.md's
# recommended options A-D) - it's meant to be short-lived, not a
# permanent blocklist.
_KNOWN_BLOCKED_HOST_SUFFIXES = {
    "myworkdayjobs.com": KnownBlocked(
        platform="workday",
        reason=(
            "Workday sites are protected by Cloudflare Bot Management. Confirmed live: "
            "httpx, requests, and even a real headless Chromium (Playwright) all get the "
            "connection reset before any content arrives - and the block appears to worsen "
            "with request volume (a tenant that worked once failed on a retry minutes later), "
            "not a fixed per-tenant allow/block list. Not worth attempting."
        ),
    ),
    "stepstone.de": KnownBlocked(
        platform="stepstone",
        reason=(
            "StepStone is protected by an Akamai-fronted WAF - confirmed live: a plain HTTP "
            "GET to the ad page itself returns 403, before any redirect-resolution logic "
            "(finding the outbound company-ATS link) even gets a chance to run."
        ),
    ),
    # Confirmed live 2026-08-28 against 2 different real tenants
    # (gruen.softgarden.io, om-digitalsolutions.career.softgarden.de) -
    # both Cloudflare-fronted, both reset the connection from a Linux
    # container. Originally assumed "no new code needed" (issue #229's own
    # "Easy" rating) - true for EXTRACTION (both have real JSON-LD/
    # trafilatura-parseable content, confirmed) but irrelevant if the
    # fetch itself never completes.
    "softgarden.io": KnownBlocked(
        platform="softgarden",
        reason=(
            "Softgarden career sites (both .io and career.softgarden.de) are Cloudflare-"
            "fronted and get a raw TLS connection reset from a Linux container on every "
            "tenant tried - same failure mode as Workday."
        ),
    ),
    "career.softgarden.de": KnownBlocked(
        platform="softgarden",
        reason=(
            "Softgarden career sites (both .io and career.softgarden.de) are Cloudflare-"
            "fronted and get a raw TLS connection reset from a Linux container on every "
            "tenant tried - same failure mode as Workday."
        ),
    ),
}


def check(url: str) -> KnownBlocked | None:
    host = urlparse(url).hostname or ""
    for suffix, info in _KNOWN_BLOCKED_HOST_SUFFIXES.items():
        if host == suffix or host.endswith("." + suffix):
            return info
    return None
