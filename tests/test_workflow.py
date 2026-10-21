"""End-to-end grilling pipeline through the FastAPI boundary with fake providers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import csrf_for, make_settings
from app.main import create_app


class TestEntry:
    def test_landing_renders_composer(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "vl_session" in r.headers.get("set-cookie", "")
        assert 'id="opening-prompt"' in r.text
        assert "Start exploring" in r.text
        assert "illustrative demo data" in r.text.lower()

    def test_blank_prompt_returns_error(self, client):
        token = csrf_for(client)
        r = client.post("/start", data={"prompt": "   ", "csrf": token})
        assert "Please describe your business idea" in r.text

    def test_invalid_csrf_rejected(self, client):
        csrf_for(client)
        r = client.post("/start", data={"prompt": "coffee shop", "csrf": "invalid"})
        assert r.status_code == 403
        assert "Invalid session token" in r.text


class TestGrilling:
    def test_start_opens_first_dynamic_question(self, client):
        token = csrf_for(client)
        client.post(
            "/start",
            data={"prompt": "I have $250k and want to open a specialty coffee shop in Illinois.", "csrf": token},
        )
        r = client.get("/grill")
        assert "When would you hope to launch?" in r.text
        assert "Who is your primary customer" in r.text
        assert "What's your approximate start-up budget?" not in r.text
        assert "(Recommended)" in r.text
        assert "PLANNING GUIDE" in r.text

    def test_answers_advance_without_replaying_history(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        token = csrf_for(client)
        client.post(
            "/grill",
            data={"csrf": token, "a_budget": "Under $150k"},
        )
        r = client.get("/grill")
        assert "Under $150k" not in r.text
        assert "What's your approximate start-up budget?" not in r.text
        assert "When would you hope to launch?" in r.text

    def test_grill_offer_options_derived_from_prompt(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        r = client.get("/grill")
        assert 'type="radio" name="a_budget"' in r.text
        assert "Under $50k" in r.text

    def test_confirm_after_the_tree_produces_report(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        token = csrf_for(client, "/grill")
        client.post(
            "/grill",
            data={
                "csrf": token,
                "a_budget": "Under $150k",
                "a_timeline": "Within 6 months",
                "a_audience": "Local regulars",
                "a_concept": "Lean and focused",
                "a_location": "One city / metro",
                "a_team": "Just me",
            },
        )
        token = csrf_for(client, "/grill")
        client.post(
            "/grill",
            data={
                "csrf": token,
                "a_coffee_position": "Espresso bar",
                "a_open_questions": "Nothing else",
            },
        )
        token = csrf_for(client, "/grill")
        page = client.get("/grill")
        assert "Does this match what you mean?" in page.text
        client.post("/grill", data={"csrf": token, "confirm": "1"})
        r = client.get("/report")
        assert "Business brief" in r.text
        assert "Under $150k" in r.text
        assert "demo provider" in r.text.lower()


class TestReport:
    def test_report_page_and_download(self, flow):
        page = flow.get("/report")
        assert "Business brief — specialty coffee shop" in page.text
        download = flow.get("/report/download")
        assert download.headers["content-type"].startswith("text/markdown")
        assert "# Business brief" in download.text
        assert "Within 6 months" in download.text

    def test_new_idea_discards_session_and_returns_to_composer(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        old = client.cookies.get("vl_session")
        token = csrf_for(client)
        r = client.post("/new", data={"csrf": token})
        assert 'id="opening-prompt"' in r.text
        assert client.cookies.get("vl_session") != old


class TestQueryBudget:
    def test_budget_exhaustion_blocks_report(self):
        app = create_app(make_settings(session_query_budget=1))
        with TestClient(app) as client:
            token = csrf_for(client)
            client.post("/start", data={"prompt": "coffee shop", "csrf": token})  # consumes budget
            token = csrf_for(client)
            client.post("/grill", data={"csrf": token, "confirm": "1"})  # report needs budget -> blocked
            r = client.get("/report")
            assert "research allowance" in r.text