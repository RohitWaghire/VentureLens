"""Provider interface.

Callers learn three methods. ``extract_opening`` reads the opening prompt.
``question`` is the next grilling question. ``write_report`` asks the model to name a place category, Qloo for
places of that category, and the model again for the brief.

A live call raises ``ProviderError`` with a message that is safe to show.
The message never includes credentials or response bodies.
"""

from __future__ import annotations

from typing import List

from app.model import BusinessProfile, GrillQuestion, GrillTurn, Report
from app.providers import grilling


class ProviderError(Exception):
    """The live provider could not finish a report. Safe to show to the user."""


class Provider:
    name: str = "base"

    def extract_opening(self, text: str) -> BusinessProfile:
        """Parse idea, budget, and region from the opening prompt."""
        return grilling.extract_opening(text)

    def question(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> GrillQuestion | None:
        """Return the first frontier question, or None when the tree is settled."""
        ready = self.frontier(profile, transcript)
        return ready[0] if ready else None

    def frontier(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> List[GrillQuestion]:
        """The next question, chosen by the live provider from this idea."""
        return []

    def write_report(
        self,
        profile: BusinessProfile,
        opening: str,
        transcript: List[GrillTurn],
    ) -> Report:
        """Write the brief from the opening prompt and the collected answers."""
        raise NotImplementedError
