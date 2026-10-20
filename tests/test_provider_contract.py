"""Demo provider contract behavior: dynamic grilling + report writing."""

from __future__ import annotations

from app.model import BusinessProfile, GrillTurn
from app.providers.demo import DemoProvider

P = DemoProvider()


class TestOpening:
    def test_extracts_idea_budget_region(self):
        profile = P.extract_opening(
            "I have $250k and want to open a specialty coffee shop in Illinois."
        )
        assert profile.idea.strip() == "specialty coffee shop"
        assert profile.budget == "$250k"
        assert profile.region == "Illinois"

    def test_empty_prompt_is_safe(self):
        assert P.extract_opening("").idea == ""


class TestDynamicQuestions:
    def test_first_question_has_options(self):
        q = P.question(P.extract_opening("mutant poke bar"), [])
        assert q.id == "budget"
        assert q.options
        assert all(opt.label for opt in q.options)

    def test_budget_question_skipped_when_already_stated(self):
        profile = P.extract_opening("I have $250k and want to open a coffee shop in Illinois.")
        q = P.question(profile, [])
        assert q.id != "budget"

    def test_questions_do_not_repeat(self):
        profile = BusinessProfile(idea="coffee shop")
        q_ids = []
        q = P.question(profile, [])
        turns = []
        while q is not None:
            q_ids.append(q.id)
            turns.append(GrillTurn(question_id=q.id, question=q.text, answer="ok"))
            q = P.question(profile, turns)
        assert len(q_ids) == len(set(q_ids))

    def test_cafe_prompt_surfaces_cafe_specific_question(self):
        profile = BusinessProfile(idea="specialty coffee shop")
        turns = [
            GrillTurn(question_id="budget", question="Q1", answer="ok"),
            GrillTurn(question_id="timeline", question="Q2", answer="ok"),
            GrillTurn(question_id="audience", question="Q3", answer="ok"),
            GrillTurn(question_id="concept", question="Q4", answer="ok"),
        ]
        q = P.question(profile, turns)
        assert q.id == "coffee_position"

    def test_restaurant_prompt_surfaces_restaurant_specific_question(self):
        profile = BusinessProfile(idea="a neighborhood pizzeria")
        q = P.question(
            profile,
            [GrillTurn(question_id="budget", question="Q1", answer="ok")],
        )
        ids = []
        while q is not None:
            ids.append(q.id)
            q = P.question(
                profile,
                [GrillTurn(question_id=i, question="Q", answer="ok") for i in ids],
            )
        assert "cuisine" in ids
        assert "coffee_position" not in ids


class TestReport:
    def test_report_reflects_answers_and_caveat(self):
        profile = P.extract_opening("I have $120k and want to open a coffee shop in Texas.")
        transcript = [
            GrillTurn(question_id="timeline", question="Timing?", answer="Within 6 months"),
            GrillTurn(question_id="audience", question="Audience?", answer="Students"),
        ]
        report = P.write_report(profile, "I have $120k and want to open a coffee shop in Texas.", transcript)
        assert "coffee shop" in report.title
        assert any(s.body == "Within 6 months" for s in report.sections)
        assert any(s.body == "Students" for s in report.sections)
        assert any(s.heading == "Target area" and s.body == "Texas" for s in report.sections)
        assert report.caveat

    def test_empty_transcript_still_writes_report(self):
        report = P.write_report(BusinessProfile(idea="bakery"), "", [])
        assert report.sections
        assert report.title == "Business brief — bakery"