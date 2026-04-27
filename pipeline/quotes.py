"""Quote grounding against source transcripts."""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from config import INTERMEDIATE_DIR


QUOTE_MATCH_THRESHOLD = 0.84


@dataclass
class QuoteMatch:
    matched: bool
    source_text: str = ""
    char_start: int | None = None
    char_end: int | None = None
    score: float = 0.0


@dataclass
class QuoteGroundingResult:
    summary: dict
    quote: dict
    warnings: list[str]
    report_path: str | None = None
    usage: dict = field(default_factory=dict)


def _normalize_quotes(text):
    return (
        text.replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
        .replace("—", "-")
        .replace("–", "-")
    )


def _tokenize_with_spans(text):
    normalized = unicodedata.normalize("NFKC", _normalize_quotes(text))
    return [
        (match.group(0).casefold(), match.start(), match.end())
        for match in re.finditer(
            r"[a-z0-9]+(?:'[a-z0-9]+)?",
            normalized,
            flags=re.IGNORECASE,
        )
    ]


def _compact_text(text):
    return " ".join(token for token, _, _ in _tokenize_with_spans(text))


def _score_tokens(left, right):
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, " ".join(left), " ".join(right)).ratio()


def _candidate_starts(transcript_tokens, quote_tokens):
    positions = defaultdict(list)
    frequencies = Counter(token for token, _, _ in transcript_tokens)
    for idx, (token, _, _) in enumerate(transcript_tokens):
        positions[token].append(idx)

    anchors = [
        (frequencies[token], quote_idx, token)
        for quote_idx, token in enumerate(quote_tokens)
        if len(token) > 3 and frequencies[token] > 0
    ]
    if not anchors:
        return range(max(1, len(transcript_tokens) - len(quote_tokens) + 1))

    _, quote_anchor_idx, anchor = min(anchors)
    starts = set()
    for transcript_anchor_idx in positions[anchor]:
        start = transcript_anchor_idx - quote_anchor_idx
        if 0 <= start < len(transcript_tokens):
            starts.add(start)
    return sorted(starts)


def find_quote_match(
    quote_text,
    transcript_text,
    threshold=QUOTE_MATCH_THRESHOLD,
):
    """Find the best fuzzy match for an English quote in the transcript."""
    if not quote_text or not transcript_text:
        return QuoteMatch(matched=False)

    transcript_tokens = _tokenize_with_spans(transcript_text)
    quote_tokens_with_spans = _tokenize_with_spans(quote_text)
    quote_tokens = [token for token, _, _ in quote_tokens_with_spans]
    if not quote_tokens or not transcript_tokens:
        return QuoteMatch(matched=False)

    compact_quote = " ".join(quote_tokens)
    compact_transcript = _compact_text(transcript_text)
    if compact_quote and compact_quote in compact_transcript:
        for start in _candidate_starts(transcript_tokens, quote_tokens):
            end = start + len(quote_tokens)
            if end > len(transcript_tokens):
                continue
            window = [token for token, _, _ in transcript_tokens[start:end]]
            if window == quote_tokens:
                char_start = transcript_tokens[start][1]
                char_end = transcript_tokens[end - 1][2]
                return QuoteMatch(
                    matched=True,
                    source_text=transcript_text[char_start:char_end].strip(),
                    char_start=char_start,
                    char_end=char_end,
                    score=1.0,
                )

    best = QuoteMatch(matched=False)
    base_len = len(quote_tokens)
    spread = max(2, base_len // 5)
    lengths = sorted({
        max(1, base_len - spread),
        base_len,
        min(len(transcript_tokens), base_len + spread),
    })

    for start in _candidate_starts(transcript_tokens, quote_tokens):
        for length in lengths:
            end = start + length
            if end > len(transcript_tokens):
                continue
            window = [token for token, _, _ in transcript_tokens[start:end]]
            score = _score_tokens(quote_tokens, window)
            if score > best.score:
                char_start = transcript_tokens[start][1]
                char_end = transcript_tokens[end - 1][2]
                best = QuoteMatch(
                    matched=score >= threshold,
                    source_text=transcript_text[char_start:char_end].strip(),
                    char_start=char_start,
                    char_end=char_end,
                    score=round(score, 4),
                )

    if best.score < threshold:
        best.matched = False
    return best


def _quote_text(summary, field):
    quote = summary.get(field, {})
    if not isinstance(quote, dict):
        return "", ""
    text = quote.get("text", "")
    attribution = quote.get("attribution", "")
    return (
        text.strip() if isinstance(text, str) else "",
        attribution.strip() if isinstance(attribution, str) else "",
    )


def _speaker_from_attribution(attribution):
    if not attribution:
        return ""
    return attribution.split(",", 1)[0].strip()


def _grounded_quote_payload(summary, match):
    en_text, en_attr = _quote_text(summary, "notable_quote_en")
    ko_text, ko_attr = _quote_text(summary, "notable_quote_ko")
    attribution = en_attr or ko_attr
    source_text = match.source_text if match.matched else en_text

    return {
        "source_text_en": source_text,
        "translation_ko": ko_text,
        "speaker": _speaker_from_attribution(attribution),
        "attribution": attribution,
        "is_verbatim": bool(match.matched),
        "translation_is_verbatim": False,
        "source_char_start": match.char_start if match.matched else None,
        "source_char_end": match.char_end if match.matched else None,
        "match_score": round(match.score, 4),
    }


def _write_report(slug, quote, warnings, transcript_chars, report_dir):
    if not slug:
        return None
    path = Path(report_dir or INTERMEDIATE_DIR) / slug
    path.mkdir(parents=True, exist_ok=True)
    report_path = path / "quote_grounding.json"
    report = {
        "slug": slug,
        "transcript_chars": transcript_chars,
        "is_verbatim": quote["is_verbatim"],
        "match_score": quote["match_score"],
        "source_char_start": quote["source_char_start"],
        "source_char_end": quote["source_char_end"],
        "warnings": warnings,
        "created_at": datetime.now().isoformat(),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(report_path)


def ground_summary_quote(summary, transcript_text, slug=None, report_dir=None):
    """Attach canonical quote grounding metadata to a generated summary."""
    next_summary = dict(summary or {})
    warnings = []
    en_text, _ = _quote_text(next_summary, "notable_quote_en")

    match = find_quote_match(en_text, transcript_text)
    quote = _grounded_quote_payload(next_summary, match)
    if en_text and not match.matched:
        warnings.append(
            "notable_quote_en was not grounded in transcript "
            f"(best score={match.score:.2f})"
        )

    next_summary["notable_quote"] = quote
    if match.matched:
        next_summary["notable_quote_en"] = {
            "text": quote["source_text_en"],
            "attribution": quote["attribution"],
        }

    report_path = _write_report(
        slug,
        quote,
        warnings,
        transcript_chars=len(transcript_text or ""),
        report_dir=report_dir,
    )

    return QuoteGroundingResult(
        summary=next_summary,
        quote=quote,
        warnings=warnings,
        report_path=report_path,
        usage={
            "quote_is_verbatim": quote["is_verbatim"],
            "quote_match_score": quote["match_score"],
        },
    )
