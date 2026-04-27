import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pipeline"))

import summarize  # noqa: E402
from quality import validate_summary  # noqa: E402
from synthesis import summarize_long_episode_with_result  # noqa: E402


EPISODE = {
    "podcast": "Test Podcast",
    "category": "Technology",
    "title": "A Long Test Episode",
    "published": "2026-04-27T00:00:00Z",
}


def fake_extraction():
    return {
        "topics": ["AI infrastructure"],
        "claims": [
            {
                "claim": "Inference cost is becoming a product constraint.",
                "evidence": ["The speakers discuss routing cheaper models."],
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


def fake_summary():
    long_ko = (
        "이 에피소드는 AI 제품 경쟁이 모델 성능만이 아니라 추론 비용과 배포 구조로 이동하고 있음을 보여줍니다. "
        "진짜 쟁점은 어떤 모델이 가장 똑똑한지가 아니라, 제품이 반복적으로 호출할 수 있을 만큼 경제적인지입니다. "
        "화자들은 모델 라우팅, 비용 곡선, 제품 제약을 연결해 기업이 AI 기능을 설계하는 방식이 달라지고 있다고 설명합니다."
    )
    long_en = (
        "This episode shows that AI product competition is moving from raw model quality to inference economics and deployment design. "
        "The central issue is no longer only which model is smartest, but whether a product can afford to call that model repeatedly. "
        "The speakers connect model routing, cost curves, and product constraints to explain why AI features increasingly need economic architecture."
    )
    return {
        "guest": None,
        "summary_ko": long_ko,
        "summary_en": long_en,
        "key_points_ko": [
            {
                "heading": "추론 비용이 제품 전략을 제한합니다",
                "body": "AI 기능은 호출 비용이 누적될수록 제품 설계의 제약이 됩니다. 화자들은 모델 라우팅이 비용과 품질을 동시에 다루는 방식이라고 설명합니다. 이 관점에서는 최고 성능 모델을 항상 쓰는 전략이 아니라 맥락별 최적 모델을 고르는 전략이 중요합니다. 결과적으로 AI 제품 경쟁력은 모델 선택과 비용 통제 능력에 달려 있습니다.",
                "source_chunks": [0, 1],
            }
        ],
        "key_points_en": [
            {
                "heading": "Inference cost now constrains product strategy",
                "body": "AI features become product constraints as repeated calls accumulate cost. The speakers frame model routing as a way to manage quality and economics at the same time. That makes always using the strongest model less attractive than choosing the right model for each context. Product advantage increasingly depends on model selection and cost control.",
                "source_chunks": [0, 1],
            }
        ],
        "notable_quote_ko": {
            "text": "비용 곡선은 이제 제품 제약입니다.",
            "attribution": "Host A",
        },
        "notable_quote_en": {
            "text": "The cost curve is now a product constraint.",
            "attribution": "Host A",
        },
        "keywords_ko": ["추론 비용", "model routing", "AI 제품", "비용 곡선"],
        "keywords_en": ["inference costs", "model routing", "AI products", "cost curves"],
    }


def fake_provider(prompt, model=None):
    if "<transcript_chunk>" in prompt:
        return json.dumps(fake_extraction())
    return json.dumps(fake_summary())


class LongSynthesisFlowTests(unittest.TestCase):
    def test_long_episode_flow_writes_artifacts_and_compacts_final_input(self):
        previous = dict(summarize.PROVIDERS)
        summarize.PROVIDERS["fake"] = fake_provider
        transcript = ("First claim. Evidence follows.\n\n" * 4000)

        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                result = summarize_long_episode_with_result(
                    EPISODE,
                    transcript,
                    slug="test-long-episode",
                    provider="fake",
                    model="fake-model",
                    cache_dir=tmp_path / "cache",
                    intermediate_dir=tmp_path / "intermediate",
                )

                validation = validate_summary(result.summary)

                self.assertTrue(result.parse_succeeded)
                self.assertTrue(validation.ok)
                self.assertIn("synthesis", result.artifacts)
                self.assertTrue(Path(result.artifacts["chunks"]).exists())
                self.assertTrue(Path(result.artifacts["synthesis"]).exists())
                self.assertLess(
                    result.usage["synthesis_prompt_chars"],
                    len(transcript) * 0.4,
                )
        finally:
            summarize.PROVIDERS.clear()
            summarize.PROVIDERS.update(previous)


if __name__ == "__main__":
    unittest.main()
