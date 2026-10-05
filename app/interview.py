"""Adaptive interview state machine.

The one-question-at-a-time interview is implemented as explicit application
state transitions. Business idea and U.S. state/region are required; every other
question may be skipped and becomes a labeled assumption downstream.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Question(BaseModel):
    field: str
    text: str
    required: bool = False
    placeholder: str = ""
    skip_label: str = ""


# The adaptive sequence. Order is fixed for the MVP; the model may tune wording
# via its adapter seam, but required gates (idea, region) are enforced by code.
QUESTION_SEQUENCE: List[Question] = [
    Question(
        field="idea",
        text="What business idea are you exploring? Include your concept and, if you have a fuller opening message, your budget and target area.",
        required=True,
        placeholder="e.g. I have $250k and want to open a specialty coffee shop in Illinois",
    ),
    Question(
        field="region",
        text="Which U.S. state or metro region are you considering?",
        required=True,
        placeholder="e.g. Illinois",
    ),
    Question(
        field="budget",
        text="What is your approximate start-up budget?",
        placeholder="e.g. $250k",
        skip_label="Skip budget (leave unknown)",
    ),
    Question(
        field="audience",
        text="Who is your primary target customer or audience?",
        placeholder="e.g. young professionals and students",
        skip_label="Skip target audience",
    ),
    Question(
        field="concept",
        text="Describe your concept and how it should be positioned.",
        placeholder="e.g. specialty pour-over café, counter service",
        skip_label="Skip concept/positioning",
    ),
    Question(
        field="price",
        text="What price point are you targeting?",
        placeholder="e.g. $5–6 per drink",
        skip_label="Skip price point",
    ),
    Question(
        field="footprint",
        text="What type of footprint are you considering?",
        placeholder="e.g. small counter-service café, no seating",
        skip_label="Skip footprint",
    ),
    Question(
        field="competitors",
        text="Who are your main competitors in the area?",
        placeholder="e.g. other local specialty roasters",
        skip_label="Skip competitors",
    ),
    Question(
        field="growth",
        text="What are your growth goals for the first 1–2 years?",
        placeholder="e.g. open a single location, then expand",
        skip_label="Skip growth goals",
    ),
]

# Canonical mapping of a profile field to its Question entry.
FIELD_INDEX = {q.field: q for q in QUESTION_SEQUENCE}


class InterviewState(BaseModel):
    """Tracks which questions have been answered or skipped."""

    answered: Dict[str, str] = Field(default_factory=dict)  # field -> raw answer
    skipped: List[str] = Field(default_factory=list)
    current_field: Optional[str] = QUESTION_SEQUENCE[0].field

    def next_question(self) -> Optional[Question]:
        for q in QUESTION_SEQUENCE:
            if q.field not in self.answered and q.field not in self.skipped:
                self.current_field = q.field
                return q
        self.current_field = None
        return None

    def record_answer(self, field: str, value: str) -> bool:
        """Record an answer. Required fields must be non-empty."""
        q = FIELD_INDEX.get(field)
        if q is None:
            return False
        value = (value or "").strip()
        if q.required and not value:
            return False
        self.answered[field] = value
        self.skipped = [f for f in self.skipped if f != field]
        self.next_question()
        return True

    def record_skip(self, field: str) -> bool:
        """Skip a non-required question; required questions cannot be skipped."""
        q = FIELD_INDEX.get(field)
        if q is None or q.required:
            return False
        if field not in self.skipped:
            self.skipped.append(field)
        self.next_question()
        return True

    def answered_fields(self) -> List[str]:
        return list(self.answered.keys())


def profile_from_interview(interview: InterviewState) -> Dict[str, str]:
    """Extract the stored raw answers into a profile dict (unsanitized)."""
    return dict(interview.answered)