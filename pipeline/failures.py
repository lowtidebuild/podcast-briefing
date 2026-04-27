"""Failure artifact writers for pipeline stages."""

import json
from datetime import datetime

from config import FAILURES_DIR


def write_summary_failure(episode, slug, generation_result, validation_result):
    """Persist a failed summary attempt and return the manifest path."""
    FAILURES_DIR.mkdir(parents=True, exist_ok=True)
    raw_dir = FAILURES_DIR / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_output_path = None
    raw_text = getattr(generation_result, "raw_text", "") or ""
    if raw_text:
        raw_output_path = raw_dir / f"{slug}.txt"
        raw_output_path.write_text(raw_text, encoding="utf-8")

    manifest = {
        "slug": slug,
        "episode_id": episode.get("id", ""),
        "podcast": episode.get("podcast", ""),
        "title": episode.get("title", ""),
        "published": episode.get("published", ""),
        "stage": getattr(generation_result, "stage", "summary_validation"),
        "provider": getattr(generation_result, "provider", ""),
        "model": getattr(generation_result, "model", ""),
        "attempts": getattr(generation_result, "attempts", 0),
        "errors": validation_result.errors,
        "warnings": validation_result.warnings,
        "generation_errors": getattr(generation_result, "errors", []),
        "generation_warnings": getattr(generation_result, "warnings", []),
        "artifacts": getattr(generation_result, "artifacts", {}),
        "usage": getattr(generation_result, "usage", {}),
        "raw_output_path": str(raw_output_path) if raw_output_path else None,
        "created_at": datetime.now().isoformat(),
    }

    failure_path = FAILURES_DIR / f"{slug}.json"
    with open(failure_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    return str(failure_path)
