"""Build and cache the structured plan for a session.

Keeps plan synthesis in one place so the app layer stays thin. Follow-up chat
never regenerates the cached plan (it only appends turns).
"""

from __future__ import annotations

from app import markdown
from app.providers.base import Provider


def ensure_plan(session, provider: Provider):
    """Return the session's cached plan, building and caching it if needed."""
    if session.plan is None:
        session.plan = provider.synthesize_plan(session)
        if session.comparison is not None:
            markdown.attach_scorecard(session.plan, session.comparison)
    return session.plan