import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from state import is_episode_complete, is_episode_retryable  # noqa: E402
from state import normalize_state, update_episode_state  # noqa: E402


class PipelineStateTests(unittest.TestCase):
    def test_legacy_processed_list_migrates_to_episode_map(self):
        state = normalize_state({"processed": ["episode-1"]})

        self.assertEqual(state["version"], 2)
        self.assertIn("episode-1", state["episodes"])
        self.assertEqual(state["episodes"]["episode-1"]["status"], "published")
        self.assertTrue(is_episode_complete(state, "episode-1"))

    def test_validation_failed_episode_is_retryable_not_complete(self):
        state = update_episode_state(
            {},
            "episode-2",
            "validation_failed",
            slug="test-episode",
            stage="summary_validation",
            error="summary_ko is too short",
            warnings=["quote not grounded"],
        )

        self.assertFalse(is_episode_complete(state, "episode-2"))
        self.assertTrue(is_episode_retryable(state, "episode-2"))
        self.assertEqual(
            state["episodes"]["episode-2"]["last_error"],
            "summary_ko is too short",
        )
        self.assertEqual(state["episodes"]["episode-2"]["warnings"], ["quote not grounded"])

    def test_attempts_increment_only_when_requested(self):
        state = update_episode_state(
            {},
            "episode-3",
            "discovered",
            increment_attempt=True,
        )
        state = update_episode_state(state, "episode-3", "downloaded")
        state = update_episode_state(state, "episode-3", "published")

        self.assertEqual(state["episodes"]["episode-3"]["attempts"], 1)

    def test_sheets_failed_is_terminal_for_main_processing(self):
        state = update_episode_state(
            {},
            "episode-4",
            "sheets_failed",
            slug="test-episode",
            stage="sheets",
            error="quota exceeded",
        )

        self.assertTrue(is_episode_complete(state, "episode-4"))
        self.assertEqual(state["episodes"]["episode-4"]["last_error"], "quota exceeded")


if __name__ == "__main__":
    unittest.main()
