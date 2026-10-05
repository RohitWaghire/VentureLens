# ADR-0001 — Provider and scoring architecture

**Status:** Accepted (Phase 0 of `PROJECT_PLAN.md`)
**Date:** 2026-10-05

## Context

VentureLens needs three external capabilities — a language model for the
interview/synthesis, public web research with citations, and Qloo for
audience/cultural signals — plus a repeatable way to compare neighborhoods. The
hackathon plan explicitly defers concrete provider selection to Phase 0 based on
available credentials, terms, and cost. The MVP must be runnable and testable
with no credentials.

## Decision

1. **Provider seam.** The app depends only on `app.providers.base.Provider`.
   A deterministic, credential-free `DemoProvider` is the default and is fully
   testable. Real LLM/search/Qloo adapters implement the same interface and are
   registered behind the `VL_PROVIDER` env var. Qloo is called directly from
   the server; the CLI/MCP runtime is not a dependency.
2. **Agent control flow** is a small, explicit, linear orchestration loop
   (inspired by mini-SWE-agent's simplicity, not its shell tooling). Interview
   sequencing is application state code, not opaque model behavior.
3. **Scoring stays in application code.** Fixed, documented category weights
   (cafés and restaurants), the weighted-total arithmetic, and the comparison
   ordering rule live in `app/scoring.py`, never in the model. The model
   provides versioned 1–5 factor ratings from cited evidence.
4. **Withhold incomplete totals.** If any factor is unscored, the overall
   numeric fit is withheld (never estimated). Incomplete rows are ordered by
   evidence completeness, then by a labeled heuristic comparison score.

## Consequences

- The app runs and all tests pass without credentials or network access.
- Real providers and credentials slot in without touching app logic.
- Score meaning is stable and auditable (anchor version `1.0`).
- Research costs are bounded by per-session and global budgets enforced at the
  provider call site.

## Alternatives considered

- Bundling real provider SDKs into the MVP core: rejected — no credentials
  available for verification, and it couples the app to chosen vendors.
- Letting the model compute weighted totals directly: rejected — non-repeatable
  and conflicts with the inspected, deterministic scoring requirement.