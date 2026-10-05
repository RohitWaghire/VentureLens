# VentureLens — Project Plan

> **A clearer view of where to grow.**

**Status:** Product direction captured; implementation has not started  
**Purpose:** Hackathon MVP plan based on the product-discovery conversation  
**Working project directory:** `D:\Hackathon Projects\VentureLens`

## 1. Product Goal

**Project name:** VentureLens  
**Tagline:** “A clearer view of where to grow.”

Build a publicly accessible web app that helps a founder or small-business owner explore a business idea through an adaptive interview, evidence-backed market research, and a downloadable business plan. The first demo scenario is opening a specialty coffee shop. The product should support other small businesses conceptually, while the first location-scorecard templates are limited to cafés/coffee shops and restaurants.

The agent should make its reasoning inspectable: cite web evidence next to claims, disclose assumptions and weak evidence, and avoid producing an overall numeric fit score when any required factor cannot be scored.

## 2. Agreed MVP Scope

### User journey

1. The user describes a business idea and supplies a U.S. state or region. These are required to begin market discovery. A sample opening prompt is: “I have $250k and want to open a specialty coffee shop in Illinois.”
2. The agent conducts an adaptive, one-question-at-a-time interview. Questions depend on previous answers and may cover budget, target customer, concept, price point, footprint, competitors, and growth goals. Users may skip optional interview questions; resulting unknowns and assumptions must be labeled. The agent must obtain a business idea and U.S. state/region before city discovery.
3. The agent summarizes its understanding. The user may correct it or skip confirmation and proceed.
4. The agent researches within the user-provided state or region and returns three ranked candidate cities with reasons.
5. The user chooses a city, requests three alternatives from the same region, or enters another city. Validate a manually entered city against the selected U.S. state/region; if it is outside that area, ask the user to correct it or explicitly restart with a new region before researching neighborhoods.
6. After a city is selected, the agent discovers 5–10 candidate neighborhoods, compares them, and recommends a shortlist of three.
7. The app presents a structured plan and lets the user download it as Markdown.
8. The user may continue asking follow-up questions. The agent may initiate additional web and Qloo research automatically when needed. Follow-up findings appear in chat only and do not revise or replace the original downloadable plan.

### Business-plan contents

- Target audience and audience-fit insights.
- Business concept and positioning recommendations.
- Candidate-city rationale and neighborhood comparison.
- A transparent neighborhood scorecard, where supported by evidence.
- Recommendations, assumptions, risks, and practical next steps.
- Clickable source-title links attached inline to relevant claims; no separate bibliography.

Pricing guidance is out of scope for the MVP. Competitor findings are limited to the neighborhood competition/saturation scorecard factor; there is no standalone competitor-analysis section.

### Neighborhood scorecards

Use predefined, documented factor templates for cafés/coffee shops and restaurants. The product may conduct the broader interview and produce a general plan for other small-business ideas, but any neighborhood scorecard for an unsupported business category is only a proxy: select and disclose the closest matching template, and leave factors unavailable when the proxy or evidence is not appropriate. The templates use these factors, with category-specific interpretation:

1. Audience fit.
2. Competition/saturation.
3. Affordability.
4. Accessibility and foot traffic (restaurant interpretation may include delivery access).
5. Neighborhood momentum.

Each factor receives an LLM-assigned score from 1–5 using fixed evidence-based anchors and cited research. Application code applies the documented fixed weights to calculate a weighted total:

| Factor | Café / coffee shop | Restaurant |
| --- | ---: | ---: |
| Audience fit | 25% | 25% |
| Competition / saturation | 20% | 25% |
| Affordability | 15% | 15% |
| Accessibility / foot traffic (including restaurant delivery access where relevant) | 25% | 20% |
| Neighborhood momentum | 15% | 15% |

These are starting heuristics, not empirically validated weights; document them as such and leave calibration for later. If any factor is unavailable because evidence is insufficient, withhold the overall numeric score and show the available factor ratings and evidence instead. Do not fabricate missing evidence or scores.

**Scoring detail to resolve before implementing ranking:** the conversation also called for showing relative rank separately. Define a defensible ordering rule for candidates with incomplete factors; do not imply that incomplete candidates have directly comparable numeric totals. Version and document the fixed 1–5 rubric anchors before implementing score generation.

## 3. Proposed Architecture

