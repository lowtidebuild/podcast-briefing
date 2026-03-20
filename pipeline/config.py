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

# Model choice — switch between sonnet and haiku
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250514")
# Fallback models if the above is unavailable:
# "claude-sonnet-4-5-20250514", "claude-haiku-4-5-20251001"

# Whisper settings
WHISPER_MODEL = "whisper-1"
MAX_AUDIO_SIZE_MB = 25

# Feed limits
MAX_ENTRIES_PER_FEED = 3
MIN_EPISODE_DURATION_SEC = 600  # Skip episodes shorter than 10 min
MAX_FEED_INDEX_SIZE = 50
