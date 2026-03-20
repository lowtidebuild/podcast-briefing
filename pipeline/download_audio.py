"""Audio download and preprocessing for Whisper API."""

import os
import re
import subprocess
import requests
from pathlib import Path

from config import AUDIO_DIR, MAX_AUDIO_SIZE_MB


def slugify(text):
    """Convert text to a URL-safe slug."""
    text = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[\s]+', '-', text)[:80]


def download_audio(episode):
    """Download podcast audio and preprocess for Whisper.

    Returns path to processed audio file ready for Whisper API.
    """
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    slug = slugify(f"{episode['podcast']}-{episode['title']}")
    raw_path = AUDIO_DIR / f"{slug}-raw.mp3"
    processed_path = AUDIO_DIR / f"{slug}.mp3"

    # Skip if already processed
    if processed_path.exists():
        return str(processed_path)

    # Download
    print(f"    Downloading from {episode['audio_url'][:80]}...")
    resp = requests.get(episode["audio_url"], stream=True, timeout=120)
    resp.raise_for_status()
    with open(raw_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    # Convert to mono 16kHz MP3 to reduce file size (~40% reduction)
    print("    Converting to mono 16kHz...")
    try:
        subprocess.run(
            [
                "ffmpeg", "-i", str(raw_path),
                "-ac", "1",          # mono
                "-ar", "16000",      # 16kHz sample rate
                "-b:a", "64k",       # 64kbps bitrate
                "-y",                # overwrite
                str(processed_path),
            ],
            capture_output=True,
            timeout=300,
            check=True,
        )
        # Remove raw file
        raw_path.unlink(missing_ok=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # ffmpeg not available or failed — use raw file directly
        print(f"    Warning: ffmpeg conversion failed ({e}), using raw audio")
        if raw_path.exists():
            raw_path.rename(processed_path)

    return str(processed_path)


def get_audio_chunks(audio_path):
    """Split audio into chunks if it exceeds Whisper's 25MB limit.

    Returns list of file paths (single element if no splitting needed).
    """
    size_mb = os.path.getsize(audio_path) / (1024 * 1024)

    if size_mb <= MAX_AUDIO_SIZE_MB:
        return [audio_path]

    # Split into chunks using ffmpeg
    print(f"    Audio is {size_mb:.1f}MB, splitting into chunks...")
    chunk_duration = 1200  # 20 minutes per chunk
    base = audio_path.replace(".mp3", "")
    chunks = []

    try:
        # Get total duration
        result = subprocess.run(
            ["ffprobe", "-i", audio_path, "-show_entries", "format=duration",
             "-v", "quiet", "-of", "csv=p=0"],
            capture_output=True, text=True, timeout=30,
        )
        total_duration = float(result.stdout.strip())

        offset = 0
        idx = 0
        while offset < total_duration:
            chunk_path = f"{base}-chunk{idx}.mp3"
            subprocess.run(
                [
                    "ffmpeg", "-i", audio_path,
                    "-ss", str(offset),
                    "-t", str(chunk_duration),
                    "-y", chunk_path,
                ],
                capture_output=True, timeout=300, check=True,
            )
            chunks.append(chunk_path)
            offset += chunk_duration
            idx += 1

    except Exception as e:
        print(f"    Warning: Chunk splitting failed ({e}), attempting with full file")
        return [audio_path]

    return chunks


def cleanup_audio(audio_path):
    """Delete audio file and any chunks to free disk space."""
    base = audio_path.replace(".mp3", "")
    Path(audio_path).unlink(missing_ok=True)

    # Clean up chunks
    import glob
    for chunk in glob.glob(f"{base}-chunk*.mp3"):
        Path(chunk).unlink(missing_ok=True)
