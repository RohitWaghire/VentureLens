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
                                "id": "urn:tag:category:place:grocery_store",
                                "name": "Grocery Store",
                                "type": "urn:tag:category:place",
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
    assert query["filter.tags"] == ["urn:tag:category:place:grocery_store"]
    assert "signal.interests.tags" not in query
    assert query["filter.location.query"] == ["New York City"]
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
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
                            "id": "urn:tag:category:place:grocery_store",
                            "name": "Grocery Store",
                            "type": "urn:tag:category:place",
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
    assert any(section.heading == "What similar places suggest" and "Corner Market" in section.body for section in report.sections)
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
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
    assert "no place affinities" in taste


def test_model_rewrites_qloo_places_without_raw_tags():
    settings = _settings()

    def fetch(method, url, headers, body, timeout):
        if method == "GET":
            return 200, json.dumps(
                {
                    "results": {
                        "tags": [
                            {
                                "id": "urn:tag:category:place:grocery_store",
                                "name": "Grocery Store",
                                "type": "urn:tag:category:place",
                            }
                        ],
                        "entities": [
                            {
                                "name": "Food Bazaar",
                                "entity_id": "place-1",
                                "tags": [{"name": "Metal cans"}, {"name": "Impulse visit"}],
                                "properties": {"short_description": "Neighborhood supermarket."},
                            }
                        ],
                    }
                }
            ).encode()
        user = json.loads(body)["messages"][-1]["content"]
        if '"places"' in user:
            return 200, json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "body": (
                                            "Food Bazaar is a neighborhood supermarket. "
                                            "Qloo is pointing at grocery stores like this, not a demand forecast."
                                        )
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode()
        return _brief()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region="New York"),
        "I want to start a grocery shop in New York.",
        [],
    )
    section = next(item for item in report.sections if item.heading == "What similar places suggest")
    assert "Food Bazaar" in section.body
    assert "neighborhood supermarket" in section.body
    assert "Metal cans" not in section.body
    assert "Impulse visit" not in section.body


def test_search_phrases_come_from_the_idea_itself():
    from app.providers.live import _search_phrases

    chocolate = _search_phrases(
        BusinessProfile(idea="boxed chocolate shop"),
        "I want a boxed chocolate shop in New Hampshire",
    )
    yoga = _search_phrases(
        BusinessProfile(idea="yoga studio"),
        "I want to open a yoga studio in Austin",
    )
    books = _search_phrases(
        BusinessProfile(idea="used bookstore"),
        "I want a used bookstore in Portland",
    )
    tea = _search_phrases(BusinessProfile(idea="tea shop"), "I want a tea shop")
    gym = _search_phrases(BusinessProfile(idea="gym"), "I want to open a gym")
    bar = _search_phrases(BusinessProfile(idea="bar"), "I want to open a bar")
    assert chocolate[0] == "chocolate"
    assert "yoga" in yoga
    assert books[0] == "bookstore"
    assert tea == ["tea"]
    assert gym == ["gym"]
    assert bar == ["bar"]
    assert "local business" not in tea + gym + bar
    canned = {"coffee shop", "chocolate shop", "grocery store", "candy store"}
    assert canned.isdisjoint(yoga)
    assert canned.isdisjoint(books)


def test_roofing_business_prefers_the_contractor():
    from app.providers.live import _best_tag

    tag = _best_tag(
        [
            (
                "roofing",
                [
                    {
                        "id": "urn:tag:category:place:roofing_supply_store",
                        "name": "Roofing supply store",
                        "type": "urn:tag:category:place",
                    },
                    {
                        "id": "urn:tag:category:place:roofing_contractor",
                        "name": "Roofing contractor",
                        "type": "urn:tag:category:place",
                    },
                ],
            )
        ]
    )
    assert tag is not None
    assert tag["id"] == "urn:tag:category:place:roofing_contractor"


