# Podcast Briefing Pipeline — Design Document

## 1. Overview

An automated pipeline that detects new episodes from 9 English-language podcasts, generates transcripts, produces bilingual (Korean/English) structured summaries via Claude API, and deploys outputs simultaneously to an Obsidian vault and a static web app.

```
┌──────────────────────────────────────────────────────────┐
│                   GitHub Actions (Cron)                    │
│                   Daily at 06:00 UTC                      │
│                                                           │
│  ① Parse RSS feeds → detect new episodes                  │
│  ② Download audio (MP3)                                   │
│  ③ Whisper API → English transcript                       │
│  ④ Claude API → bilingual structured summary (KO + EN)    │
│  ⑤ Generate outputs (Markdown + JSON)                     │
│  ⑥ Git commit & push                                     │
│                                                           │
│  Output:                                                  │
│  ├── /obsidian/  → Obsidian vault sync (personal, KO)     │
│  └── /web/data/  → Static web app data (shared, KO/EN)    │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Repository Structure

```
podcast-briefing/
├── .github/
│   └── workflows/
│       └── daily-briefing.yml      # GitHub Actions workflow
├── src/
│   ├── fetch_feeds.py              # RSS parsing + new episode detection
│   ├── download_audio.py           # MP3 download
│   ├── transcribe.py               # Whisper API calls
│   ├── summarize.py                # Claude API calls (bilingual summary)
│   ├── generate_output.py          # Markdown + JSON output generation
│   └── config.py                   # Feed list, API config
├── config/
│   └── feeds.yaml                  # Podcast RSS feed list
├── data/
│   ├── state.json                  # Processed episode ID tracking
│   ├── transcripts/                # Transcript storage (optional)
│   └── summaries/                  # Summary JSON storage
├── obsidian/                       # Obsidian vault markdown output
│   └── Podcast Briefings/
│       └── 2026-03-20-hard-fork.md
├── web/
│   ├── index.html                  # Web app (single file or React)
│   └── data/
│       ├── feed.json               # Recent summary index (read by web app)
│       └── episodes/               # Per-episode detail JSON
├── requirements.txt
└── README.md
```

---

## 3. feeds.yaml

```yaml
podcasts:
  - name: "Odd Lots"
    category: "Macro / Markets"
    rss: "https://feeds.bloomberg.com/podcasts/odd_lots.xml"
    frequency: "2-3/week"
    transcript_source: "whisper"

  - name: "Dwarkesh Podcast"
    category: "AI / Tech Deep Dive"
    rss: "https://apple.dwarkesh-podcast.workers.dev/feed.rss"
    frequency: "biweekly"
    transcript_source: "substack_fallback"  # Try Substack text first, fall back to Whisper

  - name: "Fareed Zakaria GPS"
    category: "Geopolitics"
    rss: "https://feeds.megaphone.fm/WMHY7703459968"
    frequency: "weekly"
    transcript_source: "whisper"

  - name: "Hard Fork"
    category: "Tech / AI Current Affairs"
    rss: "https://feeds.simplecast.com/l2i9YnTd"
    frequency: "weekly"
    transcript_source: "whisper"

  - name: "a16z Podcast"
    category: "VC / Tech Business"
    rss: "https://feeds.simplecast.com/JGE3yC0V"
    frequency: "2-3/week"
    transcript_source: "whisper"

  - name: "Ezra Klein Show"
    category: "Politics / Policy"
    rss: "https://feeds.simplecast.com/82FI35Px"
    frequency: "1-2/week"
    transcript_source: "whisper"

  - name: "All-In Podcast"
    category: "Tech × Politics × Economics"
    rss: "https://rss.libsyn.com/shows/254861/destinations/1928300.xml"
    frequency: "1-2/week"
    transcript_source: "whisper"

  - name: "Lex Fridman Podcast"
    category: "AI / Science / Philosophy"
    rss: "https://lexfridman.com/feed/podcast/"
    frequency: "biweekly"
    transcript_source: "whisper"

  - name: "Exponential View"
    category: "AI × Energy × Geopolitics"
    rss: "https://feeds.simplecast.com/e_GRxR9a"
    frequency: "weekly"
    transcript_source: "whisper"
