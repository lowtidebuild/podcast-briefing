"""Bilingual summary generation via Claude API."""

import re
import json
import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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
  "summary_ko": "KOREAN: 6-10 sentences (~350 words). Open with why this episode matters (So what?). Then: core thesis, key evidence, and practical implications. Write as if briefing a CEO who has 2 minutes.",
  "summary_en": "ENGLISH: 6-10 sentences (~300 words). Same structure: So what → thesis → evidence → implications. Economist tone — precise, analytical, slightly opinionated.",
  "key_points_ko": [
    {{"heading": "Concise Korean subheading (the claim, not the topic)", "body": "KOREAN: 4-5 sentences. Start with the specific claim or finding. Then provide the evidence or reasoning. End with why this matters or what it implies. Use concrete numbers and names."}},
    {{"heading": "...", "body": "..."}},
    {{"heading": "...", "body": "..."}}
  ],
  "key_points_en": [
    {{"heading": "Concise English subheading (the claim, not the topic)", "body": "ENGLISH: 4-5 sentences. Same structure as Korean. Claim → evidence → implication."}},
    {{"heading": "...", "body": "..."}},
    {{"heading": "...", "body": "..."}}
  ],
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
        max_tokens=8000,
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
