"""Helpers shared by workflow tests.

The app has no demo provider. These tests talk to the live provider with a
stand-in transport so they never call Qloo or a model.
"""

from __future__ import annotations

import json
import re

from app.config import Settings


_QUESTIONS = (
    (
        "launch",
        "When would you hope to launch?",
        ["Within 6 months", "6–12 months", "Longer term"],
    ),
    (
        "audience",
        "Who is your primary customer?",
        ["Young professionals", "Students", "Local regulars"],
    ),
    (
        "offer",
        "What should the shop be known for?",
        ["A focused menu", "A neighborhood staple", "A premium version"],
    ),
)


def make_settings(**overrides) -> Settings:
    settings = Settings()
    defaults = {
        "rate_limit_per_ip": 100_000,
        "session_query_budget": 100,
        "global_query_budget": 100_000,
        "provider": "live",
    }
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(settings, key, value)
    return settings


def scripted_fetch(method, url, headers, body, timeout):
    """One idea-specific question at a time, then a brief. No network."""
    if method == "GET" and "/v2/tags" in url:
        return 200, json.dumps(
            {
                "results": {
                    "tags": [
                        {
                            "id": "urn:tag:category:place:cafe",
                            "name": "Cafe",
                            "type": "urn:tag:category:place",
                        }
                    ]
                }
            }
        ).encode()
    if method == "GET":
        return 200, json.dumps(
            {
                "results": {
                    "entities": [
                        {
                            "name": "Corner Market",
                            "entity_id": "place-1",
                            "properties": {"short_description": "A neighborhood shop."},
                        }
                    ]
                }
            }
        ).encode()
    payload = json.loads(body)
    system = payload["messages"][0]["content"]
    user = json.loads(payload["messages"][-1]["content"])
    if "grilling a founder" in system:
        asked = user.get("answered") or []
        if len(asked) >= len(_QUESTIONS):
            content = {"questions": []}
        else:
            question_id, text, options = _QUESTIONS[len(asked)]
            content = {
                "questions": [
                    {
                        "id": question_id,
                        "text": text,
                        "options": options,
                        "recommendation": options[0],
                    }
                ]
            }
    elif "Turn Qloo" in system:
        content = {
            "body": (
                "Corner Market is a nearby match. "
                "These are aggregate taste matches, not proof of demand."
            )
        }
    else:
        idea = user.get("idea") or "your business"
        sections = [
            {"heading": item.get("question") or "Answer", "body": item.get("answer") or ""}
            for item in user.get("answers") or []
        ] or [{"heading": "Next", "body": "Open on a main street."}]
        content = {
            "title": f"Business brief — {idea}",
            "summary": f"A brief for {idea}.",
            "sections": sections,
        }
    return 200, json.dumps(
        {"choices": [{"message": {"content": json.dumps(content)}}]}
    ).encode()


def csrf_for(client, path: str = "/") -> str:
    """Read the rendered per-session CSRF token from a page response."""
    response = client.get(path)
    match = re.search(r'name="csrf" value="([a-f0-9]+)"', response.text)
    assert match, f"CSRF token not found on {path}"
    return match.group(1)


def answer_current(client) -> str:
    """Post the first option on the question currently shown."""
    page = client.get("/grill")
    token = csrf_for(client, "/grill")
    field = re.search(r'name="(a_[^"]+)" value="([^"]+)"', page.text)
    assert field, "no answer option on the grilling page"
    client.post("/grill", data={"csrf": token, field.group(1): field.group(2)})
    return field.group(2)


def walk_to_confirm(client):
    """Answer one question at a time until the confirm step."""
    for _ in range(8):
        page = client.get("/grill")
        if "Does this match what you mean?" in page.text:
            return page
        answer_current(client)
    raise AssertionError("grilling did not reach confirmation")
