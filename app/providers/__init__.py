"""Provider factory.

The app always uses the live provider. There is no demo checklist to fall
back to when the model or Qloo is unavailable.
"""

from __future__ import annotations

from app.config import Settings
from app.providers.base import Provider
from app.providers.live import LiveProvider


def get_provider(settings: Settings) -> Provider:
    return LiveProvider(settings)
