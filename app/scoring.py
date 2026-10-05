"""Neighborhood scorecard logic.

Weight application and weighted-total arithmetic live in plain application code,
never in the model. The model supplies per-factor 1-5 ratings from cited
evidence using the fixed anchors below; unavailable factors are handled here.

Conventions
-----------
- Five canonical factors map to two category templates with documented weights.
- A weighted total is only computed when *every* factor for the category is
  scored (scores 1-5). If any factor is unavailable, the total is withheld.
- Ordering rule for comparison (documented product decision):
    1. More complete evidence first: rows with more scored factors rank higher.
    2. Among rows with equal scored-factor counts, use ``comparable_score``
       (the weighted average over available factors only) as a *heuristic
       tie-breaker*. This is never displayed as the authoritative total and is
       explicitly labeled as a comparison heuristic.
    3. Alphabetical by neighborhood name as a final deterministic tie-break.
- Eligibility for the shortlist: at least ``MIN_SCORED_FOR_SHORTLIST`` factors
  (default 3 of 5) must be scored. If fewer than three comparable neighborhoods
  qualify, the app explains the limitation instead of implying comparability.

Rubric anchors are versioned so score meaning is stable and auditable.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Optional

CATEGORY_CAFE = "cafe"
CATEGORY_RESTAURANT = "restaurant"

# Canonical factor keys.
F_AUDIENCE = "audience"
F_COMPETITION = "competition"
F_AFFORDABILITY = "affordability"
F_ACCESSIBILITY = "accessibility"
F_MOMENTUM = "momentum"

CANONICAL_FACTORS = [
    F_AUDIENCE,
    F_COMPETITION,
    F_AFFORDABILITY,
    F_ACCESSIBILITY,
    F_MOMENTUM,
]

# Documented starting weights. Heuristics, not validated predictors.
CATEGORY_TEMPLATES: Dict[str, "OrderedDict[str, Dict[str, object]]"] = {
    CATEGORY_CAFE: OrderedDict(
        [
            (F_AUDIENCE, {"label": "Audience fit", "weight": 0.25}),
            (F_COMPETITION, {"label": "Competition / saturation", "weight": 0.20}),
            (F_AFFORDABILITY, {"label": "Affordability", "weight": 0.15}),
            (F_ACCESSIBILITY, {"label": "Accessibility / foot traffic", "weight": 0.25}),
            (F_MOMENTUM, {"label": "Neighborhood momentum", "weight": 0.15}),
        ]
    ),
    CATEGORY_RESTAURANT: OrderedDict(
        [
            (F_AUDIENCE, {"label": "Audience fit", "weight": 0.25}),
            (F_COMPETITION, {"label": "Competition / saturation", "weight": 0.25}),
            (F_AFFORDABILITY, {"label": "Affordability", "weight": 0.15}),
            (
                F_ACCESSIBILITY,
                {"label": "Accessibility / foot traffic / delivery access", "weight": 0.20},
            ),
            (F_MOMENTUM, {"label": "Neighborhood momentum", "weight": 0.15}),
        ]
    ),
}

ANCHOR_VERSION = "1.0"

# Fixed 1-5 rubric anchors, per factor. "unavailable" states when evidence is
# too sparse to score the factor at all.
RUBRIC_ANCHORS: Dict[str, Dict[str, str]] = {
    F_AUDIENCE: {
        "1": "No evident overlap between the neighborhood's resident/visitor profile and the target customer.",
        "2": "Occasional alignment with the target customer; coverage is inconsistent.",
        "3": "Moderate alignment; a meaningful share of foot traffic resembles the target customer.",
        "4": "Strong alignment; the neighborhood's profile closely matches the target customer.",
        "5": "Exceptional alignment; the neighborhood is a concentrated match for the target customer.",
        "unavailable": "No reliable evidence could establish the neighborhood's audience profile.",
    },
    F_COMPETITION: {
        "1": "Heavy saturation with directly competing establishments.",
        "2": "Notable existing competition that will require clear differentiation.",
        "3": "A balanced mix; some competition but clear space for another entrant.",
        "4": "Light competition with room to differentiate.",
        "5": "Very little direct competition while demand still appears present.",
        "unavailable": "Competition data for this neighborhood could not be verified.",
    },
    F_AFFORDABILITY: {
        "1": "Space and operating costs are likely prohibitive for the stated budget.",
        "2": "Costs are high and may strain the budget.",
        "3": "Costs are within a plausible range for the budget.",
        "4": "Costs are comfortably within budget.",
        "5": "Costs are well below budget for the stated scale.",
        "unavailable": "Commercial rent/cost evidence was not available for this neighborhood.",
    },
    F_ACCESSIBILITY: {
        "1": "Poor foot traffic and hard to reach (limited transit/parking).",
        "2": "Low foot traffic and only modest accessibility.",
        "3": "Decent foot traffic with reasonable transit or parking access.",
        "4": "Good foot traffic and convenient access.",
        "5": "Excellent foot traffic and very strong accessibility.",
        "unavailable": "Accessibility/foot-traffic evidence could not be established.",
    },
    F_MOMENTUM: {
        "1": "Evidence points to a static or declining neighborhood.",
        "2": "Limited signals of growth; direction is unclear.",
        "3": "Modest new development or population trends.",
        "4": "Clear signs of growth and new investment.",
        "5": "Strong, broad momentum with visible development and inbound interest.",
        "unavailable": "Underlying growth/development trends could not be verified.",
    },
}

# Minimum scored factors for a neighborhood to be eligible for the shortlist.
MIN_SCORED_FOR_SHORTLIST = 3
SHORTLIST_SIZE = 3
NEIGHBORHOOD_CANDIDATE_MIN = 5
NEIGHBORHOOD_CANDIDATE_MAX = 10

SUPPORTED_KEYWORDS = {
    CATEGORY_CAFE: ("coffee", "café", "cafe", "espresso", "bakery"),
    CATEGORY_RESTAURANT: ("restaurant", "kitchen", "diner", "bistro", "pizzeria", "food hall"),
}


def factor_labels(category: str) -> "OrderedDict[str, str]":
    """Return canonical factor key -> display label for a category."""
    return OrderedDict(
        (key, str(spec["label"])) for key, spec in CATEGORY_TEMPLATES[category].items()
    )


def factor_weights(category: str) -> "OrderedDict[str, float]":
    """Return canonical factor key -> weight for a category."""
    return OrderedDict(
        (key, float(spec["weight"])) for key, spec in CATEGORY_TEMPLATES[category].items()
    )


def detect_category(idea: str) -> Optional[str]:
    """Pick a scorecard template from the business idea description.

    Returns None when the idea does not clearly match a supported template; the
    caller then selects the closest template and discloses the proxy.
    """
    text = (idea or "").lower()
    for category, keywords in SUPPORTED_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return None


def closest_template(category: Optional[str]) -> str:
    """Resolve a category to a concrete template, disclosing proxies upstream."""
    if category in CATEGORY_TEMPLATES:
        return category
    # Café is the default proxy template for unsupported business ideas.
    return CATEGORY_CAFE


def validate_factor_score(value) -> bool:
    """A factor score must be an int in 1..5."""
    return isinstance(value, int) and 1 <= value <= 5


def weighted_total(scores: Dict[str, Optional[int]], category: str) -> Optional[float]:
    """Return the weighted total fit score, or None if any factor is unscored."""
    template = CATEGORY_TEMPLATES[category]
    for key in template:
        if scores.get(key) is None:
            return None
    total = sum(float(spec["weight"]) * scores[key] for key, spec in template.items())
    return round(total, 2)


def comparable_score(scores: Dict[str, Optional[int]], category: str) -> Optional[float]:
    """Weighted average over available factors only (comparison heuristic).

    A tie-breaking heuristic; must never be presented as the authoritative
    overall score, because incomplete rows are not directly comparable.
    """
    template = CATEGORY_TEMPLATES[category]
    available = [(key, scores[key]) for key in template if scores.get(key) is not None]
    if not available:
        return None
    weight_sum = sum(float(template[key]["weight"]) for key, _ in available)
    if weight_sum <= 0:
        return None
    total = sum(float(template[key]["weight"]) * scores[key] for key, _ in available)
    return round(total / weight_sum, 2)


def sort_for_comparison(rows: List[Dict], category: str) -> List[Dict]:
    """Order comparison rows: completeness, then heuristic score, then name."""

    def sort_key(row):
        scores = {
            key: (row.get("scores", {}) or {}).get(key)
            for key in CANONICAL_FACTORS
        }
        cs = comparable_score(scores, category)
        return (-row.get("scored_count", 0), -(cs if cs is not None else -1), row.get("neighborhood", ""))

    return sorted(rows, key=sort_key)


def shortlist_and_limitation(scorecards: List) -> List[str]:
    """Pick up to three eligible neighborhoods, returning (shortlist, note).

    Eligibility requires at least ``MIN_SCORED_FOR_SHORTLIST`` scored factors.
    ``note`` is non-empty when fewer than three comparable candidates exist.
    """
    eligible = [
        s.neighborhood
        for s in scorecards
        if s.scored_count >= MIN_SCORED_FOR_SHORTLIST
    ]
    shortlist = eligible[:SHORTLIST_SIZE]
    if len(shortlist) < SHORTLIST_SIZE:
        note = (
            f"Fewer than {SHORTLIST_SIZE} neighborhoods had enough evidence "
            f"({MIN_SCORED_FOR_SHORTLIST}+ of {len(CANONICAL_FACTORS)} factors) for a "
            "directly comparable shortlist, so the recommendation emphasis is limited "
            "by evidence coverage."
        )
        return shortlist, note
    return shortlist, ""