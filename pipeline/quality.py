"""Summary validation and sanitization helpers."""

from dataclasses import dataclass

from schema import OPTIONAL_SUMMARY_FIELDS, SUMMARY_FIELDS


@dataclass
class ValidationResult:
    """Result of validating an LLM summary payload."""

    ok: bool
    errors: list[str]
    warnings: list[str]
    sanitized_summary: dict | None = None


def _is_nonempty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _looks_like_json_fragment(value):
    if not isinstance(value, str):
        return False
    stripped = value.strip()
    if stripped.startswith("{") or stripped.startswith("[") or stripped.startswith("```"):
        return True
    probe = stripped[:500]
    return '"summary_ko"' in probe or '"summary_en"' in probe


def summary_text_errors(summary, min_chars=100):
    """Return hard text-quality errors for summary fields."""
    errors = []
    if not isinstance(summary, dict):
        return ["summary is not an object"]

    for field in ("summary_ko", "summary_en"):
        value = summary.get(field, "")
        if not isinstance(value, str):
            errors.append(f"{field} must be a string")
            continue
        if len(value.strip()) < min_chars:
            errors.append(f"{field} is shorter than {min_chars} characters")
        if _looks_like_json_fragment(value):
            errors.append(f"{field} looks like a JSON fragment")

    return errors


def _sanitize_key_points(value, field, errors, warnings):
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []

    sanitized = []
    for idx, point in enumerate(value):
        if not isinstance(point, dict):
            errors.append(f"{field}[{idx}] must be an object")
            continue
        heading = point.get("heading", "")
        body = point.get("body", "")
        if not _is_nonempty_string(heading):
            errors.append(f"{field}[{idx}].heading is empty")
        if not _is_nonempty_string(body):
            errors.append(f"{field}[{idx}].body is empty")
        item = {
            "heading": heading.strip() if isinstance(heading, str) else "",
            "body": body.strip() if isinstance(body, str) else "",
        }
        source_chunks = point.get("source_chunks")
        if source_chunks is not None:
            clean_chunks = [
                chunk for chunk in source_chunks
                if isinstance(chunk, int) and chunk >= 0
            ] if isinstance(source_chunks, list) else []
            if clean_chunks:
                item["source_chunks"] = sorted(set(clean_chunks))
            else:
                warnings.append(
                    f"{field}[{idx}].source_chunks stripped because it is invalid"
                )
        sanitized.append(item)
    return sanitized


def _sanitize_quote(value, field, errors):
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {"text": "", "attribution": ""}

    text = value.get("text", "")
    attribution = value.get("attribution", "")
    if not _is_nonempty_string(text):
        errors.append(f"{field}.text is empty")
    if not _is_nonempty_string(attribution):
        errors.append(f"{field}.attribution is empty")
    return {
        "text": text.strip() if isinstance(text, str) else "",
        "attribution": attribution.strip() if isinstance(attribution, str) else "",
    }


def _sanitize_grounded_quote(value, warnings):
    if value is None:
        return None
    if not isinstance(value, dict):
        warnings.append("notable_quote stripped because it is not an object")
        return None

    def string_field(name):
        item = value.get(name, "")
        return item.strip() if isinstance(item, str) else ""

    def bool_field(name):
        return value.get(name) is True

    def int_or_none(name):
        item = value.get(name)
        return item if isinstance(item, int) and item >= 0 else None

    score = value.get("match_score", 0.0)
    if not isinstance(score, (int, float)):
        score = 0.0
    score = min(1.0, max(0.0, float(score)))

    is_verbatim = bool_field("is_verbatim")
    source_char_start = int_or_none("source_char_start")
    source_char_end = int_or_none("source_char_end")
    if is_verbatim and (
        source_char_start is None
        or source_char_end is None
        or source_char_end <= source_char_start
    ):
        warnings.append("notable_quote marked non-verbatim because source range is invalid")
        is_verbatim = False
        source_char_start = None
        source_char_end = None

    return {
        "source_text_en": string_field("source_text_en"),
        "translation_ko": string_field("translation_ko"),
        "speaker": string_field("speaker"),
        "attribution": string_field("attribution"),
        "is_verbatim": is_verbatim,
        "translation_is_verbatim": bool_field("translation_is_verbatim"),
        "source_char_start": source_char_start,
        "source_char_end": source_char_end,
        "match_score": round(score, 4),
    }


