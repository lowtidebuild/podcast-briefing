#!/usr/bin/env python3
"""A/B Test: Claude Sonnet 4.6 vs Gemini 3.1 Pro for podcast summarization.

Runs the same transcripts through both models and outputs side-by-side results
for manual quality comparison.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import SUMMARIES_DIR, TRANSCRIPTS_DIR
from summarize import summarize_episode, _build_prompt

# Test episodes — short, medium, long
TEST_SLUGS = [
    "2026-03-18-exponential-view",   # ~20K chars (short)
    "2026-03-20-odd-lots",           # ~53K chars (medium)
    "2026-03-20-ezra-klein-show",    # ~76K chars (long)
]

OUTPUT_DIR = SUMMARIES_DIR.parent / "ab_test"


def load_episode_meta(slug):
    """Load episode metadata from existing summary JSON."""
    path = SUMMARIES_DIR / f"{slug}.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "podcast": data["podcast"],
        "category": data["category"],
        "title": data["title"],
        "published": data["published"],
    }


def load_transcript(slug):
    path = TRANSCRIPTS_DIR / f"{slug}.txt"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def run_test(slug, provider, model=None):
    """Run summarization and return (result_dict, elapsed_seconds)."""
    ep = load_episode_meta(slug)
    transcript = load_transcript(slug)

    start = time.time()
    result = summarize_episode(ep, transcript, provider=provider, model=model)
    elapsed = time.time() - start

    return result, elapsed


def print_comparison(slug, claude_result, claude_time, gemini_result, gemini_time):
    """Print side-by-side comparison."""
    sep = "=" * 80
    print(f"\n{sep}")
    print(f"  EPISODE: {slug}")
    print(sep)

    print(f"\n  Claude Sonnet 4.6  ({claude_time:.1f}s)")
    print(f"  Gemini 3.1 Pro     ({gemini_time:.1f}s)")

    # Korean summary comparison
    print(f"\n{'─' * 80}")
    print("  SUMMARY (KO)")
    print(f"{'─' * 80}")
    print(f"\n  [Claude]\n")
    print(claude_result.get("summary_ko", "(empty)"))
    print(f"\n  [Gemini]\n")
    print(gemini_result.get("summary_ko", "(empty)"))

    # English summary comparison
    print(f"\n{'─' * 80}")
    print("  SUMMARY (EN)")
    print(f"{'─' * 80}")
    print(f"\n  [Claude]\n")
    print(claude_result.get("summary_en", "(empty)"))
    print(f"\n  [Gemini]\n")
    print(gemini_result.get("summary_en", "(empty)"))

    # Key points count
    print(f"\n{'─' * 80}")
    print("  KEY POINTS")
    print(f"{'─' * 80}")
    ckp = claude_result.get("key_points_en", [])
    gkp = gemini_result.get("key_points_en", [])
    print(f"  Claude: {len(ckp)} points")
    for kp in ckp:
        print(f"    • {kp.get('heading', '')}")
    print(f"  Gemini: {len(gkp)} points")
    for kp in gkp:
        print(f"    • {kp.get('heading', '')}")

    # Notable quote
    print(f"\n{'─' * 80}")
    print("  NOTABLE QUOTE (EN)")
    print(f"{'─' * 80}")
    cq = claude_result.get("notable_quote_en", {})
    gq = gemini_result.get("notable_quote_en", {})
    print(f"  Claude: \"{cq.get('text', '')}\"")
    print(f"         — {cq.get('attribution', '')}")
    print(f"  Gemini: \"{gq.get('text', '')}\"")
    print(f"         — {gq.get('attribution', '')}")

    # JSON validity
    print(f"\n{'─' * 80}")
    print("  QUALITY CHECKS")
    print(f"{'─' * 80}")
    for label, r in [("Claude", claude_result), ("Gemini", gemini_result)]:
        has_guest = r.get("guest") is not None
        has_ko = bool(r.get("summary_ko"))
        has_en = bool(r.get("summary_en"))
        kp_count = len(r.get("key_points_ko", []))
        kw_count = len(r.get("keywords_en", []))
        print(f"  {label}: guest={'✓' if has_guest else '✗'}  "
              f"ko={'✓' if has_ko else '✗'}  en={'✓' if has_en else '✗'}  "
              f"key_points={kp_count}  keywords={kw_count}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_results = {}

    for slug in TEST_SLUGS:
        print(f"\n>>> Testing: {slug}")
        transcript = load_transcript(slug)
        print(f"    Transcript size: {len(transcript):,} chars")

        print(f"    Running Claude Sonnet 4.6...")
        claude_result, claude_time = run_test(slug, provider="claude")
        print(f"    Done ({claude_time:.1f}s)")

        print(f"    Running Gemini 3.1 Pro...")
        gemini_result, gemini_time = run_test(slug, provider="gemini")
        print(f"    Done ({gemini_time:.1f}s)")

        print_comparison(slug, claude_result, claude_time, gemini_result, gemini_time)

        all_results[slug] = {
            "claude": {"result": claude_result, "time": claude_time},
            "gemini": {"result": gemini_result, "time": gemini_time},
        }

    # Save raw results
    output_path = OUTPUT_DIR / "ab_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"\n\nRaw results saved to: {output_path}")


if __name__ == "__main__":
    main()
