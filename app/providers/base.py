"""Provider adapters and the factory that selects one.

The app depends on the ``Provider`` protocol only. The demo provider is the
default (deterministic, credential-free, fully testable). Real LLM, search, and
Qloo adapters can be added behind the same seam by implementing this protocol
and mapping ``VL_PROVIDER`` to the chosen adapter (see app/config.py).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.model import (
    BusinessProfile,
    CityCandidate,
    FollowupTurn,
    NeighborhoodComparison,
    Plan,
)


class Provider:
    """The seam between the application and external research/synthesis services.

    Real adapters implement these methods; the demo provider ships a
    deterministic implementation. Methods that perform live research should
    respect the configured timeouts and be wrapped so the session/global query
    budgets are charged at the call site.
    """

    name: str = "base"

    def extract_opening(self, text: str) -> Dict[str, str]:
        """Best-effort extraction from the user's opening prompt into a profile.

        Returns a dict of profile fields (e.g. idea, region, budget) that the
        interview may pre-fill. Never invents facts not stated.
        """
        raise NotImplementedError

    def region_valid(self, region: str) -> bool:
        """Return True when ``region`` is a usable U.S. state or region for discovery."""
        raise NotImplementedError

    def discover_cities(
        self,
        profile: BusinessProfile,
        offset: int = 0,
        excludes: Optional[List[str]] = None,
    ) -> List[CityCandidate]:
        """Return the next batch of ranked candidate cities for the region."""
        raise NotImplementedError

    def city_in_region(self, city: str, profile: BusinessProfile) -> bool:
        """Return True when a manually entered city is inside the selected region."""
        raise NotImplementedError

    def analyze_neighborhoods(
        self,
        profile: BusinessProfile,
        city: str,
        category: str,
    ) -> NeighborhoodComparison:
        """Discover and score 5-10 neighborhoods in ``city``."""
        raise NotImplementedError

    def synthesize_plan(self, session) -> Plan:
        """Assemble the structured plan from the session's profile and comparison."""
        raise NotImplementedError

    def answer_followup(
        self,
        session,
        question: str,
        context_citations: Optional[List] = None,
    ) -> FollowupTurn:
        """Answer a follow-up question; may perform new research when needed."""
        raise NotImplementedError

    def analyze_neighborhoods_v1(
        self,
        profile: BusinessProfile,
        city: str,
        category: str,
    ) -> NeighborhoodComparison:
        # Alias retained for explicit seam clarity.
        return self.analyze_neighborhoods(profile, city, category)