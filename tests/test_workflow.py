"""End-to-end user journey through the FastAPI boundary with fake providers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import make_settings
from tests.conftest import csrf_for
from app.main import create_app

REMAINING_FIELDS = ["budget", "audience", "concept", "price", "footprint", "competitors", "growth"]


def _complete_interview(client):
    token = csrf_for(client)
    client.post("/start", data={"prompt": "I want to open a specialty coffee shop", "csrf": token})
    # Region is a required question; other profile answers can be supplied or skipped.
    token = csrf_for(client)
    client.post("/interview", data={"field": "region", "answer": "Illinois", "csrf": token})
    for field in REMAINING_FIELDS:
        token = csrf_for(client)
        r = client.post("/interview", data={"field": field, "answer": "answered value", "csrf": token})
    return r


class TestInterviewFlow:
    def test_first_question_and_sets_cookie(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "vl_session" in r.headers.get("set-cookie", "")
        assert "A clearer view of" in r.text
        assert 'id="opening-prompt"' in r.text
        assert "Start exploring" in r.text
        assert "illustrative demo data" in r.text.lower()

    def test_frontend_assets_include_responsive_and_reduced_motion_support(self, client):
        css = client.get("/static/style.css")
        icon = client.get("/static/favicon.svg")
        assert css.status_code == 200
        assert "@media (max-width: 600px)" in css.text
        assert "prefers-reduced-motion: reduce" in css.text
        assert icon.status_code == 200
        assert "<svg" in icon.text

    def test_opening_prompt_starts_session_and_prefills_details(self, client):
        token = csrf_for(client)
        r = client.post(
            "/start",
            data={"prompt": "I have $250k and want to open a specialty coffee shop in Illinois.", "csrf": token},
        )
        assert r.status_code == 200
        assert "Who is your primary target customer" in r.text
        assert "specialty coffee shop" in r.text
        assert "$250k" in r.text
        assert "Illinois" in r.text
        assert "STEP 4 OF 9" in r.text

    def test_opening_prompt_without_region_asks_required_region(self, client):
        token = csrf_for(client)
        r = client.post("/start", data={"prompt": "I want to open a neighborhood bakery.", "csrf": token})
        assert r.status_code == 200
        assert "Which U.S. state or metro region" in r.text

    def test_blank_opening_prompt_returns_to_entry_with_error(self, client):
        token = csrf_for(client)
        r = client.post("/start", data={"prompt": "   ", "csrf": token})
        assert r.status_code == 200
        assert "Please describe your business idea" in r.text

    def test_new_idea_discards_current_session_and_returns_to_composer(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop in Illinois", "csrf": token})
        old_session = client.cookies.get("vl_session")
        token = csrf_for(client)
        r = client.post("/new", data={"csrf": token})
        assert r.status_code == 200
        assert "opening-prompt" in r.text
        new_session = client.cookies.get("vl_session")
        assert old_session != new_session

    def test_required_fields_cannot_be_skipped(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        token = csrf_for(client)
        r = client.post("/interview", data={"field": "region", "answer": " ", "skip": "1", "csrf": token})
        # Fails to advance; still on the idea question.
        assert "exploring" in r.text

    def test_full_interview_reaches_summary(self, client):
        _complete_interview(client)
        r = client.get("/profile-ready")
        assert "Your idea is taking shape" in r.text
        assert "illustrative demo data" in r.text.lower()
        assert "INTERVIEW COMPLETE" in r.text
        assert "Live web search and Qloo research are not connected" in r.text
        r = client.get("/summary")
        assert "Confirm your business profile" in r.text


class TestRegionGate:
    def test_missing_region_is_rejected(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        token = csrf_for(client)
        r = client.post("/summary", data={"idea": "coffee shop", "region": " ", "csrf": token})
        assert "are required" in r.text

    def test_invalid_region_rejected(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        token = csrf_for(client)
        r = client.post("/summary", data={"idea": "coffee shop", "region": "Nowhereland", "csrf": token})
        assert "not a recognized U.S. state" in r.text


class TestCityJourney:
    def test_city_outside_region_rejected(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop in Illinois", "csrf": token})
        token = csrf_for(client)
        client.post("/summary", data={"idea": "coffee shop", "region": "Illinois", "csrf": token})
        r = client.get("/cities")
        assert "Chicago" in r.text
        token = csrf_for(client, "/cities")
        r = client.post("/cities", data={"action": "custom", "city": "Phoenix", "csrf": token})
        assert "outside your selected region" in r.text


class TestFullJourney:
    def test_plan_page_and_download_rendered(self, flow):
        assert "Neighborhood comparison" in flow.get("/neighborhoods").text
        plan = flow.get("/plan")
        assert "Business Plan" in plan.text
        assert "withheld" in plan.text  # Hyde Park incomplete row is disclosed


class TestQueryBudget:
    def test_budget_exhaustion_blocks_research(self):
        app = create_app(make_settings(session_query_budget=1))
        with TestClient(app) as client:
            token = csrf_for(client)
            client.post("/start", data={"prompt": "coffee shop", "csrf": token})
            token = csrf_for(client)
            # Discovery consumes the sole budget unit.
            r = client.post("/summary", data={"idea": "coffee shop", "region": "Illinois", "csrf": token})
            assert "Top candidate cities" in r.text
            # Selecting a city needs another unit -> budget error.
            token = csrf_for(client, "/cities")
            r = client.post("/cities", data={"action": "select", "city": "Chicago", "csrf": token})
            assert "research allowance" in r.text

    def test_invalid_csrf_token_rejected(self, client):
        token = csrf_for(client)
        r = client.post("/start", data={"prompt": "coffee shop", "csrf": "invalid"})
        assert r.status_code == 403
        assert "Invalid session token" in r.text