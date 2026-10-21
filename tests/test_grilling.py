"""How the opening prompt is read. Questions are not chosen from a fixed list."""

from __future__ import annotations

from app.providers.base import Provider

P = Provider()


def test_a_grocery_shop_in_nyc_keeps_the_city():
    profile = P.extract_opening("I want to start a grocery shop in NYC.")
    assert profile.idea.strip() == "grocery shop"
    assert profile.region == "New York City"


def test_a_stated_budget_and_state_are_kept():
    profile = P.extract_opening("I have $250k and want to open a coffee shop in Illinois.")
    assert profile.idea.strip() == "coffee shop"
    assert profile.budget == "$250k"
    assert profile.region == "Illinois"


def test_new_york_city_is_not_reduced_to_the_state():
    city = P.extract_opening("I want to start a grocery shop in New York City.")
    state = P.extract_opening("I want to start a grocery shop in New York.")
    assert city.region == "New York City"
    assert state.region == "New York"
    assert city.idea.strip() == "grocery shop"


def test_a_city_that_is_not_a_state_stays_the_region():
    profile = P.extract_opening("I want to open a roofing repair business in Albany")
    assert profile.region == "Albany"
    assert profile.idea.strip() == "roofing repair business"


def test_an_empty_prompt_is_safe():
    assert P.extract_opening("").idea == ""
