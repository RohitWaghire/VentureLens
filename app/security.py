"""Public-demo safeguards: rate limiting, budget tracking, CSRF, and IP handling.

Credentials stay server-side and out of browser code. Forwarded client-IP
headers are trusted only when a trusted-proxy allowlist is configured.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
import time
from typing import Dict, List, Optional

from fastapi import Request

from app.sessions import Session


def client_ip(request: Request, trusted_proxies: List[str]) -> str:
    """Best-effort client IP, honoring forwarded headers only behind proxies.

    In a real deployment verify ``trusted_proxies`` matches the actual reverse
    proxies. When the allowlist is empty, only the direct peer address is used.
    """
    direct = request.client.host if request.client else "unknown"
    if trusted_proxies:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first = xff.split(",")[0].strip()
            if first:
                return first
    return direct


def origin_allowed(request: Request, allowed_origins: List[str]) -> bool:
    """True when the request Origin is absent or in the allowed list.

    SameSite=Lax cookies already limit cross-site POSTs; this origin check is an
    additional defense-in-depth layer for state-changing requests.
    """
    origin = request.headers.get("origin")
    if not origin:
        return True
    return origin in allowed_origins


class RateLimiter:
    """Fixed-window per-IP rate limiting."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: Dict[str, list] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            window = self._hits.get(key, [])
            window = [ts for ts in window if now - ts < self.window]
            if len(window) >= self.limit:
                self._hits[key] = window
                return False
            window.append(now)
            self._hits[key] = window
            return True


class QueryBudget:
    """Per-session and global research-query budgets.

    A single provider research step consumes one unit. When either the session
    budget or the global budget is exhausted, no further research is spent and
    the app returns a clear user-facing response.
    """

    def __init__(self, per_session: int, global_budget: int) -> None:
        self.per_session = per_session
        self.global_budget = global_budget
        self._global_used = 0
        self._lock = threading.Lock()

    def can_spend(self, session: Session, count: int = 1) -> bool:
        if session.query_count + count > self.per_session:
            return False
        with self._lock:
            return self._global_used + count <= self.global_budget

    def register_spend(self, session: Session, count: int = 1) -> bool:
        if not self.can_spend(session, count):
            return False
        with self._lock:
            self._global_used += count
        session.bump_queries(count)
        return True


def csrf_token(secret: str, session: Session) -> str:
    msg = f"csrf:{session.id}:{session.csrf_salt}".encode()
    return hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()


def verify_csrf(secret: str, session: Session, token: Optional[str]) -> bool:
    expected = csrf_token(secret, session)
    return hmac.compare_digest(expected, token or "")