def test_far_places_are_left_out_of_a_city_brief():
    settings = _settings()
    calls = []

    def fetch(method, url, headers, body, timeout):
        if method != "GET":
            return _brief()
        calls.append(url)
        query = parse_qs(urlparse(url).query)
        if "/v2/tags" in url:
            return 200, json.dumps(
                {
                    "results": {
                        "tags": [
                            {
                                "id": "urn:tag:category:place:roofing_contractor",
                                "name": "Roofing contractor",
                                "type": "urn:tag:category:place",
                            }
                        ]
                    }
                }
            ).encode()
        location = query.get("filter.location.query", [""])[0]
        if location == "Albany":
            return 200, json.dumps(
                {
                    "query": {
                        "localities": {
                            "filter": [
                                {
                                    "name": "Albany",
                                    "disambiguation": "Albany, Albany County, New York, United States",
                                    "location": {"lat": 42.65, "lon": -73.75},
                                }
                            ]
                        }
                    },
                    "results": {"entities": []},
                }
            ).encode()
        return 200, json.dumps(
            {
                "results": {
                    "entities": [
                        {
                            "name": "Four Winds Chimney",
                            "entity_id": "near",
                            "disambiguation": "831 NY-67 Ballston Spa, NY 12020",
                            "location": {"lat": 42.9, "lon": -73.85},
                            "properties": {"short_description": "Chimney service in Ballston Spa."},
                        },
                        {
                            "name": "The Home Depot",
                            "entity_id": "far",
                            "disambiguation": "4625 Rue Saint-Antoine O Montreal, Quebec H4C 1E2 Canada",
                            "location": {"lat": 45.5, "lon": -73.57},
                            "properties": {"short_description": "Home improvement store in Montreal."},
                        },
                    ]
                }
            }
        ).encode()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="roofing repair business", region="Albany"),
        "I want to open a roofing repair business in Albany",
        [],
    )
    insights = [url for url in calls if "/v2/insights" in url]
    assert [parse_qs(urlparse(url).query)["filter.location.query"][0] for url in insights] == [
        "Albany",
        "New York",
    ]
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
    assert "Four Winds Chimney" in taste
    assert "Home Depot" not in taste
    assert "Montreal" not in taste
    assert "is described as" not in taste


def test_new_york_city_keeps_nearby_places_and_drops_far_ones():
    from app.providers.live import _miles

    settings = _settings()
    calls = []
    city = (40.7128, -74.0060)
    eataly = (40.7420, -73.9890)
    albany = (42.6526, -73.7562)
    assert _miles(*city, *eataly) < 40
    assert _miles(*city, *albany) > 40

    def fetch(method, url, headers, body, timeout):
        if method != "GET":
            return _brief()
        calls.append((url, timeout))
        if "/v2/tags" in url:
            return 200, _grocery_tags()
        return 200, json.dumps(
            {
                "query": {
                    "localities": {
                        "filter": [
                            {
                                "name": "New York City",
                                "disambiguation": "New York City, New York County, New York, United States",
                                "location": {"lat": city[0], "lon": city[1]},
                            }
                        ]
                    }
                },
                "results": {
                    "entities": [
                        _place("Eataly", "near", eataly, "Italian market in New York City."),
                        _place("Albany Market", "far", albany, "Grocery in Albany."),
                    ]
                },
            }
        ).encode()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region=""),
        "I want to start a grocery shop in NYC.",
        [],
    )
    insights = [url for url, _timeout in calls if "/v2/insights" in url]
    assert [parse_qs(urlparse(url).query)["filter.location.query"][0] for url in insights] == [
        "New York City"
    ]
    qloo_timeouts = {timeout for url, timeout in calls if "/v2/" in url}
    assert qloo_timeouts == {settings.qloo_timeout_seconds}
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
    assert "Eataly" in taste
    assert "Albany Market" not in taste


def test_state_resolution_keeps_places_far_from_the_centroid():
    from app.providers.live import _is_city, _miles, _resolved_locality

    settings = _settings()
    settings.qloo_timeout_seconds = 17
    center = (42.9538, -75.5268)
    eataly = (40.7420, -73.9890)
    assert _miles(*center, *eataly) > 40
    payload = {
        "query": {
            "localities": {
                "filter": [
                    {
                        "name": "New York",
                        "disambiguation": "New York, United States",
                        "location": {"lat": center[0], "lon": center[1]},
                    }
                ]
            }
        },
        "results": {
            "entities": [
                _place("Eataly", "nyc", eataly, "Italian market in New York City."),
            ]
        },
    }
    resolved = _resolved_locality(payload)
    assert resolved["state"] == ""
    assert _is_city(resolved) is False

    def fetch(method, url, headers, body, timeout):
        if method != "GET":
            return _brief()
        assert timeout == 17
        if "/v2/tags" in url:
            return 200, _grocery_tags()
        return 200, json.dumps(payload).encode()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="grocery shop", region="New York"),
        "I want to start a grocery shop in New York.",
        [],
    )
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
    assert "Eataly" in taste


