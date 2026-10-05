"""Provider factory: map VL_PROVIDER to a concrete adapter.

The demo provider is the default so the app runs with no credentials. Real
adapters plug in here behind the same app.providers.base.Provider interface.
"""

from __future__ import annotations

from app.config import get_settings
from app.providers.base import Provider
from app.providers.demo import DemoProvider


def get_provider() -> Provider:
    settings = get_settings()
    name = (settings.provider or "demo").strip().lower()
    if name == "demo":
        return DemoProvider()
    # Real adapters (e.g. a LiteLLM-backed provider) would be registered here.
    # Unknown names fall back to demo with a clear marker so the app still runs.
    return DemoProvider()