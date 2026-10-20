# AGENTS.md — VentureLens

Guidance for AI coding agents working in this repository.

## Project

VentureLens is a server-rendered FastAPI app for evidence-backed small-business
planning (MVP per `PROJECT_PLAN.md`). The default `demo` provider is
deterministic and credential-free so the app and tests run with no external
services.

## Domain vocabulary

Use these terms consistently.

- **Prompt** — the natural-language business idea entered on the landing page.
- **Grilling** — the adaptive question flow. A question (with shortlisted
  answer options) is generated from the prompt and prior answers, instead of a
  fixed questionnaire. Details already stated in the prompt are not re-asked.
- **Transcript** — the ordered list of collected question/answer turns
  (`GrillTurn`), the input to report writing.
- **Profile** — `BusinessProfile` details parsed from the opening prompt
  (idea, budget, region).
- **Report** — the brief the model writes from the transcript; shown to the
  user and downloadable as Markdown.

## Conventions

- Python 3.11+, FastAPI, Pydantic v2, Jinja2 for server rendering.
- Provider calls — dynamic grilling (`first_question`/`next_question`) and
  report writing (`write_report`) — happen behind `app.providers.base.Provider`
  and are charged against the session/global budgets at the call site. Do not
  add providers that bypass `app.providers/base.py`.
- Credentials are server-side environment variables only; never send secrets to
  the browser or commit them.
- No user accounts or persistent history. In-memory sessions expire server
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

## Rules

| Rule | Enforced by |
| --- | --- |
| Place insights ask for places of a confirmed category. The tag id starts with `urn:tag:category:place:` and is sent as `filter.tags`. An interest signal (`signal.interests.*`) is a different question and is rejected. A location with no category tag is not an insights call. | `place_insights_params` and `LiveProvider._qloo_get` in `app/providers/live.py`. `tests/test_live_provider.py` (`test_interest_signal_request_is_rejected`, `test_genre_tag_is_not_a_place_category_filter`). |
