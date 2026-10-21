"""Opening-prompt contract. Questions are not taken from a fixed checklist."""

from __future__ import annotations

from app.model import BusinessProfile, GrillTurn
from app.providers.base import Provider
from app.providers.grilling import answers_report

P = Provider()


def test_extracts_idea_budget_region():
    profile = P.extract_opening(
        "I have $250k and want to open a specialty coffee shop in Illinois."
    )
    assert profile.idea.strip() == "specialty coffee shop"
    assert profile.budget == "$250k"
    assert profile.region == "Illinois"


def test_a_city_is_the_region_when_it_is_not_a_state():
    profile = P.extract_opening("I want to open a roofing repair business in Albany")
    assert profile.region == "Albany"
    assert profile.idea.strip() == "roofing repair business"


def test_new_york_city_is_not_reduced_to_the_state():
    city = P.extract_opening("I want to start a grocery shop in New York City.")
    nyc = P.extract_opening("I want to start a grocery shop in NYC.")
    state = P.extract_opening("I want to start a grocery shop in New York.")
    assert city.region == "New York City"
    assert nyc.region == "New York City"
    assert state.region == "New York"
    assert city.idea.strip() == "grocery shop"


def test_empty_prompt_is_safe():
    assert P.extract_opening("").idea == ""


def test_a_brief_can_be_built_from_the_answers_alone():
    profile = P.extract_opening("I have $120k and want to open a coffee shop in Texas.")
    transcript = [
        GrillTurn(question_id="launch", question="Timing?", answer="Within 6 months"),
        GrillTurn(question_id="audience", question="Audience?", answer="Students"),
    ]
    report = answers_report(profile, transcript)
    assert "coffee shop" in report.title
    assert any(section.body == "Within 6 months" for section in report.sections)
    assert any(section.body == "Students" for section in report.sections)
    assert any(section.heading == "Target area" and section.body == "Texas" for section in report.sections)


def test_an_empty_transcript_still_has_a_section():
    report = answers_report(BusinessProfile(idea="bakery"), [])
    assert report.sections
    assert report.title == "Business brief — bakery"
