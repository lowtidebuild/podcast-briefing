"""Pipeline configuration and paths."""

import os
from pathlib import Path

# Paths (relative to repo root)
REPO_ROOT = Path(__file__).parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "feeds.yaml"
STATE_PATH = REPO_ROOT / "data" / "state.json"
SUMMARIES_DIR = REPO_ROOT / "data" / "summaries"
AUDIO_DIR = REPO_ROOT / "data" / "audio"
TRANSCRIPTS_DIR = REPO_ROOT / "data" / "transcripts"

# API settings
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Model choice — use CLAUDE_MODEL env var to override
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# Whisper settings
WHISPER_MODEL = "gpt-4o-mini-transcribe"
MAX_AUDIO_SIZE_MB = 25

# Feed limits
MAX_ENTRIES_PER_FEED = 1
MIN_EPISODE_DURATION_SEC = 600  # Skip episodes shorter than 10 min
MAX_FEED_INDEX_SIZE = 50