```

---

## 4. Step-by-Step Design

### Step 1: RSS Parsing (`fetch_feeds.py`)

```python
import feedparser
import yaml
import json
from datetime import datetime
from email.utils import parsedate_to_datetime

def load_feeds(config_path="config/feeds.yaml"):
    with open(config_path) as f:
        return yaml.safe_load(f)["podcasts"]

def load_state(state_path="data/state.json"):
    try:
        with open(state_path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"processed": []}

def fetch_new_episodes(feeds, state):
    new_episodes = []
    for pod in feeds:
        feed = feedparser.parse(pod["rss"])
        for entry in feed.entries[:3]:  # Check latest 3 only
            episode_id = entry.get("id") or entry.get("link") or entry.get("title")
            if episode_id in state["processed"]:
                continue

            audio_url = None
            for enc in entry.get("enclosures", []):
                if enc.get("type", "").startswith("audio"):
                    audio_url = enc["href"]
                    break

            if audio_url:
                pub_date = entry.get("published", "")
                try:
                    pub_dt = parsedate_to_datetime(pub_date)
                except:
                    pub_dt = datetime.now()

                new_episodes.append({
                    "id": episode_id,
                    "podcast": pod["name"],
                    "category": pod["category"],
                    "title": entry.get("title", "Untitled"),
                    "published": pub_dt.isoformat(),
                    "audio_url": audio_url,
                    "link": entry.get("link", ""),
                    "transcript_source": pod["transcript_source"],
                    "description": entry.get("summary", "")[:500],
                })
    return new_episodes
```

### Step 2: Audio Download (`download_audio.py`)

```python
import requests
import os
from pathlib import Path

def download_audio(episode, output_dir="data/audio"):
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    slug = slugify(f"{episode['podcast']}-{episode['title']}")
    filepath = os.path.join(output_dir, f"{slug}.mp3")

    if os.path.exists(filepath):
        return filepath

    resp = requests.get(episode["audio_url"], stream=True, timeout=120)
    resp.raise_for_status()
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return filepath

def slugify(text):
    import re
    text = re.sub(r'[^\w\s-]', '', text.lower())
    return re.sub(r'[\s]+', '-', text)[:80]
```

### Step 3: Transcript Generation (`transcribe.py`)

```python
import openai
import os

client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def transcribe_audio(audio_path):
    """Whisper API — $0.006/min"""
    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    return {
        "text": result.text,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in result.segments
        ]
    }

def fetch_substack_transcript(episode_link):
    """For Substack-based podcasts (e.g. Dwarkesh) — skip STT if text available"""
    import requests
    from bs4 import BeautifulSoup
    try:
        resp = requests.get(episode_link, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        body = soup.select_one(".body.markup")
        if body and len(body.get_text()) > 2000:
            return {"text": body.get_text(separator="\n"), "segments": []}
    except:
        pass
    return None

def get_transcript(episode, audio_path):
    # Try Substack text first for substack_fallback sources
    if episode.get("transcript_source") == "substack_fallback":
        transcript = fetch_substack_transcript(episode.get("link", ""))
        if transcript:
            return transcript

    # Default: Whisper API
    return transcribe_audio(audio_path)
```

### Step 4: Bilingual Summary Generation (`summarize.py`)

```python
import anthropic
import os
import re

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SUMMARY_PROMPT = """Below is a transcript of a podcast episode.

Podcast: {podcast}
Category: {category}
Title: {title}
Published: {published}

<transcript>
{transcript}
</transcript>

Generate summaries in both Korean and English.
Korean: use formal register (했습니다/합니다 체).
English: use concise, analytical tone.

Output strictly in the following XML tag structure:

<ko>
## 핵심 요약 (3-5문장)
에피소드의 핵심 논점을 간결하게 요약합니다.

## 주요 논점
각 논점을 소제목과 함께 2-3문장으로 정리합니다.

## 인용할 만한 발언
게스트나 호스트의 주요 발언을 원문(영어)과 함께 정리합니다.

## 연관 키워드
쉼표로 구분된 키워드 목록 (Obsidian 태그용)
</ko>

<en>
## Key Takeaways (3-5 sentences)
Concise summary of the episode's core arguments.

## Main Points
Each point with a subheading and 2-3 sentence explanation.

## Notable Quotes
Key statements from guests or hosts, with context.

## Keywords
Comma-separated keyword list
</en>
"""

def summarize_episode(episode, transcript_text):
    """Generate bilingual summary. Returns dict: {"ko": "...", "en": "..."}"""

    # Token limit handling: sample beginning + end for long transcripts
    if len(transcript_text) > 80000:
        transcript_text = (
            transcript_text[:40000]
            + "\n\n[...truncated...]\n\n"
            + transcript_text[-40000:]
        )

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=6000,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(
                podcast=episode["podcast"],
                category=episode["category"],
                title=episode["title"],
                published=episode["published"],
                transcript=transcript_text,
            )
        }]
    )

    raw = response.content[0].text
    return parse_bilingual(raw)


