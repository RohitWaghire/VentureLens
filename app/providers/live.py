"""Live report writer: Qloo taste signals, then a model brief.

Grilling stays on the shared question pool. ``write_report`` sends the idea
and place to Qloo, then sends those signals plus the answers to an
OpenAI-compatible chat model. VentureLens does not store either response.

The HTTP transport is injected so tests can exercise this adapter with no network.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, List, Optional

from app.config import Settings
from app.model import BusinessProfile, GrillTurn, Report, ReportSection
from app.providers.base import Provider, ProviderError
from app.providers.grilling import answers_report

Fetch = Callable[[str, str, dict, Optional[bytes], float], tuple[int, bytes]]

_LLM_BASES = {
    "openrouter": "https://openrouter.ai/api/v1",
    "groq": "https://api.groq.com/openai/v1",
    "together": "https://api.together.xyz/v1",
}

_CAVEAT = (
    "Taste signals are aggregate Qloo affinities, not evidence about a specific "
    "person, foot traffic, or profit. The narrative was written by the configured "
    "model from those signals and your answers. VentureLens keeps them only for "
    "this session and does not delete them from Qloo or the model provider."
)


def urllib_fetch(
    method: str,
    url: str,
    headers: dict,
    body: Optional[bytes],
    timeout: float,
) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read(1_000_000)
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(1_000_000)
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise ProviderError("The taste service or the model could not be reached.") from exc


class LiveProvider(Provider):
    name = "live"

    def __init__(self, settings: Settings, fetch: Fetch = urllib_fetch) -> None:
        self.settings = settings
        self.fetch = fetch

    def write_report(
        self,
        profile: BusinessProfile,
        opening: str,
        transcript: List[GrillTurn],
    ) -> Report:
        signals = self._taste(profile)
        narrative = self._narrate(profile, opening, transcript, signals)
        report = narrative or answers_report(profile, transcript)
        report.sections = [
            section
            for section in report.sections
            if section.heading.strip().lower() != "taste signals"
        ]
        report.sections.append(_taste_section(signals))
        report.caveat = _CAVEAT
        return report

    def _taste(self, profile: BusinessProfile) -> list[dict]:
        if not self.settings.qloo_api_key:
            raise ProviderError("Set VL_QLOO_API_KEY before using the live provider.")
        idea = (profile.idea or "local business").strip()
        tag_ids = self._tag_ids(idea)
        params = {
            "filter.type": "urn:entity:place",
            "take": "8",
        }
        if profile.region:
            params["filter.location.query"] = profile.region
        if tag_ids:
            params["signal.interests.tags"] = ",".join(tag_ids)
        status, payload = self._qloo_get("/v2/insights", params)
        if status in (401, 403):
            raise ProviderError(
                "Qloo refused the request. Use a hackathon key with "
                "https://hackathon.api.qloo.com."
            )
        if status == 429:
            raise ProviderError("Qloo rate limit reached. Try again shortly.")
        entities = _entities(payload) if status == 200 else []
        if entities:
            return entities
        return self._search_places(idea, profile.region)

    def _tag_ids(self, idea: str) -> list[str]:
        status, payload = self._qloo_get("/v2/tags", {"filter.query": idea[:80], "take": "5"})
        if status != 200:
            return []
        tags = _tags(payload)
        return [tag["id"] for tag in tags if tag.get("id")][:5]

    def _search_places(self, idea: str, region: str) -> list[dict]:
        query = f"{idea} {region}".strip()
        status, payload = self._qloo_get(
            "/search",
            {"query": query[:120], "types": "urn:entity:place", "take": "5"},
        )
        if status == 404 or status != 200:
            return []
        found = _entities(payload) or _search_hits(payload)
        if not found:
            return []
        ids = [item["id"] for item in found if item.get("id")]
        if not ids:
            return found
        params = {
            "filter.type": "urn:entity:place",
            "signal.interests.entities": ",".join(ids[:5]),
            "take": "8",
        }
        if region:
            params["filter.location.query"] = region
        status, payload = self._qloo_get("/v2/insights", params)
        if status != 200:
            return found
        insights = _entities(payload)
        return insights or found

    def _qloo_get(self, path: str, params: dict) -> tuple[int, object]:
        base = self.settings.qloo_base_url.rstrip("/")
        url = f"{base}{path}?{urllib.parse.urlencode(params)}"
        status, raw = self.fetch(
            "GET",
            url,
            {"X-Api-Key": self.settings.qloo_api_key, "Accept": "application/json"},
            None,
            self.settings.qloo_timeout_seconds,
        )
        return status, _json_bytes(raw)

    def _narrate(
        self,
        profile: BusinessProfile,
        opening: str,
        transcript: List[GrillTurn],
        signals: list[dict],
    ) -> Optional[Report]:
        if not self.settings.llm_api_key or not self.settings.llm_model:
            return None
        payload = _chat_payload(
            self.settings.llm_model,
            [
                {
                    "role": "system",
                    "content": (
                        "Write a short small-business brief as JSON with keys "
                        "title, summary, and sections. sections is a list of "
                        "{heading, body}. Use only the answers and the Qloo taste "
                        "signals in the user message. Do not invent places, scores, "
                        "or demand. Call anything beyond those inputs an assumption. "
                        "Qloo signals are aggregate taste, not proof of profit. "
                        "Do not add a Taste signals section."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "opening": opening,
                            "idea": profile.idea,
                            "region": profile.region,
                            "budget": profile.budget,
                            "answers": [
                                {"question": turn.question, "answer": turn.answer}
                                for turn in transcript
                            ],
                            "qloo_places": signals,
                        }
                    ),
                },
            ],
        )
        body = json.dumps(payload).encode()
        url = f"{_llm_base(self.settings)}/chat/completions"
        try:
            status, raw = self.fetch(
                "POST",
                url,
                {
                    "Authorization": f"Bearer {self.settings.llm_api_key}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body,
                self.settings.llm_timeout_seconds,
            )
        except ProviderError:
            return None
        if status != 200:
            return None
        content = _message_content(_json_bytes(raw))
        parsed = _parse_json_object(content)
        if not parsed:
            return None
        sections = []
        for item in (parsed.get("sections") or [])[:6]:
            if not isinstance(item, dict):
                continue
            heading = str(item.get("heading") or "").strip()
            text = str(item.get("body") or "").strip()
            if heading and text:
                sections.append(ReportSection(heading=heading[:120], body=text[:2000]))
        if not sections:
            return None
        idea = profile.idea or "your business"
        return Report(
            title=str(parsed.get("title") or f"Business brief — {idea}")[:160],
            summary=str(parsed.get("summary") or "")[:1000],
            sections=sections,
        )


def _chat_payload(model: str, messages: list) -> dict:
    """Build a chat-completions body the named model will accept.

    GPT-6 rejects temperature unless reasoning effort is none. Luna supports
    none, which is the right effort for a short structured brief.
    """
    payload = {"model": model, "messages": messages}
    name = (model or "").strip().lower()
    if name.startswith("gpt-6"):
        if "luna" in name or name == "gpt-6-sol":
            payload["reasoning_effort"] = "none"
        return payload
    payload["temperature"] = 0.2
    return payload


def _llm_base(settings: Settings) -> str:
    configured = getattr(settings, "llm_base_url", "") or ""
    if configured.strip():
        return configured.rstrip("/")
    return _LLM_BASES.get((settings.llm_provider or "").strip().lower(), "https://api.openai.com/v1")


def _json_bytes(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8", errors="replace") or "null")
    except json.JSONDecodeError:
        return None


def _parse_json_object(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: text.rfind("```")]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            return None
    return None


def _message_content(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content") if isinstance(message, dict) else ""
    return content if isinstance(content, str) else ""


def _tags(payload: object) -> list[dict]:
    results = _results(payload)
    raw = []
    if isinstance(results, dict):
        raw = results.get("tags") or []
    elif isinstance(payload, dict):
        raw = payload.get("tags") or []
    tags = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tag_id = item.get("id") or item.get("tag_id") or ""
        tags.append({"id": str(tag_id), "name": str(item.get("name") or "")})
    return tags


def _entities(payload: object) -> list[dict]:
    results = _results(payload)
    raw = []
    if isinstance(results, dict):
        raw = results.get("entities") or []
    elif isinstance(results, list):
        raw = results
    return [_place(item) for item in raw if isinstance(item, dict)]


def _search_hits(payload: object) -> list[dict]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("results")
    if isinstance(raw, list):
        return [_place(item) for item in raw if isinstance(item, dict)]
    return []


def _results(payload: object):
    if isinstance(payload, dict):
        return payload.get("results")
    return None


def _place(item: dict) -> dict:
    props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
    detail = props.get("short_description") or props.get("description") or ""
    tag_names = []
    for tag in item.get("tags") or []:
        if isinstance(tag, dict) and tag.get("name"):
            tag_names.append(str(tag["name"]))
    place_id = item.get("entity_id") or item.get("id") or ""
    return {
        "id": str(place_id),
        "name": str(item.get("name") or "Unnamed place"),
        "detail": str(detail)[:400],
        "tags": tag_names[:8],
    }


def _taste_section(signals: list[dict]) -> ReportSection:
    if not signals:
        return ReportSection(
            heading="Taste signals",
            body=(
                "Qloo returned no place affinities for this idea and location. "
                "Treat the rest of the brief as based on your answers."
            ),
        )
    lines = []
    for signal in signals[:8]:
        bits = [signal["name"]]
        if signal.get("tags"):
            bits.append(", ".join(signal["tags"][:4]))
        if signal.get("detail"):
            bits.append(signal["detail"])
        lines.append(" — ".join(bits))
    return ReportSection(heading="Taste signals", body="\n".join(lines))
