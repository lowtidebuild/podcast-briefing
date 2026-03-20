"""Transcript generation via Whisper API with Substack fallback."""

import os
import openai
import requests
from bs4 import BeautifulSoup

from config import OPENAI_API_KEY, WHISPER_MODEL
from download_audio import get_audio_chunks

client = openai.OpenAI(api_key=OPENAI_API_KEY)


def transcribe_audio(audio_path):
    """Transcribe audio file via Whisper API.

    Handles chunked audio for files exceeding 25MB limit.
    Returns dict with 'text' key.
    """
    chunks = get_audio_chunks(audio_path)
    all_text = []

    for chunk_path in chunks:
        with open(chunk_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=f,
                response_format="text",
            )
        all_text.append(result)

    return {"text": " ".join(all_text)}


def fetch_substack_transcript(episode_link):
    """Try to extract transcript text from a Substack post.

    For podcasts like Dwarkesh that publish transcripts on Substack.
    Returns transcript dict if found (>5000 chars), else None.
    """
    if not episode_link:
        return None

    try:
        resp = requests.get(episode_link, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Substack transcript body
        body = soup.select_one(".body.markup") or soup.select_one(".body")
        if body:
            text = body.get_text(separator="\n")
            if len(text) > 5000:
                return {"text": text}

    except Exception as e:
        print(f"    Substack fetch failed: {e}")

    return None


def get_transcript(episode, audio_path):
    """Get transcript for an episode.

    For substack_fallback sources, tries Substack text first.
    Falls back to Whisper API for all other cases.
    """
    if episode.get("transcript_source") == "substack_fallback":
        transcript = fetch_substack_transcript(episode.get("link", ""))
        if transcript:
            print("    Using Substack transcript")
            return transcript

    print("    Transcribing via Whisper API...")
    return transcribe_audio(audio_path)