def parse_bilingual(text):
    """Split <ko>...</ko> and <en>...</en> blocks"""
    ko = extract_tag(text, "ko") or text  # Fallback: treat entire output as KO
    en = extract_tag(text, "en") or ""
    return {"ko": ko.strip(), "en": en.strip()}


def extract_tag(text, tag):
    pattern = rf"<{tag}>(.*?)</{tag}>"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None
```

### Step 5: Output Generation (`generate_output.py`)

```python
import json
import os
from datetime import datetime
from pathlib import Path

def generate_obsidian_md(episode, summary):
    """Obsidian vault markdown — Korean only"""
    date_str = episode["published"][:10]
    slug = episode["podcast"].lower().replace(" ", "-").replace("(", "").replace(")", "")
    filename = f"{date_str}-{slug}.md"

    # summary is {"ko": "...", "en": "..."} dict
    ko_summary = summary["ko"] if isinstance(summary, dict) else summary

    content = f"""---
podcast: "{episode['podcast']}"
category: "{episode['category']}"
title: "{episode['title']}"
date: {date_str}
link: "{episode.get('link', '')}"
type: podcast-briefing
---

# {episode['title']}
> **{episode['podcast']}** | {episode['category']} | {date_str}

{ko_summary}

---
*Auto-generated by Podcast Briefing Pipeline*
"""

    output_dir = "obsidian/Podcast Briefings"
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w") as f:
        f.write(content)
    return filepath


def generate_web_json(episode, summary):
    """Web app JSON — both KO and EN included (toggled in UI)"""
    date_str = episode["published"][:10]
    slug = episode["podcast"].lower().replace(" ", "-")

    if isinstance(summary, dict):
        summary_ko = summary["ko"]
        summary_en = summary["en"]
    else:
        summary_ko = summary
        summary_en = ""

    entry = {
        "id": episode["id"],
        "podcast": episode["podcast"],
        "category": episode["category"],
        "title": episode["title"],
        "published": episode["published"],
        "link": episode.get("link", ""),
        "summary_ko": summary_ko,
        "summary_en": summary_en,
        "generated_at": datetime.now().isoformat(),
    }

    # Per-episode detail JSON
    ep_dir = "web/data/episodes"
    Path(ep_dir).mkdir(parents=True, exist_ok=True)
    ep_path = os.path.join(ep_dir, f"{date_str}-{slug}.json")
    with open(ep_path, "w") as f:
        json.dump(entry, f, ensure_ascii=False, indent=2)

    # Append to feed.json (keep latest 50)
    feed_path = "web/data/feed.json"
    try:
        with open(feed_path) as f:
            feed = json.load(f)
    except FileNotFoundError:
        feed = []

    feed.insert(0, {
        "podcast": entry["podcast"],
        "category": entry["category"],
        "title": entry["title"],
        "published": entry["published"],
        "file": f"episodes/{date_str}-{slug}.json",
    })
    feed = feed[:50]

    with open(feed_path, "w") as f:
        json.dump(feed, f, ensure_ascii=False, indent=2)

    return ep_path
```

---

## 5. GitHub Actions Workflow

```yaml
# .github/workflows/daily-briefing.yml
name: Daily Podcast Briefing

