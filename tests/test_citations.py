"""Citation integrity: sources are preserved from research through plan export."""

from __future__ import annotations

from app.markdown import render_plan
from app.model import BusinessProfile
from app.providers import data
from app.providers.demo import DemoProvider

P = DemoProvider()
ALLOWED_URLS = {url for _, url in data.DEMO_SOURCES}


def _chicago_plan():
    profile = BusinessProfile(idea="specialty coffee shop", region="Illinois")
    comp = P.analyze_neighborhoods(profile, "Chicago", "cafe")
    session = type("S", (), {
        "profile": profile, "selected_city": "Chicago", "comparison": comp,
    })()
    return P.synthesize_plan(session), comp


class _Flatten:
    @staticmethod
    def claim_urls(plan):
        urls = []
        for section in ("audience", "concept", "location", "recommendations",
                        "assumptions", "risks", "next_steps"):
            for c in getattr(plan, section):
                urls.extend(cite.url for cite in c.citations)
        return urls


class TestCitationIntegrity:
    def test_all_citations_from_retrieved_sources(self):
        plan, _ = _chicago_plan()
        urls = _Flatten.claim_urls(plan)
        assert urls
        assert all(u in ALLOWED_URLS for u in urls), "model invented an out-of-scope URL"

    def test_citations_survive_markdown_export(self):
        plan, _ = _chicago_plan()
        md = render_plan(plan)
        sample_url = plan.location[0].citations[0].url
        assert sample_url in md, "citation URL lost during export"


class TestScorecardMarkdown:
    def test_incomplete_row_marks_total_withheld(self):
        from app.markdown import render_scorecard_markdown
        _, comp = _chicago_plan()
        hyde = next(s for s in comp.scorecards if s.neighborhood == "Hyde Park")
        md = render_scorecard_markdown(comp)
        assert "Hyde Park" in md
        assert "withheld" in md
        assert hyde.weighted_total is None