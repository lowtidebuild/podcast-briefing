"""Canonical summary schema fields and defaults."""

SUMMARY_FIELDS = {
    "guest",
    "summary_ko",
    "summary_en",
    "key_points_ko",
    "key_points_en",
    "notable_quote_ko",
    "notable_quote_en",
    "notable_quote",
    "keywords_ko",
    "keywords_en",
}

OPTIONAL_SUMMARY_FIELDS = {
    "notable_quote",
}


def empty_summary():
    """Return the legacy empty summary shape for compatibility boundaries."""
    return {
        "guest": None,
        "summary_ko": "",
        "summary_en": "",
        "key_points_ko": [],
        "key_points_en": [],
        "notable_quote_ko": {"text": "", "attribution": ""},
        "notable_quote_en": {"text": "", "attribution": ""},
        "notable_quote": {
            "source_text_en": "",
            "translation_ko": "",
            "speaker": "",
            "attribution": "",
            "is_verbatim": False,
            "translation_is_verbatim": False,
            "source_char_start": None,
            "source_char_end": None,
            "match_score": 0.0,
        },
        "keywords_ko": [],
        "keywords_en": [],
    }
