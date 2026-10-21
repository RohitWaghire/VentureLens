"""Shared pytest fixtures.

The app always uses the live provider. Tests replace its transport with a
stand-in so the suite never calls Qloo or a model.
"""

from __future__ import annotations

import pytest

from app.main import create_app
from tests.helpers import make_settings, scripted_fetch, walk_to_confirm


@pytest.fixture
def app():
    application = create_app(
        make_settings(
            qloo_api_key="qloo-test",
            llm_api_key="llm-test",
            llm_model="gpt-6-luna",
            llm_provider="openai",
        )
    )
    application.state.provider.fetch = scripted_fetch
    return application


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as current:
        yield current


@pytest.fixture
def flow(client):
    """A coffee-shop session through one question at a time and confirmation."""
    client.get("/")
    from tests.helpers import csrf_for

    csrf = csrf_for(client)
    client.post(
        "/start",
        data={
            "prompt": "I have $250k and want to open a specialty coffee shop in Illinois.",
            "csrf": csrf,
        },
    )
    page = walk_to_confirm(client)
    token = csrf_for(client, "/grill")
    assert "Does this match what you mean?" in page.text
    client.post("/grill", data={"csrf": token, "confirm": "1"})
    return client
