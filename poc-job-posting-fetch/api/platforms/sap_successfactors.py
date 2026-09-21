"""SAP SuccessFactors (RMK career sites) - live test (2026-08-26) against
jobs.hensoldt.net showed NO JSON-LD, but trafilatura alone (no custom
selectors) produced 3420 chars of clean, well-structured text straight
from the raw HTML. Downgrades this issue's own original "Medium - needs
custom DOM selectors" assumption - no bespoke native fetcher needed
after all. See generic_probe.py's module docstring."""

from __future__ import annotations

from urllib.parse import urlparse

from .base import PlatformResult
from .generic_probe import probe

PLATFORM = "sap_successfactors"

# Every known RMK-hosted host from the issue's own "Companies covered"
# list, matched by suffix - NOT an exhaustive SuccessFactors detector
# (there is no reliable generic signature for this ATS beyond the
# `/job/<Location>-<Title>/<JobID>/` URL shape, which is too generic to
# match safely on its own).
_KNOWN_HOSTS_SUFFIXES = (
    "jobs.hensoldt.net",
    ".knds.com",
    ".kmweg.com",
    "karriere.knorr-bremse.com",
    "karriere.allianz.de",
    "jobs.man.eu",
    "jobs.tuvsud.com",
    "karriere.kraussmaffei.com",
    "jobs.te.com",
    "jobs.koerber.com",
    "karriere.canon.de",
    "jobs.webasto.com",
    "jobs.siemens-energy.com",
)


def matches(url: str) -> bool:
    host = urlparse(url).hostname or ""
    return any(host == h or host.endswith(h) for h in _KNOWN_HOSTS_SUFFIXES)


def fetch(url: str) -> PlatformResult:
    return probe(PLATFORM, url)
