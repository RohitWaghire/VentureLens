"""Shared data models for VentureLens.

Pydantic models describe the interview profile, candidate cities, neighborhood
scorecards, and the synthesized business plan. Citations are modeled as
(source title, url) pairs attached to individual claims so integrity can be
preserved from research through export.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    """A retrieved source that supports a claim."""

    title: str
    url: str


class Claim(BaseModel):
    """A single statement in the plan, optionally backed by citations."""

    text: str
    citations: List[Evidence] = Field(default_factory=list)
    is_assumption: bool = False


class BusinessProfile(BaseModel):
    """The agreed understanding of the user's business.

    Every free field may be blank when the user skipped an optional interview
    question; skipped fields become labeled assumptions downstream rather than
    being silently invented.
    """

    idea: str = ""
    region: str = ""
    budget: str = ""
    audience: str = ""
    concept: str = ""
    price: str = ""
    footprint: str = ""
    competitors: str = ""
    growth: str = ""

    @property
    def idea_known(self) -> bool:
        return bool(self.idea.strip())

    @property
    def region_known(self) -> bool:
        return bool(self.region.strip())

    @property
    def required_complete(self) -> bool:
        """The gate before city discovery: business idea + U.S. region."""
        return self.idea_known and self.region_known

    def assumptions(self) -> List[str]:
        """Human-readable labels for fields the user did not provide."""
        labels = {
            "idea": "business idea",
            "region": "U.S. state/region",
            "budget": "start-up budget",
            "audience": "target customer",
            "concept": "concept/positioning",
            "price": "price point",
            "footprint": "footprint",
            "competitors": "competitors",
            "growth": "growth goals",
        }
        out = []
        for field, label in labels.items():
            if not getattr(self, field).strip():
                out.append(f"{label} was not provided and is treated as an assumption")
        return out


class CityCandidate(BaseModel):
    """A ranked candidate city returned from discovery."""

    name: str
    rationale: str = ""
    citations: List[Evidence] = Field(default_factory=list)
    is_custom: bool = False


class FactorScore(BaseModel):
    """A single 1-5 factor score, or an explicit unavailable marker.

    ``score`` is ``None`` exactly when ``unavailable`` is True.
    """

    factor: str
    score: Optional[int] = None
    unavailable: bool = False
    rationale: str = ""
    citations: List[Evidence] = Field(default_factory=list)


class NeighborhoodScorecard(BaseModel):
    """Scorecard for one neighborhood in one category template."""

    city: str
    neighborhood: str
    category: str
    template_proxy_disclosed: bool = False
    factors: List[FactorScore] = Field(default_factory=list)
    # Numeric overall fit score; set only when every factor is scored.
    weighted_total: Optional[float] = None
    all_scored: bool = False
    # Heuristic ordering value over available factors only; never shown as the
    # authoritative total. Used for tie-breaking among equal-completeness rows.
    comparable_score: Optional[float] = None
    scored_count: int = 0
    summary: str = ""


class NeighborhoodComparison(BaseModel):
    """The result of comparing 5-10 neighborhoods in a chosen city."""

    city: str
    category: str
    template_name: str
    template_proxy_for: Optional[str] = None
    scorecards: List[NeighborhoodScorecard] = Field(default_factory=list)
    shortlist: List[str] = Field(default_factory=list)
    limitation_note: str = ""


class FollowupTurn(BaseModel):
    question: str
    answer: str
    citations: List[Evidence] = Field(default_factory=list)


class Plan(BaseModel):
    """The structured business plan shown to the user and exported as Markdown."""

    title: str = ""
    overview: str = ""
    scorecard_markdown: str = ""
    audience: List[Claim] = Field(default_factory=list)
    concept: List[Claim] = Field(default_factory=list)
    location: List[Claim] = Field(default_factory=list)
    recommendations: List[Claim] = Field(default_factory=list)
    assumptions: List[Claim] = Field(default_factory=list)
    risks: List[Claim] = Field(default_factory=list)
    next_steps: List[Claim] = Field(default_factory=list)