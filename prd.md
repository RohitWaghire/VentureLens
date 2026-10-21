---
doc: prd
status: draft
---

# VentureLens — Product Requirements

A founder or small-business owner describes an idea and gets a short brief they can download. The name and tagline come from the discovery dialogue: VentureLens, "A clearer view of where to grow."
Source: `scope.md > The Unique Kernel` and `scope.md > The Core Loop`.

## The Core Journey
1. They land on a single screen and type a business idea in everyday language. A U.S. place in that prompt is what makes a live place lookup useful. They can also start from a shown example.
2. The app asks a short round of questions drawn from the idea and from what is still unsettled. It does not ask again for a budget, place, or other detail already written in the prompt. Each question offers shortlisted answers and a place to type their own.
3. They move through that round one question at a time. Earlier questions and answers are not replayed on the screen.
4. When the round is finished, they confirm that the collected answers match what they meant. The brief is not written until they confirm.
5. They see one brief: a title, a short summary, the sections the model wrote, and the answers that were collected. They can download that same brief as Markdown, or start a new idea, which discards the session.
6. Success, for the proof of concept, is that coffee-shop walk-through completing on screen without an account. With the demo provider, no API key is required. With the live provider configured, the brief may also name places Qloo returned for that idea and city.

Source: `scope.md > The Core Loop` and `scope.md > What "Working" Looks Like`.

## Screens and Layout
Four surfaces, all server-rendered in the same window.

- **Landing.** Brand and tagline, one glass composer, two example chips, and a short trust line. No account gate.
- **Grilling.** "New idea" returns to the landing and discards the session. The current question opens in a glass card from the bottom: the question, lettered options, a typed answer, and Continue. The next question replaces the current one.
- **Confirm.** The same card asks whether the answers match. The only forward action is writing the brief.
- **Brief.** One card holds the ready mark's absence (no orb), the title, the summary, download, "Start a new idea," and the sections, separated by light rules. The footer states what was sent to outside services when the live provider is on.

## Look and Feel
Settled in the design dialogue after the discovery plan, and visible in the running app. Landscape video behind the page. Type is Schibsted Grotesk for interface text and Fustat for titles. The composer, the question card, "New idea," and "Start a new idea" share a glass treatment: a light border, a dark translucent wash, and blur. Primary actions are black pills with white text. The brief itself is one pale card. Do not add a solid black question slab, a loading overlay that covers the page, a "private session" pill, or a decorative orb.

## Features and Behavior

### Opening prompt
The founder must describe an idea before grilling starts. The examples fill the composer with a full prompt. Empty input is refused with a short error on the landing screen.

### Grilling
Questions are chosen from the idea and prior answers. Options can be selected or the founder can type their own answer. Optional detail can be skipped by continuing. A recommendation may be marked on one option. The screen shows only the current question.

### Confirm and brief
Confirmation is explicit. The brief is generated from the transcript. In demo mode the brief is built from the answers. In live mode the provider may add a place note from Qloo, and the page says that the idea, place, and answers were sent to Qloo and the configured model for this session only. Download returns the brief as Markdown. "Start a new idea" and "New idea" both discard the session and return to the composer.

### Session safety
No accounts and no saved history. The session lives in memory, expires on the server, and is rejected when expired. State-changing requests require a session token. A research budget can stop a run with a clear error instead of a partial secret or a stack trace.

## States and Boundaries

- **First use** — landing composer, empty, with examples.
- **Grilling** — one question card. No transcript on that screen.
- **Needs confirmation** — the brief is withheld until they confirm.
- **Brief ready** — one card, download available.
- **Empty idea** — they stay on the landing page with an error.
- **Provider or budget failure** — a short message, no credentials and no internal trace.
- **Leaving** — closing the browser does not create an account. The server drops the session when it expires. Starting a new idea drops it immediately.
- **What is stored** — idea, answers, and the brief, in that server session only.

## Product Decisions

- Adaptive grilling instead of a fixed form — the discovery dialogue rejected a questionnaire that re-asks known details.
- A written brief with Markdown download, not a numeric score — the build dialogue removed the scorecard.
- Demo path with no keys, and an optional live Qloo and model provider behind the same screens — so the proof of concept runs for a reviewer without credentials.
- One question on screen at a time — the build dialogue removed the grilling history.
- Glass cards on the landscape — the design dialogue, after the discovery plan's simpler shell.

## What We're Building
The journey above, on the four screens, with the demo provider working with no secrets, tests that do not call live APIs, and the optional live provider left behind the same flow.

## Deferred From the POC
Ranked cities, neighborhood shortlists, inline citations on web research, and a follow-up chat that must not change the downloaded brief. The discovery dialogue specified them. They are not required to prove the kernel that shipped.

## Possible Later Enhancements
City discovery inside the stated region, then a neighborhood comparison, each with cited evidence. A follow-up conversation that can research again without rewriting the original download.

## Non-Goals
- A neighborhood scorecard or any overall numeric fit score. Removed because missing evidence was being turned into false precision.
- Pricing advice and a standalone competitor report. Cut in the discovery dialogue.
- Accounts, saved plans, or international coverage. Cut in the discovery dialogue.
- A loading overlay that covers the page. Removed because it interrupted the flow.

## Open Questions
- Whether the deferred city and neighborhood research should ever return. Can wait. It is not part of this proof of concept.
- Which live model and Qloo terms apply in a public demo. Can wait until someone enables the live provider. The demo path does not need that answer.
