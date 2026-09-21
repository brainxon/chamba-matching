"""Workday - live test (2026-08-26) against the issue's own Airbus test
URL was INCONCLUSIVE. Constructed the CXS endpoint per the issue's own
recommendation:

  https://<tenant>.<wdN>.myworkdayjobs.com/wday/cxs/<tenant>/<site>/job/<jobPath>

from https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Mnchen-Area/Project-Management-Officer--d-f-m-_JR10416070
-> tenant=ag, site=Airbus, jobPath=Mnchen-Area/Project-Management-Officer--d-f-m-_JR10416070

Both GET and POST (empty body, and {"appliedFacets": {}}) returned
errors:
  - GET  -> 403 {"errorCode":"S22", "message":"permission denied"}
  - POST -> 400 {"errorCode":"HTTP_400"}

Left implemented (not deleted) so the exact failure is visible in
run_all.py's results.json - this needs real reverse-engineering (likely
missing a session/CSRF token the SPA acquires on first page load, or a
wrong path segment) beyond this POC's scope. See report.md - this
platform stays "not yet solved," not silently assumed to work.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .base import PlatformResult, fail, make_client, ok

PLATFORM = "workday"
_TENANT_HOST_RE = re.compile(r"^([a-z0-9-]+)\.[a-z0-9]+\.myworkdayjobs\.com$", re.IGNORECASE)


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return bool(_TENANT_HOST_RE.match(host))


def _parse(url: str) -> tuple[str, str, str] | None:
    """Returns (tenant, site, job_path) or None if the URL doesn't match
    the expected /<locale>/<site>/job/<jobPath> shape."""
    parsed = urlparse(url)
    host_match = _TENANT_HOST_RE.match(parsed.hostname or "")
    if not host_match:
        return None
    tenant = host_match.group(1)

    parts = [p for p in parsed.path.split("/") if p]
    if "job" not in parts:
        return None
    job_index = parts.index("job")
    if job_index < 1:
        return None
    site = parts[job_index - 1]
    job_path = "/".join(parts[job_index + 1 :])
    if not job_path:
        return None
    return tenant, site, job_path


def fetch(url: str) -> PlatformResult:
    parsed = _parse(url)
    if not parsed:
        return fail(PLATFORM, url, "native-api", "could not parse tenant/site/jobPath from URL")
    tenant, site, job_path = parsed
    host = urlparse(url).hostname
    api_url = f"https://{host}/wday/cxs/{tenant}/{site}/job/{job_path}"

    try:
        with make_client() as client:
            resp = client.post(api_url, json={})
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:  # noqa: BLE001
        return fail(PLATFORM, url, "native-api", f"unresolved endpoint shape: {e}")

    description = (data.get("jobPostingInfo") or {}).get("jobDescription")
    if not description:
        return fail(PLATFORM, url, "native-api", "response had no jobPostingInfo.jobDescription")
    return ok(PLATFORM, url, "native-api", text=description, title=data.get("title"))
