# AGENTS.md — VentureLens

Guidance for AI coding agents working in this repository.

## Project

VentureLens is a server-rendered FastAPI app for evidence-backed small-business
planning (MVP per `PROJECT_PLAN.md`). The default `demo` provider is
deterministic and credential-free so the app and tests run with no external
services.

## Domain vocabulary

Use these terms consistently.

- **Interview** — the one-question-at-a-time flow (`app/interview.py`). Business
  idea and U.S. state/region are required; other answers may be skipped and
  become **assumptions**.
- **Profile** — the confirmed `BusinessProfile` (idea, region, budget, audience,
  concept, price, footprint, competitors, growth).
- **City discovery** — returns three ranked `CityCandidate`s for a region.
- **Comparison** — a `NeighborhoodComparison` of 5–10 neighborhoods in a chosen
  city, plus a three-item **shortlist**.
- **Scorecard** — per-neighborhood five-factor ratings. The overall numeric
  **weighted total** is shown only when every factor is scored; otherwise it is
  **withheld**.
- **Factor / category** — five canonical factors map to `cafe` and `restaurant`
  templates with fixed documented weights (`app/scoring.py`). Unsupported
  categories use the closest template and disclose a proxy.
- **Claim** — a plan statement with optional `citations` (retrieved source
  title+url). Assumptions are flagged.

## Conventions

- Python 3.11+, FastAPI, Pydantic v2, Jinja2 for server rendering.
- Weight arithmetic and rank ordering live in plain code (`app/scoring.py`),
  never produced by the model provider. The model supplies per-factor 1–5
  ratings from cited evidence.
- Citations must come from retrieved or otherwise known source objects; never
  let providers invent URLs. Keep them attached to the claims they support.
- Provider calls happen behind `app.providers.base.Provider` and are charged
  against the session/global budgets at the call site. Do not add providers
  that bypass `app/providers/base.py`.
- Credentials are server-side environment variables only; never send secrets to
  the browser or commit them.
- No user accounts or persistent plan history. In-memory sessions expire server
  side; expired sessions are rejected on every read/write.
- Test externally observable behavior at the FastAPI boundary with the demo
  provider; avoid coupling tests to internal functions. Tests must require no
  live APIs or credentials.

## Commands

- Run the app: `uvicorn app.main:app --reload`
- Run tests: `pytest`
- Install: `pip install -e ".[test]"`
- Config reference: `.env.example`

## Adding a real provider

1. Implement `app.providers.base.Provider`.
2. Register it in `app/providers/__init__.py` by `VL_PROVIDER` name.
3. Charge research in the provider seam and respect configured timeouts.
4. Before enabling livable: review/document what the provider receives
   (retention, training, terms) and add a user disclosure.