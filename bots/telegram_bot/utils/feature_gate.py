"""
Feature Gate Access Control Layer for PFAST_AI.

Connects the Feature Registry (metadata & defaults) with the
database feature_flags (runtime overrides), backed by a lightweight
in-memory TTL cache to prevent frequent database lookups.
"""

import time
from typing import Any, Dict, Optional

from database.db import get_feature_flag
from services.features.registry import get_feature_definition, validate_feature_exists


# Default cache TTL in seconds
CACHE_TTL_SECONDS = 60.0

# In-memory cache structure:
# { feature_name: { "data": dict_result, "cached_at": float_timestamp } }
_FEATURE_CACHE: Dict[str, Dict[str, Any]] = {}


def clear_feature_cache() -> None:
    """
    Invalidate the entire in-memory feature cache.
    Useful after an admin updates or toggles a feature flag.
    """
    global _FEATURE_CACHE
    _FEATURE_CACHE.clear()


def check_feature_access(feature_name: str) -> Dict[str, Any]:
    """
    Check if a feature is available for use.

    Evaluation hierarchy:
    1. Validation: Must exist in Feature Registry. Unknown features return allowed=False.
    2. Cache check: If valid non-expired cached result exists, return cached result.
    3. Database check: Read runtime state from feature_flags table in database.
    4. Fallback: If no database record exists, fallback to registry default_enabled state.

    Returns:
        {
            "allowed": bool,
            "feature": str,
            "message": Optional[str],
        }
    """
    raw_name = feature_name
    normalized_name = str(feature_name or "").strip().lower()

    if not normalized_name or not validate_feature_exists(normalized_name):
        return {
            "allowed": False,
            "feature": str(raw_name or ""),
            "message": "❌ قابلیت درخواستی در سامانه تعریف نشده است.",
        }

    now = time.time()

    # Check cache
    cached_entry = _FEATURE_CACHE.get(normalized_name)
    if cached_entry and (now - cached_entry["cached_at"] < CACHE_TTL_SECONDS):
        return dict(cached_entry["data"])

    # Load registry definition
    definition = get_feature_definition(normalized_name)
    if definition is None:
        return {
            "allowed": False,
            "feature": normalized_name,
            "message": "❌ قابلیت درخواستی در سامانه تعریف نشده است.",
        }

    # Query database for runtime override
    db_flag = get_feature_flag(normalized_name)

    if db_flag is not None:
        is_enabled = bool(db_flag.get("is_enabled", False))
        custom_message = str(db_flag.get("disabled_message") or "").strip()
        disabled_message = custom_message or definition["disabled_message"]
    else:
        # Fallback to registry default
        is_enabled = bool(definition.get("default_enabled", True))
        disabled_message = definition["disabled_message"]

    result = {
        "allowed": is_enabled,
        "feature": normalized_name,
        "message": None if is_enabled else disabled_message,
    }

    # Store in cache
    _FEATURE_CACHE[normalized_name] = {
        "data": dict(result),
        "cached_at": now,
    }

    return result


def is_feature_enabled(feature_name: str) -> bool:
    """
    Quick boolean helper to check if a feature is enabled.
    """
    return bool(check_feature_access(feature_name).get("allowed", False))

