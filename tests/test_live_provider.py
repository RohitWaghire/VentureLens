"""Live provider with a fake transport. No network and no real credentials."""

from __future__ import annotations

import json

from app.config import Settings
from app.model import BusinessProfile
from app.providers.live import LiveProvider


def test_gpt6_luna_brief_omits_temperature_and_keeps_qloo_places():
    settings = Settings()
    settings.provider = "live"
    settings.qloo_api_key = "qloo-test"
    settings.qloo_base_url = "https://hackathon.api.qloo.com"
    settings.llm_api_key = "llm-test"
    settings.llm_provider = "openai"
    settings.llm_model = "gpt-6-luna"
    settings.llm_base_url = ""
    captured = {}

    def fetch(method, url, headers, body, timeout):
        if method == "GET":
            return 200, json.dumps(
                {
                    "results": {
                        "tags": [{"id": "urn:tag:grocery", "name": "grocery"}],
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
            ).encode()
        captured["url"] = url
        captured["body"] = json.loads(body)
        captured["auth"] = headers.get("Authorization")
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
