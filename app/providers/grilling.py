"""Opening-prompt parse shared by the live provider.

Questions come from the model. This module only reads the idea, budget, and
place out of the opening prompt, and can turn collected answers into a brief
when the model does not write one.
"""

from __future__ import annotations

import re
from typing import List

from app.model import BusinessProfile, GrillTurn, Report, ReportSection
from app.providers import data

_BUDGET_RE = re.compile(r"\$[\d]+(?:,\d{3})*(?:\.\d+)?[kKmM]?")


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
