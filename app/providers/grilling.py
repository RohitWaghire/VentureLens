"""Shared grilling behavior for every provider adapter.

The question pool and the opening-prompt parse are the same whoever writes the
report. Adapters differ in ``write_report``, not in which question comes next.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app.model import (
    BusinessProfile,
    GrillOption,
    GrillQuestion,
    GrillTurn,
    Report,
    ReportSection,
)
from app.providers import data

_BUDGET_RE = re.compile(r"\$[\d]+(?:,\d{3})*(?:\.\d+)?[kKmM]?")

_CAFE_KEYWORDS = ("coffee", "café", "cafe", "espresso", "bakery")
_RESTAURANT_KEYWORDS = ("restaurant", "kitchen", "diner", "bistro", "pizzeria", "food hall")


_GROCERY_KEYWORDS = ("grocery", "bodega", "supermarket", "greengrocer", "food shop")


def _category(idea: str) -> Optional[str]:
    text = (idea or "").lower()
    if any(k in text for k in _GROCERY_KEYWORDS):
        return "grocery"
    if any(k in text for k in _CAFE_KEYWORDS):
        return "cafe"
    if any(k in text for k in _RESTAURANT_KEYWORDS):
        return "restaurant"
    return None


# ``category`` restricts to a category (None = general).
# ``skip_field`` skips the question when the opening prompt already stated it.
_POOL: List[Dict] = [
    {
        "id": "budget",
        "text": "What's your approximate start-up budget?",
        "options": ["Under $50k", "$50k–$150k", "$150k–$500k", "$500k+"],
        "free_text_hint": "Enter a specific amount if you prefer.",
        "skip_field": "budget",
        "category": None,
        "depends_on": [],
        "recommendation": "$50k–$150k",
    },
    {
        "id": "timeline",
        "text": "When would you hope to launch?",
        "options": ["Within 6 months", "6–12 months", "Longer term / TBD"],
        "category": None,
        "depends_on": [],
        "recommendation": "6–12 months",
    },
    {
        "id": "audience",
        "text": "Who is your primary customer or audience?",
        "options": ["Young professionals", "Students", "Families", "Tourists", "Local regulars"],
        "category": None,
        "depends_on": [],
        "recommendation": "Local regulars",
    },
    {
        "id": "concept",
        "text": "Describe the concept you have in mind.",
        "options": ["Lean and focused", "Premium / specialty", "Family-friendly", "Local community anchor"],
        "free_text_hint": "Describe your concept in your own words.",
        "category": None,
        "depends_on": [],
        "recommendation": "Lean and focused",
    },
    {
        "id": "coffee_position",
        "text": "How do you want to position the coffee program?",
        "options": ["Specialty pour-over", "Espresso bar", "Bakery + coffee", "Drive-thru / quick stop"],
        "category": "cafe",
        "depends_on": ["concept"],
        "recommendation": "Espresso bar",
    },
    {
        "id": "cuisine",
        "text": "What style are you most drawn to?",
        "options": ["Classic & approachable", "Seasonal / modern", "Comfort food", "International"],
        "category": "restaurant",
        "depends_on": ["concept"],
        "recommendation": "Classic & approachable",
    },
    {
        "id": "grocery_format",
        "text": "What kind of grocery shop is this?",
        "options": ["Neighborhood market", "Specialty / gourmet", "Convenience", "Full supermarket"],
        "category": "grocery",
        "depends_on": ["concept"],
        "recommendation": "Neighborhood market",
    },
    {
        "id": "assortment",
        "text": "What should the shop be known for?",
        "options": ["Fresh produce", "Prepared food", "Pantry staples", "A tight specialty selection"],
        "category": "grocery",
        "depends_on": ["grocery_format"],
        "recommendation": "Fresh produce",
    },
    {
        "id": "location",
        "text": "Do you have a location or region in mind?",
        "options": ["One city / metro", "Multiple cities", "Not decided yet"],
        "free_text_hint": "e.g. a specific city or state.",
        "skip_field": "region",
        "category": None,
        "depends_on": [],
        "recommendation": "One city / metro",
    },
    {
        "id": "team",
        "text": "How many people will run it at launch?",
        "options": ["Just me", "2–3", "4+"],
        "category": None,
        "depends_on": [],
        "recommendation": "2–3",
    },
    {
        "id": "open_questions",
        "text": "Anything else you'd like the plan to account for?",
        "options": ["Nothing else", "I have specifics I'll type"],
        "free_text_hint": "Add anything you'd like captured.",
        "category": None,
        "depends_on": ["timeline", "audience", "concept", "team"],
        "recommendation": "Nothing else",
    },
]


def _to_question(pool_item: Dict, profile: BusinessProfile) -> GrillQuestion:
    recommendation = pool_item.get("recommendation", "")
    if pool_item["id"] == "coffee_position" and "specialty" in (profile.idea or "").lower():
        recommendation = "Specialty pour-over"
    return GrillQuestion(
        id=pool_item["id"],
        text=pool_item["text"],
        options=[GrillOption(label=o, value=o) for o in pool_item["options"]],
        free_text_hint=pool_item.get("free_text_hint", ""),
        recommendation=recommendation,
    )


def extract_opening(text: str) -> BusinessProfile:
    """Pull idea, budget, and region out of the opening prompt."""
    text = (text or "").strip()
    profile = BusinessProfile()
    if not text:
        return profile
    budget = _BUDGET_RE.search(text)
    if budget:
        profile.budget = budget.group(0)
    low = text.lower()
    place = _place_after_in(text)
    if place.lower() in {"nyc", "new york city"}:
        place = "New York City"
    elif not place and (re.search(r"\bnyc\b", low) or "new york city" in low):
        place = "New York City"
    # "New York" is inside "New York City". Qloo reads the shorter name as the state.
    state = "" if place.lower() == "new york city" else _named_state(low)
    if not state and not place:
        for metro in data.KNOWN_METROS:
            if metro in low:
                state = metro.title()
                break
    if place and state and place.lower() != state.lower():
        profile.region = f"{place}, {state}"
    elif state:
        profile.region = state
    elif place:
        profile.region = place
    idea_raw = None
    for phrase in ("open a ", "launch a ", "start a "):
        if phrase in low:
            idea_raw = text.split(phrase, 1)[1]
            break
    if idea_raw is None:
        idea_raw = text
    idea_raw = re.split(r"\bin\s+[A-Za-z]", idea_raw, maxsplit=1)[0].strip(" .,;:")
    profile.idea = idea_raw
    return profile


def _named_state(low: str) -> str:
    """A state named in the prompt. New York City is not that state."""
    scrubbed = re.sub(r"\bnyc\b", " ", low)
    scrubbed = scrubbed.replace("new york city", " ")
    for _abbr, name in data.US_STATES.items():
        if name.lower() in scrubbed:
            return name
    return ""


_NOT_A_PLACE = {
    "a", "an", "the", "addition", "general", "mind", "store", "shop", "house",
    "person", "order", "front", "fact", "place", "business", "my", "our",
    "this", "that", "your", "town", "home", "it",
}


def _place_after_in(text: str) -> str:
    """The capitalized place in 'in Albany', when the prompt names one."""
    match = re.search(
        r"\bin\s+([A-Za-z][\w.'-]*(?:\s+[A-Za-z][\w.'-]*){0,2})",
        text or "",
    )
    if not match:
        return ""
    kept = []
    for raw in match.group(1).split():
        word = raw.strip(".,;:")
        if not word or word.lower() in _NOT_A_PLACE:
            break
        kept.append(word if word.isupper() and len(word) <= 3 else word.capitalize())
    return " ".join(kept)


def _applicable(profile: BusinessProfile) -> List[Dict]:
    cat = _category(profile.idea)
    return [
        item for item in _POOL
        if item["category"] is None or item["category"] == cat
    ]


def frontier(profile: BusinessProfile, transcript: List[GrillTurn]) -> List[GrillQuestion]:
    """Questions whose prerequisites are already settled.

    A round asks this whole list. A question that still depends on an open
    answer waits for a later round.
    """
    answered = {turn.question_id for turn in transcript}
    applicable = _applicable(profile)
    applicable_ids = {item["id"] for item in applicable}
    ready = []
    for item in applicable:
        if item["id"] in answered:
            continue
        skip_field = item.get("skip_field")
        if skip_field and getattr(profile, skip_field, "").strip():
            continue
        deps = [dep for dep in item.get("depends_on", []) if dep in applicable_ids]
        if any(dep not in answered for dep in deps):
            continue
        ready.append(_to_question(item, profile))
    return ready


def answers_report(profile: BusinessProfile, transcript: List[GrillTurn]) -> Report:
    """A brief built only from the collected answers."""
    idea = profile.idea or "your business"
    sections = [
        ReportSection(heading=turn.question, body=turn.answer)
        for turn in transcript
    ]
    if not sections:
        sections.append(
            ReportSection(
                heading="Where to go next",
                body="Add a few answers during grilling so the report can reflect your plans.",
            )
        )
    if profile.region:
        sections.append(ReportSection(heading="Target area", body=profile.region))
    if profile.budget:
        sections.append(ReportSection(heading="Stated budget", body=profile.budget))
    return Report(
        title=f"Business brief — {idea}",
        summary=(
            f"A draft brief for {idea}, based on the answers collected during the "
            "planning session."
        ),
        sections=sections,
    )
