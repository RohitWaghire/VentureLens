"""Provider adapter interface and notes on how real services plug in.

The app depends on the ``Provider`` interface only. The demo provider is the
default (deterministic, credential-free, fully testable).

Mapping to the requested pipeline:
- ``first_question`` / ``next_question`` emulate the "grilling" skill: they
  dynamically produce a question and shortlisted answer options derived from
  the user's prompt and prior answers. A real deployment implements this as an
  LLM call that respects the provider seam and session/global budgets.
- ``write_report`` emulates the model step that consumes the collected answers
  and returns a report. The user's reference calls this "Qloo LLM"; in practice
  Qloo is a taste/data API and the reasoning model is the configured LLM, so a
  real adapter composes both. The demo provider stands in until credentials are
  wired through ``VL_PROVIDER``.
"""

from __future__ import annotations

from typing import List, Optional

from app.model import BusinessProfile, GrillQuestion, GrillTurn, Report


class Provider:
    name: str = "base"

    def extract_opening(self, text: str) -> BusinessProfile:
        """Best-effort parse of the opening prompt into a profile."""
        raise NotImplementedError

    def first_question(
        self,
        profile: BusinessProfile,
        opening: str,
    ) -> GrillQuestion:
        """Return the first grilling question for this prompt."""
        raise NotImplementedError

    def next_question(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> Optional[GrillQuestion]:
        """Return the next grilling question, or None when grilling is done.

        Each returned question may depend on the opening prompt and prior
        answers, mirroring the grilling skill's dynamic questioning.
        """
        raise NotImplementedError

    def write_report(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> Report:
        """Consume the collected answers and return the report."""
        raise NotImplementedError