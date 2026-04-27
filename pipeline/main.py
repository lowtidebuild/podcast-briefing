#!/usr/bin/env python3
"""Podcast Briefing Pipeline — Daily Orchestrator.

Processes new podcast episodes sequentially:
RSS parse → audio download → transcribe → summarize → output → cleanup
"""

import sys
import os
import json

# Add pipeline directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_feeds import load_feeds, load_state, save_state, fetch_new_episodes
from download_audio import download_audio, cleanup_audio
from transcribe import get_transcript
from summarize import summarize_episode_with_result
from generate_output import generate_episode_json, rebuild_feed_index, make_slug
from config import SUMMARIES_DIR, TRANSCRIPTS_DIR
from sheets import append_episode
from quality import validate_summary
from failures import write_summary_failure
from quotes import ground_summary_quote
from state import update_episode_state


def _episode_from_summary_entry(entry):
    return {
        "id": entry.get("id", ""),
        "podcast": entry.get("podcast", ""),
        "category": entry.get("category", ""),
        "title": entry.get("title", ""),
        "published": entry.get("published", ""),
        "link": entry.get("link", ""),
        "podcast_url": entry.get("podcast_url", ""),
    }


def retry_failed_sheet_updates(state):
    """Retry Sheets appends for episodes already published to JSON."""
    for episode_id, episode_state in list(state.get("episodes", {}).items()):
        if episode_state.get("status") != "sheets_failed":
            continue

        slug = episode_state.get("slug")
        if not slug:
            continue
        summary_path = SUMMARIES_DIR / f"{slug}.json"
        if not summary_path.exists():
            state = update_episode_state(
                state,
                episode_id,
                "sheets_failed",
                slug=slug,
                stage="sheets_retry",
                error=f"summary file missing for Sheets retry: {summary_path}",
            )
            continue

        try:
            with open(summary_path, encoding="utf-8") as f:
                summary_entry = json.load(f)
            result = append_episode(
                _episode_from_summary_entry(summary_entry),
                summary_entry,
                slug,
            )
        except Exception as e:
            result = None
            error = str(e)
        else:
            error = result.error if result else "Google Sheets retry failed"

        if result and result.ok:
            state = update_episode_state(
                state,
                episode_id,
                "published",
                slug=slug,
                stage="sheets_retry",
                error=None,
                usage={"sheets_configured": result.configured},
            )
        else:
            state = update_episode_state(
                state,
                episode_id,
                "sheets_failed",
                slug=slug,
                stage="sheets_retry",
                error=error,
            )

    return state


