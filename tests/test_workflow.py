"""End-to-end grilling pipeline through the FastAPI boundary with fake providers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.providers.base import ProviderError
from tests.helpers import csrf_for, make_settings
from app.main import create_app


class TestEntry:
    def test_landing_renders_composer(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "vl_session" in r.headers.get("set-cookie", "")
        assert 'id="opening-prompt"' in r.text
        assert "Start exploring" in r.text
        assert "illustrative demo data" not in r.text.lower()
        assert "demo flow" not in r.text.lower()
        assert "sends your idea" in r.text.lower()

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
    def test_start_opens_only_the_current_question(self, client):
        token = csrf_for(client)
        client.post(
            "/start",
            data={"prompt": "I have $250k and want to open a specialty coffee shop in Illinois.", "csrf": token},
        )
        r = client.get("/grill")
        assert 'class="question-title">When would you hope to launch?</h1>' in r.text
        assert r.text.count('class="round-question"') == 1
        assert "Who is your primary customer" not in r.text
        assert "What's your approximate start-up budget?" not in r.text
        assert "Do you have a location" not in r.text
        assert "Decisions we can settle now" not in r.text
        assert "(Recommended)" in r.text

    def test_answers_advance_without_replaying_history(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        token = csrf_for(client)
        from tests.helpers import answer_current

        answer_current(client)
        r = client.get("/grill")
        assert "Within 6 months" not in r.text
        assert "What's your approximate start-up budget?" not in r.text
        assert 'class="question-title">Who is your primary customer?</h1>' in r.text
        assert "When would you hope to launch?" not in r.text
        assert r.text.count('class="round-question"') == 1

    def test_grill_offer_options_come_from_the_question(self, client):
        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        r = client.get("/grill")
        assert 'type="radio" name="a_launch"' in r.text
        assert "Within 6 months" in r.text

    def test_confirm_after_the_questions_produces_report(self, client):
        from tests.helpers import walk_to_confirm

        token = csrf_for(client)
        client.post("/start", data={"prompt": "coffee shop", "csrf": token})
        page = walk_to_confirm(client)
        assert "Does this match what you mean?" in page.text
        token = csrf_for(client, "/grill")
        client.post("/grill", data={"csrf": token, "confirm": "1"})
        r = client.get("/report")
        assert "Business brief" in r.text
        assert "Within 6 months" in r.text
        assert "demo provider" not in r.text.lower()
        assert "aggregate qloo" in r.text.lower()


class TestLiveGrillingPage:
    def test_a_failed_model_does_not_show_the_shared_checklist(self):
        app = create_app(
            make_settings(
                provider="live",
                qloo_api_key="qloo-test",
                llm_api_key="llm-test",
                llm_model="gpt-6-luna",
            )
        )

        def fetch(method, url, headers, body, timeout):
            raise ProviderError("The taste service or the model could not be reached.")

        app.state.provider.fetch = fetch
        with TestClient(app, raise_server_exceptions=False) as client:
            token = csrf_for(client)
            client.post(
                "/start",
                data={"prompt": "I want to start a grocery shop in NYC.", "csrf": token},
            )
            page = client.get("/grill")
        assert page.status_code != 500
        assert "start-up budget" not in page.text.lower()
        assert "when would you hope to launch" not in page.text.lower()
        assert "did not return" in page.text.lower() or "could not" in page.text.lower()


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