- **Application:** One Python application using FastAPI, serving a lightweight server-rendered web interface and backend endpoints.
- **Agent control flow:** A small, explicit, linear orchestration loop inspired by mini-SWE-agent's simplicity. Keep conversation/history transitions inspectable. Do not import its shell-based software-engineering tools or give this business agent unrestricted shell access.
- **Model:** One deployment-configured LLM provider, selected during implementation according to available credentials and API compatibility. Keep the integration boundary replaceable so another provider can be added later. The model handles the interview, structured evidence interpretation, factor ratings, and written synthesis.
- **Qloo:** Call Qloo directly from the server for relevant cultural and audience-affinity signals. Treat those as aggregate signals, not proof about individuals or guaranteed business outcomes. Use the Qloo Hackathon Kit as an API/workflow reference, not as a required CLI or MCP runtime.
- **Public research:** Use one server-configured web-search API/provider for cited evidence. Select the provider during implementation based on availability and cost. Attach clickable source-title links to claims in the generated plan.
- **Scoring:** Keep weight application and weighted-total calculation in ordinary application code. The LLM assigns per-factor 1–5 ratings from cited evidence according to fixed anchors. Reject malformed model output and never convert insufficient evidence into a numeric rating.
- **Session state:** No user accounts or persistent plan history. Keep interview, plan, and follow-up data only for the active session. Request deletion on tab/window close when possible and enforce a server-side maximum session lifetime as a cleanup fallback; check expiry on every session read/write, rather than relying only on background cleanup. Keep API credentials in server-side environment variables, never in browser code.
- **Public-demo safeguards:** Add basic per-IP rate limiting and server-side request/time limits to protect provider quotas and bound work. Trust forwarded client IP headers only from explicitly configured hosting proxies.
- **Progress UI:** Use the agreed simple loading indicator during research; show the completed result when ready.
- **Export:** Download the original generated plan as Markdown. Follow-up chat must not mutate the exported plan.

The project directory currently has no repository, code, project instructions, ADRs, test suite, deployment configuration, or issue-tracker setup. The implementation should first bootstrap a repository and record project-specific decisions in it.

## 4. Phased Implementation Plan

### Phase 0 — Bootstrap and integration decisions

**Work**

- Initialize a Git repository and a small Python/FastAPI project with a server-rendered page.
- Add project instructions, environment-variable documentation, and a clear local run/test workflow.
- Choose the initial LLM provider, web-search provider, Qloo API access pattern/endpoints, session store/cleanup mechanism, and hosting target based on available credentials, API terms, cost, and deployment constraints.
- Before sending business details to providers, document what data each provider receives and verify its retention, model-training, and usage terms. Define the user-facing disclosure and do not use a provider whose terms conflict with the session-data expectations.
- Define structured request/response contracts for model, Qloo, and search integrations; keep provider calls behind replaceable adapters.
- Confirm how incomplete scorecards affect relative ordering, while preserving the rule to withhold the overall numeric total if any factor is unscored.

**Acceptance checkpoint**

- A new contributor can install dependencies, run the app locally, and run tests using documented commands.
- Provider selection and secrets are configurable server-side; no secret is committed or sent to the browser.
- The intended public demo hosting target supports the Python app and required server-side configuration.
- Provider data handling and retention terms have been reviewed and disclosed before user business details are sent to external services.
- The business idea and U.S. state/region are validated as required inputs for market discovery; optional interview answers may be skipped.

### Phase 1 — App shell, session lifecycle, and safety limits

**Work**

- Build the server-rendered FastAPI interface for the chat flow, loading state, results, follow-up chat, and Markdown download.
- Implement session creation, scoped state, best-effort close cleanup, and server-side expiry fallback.
- Use opaque unpredictable session identifiers, secure `Secure`/`HttpOnly`/`SameSite` cookies, and CSRF/origin protections for state-changing requests.
- Add per-IP rate limiting, request-size limits, and bounded timeouts for agent and external-provider calls.
- Add per-session and global research/query budgets so public traffic has a bounded provider-cost ceiling, with a clear user-facing response when a budget is reached.
- Ensure errors from providers are handled without exposing keys or leaking internal traces to public users.

**Acceptance checkpoint**

- A user can start a session without an account and receive isolated session state.
- Session cleanup is triggered on close where possible; expired sessions are rejected on every read/write and deleted by the configured server-side expiry mechanism.
- Rate/time limits produce understandable user-facing errors and do not expose secrets.