def _sanitize_keywords(value, field, errors):
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _sanitize_guest(value, errors, warnings):
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.append("guest must be null or an object")
        return None

    name = value.get("name")
    title = value.get("title", "")
    if not _is_nonempty_string(name):
        warnings.append("guest object without a name normalized to null")
        return None
    if title is None:
        title = ""
    if not isinstance(title, str):
        errors.append("guest.title must be a string")
        title = ""

    return {
        "name": name.strip() if isinstance(name, str) else "",
        "title": title.strip(),
    }


def validate_summary(summary, raw_text=None, min_summary_chars=100):
    """Validate and sanitize a generated summary.

    Hard failures are intentionally narrow for the first gate: empty summaries,
    JSON-fragment summaries, invalid guest shape, missing key point content, and
    missing quote content. Lower-frequency schema polish issues are warnings.
    """
    errors = []
    warnings = []

    if summary is None:
        return ValidationResult(
            ok=False,
            errors=["summary parsing failed"],
            warnings=[],
            sanitized_summary=None,
        )

    if not isinstance(summary, dict):
        return ValidationResult(
            ok=False,
            errors=["summary is not an object"],
            warnings=[],
            sanitized_summary=None,
        )

    extra_fields = sorted(set(summary) - SUMMARY_FIELDS)
    if extra_fields:
        warnings.append(f"extra fields stripped: {', '.join(extra_fields)}")

    for field in SUMMARY_FIELDS - {"guest"} - OPTIONAL_SUMMARY_FIELDS:
        if field not in summary:
            errors.append(f"{field} is missing")

    errors.extend(summary_text_errors(summary, min_chars=min_summary_chars))

    sanitized = {
        "guest": _sanitize_guest(summary.get("guest"), errors, warnings),
        "summary_ko": summary.get("summary_ko", "").strip()
        if isinstance(summary.get("summary_ko"), str) else "",
        "summary_en": summary.get("summary_en", "").strip()
        if isinstance(summary.get("summary_en"), str) else "",
        "key_points_ko": _sanitize_key_points(
            summary.get("key_points_ko", []), "key_points_ko", errors, warnings
        ),
        "key_points_en": _sanitize_key_points(
            summary.get("key_points_en", []), "key_points_en", errors, warnings
        ),
        "notable_quote_ko": _sanitize_quote(
            summary.get("notable_quote_ko", {}), "notable_quote_ko", errors
        ),
        "notable_quote_en": _sanitize_quote(
            summary.get("notable_quote_en", {}), "notable_quote_en", errors
        ),
        "notable_quote": _sanitize_grounded_quote(
            summary.get("notable_quote"), warnings
        ),
        "keywords_ko": _sanitize_keywords(
            summary.get("keywords_ko", []), "keywords_ko", errors
        ),
        "keywords_en": _sanitize_keywords(
            summary.get("keywords_en", []), "keywords_en", errors
        ),
    }

    if len(sanitized["key_points_ko"]) < 1:
        errors.append("key_points_ko must contain at least 1 item")
    if len(sanitized["key_points_en"]) < 1:
        errors.append("key_points_en must contain at least 1 item")

    if len(sanitized["key_points_ko"]) != len(sanitized["key_points_en"]):
        warnings.append(
            "key point language counts differ: "
            f"ko={len(sanitized['key_points_ko'])}, "
            f"en={len(sanitized['key_points_en'])}"
        )

    for field in ("key_points_ko", "key_points_en"):
        count = len(sanitized[field])
        if count < 2 or count > 5:
            warnings.append(f"{field} has {count} items; expected 2-5")

    for field in ("keywords_ko", "keywords_en"):
        count = len(sanitized[field])
        if count < 4 or count > 6:
            warnings.append(f"{field} has {count} items; expected 4-6")

    return ValidationResult(
        ok=not errors,
        errors=errors,
        warnings=warnings,
        sanitized_summary=sanitized if not errors else None,
    )
