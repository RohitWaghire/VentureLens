"""Helpers shared by workflow tests.

Kept outside ``conftest`` so test modules can import them. Pytest does not put
the repository root on ``sys.path`` when it is started as ``pytest`` rather
than ``python -m pytest``.
"""

from __future__ import annotations

import re

from app.config import Settings


def make_settings(**overrides) -> Settings:
    settings = Settings()
    defaults = {
        "rate_limit_per_ip": 100_000,
        "session_query_budget": 100,
        "global_query_budget": 100_000,
        "provider": "demo",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def csrf_for(client, path: str = "/") -> str:
    """Read the rendered per-session CSRF token from a page response."""
    response = client.get(path)
    match = re.search(r'name="csrf" value="([a-f0-9]+)"', response.text)
    assert match, f"CSRF token not found on {path}"
    return match.group(1)


def answer_grill(client, csrf: str, answers: dict):
    client.post("/grill", data={"csrf": csrf, **answers})
