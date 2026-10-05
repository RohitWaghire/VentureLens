"""Unit tests for scorecard rules (external behavior of scoring functions)."""

from __future__ import annotations

import pytest

from app import scoring
from app.model import NeighborhoodScorecard


def _card(name, scored_count, scores):
    return NeighborhoodScorecard(
        city="Chicago",
        neighborhood=name,
        category="cafe",
        factors=[],
        scored_count=scored_count,
    )


class TestCategoryDetection:
    def test_coffee_is_cafe(self):
        assert scoring.detect_category("a specialty coffee shop") == "cafe"

    def test_espresso_is_cafe(self):
        assert scoring.detect_category("espresso bar") == "cafe"

    def test_pizzeria_is_restaurant(self):
        assert scoring.detect_category("a pizzeria") == "restaurant"

    def test_unknown_category_maps_to_closest_proxy(self):
        detected = scoring.detect_category("a dog-washing business")
        assert detected is None
        assert scoring.closest_template(detected) == "cafe"


class TestWeightsAndTotals:
    def test_cafe_weights_sum_to_one(self):
        weights = scoring.factor_weights("cafe")
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        assert weights["accessibility"] == pytest.approx(0.25)

    def test_restaurant_weights_sum_to_one(self):
        weights = scoring.factor_weights("restaurant")
        assert abs(sum(weights.values()) - 1.0) < 1e-9
        assert weights["competition"] == pytest.approx(0.25)

    def test_weighted_total_when_all_scored(self):
        scores = {"audience": 5, "competition": 4, "affordability": 3,
                  "accessibility": 5, "momentum": 4}
        assert scoring.weighted_total(scores, "cafe") == pytest.approx(4.35)

    def test_total_withheld_when_any_missing(self):
        scores = {"audience": 5, "competition": 4, "affordability": 3,
                  "accessibility": None, "momentum": 4}
        assert scoring.weighted_total(scores, "cafe") is None

    def test_total_withheld_when_any_none(self):
        scores = {"audience": None, "competition": 4, "affordability": 3,
                  "accessibility": 5, "momentum": 4}
        assert scoring.weighted_total(scores, "cafe") is None

    def test_invalid_score_rejected(self):
        assert not scoring.validate_factor_score(0)
        assert not scoring.validate_factor_score(6)
        assert not scoring.validate_factor_score("4")
        assert scoring.validate_factor_score(3)


class TestOrdering:
    def test_more_complete_rows_weighted_first(self):
        complete = {"audience": 3, "competition": 3, "affordability": 3,
                    "accessibility": 3, "momentum": 3}
        partial = {"audience": 5, "competition": 5, "affordability": 5,
                   "accessibility": None, "momentum": None}
        rows = [
            {"neighborhood": "Partial High", "scored_count": 3, "scores": partial},
            {"neighborhood": "Complete Mid", "scored_count": 5, "scores": complete},
        ]
        ordered = scoring.sort_for_comparison(rows, "cafe")
        assert ordered[0]["neighborhood"] == "Complete Mid"

    def test_tie_break_by_heuristic_score(self):
        a = {"neighborhood": "A", "scored_count": 5,
             "scores": {"audience": 5, "competition": 5, "affordability": 5,
                        "accessibility": 5, "momentum": 5}}
        b = {"neighborhood": "B", "scored_count": 5,
             "scores": {"audience": 1, "competition": 1, "affordability": 1,
                        "accessibility": 1, "momentum": 1}}
        ordered = scoring.sort_for_comparison([b, a], "cafe")
        assert ordered[0]["neighborhood"] == "A"


class TestShortlist:
    def test_three_eligible_candidates_selected(self):
        cards = [_card(f"N{i}", 5, {}) for i in range(4)]
        shortlist, note = scoring.shortlist_and_limitation(cards)
        assert len(shortlist) == 3
        assert note == ""

    def test_shortlist_limited_when_insufficient_evidence(self):
        cards = [_card("N1", 2, {}), _card("N2", 3, {})]
        shortlist, note = scoring.shortlist_and_limitation(cards)
        assert len(shortlist) < 3
        assert "Fewer than 3" in note