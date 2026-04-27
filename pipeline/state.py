"""Pipeline state normalization and episode status transitions."""

from copy import deepcopy
from datetime import datetime


STATE_VERSION = 2

COMPLETED_STATUSES = {
    "published",
    "sheets_failed",
}

RETRYABLE_STATUSES = {
    "discovered",
    "downloaded",
    "transcribed",
    "extracted",
    "download_failed",
    "transcribe_failed",
    "transcript_save_failed",
    "summary_failed",
    "validation_failed",
    "publish_failed",
}


def _now():
    return datetime.now().isoformat()


def _base_episode_state(status="discovered"):
    return {
        "slug": None,
        "status": status,
        "last_stage": None,
        "attempts": 0,
        "last_error": None,
        "warnings": [],
        "artifacts": {},
        "usage": {},
        "updated_at": _now(),
    }


def normalize_state(raw_state):
    """Return canonical v2 state, migrating legacy processed lists."""
    if not isinstance(raw_state, dict):
        raw_state = {}

    episodes = deepcopy(raw_state.get("episodes", {}))
    if not isinstance(episodes, dict):
        episodes = {}

    legacy_processed = raw_state.get("processed", [])
    if isinstance(legacy_processed, list):
        for episode_id in legacy_processed:
            if not episode_id or episode_id in episodes:
                continue
            item = _base_episode_state(status="published")
            item["last_stage"] = "legacy_processed"
            item["attempts"] = 1
            episodes[episode_id] = item

    normalized = {
        "version": STATE_VERSION,
        "episodes": episodes,
    }

    for key, value in raw_state.items():
        if key not in {"version", "processed", "episodes"}:
            normalized[key] = value

    return normalized


def is_episode_complete(state, episode_id):
    """Return True when the episode should not be reprocessed by the main flow."""
    state = normalize_state(state)
    episode_state = state["episodes"].get(episode_id, {})
    return episode_state.get("status") in COMPLETED_STATUSES


def is_episode_retryable(state, episode_id):
    """Return True when the episode has a known retryable failure or partial state."""
    state = normalize_state(state)
    episode_state = state["episodes"].get(episode_id, {})
    return episode_state.get("status") in RETRYABLE_STATUSES


def update_episode_state(
    state,
    episode_id,
    status,
    slug=None,
    stage=None,
    error=None,
    warnings=None,
    artifacts=None,
    usage=None,
    increment_attempt=False,
):
    """Update one episode state entry and return the normalized state."""
    next_state = normalize_state(state)
    current = deepcopy(
        next_state["episodes"].get(episode_id, _base_episode_state())
    )

    current["status"] = status
    if slug is not None:
        current["slug"] = slug
    if stage is not None:
        current["last_stage"] = stage
    current["last_error"] = error
    current["updated_at"] = _now()

    if warnings is not None:
        current["warnings"] = list(warnings)
    if artifacts:
        merged = dict(current.get("artifacts", {}))
        merged.update(artifacts)
        current["artifacts"] = merged
    if usage:
        merged = dict(current.get("usage", {}))
        merged.update(usage)
        current["usage"] = merged

    if increment_attempt:
        current["attempts"] = int(current.get("attempts", 0) or 0) + 1

    next_state["episodes"][episode_id] = current
    return next_state
