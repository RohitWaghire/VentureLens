---
doc: scope
status: draft
---

# VentureLens

A clearer view of where to grow. A founder describes a business idea, answers a short adaptive grilling, and receives a brief they can read and download.

This sketch comes from the product-discovery dialogue recorded in `PROJECT_PLAN.md`, then narrowed by the later build dialogue. That later dialogue shipped the prompt, grilling, and brief, and dropped the neighborhood scorecard.

## The Unique Kernel
The questions and the place evidence come from the idea the founder actually typed. VentureLens does not run a fixed questionnaire, and it does not look up places from a hardcoded list of business types. Anything already stated in the opening prompt is not asked again. A live place lookup uses a confirmed place category and stays near the city the founder named.

## Who It's For
A founder or small-business owner who has an idea and a rough U.S. place in mind, and who wants a short brief before spending money. The discovery dialogue pictured them opening with something like "I have $250k and want to open a specialty coffee shop in Illinois." Today they would start from a blank document, a generic chatbot, and a maps search.

## The Core Loop
They open the app, write the idea, answer one short round of questions, confirm that the collected answers match what they meant, and read the brief. They can download that brief as Markdown or start a new idea. The session keeps the answers only while it lasts.

## Inspiration & Identity
The discovery dialogue named the tagline "A clearer view of where to grow." The later design dialogue settled the running look: a landscape behind a glass composer, and a question card that opens upward from the bottom. The brief is one card, not a stack of separate boxes.

## Why This Matters to the Learner
They built VentureLens in this shape and asked for the planning files to be taken from that work, because the skill files were never written during the original dialogue.

## What "Working" Looks Like
On one screen, with no account: type the coffee-shop prompt, answer the grilling, confirm, and see a brief that downloads as Markdown. The demo path does this with no API keys. When the live provider is configured, the same path can add Qloo places for that idea and city. A reviewer can see this in a short screen recording. A public GitHub repository is the other submission requirement. Deployment is optional.

## The POC Boundary
In: the opening prompt, adaptive grilling with shortlisted options and a typed answer, a confirm step, a written brief, Markdown download, an in-memory session that expires, and a credential-free demo provider. The live Qloo and model provider is in only as an optional seam on that same flow.

## Later
From the discovery dialogue, not in the running proof of concept: three ranked cities inside the stated region, a neighborhood shortlist, inline source citations on research claims, and a follow-up conversation that does not change the downloaded brief.

## Explicitly Cut
A numeric neighborhood scorecard, including café and restaurant weights and a withheld total when evidence is missing. The later build dialogue removed unused scorecard code. The brief is prose. Pricing advice, a standalone competitor report, user accounts, saved plans, international coverage, and editing the original brief through later chat were cut in the discovery dialogue and stay cut.
