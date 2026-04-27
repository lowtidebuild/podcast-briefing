import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from quality import validate_summary  # noqa: E402


FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return json.load(f)


class SummaryQualityTests(unittest.TestCase):
    def test_valid_summary_passes(self):
        result = validate_summary(load_fixture("valid_summary.json"))

        self.assertTrue(result.ok)
        self.assertEqual(result.errors, [])
        self.assertIsNotNone(result.sanitized_summary)

    def test_extra_field_is_warning_and_stripped_for_p0(self):
        result = validate_summary(load_fixture("summary_with_extra_field.json"))

        self.assertTrue(result.ok)
        self.assertTrue(any("extra fields stripped" in w for w in result.warnings))
        self.assertNotIn("_key_points_note", result.sanitized_summary)

    def test_empty_summary_fails(self):
        result = validate_summary(load_fixture("summary_empty.json"))

        self.assertFalse(result.ok)
        self.assertTrue(any("summary_ko" in e for e in result.errors))
        self.assertTrue(any("summary_en" in e for e in result.errors))

    def test_json_fragment_summary_fails(self):
        result = validate_summary(load_fixture("summary_json_fragment_in_field.json"))

        self.assertFalse(result.ok)
        self.assertTrue(any("JSON fragment" in e for e in result.errors))

    def test_known_failed_artifacts_fail_validation(self):
        fixture_names = [
            "2026-03-11-lex-fridman-podcast.failed.json",
            "2026-04-14-ezra-klein-show.failed.json",
        ]

        for name in fixture_names:
            with self.subTest(name=name):
                result = validate_summary(load_fixture(name))
                self.assertFalse(result.ok)

    def test_guest_name_null_is_normalized_for_hosts_only_outputs(self):
        summary = load_fixture("valid_summary.json")
        summary["guest"] = {"name": None, "title": "Host monologue"}

        result = validate_summary(summary)

        self.assertTrue(result.ok)
        self.assertIsNone(result.sanitized_summary["guest"])
        self.assertTrue(any("guest object without a name" in w for w in result.warnings))

    def test_key_point_count_mismatch_is_warning_not_failure(self):
        summary = deepcopy(load_fixture("valid_summary.json"))
        summary["key_points_en"] = summary["key_points_en"][:1]

        result = validate_summary(summary)

        self.assertTrue(result.ok)
        self.assertTrue(any("language counts differ" in w for w in result.warnings))

    def test_key_point_source_chunks_are_preserved_when_valid(self):
        summary = deepcopy(load_fixture("valid_summary.json"))
        summary["key_points_ko"][0]["source_chunks"] = [2, 0, 2]
        summary["key_points_en"][0]["source_chunks"] = [0, 2]

        result = validate_summary(summary)

        self.assertTrue(result.ok)
        self.assertEqual(result.sanitized_summary["key_points_ko"][0]["source_chunks"], [0, 2])
        self.assertEqual(result.sanitized_summary["key_points_en"][0]["source_chunks"], [0, 2])

    def test_grounded_quote_metadata_is_preserved(self):
        summary = deepcopy(load_fixture("valid_summary.json"))
        summary["notable_quote"] = {
            "source_text_en": "The cost curve is now a product constraint.",
            "translation_ko": "비용 곡선은 이제 제품 제약입니다.",
            "speaker": "Casey Newton",
            "attribution": "Casey Newton",
            "is_verbatim": True,
            "translation_is_verbatim": False,
            "source_char_start": 10,
            "source_char_end": 55,
            "match_score": 0.94,
        }

        result = validate_summary(summary)

        self.assertTrue(result.ok)
        self.assertTrue(result.sanitized_summary["notable_quote"]["is_verbatim"])
        self.assertEqual(result.sanitized_summary["notable_quote"]["match_score"], 0.94)


if __name__ == "__main__":
    unittest.main()