### Phase 2 — Adaptive interview and business-profile confirmation

**Work**

- Implement the one-question-at-a-time interview as explicit application state transitions.
- Capture the idea, budget, audience, concept, price point, footprint, region, competitors, and growth goals when relevant.
- Allow optional answers to be skipped and preserve them as labeled unknowns/assumptions rather than silently filling them in. Require a business idea and U.S. state/region before starting city discovery.
- Present the profile summary with edit/correct and skip-to-research actions.

**Acceptance checkpoint**

- Each response leads to an appropriate next question or completion of intake.
- Skipping optional answers does not block progress; the business idea and U.S. state/region remain required before city discovery. Skipped optional answers result in visible, labeled assumptions.
- The user can correct the summary or bypass confirmation.

### Phase 3 — City discovery and user selection

**Work**

- Search within the submitted U.S. state or region for candidate cities relevant to the business profile.
- Use public evidence and Qloo audience/cultural signals where relevant; clearly separate cited facts from model-generated synthesis.
- Return three ranked city candidates with concise rationales and source-title citations.
- Support selecting a candidate, requesting three alternatives from the same region, or entering another city in the region.

**Acceptance checkpoint**

- The app does not begin neighborhood research until the user selects/confirms a city.
- A manually entered city outside the selected region is rejected with a correction/restart choice; no neighborhood research proceeds under a mismatched region.
- Research-derived factual claims have inline clickable citations; unsupported claims are labeled as assumptions/inferences or omitted, not presented as sourced facts.
- Citation tests verify that displayed citations use retrieved source URLs, remain attached to the claims they support, and survive Markdown export.
- Failures or weak coverage are disclosed instead of being represented as confident findings.

### Phase 4 — Neighborhood discovery, evidence, and scorecards

**Work**

- Discover 5–10 candidate neighborhoods in the selected city.
- Retrieve evidence for the five category-specific factors, using Qloo for relevant aggregate audience/cultural signals and web research for other evidence.
- Define and version fixed 1–5 rubric anchors before score generation; require structured model output that includes factor score or unavailable, rationale, citations, and uncertainty.
- Validate model output and calculate the weighted total in application code only when every required factor is scored.
- Rank/shortlist three neighborhoods under the documented comparison rule, which must define eligibility and ties when evidence is incomplete; display factor-level evidence and uncertainty.
- Disclose when the closest category template is being used.

**Acceptance checkpoint**

- Both café and restaurant templates use their documented starting weights and factor interpretations.
- An unavailable factor suppresses the overall numeric score; no missing value is silently imputed.
- Every displayed factor rating has evidence and rationale, or is explicitly marked unavailable.
- The shortlist contains three candidates when enough comparable evidence exists; otherwise the app explains the limitation. No overall numeric score is shown if any factor is unavailable.

### Phase 5 — Plan synthesis, Markdown export, and follow-up research

**Work**

- Synthesize the interview and city/neighborhood findings into a structured plan covering audience, concept/positioning, location comparison, assumptions, risks, recommendations, and next steps.
- Place clickable source-title links inline on the relevant claims; do not add a separate source list.
- Provide a downloadable Markdown version that preserves those links and scorecard limitations.
- Add follow-up chat that can autonomously call web search and Qloo again when needed.
- Keep follow-up answers in chat only; preserve the original plan and download unchanged.

**Acceptance checkpoint**

- The plan follows the agreed scope and omits pricing guidance and a standalone competitor report.
- Markdown download matches the original displayed plan and contains inline source links.
- Follow-up questions can produce newly researched chat answers without changing the report/download.

### Phase 6 — End-to-end validation and public demo readiness

**Work**

- Complete user-visible workflow tests through the FastAPI boundary using fake model, Qloo, and search clients.
- Separately test score weighting, missing-factor behavior, category-template selection, and score validation.
- Test session expiry, cookie and CSRF/origin protections, rate limits and query budgets, provider failures/timeouts, citation-to-claim integrity, follow-up isolation, and Markdown export.
- Run a full coffee-shop demo scenario using configured test/staging credentials, then deploy the public demo.
- Document setup, required credentials, provider costs/limits, known data gaps, and demo operation.

**Acceptance checkpoint**

- Automated tests do not require live external APIs or provider credentials.
- Critical user journeys pass with deterministic fake provider responses.
- A live demo completes the interview → city choice → neighborhood comparison → plan download → follow-up flow.
- Public demo credentials remain server-side and usage limits are active.