def test_tag_lookup_errors_are_not_empty_place_lists():
    settings = _settings()

    def fetch_status(status):
        def fetch(method, url, headers, body, timeout):
            if "/v2/tags" in url:
                return status, b"{}"
            return _brief()

        return fetch

    for status in (401, 429):
        try:
            LiveProvider(settings, fetch_status(status)).write_report(
                BusinessProfile(idea="grocery shop", region="New York"),
                "I want to start a grocery shop in New York.",
                [],
            )
        except ProviderError as exc:
            text = str(exc).lower()
            if status == 401:
                assert "refused" in text
            else:
                assert "rate limit" in text
            continue
        raise AssertionError(status)


def test_chocolate_shop_prefers_the_shop_category():
    from app.providers.live import _best_tag

    tag = _best_tag(
        [
            (
                "chocolate",
                [
                    {
                        "id": "urn:tag:category:place:chocolate",
                        "name": "Chocolate",
                        "type": "urn:tag:category:place",
                    },
                    {
                        "id": "urn:tag:category:place:chocolate_shop",
                        "name": "Chocolate shop",
                        "type": "urn:tag:category:place",
                    },
                    {
                        "id": "urn:tag:category:place:chocolate_manufacturer",
                        "name": "Chocolate manufacturer",
                        "type": "urn:tag:category:place",
                    },
                ],
            )
        ]
    )
    assert tag is not None
    assert tag["id"] == "urn:tag:category:place:chocolate_shop"


def test_empty_local_results_stay_in_the_region():
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
                                "id": "urn:tag:category:place:chocolate",
                                "name": "Chocolate",
                                "type": "urn:tag:category:place",
                            },
                            {
                                "id": "urn:tag:category:place:chocolate_shop",
                                "name": "Chocolate shop",
                                "type": "urn:tag:category:place",
                            },
                        ]
                    }
                }
            ).encode()
        query = parse_qs(urlparse(url).query)
        tag = query.get("filter.tags", [""])[0]
        if tag.endswith(":chocolate_shop"):
            return 200, b'{"results":{"entities":[]}}'
        return 200, json.dumps(
            {
                "results": {
                    "entities": [
                        {
                            "name": "Granite State Candy Shoppe",
                            "entity_id": "place-nh",
                            "properties": {"short_description": "Artisanal chocolate shop in Concord."},
                        }
                    ]
                }
            }
        ).encode()

    report = LiveProvider(settings, fetch).write_report(
        BusinessProfile(idea="chocolate shop", region="New Hampshire"),
        "I want to open a chocolate shop in New Hampshire.",
        [],
    )
    insights = [url for url in calls if "/v2/insights" in url]
    assert insights
    for url in insights:
        assert parse_qs(urlparse(url).query)["filter.location.query"] == ["New Hampshire"]
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
    assert "Granite State Candy Shoppe" in taste


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
    taste = next(section.body for section in report.sections if section.heading == "What similar places suggest")
    assert "no place affinities" in taste


def test_genre_tag_is_not_a_place_category_filter():
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
                            },
                            {
                                "id": "urn:tag:category:place:restaurant",
                                "name": "Restaurant",
                                "type": "urn:tag:category:place",
                            },
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
    assert query["filter.tags"] == ["urn:tag:category:place:restaurant"]
    assert "signal.interests.tags" not in query


def test_interest_signal_request_is_rejected():
    from app.providers.base import ProviderError

    settings = _settings()
    provider = LiveProvider(settings, lambda *args, **kwargs: (200, b"{}"))
    for params in (
        {
            "filter.type": "urn:entity:place",
            "signal.interests.tags": "urn:tag:category:place:grocery_store",
            "filter.location.query": "New York",
        },
        {"filter.type": "urn:entity:place", "filter.location.query": "New York"},
    ):
        try:
            provider._qloo_get("/v2/insights", params)
        except ProviderError:
            continue
        raise AssertionError(params)


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


def _grocery_tags() -> bytes:
    return json.dumps(
        {
            "results": {
                "tags": [
                    {
                        "id": "urn:tag:category:place:grocery_store",
                        "name": "Grocery Store",
                        "type": "urn:tag:category:place",
                    }
                ]
            }
        }
    ).encode()


def _place(name: str, entity_id: str, point: tuple[float, float], detail: str) -> dict:
    return {
        "name": name,
        "entity_id": entity_id,
        "location": {"lat": point[0], "lon": point[1]},
        "properties": {"short_description": detail},
    }


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
