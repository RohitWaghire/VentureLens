"""Report export behavior."""

from __future__ import annotations


class TestDownload:
    def test_download_returns_markdown(self, flow):
        r = flow.get("/report/download")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/markdown")
        assert "venturelens-report.md" in r.headers["content-disposition"]
        assert r.text.startswith("# Business brief")
        assert "## " in r.text
        assert "Young professionals" in r.text

    def test_collected_answers_preserved_in_report_page(self, flow):
        page = flow.get("/report").text
        assert "Within 6 months" in page
        assert "Young professionals" in page