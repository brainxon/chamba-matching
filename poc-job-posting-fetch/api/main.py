"""POC job-posting-fetch - FastAPI app.

Endpoints:
  GET  /health
  GET  /api/v1/platforms
  POST /api/v1/fetch    {"url": "..."}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import settings
from .dispatch import dispatch, find_platform

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = FastAPI(
    title="POC Job Posting Fetch",
    version="0.1.0",
    description="Validates native fetch strategies for the top 10 German job platforms (issue #229)",
)

# Permissive CORS - this is a local-only POC (see feature_spec.md scope),
# never deployed, so the usual origin-allowlist discipline doesn't apply.
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class FetchRequest(BaseModel):
    url: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "poc-job-posting-fetch"}


@app.get("/api/v1/platforms")
def platforms():
    from .dispatch import _MODULES

    return {"platforms": [m.PLATFORM for m in _MODULES]}


@app.post("/api/v1/fetch")
def fetch(req: FetchRequest):
    # dispatch() itself checks known_blocked.py first (fail-fast, no
    # network call) before trying any platform module - see dispatch.py's
    # own comment for why that now lives there instead of just here.
    platform = find_platform(req.url)
    result = dispatch(req.url)
    return {
        "matched_platform": platform,
        "success": result.success,
        "strategy": result.strategy,
        "title": result.title,
        "text_length": len(result.text) if result.text else 0,
        # Full text, not a truncated preview - this is a local-only POC
        # demo, no payload-size concern, and a truncated preview here
        # once looked like a real extraction bug (it wasn't - see the
        # chat writeup around 2026-08-27's bundesagentur review).
        "text": result.text,
        "error": result.error,
        "raw_meta": result.raw_meta,
    }
