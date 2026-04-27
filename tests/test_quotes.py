import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from quotes import find_quote_match, ground_summary_quote  # noqa: E402


def summary_with_quote(en_text):
    return {
        "notable_quote_en": {
            "text": en_text,
            "attribution": "Casey Newton",
        },
        "notable_quote_ko": {
            "text": "비용 곡선은 이제 제품 제약입니다.",
            "attribution": "Casey Newton",
        },
    }


class QuoteGroundingTests(unittest.TestCase):
    def test_exact_quote_match_returns_source_span(self):
        transcript = (
            "First the hosts discuss markets. "
            "The cost curve is now a product constraint. "
            "Then they move to regulation."
        )

        match = find_quote_match(
            "The cost curve is now a product constraint.",
            transcript,
        )

        self.assertTrue(match.matched)
        self.assertEqual(match.score, 1.0)
        self.assertEqual(
            transcript[match.char_start:match.char_end],
            "The cost curve is now a product constraint",
        )

    def test_fuzzy_quote_match_tolerates_punctuation_changes(self):
        transcript = "She said, the cost curve is now a product constraint, not a lab curiosity."

        match = find_quote_match(
            "The cost curve is now a product constraint not a lab curiosity.",
            transcript,
        )

        self.assertTrue(match.matched)
        self.assertGreaterEqual(match.score, 0.84)

    def test_ungrounded_quote_is_marked_non_verbatim(self):
        transcript = "The hosts discuss a different point about distribution."

        result = ground_summary_quote(
            summary_with_quote("The cost curve is now a product constraint."),
            transcript,
        )

        self.assertFalse(result.quote["is_verbatim"])
        self.assertIsNone(result.quote["source_char_start"])
        self.assertTrue(any("not grounded" in warning for warning in result.warnings))

    def test_grounded_quote_report_is_written(self):
        transcript = "The cost curve is now a product constraint."

        with tempfile.TemporaryDirectory() as tmp:
            result = ground_summary_quote(
                summary_with_quote("The cost curve is now a product constraint."),
                transcript,
                slug="test-episode",
                report_dir=tmp,
            )

            self.assertTrue(result.quote["is_verbatim"])
            self.assertIsNotNone(result.report_path)
            report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
            self.assertTrue(report["is_verbatim"])
            self.assertEqual(report["match_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
