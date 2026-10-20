# VentureLens

> **A clearer view of where to grow.**

An evidence-backed small-business planning app. The user gives a natural-language
prompt, an adaptive grilling session asks a small number of questions with
shortlisted answer options, and the model writes a report that is presented to
the user (and can be downloaded as Markdown).

> **Status:** Hackathon MVP. The grilling pipeline runs end-to-end now using a
> deterministic, credential-free **demo provider**. A real LLM (and Qloo data)
> is wired behind a replaceable seam but is not yet configured — see the
> [Provider seam](#provider-seam).

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
| `VL_PROVIDER` | Adapter to use (`demo` is the default; no credentials). |
| `VL_SESSION_MAX_AGE_SECONDS` | Server-side session lifetime fallback. |
| `VL_RATE_LIMIT_PER_IP` | Per-IP requests per window. |
| `VL_SESSION_QUERY_BUDGET` / `VL_GLOBAL_QUERY_BUDGET` | Research budget caps. |
| `VL_TRUSTED_PROXIES` | Proxy allowlist whose `X-Forwarded-For` is trusted. |
| `VL_ALLOWED_ORIGINS` | Origin allowlist for state-changing requests. |
| `VL_COOKIE_SECURE` | Enable when serving over HTTPS. |
| `VL_LLM_*`, `VL_QLOO_*` | Live provider only. Ignored while `VL_PROVIDER=demo`. |

## Architecture

- **`app/main.py`** — FastAPI app, server-rendered UI, and the grilling/report
  routes (`/`, `/start`, `/grill`, `/report`, `/report/download`, `/new`,
  `/close`).
- **`app/providers/`** — the adapter seam (`base.Provider`) and the default
  demo provider (`demo.DemoProvider`). `first_question`/`next_question` drive
  dynamic grilling; `write_report` produces the brief.
- **`app/sessions.py`** / **`app/security.py`** — session store, rate limiting,
  budgets, CSRF/origin and IP handling.
- **`app/model.py`** — pydantic models for the profile, grilling questions,
  the transcript, and the report.
- **`app/markdown.py`** — renders the report to Markdown for download.
- **`app/templates/`** + **`app/static/`** — server-rendered pages and styles.

### Provider seam

The app depends on `app.providers.base.Provider` only. The `demo` provider is
deterministic and credential-free so the app and tests run anywhere. A real
adapter implements the same interface — dynamic grilling and report writing via
an LLM, combined with Qloo data — and is registered in
`app/providers/__init__.py` behind `VL_PROVIDER`. Before enabling live
providers, review and disclose what each provider receives (retention,
training, terms).

## Demo note

The demo provider generates questions and reports deterministically. It is a
stand-in for a real LLM + Qloo integration, not real research or analysis. Do
not present it as such in a public demo.

## Testing

`pytest` (all tests require no live services):

- `tests/test_workflow.py` — end-to-end grilling pipeline through FastAPI
  (prompt → dynamic questions → report → download), CSRF, and budget caps.
- `tests/test_provider_contract.py` — demo provider grilling + report behavior.
- `tests/test_export.py` — Markdown report export.
- `tests/test_security.py` — rate limit, budgets, CSRF, origin, IP.

## Plan

`PROJECT_PLAN.md` records the original scope. The pipeline described here —
prompt → grilling → collect → model writes a report — is the current, leaner
implementation; sizeable parts of the original plan (city/neighborhood scoring)
are intentionally out of scope now.