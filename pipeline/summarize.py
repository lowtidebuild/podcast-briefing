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

Output STRICTLY as a valid JSON object with this exact structure (no markdown, no code fences, just JSON):

{{
  "summary_ko": "3-5 sentences summarizing the core arguments in Korean",
  "summary_en": "3-5 sentences summarizing the core arguments in English",
  "key_points_ko": [
    {{"heading": "Korean subheading", "body": "2-3 sentence explanation in Korean"}},
    {{"heading": "Korean subheading", "body": "2-3 sentence explanation in Korean"}}
  ],
  "key_points_en": [
    {{"heading": "English subheading", "body": "2-3 sentence explanation in English"}},
    {{"heading": "English subheading", "body": "2-3 sentence explanation in English"}}
  ],
  "notable_quote_ko": {{
    "text": "Translated notable quote in Korean",
    "attribution": "Speaker name in Korean"
  }},
  "notable_quote_en": {{
    "text": "Original notable quote in English",
    "attribution": "Speaker name"
  }},
  "keywords_ko": ["keyword1", "keyword2", "keyword3"],
  "keywords_en": ["keyword1", "keyword2", "keyword3"]
}}

Requirements:
- 2-4 key points per language
- 3-5 keywords per language
- Pick the single most impactful quote from the episode
- Korean summaries should be ~150 words, English ~120 words
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
        max_tokens=4000,
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
        # Fallback: return raw text as summary
        return {
            "summary_ko": text[:500],
            "summary_en": "",
            "key_points_ko": [],
            "key_points_en": [],
            "notable_quote_ko": {"text": "", "attribution": ""},
            "notable_quote_en": {"text": "", "attribution": ""},
            "keywords_ko": [],
            "keywords_en": [],
        }
