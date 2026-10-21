"""Planning session.

A round asks every question whose prerequisites are already settled. The
report waits until that tree is empty and the user confirms the understanding.
"""

from __future__ import annotations

import logging

from app.model import BusinessProfile, GrillTurn
from app.providers.base import Provider, ProviderError
from app.security import QueryBudget
from app.sessions import Session

QUESTION = "question"
CONFIRM = "confirm"
REPORT = "report"
BUDGET = "budget"
UNAVAILABLE = "unavailable"

log = logging.getLogger(__name__)


class Planner:
    def __init__(self, provider: Provider, budget: QueryBudget) -> None:
        self.provider = provider
        self.budget = budget

    def start(self, session: Session, prompt: str) -> str:
        """Store the opening prompt. Costs one research unit."""
        if not self.budget.register_spend(session, 1):
            return BUDGET
        session.opening = prompt
        session.profile = self.provider.extract_opening(prompt)
        session.transcript = []
        session.report = None
        return QUESTION

    def frontier(self, session: Session):
        profile = session.profile or BusinessProfile()
        return self.provider.frontier(profile, session.transcript)

    def current_question(self, session: Session):
        ready = self.frontier(session)
        return ready[0] if ready else None

    def record(self, session: Session, answers: dict[str, str]) -> str:
        """Store the answer and return. The next question is chosen on the following page."""
        by_id = {question.id: question for question in self.frontier(session)}
        for question_id, text in answers.items():
            text = (text or "").strip()
            question = by_id.get(question_id)
            if not text or question is None:
                continue
            session.transcript.append(
                GrillTurn(question_id=question.id, question=question.text, answer=text)
            )
        return QUESTION

    def confirm(self, session: Session) -> str:
        """Write the brief only after the tree is settled."""
        if self.frontier(session):
            return QUESTION
        return self.ensure_report(session)

    def ensure_report(self, session: Session) -> str:
        """Build the report once. Costs one research unit."""
        if session.report is not None:
            return REPORT
        if not self.budget.register_spend(session, 1):
            return BUDGET
        try:
            session.report = self.provider.write_report(
                session.profile or BusinessProfile(),
                session.opening,
                session.transcript,
            )
        except ProviderError as exc:
            log.warning("report provider failed: %s", exc)
            return UNAVAILABLE
        return REPORT
