import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import generate_output  # noqa: E402


class FeedIndexReportTests(unittest.TestCase):
    def test_rebuild_feed_index_writes_skip_report(self):
        original_summaries = generate_output.SUMMARIES_DIR
        original_reports = generate_output.REPORTS_DIR

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            summaries = tmp_path / "summaries"
            reports = tmp_path / "reports"
            summaries.mkdir()

            (summaries / "valid.json").write_text(
                json.dumps(
                    {
                        "slug": "valid",
                        "podcast": "Test Podcast",
                        "category": "Technology",
                        "title": "Valid Episode",
                        "published": "2026-04-27T00:00:00",
                    }
                ),
                encoding="utf-8",
            )
            (summaries / "invalid.json").write_text("{", encoding="utf-8")

            generate_output.SUMMARIES_DIR = summaries
            generate_output.REPORTS_DIR = reports
            try:
                feed_path = generate_output.rebuild_feed_index()
            finally:
                generate_output.SUMMARIES_DIR = original_summaries
                generate_output.REPORTS_DIR = original_reports

            feed = json.loads(Path(feed_path).read_text(encoding="utf-8"))
            report = json.loads(
                (reports / "feed_index_report.json").read_text(encoding="utf-8")
            )

            self.assertEqual(len(feed), 1)
            self.assertEqual(report["scanned_files"], 2)
            self.assertEqual(report["indexed_count"], 1)
            self.assertEqual(report["skipped_count"], 1)
            self.assertEqual(report["skipped"][0]["file"], "invalid.json")


if __name__ == "__main__":
    unittest.main()
