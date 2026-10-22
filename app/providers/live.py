"""Live report writer. The model mediates between the founder and Qloo.

``write_report`` asks the model to name a place category from the idea and
the transcript. Qloo is searched for that phrase. Only place-category tags
are kept, and when several match the model picks one. Insights uses that tag
and the city. The model then writes the brief and a short note from the
places Qloo returned. VentureLens does not store either response.

The HTTP transport is injected so tests can exercise this adapter with no network.
"""

from __future__ import annotations

import json
import logging
import math
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, List, Optional

from app.config import Settings
from app.model import BusinessProfile, GrillOption, GrillQuestion, GrillTurn, Report, ReportSection
from app.providers.base import Provider, ProviderError
from app.providers.grilling import answers_report

log = logging.getLogger(__name__)

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

_CATEGORY_PROMPT = (
    "You choose the Qloo place-category search phrase for one business. "
    "Return JSON {\"category\": \"...\"}. "
    "Use 1 to 3 words from the business itself. "
    "There is no fixed list of business types. "
    "Leave out the city, the budget, the timeline, and who the customers are. "
    "Name the place the way a directory would. "
    "A food business is a restaurant when that is the place, so a ramen shop is a ramen restaurant. "
    "Keep shop when the business is a shop, such as a coffee shop or a chocolate shop. "
    "A bar is a bar, not a barber shop. "
    "A roofing business is a roofing contractor, not a supply store. "
    "A chocolate business that is a shop is a chocolate shop, not a manufacturer."
)

