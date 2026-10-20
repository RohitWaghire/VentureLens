"""Provider factory: map VL_PROVIDER to a concrete adapter.

``demo`` needs no credentials. ``live`` calls Qloo and an OpenAI-compatible
model. Any other name stays on the demo adapter so the app still runs.
"""

from __future__ import annotations

from app.config import Settings
from app.providers.base import Provider
from app.providers.demo import DemoProvider
from app.providers.live import LiveProvider


def get_provider(settings: Settings) -> Provider:
    name = (settings.provider or "demo").strip().lower()
    if name == "live":
        return LiveProvider(settings)
    return DemoProvider()
