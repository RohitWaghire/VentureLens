"""How the live provider should grill: questions from this idea, not a shared list.

Qloo is for the brief. Choosing the next question talks only to the model.
A model failure is not filled in with the demo checklist.
"""

from __future__ import annotations

import json

from app.config import Settings
from app.model import BusinessProfile, GrillTurn
from app.providers.base import Provider, ProviderError
from app.providers.live import LiveProvider

_CHECKLIST = (
    "What's your approximate start-up budget?",
    "When would you hope to launch?",
    "Who is your primary customer or audience?",
    "Describe the concept you have in mind.",
    "How many people will run it at launch?",
)


def _settings() -> Settings:
    settings = Settings()
    settings.provider = "live"
    settings.qloo_api_key = "qloo-test"
    settings.llm_api_key = "llm-test"
    settings.llm_model = "gpt-6-luna"
    settings.llm_provider = "openai"
    return settings


def _model_questions(text: str, options: list[str]) -> tuple[int, bytes]:
    payload = {
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
    return 200, json.dumps(payload).encode()


def test_a_missing_city_is_asked_before_the_model():
    calls = []

    def fetch(method, url, headers, body, timeout):
        calls.append(url)
        return _model_questions("What should the shop sell?", ["Produce", "Pantry goods", "Both"])

    questions = LiveProvider(_settings(), fetch).frontier(
        BusinessProfile(idea="dropshipping store"),
        [],
    )
    assert questions[0].text == "Which U.S. city should this be in?"
    assert calls == []


def test_a_city_answer_is_sent_to_qloo():
    from app.providers.live import _location

    place = _location(
        BusinessProfile(idea="dropshipping store"),
        [
            GrillTurn(
                question_id="place",
                question="Which U.S. city should this be in?",
                answer="Austin",
            )
        ],
    )
    assert place == "Austin"


def test_without_a_city_the_brief_says_qloo_was_not_asked():
    calls = []

    def fetch(method, url, headers, body, timeout):
        calls.append(url)
        if method == "GET":
            return 200, b'{"results":{"entities":[]}}'
        return 200, json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "Brief",
                                    "summary": "A dropshipping brief.",
                                    "sections": [{"heading": "Next", "body": "Pick a city."}],
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()

    report = LiveProvider(_settings(), fetch).write_report(
        BusinessProfile(idea="dropshipping store"),
        "I want to start a dropshipping store.",
        [GrillTurn(question_id="focus", question="What will you sell?", answer="Home goods")],
    )
    section = next(item for item in report.sections if item.heading == "What similar places suggest")
    assert "no place affinities" not in section.body
    assert "city" in section.body.lower()
    assert not any("/v2/insights" in url for url in calls)


def test_a_grocery_shop_and_a_yoga_studio_are_not_asked_the_same_question():
    def fetch(method, url, headers, body, timeout):
        user = json.loads(body)["messages"][1]["content"]
        if "yoga" in user:
            return _model_questions("What kind of classes should the studio lead with?", ["Vinyasa", "Yin", "Hot yoga"])
        return _model_questions("What should fill most of the shelves?", ["Produce", "Packaged staples", "Prepared food"])

    provider = LiveProvider(_settings(), fetch)
    yoga = provider.frontier(BusinessProfile(idea="yoga studio", region="Austin"), [])
    grocery = provider.frontier(BusinessProfile(idea="grocery shop", region="New York City"), [])
    assert yoga[0].text != grocery[0].text
    assert "classes" in yoga[0].text
    assert "shelves" in grocery[0].text


def test_the_question_request_keeps_the_city_the_founder_named():
    profile = Provider().extract_opening("I want to start a grocery shop in NYC.")
    captured = {}

    def fetch(method, url, headers, body, timeout):
        captured["url"] = url
        captured["body"] = json.loads(body)
        return _model_questions("What should the shop be known for?", ["Produce", "Prepared food", "A small specialty set"])

    LiveProvider(_settings(), fetch).frontier(profile, [])
    assert "/v2/" not in captured["url"]
    user = captured["body"]["messages"][-1]["content"]
    assert "grocery shop" in user
    assert "New York City" in user


def test_choosing_a_question_does_not_call_qloo():
    calls = []

    def fetch(method, url, headers, body, timeout):
        calls.append(url)
        return _model_questions("What should the shop be known for?", ["Produce", "Prepared food", "A small specialty set"])

    LiveProvider(_settings(), fetch).frontier(
        BusinessProfile(idea="grocery shop", region="New York City"),
        [],
    )
    assert calls
    assert all("/v2/" not in url for url in calls)


def test_a_model_failure_is_not_replaced_by_the_shared_checklist():
    def fetch(method, url, headers, body, timeout):
        raise ProviderError("The taste service or the model could not be reached.")

    provider = LiveProvider(_settings(), fetch)
    try:
        questions = provider.frontier(BusinessProfile(idea="yoga studio", region="Austin"), [])
    except ProviderError:
        return
    texts = [question.text for question in questions]
    assert not any(text in texts for text in _CHECKLIST)


def test_an_empty_opening_reply_is_not_replaced_by_the_shared_checklist():
    def fetch(method, url, headers, body, timeout):
        return 200, json.dumps(
            {"choices": [{"message": {"content": json.dumps({"questions": []})}}]}
        ).encode()

    provider = LiveProvider(_settings(), fetch)
    try:
        questions = provider.frontier(BusinessProfile(idea="tea shop", region="Austin"), [])
    except ProviderError:
        return
    texts = [question.text for question in questions]
    assert not any(text in texts for text in _CHECKLIST)


def test_after_an_answer_an_empty_model_list_ends_the_interview():
    def fetch(method, url, headers, body, timeout):
        return 200, json.dumps(
            {"choices": [{"message": {"content": json.dumps({"questions": []})}}]}
        ).encode()

    questions = LiveProvider(_settings(), fetch).frontier(
        BusinessProfile(idea="grocery shop", region="New York City"),
        [GrillTurn(question_id="shelves", question="What should fill most of the shelves?", answer="Produce")],
    )
    assert questions == []


def test_a_question_already_answered_is_not_asked_again():
    asked = "What should fill most of the shelves?"

    def fetch(method, url, headers, body, timeout):
        return _model_questions(asked, ["Produce", "Packaged staples", "Prepared food"])

    questions = LiveProvider(_settings(), fetch).frontier(
        BusinessProfile(idea="grocery shop", region="New York City"),
        [GrillTurn(question_id="shelves", question=asked, answer="Produce")],
    )
    assert all(question.text != asked for question in questions)


def test_the_recommendation_is_one_of_the_options():
    def fetch(method, url, headers, body, timeout):
        return 200, json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "questions": [
                                        {
                                            "id": "shelves",
                                            "text": "What should fill most of the shelves?",
                                            "options": ["Produce", "Packaged staples"],
                                            "recommendation": "Something else",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            }
        ).encode()

    questions = LiveProvider(_settings(), fetch).frontier(
        BusinessProfile(idea="grocery shop", region="New York City"),
        [],
    )
    assert questions[0].recommendation == "Produce"
