# VentureLens

> **A clearer view of where to grow.**

An evidence-backed small-business planning app. A founder describes a business
idea and a U.S. region, answers a short adaptive interview, then gets three
ranked candidate cities, a neighborhood comparison, and a downloadable business
plan with clickable source citations inline.

> **Status:** Hackathon MVP scaffold. The app runs end-to-end now using a
> deterministic, credential-free **demo provider**. Real LLM / web-search /
> Qloo adapters are wired behind a replaceable seam but are not yet configured
> (see [Provider seam](#provider-seam)).

## Key behaviors

- **Prompt-first entry** — start with a natural-language business idea in a
  centered composer, then continue into the guided one-question-at-a-time
  planning interview. Example prompts can prefill the composer.
- **Interview completion transition** — a reduced-motion-aware orb-inspired
  animation marks profile completion and hands off to profile review; it does
  not claim that live research has run.
- **Adaptive interview** — one question at a time. A business idea and a U.S.
  state/region are required; every other question may be skipped and becomes a
  labeled assumption.
- **City discovery** — three ranked candidate cities from the chosen region;
  the user selects, requests alternatives, or enters a city (validated against
  the region).
- **Neighborhood comparison** — 5–10 neighborhoods scored on 5 factors using
  fixed category weights (cafés and restaurants), with a shortlist of three.
- **Scorecard honesty** — if any factor lacks evidence, the overall numeric fit
  score is **withheld**, not estimated. Rubric anchors are versioned.
- **Business plan + Markdown export** — audience, concept/positioning, location
  comparison, recommendations, assumptions, risks, and next steps, with inline
  source-title links.
- **Follow-up chat** — may trigger new research automatically, but answers only
  appear in chat; they never mutate the downloadable plan.
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
| `VL_LLM_*`, `VL_SEARCH_*`, `VL_QLOO_*` | Optional real-provider credentials. |

## Architecture

- **`app/main.py`** — FastAPI app, server-rendered UI, routes, safety middleware.
- **`app/interview.py`** — explicit interview state machine and required gates.
- **`app/scoring.py`** — category templates, weights, versioned 1–5 rubric
  anchors, weighted-total arithmetic, ordering rule.
- **`app/sessions.py`** / **`app/security.py`** — session store, rate limiting,
  budgets, CSRF/origin and IP handling.
- **`app/providers/`** — the adapter seam (`base.Provider`) and the default
  demo provider (`demo.DemoProvider`).
- **`app/model.py`** — pydantic models for profile, candidates, scorecards, plan.
- **`app/markdown.py`** / **`app/plan_builder.py`** — Markdown export and plan
  assembly.
- **`app/templates/`** + **`app/static/`** — server-rendered pages and styles.

### Provider seam

The app depends on `app.providers.base.Provider` only. The `demo` provider is
deterministic and credential-free so the app and tests run anywhere. Real
LLM/web-search/Qloo adapters implement the same interface and are registered in
`app/providers/__init__.py` behind `VL_PROVIDER`. Before enabling live
providers, review and disclose what each provider receives (retention,
training, terms) per the plan.

## Demo data disclaimer

The demo provider ships placeholder research data and stable fake sources so the
flow is fully testable. It is **not** real market data. Do not present it as such
in a public demo.

## Testing

`pytest` (all tests require no live services):

- `tests/test_scoring.py` — weights, anchors, withheld totals, ordering.
- `tests/test_interview.py` — required gates, skips, assumptions.
- `tests/test_security.py` — rate limit, budgets, CSRF, origin, IP.
- `tests/test_provider_contract.py` — demo provider behaviors.
- `tests/test_citations.py` — citations from retrieved sources; survive export.
- `tests/test_export.py` — Markdown export; follow-up isolation.
- `tests/test_workflow.py` — end-to-end user journey through FastAPI.

## Plan

See `PROJECT_PLAN.md` for the full phased plan, accepted scope, test seams,
risks, and intentionally deferred decisions (provider selection, hosting,
ranking eligibility details).