## 5. Testing Strategy

Test externally observable behavior at the highest practical seam:

1. **FastAPI workflow integration tests:** Drive the user-facing flow through the app boundary with scripted fake LLM, Qloo, and web-search clients. Verify interview progression, city selection gates, neighborhood result rendering, plan creation, follow-up behavior, and export.
2. **Scoring rule tests:** Independently verify category template selection, fixed weights, 1–5 input validation, weighted totals, and suppression of the total when any factor is unavailable.
3. **Session/security behavior tests:** Verify isolation, opaque session IDs, secure cookie attributes, CSRF/origin protections, close-triggered best-effort cleanup, server-side expiry, trusted-proxy-aware per-IP limits, query budgets, timeout handling, and that no secret is returned to the client.
4. **Provider contract tests:** Test adapter handling of representative success, partial data, malformed responses, rate limits, and timeouts without relying on live services.

The repository is currently empty, so there is no existing test prior art. These seams are approved product decisions and should be implemented before adding lower-level tests that couple to internal functions.

## 6. Main Risks and Mitigations

- **Qloo access and endpoint fit:** Confirm actual event credentials, allowed usage, rate limits, and relevant endpoints early. Keep integration server-side and isolate it behind an adapter.
- **Sparse/uneven local data:** Neighborhood-level evidence may vary. Mark unavailable factors and withhold the total rather than fabricate values; explain when three comparable recommendations cannot be supported.
- **LLM false precision:** Use fixed score anchors, require citations and rationale, validate structured responses, and keep weighted arithmetic in application code.
- **Score comparability and incomplete data:** Define candidate eligibility and relative ordering when factors are unavailable before implementing ranking. Never show a weighted total under the agreed missing-factor condition.
- **Sensitive session content and provider retention:** Business budgets and plans may be sensitive. Document which data is sent to LLM, search, and Qloo providers and review their terms/retention; exclude session content and secrets from application logs and analytics, and do not promise deletion from third-party systems unless verified.
- **Proxy-aware rate limiting:** Behind a hosting proxy, incorrect forwarded-IP handling can defeat or misapply per-IP limits. Trust forwarding headers only from configured proxies and verify limits on the deployed request path.
- **Unbounded provider spend:** Per-IP limits alone may not prevent high aggregate search/model usage. Enforce per-session and global query/cost budgets before public launch and define graceful behavior when exhausted.
- **Broad research scope and latency/cost:** The user-selected region may be large and follow-ups may trigger additional research. Set implementation-time search/query budgets, provider timeouts, request limits, and rate limits without changing the agreed user flow.
- **Session close reliability:** Browser close events can be missed. Treat close deletion as best effort and rely on server-side maximum lifetime for guaranteed cleanup.
- **Public API quota abuse:** Apply per-IP throttling, request/time caps, and safe error handling before opening the demo publicly.
- **Citation integrity:** Preserve source identity from retrieval through model synthesis and Markdown export; do not let the model invent URLs or attach unrelated citations.
- **Unvalidated weights:** Clearly describe initial weights as heuristics. Do not present them as empirically proven business-success predictors.

## 7. Explicitly Out of Scope

- Pricing recommendations in the MVP.
- A standalone competitor landscape/report section.
- Storefront/address-level property discovery.
- User accounts, saved plans, or persistent plan history.
- Editing or regenerating the original report through follow-up chat.
- User-adjustable scorecard weights.
- International market coverage.
- Scorecard templates beyond cafés/coffee shops and restaurants (other ideas use the closest template, disclosed).
- A Qloo CLI/MCP runtime dependency or mini-SWE-agent shell/software-engineering tools.
- Any claim that aggregate taste affinities prove individual preferences, demand, profitability, or business success.

## 8. Decisions Intentionally Deferred

Choose these during Phase 0 rather than guessing now:

- Initial LLM provider/model and corresponding structured-output capabilities.
- Web-search API/provider and its citation/result limits.
- Exact Qloo endpoints/workflows, credentials, terms, and handling/retention of returned data.
- Hosting platform, session store, and practical tab-close cleanup mechanism.
- Search-depth/query budgets for city and neighborhood discovery.
- The exact relative-ranking eligibility/tie-break rule when evidence coverage is incomplete (must be settled before ranking implementation).
- Specific 1–5 rubric anchor wording and any later calibration process (must be versioned before score-generation implementation).
