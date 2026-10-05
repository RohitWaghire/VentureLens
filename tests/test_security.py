"""Security primitives: rate limit, budgets, CSRF, origin and IP handling."""

from __future__ import annotations

from app.config import Settings
from app.sessions import Session
from app.security import (
    QueryBudget,
    RateLimiter,
    client_ip,
    csrf_token,
    origin_allowed,
    verify_csrf,
)


class TestRateLimiter:
    def test_allows_within_limit_and_blocks_after(self):
        limiter = RateLimiter(limit=3, window_seconds=60)
        assert limiter.allow("ip:1") is True
        assert limiter.allow("ip:1") is True
        assert limiter.allow("ip:1") is True
        assert limiter.allow("ip:1") is False
        # Different key is unaffected.
        assert limiter.allow("ip:2") is True


class TestQueryBudget:
    def test_session_budget_blocks_further_spend(self):
        budget = QueryBudget(per_session=2, global_budget=100)
        s = Session("sid", max_age=3600)
        assert budget.register_spend(s, 1) is True
        assert budget.register_spend(s, 1) is True
        assert budget.register_spend(s, 1) is False

    def test_global_budget_blocks(self):
        budget = QueryBudget(per_session=100, global_budget=3)
        s = Session("sid", max_age=3600)
        assert budget.register_spend(s, 3) is True
        assert budget.register_spend(s, 1) is False


class TestCsrf:
    def test_token_verifies_and_rejects_forgery(self):
        settings = Settings()
        s = Session("sid", max_age=3600)
        token = csrf_token(settings.secret_key, s)
        assert verify_csrf(settings.secret_key, s, token) is True
        assert verify_csrf(settings.secret_key, s, "nope") is False
        assert verify_csrf("other-secret", s, token) is False


class TestOrigin:
    def test_allowed_origin_ok(self):
        assert origin_allowed(_req({"origin": "http://localhost:8000"}), ["http://localhost:8000"])

    def test_disallowed_origin_rejected(self):
        assert origin_allowed(_req({"origin": "https://evil.example"}), ["http://localhost:8000"]) is False

    def test_missing_origin_allowed(self):
        assert origin_allowed(_req({}), ["http://localhost:8000"]) is True


class TestClientIp:
    def test_ignores_forwarded_when_not_trusting_proxies(self):
        req = _req({"x-forwarded-for": "203.0.113.9"})
        req.client.host = "127.0.0.1"
        assert client_ip(req, []) == "127.0.0.1"

    def test_uses_forwarded_when_trusting_proxies(self):
        req = _req({"x-forwarded-for": "203.0.113.9"})
        req.client.host = "10.0.0.2"
        assert client_ip(req, ["10.0.0.2"]) == "203.0.113.9"


class _Req:
    def __init__(self, headers):
        headers.setdefault("host", "localhost")
        self.headers = headers
        self.client = type("Client", (), {"host": "127.0.0.1"})()

    def __getattr__(self, name):
        return None


_req = _Req