import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

from extraction import chunk_transcript, extract_episode_chunks  # noqa: E402
from extraction import should_use_chunked_summary  # noqa: E402
from synthesis import build_synthesis_prompt  # noqa: E402


EPISODE = {
    "podcast": "Test Podcast",
    "category": "Technology",
    "title": "A Long Test Episode",
    "published": "2026-04-27T00:00:00Z",
}


def extraction_payload():
    return {
        "topics": ["AI infrastructure"],
        "claims": [
            {
                "claim": "Inference costs shape product strategy.",
                "evidence": ["The hosts compare model routing costs."],
                "speakers": ["Host A"],
            }
        ],
        "quote_candidates": [
            {
                "text": "The cost curve is now a product constraint.",
                "speaker": "Host A",
                "char_start": None,
                "char_end": None,
            }
        ],
        "guest_candidates": [],
        "keyword_candidates": ["inference costs", "model routing"],
    }


class FakeJsonCaller:
    def __init__(self, fail_calls=None):
        self.fail_calls = set(fail_calls or [])
        self.calls = 0

    def __call__(self, prompt, provider, model, max_retries, label):
        self.calls += 1
        if self.calls in self.fail_calls:
            return SimpleNamespace(
                summary=None,
                raw_text="not json",
                provider=provider,
                model=model,
                attempts=1,
                parse_succeeded=False,
            )

        payload = extraction_payload()
        return SimpleNamespace(
            summary=payload,
            raw_text=json.dumps(payload),
            provider=provider,
            model=model,
            attempts=1,
            parse_succeeded=True,
        )


class ChunkExtractionTests(unittest.TestCase):
    def test_chunk_transcript_covers_text_without_gaps(self):
        text = ("Intro sentence. More detail follows.\n\n" * 30) + "Final sentence."
        chunks = chunk_transcript(text, target_chars=140, min_chars=90, max_chars=180)

        self.assertGreater(len(chunks), 1)
        self.assertEqual(
            "".join(text[chunk.char_start:chunk.char_end] for chunk in chunks),
            text,
        )
        self.assertEqual([chunk.index for chunk in chunks], list(range(len(chunks))))

        for previous, current in zip(chunks, chunks[1:]):
            self.assertEqual(previous.char_end, current.char_start)

    def test_chunked_summary_threshold_is_strictly_above_80000_chars(self):
        self.assertFalse(should_use_chunked_summary("x" * 80000))
        self.assertTrue(should_use_chunked_summary("x" * 80001))

    def test_successful_chunks_are_cached_after_partial_failure(self):
        transcript = ("One claim. Another detail.\n\n" * 40) + "Closing claim."
        expected_chunks = chunk_transcript(
            transcript,
            target_chars=140,
            min_chars=90,
            max_chars=180,
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            first_caller = FakeJsonCaller(fail_calls={2})
            first = extract_episode_chunks(
                EPISODE,
                transcript,
                slug="test-long-episode",
                provider="claude",
                model="test-model",
                call_json=first_caller,
                cache_dir=tmp_path / "cache",
                intermediate_dir=tmp_path / "intermediate",
                target_chars=140,
                min_chars=90,
                max_chars=180,
            )

            self.assertFalse(first.ok)
            self.assertEqual(first.cache_hits, 0)
            self.assertEqual(first_caller.calls, len(expected_chunks))

            second_caller = FakeJsonCaller()
            second = extract_episode_chunks(
                EPISODE,
                transcript,
                slug="test-long-episode",
                provider="claude",
                model="test-model",
                call_json=second_caller,
                cache_dir=tmp_path / "cache",
                intermediate_dir=tmp_path / "intermediate",
                target_chars=140,
                min_chars=90,
                max_chars=180,
            )

            self.assertTrue(second.ok)
            self.assertEqual(second.cache_hits, len(expected_chunks) - 1)
            self.assertEqual(second_caller.calls, 1)

    def test_synthesis_prompt_uses_compact_extractions(self):
        extractions = [
            {
                **extraction_payload(),
                "chunk_index": index,
                "char_start": index * 30000,
                "char_end": (index + 1) * 30000,
            }
            for index in range(4)
        ]

        prompt = build_synthesis_prompt(
            EPISODE,
            extractions,
            transcript_chars=120000,
        )

        self.assertIn("<chunk_extractions>", prompt)
        self.assertLess(len(prompt), 120000 * 0.4)


if __name__ == "__main__":
    unittest.main()
