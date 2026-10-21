"""How a planning session moves from one answer to the brief.

The provider here is a stand-in with a fixed sequence. It is not a demo mode.
"""

from __future__ import annotations

from app.model import BusinessProfile, GrillOption, GrillQuestion, GrillTurn, Report
from app.planning import CONFIRM, QUESTION, REPORT, Planner
from app.providers.base import Provider
from app.providers.grilling import answers_report
from app.security import QueryBudget
from app.sessions import Session


class _Sequence(Provider):
    def frontier(self, profile: BusinessProfile, transcript: list[GrillTurn]) -> list[GrillQuestion]:
        if len(transcript) >= 2:
            return []
        number = len(transcript) + 1
        return [
            GrillQuestion(
                id=f"q{number}",
                text=f"Question {number} for {profile.idea}?",
                options=[GrillOption(label="Yes", value="Yes")],
                recommendation="Yes",
            )
        ]

    def write_report(self, profile, opening, transcript) -> Report:
        return answers_report(profile, transcript)


def _planner() -> Planner:
    return Planner(_Sequence(), QueryBudget(30, 100))


def _session() -> Session:
    return Session("session", 3600)


def test_starting_stores_the_city_and_does_not_write_the_brief():
    planner = _planner()
    session = _session()
    assert planner.start(session, "I want to start a grocery shop in NYC.") == QUESTION
    assert session.profile.region == "New York City"
    assert session.profile.idea.strip() == "grocery shop"
    assert session.report is None
    assert planner.current_question(session) is not None


def test_one_answer_leaves_the_rest_of_the_interview_open():
    planner = _planner()
    session = _session()
    planner.start(session, "I want to open a coffee shop.")
    first = planner.current_question(session)
    assert planner.record(session, {first.id: first.options[0].value}) == QUESTION
    nxt = planner.current_question(session)
    assert nxt is not None
    assert nxt.id != first.id
    assert planner.confirm(session) == QUESTION
    assert session.report is None


def test_confirm_writes_the_brief_only_when_every_question_is_answered():
    planner = _planner()
    session = _session()
    planner.start(session, "I want to open a coffee shop in Illinois.")
    seen = []
    while planner.current_question(session) is not None:
        question = planner.current_question(session)
        assert question.id not in seen
        seen.append(question.id)
        kind = planner.record(session, {question.id: question.options[0].value})
        assert kind in {QUESTION, CONFIRM}
        assert len(seen) < 20
    assert seen
    assert planner.confirm(session) == REPORT
    assert session.report is not None
    assert "coffee shop" in session.report.title
