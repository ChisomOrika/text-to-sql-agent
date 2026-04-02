"""API authentication and per-user rate limiting.

Uses API key authentication via X-API-Key header. Keys are stored in a simple
config for the demo — in production, use a proper secrets manager (AWS Secrets
Manager, HashiCorp Vault) and store hashed keys in a database.

Rate limiting uses a sliding window counter per API key. This prevents a single
user from burning through your Claude API credits. The window and limit are
configurable per key, so you can give higher limits to trusted internal users.
"""

import time
from collections import defaultdict
from typing import Any

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

# API key store — in production, load from a database or secrets manager.
# Keys map to user metadata for logging/auditing.
API_KEYS: dict[str, dict[str, Any]] = {
    "demo-key-001": {
        "user": "demo",
        "rate_limit": 60,       # requests per window
        "rate_window": 60,      # window in seconds
    },
    "admin-key-001": {
        "user": "admin",
        "rate_limit": 300,
        "rate_window": 60,
    },
}

# Sliding window counters: key -> list of request timestamps
_request_log: dict[str, list[float]] = defaultdict(list)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
) -> dict[str, Any]:
    """Validate API key and enforce rate limits. Returns user metadata."""
    # Allow unauthenticated access to health and docs
    if request.url.path in ("/api/health", "/docs", "/openapi.json", "/redoc"):
        return {"user": "anonymous", "rate_limit": 10, "rate_window": 60}

    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    user_meta = API_KEYS.get(api_key)
    if not user_meta:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Rate limit check
    _enforce_rate_limit(api_key, user_meta)

    return user_meta


def _enforce_rate_limit(api_key: str, user_meta: dict[str, Any]):
    """Sliding window rate limiter."""
    now = time.time()
    window = user_meta.get("rate_window", 60)
    limit = user_meta.get("rate_limit", 60)

    # Remove expired entries
    _request_log[api_key] = [
        ts for ts in _request_log[api_key] if now - ts < window
    ]

    if len(_request_log[api_key]) >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded: {limit} requests per {window}s",
            headers={"Retry-After": str(window)},
        )

    _request_log[api_key].append(now)