def main():
    feeds = load_feeds()
    state = load_state()
    state = retry_failed_sheet_updates(state)
    save_state(state)

    print(f"Checking {len(feeds)} podcast feeds...")
    new_episodes = fetch_new_episodes(feeds, state)

    if not new_episodes:
        print("No new episodes found.")
        rebuild_feed_index()
        return

    print(f"Found {len(new_episodes)} new episode(s)\n")
    processed_count = 0

    for ep in new_episodes:
        audio_path = None
        slug = state.get("episodes", {}).get(ep["id"], {}).get("slug") or make_slug(ep)
        current_stage = "discovered"
        try:
            print(f"--- {ep['podcast']}: {ep['title']}")
            state = update_episode_state(
                state,
                ep["id"],
                "discovered",
                slug=slug,
                stage="discovered",
                increment_attempt=True,
            )
            save_state(state)

            # Step 1: Download audio
            print("  [1/6] Downloading audio...")
            current_stage = "download"
            audio_path = download_audio(ep)
            state = update_episode_state(
                state,
                ep["id"],
                "downloaded",
                slug=slug,
                stage="download",
            )
            save_state(state)

            # Step 2: Transcribe
            print("  [2/6] Transcribing...")
            current_stage = "transcribe"
            transcript = get_transcript(ep, audio_path)
            state = update_episode_state(
                state,
                ep["id"],
                "transcribed",
                slug=slug,
                stage="transcribe",
            )
            save_state(state)

            # Step 3: Save transcript
            print("  [3/6] Saving transcript...")
            current_stage = "transcript_save"
            TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
            with open(TRANSCRIPTS_DIR / f"{slug}.txt", "w", encoding="utf-8") as f:
                f.write(transcript["text"])

            # Step 4: Summarize (bilingual)
            print("  [4/6] Generating bilingual summary...")
            current_stage = "summary"
            generation = summarize_episode_with_result(
                ep,
                transcript["text"],
                slug=slug,
            )
            if generation.summary is not None:
                quote_grounding = ground_summary_quote(
                    generation.summary,
                    transcript["text"],
                    slug=slug,
                )
                generation.summary = quote_grounding.summary
                generation.warnings.extend(quote_grounding.warnings)
                if quote_grounding.report_path:
                    generation.artifacts["quote_grounding"] = quote_grounding.report_path
                generation.usage.update(quote_grounding.usage)

            validation = validate_summary(
                generation.summary,
                raw_text=generation.raw_text,
            )
            if not validation.ok:
                status = (
                    "summary_failed"
                    if generation.summary is None
                    else "validation_failed"
                )
                failure_path = write_summary_failure(
                    ep,
                    slug,
                    generation,
                    validation,
                )
                print("  Summary validation failed:")
                for error in getattr(generation, "errors", []):
                    print(f"    - {error}")
                for error in validation.errors:
                    print(f"    - {error}")
                generation_warnings = getattr(generation, "warnings", [])
                if generation_warnings or validation.warnings:
                    print("  Summary validation warnings:")
                    for warning in generation_warnings:
                        print(f"    - {warning}")
                    for warning in validation.warnings:
                        print(f"    - {warning}")
                print(f"  Failure artifact: {failure_path}\n")
                state = update_episode_state(
                    state,
                    ep["id"],
                    status,
                    slug=slug,
                    stage=getattr(generation, "stage", "summary_validation"),
                    error="; ".join(
                        list(getattr(generation, "errors", [])) + validation.errors
                    ),
                    warnings=list(getattr(generation, "warnings", []))
                    + validation.warnings,
                    artifacts={
                        **getattr(generation, "artifacts", {}),
                        "failure": failure_path,
                    },
                    usage=getattr(generation, "usage", {}),
                )
                save_state(state)
                if audio_path:
                    cleanup_audio(audio_path)
                    audio_path = None
                continue

            summary = validation.sanitized_summary
            generation_warnings = getattr(generation, "warnings", [])
            if generation_warnings or validation.warnings:
                print("  Summary validation warnings:")
                for warning in generation_warnings:
                    print(f"    - {warning}")
                for warning in validation.warnings:
                    print(f"    - {warning}")

            # Step 5: Write output
            print("  [5/6] Writing output...")
            current_stage = "publish"
            output_path = generate_episode_json(ep, summary, slug=slug)
            print(f"  Output: {output_path}")
            state = update_episode_state(
                state,
                ep["id"],
                "published",
                slug=slug,
                stage="publish",
                artifacts={
                    **getattr(generation, "artifacts", {}),
                    "summary": output_path,
                },
                usage=getattr(generation, "usage", {}),
            )
            save_state(state)

            # Step 6: Google Sheets
            print("  [6/6] Updating Google Sheet...")
            current_stage = "sheets"
            sheets_result = append_episode(ep, summary, slug)
            if not sheets_result.ok:
                state = update_episode_state(
                    state,
                    ep["id"],
                    "sheets_failed",
                    slug=slug,
                    stage="sheets",
                    error=sheets_result.error or "Google Sheets append failed",
                )
            else:
                state = update_episode_state(
                    state,
                    ep["id"],
                    "published",
                    slug=slug,
                    stage="sheets",
                    usage={"sheets_configured": sheets_result.configured},
                )
            save_state(state)

            # Cleanup audio to conserve disk space
            cleanup_audio(audio_path)
            audio_path = None

            processed_count += 1
            print("  Done\n")

        except Exception as e:
            print(f"  Error: {e}\n")
            failed_status = {
                "download": "download_failed",
                "transcribe": "transcribe_failed",
                "transcript_save": "transcript_save_failed",
                "summary": "summary_failed",
                "publish": "publish_failed",
                "sheets": "sheets_failed",
            }.get(current_stage, "publish_failed")
            state = update_episode_state(
                state,
                ep["id"],
                failed_status,
                slug=slug,
                stage=current_stage,
                error=str(e),
            )
            save_state(state)
            # Attempt cleanup even on error
            if audio_path:
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
