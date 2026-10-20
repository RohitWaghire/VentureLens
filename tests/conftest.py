"""Shared pytest fixtures.

The app is instantiated per-test with relaxed safety limits so the full
grilling pipeline runs deterministically with the demo provider (no credentials
needed).
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
        "provider": "demo",
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


def answer_grill(client, csrf: str, answers: dict):
    client.post("/grill", data={"csrf": csrf, **answers})


@pytest.fixture
def flow(client):
    """A coffee-shop session through both rounds and the confirmation."""
    client.get("/")
    csrf = csrf_for(client)
    client.post(
        "/start",
        data={
            "prompt": "I have $250k and want to open a specialty coffee shop in Illinois.",
            "csrf": csrf,
        },
    )
    csrf = csrf_for(client, "/grill")
    answer_grill(
        client,
        csrf,
        {
            "a_timeline": "Within 6 months",
            "a_audience": "Young professionals",
            "a_concept": "Premium / specialty",
            "a_team": "2–3",
        },
    )
    csrf = csrf_for(client, "/grill")
    answer_grill(
        client,
        csrf,
        {
            "a_coffee_position": "Specialty pour-over",
            "a_open_questions": "Nothing else",
        },
    )
    csrf = csrf_for(client, "/grill")
    client.post("/grill", data={"csrf": csrf, "confirm": "1"})
    return client