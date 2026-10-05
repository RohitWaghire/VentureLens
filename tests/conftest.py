"""Shared pytest fixtures.

The app is instantiated per-test with relaxed safety limits so the full user
flow can run deterministically with the demo provider (no credentials needed).
"""

from __future__ import annotations

import re

import pytest

from app.config import Settings
from app.main import create_app


def make_settings(**overrides) -> Settings:
    settings = Settings()
    defaults = {
        "rate_limit_per_ip": 100_000,
        "session_query_budget": 100,
        "global_query_budget": 100_000,
        "debug": True,
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


@pytest.fixture
def app():
    return create_app(make_settings())


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def csrf_for(client, path: str = "/") -> str:
    """Read the rendered per-session CSRF token from a page response."""
    response = client.get(path)
    match = re.search(r'name="csrf" value="([a-f0-9]+)"', response.text)
    assert match, f"CSRF token not found on {path}"
    return match.group(1)


@pytest.fixture
def flow(client):
    """A session driven to the plan page via the demo provider."""
    csrf = csrf_for(client)  # create session + cookie
    client.post(
        "/summary",
        data={"idea": "specialty coffee shop", "region": "Illinois", "csrf": csrf},
    )
    client.get("/cities")
    client.post("/cities", data={"action": "select", "city": "Chicago", "csrf": csrf})
    client.get("/neighborhoods")
    return client