"""End-to-end user journey through the FastAPI boundary with fake providers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import make_settings
from app.main import create_app

REMAINING_FIELDS = ["budget", "audience", "concept", "price", "footprint", "competitors", "growth"]


def _complete_interview(client):
    client.get("/")
    r = client.post("/interview", data={"field": "idea", "answer": "specialty coffee shop"})
    r = client.post("/interview", data={"field": "region", "answer": "Illinois"})
    for field in REMAINING_FIELDS:
        r = client.post("/interview", data={"field": field, "answer": "answered value"})
    return r


class TestInterviewFlow:
    def test_first_question_and_sets_cookie(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "vl_session" in r.headers.get("set-cookie", "")
        assert "Let’s explore" in r.text

    def test_required_fields_cannot_be_skipped(self, client):
        client.get("/")
        r = client.post("/interview", data={"field": "idea", "answer": " ", "skip": "1"})
        # Fails to advance; still on the idea question.
        assert "exploring" in r.text

    def test_full_interview_reaches_summary(self, client):
        _complete_interview(client)
        r = client.get("/summary")
        assert "Confirm your business profile" in r.text


class TestRegionGate:
    def test_missing_region_is_rejected(self, client):
        client.get("/")
        r = client.post("/summary", data={"idea": "coffee shop", "region": " "})
        assert "are required" in r.text

    def test_invalid_region_rejected(self, client):
        client.get("/")
        r = client.post("/summary", data={"idea": "coffee shop", "region": "Nowhereland"})
        assert "not a recognized U.S. state" in r.text


class TestCityJourney:
    def test_city_outside_region_rejected(self, client):
        client.get("/")
        client.post("/summary", data={"idea": "coffee shop", "region": "Illinois"})
        r = client.get("/cities")
        assert "Chicago" in r.text
        r = client.post("/cities", data={"action": "custom", "city": "Phoenix"})
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
            client.get("/")
            # Discovery consumes the sole budget unit.
            r = client.post("/summary", data={"idea": "coffee shop", "region": "Illinois"})
            assert "Top candidate cities" in r.text
            # Selecting a city needs another unit -> budget error.
            r = client.post("/cities", data={"action": "select", "city": "Chicago"})
            assert "research allowance" in r.text