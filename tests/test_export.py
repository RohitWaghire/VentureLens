"""Markdown export: plan download, section coverage, and follow-up isolation."""

from __future__ import annotations

from tests.conftest import csrf_for


class TestDownloadEndpoint:
    def test_download_returns_markdown_with_inline_links(self, flow):
        r = flow.get("/plan/download")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/markdown")
        assert "venturelens-plan.md" in r.headers["content-disposition"]
        assert r.text.startswith("# Business Plan")
        assert "https://demo.example.com/" in r.text
        assert "](" in r.text

    def test_download_has_expected_sections(self, flow):
        r = flow.get("/plan/download")
        for section in ("Target Audience", "Concept & Positioning", "Location Comparison",
                        "Recommendations", "Assumptions", "Risks", "Practical Next Steps"):
            assert f"## {section}" in r.text


class TestFollowupIsolation:
    def test_followup_does_not_change_downloaded_plan(self, flow):
        before = flow.get("/plan/download").text
        token = csrf_for(flow, "/plan")
        flow.post("/followup", data={"question": "Which neighborhood suits students?", "csrf": token})
        after = flow.get("/plan/download").text
        assert before == after, "follow-up must not mutate the exported plan"

    def test_followup_answer_appears_in_chat(self, flow):
        token = csrf_for(flow, "/plan")
        flow.post("/followup", data={"question": "Which neighborhood suits students?", "csrf": token})
        page = flow.get("/plan").text
        assert "Based on the current findings, the leading recommendation is" in page