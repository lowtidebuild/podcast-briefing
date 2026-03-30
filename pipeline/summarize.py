"""Bilingual summary generation via LLM API (Claude / Gemini)."""

import re
import json
import anthropic
from google import genai

from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    GOOGLE_API_KEY, GEMINI_MODEL,
)

_anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
_gemini_client = genai.Client(api_key=GOOGLE_API_KEY)

SUMMARY_PROMPT = """You are a senior research analyst writing editorial briefings in the style of The Economist. Your audience is a busy professional who needs to understand not just WHAT was said, but WHY it matters.

Podcast: {podcast}
Category: {category}
Title: {title}
Published: {published}

<transcript>
{transcript}
</transcript>

Write a structured bilingual (Korean/English) briefing following these principles:

ANALYTICAL FRAMEWORK:
1. Lead with the "So what?" — Why should a busy reader care about this episode? What is the single most important insight or argument?
2. Identify the core thesis — What is the speaker's central claim? How does it differ from conventional wisdom?
3. Evaluate the evidence — What data, examples, or reasoning supports the thesis? Are there weaknesses?
4. Draw implications — What does this mean for the reader's understanding of the world, markets, technology, or policy?

WRITING STYLE:
- Authoritative but accessible — assume an intelligent reader who is NOT a domain expert
- Analytical, not descriptive — don't summarize what was said, analyze what it means
- Specific over vague — use concrete numbers, names, examples from the episode
- Opinionated where warranted — if the guest's argument has a flaw, note it
- Every sentence must carry information — zero filler, zero throat-clearing

BANNED PHRASES (never use these — they waste the reader's time):
- "이 에피소드가 중요한 이유는 단순합니다" / "The reason this episode matters is simple"
- "한 마디로 요약하자면" / "In a nutshell"
- "흥미로운 점은" / "What's interesting is"
- "주목할 만한 것은" / "What's noteworthy is"
- "결론적으로" / "In conclusion"
- Any sentence that announces what you're about to say instead of just saying it
- Any generic transition that could appear in any briefing about any topic

KOREAN TEXT RULES (CRITICAL):
- Person names: ALWAYS keep in English (e.g., "Torsten Sløk", NOT "토르스텐 슬뢰크")
- Company/organization names: ALWAYS keep in English (e.g., "Apollo", "Federal Reserve")
- Technical terms with no standard Korean translation: keep in English
- Korean register: formal (했습니다/합니다 체)

Output STRICTLY as a valid JSON object (no markdown, no code fences):

{{
  "guest": {{
    "name": "Guest full name in English (null if hosts-only)",
    "title": "Role, Organization (e.g., 'Chief Economist, Apollo Global Management')"
  }},
  "summary_ko": "KOREAN: Scale length to transcript size. Short (<5000 words): 200-300 words. Medium (5000-15000): 350-450 words. Long (>15000): 450-600 words. IMPORTANT: Use \\n\\n to separate into 2-4 paragraphs by meaning (e.g., context → thesis → evidence → implications). Never write one giant block. Open with why this matters (So what?).",
  "summary_en": "ENGLISH: Scale length to transcript size. Short (<5000 words): 150-250 words. Medium (5000-15000): 300-400 words. Long (>15000): 400-500 words. IMPORTANT: Use \\n\\n to separate into 2-4 paragraphs by meaning. Same structure: So what → thesis → evidence → implications. Economist tone.",
  "key_points_ko": [
    {{"heading": "Concise Korean subheading (the claim, not the topic)", "body": "KOREAN: 4-5 sentences. Claim → evidence → implication. Use concrete numbers and names."}}
  ],
  "key_points_en": [
    {{"heading": "Concise English subheading (the claim, not the topic)", "body": "ENGLISH: 4-5 sentences. Claim → evidence → implication."}}
  ],
  "_key_points_note": "Generate 2-3 key points for short transcripts, 3-4 for medium, 4-5 for long.",
  "notable_quote_ko": {{
    "text": "The single quote that best captures the episode's central thesis, translated to Korean (keep names in English)",
    "attribution": "Speaker Name, Role (always English)"
  }},
  "notable_quote_en": {{
    "text": "The single quote that best captures the episode's central thesis — choose for insight density, not drama",
    "attribution": "Speaker Name, Role"
  }},
  "keywords_en": ["4-6 keywords: specific concepts, not generic categories"],
  "keywords_ko": ["4-6 keywords in Korean where natural, English for proper nouns/technical terms"]
}}

KEY POINT STRUCTURE — follow this flow across points:
1. Context/Background — What's the landscape? What does the reader need to know?
2. Core Argument — What's the speaker's central thesis?
3. Evidence/Data — What supports (or undermines) this argument?
4. Implications — What should the reader do with this information?

Not every episode needs all 4 — adapt to the content. But always lead with the CLAIM in the heading, not the topic.

BAD heading: "AI Agent Market" (topic)
GOOD heading: "90% of enterprise AI pilots fail — and technology isn't the bottleneck" (claim)

QUOTE SELECTION:
Choose the quote that would make someone say "I need to listen to this episode."
It should capture the episode's thesis in one memorable sentence.
Prefer quotes with specific insight over generic wisdom.

BAD: "AI is going to change everything." (generic)
GOOD: "The bond market isn't broken — it's pricing in a world where deficits matter again." (specific thesis)"""


def _build_prompt(episode, transcript_text):
    """Build the summary prompt with truncation if needed."""
    if len(transcript_text) > 80000:
        transcript_text = (
            transcript_text[:40000]
            + "\n\n[...middle section omitted for length...]\n\n"
            + transcript_text[-40000:]
        )
    return SUMMARY_PROMPT.format(
        podcast=episode["podcast"],
        category=episode["category"],
        title=episode["title"],
        published=episode["published"],
        transcript=transcript_text,
    )


def _summarize_claude(prompt, model=None):
    """Call Claude API and return raw text."""
    response = _anthropic_client.messages.create(
        model=model or CLAUDE_MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _summarize_gemini(prompt, model=None):
    """Call Gemini API and return raw text."""
    response = _gemini_client.models.generate_content(
        model=model or GEMINI_MODEL,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            max_output_tokens=8000,
            response_mime_type="application/json",
        ),
    )
    return response.text


PROVIDERS = {
    "claude": _summarize_claude,
    "gemini": _summarize_gemini,
}


def summarize_episode(episode, transcript_text, provider="claude", model=None):
    """Generate bilingual structured summary via LLM.

    Args:
        provider: "claude" or "gemini"
        model: override the default model for the provider
    Returns dict matching the episode JSON schema.
    """
    prompt = _build_prompt(episode, transcript_text)
    fn = PROVIDERS[provider]
    raw = fn(prompt, model=model)
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
