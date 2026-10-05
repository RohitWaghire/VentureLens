"""Render the business plan to Markdown with inline source-title links.

Citations are attached inline to the claims they support ([source title](url)),
and the original plan is preserved. Follow-up chat never mutates this export.
"""

from __future__ import annotations

from typing import List

from app.model import Claim


def _render_citations(citations: List) -> str:
    parts = []
    for c in citations:
        parts.append(f"[{c.title}]({c.url})")
    return " (" + "; ".join(parts) + ")" if parts else ""


def _claim_line(claim: Claim) -> str:
    suffix = " [assumption]" if claim.is_assumption else ""
    return f"- {claim.text}{suffix}{_render_citations(claim.citations)}"


def _section(title: str, claims: List[Claim]) -> str:
    if not claims:
        return f"## {title}\n\nNo findings recorded for this section.\n"
    body = "\n".join(_claim_line(c) for c in claims)
    return f"## {title}\n\n{body}\n"


def render_plan(plan) -> str:
    lines = [f"# {plan.title}", "", plan.overview, ""]
    if getattr(plan, "scorecard_markdown", ""):
        lines.append(plan.scorecard_markdown)
        lines.append("")
    lines.append(_section("Target Audience", plan.audience))
    lines.append(_section("Concept & Positioning", plan.concept))
    lines.append(_section("Location Comparison", plan.location))
    lines.append(_section("Recommendations", plan.recommendations))
    lines.append(_section("Assumptions", plan.assumptions))
    lines.append(_section("Risks", plan.risks))
    lines.append(_section("Practical Next Steps", plan.next_steps))
    return "\n".join(lines).strip() + "\n"


def render_scorecard_markdown(comparison) -> str:
    """Render the neighborhood scorecard comparison as Markdown.

    Numeric totals appear only where every factor was scored; incomplete rows
    show their available factor scores with the total withheld.
    """
    lines = ["### Neighborhood Comparison", ""]
    lines.append(f"City: **{comparison.city}** · Template: **{comparison.template_name}**")
    if comparison.template_proxy_for:
        lines.append(
            f"_Proxy scorecard: using the {comparison.template_name} template for an "
            "unsupported business category._"
        )
    if comparison.limitation_note:
        lines.append(f"_Note: {comparison.limitation_note}_")
    lines.append("")
    for s in comparison.scorecards:
        total = f"{s.weighted_total:.2f}/5" if s.weighted_total is not None else "withheld (incomplete evidence)"
        factors = "; ".join(
            f"{f.factor}: "
            + (str(f.score) if f.score is not None else "n/a")
            for f in s.factors
        )
        lines.append(f"- **{s.neighborhood}** — fit {total} ({factors})")
        if s.summary:
            lines.append(f"  - {s.summary}")
    return "\n".join(lines) + "\n"


def attach_scorecard(plan, comparison) -> None:
    plan.scorecard_markdown = render_scorecard_markdown(comparison)