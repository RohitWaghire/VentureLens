# VentureLens

> **A clearer view of where to grow.**

An evidence-backed small-business planning app. The user gives a natural-language
prompt, an adaptive grilling session asks a small number of questions with
shortlisted answer options, and the model writes a report that is presented to
the user (and can be downloaded as Markdown).

> **Status:** Hackathon MVP. Grilling questions come from the configured model,
> one at a time. The brief uses those answers and Qloo places. Both keys are required.

## Key behaviors

- **Prompt-first entry** — start with a natural-language business idea in a
  centered composer.
- **Dynamic grilling** — instead of a fixed questionnaire, a question is
  generated from the prompt and prior answers, with shortlisted answer options
  (this mirrors the "grilling" approach). Details already stated in the prompt
  (e.g., budget, region) are not re-asked.
- **Report** — the collected answers are handed to the model, which writes a
  business brief presented to the user and downloadable as Markdown.
- **Public-demo safety** — no accounts; in-memory sessions that expire server
  side; per-IP rate limiting; per-session and global research budgets; secure
  cookies; origin/CSRF protections.

## Quickstart

```bash
# Create and use the virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install
pip install -e ".[test]"

# Run
uvicorn app.main:app --reload

# Test
pytest
```

Open <http://127.0.0.1:8000/> and walk the coffee-shop demo prompt:
`I have $250k and want to open a specialty coffee shop in Illinois.`

## Configuration

All configuration comes from environment variables (see `.env.example`). Never
commit a real secret. Key knobs:

| Variable | Purpose |
| --- | --- |
| `VL_SECRET_KEY` | Signs CSRF tokens. Set a strong random value before deploy. |
| `VL_SESSION_MAX_AGE_SECONDS` | Server-side session lifetime fallback. |
| `VL_RATE_LIMIT_PER_IP` | Per-IP requests per window. |
| `VL_SESSION_QUERY_BUDGET` / `VL_GLOBAL_QUERY_BUDGET` | Research budget caps. |
| `VL_TRUSTED_PROXIES` | Proxy allowlist whose `X-Forwarded-For` is trusted. |
| `VL_ALLOWED_ORIGINS` | Origin allowlist for state-changing requests. |
| `VL_COOKIE_SECURE` | Enable when serving over HTTPS. |
| `VL_LLM_*`, `VL_QLOO_*` | Model and Qloo credentials. Required. |

## Deploy

The public demo is one free Render web service, defined in `render.yaml`.
Keep it at one instance. Render stops that process after 15 minutes without
a visitor. The next open takes about a minute while Render starts it again,
and the new process has an empty session, so that visit begins at the landing
page. A walk-through that stays active keeps the same process, and the
questions and brief remain available. The research budget also starts over
when the process starts over.

Render checks `GET /health`. Render sets `RENDER_EXTERNAL_URL`, and the app
adds that origin to the allowlist. The blueprint turns on `VL_COOKIE_SECURE`
and sets `VL_GLOBAL_QUERY_BUDGET` to 400 for one running process. Render
generates `VL_SECRET_KEY`. Set `VL_QLOO_API_KEY` and `VL_LLM_API_KEY` in the
Render dashboard. Leave `VL_TRUSTED_PROXIES` empty.

A redeploy also starts a new process and drops in-memory sessions. Delete or
suspend the service after November 5, 2026, when Qloo judging ends.

### Note for judges

VentureLens is hosted on Render’s free tier. If nobody has opened it for
about 15 minutes, the first visit takes about a minute while the app starts.
Render shows its own loading page during that wait. Wait until the
VentureLens page appears, then begin. That start is a fresh session. Once
the page is up, continue through the questions; a pause longer than 15
minutes returns you to the beginning.

## Architecture

- **`app/main.py`** — FastAPI app, server-rendered UI, and the grilling/report
  routes (`/`, `/health`, `/start`, `/grill`, `/report`, `/report/download`,
  `/new`, `/close`).
- **`app/providers/`** — the live provider. The model asks the next question.
  `write_report` asks the model to name a place category, asks Qloo for places
  of that category, then asks the model to write the brief.
- **`app/sessions.py`** / **`app/security.py`** — session store, rate limiting,
  budgets, CSRF/origin and IP handling.
- **`app/model.py`** — pydantic models for the profile, grilling questions,
  the transcript, and the report.
- **`app/markdown.py`** — renders the report to Markdown for download.
- **`app/templates/`** + **`app/static/`** — server-rendered pages and styles.

### Provider seam

The app depends on `app.providers.base.Provider`. `LiveProvider` is the only
adapter. Tests replace its HTTP transport. Review and disclose what Qloo and
the model receive (retention, training, terms) before a public demo.

## Testing

`pytest` (all tests require no live services):

- `tests/test_workflow.py` — end-to-end grilling pipeline through FastAPI
  (prompt → dynamic questions → report → download), CSRF, and budget caps.
- `tests/test_provider_contract.py` — opening-prompt parsing.
- `tests/test_export.py` — Markdown report export.
- `tests/test_security.py` — rate limit, budgets, CSRF, origin, IP.

## Devpost Learn skills

The Build With AI Basics skill pack lives in `.agents/skills/` (`1-start` through `6-ship`), locked in `skills-lock.json`. `.claude/skills` points at those same folders. Personal learning notes stay out of git via `/devpost/learner-profile.md` in `.gitignore`. Planning docs the pack writes (`devpost/scope.md`, `devpost/prd.md`, `devpost/spec.md`) belong in the repo once they are approved.

## Plan

`PROJECT_PLAN.md` records the original scope. The pipeline described here —
prompt → grilling → collect → model writes a report — is the current, leaner
implementation; sizeable parts of the original plan (city/neighborhood scoring)
are intentionally out of scope now.