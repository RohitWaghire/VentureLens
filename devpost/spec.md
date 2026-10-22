---
doc: spec
status: draft
---

# VentureLens — Technical Spec

## How This Works, In Plain Language
The app is one Python web server. Pages are rendered on the server, not as a separate frontend app. A session in memory holds the idea, the questions and answers, and the brief. A provider sits behind one seam. The live provider asks the model to name a place category, asks Qloo for places of that category, and asks the model to write the brief. Tests inject a fake transport and need no keys. The browser never receives API keys.

This shape is the discovery dialogue's "one FastAPI app with a replaceable provider," kept smaller than city and neighborhood research.

## The Core Journey Through the System
PRD ref: `prd.md > The Core Journey`.

1. The browser requests `/`. FastAPI renders the landing page and sets a session cookie.
2. The founder submits the prompt to `/start`. The server checks the session token, stores the idea, and asks the provider for the first round of questions.
3. `/grill` shows one question. Each answer is posted back to `/grill` and appended to the transcript. The next question is chosen from the idea and the transcript.
4. When the provider has no further question, `/grill` asks for confirmation. Posting that confirmation calls the provider to write the brief.
5. `/report` renders the brief. `/report/download` returns the same brief as Markdown. `/new` drops the session and returns to `/`.

## Stack
- Python 3.11+. The language the discovery dialogue chose for one server-rendered app.
- FastAPI, the web framework. Documentation: https://fastapi.tiangolo.com/
- Uvicorn, the server that runs it. Documentation: https://www.uvicorn.org/
- Jinja2, the page templates. Documentation: https://jinja.palletsprojects.com/
- Pydantic v2, the shapes for the profile, questions, transcript, and brief. Documentation: https://docs.pydantic.dev/
- pytest and httpx, for tests through the HTTP boundary. Documentation: https://docs.pytest.org/
- No frontend framework. Styling is one CSS file. That matches the dialogue's "lightweight server-rendered interface."

Versions are the minimums in `pyproject.toml` (`fastapi>=0.110`, `uvicorn>=0.29`, `jinja2>=3.1`, `pydantic>=2.6`, `pytest>=8`).

## Where It Runs and How Someone Tries It
It runs as a local web server. The demo recording can be a screen recording of that server. Deployment is optional and is not a substitute for the video or the public repository.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[test]"
uvicorn app.main:app --reload
pytest
```

Open http://127.0.0.1:8000/ and use: "I have $250k and want to open a specialty coffee shop in Illinois."

No API key is required for that demo. Live mode reads server environment variables documented in `.env.example`. Real values stay in `.env`, which is gitignored.

## Look and Feel
Carried from `prd.md > Look and Feel` and `scope.md > Inspiration & Identity`.
Pale landscape, dark glass panels (`rgba(0, 0, 0, 0.24)` with a white 15% border and a 14px blur), black pill buttons, Fustat titles, Schibsted Grotesk interface text. The brief is one pale card (`rgba(255, 255, 255, 0.9)`, 18px radius). Jinja templates and one stylesheet can honor this. There is no component library to fight it.

## Components

### Pages
`app/templates/` renders landing, grilling, the brief, and errors. `app/static/style.css` is the only stylesheet.
PRD ref: `prd.md > Screens and Layout`.

### Session and safety
`app/sessions.py` keeps the in-memory session and expiry. `app/security.py` checks the session token, origin, rate limit, and query budget.
PRD ref: `prd.md > Session safety`.

### Planning loop
`app/planning.py` moves a session from the prompt, to a question, to confirm, to the brief. `app/providers/grilling.py` parses the opening prompt. The model chooses the next question.
PRD ref: `prd.md > Grilling` and `prd.md > Confirm and brief`.

### Providers
`app/providers/base.py` is the seam. `live.py` is the only adapter. The model names the place category, Qloo is queried for that category, and the model writes the brief. `VL_PROVIDER` is ignored.
PRD ref: `prd.md > Product Decisions`.

### Brief export
`app/markdown.py` turns the brief into the download. `app/model.py` holds the data shapes.
PRD ref: `prd.md > Confirm and brief`.

## Data Model
All of this lives on the server session, not in a database.

- Profile: idea, budget, and region parsed from the opening prompt.
- Transcript: ordered question and answer turns.
- Brief: title, summary, sections, and an optional caveat.
- Leaving and coming back later does not restore it. Expiry or "new idea" deletes it.

## File Structure

```
VentureLens/
├── app/
│   ├── main.py              # routes
│   ├── planning.py          # prompt → question → confirm → brief
│   ├── sessions.py          # in-memory session
│   ├── security.py          # token, origin, rate limit, budget
│   ├── config.py            # environment variables
│   ├── model.py             # data shapes
│   ├── markdown.py          # download
│   ├── providers/
│   │   ├── base.py          # provider seam
│   │   ├── live.py          # model, then Qloo, then the brief
│   │   ├── grilling.py      # opening-prompt parsing
│   │   └── data.py          # U.S. state names used by the parser
│   ├── templates/           # landing, grill, report, error
│   └── static/style.css
├── tests/                   # HTTP-boundary tests, no live APIs
├── devpost/                 # learning docs; learner profile is gitignored
├── PROJECT_PLAN.md          # original discovery dialogue
├── .env.example             # names only, no secrets
└── pyproject.toml
```

## External Services and Dependencies
The running app calls both services. Tests do not.

- Qloo. Hackathon base URL `https://hackathon.api.qloo.com`. The model names a place category. The server searches `/v2/tags` for that phrase, keeps a tag whose id starts with `urn:tag:category:place:`, and sends it to `/v2/insights` with the city. Header `X-Api-Key` from `VL_QLOO_API_KEY`. Documentation is the hackathon kit the discovery dialogue named, not a CLI.
- An OpenAI-compatible chat completion. The model grills, names the Qloo category, and writes the brief. `VL_LLM_API_KEY`, `VL_LLM_BASE_URL`, and `VL_LLM_MODEL`. The key stays on the server. GPT-6 Luna is the configured model.

Timeouts and the session and global query budgets bound cost. Exact vendor prices were left open in the discovery dialogue and are still unset.

## Important Failure Modes

- **Qloo or the model cannot be reached, or the key is refused** → the brief says Qloo could not be reached, or the app shows the provider error. A failed category lookup and a failed place request are said separately from an empty place list. Keys are not shown.
- **The research budget is spent** → the founder sees a budget message instead of a hung request.
- **The session expired** → the next click returns them to the start. Nothing is saved.

## What Was Simplified and Why

- **No demo provider.** The build dialogue started with a credential-free demo. The app now always uses the live provider. Tests inject a fake transport, so they still need no keys. A public demo needs credentials and vendor terms.
- **Prose brief** instead of the discovery dialogue's neighborhood scorecard — the build dialogue removed the scorecard so missing evidence would not become a number.
- **In-memory sessions** instead of a database — the discovery dialogue already cut accounts and saved plans. A database would add persistence the product refused.

## Decisions and Open Issues
The learner chose, in the discovery dialogue, one Python server, no accounts, Qloo as an aggregate signal, and a downloadable brief. The build dialogue dropped the scorecard. The live model is GPT-6 Luna, and it mediates Qloo: it names the place category, then writes the brief from the places Qloo returns. An agent assumption is not attributed beyond that.

One uncertainty the discovery dialogue left open, and that is still open: Qloo's retention terms before a public demo sends real ideas to that service. Check `.env.example` and the provider's terms before a public demo.

Carried from `prd.md > Open Questions`: city and neighborhood research stays deferred. No spec work should start it unless the scope is reopened.
