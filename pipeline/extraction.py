"""Chunk-level extraction for long podcast transcripts."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from config import EXTRACTION_CACHE_DIR, INTERMEDIATE_DIR


LONG_TRANSCRIPT_THRESHOLD_CHARS = 80000
CHUNK_TARGET_CHARS = 36000
CHUNK_MIN_CHARS = 24000
CHUNK_MAX_CHARS = 44000
EXTRACTION_PROMPT_VERSION = "chunk-extraction-v1"


@dataclass
class TranscriptChunk:
    index: int
    char_start: int
    char_end: int
    text: str


@dataclass
class ExtractionRunResult:
    ok: bool
    chunks: list[dict]
    errors: list[str]
    warnings: list[str]
    cache_hits: int
    attempts: int
    raw_text: str
    artifacts: dict = field(default_factory=dict)
    usage: dict = field(default_factory=dict)


EXTRACTION_PROMPT = """You are extracting grounded analytical notes from one chunk of a podcast transcript.

Podcast: {podcast}
Category: {category}
Title: {title}
Published: {published}
Chunk: {chunk_index}/{chunk_count}
Character range: {char_start}-{char_end}

Rules:
- Use ONLY this chunk. Do not infer details from outside the chunk.
- Extract claims, evidence, speakers, topics, and direct quote candidates.
- A claim must be a proposition, not a topic label.
- Evidence should be concrete numbers, examples, named entities, or causal reasoning stated in the chunk.
- Quote candidates must be copied from the transcript text, not paraphrased.
- Keep output compact. Prefer fewer, denser items over exhaustive notes.

Output STRICTLY as valid JSON with this shape:

{{
  "topics": ["2-5 specific topic labels"],
  "claims": [
    {{
      "claim": "A concrete claim made or implied in this chunk",
      "evidence": ["1-3 concrete evidence items from the chunk"],
      "speakers": ["Speaker names if identifiable"]
    }}
  ],
  "quote_candidates": [
    {{
      "text": "verbatim quote from this chunk",
      "speaker": "Speaker name if identifiable, otherwise empty string",
      "char_start": null,
      "char_end": null
    }}
  ],
  "guest_candidates": [
    {{"name": "Guest full name in English", "title": "Role, Organization"}}
  ],
  "keyword_candidates": ["4-8 specific keywords or named entities"]
}}

