"""Shared JSON-LD + trafilatura probe - what the real backend's EXISTING
tier 0/1 pipeline already does with zero platform-specific code
(job_posting_url_fetcher_service.py). Used by the platform modules below
whose live test (2026-08-26) showed the existing generic pipeline
already produces good text, so no bespoke native fetcher is warranted:

  - Personio: the individual job page embeds real schema.org JobPosting
    JSON-LD directly (confirmed - the XML feed some docs point to isn't
    even needed).
  - JOIN: same, JSON-LD present after following its redirect.
  - SAP SuccessFactors (RMK): no JSON-LD, but trafilatura alone produced
    3420 chars of clean, well-structured text from the raw HTML - no
    custom selectors needed after all (contradicts this issue's own
    original "Medium, needs custom selectors" assumption).

Softgarden and Phenom's test URLs had EXPIRED (404 / 410) by the time
this POC ran, so those two couldn't be live-verified either way - see
report.md.

FINDING (also worth taking back to the real backend, not just this POC):
trafilatura against Eightfold's client-rendered SPA shell "extracted"
172KB of embedded frontend theme/config JSON, not job text - a false
positive under a naive `len(text) >= MIN_USABLE_TEXT_LENGTH` check alone
(exactly what the real job_posting_url_fetcher_service.py's tier 1 check
does today). _looks_like_json() below rejects that specific failure
mode; the real backend doesn't have an equivalent guard yet.

SECOND FINDING (2026-08-27, caught live testing the demo UI): the
original SAP SuccessFactors test URL (Hensoldt, Ulm posting) had
expired - the posting is gone, but the site doesn't 404/410 like
Softgarden/Phenom did. It returns a plain HTTP 200 with its generic
site-chrome/nav shell instead, ending in "The page you are trying to
access is for employees. Please login." trafilatura happily "extracted"
that nav (733 chars, comfortably over MIN_USABLE_TEXT_LENGTH) because
it's real prose-shaped text, not JSON - _looks_like_json() doesn't catch
this at all, it's a different failure shape. The tell: the exact same
nav block ("Home\nSites\nGermany\n...") repeats verbatim 2-3 times in
the extracted text - real job descriptions don't do that.
_looks_like_repeated_boilerplate() below catches this by duplicate-line
ratio. Replaced with a fresh, confirmed-working Hensoldt URL (Enfield,
Senior RF Engineer) in sample-data/test-urls.json.
"""

from __future__ import annotations

import html as html_module
import json

import trafilatura
from bs4 import BeautifulSoup

from .base import PlatformResult, fail, make_client, ok


def _looks_like_json(text: str) -> bool:
    """Rejects the Eightfold false-positive: a client-rendered SPA shell
    with no real content dumps its own frontend config as inline JSON,
    which trafilatura sometimes "extracts" as if it were the main text.
    A real job description is prose; this is a structural fingerprint
    check, not a content check - cheap and specific to that failure mode."""
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        json.loads(stripped)
        return True
    except json.JSONDecodeError:
        # Even non-parseable JSON-*shaped* blobs (truncated, nested
        # further than trafilatura captured) still aren't prose - a high
        # density of `"key":` pairs is enough of a signal on its own.
        return stripped.count('":') > 20


def _looks_like_repeated_boilerplate(text: str) -> bool:
    """Rejects the SAP SuccessFactors false-positive found live
    (2026-08-27): a site-chrome/nav shell served with HTTP 200 for an
    expired posting, no error status to key off of. Real job descriptions
    don't repeat entire lines verbatim; a site nav rendered multiple
    times on the page (once per breakpoint/menu variant, commonly) does.
    Threshold (>=30% duplicate, >=3 non-trivial lines) is deliberately
    conservative - a real job posting can reasonably repeat a short
    phrase or two, just not a third of its own lines."""
    lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) >= 3]
    if len(lines) < 3:
        return False
    seen = set()
    duplicate_count = 0
    for line in lines:
        if line in seen:
            duplicate_count += 1
        seen.add(line)
    return (duplicate_count / len(lines)) >= 0.3


def probe(platform: str, url: str) -> PlatformResult:
    try:
        with make_client() as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text
    except Exception as e:  # noqa: BLE001
        return fail(platform, url, "generic-probe", str(e))

    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            types = candidate.get("@type")
            types = types if isinstance(types, list) else [types]
            if "JobPosting" in types and isinstance(candidate.get("description"), str):
                # Some sites (e.g. JOIN) double-escape - the JSON string
                # itself contains "&lt;p&gt;" rather than a real "<p>" tag,
                # same pattern as Greenhouse's `content` field. One
                # html.unescape() pass before stripping tags handles both
                # cases (a no-op for sites that weren't double-escaped).
                unescaped = html_module.unescape(candidate["description"])
                text = BeautifulSoup(unescaped, "html.parser").get_text(separator="\n").strip()
                if text:
                    return ok(platform, url, "generic-probe:json-ld", text=text, title=candidate.get("title"))

    text = trafilatura.extract(html)
    if text and len(text.strip()) >= 200:
        if _looks_like_json(text):
            return fail(platform, url, "generic-probe:trafilatura", "extracted text looks like embedded JSON, not prose - likely a JS SPA shell")
        if _looks_like_repeated_boilerplate(text):
            return fail(
                platform,
                url,
                "generic-probe:trafilatura",
                "extracted text is mostly duplicate lines - likely site nav/chrome for an expired posting, not a job description",
            )
        return ok(platform, url, "generic-probe:trafilatura", text=text.strip())

    return fail(platform, url, "generic-probe", "neither JSON-LD nor trafilatura produced usable text")
