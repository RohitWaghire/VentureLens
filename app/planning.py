"""Planning session.

Routes learn three outcomes: show the next question, show the report, or stop
because the budget or a live provider call failed. Question order, the server
question text, and when a provider call costs a budget unit sit here.
"""

from __future__ import annotations

from app.model import BusinessProfile, GrillTurn
from app.providers.base import Provider, ProviderError
from app.security import QueryBudget
from app.sessions import Session

QUESTION = "question"
REPORT = "report"
BUDGET = "budget"
UNAVAILABLE = "unavailable"


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

    def current_question(self, session: Session):
        profile = session.profile or BusinessProfile()
        return self.provider.question(profile, session.transcript)

    def answer(self, session: Session, answer: str, finish: bool) -> str:
        """Record the server's current question, or finish the brief.

        The posted question text is ignored. The transcript stores the question
        this session actually asked.
        """
        if not finish and answer:
            question = self.current_question(session)
            if question is None:
                return self.ensure_report(session)
            session.transcript.append(
                GrillTurn(question_id=question.id, question=question.text, answer=answer)
            )
            if self.current_question(session) is not None:
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
        except ProviderError:
            return UNAVAILABLE
        return REPORT
