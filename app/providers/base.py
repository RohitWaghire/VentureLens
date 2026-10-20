"""Provider interface.

Callers learn three methods. ``extract_opening`` and ``question`` are shared:
every adapter asks the same next question. ``write_report`` is the seam where
the demo brief and the live Qloo-plus-model brief differ.

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
        """Every question that can be asked now, given the answers so far."""
        return grilling.frontier(profile, transcript)

    def write_report(
        self,
        profile: BusinessProfile,
        opening: str,
        transcript: List[GrillTurn],
    ) -> Report:
        """Write the brief from the opening prompt and the collected answers."""
        raise NotImplementedError
