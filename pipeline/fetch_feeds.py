"""RSS feed parsing and new episode detection."""

import json
import feedparser
import yaml
from datetime import datetime
from email.utils import parsedate_to_datetime

from config import CONFIG_PATH, STATE_PATH, MAX_ENTRIES_PER_FEED
from state import is_episode_complete, normalize_state


def load_feeds():
    """Load podcast feed configuration from YAML."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)["podcasts"]


def load_state():
    """Load pipeline state. Re-initialize if missing or corrupt."""
    try:
        with open(STATE_PATH) as f:
            return normalize_state(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return normalize_state({})


def save_state(state):
    """Write state back to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(normalize_state(state), f, indent=2)


def _get_episode_id(entry):
    """Extract a stable episode ID from an RSS entry."""
    return entry.get("id") or entry.get("link") or entry.get("title")


def _get_audio_url(entry):
    """Extract audio URL from RSS enclosures or media:content."""
    # Standard enclosures
    for enc in entry.get("enclosures", []):
        if enc.get("type", "").startswith("audio"):
            return enc.get("href") or enc.get("url")

    # media:content fallback (used by some feeds like a16z)
    for mc in entry.get("media_content", []):
        if mc.get("type", "").startswith("audio"):
            return mc.get("url")

    # links with audio type
    for link in entry.get("links", []):
        if link.get("type", "").startswith("audio"):
            return link.get("href")

    return None


def _parse_date(entry):
    """Parse publish date from RSS entry."""
    pub_date = entry.get("published", "")
    try:
        return parsedate_to_datetime(pub_date)
    except Exception:
        return datetime.now()


def _estimate_duration(entry):
    """Estimate episode duration in seconds from RSS metadata."""
    # itunes:duration field
    duration = entry.get("itunes_duration", "")
    if duration:
        parts = str(duration).split(":")
        try:
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            else:
                return int(parts[0])
        except ValueError:
            pass
    return None  # Unknown duration — process anyway


def fetch_new_episodes(feeds, state):
    """Check all feeds and return list of new (unprocessed) episodes."""
    new_episodes = []

    for pod in feeds:
        try:
            feed = feedparser.parse(pod["rss"])
            if feed.bozo and not feed.entries:
                print(f"  Warning: Failed to parse RSS for {pod['name']}")
                continue

            for entry in feed.entries[:MAX_ENTRIES_PER_FEED]:
                episode_id = _get_episode_id(entry)
                if not episode_id or is_episode_complete(state, episode_id):
                    continue

                audio_url = _get_audio_url(entry)
                if not audio_url:
                    continue

                # Skip short episodes (trailers, promos)
                duration = _estimate_duration(entry)
                if duration is not None and duration < 600:
                    continue

                pub_dt = _parse_date(entry)

                new_episodes.append({
                    "id": episode_id,
                    "podcast": pod["name"],
                    "category": pod["display_category"],
                    "podcast_url": pod.get("homepage", ""),
                    "title": entry.get("title", "Untitled"),
                    "published": pub_dt.isoformat(),
                    "audio_url": audio_url,
                    "link": entry.get("link", ""),
                    "transcript_source": pod.get("transcript_source", "whisper"),
                    "description": entry.get("summary", "")[:500],
                })

        except Exception as e:
            print(f"  Error fetching {pod['name']}: {e}")
            continue

    return new_episodes
