"""Output generation — episode JSON files and feed index."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

from config import SUMMARIES_DIR, MAX_FEED_INDEX_SIZE


def slugify(text):
    """Convert text to a URL-safe slug."""
    text = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[\s]+', '-', text)[:60]


def make_slug(episode):
    """Generate episode slug with collision handling.

    Format: {YYYY-MM-DD}-{podcast-name-slugified}
    Appends -2, -3, etc. if file already exists.
    """
    date_str = episode["published"][:10]
    podcast_slug = slugify(episode["podcast"])
    base_slug = f"{date_str}-{podcast_slug}"

    # Check for collisions
    slug = base_slug
    suffix = 2
    while (SUMMARIES_DIR / f"{slug}.json").exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    return slug


def generate_episode_json(episode, summary):
    """Write a single episode summary JSON file."""
    SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

    slug = make_slug(episode)

    entry = {
        "id": episode["id"],
        "slug": slug,
        "podcast": episode["podcast"],
        "category": episode["category"],
        "title": episode["title"],
        "published": episode["published"],
        "link": episode.get("link", ""),
        "summary_ko": summary.get("summary_ko", ""),
        "summary_en": summary.get("summary_en", ""),
        "key_points_ko": summary.get("key_points_ko", []),
        "key_points_en": summary.get("key_points_en", []),
        "notable_quote_ko": summary.get("notable_quote_ko", {"text": "", "attribution": ""}),
        "notable_quote_en": summary.get("notable_quote_en", {"text": "", "attribution": ""}),
        "keywords_ko": summary.get("keywords_ko", []),
        "keywords_en": summary.get("keywords_en", []),
        "generated_at": datetime.now().isoformat(),
    }

    filepath = SUMMARIES_DIR / f"{slug}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)

    return str(filepath)


def rebuild_feed_index():
    """Rebuild feed.json from all episode JSON files.

    Scans data/summaries/, sorts by published date (newest first),
    keeps the latest MAX_FEED_INDEX_SIZE entries.
    """
    episodes = []

    for f in SUMMARIES_DIR.glob("*.json"):
        if f.name == "feed.json":
            continue
        try:
            with open(f, encoding="utf-8") as fh:
                ep = json.load(fh)
                if "slug" in ep:
                    episodes.append({
                        "slug": ep["slug"],
                        "podcast": ep["podcast"],
                        "category": ep["category"],
                        "title": ep["title"],
                        "published": ep["published"],
                    })
        except (json.JSONDecodeError, KeyError):
            continue

    # Sort newest first, limit size
    episodes.sort(key=lambda x: x["published"], reverse=True)
    episodes = episodes[:MAX_FEED_INDEX_SIZE]

    feed_path = SUMMARIES_DIR / "feed.json"
    with open(feed_path, "w", encoding="utf-8") as f:
        json.dump(episodes, f, ensure_ascii=False, indent=2)

    return str(feed_path)
