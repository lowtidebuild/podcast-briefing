#!/usr/bin/env python3
"""Podcast Briefing Pipeline — Daily Orchestrator.

Processes new podcast episodes sequentially:
RSS parse → audio download → transcribe → summarize → output → cleanup
"""

import sys
import os

# Add pipeline directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_feeds import load_feeds, load_state, save_state, fetch_new_episodes
from download_audio import download_audio, cleanup_audio
from transcribe import get_transcript
from summarize import summarize_episode
from generate_output import generate_episode_json, rebuild_feed_index


def main():
    feeds = load_feeds()
    state = load_state()

    print(f"Checking {len(feeds)} podcast feeds...")
    new_episodes = fetch_new_episodes(feeds, state)

    if not new_episodes:
        print("No new episodes found.")
        rebuild_feed_index()
        return

    print(f"Found {len(new_episodes)} new episode(s)\n")
    processed_count = 0

    for ep in new_episodes:
        try:
            print(f"--- {ep['podcast']}: {ep['title']}")

            # Step 1: Download audio
            print("  [1/4] Downloading audio...")
            audio_path = download_audio(ep)

            # Step 2: Transcribe
            print("  [2/4] Transcribing...")
            transcript = get_transcript(ep, audio_path)

            # Step 3: Summarize (bilingual)
            print("  [3/4] Generating bilingual summary...")
            summary = summarize_episode(ep, transcript["text"])

            # Step 4: Write output
            print("  [4/4] Writing output...")
            output_path = generate_episode_json(ep, summary)
            print(f"  Output: {output_path}")

            # Mark as processed
            state["processed"].append(ep["id"])
            save_state(state)

            # Cleanup audio to conserve disk space
            cleanup_audio(audio_path)

            processed_count += 1
            print("  Done\n")

        except Exception as e:
            print(f"  Error: {e}\n")
            # Attempt cleanup even on error
            try:
                cleanup_audio(audio_path)
            except Exception:
                pass
            continue

    # Rebuild feed index with all episodes
    print("Rebuilding feed index...")
    rebuild_feed_index()

    print(f"\nCompleted. Processed {processed_count}/{len(new_episodes)} episodes.")


if __name__ == "__main__":
    main()
