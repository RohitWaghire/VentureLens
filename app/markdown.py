"""Render a Report to Markdown for download."""

from __future__ import annotations

from app.model import Report


def render_report(report: Report) -> str:
    lines = [f"# {report.title or 'Business brief'}", "", report.summary, ""]
    for section in report.sections:
        lines.append(f"## {section.heading}")
        lines.append("")
        lines.append(section.body)
        lines.append("")
    if report.caveat:
        lines.append("---")
        lines.append(report.caveat)
    return "\n".join(lines).strip() + "\n"