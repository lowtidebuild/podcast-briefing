import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import sheets  # noqa: E402


EPISODE = {
    "published": "2026-04-27T00:00:00",
    "podcast": "Test Podcast",
    "title": "Test Episode",
    "category": "Technology",
    "link": "https://example.com",
}

SUMMARY = {
    "guest": None,
    "summary_en": "A valid English summary that is long enough for the sheet helper.",
    "summary_ko": "충분히 긴 한국어 요약입니다. 시트 헬퍼가 실패로 표시하지 않을 정도의 내용입니다.",
}


class FakeSheet:
    def __init__(self, fail_append=False):
        self.fail_append = fail_append
        self.rows = []

    def row_values(self, row):
        return []

    def append_row(self, row):
        if self.fail_append:
            raise RuntimeError("quota exceeded")
        self.rows.append(row)


class SheetsAppendTests(unittest.TestCase):
    def test_append_episode_reports_not_configured_as_non_failure(self):
        original = sheets.get_sheet
        sheets.get_sheet = lambda: None
        try:
            result = sheets.append_episode(EPISODE, SUMMARY, "test-episode")
        finally:
            sheets.get_sheet = original

        self.assertTrue(result.ok)
        self.assertFalse(result.configured)

    def test_append_episode_reports_failure(self):
        original = sheets.get_sheet
        sheets.get_sheet = lambda: FakeSheet(fail_append=True)
        try:
            result = sheets.append_episode(EPISODE, SUMMARY, "test-episode")
        finally:
            sheets.get_sheet = original

        self.assertFalse(result.ok)
        self.assertTrue(result.configured)
        self.assertIn("quota exceeded", result.error)


if __name__ == "__main__":
    unittest.main()