<transcript_chunk>
{chunk_text}
</transcript_chunk>"""


def should_use_chunked_summary(transcript_text):
    """Return True when the transcript is long enough for extraction/synthesis."""
    return len(transcript_text or "") > LONG_TRANSCRIPT_THRESHOLD_CHARS


def _find_boundary(text, start, min_end, target_end, max_end):
    """Find a chunk boundary near target_end without cutting obvious structure."""
    for separator in ("\n\n", "\n", ". ", "? ", "! "):
        before = text.rfind(separator, min_end, target_end)
        if before != -1:
            return before + len(separator)
        after = text.find(separator, target_end, max_end)
        if after != -1:
            return after + len(separator)
    return max_end


def chunk_transcript(
    transcript_text,
    target_chars=CHUNK_TARGET_CHARS,
    min_chars=CHUNK_MIN_CHARS,
    max_chars=CHUNK_MAX_CHARS,
):
    """Split transcript into contiguous chunks, preferring paragraph boundaries."""
    if not transcript_text:
        return []
    if target_chars <= 0 or min_chars <= 0 or max_chars <= 0:
        raise ValueError("chunk sizes must be positive")
    if min_chars > target_chars or target_chars > max_chars:
        raise ValueError("chunk sizes must satisfy min <= target <= max")

    chunks = []
    start = 0
    text_len = len(transcript_text)

    while start < text_len:
        remaining = text_len - start
        if remaining <= max_chars:
            end = text_len
        else:
            min_end = min(text_len, start + min_chars)
            target_end = min(text_len, start + target_chars)
            max_end = min(text_len, start + max_chars)
            end = _find_boundary(transcript_text, start, min_end, target_end, max_end)
            if end <= start:
                end = max_end

        chunks.append(
            TranscriptChunk(
                index=len(chunks),
                char_start=start,
                char_end=end,
                text=transcript_text[start:end],
            )
        )
        start = end

    return chunks


def _transcript_hash(transcript_text):
    return hashlib.sha256(transcript_text.encode("utf-8")).hexdigest()


def _chunk_hash(chunk):
    return hashlib.sha256(chunk.text.encode("utf-8")).hexdigest()


def chunk_cache_key(transcript_text, chunk, provider, model):
    """Build a deterministic cache key for one extraction chunk."""
    material = "\n".join([
        EXTRACTION_PROMPT_VERSION,
        provider or "",
        model or "",
        _transcript_hash(transcript_text),
        str(chunk.index),
        str(chunk.char_start),
        str(chunk.char_end),
        _chunk_hash(chunk),
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _as_string_list(value):
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _sanitize_extraction(payload, chunk):
    errors = []
    warnings = []

    if not isinstance(payload, dict):
        return None, ["chunk extraction is not an object"], warnings

    topics = _as_string_list(payload.get("topics"))[:8]
    keyword_candidates = _as_string_list(payload.get("keyword_candidates"))[:12]

    claims = []
    raw_claims = payload.get("claims", [])
    if not isinstance(raw_claims, list):
        errors.append("claims must be a list")
        raw_claims = []

    for idx, item in enumerate(raw_claims[:8]):
        if not isinstance(item, dict):
            warnings.append(f"claims[{idx}] stripped because it is not an object")
            continue
        claim = item.get("claim", "")
        if not isinstance(claim, str) or not claim.strip():
            warnings.append(f"claims[{idx}] stripped because claim is empty")
            continue
        claims.append({
            "claim": claim.strip(),
            "evidence": _as_string_list(item.get("evidence"))[:4],
            "speakers": _as_string_list(item.get("speakers"))[:4],
        })

    quote_candidates = []
    raw_quotes = payload.get("quote_candidates", [])
    if not isinstance(raw_quotes, list):
        errors.append("quote_candidates must be a list")
        raw_quotes = []

    for idx, item in enumerate(raw_quotes[:6]):
        if not isinstance(item, dict):
            warnings.append(
                f"quote_candidates[{idx}] stripped because it is not an object"
            )
            continue
        text = item.get("text", "")
        if not isinstance(text, str) or not text.strip():
            warnings.append(
                f"quote_candidates[{idx}] stripped because text is empty"
            )
            continue
        char_start = item.get("char_start")
        char_end = item.get("char_end")
        quote_candidates.append({
            "text": text.strip(),
            "speaker": item.get("speaker", "").strip()
            if isinstance(item.get("speaker"), str) else "",
            "char_start": char_start if isinstance(char_start, int) else None,
            "char_end": char_end if isinstance(char_end, int) else None,
        })

    guest_candidates = []
    raw_guests = payload.get("guest_candidates", [])
    if isinstance(raw_guests, list):
        for idx, item in enumerate(raw_guests[:5]):
            if not isinstance(item, dict):
                warnings.append(
                    f"guest_candidates[{idx}] stripped because it is not an object"
                )
                continue
            name = item.get("name", "")
            if not isinstance(name, str) or not name.strip():
                continue
            title = item.get("title", "")
            guest_candidates.append({
                "name": name.strip(),
                "title": title.strip() if isinstance(title, str) else "",
            })
    elif raw_guests is not None:
        warnings.append("guest_candidates stripped because it is not a list")

    if not topics and not claims:
        warnings.append("chunk produced no topics or claims")

    sanitized = {
        "chunk_index": chunk.index,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "topics": topics,
        "claims": claims,
        "quote_candidates": quote_candidates,
        "guest_candidates": guest_candidates,
        "keyword_candidates": keyword_candidates,
    }

    return sanitized, errors, warnings


def _load_cached_extraction(cache_path, chunk):
    if not cache_path.exists():
        return None, [], []
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None, [], ["invalid extraction cache ignored"]

    extraction = cached.get("extraction")
    sanitized, errors, warnings = _sanitize_extraction(extraction, chunk)
    if errors:
        return None, [], [f"invalid extraction cache ignored: {', '.join(errors)}"]
    return sanitized, [], warnings


def _write_cache(cache_path, transcript_text, chunk, provider, model, extraction):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "prompt_version": EXTRACTION_PROMPT_VERSION,
        "provider": provider,
        "model": model,
        "transcript_hash": _transcript_hash(transcript_text),
        "chunk_hash": _chunk_hash(chunk),
        "chunk_index": chunk.index,
        "char_start": chunk.char_start,
        "char_end": chunk.char_end,
        "extraction": extraction,
        "created_at": datetime.now().isoformat(),
    }
    cache_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_extraction_prompt(episode, chunk, chunk_count):
    return EXTRACTION_PROMPT.format(
        podcast=episode.get("podcast", ""),
        category=episode.get("category", ""),
        title=episode.get("title", ""),
        published=episode.get("published", ""),
        chunk_index=chunk.index + 1,
        chunk_count=chunk_count,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        chunk_text=chunk.text,
    )


def _artifact_dir(slug, intermediate_dir):
    path = Path(intermediate_dir) / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def extract_episode_chunks(
    episode,
    transcript_text,
    slug,
    provider,
    model,
    call_json,
    max_retries=1,
    cache_dir=None,
    intermediate_dir=None,
    target_chars=CHUNK_TARGET_CHARS,
    min_chars=CHUNK_MIN_CHARS,
    max_chars=CHUNK_MAX_CHARS,
):
    """Extract grounded chunk notes with per-chunk cache reuse."""
    cache_dir = Path(cache_dir or EXTRACTION_CACHE_DIR)
    intermediate_dir = Path(intermediate_dir or INTERMEDIATE_DIR)
    artifact_dir = _artifact_dir(slug, intermediate_dir)
    raw_dir = artifact_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    chunks = chunk_transcript(
        transcript_text,
        target_chars=target_chars,
        min_chars=min_chars,
        max_chars=max_chars,
    )
    chunk_count = len(chunks)
    extracted = []
    raw_outputs = []
    errors = []
    warnings = []
    cache_hits = 0
    attempts = 0
    prompt_input_chars = 0

    for chunk in chunks:
        key = chunk_cache_key(transcript_text, chunk, provider, model)
        cache_path = cache_dir / f"{key}.json"
        cached, _, cache_warnings = _load_cached_extraction(cache_path, chunk)
        warnings.extend(
            f"chunk {chunk.index}: {warning}" for warning in cache_warnings
        )
        if cached is not None:
            cache_hits += 1
            extracted.append(cached)
            continue

        prompt = _build_extraction_prompt(episode, chunk, chunk_count)
        prompt_input_chars += len(prompt)
        generation = call_json(
            prompt,
            provider=provider,
            model=model,
            max_retries=max_retries,
            label=f"chunk_extraction[{chunk.index}]",
        )
        attempts += getattr(generation, "attempts", 0)

        raw_text = getattr(generation, "raw_text", "") or ""
        if raw_text:
            raw_outputs.append(raw_text)
            (raw_dir / f"chunk-{chunk.index}.txt").write_text(
                raw_text,
                encoding="utf-8",
            )

        if not getattr(generation, "parse_succeeded", False):
            errors.append(f"chunk {chunk.index} extraction failed to parse")
            continue

        sanitized, item_errors, item_warnings = _sanitize_extraction(
            getattr(generation, "summary", None),
            chunk,
        )
        warnings.extend(
            f"chunk {chunk.index}: {warning}" for warning in item_warnings
        )
        if item_errors:
            errors.extend(
                f"chunk {chunk.index}: {error}" for error in item_errors
            )
            continue

        _write_cache(cache_path, transcript_text, chunk, provider, model, sanitized)
        extracted.append(sanitized)

    chunks_path = artifact_dir / "chunks.json"
    chunks_path.write_text(
        json.dumps(extracted, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = {
        "slug": slug,
        "prompt_version": EXTRACTION_PROMPT_VERSION,
        "provider": provider,
        "model": model,
        "transcript_chars": len(transcript_text),
        "chunk_count": chunk_count,
        "extracted_chunk_count": len(extracted),
        "cache_hits": cache_hits,
        "attempts": attempts,
        "prompt_input_chars": prompt_input_chars,
        "errors": errors,
        "warnings": warnings,
        "created_at": datetime.now().isoformat(),
    }
    report_path = artifact_dir / "extraction_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return ExtractionRunResult(
        ok=not errors and len(extracted) == chunk_count,
        chunks=extracted,
        errors=errors,
        warnings=warnings,
        cache_hits=cache_hits,
        attempts=attempts,
        raw_text="\n\n---\n\n".join(raw_outputs),
        artifacts={
            "chunks": str(chunks_path),
            "extraction_report": str(report_path),
            "raw_dir": str(raw_dir),
        },
        usage={
            "transcript_chars": len(transcript_text),
            "chunk_count": chunk_count,
            "extracted_chunk_count": len(extracted),
            "cache_hits": cache_hits,
            "extraction_prompt_input_chars": prompt_input_chars,
        },
    )
