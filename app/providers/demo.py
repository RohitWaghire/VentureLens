"""Deterministic demo provider.

Runs the full VentureLens flow with a compact dataset and stable hashes so the
app works end-to-end with no credentials and is fully testable. This provider is
NOT a substitute for real LLM/search/Qloo adapters; it is the MVP default and a
test seam. Real adapters should implement app.providers.base.Provider and be
wired through VL_PROVIDER.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from app import scoring
from app.model import (
    BusinessProfile,
    CityCandidate,
    Evidence,
    FactorScore,
    FollowupTurn,
    NeighborhoodComparison,
    NeighborhoodScorecard,
    Plan,
    Claim,
)
from app.providers import data

FACTOR_ORDER = scoring.CANONICAL_FACTORS

_BUDGET_RE = re.compile(r"\$[\d]+(?:,\d{3})*(?:\.\d+)?[kKmM]?")


def _pick_source(key: str, index: int) -> Evidence:
    title, url = data.DEMO_SOURCES[index % len(data.DEMO_SOURCES)]
    return Evidence(title=title, url=url)


class DemoProvider:
    name = "demo"

    # --- opening prompt extraction ------------------------------------------
    def extract_opening(self, text: str) -> Dict[str, str]:
        result: Dict[str, str] = {}
        text = (text or "").strip()
        if not text:
            return result
        budget = _BUDGET_RE.search(text)
        if budget:
            result["budget"] = budget.group(0)
        low = text.lower()
        for abbr, name in data.US_STATES.items():
            if name.lower() in low:
                result["region"] = data.state_name(abbr)
                break
        if "region" not in result:
            for metro in data.KNOWN_METROS:
                if metro in low:
                    result["region"] = metro.title()
                    break
        idea_raw = None
        for phrase in ("open a ", "launch a ", "start a "):
            if phrase in low:
                idea_raw = text.split(phrase, 1)[1]
                break
        if idea_raw is None:
            idea_raw = text
        idea_raw = re.split(r"\bin\s+[A-Z][\w-]*", idea_raw)[0].strip(" .,;:")
        if idea_raw:
            result["idea"] = idea_raw
        return result

    # --- region validation --------------------------------------------------
    def region_valid(self, region: str) -> bool:
        return data.normalize_region(region) is not None

    # --- city discovery -----------------------------------------------------
    def _region_abbr(self, region: str) -> str:
        abbr = data.normalize_region(region)
        return abbr if abbr else ""

    def discover_cities(
        self,
        profile: BusinessProfile,
        offset: int = 0,
        excludes: Optional[List[str]] = None,
    ) -> List[CityCandidate]:
        excludes = set(excludes or [])
        abbr = self._region_abbr(profile.region)
        pool = data.CITY_TIERS.get(abbr, data.GENERIC_CITIES)
        pool = [c for c in pool if c not in excludes]
        window = pool[offset:offset + 3]
        if not window:
            window = [f"{data.state_name(abbr) or 'Region'} Center"]
        out: List[CityCandidate] = []
        for i, city in enumerate(window):
            out.append(
                CityCandidate(
                    name=city,
                    rationale=(
                        f"Ranked among the {data.state_name(abbr) or 'region'} candidates "
                        "for general desirability and local commercial conditions (demo)."
                    ),
                    citations=[_pick_source(f"{city}-candidate", i)],
                )
            )
        return out

    def city_in_region(self, city: str, profile: BusinessProfile) -> bool:
        abbr = self._region_abbr(profile.region)
        if not abbr:
            return True
        reverse = {c: a for a, cities in data.CITY_TIERS.items() for c in cities}
        return reverse.get(city) == abbr

    # --- neighborhood analysis ----------------------------------------------
    def analyze_neighborhoods(
        self,
        profile: BusinessProfile,
        city: str,
        category: str,
    ) -> NeighborhoodComparison:
        names = data.NEIGHBORHOOD_NAMES.get(city) or data.GENERIC_NEIGHBORHOODS[:8]
        detected = scoring.detect_category(profile.idea)
        template = scoring.closest_template(detected)
        proxy = None if detected in scoring.CATEGORY_TEMPLATES else (detected or "unsupported-category")

        rows: List[NeighborhoodScorecard] = []
        for name in names:
            override = data.OVERRIDES.get((city, name))
            if override:
                raw = override["factors"]
                summary = override["summary"]
            else:
                raw = {
                    f: data.hash_between(f"{city}|{name}|{f}", 2, 5)
                    for f in FACTOR_ORDER
                }
                summary = f"{name} — demo composite view of local conditions."
            factors = self._build_factors(template, name, raw, summary)
            scorecard = self._scorecard(city, name, template, proxy, factors, summary)
            rows.append(scorecard)

        ordered = scoring.sort_for_comparison([self._row_dict(r) for r in rows], template)
        ordered_models = [r["scorecard"] for r in ordered]
        shortlist, note = scoring.shortlist_and_limitation(ordered_models)
        return NeighborhoodComparison(
            city=city,
            category=category,
            template_name=template,
            template_proxy_for=proxy,
            scorecards=ordered_models,
            shortlist=shortlist,
            limitation_note=note,
        )

    def _build_factors(self, template, name, raw, summary) -> List[FactorScore]:
        labels = scoring.factor_labels(template)
        factors: List[FactorScore] = []
        for key in FACTOR_ORDER:
            val = raw.get(key)
            if val is not None and not scoring.validate_factor_score(val):
                val = None
            if val is None:
                factors.append(
                    FactorScore(
                        factor=labels[key],
                        score=None,
                        unavailable=True,
                        rationale=summary + " Factor could not be scored from available demo evidence.",
                        citations=[_pick_source(f"{name}-{key}-missing", 1)],
                    )
                )
            else:
                factors.append(
                    FactorScore(
                        factor=labels[key],
                        score=val,
                        unavailable=False,
                        rationale=summary,
                        citations=[_pick_source(f"{name}-{key}", 2)],
                    )
                )
        return factors

    def _scorecard(self, city, name, template, proxy, factors, summary) -> NeighborhoodScorecard:
        scores = {scoring.CANONICAL_FACTORS[i]: f.score for i, f in enumerate(factors)}
        total = scoring.weighted_total(scores, template)
        cs = scoring.comparable_score(scores, template)
        scored_count = sum(1 for v in scores.values() if v is not None)
        return NeighborhoodScorecard(
            city=city,
            neighborhood=name,
            category=template,
            template_proxy_disclosed=bool(proxy),
            factors=factors,
            weighted_total=total,
            all_scored=total is not None,
            comparable_score=cs,
            scored_count=scored_count,
            summary=summary,
        )

    def _row_dict(self, scorecard: NeighborhoodScorecard) -> Dict:
        return {
            "neighborhood": scorecard.neighborhood,
            "scored_count": scorecard.scored_count,
            "scores": {scoring.CANONICAL_FACTORS[i]: f.score for i, f in enumerate(scorecard.factors)},
            "scorecard": scorecard,
        }

    # --- plan synthesis -----------------------------------------------------
    def synthesize_plan(self, session) -> Plan:
        profile: BusinessProfile = session.profile
        selected = session.selected_city
        comparison: NeighborhoodComparison = session.comparison
        region_label = data.state_name(self._region_abbr(profile.region)) or profile.region

        leader = comparison.scorecards[0] if comparison.scorecards else None
        short_top3 = "; ".join(
            comparison.shortlist or [s.neighborhood for s in comparison.scorecards[:3]]
        )

        header = f"Business Plan — {profile.idea or 'Untitled idea'}"
        overview = (
            f"A planning brief for {profile.idea or 'your business'} in {region_label}. "
            "Recommendations are decision support built from cited, aggregate signals and "
            "labeled assumptions, not guarantees of outcomes."
        )

        audience = [Claim(text=self._audience_line(profile), citations=self._neighborhood_cites(comparison))]
        concept = [
            Claim(
                text=(
                    f"Position the concept around {profile.concept.strip() or 'local specialty and a distinct, '
                    'approachable experience'}; pricing guidance is intentionally out of scope for this version."
                ),
                is_assumption=not profile.concept.strip(),
            )
        ]

        location: List[Claim] = []
        if leader is not None:
            if leader.weighted_total is not None:
                location.append(
                    Claim(
                        text=(
                            f"Within {selected}, the leading neighborhood is {leader.neighborhood} "
                            f"({leader.weighted_total:.2f}/5 weighted fit where all factors were scored)."
                        ),
                        citations=[c for f in leader.factors for c in f.citations],
                    )
                )
            else:
                location.append(
                    Claim(
                        text=(
                            f"Within {selected}, {leader.neighborhood} leads the comparison, but its overall "
                            "numeric fit is withheld because some factors lacked sufficient evidence."
                        ),
                        citations=[c for f in leader.factors for c in f.citations],
                    )
                )
        location.append(
            Claim(
                text=f"Recommended neighborhood shortlist: {short_top3 or 'none (insufficient comparable evidence)'}.",
                citations=self._neighborhood_cites(comparison),
            )
        )

        recommendations = [
            Claim(
                text=f"Prioritize {leader.neighborhood if leader else 'the leading neighborhood'} first for site research.",
                citations=self._neighborhood_cites(comparison),
            )
        ]
        assumptions = [Claim(text=a, is_assumption=True) for a in (profile.assumptions() or ["None"])]
        risks = [
            Claim(text="Aggregate taste and audience signals describe groups, not guaranteed demand or profitability."),
            Claim(text="Weights are initial heuristics and have not been empirically validated."),
        ]
        next_steps = [
            Claim(
                text=(
                    "Visit the shortlisted neighborhoods; validate rents, foot traffic, and permits; "
                    "and refine the concept against local competitors before committing a site."
                )
            )
        ]

        return Plan(
            title=header,
            overview=overview,
            audience=audience,
            concept=concept,
            location=location,
            recommendations=recommendations,
            assumptions=assumptions,
            risks=risks,
            next_steps=next_steps,
        )

    def _audience_line(self, profile: BusinessProfile) -> str:
        if profile.audience.strip():
            return f"Primary audience captured during intake: {profile.audience.strip()}."
        return "Target audience was not specified; audience fit relies on neighborhood-level aggregate signals."

    def _neighborhood_cites(self, comparison: NeighborhoodComparison):
        cites: List[Evidence] = []
        for s in comparison.scorecards:
            for f in s.factors:
                cites.extend(f.citations)
        return cites[:6]

    # --- follow-up ----------------------------------------------------------
    def answer_followup(self, session, question: str, context_citations: Optional[List] = None) -> FollowupTurn:
        comparison = session.comparison
        short_top = comparison.shortlist[0] if comparison.shortlist else (
            comparison.scorecards[0].neighborhood if comparison.scorecards else "the leading area"
        )
        answer = (
            f"Based on the current findings, the leading recommendation is {short_top}. "
            f"Verify {short_top} with an on-the-ground visit before committing. "
            "(Demo provider answer; new research is simulated deterministically.)"
        )
        citations = context_citations or (self._neighborhood_cites(comparison) if comparison else [])
        return FollowupTurn(question=question, answer=answer, citations=citations)