on:
  schedule:
    - cron: '0 6 * * *'  # Daily at 06:00 UTC (15:00 KST)
  workflow_dispatch:        # Manual trigger

jobs:
  briefing:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run pipeline
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python src/main.py

      - name: Commit and push
        run: |
          git config user.name "podcast-bot"
          git config user.email "bot@example.com"
          git add data/ obsidian/ web/
          git diff --cached --quiet || git commit -m "briefing: $(date +%Y-%m-%d)"
          git push

      - name: Deploy web (GitHub Pages)
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./web
```

---

## 6. Orchestrator (`main.py`)

```python
#!/usr/bin/env python3
"""Podcast Briefing Pipeline — Daily Orchestrator"""

from fetch_feeds import load_feeds, load_state, fetch_new_episodes
from download_audio import download_audio
from transcribe import get_transcript
from summarize import summarize_episode
from generate_output import generate_obsidian_md, generate_web_json
import json
import os

def main():
    feeds = load_feeds()
    state = load_state()
    new_episodes = fetch_new_episodes(feeds, state)

    if not new_episodes:
        print("No new episodes found.")
        return

    print(f"Found {len(new_episodes)} new episode(s)")

    for ep in new_episodes:
        try:
            print(f"\n--- Processing: {ep['podcast']} — {ep['title']}")

            # Step 1: Download
            print("  Downloading audio...")
            audio_path = download_audio(ep)

            # Step 2: Transcribe
            print("  Transcribing...")
            transcript = get_transcript(ep, audio_path)

            # Step 3: Summarize (bilingual)
            print("  Generating bilingual summary...")
            summary = summarize_episode(ep, transcript["text"])

            # Step 4: Output
            print("  Writing outputs...")
            generate_obsidian_md(ep, summary)
            generate_web_json(ep, summary)

            # Step 5: Mark as processed
            state["processed"].append(ep["id"])

            # Cleanup: delete audio file (save GitHub Actions storage)
            os.remove(audio_path)

            print("  Done")

        except Exception as e:
            print(f"  Error: {e}")
            continue

    # Save state
    with open("data/state.json", "w") as f:
        json.dump(state, f, indent=2)

    print(f"\nCompleted. Processed {len(new_episodes)} episodes.")

if __name__ == "__main__":
    main()
```

---

## 7. Cost Estimate

| Item | Unit Price | Est. Monthly Usage | Monthly Cost |
|------|-----------|-------------------|-------------|
| Whisper API | $0.006/min | ~800 min (8 feeds × 12-15 ep/week × 40 min) | ~$5 |
| Claude API (Haiku, bilingual) | ~$0.25/M input, $1.25/M output | ~2M input + ~1M output tokens/mo | ~$2 |
| GitHub Actions | Free (public repo) or 2,000 min/mo (free tier) | ~30 min/day | $0 |
| **Total** | | | **~$7/month** |

> **Note**: Switching from Sonnet to Haiku and adding bilingual output still results in lower total cost — the output token increase is offset by Haiku's lower per-token price. If summary quality proves insufficient, switch to Sonnet (~$13/month).

---

## 8. Obsidian Integration

### Option A: Git Sync (Recommended)
- Use the Obsidian Git plugin to connect the repo's `obsidian/` folder to your vault
- Configure auto-pull so new briefings appear shortly after pipeline execution

### Option B: Symlink into Vault
- Clone the repo and symlink `obsidian/Podcast Briefings/` into your vault root

---

## 9. Web App Deployment

- Deploy the `web/` folder via GitHub Pages
- The web app fetches `web/data/feed.json` and renders episode summary cards
- **KO/EN toggle**: each episode JSON includes both `summary_ko` and `summary_en` fields, enabling one-click language switching in the UI
- Custom domain supported (e.g., `briefing.example.com`)
- Web app prototype to be designed separately

---

## 10. Future Extensions

- Add Korean podcast sources (e.g., Schuka World) via YouTube subtitle extraction
- Weekly cross-source synthesis briefing (all 9 sources analyzed together)
- Obsidian Dataview queries for category/keyword filtering
- Telegram/Slack notification integration
