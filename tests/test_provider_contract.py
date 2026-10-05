"""Provider contract behavior with the deterministic demo provider."""

from __future__ import annotations

from types import SimpleNamespace

from app.model import BusinessProfile
from app.providers.demo import DemoProvider

P = DemoProvider()


class TestOpeningExtraction:
    def test_full_opening_prompt(self):
        out = P.extract_opening(
            "I have $250k and want to open a specialty coffee shop in Illinois."
        )
        assert out["budget"] == "$250k"
        assert out["region"] == "Illinois"
        assert "specialty coffee shop" == out["idea"].strip()

    def test_empty_prompt_is_safe(self):
        assert P.extract_opening("") == {}


class TestRegionAndCities:
    def test_region_valid_and_invalid(self):
        assert P.region_valid("Illinois") is True
        assert P.region_valid("IL") is True
        assert P.region_valid("Nowhereland") is False

    def test_discover_cities_returns_three(self):
        profile = BusinessProfile(idea="coffee shop", region="Illinois")
        cities = P.discover_cities(profile)
        assert len(cities) == 3
        assert cities[0].name == "Chicago"

    def test_city_in_region(self):
        profile = BusinessProfile(idea="coffee shop", region="Illinois")
        assert P.city_in_region("Chicago", profile) is True
        assert P.city_in_region("Phoenix", profile) is False


class TestNeighborhoodAnalysis:
    def test_chicago_scorecards_and_shortlist(self):
        profile = BusinessProfile(idea="specialty coffee shop", region="Illinois")
        comp = P.analyze_neighborhoods(profile, "Chicago", "cafe")
        assert comp.template_name == "cafe"
        assert len(comp.scorecards) >= 5
        assert len(comp.shortlist) == 3

    def test_incomplete_evidence_withholds_total(self):
        profile = BusinessProfile(idea="coffee shop", region="Illinois")
        comp = P.analyze_neighborhoods(profile, "Chicago", "cafe")
        hyde = next(s for s in comp.scorecards if s.neighborhood == "Hyde Park")
        assert hyde.all_scored is False
        assert hyde.weighted_total is None
        assert hyde.scored_count < 5

    def test_fully_scored_rows_have_totals(self):
        profile = BusinessProfile(idea="coffee shop", region="Illinois")
        comp = P.analyze_neighborhoods(profile, "Chicago", "cafe")
        complete = [s for s in comp.scorecards if s.neighborhood != "Hyde Park"]
        assert all(s.all_scored for s in complete)
        assert all(s.weighted_total is not None for s in complete)

    def test_unsupported_category_uses_proxy_template(self):
        profile = BusinessProfile(idea="dog-washing service", region="Illinois")
        comp = P.analyze_neighborhoods(profile, "Chicago", "cafe")
        assert comp.template_name == "cafe"
        assert comp.template_proxy_for  # proxy template is disclosed


class TestPlanSynthesis:
    def _session(self, comparison, sel="Chicago"):
        return SimpleNamespace(
            profile=BusinessProfile(idea="specialty coffee shop", region="Illinois"),
            selected_city=sel,
            comparison=comparison,
        )

    def test_plan_has_sections_and_citations(self):
        profile = BusinessProfile(idea="specialty coffee shop", region="Illinois")
        comp = P.analyze_neighborhoods(profile, "Chicago", "cafe")
        session = self._session(comp)
        plan = P.synthesize_plan(session)
        assert plan.title
        assert plan.location
        assert plan.recommendations
        assert any(plan.location[0].citations)

    def test_leader_notes_withheld_total(self):
        from app.model import NeighborhoodComparison, NeighborhoodScorecard

        leader = NeighborhoodScorecard(
            city="X", neighborhood="Leader", category="cafe", factors=[],
            weighted_total=None, all_scored=False, scored_count=3,
        )
        comp = NeighborhoodComparison(
            city="X", category="cafe", template_name="cafe",
            scorecards=[leader], shortlist=[], limitation_note="",
        )
        plan = P.synthesize_plan(self._session(comp, sel="X"))
        combined = " ".join(c.text for c in plan.location)
        assert "withheld" in combined