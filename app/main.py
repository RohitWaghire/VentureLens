"""VentureLens FastAPI application.

Server-rendered web UI + backend endpoints, with an in-memory session store,
per-IP rate limiting, per-session/global research budgets, cookie/CSRF
protections, and a deterministic demo provider behind a replaceable seam.
"""

from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import markdown, scoring
from app.config import Settings, get_settings
from app.interview import FIELD_INDEX, InterviewState, QUESTION_SEQUENCE
from app.model import BusinessProfile
from app.plan_builder import ensure_plan
from app.providers import get_provider
from app.providers.base import Provider
from app.security import RateLimiter, QueryBudget, client_ip, csrf_token, verify_csrf, origin_allowed
from app.sessions import Session, SessionStore

_TEMPLATE_DIR = "app/templates"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = SessionStore(settings.session_max_age_seconds)
    limiter = RateLimiter(settings.rate_limit_per_ip, settings.rate_limit_window_seconds)
    budget = QueryBudget(settings.session_query_budget, settings.global_query_budget)
    provider: Provider = get_provider()
    templates = Jinja2Templates(directory=_TEMPLATE_DIR)

    app = FastAPI(title=settings.app_name)

    # --- request-level safety middleware ------------------------------------
    @app.middleware("http")
    async def safety(request: Request, call_next):
        ip = client_ip(request, settings.trusted_proxies)
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if not origin_allowed(request, settings.allowed_origins):
                return PlainTextResponse("Origin not allowed", status_code=403)
            if not limiter.allow(f"ip:{ip}"):
                return PlainTextResponse("Rate limit exceeded. Please slow down.", status_code=429)
        else:
            limiter.allow(f"ip:{ip}")
        response = await call_next(request)
        return response

    # --- helpers -------------------------------------------------------------
    app.state.store = store
    app.state.budget = budget
    app.state.provider = provider
    app.state.settings = settings

    def session_id(request: Request) -> Optional[str]:
        return request.cookies.get(settings.session_cookie_name)

    def session_or_create(request: Request) -> "Session":
        s = store.get(session_id(request))
        if s is None:
            s = store.create()
            s.interview = InterviewState()
        return s

    def session_only(request: Request):
        return store.get(session_id(request))

    def set_cookie(response, session) -> None:
        response.set_cookie(
            settings.session_cookie_name,
            session.id,
            max_age=settings.session_max_age_seconds,
            httponly=True,
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
        )

    def ctx(request: Request, session, **extra) -> dict:
        base = {
            "request": request,
            "app_name": settings.app_name,
            "tagline": settings.tagline,
            "csrf": csrf_token(settings.secret_key, session) if session else "",
            "demo_mode": getattr(provider, "name", "demo") == "demo",
        }
        base.update(extra)
        return base

    def charge(session, count: int = 1) -> bool:
        return budget.register_spend(session, count)

    def valid_form_token(session, token: str) -> bool:
        return bool(session and verify_csrf(settings.secret_key, session, token))

    # --- entry / interview ----------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        session = session_or_create(request)
        if session.interview is None:
            session.interview = InterviewState()
        if not session.interview.answered.get("idea", "").strip():
            response = templates.TemplateResponse(
                request,
                "landing.html",
                ctx(request, session, error=request.query_params.get("error")),
            )
            set_cookie(response, session)
            return response
        question = session.interview.next_question()
        if question is None:
            if session.profile is None:
                response = RedirectResponse("/summary", status_code=303)
            else:
                response = RedirectResponse("/cities", status_code=303)
            set_cookie(response, session)
            return response
        pending = [
            q for q in QUESTION_SEQUENCE
            if q.field not in session.interview.answered and q.field not in session.interview.skipped
        ]
        history = []
        for previous in QUESTION_SEQUENCE:
            if previous.field == question.field:
                break
            if previous.field in session.interview.answered:
                history.append({
                    "question": previous.text,
                    "answer": session.interview.answered[previous.field],
                    "skipped": False,
                })
            elif previous.field in session.interview.skipped:
                history.append({
                    "question": previous.text,
                    "answer": previous.skip_label or "Skipped for now",
                    "skipped": True,
                })
        ctx_data = ctx(
            request,
            session,
            question=question,
            answered=session.interview.answered,
            skipped=session.interview.skipped,
            questions=QUESTION_SEQUENCE,
            history=history,
            is_final_question=len(pending) == 1,
        )
        response = templates.TemplateResponse(request, "interview.html", ctx_data)
        set_cookie(response, session)
        return response

    @app.post("/start", response_class=HTMLResponse)
    def start_from_prompt(
        request: Request,
        prompt: str = Form(..., max_length=2000),
        csrf: str = Form(...),
    ):
        """Start a session from the natural-language prompt composer."""
        prompt = (prompt or "").strip()
        if not prompt:
            return RedirectResponse("/?error=Please describe your business idea to begin.", status_code=303)

        session = store.get(request.cookies.get(settings.session_cookie_name))
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        store.delete(session.id)
        session = store.create()
        session.interview = InterviewState()
        extracted = provider.extract_opening(prompt)
        # The prompt itself always captures the idea. The demo extractor may
        # additionally prefill explicitly mentioned budget/region details.
        extracted["idea"] = extracted.get("idea", "").strip() or prompt
        if extracted.get("region") and not provider.region_valid(extracted["region"]):
            extracted.pop("region", None)
        for field, value in extracted.items():
            if field in FIELD_INDEX and isinstance(value, str) and value.strip():
                session.interview.record_answer(field, value.strip())

        response = RedirectResponse("/", status_code=303)
        set_cookie(response, session)
        return response

    @app.post("/interview", response_class=HTMLResponse)
    def interview_submit(
        request: Request,
        field: str = Form(...),
        answer: str = Form(""),
        skip: str = Form(""),
        csrf: str = Form(...),
    ):
        session = session_only(request)
        if session is None:
            return RedirectResponse("/", status_code=303)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        if session.interview is None:
            session.interview = InterviewState()
        q = next((x for x in QUESTION_SEQUENCE if x.field == field), None)
        if q is not None:
            if skip == "1" and not q.required:
                session.interview.record_skip(q.field)
            else:
                session.interview.record_answer(q.field, answer)
        if session.interview.next_question() is None:
            # Animate completion of the grilling flow before profile confirmation.
            return RedirectResponse("/profile-ready", status_code=303)
        response = RedirectResponse("/", status_code=303)
        set_cookie(response, session)
        return response

    # --- profile summary & confirmation -------------------------------------
    @app.get("/profile-ready", response_class=HTMLResponse)
    def profile_ready(request: Request):
        session = session_only(request)
        if session is None or session.interview is None:
            return RedirectResponse("/", status_code=303)
        if session.interview.next_question() is not None:
            return RedirectResponse("/", status_code=303)
        profile = BusinessProfile(**session.interview.answered)
        return templates.TemplateResponse(
            request,
            "profile_ready.html",
            ctx(request, session, profile=profile),
        )

    @app.get("/summary", response_class=HTMLResponse)
    def summary(request: Request):
        session = session_only(request)
        if session is None:
            return RedirectResponse("/", status_code=303)
        inter = session.interview or InterviewState()
        profile = session.profile or BusinessProfile(
            **{k: v for k, v in inter.answered.items()}
        )
        error = request.query_params.get("error")
        return templates.TemplateResponse(
            request,
            "summary.html",
            ctx(
                request,
                session,
                profile=profile,
                assumptions=profile.assumptions(),
                error=error,
            ),
        )

    @app.post("/summary", response_class=HTMLResponse)
    def summary_submit(
        request: Request,
        idea: str = Form(""),
        region: str = Form(""),
        budget: str = Form(""),
        audience: str = Form(""),
        concept: str = Form(""),
        price: str = Form(""),
        footprint: str = Form(""),
        competitors: str = Form(""),
        growth: str = Form(""),
        csrf: str = Form(...),
    ):
        session = session_only(request)
        if session is None:
            return RedirectResponse("/", status_code=303)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        values = {
            "idea": idea.strip(),
            "region": region.strip(),
            "budget": budget.strip(),
            "audience": audience.strip(),
            "concept": concept.strip(),
            "price": price.strip(),
            "footprint": footprint.strip(),
            "competitors": competitors.strip(),
            "growth": growth.strip(),
        }
        if not values["idea"] or not values["region"]:
            return RedirectResponse("/summary?error=Business idea and U.S. state/region are required.", status_code=303)
        if not provider.region_valid(values["region"]):
            return RedirectResponse("/summary?error=That region is not a recognized U.S. state or known metro.", status_code=303)
        session.profile = BusinessProfile(**values)
        session.category = scoring.detect_category(values["idea"])
        if not charge(session, 1):
            return RedirectResponse("/error?reason=budget", status_code=303)
        session.cities = provider.discover_cities(session.profile, offset=0)
        return RedirectResponse("/cities", status_code=303)

    # --- city selection -----------------------------------------------------
    @app.get("/cities", response_class=HTMLResponse)
    def cities(request: Request):
        session = session_only(request)
        if session is None or session.profile is None or not session.profile.required_complete:
            return RedirectResponse("/", status_code=303)
        if not session.cities:
            if not charge(session, 1):
                return RedirectResponse("/error?reason=budget", status_code=303)
            session.cities = provider.discover_cities(session.profile, offset=0)
        return templates.TemplateResponse(
            request,
            "cities.html",
            ctx(
                request,
                session,
                cities=session.cities,
                region=session.profile.region,
                error=request.query_params.get("error"),
            ),
        )

    @app.post("/cities", response_class=HTMLResponse)
    def cities_submit(
        request: Request,
        action: str = Form(...),
        city: str = Form(""),
        csrf: str = Form(...),
    ):
        session = session_only(request)
        if session is None or session.profile is None:
            return RedirectResponse("/", status_code=303)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        profile = session.profile
        if action == "select":
            if not charge(session, 1):
                return RedirectResponse("/error?reason=budget", status_code=303)
            session.selected_city = city
            session.comparison = provider.analyze_neighborhoods(profile, city, session.category or "cafe")
            return RedirectResponse("/neighborhoods", status_code=303)
        if action == "alternatives":
            if not charge(session, 1):
                return RedirectResponse("/error?reason=budget", status_code=303)
            offset = len(session.cities)
            excludes = [c.name for c in session.cities]
            batch = provider.discover_cities(profile, offset=offset, excludes=excludes)
            if batch:
                session.cities.extend(batch)
            return RedirectResponse("/cities", status_code=303)
        if action == "custom":
            if not provider.city_in_region(city, profile):
                return RedirectResponse("/cities?error=That city is outside your selected region.", status_code=303)
            if not charge(session, 1):
                return RedirectResponse("/error?reason=budget", status_code=303)
            session.selected_city = city
            session.comparison = provider.analyze_neighborhoods(profile, city, session.category or "cafe")
            return RedirectResponse("/neighborhoods", status_code=303)
        return RedirectResponse("/cities", status_code=303)

    # --- neighborhood comparison --------------------------------------------
    @app.get("/neighborhoods", response_class=HTMLResponse)
    def neighborhoods(request: Request):
        session = session_only(request)
        if session is None or session.comparison is None:
            return RedirectResponse("/cities", status_code=303)
        return templates.TemplateResponse(
            request,
            "neighborhoods.html",
            ctx(
                request,
                session,
                comparison=session.comparison,
                anchor_version=scoring.ANCHOR_VERSION,
            ),
        )

    # --- structured plan -----------------------------------------------------
    @app.get("/plan", response_class=HTMLResponse)
    def plan(request: Request):
        session = session_only(request)
        if session is None or session.comparison is None:
            return RedirectResponse("/neighborhoods", status_code=303)
        ensure_plan(session, provider)
        return templates.TemplateResponse(
            request,
            "plan.html",
            ctx(request, session, plan=session.plan, followups=session.followups),
        )

    @app.get("/plan/download", response_class=PlainTextResponse)
    def download_plan(request: Request):
        session = session_only(request)
        if session is None or session.comparison is None:
            return RedirectResponse("/neighborhoods", status_code=303)
        plan_model = ensure_plan(session, provider)
        md = markdown.render_plan(plan_model)
        return PlainTextResponse(
            md,
            headers={
                "Content-Disposition": 'attachment; filename="venturelens-plan.md"',
                "Content-Type": "text/markdown",
            },
        )

    @app.post("/followup", response_class=HTMLResponse)
    def followup(
        request: Request,
        question: str = Form(""),
        csrf: str = Form(...),
    ):
        session = session_only(request)
        if session is None or session.comparison is None:
            return RedirectResponse("/neighborhoods", status_code=303)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        question = (question or "").strip()
        if not question:
            return RedirectResponse("/plan", status_code=303)
        if not charge(session, 1):
            return RedirectResponse("/error?reason=budget", status_code=303)
        turn = provider.answer_followup(session, question)
        session.followups.append(turn)
        return RedirectResponse("/plan#followups", status_code=303)

    @app.post("/close", response_class=HTMLResponse)
    def close(request: Request, csrf: str = Form(...)):
        sid = session_id(request)
        session = store.get(sid)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        if sid:
            store.delete(sid)
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(settings.session_cookie_name)
        return response

    @app.post("/new", response_class=HTMLResponse)
    def new_session(request: Request, csrf: str = Form(...)):
        """Discard the current session and return to a fresh prompt composer."""
        sid = session_id(request)
        session = store.get(sid)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        store.delete(sid)
        response = RedirectResponse("/", status_code=303)
        response.delete_cookie(settings.session_cookie_name)
        return response

    @app.get("/error", response_class=HTMLResponse)
    def error_page(request: Request):
        session = session_only(request)
        reason = request.query_params.get("reason", "unknown")
        message = {
            "budget": "This session has used its research allowance. Start a new session to continue.",
        }.get(reason, "Something went wrong. Please try starting over.")
        return templates.TemplateResponse(
            request,
            "error.html",
            ctx(request, session, message=message),
        )

    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    return app


app = create_app()