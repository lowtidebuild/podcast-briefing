"""Bilingual summary generation via Claude API."""

import re
import json
import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SUMMARY_PROMPT = """You are a bilingual (Korean/English) podcast analyst. Below is a transcript of a podcast episode.

Podcast: {podcast}
Category: {category}
Title: {title}
Published: {published}

<transcript>
{transcript}
</transcript>

Generate a structured bilingual summary. Korean should use formal register (했습니다/합니다 체). English should be concise and analytical.

CRITICAL Korean text rules:
- Person names: ALWAYS keep in English (e.g., "Torsten Sløk", NOT "토르스텐 슬뢰크")
- Company/organization names: ALWAYS keep in English (e.g., "Apollo", "Federal Reserve", NOT "아폴로", "연방준비제도")
- Technical terms with no standard Korean translation: keep in English
- attribution fields: ALWAYS in English for both languages

Output STRICTLY as a valid JSON object (no markdown, no code fences, just JSON):

{{
  "guest": {{
    "name": "Guest full name in English (or null if no guest / hosts-only episode)",
    "title": "One-line role/affiliation in English (e.g., 'Chief Economist, Apollo Global Management')"
  }},
  "summary_ko": "5-8 sentences summarizing the core arguments in Korean (~300 words)",
  "summary_en": "5-8 sentences summarizing the core arguments in English (~250 words)",
  "key_points_ko": [
    {{"heading": "Korean subheading", "body": "3-4 sentence explanation in Korean"}},
    {{"heading": "Korean subheading", "body": "3-4 sentence explanation in Korean"}},
    {{"heading": "Korean subheading", "body": "3-4 sentence explanation in Korean"}}
  ],
  "key_points_en": [
    {{"heading": "English subheading", "body": "3-4 sentence explanation in English"}},
    {{"heading": "English subheading", "body": "3-4 sentence explanation in English"}},
    {{"heading": "English subheading", "body": "3-4 sentence explanation in English"}}
  ],
  "notable_quote_ko": {{
    "text": "Notable quote translated to Korean (keep names in English)",
    "attribution": "Speaker Name, Role (always English)"
  }},
  "notable_quote_en": {{
    "text": "Original notable quote in English",
    "attribution": "Speaker Name, Role"
  }},
  "keywords_ko": ["keyword1", "keyword2", "keyword3", "keyword4"],
  "keywords_en": ["keyword1", "keyword2", "keyword3", "keyword4"]
}}

Requirements:
- guest: extract the primary guest. Set to null if hosts-only (no guest)
- 3-5 key points per language
- 4-6 keywords per language
- Pick the single most impactful quote from the episode
- Korean summaries: ~300 words, English: ~250 words
- Each key point body: 3-4 sentences with specific details
- Output ONLY the JSON object, nothing else"""


def summarize_episode(episode, transcript_text):
    """Generate bilingual structured summary via Claude.

    Returns dict matching the episode JSON schema.
    """
    # Truncate long transcripts to fit context window
    if len(transcript_text) > 80000:
        transcript_text = (
            transcript_text[:40000]
            + "\n\n[...middle section omitted for length...]\n\n"
            + transcript_text[-40000:]
        )

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=6000,
        messages=[{
            "role": "user",
            "content": SUMMARY_PROMPT.format(
                podcast=episode["podcast"],
                category=episode["category"],
                title=episode["title"],
                published=episode["published"],
                transcript=transcript_text,
            ),
        }],
    )

    raw = response.content[0].text
    return _parse_summary(raw)


def _parse_summary(text):
    """Parse Claude's JSON output into summary dict."""
    # Strip any markdown code fences if present
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"    Warning: Failed to parse summary JSON: {e}")
        return {
            "guest": None,
            "summary_ko": text[:500],
            "summary_en": "",
            "key_points_ko": [],
            "key_points_en": [],
            "notable_quote_ko": {"text": "", "attribution": ""},
            "notable_quote_en": {"text": "", "attribution": ""},
            "keywords_ko": [],
            "keywords_en": [],
        }
