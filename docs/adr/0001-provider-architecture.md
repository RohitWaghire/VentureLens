# ADR-0001 — Provider architecture

**Status:** Accepted, revised
**Date:** 2026-10-05, revised 2026-10-22

## Context

VentureLens needs a language model for the interview and the brief, and Qloo
for aggregate place affinities. An earlier draft of this note described a
credential-free demo provider, a `VL_PROVIDER` switch, and a scoring module.
None of those are in the app.

## Decision

1. **One provider.** The app depends on `app.providers.base.Provider`.
   `LiveProvider` is the only adapter. Tests inject an HTTP transport and do
   not call live APIs. There is no demo provider and no shared question list.
2. **The model mediates Qloo.** Luna reads the opening prompt and the
   transcript and names one place category. The app searches Qloo tags for
   that phrase and keeps ids that start with `urn:tag:category:place:`. When
   several match, Luna picks among the tags Qloo returned. An id Luna invents
   is not sent. Insights then uses that tag and the named city. Luna writes
   the brief and the short place note from what came back.
3. **Place rules stay in code.** Insights require a place-category tag. An
   interest signal is rejected. A named city stays on the request. An empty
   city does not become a worldwide search. A statewide retry keeps only
   places near that city.
4. **A failed Qloo call is not an empty affinity list.** A category-lookup
   failure, a place-request failure, a missing category, and a real empty
   list are different sentences in the brief. The status code and a short
   piece of a non-200 body are logged. The log and the page never include
   the key.

## Consequences

- Tests pass without credentials or network access.
- The category is the model's reading of this idea, not a word-overlap score.
- Qloo errors and empty results no longer share one sentence.

## Alternatives considered

- Ranking Qloo tags in Python by word overlap: rejected. It treated answer
  words as searches and could rank a barber shop above a bar.
- Letting the model invent a tag id: rejected. Insights only accepts a tag
  Qloo returned.
