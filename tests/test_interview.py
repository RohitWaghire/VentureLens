"""Interview state machine behavior."""

from __future__ import annotations

from app.interview import InterviewState, QUESTION_SEQUENCE
from app.model import BusinessProfile


class TestRequiredGates:
    def test_required_questions_cannot_be_skipped(self):
        inter = InterviewState()
        first = inter.next_question()
        assert first.field == "idea"
        assert first.required
        assert inter.record_skip(first.field) is False

    def test_required_question_requires_value(self):
        inter = InterviewState()
        q = inter.next_question()
        assert inter.record_answer(q.field, "   ") is False

    def test_profile_required_complete_gate(self):
        incomplete = BusinessProfile(idea="coffee shop", region="")
        assert incomplete.required_complete is False
        complete = BusinessProfile(idea="coffee shop", region="Illinois")
        assert complete.required_complete is True


class TestAdvancement:
    def test_optional_skip_advances_without_blocking(self):
        inter = InterviewState()
        q = inter.next_question()  # idea (required)
        inter.record_answer(q.field, "specialty coffee shop")
        # region is also required; move through optional fields after region.
        region = inter.next_question()
        assert region.field == "region"
        inter.record_answer(region.field, "Illinois")
        optional = inter.next_question()
        assert optional.required is False
        assert inter.record_skip(optional.field) is True
        assert optional.field not in inter.answered

    def test_full_interview_reaches_summary(self):
        inter = InterviewState()
        while True:
            q = inter.next_question()
            if q is None:
                break
            if q.required:
                inter.record_answer(q.field, "A value")
            else:
                inter.record_skip(q.field)
        assert inter.next_question() is None
        profile = BusinessProfile(**inter.answered)
        assert profile.required_complete


class TestAssumptions:
    def test_blank_fields_become_assumptions(self):
        profile = BusinessProfile(idea="Café", region="Illinois")
        assumptions = profile.assumptions()
        assert any("budget" in a for a in assumptions)
        assert any("target customer" in a for a in assumptions)
        assert not any("business idea" in a for a in assumptions)