"""Deterministic demo provider for the grilling pipeline.

Emulates the two pipeline steps that will later be real model calls:
1. Dynamic questioning ("grilling"): questions + shortlisted options derived
   from the prompt/category and prior answers.
2. Report writing: consumes the collected answers into a report.

Everything is deterministic and credential-free so the app and tests run
anywhere. It is NOT a substitute for a real LLM + Qloo integration.
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
from app.providers.base import Provider

_BUDGET_RE = re.compile(r"\$[\d]+(?:,\d{3})*(?:\.\d+)?[kKmM]?")

_CAFE_KEYWORDS = ("coffee", "café", "cafe", "espresso", "bakery")
_RESTAURANT_KEYWORDS = ("restaurant", "kitchen", "diner", "bistro", "pizzeria", "food hall")


def _category(idea: str) -> Optional[str]:
    text = (idea or "").lower()
    if any(k in text for k in _CAFE_KEYWORDS):
        return "cafe"
    if any(k in text for k in _RESTAURANT_KEYWORDS):
        return "restaurant"
    return None


# Question pool. ``category`` restricts to a category (None = general).
# ``skip_field`` skips the question when already stated in the opening prompt.
_POOL: List[Dict] = [
    {
        "id": "budget",
        "text": "What's your approximate start-up budget?",
        "options": ["Under $50k", "$50k–$150k", "$150k–$500k", "$500k+"],
        "free_text_hint": "Enter a specific amount if you prefer.",
        "skip_field": "budget",
        "category": None,
    },
    {
        "id": "timeline",
        "text": "When would you hope to launch?",
        "options": ["Within 6 months", "6–12 months", "Longer term / TBD"],
        "category": None,
    },
    {
        "id": "audience",
        "text": "Who is your primary customer or audience?",
        "options": ["Young professionals", "Students", "Families", "Tourists", "Local regulars"],
        "category": None,
    },
    {
        "id": "concept",
        "text": "Describe the concept you have in mind.",
        "options": ["Lean and focused", "Premium / specialty", "Family-friendly", "Local community anchor"],
        "free_text_hint": "Describe your concept in your own words.",
        "category": None,
    },
    {
        "id": "coffee_position",
        "text": "How do you want to position the coffee program?",
        "options": ["Specialty pour-over", "Espresso bar", "Bakery + coffee", "Drive-thru / quick stop"],
        "category": "cafe",
    },
    {
        "id": "cuisine",
        "text": "What style are you most drawn to?",
        "options": ["Classic & approachable", "Seasonal / modern", "Comfort food", "International"],
        "category": "restaurant",
    },
    {
        "id": "location",
        "text": "Do you have a location or region in mind?",
        "options": ["One city / metro", "Multiple cities", "Not decided yet"],
        "free_text_hint": "e.g. a specific city or state.",
        "skip_field": "region",
        "category": None,
    },
    {
        "id": "team",
        "text": "How many people will run it at launch?",
        "options": ["Just me", "2–3", "4+"],
        "category": None,
    },
    {
        "id": "open_questions",
        "text": "Anything else you'd like the plan to account for?",
        "options": ["Nothing else", "I have specifics I'll type"],
        "free_text_hint": "Add anything you'd like captured.",
        "category": None,
    },
]


def _to_question(pool_item: Dict) -> GrillQuestion:
    return GrillQuestion(
        id=pool_item["id"],
        text=pool_item["text"],
        options=[GrillOption(label=o, value=o) for o in pool_item["options"]],
        free_text_hint=pool_item.get("free_text_hint", ""),
    )


class DemoProvider(Provider):
    name = "demo"

    # --- opening prompt extraction ------------------------------------------
    def extract_opening(self, text: str) -> BusinessProfile:
        text = (text or "").strip()
        profile = BusinessProfile()
        if not text:
            return profile
        budget = _BUDGET_RE.search(text)
        if budget:
            profile.budget = budget.group(0)
        low = text.lower()
        for abbr, name in data.US_STATES.items():
            if name.lower() in low:
                profile.region = name
                break
        if not profile.region:
            for metro in data.KNOWN_METROS:
                if metro in low:
                    profile.region = metro.title()
                    break
        idea_raw = None
        for phrase in ("open a ", "launch a ", "start a "):
            if phrase in low:
                idea_raw = text.split(phrase, 1)[1]
                break
        if idea_raw is None:
            idea_raw = text
        idea_raw = re.split(r"\bin\s+[A-Z][\w-]*", idea_raw)[0].strip(" .,;:")
        profile.idea = idea_raw
        return profile

    # --- dynamic narrowing of the next question ------------------------------
    def first_question(
        self,
        profile: BusinessProfile,
        opening: str,
    ) -> GrillQuestion:
        item = self._pick(profile, [])
        return _to_question(item)

    def next_question(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> Optional[GrillQuestion]:
        item = self._pick(profile, [t.question_id for t in transcript])
        return _to_question(item) if item else None

    def _pick(self, profile: BusinessProfile, answered: List[str]) -> Optional[Dict]:
        cat = _category(profile.idea)
        for item in _POOL:
            if item["id"] in answered:
                continue
            if item["category"] is not None and item["category"] != cat:
                continue
            skip_field = item.get("skip_field")
            if skip_field and getattr(profile, skip_field, "").strip():
                continue
            return item
        return None

    # --- report writing ------------------------------------------------------
    def write_report(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> Report:
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
        summary = (
            f"A draft brief for {idea}, based on the answers collected during the "
            "planning session."
        )
        return Report(
            title=f"Business brief — {idea}",
            summary=summary,
            sections=sections,
            caveat=(
                "Draft generated by the VentureLens demo provider. Connect a real "
                "LLM and Qloo data before using it for decisions."
            ),
        )