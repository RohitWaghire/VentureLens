"""Live provider with a fake transport. No network and no real credentials."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

from app.config import Settings
from app.model import BusinessProfile, GrillTurn
from app.providers.base import ProviderError
from app.providers.live import LiveProvider


def test_qloo_uses_a_place_tag_and_the_answered_location():
    settings = _settings()
    calls = []

    def fetch(method, url, headers, body, timeout):
        if method != "GET":
            return _brief()
        calls.append(url)
        if "/v2/tags" in url:
            return 200, json.dumps(
                {
                    "results": {
                        "tags": [
                            {"id": "urn:tag:genre:media:comedy", "name": "Comedy", "type": "urn:tag:genre:media"},
                            {
                                "id": "urn:tag:genre:place:grocery_store",
                                "name": "Grocery Store",
                                "type": "urn:tag:genre:place",
                            },
                        ]
                    }
                }
            ).encode()
        return 200, json.dumps(
            {
                "results": {
                    "entities": [
                        {
                            "name": "Corner Market",
                            "entity_id": "place-1",
                            "tags": [{"name": "grocery"}],
                            "properties": {"short_description": "Neighborhood grocery."},
                        }
                    ]
                }
            }
        ).encode()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region=""),
        "I want to start a grocery shop in NYC.",
        [GrillTurn(question_id="location", question="Where?", answer="New York")],
    )
    insights = next(url for url in calls if "/v2/insights" in url)
    query = parse_qs(urlparse(insights).query)
    assert query["filter.tags"] == ["urn:tag:genre:place:grocery_store"]
    assert "signal.interests.tags" not in query
    assert query["filter.location.query"] == ["New York"]
    taste = next(section.body for section in report.sections if section.heading == "Taste signals")
    assert "Corner Market" in taste


def test_gpt6_luna_brief_omits_temperature_and_keeps_qloo_places():
    settings = _settings()
    captured = {}

    def fetch(method, url, headers, body, timeout):
        if method == "GET":
            payload = {
                "results": {
                    "tags": [
                        {
                            "id": "urn:tag:genre:place:grocery_store",
                            "name": "Grocery Store",
                            "type": "urn:tag:genre:place",
                        }
                    ],
                    "entities": [
                        {
                            "name": "Corner Market",
                            "entity_id": "place-1",
                            "tags": [{"name": "grocery"}],
                            "properties": {"short_description": "Neighborhood grocery."},
                        }
                    ],
                }
            }
            return 200, json.dumps(payload).encode()
        captured["url"] = url
        captured["body"] = json.loads(body)
        captured["auth"] = headers.get("Authorization")
        return _brief()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region="New York"),
        "I want to start a grocery shop in New York.",
        [],
    )

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["body"]["model"] == "gpt-6-luna"
    assert captured["body"]["reasoning_effort"] == "none"
    assert "temperature" not in captured["body"]
    assert captured["auth"] == "Bearer llm-test"
    assert any(section.heading == "Taste signals" and "Corner Market" in section.body for section in report.sections)
    assert "aggregate Qloo" in report.caveat


def test_qloo_timeout_still_writes_the_brief():
    settings = _settings()

    def fetch(method, url, headers, body, timeout):
        if method == "GET":
            raise ProviderError("The taste service or the model could not be reached.")
        return _brief()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region="New York"),
        "I want to start a grocery shop in New York.",
        [],
    )
    assert report.title
    taste = next(section.body for section in report.sections if section.heading == "Taste signals")
    assert "no place affinities" in taste


def test_uncertain_tag_does_not_call_insights():
    settings = _settings()
    calls = []

    def fetch(method, url, headers, body, timeout):
        if method != "GET":
            return _brief()
        calls.append(url)
        return 200, json.dumps(
            {
                "results": {
                    "tags": [
                        {"id": "urn:tag:genre:place:bookstore", "name": "Bookstore", "type": "urn:tag:genre:place"}
                    ]
                }
            }
        ).encode()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region="New York"),
        "I want to start a grocery shop in New York.",
        [GrillTurn(question_id="focus", question="Where will you open?", answer="Brooklyn")],
    )
    assert not any("/v2/insights" in url for url in calls)
    taste = next(section.body for section in report.sections if section.heading == "Taste signals")
    assert "no place affinities" in taste


def test_cuisine_tag_without_the_word_place_is_a_valid_signal():
    settings = _settings()
    calls = []

    def fetch(method, url, headers, body, timeout):
        if method != "GET":
            return _brief()
        calls.append(url)
        if "/v2/tags" in url:
            return 200, json.dumps(
                {
                    "results": {
                        "tags": [
                            {
                                "id": "urn:tag:genre:restaurant:Italian",
                                "name": "Italian",
                                "type": "urn:tag:genre:restaurant",
                            }
                        ]
                    }
                }
            ).encode()
        return 200, b'{"results":{"entities":[]}}'

    LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="Italian restaurant", region="Chicago"),
        "I want to open an Italian restaurant in Chicago.",
        [],
    )
    insights = next(url for url in calls if "/v2/insights" in url)
    query = parse_qs(urlparse(insights).query)
    assert query["filter.tags"] == ["urn:tag:genre:restaurant:Italian"]


def test_cafe_tag_matches_a_coffee_shop():
    from app.providers.live import _best_tag

    tag = _best_tag(
        [
            (
                "coffee shop",
                [
                    {
                        "id": "urn:tag:category:place:cafe",
                        "name": "Cafe",
                        "type": "urn:tag:category:place",
                    }
                ],
            )
        ]
    )
    assert tag is not None
    assert tag["id"] == "urn:tag:category:place:cafe"


def test_uncertain_place_tag_is_not_sent_to_qloo():
    from app.providers.live import _best_tag

    tag = _best_tag(
        [
            (
                "grocery store",
                [
                    {"id": "urn:tag:genre:place:bookstore", "name": "Bookstore", "type": "urn:tag:genre:place"},
                    {"id": "urn:tag:genre:media:comedy", "name": "Comedy", "type": "urn:tag:genre:media"},
                ],
            )
        ]
    )
    assert tag is None


def test_questions_change_with_the_business_idea():
    settings = _settings()

    def fetch(method, url, headers, body, timeout):
        user = json.loads(body)["messages"][1]["content"]
        if "yoga" in user:
            text, options = "What kind of classes should the studio lead with?", ["Vinyasa", "Yin", "Hot yoga"]
        else:
            text, options = "What should fill most of the shelves?", ["Produce", "Packaged staples", "Prepared food"]
        return 200, json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "questions": [
                                        {
                                            "id": "focus",
                                            "text": text,
                                            "options": options,
                                            "recommendation": options[0],
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()

    provider = LiveProvider(settings, fetch)
    yoga = provider.frontier(BusinessProfile(idea="yoga studio"), [])
    grocery = provider.frontier(BusinessProfile(idea="grocery shop"), [])
    assert "classes" in yoga[0].text
    assert "shelves" in grocery[0].text
    assert yoga[0].text != grocery[0].text


def _settings() -> Settings:
    settings = Settings()
    settings.provider = "live"
    settings.qloo_api_key = "qloo-test"
    settings.qloo_base_url = "https://hackathon.api.qloo.com"
    settings.llm_api_key = "llm-test"
    settings.llm_provider = "openai"
    settings.llm_model = "gpt-6-luna"
    settings.llm_base_url = ""
    return settings


def _brief():
    return 200, json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "Brief",
                                "summary": "A grocery shop brief.",
                                "sections": [{"heading": "Next", "body": "Open on a main street."}],
                            }
                        )
                    }
                }
            ]
        }
    ).encode()
