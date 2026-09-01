"""
Feature Management Service for PFAST_AI.

Coordinates runtime feature operations between Feature Registry,
Database persistence, and Feature Gate cache invalidation.
"""

from typing import Any, Dict, List

from database.db import get_all_feature_flags, set_feature_flag
from services.features.registry import get_all_features, get_feature_definition
from utils.feature_gate import clear_feature_cache, is_feature_enabled


def list_features_with_status() -> List[Dict[str, Any]]:
    """
    Returns a unified list of all registered features alongside their current
    runtime status (enabled/disabled) and metadata.
    """
    registered = get_all_features()
    db_flags = get_all_feature_flags()

    result = []
    for name, meta in registered.items():
        db_record = db_flags.get(name)
        if db_record is not None:
            is_enabled = bool(db_record["is_enabled"])
            disabled_msg = db_record.get("disabled_message") or meta["disabled_message"]
        else:
            is_enabled = bool(meta.get("default_enabled", True))
            disabled_msg = meta["disabled_message"]

        result.append({
            "name": name,
            "display_name": meta.get("display_name", name),
            "category": meta.get("category", "general"),
            "is_enabled": is_enabled,
            "disabled_message": disabled_msg,
        })

    return result


def toggle_feature(feature_name: str) -> bool:
    """
    Toggles the enabled status of a feature, persists to database,
    and invalidates the Feature Gate cache.
    Returns the new is_enabled status.
    """
    feature_name = str(feature_name or "").strip().lower()
    meta = get_feature_definition(feature_name)
    if not meta:
        return False

    current_status = is_feature_enabled(feature_name)
    new_status = not current_status

    set_feature_flag(
        feature_name=feature_name,
        is_enabled=new_status,
        category=meta.get("category", "general"),
        display_name=meta.get("display_name", feature_name),
        disabled_message=meta.get("disabled_message", ""),
    )

    clear_feature_cache()
    return new_status


def set_feature_status(feature_name: str, enabled: bool) -> bool:
    """
    Explicitly enables or disables a feature, persists to database,
    and invalidates the Feature Gate cache.
    """
    feature_name = str(feature_name or "").strip().lower()
    meta = get_feature_definition(feature_name)
    if not meta:
        return False

    set_feature_flag(
        feature_name=feature_name,
        is_enabled=enabled,
        category=meta.get("category", "general"),
        display_name=meta.get("display_name", feature_name),
        disabled_message=meta.get("disabled_message", ""),
    )

    clear_feature_cache()
    return True

