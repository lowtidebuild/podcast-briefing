"""Episode-level synthesis from chunk extraction artifacts."""

import json
from datetime import datetime
from pathlib import Path

from config import INTERMEDIATE_DIR
from extraction import extract_episode_chunks


SYNTHESIS_PROMPT_VERSION = "episode-synthesis-v1"


SYNTHESIS_PROMPT = """You are writing a bilingual analytical podcast briefing from chunk-level evidence.

Podcast: {podcast}
Category: {category}
Title: {title}
Published: {published}
Transcript length: {transcript_chars} characters

You do NOT have the full transcript. You have grounded extraction notes from every transcript chunk.
Use the notes to synthesize the episode-level argument. Do not invent facts outside the notes.

Analytical requirements:
- Lead with the "So what?" and the core thesis.
- Preserve coverage across the full episode. Do not overweight the first or last chunk.
- Key points must be claims, not topic labels.
- Mention concrete evidence and named entities when available.
- If a guest is uncertain or the episode is hosts-only, set guest to null.
- Pick notable_quote_en from quote_candidates only. The Korean quote should be a translation of that selected English quote.

Output STRICTLY as valid JSON with this shape:

{{
  "guest": {{
    "name": "Guest full name in English, or null if hosts-only",
    "title": "Role, Organization"
  }},
  "summary_ko": "KOREAN: 450-600 words across 2-4 paragraphs separated by \\n\\n. Formal Korean. Keep person/company names in English.",
  "summary_en": "ENGLISH: 400-500 words across 2-4 paragraphs separated by \\n\\n. Economist-style analytical tone.",
  "key_points_ko": [
    {{
      "heading": "Concise Korean claim heading",
      "body": "KOREAN: 4-5 sentences. Claim -> evidence -> implication.",
      "source_chunks": [0, 2]
    }}
  ],
  "key_points_en": [
    {{
      "heading": "Concise English claim heading",
      "body": "ENGLISH: 4-5 sentences. Claim -> evidence -> implication.",
      "source_chunks": [0, 2]
    }}
  ],
  "notable_quote_ko": {{
    "text": "Korean translation of selected English quote",
    "attribution": "Speaker Name, Role"
  }},
  "notable_quote_en": {{
    "text": "Exact quote text copied from quote_candidates",
    "attribution": "Speaker Name, Role"
  }},
  "keywords_en": ["4-6 specific concepts or named entities"],
  "keywords_ko": ["4-6 keywords in Korean where natural, English for proper nouns/technical terms"]
}}

Coverage rules:
- Generate 4-5 key points for long transcripts.
- Every key point must include source_chunks as integer chunk indexes.
- Across all key points, source_chunks should cover the episode's major claims from beginning, middle, and end chunks.

<chunk_extractions>
{chunk_extractions}
</chunk_extractions>"""


def build_synthesis_prompt(episode, chunk_extractions, transcript_chars):
    """Build the episode synthesis prompt from compact extraction notes."""
    return SYNTHESIS_PROMPT.format(
        podcast=episode.get("podcast", ""),
        category=episode.get("category", ""),
        title=episode.get("title", ""),
        published=episode.get("published", ""),
        transcript_chars=transcript_chars,
        chunk_extractions=json.dumps(
            chunk_extractions,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )


def _reduction_ratio(transcript_chars, synthesis_prompt_chars):
    if not transcript_chars:
        return None
    return round(1 - (synthesis_prompt_chars / transcript_chars), 4)


def _write_synthesis_artifact(
    slug,
    generation,
    extraction,
    synthesis_prompt_chars,
    transcript_chars,
    intermediate_dir,
):
    artifact_dir = Path(intermediate_dir) / slug
    artifact_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_text = getattr(generation, "raw_text", "") or ""
    raw_path = None
    if raw_text:
        raw_path = raw_dir / "synthesis.txt"
        raw_path.write_text(raw_text, encoding="utf-8")

    ratio = _reduction_ratio(transcript_chars, synthesis_prompt_chars)
    report = {
        "slug": slug,
        "prompt_version": SYNTHESIS_PROMPT_VERSION,
        "provider": getattr(generation, "provider", ""),
        "model": getattr(generation, "model", ""),
        "transcript_chars": transcript_chars,
        "chunk_count": extraction.usage.get("chunk_count", 0),
        "cache_hits": extraction.usage.get("cache_hits", 0),
        "synthesis_prompt_chars": synthesis_prompt_chars,
        "synthesis_input_reduction_ratio": ratio,
        "parse_succeeded": getattr(generation, "parse_succeeded", False),
        "summary": getattr(generation, "summary", None),
        "errors": getattr(generation, "errors", []),
        "warnings": getattr(generation, "warnings", []),
        "raw_output_path": str(raw_path) if raw_path else None,
        "created_at": datetime.now().isoformat(),
    }

    path = artifact_dir / "synthesis.json"
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path), ratio


def summarize_long_episode_with_result(
    episode,
    transcript_text,
    slug,
    provider="claude",
    model=None,
    max_retries=2,
    cache_dir=None,
    intermediate_dir=None,
):
    """Summarize a long transcript through extraction then compact synthesis."""
    from summarize import SummaryGenerationResult, _effective_model
    from summarize import _generate_json_with_result

    model_name = _effective_model(provider, model)
    intermediate_dir = intermediate_dir or INTERMEDIATE_DIR

    extraction = extract_episode_chunks(
        episode,
        transcript_text,
        slug=slug,
        provider=provider,
        model=model_name,
        call_json=_generate_json_with_result,
        max_retries=1,
        cache_dir=cache_dir,
        intermediate_dir=intermediate_dir,
    )

    if not extraction.ok:
        return SummaryGenerationResult(
            summary=None,
            raw_text=extraction.raw_text,
            provider=provider,
            model=model_name,
            attempts=extraction.attempts,
            parse_succeeded=False,
            stage="extraction_failed",
            errors=extraction.errors,
            warnings=extraction.warnings,
            artifacts=extraction.artifacts,
            usage=extraction.usage,
        )

    synthesis_prompt = build_synthesis_prompt(
        episode,
        extraction.chunks,
        transcript_chars=len(transcript_text),
    )
    generation = _generate_json_with_result(
        synthesis_prompt,
        provider=provider,
        model=model_name,
        max_retries=max_retries,
        label="episode_synthesis",
    )

    synthesis_path, ratio = _write_synthesis_artifact(
        slug,
        generation,
        extraction,
        synthesis_prompt_chars=len(synthesis_prompt),
        transcript_chars=len(transcript_text),
        intermediate_dir=intermediate_dir,
    )

    warnings = list(extraction.warnings) + list(getattr(generation, "warnings", []))
    if ratio is not None and ratio < 0.6:
        warnings.append(
            "synthesis input reduction below target: "
            f"{ratio:.1%} vs expected >= 60.0%"
        )

    artifacts = dict(extraction.artifacts)
    artifacts["synthesis"] = synthesis_path

    usage = dict(extraction.usage)
    usage.update({
        "synthesis_prompt_chars": len(synthesis_prompt),
        "synthesis_input_reduction_ratio": ratio,
    })

    return SummaryGenerationResult(
        summary=generation.summary,
        raw_text=generation.raw_text,
        provider=generation.provider,
        model=generation.model,
        attempts=extraction.attempts + generation.attempts,
        parse_succeeded=generation.parse_succeeded,
        stage="episode_synthesis",
        errors=getattr(generation, "errors", []),
        warnings=warnings,
        artifacts=artifacts,
        usage=usage,
    )
