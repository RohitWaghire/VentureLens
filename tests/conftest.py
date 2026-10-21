"""Shared pytest fixtures.

The app is instantiated per-test with relaxed safety limits so the full
grilling pipeline runs deterministically with the demo provider (no credentials
needed).
"""

from __future__ import annotations

import pytest

from app.main import create_app
from tests.helpers import answer_grill, csrf_for, make_settings


@pytest.fixture
def app():
    return create_app(make_settings())


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


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