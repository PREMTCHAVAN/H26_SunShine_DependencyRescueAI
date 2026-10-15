import unittest
from pathlib import Path
from unittest.mock import patch

from app import html_table, normalize_github_url, scan_repository
from reporting import generate_pdf_report


class GitHubUrlTests(unittest.TestCase):
    def test_normalizes_https_repository_url(self):
        self.assertEqual(
            normalize_github_url("https://github.com/example/project"),
            "https://github.com/example/project.git",
        )

    def test_accepts_git_suffix(self):
        self.assertEqual(
            normalize_github_url("https://github.com/example/project.git"),
            "https://github.com/example/project.git",
        )

    def test_rejects_non_github_and_extra_path(self):
        for value in (
            "http://github.com/example/project",
            "https://example.com/example/project",
            "https://github.com:8443/example/project",
            "https://github.com/example/project/tree/main",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_github_url(value)


class PdfReportTests(unittest.TestCase):
    def test_generates_pdf_with_empty_diff_table(self):
        report = {
            "repository_url": "https://github.com/example/project",
            "generated_at": "2026-10-15 00:00 UTC",
            "evidence": {
                "dependencies": [],
                "limitations": ["Static inspection only."],
            },
            "findings": [],
            "gemma_suggestions": "Gemma analysis was not run.",
        }
        pdf = generate_pdf_report(report)
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertGreater(len(pdf), 1000)


class HtmlTableTests(unittest.TestCase):
    def test_escapes_content_and_keeps_empty_table_blank(self):
        table = html_table(
            ["Package", "Current"],
            [{"Package": "<script>", "Current": "1.0"}],
        )
        self.assertIn("&lt;script&gt;", table)
        self.assertNotIn("<script>", table)

        empty_table = html_table(["Package", "Current"], [])
        self.assertIn("<th>Package</th>", empty_table)
        self.assertIn("<tbody></tbody>", empty_table)


class ScanTests(unittest.TestCase):
    @patch("app.clone_repository")
    def test_scans_repository_and_builds_report(self, clone_repository):
        def create_repository(_url, destination):
            Path(destination).mkdir()
            (Path(destination) / "requirements.txt").write_text(
                "demo==1.0\ndemo>=2\n",
                encoding="utf-8",
            )
            (Path(destination) / "main.py").write_text(
                "import demo\ndemo.run()\n",
                encoding="utf-8",
            )

        clone_repository.side_effect = create_repository
        report = scan_repository(
            "https://github.com/example/project.git",
            api_key="",
        )

        self.assertEqual(
            [item["package"] for item in report["evidence"]["dependencies"]],
            ["demo"],
        )
        self.assertEqual(len(report["findings"]), 1)
        self.assertIn("Gemma analysis was not run", report["gemma_suggestions"])
        self.assertTrue(report["pdf"].startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