_PICK_PROMPT = (
    "Pick one Qloo place-category tag for this business. "
    "Return JSON {\"id\": \"<id from the list>\"}. "
    "Copy an id exactly. If none name this business, return {\"id\": \"\"}. "
    "Prefer the tag that names the business over a parent category, a manufacturer, or a supply variant. "
    "A bar is not a barber shop."
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
        self._frontier_cache: dict = {}

    def frontier(self, profile: BusinessProfile, transcript: List[GrillTurn]) -> List[GrillQuestion]:
        """The next question for this idea. A model failure is not a shared checklist."""
        if not self.settings.llm_api_key or not self.settings.llm_model:
            raise ProviderError("Set VL_LLM_API_KEY and VL_LLM_MODEL before grilling.")
        key = (
            profile.idea,
            profile.region,
            profile.budget,
            tuple((turn.question_id, turn.answer) for turn in transcript),
        )
        cached = self._frontier_cache.get(key)
        if cached is not None:
            return cached
        if not _location(profile, transcript) and not _answered_place(transcript):
            return [_city_question()]
        if len(transcript) >= 8:
            questions: List[GrillQuestion] = []
        else:
            generated = self._questions_for_idea(profile, transcript)
            if generated is None or (not generated and not transcript):
                raise ProviderError(
                    "The planning guide could not form the next question. "
                    "Check the live provider settings and try again."
                )
            questions = generated[:1]
        self._frontier_cache[key] = questions
        return questions

    def write_report(
        self,
        profile: BusinessProfile,
        opening: str,
        transcript: List[GrillTurn],
    ) -> Report:
        signals, gap = self._taste(profile, transcript, opening)
        narrative = self._narrate(profile, opening, transcript, signals)
        report = narrative or answers_report(profile, transcript)
        report.sections = [
            section
            for section in report.sections
            if section.heading.strip().lower() not in {"taste signals", "what similar places suggest"}
        ]
        report.sections.append(self._readable_places(profile, signals, gap))
        report.caveat = _CAVEAT
        return report

    def _taste(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
        opening: str = "",
    ) -> tuple[list[dict], str]:
        if not self.settings.qloo_api_key:
            raise ProviderError("Set VL_QLOO_API_KEY before using the live provider.")
        location = _location(profile, transcript, opening)
        if not location:
            return [], "no-city"
        phrase = self._category_phrase(profile, opening, transcript)
        if not phrase:
            return [], "no-category"
        status, payload = self._qloo_get(
            "/v2/tags",
            {"filter.query": phrase[:80], "take": "8"},
        )
        if status == 0:
            return [], "down"
        if status != 200:
            return [], "tag-error"
        tags = [tag for tag in _tags(payload) if _is_category_place(tag)]
        chosen, reason = self._choose_tag(profile, opening, tags)
        if chosen is None:
            return [], reason
        # A named city stays on the request. An empty city is not a reason to
        # search the world; the only wider call is the same state, and only
        # places near that city are kept.
        return self._local_places(chosen["id"], location)

    def _category_phrase(
        self,
        profile: BusinessProfile,
        opening: str,
        transcript: List[GrillTurn],
    ) -> str:
        """The place category the model names. Answer words are not extra searches."""
        parsed = self._chat(
            [
                {"role": "system", "content": _CATEGORY_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "idea": profile.idea,
                            "opening": opening,
                            "region": profile.region,
                            "answers": [
                                {"question": turn.question, "answer": turn.answer}
                                for turn in transcript
                            ],
                        }
                    ),
                },
            ]
        )
        if not isinstance(parsed, dict):
            return ""
        return " ".join(str(parsed.get("category") or "").split())[:80]

    def _choose_tag(
        self,
        profile: BusinessProfile,
        opening: str,
        tags: list[dict],
    ) -> tuple[Optional[dict], str]:
        """One confirmed place category. An id the model invents is not used."""
        if not tags:
            return None, "no-tags"
        if len(tags) == 1:
            return tags[0], ""
        parsed = self._chat(
            [
                {"role": "system", "content": _PICK_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "idea": profile.idea,
                            "opening": opening,
                            "tags": [{"id": tag["id"], "name": tag["name"]} for tag in tags],
                        }
                    ),
                },
            ]
        )
        if not isinstance(parsed, dict):
            return None, "no-choice"
        wanted = str(parsed.get("id") or "").strip()
        chosen = next((tag for tag in tags if tag["id"] == wanted), None)
        if chosen is None:
            return None, "no-match"
        return chosen, ""

    def _insights(self, tag_id: str, location: str) -> tuple[int, object]:
        return self._qloo_get("/v2/insights", place_insights_params(tag_id, location))

    def _local_places(self, tag_id: str, location: str) -> tuple[list[dict], str]:
        status, payload = self._insights(tag_id, location)
        if status == 0:
            return [], "down"
        if status != 200:
            return [], "insights-error"
        center = _resolved_locality(payload)
        places = _entities(payload)
        if not _is_city(center):
            kept = _dedupe_places(places)
            return (kept, "") if kept else ([], "no-places")
        places = _within_miles(places, center, _CITY_MILES)
        if places:
            return _dedupe_places(places), ""
        state = str(center.get("state") or "")
        if not state or state.lower() == location.lower():
            return [], "no-places"
        status, wider = self._insights(tag_id, state)
        if status == 0:
            return [], "down"
        if status != 200:
            return [], "insights-error"
        kept = _dedupe_places(_within_miles(_entities(wider), center, _CITY_MILES))
        return (kept, "") if kept else ([], "no-places")

    def _qloo_get(self, path: str, params: dict, timeout: float | None = None) -> tuple[int, object]:
        if path.startswith("/v2/insights"):
            _reject_bad_insights(params)
        base = self.settings.qloo_base_url.rstrip("/")
        url = f"{base}{path}?{urllib.parse.urlencode(params)}"
        try:
            status, raw = self.fetch(
                "GET",
                url,
                {"X-Api-Key": self.settings.qloo_api_key, "Accept": "application/json"},
                None,
                timeout or self.settings.qloo_timeout_seconds,
            )
        except ProviderError:
            log.warning("qloo request failed for %s", path)
            return 0, None
        if status != 200:
            log.warning("qloo %s returned %s: %s", path, status, _body_snippet(raw))
        _raise_for_qloo_status(status)
        return status, _json_bytes(raw)

    def _questions_for_idea(
        self,
        profile: BusinessProfile,
        transcript: List[GrillTurn],
    ) -> Optional[List[GrillQuestion]]:
        parsed = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "You are grilling a founder about one specific business. "
                        "Return JSON {\"questions\": [{\"id\", \"text\", \"options\", \"recommendation\"}]}. "
                        "Ask exactly one question that can be decided from what is already known. "
                        "The question must be specific to this business. A grocery shop, a yoga studio, "
                        "and a coffee shop must not receive the same questions. "
                        "Do not repeat a topic already answered. Do not ask a question whose answer "
                        "depends on something still open. Options are 3 to 5 short choices. "
                        "recommendation is one of those options. "
                        "If region is empty, ask which U.S. city they want before any other question. "
                        "If nothing material is left to decide, return {\"questions\": []}."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "idea": profile.idea,
                            "region": profile.region,
                            "budget": profile.budget,
                            "answered": [
                                {"question": turn.question, "answer": turn.answer}
                                for turn in transcript
                            ],
                        }
                    ),
                },
            ]
        )
        if not parsed or not isinstance(parsed.get("questions"), list):
            return None
        asked = {turn.question.strip().lower() for turn in transcript}
        asked_ids = {turn.question_id for turn in transcript}
        questions = []
        for item in parsed["questions"][:1]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            options = [str(option).strip() for option in item.get("options") or [] if str(option).strip()]
            if not text or text.lower() in asked or len(options) < 2:
                continue
            question_id = str(item.get("id") or f"q{len(questions) + 1}").strip()[:40]
            if question_id in asked_ids:
                continue
            recommendation = str(item.get("recommendation") or options[0]).strip()
            if recommendation not in options:
                recommendation = options[0]
            questions.append(
                GrillQuestion(
                    id=question_id,
                    text=text[:240],
                    options=[GrillOption(label=option, value=option) for option in options[:5]],
                    recommendation=recommendation,
                )
            )
            asked.add(text.lower())
            asked_ids.add(question_id)
        return questions

    def _readable_places(
        self,
        profile: BusinessProfile,
        signals: list[dict],
        gap: str,
    ) -> ReportSection:
        """Ask the model to turn raw Qloo places into a short founder note."""
        heading = "What similar places suggest"
        if not signals:
            return ReportSection(heading=heading, body=_missing_places(gap))
        parsed = self._chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Turn Qloo place results into a short note a founder can read. "
                        "Return JSON {\"body\": \"...\"}. Write 2 or 3 plain sentences. "
                        "Name at most four places and the town each one is in. "
                        "Do not repeat a chain, and do not paste the source descriptions. "
                        "Do not list tags, scores, age ranges, or payment methods. "
                        "Do not invent places that are not in the list. "
                        "Say when the list is thin. These are aggregate taste matches, not proof of demand."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "business": profile.idea,
                            "region": profile.region,
                            "places": [
                                {
                                    "name": place["name"],
                                    "where": place.get("where") or "",
                                    "about": place.get("detail") or "",
                                }
                                for place in signals[:6]
                            ],
                        }
                    ),
                },
            ]
        )
        body = ""
        if isinstance(parsed, dict):
            body = str(parsed.get("body") or "").strip()
        if not body:
            body = _plain_places(signals, profile.region)
        return ReportSection(heading=heading, body=body)

    def _chat(self, messages: list) -> Optional[dict]:
        if not self.settings.llm_api_key or not self.settings.llm_model:
            return None
        body = json.dumps(_chat_payload(self.settings.llm_model, messages)).encode()
        try:
            status, raw = self.fetch(
                "POST",
                f"{_llm_base(self.settings)}/chat/completions",
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
        if parsed:
            return parsed
        text = (content or "").strip()
        if text and not text.startswith("{") and len(text) < 700:
            return {"body": text}
        return None

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
                        "Do not mention tags or paste source descriptions. "
                        "Do not add a section titled Taste signals or What similar places suggest."
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


def _raise_for_qloo_status(status: int) -> None:
    if status in (401, 403):
        raise ProviderError(
            "Qloo refused the request. Use a hackathon key with "
            "https://hackathon.api.qloo.com."
        )
    if status == 429:
        raise ProviderError("Qloo rate limit reached. Try again shortly.")


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


def _location(profile: BusinessProfile, transcript: List[GrillTurn], opening: str = "") -> str:
    if (profile.region or "").strip():
        return _qloo_location(profile.region)
    from app.providers.grilling import extract_opening

    stated = extract_opening(opening).region
    if stated:
        return _qloo_location(stated)
    for turn in transcript:
        answer = (turn.answer or "").strip()
        if not answer or answer.lower() in _GENERIC_ANSWERS:
            continue
        if _is_place_turn(turn):
            parsed = extract_opening(f"shop in {answer}").region
            return _qloo_location(parsed or answer)
    return ""


def _is_place_turn(turn: GrillTurn) -> bool:
    question = f"{turn.question_id} {turn.question}".lower()
    return any(word in question for word in ("where", "city", "neighborhood", "location", "area", "place"))


def _answered_place(transcript: List[GrillTurn]) -> bool:
    return any(_is_place_turn(turn) and (turn.answer or "").strip() for turn in transcript)


def _city_question() -> GrillQuestion:
    return GrillQuestion(
        id="place",
        text="Which U.S. city should this be in?",
        free_text_hint="Name a city.",
    )


def _missing_places(reason: str) -> str:
    if reason == "no-city":
        return (
            "Qloo was not asked for places because this session has no U.S. city. "
            "Name a city to get a place list."
        )
    if reason == "down":
        return "Qloo could not be reached, so this brief has no place list."
    if reason == "no-category":
        return (
            "The planning guide could not name a place category for this idea, "
            "so Qloo was not asked for places."
        )
    if reason == "tag-error":
        return "Qloo's category lookup failed, so this brief has no place list."
    if reason == "no-tags":
        return "Qloo returned no place category for this idea, so this brief has no place list."
    if reason == "no-choice":
        return (
            "The planning guide could not choose a Qloo place category, "
            "so places were not requested."
        )
    if reason == "no-match":
        return (
            "None of Qloo's place categories named this business, "
            "so places were not requested."
        )
    if reason == "insights-error":
        return "Qloo's place request failed, so this brief has no place list."
    return (
        "Qloo returned no place affinities for this idea and location. "
        "Treat the rest of the brief as based on your answers."
    )


def _body_snippet(raw: bytes) -> str:
    return raw[:180].decode("utf-8", errors="replace").replace("\n", " ").strip()


def _qloo_location(value: str) -> str:
    """Send the city Qloo can resolve. Bare 'New York' is the state."""
    text = (value or "").strip()
    if text.casefold() in {"nyc", "new york city"}:
        return "New York City"
    return text


_GENERIC_ANSWERS = {
    "one city / metro",
    "multiple cities",
    "not decided yet",
    "lean and focused",
    "premium / specialty",
    "family-friendly",
    "local community anchor",
    "nothing else",
    "i have specifics i'll type",
}


_CITY_MILES = 40


def place_insights_params(tag_id: str, location: str) -> dict:
    """The only place-insights request this app sends.

    ``filter.tags`` keeps places of that category. An interest signal asks which
    other places fans of the tag like, which is a different question.
    """
    if not str(tag_id).startswith("urn:tag:category:place:"):
        raise ValueError("place insights require a category place tag")
    params = {
        "filter.type": "urn:entity:place",
        "take": "8",
        "filter.tags": tag_id,
    }
    if location:
        params["filter.location.query"] = location
    return params


def _reject_bad_insights(params: dict) -> None:
    if any(key.startswith("signal.interests") for key in params):
        raise ProviderError(
            "Place insights filter by category. Do not send an interest signal."
        )
    if not str(params.get("filter.tags") or "").startswith("urn:tag:category:place:"):
        raise ProviderError("Place insights require a confirmed category tag.")


def _is_category_place(tag: dict) -> bool:
    return str(tag.get("id") or "").startswith("urn:tag:category:place:")


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
        kind = item.get("type") or item.get("subtype") or ""
        tags.append({"id": str(tag_id), "name": str(item.get("name") or ""), "type": str(kind)})
    return tags


def _entities(payload: object) -> list[dict]:
    results = _results(payload)
    raw = []
    if isinstance(results, dict):
        raw = results.get("entities") or []
    elif isinstance(results, list):
        raw = results
    return [_place(item) for item in raw if isinstance(item, dict)]


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
    point = item.get("location") if isinstance(item.get("location"), dict) else {}
    return {
        "id": str(place_id),
        "name": str(item.get("name") or "Unnamed place"),
        "detail": str(detail)[:400],
        "where": _town(item, props),
        "lat": point.get("lat"),
        "lon": point.get("lon"),
        "tags": tag_names[:8],
    }


def _town(item: dict, props: dict) -> str:
    locality = props.get("locality")
    if isinstance(locality, dict):
        locality = locality.get("name") or ""
    if isinstance(locality, str) and locality.strip():
        return locality.strip()
    found = re.findall(
        r"([A-Za-z][A-Za-z .'-]{1,40}),\s*([A-Z]{2})\b",
        str(item.get("disambiguation") or ""),
    )
    if not found:
        return ""
    town = " ".join(found[-1][0].split()[-3:]).strip(" .")
    return f"{town}, {found[-1][1]}"


def _plain_places(signals: list[dict], location: str = "") -> str:
    """A short note when the model does not rewrite the place list."""
    named = []
    seen = set()
    for place in signals:
        name = str(place.get("name") or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        where = str(place.get("where") or "").strip()
        named.append(f"{name} in {where}" if where and where.lower() not in name.lower() else name)
        if len(named) == 4:
            break
    area = location or "the area you named"
    if not named:
        return (
            f"Qloo returned no places in {area} for this idea. "
            "Treat the rest of the brief as based on your answers."
        )
    if len(named) == 1:
        listed = named[0]
    else:
        listed = ", ".join(named[:-1]) + f", and {named[-1]}"
    return (
        f"The closest Qloo matches near {area} are {listed}. "
        "These are aggregate taste matches, not proof of demand."
    )


def _resolved_locality(payload: object) -> Optional[dict]:
    """The place Qloo understood a location query to mean, including its map point."""
    if not isinstance(payload, dict):
        return None
    query = payload.get("query")
    if not isinstance(query, dict):
        return None
    filters = ((query.get("localities") or {}).get("filter") or [])
    if not filters or not isinstance(filters[0], dict):
        return None
    item = filters[0]
    point = item.get("location") if isinstance(item.get("location"), dict) else {}
    parts = [part.strip() for part in str(item.get("disambiguation") or "").split(",") if part.strip()]
    state = parts[-2] if len(parts) >= 3 else ""
    return {
        "name": str(item.get("name") or ""),
        "state": state,
        "lat": point.get("lat"),
        "lon": point.get("lon"),
    }


def _is_city(center: Optional[dict]) -> bool:
    """True only when Qloo resolved a city, not the state that shares its name.

    A state comes back as "New York, United States". That has no separate state
    field. Calling it a city measures distance from the state centroid and drops
    places that were valid for the state.
    """
    if not center or center.get("lat") is None or center.get("lon") is None:
        return False
    name = str(center.get("name") or "").strip().lower()
    state = str(center.get("state") or "").strip().lower()
    return bool(name) and bool(state) and name != state


def _miles(lat1: float, lon1: float, lat2: object, lon2: object) -> Optional[float]:
    if lat2 is None or lon2 is None:
        return None
    lat1, lon1, lat2, lon2 = map(math.radians, (float(lat1), float(lon1), float(lat2), float(lon2)))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 3958.8 * 2 * math.asin(math.sqrt(arc))


def _within_miles(places: list[dict], center: dict, radius: float) -> list[dict]:
    kept = []
    for place in places:
        distance = _miles(center["lat"], center["lon"], place.get("lat"), place.get("lon"))
        if distance is None or distance > radius:
            continue
        near = dict(place)
        near["miles"] = distance
        kept.append(near)
    kept.sort(key=lambda place: place["miles"])
    return kept


def _dedupe_places(places: list[dict]) -> list[dict]:
    seen = set()
    unique = []
    for place in places:
        key = str(place.get("name") or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(place)
    return unique[:6]
