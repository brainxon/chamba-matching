"""Env-var config, loaded once at import time (python-dotenv reads .env if
present, real env vars always win). See .env.example for every var this
POC reads - the point is nothing here is hardcoded, unlike poc-typst-cv's
db_extractor.py hardcoding its DB connection string directly."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    arbeitsagentur_api_key: str
    http_timeout_seconds: float
    user_agent: str
    log_level: str
    port: int


def _load() -> Settings:
    return Settings(
        arbeitsagentur_api_key=os.getenv("ARBEITSAGENTUR_API_KEY", "jobboerse-jobsuche"),
        http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "10")),
        user_agent=os.getenv(
            "FETCH_USER_AGENT",
            "Mozilla/5.0 (compatible; HustlenJobPostingPOC/1.0; +https://hustlen.ai)",
        ),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        port=int(os.getenv("PORT", "8002")),
    )


settings = _load()
