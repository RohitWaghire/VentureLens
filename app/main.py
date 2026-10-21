"""VentureLens FastAPI application.

Pipeline: user prompt -> one grilling question at a time -> collected answers
-> Qloo places and the model write a report -> presented to the user.

Server-rendered, with an in-memory session store, per-IP rate limiting,
per-session/global research budgets, and cookie/CSRF protections.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import markdown
from app.config import Settings, get_settings
from app.planning import BUDGET, CONFIRM, QUESTION, REPORT, UNAVAILABLE, Planner
from app.providers import get_provider
from app.providers.base import ProviderError
from app.security import RateLimiter, QueryBudget, client_ip, csrf_token, verify_csrf, origin_allowed
from app.sessions import SessionStore

_TEMPLATE_DIR = "app/templates"
_STYLE_PATH = Path(__file__).resolve().parent / "static" / "style.css"
log = logging.getLogger(__name__)

_DISCLOSURE = (
    "Live mode sends your idea, place, and answers to Qloo and to the configured model. "
    "VentureLens keeps them only for this session."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    store = SessionStore(settings.session_max_age_seconds)
    limiter = RateLimiter(settings.rate_limit_per_ip, settings.rate_limit_window_seconds)
    budget = QueryBudget(settings.session_query_budget, settings.global_query_budget)
    provider = get_provider(settings)
    planner = Planner(provider, budget)
    templates = Jinja2Templates(directory=_TEMPLATE_DIR)

    app = FastAPI(title=settings.app_name)

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
        return await call_next(request)

    app.state.store = store
    app.state.budget = budget
    app.state.provider = provider
    app.state.settings = settings

    def session_id(request: Request) -> Optional[str]:
        return request.cookies.get(settings.session_cookie_name)

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
            "disclosure": _DISCLOSURE,
            "css_version": str(int(_STYLE_PATH.stat().st_mtime)) if _STYLE_PATH.exists() else "1",
        }
        base.update(extra)
        return base

    def valid_form_token(session, token: str) -> bool:
        return bool(session and verify_csrf(settings.secret_key, session, token))

    def guarded(action):
        try:
            return redirect_for(action())
        except ProviderError as exc:
            log.warning("live provider failed: %s", exc)
            return redirect_for(UNAVAILABLE)

    def redirect_for(kind: str):
        if kind == BUDGET:
            return RedirectResponse("/error?reason=budget", status_code=303)
        if kind == UNAVAILABLE:
            return RedirectResponse("/error?reason=provider", status_code=303)
        if kind == QUESTION or kind == CONFIRM:
            return RedirectResponse("/grill", status_code=303)
        return RedirectResponse("/report", status_code=303)

    # --- entry ---------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        session = session_only(request) or store.create()
        if session.report is not None:
            return RedirectResponse("/report", status_code=303)
        if session.transcript or session.profile is not None:
            return RedirectResponse("/grill", status_code=303)
        response = templates.TemplateResponse(
            request,
            "landing.html",
            ctx(request, session, error=request.query_params.get("error")),
        )
        set_cookie(response, session)
        return response

    @app.post("/start", response_class=HTMLResponse)
    def start(request: Request, prompt: str = Form(..., max_length=2000), csrf: str = Form(...)):
        prompt = (prompt or "").strip()
        session = session_only(request)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        if not prompt:
            return RedirectResponse("/?error=Please describe your business idea to begin.", status_code=303)
        return redirect_for(planner.start(session, prompt))

    # --- grilling ------------------------------------------------------------
    @app.get("/grill", response_class=HTMLResponse)
    def grill(request: Request):
        session = session_only(request)
        if session is None:
            return RedirectResponse("/", status_code=303)
        if session.report is not None:
            return RedirectResponse("/report", status_code=303)
        try:
            questions = planner.frontier(session)
        except ProviderError as exc:
            log.warning("live provider failed: %s", exc)
            return redirect_for(UNAVAILABLE)
        if not questions:
            return templates.TemplateResponse(
                request,
                "grill.html",
                ctx(request, session, questions=[], confirming=True, transcript=session.transcript),
            )
        return templates.TemplateResponse(
            request,
            "grill.html",
            ctx(
                request,
                session,
                questions=questions,
                confirming=False,
                transcript=session.transcript,
            ),
        )

    @app.post("/grill", response_class=HTMLResponse)
    async def grill_submit(request: Request, csrf: str = Form(...), confirm: str = Form("")):
        session = session_only(request)
        if session is None:
            return RedirectResponse("/", status_code=303)
        if not valid_form_token(session, csrf):
            return PlainTextResponse("Invalid session token. Refresh and try again.", status_code=403)
        if confirm == "1":
            return guarded(lambda: planner.confirm(session))
        form = await request.form()

        def save_answers():
            answers = {}
            for question in planner.frontier(session):
                typed = str(form.get(f"t_{question.id}") or "").strip()
                picked = str(form.get(f"a_{question.id}") or "").strip()
                answers[question.id] = typed or picked
            return planner.record(session, answers)

        return guarded(save_answers)

    # --- report --------------------------------------------------------------
    @app.get("/report", response_class=HTMLResponse)
    def report(request: Request):
        session = session_only(request)
        if session is None:
            return RedirectResponse("/", status_code=303)
        if session.report is None:
            if not session.profile and not session.transcript:
                return RedirectResponse("/", status_code=303)
            kind = planner.ensure_report(session)
            if kind != REPORT:
                return redirect_for(kind)
        return templates.TemplateResponse(
            request,
            "report.html",
            ctx(
                request,
                session,
                report=session.report,
                profile=session.profile,
                transcript=session.transcript,
            ),
        )

    @app.get("/report/download", response_class=PlainTextResponse)
    def download_report(request: Request):
        session = session_only(request)
        if session is None or session.report is None:
            return RedirectResponse("/report", status_code=303)
        md = markdown.render_report(session.report)
        return PlainTextResponse(
            md,
            headers={
                "Content-Disposition": 'attachment; filename="venturelens-report.md"',
                "Content-Type": "text/markdown",
            },
        )

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
        message = {
            "budget": "This session has used its research allowance. Start a new session to continue.",
            "provider": "The taste service or the model did not return a brief. Check the live provider settings and try again.",
        }.get(request.query_params.get("reason", "unknown"), "Something went wrong. Please try starting over.")
        return templates.TemplateResponse(request, "error.html", ctx(request, session, message=message))

    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    return app


app = create_app()